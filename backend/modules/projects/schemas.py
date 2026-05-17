from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    goals: str | None = None
    tech_stack: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    goals: str | None = None
    tech_stack: str | None = None
    status: str | None = Field(None, pattern="^(active|archived)$")


class ProjectResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    description: str | None
    goals: str | None
    tech_stack: str | None
    status: str
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    my_role: str | None = None

    model_config = {"from_attributes": True}


class ProjectMemberAdd(BaseModel):
    user_id: UUID
    role: str = Field(default="viewer", pattern="^(manager|developer|viewer)$")


class ProjectMemberUpdate(BaseModel):
    role: str = Field(..., pattern="^(manager|developer|viewer)$")


class ProjectMemberResponse(BaseModel):
    id: UUID
    project_id: UUID
    user_id: UUID
    role: str
    full_name: str | None = None
    email: str | None = None

    model_config = {"from_attributes": True}
