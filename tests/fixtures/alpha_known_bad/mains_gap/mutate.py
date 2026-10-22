"""
mutate.py — the mains_gap case: a mains net and a SELV net, far too close.

THE DEFECT
----------
This board switches mains through a relay contact and reads a DHT22 on the
same card. The mains net (MAINS_L) leaves the relay's COM contact and runs to
a terminal block that brings mains onto the board. The SELV side of the board
is the same ATmega328P + DHT22 + 2N2222A + relay board the other cases use,
copper for copper.

In THIS board the mains run and the DHT22's data trace are 0.35 mm apart.
The separation a mains-to-SELV boundary needs at 250 V with reinforced
insulation is 5.0 mm (IEC 60664-1 Table F.4, PD2, group III, doubled basic
insulation). 0.35 mm is seven percent of it. The board in board_base.json is
the same board with the same two runs 5.85 mm apart, which is over the
requirement and is the layout the base board ships.

The gap is a real distance between real copper: the 0.8 mm mains trace on
F.Cu and the 0.3 mm DHT22_DATA trace on F.Cu, measured edge to edge, along
the 3 mm where they run side by side. It can be measured in KiCad with the
measure tool and it comes out at 0.35 mm. measure.py in this directory does
it from the file and prints the number.

THE BOARD
---------
The SELV half of the board is the PRODUCT's own board: the netlist in
netlist.json is backend/pcb_engine/netlist_dht22.json with three additions,
and the product's own compile_board() places and routes everything it knows
how to place. The half of the board the product cannot do — the mains
domain — is authored here, and the manifest says so:

  * J1, a two-pin mains terminal block, is placed at (49.0, 6.0) mm, at the
    bottom right of the board, where the incoming mains would enter.
  * MAINS_L runs from the relay's COM contact (K1 pad 3, at (44.29, 26.71))
    down the right-hand corridor to that terminal block.
  * A B.Cu keepout ("mains corridor") cuts the ground pour back under that
    corridor, because a ground pour under a mains run is its own problem
    even when the surface creepage is right.

The product has no mains template, no mains terminal block part and no
insulation rule of any kind. Its only clearances are net-class DRC
clearances in millimetres (0.25 mm signal, 0.3 mm power) — the kind of
number a DRC uses to keep copper from touching, not the kind that keeps a
250 V conductor an arm's length from a 5 V one. Left to itself the product
put J1 next to the relay and drew MAINS_L as a 0.8 mm straight line at
y = 26.8 mm, 13 mm from anything: compliant by luck, not by rule. The defect
below is what a layout gets when that luck runs out.

HOW THE GAP IS MADE — THE RULE
------------------------------
The rule is one number. Write the mains run's vertical segment at x = X, and
the DHT22_DATA trace runs vertically at x = 39.6 mm with a 0.3 mm width, so
its right-hand edge is at 39.75 mm. The mains run is 0.8 mm wide, so its
left-hand edge is at X - 0.4 mm. The copper-to-copper gap between them is

    (X - 0.4) - 39.75 = X - 40.15

  * the base board  : gap 5.85 mm  ->  X = 46.0 mm
  * the defect      : gap 0.35 mm  ->  X = 40.5 mm

Nothing else changes. The terminal block, the keepout, the relay, the SELV
copper, the nets, the pads and the vias are byte-identical between the two
boards; the mains run moves 5.5 mm to the left and comes to rest beside the
data trace.

Both numbers are derived from the board at run time, not typed in: the
anchor x = 39.6 mm and its 0.3 mm width are read out of the DHT22_DATA
track, and X is computed from the gap. Change the board and the rule still
holds.

THE REQUIREMENT IS NOT QUALIFIED
--------------------------------
The 5.0 mm figure is quoted from IEC 60664-1 Table F.4 and nobody in this
project has qualified it. The GEOMETRY is exact: two pieces of copper in a
file, a distance you can measure, a number you can reproduce. The
REQUIREMENT is a table value, taken on trust. The manifest says the same
thing, because a case that hid it would be claiming more than it knows.

DETERMINISM AND IDEMPOTENCE
----------------------------
No randomness, no wall clock, no network. The board comes from the product's
own compiler, which is deterministic, and the seed is a pure function of the
board it is given: seed(seed(x)) == seed(x). Running this file twice writes
byte-identical files.

    python tests/fixtures/alpha_known_bad/mains_gap/mutate.py
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

# ── the case's constants ────────────────────────────────────────────────────
MAINS_NET = "MAINS_L"          # the net that carries mains
SELV_NET = "DHT22_DATA"        # the SELV net the mains run comes too close to
RELAY_REF = "K1"               # the relay whose COM contact carries mains
TERMINAL_REF = "J1"            # the mains terminal block

CREEPAGE_MM = 5.0              # IEC 60664-1 Table F.4, PD2, group III
BASE_GAP_MM = 5.85             # what board_base.json has
DEFECT_GAP_MM = 0.35           # what board_defective.json has

MAINS_WIDTH = 0.8              # the mains run's width (the power net class)
MAINS_LAYER = "F.Cu"

#: Where the fixture puts the mains terminal block: bottom right, where the
#: incoming mains would enter the board. The product's own greedy placer
#: drops it next to the relay instead (see the module docstring).
TERMINAL_AT = (49.0, 6.0)

#: A keepout that cuts the ground pour back under the mains corridor. It is
#: the same in the base board and in the defective board, so it is not part
#: of the defect; it is the part of a mains layout the product cannot draw.
CORRIDOR_KEEPOUT = {
    "kind": "wire",
    "layer": "B.Cu",
    "x": 39.0,
    "y": 1.0,
    "w": 13.0,
    "h": 39.0,
    "reason": "mains corridor: keep the ground pour clear of the mains run",
}

_HERE = pathlib.Path(__file__).resolve().parent
_REPO = _HERE.parents[3]                     # mains_gap -> alpha_known_bad -> fixtures -> tests -> repo
_PRODUCT_NETLIST = _REPO / "backend" / "pcb_engine" / "netlist_dht22.json"
_OUT = _HERE


# ── geometry ────────────────────────────────────────────────────────────────
# The measurement is edge to edge, everywhere: a track is its centreline
# swept by half its width, a pad is its rectangle, a via is its disc.

def _pt_seg(px, py, a, b) -> float:
    """Distance from a point to a segment."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _orient(p, q, r) -> int:
    v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if v > 1e-12:
        return 1
    if v < -1e-12:
        return -1
    return 0


def _on_seg(p, q, r) -> bool:
    """Is r on the segment pq?"""
    return (min(p[0], q[0]) - 1e-12 <= r[0] <= max(p[0], q[0]) + 1e-12 and
            min(p[1], q[1]) - 1e-12 <= r[1] <= max(p[1], q[1]) + 1e-12)


def _seg_seg(a, b, c, d) -> float:
    """Distance between two segments; 0.0 if they touch or cross."""
    o1, o2 = _orient(a, b, c), _orient(a, b, d)
    o3, o4 = _orient(c, d, a), _orient(c, d, b)
    if o1 != o2 and o3 != o4:
        return 0.0
    if o1 == 0 and _on_seg(a, b, c):
        return 0.0
    if o2 == 0 and _on_seg(a, b, d):
        return 0.0
    if o3 == 0 and _on_seg(c, d, a):
        return 0.0
    if o4 == 0 and _on_seg(c, d, b):
        return 0.0
    return min(_pt_seg(a[0], a[1], c, d), _pt_seg(b[0], b[1], c, d),
               _pt_seg(c[0], c[1], a, b), _pt_seg(d[0], d[1], a, b))


def _pt_rect(px, py, r) -> float:
    """Distance from a point to a rectangle (x0, y0, x1, y1)."""
    dx = max(r[0] - px, 0.0, px - r[2])
    dy = max(r[1] - py, 0.0, py - r[3])
    return math.hypot(dx, dy)


def _seg_rect(a, b, r) -> float:
    """Distance from a segment to a rectangle; 0.0 if it touches or enters."""
    if _pt_rect(a[0], a[1], r) == 0.0 or _pt_rect(b[0], b[1], r) == 0.0:
        return 0.0
    edges = ((r[0], r[1], r[2], r[1]), (r[2], r[1], r[2], r[3]),
             (r[2], r[3], r[0], r[3]), (r[0], r[3], r[0], r[1]))
    for e in edges:
        if _seg_seg(a, b, (e[0], e[1]), (e[2], e[3])) == 0.0:
            return 0.0
    return min(_pt_rect(a[0], a[1], r), _pt_rect(b[0], b[1], r))


def _rect_rect(r1, r2) -> float:
    dx = max(r1[0] - r2[2], 0.0, r2[0] - r1[2])
    dy = max(r1[1] - r2[3], 0.0, r2[1] - r1[3])
    return math.hypot(dx, dy)


# ── the board as copper ─────────────────────────────────────────────────────

ALL_LAYERS = ("F.Cu", "B.Cu")


def _copper(board: dict):
    """Every piece of copper in the board, as (net, layers, kind, shape).

    A track lives on one layer. A via is a disc through the whole board. A
    through-hole pad (shape "th") is copper on every layer, which is what
    the product's own DRC and verifier treat it as.
    """
    for comp in board.get("components", []):
        for pad in comp.get("pads", []):
            if not pad.get("net"):
                continue
            layers = set(ALL_LAYERS) if pad.get("shape") == "th" else {pad.get("layer")}
            yield (pad["net"], layers, "pad", pad)
    for t in board.get("tracks", []):
        yield (t["net"], {t["layer"]}, "track", t)
    for v in board.get("vias", []):
        yield (v["net"], set(ALL_LAYERS), "via", v)


def _obj_gap(a, b) -> float:
    """Edge-to-edge distance between two copper objects."""
    (ka, sa), (kb, sb) = a, b
    if ka == "track" and kb == "track":
        pts_a, wa = sa["points"], sa["width"] / 2.0
        pts_b, wb = sb["points"], sb["width"] / 2.0
        d = min(_seg_seg(tuple(p), tuple(q), tuple(r), tuple(s))
                for p, q in zip(pts_a, pts_a[1:])
                for r, s in zip(pts_b, pts_b[1:]))
        return d - wa - wb
    if ka == "pad" and kb == "pad":
        ra = (sa["x"] - sa["w"] / 2, sa["y"] - sa["h"] / 2,
              sa["x"] + sa["w"] / 2, sa["y"] + sa["h"] / 2)
        rb = (sb["x"] - sb["w"] / 2, sb["y"] - sb["h"] / 2,
              sb["x"] + sb["w"] / 2, sb["y"] + sb["h"] / 2)
        if sa.get("shape") == "round" or sb.get("shape") == "round":
            return _disc_rect_gap(sa, sb)
        return _rect_rect(ra, rb)
    if ka == "track" and kb == "pad":
        return _track_pad_gap(sa, sb)
    if ka == "pad" and kb == "track":
        return _track_pad_gap(sb, sa)
    if ka == "track" and kb == "via":
        pts, w = sa["points"], sa["width"] / 2.0
        r = sb["diameter"] / 2.0
        d = min(_pt_seg(sb["x"], sb["y"], tuple(p), tuple(q))
                for p, q in zip(pts, pts[1:]))
        return d - w - r
    if ka == "via" and kb == "track":
        return _obj_gap(b, a)
    if ka == "via" and kb == "pad":
        r = sa["diameter"] / 2.0
        if sb.get("shape") == "round":
            return math.hypot(sa["x"] - sb["x"], sa["y"] - sb["y"]) - r - sb["w"] / 2
        rb = (sb["x"] - sb["w"] / 2, sb["y"] - sb["h"] / 2,
              sb["x"] + sb["w"] / 2, sb["y"] + sb["h"] / 2)
        return _pt_rect(sa["x"], sa["y"], rb) - r
    if ka == "pad" and kb == "via":
        return _obj_gap(b, a)
    if ka == "via" and kb == "via":
        return (math.hypot(sa["x"] - sb["x"], sa["y"] - sb["y"])
                - sa["diameter"] / 2.0 - sb["diameter"] / 2.0)
    raise ValueError(f"unknown copper kinds {ka} {kb}")


def _track_pad_gap(track: dict, pad: dict) -> float:
    w = track["width"] / 2.0
    if pad.get("shape") == "round":
        r = pad["w"] / 2.0
        d = min(_pt_seg(pad["x"], pad["y"], tuple(p), tuple(q))
                for p, q in zip(track["points"], track["points"][1:]))
        return d - w - r
    rect = (pad["x"] - pad["w"] / 2, pad["y"] - pad["h"] / 2,
            pad["x"] + pad["w"] / 2, pad["y"] + pad["h"] / 2)
    d = min(_seg_rect(tuple(p), tuple(q), rect)
            for p, q in zip(track["points"], track["points"][1:]))
    return d - w


def _disc_rect_gap(a: dict, b: dict) -> float:
    """Distance between a round pad and a rectangular pad."""
    ra = (b["x"] - b["w"] / 2, b["y"] - b["h"] / 2,
          b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
    return _pt_rect(a["x"], a["y"], ra) - a["w"] / 2


def gaps_to_mains(board: dict, mains_net: str = MAINS_NET) -> dict:
    """Minimum edge-to-edge gap from the mains copper to every other net.

    Returns {net: (gap_mm, description)}. Only copper that shares a layer
    with the mains copper is compared: creepage is a distance along one
    surface.
    """
    copper = list(_copper(board))
    mains = [c for c in copper if c[0] == mains_net]
    out: dict[str, tuple[float, str]] = {}
    for net, layers, kind, shape in copper:
        if net == mains_net:
            continue
        best = None
        for mnet, mlayers, mkind, mshape in mains:
            if not (mlayers & layers):
                continue
            d = _obj_gap((mkind, mshape), (kind, shape))
            if best is None or d < best[0]:
                best = (d, f"{mkind} {mnet} vs {kind} {net}")
        if best is None:
            continue
        if net not in out or best[0] < out[net][0]:
            out[net] = best
    return out


# ── the mains domain: the part of the board the product cannot draw ────────

def _normalise(board: dict) -> dict:
    """A board as plain JSON, so a diff of two boards is a diff of dicts."""
    return json.loads(json.dumps(board))


def _component(board: dict, ref: str) -> dict:
    for comp in board.get("components", []):
        if comp.get("ref") == ref:
            return comp
    raise KeyError(f"no component {ref} on this board")


def _place_terminal(board: dict) -> None:
    """Put the mains terminal block where the fixture wants it.

    The product's greedy placer has no idea that this part carries mains: it
    drops the terminal block next to the relay and leaves the rest of the
    board alone. A mains terminal block belongs at the board edge the mains
    enters through, so the fixture moves it there. The move is written into
    the board, and the pads move with it.
    """
    comp = _component(board, TERMINAL_REF)
    dx = TERMINAL_AT[0] - comp["x"]
    dy = TERMINAL_AT[1] - comp["y"]
    if dx == 0.0 and dy == 0.0:
        return
    comp["x"] = TERMINAL_AT[0]
    comp["y"] = TERMINAL_AT[1]
    for pad in comp.get("pads", []):
        pad["x"] += dx
        pad["y"] += dy


def _selv_anchor(board: dict) -> tuple[float, float]:
    """The SELV trace the mains run runs beside: its x and its width.

    It is the SELV track of the named net that reaches furthest to the
    right — on this board the DHT22's data trace, which runs vertically
    down the right-hand side of the sensor cluster at x = 39.6 mm.
    """
    best = None
    for t in board.get("tracks", []):
        if t.get("net") != SELV_NET or t.get("layer") != MAINS_LAYER:
            continue
        mx = max(p[0] for p in t["points"])
        if best is None or mx > best[0]:
            best = (mx, t)
    if best is None:
        raise SystemExit(f"no {SELV_NET} track on {MAINS_LAYER} to run beside")
    return best[0], best[1]["width"]


def _run_x(board: dict, gap_mm: float) -> float:
    """Where the mains run's vertical goes, for a given copper-to-copper gap.

    gap = (X - mains_width/2) - (anchor_x + anchor_width/2)
    """
    anchor_x, anchor_w = _selv_anchor(board)
    return anchor_x + anchor_w / 2.0 + gap_mm + MAINS_WIDTH / 2.0


def _mains_route(board: dict, gap_mm: float) -> dict:
    """The mains run, from the relay's COM contact to the terminal block.

    Two points are read out of the board: the relay's contact pad (where the
    run starts) and the terminal block's mains pad (where it ends). The run
    goes sideways to the corridor, down the corridor, and sideways to the
    terminal.
    """
    relay = _component(board, RELAY_REF)
    contact = next(p for p in relay["pads"] if p.get("net") == MAINS_NET)
    terminal = _component(board, TERMINAL_REF)
    end = next(p for p in terminal["pads"] if p.get("net") == MAINS_NET)
    x = _run_x(board, gap_mm)
    return {
        "layer": MAINS_LAYER,
        "net": MAINS_NET,
        "width": MAINS_WIDTH,
        "points": [[contact["x"], contact["y"]], [x, contact["y"]],
                   [x, end["y"]], [end["x"], end["y"]]],
        "rev": 0,
    }


def _mains_domain(board: dict, gap_mm: float) -> dict:
    """The whole mains domain, at a given gap: terminal, run, keepout."""
    board = _normalise(board)
    _place_terminal(board)
    board["tracks"] = [t for t in board["tracks"] if t.get("net") != MAINS_NET]
    board["vias"] = [v for v in board["vias"] if v.get("net") != MAINS_NET]
    board["tracks"].append(_mains_route(board, gap_mm))
    keepouts = [k for k in board.get("keepouts", [])
                if k.get("reason") != CORRIDOR_KEEPOUT["reason"]]
    keepouts.append(dict(CORRIDOR_KEEPOUT))
    board["keepouts"] = keepouts
    return board


# ── the public API ──────────────────────────────────────────────────────────

def seed(base_board_json: dict) -> dict:
    """Seed the defect: move the mains run to 0.35 mm from the data trace.

    Idempotent. seed(seed(x)) == seed(x), because the rule is a function of
    the board and the board it is given already satisfies it.
    """
    board = _mains_domain(base_board_json, DEFECT_GAP_MM)
    if _mains_domain(board, DEFECT_GAP_MM) != board:
        raise SystemExit("the seed is not idempotent")
    return board


def seed_netlist(netlist: dict) -> dict:
    """No-op. The defect is copper, not netlist.

    The netlist says a mains net exists (that is a requirement, not a
    defect): the relay's COM contact and the terminal block's first position
    are on MAINS_L, and MAINS_L is a power net, so it is drawn 0.8 mm wide.
    Where that copper goes is the defect, and copper lives in the board.
    """
    return json.loads(json.dumps(netlist))


def defect_site(board_json: dict) -> dict:
    """Where the defect is, for the record: the run and its nearest neighbour."""
    gaps = gaps_to_mains(board_json)
    nearest = min(gaps.items(), key=lambda kv: kv[1][0])
    run = next(t for t in board_json["tracks"] if t.get("net") == MAINS_NET)
    return {
        "mains_run_points": run["points"],
        "mains_run_width": run["width"],
        "nearest_net": nearest[0],
        "nearest_gap_mm": round(nearest[1][0], 6),
        "requirement_mm": CREEPAGE_MM,
    }


# ── the netlist and the board the case is built on ─────────────────────────

def mains_netlist() -> dict:
    """The product's netlist, with the mains domain added to it.

    Three changes and no more:
      * the relay's COM contact (K1 pad 3) is on MAINS_L,
      * J1, a two-pin mains terminal block, is on the board, its first
        position on MAINS_L,
      * MAINS_L is a power net, so it is drawn 0.8 mm wide, as a mains run
        is drawn.
    """
    netlist = json.loads(_PRODUCT_NETLIST.read_text(encoding="utf-8"))
    for comp in netlist["components"]:
        if comp["ref"] == RELAY_REF:
            comp["pins"]["3"] = MAINS_NET
    netlist["components"].append({
        "ref": TERMINAL_REF,
        "mpn": "22-27-2021",
        "pins": {"1": MAINS_NET},
        "package": "THT 2.54 mm, 2-pin",
        "type": "connector",
    })
    netlist["power_nets"].append(MAINS_NET)
    return netlist


def _product_board(netlist: dict) -> dict:
    """The product's own board for that netlist, as a dict."""
    engine = str(_REPO / "backend" / "pcb_engine")
    if engine not in sys.path:
        sys.path.insert(0, engine)
    from compile_board import compile_board
    result = compile_board(netlist)
    return json.loads(result.board.to_json())


def _regenerate() -> int:
    netlist = mains_netlist()
    product_board = _product_board(netlist)
    base = _mains_domain(product_board, BASE_GAP_MM)
    defective = seed(base)

    (_OUT / "board_base.json").write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
    (_OUT / "board_defective.json").write_text(json.dumps(defective, indent=2) + "\n", encoding="utf-8")
    (_OUT / "netlist.json").write_text(json.dumps(netlist, indent=2) + "\n", encoding="utf-8")

    base_gaps = gaps_to_mains(base)
    defect_gaps = gaps_to_mains(defective)
    base_min = min(base_gaps.items(), key=lambda kv: kv[1][0])
    defect_min = min(defect_gaps.items(), key=lambda kv: kv[1][0])
    print(f"base board     : nearest other net {base_min[0]} at {base_min[1][0]:.3f} mm")
    print(f"defective board: nearest other net {defect_min[0]} at {defect_min[1][0]:.3f} mm")
    print(f"requirement    : {CREEPAGE_MM:.1f} mm (IEC 60664-1 Table F.4)")
    print(f"seed is idempotent: {seed(defective) == defective}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_regenerate())
