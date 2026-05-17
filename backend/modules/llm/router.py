from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db, require_project_role
from modules.llm.schemas import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMProviderInfo,
    LLMTestResponse,
)
from modules.llm.service import LLMService
from modules.users.models import User

router = APIRouter(tags=["llm"])


@router.get("/llm/providers", response_model=list[LLMProviderInfo])
async def list_llm_providers():
    return LLMService.list_providers()


@router.get("/projects/{project_id}/llm", response_model=LLMConfigResponse | None)
async def get_llm_config(
    project_id: UUID,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await LLMService(db).get_config(current_user, project_id)


@router.post(
    "/projects/{project_id}/llm",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_llm_config(
    project_id: UUID,
    payload: LLMConfigCreate,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await LLMService(db).save_config(current_user, project_id, payload)


@router.post("/projects/{project_id}/llm/test", response_model=LLMTestResponse)
async def test_llm_connection(
    project_id: UUID,
    current_user: Annotated[User, Depends(require_project_role("manager"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await LLMService(db).test_connection(current_user, project_id)
