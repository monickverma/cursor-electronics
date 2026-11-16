"""The library: reopening a saved design, and filing it under a project.

This module calls no model and imports none. It reads a stored CircuitIR and
hands it to the same deterministic compilers that made the design's outputs the
first time. It lives apart from api/routes/design.py for exactly that reason:
that module calls the model that writes requirements, and
tests/test_llm_cannot_write_circuit_ir.py does not allow one module to both call
a model and construct a CircuitIR.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.auth import get_current_user
from api.routes.firmware import firmware_view
from api.routes.projects import load_owned_project
from core.ir_schema import CircuitIR
from core.ir_validator import validate_ir
from db.crud import get_design, latest_simulation_job, set_design_project
from db.models import get_db
from generators.bom.compiler import BOMCompiler
from generators.netlist.pcb import PcbNetlistGenerator
from generators.schematic.kicad import KiCadSchematicGenerator
from middleware.rate_limit import limiter
from validation.rule_engine import HardwareRuleEngine

router = APIRouter()


class DesignView(BaseModel):
    """A stored design, opened again. The generate response's fields, plus where it is filed."""
    circuit_id: str
    intent: str
    application_class: str
    target_mcu: Optional[str]
    version: int
    simulation_job_id: Optional[str]
    validation: dict
    firmware: Optional[str]
    firmware_build: Optional[dict] = None
    schematic: str
    bom: list
    explanation: str
    explanation_error: Optional[str] = None
    explanation_status: str = "written"
    pcb_netlist: Optional[dict] = None
    ir: dict
    validation_coverage: Optional[dict] = None
    project_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    #: False for a design saved before requirements were stored: it can be read, not patched.
    patchable: bool = True


class FileUnder(BaseModel):
    project_id: Optional[str] = None


async def _load_owned(db: AsyncSession, circuit_id: str, user):
    design = await get_design(db, circuit_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    if str(design.user_id) != str(user.id):
        raise HTTPException(403, detail="Access denied")
    return design


@router.get("/{circuit_id}", response_model=DesignView)
@limiter.limit("300/hour")
async def open_design(
    request: Request,
    circuit_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    """A saved design with every output, re-derived from the stored CircuitIR.

    Nothing is regenerated from the prompt: the schematic, the BOM, the board
    netlist and the validation are compiled again from the IR that was stored,
    by the same compilers that made them the first time. The firmware goes
    through the same compile gate.

    The explanation is not read here. It has its own route
    (GET /design/{id}/explanation), in a module that can reach the model that
    writes explanations; importing it would make this module one that talks to
    a model. So this answers `explanation_status: "writing"`, which is what
    sends the client to that route — where a stored explanation comes straight
    back.
    """
    design = await _load_owned(db, circuit_id, user)
    ir = CircuitIR.model_validate(design.ir_json)

    val_result = validate_ir(ir)
    rule_result = HardwareRuleEngine().run(ir)
    errors = val_result.errors + rule_result.errors
    warnings = val_result.warnings + rule_result.warnings

    fw = await firmware_view(db, ir)
    created = getattr(design, "created_at", None)
    updated = getattr(design, "updated_at", None)

    return DesignView(
        circuit_id=ir.circuit_id,
        intent=ir.intent,
        application_class=str(ir.application_class),
        target_mcu=ir.target_mcu,
        version=ir.version,
        simulation_job_id=await latest_simulation_job(db, circuit_id),
        validation={
            "passed": len(errors) == 0,
            "errors": [{"field": e.field_path, "message": e.message} for e in errors],
            "warnings": [{"field": w.field_path, "message": w.message} for w in warnings],
        },
        firmware=fw.firmware,
        firmware_build=fw.model_dump(exclude={"firmware", "platformio_ini"}),
        schematic=KiCadSchematicGenerator().generate(ir),
        bom=BOMCompiler().compile(ir),
        explanation="",
        explanation_error=None,
        explanation_status="writing",
        pcb_netlist=PcbNetlistGenerator().generate(ir),
        ir=ir.model_dump(mode="json"),
        validation_coverage=ir.validation_coverage,
        project_id=str(design.project_id) if getattr(design, "project_id", None) else None,
        created_at=created.isoformat() if created else None,
        updated_at=updated.isoformat() if updated else None,
        patchable=getattr(design, "intent_ir", None) is not None,
    )


@router.put("/{circuit_id}/project")
@limiter.limit("300/hour")
async def file_design(
    request: Request,
    circuit_id: str,
    body: FileUnder,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    """File a design under one of the user's projects, or (null) under none."""
    await _load_owned(db, circuit_id, user)
    if body.project_id is not None:
        await load_owned_project(db, body.project_id, user)
    await set_design_project(db, circuit_id, body.project_id)
    return {"circuit_id": circuit_id, "project_id": body.project_id}
