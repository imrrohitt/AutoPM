import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ForbiddenError, NotFoundError
from modules.projects.models import Project, ProjectMember
from modules.stories.models import Story
from modules.stories.service import StoryService
from modules.tickets.models import Comment, Ticket
from modules.tickets.schemas import (
    CommentCreate,
    CommentResponse,
    TicketCreate,
    TicketResponse,
    TicketUpdate,
)
from modules.users.models import User


class TicketService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _ensure_story_access(self, user: User, story_id: uuid.UUID) -> Story:
        story = await StoryService(self.db).get_by_id(story_id)
        result = await self.db.execute(
            select(Project).where(Project.id == story.project_id, Project.company_id == user.company_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("Story not found")
        if user.global_role in ("owner", "admin"):
            return story
        member = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == story.project_id,
                ProjectMember.user_id == user.id,
            )
        )
        if not member.scalar_one_or_none():
            raise ForbiddenError()
        return story

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
        if not member.scalar_one_or_none():
            raise ForbiddenError()
        return ticket

    def _require_developer(self, user: User, project_id: uuid.UUID, member: ProjectMember | None) -> None:
        if user.global_role in ("owner", "admin"):
            return
        if not member or member.role not in ("manager", "developer"):
            raise ForbiddenError()

    async def _get_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
        result = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_story(self, user: User, story_id: uuid.UUID) -> list[TicketResponse]:
        await self._ensure_story_access(user, story_id)
        result = await self.db.execute(
            select(Ticket).where(Ticket.story_id == story_id).order_by(Ticket.created_at)
        )
        return [TicketResponse.model_validate(t) for t in result.scalars().all()]

    async def create(self, user: User, story_id: uuid.UUID, payload: TicketCreate) -> TicketResponse:
        story = await self._ensure_story_access(user, story_id)
        member = await self._get_member(story.project_id, user.id)
        self._require_developer(user, story.project_id, member)

        ticket = Ticket(
            story_id=story_id,
            project_id=story.project_id,
            title=payload.title,
            description=payload.description,
            type=payload.type,
            priority=payload.priority,
            assigned_to=payload.assigned_to,
            created_by=user.id,
        )
        self.db.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)
        return TicketResponse.model_validate(ticket)

    async def get(self, user: User, ticket_id: uuid.UUID) -> TicketResponse:
        ticket = await self._ensure_ticket_access(user, ticket_id)
        return TicketResponse.model_validate(ticket)

    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket:
        result = await self.db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise NotFoundError("Ticket not found")
        return ticket

    async def update(self, user: User, ticket_id: uuid.UUID, payload: TicketUpdate) -> TicketResponse:
        ticket = await self._ensure_ticket_access(user, ticket_id)
        member = await self._get_member(ticket.project_id, user.id)
        self._require_developer(user, ticket.project_id, member)

        if payload.title is not None:
            ticket.title = payload.title
        if payload.description is not None:
            ticket.description = payload.description
        if payload.type is not None:
            ticket.type = payload.type
        if payload.priority is not None:
            ticket.priority = payload.priority
        if payload.status is not None:
            ticket.status = payload.status
        if payload.assigned_to is not None:
            ticket.assigned_to = payload.assigned_to
        if payload.agent_enabled is not None:
            ticket.agent_enabled = payload.agent_enabled

        await self.db.commit()
        await self.db.refresh(ticket)
        return TicketResponse.model_validate(ticket)

    async def delete(self, user: User, ticket_id: uuid.UUID) -> None:
        ticket = await self._ensure_ticket_access(user, ticket_id)
        if user.global_role not in ("owner", "admin"):
            member = await self._get_member(ticket.project_id, user.id)
            if not member or member.role != "manager":
                raise ForbiddenError()
        await self.db.delete(ticket)
        await self.db.commit()

    async def enable_agent(self, user: User, ticket_id: uuid.UUID) -> TicketResponse:
        ticket = await self._ensure_ticket_access(user, ticket_id)
        member = await self._get_member(ticket.project_id, user.id)
        self._require_developer(user, ticket.project_id, member)
        ticket.agent_enabled = True
        await self.db.commit()
        await self.db.refresh(ticket)
        return TicketResponse.model_validate(ticket)

    async def add_comment(
        self, user: User, ticket_id: uuid.UUID, payload: CommentCreate
    ) -> CommentResponse:
        ticket = await self._ensure_ticket_access(user, ticket_id)
        if user.global_role not in ("owner", "admin"):
            member = await self._get_member(ticket.project_id, user.id)
            if not member or member.role == "viewer":
                raise ForbiddenError()

        comment = Comment(
            ticket_id=ticket_id,
            author_id=user.id,
            body=payload.body,
            is_agent=False,
        )
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        return CommentResponse.model_validate(comment)

    async def list_comments(self, user: User, ticket_id: uuid.UUID) -> list[CommentResponse]:
        await self._ensure_ticket_access(user, ticket_id)
        result = await self.db.execute(
            select(Comment).where(Comment.ticket_id == ticket_id).order_by(Comment.created_at)
        )
        return [CommentResponse.model_validate(c) for c in result.scalars().all()]
