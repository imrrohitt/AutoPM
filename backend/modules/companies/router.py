from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_user, get_db
from modules.companies.schemas import CompanyResponse, CompanyUpdate
from modules.companies.service import CompanyService
from modules.users.models import User

router = APIRouter(prefix="/company", tags=["company"])


@router.get("", response_model=CompanyResponse)
async def get_company(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CompanyService(db).get_for_user(current_user)


@router.patch("", response_model=CompanyResponse)
async def update_company(
    payload: CompanyUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CompanyService(db).update(current_user, payload)
