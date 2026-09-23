"""
Arduino Uno + MAX485 RS-485 Modbus RTU master — Stage 3, Phase 1 TPL_002.

    VCC ── R2 (bias) ──┬── RS485_A ──┐
                       R1 (term.)    MAX485 A/B ── bus ── far-end terminator
    GND ── R3 (bias) ──┴── RS485_B ──┘
    U1 D11 → DI,  D10 ← RO,  D2 → DE/RE   (SoftwareSerial, as the firmware uses)

**The claim this generator exists to make is fail-safe bias.** When every
driver on the bus is off, A and B float, and a receiver reading a floating
pair reports noise as data. The bias network holds the idle bus at

    V_AB = V_CC · R_eq / (R2 + R_eq + R3),   R_eq = R1 ∥ R_far

which must stay above the receivers' 200 mV threshold for every part in
tolerance. V_AB rises with R1 and R_far and falls with R2 and R3, so its band
is two opposite corners — G1. The same network loads the driver: TIA-485
specifies drivers into 54 Ω, and R_eq ∥ (R2 + R3) must not fall below it.

Bias selection picks the **largest** equal E96 pair (least idle current) that
keeps worst-case V_AB at least 25 % above threshold with the far end
terminated, as the requirement declares by default. The far-end terminator is
a bus condition, not a board part: `predict()` includes it, and in CI the grid
adapter attaches it to the netlist as a probe.

**The terminator is 1206, not 0402.** A driver can swing the pair by up to
V_CC; 5 V across 120 Ω is 208 mW, over three times an 0402's 62.5 mW. The
Phase 1 template used an 0402 there.

**Found building it:** Phase 1's `IR_005` wired the MAX485 to D0/D1 — the
hardware UART — while `modbus_master.ino.j2` drives it with SoftwareSerial on
D10/D11 (`brain/decisions.md` [2026-06-02]). The schematic and the firmware
disagreed about which pins carry the bus. This generator wires what the
firmware drives.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional

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
    worst_corners,
)
from generators.netlist.models import load_ohms, mcu_supply_model, mcu_supply_ohms
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

NAME = "rs485_node"
VERSION = "0.2.0"
FUNCTION = "modbus_rtu_master"

XCVR_PART = "MAX485ECSA"
_XCVR = get_constraints(XCVR_PART)
THRESHOLD_MV = float(_XCVR["receiver_threshold_mv"])
RATED_LOAD_OHM = float(_XCVR["driver_rated_load_ohm"])
TERMINATION_OHM = float(_XCVR["requires_termination_ohm"])
FAILSAFE_MARGIN = 1.25
#: RC1206FR — 1% thick film, 250 mW, 200 V.
TERMINATOR_PART = "RC1206FR-07120RL"
TERMINATOR_POWER_W = 0.25
#: What SoftwareSerial on a 16 MHz Uno receives reliably; 115200 does not.
BAUD_RATES = (1200, 2400, 4800, 9600, 19200, 38400, 57600)
#: A hardware UART (ESP32, STM32) adds 115200.
HARDWARE_BAUD_RATES = BAUD_RATES + (115200,)
#: The Uno pins modbus_master.ino.j2 drives; other boards' are in data/mcu_targets.py.
PIN_TX, PIN_RX, PIN_DE_RE = "D11", "D10", "D2"

#: Stage 5: a 3.3 V board takes the MAX3485. The bus figures are TIA-485's, not
#: the part's, so the thresholds above hold for both — checked, not assumed.
TRANSCEIVERS = {"arduino_uno": XCVR_PART, "esp32_devkitc": "MAX3485ECSA", "blackpill_f411ce": "MAX3485ECSA"}
for _part in set(TRANSCEIVERS.values()):
    _t = get_constraints(_part)
    assert (_t["receiver_threshold_mv"], _t["driver_rated_load_ohm"]) == (THRESHOLD_MV, RATED_LOAD_OHM), _part


def transceiver(target) -> tuple:
    part = TRANSCEIVERS[target.id]
    return part, get_constraints(part)


def baud_rates(target) -> tuple:
    return BAUD_RATES if target.rs485_uart is None else HARDWARE_BAUD_RATES
PINNABLE = ("R1", "R2", "R3")

DEFAULT_SLAVES = [
    {"address": 1, "register_start": 0, "register_count": 4, "name": "Device_1"},
]


class _Spec:
    __slots__ = ("supply", "far_end", "baud", "budget", "slaves", "poll_ms", "pins", "target")

    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


def _read(intent: IntentLike) -> _Spec:
    target = read_target(intent)
    supply = read_number(intent, "constraints", "supply_v", target.logic_v, allow_zero=False,
                         what="a rail voltage in volts")
    budget = read_number(intent, "constraints", "supply_current_ma", DEFAULT_RAIL_BUDGET_MA,
                         allow_zero=False, what="a rail budget in mA")
    baud = read_number(intent, "constraints", "baud", 9600, allow_zero=False,
                       what="a baud rate")
    constraints = requirements(intent).get("constraints") or {}
    far_end = constraints.get("far_end_terminated", True) if isinstance(constraints, Mapping) else True
    if not isinstance(far_end, bool):
        raise Unreadable(f"constraints.far_end_terminated={far_end!r} must be true or false")
    prefs = requirements(intent).get("preferences") or {}
    slaves = prefs.get("modbus_slaves", DEFAULT_SLAVES) if isinstance(prefs, Mapping) else DEFAULT_SLAVES
    if not isinstance(slaves, list) or not all(
        isinstance(s, Mapping) and isinstance(s.get("address"), int) and 1 <= s["address"] <= 247
        for s in slaves
    ) or not slaves:
        raise Unreadable("preferences.modbus_slaves must be a non-empty list of objects with a "
                         "Modbus address 1–247")
    poll = prefs.get("poll_interval_ms", 5000) if isinstance(prefs, Mapping) else 5000
    if isinstance(poll, bool) or not isinstance(poll, int) or poll < 100:
        raise Unreadable(f"preferences.poll_interval_ms={poll!r} must be an integer of at least 100")
    pins: Dict[str, float] = {}
    for part, raw in read_pins(intent, PINNABLE).items():
        ohms = pinned_number(raw, _parse_ohms)
        if ohms is None:
            raise Unreadable(f"constraints.pinned.{part}={raw!r} is not a resistance "
                             f"this system can read (e.g. '120', '560')")
        pins[part] = ohms
    return _Spec(supply=supply, far_end=far_end, baud=baud, budget=budget,
                 slaves=[dict(s) for s in slaves], poll_ms=poll, pins=pins, target=target)


def v_ab_mv(supply: float, r_term: float, r_up: float, r_down: float, r_far: Optional[float]) -> float:
    r_eq = r_term if r_far is None else r_term * r_far / (r_term + r_far)
    return supply * r_eq / (r_up + r_eq + r_down) * 1000.0


def bus_load_ohm(r_term: float, r_up: float, r_down: float, r_far: Optional[float]) -> float:
    r_eq = r_term if r_far is None else r_term * r_far / (r_term + r_far)
    return r_eq * (r_up + r_down) / (r_eq + r_up + r_down)


def _tol(r: float):
    return (r * (1 - RESISTOR_TOLERANCE), r * (1 + RESISTOR_TOLERANCE))


def _bands(spec: _Spec, r1: float, r2: float, r3: float):
    far = TERMINATION_OHM if spec.far_end else None
    far_box = _tol(far) if far else (None, None)

    def vab(t, u, d, f):
        return v_ab_mv(spec.supply, t, u, d, f)

    def load(t, u, d, f):
        return bus_load_ohm(t, u, d, f)

    boxes = [_tol(r1), _tol(r2), _tol(r3), far_box if far else (None,)]
    return (
        worst_corners(vab, boxes), vab(r1, r2, r3, far),
        worst_corners(load, boxes), load(r1, r2, r3, far),
    )


def select(spec: _Spec):
    """(R1, R2, R3). Largest equal bias pair meeting the fail-safe margin."""
    r1 = spec.pins.get("R1", TERMINATION_OHM)
    if "R2" in spec.pins or "R3" in spec.pins:
        r2 = spec.pins.get("R2", spec.pins.get("R3"))
        r3 = spec.pins.get("R3", spec.pins.get("R2"))
        return r1, r2, r3
    for bias in reversed(e96_values(100.0, 10_000.0)):
        (vlo, _), _, (llo, _), _ = _bands(spec, r1, bias, bias)
        if vlo >= THRESHOLD_MV * FAILSAFE_MARGIN and llo >= RATED_LOAD_OHM:
            return r1, bias, bias
    return None


class RS485NodeGenerator:
    """Uno + MAX485 + termination + fail-safe bias. Implements the Generator protocol."""

    name = NAME
    version = VERSION
    function = FUNCTION
    #: Stage 5: the boards it designs for; CI sweeps `grid(board)` on each.
    boards = BOARDS

    not_applicable_rules = {
        "pullup_on_open_drain": "no open-drain line: RS-485 is driven differentially, "
                                "and the bias network is its own rule (rs485_bias_resistors)",
    }

    # ── envelope() ────────────────────────────────────────────────────────

    def envelope(self, intent: IntentLike) -> EnvelopeDecision:
        function = (intent.requirements or {}).get("function")
        if function != FUNCTION:
            return EnvelopeDecision.refuse(
                f"function={function!r} is not modbus_rtu_master — this generator builds a "
                f"Modbus RTU master on one MAX485 (5 V) or MAX3485 (3.3 V)"
            )
        try:
            spec = _read(intent)
        except Unreadable as exc:
            return EnvelopeDecision.refuse(str(exc))
        part, xcvr = transceiver(spec.target)
        vmin, vmax = xcvr["supply_voltage_min"], xcvr["supply_voltage_max"]
        if not (vmin <= spec.supply <= vmax):
            hint = ("; a 3.3 V bus needs the MAX3485 on a 3.3 V board (constraints.mcu)"
                    if spec.target.id == "arduino_uno" else "")
            return EnvelopeDecision.refuse(
                f"supply_v={spec.supply:g} outside the {part.rstrip('ECSA')}'s {vmin:g}–{vmax:g} V{hint}"
            )
        rates = baud_rates(spec.target)
        if int(spec.baud) not in rates or spec.baud != int(spec.baud):
            why = ("the firmware uses SoftwareSerial, which a 16 MHz Uno cannot receive reliably "
                   "above 57600" if spec.target.rs485_uart is None else "these are the rates offered")
            return EnvelopeDecision.refuse(f"baud={spec.baud:g} is not one of {list(rates)} — {why}")
        chosen = select(spec)
        if chosen is None:
            return EnvelopeDecision.refuse(
                f"no bias pair keeps the idle bus {FAILSAFE_MARGIN:g}× above the "
                f"{THRESHOLD_MV:g} mV threshold while loading the driver no harder than "
                f"{RATED_LOAD_OHM:g} Ω"
            )
        (vlo, _), _, (llo, _), _ = _bands(spec, *chosen)
        if vlo < THRESHOLD_MV:
            return EnvelopeDecision.refuse(
                f"pinned bias gives an idle V_AB as low as {vlo:.0f} mV, under the receivers' "
                f"{THRESHOLD_MV:g} mV threshold — the idle bus would read as noise"
            )
        if llo < RATED_LOAD_OHM:
            return EnvelopeDecision.refuse(
                f"pinned parts load the driver down to {llo:.1f} Ω, below the {RATED_LOAD_OHM:g} Ω "
                f"it is specified into"
            )
        return EnvelopeDecision.accept((
            PortContract(name="VCC", direction="power", voltage_range_v=Interval.at(spec.supply, "V")),
            PortContract(name="RS485_A", direction="bidirectional"),
            PortContract(name="RS485_B", direction="bidirectional"),
            PortContract(name="GND", direction="ground"),
        ))

    def _rail_ma(self, spec: _Spec, r1: float, r2: float, r3: float) -> float:
        _, table = transceiver(spec.target)
        xcvr = load_ohms(table["current_draw_ma"], table["supply_voltage_max"])
        far = TERMINATION_OHM if spec.far_end else None
        r_eq = r1 if far is None else r1 * far / (r1 + far)
        bias = spec.supply / (r2 + r_eq + r3) * 1000.0
        return mcu_rail_ma(spec.supply, spec.target.mcu_part) + spec.supply / xcvr * 1000.0 + bias

    # ── predict() ─────────────────────────────────────────────────────────

    def predict(self, intent: IntentLike, box: Optional[Mapping[str, Interval]] = None) -> Prediction:
        decision = self.envelope(intent)
        if not decision.accepted:
            raise ValueError(f"predict() called on a refused intent: {decision.reason}")
        if box:
            raise ValueError("rs485_node's predict() takes no box; its band is the part tolerance")
        spec = _read(intent)
        r1, r2, r3 = select(spec)
        (vlo, vhi), vnom, (llo, lhi), lnom = _bands(spec, r1, r2, r3)
        term_lo, _ = _tol(r1)
        rail = self._rail_ma(spec, r1, r2, r3)
        term_worst = spec.supply ** 2 / term_lo * 1000.0
        return Prediction(
            quantities={
                "v_ab_idle_mv": Interval(lo=vlo, hi=vhi, nominal=vnom, units="mV"),
                "bus_load_ohm": Interval(lo=llo, hi=lhi, nominal=lnom, units="ohm"),
                "termination_power_mw": Interval(lo=0.0, hi=term_worst, nominal=term_worst, units="mW"),
                "supply_current_ma": Interval.at(rail, "mA"),
            },
            scope=ClaimScope(parameters="tolerance_box",
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
        vab, load, term, rail = (q["v_ab_idle_mv"], q["bus_load_ohm"],
                                 q["termination_power_mw"], q["supply_current_ma"])
        bus = "with the far end terminated" if spec.far_end else "with this end the only terminator"
        return [
            graded("rs485.failsafe_bias",
                   f"the idle bus holds V_AB above the receivers' {THRESHOLD_MV:g} mV threshold {bus}",
                   vab.lo >= THRESHOLD_MV, "monotone_corners", scope,
                   detail=f"V_AB ∈ [{vab.lo:.0f}, {vab.hi:.0f}] mV over every resistor within 1%",
                   defeaters=("D1", "D7")),
            graded("rs485.driver_load",
                   f"the driver sees no less than the {RATED_LOAD_OHM:g} Ω it is specified into",
                   load.lo >= RATED_LOAD_OHM, "monotone_corners", scope,
                   detail=f"{load.lo:.1f}–{load.hi:.1f} Ω", defeaters=("D1", "D7"),
                   covers=("current_limits_ok",)),
            graded("rs485.termination_dissipation",
                   f"R1 stays within its {TERMINATOR_POWER_W * 1000:g} mW rating with the pair "
                   f"driven to the full {spec.supply:g} V",
                   term.hi <= TERMINATOR_POWER_W * 1000, "monotone_corners", scope,
                   detail=f"≤ {term.hi:.0f} mW (an 0402 is rated 62.5 mW)", defeaters=("D1", "D7")),
            graded("rs485.rail_current",
                   f"the idle rail stays within its {spec.budget:g} mA budget",
                   rail.hi <= spec.budget, "closed_form", scope.model_copy(update={"parameters": "nominal"}),
                   detail=f"{rail.nominal:.4g} mA, of which the MCU model is "
                          f"{mcu_rail_ma(spec.supply, spec.target.mcu_part):.0f} mA",
                   defeaters=("D1", "D2", "D7"), covers=("power_supply_adequate",)),
        ]

    # ── properties() ──────────────────────────────────────────────────────

    def properties(self, intent: IntentLike):
        """
        Stage 4. Fail-safe bias and driver load on the idle bus, with the
        far-end terminator — a bus condition, not a board part — as a bench
        element in its own 1% box when the requirement declares it.
        """
        from proof.properties import BenchElement, PropertySpec, exact

        spec = _read(intent)
        bench = (BenchElement(
            line=f"R_FAR rs485_a rs485_b {exact(TERMINATION_OHM)}",
            describe=f"the far-end {TERMINATION_OHM:g} Ω terminator",
            label="far-end terminator",
            basis=f"{RESISTOR_TOLERANCE * 100:g}%, at the other end of the bus",
            tolerance=exact(RESISTOR_TOLERANCE),
        ),) if spec.far_end else ()
        return [
            PropertySpec(id="rs485.failsafe_bias", label="the idle bus voltage V(A) − V(B)",
                         quantity="vdiff(rs485_a,rs485_b)", relation="ge",
                         lo=exact(THRESHOLD_MV, -3), units="V", bench=bench,
                         re_derives="rs485.failsafe_bias", datasheet_bound=True),
            PropertySpec(id="rs485.driver_load", label="the resistance the driver sees across A–B",
                         quantity="rth(rs485_a,rs485_b)", relation="ge",
                         lo=exact(RATED_LOAD_OHM), units="ohm", bench=bench,
                         re_derives="rs485.driver_load", datasheet_bound=True),
        ]

    # ── generate() ────────────────────────────────────────────────────────

    def generate(self, intent: IntentLike) -> CircuitIR:
        spec = _read(intent)
        chosen = select(spec)
        if chosen is None:
            raise ValueError("generate() called on an intent envelope() refuses")
        r1, r2, r3 = chosen
        (vlo, _), vnom, _, _ = _bands(spec, r1, r2, r3)
        bias_note = ("pinned by the requirement (constraints.pinned)" if {"R2", "R3"} & set(spec.pins)
                     else f"the largest E96 value keeping idle V_AB ≥ {THRESHOLD_MV * FAILSAFE_MARGIN:g} mV "
                          f"over tolerance {'with' if spec.far_end else 'without'} a far-end terminator")

        def bias(part: str, value: float, to: str, line: str) -> Component:
            return Component(
                id=part, type=ComponentType.RESISTOR, part_number=resistor_part(value),
                manufacturer="Yageo", package="0402", value=value_string(value),
                supply_voltage_max=RESISTOR_VMAX, confidence=0.95,
                justification=(
                    f"{value:g}Ω fail-safe bias, {line} to {to}: {bias_note}. Idle V_AB is "
                    f"{vnom:.0f} mV nominal, {vlo:.0f} mV worst case; a larger value would let the "
                    f"idle bus sag toward the {THRESHOLD_MV:g} mV threshold, where receivers read noise."
                ),
            )

        slaves: List[Dict[str, Any]] = spec.slaves
        target = spec.target
        part, xcvr = transceiver(target)
        tx, rx, de = (target.defaults[k] for k in ("rs485_tx", "rs485_rx", "rs485_de"))
        rail = target.rail_node
        if target.rs485_uart is None:
            mcu_note = (f"Arduino Uno MCU as Modbus RTU master: SoftwareSerial TX on {tx}, RX on "
                        f"{rx}, direction on {de}. Hardware Serial (D0/D1) stays free for "
                        f"uploads and debugging.")
        else:
            mcu_note = (f"{target.board} MCU as Modbus RTU master: {target.rs485_uart} TX on {tx}, RX on "
                        f"{rx}, direction on {de}. The USB console stays on its own port.")
        if part == XCVR_PART:
            xcvr_note = (f"MAX485 half-duplex transceiver, DE and RE tied to {de}: high "
                         f"transmits, low listens. Its supply window is "
                         f"{xcvr['supply_voltage_min']:g}–{xcvr['supply_voltage_max']:g} V; a 3.3 V "
                         f"design needs the MAX3485 instead.")
        else:
            xcvr_note = (f"MAX3485 half-duplex transceiver at the board's 3.3 V logic, DE and RE tied to "
                         f"{de}: high transmits, low listens. The 5 V MAX485 would drive 5 V into the "
                         f"MCU's RX pin.")
        where = "" if target.id == "arduino_uno" else f" on the {target.board}"
        return CircuitIR(
            intent=f"Modbus RTU master on RS-485 at {int(spec.baud)} baud, {len(slaves)} slave(s){where}",
            application_class=ApplicationClass.MODBUS_RTU,
            target_mcu=target.id,
            components=[
                mcu(mcu_note, target),
                Component(
                    id="U2", type=ComponentType.TRANSCEIVER, part_number=part, manufacturer="Maxim",
                    package="SOIC-8", supply_voltage_min=xcvr["supply_voltage_min"],
                    supply_voltage_max=xcvr["supply_voltage_max"], current_draw_ma=xcvr["current_draw_ma"],
                    confidence=0.96, lcsc_pn="C6456" if part == XCVR_PART else None,
                    justification=xcvr_note,
                    datasheet_notes=list(xcvr["notes"]),
                ),
                Component(
                    id="R1", type=ComponentType.RESISTOR, part_number=TERMINATOR_PART, manufacturer="Yageo",
                    package="1206", value=value_string(r1), supply_voltage_max=200, confidence=0.97,
                    justification=(
                        f"{r1:g}Ω termination across A/B, matching the cable's 120 Ω impedance so edges "
                        f"do not reflect. 1206, not 0402: a driver can put {spec.supply:g} V across it "
                        f"({spec.supply ** 2 / r1 * 1000:.0f} mW), over three times an 0402's rating."
                    ),
                ),
                bias("R2", r2, "VCC", "A"),
                bias("R3", r3, "GND", "B"),
                decoupling("U2", target.logic_v),
            ],
            nodes=[
                Node(id=rail, voltage_nominal=spec.supply, type=SignalType.POWER),
                Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
                Node(id="UART_TX", type=SignalType.UART_TX, protocol="UART"),
                Node(id="UART_RX", type=SignalType.UART_RX, protocol="UART"),
                Node(id="RS485_DE_RE", type=SignalType.DIGITAL),
                Node(id="RS485_A", type=SignalType.RS485_A, protocol="RS485"),
                Node(id="RS485_B", type=SignalType.RS485_B, protocol="RS485"),
            ],
            connections=[
                *power_connections(rail),
                Connection(component_id="U1", pin=tx, node_id="UART_TX", direction="output"),
                Connection(component_id="U1", pin=rx, node_id="UART_RX", direction="input"),
                Connection(component_id="U1", pin=de, node_id="RS485_DE_RE", direction="output"),
                Connection(component_id="U2", pin="VCC", node_id=rail, direction="input"),
                Connection(component_id="U2", pin="GND", node_id="GND", direction="input"),
                Connection(component_id="U2", pin="DI", node_id="UART_TX", direction="input"),
                Connection(component_id="U2", pin="RO", node_id="UART_RX", direction="output"),
                Connection(component_id="U2", pin="DE", node_id="RS485_DE_RE", direction="input"),
                Connection(component_id="U2", pin="RE", node_id="RS485_DE_RE", direction="input"),
                Connection(component_id="U2", pin="A", node_id="RS485_A", direction="bidirectional"),
                Connection(component_id="U2", pin="B", node_id="RS485_B", direction="bidirectional"),
                Connection(component_id="R1", pin="A", node_id="RS485_A"),
                Connection(component_id="R1", pin="B", node_id="RS485_B"),
                Connection(component_id="R2", pin="A", node_id=rail),
                Connection(component_id="R2", pin="B", node_id="RS485_A"),
                Connection(component_id="R3", pin="A", node_id="RS485_B"),
                Connection(component_id="R3", pin="B", node_id="GND"),
            ],
            constraints={
                "supply_voltage": spec.supply,
                "supply_current_ma": spec.budget,
                "modbus_baud": int(spec.baud),
                "modbus_slaves": slaves,
                "poll_interval_ms": spec.poll_ms,
                "far_end_terminated": spec.far_end,
            },
            simulation_spec=SimulationSpec(
                analyses=[SimulationAnalysis(type="dc_op", description="Idle bus bias and rail current")],
                expected_outputs={rail: spec.supply},
            ),
            validation_rules=[
                ValidationRule.NO_FLOATING_NODES,
                ValidationRule.VOLTAGE_RATINGS_OK,
                ValidationRule.RS485_TERMINATION_PRESENT,
                ValidationRule.RS485_BIAS_RESISTORS,
            ],
        )

    # ── CI grid and locality ──────────────────────────────────────────────

    def grid(self, board: Optional[str] = None) -> GridSpec:
        # ±5 % about the board's logic rail: 4.75/5/5.25 V on the Uno (Phase 1's
        # grid), 3.135/3.3/3.465 V on a 3.3 V board with its MAX3485.
        rail = grid_target(board).logic_v
        return GridSpec(axes={"supply_v": [round(rail * k, 3) for k in (0.95, 1.0, 1.05)]},
                        units={"supply_v": "V"},
                        sections={"supply_v": "constraints"})

    def dependency_closure(self, requirement_path: str) -> FrozenSet[str]:
        closures: Dict[str, FrozenSet[str]] = {
            # R1 too: its justification states the dissipation at this supply.
            # Found by the Stage 3 locality sweep, which this closure first failed.
            "constraints.supply_v": frozenset({"R1", "R2", "R3"}),
            "constraints.far_end_terminated": frozenset({"R2", "R3"}),
            "constraints.pinned": frozenset({"R1", "R2", "R3"}),
            "constraints.baud": frozenset(),
            "constraints.supply_current_ma": frozenset(),
            "preferences": frozenset(),
        }
        path = requirement_path
        while path:
            if path in closures:
                return closures[path]
            path = path.rpartition(".")[0]
        return frozenset({"U1", "U2", "R1", "R2", "R3", "C1"})
