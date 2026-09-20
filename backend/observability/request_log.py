"""
Request instrumentation — one row per request.

`PHASE_2_PLAN_v2.md` §4.5: instrumentation is Stage 0 and non-negotiable.
"Data not logged is gone permanently, and every later question — fine-tune,
swap models, drop the LLM, price the free tier, which generator to author
next — is unanswerable without it."

Two rules this module exists to enforce, both of them failure modes the naive
version has:

1. **A log write must never fail a request.** Observability that can take down
   the thing it observes is worse than no observability. Every write is
   wrapped, and a write that cannot reach Postgres falls back to a JSONL
   sidecar rather than raising.

2. **A log write must never be lost because the request failed.** The rows
   most worth having come from requests that went wrong — and those are
   exactly the rows a shared transaction throws away. `db.models.get_db()`
   rolls back on exception, so a row added to the request's session would
   vanish on precisely the failures §4.5 wants counted. This module therefore
   opens its own session and commits independently.

The out-of-envelope log is the generator backlog (§4.5): a refused request is
a specification for the next generator. That is why `refusal_reason` is a
first-class column with a validator behind it, not an error string in a blob.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Sidecar for rows that could not reach Postgres. Same pattern as
# simulation/monitor.py and for the same reason: a row on disk is recoverable,
# a row that was never written is not.
#
# Overridable by env var, and `tests/conftest.py` sets it. Without that, the
# suite appends a row for every request any test makes through the app — none
# of which can reach a database — and the file grows inside the source tree
# forever. An observability sink that pollutes the repo it observes is a bug
# regardless of how harmless the data is.
_FALLBACK_PATH = Path(
    os.environ.get("REQUEST_LOG_FALLBACK_PATH")
    or Path(__file__).parent / "request_log_fallback.jsonl"
)

# Bumped whenever the row shape changes. Half of the §4.4 cache key
# (prompt_hash + schema_version), so it must not vary per deployment.
LOG_SCHEMA_VERSION = "1.1.0"


class Outcome(str, Enum):
    """
    What happened to the request. REFUSED is not a failure — it is
    `envelope()` doing its job, and it is the row that feeds the backlog.
    """

    COMPLETED = "completed"
    REFUSED = "refused"
    FAILED = "failed"
    ABANDONED = "abandoned"
    PATCHED = "patched"


class RequestLogRow(BaseModel):
    """
    One request, one row.

    Stage 0 gate: "Every request produces a complete log row — G1
    (schema-enforced)." Completeness is enforced here, at construction, rather
    than checked by sampling afterwards: an incomplete row cannot be built.

    What counts as complete is keyed on **what the request did**, not on which
    route it hit, and it tightens as later stages land. Today:

      - a REFUSED row must carry a `refusal_reason` and a `prompt_hash`
      - any row carrying a `circuit_id` must carry a `prompt_hash`, because a
        design that exists came from a prompt
      - everything else — a read-only route that completed, a request that
        died before its body was read — needs neither, and must not be forced
        to invent one

    Ratcheted in Stage 1 (LOG_SCHEMA_VERSION 1.1.0): a row carrying a
    `circuit_id` must also carry `intent_ir` and `generator`, because a design
    now comes from a recorded requirement dispatched to a named generator.
    Rows written before the ratchet keep their own `schema_version`, so a
    query can tell which contract a row was written under.
    """

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    # Always required
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    route: str
    outcome: Outcome
    latency_ms: int
    api_calls: int = 0
    schema_version: str = LOG_SCHEMA_VERSION

    # Required once the request got far enough — see the validator
    prompt_hash: Optional[str] = None

    # Populated by Stage 1: IntentIR, registry dispatch, envelope()
    intent_ir: Optional[Dict[str, Any]] = None
    underdetermined: Optional[List[str]] = None
    generator: Optional[str] = None  # name@version
    refusal_reason: Optional[str] = None

    # Context, best effort
    user_id: Optional[str] = None
    circuit_id: Optional[str] = None
    status_code: Optional[int] = None
    error: Optional[str] = None

    @model_validator(mode="after")
    def _require_for_outcome(self) -> "RequestLogRow":
        # Keyed on what the request did, not on which route it hit. A GET that
        # lists designs has no prompt and must not be forced to invent one;
        # a refusal or a produced design always had one.
        if self.outcome == Outcome.REFUSED.value:
            if not self.refusal_reason:
                raise ValueError(
                    "outcome=refused requires refusal_reason — an unexplained "
                    "refusal teaches nothing, and the refusal log is the backlog"
                )
            if not self.prompt_hash:
                raise ValueError(
                    "outcome=refused requires prompt_hash — a refusal is always "
                    "a refusal of something"
                )
        if self.circuit_id:
            # The Stage 1 ratchet, as Stage 0 promised. A design now comes
            # from an IntentIR dispatched to a named generator, so a row
            # claiming a design without recording either cannot answer the
            # §4.5 questions it exists for — which generator to author next,
            # what a design cost, whether the form or the LLM produced it.
            missing = [
                field for field, value in (
                    ("prompt_hash", self.prompt_hash),
                    ("intent_ir", self.intent_ir),
                    ("generator", self.generator),
                ) if not value
            ]
            if missing:
                raise ValueError(
                    f"a row carrying circuit_id requires {missing} — a design "
                    f"that exists came from a recorded requirement dispatched "
                    f"to a named generator"
                )
        if self.latency_ms < 0:
            raise ValueError("latency_ms must not be negative")
        return self


def prompt_hash(prompt: str) -> str:
    """
    Stable hash of a prompt, for the §4.4 cache key and for counting repeats
    without storing the text a second time — the raw prompt already lives in
    `circuit_designs.intent`.
    """
    return hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()


class RequestLogContext:
    """
    Mutable per-request scratch space. The middleware creates one, the handler
    enriches it, the middleware flushes it in a `finally`.

    This indirection is what makes the gate true by construction. If handlers
    called `record()` themselves, "every request produces a row" would hold
    only for the paths someone remembered to instrument — and the forgotten
    paths are the interesting ones.
    """

    def __init__(self, route: str) -> None:
        self.route = route
        # Pessimistic default. A request that dies before any handler code
        # runs is a failure, and should read as one without anyone setting it.
        self.outcome: Outcome = Outcome.FAILED
        self.api_calls: int = 0
        self.prompt_hash: Optional[str] = None
        self.intent_ir: Optional[Dict[str, Any]] = None
        self.underdetermined: Optional[List[str]] = None
        self.generator: Optional[str] = None
        self.refusal_reason: Optional[str] = None
        self.user_id: Optional[str] = None
        self.circuit_id: Optional[str] = None
        self.status_code: Optional[int] = None
        self.error: Optional[str] = None

    def count_api_call(self, n: int = 1) -> None:
        """Every model call, including ones that failed. §4.4 counts the waste."""
        self.api_calls += n

    def refuse(self, reason: str) -> None:
        self.outcome = Outcome.REFUSED
        self.refusal_reason = reason

    def complete(self, circuit_id: Optional[str] = None) -> None:
        self.outcome = Outcome.COMPLETED
        if circuit_id:
            self.circuit_id = circuit_id

    def to_row(self, latency_ms: int) -> RequestLogRow:
        return RequestLogRow(
            route=self.route,
            outcome=self.outcome,
            latency_ms=latency_ms,
            api_calls=self.api_calls,
            prompt_hash=self.prompt_hash,
            intent_ir=self.intent_ir,
            underdetermined=self.underdetermined,
            generator=self.generator,
            refusal_reason=self.refusal_reason,
            user_id=self.user_id,
            circuit_id=self.circuit_id,
            status_code=self.status_code,
            error=self.error,
        )


def log_ctx(request: Any) -> RequestLogContext:
    """
    The request's log context, or a detached throwaway if the middleware is not
    installed — as in unit tests that exercise a router directly.

    Handlers must never have to null-check instrumentation. A null check that
    can be forgotten is how "every request produces a row" quietly becomes
    "most requests do".
    """
    state = getattr(request, "state", None)
    ctx = getattr(state, "log_ctx", None)
    if isinstance(ctx, RequestLogContext):
        return ctx
    return RequestLogContext(route="<uninstrumented>")


class RequestLogger:
    """Writes rows. Never raises into the caller."""

    def __init__(self, fallback_path: Path = _FALLBACK_PATH) -> None:
        self._fallback_path = fallback_path

    async def record(self, row: RequestLogRow) -> bool:
        """
        Persist one row. True if it reached Postgres, False if it went to the
        sidecar. Never raises — a logging failure is not a request failure.
        """
        try:
            await self._write_db(row)
            return True
        except Exception:
            self.write_fallback(row)
            return False

    async def _write_db(self, row: RequestLogRow) -> None:
        # Imported here rather than at module scope: db.models builds an async
        # engine at import time, and this module must stay importable in unit
        # tests that have no database driver installed.
        from sqlalchemy.ext.asyncio import AsyncSession

        from db.models import RequestLog, engine

        data = row.model_dump()
        # created_at travels as an ISO string so the row stays JSON-round-
        # trippable for the sidecar; the column is TIMESTAMPTZ.
        data["created_at"] = datetime.fromisoformat(data["created_at"])

        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(RequestLog(**data))
            await session.commit()

    def write_fallback(self, row: RequestLogRow) -> None:
        """
        Last resort. Swallows its own errors too: if the disk is gone as well
        there is nothing further to try, and raising here would defeat the
        purpose of the module.
        """
        try:
            self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._fallback_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row.model_dump(), default=str) + "\n")
        except Exception:
            pass

    def read_fallback(self) -> List[dict]:
        """Rows that never reached Postgres. Replay source, and a health signal."""
        if not self._fallback_path.exists():
            return []
        rows: List[dict] = []
        with open(self._fallback_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows
