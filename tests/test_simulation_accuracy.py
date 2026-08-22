"""Criterion 11 — simulation accuracy via closed-form analytical cross-check.

Replaces the physical bench test (oscilloscope + function generator). Decision
recorded 2026-08-07 in `.claude/shared-memory/brain/decisions.md`: no lab access
is available and none is expected.

WHAT THIS VALIDATES
    The SPICE netlist emitted by `SpiceNetlistGenerator`, compared against
    closed-form circuit equations at 2% tolerance. That is the failure mode
    criterion 11 actually guards against — a netlist generator that emits
    plausible-looking but wrong SPICE. ngspice itself is a mature, independently
    validated simulator; the risk lives in the code written here.

WHAT THIS DOES NOT VALIDATE
    Physical reality. It cannot catch parasitic capacitance, breadboard contact
    resistance, ground-loop effects, or a component behaving outside its
    datasheet. Criterion 11 is therefore `met_by_substitute`, NOT `met`. The
    public claim is "simulates before it ships" — that claim is still owed a
    physical measurement. When lab access appears, run the bench test and
    upgrade the criterion. Do not let `met_by_substitute` quietly become `met`.

WHY 2% AND NOT 15%
    The 15% gate in `SimulationGrader` exists to absorb real component tolerance
    (±5% resistors, ±10% capacitors) on a physical bench. There is no physical
    component here — both sides of the comparison are mathematics. Anything
    beyond a couple of percent is a bug in the netlist generator, not
    measurement noise. A loose gate on an exact comparison tests nothing.

COVERAGE
    Six R/C pairs with cutoffs spanning 100 Hz to 100 kHz, each swept two
    decades either side of cutoff. A single 1 kHz point would pass on a
    generator with a decade-scaling bug.
"""

import asyncio
import math
import os
import shutil
from typing import Dict, List, Optional, Tuple

import pytest

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
from generators.netlist.spice import SpiceNetlistGenerator, _parse_farads, _parse_ohms
from simulation.parser import SimulationData
from simulation.parser import SpiceResultParser
from simulation.runner import NgspiceRunner


_ngspice_available = bool(
    shutil.which("ngspice")
    or shutil.which("ngspice_con")
    or os.path.exists(r"C:\msys64\ucrt64\bin\ngspice_con.exe")
)
_skip_no_ngspice = pytest.mark.skipif(
    not _ngspice_available, reason="ngspice not installed"
)

# The analytical gate. See module docstring for why this is 2% and not 15%.
TOLERANCE = 0.02

VIN = 5.0


# ── Closed-form references ───────────────────────────────────────────────────

def rc_cutoff_hz(ohms: float, farads: float) -> float:
    """f_c = 1 / (2·pi·R·C)"""
    return 1.0 / (2.0 * math.pi * ohms * farads)


def rc_lowpass_magnitude(vin: float, freq_hz: float, f_cutoff: float) -> float:
    """|Vout| = Vin / sqrt(1 + (f/f_c)^2) — single-pole RC low-pass."""
    return vin / math.sqrt(1.0 + (freq_hz / f_cutoff) ** 2)


def divider_vout(vin: float, r_top: float, r_bottom: float) -> float:
    """Vout = Vin · R2 / (R1 + R2)"""
    return vin * r_bottom / (r_top + r_bottom)


# ── IR builders ──────────────────────────────────────────────────────────────
#
# Built through the real schema and compiled by the real generator. The point of
# this file is to test SpiceNetlistGenerator, so a hand-written netlist here
# would test nothing.

def make_rc_lowpass_ir(r_value: str, c_value: str, f_start: float, f_stop: float) -> CircuitIR:
    return CircuitIR(
        intent=f"RC low-pass filter accuracy case: R={r_value}, C={c_value}",
        application_class=ApplicationClass.HOBBY_ARDUINO,
        components=[
            Component(
                id="R1", type=ComponentType.RESISTOR,
                part_number="ACCURACY-TEST-R", manufacturer="Analytical", package="0402",
                value=r_value, supply_voltage_max=50, confidence=1.0,
                justification="Series resistor of the RC low-pass under analytical test.",
            ),
            Component(
                id="C1", type=ComponentType.CAPACITOR,
                part_number="ACCURACY-TEST-C", manufacturer="Analytical", package="0402",
                value=c_value, supply_voltage_max=16, confidence=1.0,
                justification="Shunt capacitor of the RC low-pass under analytical test.",
            ),
        ],
        nodes=[
            Node(id="IN", voltage_nominal=VIN, type=SignalType.ANALOG),
            Node(id="OUT", type=SignalType.ANALOG),
            Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
        ],
        connections=[
            Connection(component_id="R1", pin="A", node_id="IN"),
            Connection(component_id="R1", pin="B", node_id="OUT"),
            Connection(component_id="C1", pin="+", node_id="OUT"),
            Connection(component_id="C1", pin="-", node_id="GND"),
        ],
        constraints={"supply_voltage": VIN},
        simulation_spec=SimulationSpec(
            analyses=[
                SimulationAnalysis(
                    type="ac_sweep",
                    description="Analytical cross-check of the transfer function",
                    f_start=f_start, f_stop=f_stop, points_per_decade=20,
                )
            ],
        ),
        validation_rules=[ValidationRule.NO_FLOATING_NODES],
    )


def make_divider_ir(vin: float, r_top: str, r_bottom: str) -> CircuitIR:
    return CircuitIR(
        intent=f"Voltage divider accuracy case: {vin}V through {r_top}/{r_bottom}",
        application_class=ApplicationClass.HOBBY_ARDUINO,
        components=[
            Component(
                id="R1", type=ComponentType.RESISTOR,
                part_number="ACCURACY-TEST-R1", manufacturer="Analytical", package="0402",
                value=r_top, supply_voltage_max=50, confidence=1.0,
                justification="Upper resistor of the divider under analytical test.",
            ),
            Component(
                id="R2", type=ComponentType.RESISTOR,
                part_number="ACCURACY-TEST-R2", manufacturer="Analytical", package="0402",
                value=r_bottom, supply_voltage_max=50, confidence=1.0,
                justification="Lower resistor of the divider under analytical test.",
            ),
        ],
        nodes=[
            Node(id="VIN", voltage_nominal=vin, type=SignalType.POWER),
            Node(id="VOUT", type=SignalType.ANALOG),
            Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
        ],
        connections=[
            Connection(component_id="R1", pin="A", node_id="VIN"),
            Connection(component_id="R1", pin="B", node_id="VOUT"),
            Connection(component_id="R2", pin="A", node_id="VOUT"),
            Connection(component_id="R2", pin="B", node_id="GND"),
        ],
        constraints={"supply_voltage": vin},
        simulation_spec=SimulationSpec(
            analyses=[SimulationAnalysis(type="dc_op", description="Analytical cross-check")],
        ),
        validation_rules=[ValidationRule.NO_FLOATING_NODES],
    )


# ── Harness ──────────────────────────────────────────────────────────────────

def run_ir(ir: CircuitIR) -> SimulationData:
    netlist = SpiceNetlistGenerator().generate(ir)
    result = asyncio.run(NgspiceRunner().run(netlist))
    data = SpiceResultParser().parse(result["stdout"], result["stderr"])
    assert data.ac_points or data.dc_voltages, (
        "ngspice produced no parseable output. Netlist was:\n" + netlist
    )
    return data


def interpolate_cutoff(points: List[Tuple[float, Dict[str, float]]],
                       node: str, target: float) -> Optional[float]:
    """Log-interpolate the frequency at which |V(node)| crosses `target`.

    The sweep is logarithmic, so the crossing almost never lands exactly on a
    sample point. Interpolating in log-frequency is the correct reading of a
    decade sweep; interpolating linearly would bias the answer high.
    """
    series = [(f, v[node]) for f, v in points if node in v]
    for (f_lo, m_lo), (f_hi, m_hi) in zip(series, series[1:]):
        if m_lo >= target >= m_hi and m_lo != m_hi:
            frac = (m_lo - target) / (m_lo - m_hi)
            return 10 ** (math.log10(f_lo) + frac * (math.log10(f_hi) - math.log10(f_lo)))
    return None


# R/C pairs chosen so cutoffs span three decades. Value strings are the EIA
# forms the AI layer actually emits, so this exercises the value parsers too.
RC_CASES = [
    ("15k9", "100n"),   # ~100 Hz
    ("4k7",  "100n"),   # ~339 Hz
    ("1k59", "100n"),   # ~1 kHz — the shipping IR_003 design
    ("1k59", "10n"),    # ~10 kHz
    ("10k",  "1n"),     # ~15.9 kHz
    ("159",  "10n"),    # ~100 kHz
]

DIVIDER_CASES = [
    (12.0, "7k",   "5k1"),   # the shipping IR_004 design
    (5.0,  "10k",  "10k"),   # exact halving
    (12.0, "10k",  "2k2"),
    (3.3,  "1k",   "2k"),
    (24.0, "20k",  "4k7"),
]


# ── Value parsers agree with the arithmetic this file asserts ────────────────
#
# If a value string parses to something other than intended, every downstream
# assertion would compare ngspice against the wrong closed-form number and could
# pass while the circuit is wrong. Pin the parsers first.

class TestValueStringsUnderTest:
    @pytest.mark.parametrize("value,expected_ohms", [
        ("15k9", 15900.0), ("4k7", 4700.0), ("1k59", 1590.0),
        ("10k", 10000.0), ("159", 159.0), ("7k", 7000.0),
        ("5k1", 5100.0), ("2k2", 2200.0), ("1k", 1000.0),
        ("2k", 2000.0), ("20k", 20000.0),
    ])
    def test_resistor_strings(self, value, expected_ohms):
        assert _parse_ohms(value) == pytest.approx(expected_ohms, rel=1e-9)

    @pytest.mark.parametrize("value,expected_farads", [
        ("100n", 100e-9), ("10n", 10e-9), ("1n", 1e-9),
    ])
    def test_capacitor_strings(self, value, expected_farads):
        assert _parse_farads(value) == pytest.approx(expected_farads, rel=1e-9)


# ── RC low-pass ──────────────────────────────────────────────────────────────

@_skip_no_ngspice
class TestRCLowPassAccuracy:
    """Compare the simulated transfer function against 1/sqrt(1+(f/fc)^2)."""

    @pytest.mark.slow
    @pytest.mark.parametrize("r_value,c_value", RC_CASES)
    def test_magnitude_matches_closed_form_across_sweep(self, r_value, c_value):
        ohms, farads = _parse_ohms(r_value), _parse_farads(c_value)
        f_c = rc_cutoff_hz(ohms, farads)

        ir = make_rc_lowpass_ir(r_value, c_value, f_c / 100.0, f_c * 100.0)
        points = run_ir(ir).ac_points
        assert points, f"No AC points returned for R={r_value} C={c_value}"

        worst_err, worst_f = 0.0, 0.0
        checked = 0
        for freq, values in points:
            if "out" not in values:
                continue
            expected = rc_lowpass_magnitude(VIN, freq, f_c)
            err = abs(values["out"] - expected) / expected
            if err > worst_err:
                worst_err, worst_f = err, freq
            checked += 1

        # 4 decades at 20 points/decade = 81 samples.
        assert checked >= 80, f"Expected a dense sweep, only got {checked} points"
        assert worst_err <= TOLERANCE, (
            f"R={r_value} C={c_value} (f_c={f_c:.2f}Hz): worst deviation "
            f"{worst_err * 100:.3f}% at {worst_f:.2f}Hz exceeds the "
            f"{TOLERANCE * 100:.0f}% analytical gate. This is a netlist "
            f"generator bug, not measurement noise."
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("r_value,c_value", RC_CASES)
    def test_cutoff_frequency_matches_closed_form(self, r_value, c_value):
        """The -3dB point lands where 1/(2·pi·R·C) says it should."""
        ohms, farads = _parse_ohms(r_value), _parse_farads(c_value)
        f_c = rc_cutoff_hz(ohms, farads)

        ir = make_rc_lowpass_ir(r_value, c_value, f_c / 100.0, f_c * 100.0)
        points = run_ir(ir).ac_points

        measured = interpolate_cutoff(points, "out", VIN / math.sqrt(2.0))
        assert measured is not None, (
            f"Sweep never crossed -3dB for R={r_value} C={c_value}"
        )
        err = abs(measured - f_c) / f_c
        assert err <= TOLERANCE, (
            f"R={r_value} C={c_value}: measured cutoff {measured:.2f}Hz vs "
            f"closed-form {f_c:.2f}Hz — {err * 100:.3f}% off"
        )

    @pytest.mark.slow
    def test_magnitude_at_cutoff_is_minus_3db(self):
        """At f_c exactly, the output is Vin/sqrt(2), i.e. -3.01 dB.

        A decade sweep starts on f_start, so anchoring f_start to the computed
        cutoff puts a sample exactly on f_c. Reading the nearest point of a
        wider sweep instead would measure the sweep's grid, not the circuit.
        """
        f_c = rc_cutoff_hz(_parse_ohms("1k59"), _parse_farads("100n"))
        ir = make_rc_lowpass_ir("1k59", "100n", f_c, f_c * 2.0)
        points = run_ir(ir).ac_points

        freq, values = points[0]
        assert freq == pytest.approx(f_c, rel=1e-6), (
            f"Expected first sample on f_c={f_c:.4f}Hz, got {freq:.4f}Hz"
        )

        measured = values["out"]
        assert measured == pytest.approx(VIN / math.sqrt(2.0), rel=TOLERANCE)

        db = 20.0 * math.log10(measured / VIN)
        assert db == pytest.approx(-3.01, abs=0.05), f"Got {db:.4f} dB at cutoff"


# ── Voltage divider ──────────────────────────────────────────────────────────

@_skip_no_ngspice
class TestVoltageDividerAccuracy:
    @pytest.mark.slow
    @pytest.mark.parametrize("vin,r_top,r_bottom", DIVIDER_CASES)
    def test_dc_output_matches_closed_form(self, vin, r_top, r_bottom):
        expected = divider_vout(vin, _parse_ohms(r_top), _parse_ohms(r_bottom))

        data = run_ir(make_divider_ir(vin, r_top, r_bottom))
        assert "vout" in data.dc_voltages, (
            f"No vout in DC results: {sorted(data.dc_voltages)}"
        )
        measured = data.dc_voltages["vout"]
        err = abs(measured - expected) / expected
        assert err <= TOLERANCE, (
            f"{vin}V through {r_top}/{r_bottom}: ngspice {measured:.6f}V vs "
            f"closed-form {expected:.6f}V — {err * 100:.3f}% off"
        )


# ── Negative control ─────────────────────────────────────────────────────────
#
# A gate that only ever passes is worth nothing. These assert the harness above
# would actually catch a wrong netlist — the same reasoning as criterion 4.

@_skip_no_ngspice
class TestHarnessRejectsWrongValues:
    @pytest.mark.slow
    def test_wrong_capacitor_decade_is_caught(self):
        """C off by a decade must blow the 2% gate, not squeak through it."""
        f_c_claimed = rc_cutoff_hz(_parse_ohms("1k59"), _parse_farads("100n"))

        # Built with 10n but measured against the 100n closed-form.
        ir = make_rc_lowpass_ir("1k59", "10n", f_c_claimed / 100.0, f_c_claimed * 100.0)
        points = run_ir(ir).ac_points

        worst = max(
            abs(v["out"] - rc_lowpass_magnitude(VIN, f, f_c_claimed))
            / rc_lowpass_magnitude(VIN, f, f_c_claimed)
            for f, v in points if "out" in v
        )
        assert worst > TOLERANCE, (
            "A capacitor wrong by a decade slipped through the analytical gate — "
            "the gate is not measuring what it claims to measure."
        )

    @pytest.mark.slow
    def test_wrong_divider_ratio_is_caught(self):
        wrong_expected = divider_vout(12.0, _parse_ohms("7k"), _parse_ohms("5k1"))
        data = run_ir(make_divider_ir(12.0, "10k", "2k2"))
        measured = data.dc_voltages["vout"]
        err = abs(measured - wrong_expected) / wrong_expected
        assert err > TOLERANCE, (
            "A divider with the wrong ratio passed the analytical gate."
        )
