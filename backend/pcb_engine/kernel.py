"""
kernel.py — deterministic geometry. No model ever runs in here.

This module is the reason the whole system can work. An LLM cannot verify
that two pieces of copper are 0.15 mm apart; a distance function can, exactly,
in microseconds. So every claim about a board's correctness has to bottom out
here, and the model's job is reduced to *proposing* things this file can then
accept or reject.

Two exports matter:

    drc(board)   -> list[Violation]   is this board manufacturable?
    score(board) -> Score             of two manufacturable boards, which is better?

`score` is the piece people skip, and it is what actually buys you DeepPCB's
"explore many layouts, pick a good one" behaviour. Without a total order over
candidates you have a random number generator, not an optimiser.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from board_ir import Board, Connection, Pad, Track, Via, Point

# Cheapest common fab process limits (2-layer/4-layer, 1 oz). Rules, not targets.
MIN_FAB_WIDTH = 0.127      # 5 mil
MIN_FAB_CLEARANCE = 0.127

# Copper closer than this is one piece. Below any fab's minimum feature, so a
# gap this small is not a gap a board house can make. verify.py states the same
# number independently; the two must agree or the judge and the router disagree
# about what "connected" means.
CONTACT_TOL = 0.06


# ─────────────────────────────────────────────────────────────────────────────
# Exact primitives
# ─────────────────────────────────────────────────────────────────────────────
def _seg_point_dist(a: Point, b: Point, p: Point) -> float:
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0.0:
        return math.dist(a, p)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.dist((ax + t * dx, ay + t * dy), p)


def _ccw(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def seg_seg_dist(a: Point, b: Point, c: Point, d: Point) -> float:
    """Exact minimum distance between two segments. 0.0 if they cross."""
    if (_ccw(a, b, c) * _ccw(a, b, d) < 0) and (_ccw(c, d, a) * _ccw(c, d, b) < 0):
        return 0.0
    return min(_seg_point_dist(a, b, c), _seg_point_dist(a, b, d),
               _seg_point_dist(c, d, a), _seg_point_dist(c, d, b))


def seg_rect_dist(a: Point, b: Point, rect: tuple[float, float, float, float]) -> float:
    """Distance from a segment to an axis-aligned rectangle (0 if it enters)."""
    x0, y0, x1, y1 = rect
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for p in (a, b):
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            return 0.0
    return min(seg_seg_dist(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


def _pad_point_dist(pad: Pad, p: Point) -> float:
    """Distance from a point to a pad's copper; zero inside it. Only 'round' is
    a disc — 'th' pads are drawn square in this IR."""
    if pad.shape == "round":
        return max(0.0, math.dist(p, pad.center) - max(pad.w, pad.h) / 2)
    return seg_rect_dist(p, p, pad.bbox())


def _pad_seg_dist(pad: Pad, a: Point, b: Point) -> float:
    """Distance from a segment centreline to a pad's copper."""
    if pad.shape == "round":
        return max(0.0, _seg_point_dist(a, b, pad.center) - max(pad.w, pad.h) / 2)
    return seg_rect_dist(a, b, pad.bbox())


def _pad_pad_gap(p: Pad, q: Pad) -> float:
    if p.shape == "round":
        return max(0.0, _pad_point_dist(q, p.center) - max(p.w, p.h) / 2)
    if q.shape == "round":
        return _pad_pad_gap(q, p)
    x0, y0, x1, y1 = p.bbox(); X0, Y0, X1, Y1 = q.bbox()
    return math.hypot(max(X0 - x1, 0.0, x0 - X1), max(Y0 - y1, 0.0, y0 - Y1))


def _segments(t: Track):
    return list(zip(t.points, t.points[1:]))


def _bbox_of(t: Track, pad: float) -> tuple[float, float, float, float]:
    xs = [p[0] for p in t.points]; ys = [p[1] for p in t.points]
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def _bbox_overlap(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


# ─────────────────────────────────────────────────────────────────────────────
# DRC
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Violation:
    rule: str
    severity: str          # "error" | "warning"
    detail: str
    at: Point
    nets: tuple[str, ...] = ()
    measured: float | None = None
    required: float | None = None

    def __str__(self) -> str:
        m = ""
        if self.measured is not None and self.required is not None:
            m = f"  ({self.measured:.3f} mm < {self.required:.3f} mm required)"
        return (f"[{self.severity}] {self.rule} @ "
                f"({self.at[0]:.2f}, {self.at[1]:.2f}) — {self.detail}{m}")


def drc(board: Board, edge_clearance: float = 0.3) -> list[Violation]:
    v: list[Violation] = []
    tracks = board.tracks
    pads = board.pads()

    # ── 1. track ↔ track, different nets, same layer ──
    # Each box grows by its own half-width plus its own class clearance, so the
    # two paddings sum to w1/2 + w2/2 + c1 + c2 — never less than the
    # max(c1, c2) + w1/2 + w2/2 a pair needs. Padding by the width alone (as
    # this did until 2026-10-17) culled every pair whose clearance exceeded
    # (w1 + w2) / 2 before it was ever measured: 0.2 mm tracks at a 0.25 mm
    # clearance could sit 0.42 mm apart and report no violation.
    boxes = [_bbox_of(t, t.width / 2 + board.net_class_for(t.net).clearance)
             for t in tracks]
    for i, t1 in enumerate(tracks):
        c1 = board.net_class_for(t1.net)
        for j in range(i + 1, len(tracks)):
            t2 = tracks[j]
            if t1.net == t2.net or t1.layer != t2.layer:
                continue
            req = max(c1.clearance, board.net_class_for(t2.net).clearance)
            need = req + t1.width / 2 + t2.width / 2
            if not _bbox_overlap(boxes[i], boxes[j]):
                continue
            for s1 in _segments(t1):
                for s2 in _segments(t2):
                    d = seg_seg_dist(*s1, *s2)
                    if d < need:
                        v.append(Violation(
                            "clearance.track_track", "error",
                            f"{t1.net} / {t2.net} on {t1.layer}",
                            ((s1[0][0] + s2[0][0]) / 2, (s1[0][1] + s2[0][1]) / 2),
                            (t1.net, t2.net), d, need))
                        break
                else:
                    continue
                break

    # ── 2. track ↔ pad, different nets, SAME layer ──
    # The layer test is not an optimisation. An SMD pad exists on exactly one
    # layer, so a bottom-layer track passing beneath a top-layer pad is legal
    # and extremely common — routing under parts is most of what a second layer
    # is FOR. Omitting this test made the checker report violations measured at
    # 0.000 mm (a track "through" a pad it never shared copper with) and made a
    # working router look broken.
    for t in tracks:
        cl = board.net_class_for(t.net).clearance
        for p in pads:
            if p.net == t.net:
                continue
            if p.shape != "th" and p.layer != t.layer:
                continue
            need = cl + t.width / 2
            for s in _segments(t):
                d = seg_rect_dist(*s, p.bbox())
                if d < need:
                    v.append(Violation(
                        "clearance.track_pad", "error",
                        f"track {t.net} vs pad {p.ref}.{p.pin} ({p.net})",
                        p.center, (t.net, p.net), d, need))
                    break

    # ── 3. via ↔ track, different nets ──
    for via in board.vias:
        for t in tracks:
            if t.net == via.net:
                continue
            need = board.net_class_for(t.net).clearance + t.width / 2 + via.diameter / 2
            for s in _segments(t):
                d = _seg_point_dist(*s, (via.x, via.y))
                if d < need:
                    v.append(Violation(
                        "clearance.via_track", "error",
                        f"via {via.net} vs track {t.net}",
                        (via.x, via.y), (via.net, t.net), d, need))
                    break

    # ── 3b. via ↔ pad and via ↔ via, different nets ──
    # A via is plated through, so it meets a pad on EITHER layer. Until
    # 2026-10-17 the kernel had no rule here at all: the router put an RS485_A
    # via 0.035 mm from an RS485_B pad, the board scored zero DRC errors, and
    # only verify.py's III.2 saw the short.
    for k, via in enumerate(board.vias):
        cl = board.net_class_for(via.net).clearance
        for p in pads:
            if p.net == via.net:
                continue
            need = max(cl, board.net_class_for(p.net).clearance) + via.diameter / 2
            d = _pad_point_dist(p, (via.x, via.y))
            if d < need:
                v.append(Violation(
                    "clearance.via_pad", "error",
                    f"via {via.net} vs pad {p.ref}.{p.pin} ({p.net})",
                    (via.x, via.y), (via.net, p.net), d, need))
        for other in board.vias[k + 1:]:
            if other.net == via.net:
                continue
            need = (max(cl, board.net_class_for(other.net).clearance)
                    + via.diameter / 2 + other.diameter / 2)
            d = math.dist((via.x, via.y), (other.x, other.y))
            if d < need:
                v.append(Violation(
                    "clearance.via_via", "error",
                    f"via {via.net} vs via {other.net}",
                    (via.x, via.y), (via.net, other.net), d, need))

    # ── 3c. pad ↔ pad, different nets, layers that meet ──
    # Until 2026-10-21 (F-0002) there was no rule here: two parts whose pads
    # touched, or a through-hole pad over a bottom-side SMD pad, scored zero DRC
    # errors while verify.py's III.2 failed the short. Contact is a short for
    # any pair. Below the clearance only pads of two different parts are
    # reported: the gap inside one footprint is its land pattern's pitch, not a
    # choice placement or routing made.
    for i, p in enumerate(pads):
        for q in pads[i + 1:]:
            if p.net == q.net:
                continue
            if p.shape != "th" and q.shape != "th" and p.layer != q.layer:
                continue
            d = _pad_pad_gap(p, q)
            if d <= CONTACT_TOL:
                v.append(Violation(
                    "short.pad_pad", "error",
                    f"pad {p.ref}.{p.pin} ({p.net}) touches pad {q.ref}.{q.pin} ({q.net})",
                    p.center, (p.net, q.net), d, CONTACT_TOL))
                continue
            if p.ref == q.ref:
                continue
            need = max(board.net_class_for(p.net).clearance,
                       board.net_class_for(q.net).clearance)
            if d < need:
                v.append(Violation(
                    "clearance.pad_pad", "error",
                    f"pad {p.ref}.{p.pin} ({p.net}) vs pad {q.ref}.{q.pin} ({q.net})",
                    p.center, (p.net, q.net), d, need))

    # ── 4. keepout intrusion ──
    for k in board.keepouts:
        rect = (k.x, k.y, k.x + k.w, k.y + k.h)
        if k.kind in ("wire", "all"):
            for t in tracks:
                if k.layer and t.layer != k.layer:
                    continue
                for s in _segments(t):
                    if seg_rect_dist(*s, rect) <= 0:
                        v.append(Violation(
                            "keepout.wire", "error",
                            f"track {t.net} enters keepout ({k.reason or k.kind})",
                            s[0], (t.net,)))
                        break
        if k.kind in ("via", "all"):
            for via in board.vias:
                if rect[0] <= via.x <= rect[2] and rect[1] <= via.y <= rect[3]:
                    v.append(Violation("keepout.via", "error",
                                       f"via {via.net} inside keepout",
                                       (via.x, via.y), (via.net,)))
        if k.kind in ("placement", "all"):
            for c in board.components:
                if rect[0] <= c.x <= rect[2] and rect[1] <= c.y <= rect[3]:
                    v.append(Violation("keepout.placement", "error",
                                       f"{c.ref} inside keepout ({k.reason})",
                                       (c.x, c.y)))

    # ── 5. minimum manufacturable width ──
    # Note this checks the FAB limit, not the net-class width. A net class
    # width is a target; deliberate neck-down at pads is legal and necessary,
    # so flagging every tapered segment would be noise that trains people to
    # ignore the report.
    for t in tracks:
        if t.width < MIN_FAB_WIDTH - 1e-9:
            v.append(Violation("width.min", "error",
                               f"{t.net} below fab minimum",
                               t.points[0], (t.net,), t.width, MIN_FAB_WIDTH))

    # ── 6. board edge ──
    for t in tracks:
        for (x, y) in t.points:
            if not (edge_clearance <= x <= board.outline_w - edge_clearance and
                    edge_clearance <= y <= board.outline_h - edge_clearance):
                v.append(Violation("edge.clearance", "error",
                                   f"{t.net} too close to board edge", (x, y), (t.net,)))
                break

    # ── 7. components overlapping courtyards ──
    for i, c1 in enumerate(board.components):
        for c2 in board.components[i + 1:]:
            if (abs(c1.x - c2.x) < (c1.courtyard_w + c2.courtyard_w) / 2 and
                    abs(c1.y - c2.y) < (c1.courtyard_h + c2.courtyard_h) / 2):
                v.append(Violation("placement.courtyard", "error",
                                   f"{c1.ref} overlaps {c2.ref}", (c1.x, c1.y)))
    return v


# ─────────────────────────────────────────────────────────────────────────────
# Connectivity — which required connections copper actually joins
# ─────────────────────────────────────────────────────────────────────────────
def _touch(ka: str, a, kb: str, b, tol: float) -> bool:
    """Do two pieces of one net's copper make contact? Measured copper edge to
    copper edge: a track is its centreline swept by half its width, a via a disc
    through every layer, a pad a rectangle (or disc) on its own layer."""
    if ka > kb:                                  # canonical order: pad, track, via
        ka, a, kb, b = kb, b, ka, a
    if ka == "pad" and kb == "pad":
        meet = a.shape == "th" or b.shape == "th" or a.layer == b.layer
        return meet and _pad_pad_gap(a, b) <= tol
    if ka == "pad" and kb == "track":
        if a.shape != "th" and a.layer != b.layer:
            return False
        return any(_pad_seg_dist(a, *s) <= b.width / 2 + tol for s in _segments(b))
    if ka == "pad" and kb == "via":
        return _pad_point_dist(a, (b.x, b.y)) <= b.diameter / 2 + tol
    if ka == "track" and kb == "track":
        if a.layer != b.layer:
            return False
        reach = a.width / 2 + b.width / 2 + tol
        return any(seg_seg_dist(*s, *r) <= reach
                   for s in _segments(a) for r in _segments(b))
    if ka == "track" and kb == "via":
        return any(_seg_point_dist(*s, (b.x, b.y)) <= a.width / 2 + b.diameter / 2 + tol
                   for s in _segments(a))
    return math.dist((a.x, a.y), (b.x, b.y)) <= (a.diameter + b.diameter) / 2 + tol


def open_connections(board: Board, tol: float = CONTACT_TOL) -> list[Connection]:
    """Required connections whose two pads no copper of their net joins.

    Union-find over each net's pads, tracks and vias. It has to be connectivity,
    not endpoint matching: the router splits one run into several tracks (the
    neck-down at each pad), its endpoints land wherever the grid rounded them,
    and two stubs that each touch a pad but not each other are not a connection.
    The endpoint-cell matching this replaces (2026-10-17) reported 4 of 12
    connections open on the shipped dht22_relay_monitor board while every one
    was joined — and with `Weights.unrouted` at 1000 that phantom count, not the
    board, decided which candidate won.

    Only same-net copper is joined here; copper of two nets touching is a short,
    which is DRC's business and verify.py's, not this count's."""
    pairs = board.required_pairs()
    if not pairs:
        return []
    want = {a.net for a, _ in pairs}
    items: dict[str, list[tuple[str, object]]] = defaultdict(list)
    for p in board.pads():
        if p.net in want:
            items[p.net].append(("pad", p))
    for t in board.tracks:
        if t.net in want:
            items[t.net].append(("track", t))
    for v in board.vias:
        if v.net in want:
            items[v.net].append(("via", v))

    root: dict[int, int] = {}                    # id(pad) -> its copper group
    for its in items.values():
        parent = list(range(len(its)))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i in range(len(its)):
            for j in range(i + 1, len(its)):
                if find(i) != find(j) and _touch(*its[i], *its[j], tol):
                    parent[find(j)] = find(i)
        for i, (k, o) in enumerate(its):
            if k == "pad":
                root[id(o)] = find(i)

    # Groups are numbered per net, but both pads of a pair share one.
    return [Connection(a.net, a.center, b.center)
            for a, b in pairs if root[id(a)] != root[id(b)]]


# ─────────────────────────────────────────────────────────────────────────────
# Scoring — the total order over candidates
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Weights:
    """Tune these and you change what "a good board" means. This is the single
    most product-defining object in the codebase — it is your opinion, encoded.

    DeepPCB's UI exposes exactly this as filters ("fewest layers", "shortest
    traces"): different weight vectors over one candidate pool."""
    unrouted: float = 1000.0     # an open net is not a board
    drc_error: float = 250.0
    drc_warning: float = 15.0
    via: float = 2.0             # cost, yield risk, and an SI discontinuity
    length_mm: float = 0.4
    layer_used: float = 60.0     # each extra layer is real money at the fab
    skew_mm: float = 30.0        # diff-pair length mismatch


@dataclass
class Score:
    total: float
    unrouted: int
    errors: int
    warnings: int
    vias: int
    length_mm: float
    layers_used: int
    max_skew_mm: float
    breakdown: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return (f"score={self.total:8.1f}  unrouted={self.unrouted:3d}  "
                f"err={self.errors:3d}  warn={self.warnings:3d}  vias={self.vias:3d}  "
                f"len={self.length_mm:7.1f}mm  layers={self.layers_used}")


def diff_pair_skew(board: Board) -> float:
    worst = 0.0
    for dp in board.diff_pairs:
        lp = sum(t.length() for t in board.tracks if t.net == dp.net_p)
        ln = sum(t.length() for t in board.tracks if t.net == dp.net_n)
        worst = max(worst, abs(lp - ln))
    return worst


def score(board: Board, w: Weights | None = None,
          violations: list[Violation] | None = None) -> Score:
    w = w or Weights()
    vs = violations if violations is not None else drc(board)
    errors = sum(1 for x in vs if x.severity == "error")
    warnings = len(vs) - errors
    unrouted = len(open_connections(board))
    length = sum(t.length() for t in board.tracks)
    layers = len({t.layer for t in board.tracks})
    skew = diff_pair_skew(board)

    parts = {
        "unrouted":  w.unrouted * unrouted,
        "drc_error": w.drc_error * errors,
        "drc_warn":  w.drc_warning * warnings,
        "vias":      w.via * len(board.vias),
        "length":    w.length_mm * length,
        "layers":    w.layer_used * max(0, layers - 1),
        "skew":      w.skew_mm * skew,
    }
    return Score(sum(parts.values()), unrouted, errors, warnings,
                 len(board.vias), length, layers, skew, parts)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from board_ir import demo_board, Track as T

    b = demo_board()
    print("empty board:", score(b))

    # deliberately illegal: two different nets, 0.05 mm apart, needs 0.15
    b.tracks = [
        T("F.Cu", "SPI_SCK",  .2, [(5.0, 3.0), (20.0, 3.0)]),
        T("F.Cu", "SPI_MOSI", .2, [(5.0, 3.25), (20.0, 3.25)]),
    ]
    vs = drc(b)
    print(f"\ninjected 1 clearance fault -> {len(vs)} violation(s)")
    for x in vs[:3]:
        print(" ", x)
    assert any(x.rule == "clearance.track_track" for x in vs), "DRC missed the fault"

    # exact-primitive self-checks
    assert abs(seg_seg_dist((0, 0), (10, 0), (0, 2), (10, 2)) - 2.0) < 1e-9
    assert seg_seg_dist((0, 0), (10, 0), (5, -1), (5, 1)) == 0.0
    assert abs(seg_rect_dist((0, 5), (10, 5), (4, 0, 6, 4)) - 1.0) < 1e-9
    assert seg_rect_dist((0, 2), (10, 2), (4, 0, 6, 4)) == 0.0
    print("\ngeometry primitives OK")
