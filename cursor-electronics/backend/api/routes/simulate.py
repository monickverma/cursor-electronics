"""GET /design/{circuit_id}/simulation/{job_id} — poll simulation status."""

import uuid
from typing import Annotated, Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.rate_limit import limiter

from api.routes.auth import get_current_user
from core.ir_schema import CircuitIR
from core.ir_validator import validate_ir
from db.crud import get_design, save_output, update_design_ir
from db.models import get_db
from generators.netlist.spice import SpiceNetlistGenerator
from simulation.grader import SimulationGrader
from simulation.parser import SpiceResultParser
from tasks.simulation_task import run_simulation
from worker import app as celery_app

router = APIRouter()


class SimulationStatusResponse(BaseModel):
    job_id: str
    circuit_id: str
    status: str  # queued | running | complete | failed
    duration_ms: Optional[int] = None
    results: Optional[dict] = None
    grade: Optional[dict] = None
    error: Optional[str] = None


@router.get("/{circuit_id}/simulation/{job_id}", response_model=SimulationStatusResponse)
@limiter.limit("100/hour")
async def get_simulation_status(
    request: Request,
    circuit_id: str,
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    # Verify design belongs to user
    design = await get_design(db, circuit_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    if str(design.user_id) != str(user.id):
        raise HTTPException(403, detail="Access denied")

    # Check Celery result
    task_result: AsyncResult = celery_app.AsyncResult(job_id)
    state = task_result.state  # PENDING, STARTED, SUCCESS, FAILURE

    if state in ("PENDING", "STARTED"):
        return SimulationStatusResponse(
            job_id=job_id,
            circuit_id=circuit_id,
            status="running" if state == "STARTED" else "queued",
        )

    if state == "FAILURE":
        return SimulationStatusResponse(
            job_id=job_id,
            circuit_id=circuit_id,
            status="failed",
            error=str(task_result.result),
        )

    # SUCCESS — task_result.result is the dict returned by run_simulation
    result_data: dict = task_result.result or {}

    if result_data.get("status") == "failed":
        return SimulationStatusResponse(
            job_id=job_id,
            circuit_id=circuit_id,
            status="failed",
            duration_ms=result_data.get("duration_ms"),
            error=result_data.get("error"),
        )

    # Grade the results against IR spec
    grade_summary: Optional[dict] = None
    try:
        ir = CircuitIR.model_validate(design.ir_json)
        if ir.simulation_spec:
            parser = SpiceResultParser()
            parsed = parser.parse(result_data.get("stdout", ""), "")
            grader = SimulationGrader()
            grade = grader.grade(ir, parsed)
            grade_summary = {
                "passed": grade.passed,
                "failures": grade.failures,
                "notes": grade.notes,
            }
            # Persist simulation pass/fail back to IR
            ir_updated = ir.model_copy(update={"simulation_passed": grade.passed})
            await update_design_ir(db, circuit_id, ir_updated)
    except Exception:
        pass

    return SimulationStatusResponse(
        job_id=job_id,
        circuit_id=circuit_id,
        status="complete",
        duration_ms=result_data.get("duration_ms"),
        results={
            "dc_voltages": result_data.get("dc_voltages", {}),
            "ac_points_count": result_data.get("ac_points_count", 0),
        },
        grade=grade_summary,
    )


@router.post("/{circuit_id}/simulation/start")
async def start_simulation(
    circuit_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    """Manually trigger a new simulation run for an existing design."""
    design = await get_design(db, circuit_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    if str(design.user_id) != str(user.id):
        raise HTTPException(403, detail="Access denied")

    ir = CircuitIR.model_validate(design.ir_json)
    netlist = SpiceNetlistGenerator().generate(ir)
    job_id = str(uuid.uuid4())
    run_simulation.apply_async(args=[circuit_id, netlist, job_id, str(ir.application_class)], task_id=job_id)

    return {"job_id": job_id, "status": "queued"}
