"""
D7 per figure — `brain/decisions.md` [2026-09-24] D1, D2, D7.

Every part figure a claim reads has a provenance record (`data/figures.py`);
a person verifies records against their documents (`scripts/verify_figures.py`);
a claim cites D7 while any figure it reads is untrusted. With nothing verified
that is every figure-reading claim — so these tests also show what closes it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.intent_ir import IntentIR, Producer, Provenance
from data import figures as F
from data.parts import CAPACITORS, RESISTOR_SERIES, passive_figures, resistor_series, resistor_value
from generators.protocol import grid_of
from generators.realize import realize
from validation.grid_adapters import ADAPTERS, board_cases

ROOT = Path(__file__).resolve().parent.parent


def _design(name, board):
    adapter = ADAPTERS[name].build(board)
    point = next(iter(grid_of(adapter.generator, board).points()))
    intent = IntentIR(requirements=adapter.intent_for(point).requirements,
                      provenance=Provenance(producer=Producer.FORM))
    return realize(adapter.generator, intent)


def _rows(design):
    return {c["id"]: c for c in design.validation_coverage["claims"]}


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A verification store of the test's own, so the repository's is never written."""
    path = tmp_path / "verifications.json"
    path.write_text(json.dumps({"verifications": []}), encoding="utf-8")
    monkeypatch.setenv("CIRCUITOS_FIGURE_VERIFICATIONS", str(path))

    def verify(*figure_ids):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["verifications"] += [{"figure": f, "record_hash": F.record_hash(f), "by": "test", "at": "now"}
                                  for f in figure_ids]
        path.write_text(json.dumps(data), encoding="utf-8")
        # mtime resolution can be coarse; the cache is keyed on it
        os.utime(path, (os.path.getatime(path), os.path.getmtime(path) + len(data["verifications"])))
    return verify


# ── The registry ─────────────────────────────────────────────────────────────

class TestRegistry:
    def test_every_record_resolves_to_a_value_in_its_owning_table(self):
        for fid in F.FIGURES:
            F.value(fid)

    def test_every_board_pin_has_a_record(self):
        from data.mcu_targets import TARGETS

        for tid, target in TARGETS.items():
            for pin in target.pins:
                assert f"board:{tid}/{pin}" in F.FIGURES

    def test_records_are_the_agents_and_say_so(self):
        # The agent cannot verify its own reading: every record says it is the
        # agent's, and that its check of the document is not a verification.
        for record in F.FIGURES.values():
            assert "the agent" in record.recorded_by
            assert "figure_evidence.json" in record.recorded_by and "not a person's verification" in record.recorded_by

    def test_what_holds_a_pin_between_reset_and_the_sketch_is_said_where_a_pull_does_not(self):
        # [2026-09-30]: the recheck found pins that float while reset is held,
        # and Uno pins a bootloader or the USB bridge drives.
        assert "floating while reset is held" in F.FIGURES["board:esp32_devkitc/GPIO13"].statement
        assert "floating while reset is held" in F.FIGURES["board:esp32_devkitc/GPIO14"].statement
        assert "bootloader" in F.FIGURES["board:arduino_uno/D13"].statement
        assert "bootloader" in F.FIGURES["board:arduino_uno/D1"].statement
        assert "USB-serial" in F.FIGURES["board:arduino_uno/D0"].statement
        assert "not led out" in F.FIGURES["board:esp32_devkitc/GPIO6"].statement

    def test_assumptions_and_typicals_are_labelled_as_such(self):
        assert F.FIGURES["DHT22/bus_capacitance_pf_per_m"].kind == F.Kind.ASSUMPTION
        assert F.FIGURES["150080RS75000/ideality"].kind == F.Kind.ASSUMPTION
        # [2026-10-02]: Würth publishes no V_F minimum, so the figure holding it is an assumption.
        assert F.FIGURES["150080RS75000/forward_voltage_v"].kind == F.Kind.ASSUMPTION
        assert F.FIGURES["ATmega328P-PU/gpio_output_resistance_ohm"].kind == F.Kind.TYPICAL
        assert F.FIGURES["MAX485ECSA/receiver_threshold_mv"].kind == F.Kind.STANDARD

    def test_an_unrecorded_figure_cannot_be_named(self):
        with pytest.raises(KeyError):
            F.of("DHT22", "a_figure_nobody_recorded")
        with pytest.raises(KeyError):
            F.passive("NOT-A-PART", "tolerance")

    @pytest.mark.parametrize("name,board", board_cases())
    def test_every_declared_figure_is_recorded_and_belongs_to_a_placed_part(self, name, board):
        design = _design(name, board)
        placed = {c.part_number for c in design.components}
        owners = placed | {passive_figures(p)[0] for p in placed if passive_figures(p)}
        for cid, row in _rows(design).items():
            for fid in (row.get("scope") or {}).get("figures") or ():
                assert fid in F.FIGURES, (cid, fid)
                owner = F.owner_and_key(fid)[0]
                assert owner in owners or owner.startswith("board:"), (cid, fid)


class TestPartsCatalogue:
    def test_the_generators_series_and_its_figures(self):
        s = resistor_series("RC0402FR-0710KL")
        assert (s.tolerance, s.power_w, s.voltage_max, s.package) == (0.01, 0.0625, 50.0, "0402")
        assert resistor_series("RC1206FR-07120RL").power_w == 0.25
        assert resistor_series("CRCW040210K0FKED") is None

    def test_part_numbers_read_back_to_their_value(self):
        assert resistor_value("RC0402FR-071K59L") == 1590.0
        assert resistor_value("RC1206FR-07120RL") == 120.0
        assert resistor_value("RC0402FR-0710KL") == 10000.0

    def test_capacitor_figures_follow_their_part_number_codes(self):
        # O = 16 V, B = 50 V, Q = 6.3 V; K = 10 %.
        codes = {"O": 16.0, "B": 50.0, "Q": 6.3}
        for pn, cap in CAPACITORS.items():
            assert cap.voltage_max == codes[pn[9]], pn
            assert cap.tolerance == 0.10 and pn[8] == "K", pn


# ── Hash, verification, trust ────────────────────────────────────────────────

class TestTrust:
    def test_the_hash_covers_the_value(self, monkeypatch):
        before = F.record_hash("RC0402FR/power_w")
        monkeypatch.setitem(RESISTOR_SERIES, "RC0402FR",
                            RESISTOR_SERIES["RC0402FR"].__class__(**{**RESISTOR_SERIES["RC0402FR"].__dict__,
                                                                    "power_w": 0.1}))
        assert F.record_hash("RC0402FR/power_w") != before

    def test_a_verification_of_an_edited_value_no_longer_counts(self, store, monkeypatch):
        store("DHT22/supply_voltage_max")
        assert F.verified("DHT22/supply_voltage_max")
        from data.component_constraints import COMPONENT_CONSTRAINTS

        monkeypatch.setitem(COMPONENT_CONSTRAINTS["DHT22"], "supply_voltage_max", 6.0)
        assert not F.verified("DHT22/supply_voltage_max")

    def test_only_guarantees_standards_and_policies_become_trusted(self, store):
        store("RC0402FR/tolerance", "MAX485ECSA/receiver_threshold_mv",
              "ATmega328P-PU/gpio_recommended_current_ma",
              "ATmega328P-PU/gpio_output_resistance_ohm", "DHT22/bus_capacitance_pf_per_m")
        assert F.trusted("RC0402FR/tolerance")                        # guaranteed
        assert F.trusted("MAX485ECSA/receiver_threshold_mv")          # standard
        assert F.trusted("ATmega328P-PU/gpio_recommended_current_ma")  # policy
        assert not F.trusted("ATmega328P-PU/gpio_output_resistance_ohm")  # typical, verified
        assert not F.trusted("DHT22/bus_capacitance_pf_per_m")           # assumption, verified
        assert not F.trusted("RC0402FR/power_w")                          # not verified

    def test_a_derived_figure_is_trusted_only_through_its_inputs(self, store, monkeypatch):
        derived = F.Figure("RC0402FR/voltage_max", F.Kind.DERIVED, "from its inputs",
                           inputs=("RC0402FR/tolerance", "RC0402FR/power_w"))
        monkeypatch.setitem(F.FIGURES, "RC0402FR/voltage_max", derived)
        store("RC0402FR/voltage_max", "RC0402FR/tolerance")
        assert not F.trusted("RC0402FR/voltage_max")
        store("RC0402FR/power_w")
        assert F.trusted("RC0402FR/voltage_max")


# ── What closes D7 ───────────────────────────────────────────────────────────

class TestClosure:
    def test_with_nothing_verified_every_figure_reading_claim_cites_d7(self, store):
        rows = _rows(_design("rs485_node", "arduino_uno"))
        for cid, row in rows.items():
            if (row.get("scope") or {}).get("figures"):
                assert "D7" in row["defeaters"], cid

    def test_verifying_what_a_claim_reads_drops_d7_from_that_claim_only(self, store):
        rows = _rows(_design("rs485_node", "arduino_uno"))
        store(*rows["rs485.driver_load"]["scope"]["figures"])
        after = _rows(_design("rs485_node", "arduino_uno"))
        assert "D7" not in after["rs485.driver_load"]["defeaters"]
        assert "D7" not in after["proof.rs485.driver_load"]["defeaters"]   # inherits what it re-derives
        assert after["rs485.driver_load"]["verdict"] == "holds_defeasible"  # D1 still stands
        assert "D7" in after["rs485.rail_current"]["defeaters"]             # reads a typical and an assumption
        assert "D7" in after["rs485.termination_dissipation"]["defeaters"]  # its power rating is unverified

    def test_a_claim_resting_on_a_typical_keeps_d7_whatever_is_verified(self, store):
        rows = _rows(_design("led_indicator", "arduino_uno"))
        store(*rows["led.current_band"]["scope"]["figures"])
        assert "D7" in _rows(_design("led_indicator", "arduino_uno"))["led.current_band"]["defeaters"]

    def test_the_voltage_rating_rule_closes_on_its_parts_ratings(self, store):
        rows = _rows(_design("voltage_divider", None))
        figures = rows["rule.voltage_ratings_ok"]["scope"]["figures"]
        assert figures and all(f.endswith("/voltage_max") or f.endswith("/supply_voltage_max") for f in figures)
        store(*figures)
        after = _rows(_design("voltage_divider", None))["rule.voltage_ratings_ok"]
        assert "D7" not in after["defeaters"] and after["verdict"] == "holds"

    def test_the_pin_rules_close_on_the_pin_rows_the_design_uses(self, store):
        rows = _rows(_design("rs485_node", "esp32_devkitc"))
        figures = rows["rule.pin_assignment_valid"]["scope"]["figures"]
        assert "board:esp32_devkitc/console_uart" in figures
        assert all(f.startswith("board:esp32_devkitc/") for f in figures)
        store(*figures)
        assert "D7" not in _rows(_design("rs485_node", "esp32_devkitc"))["rule.pin_assignment_valid"]["defeaters"]


# ── The verification tool ────────────────────────────────────────────────────

class TestVerifyTool:
    def _run(self, store_path, *args):
        env = {**os.environ, "CIRCUITOS_FIGURE_VERIFICATIONS": str(store_path), "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_figures.py"), *args],
                              capture_output=True, text=True, env=env, timeout=120)

    def test_verify_records_who_and_binds_the_hash(self, tmp_path):
        path = tmp_path / "v.json"
        path.write_text(json.dumps({"verifications": []}), encoding="utf-8")
        result = self._run(path, "--verify", "RC0402FR/power_w", "--by", "A. Engineer")
        assert result.returncode == 0, result.stderr
        entry = json.loads(path.read_text(encoding="utf-8"))["verifications"][0]
        assert entry["figure"] == "RC0402FR/power_w" and entry["by"] == "A. Engineer"
        assert entry["record_hash"] == F.record_hash("RC0402FR/power_w")

    def test_a_verification_must_name_a_person_and_a_real_record(self, tmp_path):
        path = tmp_path / "v.json"
        assert self._run(path, "--verify", "RC0402FR/power_w").returncode != 0
        assert self._run(path, "--verify", "NOPE/nothing", "--by", "x").returncode != 0

    def test_every_verification_in_the_repository_names_a_person_and_how_it_was_made(self):
        # Once empty; a person's confirmations live here now. What the store may
        # never hold is an unsigned or unexplained entry — and no test writes it.
        data = json.loads((ROOT / "backend" / "data" / "figure_verifications.json").read_text(encoding="utf-8"))
        for entry in data["verifications"]:
            assert F.names_a_person(entry["by"]), f"{entry['figure']}: signed {entry['by']!r}, not by a person"
            assert entry["figure"] in F.FIGURES and len(entry["record_hash"]) == 64
            assert entry.get("method", "read the document")

    def test_a_placeholder_is_not_a_name(self, tmp_path):
        path = tmp_path / "v.json"
        for placeholder in ("Your Name", "<your name>", "NAME"):
            assert self._run(path, "--verify", "RC0402FR/power_w", "--by", placeholder).returncode != 0
            assert self._run(path, "--confirm-agreeing", "--by", placeholder).returncode != 0
        assert not path.exists()

    def test_review_names_confirmations_the_records_have_since_outgrown(self, tmp_path):
        path = tmp_path / "v.json"
        path.write_text(json.dumps({"verifications": [
            {"figure": "RC0402FR/power_w", "record_hash": "0" * 64, "by": "A. Engineer", "at": "then"}]}),
            encoding="utf-8")
        result = self._run(path, "--review")
        assert "RC0402FR/power_w" in result.stdout and "changed since A. Engineer confirmed it" in result.stdout


# ── The agent's evidence ([2026-09-25]) — evidence, never verification ───────

class TestAgentEvidence:
    def _run(self, store_path, *args):
        env = {**os.environ, "CIRCUITOS_FIGURE_VERIFICATIONS": str(store_path), "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_figures.py"), *args],
                              capture_output=True, text=True, env=env, timeout=120)

    def test_every_record_has_evidence_checked_against_it_as_it_is_now(self):
        # A record edited after its check has stale evidence: check it again, or mark it not checked.
        figures = F.evidence()["figures"]
        assert set(figures) == set(F.FIGURES)
        stale = [f for f in F.FIGURES if figures[f]["record_hash"] != F.record_hash(f)]
        assert stale == []

    def test_agreeing_evidence_cites_a_document_a_page_and_what_it_reads(self):
        ev = F.evidence()
        for fid, item in ev["figures"].items():
            assert item["verdict"] in ev["verdicts"], fid
            if item["verdict"] in ("agrees", "agrees_in_part"):
                assert item["documents"] and all(d in ev["documents"] for d in item["documents"]), fid
                assert item["pages"] and item["reads"], fid
            else:
                assert item["note"], f"{fid}: a record not checked says why"

    def test_the_evidence_alone_trusts_nothing(self):
        assert F.untrusted(list(F.FIGURES), rows=()) == tuple(F.FIGURES)

    def test_confirming_is_a_named_persons_act_and_says_how_it_was_made(self, tmp_path):
        path = tmp_path / "v.json"
        path.write_text(json.dumps({"verifications": []}), encoding="utf-8")
        assert self._run(path, "--confirm-agreeing").returncode != 0, "it must name a person"
        result = self._run(path, "--confirm-agreeing", "--by", "A. Engineer")
        assert result.returncode == 0, result.stderr
        entries = json.loads(path.read_text(encoding="utf-8"))["verifications"]
        agreeing = {f for f, i in F.evidence()["figures"].items() if i["verdict"] == "agrees"}
        assert {e["figure"] for e in entries} == agreeing
        assert all("agent's cited evidence" in e["method"] and e["by"] == "A. Engineer" for e in entries)
        rows = F.verifications(str(path))
        assert F.trusted("RC0402FR/power_w", rows), "a confirmed guaranteed limit is trusted"
        assert not F.trusted("ATmega328P-PU/gpio_output_resistance_ohm", rows), "a typical never is"
        assert not F.trusted("board:blackpill_f411ce/PA0", rows), "an unchecked one is not confirmed"
        again = self._run(path, "--confirm-agreeing", "--by", "A. Engineer")
        assert "recorded 0 verifications" in again.stdout

    def test_review_lists_what_would_and_would_not_be_confirmed(self, tmp_path):
        result = self._run(tmp_path / "none.json", "--review")
        assert result.returncode == 0, result.stderr
        assert "would be confirmed by --confirm-agreeing" in result.stdout
        assert "board:blackpill_f411ce/PA0: not checked" in result.stdout


# ── Completeness, by experiment ──────────────────────────────────────────────

#: Figures the generators design with: moving them changes the design, so no
#: single claim can be held to them. Pinned, so a new one is looked at.
KNOWN_DESIGN_INPUTS = {
    ("rs485_node@arduino_uno", "MAX485ECSA/receiver_threshold_mv"),
    ("rs485_node@arduino_uno", "MAX485ECSA/requires_termination_ohm"),
    ("rs485_node@esp32_devkitc", "MAX3485ECSA/requires_termination_ohm"),
    ("rs485_node@blackpill_f411ce", "MAX3485ECSA/requires_termination_ohm"),
    # The load switch picks R1 by the forced beta; on 3.3 V boards a ×1.37 move changes R1 ([2026-10-03]).
    ("load_switch@esp32_devkitc", "MMBT2222ALT1G/forced_beta"),
    ("load_switch@blackpill_f411ce", "MMBT2222ALT1G/forced_beta"),
}


@pytest.mark.slow
def test_every_figure_a_claim_reads_is_declared():
    """
    `validation/figure_audit.py`: each figure of each placed part is moved, the
    generator rebuilt, and every claim that changed must declare it. Runs in a
    process of its own because it reloads modules.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, "-m", "validation.figure_audit"], cwd=ROOT / "backend",
                            capture_output=True, text=True, env=env, timeout=900)
    assert result.returncode == 0, result.stderr[-2000:]
    report = json.loads(result.stdout)
    assert report["violations"] == []
    assert report["checked"] >= 140
    assert {(s["case"], s["figure"]) for s in report["skipped"]} == KNOWN_DESIGN_INPUTS
