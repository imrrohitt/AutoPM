from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.tickets.schemas import TicketSummary


class StoryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    acceptance_criteria: str | None = None
    priority: str = Field(default="medium", pattern="^(critical|high|medium|low)$")


class StoryUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    acceptance_criteria: str | None = None
    priority: str | None = Field(None, pattern="^(critical|high|medium|low)$")
    status: str | None = Field(None, pattern="^(open|in_progress|done)$")


class StoryResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: str | None
    acceptance_criteria: str | None
    priority: str
    status: str
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoryDetailResponse(StoryResponse):
    tickets: list[TicketSummary] = []
