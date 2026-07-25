"""POST /design/generate — full pipeline: intent → IR → all outputs."""

import uuid
from typing import Annotated, Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.rate_limit import limiter

from ai.circuit_reasoner import CircuitGenerationError, CircuitReasoner
from ai.explainer import ExplanationEngine
from ai.intent_parser import IntentParser
from api.routes.auth import get_current_user
from core.ir_schema import CircuitIR
from core.ir_validator import validate_ir
from db.crud import list_user_designs, save_design, save_output
from db.models import get_db
from generators.bom.compiler import BOMCompiler
from generators.firmware.arduino import ArduinoFirmwareGenerator
from generators.netlist.spice import SpiceNetlistGenerator
from generators.schematic.kicad import KiCadSchematicGenerator
from tasks.simulation_task import run_simulation
from validation.rule_engine import HardwareRuleEngine

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str
    project_id: Optional[str] = None


class GenerateResponse(BaseModel):
    circuit_id: str
    intent: str
    application_class: str
    target_mcu: Optional[str]
    version: int
    simulation_job_id: Optional[str]
    validation: dict
    firmware: Optional[str]
    schematic: str
    bom: list
    explanation: str
    ir: dict


@router.post("/generate", response_model=GenerateResponse, status_code=201)
@limiter.limit("10/hour")
async def generate_design(
    request: Request,
    body: GenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    # 1. Parse intent
    try:
        spec = IntentParser().parse(body.prompt)
    except anthropic.APIError as exc:
        raise HTTPException(503, detail=f"AI service unavailable: {exc}")

    # 2. Generate IR
    try:
        ir = CircuitReasoner().generate(spec)
    except anthropic.APIError as exc:
        raise HTTPException(503, detail=f"AI service unavailable: {exc}")
    except CircuitGenerationError as exc:
        raise HTTPException(422, detail={
            "error": "circuit_generation_failed",
            "attempts": exc.attempt_errors,
        })

    # 3. Validate
    val_result = validate_ir(ir)
    rule_result = HardwareRuleEngine().run(ir)

    # 4. Generate all outputs
    spice_gen = SpiceNetlistGenerator()
    netlist = spice_gen.generate(ir)

    firmware: Optional[str] = None
    try:
        firmware = ArduinoFirmwareGenerator().generate(ir)
    except Exception:
        pass

    schematic = KiCadSchematicGenerator().generate(ir)
    bom = BOMCompiler().compile(ir)

    # 5. Explanation (best-effort)
    explanation = ""
    try:
        explanation = ExplanationEngine().explain(ir, val_result)
    except Exception:
        pass

    # 6. Persist
    await save_design(db, ir, str(user.id))
    if firmware:
        await save_output(db, ir.circuit_id, "firmware", firmware, f"{ir.circuit_id}.ino")
    await save_output(db, ir.circuit_id, "schematic", schematic, f"{ir.circuit_id}.kicad_sch")
    await save_output(db, ir.circuit_id, "netlist", netlist, f"{ir.circuit_id}.cir")

    # 7. Kick off simulation (async via Celery)
    job_id: Optional[str] = None
    if ir.simulation_spec:
        job_id = str(uuid.uuid4())
        run_simulation.apply_async(
            args=[ir.circuit_id, netlist, job_id, str(ir.application_class)],
            task_id=job_id,
        )

    # 8. Build validation summary
    all_errors = val_result.errors + rule_result.errors
    all_warnings = val_result.warnings + rule_result.warnings
    validation_summary = {
        "passed": len(all_errors) == 0,
        "errors": [{"field": e.field_path, "message": e.message} for e in all_errors],
        "warnings": [{"field": w.field_path, "message": w.message} for w in all_warnings],
    }

    return GenerateResponse(
        circuit_id=ir.circuit_id,
        intent=ir.intent,
        application_class=str(ir.application_class),
        target_mcu=ir.target_mcu,
        version=ir.version,
        simulation_job_id=job_id,
        validation=validation_summary,
        firmware=firmware,
        schematic=schematic,
        bom=bom,
        explanation=explanation,
        ir=ir.model_dump(mode="json"),
    )


@router.get("/list")
async def list_designs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    designs = await list_user_designs(db, str(user.id))
    return [
        {
            "circuit_id": d.circuit_id,
            "intent": d.intent,
            "application_class": d.application_class,
            "version": d.version,
            "simulation_passed": d.simulation_passed,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in designs
    ]
