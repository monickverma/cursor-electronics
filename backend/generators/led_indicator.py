"""
GPIO-driven indicator LED — Stage 3, the Phase 1 TPL_003 template on the contract.

    U1 pin ─(R_out)─ LED_CTRL ── R1 ── LED_ANODE ── LED1 ── GND

The Phase 1 template's simulation never lit the LED: the GPIO node had no
source, and the netlist's generic diode dropped ~0.8 V instead of the 2.0 V the
design reasoned from (`brain/decisions.md` [2026-09-21] X6 + X8). This
generator uses two declared models, both read from one place
(`generators/netlist/models.py`) by the netlist *and* by `predict()`:

- `mcu_pin_thevenin` — the pin driven high is V_CC behind the ATmega328P's
  output resistance (15–40 Ω, from the datasheet's V_OH spec). Defeater D2.
- `shockley_diode` — the LED fitted to its datasheet forward voltage at 20 mA,
  with the datasheet's min/max forward voltage as the tolerance box. D7.

`predict()` solves V = I·(R_out + R1) + n·V_t·ln(1 + I/I_s) exactly (bisection
on a strictly monotone function). I falls with R1 and R_out and rises with I_s,
so the band edges are two opposite corners — `monotone_corners`, G1.

The claims that matter are limits, and the envelope refuses anything that
would break them: GPIO current at most the ATmega's 20 mA recommended per pin
(40 mA is the absolute maximum, and designing to it is how pins die), LED
current at most its continuous rating, and R1's dissipation at most its
rating.

**0.1.1**, from the Stage 3 + 4 verification. (1) The envelope did not check
R1's dissipation: at 17 mA from a 5.25 V pin, ngspice puts the worst corner at
64.7 mW in a 62.5 mW part. It now refuses when the sound bound exceeds the
rating — conservative, the same test the divider uses. (2) LED1 carried its
5 V *reverse* rating as `supply_voltage_max`, so the voltage-ratings rule
failed every accepted design above 5.0 V. An LED has no supply rating; in
this circuit it is never reverse-biased.

**0.1.2**, Task 4.5: R1's dissipation is exact, not an interval bound. For a
fixed R1, I²·R1 rises with I, so its extremes sit at the current band's
corners in R_out and V_f; along R1 it has one peak, at R1 = R_out + r_d
(`r1_power_max_w`). The claim is G1, and the envelope accepts what the old
bound refused for no reason — 16.3–16.5 mA from a 5.25 V pin, true worst
62.0 mW in a 62.5 mW part.
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
from data.mcu_targets import Target
from generators.arduino_parts import (
    BOARDS,
    DEFAULT_RAIL_BUDGET_MA,
    MCU_PART,
    decoupling,
    grid_target,
    mcu,
    mcu_rail_ma,
    power_connections,
    read_target,
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
    requirements,
    resistor_part,
    snap_to_e96,
    value_string,
)
from generators.netlist.models import (
    MODEL_LED,
    MODEL_MCU_PIN,
    diode_voltage,
    led_parameters,
    VT,
    pin_resistance,
    solve_series_diode,
)
from generators.netlist.spice import _parse_ohms
from validation.pin_rules import Assignment, check_assignment
from generators.protocol import (
    ClaimScope,
    EnvelopeDecision,
    GridSpec,
    IntentLike,
    Interval,
    PortContract,
    Prediction,
)

NAME = "led_indicator"
VERSION = "0.2.0"
FUNCTION = "led_indicator"

LED_PART = "67-21URC/S530-A3/TR8"
_LED = get_constraints(LED_PART)
LED_MAX_MA = float(_LED["max_continuous_current_ma"])
#: The Uno's figure; other boards read their own through `gpio_limit_ma`.
GPIO_RECOMMENDED_MA = float(get_constraints(MCU_PART)["gpio_recommended_current_ma"])

#: The GPIO model is characterised at the board's logic rail (the datasheet's
#: V_OH figure), so the envelope stays within this of it rather than
#: extrapolating R_out to another rail.
SUPPLY_V = 5.0
#: CI grid per board, up to near each board's envelope edge: the per-pin limit
#: over part tolerance refuses 15 mA on the 3.3 V boards (14.5 and 13.5 mA are
#: the last accepted half-milliamps). The Uno's is Phase 1's grid.
GRID_CURRENTS_MA = {
    "arduino_uno": (2.0, 5.0, 10.0, 15.0),
    "esp32_devkitc": (2.0, 5.0, 10.0, 14.0),
    "blackpill_f411ce": (2.0, 5.0, 10.0, 13.0),
}

SUPPLY_WINDOW = {"arduino_uno": 0.25, "esp32_devkitc": 0.3, "blackpill_f411ce": 0.3}


def gpio_limit_ma(target: Target) -> float:
    """The board's recommended per-pin current (D7)."""
    return float(get_constraints(target.mcu_part)["gpio_recommended_current_ma"])
MIN_CURRENT_MA = 1.0
DEFAULT_CURRENT_MA = 10.0
COLOURS = {"red": LED_PART}
PINNABLE = ("R1",)


class _Spec:
    __slots__ = ("current_ma", "tolerance", "supply", "pin", "colour", "pins", "budget", "target")

    def __init__(self, current_ma, tolerance, supply, pin, colour, pins, budget, target):
        self.current_ma, self.tolerance, self.supply = current_ma, tolerance, supply
        self.pin, self.colour, self.pins, self.budget = pin, colour, pins, budget
        self.target = target


def _read(intent: IntentLike) -> _Spec:
    target = read_target(intent)
    current = read_number(intent, "targets", "led_current_ma", DEFAULT_CURRENT_MA,
                          allow_zero=False, what="an LED current in mA")
    tolerance = read_number(intent, "targets", "tolerance_pct", 10.0, allow_zero=False,
                            what="a tolerance in percent")
    supply = read_number(intent, "constraints", "supply_v", target.logic_v, allow_zero=False,
                         what="a rail voltage in volts")
    budget = read_number(intent, "constraints", "supply_current_ma", DEFAULT_RAIL_BUDGET_MA,
                         allow_zero=False, what="a rail budget in mA")
    prefs = requirements(intent).get("preferences") or {}
    default_pin = target.defaults["led"]
    pin = prefs.get("gpio_pin", default_pin) if isinstance(prefs, Mapping) else default_pin
    colour = prefs.get("colour", prefs.get("color", "red")) if isinstance(prefs, Mapping) else "red"
    problems = check_assignment(target, [Assignment(str(pin), "output", "LED_CTRL")])
    if problems:
        raise Unreadable(f"preferences.gpio_pin={pin!r} cannot drive the LED on the {target.board}: "
                         + "; ".join(f.message for f in problems))
    if not isinstance(colour, str) or colour.lower() not in COLOURS:
        raise Unreadable(f"preferences.colour={colour!r} has no tabulated LED; the "
                         f"catalogue offers {sorted(COLOURS)}")
    pins: Dict[str, float] = {}
    for part, raw in read_pins(intent, PINNABLE).items():
        ohms = pinned_number(raw, _parse_ohms)
        if ohms is None:
            raise Unreadable(f"constraints.pinned.{part}={raw!r} is not a resistance "
                             f"this system can read (e.g. '220', '1k')")
        pins[part] = ohms
    return _Spec(current, tolerance, supply, target.pin(pin).name, colour.lower(), pins, budget, target)


def led_current_a(supply: float, r1: float, r_out: float, vf: str = "typ") -> float:
    i_s, n = led_parameters(LED_PART, vf)
    return solve_series_diode(supply, r_out + r1, i_s, n)


def r1_power_max_w(supply: float, r1_lo: float, r1_hi: float, r_out: float, vf: str) -> float:
    """
    The largest I²·R1 for R1 in [r1_lo, r1_hi], exactly (Task 4.5).

    dP/dR1 = I²·(R_out + r_d − R1)/(R_out + R1 + r_d), with r_d = n·V_t/(I + I_s)
    the diode's incremental resistance. The bracket falls strictly with R1 (r_d
    rises, but by less than R1 does), so P has at most one peak: at an end when
    the bracket keeps one sign, at its root otherwise — found by bisection.
    """
    i_s, n = led_parameters(LED_PART, vf)

    def rising(r1: float) -> float:
        i = led_current_a(supply, r1, r_out, vf)
        return r_out + n * VT / (i + i_s) - r1

    def power(r1: float) -> float:
        return led_current_a(supply, r1, r_out, vf) ** 2 * r1

    if rising(r1_lo) <= 0:
        return power(r1_lo)
    if rising(r1_hi) >= 0:
        return power(r1_hi)
    lo, hi = r1_lo, r1_hi
    for _ in range(200):
        mid = (lo + hi) / 2.0
        lo, hi = (mid, hi) if rising(mid) > 0 else (lo, mid)
    return power((lo + hi) / 2.0)


def select_r1(spec: _Spec) -> Optional[float]:
    """E96 value giving the target current at typical parts. Deterministic."""
    if "R1" in spec.pins:
        return spec.pins["R1"]
    target = spec.current_ma / 1000.0
    i_s, n = led_parameters(LED_PART, "typ")
    part = spec.target.mcu_part
    ideal = (spec.supply - diode_voltage(target, i_s, n)) / target - pin_resistance(part)
    if ideal <= 0:
        return None
    first = snap_to_e96(ideal)
    candidates = e96_values(first / 1.1, first * 1.1)
    return min(
        candidates,
        key=lambda r: (abs(led_current_a(spec.supply, r, pin_resistance(part)) - target), r),
    )


class LedIndicatorGenerator:
    """One LED on one MCU GPIO, on any target board. Implements `generators.protocol.Generator`."""

    name = NAME
    version = VERSION
    function = FUNCTION
    #: Stage 5: the boards it designs for; CI sweeps `grid(board)` on each.
    boards = BOARDS

    not_applicable_rules = {
        "pullup_on_open_drain": "no open-drain line: the GPIO drives the LED push-pull",
    }

    # ── envelope() ────────────────────────────────────────────────────────

    def envelope(self, intent: IntentLike) -> EnvelopeDecision:
        function = (intent.requirements or {}).get("function")
        if function != FUNCTION:
            return EnvelopeDecision.refuse(
                f"function={function!r} is not led_indicator — this generator drives one "
                f"LED from one MCU GPIO"
            )
        try:
            spec = _read(intent)
        except Unreadable as exc:
            return EnvelopeDecision.refuse(str(exc))
        target, limit = spec.target, gpio_limit_ma(spec.target)
        if abs(spec.supply - target.logic_v) > SUPPLY_WINDOW[target.id]:
            return EnvelopeDecision.refuse(
                f"supply_v={spec.supply:g}: the {target.mcu_part} GPIO drive model is characterised at "
                f"{target.logic_v:g} V (the datasheet's V_OH figure) and is not extrapolated"
            )
        if not (MIN_CURRENT_MA <= spec.current_ma <= limit):
            return EnvelopeDecision.refuse(
                f"led_current_ma={spec.current_ma:g} outside {MIN_CURRENT_MA:g}–"
                f"{limit:g} mA — above that the {target.mcu_part} pin is past its "
                f"recommended per-pin current; use a transistor"
            )
        r1 = select_r1(spec)
        if r1 is None or r1 <= 0:
            return EnvelopeDecision.refuse(
                f"no series resistor reaches {spec.current_ma:g} mA from a {spec.supply:g} V pin"
            )
        band = self._current_band(spec, r1)
        nominal_err = abs(band.nominal - spec.current_ma) / spec.current_ma * 100.0
        if nominal_err > spec.tolerance:
            which = "pinned R1" if spec.pins else "nearest E96 R1"
            return EnvelopeDecision.refuse(
                f"{which}={r1:g}Ω gives {band.nominal:.3g} mA against led_current_ma="
                f"{spec.current_ma:g}, a {nominal_err:.1f}% error beyond tolerance_pct="
                f"{spec.tolerance:g}"
            )
        if band.hi > limit:
            return EnvelopeDecision.refuse(
                f"with R1={r1:g}Ω the pin could source up to {band.hi:.2f} mA over part "
                f"tolerance, above the {limit:g} mA recommended per pin"
            )
        if band.hi > LED_MAX_MA:
            return EnvelopeDecision.refuse(
                f"the LED could carry up to {band.hi:.2f} mA, above its {LED_MAX_MA:g} mA rating"
            )
        r1_power_hi = self._r1_power(spec, r1).hi
        if r1_power_hi > RESISTOR_POWER_W * 1000:
            return EnvelopeDecision.refuse(
                f"R1={r1:g}Ω could dissipate up to {r1_power_hi:.1f} mW over part tolerance, above "
                f"the {RESISTOR_POWER_W * 1000:g} mW rating of an 0402 resistor — ask for less current"
            )
        rail = mcu_rail_ma(spec.supply, target.mcu_part)
        return EnvelopeDecision.accept((
            PortContract(name="VCC", direction="power",
                         voltage_range_v=Interval.at(spec.supply, "V"),
                         current_draw_a=Interval(lo=(rail + band.lo) / 1000,
                                                 hi=(rail + band.hi) / 1000,
                                                 nominal=(rail + band.nominal) / 1000,
                                                 units="A")),
            PortContract(name="GND", direction="ground"),
        ))

    # ── predict() ─────────────────────────────────────────────────────────

    def _boxes(self, spec: _Spec, r1: float, box: Optional[Mapping[str, Interval]] = None):
        part = spec.target.mcu_part
        r1_band = Interval(lo=r1 * (1 - RESISTOR_TOLERANCE), hi=r1 * (1 + RESISTOR_TOLERANCE),
                           nominal=r1, units="ohm")
        rout = Interval(lo=pin_resistance(part, "min"), hi=pin_resistance(part, "max"),
                        nominal=pin_resistance(part, "typ"), units="ohm")
        if box:
            unknown = set(box) - {"R1", "R_out"}
            if unknown:
                raise ValueError(f"predict() box names unknown parameters {sorted(unknown)}; "
                                 f"this generator takes ['R1', 'R_out']")
            r1_band, rout = box.get("R1", r1_band), box.get("R_out", rout)
        return r1_band, rout

    def _r1_power(self, spec: _Spec, r1: float, box=None) -> Interval:
        """
        mW, exact. For a fixed R1, I²·R1 rises with I, so the extremes sit at
        the current band's corners in R_out and V_f; along R1 it is unimodal
        (`r1_power_max_w`), so the top is its peak and the bottom an end.
        """
        r1_band, rout = self._boxes(spec, r1, box)
        vf_lo, vf_hi = ("typ", "typ") if box else ("min", "max")
        hi = r1_power_max_w(spec.supply, r1_band.lo, r1_band.hi, rout.lo, vf_lo)
        lo = min(led_current_a(spec.supply, r, rout.hi, vf_hi) ** 2 * r for r in (r1_band.lo, r1_band.hi))
        nominal = led_current_a(spec.supply, r1_band.nominal, rout.nominal) ** 2 * r1_band.nominal
        return Interval(lo=lo * 1000, hi=hi * 1000, nominal=nominal * 1000, units="mW")

    def _current_band(self, spec: _Spec, r1: float, box=None) -> Interval:
        """mA. Monotone: falls with R1 and R_out, rises as V_f falls."""
        r1_band, rout = self._boxes(spec, r1, box)
        vf_box = ("typ", "typ") if box else ("max", "min")
        lo = led_current_a(spec.supply, r1_band.hi, rout.hi, vf_box[0]) * 1000
        hi = led_current_a(spec.supply, r1_band.lo, rout.lo, vf_box[1]) * 1000
        nominal = led_current_a(spec.supply, r1_band.nominal, rout.nominal) * 1000
        return Interval(lo=lo, hi=hi, nominal=nominal, units="mA")

    def predict(self, intent: IntentLike, box: Optional[Mapping[str, Interval]] = None) -> Prediction:
        decision = self.envelope(intent)
        if not decision.accepted:
            raise ValueError(f"predict() called on a refused intent: {decision.reason}")
        spec = _read(intent)
        r1 = select_r1(spec)
        current = self._current_band(spec, r1, box)
        _, rout = self._boxes(spec, r1, box)
        i_s, n = led_parameters(LED_PART, "typ")
        i_nom = current.nominal / 1000
        vf = diode_voltage(i_nom, i_s, n)
        rail = mcu_rail_ma(spec.supply, spec.target.mcu_part)
        return Prediction(
            quantities={
                "led_current_ma": current,
                "gpio_current_ma": current,
                "led_forward_v": Interval.at(vf, "V"),
                "pin_voltage_v": Interval.at(spec.supply - i_nom * rout.nominal, "V"),
                "r1_power_mw": self._r1_power(spec, r1, box),
                "supply_current_ma": Interval(lo=rail + current.lo, hi=rail + current.hi,
                                              nominal=rail + current.nominal, units="mA"),
            },
            scope=ClaimScope(
                parameters="nominal" if box else "tolerance_box",
                model=f"mna_ideal+{MODEL_MCU_PIN}+{MODEL_LED}",
                horizon="steady_state",
            ),
            method="monotone_corners",
        )

    # ── claims() ──────────────────────────────────────────────────────────

    def claims(self, intent: IntentLike):
        from validation.claims import graded

        spec = _read(intent)
        pred = self.predict(intent)
        q, scope = pred.quantities, pred.scope
        current = q["led_current_ma"]
        err = abs(current.nominal - spec.current_ma) / spec.current_ma * 100.0
        nominal_scope = scope.model_copy(update={"parameters": "nominal"})
        part, limit = spec.target.mcu_part, gpio_limit_ma(spec.target)
        rout = self._boxes(spec, select_r1(spec))[1]
        return [
            graded("led.current_nominal",
                   f"LED current at typical parts is within ±{spec.tolerance:g}% of {spec.current_ma:g} mA",
                   err <= spec.tolerance, "closed_form", nominal_scope,
                   detail=f"{current.nominal:.3g} mA ({err:.1f}% from target)",
                   defeaters=("D1", "D2", "D7")),
            graded("led.current_band",
                   f"LED current lies in [{current.lo:.3g}, {current.hi:.3g}] mA for every R1 within 1%, "
                   f"pin resistance {rout.lo:g}–{rout.hi:g} Ω and forward voltage 1.7–2.4 V",
                   True, "monotone_corners", scope, defeaters=("D1", "D2", "D7")),
            graded("led.gpio_current_limit",
                   f"the pin never sources more than the {part.split('-')[0]}'s {limit:g} mA "
                   f"recommended per-pin current",
                   current.hi <= limit, "monotone_corners", scope,
                   detail=f"worst case {current.hi:.3g} mA", defeaters=("D1", "D2", "D7"),
                   covers=("current_limits_ok",)),
            graded("led.led_current_limit",
                   f"the LED never carries more than its {LED_MAX_MA:g} mA continuous rating",
                   current.hi <= LED_MAX_MA, "monotone_corners", scope,
                   detail=f"worst case {current.hi:.3g} mA", defeaters=("D1", "D2", "D7")),
            graded("led.resistor_dissipation",
                   f"R1 stays below its {RESISTOR_POWER_W * 1000:g} mW rating",
                   q["r1_power_mw"].hi <= RESISTOR_POWER_W * 1000, "monotone_corners", scope,
                   detail=f"worst case {q['r1_power_mw'].hi:.3g} mW", defeaters=("D1", "D7")),
            graded("led.rail_current",
                   f"the rail stays within its {spec.budget:g} mA budget",
                   q["supply_current_ma"].hi <= spec.budget, "monotone_corners", scope,
                   detail=f"≤ {q['supply_current_ma'].hi:.4g} mA, of which the MCU model is "
                          f"{mcu_rail_ma(spec.supply, part):.0f} mA", defeaters=("D1", "D2"),
                   covers=("power_supply_adequate",)),
        ]

    # ── properties() ──────────────────────────────────────────────────────

    def properties(self, intent: IntentLike):
        """
        Stage 4. The LED current is decided exactly through the diode's
        Thevenin reduction; R1's dissipation at the end of R1's range that a
        proven monotonicity lemma names (Task 4.5) — G1, as predict() says.
        """
        from proof.properties import PropertySpec, exact, outward

        spec = _read(intent)
        band = self._current_band(spec, select_r1(spec))
        lo, hi = outward(band.lo / 1000, band.hi / 1000)
        return [
            PropertySpec(id="led.current", label="the LED current", quantity="diode_current(D_LED1)",
                         relation="within", lo=lo, hi=hi, units="A", re_derives="led.current_band"),
            PropertySpec(id="led.gpio_current", label="the current U1's pin sources",
                         quantity="diode_current(D_LED1)", relation="le",
                         hi=exact(gpio_limit_ma(spec.target), -3), units="A",
                         re_derives="led.gpio_current_limit", datasheet_bound=True),
            PropertySpec(id="led.led_current", label="the LED current", quantity="diode_current(D_LED1)",
                         relation="le", hi=exact(LED_MAX_MA, -3), units="A",
                         re_derives="led.led_current_limit", datasheet_bound=True),
            PropertySpec(id="led.r1_power", label="R1's dissipation", quantity="series_power(R_R1,D_LED1)",
                         relation="le", hi=exact(RESISTOR_POWER_W), units="W",
                         re_derives="led.resistor_dissipation", datasheet_bound=True),
        ]

    # ── generate() ────────────────────────────────────────────────────────

    def generate(self, intent: IntentLike) -> CircuitIR:
        spec = _read(intent)
        r1 = select_r1(spec)
        if r1 is None:
            raise ValueError("generate() called on an intent envelope() refuses")
        band = self._current_band(spec, r1)
        i_s, n = led_parameters(LED_PART, "typ")
        vf = diode_voltage(band.nominal / 1000, i_s, n)
        r_reason = (
            f"{r1:g}Ω, pinned by the requirement (constraints.pinned.R1) — the part in hand"
            if "R1" in spec.pins else f"{r1:g}Ω, the E96 value nearest {spec.current_ma:g} mA"
        )
        target, limit = spec.target, gpio_limit_ma(spec.target)
        absolute = get_constraints(target.mcu_part).get("max_gpio_source_current_ma",
                                                        get_constraints(target.mcu_part).get("max_gpio_current_ma"))
        where = "" if target.id == "arduino_uno" else f" on the {target.board}"
        board = "Arduino Uno" if target.id == "arduino_uno" else target.board
        return CircuitIR(
            intent=f"Indicator LED on {spec.pin} at {spec.current_ma:g} mA{where}",
            application_class=ApplicationClass.HOBBY_ARDUINO,
            target_mcu=target.id,
            components=[
                mcu(f"{board} MCU driving the LED from {spec.pin}. Each GPIO is rated "
                    f"{limit:g} mA recommended, {absolute:g} mA absolute; this design stays "
                    f"at or under {band.hi:.3g} mA over every part tolerance.", target),
                Component(
                    id="LED1", type=ComponentType.LED, part_number=LED_PART,
                    manufacturer="Everlight", package="0805",
                    # No supply rating: the 5 V figure is reverse voltage, and this
                    # circuit never reverse-biases the LED.
                    supply_voltage_max=None, current_draw_ma=round(band.nominal, 3),
                    confidence=0.9, lcsc_pn="C72038",
                    justification=(
                        f"Red LED, V_f {vf:.2f} V at {band.nominal:.3g} mA on its fitted diode model "
                        f"(datasheet 1.7–2.4 V at 20 mA). A lower-V_f part in the same spread raises "
                        f"the current to {band.hi:.3g} mA — still under its {LED_MAX_MA:g} mA rating."
                    ),
                ),
                Component(
                    id="R1", type=ComponentType.RESISTOR, part_number=resistor_part(r1),
                    manufacturer="Yageo", package="0402", value=value_string(r1),
                    supply_voltage_max=RESISTOR_VMAX, confidence=0.97,
                    justification=(
                        f"{r_reason}. It sets I = (V_pin − V_f)/R1 ≈ {band.nominal:.3g} mA; halving it "
                        f"would roughly double the current and, past {limit:g} mA, "
                        f"overload the pin."
                    ),
                ),
                decoupling("U1", target.logic_v),
            ],
            nodes=[
                Node(id=target.rail_node, voltage_nominal=spec.supply, type=SignalType.POWER),
                Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
                # voltage_nominal on a node the MCU drives is what makes the
                # netlist model the pin as a Thevenin source (mcu_pin_thevenin).
                Node(id="LED_CTRL", voltage_nominal=spec.supply, type=SignalType.DIGITAL),
                Node(id="LED_ANODE", type=SignalType.DIGITAL),
            ],
            connections=[
                *power_connections(target.rail_node),
                Connection(component_id="U1", pin=spec.pin, node_id="LED_CTRL", direction="output"),
                Connection(component_id="R1", pin="A", node_id="LED_CTRL"),
                Connection(component_id="R1", pin="B", node_id="LED_ANODE"),
                Connection(component_id="LED1", pin="ANODE", node_id="LED_ANODE", direction="input"),
                Connection(component_id="LED1", pin="CATHODE", node_id="GND", direction="input"),
            ],
            constraints={"supply_voltage": spec.supply, "led_current_ma": spec.current_ma},
            simulation_spec=SimulationSpec(
                analyses=[SimulationAnalysis(type="dc_op",
                                             description=f"LED current ≈ {band.nominal:.3g} mA with the pin high")],
                expected_outputs={"LED_ANODE": round(vf, 4)},
            ),
            validation_rules=[ValidationRule.NO_FLOATING_NODES, ValidationRule.VOLTAGE_RATINGS_OK],
        )

    # ── CI grid and locality ──────────────────────────────────────────────

    def grid(self, board: Optional[str] = None) -> GridSpec:
        return GridSpec(axes={"led_current_ma": list(GRID_CURRENTS_MA[grid_target(board).id])},
                        units={"led_current_ma": "mA"})

    def dependency_closure(self, requirement_path: str) -> FrozenSet[str]:
        closures: Dict[str, FrozenSet[str]] = {
            "targets.led_current_ma": frozenset({"R1", "LED1", "U1"}),
            "targets.tolerance_pct": frozenset({"R1", "LED1", "U1"}),
            "constraints.pinned": frozenset({"R1", "LED1", "U1"}),
            # The MCU's justification names the pin it drives. Found by the
            # Stage 3 locality sweep, which this closure first failed.
            "preferences.gpio_pin": frozenset({"U1"}),
            "constraints.supply_current_ma": frozenset(),
        }
        path = requirement_path
        while path:
            if path in closures:
                return closures[path]
            path = path.rpartition(".")[0]
        return frozenset({"U1", "R1", "LED1", "C1"})
