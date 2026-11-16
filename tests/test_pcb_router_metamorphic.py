"""
tests/test_pcb_router_metamorphic.py — the router's answer must not depend on
things that carry no meaning (F-0003).

There is no oracle for "the best routing of this board", so these tests do not
ask whether a route is good. They ask whether the router's answer changes when
the board changes in a way that should not change it: the same board twice, the
board moved, mirrored, turned, given more room, its parts listed in another
order, its nets renamed. The checks lived in a Temp harness that was lost; they
live here now.

Two strengths of claim, kept apart:
  exact     — determinism, renaming nets, moving the board by whole grid cells:
              the same copper, to 1e-6 mm.
  no worse  — mirror, quarter turn, more room, part order: the grid's tie-breaks
              are not symmetric, so the copper differs, but completion may not
              drop, DRC must stay clean, the judge must agree, and on an
              isometry the copper length stays within 5 %.

Each board is the template's own netlist, placed by the shipped placer and
routed with one seed of the shipped router at the shipped grid (0.2 mm).
"""
import pytest

# From the package, never `pcb_engine.compile_board`: importing that submodule
# rebinds the package's `compile_board` (the function) to the module, and every
# later test that calls `pcb_engine.compile_board(nl)` fails.
from pcb_engine import from_netlist, place_constructive
from core import ir_examples
from generators.netlist.pcb import PcbNetlistGenerator
from kernel import drc, score
from router import AStarRouter
from verify import unrouted_connections, verify_board

GRID = 0.2
SMALL = ["IR_001", "IR_002", "IR_003", "IR_004"]
ALL = SMALL + ["IR_005"]

_placed: dict = {}
_routed: dict = {}


def _board(name):
    if name not in _placed:
        nl = PcbNetlistGenerator().generate(getattr(ir_examples, name))
        _placed[name] = place_constructive(from_netlist(nl)[0])
    return _placed[name].copy()


def _route(b, seed=0):
    return AStarRouter(res=GRID).route(b, seed=seed)


def _base(name):
    if name not in _routed:
        _routed[name] = _route(_board(name))
    return _routed[name]


def _metrics(b):
    s = score(b)
    return {"unrouted": len(unrouted_connections(b)),
            "drc_errors": sum(v.severity == "error" for v in drc(b)),
            "verified": verify_board(b).ok,
            "vias": s.vias, "length": s.length_mm}


# ── transforms of a placed, unrouted board ───────────────────────────────────
def _map_points(b, f, outline, turn=False):
    b.outline_w, b.outline_h = outline
    for c in b.components:
        c.x, c.y = f(c.x, c.y)
        if turn:
            c.courtyard_w, c.courtyard_h = c.courtyard_h, c.courtyard_w
        for p in c.pads:
            p.x, p.y = f(p.x, p.y)
            if turn:
                p.w, p.h = p.h, p.w
    return b


def _shifted(b, k):
    return _map_points(b, lambda x, y: (x + k, y + k),
                       (b.outline_w + k, b.outline_h + k))


def _mirrored(b):
    w = b.outline_w
    return _map_points(b, lambda x, y: (w - x, y), (b.outline_w, b.outline_h))


def _turned(b):
    """A quarter turn: (x, y) -> (y, W - x); each pad's w and h swap."""
    w = b.outline_w
    return _map_points(b, lambda x, y: (y, w - x), (b.outline_h, b.outline_w), turn=True)


def _spread(b):
    """Twice the room: part centres scale by 2, each footprint keeps its shape."""
    b.outline_w, b.outline_h = 2 * b.outline_w, 2 * b.outline_h
    for c in b.components:
        dx, dy = c.x, c.y
        c.x, c.y = 2 * c.x, 2 * c.y
        for p in c.pads:
            p.x, p.y = p.x + dx, p.y + dy
    return b


def _reordered(b):
    b.components = b.components[::-1]
    return b


def _renamed(b, names):
    for p in b.pads():
        p.net = names.get(p.net, p.net)
    for t in b.tracks:
        t.net = names.get(t.net, t.net)
    for v in b.vias:
        v.net = names.get(v.net, v.net)
    for nc in b.net_classes:
        nc.nets = [names.get(n, n) for n in nc.nets]
    for layer in b.layers:
        if layer.plane_net:
            layer.plane_net = names.get(layer.plane_net, layer.plane_net)
    return b


# ── exact ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", ALL)
def test_the_same_board_and_seed_route_to_the_same_copper(name):
    assert _route(_board(name)).to_json() == _base(name).to_json()


@pytest.mark.parametrize("name", ALL)
def test_renaming_every_net_changes_no_copper(name):
    """Names reverse their sort order, so anything keyed on a sorted net list
    (the grid's net ids) is exercised. Renamed back, the copper is identical."""
    nets = _board(name).nets()
    names = {n: f"N{len(nets) - i:03d}_{n[::-1]}" for i, n in enumerate(nets)}
    back = {v: k for k, v in names.items()}
    routed = _renamed(_route(_renamed(_board(name), names)), back)
    assert routed.to_json() == _base(name).to_json()


@pytest.mark.parametrize("name", ["IR_001", "IR_002", "IR_005"])
def test_moving_the_board_by_whole_grid_cells_moves_the_copper(name):
    k = 10 * GRID
    base, moved = _base(name), _route(_shifted(_board(name), k))
    assert len(moved.tracks) == len(base.tracks)
    assert len(moved.vias) == len(base.vias)
    for t0, t1 in zip(base.tracks, moved.tracks):
        assert (t1.net, t1.layer, t1.width) == (t0.net, t0.layer, t0.width)
        assert len(t1.points) == len(t0.points)
        for (x0, y0), (x1, y1) in zip(t0.points, t1.points):
            assert x1 == pytest.approx(x0 + k, abs=1e-6)
            assert y1 == pytest.approx(y0 + k, abs=1e-6)
    for v0, v1 in zip(base.vias, moved.vias):
        assert (v1.x, v1.y, v1.net) == (pytest.approx(v0.x + k, abs=1e-6),
                                        pytest.approx(v0.y + k, abs=1e-6), v0.net)


# ── no worse ─────────────────────────────────────────────────────────────────
ISOMETRIES = {"mirror": _mirrored, "quarter turn": _turned}
OTHERS = {"twice the room": _spread, "parts reversed": _reordered}


def _no_worse(name, transformed):
    base, got = _metrics(_base(name)), _metrics(transformed)
    assert got["drc_errors"] == 0, got
    assert got["unrouted"] <= base["unrouted"], (base, got)
    # the judge and the kernel agree on what the router produced
    assert got["verified"] == (got["unrouted"] == 0), got
    return base, got


@pytest.mark.parametrize("how", list(ISOMETRIES))
@pytest.mark.parametrize("name", SMALL)
def test_an_isometry_keeps_completion_and_copper_length(name, how):
    base, got = _no_worse(name, _route(ISOMETRIES[how](_board(name))))
    assert got["unrouted"] == base["unrouted"] == 0
    assert got["vias"] == base["vias"]
    assert got["length"] == pytest.approx(base["length"], rel=0.05)


@pytest.mark.parametrize("how", list(OTHERS))
@pytest.mark.parametrize("name", SMALL)
def test_more_room_or_another_part_order_routes_no_worse(name, how):
    _no_worse(name, _route(OTHERS[how](_board(name))))
