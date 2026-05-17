from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRunResponse(BaseModel):
    id: UUID
    ticket_id: UUID | None = None
    story_id: UUID | None = None
    project_id: UUID
    run_type: str = "ticket"
    current_ticket_id: UUID | None = None
    status: str
    branch_name: str | None
    pr_url: str | None
    pr_number: int | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentLogResponse(BaseModel):
    id: UUID
    run_id: UUID
    level: str
    step: str | None
    message: str
    metadata: dict | None = Field(default=None, validation_alias="log_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class AgentRunDetailResponse(AgentRunResponse):
    logs: list[AgentLogResponse] = []


class AgentFileChangeResponse(BaseModel):
    path: str
    change_type: str
    before_content: str | None = None
    after_content: str | None = None
    thought: str | None = None
    updated_at: str


class AgentWorkspaceResponse(BaseModel):
    repo_owner: str | None = None
    repo_name: str | None = None
    branch: str | None = None
    tree: list[str] = []
    changes: list[AgentFileChangeResponse] = []
