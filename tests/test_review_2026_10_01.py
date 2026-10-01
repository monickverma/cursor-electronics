"""
The pre-merge review of PR #2 — `brain/decisions.md` [2026-10-01]. One test (or
a few) per finding, each the reviewer's failing scenario turned around: it
failed before the fix and passes after. Findings #1–#4 are tested where their
code is tested (`test_sentry_key.py`, `test_pricing.py`, `frontend/e2e/bom.spec.ts`).
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from core.intent_ir import IntentIR, Producer, Provenance
from generators.netlist.spice import SpiceNetlistGenerator
from generators.realize import realize
from generators.registry import default_registry


def _intent(requirements):
    return IntentIR(requirements=json.loads(json.dumps(requirements)), provenance=Provenance(producer=Producer.FORM))


def _gen(name):
    return default_registry().by_name(name)


def _claims(generator, intent):
    return {c["id"]: c for c in realize(generator, intent).validation_coverage["claims"]}


DIVIDER = {"function": "voltage_divider", "targets": {"vout_v": 2.5}, "constraints": {"supply_v": 5.0}}
RC = {"function": "low_pass_filter", "targets": {"tolerance_pct": 5.0, "cutoff_hz": 15915.0},
      "constraints": {"supply_v": 5.0}}
LED = {"function": "led_indicator", "targets": {"led_current_ma": 2.0}, "constraints": {"mcu": "arduino_uno"}}
DHT = {"function": "temperature_humidity_sensor", "constraints": {"mcu": "arduino_uno", "cable_length_m": 0.3}}
RS485 = {"function": "modbus_rtu_master", "constraints": {"mcu": "arduino_uno", "supply_v": 5.0}}


def _with(base, *, pins=None, **constraints):
    req = json.loads(json.dumps(base))
    req.setdefault("constraints", {}).update(constraints)
    if pins:
        req["constraints"]["pinned"] = pins
    return req


# ── #16, #25: a placeholder is no name ───────────────────────────────────────

class TestPlaceholders:
    def test_a_verification_signed_with_the_placeholder_never_counts(self, tmp_path, monkeypatch):
        from data import figures as F

        fid = "RC0402FR/power_w"
        row = lambda by: (fid, F.record_hash(fid), by, "2026-10-01")  # noqa: E731
        assert F.verified(fid, [row("Ada Lovelace")])
        for placeholder in ("Your Name", " your name ", "<NAME>", ""):
            assert not F.verified(fid, [row(placeholder)]), placeholder
        store = tmp_path / "v.json"
        store.write_text(json.dumps({"verifications": [
            {"figure": fid, "record_hash": F.record_hash(fid), "by": "Your Name", "at": "2026-10-01"}]}),
            encoding="utf-8")
        monkeypatch.setenv("CIRCUITOS_FIGURE_VERIFICATIONS", str(store))
        assert F.verifications() == () and not F.trusted(fid)

    @pytest.mark.parametrize("who", ["your name", "Your Name", "", "   ", None])
    def test_a_bench_record_must_name_who_measured(self, who):
        from validation.bench import BenchRecord

        with pytest.raises(ValidationError):
            BenchRecord(id="x", measured_by=who, date="2026-10-01", generator="voltage_divider",
                        requirements={}, netlist_sha256="0" * 64, measures={})

    def test_the_template_cannot_be_saved_unfilled_and_still_load(self):
        from validation.bench import BenchRecord

        written = json.loads(open("docs/bench_templates/voltage_divider.json", encoding="utf-8").read())
        assert written["measured_by"] is None
        with pytest.raises(ValidationError):
            BenchRecord.model_validate(written)


# ── #18, #17, #5: bench evidence ─────────────────────────────────────────────

@pytest.fixture
def bench_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CIRCUITOS_BENCH_DIR", str(tmp_path))
    return tmp_path


def _record(generator, intent, measures, requirements=None, rid="bench-test"):
    from validation.bench import BenchRecord, netlist_hash

    circuit = generator.generate(intent)
    return BenchRecord(id=rid, measured_by="test", date="2026-10-01", generator=generator.name,
                       board=circuit.target_mcu, requirements=requirements or dict(intent.requirements),
                       netlist_sha256=netlist_hash(SpiceNetlistGenerator().generate(circuit)), measures=measures)


def _midpoint(generator, intent, pid):
    from validation.bench import Reading, predicted_interval

    spec = next(s for s in generator.properties(intent) if s.id == pid)
    lo, hi = predicted_interval(generator.generate(intent), spec, {})
    return Reading(value=(lo + hi) / 2, accuracy=(hi - lo) / 4, instrument="test meter")


class TestBench:
    def test_a_malformed_record_is_reported_not_raised(self, bench_dir):
        from validation.bench import evidence_for, invalid_records

        half = json.loads(open("docs/bench_templates/led_indicator.json", encoding="utf-8").read())
        (bench_dir / "half.json").write_text(json.dumps(half), encoding="utf-8")
        (bench_dir / "broken.json").write_text("{not json", encoding="utf-8")
        realize(_gen("voltage_divider"), _intent(DIVIDER))           # an unrelated family: no exception
        realize(_gen("led_indicator"), _intent(LED))                 # its own family: no exception either
        assert {i.file for i in invalid_records()} == {"half.json", "broken.json"}
        assert evidence_for("led_indicator", "arduino_uno", "any") == {}

    def test_a_record_reaches_only_a_design_with_its_requirements(self):
        from validation.bench import evidence_for, netlist_hash

        generator, intent = _gen("voltage_divider"), _intent(DIVIDER)
        record = _record(generator, intent, {"divider.vout": _midpoint(generator, intent, "divider.vout")})
        netlist = SpiceNetlistGenerator().generate(generator.generate(intent))
        assert netlist_hash(netlist) == record.netlist_sha256
        assert "divider.vout" in evidence_for(generator.name, None, netlist, intent.requirements, records=[record])
        other = {**intent.requirements, "preferences": {"note": "a different requirement, the same netlist"}}
        assert evidence_for(generator.name, None, netlist, other, records=[record]) == {}

    def test_rs485_far_end_on_does_not_reach_far_end_off(self, bench_dir):
        # The reviewer's case: the far-end terminator is a bench element, so the netlists match.
        generator = _gen("rs485_node")
        pins = {"R2": "523", "R3": "523"}
        on = _intent(_with(RS485, pins=pins, far_end_terminated=True))
        off = _intent(_with(RS485, pins=pins, far_end_terminated=False))
        net = lambda i: SpiceNetlistGenerator().generate(generator.generate(i))  # noqa: E731
        assert net(on) == net(off)
        record = _record(generator, on, {"rs485.failsafe_bias": _midpoint(generator, on, "rs485.failsafe_bias")})
        (bench_dir / "on.json").write_text(record.model_dump_json(), encoding="utf-8")
        assert "D1" not in _claims(generator, on)["proof.rs485.failsafe_bias"]["defeaters"]
        assert "D1" in _claims(generator, off)["proof.rs485.failsafe_bias"]["defeaters"]

    def test_a_claim_two_proofs_re_derive_keeps_d1_until_both_are_measured(self, bench_dir):
        generator, intent = _gen("voltage_divider"), _intent(DIVIDER)
        r1 = _midpoint(generator, intent, "divider.r1_power")
        (bench_dir / "r1.json").write_text(
            _record(generator, intent, {"divider.r1_power": r1}).model_dump_json(), encoding="utf-8")
        rows = _claims(generator, intent)
        assert "D1" not in rows["proof.divider.r1_power"]["defeaters"]
        assert "D1" in rows["proof.divider.r2_power"]["defeaters"]
        assert "D1" in rows["divider.resistor_dissipation"]["defeaters"]
        r2 = _midpoint(generator, intent, "divider.r2_power")
        (bench_dir / "r1.json").write_text(
            _record(generator, intent, {"divider.r1_power": r1, "divider.r2_power": r2}).model_dump_json(),
            encoding="utf-8")
        assert "D1" not in _claims(generator, intent)["divider.resistor_dissipation"]["defeaters"]


# ── #6: a singular system raises what callers catch ──────────────────────────

def test_the_domain_solver_raises_a_value_error_on_a_singular_system():
    import sympy

    from proof.mna import _domain_solve

    x = sympy.Symbol("x", positive=True)
    with pytest.raises(ValueError):
        _domain_solve(sympy.Matrix([[x, x], [x, x]]), sympy.Matrix([1, 2]))


# ── #7: a pull to the wrong rail is no hold ──────────────────────────────────

def test_a_pull_up_under_an_assumed_low_node_leaves_the_state_to_the_pin():
    from validation.claims import derive_mcu_models, held_to

    circuit = realize(_gen("rs485_node"), _intent(RS485))
    netlist = SpiceNetlistGenerator().generate(circuit)
    line = next(ln for ln in netlist.splitlines() if ln.startswith("R_R4 "))
    flipped = netlist.replace(line, f"R_R4 vcc_5v rs485_de_re {line.split()[3]}")
    measure = [("vdiff(rs485_a,rs485_b)", ())]
    assert held_to(circuit, netlist)["rs485_de_re"] == frozenset({"low"})
    assert held_to(circuit, flipped)["rs485_de_re"] == frozenset({"high"})
    assert derive_mcu_models(circuit, netlist, measure, ("RS485_DE_RE",)) == ("mcu_pin_load",)
    assert derive_mcu_models(circuit, flipped, measure, ("RS485_DE_RE",)) == ("mcu_pin_state",)
    assert derive_mcu_models(circuit, flipped, measure, ("RS485_DE_RE=high",)) == ("mcu_pin_load",)


# ── #8, #21: the pin rules read how the board routes UARTs ───────────────────

@pytest.mark.parametrize("board", ["arduino_uno", "esp32_devkitc", "blackpill_f411ce"])
def test_the_pin_rules_declare_uart_mode_where_a_uart_is_wired(board):
    rows = _claims(_gen("rs485_node"), _intent(_with(RS485, mcu=board, supply_v=5.0 if board == "arduino_uno"
                                                   else 3.3)))
    for rid in ("rule.pin_assignment_valid", "rule.peripheral_conflict_free"):
        if rid in rows:
            assert f"board:{board}/uart_mode" in rows[rid]["scope"]["figures"], rid
    led = _claims(_gen("led_indicator"), _intent(_with(LED, mcu=board)))
    assert f"board:{board}/uart_mode" not in led["rule.pin_assignment_valid"]["scope"]["figures"]


# ── #9, #22: R2, R3 and R4 are held to their ratings ─────────────────────────

class TestRS485Ratings:
    def test_an_r4_that_overheats_while_transmitting_is_refused(self):
        decision = _gen("rs485_node").envelope(_intent(_with(RS485, pins={"R4": "270"})))
        assert not decision.accepted and "R4" in decision.reason and "rating" in decision.reason

    def test_an_0402_bias_pair_that_overheats_is_refused(self):
        decision = _gen("rs485_node").envelope(_intent(_with(RS485, pins={"R2": "330", "R3": "330"})))
        assert not decision.accepted and "R2" in decision.reason and "62.5 mW" in decision.reason

    def test_a_lower_rated_substitute_for_the_bias_pair_does_not_surface(self):
        from generators.bom.substitution import substitutes

        generator = _gen("rs485_node")
        pins = {"R2": {"part": "RC0805FR-07330RL"}, "R3": {"part": "RC0805FR-07330RL"}}
        intent = _intent(_with(RS485, pins=pins))
        circuit = realize(generator, intent)
        rows = {c["id"]: c for c in circuit.validation_coverage["claims"]}
        assert rows["rs485.bias_dissipation"]["verdict"].startswith("holds")
        found, _ = substitutes(generator, intent, circuit)
        assert not [s for s in found if s.component_id in ("R2", "R3") and s.part_number.startswith("RC0402")]


# ── #10, #12, #13, #15: part pins ────────────────────────────────────────────

class TestPartPins:
    @pytest.mark.parametrize("part", ["RC0402FR-0710RL", "RC0402FR-071ML"])
    def test_a_part_pin_is_held_to_the_rc_series_window(self, part):
        decision = _gen("rc_lowpass").envelope(_intent(_with(RC, pins={"R1": {"part": part}})))
        assert not decision.accepted and "series window" in decision.reason

    @pytest.mark.parametrize("name,base", [("rc_lowpass", RC), ("voltage_divider", DIVIDER)])
    def test_a_code_with_two_unit_letters_is_refused_by_name(self, name, base):
        decision = _gen(name).envelope(_intent(_with(base, pins={"R1": {"part": "RC0402FR-071K2KL"}})))
        assert not decision.accepted and "RC0402FR-071K2KL" in decision.reason

    @pytest.mark.parametrize("part", ["RC0402JR-071K54L", "RC0402FR-0700001K54L"])
    def test_a_part_that_is_not_made_is_refused(self, part):
        decision = _gen("led_indicator").envelope(_intent(_with(LED, pins={"R1": {"part": part}})))
        assert not decision.accepted and part in decision.reason

    def test_a_refused_part_pin_names_its_slot(self):
        decision = _gen("voltage_divider").envelope(_intent(_with(DIVIDER, pins={"R2": {"part": "XYZ-123"}})))
        assert not decision.accepted and "constraints.pinned.R2" in decision.reason
        assert "constraints.pinned.part" not in decision.reason


# ── #11: predict() uses the pinned parts' own tolerance ──────────────────────

def test_the_divider_predicts_with_the_pinned_parts_tolerance():
    pins = {"R1": {"part": "RC0402JR-0710KL"}, "R2": {"part": "RC0402JR-0710KL"}}
    q = _gen("voltage_divider").predict(_intent(_with(DIVIDER, pins=pins))).quantities
    assert q["resistance_r1_ohm"].lo == pytest.approx(9500) and q["resistance_r2_ohm"].hi == pytest.approx(10500)
    assert q["output_impedance_ohm"].lo == pytest.approx(4750)


# ── #14, #24: the text names the tolerance it computed with ──────────────────

@pytest.mark.parametrize("name,base,pins,cid,says", [
    ("dht22_node", DHT, {"R1": {"part": "RC0402JR-0710KL"}}, "dht.rise_time", "R1 ±5%"),
    ("led_indicator", {**LED, "targets": {"led_current_ma": 5.0}}, {"R1": {"part": "RC0402JR-07560RL"}},
     "led.current_band", "every R1 within 5%"),
    ("rs485_node", RS485, {"R2": {"part": "RC0402JR-07510RL"}, "R3": {"part": "RC0402JR-07510RL"}},
     "rs485.failsafe_bias", "R1 within 1%, R2 within 5% and R3 within 5%"),
])
def test_claim_text_names_a_pinned_parts_own_tolerance(name, base, pins, cid, says):
    row = _claims(_gen(name), _intent(_with(base, pins=pins)))[cid]
    text = row["claim"] + " " + (row.get("detail") or "")
    assert says in text, text


# ── #19, #20: the far-end terminator's figures are declared ──────────────────

def test_the_far_end_terminators_figures_are_declared():
    rows = _claims(_gen("rs485_node"), _intent(_with(RS485, far_end_terminated=True)))
    assert "MAX485ECSA/requires_termination_ohm" in rows["rs485.rail_current"]["scope"]["figures"]
    for cid in ("rs485.failsafe_bias", "rs485.driver_load"):
        assert "RC0402FR/tolerance" in rows[cid]["scope"]["figures"], cid


# ── #23: an accepted design never fails its own rail claim ───────────────────

@pytest.mark.parametrize("name,base", [("dht22_node", DHT), ("led_indicator", LED), ("rs485_node", RS485)])
def test_a_rail_budget_the_design_exceeds_is_refused(name, base):
    decision = _gen(name).envelope(_intent(_with(base, supply_current_ma=5)))
    assert not decision.accepted and "budget" in decision.reason
