"""
tests/test_pcb_physics.py — the layout-physics steps of the physics report
(reports/Physics layout validation - what the market does and what Circuit OS
can build.md, build table steps 0-5).

Each test was written to fail before its step was built.
"""
import pytest

from pcb_engine import verify_board, Finding
import verify
from board_ir import Board, Layer, Track
import footprints


def _part(ref, x, y, pins, pkg="0603"):
    comp = footprints.build(ref, pkg, pins, x=x, y=y)
    comp.attrs["package"] = pkg
    return comp


def _clean_board():
    b = Board(name="test", outline_w=20, outline_h=20,
              layers=[Layer("F.Cu", "signal"), Layer("B.Cu", "signal")])
    b.components.extend([_part("R1", 6.0, 10.0, {"1": "SIG", "2": "GND"}),
                         _part("R2", 13.0, 10.0, {"1": "SIG", "2": "GND"})])
    r1, r2 = b.component("R1"), b.component("R2")
    b.tracks.append(Track("F.Cu", "SIG", 0.2, [
        (r1.pads[0].x, 10.0), (r1.pads[0].x, 8.0),
        (r2.pads[0].x, 8.0), (r2.pads[0].x, 10.0)]))
    b.tracks.append(Track("F.Cu", "GND", 0.2, [
        (r1.pads[1].x, 10.0), (r1.pads[1].x, 12.0),
        (r2.pads[1].x, 12.0), (r2.pads[1].x, 10.0)]))
    return b


def _check(rep, check):
    return next((f for f in rep.findings if f.check == check), None)


# ─────────────────────────────────────────────────────────────────────────────
# Step 0 — the "simulated" rung, and "unknown" split three ways
# ─────────────────────────────────────────────────────────────────────────────
class TestRungs:
    def test_ladder_has_simulated_between_bounded_and_evidence(self):
        r = verify.RUNGS
        assert "simulated" in r and "rule check" in r
        assert r.index("bounded") < r.index("simulated") < r.index("evidence")
        assert r.index("simulated") < r.index("rule check") < r.index("evidence")

    def test_unknown_has_three_kinds(self):
        assert set(verify.UNKNOWN_KINDS) == {
            "not checkable", "checkable by simulation, not run", "checkable, tool named"}

    def test_an_unknown_without_a_kind_is_refused(self):
        with pytest.raises(ValueError):
            Finding("X", "claim", "unknown", "unknown", "why")

    def test_a_simulated_finding_must_name_its_tool(self):
        with pytest.raises(ValueError):
            Finding("X", "claim", "simulated", "pass", "a number")
        Finding("X", "claim", "simulated", "pass", "a number", tool="ngspice 44")

    def test_a_rung_outside_the_ladder_is_refused(self):
        with pytest.raises(ValueError):
            Finding("X", "claim", "proven", "pass")

    def test_every_unknown_on_a_real_board_carries_a_kind(self):
        rep = verify_board(_clean_board())
        unknowns = [f for f in rep.findings if f.rung == "unknown"]
        assert unknowns
        for f in unknowns:
            assert f.unknown_kind in verify.UNKNOWN_KINDS, f.check
            if f.unknown_kind == "checkable, tool named":
                assert f.tool, f.check

    def test_report_counts_unknowns_by_kind(self):
        d = verify_board(_clean_board()).to_dict()
        assert set(d["unknowns"]) <= set(verify.UNKNOWN_KINDS)
        assert sum(d["unknowns"].values()) == sum(
            1 for f in d["findings"] if f["rung"] == "unknown")
        assert all("unknown_kind" in f for f in d["findings"])


class TestBranchV:
    """Branch V was one blanket unknown saying everything needs 'an EM solver or a
    bench measurement'. That was false for DC drop, trace current and clearance."""

    def test_v_is_split_into_its_six_branches(self):
        rep = verify_board(_clean_board())
        assert _check(rep, "V") is None
        for c in ("V.1", "V.2", "V.3", "V.4", "V.5", "V.6"):
            assert _check(rep, c) is not None, c

    def test_emc_is_the_one_not_checkable(self):
        rep = verify_board(_clean_board())
        assert _check(rep, "V.5").unknown_kind == "not checkable"

    def test_dc_drop_current_and_clearance_are_not_said_to_need_an_em_solver(self):
        rep = verify_board(_clean_board())
        for c in ("V.3", "V.4", "V.6"):
            f = _check(rep, c)
            if f.rung == "unknown":
                assert f.unknown_kind != "not checkable", c
            assert "EM solver" not in f.detail, c


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — one Stackup object, and the ground plane realised as copper
# ─────────────────────────────────────────────────────────────────────────────
import json
from pathlib import Path

import board_ir
import stackup as stackup_mod
from scene3d import board_scene

NETLIST = json.loads((Path(board_ir.__file__).parent / "netlist_dht22.json").read_text())


class TestStackup:
    def test_default_is_a_1_6_mm_two_layer_fr4(self):
        s = stackup_mod.default_stackup(2)
        assert s.total_mm == pytest.approx(1.6, abs=1e-9)
        assert [c.name for c in s.copper] == ["F.Cu", "B.Cu"]
        assert s.copper[0].thickness_mm == pytest.approx(0.035)
        assert s.dielectric_between("F.Cu", "B.Cu") == pytest.approx(1.53)
        er = s.dielectrics[0].er
        assert er.lo < er.hi and 3.5 < er.lo and er.hi < 5.0
        assert s.source            # every figure says where it came from

    def test_the_0_48_mm_dielectric_is_gone_from_the_board(self):
        b = _clean_board()
        assert b.stackup.dielectric_between("F.Cu", "B.Cu") == pytest.approx(1.53)

    def test_old_board_json_without_a_stackup_gets_the_default(self):
        d = json.loads(_clean_board().to_json())
        d.pop("stackup")
        b = Board.from_json(json.dumps(d))
        assert b.stackup.total_mm == pytest.approx(1.6)

    def test_round_trip_keeps_a_custom_stackup(self):
        b = _clean_board()
        b.stackup = stackup_mod.two_layer(total_mm=0.8, copper_mm=0.07)
        b2 = Board.from_json(b.to_json())
        assert b2.stackup.total_mm == pytest.approx(0.8)
        assert b2.stackup.copper[0].thickness_mm == pytest.approx(0.07)

    def test_scene_draws_the_stackup_it_is_given(self):
        b = _clean_board()
        b.stackup = stackup_mod.two_layer(total_mm=0.8, copper_mm=0.07)
        sc = board_scene(b)
        assert sc["board"]["thickness"] == pytest.approx(0.8)
        assert sc["board"]["copper"] == pytest.approx(0.07)
        z = {l["name"]: l["z"] for l in sc["layers"]}
        assert z["F.Cu"] == pytest.approx(0.8) and z["B.Cu"] == pytest.approx(0.0)

    def test_the_stackup_must_add_up(self):
        with pytest.raises(ValueError):
            stackup_mod.two_layer(total_mm=0.05, copper_mm=0.035)


@pytest.fixture(scope="module")
def compiled():
    from compile_board import compile_board
    return compile_board(NETLIST, candidates=1)


class TestPour:
    def test_compiled_board_carries_real_ground_copper(self, compiled):
        b = compiled.board
        pours = [p for p in b.pours if p.net == NETLIST.get("ground_net", "GND")]
        assert pours, "the plane is declared but no copper was poured"
        p = pours[0]
        assert p.layer == "B.Cu"
        # most of a mostly-empty bottom layer is copper
        assert p.area_mm2() > 0.5 * b.outline_w * b.outline_h

    def test_pour_round_trips_through_json(self, compiled):
        b2 = Board.from_json(compiled.board.to_json())
        assert b2.pours[0].area_mm2() == pytest.approx(compiled.board.pours[0].area_mm2())

    def test_verifier_checks_the_realised_pour(self, compiled):
        rep = verify_board(compiled.board, NETLIST)
        for c in ("III.1e", "III.1f"):
            f = _check(rep, c)
            assert f is not None and f.status == "pass", (c, f and f.detail)

    def test_a_pour_over_foreign_copper_fails(self, compiled):
        b = compiled.board.copy()
        p = b.pours[0]
        # pour a cell straight under a non-ground pad on the pour's layer
        foreign = next(pd for c in b.components for pd in c.pads
                       if pd.net and pd.net != p.net and pd.shape == "th")
        p.add_cell(*p.cell_of(foreign.x, foreign.y))
        f = _check(verify_board(b, NETLIST), "III.1e")
        assert f.status == "fail"

    def test_a_pour_cut_away_from_a_pad_fails_the_join(self, compiled):
        b = compiled.board.copy()
        p = b.pours[0]
        p.rows = [[] for _ in p.rows]          # no copper at all
        assert _check(verify_board(b, NETLIST), "III.1f").status == "fail"

    def test_scene_carries_the_pour(self, compiled):
        sc = board_scene(compiled.board)
        assert sc["pours"] and sc["pours"][0]["net"] == compiled.board.pours[0].net
        assert sc["pours"][0]["rects"]
