import re
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# slowapi's own limit parser, re-used so that what this module accepts is
# exactly what slowapi will accept at request time. Imported through slowapi
# rather than from `limits` directly: slowapi is the dependency this project
# declares, and it is the one that will parse the string later.
from slowapi.wrappers import parse_many

_ENV_FILE = Path(__file__).parent.parent.parent / ".env"  # project root

#: A rate limit is slowapi's "<count>/<period>" form — "10/hour", "5/second".
_RATE_LIMIT_PATTERN = re.compile(r"^(\d+)/([A-Za-z]+)$")
#: The periods `limits` knows, for the error message.
_RATE_LIMIT_PERIODS = ("second", "minute", "hour", "day", "month", "year")


def validate_rate_limit(value: str, variable: str) -> str:
    """Check one rate-limit string, or refuse it — naming the variable.

    A bare count ("10") is not a limit slowapi can use, and a misspelled
    period ("banana/hour") is not one either. Both are refused here, at
    settings-construction time, rather than becoming a route that is quietly
    unlimited: a typo in the environment must not change the posture.
    """
    text = (value or "").strip()
    match = _RATE_LIMIT_PATTERN.match(text)
    if not match:
        raise ValueError(
            f"{variable} is not a valid rate limit: {value!r}. "
            f"Use '<count>/<period>' — e.g. '10/hour'. "
            f"Periods: {', '.join(_RATE_LIMIT_PERIODS)}."
        )
    if int(match.group(1)) < 1:
        raise ValueError(
            f"{variable} is not a valid rate limit: {value!r}. "
            f"The count must be at least 1. To remove the limit altogether, "
            f"set RATE_LIMIT_ENABLED=false."
        )
    try:
        parse_many(text)
    except ValueError as exc:
        raise ValueError(
            f"{variable} is not a valid rate limit: {value!r}. {exc}. "
            f"Use '<count>/<period>' — e.g. '10/hour'."
        ) from exc
    return text


class Settings(BaseSettings):
    # Required — app fails at startup if any of these are missing
    anthropic_api_key: str
    database_url: str
    redis_url: str
    secret_key: str  # minimum 32 chars for JWT signing

    # Optional with defaults
    anthropic_base_url: str = ""         # OpenRouter: https://openrouter.ai/api  (NO /v1 — SDK appends it)
    ai_model: str = "claude-sonnet-4-6"  # OpenRouter: anthropic/claude-sonnet-4-5

    # "anthropic" (default) or "openai_compat" — an OpenAI-compatible server
    # such as vLLM on ROCm, which is how Circuit OS runs on AMD GPUs. With
    # openai_compat, AI_MODEL is the served model name (e.g. Qwen/Qwen2.5-7B-Instruct)
    # and ANTHROPIC_API_KEY may be left empty. See docs/AMD.md.
    ai_provider: str = "anthropic"
    openai_base_url: str = "http://localhost:8000/v1"
    openai_api_key: str = "EMPTY"
    # openai_compat only ([2026-10-04]): a reasoning model's effort, sent as
    # OpenRouter's `reasoning.effort` (e.g. "high", "xhigh"). Empty sends nothing.
    # Reasoning tokens count against max_tokens and the timeout: raise
    # AI_TIMEOUT_SECONDS with it.
    ai_reasoning_effort: str = ""

    # The Anthropic SDK defaults to a 600s timeout and 2 retries. Left alone,
    # one slow upstream call occupies a request for up to half an hour and the
    # client sees an indefinite hang instead of an error. Bound it: a request
    # that exceeds this is a failure worth surfacing, not worth waiting on.
    # Raise ai_timeout_seconds if AI_MODEL is a large/slow model.
    ai_timeout_seconds: float = 45.0
    # The explanation is the one long answer (thousands of characters), so it
    # gets its own budget ([2026-10-04]: 35–90 s measured on a composed board
    # with deepseek-v4.1-flash, at every reasoning effort — it is output length,
    # not thinking). 0 uses ai_timeout_seconds.
    ai_explainer_timeout_seconds: float = 150.0
    ai_max_retries: int = 1
    celery_broker_url: str = ""          # defaults to redis_url if empty
    environment: str = "development"
    sentry_dsn: str = ""
    cors_origins: str = "http://localhost:3000"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # ── Rate limits ─────────────────────────────────────────────────────────
    # The per-route limits, in slowapi's "<count>/<period>" form. The defaults
    # are the limits the product has always had — an operator who sets nothing
    # gets exactly the posture of today. A malformed value is refused when the
    # settings are built, not when the route is first hit: a typo must not
    # quietly remove a limit.
    rate_limit_generate: str = "10/hour"      # POST /design/generate
    rate_limit_patch: str = "20/hour"         # POST /design/{id}/patch
    rate_limit_simulation: str = "100/hour"   # GET /design/{id}/simulation/{job_id}
    rate_limit_pcb: str = "60/hour"           # POST /pcb/compile
    # The master switch. True (the default) leaves every route limited; False
    # limits no route at all — for a local evaluation harness that must make
    # dozens of calls, not for a deployment that forgot to think about it.
    rate_limit_enabled: bool = True

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

    # Live distributor pricing (Mouser Search API) — optional. Empty: the BOM
    # shows only the static, dated catalogue prices. The key is the account
    # holder's own and is never logged. `brain/decisions.md` [2026-09-25].
    mouser_api_key: str = ""
    # How long a cached quote is reused before Mouser is asked again.
    price_cache_hours: float = 24.0

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

    @model_validator(mode="after")
    def _validate_rate_limits(self) -> "Settings":
        """Refuse a malformed rate limit at construction, naming the variable.

        A limit that cannot be parsed must never reach a route: slowapi logs
        the failure and registers *no* limit, which would turn a typo in
        RATE_LIMIT_GENERATE into an unlimited endpoint. Failing here, at
        startup, keeps the posture explicit.
        """
        for field_name, variable in (
            ("rate_limit_generate", "RATE_LIMIT_GENERATE"),
            ("rate_limit_patch", "RATE_LIMIT_PATCH"),
            ("rate_limit_simulation", "RATE_LIMIT_SIMULATION"),
            ("rate_limit_pcb", "RATE_LIMIT_PCB"),
        ):
            value = getattr(self, field_name)
            validated = validate_rate_limit(value, variable)
            # Normalise: strip the surrounding whitespace an env file may
            # carry, so the value the route registers is the value checked.
            setattr(self, field_name, validated)
        return self

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")


# Fails at import time if required vars are missing.
# This is intentional — better to crash on startup than at first request.
settings = Settings()
