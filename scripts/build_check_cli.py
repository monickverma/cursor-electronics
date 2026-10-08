"""
The build check at the bench.

    python scripts/build_check_cli.py sheet voltage_divider            # what to measure, and what to expect
    python scripts/build_check_cli.py sheet --detect rs485_node        # the shorter plan: notices, does not name
    python scripts/build_check_cli.py diagnose voltage_divider '{"r:vin,vout": 3412, "r:vout,0": 6603, "r:vin,0": 10010}'
    python scripts/build_check_cli.py sheets docs/BUILD_CHECK_SHEETS.md   # all five designs, written to a file

The designs are the five on the bench sheet (`scripts/bench_template.py::STANDARD`, `docs/BENCH_D1.md`). A
reading's key is printed beside it on the sheet: a node (`vout`), two nodes (`vin-vout`: v(vin) − v(vout)), or
a resistance with the power off (`r:vin,vout`, in ohms; use `Infinity` for OL). Read the rail first when any
voltage is read; its key is the rail's node.

What the verdict means, and does not, is in the docstring of `backend/validation/build_check.py`: it checks
that the board is the design, taking the model as right; the one case that charges the model (defeater D1) is
nothing listed fits *and* every resistance agrees with the design.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
for _k, _v in {"ANTHROPIC_API_KEY": "", "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
               "REDIS_URL": "redis://localhost:6379/0", "SECRET_KEY": "x" * 40}.items():
    os.environ.setdefault(_k, _v)

from build_check_oracle import standard_models  # noqa: E402
from validation.build_check import Analysis  # noqa: E402


def _expect(a: Analysis, p) -> str:
    lo, hi = a.expected(p)
    if p.kind == "r":
        return f"{lo:,.1f} … " + ("OL" if math.isinf(hi) else f"{hi:,.1f}") + " Ω" if not math.isinf(lo) else "OL (nothing joins them)"
    return f"{lo:.4f} … {hi:.4f} V"


def sheet(name: str, a: Analysis, identify: bool = True) -> str:
    plan = a.plan(identify=identify)
    sep = a.detecting()
    listed = [f for f in a.faults if not f.dc_equivalent]
    named = sum(1 for f in listed if sep[f.id])
    lines = [f"## {name}", "",
             f"{'Identification' if identify else 'Detection'} plan: **{len(plan)} readings** "
             f"({'names the fault' if identify else 'notices a fault, does not name it'}). "
             f"{named} of {len(a.faults)} listed faults are detectable.", ""]
    r_plan = [p for p in plan if p.kind == "r"]
    v_plan = [p for p in plan if p.kind == "v"]
    if r_plan:
        lines += ["**1. Power off.** Ohm range, one lead on each net; the ohm range tests below an LED's forward drop, so it "
                  "reads the resistors and ignores the LED.", "",
                  "| Between | Expect | Key |", "|---|---|---|"]
        lines += [f"| {p.text().replace('resistance ', '')} | {_expect(a, p)} | `{p.key}` |" for p in r_plan]
        lines.append("")
    if v_plan:
        lines += [f"**{2 if r_plan else 1}. Power on.**"]
        if a.model.conditions:
            lines.append("Conditions: " + "; ".join(a.model.conditions) + ".")
        lines += [f"Read the rail first — `{a.model.supply_node}` to ground, design range "
                  f"{a.model.supply_range[0]:.2f}–{a.model.supply_range[1]:.2f} V; the expected values below are for the middle of that "
                  "range and the check re-derives them from the rail you actually read.", "",
                  "| Read | Expect (rail at the middle) | Key |", "|---|---|---|"]
        lines += [f"| {p.text()} | {_expect(a, p)} | `{p.key}` |" for p in v_plan]
        lines += [f"| the rail | {a.model.supply_range[0]:.2f}–{a.model.supply_range[1]:.2f} V | `{a.model.supply_node}` |", ""]
    blind = a.blind_spots()
    if blind:
        lines += ["**What this cannot see**", ""]
        lines += [f"- {f.id}: {f.text} — {why.split(';')[0]}" for f, why in blind]
        lines.append("")
    sv = {}
    for part in a.model.parts:
        if a.model.netlist.element(part).kind == "R":
            hi, lo = a.min_detectable_factor(part, "high", probes=plan), a.min_detectable_factor(part, "low", probes=plan)
            sv[a.model.label(part)] = (hi, lo)
    if sv:
        lines += ["**How far off a resistor must be before these readings can tell:** " + "; ".join(
            f"{k} {('more than ' + format(h, 'g') + '× high') if h else 'not at 20× high'}, "
            f"{('below 1/' + format(l, 'g') + ' of its value') if l else 'not at 1/20 low'}" for k, (h, l) in sv.items()) + ".", ""]
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("sheet", "sheets", "diagnose"):
        print(__doc__)
        return 2
    cmd, rest = argv[1], argv[2:]
    models = standard_models()
    if cmd == "sheets":
        out = Path(rest[0]) if rest else ROOT / "docs" / "BUILD_CHECK_SHEETS.md"
        parts = ["# Build check — probe sheets", "",
                 "Generated by `python scripts/build_check_cli.py sheets` from the five standard designs "
                 "(`docs/BENCH_D1.md`). **Do the resistances first, with the power off.** Feed the readings to "
                 "`python scripts/build_check_cli.py diagnose <design> '<json of key: reading>'`.",
                 "", "A 3½-digit hand meter is assumed: ±(0.5 % + 3 digits) on volts, ±(0.8 % + 3 digits) on ohms, 10 MΩ input. "
                 "A better meter narrows every range; `Meter(...)` in `backend/validation/build_check.py`.", ""]
        for name, model in models.items():
            parts.append(sheet(name, Analysis(model), identify=True))
        out.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out)
        return 0
    flags = [x for x in rest if x.startswith("--")]
    pos = [x for x in rest if not x.startswith("--")]
    name = pos[0]
    if name not in models:
        print(f"no such design {name!r}; one of {', '.join(models)}")
        return 2
    a = Analysis(models[name])
    if cmd == "sheet":
        print(sheet(name, a, identify="--detect" not in flags))
        return 0
    readings: Dict[str, float] = {k: float(v) for k, v in json.loads(pos[1]).items()}
    v = a.diagnose(readings)
    print(f"status: {v.status}")
    print(v.summary())
    if v.status == "unexplained":
        print(f"reopens D1: {v.reopens_d1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
