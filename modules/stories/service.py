import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ForbiddenError, NotFoundError
from modules.projects.models import Project, ProjectMember
from modules.stories.models import Story
from modules.stories.schemas import StoryCreate, StoryDetailResponse, StoryResponse, StoryUpdate
from modules.tickets.models import Ticket
from modules.tickets.schemas import TicketSummary
from modules.users.models import User


class StoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _ensure_project_access(self, user: User, project_id: uuid.UUID) -> Project:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.company_id == user.company_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project not found")
        if user.global_role in ("owner", "admin"):
            return project
        member = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            )
        )
        if not member.scalar_one_or_none():
            raise ForbiddenError()
        return project

    async def list_stories(self, user: User, project_id: uuid.UUID) -> list[StoryResponse]:
        await self._ensure_project_access(user, project_id)
        result = await self.db.execute(
            select(Story).where(Story.project_id == project_id).order_by(Story.created_at.desc())
        )
        return [StoryResponse.model_validate(s) for s in result.scalars().all()]

    async def create(self, user: User, project_id: uuid.UUID, payload: StoryCreate) -> StoryResponse:
        await self._ensure_project_access(user, project_id)
        if user.global_role not in ("owner", "admin"):
            member = await self.db.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == user.id,
                )
            )
            m = member.scalar_one_or_none()
            if not m or m.role != "manager":
                raise ForbiddenError()

        story = Story(
            project_id=project_id,
            title=payload.title,
            description=payload.description,
            acceptance_criteria=payload.acceptance_criteria,
            priority=payload.priority,
            auto_merge=payload.auto_merge,
            created_by=user.id,
        )
        self.db.add(story)
        await self.db.commit()
        await self.db.refresh(story)
        return StoryResponse.model_validate(story)

    async def get_story(self, user: User, project_id: uuid.UUID, story_id: uuid.UUID) -> StoryDetailResponse:
        await self._ensure_project_access(user, project_id)
        result = await self.db.execute(
            select(Story).where(Story.id == story_id, Story.project_id == project_id)
        )
        story = result.scalar_one_or_none()
        if not story:
            raise NotFoundError("Story not found")

        tickets_result = await self.db.execute(
            select(Ticket).where(Ticket.story_id == story_id).order_by(Ticket.created_at)
        )
        tickets = [TicketSummary.model_validate(t) for t in tickets_result.scalars().all()]
        base = StoryResponse.model_validate(story)
        return StoryDetailResponse(**base.model_dump(), tickets=tickets)

    async def get_by_id(self, story_id: uuid.UUID) -> Story:
        result = await self.db.execute(select(Story).where(Story.id == story_id))
        story = result.scalar_one_or_none()
        if not story:
            raise NotFoundError("Story not found")
        return story

    async def update(
        self, user: User, project_id: uuid.UUID, story_id: uuid.UUID, payload: StoryUpdate
    ) -> StoryResponse:
        await self._ensure_project_access(user, project_id)
        if user.global_role not in ("owner", "admin"):
            member = await self.db.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == user.id,
                )
            )
            m = member.scalar_one_or_none()
            if not m or m.role != "manager":
                raise ForbiddenError()

        result = await self.db.execute(
            select(Story).where(Story.id == story_id, Story.project_id == project_id)
        )
        story = result.scalar_one_or_none()
        if not story:
            raise NotFoundError("Story not found")

        if payload.title is not None:
            story.title = payload.title
        if payload.description is not None:
            story.description = payload.description
        if payload.acceptance_criteria is not None:
            story.acceptance_criteria = payload.acceptance_criteria
        if payload.priority is not None:
            story.priority = payload.priority
        if payload.status is not None:
            story.status = payload.status
        if payload.auto_merge is not None:
            story.auto_merge = payload.auto_merge

        await self.db.commit()
        await self.db.refresh(story)
        return StoryResponse.model_validate(story)

    async def delete(self, user: User, project_id: uuid.UUID, story_id: uuid.UUID) -> None:
        await self._ensure_project_access(user, project_id)
        if user.global_role not in ("owner", "admin"):
            member = await self.db.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == user.id,
                )
            )
            m = member.scalar_one_or_none()
            if not m or m.role != "manager":
                raise ForbiddenError()

        result = await self.db.execute(
            select(Story).where(Story.id == story_id, Story.project_id == project_id)
        )
        story = result.scalar_one_or_none()
        if not story:
            raise NotFoundError("Story not found")
        await self.db.delete(story)
        await self.db.commit()
