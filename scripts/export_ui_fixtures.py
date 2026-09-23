"""
Export the JSON the frontend's Playwright tests replay — from the real pipeline.

    python scripts/export_ui_fixtures.py

The UI tests (`frontend/e2e/`) mock the backend at the network edge, so they
must be fed what the backend actually returns, not shapes typed by hand. This
script builds a 1 kHz RC low-pass exactly as the routes do — form producer →
registry → `realize()` (claims and Stage 4 proofs) → schematic, BOM, rule
checks — signs its properties the way `POST /sign-off` does, and runs its
netlist through ngspice and the Stage 3 waveform shaper. Re-run it when a
response shape changes; the tests then check the UI against the new shape.

Writes `frontend/e2e/fixtures/{generate,sign_off,simulation,firmware}.json`.
Needs ngspice on PATH (as the simulation worker does). `firmware.json` (Stage 5)
is an ESP32 LED design and the compile gate's answers for it, from
`firmware_view` itself with its table and broker held in memory.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
for key, value in {
    "ANTHROPIC_API_KEY": "",
    "DATABASE_URL": "postgresql+asyncpg://fixtures:fixtures@localhost/fixtures",
    "REDIS_URL": "redis://localhost:6379/0",
    "SECRET_KEY": "fixture-export-secret-key-at-least-32-chars",
}.items():
    os.environ.setdefault(key, value)

from ai.form_producer import FormProducer  # noqa: E402
from api.routes.firmware import firmware_view  # noqa: E402
from core.ir_validator import validate_ir  # noqa: E402
from generators.bom.compiler import BOMCompiler  # noqa: E402
from generators.netlist.spice import SpiceNetlistGenerator  # noqa: E402
from generators.realize import realize  # noqa: E402
from generators.registry import default_registry  # noqa: E402
from generators.schematic.kicad import KiCadSchematicGenerator  # noqa: E402
from simulation.grader import SimulationGrader  # noqa: E402
from simulation.parser import SpiceResultParser  # noqa: E402
from simulation.runner import NgspiceRunner  # noqa: E402
from simulation.waveforms import waveforms_from  # noqa: E402
from validation.rule_engine import HardwareRuleEngine  # noqa: E402

OUT = ROOT / "frontend" / "e2e" / "fixtures"
SIGNER = "engineer@example.com"
JOB_ID = "00000000-0000-4000-8000-00000000f1a7"


def _plain(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _generate_response(ir, firmware_build: dict, firmware=None) -> dict:
    """What POST /design/generate returns for `ir`."""
    val = validate_ir(ir)
    rules = HardwareRuleEngine().run(ir)
    errors, warnings = val.errors + rules.errors, val.warnings + rules.warnings
    return {
        "circuit_id": ir.circuit_id,
        "intent": ir.intent,
        "application_class": str(ir.application_class),
        "target_mcu": ir.target_mcu,
        "version": ir.version,
        "simulation_job_id": JOB_ID,
        "validation": {
            "passed": not errors,
            "errors": [{"field": e.field_path, "message": e.message} for e in errors],
            "warnings": [{"field": w.field_path, "message": w.message} for w in warnings],
        },
        "firmware": firmware,
        "firmware_build": firmware_build,
        "schematic": KiCadSchematicGenerator().generate(ir),
        "bom": [_plain(row) for row in BOMCompiler().compile(ir)],
        "explanation": "",
        "ir": ir.model_dump(mode="json"),
        "validation_coverage": ir.validation_coverage,
    }


def _firmware(registry) -> dict:
    """
    Stage 5: an ESP32 LED design, and what the compile gate answers for it while
    it compiles, once it has, and if it had failed — each from `firmware_view`,
    with the `firmware_builds` table and the Celery broker held in memory.
    """
    import api.routes.firmware as gate

    intent = FormProducer(registry).build(
        "led_indicator", {"led_current_ma": 5, "mcu": "esp32_devkitc", "supply_v": 3.3})
    ir = realize(registry.dispatch(intent).generator, intent)

    rows: dict = {}
    outcome: dict = {"value": None}

    async def get(db, build_hash):
        return rows.get(build_hash)

    async def queue(db, build_hash, target):
        rows[build_hash] = SimpleNamespace(status="queued", log="")

    async def finish(db, build_hash, status, log, seconds):
        rows[build_hash] = SimpleNamespace(status=status, log=log)

    gate.get_firmware_build, gate.queue_firmware_build, gate.finish_firmware_build = get, queue, finish
    gate.compile_firmware.apply_async = lambda args, task_id: None
    gate._poll = lambda build_hash: outcome["value"]

    view = lambda: asyncio.run(firmware_view(None, ir)).model_dump()  # noqa: E731
    compiling = view()
    outcome["value"] = {"status": "passed", "log": "[SUCCESS]", "seconds": 4.2}
    compiled = view()
    # A failed build, as the worker would record it: the log's tail, no source.
    rows[compiled["build"]] = SimpleNamespace(
        status="failed", log="src/main.ino:21:1: error: 'LED_PIN' was not declared in this scope\n"
                            "*** [.pio/build/esp32_devkitc/src/main.ino.cpp.o] Error 1\n"
                            "========== [FAILED] Took 3.10 seconds ==========")
    failed = view()
    assert compiling["status"] == "compiling" and compiling["firmware"] is None
    assert compiled["status"] == "compiled" and compiled["firmware"]
    assert failed["status"] == "failed" and failed["firmware"] is None
    hidden = {"firmware", "platformio_ini"}
    return {
        "generate": _generate_response(ir, {k: v for k, v in compiling.items() if k not in hidden}),
        "compiling": compiling, "compiled": compiled, "failed": failed,
    }


def main() -> None:
    registry = default_registry()
    intent = FormProducer(registry).build("low_pass_filter", {"cutoff_hz": 1000, "supply_v": 5})
    generator = registry.dispatch(intent).generator
    ir = realize(generator, intent)
    # Stage 5: the compile gate's status. A design with no MCU never reaches
    # the database, so this is the route's own answer.
    none = asyncio.run(firmware_view(None, ir)).model_dump(exclude={"firmware", "platformio_ini"})
    generate = _generate_response(ir, none)

    # What POST /sign-off returns: the same circuit, its proofs now counted.
    shown = ir.validation_coverage["properties_hash"]
    signed = realize(generator, intent.sign_off(by=SIGNER, properties_hash=shown))
    assert signed.validation_coverage["properties_signed"], "sign-off did not take"
    sign_off = {
        "circuit_id": ir.circuit_id, "version": signed.version, "signed_by": SIGNER,
        "properties_hash": shown, "validation_coverage": signed.validation_coverage,
        "intent_ir": {},
    }

    # What GET /simulation/{job} returns once the worker has finished.
    netlist = SpiceNetlistGenerator().generate(ir)
    run = NgspiceRunner()._run_sync(netlist)
    parsed = SpiceResultParser().parse(run["stdout"], run["stderr"])
    if not parsed.ac_points:
        raise SystemExit("ngspice produced no AC sweep — is ngspice on PATH?")
    grade = SimulationGrader().grade(ir, parsed)
    simulation = {
        "job_id": JOB_ID, "circuit_id": ir.circuit_id, "status": "complete", "duration_ms": 0,
        "results": {"dc_voltages": parsed.dc_voltages, "ac_points_count": len(parsed.ac_points),
                    "waveforms": waveforms_from(parsed)},
        "grade": {"passed": grade.passed, "failures": grade.failures, "notes": grade.notes},
    }

    firmware = _firmware(registry)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in (("generate", generate), ("sign_off", sign_off), ("simulation", simulation),
                       ("firmware", firmware)):
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
