from __future__ import annotations

<<<<<<< HEAD
import base64
import json
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
=======
from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, field_validator
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Production note: never commit real DATABASE_URL, SECRET_KEY, Redis URL, or
    provider credentials. Use .env locally and managed secrets in deployment.
    """

<<<<<<< HEAD
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")
=======
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0

    APP_NAME: str = "RoadSoS Backend"
    ENVIRONMENT: str = "development"
    API_VERSION: str = "1.1.0"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/roadsos"
<<<<<<< HEAD
    TEST_DATABASE_URL: Optional[str] = None
=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
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
<<<<<<< HEAD
=======
    FCM_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_TOKEN: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None
    SMS_PROVIDER_API_KEY: Optional[str] = None  # legacy/generic fallback
<<<<<<< HEAD
    FCM_SERVICE_ACCOUNT_JSON: Optional[str] = None
=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    SMS_FALLBACK_ENABLED: bool = True
    SMS_FALLBACK_NUMBER: str = "112"

    # Durable background work.
    TASK_QUEUE_BACKEND: str = "database"  # database | in_memory
    TASK_WORKER_POLL_SECONDS: float = 1.5
    TASK_LOCK_TIMEOUT_SECONDS: int = 900
<<<<<<< HEAD
    TASK_WORKER_CONCURRENCY: int = 4

    # Production resilience.
    REQUIRE_REDIS_IN_PRODUCTION: bool = False
    FIELD_ENCRYPTION_KEYS: Optional[str] = None
    FIELD_ENCRYPTION_REQUIRED_IN_PRODUCTION: bool = True
    ADMIN_BOOTSTRAP_ENABLED: bool = False
    ADMIN_BOOTSTRAP_TOKEN: Optional[str] = None
=======

    # Production resilience.
    REQUIRE_REDIS_IN_PRODUCTION: bool = False
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0

    # RAG settings.
    RAG_TOP_K_SEMANTIC: int = 8
    RAG_TOP_K_KEYWORD: int = 8
    RAG_MAX_CONTEXT_CHARS: int = 6000
    RAG_MIN_CONFIDENCE: float = 0.18
<<<<<<< HEAD
    RAG_EMBEDDING_DIM: int = 768
    RAG_EMBEDDING_PROVIDER: str = "hashing"  # hashing | gemini
    RAG_LLM_PROVIDER: str = "extractive"  # extractive | gemini | groq
    RAG_LLM_ENABLED: bool = False
    RAG_ALLOW_UNGROUNDED_ANSWERS: bool = False
    RAG_EMBEDDING_TIMEOUT_SECONDS: float = 20.0
    RAG_EMBEDDING_RETRIES: int = 2
    RAG_LLM_TIMEOUT_SECONDS: float = 10.0
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_CHAT_MODEL: str = "gemini-2.5-flash-lite"
    GROQ_API_KEY: Optional[str] = None
    GROQ_CHAT_MODEL: str = "llama-3.3-70b-versatile"
=======
    RAG_EMBEDDING_DIM: int = 384
    RAG_EMBEDDING_PROVIDER: str = "hashing"  # hashing | openai
    RAG_LLM_PROVIDER: str = "extractive"  # extractive | openai
    RAG_LLM_ENABLED: bool = False
    RAG_ALLOW_UNGROUNDED_ANSWERS: bool = False
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

<<<<<<< HEAD
    @field_validator("RAG_EMBEDDING_PROVIDER", "RAG_LLM_PROVIDER", "TASK_QUEUE_BACKEND", mode="before")
    @classmethod
    def lower_string_setting(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value

=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"prod", "production"}

    @property
    def asyncpg_ssl_required(self) -> bool:
        lowered = self.DATABASE_URL.lower()
        return "neon.tech" in lowered or "sslmode=require" in lowered

<<<<<<< HEAD
    @property
    def sqlalchemy_sync_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        else:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        # psycopg uses "sslmode" instead of asyncpg's "ssl"
        url = url.replace("?ssl=require", "?sslmode=require")
        url = url.replace("&ssl=require", "&sslmode=require")
        return url

    @property
    def has_redis(self) -> bool:
        return bool(self.REDIS_URL and self.REDIS_URL.strip())

    @property
    def has_field_encryption(self) -> bool:
        return bool(self.FIELD_ENCRYPTION_KEYS and self.FIELD_ENCRYPTION_KEYS.strip())

    @property
    def has_fcm_config(self) -> bool:
        return bool(self.FCM_PROJECT_ID and self.FCM_SERVICE_ACCOUNT_JSON)

    def fcm_service_account_errors(self) -> list[str]:
        if not self.FCM_SERVICE_ACCOUNT_JSON:
            return []
        try:
            parsed = json.loads(self.FCM_SERVICE_ACCOUNT_JSON)
        except json.JSONDecodeError:
            try:
                parsed = json.loads(base64.b64decode(self.FCM_SERVICE_ACCOUNT_JSON).decode("utf-8"))
            except Exception:
                return ["FCM_SERVICE_ACCOUNT_JSON must be raw JSON or base64 encoded JSON"]
        missing = [key for key in ("client_email", "private_key") if not parsed.get(key)]
        return [f"FCM_SERVICE_ACCOUNT_JSON missing {', '.join(missing)}"] if missing else []

    @property
    def has_twilio_config(self) -> bool:
        return bool(self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN and self.TWILIO_FROM_NUMBER)

    def production_config_errors(self) -> list[str]:
        if not self.is_production:
            return []
        errors: list[str] = []
        if self.SECRET_KEY == "change-this-in-production" or len(self.SECRET_KEY) < 48:
            errors.append("SECRET_KEY must be a non-default random value of at least 48 characters")
        if not self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            errors.append("DATABASE_URL must use the postgresql+asyncpg:// driver")
        if self.REQUIRE_REDIS_IN_PRODUCTION and not self.has_redis:
            errors.append("REDIS_URL is required when REQUIRE_REDIS_IN_PRODUCTION=true")
        if not self.REQUIRE_REDIS_IN_PRODUCTION:
            errors.append("REQUIRE_REDIS_IN_PRODUCTION must be true in production")
        if self.TASK_QUEUE_BACKEND != "database":
            errors.append("TASK_QUEUE_BACKEND must be database in production")
        if any(origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1") for origin in self.CORS_ORIGINS):
            errors.append("CORS_ORIGINS must not include localhost origins in production")
        if self.FIELD_ENCRYPTION_REQUIRED_IN_PRODUCTION and not self.has_field_encryption:
            errors.append("FIELD_ENCRYPTION_KEYS is required for encrypted medical profile storage")
        if not self.has_fcm_config:
            errors.append("FCM_PROJECT_ID and FCM_SERVICE_ACCOUNT_JSON are required for production push alerts")
        errors.extend(self.fcm_service_account_errors())
        if not self.has_twilio_config:
            errors.append("Twilio credentials are required for production SMS alerts")
        if self.RAG_EMBEDDING_PROVIDER not in {"hashing", "gemini"}:
            errors.append("RAG_EMBEDDING_PROVIDER must be hashing or gemini")
        if self.RAG_LLM_PROVIDER not in {"extractive", "gemini", "groq"}:
            errors.append("RAG_LLM_PROVIDER must be extractive, gemini, or groq")
        if self.RAG_EMBEDDING_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required when RAG_EMBEDDING_PROVIDER=gemini in production")
        if self.RAG_LLM_ENABLED and self.RAG_LLM_PROVIDER == "groq" and not (self.GROQ_API_KEY or self.GEMINI_API_KEY):
            errors.append("GROQ_API_KEY or GEMINI_API_KEY is required for enabled Groq/Gemini RAG generation")
        if self.ADMIN_BOOTSTRAP_ENABLED and (not self.ADMIN_BOOTSTRAP_TOKEN or len(self.ADMIN_BOOTSTRAP_TOKEN) < 48):
            errors.append("ADMIN_BOOTSTRAP_TOKEN must be at least 48 characters when bootstrap is enabled")
        return errors

    def validate_startup_configuration(self) -> None:
        errors = self.production_config_errors()
        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))

=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
