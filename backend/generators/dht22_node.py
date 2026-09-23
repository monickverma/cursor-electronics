"""
Arduino Uno + DHT22 temperature/humidity node — Stage 3, Phase 1 TPL_001.

    VCC ─┬─ R1 (pull-up) ─┬─ DHT22_DATA ── U1 D2 (bidirectional)
         │                └─ U2 DATA (open drain)
         ├─ U1, U2, C1 ── GND

The DHT22's data line is open drain: nothing drives it high except R1. That
one resistor sets the two things the bus depends on, and they pull opposite
ways:

- **rise time** t_r(10–90 %) = ln 9 · R1 · C_bus. The sensor's short "0" bit is
  26 µs high; a slow edge eats it. Longer cable, more capacitance, smaller R1.
- **sink current** V_CC / R1 through whichever open drain holds the line low
  (the MCU's start pulse, the sensor's reply). Smaller R1, more current.

Selection starts at the datasheet's 10 kΩ and only steps down when the
worst-case rise time over the declared cable length exceeds its limit; if no
E96 value satisfies both, the cable is too long and the request is refused by
name. Both quantities are monotone in R1 (and t_r in C_bus), so their bands
are exact corners — G1 — over assumptions the component table states once and
defeater D7 cites.

Rail current is a claim too, under `mcu_as_100R` (X6, defeater D2): the MCU
is a 100 Ω load, the sensor its tabulated current, both read from the same
models the netlist emits.
"""

from __future__ import annotations

import math
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
    RESISTOR_TOLERANCE,
    RESISTOR_VMAX,
    Unreadable,
    e96_values,
    pinned_number,
    read_number,
    read_pins,
    requirements,
    resistor_part,
    value_string,
)
from generators.netlist.models import load_ohms, mcu_supply_model, mcu_supply_ohms
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

NAME = "dht22_node"
VERSION = "0.2.0"
FUNCTION = "temperature_humidity_sensor"

SENSOR_PART = "DHT22"
_DHT = get_constraints(SENSOR_PART)
DEFAULT_PULLUP_OHMS = float(_DHT["pullup_value_kohm"]) * 1000.0
CABLE_PF_PER_M = _DHT["bus_capacitance_pf_per_m"]
INPUT_PF = float(_DHT["input_capacitance_pf"])
RISE_LIMIT_US = float(_DHT["rise_time_limit_us"])
SINK_LIMIT_MA = float(_DHT["open_drain_sink_limit_ma"])
MCU_SINK_LIMIT_MA = float(get_constraints(MCU_PART)["gpio_recommended_current_ma"])
LN9 = math.log(9.0)

SUPPLY_MIN_V = 4.5   # an ATmega328P at 16 MHz, and inside the DHT22's 3.3-5.5 V
SUPPLY_MAX_V = min(5.5, float(_DHT["supply_voltage_max"]))

#: Per board: (lowest, highest) supply, and why. A 3.3 V board runs the sensor
#: from its own rail: the DHT22's 3.3 V minimum up to the MCU's 3.6 V maximum.
SUPPLY_WINDOWS = {
    "arduino_uno": (SUPPLY_MIN_V, SUPPLY_MAX_V, "the ATmega328P at 16 MHz needs 4.5 V and the DHT22 is rated to 5.5 V"),
    "esp32_devkitc": (float(_DHT["supply_voltage_min"]), 3.6,
                      "the DHT22 needs 3.3 V and the ESP32 is rated to 3.6 V"),
    "blackpill_f411ce": (float(_DHT["supply_voltage_min"]), 3.6,
                         "the DHT22 needs 3.3 V and the STM32F411 is rated to 3.6 V"),
}


def mcu_sink_limit_ma(target) -> float:
    """The board's recommended per-pin current (D7)."""
    return float(get_constraints(target.mcu_part)["gpio_recommended_current_ma"])
DEFAULT_CABLE_M = 0.3
MAX_CABLE_M = 20.0   # Aosong's own figure for the longest recommended run
PINNABLE = ("R1",)


class _Spec:
    __slots__ = ("supply", "cable", "budget", "pin", "threshold", "pins", "target")

    def __init__(self, supply, cable, budget, pin, threshold, pins, target):
        self.supply, self.cable, self.budget = supply, cable, budget
        self.pin, self.threshold, self.pins, self.target = pin, threshold, pins, target


def _read(intent: IntentLike) -> _Spec:
    target = read_target(intent)
    supply = read_number(intent, "constraints", "supply_v", target.logic_v, allow_zero=False,
                         what="a rail voltage in volts")
    cable = read_number(intent, "constraints", "cable_length_m", DEFAULT_CABLE_M,
                        allow_zero=True, what="a cable length in metres")
    budget = read_number(intent, "constraints", "supply_current_ma", DEFAULT_RAIL_BUDGET_MA,
                         allow_zero=False, what="a rail budget in mA")
    prefs = requirements(intent).get("preferences") or {}
    default_pin = target.defaults["dht_data"]
    pin = prefs.get("data_pin", default_pin) if isinstance(prefs, Mapping) else default_pin
    problems = check_assignment(target, [Assignment(str(pin), "bidirectional", "DHT22_DATA")])
    if problems:
        raise Unreadable(f"preferences.data_pin={pin!r} cannot carry the DHT22's DATA line on the "
                         f"{target.board}: " + "; ".join(f.message for f in problems))
    threshold = prefs.get("alert_threshold_c") if isinstance(prefs, Mapping) else None
    if threshold is not None and (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
                                  or not math.isfinite(threshold)):
        raise Unreadable(f"preferences.alert_threshold_c={threshold!r} is not a temperature in °C")
    pins: Dict[str, float] = {}
    for part, raw in read_pins(intent, PINNABLE).items():
        ohms = pinned_number(raw, _parse_ohms)
        if ohms is None:
            raise Unreadable(f"constraints.pinned.{part}={raw!r} is not a resistance "
                             f"this system can read (e.g. '10k', '4k7')")
        pins[part] = ohms
    return _Spec(supply, cable, budget, target.pin(pin).name, threshold, pins, target)


def bus_capacitance_pf(cable_m: float, which: str) -> float:
    """MCU pin + sensor input + cable, at the cable's `min` or `max` pF/m."""
    return 2 * INPUT_PF + cable_m * CABLE_PF_PER_M[which]


def rise_time_us(r_ohms: float, c_pf: float) -> float:
    return LN9 * r_ohms * c_pf * 1e-12 * 1e6


def sink_ma(supply: float, r_ohms: float) -> float:
    return supply / r_ohms * 1000.0


def select_pullup(spec: _Spec) -> Optional[float]:
    """10 kΩ unless the cable forces a stronger pull-up. None if nothing works."""
    if "R1" in spec.pins:
        return spec.pins["R1"]
    c_max = bus_capacitance_pf(spec.cable, "max")

    def ok(r: float) -> bool:
        worst_rise = rise_time_us(r * (1 + RESISTOR_TOLERANCE), c_max)
        worst_sink = sink_ma(spec.supply, r * (1 - RESISTOR_TOLERANCE))
        return worst_rise <= RISE_LIMIT_US and worst_sink <= SINK_LIMIT_MA

    if ok(DEFAULT_PULLUP_OHMS):
        return DEFAULT_PULLUP_OHMS
    for r in reversed(e96_values(100.0, DEFAULT_PULLUP_OHMS)):
        if ok(r):
            return r
    return None


class DHT22NodeGenerator:
    """Uno + DHT22 + pull-up + bypass. Implements `generators.protocol.Generator`."""

    name = NAME
    version = VERSION
    function = FUNCTION
    #: Stage 5: the boards it designs for; CI sweeps `grid(board)` on each.
    boards = BOARDS

    not_applicable_rules: Dict[str, str] = {}

    # ── envelope() ────────────────────────────────────────────────────────

    def envelope(self, intent: IntentLike) -> EnvelopeDecision:
        function = (intent.requirements or {}).get("function")
        if function != FUNCTION:
            return EnvelopeDecision.refuse(
                f"function={function!r} is not temperature_humidity_sensor — this generator "
                f"builds one MCU board with one DHT22"
            )
        try:
            spec = _read(intent)
        except Unreadable as exc:
            return EnvelopeDecision.refuse(str(exc))
        low, high, why = SUPPLY_WINDOWS[spec.target.id]
        if not (low <= spec.supply <= high):
            return EnvelopeDecision.refuse(
                f"supply_v={spec.supply:g} outside {low:g}–{high:g} V — {why}"
            )
        if spec.cable > MAX_CABLE_M:
            return EnvelopeDecision.refuse(
                f"cable_length_m={spec.cable:g} exceeds the {MAX_CABLE_M:g} m the DHT22's "
                f"single-wire bus is specified for"
            )
        r1 = select_pullup(spec)
        if r1 is None:
            return EnvelopeDecision.refuse(
                f"no pull-up meets both the {RISE_LIMIT_US:g} µs rise time over "
                f"{spec.cable:g} m of cable and the {SINK_LIMIT_MA:g} mA sink limit"
            )
        rise = rise_time_us(r1 * (1 + RESISTOR_TOLERANCE), bus_capacitance_pf(spec.cable, "max"))
        sink = sink_ma(spec.supply, r1 * (1 - RESISTOR_TOLERANCE))
        if rise > RISE_LIMIT_US:
            return EnvelopeDecision.refuse(
                f"pinned R1={r1:g}Ω gives up to {rise:.2f} µs rise time over {spec.cable:g} m, "
                f"above the {RISE_LIMIT_US:g} µs limit"
            )
        if sink > SINK_LIMIT_MA:
            return EnvelopeDecision.refuse(
                f"pinned R1={r1:g}Ω lets {sink:.2f} mA through the sensor's open drain, above "
                f"the {SINK_LIMIT_MA:g} mA limit"
            )
        rail = self._rail_ma(spec)
        return EnvelopeDecision.accept((
            PortContract(name="VCC", direction="power", voltage_range_v=Interval.at(spec.supply, "V"),
                         current_draw_a=Interval.at(rail / 1000, "A")),
            PortContract(name="GND", direction="ground"),
        ))

    def _rail_ma(self, spec: _Spec) -> float:
        """Idle rail current: the MCU's supply model plus the sensor's tabulated load."""
        sensor = load_ohms(_DHT["current_draw_ma"], _DHT["supply_voltage_max"])
        return mcu_rail_ma(spec.supply, spec.target.mcu_part) + spec.supply / sensor * 1000.0

    # ── predict() ─────────────────────────────────────────────────────────

    def predict(self, intent: IntentLike, box: Optional[Mapping[str, Interval]] = None) -> Prediction:
        decision = self.envelope(intent)
        if not decision.accepted:
            raise ValueError(f"predict() called on a refused intent: {decision.reason}")
        spec = _read(intent)
        r1 = select_pullup(spec)
        r_band = Interval(lo=r1 * (1 - RESISTOR_TOLERANCE), hi=r1 * (1 + RESISTOR_TOLERANCE),
                          nominal=r1, units="ohm")
        c_band = Interval(lo=bus_capacitance_pf(spec.cable, "min"), hi=bus_capacitance_pf(spec.cable, "max"),
                          nominal=bus_capacitance_pf(spec.cable, "min") / 2 + bus_capacitance_pf(spec.cable, "max") / 2,
                          units="pF")
        if box:
            unknown = set(box) - {"R1", "C_bus"}
            if unknown:
                raise ValueError(f"predict() box names unknown parameters {sorted(unknown)}")
            r_band, c_band = box.get("R1", r_band), box.get("C_bus", c_band)
        rail = self._rail_ma(spec)
        return Prediction(
            quantities={
                # Monotone decreasing in R1: opposite ends of its band.
                "pullup_sink_current_ma": Interval(
                    lo=sink_ma(spec.supply, r_band.hi), hi=sink_ma(spec.supply, r_band.lo),
                    nominal=sink_ma(spec.supply, r_band.nominal), units="mA"),
                # Monotone increasing in R1 and in C_bus.
                "rise_time_us": Interval(
                    lo=rise_time_us(r_band.lo, c_band.lo), hi=rise_time_us(r_band.hi, c_band.hi),
                    nominal=rise_time_us(r_band.nominal, c_band.nominal), units="us"),
                "supply_current_ma": Interval.at(rail, "mA"),
                "pullup_ohm": r_band,
            },
            scope=ClaimScope(parameters="nominal" if box else "tolerance_box",
                             model=f"mna_ideal+{mcu_supply_model(mcu_supply_ohms(spec.target.mcu_part))}",
                             horizon="steady_state"),
            method="monotone_corners",
        )

    # ── claims() ──────────────────────────────────────────────────────────

    def claims(self, intent: IntentLike):
        from validation.claims import graded

        spec = _read(intent)
        pred = self.predict(intent)
        q, scope = pred.quantities, pred.scope
        design = self.generate(intent)
        pulled_up = any(
            {c.node_id for c in design.connections if c.component_id == comp.id} == {spec.target.rail_node, "DHT22_DATA"}
            for comp in design.components if comp.type == ComponentType.RESISTOR
        )
        graph = ClaimScope(parameters="nominal", model="design_graph")
        sink, rise, rail = q["pullup_sink_current_ma"], q["rise_time_us"], q["supply_current_ma"]
        return [
            graded("dht.pullup_present",
                   "the DHT22's open-drain DATA line has a pull-up resistor to VCC",
                   pulled_up, "exact_graph_check", graph, defeaters=(),
                   covers=("pullup_on_open_drain",)),
            graded("dht.rise_time",
                   f"DATA rises (10–90 %) within {RISE_LIMIT_US:g} µs over {spec.cable:g} m of cable",
                   rise.hi <= RISE_LIMIT_US, "monotone_corners", scope,
                   detail=f"{rise.lo:.3g}–{rise.hi:.3g} µs for R1 ±1% and 50–100 pF/m",
                   defeaters=("D1", "D7")),
            graded("dht.sink_current",
                   f"holding DATA low sinks at most {SINK_LIMIT_MA:g} mA through the sensor and "
                   f"{mcu_sink_limit_ma(spec.target):g} mA through the MCU pin",
                   sink.hi <= min(SINK_LIMIT_MA, mcu_sink_limit_ma(spec.target)), "monotone_corners", scope,
                   detail=f"≤ {sink.hi:.3g} mA", defeaters=("D1", "D7"),
                   covers=("current_limits_ok",)),
            graded("dht.rail_current",
                   f"the idle rail stays within its {spec.budget:g} mA budget",
                   rail.hi <= spec.budget, "closed_form", scope.model_copy(update={"parameters": "nominal"}),
                   detail=f"{rail.nominal:.4g} mA, of which the MCU model is "
                          f"{mcu_rail_ma(spec.supply, spec.target.mcu_part):.0f} mA",
                   defeaters=("D1", "D2", "D7"), covers=("power_supply_adequate",)),
        ]

    # ── properties() ──────────────────────────────────────────────────────

    def properties(self, intent: IntentLike):
        """
        Stage 4. Both limits on the bus, from the netlist with a test bench:
        the cable's capacitance as a box, and DATA held low by a probe.
        """
        from proof.properties import BenchElement, PropertySpec, exact

        spec = _read(intent)
        pf = {w: bus_capacitance_pf(spec.cable, w) for w in ("min", "max")}
        bus = BenchElement(
            line=f"C_BUS dht22_data 0 {exact((pf['min'] + pf['max']) / 2, -12)}",
            describe="the DATA line's capacitance",
            label="DATA line capacitance",
            basis=f"both pins, plus {spec.cable:g} m of cable at "
                  f"{CABLE_PF_PER_M['min']:g}–{CABLE_PF_PER_M['max']:g} pF/m",
            lo=exact(pf["min"], -12), hi=exact(pf["max"], -12),
        )
        probe = BenchElement(line="V_PROBE dht22_data 0 DC 0",
                             describe="DATA held at 0 V (the MCU's start pulse, or the sensor's reply)")
        return [
            PropertySpec(id="dht.rise_time", label="DATA's 10–90 % rise time",
                         quantity="rise_time(dht22_data,C_BUS)", relation="le",
                         hi=exact(RISE_LIMIT_US, -6), units="s", bench=(bus,),
                         re_derives="dht.rise_time", datasheet_bound=True),
            PropertySpec(id="dht.sink_current", label="the current into whatever holds DATA low",
                         quantity="i(V_PROBE)", relation="le",
                         hi=exact(min(SINK_LIMIT_MA, mcu_sink_limit_ma(spec.target)), -3), units="A",
                         bench=(probe,), re_derives="dht.sink_current", datasheet_bound=True),
        ]

    # ── generate() ────────────────────────────────────────────────────────

    def generate(self, intent: IntentLike) -> CircuitIR:
        spec = _read(intent)
        r1 = select_pullup(spec)
        if r1 is None:
            raise ValueError("generate() called on an intent envelope() refuses")
        c_max = bus_capacitance_pf(spec.cable, "max")
        rise = rise_time_us(r1, c_max)
        if "R1" in spec.pins:
            r_reason = f"{r1:g}Ω, pinned by the requirement (constraints.pinned.R1)"
        elif r1 == DEFAULT_PULLUP_OHMS:
            r_reason = f"{r1:g}Ω, the Aosong datasheet value, fast enough for {spec.cable:g} m of cable"
        else:
            r_reason = (f"{r1:g}Ω, below the datasheet's 10 kΩ because {spec.cable:g} m of cable "
                        f"(up to {c_max:.0f} pF) would otherwise slow the edge past {RISE_LIMIT_US:g} µs")
        constraints: Dict[str, object] = {"supply_voltage": spec.supply,
                                          "supply_current_ma": spec.budget,
                                          "cable_length_m": spec.cable}
        if spec.threshold is not None:
            constraints["threshold_temp_celsius"] = spec.threshold
        target = spec.target
        where = "" if target.id == "arduino_uno" else f" on the {target.board}"
        board = "Arduino Uno" if target.id == "arduino_uno" else target.board
        rail = target.rail_node
        return CircuitIR(
            intent=f"DHT22 temperature/humidity node on {spec.pin}, {spec.cable:g} m sensor cable{where}",
            application_class=ApplicationClass.HOBBY_ARDUINO,
            target_mcu=target.id,
            components=[
                mcu(f"{board} MCU reading the DHT22 on {spec.pin}. The pin is bidirectional: "
                    f"it pulls DATA low for the start pulse, then listens.", target),
                Component(
                    id="U2", type=ComponentType.SENSOR, sensor_type="dht22", part_number=SENSOR_PART,
                    manufacturer="Aosong", package="4-pin SIP",
                    supply_voltage_min=_DHT["supply_voltage_min"], supply_voltage_max=_DHT["supply_voltage_max"],
                    current_draw_ma=_DHT["current_draw_ma"], operating_temp_min=-40, operating_temp_max=80,
                    confidence=0.92, lcsc_pn="C19528",
                    justification=(
                        f"DHT22: ±0.5 °C, ±2 %RH over a single-wire open-drain bus. It cannot be "
                        f"read faster than every {_DHT['min_sample_interval_ms'] / 1000:g} s, and "
                        f"without R1 its DATA line never goes high."
                    ),
                    datasheet_notes=list(_DHT["notes"]),
                ),
                Component(
                    id="R1", type=ComponentType.RESISTOR, part_number=resistor_part(r1),
                    manufacturer="Yageo", package="0402", value=value_string(r1),
                    supply_voltage_max=RESISTOR_VMAX, confidence=0.97,
                    justification=(
                        f"{r_reason}. Rise time ≈ {rise:.2g} µs worst case; halving R1 halves it but "
                        f"doubles the {sink_ma(spec.supply, r1):.2g} mA sunk while DATA is held low."
                    ),
                ),
                decoupling("U2", target.logic_v),
            ],
            nodes=[
                Node(id=rail, voltage_nominal=spec.supply, type=SignalType.POWER),
                Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
                Node(id="DHT22_DATA", type=SignalType.ONE_WIRE, protocol="dht_single_wire"),
            ],
            connections=[
                *power_connections(rail),
                Connection(component_id="U1", pin=spec.pin, node_id="DHT22_DATA", direction="bidirectional"),
                Connection(component_id="U2", pin="VCC", node_id=rail, direction="input"),
                Connection(component_id="U2", pin="GND", node_id="GND", direction="input"),
                Connection(component_id="U2", pin="DATA", node_id="DHT22_DATA", direction="output"),
                Connection(component_id="R1", pin="A", node_id=rail),
                Connection(component_id="R1", pin="B", node_id="DHT22_DATA"),
            ],
            constraints=constraints,
            simulation_spec=SimulationSpec(
                analyses=[SimulationAnalysis(type="dc_op", description="Idle rail and DATA pulled high")],
                expected_outputs={"DHT22_DATA": spec.supply},
            ),
            validation_rules=[ValidationRule.NO_FLOATING_NODES, ValidationRule.VOLTAGE_RATINGS_OK],
        )

    # ── CI grid and locality ──────────────────────────────────────────────

    def grid(self, board: Optional[str] = None) -> GridSpec:
        grid_target(board)   # the same cable lengths on every board
        return GridSpec(axes={"cable_length_m": [0.3, 5.0, 10.0, 15.0]},
                        units={"cable_length_m": "m"},
                        sections={"cable_length_m": "constraints"})

    def dependency_closure(self, requirement_path: str) -> FrozenSet[str]:
        closures: Dict[str, FrozenSet[str]] = {
            "constraints.cable_length_m": frozenset({"R1"}),
            "constraints.pinned": frozenset({"R1"}),
            "constraints.supply_current_ma": frozenset(),
            "preferences.alert_threshold_c": frozenset(),
            "preferences.data_pin": frozenset({"U1"}),
        }
        path = requirement_path
        while path:
            if path in closures:
                return closures[path]
            path = path.rpartition(".")[0]
        return frozenset({"U1", "U2", "R1", "C1"})
