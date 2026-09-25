"""
The bench sheet's RC method, checked on ngspice before anyone builds it — D1.

`docs/BENCH_D1.md` and `scripts/bench/rc_timer`: time a step response to two
thresholds k1·V and k2·V, then

    RC = (t2 − t1) / ln((1 − k1) / (1 − k2))

ngspice supplies the waveform; these tests check the arithmetic the sketch
does, that any fixed delay cancels, what the pin's output resistance adds, and
the error the comparator's offset can introduce. One model checking a method
is not a measurement: D1 stays open until a person measures
(`brain/decisions.md` [2026-09-25]).
"""

from __future__ import annotations

import itertools
import math

import pytest

from test_simulation_accuracy import _skip_no_ngspice

R_PIN, R1, C1, V = 25.0, 1590.0, 100e-9, 5.0      # the Uno pin (typical), IR_003's filter
K1, K2 = 1.0 / 3.0, 2.0 / 3.0
#: ATmega328P Table 30-1: analog comparator input offset, VCC = 5 V, V_in = VCC/2 — 40 mV maximum.
OFFSET_V = 0.040


def rc_from(t1: float, t2: float, k1: float = K1, k2: float = K2) -> float:
    """What rc_timer's run() computes."""
    return (t2 - t1) / math.log((1 - k1) / (1 - k2))


def _crossing(points, level):
    previous = None
    for t, v in points:
        if previous is not None and previous[1] < level <= v:
            t0, v0 = previous
            return t0 + (level - v0) * (t - t0) / (v - v0)
        previous = (t, v)
    raise AssertionError(f"the waveform never crosses {level} V")


def _step(r_pin: float = R_PIN):
    from simulation.parser import SpiceResultParser
    from simulation.runner import NgspiceRunner

    netlist = (f"* rc_timer: the drive pin steps IN; OUT charges\n"
               f"V1 drive 0 PULSE(0 {V} 1u 1n 1n 1 2)\n"
               f"R_PIN drive in {r_pin}\nR1 in out {R1}\nC1 out 0 {C1}\n"
               f".tran 0.05u 1m 0 0.05u\n.print tran v(out)\n.end\n")
    run = NgspiceRunner()._run_sync(netlist)
    parsed = SpiceResultParser().parse(run["stdout"], run["stderr"])
    points = [(t, values["out"]) for t, values in parsed.tran_points]
    assert len(points) > 1000, "no transient came back"
    return points


def test_a_fixed_delay_cancels_in_the_difference():
    # The port write, the comparator's propagation time and the noise canceller
    # add the same delay to both crossings.
    t1, t2 = 63.8e-6, 174.9e-6
    assert rc_from(t1 + 2.3e-6, t2 + 2.3e-6) == pytest.approx(rc_from(t1, t2), rel=1e-12)


@_skip_no_ngspice
class TestOnNgspice:
    def test_the_method_recovers_rc_with_the_pins_resistance_in_series(self):
        points = _step()
        measured = rc_from(_crossing(points, K1 * V), _crossing(points, K2 * V))
        assert measured == pytest.approx((R1 + R_PIN) * C1, rel=2e-3)
        # Left out, the pin's ~25 Ω reads as +1.6 % on a 1.59 kΩ R1 — the sheet's warning.
        assert measured / (R1 * C1) - 1 == pytest.approx(R_PIN / R1, rel=0.1)

    def test_the_comparator_offset_budget_the_sheet_states(self):
        # docs/BENCH_D1.md: "up to 5.2 %". Found by this test: the agent's first
        # estimate (about 2 %) assumed the offset had one sign at both thresholds.
        points = _step()
        true_rc = (R1 + R_PIN) * C1
        errors = {}
        for s1, s2 in itertools.product((-1, 1), repeat=2):
            t1 = _crossing(points, K1 * V + s1 * OFFSET_V)
            t2 = _crossing(points, K2 * V + s2 * OFFSET_V)
            errors[(s1, s2)] = abs(rc_from(t1, t2) / true_rc - 1)
        # One offset at both thresholds: they move the same way and mostly cancel.
        assert max(errors[(1, 1)], errors[(-1, -1)]) < 0.02
        # The datasheet bounds the offset, not its sign at each common-mode level:
        # opposite signs at 40 mV move RC by up to 5.2 % — inside the 15 % gate,
        # and what a record's accuracy must carry unless the offset is measured.
        worst = max(errors.values())
        assert 0.045 < worst < 0.055
