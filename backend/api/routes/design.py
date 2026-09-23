"""POST /design/generate — full pipeline: intent → IR → all outputs."""

import uuid
from typing import Annotated, Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.rate_limit import limiter

from ai.client import timeout_detail
from ai.explainer import ExplanationEngine
from ai.intent_producer import IntentProducer, IntentProductionError
from api.routes.auth import get_current_user
from core.ir_schema import CircuitIR
from core.ir_validator import validate_ir
from db.crud import list_user_designs, save_design, save_output
from db.models import get_db
from generators.bom.compiler import BOMCompiler
from generators.firmware.arduino import ArduinoFirmwareGenerator
from generators.netlist.spice import SpiceNetlistGenerator
from generators.realize import realize
from generators.registry import default_registry
from generators.schematic.kicad import KiCadSchematicGenerator
from observability.request_log import log_ctx, prompt_hash
from tasks.simulation_task import run_simulation
from validation.rule_engine import HardwareRuleEngine

router = APIRouter()


from generators.netlist.pcb import PcbNetlistGenerator

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
    pcb_netlist: Optional[dict] = None
    ir: dict
    #: Stage 3 claim objects: kind/grade/scope/defeaters per claim, the grade
    #: floor, open defeaters, and the not-assessed / out-of-scope rows.
    validation_coverage: Optional[dict] = None


@router.post("/generate", response_model=GenerateResponse, status_code=201)
@limiter.limit("10/hour")
async def generate_design(
    request: Request,
    body: GenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    # 0. Instrumentation — §4.5. Set before anything that can fail, so a row
    #    survives even when the request does not.
    ctx = log_ctx(request)
    ctx.prompt_hash = prompt_hash(body.prompt)
    ctx.user_id = str(user.id)

    # 1. Transcribe the request into IntentIR.
    #
    # The model writes a *requirement*, never a design. `IntentProducer.produce`
    # is synchronous — it blocks on a network call — and calling it directly in
    # an async def would block the whole uvicorn event loop, so one slow
    # transcription stalls every other request including /health. It runs in a
    # threadpool for that reason; the SDK timeout in ai/client.py bounds how
    # long a thread can be held.
    registry = default_registry()
    try:
        ctx.count_api_call()
        intent = await run_in_threadpool(IntentProducer(registry).produce, body.prompt)
    except anthropic.APITimeoutError as exc:
        raise HTTPException(504, detail=timeout_detail("Intent transcription", exc))
    except anthropic.APIError as exc:
        raise HTTPException(503, detail=f"AI service unavailable: {exc}")
    except IntentProductionError as exc:
        # X5 Departure 1 attaches the raw tool input to this exception so that
        # a broken assumption announces itself. An exception announces it only
        # to whoever is holding it — this is where it becomes a record. Without
        # this line the evidence dies with the handler and "schema failure is
        # structurally impossible" stays permanently unmeasured.
        ctx.error = exc.as_log_entry()
        raise HTTPException(422, detail={
            "error": "intent_production_failed",
            "kind": exc.kind,
            "message": str(exc),
        })

    ctx.intent_ir = intent.model_dump(mode="json")

    # 2. An unanswered question is put back to the user, never guessed at.
    #    Stage 1 gate: underdetermined non-empty → ask, never generate.
    if not intent.is_answerable:
        ctx.underdetermined = intent.open_questions()
        raise HTTPException(422, detail={
            "error": "underdetermined",
            "questions": intent.open_questions(),
            "message": "The request does not pin these down. Supply them and resubmit.",
        })

    # 3. Dispatch to a generator whose declared envelope accepts this intent.
    #    A refusal is a product outcome, not an error: §4.5 makes the
    #    out-of-envelope log the generator backlog, ranked by frequency.
    dispatch = registry.dispatch(intent)
    if not dispatch.accepted:
        ctx.refuse(dispatch.refusal_summary())
        raise HTTPException(422, detail={
            "error": "out_of_envelope",
            "refusals": [
                {"generator": r.generator, "reason": r.reason} for r in dispatch.refusals
            ],
            "catalogue": list(registry.functions()),
        })

    generator = dispatch.generator
    ctx.generator = f"{generator.name}@{generator.version}"

    # 4. The design itself is produced deterministically, with no model in the
    #    loop. This is the invariant tests/test_llm_cannot_write_circuit_ir.py
    #    asserts mechanically. realize() stamps the circuit_id derived from the
    #    intent, so the same intent always yields a byte-identical design.
    # Off the event loop: realize() runs the Stage 4 proofs (sympy, z3).
    ir = await run_in_threadpool(realize, generator, intent)

    # 5. Validate
    val_result = validate_ir(ir)
    rule_result = HardwareRuleEngine().run(ir)

    # 6. Generate all outputs
    spice_gen = SpiceNetlistGenerator()
    netlist = spice_gen.generate(ir)

    firmware: Optional[str] = None
    try:
        firmware = ArduinoFirmwareGenerator().generate(ir)
    except Exception:
        pass

    schematic = KiCadSchematicGenerator().generate(ir)
    bom = BOMCompiler().compile(ir)
    pcb_netlist = PcbNetlistGenerator().generate(ir)

    # 7. Explanation (best-effort — a failure here must not lose the design)
    explanation = ""
    try:
        ctx.count_api_call()
        explanation = await run_in_threadpool(ExplanationEngine().explain, ir, val_result)
    except Exception:
        pass

    # 8. Persist — the requirement with the design, so it can be patched (X2).
    await save_design(db, ir, str(user.id), intent_ir=intent.model_dump(mode="json"))
    if firmware:
        await save_output(db, ir.circuit_id, "firmware", firmware, f"{ir.circuit_id}.ino")
    await save_output(db, ir.circuit_id, "schematic", schematic, f"{ir.circuit_id}.kicad_sch")
    await save_output(db, ir.circuit_id, "netlist", netlist, f"{ir.circuit_id}.cir")

    # 9. Kick off simulation (async via Celery)
    job_id: Optional[str] = None
    if ir.simulation_spec:
        job_id = str(uuid.uuid4())
        run_simulation.apply_async(
            args=[ir.circuit_id, netlist, job_id, str(ir.application_class)],
            task_id=job_id,
        )

    # 10. Build validation summary
    all_errors = val_result.errors + rule_result.errors
    all_warnings = val_result.warnings + rule_result.warnings
    validation_summary = {
        "passed": len(all_errors) == 0,
        "errors": [{"field": e.field_path, "message": e.message} for e in all_errors],
        "warnings": [{"field": w.field_path, "message": w.message} for w in all_warnings],
    }

    ctx.complete(circuit_id=ir.circuit_id)

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
        pcb_netlist=pcb_netlist,
        ir=ir.model_dump(mode="json"),
        validation_coverage=ir.validation_coverage,
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
