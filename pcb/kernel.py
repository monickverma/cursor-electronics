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
from dataclasses import dataclass, field

from board_ir import Board, Pad, Track, Via, Point

# Cheapest common fab process limits (2-layer/4-layer, 1 oz). Rules, not targets.
MIN_FAB_WIDTH = 0.127      # 5 mil
MIN_FAB_CLEARANCE = 0.127


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
    boxes = [_bbox_of(t, t.width) for t in tracks]
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
    unrouted = len(board.unrouted())
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
