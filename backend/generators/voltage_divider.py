"""
Resistive voltage divider — Stage 3, the Phase 1 TPL_005 template on the contract.

    VIN ── R1 ──┬── VOUT ── (optional load R_L)
                R2
    GND ────────┘

`predict()` is closed form over the resistor tolerance box:

    V_out = V_in · R2' / (R1 + R2'),   R2' = R2 ∥ R_L

V_out rises with R2 (and R_L) and falls with R1, so the band edges are two
opposite corners of the box — `monotone_corners`, exact, G1. Supply current and
output impedance are monotone too. Resistor dissipation is *not* monotone in
R1 (it peaks where R1 = R2'), so its bound comes from interval arithmetic
instead — sound but not tight, which is a different grade (G2), and its claim
says so.

Selection is deterministic: R2 walks the E96 values around the ideal, R1 is
snapped to E96 for each. Among pairs within half a percent of the target —
closer than 1% parts can hold anyway — the one nearest the requested bleed
current wins; if none is that close, the most accurate does. At small ratios
the E96 steps are coarse, and that fallback is what the current then follows.
`constraints.pinned` fixes R1 and/or R2, honoured or refused by name.

The load is part of the requirement (`constraints.load_ohm`), not part of the
board: it appears in `predict()` and, in CI, as a probe the grid adapter
attaches — never in the product netlist or the BOM.
"""

from __future__ import annotations

import math
from typing import Dict, FrozenSet, Mapping, Optional, Sequence, Tuple

from core.ir_schema import (
    ApplicationClass,
    CircuitIR,
    Component,
    ComponentType,
    Connection,
    Node,
    SignalType,
    SimulationAnalysis,
    SimulationSpec,
    ValidationRule,
)
from generators.common import (
    RESISTOR_POWER_W,
    RESISTOR_TOLERANCE,
    RESISTOR_VMAX,
    Unreadable,
    e96_values,
    pinned_number,
    read_number,
    read_pins,
    resistor_part,
    snap_to_e96,
    value_string,
    worst_corners,
)
from generators.netlist.spice import _parse_ohms
from generators.protocol import (
    ClaimScope,
    EnvelopeDecision,
    GridSpec,
    IntentLike,
    Interval,
    PortContract,
    Prediction,
)

NAME = "voltage_divider"
VERSION = "0.1.0"
FUNCTION = "voltage_divider"

MAX_SUPPLY_V = RESISTOR_VMAX
MIN_RATIO = 0.01
MAX_RATIO = 0.99
#: Default bleed current. Low enough not to waste a battery, high enough that a
#: typical ADC input (tens of kΩ) is a small load.
DEFAULT_BLEED_MA = 0.5
MIN_BLEED_MA = 0.01
MAX_BLEED_MA = 10.0
MIN_OHMS = 100.0
MAX_OHMS = 1_000_000.0
PINNABLE = ("R1", "R2")
#: Half the resistor tolerance: inside it, nominal accuracy is not the thing
#: that decides how close the built divider lands.
ACCURACY_BUDGET_PCT = 0.5


def divider_vout(vin: float, r1: float, r2: float, load: Optional[float]) -> float:
    r2_eff = r2 if load is None else r2 * load / (r2 + load)
    return vin * r2_eff / (r1 + r2_eff)


class _Spec:
    __slots__ = ("vout", "supply", "tolerance", "bleed", "load", "pins")

    def __init__(self, vout, supply, tolerance, bleed, load, pins):
        self.vout, self.supply, self.tolerance = vout, supply, tolerance
        self.bleed, self.load, self.pins = bleed, load, pins


class _Selection:
    __slots__ = ("r1", "r2", "vout", "error_pct")

    def __init__(self, r1: float, r2: float, spec: _Spec):
        self.r1, self.r2 = r1, r2
        self.vout = divider_vout(spec.supply, r1, r2, spec.load)
        self.error_pct = abs(self.vout - spec.vout) / spec.vout * 100.0


def _read(intent: IntentLike) -> _Spec:
    vout = read_number(intent, "targets", "vout_v", None, allow_zero=False,
                       what="an output voltage in volts")
    supply = read_number(intent, "constraints", "supply_v", None, allow_zero=False,
                         what="an input rail in volts")
    tolerance = read_number(intent, "targets", "tolerance_pct", 5.0, allow_zero=False,
                            what="a tolerance in percent")
    bleed = read_number(intent, "constraints", "divider_current_ma", DEFAULT_BLEED_MA,
                        allow_zero=False, what="a divider current in mA")
    load = read_number(intent, "constraints", "load_ohm", None, allow_zero=False,
                       what="a load resistance in ohms")
    raw_pins = read_pins(intent, PINNABLE)
    pins: Dict[str, float] = {}
    for part, raw in raw_pins.items():
        ohms = pinned_number(raw, _parse_ohms)
        if ohms is None:
            raise Unreadable(f"constraints.pinned.{part}={raw!r} is not a resistance "
                             f"this system can read (e.g. '4.7k', '4k7', 4700)")
        if not (MIN_OHMS <= ohms <= MAX_OHMS):
            raise Unreadable(f"constraints.pinned.{part}={ohms:g}Ω is outside "
                             f"{MIN_OHMS:g}–{MAX_OHMS:g}Ω")
        pins[part] = ohms
    return _Spec(vout, supply, tolerance, bleed, load, pins)


def select(spec: _Spec) -> Optional[_Selection]:
    """Deterministic E96 pair. None if nothing lands inside the value window."""
    if "R1" in spec.pins and "R2" in spec.pins:
        return _Selection(spec.pins["R1"], spec.pins["R2"], spec)

    ratio = spec.vout / spec.supply
    total = spec.supply / (spec.bleed / 1000.0)
    best: Optional[_Selection] = None
    best_key: Optional[Tuple[float, float]] = None

    if "R1" in spec.pins:
        candidates = [(spec.pins["R1"], r2) for r2 in e96_values(MIN_OHMS, MAX_OHMS)]
    else:
        ideal_r2 = total * ratio
        r2s = [spec.pins["R2"]] if "R2" in spec.pins else e96_values(
            max(MIN_OHMS, ideal_r2 / 3.0), min(MAX_OHMS, ideal_r2 * 3.0)
        )
        candidates = []
        for r2 in r2s:
            r2_eff = r2 if spec.load is None else r2 * spec.load / (r2 + spec.load)
            ideal_r1 = r2_eff * (spec.supply - spec.vout) / spec.vout
            if ideal_r1 <= 0:
                continue
            r1 = snap_to_e96(ideal_r1)
            if MIN_OHMS <= r1 <= MAX_OHMS:
                candidates.append((r1, r2))

    # With 1% parts, a pair within ACCURACY_BUDGET_PCT of the target is as
    # good as any other — chasing the last 0.01% of ratio would drag the bleed
    # current far from what was asked. So: among pairs inside the budget, the
    # one closest to the requested current; if none is, the most accurate.
    for r1, r2 in candidates:
        sel = _Selection(r1, r2, spec)
        current = spec.supply / (r1 + (r2 if spec.load is None else r2 * spec.load / (r2 + spec.load)))
        distance = abs(math.log(current * 1000.0 / spec.bleed))
        if sel.error_pct <= ACCURACY_BUDGET_PCT:
            key = (0.0, distance, sel.error_pct)
        else:
            key = (1.0, sel.error_pct, distance)
        if best_key is None or key < best_key:
            best, best_key = sel, key
    return best


class VoltageDividerGenerator:
    """Two-resistor divider. Implements `generators.protocol.Generator`."""

    name = NAME
    version = VERSION
    function = FUNCTION

    #: X8 accounting: unimplemented rules this topology cannot violate.
    not_applicable_rules = {
        "pullup_on_open_drain": "no open-drain line in a resistive divider",
        "power_supply_adequate": "the divider's supply current is a claim of its own "
                                 "(divider.supply_current); there is no rail budget to check",
    }

    # ── envelope() ────────────────────────────────────────────────────────

    def envelope(self, intent: IntentLike) -> EnvelopeDecision:
        function = (intent.requirements or {}).get("function")
        if function != FUNCTION:
            return EnvelopeDecision.refuse(
                f"function={function!r} is not voltage_divider — this generator builds "
                f"two-resistor dividers only"
            )
        try:
            spec = _read(intent)
        except Unreadable as exc:
            return EnvelopeDecision.refuse(str(exc))
        if spec.vout is None:
            return EnvelopeDecision.refuse(
                "targets.vout_v is missing — a divider without an output voltage is "
                "underdetermined, not out of envelope"
            )
        if spec.supply is None:
            return EnvelopeDecision.refuse(
                "constraints.supply_v is missing — a divider's ratio means nothing "
                "without the input rail"
            )
        if spec.supply > MAX_SUPPLY_V:
            return EnvelopeDecision.refuse(
                f"supply_v={spec.supply:g} exceeds the {MAX_SUPPLY_V:g} V rating of the "
                f"0402 resistors this generator places"
            )
        ratio = spec.vout / spec.supply
        if not (MIN_RATIO <= ratio <= MAX_RATIO):
            return EnvelopeDecision.refuse(
                f"vout_v={spec.vout:g} from supply_v={spec.supply:g} is a ratio of "
                f"{ratio:.3f}, outside {MIN_RATIO:g}–{MAX_RATIO:g} — a divider cannot "
                f"step up, and near 0 or 1 one resistor does all the work"
            )
        if not (MIN_BLEED_MA <= spec.bleed <= MAX_BLEED_MA):
            return EnvelopeDecision.refuse(
                f"divider_current_ma={spec.bleed:g} outside {MIN_BLEED_MA:g}–{MAX_BLEED_MA:g} mA"
            )

        sel = select(spec)
        if sel is None:
            return EnvelopeDecision.refuse(
                f"no E96 pair within {MIN_OHMS:g}–{MAX_OHMS:g}Ω gives vout_v={spec.vout:g} "
                f"from supply_v={spec.supply:g}"
            )
        if sel.error_pct > spec.tolerance:
            pair = "pinned pair" if spec.pins else "nearest E96 pair"
            return EnvelopeDecision.refuse(
                f"{pair} R1={sel.r1:g}Ω, R2={sel.r2:g}Ω gives {sel.vout:.4g} V against "
                f"vout_v={spec.vout:g}, a {sel.error_pct:.2f}% error that exceeds the "
                f"requested tolerance_pct={spec.tolerance:g}"
            )
        power = self._power_bounds(spec, sel)
        for part, (_, hi) in power.items():
            if hi > RESISTOR_POWER_W:
                return EnvelopeDecision.refuse(
                    f"{part} could dissipate up to {hi * 1000:.1f} mW, above the "
                    f"{RESISTOR_POWER_W * 1000:g} mW rating of an 0402 resistor — raise the "
                    f"resistance or lower divider_current_ma"
                )
        return EnvelopeDecision.accept(self._ports(spec, sel))

    def _ports(self, spec: _Spec, sel: _Selection) -> Sequence[PortContract]:
        z_out = self._box(sel)
        r1b, r2b = z_out
        zo = lambda a, b: a * b / (a + b)  # noqa: E731
        lo, hi = worst_corners(zo, [(r1b.lo, r1b.hi), (r2b.lo, r2b.hi)])
        return (
            PortContract(
                name="VIN", direction="power",
                voltage_range_v=Interval.at(spec.supply, "V"),
                current_draw_a=self._current_band(spec, sel, scale=1.0),
            ),
            PortContract(
                name="VOUT", direction="output",
                impedance_ohm=Interval(lo=lo, hi=hi, nominal=zo(sel.r1, sel.r2), units="ohm"),
                voltage_range_v=self._vout_band(spec, sel),
            ),
            PortContract(name="GND", direction="ground"),
        )

    # ── predict() ─────────────────────────────────────────────────────────

    def _box(self, sel: _Selection, box: Optional[Mapping[str, Interval]] = None):
        r1 = Interval(lo=sel.r1 * (1 - RESISTOR_TOLERANCE), hi=sel.r1 * (1 + RESISTOR_TOLERANCE),
                      nominal=sel.r1, units="ohm")
        r2 = Interval(lo=sel.r2 * (1 - RESISTOR_TOLERANCE), hi=sel.r2 * (1 + RESISTOR_TOLERANCE),
                      nominal=sel.r2, units="ohm")
        if box:
            unknown = set(box) - {"R1", "R2"}
            if unknown:
                raise ValueError(f"predict() box names unknown parameters {sorted(unknown)}; "
                                 f"this generator takes ['R1', 'R2']")
            r1, r2 = box.get("R1", r1), box.get("R2", r2)
        return r1, r2

    def _vout_band(self, spec, sel, box=None) -> Interval:
        r1, r2 = self._box(sel, box)
        f = lambda a, b: divider_vout(spec.supply, a, b, spec.load)  # noqa: E731
        lo, hi = worst_corners(f, [(r1.lo, r1.hi), (r2.lo, r2.hi)])
        return Interval(lo=lo, hi=hi, nominal=f(r1.nominal, r2.nominal), units="V")

    def _current_band(self, spec, sel, box=None, scale=1000.0) -> Interval:
        r1, r2 = self._box(sel, box)

        def current(a, b):
            b_eff = b if spec.load is None else b * spec.load / (b + spec.load)
            return spec.supply / (a + b_eff) * scale

        lo, hi = worst_corners(current, [(r1.lo, r1.hi), (r2.lo, r2.hi)])
        return Interval(lo=lo, hi=hi, nominal=current(r1.nominal, r2.nominal),
                        units="mA" if scale == 1000.0 else "A")

    def _power_bounds(self, spec, sel, box=None) -> Dict[str, Tuple[float, float]]:
        """
        Interval-arithmetic bounds on each resistor's dissipation, in watts.

        P_R1 = V_in²·R1/(R1+R2')² peaks where R1 = R2', so it is not monotone
        and corner evaluation would not bound it. Outward interval arithmetic
        does — numerator at its largest, denominator at its smallest — which is
        sound and loose: a `sound_enclosure`, G2.
        """
        r1, r2 = self._box(sel, box)
        load = spec.load

        def eff(lo_or_hi):
            return lo_or_hi if load is None else lo_or_hi * load / (lo_or_hi + load)

        r2e_lo, r2e_hi = eff(r2.lo), eff(r2.hi)
        v2 = spec.supply ** 2
        p1_hi = v2 * r1.hi / (r1.lo + r2e_lo) ** 2
        p1_lo = v2 * r1.lo / (r1.hi + r2e_hi) ** 2
        # R2 carries V_out²/R2; V_out ≤ its band top, R2 ≥ its bottom.
        vband = self._vout_band(spec, sel, box)
        p2_hi = vband.hi ** 2 / r2.lo
        p2_lo = vband.lo ** 2 / r2.hi
        return {"R1": (p1_lo, p1_hi), "R2": (p2_lo, p2_hi)}

    def predict(self, intent: IntentLike, box: Optional[Mapping[str, Interval]] = None) -> Prediction:
        decision = self.envelope(intent)
        if not decision.accepted:
            raise ValueError(f"predict() called on a refused intent: {decision.reason}")
        spec = _read(intent)
        sel = select(spec)
        r1, r2 = self._box(sel, box)
        zo = lambda a, b: a * b / (a + b)  # noqa: E731
        z_lo, z_hi = worst_corners(zo, [(r1.lo, r1.hi), (r2.lo, r2.hi)])
        power = self._power_bounds(spec, sel, box)
        nominal_i = spec.supply / (sel.r1 + (sel.r2 if spec.load is None else
                                              sel.r2 * spec.load / (sel.r2 + spec.load)))
        p1_nom = nominal_i ** 2 * sel.r1
        p2_nom = divider_vout(spec.supply, sel.r1, sel.r2, spec.load) ** 2 / sel.r2
        return Prediction(
            quantities={
                "vout_v": self._vout_band(spec, sel, box),
                "supply_current_ma": self._current_band(spec, sel, box),
                "output_impedance_ohm": Interval(lo=z_lo, hi=z_hi, nominal=zo(r1.nominal, r2.nominal), units="ohm"),
                "r1_power_mw": Interval(lo=min(power["R1"][0], p1_nom) * 1000, hi=max(power["R1"][1], p1_nom) * 1000,
                                        nominal=p1_nom * 1000, units="mW"),
                "r2_power_mw": Interval(lo=min(power["R2"][0], p2_nom) * 1000, hi=max(power["R2"][1], p2_nom) * 1000,
                                        nominal=p2_nom * 1000, units="mW"),
                "resistance_r1_ohm": r1,
                "resistance_r2_ohm": r2,
            },
            scope=ClaimScope(
                parameters="nominal" if (r1.is_point and r2.is_point) else "tolerance_box",
                model="mna_ideal", horizon="steady_state",
            ),
            method="monotone_corners",
        )

    # ── claims() ──────────────────────────────────────────────────────────

    def claims(self, intent: IntentLike):
        from validation.claims import graded

        spec = _read(intent)
        sel = select(spec)
        pred = self.predict(intent)
        q = pred.quantities
        box = pred.scope
        nominal = ClaimScope(parameters="nominal", model="mna_ideal")
        load = "unloaded" if spec.load is None else f"into R_L={spec.load:g}Ω"
        vout, cur = q["vout_v"], q["supply_current_ma"]
        return [
            graded(
                "divider.vout_nominal",
                f"V_out at nominal parts is within ±{spec.tolerance:g}% of {spec.vout:g} V ({load})",
                sel.error_pct <= spec.tolerance, "closed_form", nominal,
                detail=f"{vout.nominal:.4g} V, {sel.error_pct:.2f}% from target",
            ),
            graded(
                "divider.vout_band",
                f"V_out lies in [{vout.lo:.4g}, {vout.hi:.4g}] V for every R1, R2 within 1% ({load})",
                True, "monotone_corners", box,
                detail=f"band width {100 * (vout.hi - vout.lo) / vout.nominal:.2f}% of nominal",
            ),
            graded(
                "divider.supply_current",
                f"the divider draws {cur.lo:.4g}–{cur.hi:.4g} mA from the {spec.supply:g} V rail",
                True, "monotone_corners", box,
            ),
            graded(
                "divider.resistor_dissipation",
                f"each resistor stays below its {RESISTOR_POWER_W * 1000:g} mW rating",
                max(q["r1_power_mw"].hi, q["r2_power_mw"].hi) <= RESISTOR_POWER_W * 1000,
                "sound_enclosure", box,
                detail=f"R1 ≤ {q['r1_power_mw'].hi:.3g} mW, R2 ≤ {q['r2_power_mw'].hi:.3g} mW "
                       f"(interval bound, loose by construction)",
                defeaters=("D1", "D7"),
                covers=("current_limits_ok",),
            ),
        ]

    # ── generate() ────────────────────────────────────────────────────────

    def generate(self, intent: IntentLike) -> CircuitIR:
        spec = _read(intent)
        if spec.vout is None or spec.supply is None:
            raise ValueError("generate() requires vout_v and supply_v — call envelope() first")
        sel = select(spec)
        if sel is None:
            raise ValueError("generate() called on an intent envelope() refuses")
        current_ma = spec.supply / (sel.r1 + sel.r2) * 1000.0
        load = "" if spec.load is None else f" into a {spec.load:g}Ω load"

        def reason(part: str, ohms: float, role: str) -> str:
            if part in spec.pins:
                return (f"{ohms:g}Ω, pinned by the requirement (constraints.pinned.{part}) — "
                        f"the part in hand, assumed from the same 1% series. {role}")
            return f"{ohms:g}Ω, E96 (1%). {role}"

        return CircuitIR(
            intent=f"Voltage divider: {spec.vout:g} V from {spec.supply:g} V{load}",
            application_class=ApplicationClass.HOBBY_ARDUINO,
            components=[
                Component(
                    id="R1", type=ComponentType.RESISTOR, part_number=resistor_part(sel.r1),
                    manufacturer="Yageo", package="0402", value=value_string(sel.r1),
                    supply_voltage_max=RESISTOR_VMAX, confidence=0.95,
                    justification=reason("R1", sel.r1,
                        f"Upper leg: with R2={sel.r2:g}Ω it sets V_out = {sel.vout:.4g} V "
                        f"({sel.error_pct:.2f}% from the {spec.vout:g} V asked for). Raising R1 "
                        f"lowers V_out; the pair draws {current_ma:.3g} mA from the rail."),
                ),
                Component(
                    id="R2", type=ComponentType.RESISTOR, part_number=resistor_part(sel.r2),
                    manufacturer="Yageo", package="0402", value=value_string(sel.r2),
                    supply_voltage_max=RESISTOR_VMAX, confidence=0.95,
                    justification=reason("R2", sel.r2,
                        f"Lower leg: V_out appears across it. Output impedance is "
                        f"R1∥R2 = {sel.r1 * sel.r2 / (sel.r1 + sel.r2):.4g}Ω — a load much "
                        f"smaller than that pulls V_out down."),
                ),
            ],
            nodes=[
                Node(id="VIN", voltage_nominal=spec.supply, type=SignalType.POWER),
                Node(id="VOUT", type=SignalType.ANALOG),
                Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
            ],
            connections=[
                Connection(component_id="R1", pin="A", node_id="VIN"),
                Connection(component_id="R1", pin="B", node_id="VOUT"),
                Connection(component_id="R2", pin="A", node_id="VOUT"),
                Connection(component_id="R2", pin="B", node_id="GND"),
            ],
            constraints={"supply_voltage": spec.supply, "vout_v": spec.vout},
            simulation_spec=SimulationSpec(
                analyses=[SimulationAnalysis(type="dc_op", description=f"Verify V_out ≈ {sel.vout:.4g} V")],
                expected_outputs={"VOUT": round(sel.vout, 6)},
            ),
            validation_rules=[ValidationRule.NO_FLOATING_NODES, ValidationRule.VOLTAGE_RATINGS_OK],
        )

    # ── CI grid and locality ──────────────────────────────────────────────

    def grid(self) -> GridSpec:
        return GridSpec(
            axes={"vout_v": [0.5, 1.8, 3.3], "supply_v": [5.0, 12.0, 24.0]},
            units={"vout_v": "V", "supply_v": "V"},
            sections={"vout_v": "targets", "supply_v": "constraints"},
        )

    def dependency_closure(self, requirement_path: str) -> FrozenSet[str]:
        # Every input moves the ratio or the impedance, and both parts set both.
        return frozenset({"R1", "R2"})
