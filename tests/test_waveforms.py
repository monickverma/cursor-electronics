"""
Stage 3 — the waveform viewer's data path. `simulation/parser.py` (transient
tables) and `simulation/waveforms.py`.

Gate: *"Waveform viewer renders AC / transient / DC"* — empirical, G5. The
rendering itself is checked in a browser against these same shapes; what is
pinned here is that the data reaching it is real ngspice output, complete for
each analysis, bounded in size, and never invented.
"""

import math

import pytest

from core.ir_examples import IR_003, IR_004
from generators.netlist.spice import SpiceNetlistGenerator
from simulation.parser import SimulationData, SpiceResultParser
from simulation.waveforms import MAX_POINTS, waveforms_from
from test_simulation_accuracy import _skip_no_ngspice
from validation.grid_adapters import simulate

TRAN_STDOUT = """\
Index   time            v(in)           v(out)
--------------------------------------------------------------------------------
0\t0.000000e+00\t0.000000e+00\t0.000000e+00\t
1\t1.000000e-04\t5.000000e+00\t2.300000e+00\t
2\t2.000000e-04\t5.000000e+00\t3.500000e+00\t

                                  * page two
Index   time            v(in)           v(out)
--------------------------------------------------------------------------------
2\t2.000000e-04\t5.000000e+00\t3.500000e+00\t
3\t3.000000e-04\t5.000000e+00\t4.200000e+00\t
"""


class TestTransientParser:
    def test_rows_are_read_with_every_column(self):
        data = SpiceResultParser().parse(TRAN_STDOUT, "")
        assert [t for t, _ in data.tran_points] == [0.0, 1e-4, 2e-4, 3e-4]
        assert data.tran_points[-1][1] == {"in": 5.0, "out": 4.2}

    def test_a_repeated_page_does_not_duplicate_a_sample(self):
        data = SpiceResultParser().parse(TRAN_STDOUT, "")
        assert len(data.tran_points) == 4

    def test_a_dc_run_has_no_transient(self):
        data = SpiceResultParser().parse("\tNode  Voltage\n\t----  -------\n\tout   2.5\n", "")
        assert data.tran_points == []


class TestWaveforms:
    def test_shapes_all_three_analyses(self):
        data = SimulationData(
            dc_voltages={"out": 2.5, "bad": float("nan")},
            branch_currents={"v_vcc": -0.05},
            ac_points=[(10.0, {"out": 1.0}), (100.0, {"out": 0.7})],
            tran_points=[(0.0, {"out": 0.0}), (1e-3, {"out": 5.0})],
        )
        w = waveforms_from(data)
        assert w["dc"] == {"voltages": {"out": 2.5}, "currents": {"v_vcc": -0.05}}
        assert w["ac"] == {"x": [10.0, 100.0], "series": {"out": [1.0, 0.7]}}
        assert w["tran"] == {"x": [0.0, 1e-3], "series": {"out": [0.0, 5.0]}}

    def test_a_missing_sample_is_none_not_zero(self):
        # 0 V is a real reading; a gap must not be drawn as one.
        data = SimulationData(ac_points=[(1.0, {"a": 1.0, "b": 2.0}), (2.0, {"a": 0.5})])
        assert waveforms_from(data)["ac"]["series"]["b"] == [2.0, None]

    def test_long_sweeps_are_strided_and_keep_the_last_sample(self):
        points = [(float(i), {"v": float(i)}) for i in range(10_001)]
        w = waveforms_from(SimulationData(tran_points=points))
        assert len(w["tran"]["x"]) <= MAX_POINTS + 1
        assert w["tran"]["x"][0] == 0.0 and w["tran"]["x"][-1] == 10_000.0
        # Every kept point is a real sample, not an interpolation.
        assert all(x == v for x, v in zip(w["tran"]["x"], w["tran"]["series"]["v"]))

    def test_nothing_is_empty_data_not_an_error(self):
        w = waveforms_from(SimulationData())
        assert w["ac"] == {"x": [], "series": {}} and w["tran"] == {"x": [], "series": {}}


@_skip_no_ngspice
class TestFromRealRuns:
    def test_the_rc_filter_ac_sweep_rolls_off(self):
        w = waveforms_from(simulate(SpiceNetlistGenerator().generate(IR_003)))
        out = w["ac"]["series"]["out"]
        assert len(w["ac"]["x"]) > 50
        assert out[0] > 4.9 and out[-1] < 0.1    # passband ~5 V, stopband ~0

    def test_the_divider_dc_point_and_rail_current(self):
        w = waveforms_from(simulate(SpiceNetlistGenerator().generate(IR_004)))
        assert w["dc"]["voltages"]["vout_5v"] == pytest.approx(12 * 5.1 / 12.1, rel=1e-4)
        assert w["dc"]["currents"]["v_vin_12v"] == pytest.approx(-12 / 12_100, rel=1e-4)

    def test_a_transient_step_charges_the_capacitor(self):
        netlist = "\n".join([
            "* step", "V_IN in 0 PULSE(0 5 0 1n 1n 1 2)", "R_R1 in out 1590", "C_C1 out 0 100n",
            ".tran 20u 1m", ".print tran v(in) v(out)", ".end",
        ])
        w = waveforms_from(simulate(netlist))
        out = w["tran"]["series"]["out"]
        tau = 1590 * 100e-9
        assert out[-1] == pytest.approx(5 * (1 - math.exp(-1e-3 / tau)), rel=0.02)
