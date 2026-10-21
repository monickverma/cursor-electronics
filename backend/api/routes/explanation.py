"""
The explanation, delivered apart from the design. [2026-10-05].

POST /design/generate returns the design and queues its explanation
(`tasks/explain_task.py`); this route says where that stands — writing,
written, failed, or unavailable — and stores the text the first time it is read
back, so it outlives the task result. One explanation per design version.

A failure is kept as it happened and shown; an explanation is never an empty
string with no reason.

[2026-10-21, F-0006] The route used to re-queue the task on every poll that
landed while it was still running. The task id was deterministic
(`explain-{circuit_id}-v{version}`), so each re-queue *replaced* the attempt
already in the broker: the poll could never see the result, so it re-queued
again, and the loop never ended. Every cycle cost one 35–90 s model call.
The attempt ledger below makes the count durable and the id unique, so a
re-queue can only ever add an attempt, never destroy one.

No `from __future__ import annotations` here: the pinned FastAPI resolves a
rate-limited endpoint's string annotations in slowapi's globals, where
`Annotated` does not exist (`tests/test_firmware_gate.py`).
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.auth import get_current_user
from core.ir_schema import CircuitIR
from db.crud import get_design, get_output, get_explanation_attempt, record_explanation_attempt, save_output
from db.models import get_db
from middleware.rate_limit import limiter
from tasks.explain_task import explain_design

router = APIRouter()

#: Past this, a task nothing has heard from is *considered* for a retry: its
#: result has expired, or the worker that held it is gone. Twice the
#: explainer's budget.
STALE_AFTER_S = 300.0

#: How many times one design version's explanation may be queued in total —
#: the first attempt plus one retry. The first attempt is what the generate
#: route queues; the retry covers the one real failure mode there is, a task
#: that was lost (the worker died, or the broker dropped it before it ran).
#: A second retry would pay for another model answer to fix a failure that
#: one retry has already had its chance at, and the failure is reported
#: honestly either way. One retry is the whole budget.
MAX_ATTEMPTS = 2


class ExplanationView(BaseModel):
    #: writing | written | failed | unavailable (no worker to write it)
    status: str
    explanation: str = ""
    error: Optional[str] = None


def _task_id(circuit_id: str, version: int) -> str:
    """The id of the *first* attempt. Kept stable so the design version's
    attempt row and any earlier record still name the same task."""
    return f"explain-{circuit_id}-v{version}"


def _attempt_task_id(circuit_id: str, version: int, attempt: int) -> str:
    """
    The Celery id of one attempt.

    Every attempt gets its own id, and the retry's differs from the first's.
    That is the whole point: Celery's result backend and the broker key a
    queued task by its id, so re-using one id for a second `apply_async`
    *replaces* the task in flight — the running attempt is cancelled, its
    result is never written, and the poll that was waiting for it re-queues
    again, for ever. Distinct ids make a retry additive: the attempt already
    running keeps running and is still polled.
    """
    if attempt <= 1:
        return _task_id(circuit_id, version)
    return f"{_task_id(circuit_id, version)}-r{attempt - 1}"


def _file_name(circuit_id: str, version: int) -> str:
    return f"{circuit_id}.v{version}.md"


def queue_explanation(ir: CircuitIR, attempt: int = 1) -> str:
    """Queue the design's explanation as attempt `attempt`; return its task id.

    Raises if there is no broker to take it.
    """
    task_id = _attempt_task_id(ir.circuit_id, ir.version, attempt)
    explain_design.apply_async(args=[ir.model_dump(mode="json")], task_id=task_id)
    return task_id


def _poll(task_id: str) -> Optional[dict]:
    """The finished task's result, or None while it runs (or when the backend cannot say)."""
    try:
        from celery.result import AsyncResult

        result = AsyncResult(task_id, app=explain_design.app)
        if not result.ready():
            return None
        if result.failed():
            return {"status": "failed", "explanation": "", "error": f"the explain task raised: {result.result!r}"}
        return dict(result.result)
    except Exception:  # noqa: BLE001 — a backend that cannot answer means "still writing"
        return None


def _age_s(when: Optional[datetime]) -> float:
    if when is None:
        return 0.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).total_seconds()


def _is_lost(task_id: Optional[str], age_s: float) -> bool:
    """
    Is the attempt we queued genuinely gone, or merely slow?

    Celery's own view cannot tell the two apart: `AsyncResult.state` is
    PENDING both for a task that was never sent and for one that is queued
    and has not started yet, and a task that has been running for longer than
    the stale window is still running, not lost. So the decision is not left
    to Celery: the attempt ledger in PostgreSQL is the record of what *we*
    queued and when. A row that says an attempt was queued at T, plus a
    Celery state of PENDING at a time well after T, means the message was
    taken by a worker and then lost (the worker died, or the broker dropped
    it) — a task Celery still believes is queued would be STARTED once a
    worker picks it up, and a task nobody ever took is still PENDING only
    because the queue is empty or no worker is alive.

    The one thing this cannot see is a task that is queued behind a long
    simulation in the same worker. That case is safe: the attempt is not
    lost, so it is not retried, and the poll keeps saying "writing" until it
    answers.

    `age_s` is how long ago the attempt was queued — the ledger's own clock
    when there is one, and the design's age otherwise.
    """
    if task_id is None:
        return True  # nothing was ever queued for this version
    try:
        from celery.result import AsyncResult

        state = AsyncResult(task_id, app=explain_design.app).state
    except Exception:  # noqa: BLE001 — a backend that cannot answer: assume it is alive
        return False
    if state in ("STARTED", "RETRY", "RECEIVED"):
        return False
    if state == "SUCCESS" or state == "FAILURE":
        return False  # it answered; the poll will read it
    # PENDING: never sent, or queued and not started. Only the clock can
    # separate "queued and waiting" from "gone".
    return age_s > STALE_AFTER_S


async def explanation_view(db: AsyncSession, ir: CircuitIR, design_age_s: float = 0.0) -> ExplanationView:
    """Where the design's explanation stands, storing it the first time it is read back."""
    stored = await get_output(db, ir.circuit_id, "explanation", _file_name(ir.circuit_id, ir.version))
    if stored is not None:
        return ExplanationView(status="written", explanation=stored.file_content)
    failed = await get_output(db, ir.circuit_id, "explanation_error", _file_name(ir.circuit_id, ir.version))
    if failed is not None:
        return ExplanationView(status="failed", error=failed.file_content)

    ledger = await get_explanation_attempt(db, ir.circuit_id, ir.version)
    attempts = ledger.attempts if ledger is not None else 0
    queued_task_id = ledger.task_id if ledger is not None else None
    queued_at = getattr(ledger, "queued_at", None) if ledger is not None else None

    # What to poll. A design made before the ledger existed has a task under
    # the first-attempt id and no row, so that id is what we read.
    poll_task_id = queued_task_id or _task_id(ir.circuit_id, ir.version)
    # How long the attempt has been waiting. The ledger's clock is the exact
    # one; without a row, the design's age is the best we have.
    age_s = _age_s(queued_at) if queued_at is not None else design_age_s

    outcome = _poll(poll_task_id)
    if outcome is None:
        if attempts >= MAX_ATTEMPTS:
            # The budget is spent. Say so rather than pay for another answer.
            return ExplanationView(
                status="unavailable",
                error=(f"the explanation was queued {attempts} times and no worker has answered; "
                       f"the queue is not delivering tasks (is a Celery worker running?)"))
        if design_age_s > STALE_AFTER_S and _is_lost(queued_task_id, age_s):
            # Genuinely lost: the attempt we queued is neither running nor
            # queued any more. Queue it again under a *new* id, so the
            # attempt in flight (if any) is not replaced.
            attempt = attempts + 1
            try:
                new_task_id = queue_explanation(ir, attempt)
            except Exception as exc:  # noqa: BLE001
                return ExplanationView(status="unavailable",
                                       error=f"the explanation service is unavailable ({type(exc).__name__})")
            await record_explanation_attempt(db, ir.circuit_id, ir.version, attempt, new_task_id)
            return ExplanationView(status="writing")
        return ExplanationView(status="writing")
    if outcome.get("status") == "written":
        await save_output(db, ir.circuit_id, "explanation", outcome["explanation"],
                          _file_name(ir.circuit_id, ir.version))
        return ExplanationView(status="written", explanation=outcome["explanation"])
    error = outcome.get("error") or "the explanation could not be written"
    await save_output(db, ir.circuit_id, "explanation_error", error, _file_name(ir.circuit_id, ir.version))
    return ExplanationView(status="failed", error=error)


@router.get("/{circuit_id}/explanation", response_model=ExplanationView)
@limiter.limit("200/hour")
async def get_explanation(
    request: Request,
    circuit_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    """Poll a design's explanation. It is written after the design is returned."""
    design = await get_design(db, circuit_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    if str(design.user_id) != str(user.id):
        raise HTTPException(403, detail="Access denied")
    return await explanation_view(db, CircuitIR.model_validate(design.ir_json),
                                  _age_s(getattr(design, "updated_at", None)))
