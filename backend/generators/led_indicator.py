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
from generators.arduino_parts import (
    DEFAULT_RAIL_BUDGET_MA,
    MCU_PART,
    UNO_DIGITAL_PINS,
    decoupling,
    mcu,
    mcu_rail_ma,
    power_connections,
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
    pin_resistance,
    solve_series_diode,
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

NAME = "led_indicator"
VERSION = "0.1.1"
FUNCTION = "led_indicator"

LED_PART = "67-21URC/S530-A3/TR8"
_LED = get_constraints(LED_PART)
LED_MAX_MA = float(_LED["max_continuous_current_ma"])
GPIO_RECOMMENDED_MA = float(get_constraints(MCU_PART)["gpio_recommended_current_ma"])

#: The GPIO model is characterised at 5 V (the datasheet's V_OH figure), so the
#: envelope stays there rather than extrapolating R_out to another rail.
SUPPLY_V = 5.0
SUPPLY_WINDOW = 0.25
MIN_CURRENT_MA = 1.0
DEFAULT_CURRENT_MA = 10.0
COLOURS = {"red": LED_PART}
PINNABLE = ("R1",)


class _Spec:
    __slots__ = ("current_ma", "tolerance", "supply", "pin", "colour", "pins", "budget")

    def __init__(self, current_ma, tolerance, supply, pin, colour, pins, budget):
        self.current_ma, self.tolerance, self.supply = current_ma, tolerance, supply
        self.pin, self.colour, self.pins, self.budget = pin, colour, pins, budget


def _read(intent: IntentLike) -> _Spec:
    current = read_number(intent, "targets", "led_current_ma", DEFAULT_CURRENT_MA,
                          allow_zero=False, what="an LED current in mA")
    tolerance = read_number(intent, "targets", "tolerance_pct", 10.0, allow_zero=False,
                            what="a tolerance in percent")
    supply = read_number(intent, "constraints", "supply_v", SUPPLY_V, allow_zero=False,
                         what="a rail voltage in volts")
    budget = read_number(intent, "constraints", "supply_current_ma", DEFAULT_RAIL_BUDGET_MA,
                         allow_zero=False, what="a rail budget in mA")
    prefs = requirements(intent).get("preferences") or {}
    pin = prefs.get("gpio_pin", "D13") if isinstance(prefs, Mapping) else "D13"
    colour = prefs.get("colour", prefs.get("color", "red")) if isinstance(prefs, Mapping) else "red"
    if not isinstance(pin, str) or pin.upper() not in UNO_DIGITAL_PINS:
        raise Unreadable(f"preferences.gpio_pin={pin!r} is not an Arduino Uno digital pin "
                         f"this generator drives ({', '.join(UNO_DIGITAL_PINS)})")
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
    return _Spec(current, tolerance, supply, pin.upper(), colour.lower(), pins, budget)


def led_current_a(supply: float, r1: float, r_out: float, vf: str = "typ") -> float:
    i_s, n = led_parameters(LED_PART, vf)
    return solve_series_diode(supply, r_out + r1, i_s, n)


def select_r1(spec: _Spec) -> Optional[float]:
    """E96 value giving the target current at typical parts. Deterministic."""
    if "R1" in spec.pins:
        return spec.pins["R1"]
    target = spec.current_ma / 1000.0
    i_s, n = led_parameters(LED_PART, "typ")
    ideal = (spec.supply - diode_voltage(target, i_s, n)) / target - pin_resistance(MCU_PART)
    if ideal <= 0:
        return None
    first = snap_to_e96(ideal)
    candidates = e96_values(first / 1.1, first * 1.1)
    return min(
        candidates,
        key=lambda r: (abs(led_current_a(spec.supply, r, pin_resistance(MCU_PART)) - target), r),
    )


class LedIndicatorGenerator:
    """One LED on one Uno GPIO. Implements `generators.protocol.Generator`."""

    name = NAME
    version = VERSION
    function = FUNCTION

    not_applicable_rules = {
        "pullup_on_open_drain": "no open-drain line: the GPIO drives the LED push-pull",
    }

    # ── envelope() ────────────────────────────────────────────────────────

    def envelope(self, intent: IntentLike) -> EnvelopeDecision:
        function = (intent.requirements or {}).get("function")
        if function != FUNCTION:
            return EnvelopeDecision.refuse(
                f"function={function!r} is not led_indicator — this generator drives one "
                f"LED from one Arduino Uno GPIO"
            )
        try:
            spec = _read(intent)
        except Unreadable as exc:
            return EnvelopeDecision.refuse(str(exc))
        if abs(spec.supply - SUPPLY_V) > SUPPLY_WINDOW:
            return EnvelopeDecision.refuse(
                f"supply_v={spec.supply:g}: the GPIO drive model is characterised at "
                f"{SUPPLY_V:g} V (the datasheet's V_OH figure) and is not extrapolated"
            )
        if not (MIN_CURRENT_MA <= spec.current_ma <= GPIO_RECOMMENDED_MA):
            return EnvelopeDecision.refuse(
                f"led_current_ma={spec.current_ma:g} outside {MIN_CURRENT_MA:g}–"
                f"{GPIO_RECOMMENDED_MA:g} mA — above that the ATmega328P pin is past its "
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
        if band.hi > GPIO_RECOMMENDED_MA:
            return EnvelopeDecision.refuse(
                f"with R1={r1:g}Ω the pin could source up to {band.hi:.2f} mA over part "
                f"tolerance, above the {GPIO_RECOMMENDED_MA:g} mA recommended per pin"
            )
        if band.hi > LED_MAX_MA:
            return EnvelopeDecision.refuse(
                f"the LED could carry up to {band.hi:.2f} mA, above its {LED_MAX_MA:g} mA rating"
            )
        r1_power_hi = self._r1_power_hi(r1, band)
        if r1_power_hi > RESISTOR_POWER_W * 1000:
            return EnvelopeDecision.refuse(
                f"R1={r1:g}Ω could dissipate up to {r1_power_hi:.1f} mW over part tolerance, above "
                f"the {RESISTOR_POWER_W * 1000:g} mW rating of an 0402 resistor — ask for less current"
            )
        return EnvelopeDecision.accept((
            PortContract(name="VCC", direction="power",
                         voltage_range_v=Interval.at(spec.supply, "V"),
                         current_draw_a=Interval(lo=(mcu_rail_ma(spec.supply) + band.lo) / 1000,
                                                 hi=(mcu_rail_ma(spec.supply) + band.hi) / 1000,
                                                 nominal=(mcu_rail_ma(spec.supply) + band.nominal) / 1000,
                                                 units="A")),
            PortContract(name="GND", direction="ground"),
        ))

    # ── predict() ─────────────────────────────────────────────────────────

    def _boxes(self, r1: float, box: Optional[Mapping[str, Interval]] = None):
        r1_band = Interval(lo=r1 * (1 - RESISTOR_TOLERANCE), hi=r1 * (1 + RESISTOR_TOLERANCE),
                           nominal=r1, units="ohm")
        rout = Interval(lo=pin_resistance(MCU_PART, "min"), hi=pin_resistance(MCU_PART, "max"),
                        nominal=pin_resistance(MCU_PART, "typ"), units="ohm")
        if box:
            unknown = set(box) - {"R1", "R_out"}
            if unknown:
                raise ValueError(f"predict() box names unknown parameters {sorted(unknown)}; "
                                 f"this generator takes ['R1', 'R_out']")
            r1_band, rout = box.get("R1", r1_band), box.get("R_out", rout)
        return r1_band, rout

    def _r1_power_hi(self, r1: float, band: Interval, box=None) -> float:
        """mW. Largest current with largest resistance: sound, loose (G2)."""
        r1_band, _ = self._boxes(r1, box)
        return (band.hi / 1000) ** 2 * r1_band.hi * 1000

    def _current_band(self, spec: _Spec, r1: float, box=None) -> Interval:
        """mA. Monotone: falls with R1 and R_out, rises as V_f falls."""
        r1_band, rout = self._boxes(r1, box)
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
        r1_band, rout = self._boxes(r1, box)
        i_s, n = led_parameters(LED_PART, "typ")
        i_nom = current.nominal / 1000
        vf = diode_voltage(i_nom, i_s, n)
        # I²·R1 is not monotone in R1, so bound it outwardly: largest current
        # with largest resistance. Sound, loose — the claim says G2.
        p_hi = self._r1_power_hi(r1, current, box)
        p_lo = (current.lo / 1000) ** 2 * r1_band.lo * 1000
        p_nom = i_nom ** 2 * r1 * 1000
        rail = mcu_rail_ma(spec.supply)
        return Prediction(
            quantities={
                "led_current_ma": current,
                "gpio_current_ma": current,
                "led_forward_v": Interval.at(vf, "V"),
                "pin_voltage_v": Interval.at(spec.supply - i_nom * rout.nominal, "V"),
                "r1_power_mw": Interval(lo=min(p_lo, p_nom), hi=max(p_hi, p_nom), nominal=p_nom, units="mW"),
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
        return [
            graded("led.current_nominal",
                   f"LED current at typical parts is within ±{spec.tolerance:g}% of {spec.current_ma:g} mA",
                   err <= spec.tolerance, "closed_form", nominal_scope,
                   detail=f"{current.nominal:.3g} mA ({err:.1f}% from target)",
                   defeaters=("D1", "D2", "D7")),
            graded("led.current_band",
                   f"LED current lies in [{current.lo:.3g}, {current.hi:.3g}] mA for every R1 within 1%, "
                   f"pin resistance 15–40 Ω and forward voltage 1.7–2.4 V",
                   True, "monotone_corners", scope, defeaters=("D1", "D2", "D7")),
            graded("led.gpio_current_limit",
                   f"the pin never sources more than the ATmega328P's {GPIO_RECOMMENDED_MA:g} mA "
                   f"recommended per-pin current",
                   current.hi <= GPIO_RECOMMENDED_MA, "monotone_corners", scope,
                   detail=f"worst case {current.hi:.3g} mA", defeaters=("D1", "D2", "D7"),
                   covers=("current_limits_ok",)),
            graded("led.led_current_limit",
                   f"the LED never carries more than its {LED_MAX_MA:g} mA continuous rating",
                   current.hi <= LED_MAX_MA, "monotone_corners", scope,
                   detail=f"worst case {current.hi:.3g} mA", defeaters=("D1", "D2", "D7")),
            graded("led.resistor_dissipation",
                   f"R1 stays below its {RESISTOR_POWER_W * 1000:g} mW rating",
                   q["r1_power_mw"].hi <= RESISTOR_POWER_W * 1000, "sound_enclosure", scope,
                   detail=f"≤ {q['r1_power_mw'].hi:.3g} mW (interval bound)", defeaters=("D1", "D7")),
            graded("led.rail_current",
                   f"the rail stays within its {spec.budget:g} mA budget",
                   q["supply_current_ma"].hi <= spec.budget, "monotone_corners", scope,
                   detail=f"≤ {q['supply_current_ma'].hi:.4g} mA, of which the MCU model is "
                          f"{mcu_rail_ma(spec.supply):.0f} mA", defeaters=("D1", "D2"),
                   covers=("power_supply_adequate",)),
        ]

    # ── properties() ──────────────────────────────────────────────────────

    def properties(self, intent: IntentLike):
        """
        Stage 4. The LED current is decided exactly through the diode's
        Thevenin reduction; R1's dissipation is proved from a proven current
        bound, which is sound but not complete — G2, as predict() already says.
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
                         hi=exact(GPIO_RECOMMENDED_MA, -3), units="A",
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
        return CircuitIR(
            intent=f"Indicator LED on {spec.pin} at {spec.current_ma:g} mA",
            application_class=ApplicationClass.HOBBY_ARDUINO,
            target_mcu="arduino_uno",
            components=[
                mcu(f"Arduino Uno MCU driving the LED from {spec.pin}. Each GPIO is rated "
                    f"{GPIO_RECOMMENDED_MA:g} mA recommended, 40 mA absolute; this design stays "
                    f"at or under {band.hi:.3g} mA over every part tolerance."),
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
                        f"would roughly double the current and, past {GPIO_RECOMMENDED_MA:g} mA, "
                        f"overload the pin."
                    ),
                ),
                decoupling("U1"),
            ],
            nodes=[
                Node(id="VCC_5V", voltage_nominal=spec.supply, type=SignalType.POWER),
                Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
                # voltage_nominal on a node the MCU drives is what makes the
                # netlist model the pin as a Thevenin source (mcu_pin_thevenin).
                Node(id="LED_CTRL", voltage_nominal=spec.supply, type=SignalType.DIGITAL),
                Node(id="LED_ANODE", type=SignalType.DIGITAL),
            ],
            connections=[
                *power_connections(),
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

    def grid(self) -> GridSpec:
        return GridSpec(axes={"led_current_ma": [2.0, 5.0, 10.0, 15.0]},
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
