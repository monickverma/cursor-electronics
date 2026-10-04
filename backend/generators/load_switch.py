"""
NPN low-side load switch — Composition M3 (`COMPOSITION_PLAN.md`,
`brain/decisions.md` [2026-10-03]).

    U1 pin ─(R_out)─ SW_CTRL ── R1 ── SW_BASE ── Q1 base
    rail ── J1 (the load) ── SW_LOAD ── Q1 collector;  Q1 emitter ── GND
    D1 across the load (anode SW_LOAD, cathode rail) when it is inductive

One block that switches a load the pin cannot drive: a buzzer first, and the
same block later a relay coil, a small motor or a pump. The load is off-board,
on header J1, and declared by the request as the current it draws at the
board's rail (`targets.load_current_ma`) and whether it is inductive
(`constraints.load_inductive`, default true — the safe guess, which places the
flyback diode).

Models, read by the netlist *and* by `predict()` (`generators/netlist/models.py`):

- `mcu_pin_thevenin` — the pin driven high, as for the LED. D2.
- `npn_saturated` — Q1's base-emitter junction as a diode fitted to its
  V_BE(sat) (0.6–1.2 V guaranteed at I_B = 15 mA), its collector as V_CE(sat)
  0.3 V. That model is only true in saturation, and the datasheet guarantees
  V_CE(sat) only at a forced beta of 10, so the block **proves** its own
  validity: the base current, over every part tolerance, is at least
  I_load / 10. D7 for the figures, D1 until a bench reads it.

R1 is the largest E96 value that still saturates Q1 at the worst corner (high
R1, high pin resistance, high V_BE) — the least pin current that does the job —
and the envelope refuses if the best corner then exceeds the pin's recommended
current. The load is the request's: J1's netlist element is the load's
equivalent resistance, V_rail / I_load, exactly.

The flyback diode is reverse-biased in steady state and absent from the DC
netlist; its job is the turn-off transient, which its claim checks against its
ratings (it carries the load current, it blocks the rail).
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Mapping, Optional

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
from data.component_constraints import get_constraints
from data.figures import of, passive
from data.mcu_targets import Target
from generators.arduino_parts import (
    BOARDS,
    DEFAULT_RAIL_BUDGET_MA,
    decoupling,
    grid_target,
    mcu,
    mcu_rail_ma,
    power_connections,
    read_target,
)
from generators.common import (
    PartFigures,
    Unreadable,
    e96_values,
    pinned_number,
    pinned_parts,
    read_number,
    read_pins,
    requirements,
    value_string,
)
from generators.netlist.models import (
    MODEL_MCU_PIN,
    MODEL_NPN_SATURATED,
    VT,
    led_parameters,
    pin_resistance,
    solve_series_diode,
    vce_sat,
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
from validation.pin_rules import Assignment, check_assignment

NAME = "load_switch"
VERSION = "0.1.0"
FUNCTION = "load_switch"

Q_PART = "MMBT2222ALT1G"
D_PART = "1N4148W-7-F"
J_PART = "22-27-2021"
_Q = get_constraints(Q_PART)
_D = get_constraints(D_PART)
FORCED_BETA = float(_Q["forced_beta"])
VCE_SAT_V = float(_Q["vce_sat_v"])
Q_IC_MAX_MA = float(_Q["max_collector_current_ma"])
Q_PD_MW = float(_Q["power_dissipation_mw"])
D_IF_MAX_MA = float(_D["max_forward_current_ma"])
D_VR_MAX = float(_D["reverse_voltage_max"])

#: The V_CE(sat) guarantee is at I_C = 150 mA; below 100 mA there is margin to it,
#: and the flyback diode's 150 mA average rating is not approached.
MIN_LOAD_MA, MAX_LOAD_MA = 1.0, 100.0
#: As for the LED: the pin model is characterised at the board's logic rail.
SUPPLY_WINDOW = {"arduino_uno": 0.25, "esp32_devkitc": 0.3, "blackpill_f411ce": 0.3}
#: A free general-purpose pin on each board — no strapping, console or other block default.
DEFAULT_PINS = {"arduino_uno": "D8", "esp32_devkitc": "GPIO25", "blackpill_f411ce": "PB10"}
GRID_LOADS_MA = {
    "arduino_uno": (5.0, 30.0, 60.0, 100.0),
    "esp32_devkitc": (5.0, 30.0, 60.0, 100.0),
    "blackpill_f411ce": (5.0, 30.0, 60.0, 100.0),
}
PINNABLE = ("R1",)


def default_pin(target: Target) -> str:
    return DEFAULT_PINS[target.id]


def gpio_limit_ma(target: Target) -> float:
    return float(get_constraints(target.mcu_part)["gpio_recommended_current_ma"])


class _Spec:
    __slots__ = ("load_ma", "inductive", "supply", "pin", "pins", "budget", "target", "figs")

    def __init__(self, load_ma, inductive, supply, pin, pins, budget, target, figs):
        self.load_ma, self.inductive, self.supply, self.pin = load_ma, inductive, supply, pin
        self.pins, self.budget, self.target, self.figs = pins, budget, target, figs

    @property
    def r_load(self) -> float:
        """The load's equivalent resistance, as written into the netlist (6 significant figures)."""
        return float(f"{self.supply / (self.load_ma / 1000.0):.6g}")

    @property
    def base_needed_ma(self) -> float:
        """The forced-beta base current: I_load / 10, with I_load the declared upper bound on I_C."""
        return self.load_ma / FORCED_BETA

    @property
    def collector_ma(self) -> float:
        return (self.supply - VCE_SAT_V) / self.r_load * 1000.0


def _read(intent: IntentLike) -> _Spec:
    target = read_target(intent)
    load = read_number(intent, "targets", "load_current_ma", None, allow_zero=False,
                       what="the load's current in mA")
    if load is None:
        raise Unreadable("targets.load_current_ma is required: the current the load draws at the "
                         "board's rail, in mA (a buzzer's or relay coil's rated current)")
    constraints = requirements(intent).get("constraints") or {}
    inductive = constraints.get("load_inductive", True) if isinstance(constraints, Mapping) else True
    if not isinstance(inductive, bool):
        raise Unreadable(f"constraints.load_inductive={inductive!r} must be true or false")
    supply = read_number(intent, "constraints", "supply_v", target.logic_v, allow_zero=False,
                         what="a rail voltage in volts")
    budget = read_number(intent, "constraints", "supply_current_ma", DEFAULT_RAIL_BUDGET_MA,
                         allow_zero=False, what="a rail budget in mA")
    prefs = requirements(intent).get("preferences") or {}
    pin = prefs.get("gpio_pin", default_pin(target)) if isinstance(prefs, Mapping) else default_pin(target)
    problems = check_assignment(target, [Assignment(str(pin), "output", "SW_CTRL")])
    if problems:
        raise Unreadable(f"preferences.gpio_pin={pin!r} cannot drive the switch on the {target.board}: "
                         + "; ".join(f.message for f in problems))
    pins: Dict[str, float] = {}
    for part, raw in read_pins(intent, PINNABLE).items():
        ohms = pinned_number(raw, _parse_ohms, part)
        if ohms is None:
            raise Unreadable(f"constraints.pinned.{part}={raw!r} is not a resistance "
                             f"this system can read (e.g. '470', '1k')")
        pins[part] = ohms
    figs = PartFigures(pinned_parts(intent, PINNABLE, {"R1": "resistor"}))
    return _Spec(load, inductive, supply, target.pin(pin).name, pins, budget, target, figs)


def base_current_a(supply: float, r1: float, r_out: float, vbe: str = "typ") -> float:
    i_s, n = led_parameters(Q_PART, vbe)
    return solve_series_diode(supply, r_out + r1, i_s, n)


def r1_power_max_w(supply: float, r1_lo: float, r1_hi: float, r_out: float, vbe: str) -> float:
    """
    The largest I²·R1 for R1 in [r1_lo, r1_hi], exactly. dP/dR1 has the sign of
    R_out + r_d − R1, with r_d = n·V_t/(I + I_s) the junction's incremental
    resistance, which falls strictly in R1 — so one peak, found by bisection.
    """
    i_s, n = led_parameters(Q_PART, vbe)

    def rising(r1: float) -> float:
        return r_out + n * VT / (base_current_a(supply, r1, r_out, vbe) + i_s) - r1

    def power(r1: float) -> float:
        return base_current_a(supply, r1, r_out, vbe) ** 2 * r1

    if rising(r1_lo) <= 0:
        return power(r1_lo)
    if rising(r1_hi) >= 0:
        return power(r1_hi)
    lo, hi = r1_lo, r1_hi
    for _ in range(200):
        mid = (lo + hi) / 2.0
        lo, hi = (mid, hi) if rising(mid) > 0 else (lo, mid)
    return power((lo + hi) / 2.0)


def _worst_low(spec: _Spec, r1: float) -> float:
    """mA at the corner that starves the base: R1 high, pin resistance high, V_BE(sat) at its maximum."""
    tol = spec.figs.tolerance("R1")
    return base_current_a(spec.supply, r1 * (1 + tol), pin_resistance(spec.target.mcu_part, "max"), "max") * 1000


def select_r1(spec: _Spec) -> Optional[float]:
    """The largest E96 R1 that still saturates Q1 at its worst corner. Deterministic."""
    if "R1" in spec.pins:
        return spec.pins["R1"]
    need = spec.base_needed_ma
    values = sorted(e96_values(10.0, 100_000.0))
    # _worst_low falls strictly as R1 rises: bisect for the last value that still meets `need`.
    lo, hi = 0, len(values)
    while lo < hi:
        mid = (lo + hi) // 2
        if _worst_low(spec, values[mid]) >= need:
            lo = mid + 1
        else:
            hi = mid
    return values[lo - 1] if lo else None


class LoadSwitchGenerator:
    """One NPN low-side switch on one MCU GPIO, on any target board. Implements `generators.protocol.Generator`."""

    name = NAME
    version = VERSION
    function = FUNCTION
    boards = BOARDS

    not_applicable_rules = {
        "pullup_on_open_drain": "no open-drain line: the GPIO drives the base push-pull",
    }

    # ── envelope() ────────────────────────────────────────────────────────

    def envelope(self, intent: IntentLike) -> EnvelopeDecision:
        function = (intent.requirements or {}).get("function")
        if function != FUNCTION:
            return EnvelopeDecision.refuse(
                f"function={function!r} is not load_switch — this generator switches one load "
                f"with an NPN transistor from one MCU GPIO")
        try:
            spec = _read(intent)
        except Unreadable as exc:
            return EnvelopeDecision.refuse(str(exc))
        target, limit = spec.target, gpio_limit_ma(spec.target)
        if abs(spec.supply - target.logic_v) > SUPPLY_WINDOW[target.id]:
            return EnvelopeDecision.refuse(
                f"supply_v={spec.supply:g}: the {target.mcu_part} GPIO drive model is characterised at "
                f"{target.logic_v:g} V (the datasheet's V_OH figure) and is not extrapolated")
        if not (MIN_LOAD_MA <= spec.load_ma <= MAX_LOAD_MA):
            return EnvelopeDecision.refuse(
                f"load_current_ma={spec.load_ma:g} outside {MIN_LOAD_MA:g}–{MAX_LOAD_MA:g} mA — the "
                f"{Q_PART}'s V_CE(sat) is guaranteed to 150 mA and this block keeps margin to it; a larger "
                f"load needs a MOSFET or a relay driver this catalogue does not have yet")
        r1 = select_r1(spec)
        if r1 is None or r1 <= 0:
            return EnvelopeDecision.refuse(
                f"no base resistor saturates Q1 for {spec.load_ma:g} mA from a {spec.supply:g} V pin "
                f"(it needs {spec.base_needed_ma:.3g} mA of base current at the worst corner)")
        band = self._base_band(spec, r1)
        if band.lo < spec.base_needed_ma:
            return EnvelopeDecision.refuse(
                f"pinned R1={r1:g}Ω gives as little as {band.lo:.3g} mA of base current, under the "
                f"{spec.base_needed_ma:.3g} mA (I_load/{FORCED_BETA:g}) that saturates Q1")
        if band.hi > limit:
            return EnvelopeDecision.refuse(
                f"with R1={r1:g}Ω the pin could source up to {band.hi:.2f} mA over part tolerance, above "
                f"the {limit:g} mA recommended per pin — {spec.load_ma:g} mA of load is too much for this "
                f"pin through one NPN; ask for less load current")
        rating = spec.figs.power_w("R1")
        if self._r1_power(spec, r1).hi > rating * 1000:
            return EnvelopeDecision.refuse(
                f"R1={r1:g}Ω could dissipate up to {self._r1_power(spec, r1).hi:.1f} mW, above its "
                f"{rating * 1000:g} mW rating")
        if spec.load_ma * VCE_SAT_V > Q_PD_MW:
            return EnvelopeDecision.refuse(
                f"Q1 could dissipate {spec.load_ma * VCE_SAT_V:.1f} mW, above its {Q_PD_MW:g} mW rating")
        if spec.inductive and (spec.load_ma > D_IF_MAX_MA or spec.supply > D_VR_MAX):
            return EnvelopeDecision.refuse(
                f"the flyback diode {D_PART} cannot clamp this load ({D_IF_MAX_MA:g} mA, {D_VR_MAX:g} V)")
        rail = mcu_rail_ma(spec.supply, target.mcu_part)
        if rail + spec.load_ma + band.hi > spec.budget:
            return EnvelopeDecision.refuse(
                f"the rail could draw up to {rail + spec.load_ma + band.hi:.4g} mA, over the "
                f"{spec.budget:g} mA budget (constraints.supply_current_ma)")
        return EnvelopeDecision.accept((
            PortContract(name="VCC", direction="power", voltage_range_v=Interval.at(spec.supply, "V"),
                         current_draw_a=Interval(lo=(rail + spec.collector_ma + band.lo) / 1000,
                                                 hi=(rail + spec.load_ma + band.hi) / 1000,
                                                 nominal=(rail + spec.collector_ma + band.nominal) / 1000,
                                                 units="A")),
            PortContract(name="GND", direction="ground"),
        ))

    # ── predict() ─────────────────────────────────────────────────────────

    def _boxes(self, spec: _Spec, r1: float, box: Optional[Mapping[str, Interval]] = None):
        part = spec.target.mcu_part
        tol = spec.figs.tolerance("R1")
        r1_band = Interval(lo=r1 * (1 - tol), hi=r1 * (1 + tol), nominal=r1, units="ohm")
        rout = Interval(lo=pin_resistance(part, "min"), hi=pin_resistance(part, "max"),
                        nominal=pin_resistance(part, "typ"), units="ohm")
        if box:
            unknown = set(box) - {"R1", "R_out"}
            if unknown:
                raise ValueError(f"predict() box names unknown parameters {sorted(unknown)}; "
                                 f"this generator takes ['R1', 'R_out']")
            r1_band, rout = box.get("R1", r1_band), box.get("R_out", rout)
        return r1_band, rout

    def _base_band(self, spec: _Spec, r1: float, box=None) -> Interval:
        """mA. Monotone: falls with R1, R_out and V_BE(sat)."""
        r1_band, rout = self._boxes(spec, r1, box)
        lo_vbe, hi_vbe = ("typ", "typ") if box else ("max", "min")
        return Interval(lo=base_current_a(spec.supply, r1_band.hi, rout.hi, lo_vbe) * 1000,
                        hi=base_current_a(spec.supply, r1_band.lo, rout.lo, hi_vbe) * 1000,
                        nominal=base_current_a(spec.supply, r1_band.nominal, rout.nominal) * 1000,
                        units="mA")

    def _r1_power(self, spec: _Spec, r1: float, box=None) -> Interval:
        """
        mW, exact. For a fixed R1, I²·R1 rises with I, so its extremes sit at
        the base band's corners in R_out and V_BE; along R1 it has one peak, at
        R1 = R_out + r_d (`r1_power_max_w`) — the LED's argument, on Q1's junction.
        """
        r1_band, rout = self._boxes(spec, r1, box)
        vbe_lo, vbe_hi = ("typ", "typ") if box else ("min", "max")
        hi = r1_power_max_w(spec.supply, r1_band.lo, r1_band.hi, rout.lo, vbe_lo)
        lo = min(base_current_a(spec.supply, r, rout.hi, vbe_hi) ** 2 * r for r in (r1_band.lo, r1_band.hi))
        nominal = base_current_a(spec.supply, r1_band.nominal, rout.nominal) ** 2 * r1_band.nominal
        return Interval(lo=lo * 1000, hi=hi * 1000, nominal=nominal * 1000, units="mW")

    def predict(self, intent: IntentLike, box: Optional[Mapping[str, Interval]] = None) -> Prediction:
        decision = self.envelope(intent)
        if not decision.accepted:
            raise ValueError(f"predict() called on a refused intent: {decision.reason}")
        spec = _read(intent)
        r1 = select_r1(spec)
        base = self._base_band(spec, r1, box)
        rail = mcu_rail_ma(spec.supply, spec.target.mcu_part)
        ic = Interval.at(spec.collector_ma, "mA")
        return Prediction(
            quantities={
                "base_current_ma": base,
                "gpio_current_ma": base,
                "collector_current_ma": ic,
                "r1_power_mw": self._r1_power(spec, r1, box),
                "supply_current_ma": Interval(lo=rail + ic.nominal + base.lo, hi=rail + ic.nominal + base.hi,
                                              nominal=rail + ic.nominal + base.nominal, units="mA"),
            },
            scope=ClaimScope(parameters="nominal" if box else "tolerance_box",
                             model=f"mna_ideal+{MODEL_MCU_PIN}+{MODEL_NPN_SATURATED}",
                             horizon="steady_state"),
            method="monotone_corners",
        )

    # ── claims() ──────────────────────────────────────────────────────────

    def claims(self, intent: IntentLike):
        from validation.claims import graded

        spec = _read(intent)
        pred = self.predict(intent)
        q, scope = pred.quantities, pred.scope
        base = q["base_current_ma"]
        part, limit = spec.target.mcu_part, gpio_limit_ma(spec.target)
        placed = {c.id: c.part_number for c in self.generate(intent).components}
        # Every claim on this netlist reads the saturated model: V_CE(sat) is an element of it.
        band_reads = (of(Q_PART, "forward_voltage_v", "test_current_ma", "ideality", "vce_sat_v")
                      + of(part, "gpio_output_resistance_ohm") + passive(placed["R1"], "tolerance"))

        def reads(*extra):
            return scope.model_copy(update={"figures": band_reads + tuple(x for e in extra for x in e)})

        out = [
            graded("sw.saturation",
                   f"Q1 saturates: its base current, at least {base.lo:.3g} mA over every part tolerance, meets "
                   f"I_load/{FORCED_BETA:g} = {spec.base_needed_ma:.3g} mA, where V_CE(sat) ≤ {VCE_SAT_V:g} V is "
                   f"guaranteed", base.lo >= spec.base_needed_ma, "monotone_corners",
                   reads(of(Q_PART, "forced_beta")),
                   detail=f"worst case {base.lo:.3g} mA", defeaters=("D1", "D2", "D7")),
            graded("sw.gpio_current_limit",
                   f"the pin never sources more than the {part.split('-')[0]}'s {limit:g} mA recommended "
                   f"per-pin current", base.hi <= limit, "monotone_corners",
                   reads(of(part, "gpio_recommended_current_ma")),
                   detail=f"worst case {base.hi:.3g} mA", defeaters=("D1", "D2", "D7"),
                   covers=("current_limits_ok",)),
            graded("sw.resistor_dissipation",
                   f"R1 stays below its {spec.figs.power_w('R1') * 1000:g} mW rating",
                   q["r1_power_mw"].hi <= spec.figs.power_w("R1") * 1000, "monotone_corners",
                   reads(passive(placed["R1"], "power_w")),
                   detail=f"worst case {q['r1_power_mw'].hi:.3g} mW", defeaters=("D1", "D7")),
            graded("sw.collector_limits",
                   f"Q1 carries at most the load's {spec.load_ma:g} mA, inside its {Q_IC_MAX_MA:g} mA rating, and "
                   f"dissipates at most {spec.load_ma * VCE_SAT_V:.3g} mW of its {Q_PD_MW:g} mW",
                   spec.load_ma <= Q_IC_MAX_MA and spec.load_ma * VCE_SAT_V <= Q_PD_MW, "closed_form",
                   scope.model_copy(update={"parameters": "nominal", "measures": ("i(V_SAT_Q1)",), "figures": of(
                       Q_PART, "vce_sat_v", "max_collector_current_ma", "power_dissipation_mw")}),
                   detail=f"I_C = {spec.collector_ma:.3g} mA at V_CE(sat)", defeaters=("D1", "D7")),
            graded("sw.rail_current",
                   f"the rail stays within its {spec.budget:g} mA budget",
                   q["supply_current_ma"].hi <= spec.budget, "monotone_corners",
                   reads(of(part, "supply_model_ohm")).model_copy(
                       update={"measures": (f"i(V_{spec.target.rail_node})", "i(V_PIN_SW_CTRL)")}),
                   detail=f"≤ {q['supply_current_ma'].hi:.4g} mA, of which the load is {spec.collector_ma:.3g} mA",
                   defeaters=("D1", "D2"), covers=("power_supply_adequate",)),
        ]
        if spec.inductive:
            out.append(graded(
                "sw.flyback",
                f"D1 clamps the load's turn-off: it carries the load's {spec.load_ma:g} mA (rated "
                f"{D_IF_MAX_MA:g} mA) and blocks the {spec.supply:g} V rail (rated {D_VR_MAX:g} V)",
                spec.load_ma <= D_IF_MAX_MA and spec.supply <= D_VR_MAX, "closed_form",
                scope.model_copy(update={"parameters": "nominal", "horizon": "turn_off_transient",
                                         "measures": ("i(V_SAT_Q1)",),
                                         "figures": of(D_PART, "max_forward_current_ma", "reverse_voltage_max")}),
                defeaters=("D1", "D7")))
        return out

    # ── properties() ──────────────────────────────────────────────────────

    def properties(self, intent: IntentLike):
        """
        Stage 4, on the netlist: the base current through the junction's
        Thevenin reduction — bounded below by the forced-beta requirement that
        makes the saturated model valid, and above by the pin's rating — and
        R1's dissipation.
        """
        from proof.properties import PropertySpec, exact, outward

        spec = _read(intent)
        band = self._base_band(spec, select_r1(spec))
        lo, hi = outward(band.lo / 1000, band.hi / 1000)
        return [
            PropertySpec(id="sw.base_current", label="Q1's base current", quantity="diode_current(D_Q1)",
                         relation="within", lo=lo, hi=hi, units="A", re_derives="sw.saturation"),
            PropertySpec(id="sw.saturation", label="Q1's base current", quantity="diode_current(D_Q1)",
                         relation="ge", lo=exact(spec.base_needed_ma, -3), units="A",
                         re_derives="sw.saturation", datasheet_bound=True),
            PropertySpec(id="sw.gpio_current", label="the current U1's pin sources",
                         quantity="diode_current(D_Q1)", relation="le",
                         hi=exact(gpio_limit_ma(spec.target), -3), units="A",
                         re_derives="sw.gpio_current_limit", datasheet_bound=True),
            PropertySpec(id="sw.r1_power", label="R1's dissipation", quantity="series_power(R_R1,D_Q1)",
                         relation="le", hi=exact(spec.figs.power_w("R1")), units="W",
                         re_derives="sw.resistor_dissipation", datasheet_bound=True),
        ]

    # ── generate() ────────────────────────────────────────────────────────

    def generate(self, intent: IntentLike) -> CircuitIR:
        spec = _read(intent)
        r1 = select_r1(spec)
        if r1 is None:
            raise ValueError("generate() called on an intent envelope() refuses")
        band = self._base_band(spec, r1)
        target, limit = spec.target, gpio_limit_ma(spec.target)
        rail = target.rail_node
        where = "" if target.id == "arduino_uno" else f" on the {target.board}"
        board = "Arduino Uno" if target.id == "arduino_uno" else target.board
        r1_part, r1_package, r1_maker = spec.figs.resistor("R1", r1)
        r_reason = (f"{r1:g}Ω, pinned by the requirement (constraints.pinned.R1) — the part in hand"
                    if "R1" in spec.pins else
                    f"{r1:g}Ω, the largest E96 value that still saturates Q1 at the worst corner")
        components = [
            mcu(f"{board} MCU switching the load from {spec.pin}. The pin sources at most {band.hi:.3g} mA "
                f"into Q1's base over every part tolerance, under the {limit:g} mA recommended per pin.",
                target),
            Component(
                id="Q1", type=ComponentType.TRANSISTOR, part_number=Q_PART, manufacturer="onsemi",
                package="SOT-23", supply_voltage_max=float(_Q["supply_voltage_max"]),
                current_draw_ma=round(spec.collector_ma, 3), confidence=0.9,
                justification=(
                    f"NPN low-side switch for the {spec.load_ma:g} mA load. It needs {spec.base_needed_ma:.3g} mA "
                    f"of base current (I_C/{FORCED_BETA:g}) to saturate at V_CE ≤ {VCE_SAT_V:g} V; it gets at "
                    f"least {band.lo:.3g} mA. Under-driven, it would sit in its linear region and heat."),
            ),
            Component(
                id="R1", type=ComponentType.RESISTOR, part_number=r1_part, manufacturer=r1_maker,
                package=r1_package, value=value_string(r1), supply_voltage_max=spec.figs.voltage_max("R1"),
                confidence=0.97,
                justification=(f"{r_reason}. Base current {band.lo:.3g}–{band.hi:.3g} mA; a larger R1 starves "
                               f"the base, a smaller one loads the pin for nothing."),
            ),
            Component(
                id="J1", type=ComponentType.CONNECTOR, part_number=J_PART, manufacturer="Molex",
                package="THT 2.54 mm, 2-pin", value=f"{spec.r_load:.6g}",
                current_draw_ma=spec.load_ma, confidence=0.85,
                justification=(
                    f"Header for the load: pin 1 to the {spec.supply:g} V rail, pin 2 to Q1's collector. The "
                    f"value is the load's equivalent resistance as declared — {spec.supply:g} V at "
                    f"{spec.load_ma:g} mA — which is what the netlist models; it is not a part on the board."),
            ),
        ]
        connections = [
            *power_connections(rail),
            Connection(component_id="U1", pin=spec.pin, node_id="SW_CTRL", direction="output"),
            Connection(component_id="R1", pin="A", node_id="SW_CTRL"),
            Connection(component_id="R1", pin="B", node_id="SW_BASE"),
            Connection(component_id="Q1", pin="B", node_id="SW_BASE", direction="input"),
            Connection(component_id="Q1", pin="C", node_id="SW_LOAD"),
            Connection(component_id="Q1", pin="E", node_id="GND"),
            Connection(component_id="J1", pin="1", node_id=rail, direction="input"),
            Connection(component_id="J1", pin="2", node_id="SW_LOAD"),
        ]
        if spec.inductive:
            components.append(Component(
                id="D1", type=ComponentType.DIODE, part_number=D_PART, manufacturer="Diodes Incorporated",
                package="SOD-123", supply_voltage_max=float(_D["supply_voltage_max"]), confidence=0.95,
                justification=(
                    f"Flyback diode across the load. When Q1 turns off, the load's inductance drives its "
                    f"{spec.load_ma:g} mA on through D1 instead of spiking Q1's collector past its 40 V rating."),
            ))
            connections += [Connection(component_id="D1", pin="A", node_id="SW_LOAD"),
                            Connection(component_id="D1", pin="K", node_id=rail)]
        components.append(decoupling("U1", target.logic_v))
        return CircuitIR(
            intent=f"Load switch on {spec.pin} for a {spec.load_ma:g} mA "
                   f"{'inductive ' if spec.inductive else ''}load{where}",
            application_class=ApplicationClass.HOBBY_ARDUINO,
            target_mcu=target.id,
            components=components,
            nodes=[
                Node(id=rail, voltage_nominal=spec.supply, type=SignalType.POWER),
                Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
                Node(id="SW_CTRL", voltage_nominal=spec.supply, type=SignalType.DIGITAL),
                Node(id="SW_BASE", type=SignalType.DIGITAL),
                Node(id="SW_LOAD", type=SignalType.DIGITAL),
            ],
            connections=connections,
            constraints={"supply_voltage": spec.supply, "load_current_ma": spec.load_ma,
                         "load_inductive": spec.inductive},
            simulation_spec=SimulationSpec(
                analyses=[SimulationAnalysis(
                    type="dc_op", description=f"Q1 on: base {band.nominal:.3g} mA, load {spec.collector_ma:.3g} mA")],
                expected_outputs={"SW_LOAD": VCE_SAT_V},
            ),
            validation_rules=[ValidationRule.NO_FLOATING_NODES, ValidationRule.VOLTAGE_RATINGS_OK],
        )

    # ── CI grid and locality ──────────────────────────────────────────────

    def grid(self, board: Optional[str] = None) -> GridSpec:
        return GridSpec(axes={"load_current_ma": list(GRID_LOADS_MA[grid_target(board).id])},
                        units={"load_current_ma": "mA"})

    def dependency_closure(self, requirement_path: str) -> FrozenSet[str]:
        closures: Dict[str, FrozenSet[str]] = {
            "targets.load_current_ma": frozenset({"R1", "Q1", "J1", "D1", "U1"}),
            "constraints.load_inductive": frozenset({"D1"}),
            "constraints.pinned": frozenset({"R1", "Q1", "U1"}),
            "preferences.gpio_pin": frozenset({"U1"}),
            "constraints.supply_current_ma": frozenset(),
        }
        path = requirement_path
        while path:
            if path in closures:
                return closures[path]
            path = path.rpartition(".")[0]
        return frozenset({"U1", "Q1", "R1", "J1", "D1", "C1"})
