import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, ForbiddenError, NotFoundError
from core.security import hash_password
from modules.users.models import User
from modules.users.schemas import UserInviteRequest, UserResponse, UserRoleUpdate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _require_admin(self, actor: User) -> None:
        if actor.global_role not in ("owner", "admin"):
            raise ForbiddenError()

    async def list_company_users(self, actor: User) -> list[UserResponse]:
        self._require_admin(actor)
        result = await self.db.execute(
            select(User).where(User.company_id == actor.company_id).order_by(User.created_at)
        )
        users = result.scalars().all()
        return [UserResponse.model_validate(u) for u in users]

    async def invite(self, actor: User, payload: UserInviteRequest) -> UserResponse:
        self._require_admin(actor)
        if payload.global_role == "admin" and actor.global_role != "owner":
            raise ForbiddenError("Only owners can invite admins")

        existing = await self.db.execute(select(User).where(User.email == payload.email))
        if existing.scalar_one_or_none():
            raise ConflictError("Email already registered")

        temp_password = secrets.token_urlsafe(16)
        user = User(
            company_id=actor.company_id,
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(temp_password),
            global_role=payload.global_role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return UserResponse.model_validate(user)

    async def update_role(
        self, actor: User, user_id: uuid.UUID, payload: UserRoleUpdate
    ) -> UserResponse:
        if actor.global_role != "owner":
            raise ForbiddenError("Only owners can change global roles")

        result = await self.db.execute(
            select(User).where(User.id == user_id, User.company_id == actor.company_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")
        if user.id == actor.id and payload.global_role != "owner":
            raise ForbiddenError("Cannot demote yourself")

        user.global_role = payload.global_role
        await self.db.commit()
        await self.db.refresh(user)
        return UserResponse.model_validate(user)

    async def deactivate(self, actor: User, user_id: uuid.UUID) -> UserResponse:
        self._require_admin(actor)
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.company_id == actor.company_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")
        if user.id == actor.id:
            raise ForbiddenError("Cannot deactivate yourself")
        if user.global_role == "owner" and actor.global_role != "owner":
            raise ForbiddenError()

        user.is_active = False
        await self.db.commit()
        await self.db.refresh(user)
        return UserResponse.model_validate(user)
