from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_user, get_db, require_project_role
from modules.stories.schemas import StoryCreate, StoryDetailResponse, StoryResponse, StoryUpdate
from modules.stories.service import StoryService
from modules.users.models import User

router = APIRouter(tags=["stories"])


@router.get("/projects/{project_id}/stories", response_model=list[StoryResponse])
async def list_stories(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoryService(db).list_stories(current_user, project_id)


@router.post(
    "/projects/{project_id}/stories",
    response_model=StoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_story(
    project_id: UUID,
    payload: StoryCreate,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoryService(db).create(current_user, project_id, payload)


@router.get("/projects/{project_id}/stories/{story_id}", response_model=StoryDetailResponse)
async def get_story(
    project_id: UUID,
    story_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoryService(db).get_story(current_user, project_id, story_id)


@router.patch("/projects/{project_id}/stories/{story_id}", response_model=StoryResponse)
async def update_story(
    project_id: UUID,
    story_id: UUID,
    payload: StoryUpdate,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoryService(db).update(current_user, project_id, story_id, payload)


@router.delete("/projects/{project_id}/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(
    project_id: UUID,
    story_id: UUID,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await StoryService(db).delete(current_user, project_id, story_id)
