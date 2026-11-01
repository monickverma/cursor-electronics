"""
pour.py — the declared plane, filled as copper.

A Layer with `plane_net` said "this layer is GND" and nothing more: no polygon,
so return paths, DC drop and plane connectivity had nothing to analyse. This
fills it the way a board tool fills a zone, on a grid of `grid` mm cells:

  * a cell is copper only if its whole square keeps the clearance from every
    foreign net's copper on that layer, and the edge clearance from the outline
    (its centre is at least clearance + grid/sqrt(2) away);
  * the region is opened by the pour's minimum width, removing necks a fab
    could not etch;
  * islands that touch none of the net's own copper are removed (KiCad's
    default "remove islands").

Pads join the pour solidly: no thermal spokes are modelled, which overstates
the pad-to-plane conductance a real relief would give. The verifier checks the
result with its own geometry (verify.py III.1e, III.1f); this file never judges
itself.
"""
from __future__ import annotations

import math
from collections import deque

from board_ir import Board, Pour

GRID = 0.1                 # mm per cell
MIN_WIDTH = 0.25           # KiCad's default zone minimum width
EDGE_CLEARANCE = 0.3       # copper to board edge, as kernel.drc
_EPS = 1e-6                # keeps a cell on the safe side of a float tie


def _reaches(kind: str, o, layer: str) -> bool:
    if kind == "via":
        return True
    if kind == "pad":
        return o.shape == "th" or o.layer == layer
    return o.layer == layer


def _distance(kind: str, o, X, Y):
    """Distance from each grid point to this object's copper (0 inside)."""
    import numpy as np
    if kind == "via":
        return np.maximum(np.hypot(X - o.x, Y - o.y) - o.diameter / 2, 0)
    if kind == "pad":
        if o.shape == "round":
            return np.maximum(np.hypot(X - o.x, Y - o.y) - max(o.w, o.h) / 2, 0)
        hw, hh = o.w / 2, o.h / 2       # rect and through-hole: the land's box
        dx = np.maximum(np.abs(X - o.x) - hw, 0)
        dy = np.maximum(np.abs(Y - o.y) - hh, 0)
        return np.hypot(dx, dy)
    best = np.full(X.shape, np.inf)
    for (ax, ay), (bx, by) in zip(o.points, o.points[1:]):
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else np.clip(((X - ax) * dx + (Y - ay) * dy) / L, 0, 1)
        best = np.minimum(best, np.hypot(X - (ax + t * dx), Y - (ay + t * dy)))
    return np.maximum(best - o.width / 2, 0)


def _extent(kind: str, o) -> tuple[float, float, float, float]:
    if kind == "via":
        r = o.diameter / 2
        return o.x - r, o.y - r, o.x + r, o.y + r
    if kind == "pad":
        r = max(o.w, o.h) / 2
        return o.x - r, o.y - r, o.x + r, o.y + r
    xs = [p[0] for p in o.points]; ys = [p[1] for p in o.points]
    w = o.width / 2
    return min(xs) - w, min(ys) - w, max(xs) + w, max(ys) + w


def fill_pour(board: Board, layer: str, net: str, grid: float = GRID) -> Pour:
    import numpy as np

    nx, ny = max(1, int(board.outline_w / grid)), max(1, int(board.outline_h / grid))
    xs, ys = (np.arange(nx) + 0.5) * grid, (np.arange(ny) + 0.5) * grid
    half = grid / math.sqrt(2)
    pour_cl = board.net_class_for(net).clearance

    free = np.zeros((ny, nx), dtype=bool)
    e = EDGE_CLEARANCE + half + _EPS
    free[np.ix_((ys >= e) & (ys <= board.outline_h - e),
                (xs >= e) & (xs <= board.outline_w - e))] = True
    own = np.zeros((ny, nx), dtype=bool)

    items = ([("pad", p) for p in board.pads()] + [("track", t) for t in board.tracks]
             + [("via", v) for v in board.vias])
    for kind, o in items:
        if not _reaches(kind, o, layer) or (kind == "track" and len(o.points) < 2):
            continue
        foreign = o.net != net
        m = (max(pour_cl, board.net_class_for(o.net).clearance) if o.net else pour_cl) \
            + half + _EPS if foreign else 0.0
        x0, y0, x1, y1 = _extent(kind, o)
        i0, i1 = max(0, int((y0 - m) / grid) - 1), min(ny, int((y1 + m) / grid) + 2)
        j0, j1 = max(0, int((x0 - m) / grid) - 1), min(nx, int((x1 + m) / grid) + 2)
        if i0 >= i1 or j0 >= j1:
            continue
        X, Y = np.meshgrid(xs[j0:j1], ys[i0:i1])
        d = _distance(kind, o, X, Y)
        if foreign:
            free[i0:i1, j0:j1] &= ~(d < m)
        else:
            own[i0:i1, j0:j1] |= d <= 0

    # Opening by a disc of the minimum width.
    r = int(math.ceil(MIN_WIDTH / 2 / grid))
    offs = [(a, b) for a in range(-r, r + 1) for b in range(-r, r + 1) if a * a + b * b <= r * r]

    def shift(a, di, dj):
        out = np.zeros_like(a)
        out[max(0, -di):ny + min(0, -di), max(0, -dj):nx + min(0, -dj)] = \
            a[max(0, di):ny + min(0, di), max(0, dj):nx + min(0, dj)]
        return out

    eroded = free.copy()
    for di, dj in offs:
        eroded &= shift(free, di, dj)
    copper = np.zeros_like(free)
    for di, dj in offs:
        copper |= shift(eroded, di, dj)
    copper &= free

    # Keep only islands that touch the net's own copper.
    keep = np.zeros_like(copper)
    seen = np.zeros_like(copper)
    joined = copper | own
    for si, sj in zip(*np.nonzero(own)):
        if seen[si, sj]:
            continue
        q = deque([(si, sj)]); seen[si, sj] = True
        while q:
            i, j = q.popleft()
            keep[i, j] = True
            for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if 0 <= a < ny and 0 <= b < nx and joined[a, b] and not seen[a, b]:
                    seen[a, b] = True
                    q.append((a, b))
    copper &= keep

    rows: list[list[list[int]]] = []
    for row in copper:
        idx = np.flatnonzero(np.diff(np.concatenate(([0], row.view(np.int8), [0]))))
        rows.append([[int(idx[k]), int(idx[k + 1])] for k in range(0, len(idx), 2)])
    return Pour(layer=layer, net=net, grid=grid, rows=rows)


def fill_planes(board: Board, grid: float = GRID) -> Board:
    """Fill every declared plane; replaces any pour already on the board."""
    board.pours = [fill_pour(board, l.name, l.plane_net, grid)
                   for l in board.layers if l.plane_net]
    return board
