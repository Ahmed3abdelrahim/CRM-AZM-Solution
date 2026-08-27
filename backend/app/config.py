from functools import lru_cache
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str

    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "crm-attachments"
    MINIO_SECURE: bool = False

    LITELLM_API_BASE: str
    LITELLM_API_KEY: str
    LITELLM_MODEL_CHAT: str
    LITELLM_MODEL_CLASSIFY: str
    # PLAN.md F07 specifies 10s; docs/DEBT.md D13 documents the local dev override to 60s for
    # CPU-only inference (LiteLlmWrapper's own default of 10.0 stays the production-intended one).
    LITELLM_TIMEOUT_SECONDS: float = 10.0
    LITELLM_MAX_RETRIES: int = 1

    JWT_SECRET: str
    JWT_ACCESS_TTL_MINUTES: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7

    SYSTEM_DEFAULT_BRANCH_ID: UUID
    SYSTEM_DEFAULT_DEPARTMENT_ID: UUID

    CORS_ORIGINS: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
