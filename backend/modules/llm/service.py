import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.encryption import decrypt_value, encrypt_value
from core.exceptions import NotFoundError
from modules.llm.client import test_anthropic, test_ollama_generate, test_openai_compatible
from modules.llm.models import LLMConfig
from modules.llm.schemas import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMProviderInfo,
    LLMTestResponse,
    PROVIDER_DEFAULTS,
)
from modules.projects.models import Project
from modules.users.models import User

settings = get_settings()

PROVIDER_META: list[LLMProviderInfo] = [
    LLMProviderInfo(
        id="anthropic",
        label="Anthropic (Claude)",
        description="Cloud Claude API — API key + model name only",
        default_model="claude-sonnet-4-20250514",
        default_base_url=None,
        requires_api_key=True,
        requires_base_url=False,
    ),
    LLMProviderInfo(
        id="ollama",
        label="Ollama (local)",
        description="Local Ollama — base URL + model (uses /api/generate)",
        default_model="gemma:2b",
        default_base_url="http://localhost:11434",
        requires_api_key=False,
        requires_base_url=True,
    ),
    LLMProviderInfo(
        id="litellm",
        label="LiteLLM / OpenAI-compatible",
        description="LiteLLM proxy or any OpenAI-compatible API — base URL, API key, model",
        default_model="gemma:2b",
        default_base_url="http://localhost:4000",
        requires_api_key=False,
        requires_base_url=True,
    ),
    LLMProviderInfo(
        id="openai",
        label="OpenAI",
        description="OpenAI API — base URL, API key, model",
        default_model="gpt-4o-mini",
        default_base_url="https://api.openai.com/v1",
        requires_api_key=True,
        requires_base_url=True,
    ),
    LLMProviderInfo(
        id="groq",
        label="Groq",
        description="Groq OpenAI-compatible API",
        default_model="llama-3.3-70b-versatile",
        default_base_url="https://api.groq.com/openai/v1",
        requires_api_key=True,
        requires_base_url=True,
    ),
]


def _mask_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


def _provider_flags(provider: str) -> tuple[bool, bool]:
    meta = next((p for p in PROVIDER_META if p.id == provider), None)
    if not meta:
        return provider != "ollama", True
    return meta.requires_base_url, meta.requires_api_key


class LLMService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_project(self, project_id: uuid.UUID, company_id: uuid.UUID) -> Project:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.company_id == company_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project not found")
        return project

    def _to_response(self, config: LLMConfig) -> LLMConfigResponse:
        decrypted = decrypt_value(config.api_key_encrypted) if config.api_key_encrypted else None
        uses_base_url, uses_api_key = _provider_flags(config.provider)
        return LLMConfigResponse(
            id=config.id,
            project_id=config.project_id,
            provider=config.provider,
            model=config.model,
            api_key_masked=_mask_key(decrypted),
            base_url=config.base_url,
            max_tokens=config.max_tokens,
            created_at=config.created_at,
            updated_at=config.updated_at,
            uses_base_url=uses_base_url,
            uses_api_key=uses_api_key,
        )

    @staticmethod
    def list_providers() -> list[LLMProviderInfo]:
        return PROVIDER_META

    async def get_config(self, user: User, project_id: uuid.UUID) -> LLMConfigResponse | None:
        await self._get_project(project_id, user.company_id)
        result = await self.db.execute(select(LLMConfig).where(LLMConfig.project_id == project_id))
        config = result.scalar_one_or_none()
        if not config:
            return None
        return self._to_response(config)

    async def save_config(self, user: User, project_id: uuid.UUID, payload: LLMConfigCreate) -> LLMConfigResponse:
        await self._get_project(project_id, user.company_id)
        result = await self.db.execute(select(LLMConfig).where(LLMConfig.project_id == project_id))
        config = result.scalar_one_or_none()

        if payload.api_key:
            encrypted_key = encrypt_value(payload.api_key)
        elif config:
            encrypted_key = config.api_key_encrypted
        else:
            encrypted_key = None

        defaults = PROVIDER_DEFAULTS.get(payload.provider, {})
        base_url = payload.base_url or defaults.get("base_url") or None
        if isinstance(base_url, str) and not base_url.strip():
            base_url = None

        if config:
            config.provider = payload.provider
            config.model = payload.model
            config.api_key_encrypted = encrypted_key
            config.base_url = base_url
            config.max_tokens = payload.max_tokens
        else:
            config = LLMConfig(
                project_id=project_id,
                provider=payload.provider,
                model=payload.model,
                api_key_encrypted=encrypted_key,
                base_url=base_url,
                max_tokens=payload.max_tokens,
            )
            self.db.add(config)

        await self.db.commit()
        await self.db.refresh(config)
        return self._to_response(config)

    async def test_connection(self, user: User, project_id: uuid.UUID) -> LLMTestResponse:
        await self._get_project(project_id, user.company_id)
        result = await self.db.execute(select(LLMConfig).where(LLMConfig.project_id == project_id))
        config = result.scalar_one_or_none()
        if not config:
            return LLMTestResponse(success=False, message="LLM config not set for this project")

        api_key = (
            decrypt_value(config.api_key_encrypted)
            if config.api_key_encrypted
            else None
        )

        try:
            if config.provider == "anthropic":
                key = api_key or settings.ANTHROPIC_API_KEY
                if not key:
                    return LLMTestResponse(success=False, message="No Anthropic API key configured")
                ok, msg = await test_anthropic(key, config.model)
                return LLMTestResponse(success=ok, message=msg)

            if config.provider == "ollama":
                ok, msg = await test_ollama_generate(config)
                return LLMTestResponse(success=ok, message=msg)

            if config.provider == "litellm":
                ok, msg = await test_openai_compatible(
                    config, api_key, default_base="http://localhost:4000"
                )
                return LLMTestResponse(success=ok, message=msg)

            if config.provider == "openai":
                if not api_key:
                    return LLMTestResponse(success=False, message="OpenAI API key is required")
                ok, msg = await test_openai_compatible(
                    config, api_key, default_base="https://api.openai.com/v1"
                )
                return LLMTestResponse(success=ok, message=msg)

            if config.provider == "groq":
                if not api_key:
                    return LLMTestResponse(success=False, message="Groq API key is required")
                ok, msg = await test_openai_compatible(
                    config, api_key, default_base="https://api.groq.com/openai/v1"
                )
                return LLMTestResponse(success=ok, message=msg)

            return LLMTestResponse(
                success=False,
                message=f"Unknown provider: {config.provider}",
            )
        except Exception as e:
            return LLMTestResponse(success=False, message=str(e)[:500])

    async def get_api_key(self, project_id: uuid.UUID) -> tuple[LLMConfig, str | None]:
        result = await self.db.execute(select(LLMConfig).where(LLMConfig.project_id == project_id))
        config = result.scalar_one_or_none()
        if not config:
            raise NotFoundError("LLM config not found")
        if config.api_key_encrypted:
            return config, decrypt_value(config.api_key_encrypted)
        if config.provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            return config, settings.ANTHROPIC_API_KEY
        return config, None
