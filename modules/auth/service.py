import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, UnauthorizedError
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserProfile
from modules.companies.models import Company
from modules.users.models import User


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "company"


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, payload: RegisterRequest) -> TokenResponse:
        existing = await self.db.execute(select(User).where(User.email == payload.email))
        if existing.scalar_one_or_none():
            raise ConflictError("Email already registered")

        base_slug = _slugify(payload.company_name)
        slug = base_slug
        suffix = 0
        while True:
            company_check = await self.db.execute(select(Company).where(Company.slug == slug))
            if not company_check.scalar_one_or_none():
                break
            suffix += 1
            slug = f"{base_slug}-{suffix}"

        company = Company(name=payload.company_name, slug=slug)
        self.db.add(company)
        await self.db.flush()

        user = User(
            company_id=company.id,
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            global_role="owner",
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def login(self, payload: LoginRequest) -> TokenResponse:
        result = await self.db.execute(
            select(User).where(User.email == payload.email, User.is_active.is_(True))
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except ValueError as e:
            raise UnauthorizedError() from e
        if payload.get("type") != "refresh":
            raise UnauthorizedError()

        user_id = payload.get("sub")
        result = await self.db.execute(
            select(User).where(User.id == uuid.UUID(user_id), User.is_active.is_(True))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise UnauthorizedError()

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def get_profile(self, user: User) -> UserProfile:
        return UserProfile.model_validate(user)
