"""
verify.py — a software-only verification layer for a Board IR.

WHAT THIS IS FOR
----------------
`compile_board.py` emits a board and reports a number it calls "routed". That
number is the router's opinion of its own work, and the router is wrong in ways
this file was built to name:

  * `Board.unrouted()` compared quantisation cells, not distances, so a
    connection whose copper ended 0.05 mm from the pad centre could read as
    open. Fixed 2026-10-17 (kernel.open_connections, union-find); this file's
    count stays the independent second opinion on it.
  * `footprints.build()` assigned an unrecognised pin label to the first free
    pad, in netlist order, until 2026-10-17. It now leaves the pin unconnected,
    and III.4d fails the board.
  * The generator's pinouts and this file's used to come from one table,
    `footprints.PINMAPS`, keyed by package. IV.2 now reads each part's pinout
    from the KiCad symbol library by part number (part_pinouts.py), a
    transcription the generator never wrote.
  * KiCad's own DRC accepts netless "ghost" copper: standalone copper needs no
    connection, so it is not a short and not an unconnected item.

This module is the second opinion. Every check here is authored against the
Board IR contract, never against the router, and every check carries the rung
it stands on:

    exact     decided by arithmetic on the IR. No tolerance beyond the one named.
    sound     an over-approximation: may say "fine" too rarely, never too often.
    bounded   verified up to a stated bound, not globally.
    evidence  a figure to inspect, not a proof.
    unknown   not checked, and said so.

A check that cannot decide reports `unknown` and names the missing tool. It does
not report `pass`. That is the whole discipline: an unchecked thing is never a
checked-and-passed thing.

WHAT IT DOES NOT DO
-------------------
It does not know whether the footprint matches the real part (IV.1 is a registry
comparison, evidence at best), whether the parts will survive assembly (II.3
tombstoning needs a reflow model), or whether the board behaves electrically
parasitics and all). Those are separate rungs and are named as unknown rather
than quietly omitted.

    python verify.py netlist_dht22.json      # compile, then verify
    python verify.py board.json              # verify an already-compiled board
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from board_ir import Board, Component, Pad, Track, Via
import footprints
import part_pinouts

# Copper closer than this is one piece. Chosen below any fab's minimum feature,
# so a gap this small is not a gap a board house can make.
CONTACT_TOL = 0.06

RUNGS = ("exact", "sound", "bounded", "evidence", "unknown")


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Finding:
    """One check, its claim, the rung it stands on, and what it found."""
    check: str                    # tree id, e.g. "III.1"
    claim: str
    rung: str
    status: str                   # "pass" | "fail" | "unknown"
    detail: str = ""
    subjects: list = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status == "fail"

    def line(self) -> str:
        mark = {"pass": "ok  ", "fail": "FAIL", "unknown": "?   "}[self.status]
        rung = f"[{self.rung}]"
        head = f"{mark} {self.check:<5} {rung:<10} {self.claim}"
        return f"{head}\n           {self.detail}" if self.detail else head


@dataclass
class Report:
    board_name: str
    findings: list[Finding]

    def failed(self) -> list[Finding]:
        return [f for f in self.findings if f.status == "fail"]

    def unknown(self) -> list[Finding]:
        return [f for f in self.findings if f.status == "unknown"]

    def passes(self) -> list[Finding]:
        return [f for f in self.findings if f.status == "pass"]

    @property
    def ok(self) -> bool:
        """True when nothing decidable is wrong. Unknown findings do not make a
        board fail; they make it unproven, which `gate()` distinguishes."""
        return not self.failed()

    @property
    def proven(self) -> bool:
        """True when every check both passed and stood on an exact or sound rung."""
        return self.ok and all(
            f.rung in ("exact", "sound") for f in self.findings)

    def gate(self) -> tuple[bool, str]:
        """Should this board be emitted? A decidable failure is a hard no.

        So is a pinout nobody compared (plan decision 9; F-S0-0001): IV.2b
        lists the parts whose pin-to-pad map has only the generator's word. The
        board is not failed — `ok` stays true and it can be shown — but its
        fab files are not emitted. Until 2026-10-21 a 2N2222A with emitter and
        collector swapped passed here because KiCad has no symbol of that name."""
        bad = self.failed()
        if bad:
            return False, f"{len(bad)} check(s) failed: " + ", ".join(f.check for f in bad)
        blocked = [f for f in self.findings if f.check in EXPORT_BLOCKERS and f.status != "pass"]
        if blocked:
            return False, ("export blocked: " + "; ".join(
                f"{f.check}, {len(f.subjects)} part(s) whose pinout no second "
                f"source confirms" for f in blocked)
                + " (an uncompared pinout blocks export)")
        return True, ("proven by exact/sound checks" if self.proven
                      else f"{len(self.unknown())} check(s) unproven (unknown rung)")

    def to_dict(self) -> dict:
        emit, why = self.gate()
        return {"board": self.board_name,
                "ok": self.ok, "proven": self.proven,
                "gate": {"emit": emit, "reason": why},
                "findings": [f.__dict__ for f in self.findings]}

    def render(self) -> str:
        out = [f"verification — {self.board_name}",
               "=" * 68]
        for f in self.findings:
            out.append(f.line())
        out.append("-" * 68)
        ok, why = self.gate()
        out.append(f"gate: {'EMIT' if ok else 'REFUSE'} — {why}")
        return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Geometry — authored from the IR contract, independent of kernel.py
# ─────────────────────────────────────────────────────────────────────────────
def _pt_seg(p, a, b) -> float:
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segs_cross(a, b, c, d) -> bool:
    """Do segments ab and cd share a point? Collinear overlap and an endpoint
    lying on the other segment count; the endpoint distances catch those, so
    only the proper crossing is decided here."""
    d1, d2 = _cross(c, d, a), _cross(c, d, b)
    d3, d4 = _cross(a, b, c), _cross(a, b, d)
    return ((d1 > 0) != (d2 > 0) and d1 != 0 and d2 != 0 and
            (d3 > 0) != (d4 > 0) and d3 != 0 and d4 != 0)


def _seg_seg(a, b, c, d) -> float:
    """Distance between segments ab and cd: zero where they cross, otherwise the
    nearest endpoint-to-segment distance (which is exact for two segments that
    do not intersect)."""
    if _segs_cross(a, b, c, d):
        return 0.0
    return min(_pt_seg(a, c, d), _pt_seg(b, c, d),
               _pt_seg(c, a, b), _pt_seg(d, a, b))


def _corners(pad: Pad):
    x0, y0, x1, y1 = pad.bbox()
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _pt_rect(p, pad: Pad) -> float:
    """Distance from a point to a rectangular pad's copper; zero inside it."""
    x0, y0, x1, y1 = pad.bbox()
    dx = max(x0 - p[0], 0.0, p[0] - x1)
    dy = max(y0 - p[1], 0.0, p[1] - y1)
    return math.hypot(dx, dy)


def _pad_pt(pad: Pad, p) -> float:
    """Distance from a point to a pad's copper. 'th' pads are drawn square in
    this IR (footprints.TH_PAD), so only 'round' is a disc."""
    if pad.shape == "round":
        return max(0.0, math.dist(p, pad.center) - max(pad.w, pad.h) / 2)
    return _pt_rect(p, pad)


def _pad_seg(pad: Pad, a, b) -> float:
    """Distance from a segment (a centreline, zero width) to a pad's copper."""
    if pad.shape == "round":
        return max(0.0, _pt_seg(pad.center, a, b) - max(pad.w, pad.h) / 2)
    if _pt_rect(a, pad) == 0.0 or _pt_rect(b, pad) == 0.0:
        return 0.0
    cs = _corners(pad)
    return min(_seg_seg(a, b, c, d) for c, d in zip(cs, cs[1:] + cs[:1]))


def _pad_pad(a: Pad, b: Pad) -> float:
    if a.shape == "round" and b.shape == "round":
        return max(0.0, math.dist(a.center, b.center)
                   - max(a.w, a.h) / 2 - max(b.w, b.h) / 2)
    if a.shape == "round":
        return _pad_pad(b, a)
    if b.shape == "round":
        return max(0.0, _pt_rect(b.center, a) - max(b.w, b.h) / 2)
    x0, y0, x1, y1 = a.bbox(); X0, Y0, X1, Y1 = b.bbox()
    return math.hypot(max(X0 - x1, 0.0, x0 - X1), max(Y0 - y1, 0.0, y0 - Y1))


def _layers_meet(a_layer: str, a_th: bool, b_layer: str, b_th: bool) -> bool:
    """Two copper objects on the same side meet; a through-hole pad meets a
    track on any layer, which is what shape == 'th' means in this IR."""
    return a_th or b_th or a_layer == b_layer


def _touches(ka, a, kb, b) -> bool:
    """Do two copper objects physically make contact? Net-agnostic: this is used
    to find both connectivity and the shorts connectivity must not create.

    Every case measures copper edge to copper edge: a track is its centreline
    swept by half its width, a via is a disc of its diameter. Measuring
    centrelines instead (as this did until the 2026-10-12 review) let two wide
    tracks overlap, or a via sit on a foreign pad, and read as apart."""
    if ka == "pad" and kb == "pad":
        if not _layers_meet(a.layer, a.shape == "th", b.layer, b.shape == "th"):
            return False
        return _pad_pad(a, b) <= CONTACT_TOL
    if ka == "pad" and kb == "track":
        if not _layers_meet(a.layer, a.shape == "th", b.layer, False):
            return False
        return any(_pad_seg(a, p, q) <= b.width / 2 + CONTACT_TOL
                   for p, q in zip(b.points, b.points[1:]))
    if ka == "track" and kb == "pad":
        return _touches(kb, b, ka, a)
    if ka == "track" and kb == "track":
        if a.layer != b.layer:
            return False
        reach = a.width / 2 + b.width / 2 + CONTACT_TOL
        return any(_seg_seg(p, q, r, s) <= reach
                   for p, q in zip(a.points, a.points[1:])
                   for r, s in zip(b.points, b.points[1:]))
    if ka == "via" and kb == "track":
        return any(_pt_seg((a.x, a.y), p, q) <= a.diameter / 2 + b.width / 2 + CONTACT_TOL
                   for p, q in zip(b.points, b.points[1:]))
    if ka == "track" and kb == "via":
        return _touches(kb, b, ka, a)
    if ka == "via" and kb == "pad":
        return _pad_pt(b, (a.x, a.y)) <= a.diameter / 2 + CONTACT_TOL
    if ka == "pad" and kb == "via":
        return _touches(kb, b, ka, a)
    if ka == "via" and kb == "via":
        return math.dist((a.x, a.y), (b.x, b.y)) <= \
            (a.diameter + b.diameter) / 2 + CONTACT_TOL
    return False


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _copper_items(board: Board) -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = [("pad", p) for p in board.pads()]
    items += [("track", t) for t in board.tracks]
    items += [("via", v) for v in board.vias]
    return items


def _groups(board: Board) -> tuple[_UF, list[tuple[str, object]], dict[int, int]]:
    """Union-find over every copper object on the board, ignoring net.

    One pass gives both answers this file needs: which pads share a piece of
    copper (connectivity), and which nets that piece carries (shorts).
    Returns the union-find, the item list, and pad-id -> item-index.
    """
    items = _copper_items(board)
    uf = _UF(len(items))
    for i in range(len(items)):
        ki, oi = items[i]
        for j in range(i + 1, len(items)):
            kj, oj = items[j]
            if _touches(ki, oi, kj, oj):
                uf.union(i, j)
    pad_index = {id(o): i for i, (k, o) in enumerate(items) if k == "pad"}
    return uf, items, pad_index


# ─────────────────────────────────────────────────────────────────────────────
# Checks
# ─────────────────────────────────────────────────────────────────────────────
def _missing_connections(board: Board, uf, pad_index) -> tuple[list, list]:
    """The required connections whose endpoints are not in one piece of copper,
    and those whose endpoints are not pins at all."""
    pads = {}
    for p in board.pads():
        if p.net:
            pads[(p.net, round(p.x, 2), round(p.y, 2))] = p

    missing, orphan_ends = [], []
    for c in board.required_connections():
        pa = pads.get((c.net, round(c.a[0], 2), round(c.a[1], 2)))
        pb = pads.get((c.net, round(c.b[0], 2), round(c.b[1], 2)))
        if pa is None or pb is None:
            orphan_ends.append(c)
            continue
        if uf.find(pad_index[id(pa)]) != uf.find(pad_index[id(pb)]):
            missing.append(c)
    return missing, orphan_ends


def unrouted_connections(board: Board) -> list:
    """Required connections with no copper joining their pads.

    The independent judge `Board.unrouted()` was always meant to be replaced
    with: union-find over the copper itself, not endpoint-cell matching. This is
    that replacement, exposed so generation reports its real completion rather
    than the router's opinion of its own work."""
    uf, _, pad_index = _groups(board)
    return _missing_connections(board, uf, pad_index)[0]


def _check_connectivity(board: Board, uf, items, pad_index) -> list[Finding]:
    missing, orphan_ends = _missing_connections(board, uf, pad_index)

    detail = (f"{len(missing)} of {len(board.required_connections())} required "
              f"connections have no copper path between their pads")
    subjects = [f"{c.net} ({c.a[0]:.1f},{c.a[1]:.1f})->({c.b[0]:.1f},{c.b[1]:.1f})"
                for c in missing[:12]]
    findings = [Finding(
        "III.1", "every required connection is realised in copper", "exact",
        "fail" if missing else "pass",
        detail if missing else
        f"all {len(board.required_connections())} required connections are joined "
        f"by copper (contact tolerance {CONTACT_TOL} mm)",
        subjects)]

    if orphan_ends:
        findings.append(Finding(
            "III.1b", "every required connection has two real pads", "exact",
            "fail", f"{len(orphan_ends)} connection endpoints are not pads",
            [f"{c.net}" for c in orphan_ends[:12]]))

    findings += _check_planes(board, uf, items)
    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Plane nets — excluded from required_connections, so checked here
# ─────────────────────────────────────────────────────────────────────────────
PLANE_GRID = 0.1          # mm per raster cell
PLANE_MIN_WIDTH = 0.25    # pour minimum width (KiCad's default zone min width)
EDGE_CLEARANCE = 0.3      # copper to board edge, as kernel.drc


def _reaches(kind: str, o, layer: str) -> bool:
    """Does this copper object touch the given layer?"""
    if kind == "via":
        return True
    if kind == "pad":
        return o.shape == "th" or o.layer == layer
    return o.layer == layer


def _copper_shape(kind: str, o):
    """(bbox, distance-to-copper function over numpy grids) for one object."""
    import numpy as np

    if kind in ("via", "pad") and (kind == "via" or o.shape == "round"):
        r = o.diameter / 2 if kind == "via" else max(o.w, o.h) / 2
        return ((o.x - r, o.y - r, o.x + r, o.y + r),
                lambda X, Y: np.maximum(np.hypot(X - o.x, Y - o.y) - r, 0))
    if kind == "pad":
        x0, y0, x1, y1 = o.bbox()
        return ((x0, y0, x1, y1),
                lambda X, Y: np.hypot(np.maximum(np.maximum(x0 - X, 0), X - x1),
                                      np.maximum(np.maximum(y0 - Y, 0), Y - y1)))
    w = o.width / 2
    px = [p[0] for p in o.points]
    py = [p[1] for p in o.points]

    def dist(X, Y):
        out = np.full(X.shape, np.inf)
        for (ax, ay), (bx, by) in zip(o.points, o.points[1:]):
            dx, dy = bx - ax, by - ay
            L = dx * dx + dy * dy
            t = (np.zeros_like(X) if L == 0 else
                 np.clip(((X - ax) * dx + (Y - ay) * dy) / L, 0.0, 1.0))
            out = np.minimum(out, np.hypot(X - (ax + t * dx), Y - (ay + t * dy)))
        return np.maximum(out - w, 0)
    return (min(px) - w, min(py) - w, max(px) + w, max(py) + w), dist


def _plane_raster(board: Board, layer: str, net: str):
    """The plane's pour, under-approximated on a grid.

    A cell is copper only if its whole square would be filled by a full pour:
    its centre is at least clearance + h/sqrt(2) from foreign copper on that
    layer and at least the edge clearance + h/sqrt(2) inside the outline. The
    free region is then opened by the pour's minimum width, which removes the
    necks a real pour cannot fill. Each step only removes cells a real pour
    would keep, so connectivity found here holds on the real pour.

    Returns (pour mask, [(item index, window slices, cells inside the item)])
    for the plane net's own copper on that layer."""
    import numpy as np

    h = PLANE_GRID
    nx = max(1, int(board.outline_w / h))
    ny = max(1, int(board.outline_h / h))
    xs = (np.arange(nx) + 0.5) * h
    ys = (np.arange(ny) + 0.5) * h
    half = h / math.sqrt(2)
    plane_cl = board.net_class_for(net).clearance

    free = np.zeros((ny, nx), dtype=bool)
    e = EDGE_CLEARANCE + half
    free[np.ix_((ys >= e) & (ys <= board.outline_h - e),
                (xs >= e) & (xs <= board.outline_w - e))] = True

    def window(x0, y0, x1, y1):
        i0 = max(0, int(math.floor(y0 / h))); i1 = min(ny, int(math.ceil(y1 / h)) + 1)
        j0 = max(0, int(math.floor(x0 / h))); j1 = min(nx, int(math.ceil(x1 / h)) + 1)
        if i0 >= i1 or j0 >= j1:
            return None
        X, Y = np.meshgrid(xs[j0:j1], ys[i0:i1])
        return (slice(i0, i1), slice(j0, j1)), X, Y

    own = np.zeros((ny, nx), dtype=bool)
    own_items = []
    for idx, (kind, o) in enumerate(_copper_items(board)):
        if not _reaches(kind, o, layer):
            continue
        (x0, y0, x1, y1), dist = _copper_shape(kind, o)
        if o.net == net:
            win = window(x0, y0, x1, y1)
            if win is None:
                continue
            sl, X, Y = win
            inside = dist(X, Y) <= 0
            own[sl] |= inside
            own_items.append((idx, sl, inside))
            continue
        cl = max(plane_cl, board.net_class_for(o.net).clearance) if o.net else plane_cl
        m = cl + half
        win = window(x0 - m, y0 - m, x1 + m, y1 + m)
        if win is None:
            continue
        sl, X, Y = win
        free[sl] &= ~(dist(X, Y) < m)

    # Opening by a disc of the pour's minimum width.
    r = int(math.ceil(PLANE_MIN_WIDTH / 2 / h))
    offs = [(di, dj) for di in range(-r, r + 1) for dj in range(-r, r + 1)
            if di * di + dj * dj <= r * r]

    def shifted(a, di, dj):
        out = np.zeros_like(a)
        out[max(0, -di):ny + min(0, -di), max(0, -dj):nx + min(0, -dj)] = \
            a[max(0, di):ny + min(0, di), max(0, dj):nx + min(0, dj)]
        return out

    eroded = free.copy()
    for di, dj in offs:
        eroded &= shifted(free, di, dj)
    opened = np.zeros_like(free)
    for di, dj in offs:
        opened |= shifted(eroded, di, dj)
    return opened | own, own_items


def _label_runs(mask) -> tuple[_UF, list[list[tuple[int, int, int]]]]:
    """4-connected regions of a boolean grid, by run-length union-find.
    Returns the union-find over runs and, per row, [(start, end, run id)]."""
    rows: list[list[tuple[int, int, int]]] = []
    n = 0
    for row in mask:
        runs = []
        idx = row.nonzero()[0]
        k = 0
        while k < len(idx):
            start = idx[k]
            while k + 1 < len(idx) and idx[k + 1] == idx[k] + 1:
                k += 1
            runs.append((int(start), int(idx[k]) + 1, n))
            n += 1
            k += 1
        rows.append(runs)
    uf = _UF(n)
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        p = q = 0
        while p < len(a) and q < len(b):
            if a[p][0] < b[q][1] and b[q][0] < a[p][1]:
                uf.union(a[p][2], b[q][2])
            if a[p][1] < b[q][1]:
                p += 1
            else:
                q += 1
    return uf, rows


def _check_planes(board: Board, uf, items) -> list[Finding]:
    """III.1c / III.1d — plane nets are left out of required_connections (the
    pour is meant to join them), so until 2026-10-17 their connectivity was
    only ever reported unknown."""
    findings = []
    for layer, net in [(l.name, l.plane_net) for l in board.layers if l.plane_net]:
        pads = [i for i, (k, o) in enumerate(items) if k == "pad" and o.net == net]
        if not pads:
            continue
        reaching = {uf.find(i) for i, (k, o) in enumerate(items)
                    if o.net == net and _reaches(k, o, layer)}
        stranded = [items[i][1] for i in pads if uf.find(i) not in reaching]
        findings.append(Finding(
            "III.1c", f"every {net} pad reaches the {layer} plane through copper",
            "exact", "fail" if stranded else "pass",
            (f"{len(stranded)} of {len(pads)} {net} pad(s) have no via, through-hole "
             f"pad or {layer} copper in their piece of copper")
            if stranded else
            f"all {len(pads)} {net} pads reach {layer} through copper",
            [f"{p.ref}.{p.pin}" for p in stranded[:12]]))

        try:
            pour, own_items = _plane_raster(board, layer, net)
        except ImportError:
            findings.append(Finding(
                "III.1d", f"the {layer} pour joins every {net} pad into one piece",
                "unknown", "unknown", "numpy is not installed; the pour was not modelled"))
            continue
        ruf, rows = _label_runs(pour)
        groups = sorted({uf.find(i) for i in range(len(items))})
        gid = {g: k for k, g in enumerate(groups)}
        base = len(groups)
        joint = _UF(base + len(ruf.p))
        for idx, sl, inside in own_items:
            g = gid[uf.find(idx)]
            for di, dj in zip(*inside.nonzero()):
                i, j = sl[0].start + int(di), sl[1].start + int(dj)
                for s_, e_, rid in rows[i]:
                    if s_ <= j < e_:
                        joint.union(g, base + ruf.find(rid))
                        break
        pieces = {joint.find(gid[uf.find(i)]) for i in pads}
        model = (f"model: full pour on {layer} at net-class clearance, solid pad "
                 f"connection (no thermal spokes), minimum width {PLANE_MIN_WIDTH} mm, "
                 f"{PLANE_GRID} mm grid, under-approximated")
        findings.append(Finding(
            "III.1d", f"the {layer} pour joins every {net} pad into one piece", "sound",
            "pass" if len(pieces) == 1 else "fail",
            (f"all {len(pads)} {net} pads are one piece of copper with the pour; {model}")
            if len(pieces) == 1 else
            (f"the {net} pads fall into {len(pieces)} pieces: tracks on {layer} may "
             f"split the pour, or the under-approximation may be too tight (a sound "
             f"check can fail a board that is fine); {model}")))
    return findings


def _check_shorts(board: Board, uf, items, pad_index) -> list[Finding]:
    by_root: dict[int, set[str]] = defaultdict(set)
    for i, (k, o) in enumerate(items):
        n = o.net
        if n:
            by_root[uf.find(i)].add(n)

    shorts = {r: sorted(ns) for r, ns in by_root.items() if len(ns) > 1}
    if not shorts:
        return [Finding("III.2", "no two nets share a piece of copper", "exact",
                        "pass", "no copper group carries more than one net")]
    subjects = [f"nets {ns} joined" for ns in list(shorts.values())[:12]]
    return [Finding("III.2", "no two nets share a piece of copper", "exact",
                    "fail", f"{len(shorts)} copper group(s) carry two or more nets "
                    f"(a short at {CONTACT_TOL} mm contact tolerance)", subjects)]


def _package_of(comp: Component, nl_comp: dict | None) -> str | None:
    """The package a component was built as. `from_netlist` records it on the IR;
    a hand-built board may not, so fall back to what the netlist declared."""
    pkg = comp.attrs.get("package")
    if pkg:
        return pkg
    return footprints.normalize_package((nl_comp or {}).get("package"))


def _mpn_of(comp: Component, nl_comp: dict | None) -> str:
    return comp.attrs.get("mpn") or (nl_comp or {}).get("mpn") or ""


def _expected_pins(ref: str, package: str, pins: dict,
                   mpn: str | None = None) -> tuple[dict, list, list]:
    """Re-derive what footprints.build() should have produced for this part.

    Returns (expected_pin_nets, undetermined_labels, collisions).
    A label is `undetermined` when nothing declared where it goes: build() now
    leaves it unconnected instead of putting it on the first free pad.
    A `collision` is two labels asking for the same pad, which silently drops one.
    """
    expected, undetermined, collisions, _ = footprints.resolve(package, pins, mpn)
    return expected, undetermined, collisions


def _check_footprint_parity(board: Board, netlist: dict | None) -> list[Finding]:
    if not netlist:
        return [Finding("III.3/III.4", "footprint matches the netlist", "unknown",
                        "unknown",
                        "no netlist supplied — pin assignment is not checked")]

    nl_by_ref = {c.get("ref"): c for c in netlist.get("components", [])}
    netlist_named_netless = []
    parity_mismatch = []
    undetermined_parts = []
    collisions_all = []
    dropped = []
    missing_pkg = []

    for comp in board.components:
        nl = nl_by_ref.get(comp.ref)
        if nl is None:
            continue
        pkg = _package_of(comp, nl)
        if not pkg or pkg not in footprints.PACKAGES:
            missing_pkg.append(comp.ref)
            continue
        pins = {str(k): v for k, v in (nl.get("pins") or {}).items()}
        avail_n = footprints.pin_count(pkg)
        if len(pins) > avail_n:
            dropped.append(f"{comp.ref} ({pkg}): netlist names {len(pins)} pins, "
                           f"footprint has {avail_n}")

        expected, undetermined, collisions = _expected_pins(
            comp.ref, pkg, pins, _mpn_of(comp, nl))
        collisions_all += [f"{comp.ref}: {c}" for c in collisions]
        if undetermined:
            undetermined_parts.append(
                f"{comp.ref} ({pkg}, {_mpn_of(comp, nl) or 'no part number'}): "
                f"{', '.join(map(repr, undetermined))}")

        actual = {p.pin: p.net for p in comp.pads}
        for pin, net in expected.items():
            if actual.get(pin, "") != net:
                parity_mismatch.append(
                    f"{comp.ref} pin {pin}: netlist expects {net!r}, board has "
                    f"{actual.get(pin, '')!r}")
        # a pad the netlist named that came out netless
        for pin in expected:
            if actual.get(pin, "") == "" and expected[pin]:
                netlist_named_netless.append(f"{comp.ref} pin {pin} ({expected[pin]})")

    findings = []
    # III.4a (F-S2-R005-2): a part the board left out — no footprint for its
    # package, so from_netlist warned and went on — is invisible to every
    # other check, which visit the parts that are there. Its nets then end at
    # the parts that remain and read as complete.
    on_board = {c.ref for c in board.components}
    missing = [f"{ref} ({c.get('package') or 'no package'}, {c.get('mpn') or 'no part number'})"
               for ref, c in nl_by_ref.items() if ref and ref not in on_board]
    findings.append(Finding(
        "III.4a", "every part in the netlist is on the board", "exact",
        "fail" if missing else "pass",
        (f"{len(missing)} netlist part(s) are not on the board, so their nets "
         f"end open where they should meet them: " + "; ".join(missing[:6]))
        if missing else f"all {len(nl_by_ref)} netlist part(s) are placed",
        missing[:12]))
    findings.append(Finding(
        "III.4", "the board's pin-to-net map is the netlist's", "exact",
        "fail" if parity_mismatch else "pass",
        (f"{len(parity_mismatch)} pad(s) disagree with the netlist; "
         f"the generator is not deterministic on this netlist: "
         + "; ".join(parity_mismatch[:6]))
        if parity_mismatch else
        "every pad carries the net the netlist assigns to its pin"))

    if dropped:
        findings.append(Finding(
            "III.4b", "the footprint has a pad for every netlist pin", "exact",
            "fail", f"{len(dropped)} part(s) have more named pins than pads: "
            + "; ".join(dropped[:6])))

    if collisions_all:
        findings.append(Finding(
            "III.4c", "no two netlist pins resolve to the same pad", "exact",
            "fail", f"{len(collisions_all)} pin collision(s), one net silently "
            f"dropped: " + "; ".join(collisions_all[:6])))

    ghost = netlist_named_netless
    if ghost:
        findings.append(Finding(
            "III.3", "no pad named by the netlist is left unconnected", "exact",
            "fail", f"{len(ghost)} pad(s) the netlist named carry no net "
            f"(KiCad DRC accepts these silently): " + "; ".join(ghost[:6])))
    else:
        findings.append(Finding(
            "III.3", "no pad named by the netlist is left unconnected", "exact",
            "pass", "every pad the netlist names carries its net"))

    # Pin order. A pin no declared map places is left unconnected by build(),
    # so the board is missing a connection the design needs: a failure, not an
    # unknown. Until 2026-10-17 build() guessed a free pad and this said unknown.
    if undetermined_parts:
        findings.append(Finding(
            "III.4d", "every pin is placed by a declared pinout, not by luck",
            "exact", "fail",
            f"{len(undetermined_parts)} part(s) name pins that no declared pinout "
            f"places; they are left unconnected (supply a per-part pinout): "
            + "; ".join(undetermined_parts[:6])))
    elif missing_pkg:
        findings.append(Finding(
            "III.4d", "every pin is placed by a declared pinout, not by luck",
            "unknown", "unknown",
            f"{len(missing_pkg)} component(s) carry no package on the IR: "
            + ", ".join(missing_pkg[:6])))
    else:
        findings.append(Finding(
            "III.4d", "every pin is placed by a declared pinout, not by luck",
            "exact", "pass",
            "every netlist pin resolved through a declared map or a literal pad id"))
    return findings


def _check_placement(board: Board) -> list[Finding]:
    findings = []
    outside = []
    for c in board.components:
        x0 = c.x - c.courtyard_w / 2; x1 = c.x + c.courtyard_w / 2
        y0 = c.y - c.courtyard_h / 2; y1 = c.y + c.courtyard_h / 2
        if x0 < -1e-9 or y0 < -1e-9 or x1 > board.outline_w + 1e-9 or \
           y1 > board.outline_h + 1e-9:
            outside.append(f"{c.ref} courtyard [{x0:.1f},{y0:.1f}]-[{x1:.1f},{y1:.1f}]"
                           f" vs board {board.outline_w}x{board.outline_h}")
    findings.append(Finding(
        "II.1", "every component courtyard lies inside the board outline",
        "exact", "fail" if outside else "pass",
        ("; ".join(outside[:8])) if outside else
        f"all {len(board.components)} courtyards are within "
        f"{board.outline_w}x{board.outline_h} mm"))

    overlaps = []
    for i, a in enumerate(board.components):
        for b in board.components[i + 1:]:
            if a.side != b.side:
                continue
            if (abs(a.x - b.x) < (a.courtyard_w + b.courtyard_w) / 2 - 1e-9 and
                    abs(a.y - b.y) < (a.courtyard_h + b.courtyard_h) / 2 - 1e-9):
                overlaps.append(f"{a.ref} <-> {b.ref}")
    findings.append(Finding(
        "II.2", "no two courtyards on the same side overlap", "exact",
        "fail" if overlaps else "pass",
        ("; ".join(overlaps[:8])) if overlaps else
        "no courtyard overlap (parts can be placed and reworked)"))
    return findings


def _check_assembly(board: Board) -> list[Finding]:
    """II.3 — tombstoning. Asymmetric pad heating lifts one end of a two-terminal
    part during reflow. Unequal pad copper is the decidable half of that; the
    thermal model that would decide the rest is not in this IR."""
    asym = []
    for c in board.components:
        pads = c.pads
        if len(pads) != 2 or not all(p.shape == "rect" for p in pads):
            continue
        areas = [p.w * p.h for p in pads]
        lo, hi = min(areas), max(areas)
        if lo <= 0 or hi / lo > 1.05:
            asym.append(f"{c.ref}: pad areas {areas[0]:.3f} vs {areas[1]:.3f} mm^2")
    return [
        Finding("II.3", "two-terminal parts have equal pad copper", "exact",
                "fail" if asym else "pass",
                ("; ".join(asym[:8])) if asym else
                "every two-terminal SMD part has symmetric pads"),
        Finding("II.3b", "neither end of a two-terminal part will lift in reflow",
                "unknown", "unknown",
                "the reflow thermal model (paste volume, pad-to-plane thermal "
                "relief, part mass) is not carried by the Board IR"),
    ]


LAND_TOL = 0.01           # mm; the table and the generator are both exact numbers


def _pitch_and_row(comp: Component) -> tuple[float | None, float | None]:
    """Rotation-invariant measures of a footprint, as land_patterns.json defines
    them: pitch = the smallest centre distance between consecutively numbered
    pads; row = pad 1 to pad N, which face each other on DIP and SOIC."""
    by = {}
    for p in comp.pads:
        if p.pin.isdigit():
            by[int(p.pin)] = p.center
    nums = sorted(by)
    steps = [math.dist(by[a], by[a + 1]) for a in nums if a + 1 in by]
    pitch = min(steps) if steps else None
    row = math.dist(by[nums[0]], by[nums[-1]]) if len(nums) >= 2 and nums[0] == 1 else None
    return pitch, row


def _check_land_patterns(board: Board, netlist: dict | None = None) -> list[Finding]:
    """IV.1 — compare the generated land pattern to a figure written down
    outside the generator. Two separate claims, two separate rungs."""
    path = Path(__file__).with_name("land_patterns.json")
    try:
        table = json.loads(path.read_text())
    except Exception as e:                                    # noqa: BLE001
        return [Finding("IV.1", "land pattern matches an external figure",
                        "unknown", "unknown",
                        f"land_patterns.json unreadable ({e})")]

    nl_by_ref = {c.get("ref"): c for c in (netlist or {}).get("components", [])}
    mismatch, unlisted, unverified = [], [], set()
    for comp in board.components:
        pkg = _package_of(comp, nl_by_ref.get(comp.ref))
        if not pkg:
            continue
        row = table.get(pkg)
        if not row:
            unlisted.append(comp.ref + ":" + pkg)
            continue
        n_pads = len(comp.pads)
        if row.get("pad_count") is not None and n_pads != row["pad_count"]:
            mismatch.append(f"{comp.ref} ({pkg}): {n_pads} pads, table says "
                            f"{row['pad_count']}")
        pitch, span = _pitch_and_row(comp)
        for what, got, want in (("pitch", pitch, row.get("pitch_mm")),
                                ("row", span, row.get("row_mm"))):
            if want is None:
                continue
            if got is None or abs(got - want) > LAND_TOL:
                mismatch.append(f"{comp.ref} ({pkg}): {what} "
                                f"{'none' if got is None else f'{got:.3f}'} mm, "
                                f"table says {want} mm")
        if not row.get("verified"):
            unverified.add(pkg)

    findings = [Finding(
        "IV.1", "the footprint the generator makes equals the figure we wrote down",
        "exact", "fail" if mismatch else "pass",
        ("; ".join(mismatch[:8])) if mismatch else
        "generated pad counts, pitches and row spans match land_patterns.json "
        f"for every listed package (tolerance {LAND_TOL} mm)")]

    if unlisted:
        findings.append(Finding(
            "IV.1b", "every package has an entry in the land-pattern table",
            "unknown", "unknown",
            f"{len(unlisted)} package(s) not in the table: " + ", ".join(unlisted[:8])))

    findings.append(Finding(
        "IV.3", "courtyard and body match the part's datasheet outline", "unknown",
        "unknown",
        "no datasheet package outline is recorded; courtyards are footprints.py's "
        "own numbers and are compared with nothing"))

    findings.append(Finding(
        "IV.1c", "the land-pattern figures themselves are externally verified",
        "evidence" if unverified else "exact",
        "unknown" if unverified else "pass",
        (f"{len(unverified)} package(s) are self-declared, verified against no "
         f"datasheet or library: " + ", ".join(sorted(unverified)[:8]) +
         ". The table can disagree with footprints.py; nothing yet makes it right.")
        if unverified else
        "every package's land pattern cites a verified external source"))
    return findings


# Checks whose `unknown` blocks export without failing the board.
EXPORT_BLOCKERS = ("IV.2b",)


def _check_part_pinouts(board: Board, netlist: dict | None = None) -> list[Finding]:
    """IV.2 — each part's pinout against the KiCad symbol for its part number.

    The generator's map (footprints.PART_PINMAPS) and the KiCad library are two
    transcriptions of one datasheet, made by different people. Agreement is
    trust level T1: strong evidence, not proof. Disagreement fails closed and
    shows both. A part KiCad has no usable symbol for stays unknown (T0)."""
    claim = "every part's pinout agrees with the KiCad symbol for its part number"
    # No library is no early exit: every part that needed a comparison is
    # listed in IV.2b, and IV.2b blocks export. A datasheet record may still
    # answer for a part.
    no_library = part_pinouts.symbol_dir() is None

    nl_by_ref = {c.get("ref"): c for c in (netlist or {}).get("components", [])}
    agree, disagree, unchecked = [], [], []
    for comp in board.components:
        nl = nl_by_ref.get(comp.ref)
        pkg = _package_of(comp, nl)
        mpn = _mpn_of(comp, nl)
        pads = {p.pin for p in comp.pads}
        # The netlist's pin labels; without the netlist, the ones compile_board
        # kept on the part (the fab exporter verifies the board alone); last,
        # the pad numbers, which name no function.
        pins = ({str(k): v for k, v in ((nl or {}).get("pins") or {}).items()}
                or dict(comp.attrs.get("pins") or {})
                or {p.pin: p.net for p in comp.pads if p.net})
        named = {l: n for l, n in pins.items() if l not in pads}
        # A resistor's or plain capacitor's two ends cannot be the wrong way round;
        # a two-pad part is checked only when its symbol says its ends differ.
        symmetric = len(pads) == 2 and set(pins) <= {"A", "B", "1", "2", "+", "-"}
        if symmetric and not mpn:
            continue
        if not mpn:
            unchecked.append(f"{comp.ref}: no part number")
            continue
        r = part_pinouts.lookup(mpn, pkg)
        if symmetric and (r.symbol is None or len({part_pinouts.norm_name(n)
                                                   for n in r.symbol.pins.values()}) < 2):
            continue
        if r.symbol is None:
            unchecked.append(f"{comp.ref} ({mpn}): {r.reason}")
            continue
        sym = r.symbol
        bad = []
        sym_pkg = part_pinouts.footprint_package(sym.footprint)
        if sym_pkg and pkg and sym_pkg != pkg:
            bad.append(f"{sym.cite()} defaults to {sym.footprint}, the board builds {pkg}")
        missing = sorted(set(sym.pins) - pads, key=lambda p: (len(p), p))
        if missing:
            bad.append(f"{sym.cite()} numbers pin(s) {missing} that the {pkg} "
                       f"footprint has no pad for")
        actual = {p.pin: p.net for p in comp.pads}
        compared, blank = 0, []
        for label, net in named.items():
            kp = part_pinouts.pads_for(sym, label)
            if kp is None:
                blank.append(label)
                continue
            compared += 1
            for k in kp:
                if actual.get(k, "") != net:
                    bad.append(f"'{label}' ({net}): {sym.cite()} puts it on pad {k}, "
                               f"the board has {actual.get(k) or 'nothing'} there")
        if bad:
            disagree.append(f"{comp.ref} ({mpn}): " + "; ".join(bad[:3]))
        elif blank:
            unchecked.append(f"{comp.ref} ({mpn}): {sym.cite()} has no pin answering "
                             f"to {', '.join(map(repr, blank))}")
        elif compared:
            agree.append(f"{comp.ref} ({mpn}) T1 = {sym.cite()} [{r.how} match]")
        else:
            names = ", ".join(f"pad {k} = {sym.pins.get(k) or '?'} ({v})"
                              for k, v in sorted(actual.items(), key=lambda kv: (len(kv[0]), kv[0]))
                              if v)
            unchecked.append(f"{comp.ref} ({mpn}): the netlist names pads by number, "
                             f"so nothing says which function it meant; per {sym.cite()}: {names}")

    findings = [Finding(
        "IV.2", claim, "evidence",
        "fail" if disagree else "pass" if agree else "unknown",
        (f"{len(disagree)} part(s) disagree with the KiCad library: "
         + " | ".join(disagree[:6])) if disagree else
        (f"{len(agree)} part(s) agree with an independent transcription (T1); "
         "agreement is evidence, not proof" if agree else
         "KiCad symbol library not found (install KiCad or set KICAD_SYMBOL_DIR); "
         "no pinout was checked against a second source" if no_library else
         "no part could be compared"),
        agree[:12] + disagree[:12])]
    if unchecked:
        findings.append(Finding(
            "IV.2b", "every part's pinout has a second source", "unknown", "unknown",
            f"{len(unchecked)} part(s) have only the generator's word for their "
            f"pinout (T0): " + "; ".join(unchecked[:6]), unchecked[:12]))
    return findings


def _check_out_of_reach(board: Board) -> list[Finding]:
    """Checks the tree names that live entirely outside this IR, stated so the
    harness cannot be mistaken for having covered them."""
    return [
        Finding("V", "as-built electrical behaviour matches the design", "unknown",
                "unknown",
                "parasitics, signal integrity, PDN and EMC need an EM solver or a "
                "bench measurement; the IR carries no field data"),
        Finding("VI", "the design itself is electrically correct", "unknown",
                "unknown",
                "analog functional correctness is undecidable in general; see "
                "reports/Analog circuit formal verification.md"),
        Finding("VII", "the board works in its environment", "unknown", "unknown",
                "cables, supply, firmware and enclosure are outside the Board IR"),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# The entry point
# ─────────────────────────────────────────────────────────────────────────────
def verify_board(board: Board, netlist: dict | None = None) -> Report:
    uf, items, pad_index = _groups(board)
    findings: list[Finding] = []
    findings += _check_placement(board)
    findings += _check_assembly(board)
    findings += _check_connectivity(board, uf, items, pad_index)
    findings += _check_shorts(board, uf, items, pad_index)
    findings += _check_footprint_parity(board, netlist)
    findings += _check_land_patterns(board, netlist)
    findings += _check_part_pinouts(board, netlist)
    findings += _check_out_of_reach(board)
    return Report(board.name, findings)


def _load(path: str) -> tuple[Board, dict | None]:
    d = json.loads(Path(path).read_text())
    if "components" in d and "board" in d and "layers" not in d:
        from compile_board import compile_board
        r = compile_board(d)
        return r.board, d
    return Board.from_json(json.dumps(d)), None


def main() -> None:
    try:                                  # the report uses real dashes; cp1252 does not
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                     # noqa: BLE001
        pass
    args = sys.argv[1:] or ["netlist_dht22.json"]
    board, netlist = _load(args[0])
    rep = verify_board(board, netlist)
    print(rep.render())
    ok, why = rep.gate()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
