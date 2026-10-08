"""
Build check — is the board on the bench the design that was drawn?

`validation/bench.py` assumes the board was built correctly and asks whether the
*model* is right (defeater D1). This module asks the other question, with the model
taken as right: **did the person wire what the netlist says?** The two read the same
multimeter, so each needs the other: a resistor in the wrong breadboard row would
otherwise be charged to the model, and D1 would reopen for a design that was never
built.

**What it does, in three steps.**

1. *Faults* (`enumerate_faults`): the usual ways a build goes wrong — a part missing
   or a lead lifted (open), a solder bridge (short), a value far off (more than 1.5× too large or
   less than ⅔), two parts exchanged, one lead one hole over (every other net), an LED backwards —
   each made by changing the design's own netlist and re-reading it.
2. *Analysis* (`Analysis`): for every reading a multimeter can take — power off, the
   resistance between two nets; power on, a voltage from a node to ground or between two
   nodes — the exact range the correct build can give, over every part's tolerance box and
   the supply; and the same for each fault. A fault is
   **detectable** by a reading when its range and the correct build's are further
   apart than the meter's stated accuracy allows at both ends. A smallest set of
   readings that detects every detectable fault is the **probe plan**. A fault no
   reading separates is a **blind spot**, reported with the nearest miss — never
   counted as passed.
3. *Verdict* (`Analysis.diagnose`): readings in, one of
   `as_designed`  — consistent with the design, every detectable fault excluded;
   `inconclusive` — consistent, but the readings taken leave a detectable fault open;
   `fault`        — the design is inconsistent with the readings and these listed
                     faults fit (one name, or several the readings cannot separate);
   `unexplained`  — nothing listed fits. Only this case can be a model question, and it is the
                     one that reopens D1 (the owner's choice, 2026-10-06) — unless a power-off
                     resistance reads off, which says a *part* is wrong, not the model: see
                     `Verdict.reopens_d1` and `brain/decisions.md` [2026-10-08] item 4.
   The measured supply is read first and used in place of the design's ±5 % — what
   the bench rail really is — and a rail outside the design range is reported on its
   own, not blamed on a part.

**What the guarantee is, and what it is not.** If every part lies inside its tolerance
box (the same boxes the proofs use, `proof/prover.py::part_variables`), the supply
inside the range it was read in, and the meter within its stated accuracy, then a
fault the plan detects *cannot* produce readings the correct build could produce, so
the verdict is never `as_designed` while it is present. That is the whole claim:

- The device models are assumed right (this is the check that *takes* the model as
  right); an LED's forward voltage is its datasheet range, not a measurement.
- Only resistors, capacitors and LEDs/diodes are parts a fault can be listed for. An IC's pins
  (A and B swapped at a transceiver), a transistor's legs, a connector, the load and the MCU are
  not: a mistake there is not listed and is not covered. On the load switch the check lists
  faults for R1 and C1 and for nothing else.
- It covers listed faults. A fault nobody listed is not shown absent: it ends
  `unexplained` or, worse, matches a listed fault by accident — which the accuracy
  experiment (`scripts/build_check_accuracy.py`) measures instead of assuming.
- A capacitor is invisible to a multimeter's DC ranges (open or wrong value changes nothing)
  and a short across an *ideal* supply changes no voltage — but the power-off resistance
  between the rail and ground sees that short, so only the capacitor's *value* is blind, and
  says so. An LED reads open on the ohm range (its forward drop is above the meter's test
  voltage); its polarity is a voltage reading.
- The power-off network is the physical resistors only: the MCU's supply model, a pin's
  Thevenin source and the 1 GΩ floating-node ties exist only while powered. A resistance
  above the meter's top range reads OL, and OL is a reading like any other.
- "Exact" means: node voltages of a resistive network are Möbius functions of each
  single resistance, so every extreme over the tolerance box sits at a corner, and
  corners are solved in rational arithmetic. The one diode is solved by bisection
  over its saturation-current box, the way `bench.py` does it.

Pure Python (fractions and floats); no solver is imported. The oracle that
tests it is ngspice (`tests/test_build_check.py`, `scripts/build_check_accuracy.py`).
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from proof.netlist import Element, Netlist

#: Thermal voltage at ngspice's 27 °C, as `proof/prover.py` has it.
VT = 1.380649e-23 * 300.15 / 1.602176634e-19

OPEN_OHM = Fraction(10) ** 9          # an open part, as the netlist's own floating-node tie
SHORT_OHM = Fraction(1, 1000)         # a solder bridge, at its best
SHORT_MAX_OHM = Fraction(1)           # …and at its worst: contact and lead resistance never reach zero
#: A leak to ground on every free node, so a node nothing holds (a capacitor's far end at DC,
#: a lifted lead) has a defined voltage instead of a singular system. ngspice puts none on a
#: linear node, so this is 1 PΩ — under its print precision — to agree with it.
GMIN = Fraction(1, 10 ** 15)


class Unsupported(ValueError):
    """A netlist this module does not read: it refuses rather than guess."""


# ── The meter ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Meter:
    """
    A DC voltmeter as its data sheet states it: ±(gain · reading + digits · resolution)
    on the range the reading needs, and an input resistance that loads the circuit.
    The default is a 3½-digit hand meter (±0.5 % + 3 digits on 2 V and 20 V ranges).
    """

    gain: float = 0.005
    digits: int = 3
    ranges: Tuple[Tuple[float, float], ...] = ((2.0, 0.001), (20.0, 0.01), (200.0, 0.1), (1000.0, 1.0))
    input_ohm: float = 10e6
    #: The ohm ranges of the same meter: ±(0.8 % + 3 digits), full scale 200 Ω … 20 MΩ, then OL.
    r_gain: float = 0.008
    r_digits: int = 3
    r_ranges: Tuple[Tuple[float, float], ...] = ((200.0, 0.1), (2e3, 1.0), (20e3, 10.0), (200e3, 100.0),
                                                 (2e6, 1e3), (20e6, 1e4))

    def resolution(self, volts: float) -> float:
        a = abs(volts)
        for full_scale, res in self.ranges:
            if a <= full_scale:
                return res
        return self.ranges[-1][1]

    def uncertainty(self, volts: float) -> float:
        return self.gain * abs(volts) + self.digits * self.resolution(volts)

    @property
    def overload_ohm(self) -> float:
        return self.r_ranges[-1][0]

    def r_resolution(self, ohms: float) -> float:
        a = abs(ohms)
        for full_scale, res in self.r_ranges:
            if a <= full_scale:
                return res
        return self.r_ranges[-1][1]

    def r_uncertainty(self, ohms: float) -> float:
        if math.isinf(ohms):
            return 0.0
        return self.r_gain * abs(ohms) + self.r_digits * self.r_resolution(ohms)

    def observe_ohm(self, ohms: float) -> float:
        """What the ohm range shows for a true resistance: itself, or OL (∞) above its top range."""
        return ohms if ohms <= self.overload_ohm else math.inf


#: A good bench meter, for the sensitivity runs.
BENCH_METER = Meter(gain=0.001, digits=2, ranges=((0.2, 1e-5), (2.0, 1e-4), (20.0, 1e-3), (200.0, 1e-2)),
                    r_gain=0.002, r_digits=2)


# ── A probe is a reading ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class Probe:
    """One reading. Voltage (powered): v(a) to ground, or v(a) − v(b). Resistance (power off): a to b."""

    a: str
    b: Optional[str] = None
    kind: str = "v"                # "v" | "r"

    @property
    def key(self) -> str:
        if self.kind == "r":
            return f"r:{self.a},{self.b}"
        return self.a if self.b is None else f"{self.a}-{self.b}"

    def text(self) -> str:
        if self.kind == "r":
            name = lambda n: "GND" if n == "0" else n.upper()
            return f"resistance {name(self.a)} ↔ {name(self.b)}"
        return f"v({self.a})" if self.b is None else f"v({self.a}) − v({self.b})"


# ── What is built ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BuildModel:
    """The design as a person builds it: parts with boxes, nets, and what a meter can reach."""

    netlist: Netlist
    boxes: Mapping[str, Tuple[Fraction, Fraction]]       # toleranced R and C: element → (lo, hi)
    parts: Tuple[str, ...]                               # elements a person places (fault-eligible)
    labels: Mapping[str, str]                            # element → "R1"
    nets: Tuple[str, ...]                                # nets a lead can land on, ground ("0") included
    probes: Tuple[str, ...]                              # nodes a meter can read, supply excluded
    supply_node: str
    supply_source: str
    supply_range: Tuple[float, float]                    # the design's range for the rail, volts
    follow: Tuple[str, ...] = ()                         # sources that follow the rail (a pin driving high)
    diode_is: Mapping[str, Tuple[float, float]] = field(default_factory=dict)   # diode → (Is lo, Is hi)
    conditions: Tuple[str, ...] = ()

    @classmethod
    def from_circuit(cls, circuit, supply_tol: float = 0.05) -> "BuildModel":
        """From a generated CircuitIR, with the tolerance boxes the proofs use."""
        from generators.netlist.spice import SpiceNetlistGenerator
        from proof.netlist import parse
        from proof.prover import _diode_box, part_variables

        nl = parse(SpiceNetlistGenerator().generate(circuit))
        # A filter's source is an AC source; the bench drives it with the same level as DC.
        els = [replace(e, value=e.ac, ac=None) if e.kind == "V" and e.ac else e for e in nl.elements]
        nl = Netlist(elements=els, diode_models=nl.diode_models, analysis="op")
        variables, _, _ = part_variables(circuit, nl, ())
        boxes = {n: (Fraction(v.lo), Fraction(v.hi)) for n, v in variables.items()}
        comps = {c.id: c for c in circuit.components}
        parts, labels = [], {}
        for e in nl.elements:
            if e.kind in ("R", "C", "D") and "_" in e.name:
                cid = e.name.split("_", 1)[1]
                comp = comps.get(cid)
                if comp is not None and comp.type.value in ("resistor", "capacitor", "led", "diode"):
                    parts.append(e.name)
                    labels[e.name] = cid
        sources = [e for e in nl.elements if e.kind == "V"]
        supply = next(e for e in sources if not e.name.upper().startswith(("V_PIN_", "V_SAT_")))
        follow = tuple(e.name for e in sources if e.name.upper().startswith("V_PIN_"))
        volts = float(supply.value)
        nets = tuple(sorted({n.id.lower() for n in circuit.nodes} - {"gnd"})) + ("0",)
        touched = {n for e in nl.elements if e.name in parts for n in (e.a, e.b)}
        probes = tuple(n for n in nl.nodes() if n in nets and n in touched and n != supply.a)
        diode_is = {}
        for e in nl.elements:
            if e.kind == "D":
                box = _diode_box(circuit, nl, e.name)
                diode_is[e.name] = (float(box.is_lo_outer), float(box.is_hi_outer))
        conditions = tuple(f"the MCU pin driving {e.a.replace('_src', '').upper()} is held high by the firmware"
                           for e in sources if e.name in follow)
        return cls(nl, boxes, tuple(parts), labels, nets, probes, supply.a, supply.name,
                   (volts * (1 - supply_tol), volts * (1 + supply_tol)), follow, diode_is, conditions)

    @property
    def node_order(self) -> Tuple[str, ...]:
        return (self.supply_node,) + tuple(self.probes)

    def r_nodes(self) -> Tuple[str, ...]:
        """Nets a physical part touches, then ground — the places an ohmmeter can be put."""
        seen: List[str] = []
        for e in self.netlist.elements:
            if e.name in self.parts:
                for n in (e.a, e.b):
                    if n != "0" and n not in seen:
                        seen.append(n)
        return tuple(seen) + ("0",)

    def all_probes(self, kinds: Sequence[str] = ("v", "r")) -> Tuple[Probe, ...]:
        out: List[Probe] = []
        if "v" in kinds:
            out += [Probe(n) for n in self.probes]
            out += [Probe(a, b) for a, b in itertools.combinations(self.node_order, 2)]
        if "r" in kinds:
            out += [Probe(a, b, "r") for a, b in itertools.combinations(self.r_nodes(), 2)]
        return tuple(out)

    def label(self, element: str) -> str:
        return self.labels.get(element, element)


# ── Faults ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Fault:
    id: str
    kind: str            # open | short | wrong_value | swapped | moved | reversed
    text: str            # what the person did, in words
    elements: Tuple[str, ...]
    netlist: Netlist
    boxes: Mapping[str, Tuple[Fraction, Fraction]]
    dc_equivalent: bool = False      # identical to the design at DC: nothing a voltmeter can see


def _replace_element(nl: Netlist, name: str, new: Optional[Element]) -> Netlist:
    els = []
    for e in nl.elements:
        if e.name == name:
            if new is not None:
                els.append(new)
        else:
            els.append(e)
    return Netlist(elements=els, diode_models=nl.diode_models, analysis=nl.analysis)


def _canon(nl: Netlist, boxes: Mapping[str, Tuple[Fraction, Fraction]]) -> Tuple:
    """A netlist as DC sees it, independent of part names: capacitors are open and drop out."""
    rows = []
    for e in nl.elements:
        if e.kind == "C":
            continue
        ends = tuple(sorted((e.a, e.b))) if e.kind == "R" else (e.a, e.b)
        box = boxes.get(e.name)
        rows.append((e.kind, ends, e.value if e.kind in ("R", "V") else e.model, box))
    return tuple(sorted(rows, key=repr))


#: A resistor of the wrong value is a *range*, not a handful of factors: more than 1.5× too
#: large (a colour band misread, 4.7k put where 2.2k goes) or less than ⅔ of its value. Two
#: ranges name every mistake from 1.5× to 20× off without a candidate per factor; anything
#: closer than 1.5× is an E-series neighbour a meter cannot tell from tolerance, and is reported
#: as a sensitivity (`Analysis.min_detectable_factor`), not listed as a fault.
VALUE_RANGES = (("high", Fraction(3, 2), Fraction(20), "more than 1.5× too large"),
                ("low", Fraction(1, 20), Fraction(2, 3), "less than ⅔ of its value"))


def enumerate_faults(model: BuildModel, moved: bool = True) -> List[Fault]:
    """Every listed way to build it wrong, as a changed netlist. Duplicates (same DC network) are folded."""
    nl = model.netlist
    base = {e.name: e for e in nl.elements}
    tol = {n: (lo, hi) for n, (lo, hi) in model.boxes.items()}
    out: List[Fault] = []
    seen = {_canon(nl, tol)}
    lab = model.label

    def add(fid: str, kind: str, text: str, els: Tuple[str, ...], netlist: Netlist,
            boxes: Mapping[str, Tuple[Fraction, Fraction]], eq: bool = False) -> None:
        key = _canon(netlist, boxes)
        if key in seen:
            if not eq:
                return
        seen.add(key)
        out.append(Fault(fid, kind, text, els, netlist, dict(boxes), dc_equivalent=eq))

    for name in model.parts:
        e = base[name]
        L = lab(name)
        if e.kind == "R":
            nominal = (tol[name][0] + tol[name][1]) / 2 if name in tol else e.value
            b = {k: v for k, v in tol.items() if k != name}
            add(f"{L}:open", "open", f"{L} left out, or one lead not in its hole", (name,),
                _replace_element(nl, name, replace(e, value=OPEN_OHM)), b)
            bs = dict(b)
            bs[name] = (SHORT_OHM, SHORT_MAX_OHM)
            add(f"{L}:short", "short", f"{L} bridged by solder or a jumper (both ends on one net)", (name,),
                _replace_element(nl, name, replace(e, value=SHORT_OHM)), bs)
            for tag, flo, fhi, words in VALUE_RANGES:
                bb = dict(b)
                bb[name] = (nominal * flo, nominal * fhi)
                add(f"{L}:{tag}", "wrong_value", f"{L} {words}: a colour band misread, or the wrong part picked",
                    (name,), nl, bb)
        elif e.kind == "C":
            # At DC a capacitor is open: open and wrong-value change nothing a voltmeter sees.
            add(f"{L}:open", "open", f"{L} left out", (name,), nl, tol, eq=True)
            add(f"{L}:wrong_value", "wrong_value", f"{L} the wrong capacitance", (name,), nl, tol, eq=True)
            b = {k: v for k, v in tol.items() if k != name}
            b[name] = (SHORT_OHM, SHORT_MAX_OHM)
            short = Element("R", name, e.a, e.b, value=SHORT_OHM)
            add(f"{L}:short", "short", f"{L} shorted (a wrong part, or a bridge)", (name,),
                _replace_element(nl, name, short), b)
        elif e.kind == "D":
            add(f"{L}:reversed", "reversed", f"{L} in backwards", (name,),
                _replace_element(nl, name, replace(e, a=e.b, b=e.a)), tol)
            add(f"{L}:open", "open", f"{L} left out, or one lead not in its hole", (name,),
                _replace_element(nl, name, None), tol)
            ds = dict(tol)
            ds[name] = (SHORT_OHM, SHORT_MAX_OHM)
            add(f"{L}:short", "short", f"{L} bridged", (name,),
                _replace_element(nl, name, Element("R", name, e.a, e.b, value=SHORT_OHM)), ds)

    # Two parts exchanged: each takes the other's value (and its tolerance).
    rs = [n for n in model.parts if base[n].kind == "R"]
    for x, y in itertools.combinations(rs, 2):
        vx, vy = base[x].value, base[y].value
        if vx == vy:
            continue
        els = []
        for e in nl.elements:
            if e.name == x:
                els.append(replace(e, value=vy))
            elif e.name == y:
                els.append(replace(e, value=vx))
            else:
                els.append(e)
        b = dict(tol)
        if x in tol and y in tol:
            b[x], b[y] = tol[y], tol[x]
        add(f"{lab(x)}↔{lab(y)}:swapped", "swapped", f"{lab(x)} and {lab(y)} in each other's places", (x, y),
            Netlist(elements=els, diode_models=nl.diode_models, analysis=nl.analysis), b)

    # A lead one hole over: each terminal of each resistor or diode on every other net.
    if moved:
        for name in model.parts:
            e = base[name]
            if e.kind not in ("R", "D"):
                continue
            for end in ("a", "b"):
                here, there = getattr(e, end), getattr(e, "b" if end == "a" else "a")
                for net in model.nets:
                    if net in (here, there):
                        continue
                    moved_e = replace(e, **{end: net})
                    add(f"{lab(name)}.{end}→{net}:moved",
                        "moved", f"{lab(name)}'s {'first' if end == 'a' else 'second'} lead on net {net.upper() if net != '0' else 'GND'}"
                        f" instead of {here.upper() if here != '0' else 'GND'}", (name,),
                        _replace_element(nl, name, moved_e), tol)
    return out


# ── The DC solver, in rational arithmetic ────────────────────────────────────

def _solve(G: List[List[Fraction]], rhs: List[List[Fraction]]) -> List[List[Fraction]]:
    n = len(G)
    A = [list(G[i]) + list(rhs[i]) for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(A[r][col]))
        if A[piv][col] == 0:
            raise ArithmeticError("singular system")
        A[col], A[piv] = A[piv], A[col]
        inv = 1 / A[col][col]
        A[col] = [x * inv for x in A[col]]
        for r in range(n):
            if r != col and A[r][col] != 0:
                f = A[r][col]
                A[r] = [x - f * y for x, y in zip(A[r], A[col])]
    return [row[n:] for row in A]


class _Struct:
    """A netlist read once for repeated DC solves with different part values."""

    def __init__(self, nl: Netlist, supply_source: str, follow: Sequence[str]) -> None:
        self.res = [(e.name, e.a, e.b, e.value) for e in nl.elements if e.kind == "R"]
        self.diodes = [(e.name, e.a, e.b, e.model) for e in nl.elements if e.kind == "D"]
        self.supply_source, self.follow = supply_source, frozenset(follow)
        self.fixed: Dict[str, Tuple[str, int, Fraction]] = {}
        for e in nl.elements:
            if e.kind == "V":
                if e.b == "0":
                    self.fixed[e.a] = (e.name, 1, e.value)
                elif e.a == "0":
                    self.fixed[e.b] = (e.name, -1, e.value)
                else:
                    raise Unsupported(f"source {e.name} floats between {e.a} and {e.b}")
        nodes = list(nl.nodes())
        self.free = [n for n in nodes if n not in self.fixed]
        self.idx = {n: i for i, n in enumerate(self.free)}
        self.models = nl.diode_models
        self.nodes = nodes

    def dc(self, rvals: Mapping[str, Fraction], supply: Fraction, loads: Sequence[Tuple[str, Optional[str], Fraction]] = (),
           is_value: Optional[float] = None) -> Dict[str, float]:
        # A meter lead can land on a node nothing in this netlist touches (a lead moved off it).
        idx = dict(self.idx)
        for a, b, _ in loads:
            for x in (a, b):
                if x is not None and x != "0" and x not in idx and x not in self.fixed:
                    idx[x] = len(idx)
        n = len(idx)
        G = [[Fraction(0)] * n for _ in range(n)]
        rhs = [Fraction(0)] * n
        fixed_v: Dict[str, Fraction] = {}
        for node, (name, sign, val) in self.fixed.items():
            v = supply if (name == self.supply_source or name in self.follow) else val
            fixed_v[node] = sign * v

        def stamp(a: str, b: str, g: Fraction) -> None:
            for x, y in ((a, b), (b, a)):
                if x in idx:
                    i = idx[x]
                    G[i][i] += g
                    if y in idx:
                        G[i][idx[y]] -= g
                    elif y in fixed_v:
                        rhs[i] += g * fixed_v[y]

        for name, a, b, val in self.res:
            stamp(a, b, 1 / rvals.get(name, val))
        for a, b, ohm in loads:
            stamp(a, b if b is not None else "0", 1 / Fraction(ohm))
        for i in range(n):
            G[i][i] += GMIN
        cols = [[r] for r in rhs]
        diode = self.diodes[0] if self.diodes else None
        if diode is not None and len(self.diodes) > 1:
            raise Unsupported("more than one diode")
        if diode is not None:
            _, da, dc, _ = diode
            for i, row in enumerate(cols):
                e = Fraction(0)
                if da in idx and idx[da] == i:
                    e += 1
                if dc in idx and idx[dc] == i:
                    e -= 1
                row.append(e)
        sol = _solve(G, cols) if n else []
        v0 = {nname: float(sol[i][0]) for nname, i in idx.items()}
        for node, v in fixed_v.items():
            v0[node] = float(v)
        v0["0"] = 0.0
        if diode is None:
            return v0
        _, da, dc, model = diode
        u = {nname: float(sol[i][1]) for nname, i in idx.items()}
        u.update({k: 0.0 for k in list(fixed_v) + ["0"]})
        vth = v0[da] - v0[dc]
        rth = u[da] - u[dc]
        is_, nn = self.models[model]
        is_f = float(is_) if is_value is None else is_value
        current = _diode_current(vth, rth, is_f, float(nn) * VT)
        return {k: v0[k] - current * u.get(k, 0.0) for k in v0}


def _diode_current(v_th: float, r_th: float, i_s: float, n_vt: float) -> float:
    """I from V_th = n·V_t·ln(1 + I/I_s) + I·R_th (forward), by bisection; 0 for a reverse drive."""
    if v_th <= 0.0:
        return 0.0
    lo, hi = 0.0, v_th / r_th if r_th > 0 else v_th / 1e-9
    for _ in range(200):
        mid = (lo + hi) / 2
        if n_vt * math.log1p(mid / i_s) + mid * r_th > v_th:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


# ── The power-off network: what an ohmmeter sees ────────────────────────────

class _RNet:
    """
    The physical resistors of a hypothesis with every source gone: the network an ohmmeter reads
    on an unpowered board. The MCU's supply model, a pin's Thevenin source and the floating-node
    ties are models of a *powered* chip; capacitors are open to a DC test and an LED's forward drop
    is above the meter's test voltage, so neither conducts.
    """

    def __init__(self, nl: Netlist, physical: FrozenSet[str]) -> None:
        self.res = [(e.name, e.a, e.b, e.value) for e in nl.elements if e.kind == "R" and e.name in physical]
        self.names = frozenset(n for n, *_ in self.res)
        nodes: List[str] = []
        for _, a, b, _ in self.res:
            for n in (a, b):
                if n not in nodes:
                    nodes.append(n)
        self.nodes = nodes
        self.idx = {n: i for i, n in enumerate(nodes)}

    def rab(self, rvals: Mapping[str, Fraction], a: str, b: str) -> float:
        """The resistance between two nets; ∞ if nothing joins them. Exact, in rational arithmetic."""
        if a == b:
            return 0.0
        if a not in self.idx or b not in self.idx:
            return math.inf
        n = len(self.nodes)
        G = [[Fraction(0)] * n for _ in range(n)]
        for name, x, y, val in self.res:
            g = 1 / rvals.get(name, val)
            i, j = self.idx[x], self.idx[y]
            G[i][i] += g
            G[j][j] += g
            G[i][j] -= g
            G[j][i] -= g
        for i in range(n):
            G[i][i] += GMIN
        e = [[Fraction(0)] for _ in range(n)]
        e[self.idx[a]][0] += 1
        e[self.idx[b]][0] -= 1
        x = _solve(G, e)
        return float(x[self.idx[a]][0] - x[self.idx[b]][0])


# ── Hypotheses and the analysis ──────────────────────────────────────────────

@dataclass
class Hypothesis:
    id: str
    text: str
    netlist: Netlist
    boxes: Mapping[str, Tuple[Fraction, Fraction]]
    struct: _Struct
    fault: Optional[Fault] = None
    physical: FrozenSet[str] = frozenset()
    _rnet: Optional[_RNet] = None

    @property
    def has_diode(self) -> bool:
        return bool(self.struct.diodes)

    @property
    def rnet(self) -> _RNet:
        if self._rnet is None:
            self._rnet = _RNet(self.netlist, self.physical)
        return self._rnet


def _fr(x: float) -> Fraction:
    return Fraction(str(round(x, 9)))


def _sub(x: float, y: float) -> float:
    """x − y over the extended reals, with ∞ − ∞ taken as 0 (two readings that are both OL do not differ)."""
    return 0.0 if math.isinf(x) and math.isinf(y) and x == y else x - y


@dataclass(frozen=True)
class Verdict:
    status: str                              # as_designed | inconclusive | fault | unexplained
    supply_ok: bool
    supply_volts: float                      # NaN if the rail was not read (power-off readings only)
    consistent_faults: Tuple[str, ...] = ()
    open_faults: Tuple[str, ...] = ()        # inconclusive: detectable faults the readings do not exclude
    #: Readings the design cannot give: (probe text, reading, the range the design allows).
    deviations: Tuple[Tuple[str, float, Tuple[float, float]], ...] = ()
    #: Did every power-off resistance reading agree with the design? None if none was taken.
    parts_check_out: Optional[bool] = None
    notes: Tuple[str, ...] = ()

    @property
    def reopens_d1(self) -> bool:
        """
        A model question, and only then: nothing listed fits, and the parts have not been shown wrong.
        A resistance that reads off says the board is wrong, not the model — fix it first.
        """
        return self.status == "unexplained" and self.parts_check_out is not False

    def summary(self) -> str:
        parts = []
        if not self.supply_ok:
            parts.append(f"the rail reads {self.supply_volts:.3f} V, outside the design's range")
        if self.status == "as_designed":
            parts.append("consistent with the design; every detectable listed fault is excluded")
        elif self.status == "inconclusive":
            parts.append("consistent with the design, but these listed faults are not yet excluded: "
                         + ", ".join(self.open_faults))
        elif self.status == "fault":
            parts.append("does not fit the design; fits: " + ", ".join(self.consistent_faults))
        else:
            off = "; ".join(f"{k} reads {r:,.4g} where the design gives {lo:,.4g}…{hi:,.4g}"
                            for k, r, (lo, hi) in self.deviations)
            if self.parts_check_out is False:
                parts.append("no listed fault fits, and a part reads off — the board, not the model: " + off)
            elif self.parts_check_out:
                parts.append("every resistance agrees with the design and the voltages still do not — a model "
                             "question, reopens D1: " + off)
            else:
                parts.append("no listed fault fits — measure each part's resistance before treating this as a model "
                             "question (a part under 1.5× off is not listed); if they are right it reopens D1: " + off)
        return "; ".join(parts + list(self.notes))


class Analysis:
    """The correct build and every listed fault, read through every reading a meter can take."""

    def __init__(self, model: BuildModel, meter: Meter = Meter(), faults: Optional[Sequence[Fault]] = None,
                 kinds: Sequence[str] = ("v", "r")) -> None:
        self.model, self.meter, self.kinds = model, meter, tuple(kinds)
        self.physical = frozenset(model.parts)
        self.faults = list(enumerate_faults(model) if faults is None else faults)
        self.h0 = Hypothesis("as-designed", "built as designed", model.netlist, dict(model.boxes),
                             _Struct(model.netlist, model.supply_source, model.follow), None, self.physical)
        self.hyps: Dict[str, Hypothesis] = {self.h0.id: self.h0}
        for f in self.faults:
            if f.dc_equivalent:
                continue
            self.hyps[f.id] = Hypothesis(f.id, f.text, f.netlist, f.boxes,
                                         _Struct(f.netlist, model.supply_source, model.follow), f, self.physical)
        self.probes = model.all_probes(self.kinds)
        # Without a diode every reading is proportional to the rail, provided every source follows it.
        self.scales = all(e.name == model.supply_source or e.name in model.follow
                          for e in model.netlist.elements if e.kind == "V")
        self._cache: Dict[Tuple, Tuple[float, float]] = {}
        lo, hi = model.supply_range
        self.supply_points = (lo, (lo + hi) / 2, hi)
        self._sep: Optional[Dict[str, FrozenSet[str]]] = None
        self._pairs: Optional[Dict[Tuple[str, str], FrozenSet[str]]] = None

    # ── ranges ──────────────────────────────────────────────────────────

    def _loads(self, probe: Probe) -> Tuple[Tuple[str, Optional[str], Fraction], ...]:
        return ((probe.a, probe.b, Fraction(self.meter.input_ohm)),)

    def _reading(self, hyp: Hypothesis, probe: Probe, rvals, supply: Fraction, is_value=None) -> float:
        v = hyp.struct.dc(rvals, supply, self._loads(probe), is_value)
        return v[probe.a] - (v[probe.b] if probe.b is not None else 0.0)

    def interval(self, hid: str, probe: Probe, s_lo: float = 0.0, s_hi: float = 0.0) -> Tuple[float, float]:
        """
        The reading's range with every part in its box. For a voltage, the rail may be anywhere in
        [s_lo, s_hi]; a power-off resistance does not depend on it, and an overload is ∞.
        """
        hyp = self.hyps[hid]
        if probe.kind == "r":
            key = (hid, probe.key)
            if key not in self._cache:
                rn = hyp.rnet
                names = [n for n, (lo, hi) in hyp.boxes.items() if lo != hi and n in rn.names]
                ends = [(hyp.boxes[n][0], hyp.boxes[n][1]) for n in names]
                vals = [self.meter.observe_ohm(rn.rab(dict(zip(names, combo)), probe.a, probe.b))
                        for combo in itertools.product(*ends)]
                self._cache[key] = (min(vals), max(vals))
            return self._cache[key]
        nonlinear = hyp.has_diode or not self.scales
        if nonlinear:
            # Outward to 10 mV, so a diagnosis for every measured rail does not recompute the box:
            # a wider rail box only widens the range, which can cost detection but never soundness.
            s_lo, s_hi = math.floor(s_lo * 100) / 100, math.ceil(s_hi * 100) / 100
            key = (hid, probe.key, round(s_lo, 4), round(s_hi, 4))
        else:
            key = (hid, probe.key)
        if key not in self._cache:
            names = [n for n, (lo, hi) in hyp.boxes.items() if lo != hi and any(r[0] == n for r in hyp.struct.res)]
            ends = [(hyp.boxes[n][0], hyp.boxes[n][1]) for n in names]
            supply_pts = (_fr(s_lo), _fr(s_hi)) if nonlinear else (Fraction(1),)
            is_pts: Tuple[Optional[float], ...] = (None,)
            if nonlinear and hyp.struct.diodes:
                d = hyp.struct.diodes[0][0]
                is_pts = tuple(self.model.diode_is.get(d, (None, None))) if d in self.model.diode_is else (None,)
            vals: List[float] = []
            for combo in itertools.product(*ends):
                rvals = dict(zip(names, combo))
                for s in supply_pts:
                    for is_ in is_pts:
                        vals.append(self._reading(hyp, probe, rvals, s, is_))
            self._cache[key] = (min(vals), max(vals))
        lo, hi = self._cache[key]
        if nonlinear:
            return lo, hi
        c = (lo * s_lo, lo * s_hi, hi * s_lo, hi * s_hi)         # all sources scale with the rail
        return min(c), max(c)

    def _supply_box(self, volts: float) -> Tuple[float, float]:
        u = self.meter.uncertainty(volts)
        return volts - u, volts + u

    # ── separation: the guarantee ───────────────────────────────────────

    # The meter's error is not a constant: it grows with the reading, and it jumps where the range
    # steps up (a 2 V range has 1 mV digits, a 20 V range 10 mV). So "far enough apart" is decided over
    # the whole span of the fault's readings, not at one point of it.

    def _unc(self, kind: str):
        return self.meter.r_uncertainty if kind == "r" else self.meter.uncertainty

    def _breaks(self, kind: str) -> Tuple[float, ...]:
        return tuple(fs for fs, _ in (self.meter.r_ranges if kind == "r" else self.meter.ranges))

    def _edge_points(self, kind: str, lo: float, hi: float) -> List[float]:
        pts = []
        for f in self._breaks(kind):
            for sign in (1.0, -1.0):
                for eps in (1 - 1e-9, 1 + 1e-9):
                    x = sign * f * eps
                    if lo <= x <= hi:
                        pts.append(x)
        return pts

    def _worst(self, lo: float, hi: float, kind: str, upward: bool) -> float:
        """
        Over every true value in [lo, hi] and every reading the meter may then show, the extreme of
        r − unc(r) (the smallest, `upward` False) or r + unc(r) (the largest, `upward` True): how close
        to the design the fault can look, as the design's own consistency test will see it.
        """
        unc = self._unc(kind)
        values = {lo, hi, *self._edge_points(kind, lo, hi)}
        best = -math.inf if upward else math.inf
        for v in values:
            u = unc(v)
            readings = {v - u, v + u, v, *self._edge_points(kind, v - u, v + u)}
            for r in readings:
                x = r + unc(r) if upward else r - unc(r)
                best = max(best, x) if upward else min(best, x)
        return best

    def _separate(self, a: Tuple[float, float], b: Tuple[float, float], kind: str) -> bool:
        """
        True when no reading the faulty build can give is one the design can give: the fault's readings
        all lie above the design's range by more than the meter can blur, or all below.
        """
        a0, a1 = a
        b0, b1 = b
        if b0 > a1:                                    # the fault reads above the design
            if math.isinf(b0):
                return True                            # always OL, and the design is not
            top = min(b1, self.meter.overload_ohm) if kind == "r" else b1
            return self._worst(b0, top, kind, upward=False) > a1
        if b1 < a0:                                    # the fault reads below the design
            return self._worst(b0, b1, kind, upward=True) < a0
        return False

    def gap(self, fault_id: str, probe: Probe, volts: float = 0.0) -> Tuple[float, float]:
        """
        For a report: (distance between the two ranges, the blur the meter puts on the nearer edges).
        `separated` is the proof; this is the nearest-miss figure printed beside a blind spot.
        """
        if probe.kind == "r":
            a, b = self.interval("as-designed", probe), self.interval(fault_id, probe)
        else:
            s_lo, s_hi = self._supply_box(volts)
            a = self.interval("as-designed", probe, s_lo, s_hi)
            b = self.interval(fault_id, probe, s_lo, s_hi)
        gap = max(_sub(b[0], a[1]), _sub(a[0], b[1]), 0.0)
        unc = self._unc(probe.kind)
        near_a = a[1] if b[0] > a[1] else a[0]
        near_b = b[0] if b[0] > a[1] else b[1]
        blur = sum(unc(x) for x in (near_a, near_b) if not math.isinf(x))
        return gap, blur

    def separated(self, fault_id: str, probe: Probe) -> bool:
        """
        True when this reading tells the fault from the design across the design's rail range: decided at its low,
        middle and high ends — and a test re-checks every claimed separation at 41 rails, because the meter's range
        steps could in principle open a gap between three points. A power-off resistance does not depend on the rail.
        """
        if probe.kind == "r":
            return self._separate(self.interval("as-designed", probe), self.interval(fault_id, probe), "r")
        for volts in self.supply_points:
            s_lo, s_hi = self._supply_box(volts)
            if not self._separate(self.interval("as-designed", probe, s_lo, s_hi),
                                  self.interval(fault_id, probe, s_lo, s_hi), "v"):
                return False
        return True

    def detecting(self) -> Dict[str, FrozenSet[str]]:
        """fault id → the probe keys that separate it (empty: a blind spot)."""
        if self._sep is None:
            self._sep = {f.id: frozenset(p.key for p in self.probes if self.separated(f.id, p))
                         for f in self.faults if not f.dc_equivalent}
        return self._sep

    def blind_spots(self) -> List[Tuple[Fault, str]]:
        out = []
        sep = self.detecting()
        for f in self.faults:
            if f.dc_equivalent:
                why = ("a capacitor is open to a multimeter: no reading depends on its value — check it with a "
                       "capacitance range or the rc_timer sketch" if f.elements and f.elements[0].startswith("C_")
                       else "identical to the design for a multimeter")
                out.append((f, why))
            elif not sep[f.id]:
                best = None
                for p in self.probes:
                    for volts in (self.supply_points if p.kind == "v" else (0.0,)):
                        g, need = self.gap(f.id, p, volts)
                        if math.isinf(g):
                            continue
                        if best is None or g - need > best[0]:
                            best = (g - need, p, g, need)
                why = "no reading separates it from the design"
                if best:
                    unit, scale = ("Ω", 1.0) if best[1].kind == "r" else ("mV", 1000.0)
                    why += (f"; nearest is {best[1].text()}, {best[2] * scale:.1f} {unit} apart, "
                            f"against {best[3] * scale:.1f} {unit} of meter blur on the nearer edges")
                out.append((f, why))
        return out

    def separated_pair(self, fid: str, gid: str, probe: Probe) -> bool:
        """True when this reading tells one listed fault from another across the rail range (as `separated`)."""
        if probe.kind == "r":
            return self._separate(self.interval(fid, probe), self.interval(gid, probe), "r")
        for volts in self.supply_points:
            s_lo, s_hi = self._supply_box(volts)
            if not self._separate(self.interval(fid, probe, s_lo, s_hi), self.interval(gid, probe, s_lo, s_hi), "v"):
                return False
        return True

    def _tells_apart(self) -> Dict[Tuple[str, str], FrozenSet[str]]:
        """Each pair of listed faults → the readings that tell them apart (absent: nothing does)."""
        if self._pairs is None:
            ids = [f.id for f in self.faults if not f.dc_equivalent]
            out: Dict[Tuple[str, str], FrozenSet[str]] = {}
            for i, f in enumerate(ids):
                for g in ids[i + 1:]:
                    ks = frozenset(p.key for p in self.probes
                                   if self.separated_pair(f, g, p) or self.separated_pair(g, f, p))
                    if ks:
                        out[(f, g)] = ks
            self._pairs = out
        return self._pairs

    def plan(self, identify: bool = False) -> Tuple[Probe, ...]:
        """
        A smallest set of readings that detects every detectable fault. With `identify`, one that also
        tells apart every pair of listed faults that some reading can tell apart — so a verdict names the
        fault, not a handful of suspects. Among the smallest, the one with the most power-off readings
        (they are safe, and find shorts before power is applied). Exact up to 26 candidate readings,
        greedy beyond.
        """
        sep = self.detecting()
        constraints: List[FrozenSet[str]] = [ps for ps in sep.values() if ps]
        if identify:
            constraints += list(self._tells_apart().values())
        if not constraints:
            return ()
        by_key = {p.key: p for p in self.probes}
        universe = sorted({k for c in constraints for k in c}, key=lambda k: (not k.startswith("r:"), k))
        bit = {k: 1 << i for i, k in enumerate(universe)}
        masks = list({sum(bit[k] for k in c) for c in constraints})       # a constraint is met by any of its readings
        best: Optional[Tuple[str, ...]] = None
        if len(universe) <= 26:
            for size in range(1, len(universe) + 1):
                found = []
                for combo in itertools.combinations(universe, size):
                    m = sum(bit[k] for k in combo)
                    if all(m & c for c in masks):
                        found.append(combo)
                if found:
                    best = max(found, key=lambda c: sum(1 for k in c if k.startswith("r:")))
                    break
        if best is None:                                    # greedy
            left, chosen = list(masks), []
            while left:
                k = max(universe, key=lambda k: sum(1 for c in left if c & bit[k]))
                chosen.append(k)
                left = [c for c in left if not c & bit[k]]
            best = tuple(chosen)
        ordered = sorted(best, key=lambda k: (not k.startswith("r:"), k))
        return tuple(by_key[k] for k in ordered)

    def min_detectable_factor(self, element: str, side: str = "high",
                              factors: Sequence[float] = (1.05, 1.1, 1.2, 1.3, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0),
                              probes: Optional[Sequence[Probe]] = None) -> Optional[float]:
        """
        How far off one resistor must be before the readings can tell. The smallest factor f such that
        the part at f× its value or more (side "high"), or at 1/f× or less ("low"), is separated from the
        design by one of `probes` (default: the plan) at every rail in the design range; None if even 20×
        is not. A part closer than this is inside what this meter sees through tolerance.
        """
        lo0, hi0 = self.model.boxes[element]
        nominal = (lo0 + hi0) / 2
        use = tuple(probes) if probes is not None else (self.plan() or self.probes)
        for f in factors:
            fr = Fraction(str(f))
            box = (nominal * fr, nominal * 20) if side == "high" else (nominal / 20, nominal / fr)
            hid = f"~{element}:{side}:{f}"
            if hid not in self.hyps:
                boxes = dict(self.model.boxes)
                boxes[element] = box
                self.hyps[hid] = Hypothesis(hid, f"{element} {side} by {f}×", self.model.netlist, boxes,
                                            self.h0.struct, None, self.physical)
            if any(self.separated(hid, p) for p in use):
                return float(f)
        return None

    # ── the verdict ─────────────────────────────────────────────────────

    def diagnose(self, readings: Mapping[str, float]) -> Verdict:
        """
        Readings keyed by probe key: a node (`vout`), a pair (`a-b`), or a resistance (`r:a,b`, in ohms,
        ∞ for OL). The rail's own node must be among them when any voltage is.
        """
        sn = self.model.supply_node
        by_key = {p.key: p for p in self.probes}
        has_voltage = any(by_key[k].kind == "v" for k in readings if k != sn)
        if sn in readings:
            vs = float(readings[sn])
            s_lo, s_hi = self._supply_box(vs)
            lo, hi = self.model.supply_range
            supply_ok = s_lo <= hi and lo <= s_hi
        elif has_voltage:
            raise KeyError(f"read the supply first: no reading for {sn}")
        else:
            vs, (s_lo, s_hi), supply_ok = math.nan, self.model.supply_range, True

        def consistent(hid: str) -> bool:
            for key, r in readings.items():
                if key == sn:
                    continue
                p = by_key[key]
                if p.kind == "r":
                    a, b = self.interval(hid, p)
                    if math.isinf(r):
                        ok = math.isinf(b)
                    else:
                        u = self.meter.r_uncertainty(r)
                        ok = not (r + u < a or r - u > b)
                else:
                    a, b = self.interval(hid, p, s_lo, s_hi)
                    u = self.meter.uncertainty(r)
                    ok = not (r + u < a or r - u > b)
                if not ok:
                    return False
            return True

        h0 = consistent("as-designed")
        sep = self.detecting()
        fits = tuple(f.id for f in self.faults if not f.dc_equivalent and consistent(f.id))
        if h0:
            open_ = tuple(fid for fid in fits if sep.get(fid))
            parts_ok = True if any(by_key[k].kind == "r" for k in readings if k != sn) else None
            if open_:
                return Verdict("inconclusive", supply_ok, vs, (), open_, (), parts_ok)
            return Verdict("as_designed", supply_ok, vs, parts_check_out=parts_ok)
        deviations, r_off, r_read = [], False, False
        for key, r in readings.items():
            if key == sn:
                continue
            p = by_key[key]
            if p.kind == "r":
                r_read = True
                a, b = self.interval("as-designed", p)
                u = 0.0 if math.isinf(r) else self.meter.r_uncertainty(r)
                bad = (not math.isinf(b)) if math.isinf(r) else (r + u < a or r - u > b)
            else:
                a, b = self.interval("as-designed", p, s_lo, s_hi)
                u = self.meter.uncertainty(r)
                bad = r + u < a or r - u > b
            if bad:
                deviations.append((p.text(), r, (a, b)))
                r_off = r_off or p.kind == "r"
        parts_ok = (not r_off) if r_read else None
        if fits:
            return Verdict("fault", supply_ok, vs, fits, (), tuple(deviations), parts_ok)
        return Verdict("unexplained", supply_ok, vs, (), (), tuple(deviations), parts_ok)

    # ── the sheet ───────────────────────────────────────────────────────

    def expected(self, probe: Probe, volts: Optional[float] = None) -> Tuple[float, float]:
        if probe.kind == "r":
            return self.interval("as-designed", probe)
        v = volts if volts is not None else sum(self.model.supply_range) / 2
        s_lo, s_hi = self._supply_box(v)
        return self.interval("as-designed", probe, s_lo, s_hi)

    def report(self) -> str:
        sep = self.detecting()
        plan = self.plan()
        m = self.meter
        lines = [f"Build check — {len(self.faults)} listed faults, {len(self.probes)} possible readings; meter "
                 f"±({m.gain * 100:g} % + {m.digits} digits) on volts, ±({m.r_gain * 100:g} % + {m.r_digits} digits) "
                 f"on ohms, {m.input_ohm / 1e6:g} MΩ input", ""]
        r_plan = [p for p in plan if p.kind == "r"]
        v_plan = [p for p in plan if p.kind == "v"]
        if r_plan:
            lines.append("1. Power off. Measure the resistance between:")
            for p in r_plan:
                lo, hi = self.expected(p)
                hi_t = "OL" if math.isinf(hi) else f"{hi:,.1f} Ω"
                lines.append(f"     {p.text():34s} expect {lo:,.1f} Ω … {hi_t}")
        if v_plan:
            if self.model.conditions:
                lines.append("   Conditions: " + "; ".join(self.model.conditions))
            lines.append(f"{2 if r_plan else 1}. Power on. Read the rail at {self.model.supply_node} "
                         f"(design range {self.model.supply_range[0]:.2f}–{self.model.supply_range[1]:.2f} V), then:")
            for p in v_plan:
                lo, hi = self.expected(p)
                lines.append(f"     {p.text():34s} expect {lo:9.4f} … {hi:9.4f} V at the middle of the range")
        if not plan:
            lines.append("No reading separates any fault from the design.")
        det = [f for f in self.faults if not f.dc_equivalent and sep[f.id]]
        lines.append(f"\nDetected by the plan: {len(det)} of {len(self.faults)}.")
        blind = self.blind_spots()
        lines.append(f"Blind spots: {len(blind)}")
        for f, why in blind:
            lines.append(f"  {f.id:28s} {f.text} — {why}")
        return "\n".join(lines)
