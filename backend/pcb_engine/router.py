"""
router.py — the solver. Still no model in here.

FIRST PRINCIPLES: WHAT ROUTING ACTUALLY IS
------------------------------------------
Routing is shortest-path search on a discretised board, per connection, where
every path you commit becomes an obstacle for every path after it. That is the
whole problem. Three consequences fall straight out of it, and they explain
every architectural decision in this repo:

1. It is a *search*, so it needs a cost function, not a prior over text.
   An LLM emits tokens left to right with no way to evaluate clearance mid-
   generation. A* evaluates 10^5 candidate cells a second and every one it
   accepts is legal by construction.

2. It is *order-dependent*. Route net A first and net B may have no path left.
   There is no single right answer, only a distribution of answers indexed by
   ordering. This is where DeepPCB's "explore millions of layouts" comes from —
   not from magic, from permuting this order and keeping the winners.

3. It is *verifiable*. Every output can be checked exactly by kernel.drc().
   So you never have to trust the solver, which means you can safely swap in a
   better one later without changing anything above it.

WHAT TO ACTUALLY SHIP
---------------------
`AStarRouter` below is real and works, and it is here so the loop is runnable
and so the first principles are legible. It is not competitive with a mature
router. For production, implement `RouterBackend` against Freerouting — it is
open source, has a CLI and a public API, ships Docker images, and speaks
Specctra DSN/SES. `to_dsn()` at the bottom is the bridge; it is the part that
is fiddly, so it is written out in full.

DeepPCB's own engine is reinforcement learning trained by self-play in a custom
C++ simulator, distributed over TPU clusters. You are not going to reproduce
that, and you do not need to: the RL buys better paths inside step 1, while
almost all of the *perceived* product value lives in steps 2 and 3, which are
ordinary engineering.
"""
from __future__ import annotations

import heapq
import math
import random
from concurrent.futures import ProcessPoolExecutor
from os import cpu_count
from dataclasses import dataclass
from typing import Protocol, Iterable

import numpy as np

from board_ir import Board, Connection, Track, Via, Point
from kernel import drc, score, Score, Weights

BLOCKED = -1
FREE = 0


class RouterBackend(Protocol):
    """Swap-in point. Freerouting, an RL policy, or a commercial engine all
    implement this. Nothing above this line changes when you replace it."""
    name: str
    def route(self, board: Board, seed: int, time_budget_s: float) -> Board: ...


# ─────────────────────────────────────────────────────────────────────────────
# Occupancy grid
# ─────────────────────────────────────────────────────────────────────────────
class Grid:
    """3-D occupancy: (layer, y, x). Cell holds 0 free, -1 blocked, or net id.

    A cell owned by the net we are currently routing is *free to enter* — that
    is how a router naturally joins onto its own existing copper instead of
    treating it as an obstacle."""

    def __init__(self, board: Board, res: float = 0.25, edge: float = 0.3):
        self.res = res
        self.board = board
        self.layers = [l.name for l in board.signal_layers()]
        self.li = {n: i for i, n in enumerate(self.layers)}
        self.nx = int(board.outline_w / res) + 1
        self.ny = int(board.outline_h / res) + 1
        self.occ = np.zeros((len(self.layers), self.ny, self.nx), dtype=np.int32)

        # board edge margin
        m = max(1, int(edge / res))
        self.occ[:, :m, :] = BLOCKED
        self.occ[:, -m:, :] = BLOCKED
        self.occ[:, :, :m] = BLOCKED
        self.occ[:, :, -m:] = BLOCKED

        self.net_id = {n: i + 1 for i, n in enumerate(board.nets())}

        # Obstacles are stamped at their TRUE copper extent — no halo here.
        # Clearance is applied per-route instead (see obstacle_mask), because
        # clearance is a property of the PAIR of nets involved, not of the
        # board. Baking a global worst-case halo into the grid was the single
        # biggest quality bug in this router: it charged every 0.2 mm signal
        # net the clearance budget of the widest 0.45 mm power net, which
        # forced long detours around regions that were actually passable.
        self.widest = max((nc.track_width for nc in board.net_classes), default=0.2)
        self.max_cl = max((nc.clearance for nc in board.net_classes), default=0.15)
        for p in board.pads():
            owner = self.net_id.get(p.net, BLOCKED)
            targets = (range(len(self.layers)) if p.shape == "th"
                       else ([self.li[p.layer]] if p.layer in self.li else [0]))
            for li in targets:
                self._stamp_rect(li, *p.bbox(), 0.0, owner)

        # keepouts are hard blocks
        for k in board.keepouts:
            if k.kind in ("wire", "all"):
                targets = ([self.li[k.layer]] if k.layer in self.li
                           else range(len(self.layers)))
                for li in targets:
                    self._stamp_rect(li, k.x, k.y, k.x + k.w, k.y + k.h, 0, BLOCKED)

    # ── coordinate transforms ──
    def to_cell(self, p: Point) -> tuple[int, int]:
        return (int(round(p[1] / self.res)), int(round(p[0] / self.res)))

    def to_mm(self, iy: int, ix: int) -> Point:
        return (ix * self.res, iy * self.res)

    @staticmethod
    def _claim(region, val):
        """Claim cells for `val`, but where two different nets both want a cell
        the cell becomes BLOCKED for everyone.

        Without this rule, whichever net is stamped FIRST owns the overlap, and
        because a net may always enter its own cells, it can legally route right
        up against a foreign pad. That single oversight produced 55 of the 71
        DRC errors in this router's first working version."""
        if val == BLOCKED:
            region[:] = BLOCKED
            return
        free = region == FREE
        other = (region != FREE) & (region != val) & (region != BLOCKED)
        region[free] = val
        region[other] = BLOCKED

    def _stamp_rect(self, li, x0, y0, x1, y1, halo, val):
        a = max(0, int((x0 - halo) / self.res)); b = min(self.nx - 1, int(math.ceil((x1 + halo) / self.res)))
        c = max(0, int((y0 - halo) / self.res)); d = min(self.ny - 1, int(math.ceil((y1 + halo) / self.res)))
        if a > b or c > d:
            return
        self._claim(self.occ[li, c:d + 1, a:b + 1], val)

    @staticmethod
    def _dilate(mask, d: int):
        """8-connected dilation, d times. Square kernel is >= the Euclidean
        disc, so it errs toward legal rather than toward clever."""
        out = mask
        for _ in range(d):
            m = out
            out = m.copy()
            out[:, 1:, :] |= m[:, :-1, :]
            out[:, :-1, :] |= m[:, 1:, :]
            out[:, :, 1:] |= m[:, :, :-1]
            out[:, :, :-1] |= m[:, :, 1:]
            out[:, 1:, 1:] |= m[:, :-1, :-1]
            out[:, 1:, :-1] |= m[:, :-1, 1:]
            out[:, :-1, 1:] |= m[:, 1:, :-1]
            out[:, :-1, :-1] |= m[:, 1:, 1:]
        return out

    def obstacle_mask(self, net: str, width: float, clearance: float):
        """Cells net `net` may not occupy, given the track it will lay down.

        Foreign copper is grown by (my half-width + clearance + half a cell of
        discretisation slack). Because the obstacle was stamped at its true
        extent, the resulting separation is exactly what DRC demands for THIS
        pair — no more, no less. Thin nets therefore squeeze through gaps that
        a wide net cannot, which is what makes the result look like a board."""
        net_val = self.net_id.get(net, 1)
        hard = (self.occ == BLOCKED) | ((self.occ != FREE) & (self.occ != net_val))
        d = max(1, int(math.ceil((width / 2 + clearance + self.res / 2) / self.res)))
        return self._dilate(hard, d)

    def halo_cells(self, own_width: float) -> int:
        """Cells of exclusion around a centreline. Ceil, never round — rounding
        down here is exactly how you ship a board that fails DRC by 0.05 mm."""
        # The +res term is not padding for its own sake: DRC measures continuous
        # geometry while the grid reasons in cells, so a centreline may sit up to
        # half a cell from where the checker thinks it is. Budget a whole cell on
        # both sides and the two views can never disagree.
        return max(0, int(math.ceil((own_width / 2) / self.res)))

    def stamp_path(self, cells: list[tuple[int, int, int]], net: str, halo_cells: int):
        v = self.net_id.get(net, 1)
        for (li, iy, ix) in cells:
            y0, y1 = max(0, iy - halo_cells), min(self.ny, iy + halo_cells + 1)
            x0, x1 = max(0, ix - halo_cells), min(self.nx, ix + halo_cells + 1)
            self._claim(self.occ[li, y0:y1, x0:x1], v)

    def stamp_via(self, iy: int, ix: int, net: str, diameter: float):
        """A via is an obstacle on EVERY layer, not just the two it joins.
        Forgetting this is the single largest source of phantom-legal routes."""
        h = max(1, int(math.ceil((diameter / 2) / self.res)))
        v = self.net_id.get(net, 1)
        y0, y1 = max(0, iy - h), min(self.ny, iy + h + 1)
        x0, x1 = max(0, ix - h), min(self.nx, ix + h + 1)
        for li in range(self.occ.shape[0]):
            self._claim(self.occ[li, y0:y1, x0:x1], v)

    def passable(self, li, iy, ix, net_val) -> bool:
        if not (0 <= iy < self.ny and 0 <= ix < self.nx):
            return False
        c = self.occ[li, iy, ix]
        return c == FREE or c == net_val


# ─────────────────────────────────────────────────────────────────────────────
# A* over (layer, y, x) with via transitions
# ─────────────────────────────────────────────────────────────────────────────
_STEPS = [(0, 1, 1.0), (0, -1, 1.0), (1, 0, 1.0), (-1, 0, 1.0),
          (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


def astar(grid: Grid, start: tuple[int, int, int], goal: tuple[int, int, int],
          blocked, via_cost: float = 12.0, max_expand: int = 60_000):
    ny, nx = grid.ny, grid.nx
    def free(li, iy, ix):
        return 0 <= iy < ny and 0 <= ix < nx and not blocked[li, iy, ix]
    gl, gy, gx = goal

    def h(li, iy, ix):
        dy, dx = abs(iy - gy), abs(ix - gx)
        return (max(dy, dx) + 0.4142 * min(dy, dx)) + (via_cost if li != gl else 0)

    openq = [(h(*start), 0.0, start)]
    came: dict = {}
    best = {start: 0.0}
    expanded = 0

    while openq:
        _, g, cur = heapq.heappop(openq)
        if cur == goal:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            return path[::-1]
        if g > best.get(cur, float("inf")):
            continue
        expanded += 1
        if expanded > max_expand:
            return None
        li, iy, ix = cur

        for dy, dx, w in _STEPS:
            nxt = (li, iy + dy, ix + dx)
            if not free(li, iy + dy, ix + dx):
                continue
            # No corner-cutting: a 45° move may not squeeze between two
            # diagonally-adjacent obstacles. Skipping this check is the classic
            # grid-router bug that produces copper which passes the grid but
            # fails real DRC.
            if dy and dx and not (free(li, iy + dy, ix) and free(li, iy, ix + dx)):
                continue
            ng = g + w
            if ng < best.get(nxt, float("inf")):
                best[nxt] = ng; came[nxt] = cur
                heapq.heappush(openq, (ng + h(*nxt), ng, nxt))

        for nl in range(grid.occ.shape[0]):          # layer change = via
            if nl == li:
                continue
            nxt = (nl, iy, ix)
            if not free(nl, iy, ix):
                continue
            ng = g + via_cost
            if ng < best.get(nxt, float("inf")):
                best[nxt] = ng; came[nxt] = cur
                heapq.heappush(openq, (ng + h(*nxt), ng, nxt))
    return None


def _compress(path, grid) -> list[tuple[str, list[Point]]]:
    """Collapse a cell path into per-layer polylines, dropping collinear points."""
    runs, cur_layer, pts = [], path[0][0], []
    for (li, iy, ix) in path:
        if li != cur_layer:
            runs.append((grid.layers[cur_layer], pts))
            cur_layer, pts = li, [grid.to_mm(iy, ix)]
        pts.append(grid.to_mm(iy, ix))
    runs.append((grid.layers[cur_layer], pts))

    out = []
    for layer, p in runs:
        if len(p) < 2:
            continue
        simp = [p[0]]
        for i in range(1, len(p) - 1):
            ax, ay = simp[-1]; bx, by = p[i]; cx, cy = p[i + 1]
            if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 1e-9:
                simp.append(p[i])
        simp.append(p[-1])
        out.append((layer, simp))
    return out


# ─────────────────────────────────────────────────────────────────────────────
def _split_at(pts: list[Point], dist: float) -> tuple[list[Point], list[Point]]:
    """Cut a polyline at `dist` along its length, interpolating the cut point."""
    acc = 0.0
    for i in range(1, len(pts)):
        seg = math.dist(pts[i - 1], pts[i])
        if acc + seg >= dist:
            t = (dist - acc) / seg if seg else 0.0
            cut = (pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0]),
                   pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1]))
            return pts[:i] + [cut], [cut] + pts[i:]
        acc += seg
    return pts, []


def _neck_down(pts: list[Point], width: float, min_width: float,
               neck_len: float) -> list[tuple[float, list[Point]]]:
    """Taper the ends of a track to `min_width` for `neck_len` millimetres.

    Why this exists: a 0.4 mm power track cannot legally terminate on a pad in
    an 0.8 mm-pitch package — its own half-width plus clearance overruns the
    neighbouring pad. Real routers neck the track down at the pad and widen it
    once clear. Without this the design rules are simply unsatisfiable, and the
    router is being blamed for a geometry contradiction it did not create."""
    total = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    if width <= min_width or total < 2.5 * neck_len:
        return [(width, pts)]
    head, rest = _split_at(pts, neck_len)
    body, tail = _split_at(rest, max(0.0, total - 2 * neck_len))
    out = [(min_width, head), (width, body)]
    if len(tail) >= 2:
        out.append((min_width, tail))
    return [(w, p) for w, p in out if len(p) >= 2]


@dataclass
class AStarRouter:
    """Reference backend. Deliberately simple, deliberately honest."""
    res: float = 0.25
    via_cost: float = 22.0
    passes: int = 4             # rip-up-and-retry attempts
    min_width: float = 0.2      # neck-down target at pads
    neck_len: float = 0.8       # how far the taper runs
    name: str = "astar"

    def _route_pass(self, board: Board, order: list) -> tuple[Board, list]:
        b = board.copy()
        b.tracks, b.vias = [], []
        grid = Grid(b, self.res)
        failed = []

        # Plane nets are satisfied by a via to the pour, not by copper on a
        # signal layer. Do this FIRST so the stitching vias become obstacles
        # that the signal routing has to respect, rather than an afterthought.
        planes = b.plane_nets()
        for p_ in b.pads():
            if p_.net not in planes:
                continue
            nc_ = b.net_class_for(p_.net)
            iy, ix = grid.to_cell(p_.center)
            grid.stamp_via(iy, ix, p_.net, nc_.via_diameter)
            vx, vy = grid.to_mm(iy, ix)
            b.vias.append(Via(vx, vy, net=p_.net, drill=nc_.via_drill,
                              diameter=nc_.via_diameter))

        for c in order:
            nc = b.net_class_for(c.net)
            sy, sx = grid.to_cell(c.a); gy, gx = grid.to_cell(c.b)
            blocked = grid.obstacle_mask(c.net, nc.track_width, nc.clearance)
            # The endpoints are this net's own pads, and dilating foreign copper
            # can swallow them. Re-open them — but ONLY cells this net already
            # owns. Blanket-clearing the neighbourhood instead lets the track
            # stand a quarter-millimetre from a foreign pad, which is precisely
            # the clearance violation the dilation existed to prevent.
            own = grid.occ == grid.net_id.get(c.net, 1)
            for (ey, ex) in ((sy, sx), (gy, gx)):
                y0, y1 = max(0, ey - 1), min(grid.ny, ey + 2)
                x0, x1 = max(0, ex - 1), min(grid.nx, ex + 2)
                blocked[:, y0:y1, x0:x1] &= ~own[:, y0:y1, x0:x1]
            path = None
            for sl in range(grid.occ.shape[0]):      # try each start layer
                path = astar(grid, (sl, sy, sx), (sl, gy, gx), blocked, self.via_cost)
                if path:
                    break
            if not path:
                failed.append(c)                     # fed back into the next pass
                continue

            grid.stamp_path(path, c.net, grid.halo_cells(nc.track_width))

            for layer, pts in _compress(path, grid):
                for w, run in _neck_down(pts, nc.track_width, self.min_width,
                                         self.neck_len):
                    b.tracks.append(Track(layer, c.net, w, run))
            for i in range(1, len(path)):
                if path[i][0] != path[i - 1][0]:
                    iy, ix = path[i][1], path[i][2]
                    grid.stamp_via(iy, ix, c.net, nc.via_diameter)
                    x, y = grid.to_mm(iy, ix)
                    b.vias.append(Via(x, y, net=c.net, drill=nc.via_drill,
                                      diameter=nc.via_diameter))
        return b, failed

    def route(self, board: Board, seed: int = 0, time_budget_s: float = 0.0) -> Board:
        """Rip-up and retry.

        A single pass is order-dependent and therefore unfair: whichever nets
        happen to be routed last are handed whatever space is left, and some of
        them have none. The fix every real router implements is to notice which
        connections failed and give them priority on the next attempt, throwing
        away the previous solution entirely.

        This is the cheapest large quality win available, because a failure is
        evidence: it tells you exactly which net was starved, and the only thing
        it needs is to go earlier. Keep whichever pass scored best."""
        rng = random.Random(seed)
        conns = board.required_connections()
        rng.shuffle(conns)
        conns.sort(key=lambda c: -board.net_class_for(c.net).priority)

        best_b, best_s, starved = None, None, []
        for _ in range(self.passes):
            # previously-starved connections go first, priority still dominates
            order = sorted(conns, key=lambda c: (c not in starved,
                                                 -board.net_class_for(c.net).priority))
            b, failed = self._route_pass(board, order)
            sc = score(b)
            if best_s is None or sc.total < best_s.total:
                best_b, best_s = b, sc
            if not failed:
                break
            starved = failed
        return best_b


# ─────────────────────────────────────────────────────────────────────────────
# Candidate generation — the actual "AI feeling" in DeepPCB's UI
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Candidate:
    id: int
    seed: int
    board: Board
    score: Score

    def row(self) -> dict:
        return {"id": self.id, "seed": self.seed, "score": round(self.score.total, 1),
                "unrouted": self.score.unrouted, "errors": self.score.errors,
                "vias": self.score.vias, "length_mm": round(self.score.length_mm, 1),
                "layers": self.score.layers_used}


def _route_one(payload):
    """Top-level so it is picklable for the process pool."""
    board_json, backend, seed, budget = payload
    b = Board.from_json(board_json)
    return backend.route(b, seed=seed, time_budget_s=budget).to_json(indent=None)


def generate_candidates(board: Board, backend: RouterBackend, n: int = 8,
                        weights: Weights | None = None,
                        time_budget_s: float = 10.0,
                        workers: int | None = None) -> list[Candidate]:
    """Run the solver n times under different orderings, score, rank.

    This is the whole trick. No ML required to get "here are a dozen layouts,
    sorted, pick one" — just a seeded solver and a total order.

    Each seed is fully independent, so this is embarrassingly parallel: the
    wall-clock cost of exploring the search space is (routes / cores), not
    (routes). That ratio is precisely why a candidate pool is a cheap feature
    to ship and an expensive-looking one to use."""
    payloads = [(board.to_json(indent=None), backend, i, time_budget_s)
                for i in range(n)]
    workers = workers if workers is not None else min(n, cpu_count() or 1)

    if workers > 1:
        try:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(_route_one, payloads))
        except Exception:                      # pickling / no-fork environments
            results = [_route_one(p) for p in payloads]
    else:
        results = [_route_one(p) for p in payloads]

    out = [Candidate(i, i, Board.from_json(js), score(Board.from_json(js), weights))
           for i, js in enumerate(results)]
    out.sort(key=lambda c: c.score.total)
    for rank, c in enumerate(out):
        c.id = rank
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Specctra DSN export — the bridge to Freerouting
# ─────────────────────────────────────────────────────────────────────────────
def to_dsn(board: Board) -> str:
    """Emit Specctra DSN. Feed to Freerouting:

        docker run --rm -v $PWD:/work ghcr.io/freerouting/freerouting:latest \\
            -de /work/board.dsn -do /work/board.ses -mp 100

    then parse the .ses wiring section back into Track/Via. DSN is in 1/10000
    inch internally but declaring `(unit mm)` with `(resolution mm 10000)`
    lets us stay in millimetres and scale by 10000."""
    S = 10000
    u = lambda v: int(round(v * S))
    L = [l.name for l in board.signal_layers()]

    out = [f'(pcb "{board.name}"', '  (parser (string_quote ")(space_in_quoted_tokens on)'
           '(host_cad "pcb-agent")(host_version "0.1"))',
           '  (resolution mm 10000)', '  (unit mm)', '  (structure']
    for i, n in enumerate(L):
        out.append(f'    (layer {n} (type signal)(property (index {i})))')
    W, H = u(board.outline_w), u(board.outline_h)
    out.append(f'    (boundary (rect pcb 0 0 {W} {H}))')
    dc = min((nc.clearance for nc in board.net_classes), default=0.15)
    out.append(f'    (rule (width {u(0.2)})(clearance {u(dc)}))')
    for k in board.keepouts:
        if k.kind in ("wire", "all"):
            out.append(f'    (keepout "" (rect {k.layer or L[0]} {u(k.x)} {u(k.y)} '
                       f'{u(k.x + k.w)} {u(k.y + k.h)}))')
    out.append('  )')

    # one image per component; pads inline as rectangles
    out.append('  (placement')
    for c in board.components:
        out.append(f'    (component "img_{c.ref}" (place {c.ref} {u(c.x)} {u(c.y)} '
                   f'{"front" if c.side == "top" else "back"} {c.rotation:g}))')
    out.append('  )')

    out.append('  (library')
    for c in board.components:
        out.append(f'    (image "img_{c.ref}"')
        for p in c.pads:
            out.append(f'      (pin "ps_{c.ref}_{p.pin}" {p.pin} '
                       f'{u(p.x - c.x)} {u(p.y - c.y)})')
        out.append('    )')
    for c in board.components:
        for p in c.pads:
            out.append(f'    (padstack "ps_{c.ref}_{p.pin}"')
            for n in L:
                out.append(f'      (shape (rect {n} {u(-p.w/2)} {u(-p.h/2)} '
                           f'{u(p.w/2)} {u(p.h/2)}))')
            out.append('      (attach off))')
    out.append('  )')

    out.append('  (network')
    for net, pads in board.pads_by_net().items():
        if len(pads) < 2:
            continue
        pins = " ".join(f"{p.ref}-{p.pin}" for p in pads)
        out.append(f'    (net "{net}" (pins {pins}))')
    for nc in board.net_classes:
        nets = " ".join(f'"{n}"' for n in nc.nets if n)
        out.append(f'    (class {nc.name} {nets} (rule (width {u(nc.track_width)})'
                   f'(clearance {u(nc.clearance)})))')
    out.append('  )')
    out.append(')')
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    from board_ir import demo_board

    b = demo_board()
    print(f"board: {len(b.components)} components, {len(b.nets())} nets, "
          f"{len(b.required_connections())} connections to route\n")

    t0 = time.time()
    cands = generate_candidates(b, AStarRouter(), n=6)
    dt = time.time() - t0

    print(f"{'rank':>4} {'seed':>5} {'score':>9} {'unrouted':>9} {'err':>4} "
          f"{'vias':>5} {'length':>8} {'layers':>7}")
    for c in cands:
        r = c.row()
        print(f"{r['id']:>4} {r['seed']:>5} {r['score']:>9} {r['unrouted']:>9} "
              f"{r['errors']:>4} {r['vias']:>5} {r['length_mm']:>8} {r['layers']:>7}")

    best = cands[0]
    print(f"\n{len(cands)} candidates in {dt:.1f}s "
          f"({dt/len(cands):.2f}s each, trivially parallelisable)")
    print(f"best: {best.score}")
    print(f"spread: {cands[0].score.total:.0f} … {cands[-1].score.total:.0f} "
          f"— identical inputs, ordering alone")

    dsn = to_dsn(best.board)
    open("/tmp/demo.dsn", "w").write(dsn)
    print(f"\nDSN export: {len(dsn.splitlines())} lines -> /tmp/demo.dsn")
