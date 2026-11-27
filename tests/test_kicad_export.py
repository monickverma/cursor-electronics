"""
tests/test_kicad_export.py — stage 3: the Board IR leaves as a KiCad 10 board
that KiCad itself loads, re-saves, and places pad for pad where the IR has it.

The KiCad tests run kicad-cli as a subprocess and skip where it is not
installed. The writer-only tests run everywhere.
"""
import json
import math
from pathlib import Path

import pytest

import pcb_engine  # noqa: F401  — puts the engine directory on sys.path
from board_ir import Board, Component, Keepout, Layer, NetClass, Pad, Track, Via, demo_board
import kicad_cli
import kicad_export
from kicad_export import ExportError, from_kicad, to_kicad, write_pcb, write_pro

requires_kicad = pytest.mark.skipif(not kicad_cli.available(),
                                    reason="kicad-cli not installed")

NETLIST = Path(__file__).parent.parent / "backend" / "pcb_engine" / "netlist_dht22.json"


def _two_pad(ref, x, y, rot, side="top", shape="rect", net2=None):
    """A two-pad part with its pads absolute and axis aligned, as the IR holds them."""
    t = math.radians(rot)
    dx, dy = 1.5 * math.cos(t), 1.5 * math.sin(t)
    w, h = (1.0, 0.6) if abs(math.cos(t)) > 0.5 else (0.6, 1.0)
    if shape == "th":
        w, h = 1.3, 1.3
    layer = "B.Cu" if side == "bottom" else "F.Cu"
    return Component(ref, x, y, rotation=rot, side=side, courtyard_w=4, courtyard_h=2.4,
                     pads=[Pad(ref, "1", x - dx, y - dy, w, h, "N1", layer=layer, shape=shape),
                           Pad(ref, "2", x + dx, y + dy, w, h, net2 or f"NET_{ref}",
                               layer=layer, shape=shape)])


def _placement_board() -> Board:
    """Every placement case the writer must get right: 0, 90 and 30 degrees,
    the bottom side, and a through-hole part."""
    b = Board(name="placements", outline_w=30, outline_h=20,
              layers=[Layer("F.Cu"), Layer("B.Cu")])
    b.components = [_two_pad("R1", 5, 5, 0), _two_pad("R2", 12, 8, 90),
                    _two_pad("R3", 20, 12, 30), _two_pad("R4", 8, 15, 0, "bottom"),
                    _two_pad("R5", 22, 4, 90, "bottom"), _two_pad("J1", 15, 15, 90, shape="th")]
    b.net_classes = [NetClass("default", b.nets())]
    return b


def _routed_board():
    from compile_board import compile_board
    return compile_board(json.loads(NETLIST.read_text())).board


# ─────────────────────────────────────────────────────────────────────────────
# writer only
# ─────────────────────────────────────────────────────────────────────────────
def test_frame_is_its_own_inverse():
    b = Board(outline_w=40, outline_h=24)
    assert to_kicad(b, 3.0, 4.0) == (3.0, 20.0)
    assert from_kicad(b, *to_kicad(b, 3.0, 4.0)) == (3.0, 4.0)


def test_writer_is_deterministic():
    b = _placement_board()
    assert write_pcb(b) == write_pcb(b.copy())


def test_writer_header_and_net_names():
    text = write_pcb(_placement_board())
    assert text.startswith("(kicad_pcb\n\t(version 20260206)")
    assert '(net "NET_R3")' in text
    # KiCad 10 references nets by name; a numbered net table is the old format
    assert "(net 0" not in text


def test_pad_angle_is_absolute_not_the_footprint_angle():
    """IR pads are axis aligned in board space. Writing the footprint angle on
    the pad turned R2's 0.6 x 1.0 pad into 1.0 x 0.6 in the Gerber (found 2026-10-21)."""
    text = write_pcb(_placement_board())
    r2 = text[text.index('(property "Reference" "R2"'):]
    pad = r2[r2.index("(pad "):]
    assert "(at -1.5 0)" in pad.splitlines()[1]


def test_unknown_copper_layer_is_refused():
    b = _placement_board()
    b.layers = [Layer("Top"), Layer("B.Cu")]
    with pytest.raises(ExportError):
        write_pcb(b)


def test_track_off_the_stack_is_refused():
    b = _placement_board()
    b.tracks = [Track("In1.Cu", "N1", 0.2, [(1, 1), (2, 2)])]
    with pytest.raises(ExportError):
        write_pcb(b)


def test_project_carries_net_classes():
    b = _placement_board()
    b.net_classes.append(NetClass("power", ["N1"], track_width=0.8, clearance=0.3, priority=10))
    pro = json.loads(write_pro(b, "placements"))
    names = [c["name"] for c in pro["net_settings"]["classes"]]
    assert names == ["Default", "power"]
    assert {"netclass": "power", "pattern": "N1"} in pro["net_settings"]["netclass_patterns"]


def test_compare_pads_reports_a_misplaced_pad():
    b = _placement_board()
    recs = [{"ref": p.ref, "pin": p.pin, "x": p.x, "y": b.outline_h - p.y,
             "w": p.w, "h": p.h, "through": p.shape == "th"} for p in b.pads()]
    assert kicad_cli.compare_pads(b, recs) == []
    recs[0]["x"] += 0.1
    recs[1]["w"], recs[1]["h"] = recs[1]["h"], recs[1]["w"]
    problems = kicad_cli.compare_pads(b, recs)
    assert any("no pad at" in p for p in problems)
    assert any("size" in p for p in problems)


# ─────────────────────────────────────────────────────────────────────────────
# through KiCad
# ─────────────────────────────────────────────────────────────────────────────
@requires_kicad
def test_kicad_is_the_pinned_version():
    assert kicad_cli.version() == kicad_export.KICAD_VERSION


@requires_kicad
def test_placement_cases_round_trip(tmp_path):
    rt = kicad_cli.round_trip(_placement_board(), tmp_path, "placements")
    assert rt.ok, rt.problems
    assert rt.inventory["pads"] == 12


@requires_kicad
def test_routed_board_round_trips(tmp_path):
    b = _routed_board()
    assert b.tracks and b.vias and b.plane_nets()
    rt = kicad_cli.round_trip(b, tmp_path, "dht22")
    assert rt.ok, rt.problems
    assert rt.inventory["planes"] == 1


@requires_kicad
def test_four_layer_board_with_keepout_round_trips(tmp_path):
    b = demo_board()
    b.layers[1].plane_net = "GND"
    b.tracks = [Track("In2.Cu", "IRQ", 0.2, [(5, 5), (10, 5), (10, 8)])]
    b.vias = [Via(10, 8, "IRQ")]
    b.keepouts = [Keepout("wire", "F.Cu", 33, 1, 4, 3, "antenna")]
    rt = kicad_cli.round_trip(b, tmp_path, "demo")
    assert rt.ok, rt.problems
    assert rt.inventory["keepouts"] == 1


@requires_kicad
def test_a_file_kicad_cannot_load_is_a_writer_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(kicad_cli, "write_pcb",
                        lambda b: write_pcb(b).replace("(segment", "(segmnt", 1))
    rt = kicad_cli.round_trip(_routed_board(), tmp_path, "broken")
    assert not rt.ok
    assert "could not load" in rt.problems[0]


@requires_kicad
def test_a_wrong_pad_angle_is_caught_by_kicads_own_placement(tmp_path, monkeypatch):
    """The bug found while building the writer: had the round trip existed, it
    would have refused the board instead of a Gerber with turned pads."""
    def turned(b):
        text = write_pcb(b)
        return text.replace("(at -1.5 0)\n\t\t\t(size 0.6 1)", "(at -1.5 0 90)\n\t\t\t(size 0.6 1)")
    monkeypatch.setattr(kicad_cli, "write_pcb", turned)
    rt = kicad_cli.round_trip(_placement_board(), tmp_path, "turned")
    assert any("size" in p for p in rt.problems), rt.problems
