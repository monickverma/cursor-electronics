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

Writes `frontend/e2e/fixtures/{generate,sign_off,simulation,firmware,bom,pcb}.json`.
`pcb.json` is the composed room monitor and what POST /pcb/compile returns for it —
the routed Board IR and its 3D scene (decisions.md [2026-10-06]). Only that one:

    python scripts/export_ui_fixtures.py --only pcb
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


#: [2026-09-25] The live fixture's quotes: Mouser's answer *shape*, with made-up
#: prices, in euros as a non-US account sees them. Not real prices — the UI test
#: needs a live row, a currency that is not the catalogue's, and an unlisted part.
SYNTHETIC_MOUSER = {
    "CL05B104KO5NNNC": ("187-CL05B104KO5NNNC", "0,0085 €", "81000"),
    "RC0402FR-0710KL": ("603-RC0402FR-0710KL", "0,0090 €", "250000"),
}


def _synthetic_mouser():
    import httpx

    def answer(request):
        asked = json.loads(request.content)["SearchByPartRequest"]["mouserPartNumber"].split("|")
        parts = [{"ManufacturerPartNumber": pn, "MouserPartNumber": SYNTHETIC_MOUSER[pn][0],
                  "Manufacturer": "(synthetic)", "Min": "1", "Mult": "1",
                  "PriceBreaks": [{"Quantity": 1, "Price": SYNTHETIC_MOUSER[pn][1], "Currency": "EUR"}],
                  "AvailabilityInStock": SYNTHETIC_MOUSER[pn][2],
                  "ProductDetailUrl": f"https://www.mouser.com/ProductDetail/{pn}"}
                 for pn in asked if pn in SYNTHETIC_MOUSER]
        return httpx.Response(200, json={"Errors": [], "SearchResults": {"Parts": parts}})

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(answer))


def _route_view(record, api_key: str = "", client_factory=None) -> dict:
    """What the route answers: bom_view, then live pricing — off without a key."""
    from datetime import datetime, timezone

    from api.routes.bom import bom_view
    from pricing.live import price_view

    async def nothing_cached(db, source, keys):
        return {}

    async def store_nothing(db, source, quotes):
        return None

    kwargs = {"client_factory": client_factory} if client_factory else {}
    return asyncio.run(price_view(None, bom_view(record), api_key=api_key, cache_hours=24,
                                  now=datetime(2026, 9, 25, 9, 30, tzinfo=timezone.utc),
                                  get_cached=nothing_cached, put_cached=store_nothing, **kwargs))


def _bom(registry) -> dict:
    """
    Stage 6: an RS-485 node on the Uno; what GET /design/{id}/bom answers for it
    (dated rows, checked substitutes, the terminators refused by name); what the
    patch route answers when the first substitute is used; and the BOM after.
    [2026-09-25]: the same view with live pricing on, from synthetic quotes.
    """
    from types import SimpleNamespace

    from core.intent_patch import PatchOp, apply_patch

    intent = FormProducer(registry).build("modbus_rtu_master", {"mcu": "arduino_uno"})
    generator = registry.dispatch(intent).generator
    ir = realize(generator, intent)
    record = SimpleNamespace(ir_json=ir.model_dump(mode="json"), intent_ir=intent.model_dump(mode="json"))
    before = _route_view(record)
    if not before["substitutes"]:
        raise SystemExit("the RS-485 design offered no substitutes — the fixture would test nothing")
    used = before["substitutes"][0]
    patched = apply_patch(intent, [PatchOp(**op) for op in used["ops"]]).intent
    after_ir = realize(generator, patched)
    after = _route_view(SimpleNamespace(ir_json=after_ir.model_dump(mode="json"),
                                        intent_ir=patched.model_dump(mode="json")))
    live = _route_view(record, api_key="synthetic-key", client_factory=_synthetic_mouser())
    if not any(r.get("live") for r in live["rows"]):
        raise SystemExit("no row took a synthetic live quote — the live fixture would test nothing")
    generate = _generate_response(ir, {"status": "unavailable", "message": "not built for this fixture"})
    patch = {**_generate_response(after_ir, {"status": "unavailable", "message": "not built for this fixture"}),
             "changes": [f"constraints.pinned.{used['component_id']}: (none) → {used['part_number']}"],
             "note_to_user": "", "predict_delta": [], "citations": [],
             "generator": after_ir.generator, "generator_changed": None}
    return {"generate": generate, "bom": before, "used": used, "patch": patch, "bom_after": after,
            "bom_live": live}


def _pcb(registry) -> dict:
    """The room monitor (docs/projects/room_monitor.json), composed, and the PCB
    compile route's answer for its netlist: SVG, stats, Board IR and 3D scene."""
    from generators.compose import Project, compose
    from generators.netlist.pcb import PcbNetlistGenerator
    from pcb_engine import compile_board

    project = Project.model_validate(json.loads(
        (ROOT / "docs" / "projects" / "room_monitor.json").read_text(encoding="utf-8")))
    ir = compose(registry, project).circuit
    netlist = PcbNetlistGenerator().generate(ir)
    generate = _generate_response(ir, {"status": "unavailable",
                                       "reason": "fixture: firmware is not under test here"})
    generate["pcb_netlist"] = netlist
    return {"generate": generate, "compile": compile_board(netlist).to_dict()}


def main() -> None:
    registry = default_registry()
    if sys.argv[1:] == ["--only", "pcb"]:
        path = OUT / "pcb.json"
        path.write_text(json.dumps(_pcb(registry), indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)}")
        return
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
    bom = _bom(registry)
    pcb = _pcb(registry)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in (("generate", generate), ("sign_off", sign_off), ("simulation", simulation),
                       ("firmware", firmware), ("bom", bom), ("pcb", pcb)):
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
