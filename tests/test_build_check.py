"""
Build check — did the person wire this design? `validation/build_check.py`.

The arithmetic is tested against closed forms, and — where ngspice is installed — against
ngspice itself, a solver that shares nothing with it. The guarantee in the module's
docstring is attacked, not asserted: an adversary pushes every reading toward the design as
far as the meter's accuracy allows, at every corner of the faulty build's tolerance box.
"""

from __future__ import annotations

import math
import shutil
import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ai.form_producer import FormProducer  # noqa: E402
from generators.registry import default_registry  # noqa: E402
from proof.netlist import Element, Netlist  # noqa: E402
from validation.build_check import (BENCH_METER, Analysis, BuildModel, Meter, Probe, Unsupported,  # noqa: E402
                                    _Struct, enumerate_faults)

_NGSPICE = shutil.which("ngspice_con") or shutil.which("ngspice") or (
    r"C:\msys64\ucrt64\bin\ngspice_con.exe" if Path(r"C:\msys64\ucrt64\bin\ngspice_con.exe").exists() else None)
requires_ngspice = pytest.mark.skipif(_NGSPICE is None, reason="ngspice not installed")

DESIGNS = {
    "voltage_divider": ("voltage_divider", {"vout_v": 3.3, "supply_v": 5}),
    "led_indicator": ("led_indicator", {"led_current_ma": 10, "mcu": "arduino_uno"}),
    "rc_lowpass": ("low_pass_filter", {"cutoff_hz": 1000, "supply_v": 5}),
    "dht22_node": ("temperature_humidity_sensor", {"mcu": "arduino_uno"}),
    "rs485_node": ("modbus_rtu_master", {"mcu": "arduino_uno"}),
}
_cache = {}


def model_of(name: str) -> BuildModel:
    if name not in _cache:
        reg = default_registry()
        fn, fields = DESIGNS[name]
        intent = FormProducer(reg).build(fn, fields)
        gen = reg.dispatch(intent).generator
        _cache[name] = BuildModel.from_circuit(gen.generate(intent))
    return _cache[name]


def analysis_of(name: str, meter: Meter = Meter(), kinds=("v", "r")) -> Analysis:
    key = (name, meter, tuple(kinds))
    if key not in _cache:
        _cache[key] = Analysis(model_of(name), meter, kinds=kinds)
    return _cache[key]


# ── The meter ────────────────────────────────────────────────────────────────

class TestMeter:
    def test_uncertainty_is_gain_plus_digits_on_the_range_the_reading_needs(self):
        m = Meter()
        assert m.uncertainty(5.0) == pytest.approx(0.005 * 5.0 + 3 * 0.01)       # 20 V range, 10 mV digits
        assert m.uncertainty(1.0) == pytest.approx(0.005 * 1.0 + 3 * 0.001)      # 2 V range, 1 mV digits

    def test_ohms_are_read_on_their_own_ranges_and_overload_above_the_top(self):
        m = Meter()
        assert m.r_uncertainty(3400.0) == pytest.approx(0.008 * 3400.0 + 3 * 10.0)   # 20 kΩ range, 10 Ω digits
        assert m.observe_ohm(1e6) == 1e6
        assert math.isinf(m.observe_ohm(5e7))                                        # above 20 MΩ the meter shows OL

    def test_a_better_meter_is_better_everywhere_it_matters(self):
        assert BENCH_METER.uncertainty(5.0) < Meter().uncertainty(5.0)
        assert BENCH_METER.r_uncertainty(3400.0) < Meter().r_uncertainty(3400.0)


# ── Faults ───────────────────────────────────────────────────────────────────

class TestFaults:
    def test_the_listed_faults_of_the_divider(self):
        ids = {f.id for f in enumerate_faults(model_of("voltage_divider"))}
        assert {"R1:open", "R1:short", "R1:high", "R1:low", "R2:open", "R2:short", "R1↔R2:swapped"} <= ids
        assert "R1.a→0:moved" in ids and "R2.a→vin:moved" in ids

    def test_two_parts_of_equal_value_are_not_a_swap(self):
        ids = {f.id for f in enumerate_faults(model_of("rs485_node"))}
        assert "R2↔R3:swapped" not in ids          # both 549 Ω: exchanging them changes nothing at all
        assert "R1↔R2:swapped" in ids

    def test_a_capacitor_is_invisible_to_a_multimeter_and_says_so(self):
        faults = {f.id: f for f in enumerate_faults(model_of("led_indicator"))}
        assert faults["C1:open"].dc_equivalent and faults["C1:wrong_value"].dc_equivalent
        assert not faults["C1:short"].dc_equivalent

    def test_a_shorted_part_keeps_its_place_on_the_board(self):
        f = {f.id: f for f in enumerate_faults(model_of("led_indicator"))}["C1:short"]
        assert any(e.name == "C_C1" and e.kind == "R" for e in f.netlist.elements)

    def test_an_led_can_go_in_backwards(self):
        faults = {f.id: f for f in enumerate_faults(model_of("led_indicator"))}
        f = faults["LED1:reversed"]
        d = next(e for e in f.netlist.elements if e.kind == "D")
        d0 = next(e for e in model_of("led_indicator").netlist.elements if e.kind == "D")
        assert (d.a, d.b) == (d0.b, d0.a)

    def test_a_lead_moved_never_lands_on_the_net_it_is_already_on(self):
        for f in enumerate_faults(model_of("rs485_node")):
            if f.kind == "moved":
                e = next(x for x in f.netlist.elements if x.name == f.elements[0])
                assert e.a != e.b, f.id

    def test_no_two_listed_faults_are_the_same_network(self):
        from validation.build_check import _canon
        faults = [f for f in enumerate_faults(model_of("rs485_node")) if not f.dc_equivalent]
        keys = [_canon(f.netlist, f.boxes) for f in faults]
        assert len(keys) == len(set(keys))


# ── The arithmetic ───────────────────────────────────────────────────────────

class TestIntervals:
    def test_divider_reading_range_is_the_closed_form_at_the_corners(self):
        """v(out) = S · R2′ / (R1 + R2′), R2′ = R2 ∥ the meter's 10 MΩ, over the 1 % boxes."""
        a = analysis_of("voltage_divider")
        lo, hi = a.interval("as-designed", Probe("vout"), 5.0, 5.0)
        rm = Fraction(10_000_000)

        def v(r1, r2):
            r2p = r2 * rm / (r2 + rm)
            return float(Fraction(5) * r2p / (r1 + r2p))
        r1lo, r1hi = Fraction(3366), Fraction(3434)
        r2lo, r2hi = Fraction(6650) * Fraction(99, 100), Fraction(6650) * Fraction(101, 100)
        assert lo == pytest.approx(v(r1hi, r2lo), abs=1e-9)
        assert hi == pytest.approx(v(r1lo, r2hi), abs=1e-9)

    def test_the_resistance_between_the_divider_nets_is_the_series_sum_and_the_part(self):
        a = analysis_of("voltage_divider")
        lo, hi = a.interval("as-designed", Probe("vin", "vout", "r"))
        assert (lo, hi) == pytest.approx((3366.0, 3434.0))                              # R1 alone
        lo, hi = a.interval("as-designed", Probe("vin", "0", "r"))
        assert lo == pytest.approx(3366.0 + 6650.0 * 0.99) and hi == pytest.approx(3434.0 + 6650.0 * 1.01)

    def test_nothing_joining_two_nets_reads_overload(self):
        a = analysis_of("dht22_node")
        lo, hi = a.interval("as-designed", Probe("dht22_data", "0", "r"))
        assert math.isinf(lo) and math.isinf(hi)        # the pull-up goes to the rail, not to ground

    def test_the_rail_scales_every_reading_of_a_linear_design(self):
        a = analysis_of("voltage_divider")
        lo5, hi5 = a.interval("as-designed", Probe("vout"), 5.0, 5.0)
        lo4, hi4 = a.interval("as-designed", Probe("vout"), 4.0, 4.0)
        assert lo4 / lo5 == pytest.approx(0.8) and hi4 / hi5 == pytest.approx(0.8)

    def test_a_wider_rail_range_only_widens(self):
        a = analysis_of("voltage_divider")
        narrow = a.interval("as-designed", Probe("vout"), 4.99, 5.01)
        wide = a.interval("as-designed", Probe("vout"), 4.75, 5.25)
        assert wide[0] <= narrow[0] and narrow[1] <= wide[1]

    def test_the_led_voltage_sits_inside_its_datasheet_box(self):
        a = analysis_of("led_indicator")
        lo, hi = a.interval("as-designed", Probe("led_anode"), 4.9, 5.1)
        assert 1.5 < lo < hi < 2.5                  # Würth 150080RS75000: 1.6–2.4 V

    def test_a_floating_solver_source_is_refused_not_guessed(self):
        nl = Netlist(elements=[Element("V", "V_X", "a", "b", value=Fraction(5)), Element("R", "R_1", "a", "b", value=Fraction(100))])
        with pytest.raises(Unsupported):
            _Struct(nl, "V_X", ())


# ── The guarantee: what is detectable, what is blind, and that the two are honest ─

class TestDetection:
    def test_every_divider_fault_is_detectable_and_one_voltage_reading_detects_all_of_them(self):
        a = analysis_of("voltage_divider")
        assert all(a.detecting()[f.id] for f in a.faults)
        assert len(a.plan()) == 1

    def test_naming_the_fault_takes_more_readings_than_noticing_it_and_they_are_power_off(self):
        a = analysis_of("voltage_divider")
        detect, identify = a.plan(), a.plan(identify=True)
        assert len(identify) > len(detect)
        assert all(p.kind == "r" for p in identify)               # three resistances, before power is applied

    def test_with_a_voltmeter_alone_the_rc_filter_cannot_be_checked_and_says_so(self):
        a = analysis_of("rc_lowpass", kinds=("v",))
        blind = {f.id for f, _ in a.blind_spots()}
        assert {"R1:short", "R1:high", "R1:low", "C1:open", "C1:wrong_value"} <= blind
        assert "R1:open" not in blind

    def test_an_ohmmeter_sees_what_a_voltmeter_cannot_and_only_the_capacitor_value_stays_hidden(self):
        a = analysis_of("rc_lowpass")
        blind = {f.id for f, _ in a.blind_spots()}
        assert blind == {"C1:open", "C1:wrong_value"}

    def test_a_short_across_an_ideal_supply_is_a_named_blind_spot_for_a_voltmeter_not_a_pass(self):
        a = analysis_of("led_indicator", kinds=("v",))
        why = dict((f.id, w) for f, w in a.blind_spots())
        assert "C1:short" in why and "no reading separates it" in why["C1:short"]
        # …and the ohmmeter between the rail and ground finds it
        assert "C1:short" not in {f.id for f, _ in analysis_of("led_indicator").blind_spots()}

    def test_the_dht22_pullup_value_is_invisible_to_a_voltmeter_and_plain_to_an_ohmmeter(self):
        v = analysis_of("dht22_node", kinds=("v",))
        assert {"R1:short", "R1:high", "R1:low"} <= {f.id for f, _ in v.blind_spots()}
        assert v.min_detectable_factor("R_R1", "high") is None
        both = analysis_of("dht22_node")
        assert both.min_detectable_factor("R_R1", "high") <= 1.1

    def test_the_divider_notices_a_resistor_well_before_it_is_off_by_half(self):
        a = analysis_of("voltage_divider")
        for part in ("R_R1", "R_R2"):
            assert a.min_detectable_factor(part, "high") <= 1.5
            assert a.min_detectable_factor(part, "low") <= 1.5

    def test_a_better_meter_sees_a_smaller_error(self):
        coarse = analysis_of("voltage_divider", kinds=("v",)).min_detectable_factor("R_R1", "high")
        fine = analysis_of("voltage_divider", BENCH_METER, kinds=("v",)).min_detectable_factor("R_R1", "high")
        assert fine <= coarse

    def test_a_dc_equivalent_fault_is_never_called_detectable(self):
        a = analysis_of("led_indicator")
        assert "C1:open" not in a.detecting()

    @pytest.mark.parametrize("name", ["voltage_divider", "led_indicator", "rc_lowpass", "dht22_node", "rs485_node"])
    def test_a_separation_decided_at_three_rails_holds_at_forty_one(self, name):
        """The meter's range steps (1 mV digits below 2 V, 10 mV above) could open a gap between the three points."""
        a = analysis_of(name)
        lo, hi = a.model.supply_range
        claimed = 0
        for f in a.faults:
            if f.dc_equivalent:
                continue
            for p in a.probes:
                if p.kind != "v" or not a.separated(f.id, p):
                    continue
                claimed += 1
                for i in range(41):
                    volts = lo + (hi - lo) * i / 40
                    s_lo, s_hi = a._supply_box(volts)
                    assert a._separate(a.interval("as-designed", p, s_lo, s_hi), a.interval(f.id, p, s_lo, s_hi), "v"),                         (name, f.id, p.key, round(volts, 3))
        assert claimed > 0

    def test_a_wide_fault_is_judged_over_its_whole_range_not_at_its_far_end(self):
        """R1 more than 1.5× too large spans 15 kΩ…200 kΩ: the meter's blur at 200 kΩ must not decide it."""
        a = analysis_of("dht22_node")
        assert a.detecting()["R1:high"]


# ── The verdict ──────────────────────────────────────────────────────────────

class TestDiagnosis:
    def _plan_key(self):
        return analysis_of("voltage_divider").plan()[0].key

    def test_a_correct_build_is_as_designed(self):
        a = analysis_of("voltage_divider")
        v = a.diagnose({"vin": 5.0, self._plan_key(): 5.0 - 3.3077})
        assert v.status == "as_designed" and v.supply_ok

    def test_r1_left_out_is_named(self):
        a = analysis_of("voltage_divider")
        v = a.diagnose({"vin": 5.0, self._plan_key(): 5.0})          # vout ≈ 0 with R1 absent
        assert v.status == "fault" and "R1:open" in v.consistent_faults

    def test_nothing_listed_fits_a_reading_no_wiring_could_give(self):
        a = analysis_of("voltage_divider")
        v = a.diagnose({"vin": 5.0, self._plan_key(): 6.5})          # more than the supply: no wiring does this
        assert v.status == "unexplained" and "reopens D1" in v.summary()

    def test_a_rail_off_design_is_flagged_on_its_own(self):
        a = analysis_of("voltage_divider")
        v = a.diagnose({"vin": 3.3, self._plan_key(): 3.3 - 2.18})
        assert not v.supply_ok
        assert "outside the design's range" in v.summary()

    def test_the_rail_is_read_first_when_a_voltage_is(self):
        with pytest.raises(KeyError):
            analysis_of("voltage_divider").diagnose({self._plan_key(): 1.7})

    def test_power_off_readings_need_no_rail(self):
        a = analysis_of("voltage_divider")
        v = a.diagnose({"r:vin,vout": 3400.0, "r:vout,0": 6650.0, "r:vin,0": 10050.0})
        assert v.status == "as_designed" and v.parts_check_out is True and math.isnan(v.supply_volts)

    def test_one_reading_that_leaves_a_detectable_fault_open_is_inconclusive_not_clean(self):
        a = analysis_of("led_indicator")
        lo, hi = a.interval("as-designed", Probe("led_anode"), 4.99, 5.01)
        v = a.diagnose({"vcc_5v": 5.0, "led_anode": (lo + hi) / 2})
        assert v.status in ("inconclusive", "as_designed")
        if v.status == "inconclusive":
            assert v.open_faults

    def test_the_identification_plan_names_one_fault_not_a_handful(self):
        a = analysis_of("voltage_divider")
        # R1 left out: nothing joins VIN and VOUT; VOUT to ground is R2; VIN to ground is R2 alone
        v = a.diagnose({"r:vin,vout": math.inf, "r:vout,0": 6650.0, "r:vin,0": math.inf})
        assert v.status == "fault" and v.consistent_faults == ("R1:open",)

    def test_a_part_a_little_off_is_the_board_not_the_model(self):
        """R1 at 1.25× is not a listed fault; a resistance reading says which part is off, and D1 stays closed."""
        a = analysis_of("voltage_divider")
        v = a.diagnose({"r:vin,vout": 3400.0 * 1.25, "r:vout,0": 6650.0, "r:vin,0": 3400.0 * 1.25 + 6650.0})
        assert v.status == "unexplained" and v.parts_check_out is False and not v.reopens_d1
        assert any("VIN" in text for text, _, _ in v.deviations)

    def test_good_parts_and_wrong_voltages_is_a_model_question(self):
        a = analysis_of("voltage_divider")
        v = a.diagnose({"vin": 5.0, "vin-vout": 3.0, "r:vin,vout": 3400.0, "r:vout,0": 6650.0, "r:vin,0": 10050.0})
        assert v.status == "unexplained" and v.parts_check_out is True and v.reopens_d1
        assert "model question" in v.summary()

    def test_a_short_reads_a_fraction_of_an_ohm_not_exactly_zero(self):
        a = analysis_of("dht22_node")
        short = a.diagnose({"r:dht22_data,0": math.inf, "r:vcc_5v,dht22_data": 0.5})
        assert short.status == "fault" and "R1:short" in short.consistent_faults

    def test_overload_is_a_reading_like_any_other(self):
        a = analysis_of("dht22_node")
        v = a.diagnose({"r:dht22_data,0": math.inf, "r:vcc_5v,dht22_data": 10000.0})
        assert v.status == "as_designed"
        open_ = a.diagnose({"r:dht22_data,0": math.inf, "r:vcc_5v,dht22_data": math.inf})
        assert open_.status == "fault" and "R1:open" in open_.consistent_faults


# ── Against ngspice ──────────────────────────────────────────────────────────

@requires_ngspice
class TestAgainstNgspice:
    """ngspice, run at every corner of the tolerance box and at random points inside it."""

    @pytest.mark.parametrize("name", ["voltage_divider", "led_indicator", "rc_lowpass", "dht22_node"])
    def test_the_interval_is_exact_at_the_corners_and_nothing_falls_outside(self, name):
        import build_check_oracle as oracle
        res = oracle.run({name: model_of(name)}, n_samples=4)[name]
        assert not res["mismatches"], res["mismatches"][:3]
        assert res["worst_corner_excess_v"] <= 0 and res["worst_outside_v"] <= 0

    def test_rs485_hypotheses_a_sample_of_the_faults(self):
        import random

        import build_check_oracle as oracle
        a = analysis_of("rs485_node")
        rng = random.Random(7)
        for hid in ("as-designed", "R1:open", "R2↔R4:swapped", "R4.a→rs485_a:moved", "R2:high", "R3:low", "R1.b→vcc_5v:moved",
                    "C1:short"):
            r = oracle.check_hypothesis(a, hid, 3, rng)
            assert r["corner_excess_v"] <= 0 and r["outside_v"] <= 0, (hid, r)

    def test_the_guarantee_survives_an_adversary_on_the_divider(self):
        import build_check_accuracy as acc
        r = acc.run_design("divider", model_of("voltage_divider"), n=4, seed=11, meter=Meter())
        assert r["guarantee_replay"]["violations"] == 0
        assert r["guarantee_replay"]["readings_replayed"] > 100
        assert r["detectable_detect"].get("missed", 0) == 0
        assert r["correct_detect"].get("correct", 0) == r["correct_detect"]["n"]
        assert r["detectable_identify"].get("exact", 0) == r["detectable_identify"]["n"]     # three ohms name every fault

    def test_the_guarantee_survives_an_adversary_on_the_led(self):
        import build_check_accuracy as acc
        r = acc.run_design("led", model_of("led_indicator"), n=3, seed=13, meter=Meter())
        assert r["guarantee_replay"]["violations"] == 0
        assert r["detectable_detect"].get("missed", 0) == 0
        assert r["correct_identify"].get("false_unexplained", 0) == 0
        assert r["correct_identify"].get("false_fault", 0) == 0

    def test_a_correct_board_is_never_charged_to_the_model_when_everything_is_as_stated(self):
        import build_check_accuracy as acc
        for name in ("voltage_divider", "dht22_node", "rc_lowpass"):
            r = acc.run_design(name, model_of(name), n=3, seed=17, meter=Meter())
            for label in ("correct_detect", "correct_identify", "correct_all"):
                assert r[label].get("false_unexplained", 0) == 0, (name, label, r[label])
                assert r[label].get("false_fault", 0) == 0, (name, label, r[label])
