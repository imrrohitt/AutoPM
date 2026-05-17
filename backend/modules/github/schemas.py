from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GitHubTokenSaveRequest(BaseModel):
    github_token: str = Field(..., min_length=1)


class GitHubConnectRequest(BaseModel):
    repo_owner: str = Field(..., min_length=1)
    repo_name: str = Field(..., min_length=1)
    default_branch: str = Field(default="main", min_length=1)
    github_token: str | None = Field(None, min_length=1)


class GitHubConnectionResponse(BaseModel):
    id: UUID
    project_id: UUID
    repo_owner: str | None
    repo_name: str | None
    default_branch: str
    connected_at: datetime
    last_indexed_at: datetime | None
    index_status: str
    has_token: bool = False
    is_connected: bool = False

    model_config = {"from_attributes": True}


class GitHubRepoItem(BaseModel):
    owner: str
    name: str
    full_name: str
    default_branch: str
    private: bool


class GitHubIndexStatusResponse(BaseModel):
    index_status: str
    last_indexed_at: datetime | None
