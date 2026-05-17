import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.exceptions import ConflictError, ForbiddenError, NotFoundError
from modules.projects.models import Project, ProjectMember
from modules.projects.schemas import (
    ProjectCreate,
    ProjectMemberAdd,
    ProjectMemberResponse,
    ProjectMemberUpdate,
    ProjectResponse,
    ProjectUpdate,
)
from modules.users.models import User


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _to_response(self, project: Project, user: User) -> ProjectResponse:
        my_role: str | None = None
        if user.global_role in ("owner", "admin"):
            my_role = "manager"
        return ProjectResponse.model_validate(project).model_copy(
            update={"my_role": my_role}
        )

    async def _resolve_my_role(self, user: User, project_id: uuid.UUID) -> str | None:
        if user.global_role in ("owner", "admin"):
            return "manager"
        member = await self._get_member(project_id, user.id)
        return member.role if member else None

    async def _get_project(self, project_id: uuid.UUID, company_id: uuid.UUID) -> Project:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.company_id == company_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project not found")
        return project

    async def list_for_user(self, user: User) -> list[ProjectResponse]:
        if user.global_role in ("owner", "admin"):
            result = await self.db.execute(
                select(Project)
                .where(Project.company_id == user.company_id, Project.status == "active")
                .order_by(Project.created_at.desc())
            )
        else:
            result = await self.db.execute(
                select(Project)
                .join(ProjectMember, ProjectMember.project_id == Project.id)
                .where(
                    Project.company_id == user.company_id,
                    Project.status == "active",
                    ProjectMember.user_id == user.id,
                )
                .order_by(Project.created_at.desc())
            )
        projects = result.scalars().unique().all()
        out: list[ProjectResponse] = []
        for p in projects:
            resp = ProjectResponse.model_validate(p)
            my_role = await self._resolve_my_role(user, p.id)
            out.append(resp.model_copy(update={"my_role": my_role}))
        return out

    async def create(self, user: User, payload: ProjectCreate) -> ProjectResponse:
        if user.global_role not in ("owner", "admin"):
            raise ForbiddenError()

        project = Project(
            company_id=user.company_id,
            name=payload.name,
            description=payload.description,
            goals=payload.goals,
            tech_stack=payload.tech_stack,
            created_by=user.id,
        )
        self.db.add(project)
        await self.db.flush()

        self.db.add(ProjectMember(project_id=project.id, user_id=user.id, role="manager"))
        await self.db.commit()
        await self.db.refresh(project)
        return self._to_response(project, user)

    async def get(self, user: User, project_id: uuid.UUID) -> ProjectResponse:
        if user.global_role in ("owner", "admin"):
            project = await self._get_project(project_id, user.company_id)
        else:
            result = await self.db.execute(
                select(Project)
                .join(ProjectMember, ProjectMember.project_id == Project.id)
                .where(
                    Project.id == project_id,
                    Project.company_id == user.company_id,
                    ProjectMember.user_id == user.id,
                )
            )
            project = result.scalar_one_or_none()
            if not project:
                raise NotFoundError("Project not found")
        my_role = await self._resolve_my_role(user, project_id)
        return ProjectResponse.model_validate(project).model_copy(update={"my_role": my_role})

    async def update(self, user: User, project_id: uuid.UUID, payload: ProjectUpdate) -> ProjectResponse:
        project = await self._get_project(project_id, user.company_id)
        if user.global_role not in ("owner", "admin"):
            member = await self._get_member(project_id, user.id)
            if not member or member.role != "manager":
                raise ForbiddenError()

        if payload.name is not None:
            project.name = payload.name
        if payload.description is not None:
            project.description = payload.description
        if payload.goals is not None:
            project.goals = payload.goals
        if payload.tech_stack is not None:
            project.tech_stack = payload.tech_stack
        if payload.status is not None:
            if user.global_role not in ("owner", "admin"):
                raise ForbiddenError()
            project.status = payload.status

        await self.db.commit()
        await self.db.refresh(project)
        my_role = await self._resolve_my_role(user, project_id)
        return ProjectResponse.model_validate(project).model_copy(update={"my_role": my_role})

    async def archive(self, user: User, project_id: uuid.UUID) -> ProjectResponse:
        if user.global_role not in ("owner", "admin"):
            raise ForbiddenError()
        project = await self._get_project(project_id, user.company_id)
        project.status = "archived"
        await self.db.commit()
        await self.db.refresh(project)
        return self._to_response(project, user)

    async def _get_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
        result = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
        return await self._get_member(project_id, user_id)

    async def list_members(self, user: User, project_id: uuid.UUID) -> list[ProjectMemberResponse]:
        await self.get(user, project_id)
        result = await self.db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.role)
        )
        rows = result.all()
        return [
            ProjectMemberResponse(
                id=member.id,
                project_id=member.project_id,
                user_id=member.user_id,
                role=member.role,
                full_name=u.full_name,
                email=u.email,
            )
            for member, u in rows
        ]

    async def add_member(
        self, user: User, project_id: uuid.UUID, payload: ProjectMemberAdd
    ) -> ProjectMemberResponse:
        await self._get_project(project_id, user.company_id)
        if user.global_role not in ("owner", "admin"):
            actor_member = await self._get_member(project_id, user.id)
            if not actor_member or actor_member.role != "manager":
                raise ForbiddenError()

        target = await self.db.execute(
            select(User).where(User.id == payload.user_id, User.company_id == user.company_id)
        )
        target_user = target.scalar_one_or_none()
        if not target_user:
            raise NotFoundError("User not found in company")

        existing = await self._get_member(project_id, payload.user_id)
        if existing:
            raise ConflictError("User is already a project member")

        member = ProjectMember(
            project_id=project_id,
            user_id=payload.user_id,
            role=payload.role,
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return ProjectMemberResponse(
            id=member.id,
            project_id=member.project_id,
            user_id=member.user_id,
            role=member.role,
            full_name=target_user.full_name,
            email=target_user.email,
        )

    async def update_member(
        self, user: User, project_id: uuid.UUID, member_user_id: uuid.UUID, payload: ProjectMemberUpdate
    ) -> ProjectMemberResponse:
        await self._get_project(project_id, user.company_id)
        if user.global_role not in ("owner", "admin"):
            actor_member = await self._get_member(project_id, user.id)
            if not actor_member or actor_member.role != "manager":
                raise ForbiddenError()

        result = await self.db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id, ProjectMember.user_id == member_user_id)
        )
        row = result.one_or_none()
        if not row:
            raise NotFoundError("Project member not found")
        member, target_user = row
        member.role = payload.role
        await self.db.commit()
        await self.db.refresh(member)
        return ProjectMemberResponse(
            id=member.id,
            project_id=member.project_id,
            user_id=member.user_id,
            role=member.role,
            full_name=target_user.full_name,
            email=target_user.email,
        )

    async def remove_member(self, user: User, project_id: uuid.UUID, member_user_id: uuid.UUID) -> None:
        await self._get_project(project_id, user.company_id)
        if user.global_role not in ("owner", "admin"):
            actor_member = await self._get_member(project_id, user.id)
            if not actor_member or actor_member.role != "manager":
                raise ForbiddenError()

        member = await self._get_member(project_id, member_user_id)
        if not member:
            raise NotFoundError("Project member not found")
        await self.db.delete(member)
        await self.db.commit()
