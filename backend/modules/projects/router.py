from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_user, get_db, require_global_role, require_project_role
from modules.projects.schemas import (
    ProjectCreate,
    ProjectMemberAdd,
    ProjectMemberResponse,
    ProjectMemberUpdate,
    ProjectResponse,
    ProjectUpdate,
)
from modules.projects.service import ProjectService
from modules.users.models import User

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProjectService(db).list_for_user(current_user)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: Annotated[User, Depends(require_global_role("owner", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProjectService(db).create(current_user, payload)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProjectService(db).get(current_user, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProjectService(db).update(current_user, project_id, payload)


@router.delete("/{project_id}", response_model=ProjectResponse)
async def archive_project(
    project_id: UUID,
    current_user: Annotated[User, Depends(require_global_role("owner", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProjectService(db).archive(current_user, project_id)


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_project_members(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProjectService(db).list_members(current_user, project_id)


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_project_member(
    project_id: UUID,
    payload: ProjectMemberAdd,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProjectService(db).add_member(current_user, project_id, payload)


@router.patch("/{project_id}/members/{user_id}", response_model=ProjectMemberResponse)
async def update_project_member(
    project_id: UUID,
    user_id: UUID,
    payload: ProjectMemberUpdate,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProjectService(db).update_member(current_user, project_id, user_id, payload)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_member(
    project_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await ProjectService(db).remove_member(current_user, project_id, user_id)
