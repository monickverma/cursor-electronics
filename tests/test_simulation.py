"""
Week 4 — SPICE generator, parser, grader, and end-to-end simulation tests.

What is verified:
- _parse_ohms / _parse_farads: EIA value string parsing
- SpiceNetlistGenerator: correct SPICE elements, analysis commands, MCU resistor model
- SpiceResultParser: DC op columnar format, AC tabular format (no ngspice needed)
- SimulationGrader: 15% tolerance gate, AC cutoff-frequency lookup (no ngspice needed)
- End-to-end: voltage divider DC op and RC filter AC sweep (skipped if ngspice absent)
"""

import asyncio
import shutil

import pytest

from core.ir_examples import IR_001, IR_003, IR_004
from generators.netlist.spice import SpiceNetlistGenerator, _parse_farads, _parse_ohms
from simulation.grader import GradeResult, SimulationGrader
from simulation.parser import SimulationData, SpiceResultParser
from simulation.runner import NgspiceRunner


import os as _os
_ngspice_available = bool(
    shutil.which("ngspice")
    or shutil.which("ngspice_con")
    or _os.path.exists(r"C:\msys64\ucrt64\bin\ngspice_con.exe")
)
_skip_no_ngspice = pytest.mark.skipif(
    not _ngspice_available, reason="ngspice not installed"
)


# ── Value-string parsing ─────────────────────────────────────────────────────

class TestValueParsing:
    @pytest.mark.parametrize("value,expected", [
        ("120R",  120.0),
        ("10K",   10000.0),
        ("1K59",  1590.0),
        ("5K1",   5100.0),
        ("7K",    7000.0),
        ("560R",  560.0),
        ("150R",  150.0),
    ])
    def test_parse_ohms(self, value, expected):
        assert _parse_ohms(value) == pytest.approx(expected, rel=0.001)

    def test_parse_ohms_rejects_capacitor_value(self):
        assert _parse_ohms("100nF") is None

    @pytest.mark.parametrize("value,expected", [
        ("100nF", 100e-9),
        ("1nF",   1e-9),
        ("10uF",  10e-6),
        ("100n",  100e-9),
        ("1pF",   1e-12),
    ])
    def test_parse_farads(self, value, expected):
        assert _parse_farads(value) == pytest.approx(expected, rel=0.001)


# ── SPICE netlist generator ──────────────────────────────────────────────────

class TestSpiceNetlistGenerator:
    def test_rc_filter_has_resistor_element(self):
        assert "R_R1" in SpiceNetlistGenerator().generate(IR_003)

    def test_rc_filter_has_capacitor_element(self):
        assert "C_C1" in SpiceNetlistGenerator().generate(IR_003)

    def test_rc_filter_has_ac_analysis_command(self):
        assert ".ac" in SpiceNetlistGenerator().generate(IR_003).lower()

    def test_rc_filter_ends_with_end(self):
        assert SpiceNetlistGenerator().generate(IR_003).strip().endswith(".end")

    def test_voltage_divider_has_dc_op(self):
        assert ".op" in SpiceNetlistGenerator().generate(IR_004)

    def test_voltage_divider_r1_value_is_7kohm(self):
        assert "7000" in SpiceNetlistGenerator().generate(IR_004)

    def test_voltage_divider_r2_value_is_5100ohm(self):
        assert "5100" in SpiceNetlistGenerator().generate(IR_004)

    def test_voltage_divider_has_12v_source(self):
        netlist = SpiceNetlistGenerator().generate(IR_004)
        assert "12.0" in netlist

    def test_rc_filter_capacitor_100nf_in_scientific_notation(self):
        netlist = SpiceNetlistGenerator().generate(IR_003)
        # 100nF = 1e-07 F; Python formats this as "1e-07"
        assert "1e-07" in netlist or "1.0e-07" in netlist

    def test_rc_filter_has_print_ac_directive(self):
        netlist = SpiceNetlistGenerator().generate(IR_003)
        assert ".print ac" in netlist.lower()

    def test_mcu_modeled_as_100ohm_resistor_not_voltage_source(self):
        netlist = SpiceNetlistGenerator().generate(IR_001)
        assert "R_MCU_U1" in netlist
        assert "VMCU_U1" not in netlist

    def test_gnd_node_mapped_to_spice_node_zero(self):
        netlist = SpiceNetlistGenerator().generate(IR_003)
        # C_C1 minus pin → GND → should be " 0 " in the C element line
        c1_line = next(l for l in netlist.splitlines() if l.startswith("C_C1"))
        assert " 0 " in c1_line or c1_line.endswith(" 0")

    def test_r_values_correct_for_rc_filter(self):
        netlist = SpiceNetlistGenerator().generate(IR_003)
        r1_line = next(l for l in netlist.splitlines() if l.startswith("R_R1"))
        # R1 = "1k59" → 1590Ω
        assert "1590" in r1_line


# ── Parser (unit tests — no ngspice required) ────────────────────────────────

class TestSpiceResultParser:
    # DC op output from ngspice .op — columnar Node/Voltage table
    _DC_SAMPLE = """\

              Node                    Voltage
              ----                    -------
v(vin_12v)              1.20000e+01
v(vout_5v)              5.07000e+00
v(gnd)                  0.00000e+00
"""

    # AC sweep output from .print ac v(out)
    # Real ngspice -b -o output: Index  frequency  v(out)  (complex, tab-separated)
    # v(out) at 1kHz: real=2.5024, imag=-2.5000  → magnitude = 3.5355V (-3dB)
    _AC_SAMPLE = """\
Index   frequency       v(out)
--------------------------------------------------------------------------------
0\t1.000000e+01\t4.999501e+00,\t-4.99463e-02\t
1\t1.000000e+02\t4.997500e+00,\t-4.99900e-01\t
2\t1.000000e+03\t2.502435e+00,\t-2.50000e+00\t
3\t1.000000e+04\t4.997500e-02,\t-4.99900e-01\t
"""

    def test_parse_dc_op_extracts_vin_voltage(self):
        data = SpiceResultParser().parse(self._DC_SAMPLE, "")
        assert data.dc_voltages["vin_12v"] == pytest.approx(12.0, rel=0.001)

    def test_parse_dc_op_extracts_vout_voltage(self):
        data = SpiceResultParser().parse(self._DC_SAMPLE, "")
        assert data.dc_voltages["vout_5v"] == pytest.approx(5.07, rel=0.001)

    def test_parse_ac_returns_four_frequency_points(self):
        data = SpiceResultParser().parse(self._AC_SAMPLE, "")
        assert len(data.ac_points) == 4

    def test_parse_ac_has_point_at_1khz(self):
        data = SpiceResultParser().parse(self._AC_SAMPLE, "")
        freqs = [f for f, _ in data.ac_points]
        assert any(abs(f - 1000.0) < 1.0 for f in freqs)

    def test_parse_ac_value_at_1khz_is_minus_3db(self):
        data = SpiceResultParser().parse(self._AC_SAMPLE, "")
        _, vals = next((f, v) for f, v in data.ac_points if abs(f - 1000.0) < 1.0)
        assert vals["out"] == pytest.approx(3.535534, rel=0.001)

    def test_raw_fields_stored(self):
        data = SpiceResultParser().parse("stdout_content", "stderr_content")
        assert data.raw_stdout == "stdout_content"
        assert data.raw_stderr == "stderr_content"


# ── Grader (unit tests — no ngspice required) ────────────────────────────────

class TestSimulationGrader:
    def test_exact_match_passes(self):
        data = SimulationData(dc_voltages={"vout_5v": 5.07})
        assert SimulationGrader().grade(IR_004, data).passed

    def test_within_15_percent_passes(self):
        # 4.5V vs 5.07V → 11.2% error → within 15% ✓
        data = SimulationData(dc_voltages={"vout_5v": 4.5})
        assert SimulationGrader().grade(IR_004, data).passed

    def test_outside_15_percent_fails(self):
        # 4.0V vs 5.07V → 21.1% error → outside 15%
        data = SimulationData(dc_voltages={"vout_5v": 4.0})
        result = SimulationGrader().grade(IR_004, data)
        assert not result.passed
        assert any("VOUT_5V" in f for f in result.failures)

    def test_missing_node_fails(self):
        data = SimulationData(dc_voltages={})
        assert not SimulationGrader().grade(IR_004, data).passed

    def test_no_simulation_spec_passes(self):
        ir_no_spec = IR_004.model_copy(update={"simulation_spec": None})
        assert SimulationGrader().grade(ir_no_spec, SimulationData()).passed

    def test_ac_grading_at_cutoff_frequency_passes(self):
        # Correct RC filter: out = 3.536V at 1kHz (within 15% of expected 3.536)
        ac_points = [
            (10.0,    {"out": 5.0}),
            (100.0,   {"out": 5.0}),
            (1000.0,  {"out": 3.536}),
            (10000.0, {"out": 0.5}),
        ]
        data = SimulationData(ac_points=ac_points)
        assert SimulationGrader().grade(IR_003, data).passed

    def test_ac_wrong_output_at_cutoff_fails(self):
        # Wrong capacitor: at 1kHz output stays at 5V instead of 3.536V
        ac_points = [
            (10.0,   {"out": 5.0}),
            (1000.0, {"out": 5.0}),   # 5V vs expected 3.536V → 41% error
        ]
        data = SimulationData(ac_points=ac_points)
        assert not SimulationGrader().grade(IR_003, data).passed


# ── End-to-end (skipped if ngspice not installed) ────────────────────────────

@_skip_no_ngspice
class TestEndToEndSimulation:
    def _run(self, ir):
        netlist = SpiceNetlistGenerator().generate(ir)
        result = asyncio.run(NgspiceRunner().run(netlist))
        return SpiceResultParser().parse(result["stdout"], result["stderr"])

    def test_voltage_divider_dc_op_passes(self):
        data = self._run(IR_004)
        result = SimulationGrader().grade(IR_004, data)
        assert result.passed, f"Voltage divider failed: {result.failures}"

    def test_rc_filter_ac_sweep_passes(self):
        data = self._run(IR_003)
        result = SimulationGrader().grade(IR_003, data)
        assert result.passed, f"RC filter failed: {result.failures}"

    def test_rc_filter_wrong_capacitor_fails(self):
        # C1 = 1nF → cutoff ~100kHz; at 1kHz, output ≈ 5V (well above expected 3.536V)
        modified = [
            c.model_copy(update={"value": "1nF"}) if c.id == "C1" else c
            for c in IR_003.components
        ]
        wrong_ir = IR_003.model_copy(update={"components": modified})
        data = self._run(wrong_ir)
        result = SimulationGrader().grade(wrong_ir, data)
        assert not result.passed, "Wrong capacitor should fail simulation grading"
