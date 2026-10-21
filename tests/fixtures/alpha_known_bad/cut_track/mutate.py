"""
mutate.py — seed ONE physical defect: a cut track.

THE DEFECT
----------
A track is copper. Sever it and the net it carried splits into two islands:
the pads it joined are no longer electrically the same point, and the board
comes back from the factory with a trace that goes nowhere.

This is the most ordinary physical failure a board has. A track is scratched
by a routing bit, a panel is flexed, a solder mask step etches a hairline.
Nothing about the finished board LOOKS wrong — every pad is still on its net,
every other trace still has its width, the board outline is unchanged, and
the schematic still says what it always said. What is gone is the only piece
of copper that made two things one thing. Only a connectivity check can see
it.

HOW THE CUT IS MADE
-------------------
The track is not deleted. It is SEVERED: the run is split into two stubs with
a band of copper removed from the middle of one segment. The stub ends stay
exactly where the trace used to run, so the copper is still on the right path
with the right width — a fab house that pulled copper in a plating step or
lost a hairline in etch would leave exactly this. The removed band is one
track width across (at least 0.25 mm), which is four times the contact
tolerance the verifier works to, so the two stubs are unambiguously two
pieces of copper and not one.

Deleting the whole track instead would be a different defect: the copper is
absent, the outline of the connection is visibly wrong, and a reader of the
Board IR could spot it without any geometry. A cut is harder to see, and the
whole point of this class is that it is hard to see.

WHY THIS FILE IS SELF-CONTAINED
-------------------------------
The seeding rule below is a connectivity argument, not a coordinate lookup, so
it is written out here in full rather than imported: the fixture has to be
readable and auditable on its own, and it has to be importable from a harness
that knows nothing about the backend. The geometry it uses is the geometry
`backend/pcb_engine/verify.py` uses, and the numbers below (the contact
tolerance in particular) are the same numbers that file uses — the seed
selects a cut that the verifier itself agrees opens a required connection,
which is what `__main__` below asserts.

THE RULE
--------
A cut site is a (track, segment) pair such that

    1. the track carries a net that a copper plane does not already satisfy —
       a plane net is joined by the pour, not by a trace, so severing a trace
       on a plane net is not this defect class;
    2. the segment is long enough to hold the cut with a stub left on each
       side, so the result is two pieces of trace and not a stub and a stub;
    3. no via lies in the severed band — a via inside the band would either
       bridge the gap or be left dangling, and neither is "a trace that was
       cut"; and
    4. the cut OPENS a required connection: the net's copper that was one
       piece becomes two, and a connection the board was required to make
       can no longer be made.

Among the sites that satisfy all four, take the one whose segment is LONGEST.
A long straight run is the least ambiguous place to cut: the gap is far from
any pad, any via and any corner, so what the reader sees is a trace that
stops and starts again, and nothing else. Ties are broken by
(net, layer, track index, segment index) — a total order, so the same input
always yields the same output.

If the board carries no such site, the board is already defective in this
way, and seeding is a no-op.

DETERMINISM AND IDEMPOTENCE
----------------------------
No randomness, no wall-clock, no I/O outside the function's arguments. The
choice among candidates is a total order, so the same input always yields the
same output.

Running `seed` on its own output changes nothing. The output carries the
signature of the cut — two same-net, same-layer, same-width stubs whose
facing ends are separated by exactly one cut band, with the trace running
straight through the gap — and the seed recognises that signature and
returns the board unchanged. Without that test, a second call would cut a
second track: the first cut already opened a connection, but a cut on a
different net still opens another one, and the board would accumulate defects
instead of holding one.
"""
from __future__ import annotations

import copy
import json
import math
import pathlib
from typing import Any

# Copper closer than this is one piece. The same number, for the same reason,
# in backend/pcb_engine/kernel.py (CONTACT_TOL) and backend/pcb_engine/verify.py
# (CONTACT_TOL): below any fab's minimum feature, so a gap this small is not a
# gap a board house can make. If this file disagreed with those two, the seed
# would pick a cut the product does not think is open.
CONTACT_TOL = 0.06

#: The band of copper the cut removes, measured edge to edge. At least a
#: quarter of a millimetre — four times the contact tolerance, so the two
#: stubs are two pieces of copper and not one — and never narrower than the
#: track it cuts, so the copper looks severed rather than thinned.
CUT_BAND_MIN = 0.25

#: The shortest stub left on each side of the cut. Below this the cut is a
#: nick at the end of a trace rather than a severed run.
MIN_STUB = 0.5

Board = dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Geometry — the subset of copper-contact rules the argument needs.
#
# These are verify.py's rules, written out here so the fixture stands on its
# own. They are not a simplification of that file's geometry: they are the
# same measurements, so the seed and the verifier cannot disagree about what
# "connected" means.
# ─────────────────────────────────────────────────────────────────────────────
def _pt_seg(p, a, b) -> float:
    """Distance from a point to a segment."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist((px, py), (ax + t * dx, ay + t * dy))


def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segs_cross(a, b, c, d) -> bool:
    """Do segments ab and cd cross properly? An endpoint lying on the other
    segment is caught by the endpoint distances, so only the proper crossing
    is decided here."""
    d1, d2 = _cross(c, d, a), _cross(c, d, b)
    d3, d4 = _cross(a, b, c), _cross(a, b, d)
    return ((d1 > 0) != (d2 > 0) and d1 != 0 and d2 != 0 and
            (d3 > 0) != (d4 > 0) and d3 != 0 and d4 != 0)


def _seg_seg(a, b, c, d) -> float:
    """Distance between segments ab and cd."""
    if _segs_cross(a, b, c, d):
        return 0.0
    return min(_pt_seg(a, c, d), _pt_seg(b, c, d),
               _pt_seg(c, a, b), _pt_seg(d, a, b))


def _corners(pad) -> list[tuple[float, float]]:
    """The four corners of a pad's rectangular copper."""
    x0, y0, x1, y1 = (pad["x"] - pad["w"] / 2, pad["y"] - pad["h"] / 2,
                      pad["x"] + pad["w"] / 2, pad["y"] + pad["h"] / 2)
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _pt_rect(p, pad) -> float:
    """Distance from a point to a rectangular pad's copper; zero inside it."""
    x0, y0, x1, y1 = (pad["x"] - pad["w"] / 2, pad["y"] - pad["h"] / 2,
                      pad["x"] + pad["w"] / 2, pad["y"] + pad["h"] / 2)
    dx = max(x0 - p[0], 0.0, p[0] - x1)
    dy = max(y0 - p[1], 0.0, p[1] - y1)
    return math.hypot(dx, dy)


def _pad_pt(pad, p) -> float:
    """Distance from a point to a pad's copper. 'th' pads are drawn square in
    this IR, so only 'round' is a disc."""
    if pad.get("shape") == "round":
        r = max(pad["w"], pad["h"]) / 2
        return max(0.0, math.dist((pad["x"], pad["y"]), p) - r)
    return _pt_rect(p, pad)


def _pad_seg(pad, a, b) -> float:
    """Distance from a segment (a centreline, zero width) to a pad's copper."""
    if pad.get("shape") == "round":
        r = max(pad["w"], pad["h"]) / 2
        return max(0.0, _pt_seg((pad["x"], pad["y"]), a, b) - r)
    if _pt_rect(a, pad) == 0.0 or _pt_rect(b, pad) == 0.0:
        return 0.0
    cs = _corners(pad)
    return min(_seg_seg(a, b, c, d) for c, d in zip(cs, cs[1:] + cs[:1]))


def _pad_pad(a, b) -> float:
    """Distance between two pads' copper."""
    if a.get("shape") == "round" and b.get("shape") == "round":
        return max(0.0, math.dist((a["x"], a["y"]), (b["x"], b["y"]))
                   - max(a["w"], a["h"]) / 2 - max(b["w"], b["h"]) / 2)
    if a.get("shape") == "round":
        return _pad_pad(b, a)
    if b.get("shape") == "round":
        return _pt_rect((b["x"], b["y"]), a) - max(b["w"], b["h"]) / 2
    ax0, ay0, ax1, ay1 = (a["x"] - a["w"] / 2, a["y"] - a["h"] / 2,
                          a["x"] + a["w"] / 2, a["y"] + a["h"] / 2)
    bx0, by0, bx1, by1 = (b["x"] - b["w"] / 2, b["y"] - b["h"] / 2,
                          b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
    return math.hypot(max(bx0 - ax1, 0.0, ax0 - bx1), max(by0 - ay1, 0.0, ay0 - by1))


def _layers_meet(a_layer: str, a_th: bool, b_layer: str, b_th: bool) -> bool:
    """Two copper objects on the same side meet; a through-hole pad meets a
    track on any layer, which is what shape == 'th' means in this IR."""
    return a_th or b_th or a_layer == b_layer


def _touches(ka: str, a: dict, kb: str, b: dict) -> bool:
    """Do two copper objects physically make contact? Net-agnostic: this is
    used to find both connectivity and the shorts connectivity must not
    create.

    Every case measures copper edge to copper edge: a track is its centreline
    swept by half its width, a via is a disc of its diameter.
    """
    if ka == "pad" and kb == "pad":
        if not _layers_meet(a.get("layer"), a.get("shape") == "th",
                            b.get("layer"), b.get("shape") == "th"):
            return False
        return _pad_pad(a, b) <= CONTACT_TOL
    if ka == "pad" and kb == "track":
        if not _layers_meet(a.get("layer"), a.get("shape") == "th",
                            b.get("layer"), False):
            return False
        return any(_pad_seg(a, p, q) <= b["width"] / 2 + CONTACT_TOL
                   for p, q in zip(b["points"], b["points"][1:]))
    if ka == "track" and kb == "pad":
        return _touches(kb, b, ka, a)
    if ka == "track" and kb == "track":
        if a.get("layer") != b.get("layer"):
            return False
        reach = a["width"] / 2 + b["width"] / 2 + CONTACT_TOL
        return any(_seg_seg(p, q, r, s) <= reach
                   for p, q in zip(a["points"], a["points"][1:])
                   for r, s in zip(b["points"], b["points"][1:]))
    if ka == "via" and kb == "track":
        return any(_pt_seg((a["x"], a["y"]), p, q)
                   <= a["diameter"] / 2 + b["width"] / 2 + CONTACT_TOL
                   for p, q in zip(b["points"], b["points"][1:]))
    if ka == "track" and kb == "via":
        return _touches(kb, b, ka, a)
    if ka == "via" and kb == "pad":
        return _pad_pt(b, (a["x"], a["y"])) <= a["diameter"] / 2 + CONTACT_TOL
    if ka == "pad" and kb == "via":
        return _touches(kb, b, ka, a)
    if ka == "via" and kb == "via":
        return math.dist((a["x"], a["y"]), (b["x"], b["y"])) <= \
            (a["diameter"] + b["diameter"]) / 2 + CONTACT_TOL
    return False


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
    """Nets a copper pour satisfies on its own — the ratsnest excludes them."""
    return {layer.get("plane_net") for layer in board.get("layers", [])
            if layer.get("plane_net")}


def _required_pairs(board: Board) -> list[tuple[dict, dict]]:
    """The pairs of pads each net must join — the ratsnest.

    Mirrors Board.required_pairs() in backend/pcb_engine/board_ir.py: a
    minimum spanning tree per net over pad centres, excluding nets a copper
    plane satisfies on its own.
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
                ((i, j, math.dist((a["x"], a["y"]), (b["x"], b["y"])))
                 for i, a in enumerate(inside)
                 for j, b in enumerate(outside)),
                key=lambda t: t[2])
            pairs.append((inside[i], outside[j]))
            inside.append(outside.pop(j))
    return pairs


def _copper_items(board: Board) -> list[tuple[str, dict]]:
    items: list[tuple[str, dict]] = [("pad", p) for p in _pads(board)]
    items += [("track", t) for t in board.get("tracks", [])]
    items += [("via", v) for v in board.get("vias", [])]
    return items


def _open_required_connections(board: Board) -> list[tuple[dict, dict]]:
    """Required connections whose two pads are in different pieces of copper.

    Union-find over EVERY copper object on the board, net-agnostic — the same
    union verify.py builds for its III.1 check, so "this cut opens a required
    connection" means exactly what III.1 means. (The base board is short-free,
    so net-agnostic and net-scoped unions agree; net-agnostic is used because
    it is the detector's own rule and cannot drift from it.)
    """
    pairs = _required_pairs(board)
    if not pairs:
        return []

    items = _copper_items(board)
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
            if _touches(ki, oi, kj, oj):
                parent[find(j)] = find(i)

    pad_index = {id(o): i for i, (k, o) in enumerate(items) if k == "pad"}
    return [(a, b) for a, b in pairs
            if find(pad_index[id(a)]) != find(pad_index[id(b)])]


# ─────────────────────────────────────────────────────────────────────────────
# The cut
# ─────────────────────────────────────────────────────────────────────────────
def _separation(width: float) -> float:
    """Centre-to-centre distance between the two stub ends of a cut.

    The copper edges end up `max(width, CUT_BAND_MIN)` apart, which is at
    least four contact tolerances — the two stubs are two pieces of copper,
    not one, by the verifier's own measure.
    """
    return max(width, CUT_BAND_MIN) + width


def _cut(board: Board, track_index: int, segment_index: int) -> Board:
    """Return a copy of `board` with one track severed mid-segment.

    The run becomes two tracks of the same net, layer and width, whose facing
    ends are `_separation(width)` apart and which run straight into each
    other. The copper is still on the original path; only a band of it is
    gone.
    """
    out = copy.deepcopy(board)
    t = out["tracks"][track_index]
    width = t["width"]
    sep = _separation(width)
    (ax, ay) = t["points"][segment_index]
    (bx, by) = t["points"][segment_index + 1]
    length = math.dist((ax, ay), (bx, by))
    ux, uy = (bx - ax) / length, (by - ay) / length
    mx, my = (ax + bx) / 2, (ay + by) / 2
    c0 = (mx - ux * sep / 2, my - uy * sep / 2)
    c1 = (mx + ux * sep / 2, my + uy * sep / 2)

    head = dict(t)
    head["points"] = [tuple(p) for p in t["points"][:segment_index + 1]] + [c0]
    tail = dict(t)
    tail["points"] = [c1] + [tuple(p) for p in t["points"][segment_index + 1:]]

    out["tracks"][track_index] = head
    out["tracks"].insert(track_index + 1, tail)
    return out


def _midpoint(track: dict, segment_index: int) -> tuple[float, float]:
    (ax, ay) = track["points"][segment_index]
    (bx, by) = track["points"][segment_index + 1]
    return ((ax + bx) / 2, (ay + by) / 2)


def _via_in_band(board: Board, mid: tuple[float, float], width: float) -> bool:
    """Does a via sit in the band the cut removes?

    A via inside the band would either bridge the gap — the net would not be
    open at all — or be left dangling on a stub, which is a different defect.
    Either way this is not "a trace that was cut".
    """
    reach = _separation(width) / 2
    for via in board.get("vias", []):
        if math.dist((via["x"], via["y"]), mid) <= \
                reach + via.get("diameter", 0.8) / 2 + CONTACT_TOL:
            return True
    return False


def _candidate_sites(board: Board) -> list[dict]:
    """The (track, segment) pairs whose cut opens a required connection."""
    base_open = len(_open_required_connections(board))
    planes = _plane_nets(board)
    out: list[dict] = []
    for ti, track in enumerate(board.get("tracks", [])):
        net = track.get("net", "")
        if net in planes:
            continue                                   # the pour joins it
        width = track.get("width", 0.0)
        sep = _separation(width)
        for si in range(len(track["points"]) - 1):
            length = math.dist(track["points"][si], track["points"][si + 1])
            if length < sep + 2 * MIN_STUB:
                continue                               # no room for two stubs
            mid = _midpoint(track, si)
            if _via_in_band(board, mid, width):
                continue                               # a via, not a cut
            if len(_open_required_connections(_cut(board, ti, si))) <= base_open:
                continue                               # the net survives the cut
            out.append({
                "net": net,
                "layer": track.get("layer", ""),
                "track_index": ti,
                "segment_index": si,
                "segment_length_mm": length,
                "track_width_mm": width,
                "gap_mm": max(width, CUT_BAND_MIN),
                "midpoint": [round(mid[0], 6), round(mid[1], 6)],
            })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# The signature of a board that is already cut
# ─────────────────────────────────────────────────────────────────────────────
def _unit(p, q):
    d = math.dist(p, q)
    if d == 0.0:
        return None
    return ((q[0] - p[0]) / d, (q[1] - p[1]) / d)


def _is_severed(board: Board) -> bool:
    """Does the board already carry a severed trace?

    The signature: two tracks of the same net, layer and width whose facing
    ends are separated by exactly one cut band, with the trace running
    straight through the gap, on a net the pour does not already satisfy —
    and with nothing else bridging that gap, so the two stubs really are two
    pieces of copper.

    The last clause is what keeps the test from firing on a coincidence. Two
    same-net tracks that happen to end one band apart and line up are not
    proof of anything unless the copper between them is actually gone, and
    "the copper between them is gone" is exactly the union-find question.
    """
    planes = _plane_nets(board)
    tracks = board.get("tracks", [])
    for a in tracks:
        if a.get("net") in planes or len(a["points"]) < 2:
            continue
        for b in tracks:
            if a is b or b.get("net") != a.get("net"):
                continue
            if b.get("layer") != a.get("layer") or b.get("width") != a.get("width"):
                continue
            if len(b["points"]) < 2:
                continue
            sep = _separation(a["width"])
            p, q = a["points"][-1], b["points"][0]
            if abs(math.dist(p, q) - sep) > 1e-6:
                continue
            ua = _unit(a["points"][-2], p)      # direction into the cut
            ub = _unit(q, b["points"][1])       # direction out of the cut
            ug = _unit(p, q)                    # direction across the cut
            if ua is None or ub is None or ug is None:
                continue
            if abs(ua[0] * ug[1] - ua[1] * ug[0]) > 1e-6:
                continue
            if abs(ub[0] * ug[1] - ub[1] * ug[0]) > 1e-6:
                continue
            if _gap_is_bridged(board, a, b):
                continue                       # the copper is still there
            return True
    return False


def _gap_is_bridged(board: Board, a: dict, b: dict) -> bool:
    """Is the gap between two stub ends still joined by some other copper?"""
    items = _copper_items(board)
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
            if _touches(ki, oi, kj, oj):
                parent[find(j)] = find(i)

    def group_of(track: dict) -> int | None:
        for i, (k, o) in enumerate(items):
            if k == "track" and o is track:
                return find(i)
        return None

    ga, gb = group_of(a), group_of(b)
    if ga is None or gb is None:
        return True                            # cannot tell; assume bridged
    return ga == gb


# ─────────────────────────────────────────────────────────────────────────────
# The seeding rule
# ─────────────────────────────────────────────────────────────────────────────
def _ordered(sites: list[dict]) -> list[dict]:
    """A total order on the sites: longest segment first, then a stable
    tie-break on the board's own coordinates."""
    return sorted(sites, key=lambda s: (-s["segment_length_mm"], s["net"],
                                        s["layer"], s["track_index"],
                                        s["segment_index"]))


def seed(base_board_json: dict) -> dict:
    """Return the Board IR dict with one load-bearing track severed.

    Idempotent, deterministic, and free of randomness and wall-clock time.
    The result is JSON-normalised (points are lists, not tuples), so writing
    it out and reading it back gives the same value — the shipped
    board_defective.json is exactly what this function returns.
    """
    board: Board = copy.deepcopy(base_board_json)
    if _is_severed(board):
        # Already cut. The defect is present; seeding again adds nothing.
        return _normalise(board)
    sites = _ordered(_candidate_sites(board))
    if not sites:
        # Nothing to cut: no segment of this board opens a required
        # connection when it is severed.
        return _normalise(board)
    site = sites[0]
    return _normalise(_cut(board, site["track_index"], site["segment_index"]))


def _normalise(board: Board) -> Board:
    """The board as plain JSON: lists where a list belongs, no tuples."""
    return json.loads(json.dumps(board))


def seed_netlist(netlist: dict) -> dict:
    """A no-op, deliberately.

    This defect lives in the COPPER, not in the netlist. The netlist still
    says what it always said — the two pads are still on the same net — and
    the board that carries it is broken. Seeding the netlist would produce a
    different defect (a wrong net assignment), not this one.
    """
    return copy.deepcopy(netlist)


def cut_site(base_board_json: dict) -> dict | None:
    """The site `seed` would cut, or None. Diagnostics only."""
    sites = _ordered(_candidate_sites(copy.deepcopy(base_board_json)))
    return copy.deepcopy(sites[0]) if sites else None


# ─────────────────────────────────────────────────────────────────────────────
# Regenerate the fixture from the product's own netlist
# ─────────────────────────────────────────────────────────────────────────────
_HERE = pathlib.Path(__file__).resolve().parent
_REPO = _HERE.parents[3]          # cut_track -> alpha_known_bad -> fixtures -> tests -> repo
_NETLIST = _REPO / "backend" / "pcb_engine" / "netlist_dht22.json"
_OUT = _HERE


def _regenerate() -> int:
    """Rebuild board_base.json and board_defective.json from the netlist.

    The base board is the product's own output: compile_board(netlist) — the
    same call POST /pcb/compile makes. The defect is then applied to that
    routed board, not to the netlist, because the fault has to be in what the
    product emits.
    """
    import sys

    engine = str(_REPO / "backend" / "pcb_engine")
    if engine not in sys.path:
        sys.path.insert(0, engine)
    from compile_board import compile_board          # noqa: PLC0415
    from verify import verify_board                   # noqa: PLC0415

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

    statuses = {}
    for label, board in (("base", base), ("defective", defective)):
        rep = verify_board(_as_board(board), netlist)
        failed = [f"{f.check} ({f.status})" for f in rep.findings if f.status == "fail"]
        statuses[label] = {f.check: f.status for f in rep.findings}
        print(f"{label:>10}: ok={rep.ok} proven={rep.proven} "
              f"failed={failed or 'none'}")

    site = cut_site(base)
    print(f"cut site: {site}")

    base_ok = statuses["base"].get("III.1") == "pass"
    defect_bad = statuses["defective"].get("III.1") == "fail"
    changed = sorted(c for c in set(statuses["base"]) | set(statuses["defective"])
                     if statuses["base"].get(c) != statuses["defective"].get(c))
    print(f"III.1 pass on base: {base_ok}; fail on defective: {defect_bad}; "
          f"checks changed: {changed}")

    # Idempotence: seeding the defective board changes nothing.
    again = seed(defective)
    print(f"seed is idempotent: {again == defective}")
    print(f"seed does not touch its input: {base == json.loads(result.board.to_json())}")

    return 0 if (base_ok and defect_bad and changed == ["III.1"]
                 and again == defective) else 1


def _as_board(board_json: dict):
    """Board IR dict -> the backend's Board object (only for diagnostics)."""
    import sys

    engine = str(_REPO / "backend" / "pcb_engine")
    if engine not in sys.path:
        sys.path.insert(0, engine)
    from board_ir import Board                 # noqa: PLC0415
    return Board.from_json(json.dumps(board_json))


if __name__ == "__main__":
    raise SystemExit(_regenerate())
