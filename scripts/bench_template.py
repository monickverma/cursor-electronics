"""
Print a bench record to fill in for one design — defeater D1.

    python scripts/bench_template.py voltage_divider '{"vout_v": 3.3, "supply_v": 5}'
    python scripts/bench_template.py led_indicator '{"led_current_ma": 10, "mcu": "arduino_uno"}'
    python scripts/bench_template.py --standard docs/bench_templates   # the five on the sheet

The first argument is the function (the form's name for it: low_pass_filter,
voltage_divider, led_indicator, temperature_humidity_sensor,
modbus_rtu_master); the second, the form fields as JSON. The output names the
design exactly as `validation/bench.py` will rebuild it — requirements and the
netlist's hash — lists the parts and supplies you may measure and the
properties you may measure, and leaves every reading as null to fill in. Save
the filled record as `backend/data/bench/<id>.json`; `pytest tests/test_bench.py`
then judges it, and every design it covers stops citing D1 on what agrees.
See docs/BENCH_D1.md for how to measure each one.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
for key, value in {"ANTHROPIC_API_KEY": "", "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
                   "REDIS_URL": "redis://localhost:6379/0", "SECRET_KEY": "x" * 40}.items():
    os.environ.setdefault(key, value)

from ai.form_producer import FormProducer  # noqa: E402
from generators.netlist.spice import SpiceNetlistGenerator  # noqa: E402
from generators.realize import realize  # noqa: E402
from generators.registry import default_registry  # noqa: E402
from proof.netlist import parse  # noqa: E402
from validation.bench import netlist_hash  # noqa: E402


def template(function: str, fields: dict) -> dict:
    registry = default_registry()
    intent = FormProducer(registry).build(function, fields)
    dispatch = registry.dispatch(intent)
    if not dispatch.accepted:
        raise SystemExit(f"no generator accepts that request: {dispatch.refusal_summary()}")
    generator = dispatch.generator
    circuit = realize(generator, intent)
    netlist = SpiceNetlistGenerator().generate(circuit)
    sources = [e.name[2:] for e in parse(netlist).elements if e.kind == "V" and e.value]
    reading = {"value": None, "accuracy": None, "instrument": "your meter, and its stated accuracy"}
    return {
        "id": f"{generator.name}-{datetime.date.today().isoformat()}",
        "measured_by": None,             # a record says who measured; it fails to load until filled
        "date": datetime.date.today().isoformat(),
        "generator": generator.name,
        "board": circuit.target_mcu,
        "requirements": json.loads(json.dumps(dict(intent.requirements))),
        "netlist_sha256": netlist_hash(netlist),
        "parts": {**{c.id: dict(reading, note=f"{c.part_number}, {c.value}") for c in circuit.components
                     if c.type.value in ("resistor", "capacitor")},
                  **{s: dict(reading, note="the supply as measured on the bench, in volts") for s in sources}},
        "measures": {p.id: dict(reading, note=f"{p.label}, in {p.units} ({p.quantity})")
                     for p in generator.properties(intent)},
        "notes": "Delete every part and measure you did not read; keep only real readings.",
    }


#: The designs docs/BENCH_D1.md walks through, one per family, on the Uno —
#: written pre-filled by `--standard` ([2026-09-25]).
STANDARD = {
    "voltage_divider": ("voltage_divider", {"vout_v": 3.3, "supply_v": 5}),
    "led_indicator": ("led_indicator", {"led_current_ma": 10, "mcu": "arduino_uno"}),
    "rc_lowpass": ("low_pass_filter", {"cutoff_hz": 1000, "supply_v": 5}),
    "dht22_node": ("temperature_humidity_sensor", {"mcu": "arduino_uno"}),
    "rs485_node": ("modbus_rtu_master", {"mcu": "arduino_uno"}),
}


def write_standard(folder: Path) -> list:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name, (function, fields) in STANDARD.items():
        record = template(function, fields)
        path = folder / f"{name}.json"
        path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        written.append(path)
    return written


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--standard":
        for path in write_standard(Path(sys.argv[2])):
            print(f"wrote {path}")
        raise SystemExit(0)
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print(json.dumps(template(sys.argv[1], json.loads(sys.argv[2])), indent=1, ensure_ascii=False))
