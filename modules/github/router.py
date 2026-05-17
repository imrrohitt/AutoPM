from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_user, get_db, require_project_role
from modules.github.schemas import (
    GitHubConnectRequest,
    GitHubConnectionResponse,
    GitHubIndexStatusResponse,
    GitHubRepoItem,
    GitHubTokenSaveRequest,
)
from modules.github.service import GitHubService
from modules.users.models import User

router = APIRouter(tags=["github"])


@router.get("/projects/{project_id}/github", response_model=GitHubConnectionResponse | None)
async def get_github_connection(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await GitHubService(db).get_connection(current_user, project_id)


@router.put("/projects/{project_id}/github/token", response_model=GitHubConnectionResponse)
async def save_github_token(
    project_id: UUID,
    payload: GitHubTokenSaveRequest,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await GitHubService(db).save_token(current_user, project_id, payload.github_token)


@router.get("/projects/{project_id}/github/repos", response_model=list[GitHubRepoItem])
async def list_project_github_repos(
    project_id: UUID,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await GitHubService(db).list_repos_for_project(current_user, project_id)


@router.post(
    "/projects/{project_id}/github/connect",
    response_model=GitHubConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_github(
    project_id: UUID,
    payload: GitHubConnectRequest,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await GitHubService(db).connect(current_user, project_id, payload)


@router.delete("/projects/{project_id}/github/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_github(
    project_id: UUID,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await GitHubService(db).disconnect(current_user, project_id)


@router.post("/projects/{project_id}/github/index", response_model=GitHubIndexStatusResponse)
async def trigger_github_index(
    project_id: UUID,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await GitHubService(db).trigger_index(current_user, project_id)


@router.get("/projects/{project_id}/github/index/status", response_model=GitHubIndexStatusResponse)
async def get_github_index_status(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await GitHubService(db).get_index_status(current_user, project_id)
