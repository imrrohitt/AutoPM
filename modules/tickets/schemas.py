from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    type: str = Field(default="task", pattern="^(task|bug|feature|chore)$")
    priority: str = Field(default="medium", pattern="^(critical|high|medium|low)$")
    assigned_to: UUID | None = None


class TicketUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = Field(None, min_length=1)
    type: str | None = Field(None, pattern="^(task|bug|feature|chore)$")
    priority: str | None = Field(None, pattern="^(critical|high|medium|low)$")
    status: str | None = Field(None, pattern="^(open|in_progress|review|done|failed)$")
    assigned_to: UUID | None = None
    agent_enabled: bool | None = None


class TicketSummary(BaseModel):
    id: UUID
    story_id: UUID
    project_id: UUID
    title: str
    type: str
    priority: str
    status: str
    agent_enabled: bool

    model_config = {"from_attributes": True}


class TicketResponse(BaseModel):
    id: UUID
    story_id: UUID
    project_id: UUID
    title: str
    description: str
    type: str
    priority: str
    status: str
    assigned_to: UUID | None
    agent_enabled: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    id: UUID
    ticket_id: UUID
    author_id: UUID | None
    is_agent: bool
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}
