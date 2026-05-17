from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    global_role: str
    is_active: bool

    model_config = {"from_attributes": True}


class UserInviteRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    global_role: str = Field(default="member", pattern="^(admin|member)$")


class UserRoleUpdate(BaseModel):
    global_role: str = Field(..., pattern="^(owner|admin|member)$")
