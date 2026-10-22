"""
tests/test_kicad_fab.py — stage 6: fab files come out of KiCad only for a board
that passed, and never half-written (owner decision 2026-10-17: a failed board
is shown, its fab files are refused).
"""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import pcb_engine  # noqa: F401  — puts the engine directory on sys.path
from board_ir import Board, Component, Layer, NetClass, Pad, Track
import kicad_cli
import kicad_fab
import readback

# Export now ends in the stage-7 read-back, which refuses where it cannot run.
pytestmark = pytest.mark.skipif(not (kicad_cli.available() and readback.available()),
                                reason="kicad-cli or the Python 3.12 read-back env missing")

NETLIST = Path(__file__).parent.parent / "backend" / "pcb_engine" / "netlist_dht22.json"


def _resistor(ref, x, y, n1, n2):
    return Component(ref, x, y, courtyard_w=3.0, courtyard_h=1.4, pads=[
        Pad(ref, "1", x - 0.75, y, 0.8, 0.8, n1), Pad(ref, "2", x + 0.75, y, 0.8, 0.8, n2)])


def _board() -> Board:
    b = Board(name="fab", outline_w=30, outline_h=20, layers=[Layer("F.Cu"), Layer("B.Cu")])
    b.components = [_resistor("R1", 5, 5, "A", "B"), _resistor("R2", 15, 5, "A", "B")]
    b.net_classes = [NetClass("default", b.nets(), track_width=0.2, clearance=0.25)]
    b.tracks = [Track("F.Cu", "A", 0.2, [(4.25, 5), (4.25, 3), (14.25, 3), (14.25, 5)]),
                Track("F.Cu", "B", 0.2, [(5.75, 5), (5.75, 7), (15.75, 7), (15.75, 5)])]
    return b


def test_a_clean_board_gets_every_fab_file_with_hashes(tmp_path):
    res = kicad_fab.export_fab(_board(), tmp_path, "fab")
    assert res.ok, res.refusals
    names = set(res.files)
    for want in ("fab-F_Cu.gtl", "fab-B_Cu.gbl", "fab-Edge_Cuts.gm1", "fab-F_Mask.gts",
                 "fab-PTH.drl", "fab-NPTH.drl", "fab-pos.csv", "fab.d356", "manifest.json"):
        assert want in names, names
    man = json.loads((tmp_path / "fab" / "manifest.json").read_text())
    assert man["kicad_version"] == "10.0.1"
    for n, h in man["files"].items():
        assert hashlib.sha256((tmp_path / "fab" / n).read_bytes()).hexdigest() == h
    # millimetres, not KiCad's inch default
    assert "METRIC" in (tmp_path / "fab" / "fab-PTH.drl").read_text()
    assert (tmp_path / "fab" / "fab-pos.csv").read_text().startswith("Ref,Val,Package,PosX")


def test_the_plane_is_poured_in_the_gerber(tmp_path):
    from compile_board import compile_board
    b = compile_board(json.loads(NETLIST.read_text())).board
    res = kicad_fab.export_fab(b, tmp_path, "dht22")
    assert res.ok, res.refusals
    # A zone KiCad never filled exports as nothing; the plane must be a region.
    assert "G36*" in (tmp_path / "fab" / "dht22-B_Cu.gbl").read_text()


def test_a_board_that_failed_verification_gets_no_fab_files(tmp_path):
    b = _board()
    b.tracks.append(Track("F.Cu", "A", 0.2, [(14.25, 5), (15.75, 5)]))    # A bridged to B
    res = kicad_fab.export_fab(b, tmp_path, "short")
    assert not res.ok
    assert "failed verification" in res.refusals[0] and "III.2" in res.refusals[0]
    assert not (tmp_path / "fab").exists()
    assert (tmp_path / "short.kicad_pcb").exists()       # the board is still there to look at


def test_the_compile_routes_verdict_is_honoured(tmp_path):
    """/pcb/compile returns verification as a dict; a failed one refuses."""
    res = kicad_fab.export_fab(_board(), tmp_path, "fab",
                               verification={"ok": False, "failed_checks": ["III.1"]})
    assert not res.ok and "III.1" in res.refusals[0]
    assert not (tmp_path / "fab").exists()


def test_a_kicad_drc_refusal_refuses_export(tmp_path):
    res = kicad_fab.export_fab(_board(), tmp_path, "wide",
                               rules=['(rule "wide" (constraint track_width (min 0.3mm)))'])
    assert not res.ok
    assert any(r.startswith("KiCad DRC: required rules fired: track_width") for r in res.refusals)
    assert not (tmp_path / "fab").exists()


def test_old_fab_files_never_survive_a_refusal(tmp_path):
    assert kicad_fab.export_fab(_board(), tmp_path, "fab").ok
    assert (tmp_path / "fab").exists()
    res = kicad_fab.export_fab(_board(), tmp_path, "fab",
                               verification={"ok": False, "failed_checks": ["III.2"]})
    assert not res.ok and not (tmp_path / "fab").exists()


def test_a_failed_export_command_leaves_nothing_behind(tmp_path, monkeypatch):
    real = kicad_cli.run

    def drill_fails(args, **kw):
        if args[:3] == ["pcb", "export", "drill"]:
            return subprocess.CompletedProcess(args, 2, "", "boom")
        return real(args, **kw)
    monkeypatch.setattr(kicad_cli, "run", drill_fails)
    res = kicad_fab.export_fab(_board(), tmp_path, "fab")
    assert not res.ok and "drill export failed" in res.refusals[0]
    assert not (tmp_path / "fab").exists()
