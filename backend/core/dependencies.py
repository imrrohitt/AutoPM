from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import async_session_factory
from core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from core.security import decode_token
from modules.projects.models import Project, ProjectMember
from modules.users.models import User

security_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> User:
    if not credentials:
        raise UnauthorizedError()
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as e:
        raise UnauthorizedError() from e
    if payload.get("type") != "access":
        raise UnauthorizedError()
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError()
    result = await db.execute(select(User).where(User.id == UUID(user_id), User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError()
    return user


def require_global_role(*allowed_roles: str):
    async def checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.global_role not in allowed_roles:
            raise ForbiddenError()
        return current_user

    return checker


async def get_project_for_user(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == current_user.company_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found")
    if current_user.global_role in ("owner", "admin"):
        return project
    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    if not member_result.scalar_one_or_none():
        raise ForbiddenError()
    return project


def require_project_role(*allowed_roles: str):
    async def checker(
        project_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        if current_user.global_role in ("owner", "admin"):
            return current_user
        result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
            )
        )
        member = result.scalar_one_or_none()
        if not member or member.role not in allowed_roles:
            raise ForbiddenError()
        return current_user

    return checker
