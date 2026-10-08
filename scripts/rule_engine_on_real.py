"""
The project's own RS-485 rules, run on the real circuits.

    python scripts/rule_engine_on_real.py

`validation/rule_engine.py` judges two things about an RS-485 bus from the netlist alone: that a termination
resistor bridges A and B (a warning outside 100–150 Ω, an error if none), and that A has a pull-up and B a pull-down
(an error for each that is missing). It never simulates. Here each real design from
`backend/data/reference_designs.json` is written as a CircuitIR — by this script, from the source's values, not by a
model — and the rules are run on it, beside the physical truth the rules stand for: the idle differential voltage
ngspice gives (`scripts/real_data_check.py`). A rule that passes a bus that reads 0 V, or flags one that holds
250 mV, is wrong about a real circuit.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
for _k, _v in {"ANTHROPIC_API_KEY": "", "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
               "REDIS_URL": "redis://localhost:6379/0", "SECRET_KEY": "x" * 40}.items():
    os.environ.setdefault(_k, _v)

import real_data_check as rc  # noqa: E402
from core.ir_schema import (ApplicationClass, CircuitIR, Component, ComponentType, Connection, Node,  # noqa: E402
                            SignalType, ValidationRule)
from validation.rule_engine import HardwareRuleEngine  # noqa: E402


def ir_of(entry: dict, bias_ohm=None) -> CircuitIR:
    comps, conns = [], []
    nets = {"vcc": ("VCC", SignalType.POWER), "a": ("A", SignalType.RS485_A), "b": ("B", SignalType.RS485_B), "0": ("GND", SignalType.GROUND)}
    used = set()
    for e in entry["elements"]:
        if e["kind"] != "R":
            continue
        ohm = e["ohm"]
        if isinstance(ohm, str):
            ohm = bias_ohm
        comps.append(Component(id=e["id"], type=ComponentType.RESISTOR, part_number=f"REF-{e['id']}", manufacturer="reference",
                               package="axial", value=f"{ohm:g}", confidence=0.9,
                               justification=f"{e['id']} as read from {entry['source']['doc'][:60]}"))
        for pin, node in (("1", e["a"]), ("2", e["b"])):
            conns.append(Connection(component_id=e["id"], pin=pin, node_id=nets[node][0]))
            used.add(node)
    nodes = [Node(id=nets[n][0], type=nets[n][1]) for n in nets if n in used or n in ("a", "b")]
    return CircuitIR(intent=entry["title"], application_class=ApplicationClass.MODBUS_RTU, components=comps, nodes=nodes,
                     connections=conns, validation_rules=[ValidationRule.RS485_TERMINATION_PRESENT, ValidationRule.RS485_BIAS_RESISTORS])


def main() -> None:
    corp = json.loads(rc.CORPUS.read_text(encoding="utf-8"))
    rc.CORP = corp
    engine = HardwareRuleEngine()
    rows = []
    for entry in corp["designs"]:
        if entry["family"] != "rs485_node":
            continue
        var = [None] if not entry.get("variants") else list(entry["variants"].values())[0]
        for v in var:
            ref = rc.from_corpus(entry, {"bias_ohm": v} if v is not None else None)
            sr = (entry["supply_v"]["min"], entry["supply_v"]["nominal"], entry["supply_v"]["max"])
            bias = ("RB1", "RB2") if {"RB1", "RB2"} <= {x[1] for x in ref.elements} else ()
            phys = rc.m_rs485(ref, sr, "a", "b", bias)
            res = engine.run(ir_of(entry, v))
            rows.append((entry["id"] + (f"[{v:g} Ω bias]" if v else ""), res, phys["vab_worst_low_v"]))
    # not from any source: the Modbus circuit with a bias far too weak to hold the bus — the rules check that a bias
    # resistor exists, not how large it is
    modbus = next(e for e in corp["designs"] if e["id"].startswith("rs485.modbus"))
    ref = rc.from_corpus(modbus, {"bias_ohm": 100_000})
    phys = rc.m_rs485(ref, (4.75, 5.0, 5.25), "a", "b", ("RB1", "RB2"))
    rows.append(("SYNTHETIC: the Modbus circuit with 100 kΩ bias", engine.run(ir_of(modbus, 100_000)), phys["vab_worst_low_v"]))
    # and the project's own design
    from ai.form_producer import FormProducer
    from generators.registry import default_registry
    reg = default_registry()
    intent = FormProducer(reg).build("modbus_rtu_master", {"supply_v": 5.0, "mcu": "arduino_uno"})
    gen = reg.dispatch(intent).generator
    circuit = gen.generate(intent)
    circuit.validation_rules = [ValidationRule.RS485_TERMINATION_PRESENT, ValidationRule.RS485_BIAS_RESISTORS]
    g = rc.from_generated(gen, intent, circuit, rc.bench_lines(gen, intent, "rs485.failsafe_bias"))
    gphys = rc.m_rs485(g, (4.75, 5.0, 5.25), "rs485_a", "rs485_b", ("R_R2", "R_R3"))
    rows.append(("Circuit OS, generated (549 Ω bias)", engine.run(circuit), gphys["vab_worst_low_v"]))

    print(f"{'design':56s} {'rule engine says':44s} idle V_AB worst case")
    for name, res, vab in rows:
        says = "passes" if (not res.errors and not res.warnings) else "; ".join(
            [f"error: {e.field_path}" for e in res.errors] + [f"warning: {w.field_path}" for w in res.warnings])
        print(f"{name:56s} {says:44s} {1000 * vab:7.1f} mV  ({'above' if vab >= 0.2 else 'BELOW'} the 200 mV threshold)")


if __name__ == "__main__":
    main()
