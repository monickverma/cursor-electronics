"""
Record the frontend's demo-mode examples by running the real pipeline.

    python scripts/build_demo_fixtures.py

Writes frontend/lib/demo/examples.json (and prompts.json, its prompts). Each example is what the backend
returns for one requirement: the deterministic generator's IR, the KiCad
schematic, the BOM view, the ngspice run and its grade, and the firmware once
PlatformIO has compiled it. Nothing in the file is written by hand.

Two things differ from a live `POST /design/generate`, and the file says so:

* The requirement is entered through the form producer (zero model calls),
  not transcribed from free text by the LLM. The prompt stored beside it is the
  sentence a user would type for that requirement.
* The explanation is the deterministic `DerivedExplainer`, not the LLM
  explainer — it is assembled from the generator's own justifications and
  `predict()`.

No database, no Celery, no Redis: the same functions the routes and workers
call are called here directly. Needs ngspice on PATH (or the MSYS2 path the
runner knows) and PlatformIO with the board toolchains for firmware.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# Settings are read at import. Nothing here talks to a model, a database, Redis
# or Mouser, so placeholders (the same ones tests/conftest.py uses) are enough.
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost/unused")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "demo-fixtures-placeholder-not-a-secret-000")
os.environ["MOUSER_API_KEY"] = ""

from ai.derived_explainer import DerivedExplainer  # noqa: E402
from ai.form_producer import FormProducer  # noqa: E402
from api.routes.bom import bom_view  # noqa: E402
from core.intent_ir import IntentIR, Producer, Provenance  # noqa: E402
from core.ir_validator import validate_ir  # noqa: E402
from generators.bom.compiler import BOMCompiler  # noqa: E402
from generators.compose import compose_intent  # noqa: E402
from generators.firmware.compile_gate import compile_project  # noqa: E402
from generators.firmware.project import project_for  # noqa: E402
from generators.netlist.pcb import PcbNetlistGenerator  # noqa: E402
from generators.netlist.spice import SpiceNetlistGenerator  # noqa: E402
from generators.realize import realize  # noqa: E402
from generators.registry import default_registry  # noqa: E402
from generators.schematic.kicad import KiCadSchematicGenerator  # noqa: E402
from simulation.grader import SimulationGrader  # noqa: E402
from simulation.parser import SpiceResultParser  # noqa: E402
from simulation.runner import NgspiceRunner  # noqa: E402
from simulation.waveforms import waveforms_from  # noqa: E402
from validation.rule_engine import HardwareRuleEngine  # noqa: E402

OUT = ROOT / "frontend" / "lib" / "demo" / "examples.json"
#: The prompts alone, so the chat can offer them without loading every recording.
PROMPTS = OUT.with_name("prompts.json")
FW_ROOT = Path(os.environ.get("DEMO_FW_ROOT", ROOT / ".demo-build" / "firmware"))


def single(function: str, targets: dict, constraints: dict) -> IntentIR:
    return IntentIR(
        requirements={"function": function, "targets": targets, "constraints": constraints, "preferences": {}},
        provenance=Provenance(producer=Producer.FORM),
    )


ROOM = json.loads((ROOT / "docs" / "projects" / "room_monitor.json").read_text(encoding="utf-8"))

# The requirements are the repo's own bench templates (docs/bench_templates) and
# project (docs/projects/room_monitor.json).
EXAMPLES = [
    ("rc-lowpass", "RC low-pass filter with a 1 kHz cutoff on a 5 V supply",
     lambda: single("low_pass_filter", {"cutoff_hz": 1000}, {"supply_v": 5})),
    ("voltage-divider", "Voltage divider stepping 5 V down to 3.3 V",
     lambda: single("voltage_divider", {"vout_v": 3.3}, {"supply_v": 5})),
    ("led-indicator", "Arduino Uno driving a status LED at 10 mA",
     lambda: single("led_indicator", {"led_current_ma": 10}, {"mcu": "arduino_uno"})),
    ("rs485-modbus", "Arduino Uno + MAX485 RS-485 Modbus RTU master",
     lambda: single("modbus_rtu_master", {}, {"mcu": "arduino_uno"})),
    ("room-monitor", ROOM["intent"],
     lambda: FormProducer().build_project(ROOM["blocks"], ROOM["behaviour"], mcu="arduino_uno")),
]


def simulate(ir, netlist: str) -> dict | None:
    if not ir.simulation_spec:
        return None
    job_id = str(uuid.uuid4())
    start = time.monotonic()
    result = asyncio.run(NgspiceRunner().run(netlist))
    parsed = SpiceResultParser().parse(result["stdout"], result["stderr"])
    grade = SimulationGrader().grade(ir, parsed)
    return {
        "job_id": job_id,
        "circuit_id": ir.circuit_id,
        "status": "complete",
        "duration_ms": int((time.monotonic() - start) * 1000),
        "results": {
            "dc_voltages": parsed.dc_voltages,
            "ac_points_count": len(parsed.ac_points),
            "waveforms": waveforms_from(parsed),
        },
        "grade": {"passed": grade.passed, "failures": grade.failures, "notes": grade.notes},
    }


def firmware(ir) -> dict:
    project = project_for(ir)
    if project is None:
        return {"status": "none", "message": "this design has no microcontroller, so no firmware"}
    base = {"target": project.target, "board": project.board, "build": project.hash}
    result = compile_project(project, root=FW_ROOT)
    if result.status == "passed":
        return {**base, "status": "compiled", "message": f"compiled for the {project.board}",
                "firmware": project.source, "platformio_ini": project.file("platformio.ini")}
    # Never show source that did not build — the Stage 5 rule holds in the demo too.
    return {**base, "status": "failed", "log": result.log,
            "message": f"the firmware did not compile for the {project.board}; it is not shown"}


def build(slug: str, prompt: str, make_intent) -> dict:
    registry = default_registry()
    intent = make_intent()
    assert intent.is_answerable, (slug, intent.open_questions())
    prediction = None
    if intent.requirements.get("function") == "project":
        ir = compose_intent(registry, intent, prompt).circuit
    else:
        dispatch = registry.dispatch(intent)
        assert dispatch.accepted, (slug, dispatch.refusal_summary())
        ir = realize(dispatch.generator, intent)
        prediction = dispatch.generator.predict(intent)

    val = validate_ir(ir)
    rules = HardwareRuleEngine().run(ir)
    netlist = SpiceNetlistGenerator().generate(ir)
    errors = val.errors + rules.errors
    warnings = val.warnings + rules.warnings

    sim = simulate(ir, netlist)
    fw = firmware(ir)
    if sim is not None:
        ir = ir.model_copy(update={"simulation_passed": sim["grade"]["passed"]})

    explanation = DerivedExplainer().explain(ir, val, prediction=prediction, requirements=intent.requirements)
    bom = bom_view(SimpleNamespace(ir_json=ir.model_dump(mode="json"), intent_ir=intent.model_dump(mode="json")))

    generate = {
        "circuit_id": ir.circuit_id,
        "intent": ir.intent,
        "application_class": str(ir.application_class),
        "target_mcu": ir.target_mcu,
        "version": ir.version,
        "simulation_job_id": sim["job_id"] if sim else None,
        "validation": {
            "passed": not errors,
            "errors": [{"field": e.field_path, "message": e.message} for e in errors],
            "warnings": [{"field": w.field_path, "message": w.message} for w in warnings],
        },
        "firmware": fw.get("firmware"),
        "firmware_build": {k: v for k, v in fw.items() if k not in ("firmware", "platformio_ini")},
        "schematic": KiCadSchematicGenerator().generate(ir),
        "bom": BOMCompiler().compile(ir),
        "explanation": explanation,
        "explanation_error": None,
        "explanation_status": "written",
        "pcb_netlist": PcbNetlistGenerator().generate(ir),
        "ir": ir.model_dump(mode="json"),
        "validation_coverage": ir.validation_coverage,
    }
    print(f"{slug}: {ir.circuit_id} sim={'-' if not sim else sim['grade']['passed']} fw={fw['status']} "
          f"errors={len(errors)}", file=sys.stderr)
    return {
        "slug": slug,
        "prompt": prompt,
        "requirements": intent.requirements,
        "generate": generate,
        "simulation": sim,
        "firmware": fw,
        "bom": bom,
        "netlist": netlist,
    }


def main() -> None:
    examples = [build(*e) for e in EXAMPLES]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "scripts/build_demo_fixtures.py — the deterministic pipeline run locally "
                  "(form producer → generator → validator → ngspice → PlatformIO → BOM). "
                  "Explanations are the DerivedExplainer's, not the LLM's.",
        "examples": examples,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    PROMPTS.write_text(json.dumps([{"slug": e["slug"], "prompt": e["prompt"]} for e in examples],
                                  indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} kB)", file=sys.stderr)


if __name__ == "__main__":
    main()
