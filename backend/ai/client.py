"""Shared Anthropic client factory.

Supports both direct Anthropic API and OpenRouter by reading env vars:
  ANTHROPIC_API_KEY  — Anthropic key (sk-ant-...) or OpenRouter key (sk-or-v1-...)
  ANTHROPIC_BASE_URL — leave empty for Anthropic direct; set to
                       https://openrouter.ai/api for OpenRouter.
                       NEVER add a /v1 suffix — the Anthropic SDK appends
                       /v1/messages itself, so .../api/v1 becomes
                       .../api/v1/v1/messages and OpenRouter returns a
                       404 HTML page instead of JSON.
  AI_MODEL           — model ID; defaults change depending on provider
  AI_TIMEOUT_SECONDS — per-request timeout (default 45s)
  AI_MAX_RETRIES     — SDK-level retries on transient errors (default 1)

The timeout and retry cap are not optional niceties. The SDK ships with a 600s
timeout and 2 retries, so a single stalled upstream call can hold a request for
~30 minutes; the caller just sees a hang. Every call site here is synchronous
and therefore runs in a threadpool, so an unbounded call also holds a worker
thread for that whole time.
"""

import anthropic
from core.config import settings


def make_client() -> anthropic.Anthropic:
    kwargs: dict = {
        "api_key": settings.anthropic_api_key,
        "timeout": settings.ai_timeout_seconds,
        "max_retries": settings.ai_max_retries,
    }

    if settings.anthropic_base_url:
        kwargs["base_url"] = settings.anthropic_base_url
        # OpenRouter requires HTTP-Referer
        kwargs["default_headers"] = {
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Circuit OS",
        }

    return anthropic.Anthropic(**kwargs)


def ai_model() -> str:
    return settings.ai_model


def timeout_detail(stage: str, exc: Exception) -> str:
    """Error text for a model call that ran out of time.

    Names the model and the budget, because the usual cause is AI_MODEL being
    set to something heavier than the timeout allows rather than a real outage.
    """
    return (
        f"{stage} timed out after {settings.ai_timeout_seconds:.0f}s "
        f"using model '{settings.ai_model}'. Either the provider is slow right "
        f"now or the model is too large for this budget — raise "
        f"AI_TIMEOUT_SECONDS or set AI_MODEL to a faster model. ({exc})"
    )
