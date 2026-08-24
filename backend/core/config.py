from pathlib import Path

from pydantic import model_validator
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

    # The Anthropic SDK defaults to a 600s timeout and 2 retries. Left alone,
    # one slow upstream call occupies a request for up to half an hour and the
    # client sees an indefinite hang instead of an error. Bound it: a request
    # that exceeds this is a failure worth surfacing, not worth waiting on.
    # Raise ai_timeout_seconds if AI_MODEL is a large/slow model.
    ai_timeout_seconds: float = 45.0
    ai_max_retries: int = 1
    celery_broker_url: str = ""          # defaults to redis_url if empty
    environment: str = "development"
    sentry_dsn: str = ""
    cors_origins: str = "http://localhost:3000"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # The PCB engine was pulled forward from Phase 3 and is experimental: its
    # placement is tested, its routing is not, and it silently drops components
    # it has no footprint for. Scope decision 2026-08-22 is "experimental and
    # labelled", not "disabled" — so it is available in development and off in
    # production, rather than off everywhere.
    #
    # None means "derive from environment", resolved below. An explicit
    # PCB_ENGINE_ENABLED overrides that in either direction. The default is
    # deliberately not a bare True: a production deploy that never sets the
    # variable must not end up serving an untested surface by omission.
    pcb_engine_enabled: bool | None = None

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _resolve_pcb_engine_default(self) -> "Settings":
        """Turn the None sentinel into a real bool once `environment` is known.

        Done here rather than in a property so every caller sees a plain bool
        and the route stays a simple flag check.
        """
        if self.pcb_engine_enabled is None:
            self.pcb_engine_enabled = not self.is_production
        return self

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")


# Fails at import time if required vars are missing.
# This is intentional — better to crash on startup than at first request.
settings = Settings()
