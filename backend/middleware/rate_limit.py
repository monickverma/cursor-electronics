"""Rate limiting via slowapi.

The per-route limits come from the environment, so an operator can raise them
for a long evaluation run without a code change:

  POST /design/generate             — RATE_LIMIT_GENERATE    (10/hour)
  POST /design/{id}/patch           — RATE_LIMIT_PATCH       (20/hour)
  GET  /design/.../simulation/...   — RATE_LIMIT_SIMULATION  (100/hour)
  POST /pcb/compile                 — RATE_LIMIT_PCB         (60/hour)

RATE_LIMIT_ENABLED=false turns the limiter off entirely: the decorators stay
in place, and the limiter simply stops counting. It is a switch for a local
evaluation harness that must make dozens of calls, not a default — it is True
unless an operator says otherwise.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from core.config import Settings, settings


def build_limiter(config: Settings) -> Limiter:
    """A limiter whose master switch follows the settings.

    `Limiter.enabled` is the switch slowapi itself checks — in the middleware
    and in the decorator wrapper — so setting it here is the whole of "off".
    It is set *after* construction because slowapi reads a `RATELIMIT_ENABLED`
    key of its own out of the `.env` file, and the setting in `core.config` is
    the one this project answers to.
    """
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/hour"])
    limiter.enabled = config.rate_limit_enabled
    return limiter


limiter = build_limiter(settings)
