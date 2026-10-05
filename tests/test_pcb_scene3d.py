"""pcb_engine/scene3d.py — the Board IR drawn as a 3D scene. decisions.md [2026-10-06].

The viewer draws only what this scene says, so these tests pin the scene: one
entry per component with a body, a plated hole for every through-hole pad and
none for an SMD pad, copper where the IR has copper, the DRC kernel's findings
at their locations, and the same scene for the same board. A part with no body
model must say so (`generic`) rather than look like the real thing.
"""

import json
from pathlib import Path

import pytest

from core.ir_examples import IR_001, IR_002, IR_003, IR_004, IR_005
from generators.compose import Project, compose
from generators.netlist.pcb import PcbNetlistGenerator
from generators.registry import default_registry
from pcb_engine import from_netlist, place_constructive
import board_ir
import kernel
import scene3d
from compile_board import compile_board

ROOT = Path(__file__).resolve().parent.parent
ROOM = json.loads((ROOT / "docs" / "projects" / "room_monitor.json").read_text(encoding="utf-8"))

TEMPLATES = {"dht22": IR_001, "led": IR_002, "rc_filter": IR_003,
             "divider": IR_004, "modbus": IR_005}


def placed(ir):
    board, _ = from_netlist(PcbNetlistGenerator().generate(ir))
    return place_constructive(board)


def room_monitor_ir():
    return compose(default_registry(), Project.model_validate(ROOM)).circuit


@pytest.fixture(scope="module")
def routed_room():
    """The composed room monitor, through the real compiler (placement + A*)."""
    return compile_board(PcbNetlistGenerator().generate(room_monitor_ir()))


# ── The scene is complete and honest ─────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(TEMPLATES))
def test_every_component_has_exactly_one_body(name):
    board = placed(TEMPLATES[name])
    scene = scene3d.board_scene(board)
    assert sorted(c["ref"] for c in scene["components"]) == sorted(c.ref for c in board.components)
    for c in scene["components"]:
        sx, sy, sz = c["body"]["size"]
        assert sx > 0 and sy > 0 and sz > 0, c["ref"]
        assert c["model"] in ("parametric", "generic")


def test_room_monitor_bodies_are_all_real_package_models(routed_room):
    scene = routed_room.to_dict()["scene"]
    assert scene["stats"]["generic_bodies"] == 0, [
        (c["ref"], c["package"]) for c in scene["components"] if c["model"] == "generic"]
    kinds = {c["ref"]: c["kind"] for c in scene["components"]}
    assert kinds["U1"] == "microcontroller"
    assert kinds["Q1"] == "transistor"
    assert kinds["LED1"] == "led"


def test_unknown_package_is_flagged_generic_not_disguised():
    b = board_ir.Board(name="t", outline_w=20, outline_h=20, layers=[board_ir.Layer("F.Cu")])
    c = board_ir.Component("U9", 10, 10, courtyard_w=4.2, courtyard_h=3.1,
                           attrs={"package": "QFN-48-WEIRD"})
    b.components.append(c)
    (entry,) = scene3d.board_scene(b)["components"]
    assert entry["model"] == "generic"
    assert entry["body"]["size"][:2] == [4.2, 3.1]
    assert scene3d.board_scene(b)["stats"]["generic_bodies"] == 1


@pytest.mark.parametrize("ref,expected", [("R3", "resistor"), ("C12", "capacitor"),
                                          ("LED1", "led"), ("L2", "inductor"),
                                          ("Q1", "transistor"), ("U4", "ic"),
                                          ("XYZ", "ic")])
def test_kind_falls_back_to_the_designator(ref, expected):
    assert scene3d.component_kind(board_ir.Component(ref, 0, 0)) == expected


def test_declared_type_beats_the_designator():
    c = board_ir.Component("U2", 0, 0, attrs={"type": "sensor"})
    assert scene3d.component_kind(c) == "sensor"


def test_netlist_carries_type_and_value():
    nl = PcbNetlistGenerator().generate(IR_003)
    r1 = next(c for c in nl["components"] if c["ref"] == "R1")
    assert r1["type"] == "resistor"
    assert r1.get("value")


# ── Holes, pads, copper ──────────────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(TEMPLATES))
def test_through_hole_pads_get_holes_and_smd_pads_do_not(name):
    scene = scene3d.board_scene(placed(TEMPLATES[name]))
    pad_holes = {(h["ref"], h["pin"]) for h in scene["holes"] if h["ref"]}
    for p in scene["pads"]:
        if p["through"]:
            assert (p["ref"], p["pin"]) in pad_holes
            assert 0 < p["drill"] < min(p["w"], p["h"]), p
            assert p["layer"] == "both"
        else:
            assert (p["ref"], p["pin"]) not in pad_holes
            assert "drill" not in p


def test_drill_leaves_the_annular_ring():
    pad = board_ir.Pad("U1", "1", 0, 0, 1.3, 1.3, "N", shape="th")
    assert scene3d.drill_for(pad) == pytest.approx(0.8)


def test_tracks_and_vias_match_the_ir(routed_room):
    board, scene = routed_room.board, routed_room.to_dict()["scene"]
    assert len(scene["tracks"]) == len([t for t in board.tracks if len(t.points) >= 2])
    assert len(scene["vias"]) == len(board.vias)
    for t in scene["tracks"]:
        assert t["z"] in (0.0, scene3d.BOARD_THICKNESS_MM)
        assert t["width"] > 0
    via_holes = [h for h in scene["holes"] if h["ref"] is None]
    assert len(via_holes) == len(board.vias)


def test_pads_and_tracks_sit_on_the_board(routed_room):
    scene = routed_room.to_dict()["scene"]
    w, h = scene["board"]["w"], scene["board"]["h"]
    for p in scene["pads"]:
        assert 0 <= p["x"] <= w and 0 <= p["y"] <= h, p
    for t in scene["tracks"]:
        for x, y in t["points"]:
            assert 0 <= x <= w and 0 <= y <= h


def test_ground_plane_is_declared():
    scene = scene3d.board_scene(placed(IR_001))
    assert any(pl["layer"] == "B.Cu" for pl in scene["planes"])


# ── DRC findings are in the scene, located ───────────────────────────────────

def test_drc_markers_are_the_kernels_findings():
    b = board_ir.demo_board()
    # two tracks of different nets on top of each other: a guaranteed clearance error
    b.tracks.append(board_ir.Track("F.Cu", "SPI_SCK", 0.2, [(5.0, 2.0), (15.0, 2.0)]))
    b.tracks.append(board_ir.Track("F.Cu", "SPI_MOSI", 0.2, [(5.0, 2.1), (15.0, 2.1)]))
    scene = scene3d.board_scene(b)
    expected = kernel.drc(b)
    assert len(scene["drc"]) == len(expected) > 0
    assert scene["stats"]["drc_errors"] == sum(1 for v in expected if v.severity == "error")
    for m in scene["drc"]:
        assert {"rule", "severity", "detail", "x", "y", "nets"} <= set(m)


# ── Deterministic and serialisable ───────────────────────────────────────────

def test_same_board_same_scene(routed_room):
    a = scene3d.board_scene(routed_room.board)
    b = scene3d.board_scene(board_ir.Board.from_json(routed_room.board.to_json()))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_scene_is_json(routed_room):
    out = routed_room.to_dict()
    json.dumps(out["scene"])
    assert out["scene"]["version"] == scene3d.SCENE_VERSION
    assert out["board"]["components"], "the board IR travels with the scene"


# ── Footprint gaps the room monitor exposed ──────────────────────────────────

def test_room_monitor_keeps_every_part(routed_room):
    """D1 (SOD-123) was dropped for want of a footprint."""
    refs = {c.ref for c in routed_room.board.components}
    assert {"U1", "U2", "Q1", "D1", "LED1", "J1", "R1", "R2", "R3", "C1"} <= refs
    assert not [w for w in routed_room.warnings if "no footprint" in w]


def test_sot23_transistor_is_wired_by_its_pinout():
    """1 base, 2 emitter, 3 collector — not the order the pins were listed in."""
    import footprints
    q = footprints.build("Q1", "SOT-23", {"C": "LOAD", "B": "BASE", "E": "GND"})
    assert {p.pin: p.net for p in q.pads} == {"1": "BASE", "2": "GND", "3": "LOAD"}


def test_sod123_cathode_is_pad_one():
    import footprints
    d = footprints.build("D1", "SOD-123", {"A": "LOAD", "K": "VCC"})
    assert {p.pin: p.net for p in d.pads} == {"1": "VCC", "2": "LOAD"}
    assert all(p.shape == "rect" for p in d.pads)


def test_unrouted_connections_are_drawn_as_ratsnest(routed_room):
    scene = routed_room.to_dict()["scene"]
    assert len(scene["ratsnest"]) == len(routed_room.board.unrouted())
    assert scene["stats"]["unrouted"] == len(scene["ratsnest"])


def test_dht22_courtyard_covers_its_body(routed_room):
    """As a bare HEADER-4 the placer saw a 3 x 9 mm part and put passives under
    a sensor body 7.7 x 15.1 mm wide. Found by drawing the board in 3D."""
    u2 = routed_room.board.component("U2")
    assert u2.attrs["package"] == "DHT22"
    assert u2.courtyard_w >= 7.7 and u2.courtyard_h >= 15.1
    scene = routed_room.to_dict()["scene"]
    body = next(c for c in scene["components"] if c["ref"] == "U2")
    bx, by = body["x"], body["y"]
    hw, hh = body["body"]["size"][0] / 2, body["body"]["size"][1] / 2
    for c in scene["components"]:
        if c["ref"] == "U2":
            continue
        assert not (abs(c["x"] - bx) < hw and abs(c["y"] - by) < hh), f"{c['ref']} sits under the DHT22"
