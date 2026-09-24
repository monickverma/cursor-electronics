"""
Patching a design by patching its requirement. PHASE_2_PLAN_v2.md §4.1, Stage 2.

    POST /design/{circuit_id}/patch        — command (1 model call) or ops (0)
    PUT  /design/{circuit_id}/annotations  — the annotation layer
    GET  /design/{circuit_id}/history      — the patch chain, as requirements
    POST /design/{circuit_id}/sign-off     — Stage 4: agree to the proved properties

The edit goes through the same gate as a fresh request: the patched IntentIR
must pass `envelope()`, and the design is re-realised from it. Nothing is
written until that has succeeded, so a refused patch leaves v(n) exactly as it
was. The decisions behind every step are in `brain/decisions.md` [2026-09-21]
X2 + X4.
"""

import json
import uuid
from typing import Annotated, Any, Dict, List, Optional, Sequence

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.rate_limit import limiter

from ai.client import timeout_detail
from ai.intent_patcher import IntentPatcher, IntentPatchError
from api.routes.auth import get_current_user
from api.routes.firmware import firmware_view
from core.annotations import Annotation, attach, validate_annotations
from core.intent_ir import IntentIR
from core.intent_patch import PatchError, PatchOp, apply_patch
from core.ir_schema import CircuitIR
from core.ir_validator import validate_ir
from db.crud import (
    get_design,
    list_patches,
    record_patch,
    save_output,
    update_design_annotations,
    update_design_revision,
)
from db.models import get_db
from generators.netlist.pcb import PcbNetlistGenerator
from generators.netlist.spice import SpiceNetlistGenerator
from generators.realize import check_locality, generator_tag, predict_delta, realize, same_design
from generators.registry import default_registry
from generators.schematic.kicad import KiCadSchematicGenerator
from observability.request_log import log_ctx, prompt_hash
from tasks.simulation_task import run_simulation
from validation.rule_engine import HardwareRuleEngine

router = APIRouter()

#: Written into every new patch_history row, so a reader can tell these from
#: the Phase 1 rows that recorded CircuitIR component edits. Those are frozen,
#: not migrated — decisions.md [2026-09-21] X2 + X4, item 13.
PATCH_SCHEMA = "intent_patch/1"


class PatchRequest(BaseModel):
    """Exactly one of `command` (a sentence, one model call) or `ops` (RFC 6902, none)."""

    command: Optional[str] = None
    ops: Optional[List[PatchOp]] = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "PatchRequest":
        has_command = bool((self.command or "").strip())
        if has_command == (self.ops is not None):
            raise ValueError("send either `command` or `ops`, not both and not neither")
        return self


class PatchResponse(BaseModel):
    circuit_id: str
    version: int
    #: The requirement diff, one line per changed path. Kept under the Phase 1
    #: name so existing clients keep working; it now reads as requirements.
    changes: List[str]
    note_to_user: str
    validation: dict
    simulation_job_id: Optional[str]
    #: The firmware source — present only once it has compiled (Stage 5).
    firmware: Optional[str]
    #: Its build: status, board, hash, message; the log if it failed.
    firmware_build: Optional[dict] = None
    schematic: str
    pcb_netlist: Optional[dict] = None
    ir: dict
    intent_ir: dict
    operations: List[dict] = []
    citations: List[str] = []
    predict_delta: List[str] = []
    locality: Optional[dict] = None
    annotations: dict = {}
    generator: Optional[str] = None
    generator_changed: Optional[dict] = None
    #: Stage 3 claim objects for the returned revision. None for a design
    #: built before Stage 3 that a no-op patch returns unchanged.
    validation_coverage: Optional[dict] = None


class AnnotationsRequest(BaseModel):
    annotations: List[Dict[str, Any]]


class SignOffRequest(BaseModel):
    """The hash of the property set the user was shown — never computed for them."""

    properties_hash: str


# ── Shared plumbing ──────────────────────────────────────────────────────────

async def _load_owned(db: AsyncSession, circuit_id: str, user) -> Any:
    design = await get_design(db, circuit_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    if str(design.user_id) != str(user.id):
        raise HTTPException(403, detail="Access denied")
    return design


def _validation_summary(ir: CircuitIR) -> dict:
    val_result = validate_ir(ir)
    rule_result = HardwareRuleEngine().run(ir)
    errors = val_result.errors + rule_result.errors
    warnings = val_result.warnings + rule_result.warnings
    return {
        "passed": not errors,
        "errors": [{"field": e.field_path, "message": e.message} for e in errors],
        "warnings": [{"field": w.field_path, "message": w.message} for w in warnings],
    }


async def _outputs(db: AsyncSession, ir: CircuitIR, annotations: Sequence[Annotation] = ()) -> Dict[str, Any]:
    # Firmware goes through the compile gate: source only once it has built
    # for the design's board (Stage 5 gate 1).
    fw = await firmware_view(db, ir)
    return {
        "netlist": SpiceNetlistGenerator().generate(ir),
        "firmware": fw.firmware,
        "firmware_build": fw.model_dump(exclude={"firmware", "platformio_ini"}),
        # Annotations are merged into the drawing only — never into the design.
        "schematic": KiCadSchematicGenerator().generate(ir, annotations),
        "pcb_netlist": PcbNetlistGenerator().generate(ir),
    }


def _annotation_view(report) -> dict:
    return {
        "attached": [a.model_dump(mode="json") for a in report.attached],
        "orphaned": [a.model_dump(mode="json") for a in report.orphaned],
    }


# ── POST /{circuit_id}/patch ─────────────────────────────────────────────────

@router.post("/{circuit_id}/patch", response_model=PatchResponse)
@limiter.limit("20/hour")
async def patch_design(
    request: Request,
    circuit_id: str,
    body: PatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    ctx = log_ctx(request)
    ctx.user_id = str(user.id)
    ctx.prompt_hash = prompt_hash(
        body.command if body.command else json.dumps([o.model_dump() for o in body.ops], sort_keys=True)
    )

    # 1. The design, and the requirement it was realised from.
    design = await _load_owned(db, circuit_id, user)
    if design.intent_ir is None:
        # Built before Stage 2. There is no recorded requirement, and
        # reconstructing one from a circuit would be guessing.
        raise HTTPException(409, detail={
            "error": "no_requirement_on_record",
            "message": "This design predates requirement patching and has no stored "
                       "requirement to edit. Generate it again to make it patchable.",
        })

    intent = IntentIR.model_validate(design.intent_ir)
    current = CircuitIR.model_validate(design.ir_json)
    annotations = validate_annotations(design.annotations or [])
    registry = default_registry()

    # 2. Operations: sent directly (zero model calls) or transcribed from a
    #    sentence (one). The transcription runs in a threadpool — it blocks on
    #    the network — for the same reason as in design.py.
    citations: List[str] = []
    note = ""
    if body.ops is not None:
        ops = list(body.ops)
    else:
        parts = [{"id": c.id, "type": c.type, "value": c.value} for c in current.components]
        try:
            ctx.count_api_call()
            proposal = await run_in_threadpool(
                IntentPatcher(registry.functions()).propose, intent, body.command, parts
            )
        except anthropic.APITimeoutError as exc:
            raise HTTPException(504, detail=timeout_detail("Patch transcription", exc))
        except anthropic.APIError as exc:
            raise HTTPException(503, detail=f"AI service unavailable: {exc}")
        except IntentPatchError as exc:
            ctx.error = exc.as_log_entry()
            raise HTTPException(422, detail={
                "error": "patch_transcription_failed",
                "kind": exc.kind,
                "message": str(exc),
                "kept_version": intent.revision,
            })
        ops, citations, note = list(proposal.ops), list(proposal.citations), proposal.note_to_user

    # 3. Apply to the requirement. Atomic: all operations or none.
    try:
        outcome = apply_patch(intent, ops)
    except PatchError as exc:
        raise HTTPException(422, detail={
            "error": "invalid_patch",
            "message": str(exc),
            "kept_version": intent.revision,
        })

    # 4. A patch that changes nothing is not a version (idempotence).
    if not outcome.changed:
        outputs = await _outputs(db, current, annotations)
        ctx.complete()
        return PatchResponse(
            circuit_id=circuit_id,
            version=current.version,
            changes=[],
            note_to_user=note or f"No change to the requirement; the design is still v{current.version}.",
            validation=_validation_summary(current),
            simulation_job_id=None,
            firmware=outputs["firmware"],
            firmware_build=outputs["firmware_build"],
            schematic=outputs["schematic"],
            pcb_netlist=outputs["pcb_netlist"],
            ir=current.model_dump(mode="json"),
            intent_ir=intent.model_dump(mode="json"),
            operations=[o.model_dump() for o in ops],
            citations=citations,
            annotations=_annotation_view(attach(current, annotations)),
            generator=current.generator,
            validation_coverage=current.validation_coverage,
        )

    new_intent = outcome.intent

    # 5. The same gate as a fresh request. A refusal keeps v(n) untouched.
    dispatch = registry.dispatch(new_intent)
    if not dispatch.accepted:
        ctx.refuse(dispatch.refusal_summary())
        raise HTTPException(422, detail={
            "error": "out_of_envelope",
            "refusals": [{"generator": r.generator, "reason": r.reason} for r in dispatch.refusals],
            "requested_changes": list(outcome.readable),
            "kept_version": intent.revision,
        })

    generator = dispatch.generator
    # Off the event loop: realize() runs the Stage 4 proofs (sympy, z3).
    new_ir = await run_in_threadpool(realize, generator, new_intent)
    tag = generator_tag(generator)

    # 6. Justification and checks, all derived rather than written.
    before_generator = registry.by_name(current.generator.split("@")[0]) if current.generator else None
    delta = predict_delta(before_generator, intent, generator, new_intent)
    locality = check_locality(generator, outcome.changed_paths, current, new_ir)
    report = attach(new_ir, annotations)
    generator_changed = (
        {"from": current.generator, "to": tag} if current.generator and current.generator != tag else None
    )
    validation = _validation_summary(new_ir)
    outputs = await _outputs(db, new_ir, annotations)

    job_id: Optional[str] = None
    if new_ir.simulation_spec:
        job_id = str(uuid.uuid4())

    # 7. Persist the revision, then its history row. The write is conditional
    #    on the design still being the version this patch was computed from;
    #    if another patch landed in between, this one is refused rather than
    #    written over it, and nothing below runs.
    written = await update_design_revision(
        db, circuit_id, new_ir,
        intent_ir=new_intent.model_dump(mode="json"),
        expected_version=design.version,
    )
    if not written:
        ctx.error = f"version_conflict: expected v{design.version}"
        raise HTTPException(409, detail={
            "error": "version_conflict",
            "message": f"The design changed while this patch was being applied — it is "
                       f"no longer v{design.version}. Reload it and send the change again.",
            "expected_version": design.version,
        })
    await record_patch(
        db,
        circuit_id=circuit_id,
        from_version=current.version,
        to_version=new_ir.version,
        patch_json={
            "schema": PATCH_SCHEMA,
            "from_revision": intent.revision,
            "to_revision": new_intent.revision,
            "operations": [o.model_dump() for o in ops],
            "citations": citations,
            "command": body.command,
            "readable": list(outcome.readable),
            "changed_paths": list(outcome.changed_paths),
            "from_requirements": intent.requirements,
            "intent_ir": new_intent.model_dump(mode="json"),
            "predict_delta": [d.describe() for d in delta],
            "locality": locality.model_dump(),
            "generator": tag,
            "generator_changed": generator_changed,
            "orphaned_annotations": [a.id for a in report.orphaned],
            # Results for v(n) must not be read as results for v(n+1).
            "simulation_job_id": job_id,
        },
        prompted_by=body.command or "operations",
        change_summary="; ".join(outcome.readable),
    )
    if outputs["firmware"]:
        await save_output(db, circuit_id, "firmware", outputs["firmware"], f"{circuit_id}_v{new_ir.version}.ino")
    await save_output(db, circuit_id, "schematic", outputs["schematic"], f"{circuit_id}_v{new_ir.version}.kicad_sch")
    await save_output(db, circuit_id, "netlist", outputs["netlist"], f"{circuit_id}_v{new_ir.version}.cir")

    if job_id:
        run_simulation.apply_async(
            args=[circuit_id, outputs["netlist"], job_id, str(new_ir.application_class)],
            task_id=job_id,
        )

    ctx.intent_ir = new_intent.model_dump(mode="json")
    ctx.generator = tag
    ctx.patched(circuit_id)

    return PatchResponse(
        circuit_id=circuit_id,
        version=new_ir.version,
        changes=list(outcome.readable),
        note_to_user=note,
        validation=validation,
        simulation_job_id=job_id,
        firmware=outputs["firmware"],
        firmware_build=outputs["firmware_build"],
        schematic=outputs["schematic"],
        pcb_netlist=outputs["pcb_netlist"],
        ir=new_ir.model_dump(mode="json"),
        intent_ir=new_intent.model_dump(mode="json"),
        operations=[o.model_dump() for o in ops],
        citations=citations,
        predict_delta=[d.describe() for d in delta],
        locality=locality.model_dump() | {"ok": locality.ok},
        annotations=_annotation_view(report),
        generator=tag,
        generator_changed=generator_changed,
        validation_coverage=new_ir.validation_coverage,
    )


# ── PUT /{circuit_id}/annotations ────────────────────────────────────────────

@router.put("/{circuit_id}/annotations")
@limiter.limit("60/hour")
async def put_annotations(
    request: Request,
    circuit_id: str,
    body: AnnotationsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    """
    Replace the design's annotations. Never regenerates the design: the
    circuit, its version and its claims are untouched. Only the schematic
    drawing is re-rendered, because that is where annotations appear.
    """
    design = await _load_owned(db, circuit_id, user)
    try:
        annotations = validate_annotations(body.annotations)
    except Exception as exc:  # noqa: BLE001 — a bad annotation is the caller's error
        raise HTTPException(422, detail={"error": "invalid_annotations", "message": str(exc)})
    ir = CircuitIR.model_validate(design.ir_json)
    report = attach(ir, annotations)
    await update_design_annotations(db, circuit_id, [a.model_dump(mode="json") for a in report.all])
    schematic = KiCadSchematicGenerator().generate(ir, report.all)
    await save_output(db, circuit_id, "schematic", schematic, f"{circuit_id}_v{design.version}.kicad_sch")
    return {"circuit_id": circuit_id, "version": design.version, "schematic": schematic,
            **_annotation_view(report)}


# ── GET /{circuit_id}/history ────────────────────────────────────────────────

@router.get("/{circuit_id}/history")
async def get_history(
    circuit_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    """The patch chain. Requirement patches read as requirements; Phase 1 rows are shown as they were."""
    design = await _load_owned(db, circuit_id, user)
    entries = []
    for row in await list_patches(db, circuit_id):
        data = row.patch_json or {}
        is_intent_patch = data.get("schema") == PATCH_SCHEMA
        entries.append({
            "from_version": row.from_version,
            "to_version": row.to_version,
            "kind": "requirement_patch" if is_intent_patch else "legacy_circuit_patch",
            "changes": data.get("readable") if is_intent_patch else data.get("changes", []),
            "predict_delta": data.get("predict_delta", []) if is_intent_patch else [],
            "prompted_by": row.prompted_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return {
        "circuit_id": circuit_id,
        "current_version": design.version,
        "patchable": design.intent_ir is not None,
        "entries": entries,
    }


# ── POST /{circuit_id}/sign-off ──────────────────────────────────────────────

@router.post("/{circuit_id}/sign-off")
@limiter.limit("30/hour")
async def sign_off_design(
    request: Request,
    circuit_id: str,
    body: SignOffRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    """
    Agree to a design's back-translated properties. Stage 4; `brain/decisions.md`
    [2026-09-23] item 5.

    The client sends the hash of the sentences it displayed. It must equal the
    stored design's, or the answer is 409 and nothing is signed — nobody signs
    a statement they did not read. Sign-off never re-derives the design: the
    signed requirement is realised again only to confirm it yields the same
    circuit under the installed generator, and if it does not, the user is
    told to patch first. The revision does not change.
    """
    design = await _load_owned(db, circuit_id, user)
    if design.intent_ir is None:
        raise HTTPException(409, detail={
            "error": "no_requirement_on_record",
            "message": "This design predates requirement patching; there is no stored "
                       "requirement to sign. Generate it again.",
        })
    intent = IntentIR.model_validate(design.intent_ir)
    current = CircuitIR.model_validate(design.ir_json)
    shown = (current.validation_coverage or {}).get("properties_hash")
    if not shown:
        raise HTTPException(409, detail={
            "error": "no_properties",
            "message": "This design carries no proved properties to sign — it was built "
                       "before Stage 4, or by a generator that declares none.",
        })
    if body.properties_hash != shown:
        raise HTTPException(409, detail={
            "error": "properties_changed",
            "message": "The properties you were shown are not this design's current ones. "
                       "Reload the design and read them again before signing.",
            "current_hash": shown,
        })

    name = (current.generator or "").split("@")[0]
    generator = default_registry().by_name(name) if name else None
    if generator is None or generator_tag(generator) != current.generator:
        raise HTTPException(409, detail={
            "error": "generator_changed",
            "message": f"This design was built by {current.generator}; the installed generator is "
                       f"{generator_tag(generator) if generator else 'missing'}. Its properties "
                       f"cannot be re-established as shown — patch the design first.",
        })

    if intent.signed_off is not None and intent.signed_off.properties_hash == shown and intent.is_intact():
        return {
            "circuit_id": circuit_id, "version": current.version, "signed_by": intent.signed_off.by,
            "properties_hash": shown, "validation_coverage": current.validation_coverage,
            "intent_ir": intent.model_dump(mode="json"),
        }

    try:
        signed = intent.sign_off(by=user.email, properties_hash=shown)
    except ValueError as exc:
        raise HTTPException(422, detail={"error": "not_signable", "message": str(exc)})

    # Deterministic: the same circuit, now with the proofs counted.
    new_ir = await run_in_threadpool(realize, generator, signed)
    coverage = new_ir.validation_coverage or {}
    if not same_design(new_ir, current) or not coverage.get("properties_signed"):
        raise HTTPException(409, detail={
            "error": "design_changed",
            "message": "Realising the signed requirement did not reproduce this design and its "
                       "properties. Nothing was signed; patch the design first.",
        })

    written = await update_design_revision(
        db, circuit_id, new_ir,
        intent_ir=signed.model_dump(mode="json"),
        expected_version=design.version,
    )
    if not written:
        raise HTTPException(409, detail={
            "error": "version_conflict",
            "message": f"The design changed while it was being signed — it is no longer "
                       f"v{design.version}. Reload it and read its properties again.",
            "expected_version": design.version,
        })
    return {
        "circuit_id": circuit_id,
        "version": new_ir.version,
        "signed_by": signed.signed_off.by,
        "properties_hash": shown,
        "validation_coverage": coverage,
        "intent_ir": signed.model_dump(mode="json"),
    }
