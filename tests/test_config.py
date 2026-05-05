from app.core.config import Settings


def test_development_config_allows_empty_external_provider_keys():
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        RAG_EMBEDDING_PROVIDER="gemini",
        RAG_LLM_PROVIDER="groq",
        RAG_LLM_ENABLED=True,
        GEMINI_API_KEY=None,
        GROQ_API_KEY=None,
    )
    assert settings.production_config_errors() == []


def test_production_config_requires_core_secrets_and_providers():
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY="short",
        REDIS_URL=None,
        REQUIRE_REDIS_IN_PRODUCTION=True,
        TASK_QUEUE_BACKEND="in_memory",
        CORS_ORIGINS=["http://localhost:3000"],
        FIELD_ENCRYPTION_KEYS=None,
        FCM_PROJECT_ID=None,
        FCM_SERVICE_ACCOUNT_JSON=None,
        TWILIO_ACCOUNT_SID=None,
        TWILIO_AUTH_TOKEN=None,
        TWILIO_FROM_NUMBER=None,
    )
    errors = settings.production_config_errors()
    assert any("SECRET_KEY" in error for error in errors)
    assert any("REDIS_URL" in error for error in errors)
    assert any("TASK_QUEUE_BACKEND" in error for error in errors)
    assert any("FCM" in error for error in errors)
    assert any("Twilio" in error for error in errors)
