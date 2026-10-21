"""
mutate.py — seed ONE physical defect: a deleted via.

THE DEFECT
----------
A via is a plated hole that carries a net between two copper layers. Delete
one and the net it was carrying splits into two islands of copper: the two
pads it joined are no longer electrically the same point, and the board comes
back from the factory with a wire that goes nowhere.

The fault is invisible in a drawing. Every pad is still on its net, every
track still has its width, the board outline is unchanged, and the schematic
still says what it always said. What is gone is the only piece of copper that
made two things one thing. Only a connectivity check can see it.

WHY THIS FILE IS SELF-CONTAINED
--------------------------------
The seeding rule below is a connectivity argument, not a coordinate lookup, so
it is written out here in full rather than imported: the fixture has to be
readable and auditable on its own, and it has to be importable from a harness
that knows nothing about the backend. The geometry it uses is the same
geometry `backend/pcb_engine/kernel.py` and `backend/pcb_engine/verify.py`
use, and the numbers below (the contact tolerance in particular) are the same
numbers those two files use — the seed selects the via that BOTH of them
independently agree is load-bearing, which is what `__main__` below asserts.

THE RULE
--------
Among the vias on the board, take those that

    1. carry a net whose copper exists on more than one signal layer — a via
       that does not transition layers is not carrying anything between
       layers, so deleting it is not this defect class; and
    2. are load-bearing: removing the via opens a required connection that
       was closed before it was removed, or strands a pad from the copper
       plane that was reaching it.

Delete exactly one of them, chosen deterministically. If the board carries
none, the board is already defective in this way, and seeding is a no-op.

"Opens a required connection" is decided the way verify.py's III.1 decides
it: a union-find over EVERY piece of copper on the board, with no regard for
net. That is not an accident of implementation. Two nets' copper that touch
are a short, and a short joins them — so a net-scoped union would call a
bridged net "connected" while the verifier calls it short, and the seed
could pick a via the product does not think is load-bearing. The seed's job
is to be SEEN, so it asks the detector's question, not a private one.

DETERMINISM AND IDEMPOTENCE
----------------------------
No randomness, no wall-clock, no I/O outside the function's arguments. The
choice among candidates is a total order on (net, x, y), so the same input
always yields the same output. Running `seed` on its own output changes
nothing: with the via already gone there is no longer a via whose removal
opens a connection, so the rule finds no candidate and returns the board
unchanged.
"""
from __future__ import annotations

import copy
import math
import pathlib
from typing import Any

# Copper closer than this is one piece. The same number, for the same reason,
# in backend/pcb_engine/kernel.py (CONTACT_TOL) and verify.py (CONTACT_TOL):
# below any fab's minimum feature, so a gap this small is not a gap a board
# house can make. If this file disagreed with those two, the seed would pick
# a via the product does not think is load-bearing.
CONTACT_TOL = 0.06

Board = dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Geometry — the subset of copper-contact rules the argument needs
# ─────────────────────────────────────────────────────────────────────────────
def _seg_point_dist(a, b, p) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0.0:
        return math.dist(a, p)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.dist((ax + t * dx, ay + t * dy), p)


def _seg_seg_dist(a, b, c, d) -> float:
    """Exact minimum distance between segments ab and cd; 0.0 if they cross."""
    if (_ccw(a, b, c) * _ccw(a, b, d) < 0) and (_ccw(c, d, a) * _ccw(c, d, b) < 0):
        return 0.0
    return min(_seg_point_dist(a, b, c), _seg_point_dist(a, b, d),
               _seg_point_dist(c, d, a), _seg_point_dist(c, d, b))


def _ccw(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _corners(rect) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """The four edges of an axis-aligned rectangle, as corner pairs."""
    x0, y0, x1, y1 = rect
    c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [(c[i], c[(i + 1) % 4]) for i in range(4)]


def _seg_rect_dist(a, b, rect) -> float:
    """Distance from segment ab to an axis-aligned rectangle; 0 if it enters."""
    x0, y0, x1, y1 = rect
    for p in (a, b):
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            return 0.0
    return min(_seg_seg_dist(a, b, c0, c1) for c0, c1 in _corners(rect))


def _rect_rect_dist(a, b) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return math.hypot(max(bx0 - ax1, 0.0, ax0 - bx1),
                      max(by0 - ay1, 0.0, ay0 - by1))


def _pad_bbox(pad) -> tuple[float, float, float, float]:
    return (pad["x"] - pad["w"] / 2, pad["y"] - pad["h"] / 2,
            pad["x"] + pad["w"] / 2, pad["y"] + pad["h"] / 2)


def _pad_center(pad) -> tuple[float, float]:
    return (pad["x"], pad["y"])


def _pad_is_round(pad) -> bool:
    return pad.get("shape") == "round"


def _pad_is_th(pad) -> bool:
    """A through-hole pad has a barrel: it meets copper on every layer."""
    return pad.get("shape") == "th"


def _pad_point_dist(pad, p) -> float:
    """Distance from a point to a pad's copper; zero inside it."""
    if _pad_is_round(pad):
        r = max(pad["w"], pad["h"]) / 2
        return max(0.0, math.dist(_pad_center(pad), p) - r)
    return _seg_rect_dist(p, p, _pad_bbox(pad))


def _pad_seg_dist(pad, a, b) -> float:
    """Distance from a segment centreline to a pad's copper."""
    if _pad_is_round(pad):
        r = max(pad["w"], pad["h"]) / 2
        return max(0.0, _seg_point_dist(_pad_center(pad), a, b) - r)
    return _seg_rect_dist(a, b, _pad_bbox(pad))


def _pad_pad_dist(a, b) -> float:
    if _pad_is_round(a) and _pad_is_round(b):
        return max(0.0, math.dist(_pad_center(a), _pad_center(b))
                   - max(a["w"], a["h"]) / 2 - max(b["w"], b["h"]) / 2)
    if _pad_is_round(a):
        return _pad_point_dist(a, _pad_center(b))
    if _pad_is_round(b):
        return _pad_point_dist(b, _pad_center(a))
    return _rect_rect_dist(_pad_bbox(a), _pad_bbox(b))


def _track_segments(track) -> list[tuple[tuple, tuple]]:
    pts = [(p[0], p[1]) for p in track["points"]]
    return list(zip(pts, pts[1:]))


# ─────────────────────────────────────────────────────────────────────────────
# Contact — do two pieces of copper make one piece?
# ─────────────────────────────────────────────────────────────────────────────
def _pad_pad_touch(a, b, tol) -> bool:
    if not (_pad_is_th(a) or _pad_is_th(b) or a.get("layer") == b.get("layer")):
        return False
    return _pad_pad_dist(a, b) <= tol


def _pad_track_touch(pad, track, tol) -> bool:
    if not (_pad_is_th(pad) or pad.get("layer") == track.get("layer")):
        return False
    return any(_pad_seg_dist(pad, s[0], s[1]) <= track["width"] / 2 + tol
               for s in _track_segments(track))


def _pad_via_touch(pad, via, tol) -> bool:
    return _pad_point_dist(pad, (via["x"], via["y"])) <= via["diameter"] / 2 + tol


def _track_track_touch(a, b, tol) -> bool:
    if a.get("layer") != b.get("layer"):
        return False
    reach = a["width"] / 2 + b["width"] / 2 + tol
    return any(_seg_seg_dist(s[0], s[1], r[0], r[1]) <= reach
               for s in _track_segments(a) for r in _track_segments(b))


def _track_via_touch(track, via, tol) -> bool:
    return any(_seg_point_dist(s[0], s[1], (via["x"], via["y"]))
               <= track["width"] / 2 + via["diameter"] / 2 + tol
               for s in _track_segments(track))


def _via_via_touch(a, b, tol) -> bool:
    return math.dist((a["x"], a["y"]), (b["x"], b["y"])) \
        <= (a["diameter"] + b["diameter"]) / 2 + tol


# ─────────────────────────────────────────────────────────────────────────────
# The board, as plain data
# ─────────────────────────────────────────────────────────────────────────────
def _pads(board: Board) -> list[dict]:
    out = []
    for comp in board.get("components", []):
        for pad in comp.get("pads", []):
            if pad.get("net"):
                out.append(pad)
    return out


def _plane_nets(board: Board) -> set[str]:
    return {layer.get("plane_net") for layer in board.get("layers", [])
            if layer.get("plane_net")}


def _signal_layers(board: Board) -> set[str]:
    return {layer["name"] for layer in board.get("layers", [])
            if layer.get("type", "signal") == "signal"}


def _net_layers(board: Board, net: str) -> set[str]:
    """Which signal layers carry copper of this net."""
    layers: set[str] = set()
    for pad in _pads(board):
        if pad.get("net") == net:
            if _pad_is_th(pad):
                layers |= _signal_layers(board)
            else:
                layers.add(pad.get("layer"))
    for track in board.get("tracks", []):
        if track.get("net") == net:
            layers.add(track.get("layer"))
    return layers


def _required_pairs(board: Board) -> list[tuple[dict, dict]]:
    """The pairs of pads each net must join — the ratsnest.

    Mirrors Board.required_pairs() in backend/pcb_engine/board_ir.py: a minimum
    spanning tree per net over pad centres, excluding nets a copper plane
    satisfies on its own. A spanning tree over a net whose copper has split
    into islands must have an edge across the split, so an island counts here
    exactly when the net is truly open.
    """
    planes = _plane_nets(board)
    by_net: dict[str, list[dict]] = {}
    for pad in _pads(board):
        by_net.setdefault(pad["net"], []).append(pad)

    pairs: list[tuple[dict, dict]] = []
    for net, pads in by_net.items():
        if len(pads) < 2 or net in planes:
            continue
        inside = [pads[0]]
        outside = list(pads[1:])
        while outside:
            i, j, _ = min(
                ((i, j, math.dist(_pad_center(a), _pad_center(b)))
                 for i, a in enumerate(inside)
                 for j, b in enumerate(outside)),
                key=lambda t: t[2])
            pairs.append((inside[i], outside[j]))
            inside.append(outside.pop(j))
    return pairs


def _open_connections(board: Board) -> list[tuple[dict, dict]]:
    """Required connections whose two pads are in different pieces of copper.

    Union-find over EVERY copper object on the board — pads (including the
    netless ones), tracks and vias — with no regard for net. This is
    verify.py's own union (`verify._groups`), and it is net-agnostic on
    purpose: two nets' copper that touch are a short, and a short joins them.
    A net-scoped union would call a bridged net "connected" when the verifier
    calls it short, so the seed could pick a via the product does not think is
    load-bearing. The seed's job is to be SEEN, so it asks the detector's
    question, not a private one.
    """
    pairs = _required_pairs(board)
    if not pairs:
        return []

    items: list[tuple[str, dict]] = []
    for comp in board.get("components", []):
        for pad in comp.get("pads", []):
            items.append(("pad", pad))
    items += [("track", t) for t in board.get("tracks", [])]
    items += [("via", v) for v in board.get("vias", [])]

    parent = list(range(len(items)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(items)):
        ki, oi = items[i]
        for j in range(i + 1, len(items)):
            kj, oj = items[j]
            if find(i) == find(j):
                continue
            if _touch(ki, oi, kj, oj):
                parent[find(j)] = find(i)

    pad_index = {id(o): i for i, (k, o) in enumerate(items) if k == "pad"}
    return [(a, b) for a, b in pairs
            if find(pad_index[id(a)]) != find(pad_index[id(b)])]


def _touch(ka: str, a: dict, kb: str, b: dict) -> bool:
    if ka == "pad" and kb == "pad":
        return _pad_pad_touch(a, b, CONTACT_TOL)
    if ka == "pad" and kb == "track":
        return _pad_track_touch(a, b, CONTACT_TOL)
    if ka == "track" and kb == "pad":
        return _pad_track_touch(b, a, CONTACT_TOL)
    if ka == "pad" and kb == "via":
        return _pad_via_touch(a, b, CONTACT_TOL)
    if ka == "via" and kb == "pad":
        return _pad_via_touch(b, a, CONTACT_TOL)
    if ka == "track" and kb == "track":
        return _track_track_touch(a, b, CONTACT_TOL)
    if ka == "track" and kb == "via":
        return _track_via_touch(a, b, CONTACT_TOL)
    if ka == "via" and kb == "track":
        return _track_via_touch(b, a, CONTACT_TOL)
    if ka == "via" and kb == "via":
        return _via_via_touch(a, b, CONTACT_TOL)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# The seeding rule
# ─────────────────────────────────────────────────────────────────────────────
def _candidate_vias(board: Board) -> list[tuple[int, dict]]:
    """Vias whose removal opens a connection this defect class is about."""
    base_open = len(_open_connections(board))
    out: list[tuple[int, dict]] = []
    for idx, via in enumerate(board.get("vias", [])):
        net = via.get("net", "")
        # (1) a via that does not carry a net between layers is not this defect
        if len(_net_layers(board, net)) < 2:
            continue
        trial = copy.deepcopy(board)
        del trial["vias"][idx]
        # (2) load-bearing: removing it opens a connection that was closed
        if len(_open_connections(trial)) > base_open:
            out.append((idx, via))
    return out


def seed(base_board_json: dict) -> dict:
    """Return the Board IR dict with one load-bearing via deleted.

    Idempotent, deterministic, and free of randomness and wall-clock time.
    """
    board: Board = copy.deepcopy(base_board_json)
    candidates = _candidate_vias(board)
    if not candidates:
        # Nothing to delete: either the board has no via that carries a net
        # between layers, or the via is already gone (seeding is a no-op).
        return board
    # A total order, so the choice is the same every time.
    candidates.sort(key=lambda item: (item[1].get("net", ""),
                                      round(float(item[1].get("x", 0.0)), 6),
                                      round(float(item[1].get("y", 0.0)), 6)))
    idx, _via = candidates[0]
    del board["vias"][idx]
    return board


def seed_netlist(netlist: dict) -> dict:
    """A no-op, deliberately.

    This defect lives in the COPPER, not in the netlist. The netlist still
    says what it always said — the two pads are still on the same net — and
    the board that carries it is broken. Seeding the netlist would produce a
    different defect (a wrong net assignment), not this one.
    """
    return copy.deepcopy(netlist)


def removed_via(base_board_json: dict) -> dict | None:
    """The via `seed` would delete, or None. Diagnostics only."""
    candidates = _candidate_vias(copy.deepcopy(base_board_json))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[1].get("net", ""),
                                      round(float(item[1].get("x", 0.0)), 6),
                                      round(float(item[1].get("y", 0.0)), 6)))
    return copy.deepcopy(candidates[0][1])


# ─────────────────────────────────────────────────────────────────────────────
# Regenerate the fixture from the product's own netlist
# ─────────────────────────────────────────────────────────────────────────────
_HERE = pathlib.Path(__file__).resolve().parent
_REPO = _HERE.parents[3]          # deleted_via -> alpha_known_bad -> fixtures -> tests -> repo
_NETLIST = _REPO / "backend" / "pcb_engine" / "netlist_dht22.json"
_OUT = _HERE


def _regenerate() -> int:
    """Rebuild board_base.json and board_defective.json from the netlist.

    The base board is the product's own output: compile_board(netlist) — the
    same call POST /pcb/compile makes. The defect is then applied to that
    routed board, not to the netlist, because the fault has to be in what the
    product emits.

    Returns 0 only when the seed proves what it claims: III.1 passes on the
    clean board, fails on the defective one, and no other check moved.
    """
    import json
    import sys

    engine = str(_REPO / "backend" / "pcb_engine")
    if engine not in sys.path:
        sys.path.insert(0, engine)
    from compile_board import compile_board          # noqa: E402
    from verify import verify_board                   # noqa: E402

    netlist = json.loads(_NETLIST.read_text(encoding="utf-8"))
    result = compile_board(netlist)
    base = json.loads(result.board.to_json())
    defective = seed(base)

    (_OUT / "board_base.json").write_text(json.dumps(base, indent=2) + "\n",
                                           encoding="utf-8")
    (_OUT / "board_defective.json").write_text(json.dumps(defective, indent=2) + "\n",
                                                encoding="utf-8")
    (_OUT / "netlist.json").write_text(json.dumps(netlist, indent=2) + "\n",
                                       encoding="utf-8")

    statuses: dict[str, dict[str, str]] = {}
    for label, board in (("base", base), ("defective", defective)):
        rep = verify_board(_as_board(board), netlist)
        failed = [f"{f.check} ({f.status})" for f in rep.findings if f.status == "fail"]
        statuses[label] = {f.check: f.status for f in rep.findings}
        print(f"{label:>10}: ok={rep.ok} proven={rep.proven} "
              f"failed={failed or 'none'}")

    via = removed_via(base)
    print(f"removed via: {via}")

    base_ok = statuses["base"].get("III.1") == "pass"
    defect_bad = statuses["defective"].get("III.1") == "fail"
    changed = sorted(c for c in set(statuses["base"]) | set(statuses["defective"])
                     if statuses["base"].get(c) != statuses["defective"].get(c))
    print(f"III.1 pass on base: {base_ok}; fail on defective: {defect_bad}; "
          f"checks changed: {changed}")

    again = seed(defective)
    print(f"seed is idempotent: {again == defective}")
    print(f"seed does not touch its input: "
          f"{base == json.loads(result.board.to_json())}")

    ok = (base_ok and defect_bad and changed == ["III.1"]
          and again == defective and base != defective)
    print(f"\nTHE SEED IS PROVEN: {ok}")
    return 0 if ok else 1


def _as_board(board_json: dict):
    """Board IR dict -> the backend's Board object (only for diagnostics)."""
    import sys

    engine = str(_REPO / "backend" / "pcb_engine")
    if engine not in sys.path:
        sys.path.insert(0, engine)
    from board_ir import Board                 # noqa: E402
    import json as _json
    return Board.from_json(_json.dumps(board_json))


if __name__ == "__main__":
    raise SystemExit(_regenerate())
