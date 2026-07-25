"""POST /design/{circuit_id}/patch — apply a natural language patch to an existing design."""

import uuid
from typing import Annotated, Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.rate_limit import limiter

from ai.patcher import CircuitPatcher
from api.routes.auth import get_current_user
from core.ir_schema import CircuitIR
from core.ir_validator import validate_ir
from db.crud import get_design, record_patch, save_output, update_design_ir
from db.models import get_db
from generators.firmware.arduino import ArduinoFirmwareGenerator
from generators.netlist.spice import SpiceNetlistGenerator
from generators.schematic.kicad import KiCadSchematicGenerator
from tasks.simulation_task import run_simulation
from validation.rule_engine import HardwareRuleEngine

router = APIRouter()


class PatchRequest(BaseModel):
    command: str  # "Change R1 to 4.7k", "Use DHT11 instead of DHT22", etc.


class PatchResponse(BaseModel):
    circuit_id: str
    version: int
    changes: list
    note_to_user: str
    validation: dict
    simulation_job_id: Optional[str]
    firmware: Optional[str]
    schematic: str
    ir: dict


@router.post("/{circuit_id}/patch", response_model=PatchResponse)
@limiter.limit("20/hour")
async def patch_design(
    request: Request,
    circuit_id: str,
    body: PatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    # 1. Load existing design
    design = await get_design(db, circuit_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    if str(design.user_id) != str(user.id):
        raise HTTPException(403, detail="Access denied")

    ir = CircuitIR.model_validate(design.ir_json)
    old_version = ir.version

    # 2. Generate patch (never returns full IR — only changed fields)
    try:
        patch_result = CircuitPatcher().patch(ir, body.command)
    except anthropic.APIError as exc:
        raise HTTPException(503, detail=f"AI service unavailable: {exc}")

    # 3. Apply patch — immutable, increments version
    new_ir = patch_result.apply_to(ir)

    # 4. Validate patched IR
    val_result = validate_ir(new_ir)
    rule_result = HardwareRuleEngine().run(new_ir)
    all_errors = val_result.errors + rule_result.errors
    all_warnings = val_result.warnings + rule_result.warnings
    validation_summary = {
        "passed": len(all_errors) == 0,
        "errors": [{"field": e.field_path, "message": e.message} for e in all_errors],
        "warnings": [{"field": w.field_path, "message": w.message} for w in all_warnings],
    }

    # 5. Regenerate outputs
    netlist = SpiceNetlistGenerator().generate(new_ir)
    firmware: Optional[str] = None
    try:
        firmware = ArduinoFirmwareGenerator().generate(new_ir)
    except Exception:
        pass
    schematic = KiCadSchematicGenerator().generate(new_ir)

    # 6. Persist updated IR and patch record
    await update_design_ir(db, circuit_id, new_ir)
    await record_patch(
        db,
        circuit_id=circuit_id,
        from_version=old_version,
        to_version=new_ir.version,
        patch_json={"changes": patch_result.changes, "command": body.command},
        prompted_by=body.command,
    )
    if firmware:
        await save_output(db, circuit_id, "firmware", firmware, f"{circuit_id}_v{new_ir.version}.ino")
    await save_output(db, circuit_id, "schematic", schematic, f"{circuit_id}_v{new_ir.version}.kicad_sch")
    await save_output(db, circuit_id, "netlist", netlist, f"{circuit_id}_v{new_ir.version}.cir")

    # 7. Re-run simulation if needed
    job_id: Optional[str] = None
    if new_ir.simulation_spec and patch_result.changes:
        job_id = str(uuid.uuid4())
        run_simulation.apply_async(args=[circuit_id, netlist, job_id, str(new_ir.application_class)], task_id=job_id)

    return PatchResponse(
        circuit_id=circuit_id,
        version=new_ir.version,
        changes=patch_result.changes,
        note_to_user=patch_result.note_to_user,
        validation=validation_summary,
        simulation_job_id=job_id,
        firmware=firmware,
        schematic=schematic,
        ir=new_ir.model_dump(mode="json"),
    )
