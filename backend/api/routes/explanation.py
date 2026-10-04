"""
The explanation, delivered apart from the design. [2026-10-05].

POST /design/generate returns the design and queues its explanation
(`tasks/explain_task.py`); this route says where that stands — writing,
written, failed, or unavailable — and stores the text the first time it is read
back, so it outlives the task result. One explanation per design version.

A failure is kept as it happened and shown; an explanation is never an empty
string with no reason.

No `from __future__ import annotations` here: the pinned FastAPI resolves a
rate-limited endpoint's string annotations in slowapi's globals, where
`Annotated` does not exist (`tests/test_firmware_gate.py`).
"""

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.auth import get_current_user
from core.ir_schema import CircuitIR
from db.crud import get_design, get_output, save_output
from db.models import get_db
from middleware.rate_limit import limiter
from tasks.explain_task import explain_design

router = APIRouter()

#: Past this, a task nothing has heard from is queued again: its result has
#: expired, or the worker that held it is gone. Twice the explainer's budget.
STALE_AFTER_S = 300.0


class ExplanationView(BaseModel):
    #: writing | written | failed | unavailable (no worker to write it)
    status: str
    explanation: str = ""
    error: Optional[str] = None


def _task_id(circuit_id: str, version: int) -> str:
    return f"explain-{circuit_id}-v{version}"


def _file_name(circuit_id: str, version: int) -> str:
    return f"{circuit_id}.v{version}.md"


def queue_explanation(ir: CircuitIR) -> None:
    """Queue the design's explanation. Raises if there is no broker to take it."""
    explain_design.apply_async(args=[ir.model_dump(mode="json")], task_id=_task_id(ir.circuit_id, ir.version))


def _poll(circuit_id: str, version: int) -> Optional[dict]:
    """The finished task's result, or None while it runs (or when the backend cannot say)."""
    try:
        from celery.result import AsyncResult

        result = AsyncResult(_task_id(circuit_id, version), app=explain_design.app)
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


async def explanation_view(db: AsyncSession, ir: CircuitIR, design_age_s: float = 0.0) -> ExplanationView:
    """Where the design's explanation stands, storing it the first time it is read back."""
    stored = await get_output(db, ir.circuit_id, "explanation", _file_name(ir.circuit_id, ir.version))
    if stored is not None:
        return ExplanationView(status="written", explanation=stored.file_content)
    failed = await get_output(db, ir.circuit_id, "explanation_error", _file_name(ir.circuit_id, ir.version))
    if failed is not None:
        return ExplanationView(status="failed", error=failed.file_content)

    outcome = _poll(ir.circuit_id, ir.version)
    if outcome is None:
        if design_age_s > STALE_AFTER_S:
            try:
                queue_explanation(ir)
            except Exception as exc:  # noqa: BLE001
                return ExplanationView(status="unavailable",
                                       error=f"the explanation service is unavailable ({type(exc).__name__})")
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
