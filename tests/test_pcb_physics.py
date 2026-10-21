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
