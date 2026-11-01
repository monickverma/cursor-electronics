"""
tests/test_gerber_readback.py — stage 7: the fab files, read back into copper
in their own Python 3.12 interpreter, must agree with the IR; every fault
seeded into the FILES must be found.

The mutation matrix follows the plan's prototype run (4 of 4 caught) and adds
the guards: a cut track, a deleted via hit, a bridge, a drill hit moved 3 mm in
the drill file only (KiCad's DRC reads the board and cannot see it), a wrong
X2 net label, a ring too thin to carry the barrel, a missing read-back.
"""
import re
import shutil

import pytest

import pcb_engine  # noqa: F401  — puts the engine directory on sys.path
from board_ir import Board, Component, Layer, NetClass, Pad, Track, Via
import kicad_cli
import kicad_fab
import readback

pytestmark = pytest.mark.skipif(not (kicad_cli.available() and readback.available()),
                                reason="kicad-cli or the Python 3.12 read-back env missing")


def _resistor(ref, x, y, n1, n2):
    return Component(ref, x, y, courtyard_w=3.0, courtyard_h=1.4, pads=[
        Pad(ref, "1", x - 0.75, y, 0.8, 0.8, n1), Pad(ref, "2", x + 0.75, y, 0.8, 0.8, n2)])


def _board() -> Board:
    """Net A on top only; net B dives through two vias and runs on the bottom."""
    b = Board(name="rb", outline_w=30, outline_h=20, layers=[Layer("F.Cu"), Layer("B.Cu")])
    b.components = [_resistor("R1", 5, 5, "A", "B"), _resistor("R2", 15, 5, "A", "B")]
    b.net_classes = [NetClass("default", b.nets(), track_width=0.25, clearance=0.25)]
    b.tracks = [Track("F.Cu", "A", 0.25, [(4.25, 5), (4.25, 3), (14.25, 3), (14.25, 5)]),
                Track("F.Cu", "B", 0.25, [(5.75, 5), (5.75, 8)]),
                Track("B.Cu", "B", 0.25, [(5.75, 8), (15.75, 8)]),
                Track("F.Cu", "B", 0.25, [(15.75, 8), (15.75, 5)])]
    b.vias = [Via(5.75, 8, "B"), Via(15.75, 8, "B")]
    return b


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out = tmp_path_factory.mktemp("rb")
    b = _board()
    res = kicad_fab.export_fab(b, out, "rb")
    assert res.ok, res.refusals
    return b, out / "fab"


@pytest.fixture
def fab(exported, tmp_path):
    """A private copy of the exported files to damage."""
    b, src = exported
    dst = tmp_path / "fab"
    shutil.copytree(src, dst)
    return b, dst


def _kinds(rb):
    return {p["kind"] for p in rb.result.get("problems", [])}


def test_the_exported_files_read_back_clean(exported):
    b, fab = exported
    rb = readback.run_readback(b, fab)
    assert rb.ok, rb.refusals
    assert rb.result["python"].startswith("3.12")
    assert rb.result["plated_hits"] == 2 and rb.result["x2_labels"] == 4


def test_export_carries_the_readback_verdict(tmp_path):
    res = kicad_fab.export_fab(_board(), tmp_path, "rb")
    assert res.ok and res.readback["ok"] and res.readback["opens"] == {}


def test_a_track_cut_in_the_gerber_is_an_open(fab):
    b, d = fab
    g = d / "rb-B_Cu.gbl"
    text = g.read_text()
    lines = text.splitlines()
    draws = [i for i, l in enumerate(lines) if l.endswith("D01*")]
    del lines[draws[0]]                                   # the only bottom track of B
    g.write_text("\n".join(lines) + "\n")
    rb = readback.run_readback(b, d)
    assert rb.result["opens"] == {"B": 2}, rb.result


def test_a_via_hit_deleted_from_the_drill_file_is_an_open(fab):
    b, d = fab
    drl = d / "rb-PTH.drl"
    text = drl.read_text()
    hit = re.search(r"^X5\.75Y-12\.0?\n", text, re.M)
    assert hit, text
    drl.write_text(text.replace(hit.group(0), "", 1))
    rb = readback.run_readback(b, d)
    assert "hit_count" in _kinds(rb)
    assert rb.result["opens"] == {"B": 2}


def test_a_drill_hit_moved_in_the_file_only_is_caught(fab):
    """The plan's reason for this stage: KiCad's DRC reads the board, not the
    drill file, and cannot see this. The read-back must."""
    b, d = fab
    drl = d / "rb-PTH.drl"
    text = drl.read_text()
    moved = re.sub(r"^X5\.75(Y-12\.0?)$", r"X8.75\1", text, count=1, flags=re.M)
    assert moved != text
    drl.write_text(moved)
    rb = readback.run_readback(b, d)
    assert not rb.ok
    assert rb.result["opens"] == {"B": 2}
    assert "hole_off_copper" in _kinds(rb)


def test_copper_added_between_two_nets_is_a_short(fab):
    b, d = fab
    g = d / "rb-F_Cu.gtl"
    text = g.read_text()
    # A region across R2's two pads (15 +/- 0.75, file Y = 5 - 20 = -15).
    region = ("G36*\nX14000000Y-15100000D02*\nX16000000Y-15100000D01*\n"
              "X16000000Y-14900000D01*\nX14000000Y-14900000D01*\n"
              "X14000000Y-15100000D01*\nG37*\n")
    g.write_text(text.replace("M02*", region + "M02*"))
    rb = readback.run_readback(b, d)
    assert rb.result["shorts"] == [["A", "B"]]


def test_a_pad_label_that_disagrees_with_the_ir_is_reported(fab):
    b, d = fab
    g = d / "rb-F_Cu.gtl"
    text = g.read_text()
    assert "%TO.P,R1,1,*%" in text or "%TO.P,R1,1*%" in text
    g.write_text(text.replace("%TO.N,A*%", "%TO.N,WRONG*%", 1))
    rb = readback.run_readback(b, d)
    assert "label" in _kinds(rb)


def test_a_ring_too_thin_to_carry_the_barrel_does_not_join_layers(fab, monkeypatch):
    """0.8 mm vias on 0.4 mm drills leave a 0.2 mm ring. Demand 0.3 mm and the
    holes must stop joining F.Cu to B.Cu, so net B opens — the guard that keeps
    a grazing drill from counting as a connection."""
    b, d = fab
    monkeypatch.setattr(readback, "MIN_RING", 0.3)
    rb = readback.run_readback(b, d)
    assert "breakout" in _kinds(rb)
    assert "B" in rb.result["opens"]


def test_no_readback_interpreter_refuses_the_fab_files(tmp_path, monkeypatch):
    def gone():
        raise readback.ReadbackUnavailable("not installed")
    monkeypatch.setattr(readback, "find_python", gone)
    res = kicad_fab.export_fab(_board(), tmp_path, "rb")
    assert not res.ok and "read-back did not run" in res.refusals[0]
    assert not (tmp_path / "fab").exists()


def test_a_drill_file_that_cannot_be_read_refuses(fab):
    b, d = fab
    drl = d / "rb-PTH.drl"
    drl.write_text(re.sub(r"^X5\.75Y-12\.0?$", "X8.75Y-12", drl.read_text(), count=1, flags=re.M))
    rb = readback.run_readback(b, d)
    assert not rb.ran and not rb.ok
    assert rb.refusals[0].startswith("read-back failed")


def test_frame_matches_the_files():
    b = _board()
    spec = readback.pad_table(b)
    r1 = next(p for p in spec["pads"] if p["ref"] == "R1" and p["pin"] == "1")
    assert (r1["x"], r1["y"]) == (4.25, -15)
