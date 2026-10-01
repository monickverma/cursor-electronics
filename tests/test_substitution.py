"""
Stage 6 — BOM and substitution. `PHASE_2_PLAN_v2.md` §5 Stage 6;
`brain/decisions.md` [2026-09-25] Stage 6.

Gate 1: no substitution surfaces that fails the original's checks (G1).
Gate 2: every price carries `price_asof`; pricing never gates validation (G1).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.intent_ir import IntentIR, Producer, Provenance
from core.intent_patch import PatchOp, apply_patch
from generators.bom.compiler import BOMCompiler, load_database, price_index
from generators.bom.substitution import Rejected, Substitute, candidates, check, substitutes
from generators.netlist.spice import SpiceNetlistGenerator
from generators.protocol import grid_of
from generators.realize import realize
from validation.grid_adapters import ADAPTERS, board_cases

BACKEND = Path(__file__).resolve().parent.parent / "backend"


def _case(name, board=None, pins=None):
    adapter = ADAPTERS[name].build(board)
    req = json.loads(json.dumps(dict(adapter.intent_for(next(iter(grid_of(adapter.generator, board).points())))
                                     .requirements)))
    if pins:
        req.setdefault("constraints", {})["pinned"] = pins
    intent = IntentIR(requirements=req, provenance=Provenance(producer=Producer.FORM))
    return adapter.generator, intent, realize(adapter.generator, intent)


# ── Gate 1 ───────────────────────────────────────────────────────────────────

class TestTheTerminator:
    """The case that made gate 1 concrete: an 0402 where the 1206 must be."""

    def test_the_bom_no_longer_orders_the_terminator_as_an_0402(self):
        _, _, circuit = _case("rs485_node", "arduino_uno")
        r1 = next(r for r in BOMCompiler().compile(circuit) if r["id"] == "R1")
        assert r1["part_number"] == "RC1206FR-07120RL"
        assert r1["priced_as"] is None and r1["lcsc_pn"] != "C25071"   # C25071 is the 0402

    @pytest.mark.parametrize("board", ["arduino_uno", "esp32_devkitc", "blackpill_f411ce"])
    def test_no_under_rated_terminator_surfaces(self, board):
        # A driver can hold the pair at the full supply. On a 5 V bus only the
        # 1206 takes it; on 3.3 V (≈ 83 mW) an 0603 or 0805 does, and surfaces.
        from data.parts import resistor_series

        generator, intent, circuit = _case("rs485_node", board)
        supply = intent.requirements["constraints"]["supply_v"]
        worst_w = supply ** 2 / (120 * 0.99)
        found, rejected = substitutes(generator, intent, circuit)
        for sub in (s for s in found if s.component_id == "R1"):
            assert resistor_series(sub.part_number).power_w >= worst_w, sub.part_number
        reasons = {r.part_number: r.reason for r in rejected if r.component_id == "R1"}
        assert "RC0402FR-07120RL" in reasons and "62.5 mW rating" in reasons["RC0402FR-07120RL"]
        if supply > 3.6:
            assert not [s for s in found if s.component_id == "R1"]


class TestTheOriginalsChecks:
    @pytest.mark.parametrize("name,pid,pins", [
        ("voltage_divider", "R2", {"R1": {"part": "RC0402FR-0791KL"}, "R2": {"part": "RC0402FR-0710KL"}}),
        ("rc_lowpass", "R1", {"R1": {"part": "RC0402FR-0716KL"}}),
    ])
    def test_a_looser_part_fails_the_band_the_original_proved(self, name, pid, pins):
        # Its own re-derived claims all hold; the original's proven band does not.
        # The originals are pinned to E24 values: a 5% (J) part is made only in those
        # ([2026-10-01] #13 — an unmade one is refused before any check).
        generator, intent, circuit = _case(name, pins=pins)
        placed = next(c for c in circuit.components if c.id == pid).part_number
        result = check(generator, intent, circuit, pid, placed.replace("FR-07", "JR-07"))
        assert isinstance(result, Rejected)
        assert "the original's property" in result.reason and "no longer holds" in result.reason

    def test_a_looser_part_that_still_meets_every_threshold_surfaces(self):
        # The DHT22's checks are limits (rise time, sink current), not a band.
        generator, intent, circuit = _case("dht22_node", "arduino_uno")
        result = check(generator, intent, circuit, "R1", "RC0402JR-0710KL")
        assert isinstance(result, Substitute) and "tolerance ±1% → ±5%" in result.changes

    def test_a_different_value_is_not_a_substitute(self):
        generator, intent, circuit = _case("dht22_node", "arduino_uno")
        result = check(generator, intent, circuit, "R1", "RC0603FR-079K1L")
        assert isinstance(result, Rejected) and "netlist differs" in result.reason

    def test_a_part_the_catalogue_cannot_describe_is_refused(self):
        generator, intent, circuit = _case("dht22_node", "arduino_uno")
        result = check(generator, intent, circuit, "R1", "CRCW040210K0FKED")
        assert isinstance(result, Rejected) and "not in the parts catalogue" in result.reason


@pytest.mark.parametrize("name,board", board_cases())
def test_everything_that_surfaces_passed_every_check_again(name, board):
    """
    Independent of `check()`'s own bookkeeping: apply each surfaced
    substitute's patch as the patch route would, and confirm the re-derived
    design is the same circuit, fails nothing, and proves every property the
    original proved.
    """
    from validation.claims import prove_properties

    generator, intent, circuit = _case(name, board)
    found, _ = substitutes(generator, intent, circuit)
    original = {p.spec.id for p in prove_properties(generator, intent, circuit) if p.result.status == "proven"}
    netlist = SpiceNetlistGenerator().generate(circuit)
    for sub in found:
        patched = apply_patch(intent, [PatchOp(**op) for op in sub.ops]).intent
        design = realize(generator, patched)
        assert SpiceNetlistGenerator().generate(design) == netlist, sub.part_number
        assert next(c for c in design.components if c.id == sub.component_id).part_number == sub.part_number
        assert not [c for c in design.validation_coverage["claims"] if c["verdict"] == "fails"], sub.part_number
        again = {p.spec.id: p.result.status for p in prove_properties(generator, intent, design)}
        assert all(again[pid] == "proven" for pid in original), sub.part_number


class TestCandidates:
    def test_resistors_are_offered_in_the_series_that_make_the_value(self):
        _, _, circuit = _case("dht22_node", "arduino_uno")
        r1 = next(c for c in circuit.components if c.id == "R1")
        offered = set(candidates(r1))
        assert {"RC0603FR-0710KL", "RC0805FR-0710KL", "RC1206FR-0710KL", "RC0402JR-0710KL"} == offered

    def test_the_5pc_series_is_not_offered_an_e96_value(self):
        # 10.2 kΩ exists at 1%; the 5% series is made in E24 values only.
        _, _, circuit = _case("voltage_divider")
        r1 = next(c for c in circuit.components if c.id == "R1")
        assert r1.part_number == "RC0402FR-0710K2L"
        assert not [p for p in candidates(r1) if "JR" in p]

    def test_ics_are_never_candidates(self):
        _, _, circuit = _case("rs485_node", "arduino_uno")
        for comp in circuit.components:
            if comp.id.startswith("U"):
                assert candidates(comp) == []


# ── Gate 2 ───────────────────────────────────────────────────────────────────

class TestPricing:
    def test_every_priced_catalogue_entry_is_dated(self):
        for entry in load_database()._entries:
            if entry.get("unit_price_usd") is not None:
                assert entry["price_asof"] == "2026-07-25" and entry["price_source"] == "static"

    def test_price_orders_what_surfaces_and_decides_nothing(self):
        generator, intent, circuit = _case("dht22_node", "arduino_uno")
        prices = price_index()
        found, _ = substitutes(generator, intent, circuit, prices)
        unpriced, _ = substitutes(generator, intent, circuit, {})
        assert [s.part_number for s in found if s.unit_price_usd is not None] == ["RC0603FR-0710KL"]
        assert found[0].part_number == "RC0603FR-0710KL" and found[0].price_asof == "2026-07-25"
        assert {s.part_number for s in found} == {s.part_number for s in unpriced}

    def test_moving_every_price_moves_no_claim(self, monkeypatch):
        entries = load_database()._entries
        before = {n: realize(*_case(n, b)[:2]).validation_coverage for n, b in board_cases()}
        for e in entries:
            if e.get("unit_price_usd") is not None:
                monkeypatch.setitem(e, "unit_price_usd", e["unit_price_usd"] * 1000 + 7)
        after = {n: realize(*_case(n, b)[:2]).validation_coverage for n, b in board_cases()}
        assert before == after

    def test_nothing_that_validates_reads_a_price(self):
        """No module that decides a claim or a design may mention a price."""
        banned = ("unit_price_usd", "price_asof", "price_index", "component_db", "BOMCompiler")
        roots = [BACKEND / "validation", BACKEND / "proof", BACKEND / "generators"]
        offenders = []
        for root in roots:
            for path in root.rglob("*.py"):
                if "bom" in path.parts:
                    continue
                names = {n.id for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(n, ast.Name)}
                names |= {n.attr for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(n, ast.Attribute)}
                text = path.read_text(encoding="utf-8")
                hits = [b for b in banned if b in names or f'"{b}"' in text or f"'{b}'" in text]
                if hits:
                    offenders.append((str(path.relative_to(BACKEND)), hits))
        assert offenders == []
