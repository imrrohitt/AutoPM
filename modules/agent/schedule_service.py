"""CRUD and Celery-triggered execution for story agent schedules."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, NotFoundError
from modules.agent.models import AgentRun, StoryAgentSchedule
from modules.agent.schedule_utils import compute_next_run_at
from modules.agent.schemas import (
    AgentRunResponse,
    StoryAgentScheduleCreate,
    StoryAgentScheduleResponse,
    StoryAgentScheduleUpdate,
)
from modules.agent.service import AgentService
from modules.stories.models import Story
from modules.users.models import User

logger = logging.getLogger(__name__)

VALID_SCHEDULE_TYPES = frozenset({"once", "daily", "weekly"})


class StoryAgentScheduleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_story(self, user: User, story_id: uuid.UUID) -> list[StoryAgentScheduleResponse]:
        await AgentService(self.db)._ensure_story_access_by_story(user, story_id)
        result = await self.db.execute(
            select(StoryAgentSchedule)
            .where(StoryAgentSchedule.story_id == story_id)
            .order_by(StoryAgentSchedule.created_at.desc())
        )
        schedules = list(result.scalars().all())
        return [await self._to_response(s) for s in schedules]

    async def create(
        self,
        user: User,
        project_id: uuid.UUID,
        story_id: uuid.UUID,
        body: StoryAgentScheduleCreate,
    ) -> StoryAgentScheduleResponse:
        story = await self._get_story(story_id)
        if story.project_id != project_id:
            raise NotFoundError("Story not found")
        await AgentService(self.db)._ensure_story_access(user, project_id)

        schedule_type = body.schedule_type
        if schedule_type not in VALID_SCHEDULE_TYPES:
            raise ConflictError("schedule_type must be once, daily, or weekly")

        run_at = _ensure_utc(body.run_at)
        if schedule_type == "once" and run_at <= datetime.now(timezone.utc):
            raise ConflictError("Scheduled time must be in the future")

        next_run = compute_next_run_at(
            schedule_type=schedule_type,
            run_at=run_at,
            weekdays=body.weekdays,
            tz_name=body.timezone,
        )
        if next_run is None:
            raise ConflictError("Could not compute next run time for this schedule")

        schedule = StoryAgentSchedule(
            story_id=story_id,
            project_id=project_id,
            created_by=user.id,
            label=body.label,
            schedule_type=schedule_type,
            run_at=run_at,
            weekdays=body.weekdays,
            timezone=body.timezone or "UTC",
            enabled=True,
            next_run_at=next_run,
        )
        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)
        return await self._to_response(schedule)

    async def update(
        self,
        user: User,
        schedule_id: uuid.UUID,
        body: StoryAgentScheduleUpdate,
    ) -> StoryAgentScheduleResponse:
        schedule = await self._get_schedule(schedule_id)
        await AgentService(self.db)._ensure_story_access_by_story(user, schedule.story_id)

        if body.label is not None:
            schedule.label = body.label
        if body.enabled is not None:
            schedule.enabled = body.enabled
        if body.run_at is not None:
            schedule.run_at = _ensure_utc(body.run_at)
        if body.weekdays is not None:
            schedule.weekdays = body.weekdays
        if body.timezone is not None:
            schedule.timezone = body.timezone
        if body.schedule_type is not None:
            if body.schedule_type not in VALID_SCHEDULE_TYPES:
                raise ConflictError("schedule_type must be once, daily, or weekly")
            schedule.schedule_type = body.schedule_type

        if schedule.enabled:
            next_run = compute_next_run_at(
                schedule_type=schedule.schedule_type,
                run_at=schedule.run_at,
                weekdays=schedule.weekdays,
                tz_name=schedule.timezone,
            )
            if next_run is None and schedule.schedule_type == "once":
                schedule.enabled = False
                schedule.next_run_at = schedule.run_at
            elif next_run is not None:
                schedule.next_run_at = next_run

        schedule.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(schedule)
        return await self._to_response(schedule)

    async def delete(self, user: User, schedule_id: uuid.UUID) -> None:
        schedule = await self._get_schedule(schedule_id)
        await AgentService(self.db)._ensure_story_access_by_story(user, schedule.story_id)
        await self.db.delete(schedule)
        await self.db.commit()

    async def list_history(
        self, user: User, schedule_id: uuid.UUID
    ) -> list[AgentRunResponse]:
        schedule = await self._get_schedule(schedule_id)
        await AgentService(self.db)._ensure_story_access_by_story(user, schedule.story_id)
        result = await self.db.execute(
            select(AgentRun)
            .where(AgentRun.schedule_id == schedule_id)
            .order_by(AgentRun.created_at.desc())
        )
        return [AgentRunResponse.model_validate(r) for r in result.scalars().all()]

    async def process_due_schedules(self, limit: int = 20) -> int:
        """Claim due schedules and queue agent runs. Returns count triggered."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(StoryAgentSchedule)
            .where(
                StoryAgentSchedule.enabled.is_(True),
                StoryAgentSchedule.next_run_at <= now,
            )
            .order_by(StoryAgentSchedule.next_run_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        due = list(result.scalars().all())
        triggered = 0

        for schedule in due:
            run = await self._trigger_schedule(schedule)
            if run is not None:
                triggered += 1

        await self.db.commit()
        return triggered

    async def _trigger_schedule(self, schedule: StoryAgentSchedule) -> AgentRun | None:
        agent = AgentService(self.db)
        try:
            run = await agent.queue_story_run_scheduled(
                schedule.project_id,
                schedule.story_id,
                schedule_id=schedule.id,
            )
        except ConflictError as exc:
            logger.info("schedule %s skipped: %s", schedule.id, exc)
            return None

        now = datetime.now(timezone.utc)
        schedule.last_triggered_at = now
        schedule.last_run_id = run.id

        if schedule.schedule_type == "once":
            schedule.enabled = False
            schedule.next_run_at = schedule.run_at
        else:
            schedule.next_run_at = compute_next_run_at(
                schedule_type=schedule.schedule_type,
                run_at=schedule.run_at,
                weekdays=schedule.weekdays,
                tz_name=schedule.timezone,
                after=now,
            ) or now

        schedule.updated_at = now
        return run

    async def _to_response(self, schedule: StoryAgentSchedule) -> StoryAgentScheduleResponse:
        last_run_status = None
        if schedule.last_run_id:
            res = await self.db.execute(
                select(AgentRun.status).where(AgentRun.id == schedule.last_run_id)
            )
            last_run_status = res.scalar_one_or_none()

        count = await self.db.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(AgentRun.schedule_id == schedule.id)
        )
        count = int(count or 0)

        return StoryAgentScheduleResponse(
            id=schedule.id,
            story_id=schedule.story_id,
            project_id=schedule.project_id,
            created_by=schedule.created_by,
            label=schedule.label,
            schedule_type=schedule.schedule_type,
            run_at=schedule.run_at,
            weekdays=schedule.weekdays,
            timezone=schedule.timezone,
            enabled=schedule.enabled,
            next_run_at=schedule.next_run_at,
            last_triggered_at=schedule.last_triggered_at,
            last_run_id=schedule.last_run_id,
            last_run_status=last_run_status,
            run_count=count,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )

    async def _get_schedule(self, schedule_id: uuid.UUID) -> StoryAgentSchedule:
        result = await self.db.execute(
            select(StoryAgentSchedule).where(StoryAgentSchedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()
        if not schedule:
            raise NotFoundError("Schedule not found")
        return schedule

    async def _get_story(self, story_id: uuid.UUID) -> Story:
        result = await self.db.execute(select(Story).where(Story.id == story_id))
        story = result.scalar_one_or_none()
        if not story:
            raise NotFoundError("Story not found")
        return story


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
