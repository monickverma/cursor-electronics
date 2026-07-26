from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent.parent / ".env"  # project root


class Settings(BaseSettings):
    # Required — app fails at startup if any of these are missing
    anthropic_api_key: str
    database_url: str
    redis_url: str
    secret_key: str  # minimum 32 chars for JWT signing

    # Optional with defaults
    anthropic_base_url: str = ""         # OpenRouter: https://openrouter.ai/api  (NO /v1 — SDK appends it)
    ai_model: str = "claude-sonnet-4-6"  # OpenRouter: anthropic/claude-sonnet-4-5
    celery_broker_url: str = ""          # defaults to redis_url if empty
    environment: str = "development"
    sentry_dsn: str = ""
    cors_origins: str = "http://localhost:3000"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")


# Fails at import time if required vars are missing.
# This is intentional — better to crash on startup than at first request.
settings = Settings()
