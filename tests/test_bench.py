"""
D1 — bench evidence, closable one design at a time. `validation/bench.py`;
`brain/decisions.md` [2026-09-24] D1, D2, D7.

A record agrees when the measured interval overlaps the model's interval for
the parts as measured; it reaches its own design only; a disagreement reopens
D1 for the whole family and fails this file until explained.
"""

from __future__ import annotations

import json

import pytest

from core.intent_ir import IntentIR, Producer, Provenance
from generators.netlist.spice import SpiceNetlistGenerator
from generators.protocol import grid_of
from generators.realize import realize
from validation.bench import BenchRecord, Reading, evaluate, evidence_for, load_records, netlist_hash, predicted_interval
from validation.grid_adapters import ADAPTERS


def _design(name, board=None):
    adapter = ADAPTERS[name].build(board)
    req = json.loads(json.dumps(dict(adapter.intent_for(next(iter(grid_of(adapter.generator, board).points())))
                                     .requirements)))
    intent = IntentIR(requirements=req, provenance=Provenance(producer=Producer.FORM))
    return adapter.generator, intent, realize(adapter.generator, intent)


def _value(circuit, cid):
    return float(next(c.value for c in circuit.components if c.id == cid))


def _record(name, measures, parts=None, board=None, netlist_sha=None, rid="bench-test"):
    generator, intent, circuit = _design(name, board)
    return BenchRecord(
        id=rid, measured_by="test", date="2026-09-25", generator=generator.name, board=board,
        requirements=dict(intent.requirements),
        netlist_sha256=netlist_sha or netlist_hash(SpiceNetlistGenerator().generate(circuit)),
        parts=parts or {}, measures=measures,
    )


@pytest.fixture
def bench_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CIRCUITOS_BENCH_DIR", str(tmp_path))

    def put(*records):
        for r in records:
            (tmp_path / f"{r.id}.json").write_text(r.model_dump_json(indent=1), encoding="utf-8")
    return put


def _meter(value, accuracy):
    return Reading(value=value, accuracy=accuracy, instrument="test meter")


# ── The model's interval for the parts as measured ───────────────────────────

class TestPredictedInterval:
    def test_with_nothing_measured_it_is_the_designs_own_band(self):
        generator, intent, circuit = _design("voltage_divider")
        spec = next(s for s in generator.properties(intent) if s.id == "divider.vout")
        band = generator.predict(intent).quantities["vout_v"]
        lo, hi = predicted_interval(circuit, spec, {})
        assert lo == pytest.approx(band.lo, rel=1e-9) and hi == pytest.approx(band.hi, rel=1e-9)

    def test_measured_parts_narrow_it_to_what_was_built(self):
        generator, intent, circuit = _design("voltage_divider")
        spec = next(s for s in generator.properties(intent) if s.id == "divider.vout")
        r1, r2 = _value(circuit, "R1"), _value(circuit, "R2")
        lo, hi = predicted_interval(circuit, spec, {"R1": _meter(r1, 1e-6), "R2": _meter(r2, 1e-6)})
        assert hi - lo < 1e-5 and lo <= generator.predict(intent).quantities["vout_v"].nominal <= hi

    def test_a_measured_supply_moves_the_prediction(self):
        # The bench rail is never exactly the requirement's; it is measured too.
        generator, intent, circuit = _design("voltage_divider")
        spec = next(s for s in generator.properties(intent) if s.id == "divider.vout")
        supply = intent.requirements["constraints"]["supply_v"]
        at_req = predicted_interval(circuit, spec, {"VIN": _meter(supply, 1e-9)})
        low = predicted_interval(circuit, spec, {"VIN": _meter(supply * 0.98, 1e-9)})
        assert low[1] == pytest.approx(at_req[1] * 0.98, rel=1e-6)

    def test_the_rc_cutoff_and_the_led_current_evaluate(self):
        generator, intent, circuit = _design("rc_lowpass")
        spec = next(s for s in generator.properties(intent) if s.id == "rc.cutoff")
        band = generator.predict(intent).quantities["cutoff_hz"]
        lo, hi = predicted_interval(circuit, spec, {})
        assert lo <= band.nominal <= hi
        generator, intent, circuit = _design("led_indicator", "arduino_uno")
        spec = next(s for s in generator.properties(intent) if s.id == "led.current")
        lo, hi = predicted_interval(circuit, spec, {})
        assert lo <= generator.predict(intent).quantities["led_current_ma"].nominal / 1000 <= hi


# ── Findings and their reach ─────────────────────────────────────────────────

class TestFindings:
    def test_an_agreeing_measurement_agrees(self):
        generator, intent, circuit = _design("voltage_divider")
        nominal = generator.predict(intent).quantities["vout_v"].nominal
        (finding,) = evaluate(_record("voltage_divider", {"divider.vout": _meter(nominal, 0.005)}))
        assert finding.status == "agrees"

    def test_a_measurement_outside_the_model_disagrees(self):
        generator, intent, circuit = _design("voltage_divider")
        nominal = generator.predict(intent).quantities["vout_v"].nominal
        (finding,) = evaluate(_record("voltage_divider", {"divider.vout": _meter(nominal * 1.2, 0.005)}))
        assert finding.status == "disagrees" and "model gives" in finding.detail

    def test_a_record_of_a_changed_design_is_stale(self):
        (finding,) = evaluate(_record("voltage_divider", {"divider.vout": _meter(1.0, 0.1)}, netlist_sha="0" * 64))
        assert finding.status == "stale"


class TestReach:
    def test_agreeing_evidence_drops_d1_from_the_measured_claims_only(self, bench_dir):
        generator, intent, circuit = _design("voltage_divider")
        nominal = generator.predict(intent).quantities["vout_v"].nominal
        bench_dir(_record("voltage_divider", {"divider.vout": _meter(nominal, 0.005)}))
        rows = {c["id"]: c for c in realize(generator, intent).validation_coverage["claims"]}
        assert "D1" not in rows["proof.divider.vout"]["defeaters"]
        assert "D1" not in rows["divider.vout_band"]["defeaters"]
        assert "bench record bench-test agrees" in rows["proof.divider.vout"]["detail"]
        assert "D1" in rows["proof.divider.r1_power"]["defeaters"]        # not measured
        assert "D1" in rows["divider.supply_current"]["defeaters"]

    def test_it_reaches_that_design_only(self, bench_dir):
        generator, intent, circuit = _design("voltage_divider")
        nominal = generator.predict(intent).quantities["vout_v"].nominal
        bench_dir(_record("voltage_divider", {"divider.vout": _meter(nominal, 0.005)}))
        other = IntentIR(requirements={**intent.requirements, "targets": {**intent.requirements["targets"],
                                                                          "vout_v": 1.0}},
                         provenance=Provenance(producer=Producer.FORM))
        rows = {c["id"]: c for c in realize(generator, other).validation_coverage["claims"]}
        assert "D1" in rows["proof.divider.vout"]["defeaters"]

    def test_one_disagreement_reopens_the_whole_family(self, bench_dir):
        generator, intent, circuit = _design("voltage_divider")
        nominal = generator.predict(intent).quantities["vout_v"].nominal
        bench_dir(_record("voltage_divider", {"divider.vout": _meter(nominal, 0.005)}, rid="good"),
                  _record("voltage_divider", {"divider.vout": _meter(nominal * 1.2, 0.005)}, rid="bad"))
        rows = {c["id"]: c for c in realize(generator, intent).validation_coverage["claims"]}
        assert "D1" in rows["proof.divider.vout"]["defeaters"]

    def test_with_no_records_nothing_changes(self, bench_dir):
        assert evidence_for("voltage_divider", None, "any netlist") == {}


# ── The repository's own records ─────────────────────────────────────────────

def test_every_recorded_bench_measurement_agrees_and_is_current():
    """A disagreeing or stale record fails here until it is explained or re-measured."""
    for record in load_records():
        for finding in evaluate(record):
            assert finding.status == "agrees", finding


def test_the_prefilled_templates_name_the_designs_as_they_are_built_now():
    """docs/bench_templates ([2026-09-25]): a template of a design the generator has since changed is stale."""
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("bench_template", root / "scripts" / "bench_template.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    folder = root / "docs" / "bench_templates"
    assert {p.stem for p in folder.glob("*.json")} == set(tool.STANDARD)
    for name, (function, fields) in tool.STANDARD.items():
        written = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
        now = tool.template(function, fields)
        assert written["netlist_sha256"] == now["netlist_sha256"], (
            f"{name}: regenerate with python scripts/bench_template.py --standard docs/bench_templates")
        assert set(written["parts"]) == set(now["parts"]) and set(written["measures"]) == set(now["measures"])
        assert all(r["value"] is None for r in list(written["parts"].values()) + list(written["measures"].values()))
