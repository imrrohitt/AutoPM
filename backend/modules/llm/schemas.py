from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


PROVIDER_PATTERN = "^(anthropic|openai|ollama|groq|litellm)$"

PROVIDER_DEFAULTS: dict[str, dict[str, str | int]] = {
    "anthropic": {
        "model": "claude-sonnet-4-20250514",
        "base_url": "",
    },
    "ollama": {
        "model": "gemma:2b",
        "base_url": "http://localhost:11434",
    },
    "litellm": {
        "model": "gemma:2b",
        "base_url": "http://localhost:4000",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
    },
    "groq": {
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
    },
}


class LLMConfigCreate(BaseModel):
    provider: str = Field(..., pattern=PROVIDER_PATTERN)
    model: str = Field(..., min_length=1, max_length=255)
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = Field(default=8192, ge=256, le=200000)

    @field_validator("base_url")
    @classmethod
    def strip_base_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class LLMConfigResponse(BaseModel):
    id: UUID
    project_id: UUID
    provider: str
    model: str
    api_key_masked: str | None
    base_url: str | None
    max_tokens: int
    created_at: datetime
    updated_at: datetime
    uses_base_url: bool = False
    uses_api_key: bool = True

    model_config = {"from_attributes": True}


class LLMProviderInfo(BaseModel):
    id: str
    label: str
    description: str
    default_model: str
    default_base_url: str | None
    requires_api_key: bool
    requires_base_url: bool


class LLMTestResponse(BaseModel):
    success: bool
    message: str
