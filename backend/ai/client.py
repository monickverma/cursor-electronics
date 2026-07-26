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
"""

import anthropic
from core.config import settings


def make_client() -> anthropic.Anthropic:
    kwargs: dict = {"api_key": settings.anthropic_api_key}

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
