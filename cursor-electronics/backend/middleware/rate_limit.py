"""Rate limiting via slowapi.

Limits per CLAUDE.md §Rate Limits:
  POST /design/generate   — 10/hour  (free)
  POST /design/{id}/patch — 20/hour  (free)
  GET  /design/.../sim/.. — 100/hour (free)
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["200/hour"])
