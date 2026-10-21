"""
mutate.py — seed ONE physical defect: a solder bridge between two nets.

THE DEFECT
----------
Two pads that belong to different nets are joined by a piece of copper that
the design never asked for. The copper is not a track the router drew and the
netlist never named: it is a lump of solder that ran between two pads while
the board was being assembled, or a bridged pair of pads that the stencil
left un-separated, or a piece of conductive debris that survived the wash.

On this board the bridge is drawn between U1's two supply pins:

    U1 pin 7   VCC_5V   the ATmega328P's supply
    U1 pin 8   GND     the ATmega328P's ground

U1 is a DIP-28: 2.54 mm pin pitch, 1.3 mm pads, so the copper edges of two
adjacent pins stand 1.24 mm apart. That is the canonical bridged-DIP gap, and
bridging it is the most common through-hole assembly defect there is: a
solder fillet that stands proud of the board wets across the gap to the next
pin, and the two pins become one node. Nothing in the assembly process
notices, because the board is not tested until after it is populated.

The fault is the most consequential one a board can carry that is not an
open. The ATmega's supply is tied to its ground. The rail collapses to a
few tens of millivolts, the part does not reset — it does not start — and
the board is dead in a way that looks like a dead chip. The relay coil, the
DHT22 and the LED are all fine; the board simply never runs. A technician
who does not suspect a short will replace the MCU, the DHT22 and the relay
before looking at the solder.

WHY IT IS INVISIBLE TO EVERYTHING THAT IS NOT A SHORT CHECK
------------------------------------------------------------
The defect lives in the COPPER. The netlist still says what it always said:
U1 pin 7 is VCC_5V and U1 pin 8 is GND, and those two nets are as different
as they were. Every pad still carries the net the design gives it. What has
changed is that a piece of metal now joins them, and the only question a
checker can ask about that is "is this one piece of copper carrying two
nets?".

That question is III.2, and it is decided on the exact rung: union-find over
every copper object on the board, net-agnostic, then a count of the distinct
nets each group carries. A group carrying more than one net is a short.
Nothing else in the tree asks the question, because nothing else can: III.1
asks whether each required connection is made (it is — both nets are still
routed), III.1c and III.1d ask whether the ground pour still reaches the
ground pads (it does), III.3 and III.4 ask whether the pin-to-net map matches
the netlist (it does), and IV.1 asks whether the land patterns match a table
(they do).

WHY THE BRIDGE IS ADDED, NOT MOVED
----------------------------------
A short can be seeded in two ways: by adding copper, or by moving copper
so that it reaches where it should not. Adding is the honest one here. A
solder bridge is EXTRA metal — it is not a reroute, and it is not the router
having made a mistake. It is also the harder case to catch, because the
defect is not a track that goes somewhere wrong; it is a track that is not
there at all in the design and not in the netlist either.

The bridge is drawn as a NETLESS track. That is what it is: a piece of
copper that belongs to no net, because no net was ever assigned to it. The
verifier's own group count is net-agnostic — it counts the nets each group
carries — so a netless track that touches two nets puts both nets in the
same group, and III.2 sees the short. A bridge that carried one of the two
nets would say, wrongly, that the designer had routed VCC_5V onto the ground
pad; the netless form says what a solder bridge actually is.

HOW THE BRIDGE IS SIZED
-----------------------
The bridge is a solder FILLET, so it is drawn at the width of the pads it
joins: a fillet on a 1.3 mm through-hole pad stands as wide as the pad, and
it bridges the gap because it wets onto the neighbour's shoulder. The seed
therefore takes the bridge's width from the pads, not from a constant, and
the fillet's reach is what decides which pad pairs are bridgeable at all.

HOW THE SITE IS CHOSEN
----------------------
The rule below is a contact argument, not a coordinate lookup, so it is
written out in full rather than imported: the fixture has to be readable and
auditable on its own, and it has to be importable from a harness that knows
nothing about the backend. The geometry it uses is the geometry
`backend/pcb_engine/verify.py` uses, and the numbers below (the contact
tolerance in particular) are the same numbers that file uses — the seed
selects a bridge that the verifier itself agrees is a short, which is what
`__main__` below asserts.

A bridge site is a pair of pads such that

    1. they are on the SAME layer, so a lump of solder can physically reach
       both of them;
    2. they carry DIFFERENT nets — the two ends of a bridge must be a short,
       and a bridge between one net and itself is a piece of metal doing
       nothing;
    3. they belong to the SAME component — a bridge inside one part is the
       ordinary way a short happens (solder across a DIP's pins, a bridged
       land pattern on a chip package), and it is the case a reader of the
       board can recognise;
    4. the gap between their copper is BRIDGEABLE: no wider than a solder
       fillet reaches, so that the bridge is a plausible assembly defect and
       not a piece of metal laid across the board; and
    5. the bridge, once drawn, touches copper of EXACTLY those two nets and
       nothing else — no third net, and no netless pad — so the short it
       creates is the one the reader is meant to find, and not a bigger one.

Among the sites that satisfy all five, the seed PREFERS A SUPPLY SHORT: a
pair whose two nets are both in the board's power net class. This is a
statement about which failure the calibration set needs to represent, not a
claim that the physics prefers it. A bridge that ties the supply to ground
destroys the board; a bridge between two signal nets makes one function
misbehave. If no supply-to-supply pair is bridgeable, the seed falls back to
the remaining bridgeable pairs.

Among the preferred pairs, take the one whose gap is SMALLEST: the closest
pair of pads is the pair a solder blob reaches first. Ties are broken by
(ref, pin_a, pin_b) — a total order, so the same input always yields the
same output.

If the board carries no such site, the board is already defective in this
way, and seeding is a no-op.

DETERMINISM AND IDEMPOTENCE
----------------------------
No randomness, no wall-clock, no I/O outside the function's arguments. The
choice among candidates is a total order, so the same input always yields
the same output.

Running `seed` on its own output changes nothing. The output carries the
signature of the bridge — a netless track on one layer whose two endpoints
sit exactly on the centres of two pads of different nets — and the seed
recognises that signature and returns the board unchanged. Without that
test, a second call would bridge a second pair: the first bridge already
made a short, but a bridge on another pair would make another one, and the
board would accumulate defects instead of holding one.

    python mutate.py          rebuild both boards and prove the difference
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
# would pick a bridge the product does not think is a short.
CONTACT_TOL = 0.06

#: The widest pad-to-pad gap a solder fillet is taken to bridge. A fillet on
#: a through-hole pin stands proud of the pad and wets onto the neighbour's
#: shoulder; on a 2.54 mm-pitch DIP with 1.3 mm pads the gap is 1.24 mm, and
#: bridging it is the most common through-hole assembly defect there is. A
#: gap wider than this is not a fillet that ran; it is a wire someone laid.
FILLET_SPAN_MAX = 1.3

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


def _power_nets(board: Board) -> set[str]:
    """The nets the board's power net class carries."""
    out: set[str] = set()
    for nc in board.get("net_classes", []):
        if nc.get("name") == "power":
            out |= {n for n in nc.get("nets", []) if n}
    return out


def _pad_pairs(board: Board) -> list[tuple[dict, dict]]:
    """Every pair of pads of one component that carry different nets."""
    out = []
    for comp in board.get("components", []):
        pads = [p for p in comp.get("pads", []) if p.get("net")]
        for i in range(len(pads)):
            for j in range(i + 1, len(pads)):
                a, b = pads[i], pads[j]
                if a["net"] == b["net"]:
                    continue
                out.append((a, b))
    return out


def _bridge(a: dict, b: dict) -> dict:
    """The bridge itself: a netless track from one pad centre to the other.

    Its width is the width of the pads it joins, because a solder fillet on a
    through-hole pad stands as wide as the pad and bridges the gap by
    wetting onto the neighbour's shoulder.
    """
    return {
        "layer": a.get("layer", "F.Cu"),
        "net": "",
        "width": max(a.get("w", 0.0), b.get("w", 0.0)),
        "points": [[a["x"], a["y"]], [b["x"], b["y"]]],
        "rev": 0,
    }


def _bridge_contacts(board: Board, bridge: dict) -> tuple[set[str], bool]:
    """The nets the bridge reaches, and whether it also reaches netless copper.

    A bridge that reached netless copper would be a bridge onto a dangling
    pad, not a bridge between two nets, and a reader of the board would have
    to work to see what it joined. A bridge that reached a THIRD net would be
    a short of three nets, which is a different defect from the one the
    reader is meant to find.
    """
    nets: set[str] = set()
    netless = False
    for comp in board.get("components", []):
        for pad in comp.get("pads", []):
            if not _touches("track", bridge, "pad", pad):
                continue
            if pad.get("net"):
                nets.add(pad["net"])
            else:
                netless = True
    for track in board.get("tracks", []):
        if _touches("track", bridge, "track", track) and track.get("net"):
            nets.add(track["net"])
    for via in board.get("vias", []):
        if _touches("track", bridge, "via", via) and via.get("net"):
            nets.add(via["net"])
    return nets, netless


def _candidate_sites(board: Board) -> list[dict]:
    """The pad pairs whose bridge is a short, and only a short."""
    out: list[dict] = []
    for a, b in _pad_pairs(board):
        # The two pads have to be on the same side of the board: a lump of
        # solder cannot reach through the board to the other side.
        if not _layers_meet(a.get("layer"), a.get("shape") == "th",
                            b.get("layer"), b.get("shape") == "th"):
            continue
        gap = _pad_pad(a, b)
        if gap > FILLET_SPAN_MAX:
            continue                                   # not bridgeable
        bridge = _bridge(a, b)
        nets, netless = _bridge_contacts(board, bridge)
        if netless:
            continue                                   # onto a dangling pad
        if nets != {a["net"], b["net"]}:
            continue                                   # a short, and only that
        out.append({
            "ref": a.get("ref", ""),
            "pin_a": a.get("pin", ""),
            "pin_b": b.get("pin", ""),
            "net_a": a["net"],
            "net_b": b["net"],
            "gap_mm": gap,
            "width_mm": bridge["width"],
            "layer": a.get("layer", "F.Cu"),
            "from": [a["x"], a["y"]],
            "to": [b["x"], b["y"]],
        })
    return out


def _ordered(sites: list[dict], power: set[str]) -> list[dict]:
    """A total order on the sites.

    A supply short comes first — a bridge that ties the supply to ground
    destroys the board, a bridge between two signal nets makes one function
    misbehave. That is a statement about which failure this calibration set
    needs to represent, and it is stated here rather than implied. Within a
    group, the closest pair of pads comes first (the pair a fillet reaches
    first), and the rest is a stable tie-break on the board's own naming.
    """
    def key(s: dict):
        supply = 0 if (s["net_a"] in power and s["net_b"] in power) else 1
        return (supply, s["gap_mm"], s["ref"], s["pin_a"], s["pin_b"])

    return sorted(sites, key=key)


# ─────────────────────────────────────────────────────────────────────────────
# The signature of a board that is already bridged
# ─────────────────────────────────────────────────────────────────────────────
def _is_bridged(board: Board) -> bool:
    """Does the board already carry a solder bridge?

    The signature: a netless track whose two endpoints sit exactly on the
    centres of two pads of different nets, on one layer. That is what a
    bridge is, and it is a shape a reader can recognise without geometry
    machinery: copper that belongs to no net, running from one pad to
    another.
    """
    pads = _pads(board)
    for track in board.get("tracks", []):
        if track.get("net"):
            continue                                   # a routed net, not a bridge
        points = track.get("points") or []
        if len(points) != 2:
            continue
        (ax, ay), (bx, by) = points[0], points[1]
        ends = []
        for (x, y) in ((ax, ay), (bx, by)):
            hit = None
            for pad in pads:
                if abs(pad["x"] - x) <= 1e-9 and abs(pad["y"] - y) <= 1e-9:
                    hit = pad
                    break
            ends.append(hit)
        if not all(ends):
            continue
        if ends[0]["net"] == ends[1]["net"]:
            continue                                   # one net to itself
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# The seeding rule
# ─────────────────────────────────────────────────────────────────────────────
def seed(base_board_json: dict) -> dict:
    """Return the Board IR dict with one solder bridge between two nets.

    Idempotent, deterministic, and free of randomness and wall-clock time.
    The result is JSON-normalised (points are lists, not tuples), so writing
    it out and reading it back gives the same value — the shipped
    board_defective.json is exactly what this function returns.
    """
    board: Board = copy.deepcopy(base_board_json)
    if _is_bridged(board):
        # Already bridged. The defect is present; seeding again adds nothing.
        return _normalise(board)
    sites = _ordered(_candidate_sites(board), _power_nets(board))
    if not sites:
        # Nothing to bridge: no pair of pads on this board is close enough,
        # and close enough, for a bridge to be a short and only a short.
        return _normalise(board)
    site = sites[0]
    out = copy.deepcopy(board)
    out["tracks"].append(_bridge(_pad_of(board, site["ref"], site["pin_a"]),
                                 _pad_of(board, site["ref"], site["pin_b"])))
    return _normalise(out)


def _pad_of(board: Board, ref: str, pin: str) -> dict:
    for comp in board.get("components", []):
        if comp.get("ref") != ref:
            continue
        for pad in comp.get("pads", []):
            if str(pad.get("pin")) == str(pin):
                return pad
    raise ValueError(f"no pad {ref}.{pin} on the board")


def _normalise(board: Board) -> Board:
    """The board as plain JSON: lists where a list belongs, no tuples."""
    return json.loads(json.dumps(board))


def seed_netlist(netlist: dict) -> dict:
    """A no-op, deliberately.

    This defect lives in the COPPER, not in the netlist. The netlist still
    says what it always said — the two pads are still on their own nets — and
    the board that carries it is shorted. Seeding the netlist would produce
    a different defect (a wrong net assignment), not this one.
    """
    return copy.deepcopy(netlist)


def bridge_site(base_board_json: dict) -> dict | None:
    """The site `seed` would bridge, or None. Diagnostics only."""
    board = copy.deepcopy(base_board_json)
    sites = _ordered(_candidate_sites(board), _power_nets(board))
    return copy.deepcopy(sites[0]) if sites else None


# ─────────────────────────────────────────────────────────────────────────────
# Regenerate the fixture from the product's own netlist
# ─────────────────────────────────────────────────────────────────────────────
_HERE = pathlib.Path(__file__).resolve().parent
_REPO = _HERE.parents[3]          # bridged_nets -> alpha_known_bad -> fixtures -> tests -> repo
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

    site = bridge_site(base)
    print(f"bridge site: {site}")

    base_ok = statuses["base"].get("III.2") == "pass"
    defect_bad = statuses["defective"].get("III.2") == "fail"
    changed = sorted(c for c in set(statuses["base"]) | set(statuses["defective"])
                     if statuses["base"].get(c) != statuses["defective"].get(c))
    print(f"III.2 pass on base: {base_ok}; fail on defective: {defect_bad}; "
          f"checks changed: {changed}")

    # Idempotence: seeding the defective board changes nothing.
    again = seed(defective)
    print(f"seed is idempotent: {again == defective}")
    print(f"seed does not touch its input: {base == json.loads(result.board.to_json())}")

    # The netlist is untouched — the defect is in the copper.
    print(f"netlist untouched by seed_netlist: "
          f"{seed_netlist(netlist) == netlist}")

    for f in verify_board(_as_board(defective), netlist).findings:
        if f.check == "III.2":
            print(f"\nIII.2 on the defective board: {f.status} — {f.detail}")
            for s in f.subjects:
                print(f"    {s}")

    return 0 if (base_ok and defect_bad and changed == ["III.2"]
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
