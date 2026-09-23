"""
Firmware is shown only once it compiles. Stage 5 gate 1.

    GET /design/{circuit_id}/firmware — the design's firmware and its build status

`firmware_view` is the one gate both the generate and the patch routes go
through, so no response carries firmware source that has not built. A design's
firmware is a PlatformIO project (`generators/firmware/project.py`) keyed by
its SHA-256; `firmware_builds` caches the result per hash, so identical
firmware compiles once. A new build is a Celery task
(`tasks/firmware_task.py`), never inline: `brain/decisions.md` [2026-09-23]
Stage 5, item 7.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.auth import get_current_user
from core.ir_schema import CircuitIR
from db.crud import (
    finish_firmware_build,
    get_design,
    get_firmware_build,
    queue_firmware_build,
    requeue_firmware_build,
)
from db.models import get_db
from generators.firmware.compile_gate import BUILD_TIMEOUT_S
from generators.firmware.project import FirmwareProject, project_for
from middleware.rate_limit import limiter
from tasks.firmware_task import compile_firmware

router = APIRouter()

#: A build runs for at most BUILD_TIMEOUT_S. A row still queued after twice
#: that has lost its result — the worker died, or the result backend expired it
#: (`worker.py`, one hour) before anyone polled — so it is dispatched again. A
#: rebuild with a warm cache costs seconds; a row stuck on "compiling" forever
#: would hide the firmware for good.
STALE_AFTER_S = 2 * BUILD_TIMEOUT_S


class FirmwareView(BaseModel):
    #: none (no MCU) | compiling | compiled | failed | unavailable (no worker)
    status: str
    message: str
    target: Optional[str] = None
    board: Optional[str] = None
    build: Optional[str] = None
    #: Present only when status is "compiled".
    firmware: Optional[str] = None
    platformio_ini: Optional[str] = None
    #: The build log's tail, when it failed.
    log: Optional[str] = None


def _task_id(build_hash: str) -> str:
    return f"firmware-{build_hash}"


def _dispatch(project: FirmwareProject) -> None:
    compile_firmware.apply_async(args=[project.hash, [list(f) for f in project.files], project.target],
                                 task_id=_task_id(project.hash))


def _age_s(when: Optional[datetime]) -> float:
    # No timestamp (the column is NOT NULL, so never in PostgreSQL) reads as
    # fresh: re-dispatching on every poll would be worse than waiting.
    if when is None:
        return 0.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).total_seconds()


def _poll(build_hash: str) -> Optional[dict]:
    """The finished build's result, or None while it runs (or when the backend cannot say)."""
    try:
        from celery.result import AsyncResult

        result = AsyncResult(_task_id(build_hash), app=compile_firmware.app)
        if not result.ready():
            return None
        if result.failed():
            return {"status": "failed", "log": f"the build task raised: {result.result!r}", "seconds": 0.0}
        return dict(result.result)
    except Exception:  # noqa: BLE001 — a backend that cannot answer means "still compiling"
        return None


async def firmware_view(db: AsyncSession, ir: CircuitIR) -> FirmwareView:
    """The design's firmware if its build passed; otherwise its status. Never unbuilt source."""
    project = project_for(ir)
    if project is None:
        return FirmwareView(status="none", message="this design has no microcontroller, so no firmware")
    base: dict[str, Any] = dict(target=project.target, board=project.board, build=project.hash)
    row = await get_firmware_build(db, project.hash)
    status = row.status if row is not None else None
    log = row.log if row is not None else None
    unavailable = lambda exc: FirmwareView(  # noqa: E731 — no broker: say so rather than show unbuilt source
        status="unavailable", **base,
        message=f"the compile service is unavailable ({type(exc).__name__}); firmware "
                f"is shown only once it has compiled for the {project.board}")
    if row is None:
        try:
            _dispatch(project)
        except Exception as exc:  # noqa: BLE001
            return unavailable(exc)
        await queue_firmware_build(db, project.hash, project.target)
        status = "queued"
    if status == "queued":
        outcome = _poll(project.hash)
        if outcome is None:
            if row is not None and _age_s(getattr(row, "created_at", None)) > STALE_AFTER_S:
                try:
                    _dispatch(project)
                except Exception as exc:  # noqa: BLE001
                    return unavailable(exc)
                await requeue_firmware_build(db, project.hash)
            return FirmwareView(status="compiling", **base,
                                message=f"compiling for the {project.board}; firmware appears once it builds")
        await finish_firmware_build(db, project.hash, outcome["status"], outcome.get("log", ""),
                                    float(outcome.get("seconds", 0.0)))
        status, log = outcome["status"], outcome.get("log", "")
    if status == "passed":
        return FirmwareView(status="compiled", **base, message=f"compiled for the {project.board}",
                            firmware=project.source, platformio_ini=project.file("platformio.ini"))
    return FirmwareView(status="failed", **base, log=log,
                        message=f"the firmware did not compile for the {project.board}; it is not shown")


@router.get("/{circuit_id}/firmware", response_model=FirmwareView)
@limiter.limit("100/hour")
async def get_firmware(
    request: Request,
    circuit_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    """Poll a design's firmware build. The source appears only once it has compiled."""
    design = await get_design(db, circuit_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    if str(design.user_id) != str(user.id):
        raise HTTPException(403, detail="Access denied")
    return await firmware_view(db, CircuitIR.model_validate(design.ir_json))
