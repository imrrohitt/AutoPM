from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AgentRunResponse(BaseModel):
    id: UUID
    ticket_id: UUID | None = None
    story_id: UUID | None = None
    project_id: UUID
    run_type: str = "ticket"
    schedule_id: UUID | None = None
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


class StoryAgentScheduleCreate(BaseModel):
    label: str | None = None
    schedule_type: Literal["once", "daily", "weekly"]
    run_at: datetime
    weekdays: list[int] | None = None
    timezone: str = "UTC"

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        for d in v:
            if d < 0 or d > 6:
                raise ValueError("weekdays must be 0 (Mon) through 6 (Sun)")
        return sorted(set(v))


class StoryAgentScheduleUpdate(BaseModel):
    label: str | None = None
    schedule_type: Literal["once", "daily", "weekly"] | None = None
    run_at: datetime | None = None
    weekdays: list[int] | None = None
    timezone: str | None = None
    enabled: bool | None = None

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        for d in v:
            if d < 0 or d > 6:
                raise ValueError("weekdays must be 0 (Mon) through 6 (Sun)")
        return sorted(set(v))


class StoryAgentScheduleResponse(BaseModel):
    id: UUID
    story_id: UUID
    project_id: UUID
    created_by: UUID | None
    label: str | None
    schedule_type: str
    run_at: datetime
    weekdays: list[int] | None
    timezone: str
    enabled: bool
    next_run_at: datetime
    last_triggered_at: datetime | None
    last_run_id: UUID | None
    last_run_status: str | None = None
    run_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
