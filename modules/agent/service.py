import json
import re
import uuid
from datetime import datetime, timezone

from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions import ConflictError, ForbiddenError, NotFoundError
from modules.agent.models import AgentLog, AgentRun
from modules.agent.schemas import AgentLogResponse, AgentRunDetailResponse, AgentRunResponse
from modules.github.service import GitHubService
from modules.llm.models import LLMConfig
from modules.llm.service import LLMService
from modules.projects.models import Project, ProjectMember
from modules.stories.models import Story
from modules.tickets.models import Ticket
from modules.users.models import User

settings = get_settings()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "task"


_STALE_QUEUED_SECONDS = 30


class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_context(self, ticket_id: uuid.UUID) -> str:
        ticket = await self._get_ticket(ticket_id)
        story = await self._get_story(ticket.story_id)
        project = await self._get_project(ticket.project_id)
        codebase_summary = await GitHubService(self.db).get_codebase_summary(project.id)

        return f"""You are an autonomous software engineering agent working on project: {project.name}

PROJECT GOALS:
{project.goals or "Not specified"}

TECH STACK:
{project.tech_stack or "Not specified"}

CURRENT STORY:
Title: {story.title}
Description: {story.description or ""}
Acceptance Criteria: {story.acceptance_criteria or ""}

CURRENT TICKET (your task):
Title: {ticket.title}
Description: {ticket.description}
Type: {ticket.type}
Priority: {ticket.priority}

CODEBASE CONTEXT:
{codebase_summary}

INSTRUCTIONS:
1. Analyze the ticket carefully against the project goals
2. Use the GitHub tools to read relevant files
3. Make minimal, targeted changes to fix/implement the ticket
4. Write or update tests if applicable
5. Create a PR with a clear title and description
6. Log every step you take with reasoning
7. If you get stuck, explain the blocker and stop gracefully
8. Never break existing functionality — check related files before editing
"""

    async def _redispatch_stale_queued(self, run: AgentRun) -> AgentRunResponse | None:
        """Re-send Celery task for queued runs left behind after a worker restart."""
        if run.status != "queued":
            return None
        created = run.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - created).total_seconds()
        if age < _STALE_QUEUED_SECONDS:
            return None
        from modules.agent.tasks import dispatch_agent_run

        dispatch_agent_run(run.id)
        return AgentRunResponse.model_validate(run)

    async def queue_story_run(
        self, user: User, project_id: uuid.UUID, story_id: uuid.UUID
    ) -> AgentRunResponse:
        story = await self._get_story(story_id)
        if story.project_id != project_id:
            raise NotFoundError("Story not found")
        await self._ensure_story_access(user, project_id)
        run = await self._queue_story_run(project_id, story_id, schedule_id=None)
        return AgentRunResponse.model_validate(run)

    async def queue_story_run_scheduled(
        self,
        project_id: uuid.UUID,
        story_id: uuid.UUID,
        *,
        schedule_id: uuid.UUID,
    ) -> AgentRun:
        """Queue a story agent run from Celery beat (no user context)."""
        story = await self._get_story(story_id)
        if story.project_id != project_id:
            raise NotFoundError("Story not found")
        return await self._queue_story_run(
            project_id, story_id, schedule_id=schedule_id, from_schedule=True
        )

    async def _queue_story_run(
        self,
        project_id: uuid.UUID,
        story_id: uuid.UUID,
        *,
        schedule_id: uuid.UUID | None,
        from_schedule: bool = False,
    ) -> AgentRun:
        active = await self.db.execute(
            select(AgentRun).where(
                AgentRun.story_id == story_id,
                AgentRun.status.in_(("queued", "running")),
            )
        )
        existing = active.scalar_one_or_none()
        if existing:
            if from_schedule:
                raise ConflictError("An agent run is already active for this story")
            if existing.status == "running":
                raise ConflictError("An agent run is already active for this story")
            redispatched = await self._redispatch_stale_queued(existing)
            if redispatched:
                return existing
            raise ConflictError("An agent run is already active for this story")

        github_token = await GitHubService(self.db).get_decrypted_token(project_id)
        if not github_token:
            raise ConflictError("Connect GitHub repository in project settings first")

        llm_result = await self.db.execute(
            select(LLMConfig).where(LLMConfig.project_id == project_id)
        )
        if not llm_result.scalar_one_or_none():
            raise ConflictError("Configure LLM in project settings first")

        run = AgentRun(
            story_id=story_id,
            project_id=project_id,
            run_type="story",
            status="queued",
            schedule_id=schedule_id,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        from modules.agent.tasks import dispatch_agent_run

        dispatch_agent_run(run.id)
        return run

    async def list_runs_for_story(self, user: User, story_id: uuid.UUID) -> list[AgentRunResponse]:
        await self._ensure_story_access_by_story(user, story_id)
        result = await self.db.execute(
            select(AgentRun)
            .where(AgentRun.story_id == story_id)
            .order_by(AgentRun.created_at.desc())
        )
        return [AgentRunResponse.model_validate(r) for r in result.scalars().all()]

    async def queue_run(self, user: User, ticket_id: uuid.UUID) -> AgentRunResponse:
        ticket = await self._ensure_ticket_access(user, ticket_id)
        if not ticket.agent_enabled:
            raise ConflictError("Agent is not enabled on this ticket")

        active = await self.db.execute(
            select(AgentRun).where(
                AgentRun.ticket_id == ticket_id,
                AgentRun.status.in_(("queued", "running")),
            )
        )
        existing = active.scalar_one_or_none()
        if existing:
            if existing.status == "running":
                raise ConflictError("An agent run is already active for this ticket")
            redispatched = await self._redispatch_stale_queued(existing)
            if redispatched:
                return redispatched
            raise ConflictError("An agent run is already active for this ticket")

        run = AgentRun(
            ticket_id=ticket_id,
            project_id=ticket.project_id,
            run_type="ticket",
            status="queued",
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        from modules.agent.tasks import dispatch_agent_run

        dispatch_agent_run(run.id)
        return AgentRunResponse.model_validate(run)

    async def list_runs_for_ticket(self, user: User, ticket_id: uuid.UUID) -> list[AgentRunResponse]:
        await self._ensure_ticket_access(user, ticket_id)
        result = await self.db.execute(
            select(AgentRun).where(AgentRun.ticket_id == ticket_id).order_by(AgentRun.created_at.desc())
        )
        return [AgentRunResponse.model_validate(r) for r in result.scalars().all()]

    async def get_run(self, user: User, run_id: uuid.UUID) -> AgentRunDetailResponse:
        run = await self._get_run_with_access(user, run_id)
        logs_result = await self.db.execute(
            select(AgentLog).where(AgentLog.run_id == run_id).order_by(AgentLog.created_at)
        )
        logs = [AgentLogResponse.model_validate(log) for log in logs_result.scalars().all()]
        base = AgentRunResponse.model_validate(run)
        return AgentRunDetailResponse(**base.model_dump(), logs=logs)

    async def list_logs(self, user: User, run_id: uuid.UUID) -> list[AgentLogResponse]:
        await self._get_run_with_access(user, run_id)
        result = await self.db.execute(
            select(AgentLog).where(AgentLog.run_id == run_id).order_by(AgentLog.created_at)
        )
        return [AgentLogResponse.model_validate(log) for log in result.scalars().all()]

    async def get_logs_after(
        self, run_id: uuid.UUID, after_created_at: datetime | None
    ) -> list[AgentLog]:
        query = select(AgentLog).where(AgentLog.run_id == run_id).order_by(AgentLog.created_at)
        if after_created_at is not None:
            query = query.where(AgentLog.created_at > after_created_at)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def cancel_run(self, user: User, run_id: uuid.UUID) -> AgentRunResponse:
        run = await self._get_run_with_access(user, run_id)
        if run.status not in ("queued", "running"):
            raise ConflictError("Run cannot be cancelled")
        run.status = "cancelled"
        run.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(run)
        await self.add_log(run_id, "warning", "cancelled", "Agent run cancelled by user")
        return AgentRunResponse.model_validate(run)

    async def execute_run(self, run_id: uuid.UUID) -> None:
        result = await self.db.execute(select(AgentRun).where(AgentRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            return

        if run.status == "cancelled":
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        ticket = await self._get_ticket(run.ticket_id)
        branch_name = f"autopm/{ticket.id.hex[:8]}-{_slugify(ticket.title)}"
        run.branch_name = branch_name
        await self.db.commit()

        await self.add_log(run_id, "info", "starting", "Agent starting — reading ticket and codebase")

        try:
            llm_config, api_key = await LLMService(self.db).get_api_key(run.project_id)
            github_token = await GitHubService(self.db).get_decrypted_token(run.project_id)
            if not github_token:
                raise ValueError("GitHub is not connected for this project")
            if not api_key and llm_config.provider == "anthropic":
                raise ValueError("No API key configured for LLM")

            context = await self.build_context(ticket.id)
            messages: list[dict] = [{"role": "user", "content": context}]

            client = Anthropic(api_key=api_key or settings.ANTHROPIC_API_KEY)
            mcp_servers = [
                {
                    "type": "url",
                    "url": settings.GITHUB_MCP_SERVER_URL,
                    "name": "github",
                    "authorization_token": github_token,
                }
            ]

            max_iterations = 25
            for _ in range(max_iterations):
                status_check = await self.db.execute(select(AgentRun).where(AgentRun.id == run_id))
                current_run = status_check.scalar_one_or_none()
                if current_run and current_run.status == "cancelled":
                    return

                response = client.beta.messages.create(
                    model=llm_config.model,
                    max_tokens=llm_config.max_tokens,
                    messages=messages,
                    mcp_servers=mcp_servers,
                    betas=["mcp-client-2025-04-22"],
                )

                for block in response.content:
                    if block.type == "text":
                        await self.add_log(run_id, "info", "thinking", block.text)
                    elif block.type == "tool_use":
                        await self.add_log(
                            run_id,
                            "info",
                            f"tool:{block.name}",
                            f"Calling {block.name}",
                            metadata=block.input if isinstance(block.input, dict) else {"input": block.input},
                        )

                if response.stop_reason == "end_turn":
                    run.status = "completed"
                    run.completed_at = datetime.now(timezone.utc)
                    ticket.status = "review"
                    await self.add_log(run_id, "success", "done", "Agent completed successfully")
                    await self.db.commit()
                    return

                messages.append({"role": "assistant", "content": response.content})
                if response.stop_reason == "pause_turn":
                    continue
                if response.stop_reason in ("max_tokens", "refusal"):
                    raise ValueError(f"Agent stopped: {response.stop_reason}")

            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            await self.add_log(run_id, "success", "done", "Agent reached iteration limit")
            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            result = await self.db.execute(select(AgentRun).where(AgentRun.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = "failed"
                run.error_message = str(e)
                run.completed_at = datetime.now(timezone.utc)
                await self.add_log(run_id, "error", "failed", str(e))
                await self.db.commit()

    async def add_log(
        self,
        run_id: uuid.UUID,
        level: str,
        step: str | None,
        message: str,
        metadata: dict | None = None,
    ) -> AgentLog:
        safe_meta = metadata
        if metadata:
            try:
                json.dumps(metadata)
            except (TypeError, ValueError):
                safe_meta = {"raw": str(metadata)[:2000]}
        log = AgentLog(
            run_id=run_id,
            level=level,
            step=(step or "step")[:255],
            message=message[:8000] if message else "",
            log_metadata=safe_meta,
        )
        self.db.add(log)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def _ensure_ticket_access(self, user: User, ticket_id: uuid.UUID) -> Ticket:
        result = await self.db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise NotFoundError("Ticket not found")
        proj = await self.db.execute(
            select(Project).where(Project.id == ticket.project_id, Project.company_id == user.company_id)
        )
        if not proj.scalar_one_or_none():
            raise NotFoundError("Ticket not found")
        if user.global_role in ("owner", "admin"):
            return ticket
        member = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == ticket.project_id,
                ProjectMember.user_id == user.id,
            )
        )
        m = member.scalar_one_or_none()
        if not m or m.role not in ("manager", "developer"):
            raise ForbiddenError()
        return ticket

    async def _get_run_with_access(self, user: User, run_id: uuid.UUID) -> AgentRun:
        result = await self.db.execute(select(AgentRun).where(AgentRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            raise NotFoundError("Agent run not found")
        proj = await self.db.execute(
            select(Project).where(Project.id == run.project_id, Project.company_id == user.company_id)
        )
        if not proj.scalar_one_or_none():
            raise NotFoundError("Agent run not found")
        if user.global_role in ("owner", "admin"):
            return run
        member = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == run.project_id,
                ProjectMember.user_id == user.id,
            )
        )
        if not member.scalar_one_or_none():
            raise ForbiddenError()
        return run

    async def _get_ticket(self, ticket_id: uuid.UUID) -> Ticket:
        result = await self.db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise NotFoundError("Ticket not found")
        return ticket

    async def _get_story(self, story_id: uuid.UUID) -> Story:
        result = await self.db.execute(select(Story).where(Story.id == story_id))
        story = result.scalar_one_or_none()
        if not story:
            raise NotFoundError("Story not found")
        return story

    async def _get_project(self, project_id: uuid.UUID) -> Project:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project not found")
        return project

    async def _ensure_story_access(self, user: User, project_id: uuid.UUID) -> None:
        proj = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.company_id == user.company_id)
        )
        if not proj.scalar_one_or_none():
            raise NotFoundError("Project not found")
        if user.global_role in ("owner", "admin"):
            return
        member = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            )
        )
        m = member.scalar_one_or_none()
        if not m or m.role not in ("manager", "developer"):
            raise ForbiddenError()

    async def _ensure_story_access_by_story(self, user: User, story_id: uuid.UUID) -> Story:
        story = await self._get_story(story_id)
        await self._ensure_story_access(user, story.project_id)
        return story
