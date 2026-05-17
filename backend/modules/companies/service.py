import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ForbiddenError, NotFoundError
from modules.companies.models import Company
from modules.companies.schemas import CompanyResponse, CompanyUpdate
from modules.users.models import User


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "company"


class CompanyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_for_user(self, user: User) -> CompanyResponse:
        result = await self.db.execute(select(Company).where(Company.id == user.company_id))
        company = result.scalar_one_or_none()
        if not company:
            raise NotFoundError("Company not found")
        return CompanyResponse.model_validate(company)

    async def update(self, user: User, payload: CompanyUpdate) -> CompanyResponse:
        if user.global_role not in ("owner", "admin"):
            raise ForbiddenError()

        result = await self.db.execute(select(Company).where(Company.id == user.company_id))
        company = result.scalar_one_or_none()
        if not company:
            raise NotFoundError("Company not found")

        if payload.name is not None:
            company.name = payload.name
            base_slug = _slugify(payload.name)
            slug = base_slug
            suffix = 0
            while True:
                check = await self.db.execute(
                    select(Company).where(Company.slug == slug, Company.id != company.id)
                )
                if not check.scalar_one_or_none():
                    break
                suffix += 1
                slug = f"{base_slug}-{suffix}"
            company.slug = slug

        await self.db.commit()
        await self.db.refresh(company)
        return CompanyResponse.model_validate(company)
