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

Writes `frontend/e2e/fixtures/{generate,sign_off,simulation}.json`. Needs
ngspice on PATH (as the simulation worker does).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

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


def main() -> None:
    registry = default_registry()
    intent = FormProducer(registry).build("low_pass_filter", {"cutoff_hz": 1000, "supply_v": 5})
    generator = registry.dispatch(intent).generator
    ir = realize(generator, intent)

    val = validate_ir(ir)
    rules = HardwareRuleEngine().run(ir)
    errors, warnings = val.errors + rules.errors, val.warnings + rules.warnings
    generate = {
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
        "firmware": None,
        "schematic": KiCadSchematicGenerator().generate(ir),
        "bom": [_plain(row) for row in BOMCompiler().compile(ir)],
        "explanation": "",
        "ir": ir.model_dump(mode="json"),
        "validation_coverage": ir.validation_coverage,
    }

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

    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in (("generate", generate), ("sign_off", sign_off), ("simulation", simulation)):
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
