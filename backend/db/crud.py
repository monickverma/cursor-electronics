"""Async CRUD operations for Circuit OS."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.ir_schema import CircuitIR
from db.models import CircuitDesign, GeneratedOutput, PatchHistory, SimulationRun, User


# ── User ─────────────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, hashed_password: str) -> User:
    user = User(email=email, hashed_password=hashed_password)
    db.add(user)
    await db.flush()
    return user


# ── Circuit designs ───────────────────────────────────────────────────────────

async def save_design(
    db: AsyncSession,
    ir: CircuitIR,
    user_id: str,
    intent_ir: Optional[dict] = None,
    annotations: Optional[list] = None,
) -> CircuitDesign:
    design = CircuitDesign(
        circuit_id=ir.circuit_id,
        user_id=uuid.UUID(user_id),
        version=ir.version,
        intent=ir.intent,
        application_class=ir.application_class,
        safety_class=ir.safety_class,
        target_mcu=ir.target_mcu,
        ir_json=ir.model_dump(mode="json"),
        intent_ir=intent_ir,
        annotations=annotations if annotations is not None else [],
        simulation_passed=ir.simulation_passed,
    )
    db.add(design)
    await db.flush()
    return design


async def get_design(db: AsyncSession, circuit_id: str) -> Optional[CircuitDesign]:
    result = await db.execute(
        select(CircuitDesign).where(CircuitDesign.circuit_id == circuit_id)
    )
    return result.scalar_one_or_none()


async def update_design_ir(db: AsyncSession, circuit_id: str, ir: CircuitIR) -> None:
    await db.execute(
        update(CircuitDesign)
        .where(CircuitDesign.circuit_id == circuit_id)
        .values(
            ir_json=ir.model_dump(mode="json"),
            version=ir.version,
            simulation_passed=ir.simulation_passed,
            updated_at=datetime.utcnow(),
        )
    )


async def update_design_revision(
    db: AsyncSession,
    circuit_id: str,
    ir: CircuitIR,
    intent_ir: dict,
    annotations: list,
) -> None:
    """A new revision: circuit, requirement and annotations move together."""
    await db.execute(
        update(CircuitDesign)
        .where(CircuitDesign.circuit_id == circuit_id)
        .values(
            ir_json=ir.model_dump(mode="json"),
            intent_ir=intent_ir,
            annotations=annotations,
            version=ir.version,
            simulation_passed=ir.simulation_passed,
            updated_at=datetime.utcnow(),
        )
    )


async def update_design_annotations(db: AsyncSession, circuit_id: str, annotations: list) -> None:
    await db.execute(
        update(CircuitDesign)
        .where(CircuitDesign.circuit_id == circuit_id)
        .values(annotations=annotations, updated_at=datetime.utcnow())
    )


async def list_user_designs(db: AsyncSession, user_id: str) -> list[CircuitDesign]:
    result = await db.execute(
        select(CircuitDesign)
        .where(CircuitDesign.user_id == uuid.UUID(user_id))
        .order_by(CircuitDesign.created_at.desc())
    )
    return list(result.scalars().all())


# ── Simulation runs ───────────────────────────────────────────────────────────

async def create_simulation_run(
    db: AsyncSession,
    circuit_id: str,
    netlist_text: str,
    celery_task_id: str,
    circuit_type: str = "",
) -> SimulationRun:
    run = SimulationRun(
        circuit_id=circuit_id,
        celery_task_id=celery_task_id,
        status="queued",
        circuit_type=circuit_type,
        netlist_text=netlist_text,
    )
    db.add(run)
    await db.flush()
    return run


async def get_simulation_run(db: AsyncSession, job_id: str) -> Optional[SimulationRun]:
    result = await db.execute(
        select(SimulationRun).where(SimulationRun.celery_task_id == job_id)
    )
    return result.scalar_one_or_none()


async def update_simulation_run(
    db: AsyncSession,
    job_id: str,
    status: str,
    results_json: Optional[dict] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    values: dict = {"status": status}
    if results_json is not None:
        values["results_json"] = results_json
    if error_message is not None:
        values["error_message"] = error_message
    if duration_ms is not None:
        values["duration_ms"] = duration_ms
    if status == "running":
        values["started_at"] = datetime.utcnow()
    elif status in ("complete", "failed"):
        values["completed_at"] = datetime.utcnow()

    await db.execute(
        update(SimulationRun)
        .where(SimulationRun.celery_task_id == job_id)
        .values(**values)
    )


# ── Patch history ─────────────────────────────────────────────────────────────

async def record_patch(
    db: AsyncSession,
    circuit_id: str,
    from_version: int,
    to_version: int,
    patch_json: dict,
    prompted_by: str,
    change_summary: Optional[str] = None,
) -> PatchHistory:
    patch = PatchHistory(
        circuit_id=circuit_id,
        from_version=from_version,
        to_version=to_version,
        patch_json=patch_json,
        change_summary=change_summary or f"v{from_version} → v{to_version}",
        prompted_by=prompted_by,
    )
    db.add(patch)
    await db.flush()
    return patch


async def list_patches(db: AsyncSession, circuit_id: str) -> list[PatchHistory]:
    result = await db.execute(
        select(PatchHistory)
        .where(PatchHistory.circuit_id == circuit_id)
        .order_by(PatchHistory.to_version.asc(), PatchHistory.created_at.asc())
    )
    return list(result.scalars().all())


# ── Generated outputs ─────────────────────────────────────────────────────────

async def save_output(
    db: AsyncSession,
    circuit_id: str,
    output_type: str,
    file_content: str,
    file_name: str,
) -> GeneratedOutput:
    out = GeneratedOutput(
        circuit_id=circuit_id,
        output_type=output_type,
        file_content=file_content,
        file_name=file_name,
    )
    db.add(out)
    await db.flush()
    return out
