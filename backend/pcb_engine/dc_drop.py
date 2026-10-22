"""
dc_drop.py — DC IR drop on the board's copper (physics report, build step 4).

Each rail's copper and the ground's copper (tracks, vias and the realised pour)
become a resistor network. The rail's source pad is held at 0 V, each load's
declared current is drawn at its pads, and the network is solved; a load's drop
is its rail falling plus its ground rising. Rung: simulated, one engine.

The model, stated:
  * track:  R = rho·L / (w·t), t from the board's Stackup, rho annealed copper
            at 20 °C (IEC 60028). Heating is not modelled.
  * via:    a plated barrel, R = rho·h / (pi·d·t_plate), t_plate 20 µm (assumed;
            the IPC-6012 class 2 average). Through-hole pad barrels are 0 Ω.
  * pour:   0.5 mm cells, a cell kept only where all its 0.1 mm cells are
            copper. Dropping copper only raises resistance (Rayleigh), so the
            pour's share of the drop is over-, never under-estimated — except
            that pads join the pour solidly: thermal spokes are not modelled,
            which under-estimates pad-to-plane resistance.
  * pads:   0 Ω, joined to every track point and pour cell their copper covers.
  * loads:  each part's declared current (current_a, from the IR's current_draw_ma)
            drawn at its rail pads; a part with no ground pad (a pull-up) returns
            through other parts, so its ground share is not attributed.

The physics report asks for two engines that must agree (this and padne).
padne is a new dependency and waits on the owner's approval, so this is one
engine; the finding says so. Solved by conjugate gradients in numpy (scipy is
not a dependency either); a solve that does not converge reports unknown.
"""
from __future__ import annotations

import math
from collections import defaultdict

from board_ir import Board
from stackup import COPPER_RESISTIVITY_OHM_M as RHO, default_stackup

PLATING_MM = 0.020
COARSE = 5                       # pour cells merged k x k for the solve
SOURCE_TYPES = ("regulator", "connector")
BUDGET = 0.02                    # drop ≤ 2% of the rail (proposal, S5; owner to confirm)
TOOL = "dc_drop.py resistor mesh, numpy conjugate gradients (one engine; padne blocked)"
_TOL = 0.06


def _finding(*a, **k):
    from verify import Finding          # verify imports this module
    return Finding(*a, **k)


class _UF:
    def __init__(self):
        self.p: list[int] = []

    def add(self) -> int:
        self.p.append(len(self.p))
        return len(self.p) - 1

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


class _Net:
    """One net's copper as nodes (merged by 0 Ω joins) and resistive edges."""

    def __init__(self, board: Board, net: str):
        self.uf = _UF()
        self.edges: list[tuple[int, int, float]] = []          # (a, b, conductance S)
        self.pad_node: dict[tuple[str, str], int] = {}
        st = board.stackup or default_stackup([l.name for l in board.layers])
        layers = [c.name for c in st.copper]
        pts: list[tuple[float, float, str, int]] = []
        segs: list[tuple[str, int, int]] = []

        for t in board.tracks:
            if t.net != net or len(t.points) < 2:
                continue
            g_per_mm = (t.width * st.copper_mm(t.layer)) / (RHO * 1e3)   # S·mm
            ids = []
            for x, y in t.points:
                n = self.uf.add(); ids.append(n); pts.append((x, y, t.layer, n))
            for a, b in zip(ids, ids[1:]):
                segs.append((t.layer, a, b, g_per_mm))
        xy = {n: (x, y) for x, y, _, n in pts}

        def join_on(layer, inside):
            for x, y, lay, n in pts:
                if lay == layer and inside(x, y):
                    yield n

        # Coincident points join; a point lying inside another segment splits it
        # (a T-junction), and the segment becomes the chain through its splits.
        splits: dict[int, list[tuple[float, int]]] = defaultdict(list)
        for i, (x, y, lay, n) in enumerate(pts):
            for x2, y2, lay2, n2 in pts[i + 1:]:
                if lay2 == lay and math.dist((x, y), (x2, y2)) <= _TOL:
                    self.uf.union(n, n2)
            for k, (slay, a, b, _) in enumerate(segs):
                if slay != lay or n in (a, b):
                    continue
                L = math.dist(xy[a], xy[b])
                da, db = math.dist((x, y), xy[a]), math.dist((x, y), xy[b])
                if abs(da + db - L) <= _TOL and da > _TOL and db > _TOL:
                    splits[k].append((da, n))
        for k, (_, a, b, gpm) in enumerate(segs):
            chain = [a] + [n for _, n in sorted(splits.get(k, []))] + [b]
            for u, w in zip(chain, chain[1:]):
                L = math.dist(xy[u], xy[w])
                if L <= 1e-9:
                    self.uf.union(u, w)
                else:
                    self.edges.append((u, w, gpm / L))

        # Pour cells (coarsened; a coarse cell only where all fine cells are copper).
        cells: dict[str, dict[tuple[int, int], int]] = {}
        import numpy as np
        for pr in board.pours:
            if pr.net != net:
                continue
            ny = len(pr.rows)
            nx = max((r[1] for row in pr.rows for r in row), default=0)
            fine = np.zeros((ny, max(nx, 1)), dtype=bool)
            for i, row in enumerate(pr.rows):
                for j0, j1 in row:
                    fine[i, j0:j1] = True
            cy, cx = ny // COARSE, fine.shape[1] // COARSE
            coarse = fine[:cy * COARSE, :cx * COARSE].reshape(cy, COARSE, cx, COARSE).all(axis=(1, 3))
            h = pr.grid * COARSE
            g_sheet = st.copper_mm(pr.layer) / (RHO * 1e3)                # S per square
            ids = {}
            for i, j in zip(*np.nonzero(coarse)):
                ids[(int(i), int(j))] = self.uf.add()
            for (i, j), n in ids.items():
                for nb in ((i + 1, j), (i, j + 1)):
                    if nb in ids:
                        self.edges.append((n, ids[nb], g_sheet))
            cells[pr.layer] = ids
            for x, y, lay, n in pts:
                if lay == pr.layer and (int(y // h), int(x // h)) in ids:
                    self.uf.union(n, ids[(int(y // h), int(x // h))])
            self._h = h

        def cells_in(layer, x0, y0, x1, y1):
            ids = cells.get(layer)
            if not ids:
                return []
            h = self._h
            out = [ids[(i, j)] for i in range(int(y0 // h), int(y1 // h) + 1)
                   for j in range(int(x0 // h), int(x1 // h) + 1)
                   if (i, j) in ids and x0 <= (j + .5) * h <= x1 and y0 <= (i + .5) * h <= y1]
            c = (int(((y0 + y1) / 2) // h), int(((x0 + x1) / 2) // h))
            return out + ([ids[c]] if c in ids else [])

        # Vias: one node per layer, barrel resistance between consecutive layers.
        for v in board.vias:
            if v.net != net:
                continue
            nodes = []
            for lay in layers:
                n = self.uf.add(); nodes.append(n)
                r = v.diameter / 2 + _TOL
                for m in join_on(lay, lambda x, y: math.dist((x, y), (v.x, v.y)) <= r):
                    self.uf.union(n, m)
                for m in cells_in(lay, v.x - v.diameter / 2, v.y - v.diameter / 2,
                                  v.x + v.diameter / 2, v.y + v.diameter / 2):
                    self.uf.union(n, m)
            for (a, za), (b, zb) in zip(zip(nodes, layers), zip(nodes[1:], layers[1:])):
                h_mm = abs(st.z_of(za) - st.z_of(zb)) or st.total_mm
                g = (math.pi * v.drill * PLATING_MM) / (RHO * 1e3 * h_mm)
                self.edges.append((a, b, g))

        # Pads: 0 Ω to the copper they cover.
        for c in board.components:
            for p in c.pads:
                if p.net != net:
                    continue
                n = self.uf.add()
                x0, y0, x1, y1 = p.bbox()
                on = layers if p.shape == "th" else [p.layer]
                for lay in on:
                    for m in join_on(lay, lambda x, y: x0 - _TOL <= x <= x1 + _TOL and
                                     y0 - _TOL <= y <= y1 + _TOL):
                        self.uf.union(n, m)
                    for m in cells_in(lay, x0, y0, x1, y1):
                        self.uf.union(n, m)
                self.pad_node[(c.ref, p.pin)] = n

    def solve(self, source: list[int], loads: dict[int, float]):
        """Potentials (V) with the source nodes at 0 and each load node drawing
        its current out. Returns (potential by root, reachable roots, residual)."""
        import numpy as np
        f = self.uf.find
        src = {f(s) for s in source}
        adj: dict[int, list[int]] = defaultdict(list)
        E = [(f(a), f(b), g) for a, b, g in self.edges if f(a) != f(b)]
        for a, b, _ in E:
            adj[a].append(b); adj[b].append(a)
        seen, stack = set(src), list(src)
        while stack:
            u = stack.pop()
            for w in adj[u]:
                if w not in seen:
                    seen.add(w); stack.append(w)
        free = sorted(seen - src)
        idx = {r: k for k, r in enumerate(free)}
        if not free:
            return {r: 0.0 for r in seen}, seen, 0.0
        I = np.zeros(len(free))
        for n, amps in loads.items():
            r = f(n)
            if r in idx:
                I[idx[r]] -= amps                  # current drawn out of the node
        ia, ib, gg, diag = [], [], [], np.zeros(len(free))
        for a, b, g in E:
            if a not in seen:
                continue
            for u, w in ((a, b), (b, a)):
                if u in idx:
                    diag[idx[u]] += g
                    if w in idx:
                        ia.append(idx[u]); ib.append(idx[w]); gg.append(g)
        ia, ib, gg = np.array(ia, int), np.array(ib, int), np.array(gg)

        def A(x):
            return diag * x - np.bincount(ia, weights=gg * x[ib], minlength=len(free))

        # Jacobi-preconditioned conjugate gradients on the SPD reduced Laplacian.
        x = np.zeros(len(free)); r = I - A(x); z = r / diag; p = z.copy(); rz = r @ z
        norm = np.linalg.norm(I) or 1.0
        for _ in range(20 * len(free) + 100):
            if np.linalg.norm(r) <= 1e-12 * norm:
                break
            Ap = A(p)
            alpha = rz / (p @ Ap)
            x += alpha * p; r -= alpha * Ap
            z = r / diag; rz_new = r @ z
            p = z + (rz_new / rz) * p; rz = rz_new
        v = {rt: float(x[k]) for rt, k in idx.items()}
        v.update({s: 0.0 for s in src})
        return v, seen, float(np.linalg.norm(r) / norm)


def _source(board: Board, netlist: dict, rail: str):
    ref = (netlist.get("rail_sources") or {}).get(rail)
    if ref:
        return board.component(ref)
    found = [c for c in board.components if c.attrs.get("type") in SOURCE_TYPES
             and any(p.net == rail for p in c.pads)]
    return found[0] if len(found) == 1 else None


def rail_drops(board: Board, netlist: dict) -> dict:
    """{rail: {load ref: {rail_v, ground_v, total_v, amps}} | {"_error": why}}."""
    ground = netlist.get("ground_net")
    rails = [n for n in netlist.get("power_nets", []) if n and n != ground]
    out: dict = {}
    gnd = _Net(board, ground) if ground else None
    for rail in rails:
        src = _source(board, netlist, rail)
        if src is None:
            out[rail] = {"_error": "no source identified"}
            continue
        loads = [c for c in board.components if c is not src and c.attrs.get("current_a")
                 and any(p.net == rail for p in c.pads)]
        if not loads:
            out[rail] = {}
            continue
        res: dict = {}
        for side, net in (("rail_v", _Net(board, rail)), ("ground_v", gnd)):
            if net is None:
                continue
            netname = rail if side == "rail_v" else ground
            s_nodes = [net.pad_node[(src.ref, p.pin)] for p in src.pads if p.net == netname]
            draw = {}
            for c in loads:
                pins = [p for p in c.pads if p.net == netname]
                for p in pins:
                    draw[net.pad_node[(c.ref, p.pin)]] = c.attrs["current_a"] / len(pins)
            # The ground side carries the same current back: sources and sinks swap.
            v, seen, resid = net.solve(s_nodes, draw)
            for c in loads:
                pins = [p for p in c.pads if p.net == netname]
                e = res.setdefault(c.ref, {"amps": c.attrs["current_a"], "residual": 0.0})
                e["residual"] = max(e["residual"], resid)
                roots = [net.uf.find(net.pad_node[(c.ref, p.pin)]) for p in pins]
                if not pins and side == "ground_v":
                    e[side] = 0.0              # returns through other parts; not attributable
                elif not pins or not s_nodes or any(r not in seen for r in roots):
                    e[side] = math.inf
                else:
                    e[side] = max(-v[r] for r in roots)
        for e in res.values():
            e["total_v"] = e.get("rail_v", 0.0) + e.get("ground_v", 0.0)
        out[rail] = res
    return out


def check_dc_drop(board: Board, netlist: dict | None) -> list:
    claim = "every load's supply holds within its DC drop budget"
    netlist = netlist or {}
    if not netlist.get("power_nets") or not netlist.get("ground_net"):
        return [_finding("V.3", claim, "unknown", "unknown", "no netlist names the rails",
                         unknown_kind="checkable, tool named",
                         tool="power_nets and ground_net on the PCB netlist")]
    volts = netlist.get("net_voltages") or {}
    drops = rail_drops(board, netlist)
    bad, good, unknown = [], [], []
    for rail, res in drops.items():
        if "_error" in res:
            unknown.append(f"{rail}: {res['_error']}")
            continue
        nominal = volts.get(rail)
        for ref, e in sorted(res.items()):
            if e["residual"] > 1e-6:
                unknown.append(f"{rail}→{ref}: solve did not converge")
            elif math.isinf(e["total_v"]):
                bad.append(f"{rail}→{ref}: not connected to the source through copper")
            elif nominal:
                text = (f"{rail}→{ref} {e['amps']:.3g} A: {e['total_v'] * 1e3:.2f} mV "
                        f"({e['rail_v'] * 1e3:.2f} rail + {e['ground_v'] * 1e3:.2f} ground), "
                        f"{e['total_v'] / nominal:.2%} of {nominal:g} V")
                (bad if e["total_v"] > BUDGET * nominal else good).append(text)
            else:
                unknown.append(f"{rail}: no nominal voltage on the netlist")
    model = (f" Budget {BUDGET:.0%} of the rail (proposal). Model: rho {RHO:g} Ω·m at 20 °C, "
             f"copper from the stackup, pour at {COARSE}x its grid, no thermal spokes; "
             f"one engine, not yet cross-checked (padne awaits approval).")
    if not bad and not good:
        why = "; ".join(unknown) or "no load declares a current"
        if unknown:
            return [_finding("V.3", claim, "unknown", "unknown", why,
                             unknown_kind="checkable, tool named",
                             tool="a rail source (regulator or connector, or rail_sources) "
                                  "and per-part current_a on the netlist")]
        return [_finding("V.3", claim, "simulated", "pass", why, tool=TOOL)]
    detail = "; ".join(bad or good)
    if unknown:
        detail += "; not solved: " + "; ".join(unknown)
    return [_finding("V.3", claim, "simulated", "fail" if bad else "pass", detail + model,
                     sorted({t.split("→")[1].split()[0].rstrip(":") for t in bad}), tool=TOOL)]
