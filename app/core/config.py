from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Production note: never commit real DATABASE_URL, SECRET_KEY, Redis URL, or
    provider credentials. Use .env locally and managed secrets in deployment.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)

    APP_NAME: str = "RoadSoS Backend"
    ENVIRONMENT: str = "development"
    API_VERSION: str = "1.1.0"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/roadsos"
    REDIS_URL: Optional[str] = None

    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"])

    DEFAULT_RADIUS_KM: int = 10
    MAX_RADIUS_KM: int = 50
    MAX_VOLUNTEERS_RETURN: int = 12
    SERVICE_RADIUS_KM: int = 25

    # Rate limiting. SOS is stricter by user but allows legitimate repeats.
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_SOS_PER_MINUTE: int = 3
    RATE_LIMIT_RAG_PER_MINUTE: int = 20

    # Escalation ladder. Demo mode can shorten these values.
    ESCALATION_TIER1_SECONDS: int = 90
    ESCALATION_TIER2_SECONDS: int = 180
    ESCALATION_TIER3_SECONDS: int = 300
    ESCALATION_DEMO_MODE: bool = False

    # Notification providers. Set credentials in managed secrets.
    FCM_PROJECT_ID: Optional[str] = None
    FCM_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_TOKEN: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None
    SMS_PROVIDER_API_KEY: Optional[str] = None  # legacy/generic fallback
    SMS_FALLBACK_ENABLED: bool = True
    SMS_FALLBACK_NUMBER: str = "112"

    # Durable background work.
    TASK_QUEUE_BACKEND: str = "database"  # database | in_memory
    TASK_WORKER_POLL_SECONDS: float = 1.5
    TASK_LOCK_TIMEOUT_SECONDS: int = 900

    # Production resilience.
    REQUIRE_REDIS_IN_PRODUCTION: bool = False

    # RAG settings.
    RAG_TOP_K_SEMANTIC: int = 8
    RAG_TOP_K_KEYWORD: int = 8
    RAG_MAX_CONTEXT_CHARS: int = 6000
    RAG_MIN_CONFIDENCE: float = 0.18
    RAG_EMBEDDING_DIM: int = 384
    RAG_EMBEDDING_PROVIDER: str = "hashing"  # hashing | openai
    RAG_LLM_PROVIDER: str = "extractive"  # extractive | openai
    RAG_LLM_ENABLED: bool = False
    RAG_ALLOW_UNGROUNDED_ANSWERS: bool = False
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"prod", "production"}

    @property
    def asyncpg_ssl_required(self) -> bool:
        lowered = self.DATABASE_URL.lower()
        return "neon.tech" in lowered or "sslmode=require" in lowered


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
