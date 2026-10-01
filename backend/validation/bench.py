"""
Bench evidence — defeater D1, closable one design at a time.

`brain/decisions.md` [2026-09-24] D1, D2, D7. D1 doubts every behavioural
claim because the model has only ever been checked against mathematics and
ngspice; it is eliminated by "a bench measurement agreeing within tolerance".
This module makes such a measurement count, and makes a disagreeing one fail
loudly instead of being filed.

**A record** (`data/bench/*.json`) names the design — generator, board,
requirements — and the SHA-256 of its SPICE netlist; the parts measured and the
quantities measured, each a value with the instrument's stated accuracy; the
date and who measured.

**It agrees** when the measured interval (value ± accuracy) overlaps the
model's interval for the measured parts: the design's own property quantity,
each measured part pinned to its measured interval, every unmeasured part over
its tolerance box. Evaluated exactly at the box corners — every quantity the
library proves is monotone in each part over its box, the fact the proofs
already rest on.

**It reaches that design only** — same generator, board and netlist. A record
whose design's netlist has since changed is stale: reported, never applied.

**A disagreement reopens D1 for the whole family** (generator × board) until it
is explained; CI fails on it (`tests/test_bench.py`).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from fractions import Fraction
from functools import lru_cache
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict

RECORDS_DIR = Path(__file__).resolve().parent.parent / "data" / "bench"


class Reading(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: float
    accuracy: float                  # ± in the same units, the instrument's stated accuracy
    instrument: str
    note: str = ""                   # what was read, and how — for the next person

    @property
    def interval(self) -> Tuple[float, float]:
        return self.value - abs(self.accuracy), self.value + abs(self.accuracy)


class BenchRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    measured_by: str
    date: str
    generator: str
    board: Optional[str] = None
    requirements: Dict[str, Any]
    netlist_sha256: str
    parts: Dict[str, Reading] = {}   # component id → measured value (ohms, farads)
    measures: Dict[str, Reading]     # property id → measured quantity, SI units
    notes: str = ""


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    record: str
    property: str
    status: str                      # agrees | disagrees | stale | unevaluable
    measured: Optional[Tuple[float, float]] = None
    predicted: Optional[Tuple[float, float]] = None
    detail: str = ""


def netlist_hash(netlist: str) -> str:
    return hashlib.sha256(netlist.encode("utf-8")).hexdigest()


def load_records(directory: Optional[Path] = None) -> Tuple[BenchRecord, ...]:
    directory = Path(directory or os.environ.get("CIRCUITOS_BENCH_DIR") or RECORDS_DIR)
    if not directory.is_dir():
        return ()
    stamp = tuple(sorted((p.name, p.stat().st_mtime) for p in directory.glob("*.json")))
    return _load(str(directory), stamp)


@lru_cache(maxsize=8)
def _load(directory: str, stamp: Tuple) -> Tuple[BenchRecord, ...]:
    out = []
    for name, _ in stamp:
        data = json.loads((Path(directory) / name).read_text(encoding="utf-8"))
        out.append(BenchRecord.model_validate(data))
    return tuple(out)


# ── The model's interval for the measured parts ─────────────────────────────

def _corners_range(fn, boxes: Sequence[Tuple[Fraction, Fraction]]) -> Tuple[float, float]:
    values = [fn(point) for point in product(*boxes)]
    return float(min(values)), float(max(values))


def _diode_current(v_th: float, r_th: float, i_s: float, n_vt: float) -> float:
    """I from V_th = n·V_t·ln(1 + I/I_s) + I·R_th, by bisection (monotone in I)."""
    lo, hi = 0.0, max(v_th / r_th, 0.0)
    for _ in range(200):
        mid = (lo + hi) / 2
        if n_vt * math.log1p(mid / i_s) + mid * r_th > v_th:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def predicted_interval(circuit: Any, spec: Any, parts: Dict[str, Reading]) -> Tuple[float, float]:
    """
    The property's quantity over the box: measured parts at their measured
    intervals, everything else over its declared box.
    """
    import sympy

    from generators.netlist.spice import SpiceNetlistGenerator
    from proof import mna
    from proof.netlist import parse
    from proof.prover import VT, _args, _diode_box, part_variables

    netlist = parse(SpiceNetlistGenerator().generate(circuit)).with_bench([b.line for b in spec.bench])
    variables, _, _ = part_variables(circuit, netlist, spec.bench)
    boxes: Dict[str, Tuple[Fraction, Fraction]] = {n: (Fraction(v.lo), Fraction(v.hi)) for n, v in variables.items()}
    for cid, reading in parts.items():
        # A part by component id (R1 → R_R1), or a supply by its source (VIN → V_VIN):
        # the bench rail is never exactly the requirement's, so it is measured too.
        element = next((e.name for e in netlist.elements
                        if (e.kind in "RC" and e.name.split("_", 1)[-1] == cid)
                        or (e.kind == "V" and e.name.upper() == f"V_{cid.upper()}")), None)
        if element is None:
            raise KeyError(f"measured part {cid} is not an element of the design's netlist")
        lo, hi = reading.interval
        boxes[element] = (Fraction(str(lo)), Fraction(str(hi)))
    symbols = {n: sympy.Symbol(f"B_{i}", positive=True) for i, n in enumerate(boxes)}
    names = list(boxes)
    kind, args = _args(spec.quantity)

    def at(expr):
        # Exact at each corner: rational substitution, then one float.
        return lambda point: float(expr.subs({symbols[n]: sympy.Rational(p.numerator, p.denominator)
                                              for n, p in zip(names, point)}))

    if kind in ("v", "vdiff", "i", "power"):
        system = mna.dc(netlist, symbols, solver="domain")
        if kind == "v":
            expr = system.v(args[0])
        elif kind == "vdiff":
            expr = system.v(args[0]) - system.v(args[1])
        elif kind == "i":
            expr = system.i(args[0])
        else:
            e = netlist.element(args[0])
            expr = (system.v(e.a) - system.v(e.b)) ** 2 / symbols.get(e.name, sympy.Rational(e.value.numerator, e.value.denominator))
        return _corners_range(at(expr), [boxes[n] for n in names])
    if kind == "rth":
        _, r_th = mna.thevenin(netlist, symbols, args[0], args[1] if len(args) > 1 else "0", solver="domain")
        return _corners_range(at(r_th), [boxes[n] for n in names])
    if kind == "cutoff":
        h = mna.transfer(netlist, symbols, args[0], solver="domain")
        num, den = sympy.fraction(sympy.together(h))
        poly = sympy.Poly(sympy.expand(den), mna.S)
        d1, d0 = poly.coeff_monomial(mna.S), poly.coeff_monomial(1)
        return _corners_range(at(d0 / (2 * sympy.pi * d1)), [boxes[n] for n in names])
    if kind == "rise_time":
        node, cap = args
        _, r_th = mna.thevenin(netlist, symbols, node, "0", remove=[cap], solver="domain")
        c = symbols.get(cap, netlist.element(cap).value)
        return _corners_range(at(sympy.log(9) * r_th * c), [boxes[n] for n in names])
    if kind in ("diode_current", "series_power"):
        diode = args[0] if kind == "diode_current" else args[1]
        box = _diode_box(circuit, netlist, diode)
        anode, cathode = netlist.element(diode).a, netlist.element(diode).b
        v_th, r_th = mna.thevenin(netlist, symbols, anode, cathode, remove=[diode], solver="domain")
        fv, fr = at(v_th), at(r_th)
        resistor = netlist.element(args[0]) if kind == "series_power" else None
        n_vt = float(box.n * VT)
        values = []
        for point in product(*[boxes[n] for n in names]):
            for i_s in (float(box.is_lo_outer), float(box.is_hi_outer)):
                current = _diode_current(fv(point), fr(point), i_s, n_vt)
                if resistor is None:
                    values.append(current)
                else:
                    r = float(point[names.index(resistor.name)]) if resistor.name in names else float(resistor.value)
                    values.append(current ** 2 * r)
        return min(values), max(values)
    raise ValueError(f"no bench evaluation for {spec.quantity}")


# ── Findings ─────────────────────────────────────────────────────────────────

def evaluate(record: BenchRecord) -> List[Finding]:
    """Rebuild the record's design and judge each measured quantity against the model."""
    from core.intent_ir import IntentIR, Producer, Provenance
    from generators.netlist.spice import SpiceNetlistGenerator
    from generators.registry import default_registry

    generator = default_registry().by_name(record.generator)
    if generator is None:
        return [Finding(record=record.id, property=p, status="unevaluable", detail="no such generator")
                for p in record.measures]
    intent = IntentIR(requirements=record.requirements, provenance=Provenance(producer=Producer.FORM))
    if not generator.envelope(intent).accepted:
        return [Finding(record=record.id, property=p, status="stale",
                        detail="the recorded requirement is refused by the installed generator")
                for p in record.measures]
    # generate(), not realize(): realize() assesses the claims, which would
    # consult this evidence again. The netlist does not depend on the stamps.
    circuit = generator.generate(intent)
    if netlist_hash(SpiceNetlistGenerator().generate(circuit)) != record.netlist_sha256:
        return [Finding(record=record.id, property=p, status="stale",
                        detail="the design's netlist has changed since it was measured") for p in record.measures]
    specs = {s.id: s for s in generator.properties(intent)}
    out = []
    for pid, reading in record.measures.items():
        spec = specs.get(pid)
        if spec is None:
            out.append(Finding(record=record.id, property=pid, status="unevaluable", detail="no such property"))
            continue
        try:
            lo, hi = predicted_interval(circuit, spec, record.parts)
        except (KeyError, ValueError) as exc:
            out.append(Finding(record=record.id, property=pid, status="unevaluable", detail=str(exc)))
            continue
        m_lo, m_hi = reading.interval
        agrees = m_lo <= hi and lo <= m_hi
        out.append(Finding(record=record.id, property=pid, status="agrees" if agrees else "disagrees",
                           measured=(m_lo, m_hi), predicted=(lo, hi),
                           detail=f"measured {reading.value:g} ± {reading.accuracy:g} ({reading.instrument}); "
                                  f"the model gives {lo:.6g}–{hi:.6g} for the parts as measured"))
    return out


def _findings(records: Sequence[BenchRecord]) -> Tuple[Finding, ...]:
    return _findings_of(tuple(r.model_dump_json() for r in records))


@lru_cache(maxsize=64)
def _findings_of(dumped: Tuple[str, ...]) -> Tuple[Finding, ...]:
    return tuple(f for d in dumped for f in evaluate(BenchRecord.model_validate_json(d)))


def evidence_for(generator_name: str, board: Optional[str], netlist: str,
                 records: Optional[Sequence[BenchRecord]] = None) -> Dict[str, Finding]:
    """
    The properties of *this* design (same generator, board and netlist) that
    agreeing bench evidence covers — none at all if any record for the family
    disagrees. Empty without records.
    """
    records = tuple(load_records() if records is None else records)
    family = [r for r in records if r.generator == generator_name and r.board == board]
    if not family:
        return {}
    findings = list(_findings(family))
    if any(f.status == "disagrees" for f in findings):
        return {}
    here = {r.id for r in family if r.netlist_sha256 == netlist_hash(netlist)}
    return {f.property: f for f in findings if f.record in here and f.status == "agrees"}
