from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://autopm:password@localhost:5432/autopm"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me-in-production-use-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: str = ""

    ANTHROPIC_API_KEY: str = ""
    GITHUB_MCP_SERVER_URL: str = "https://api.githubcopilot.com/mcp/"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_WORKER_CONCURRENCY: int = 10
    CELERY_QUEUES: str = "agent,default"

    API_V1_PREFIX: str = "/api/v1"

    @property
    def celery_broker_url(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_result_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or f"{self.REDIS_URL.rstrip('/0')}/1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
