"""
layout_rules.py — physics rule checks on the Board IR, the class Quilter calls
Physics Rule Checks (physics report, build step 2).

Every rule here is a *rule check* rung: a published or proposed threshold
applied to the layout, never a solve. Each threshold lives in RULES with its
source, and the ones that are only proposals say so — the owner confirms them
(benchmark plan §6 thresholds are proposals until the first full cycle).

What a part *is* comes from the IR, never from its designator or net name:
a decoupling capacitor is a part of type "capacitor" whose two pads sit on a
power net and the ground net (both declared by the netlist the IR produced);
a crystal is a part of type "crystal"; a bus or clock net is one whose IR
signal type says so (`net_types`). Where the IR does not say, the rule reports
unknown and names what is missing, rather than guessing from "C1" or "VCC".

    P.1   each decoupling cap sits close to the IC power pin it serves
    P.1b  ... and its power-side copper path is short, with few vias
    P.2   each crystal sits close to the IC pins it drives
    P.3   each net keeps one track width (width span)
    P.4   bus and clock nets run over unbroken ground (return path)
    P.5   declared differential pairs keep their gap (pair spacing)
"""
from __future__ import annotations

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass

from board_ir import Board


@dataclass(frozen=True)
class Rule:
    value: float
    unit: str
    source: str


_PROPOSAL = "benchmark_loop_plan.md §6, a proposal until the owner confirms it"
RULES: dict[str, Rule] = {
    "decap_distance": Rule(6.0, "mm", f"decoupling distance ≤ 6 mm, {_PROPOSAL}"),
    "decap_path": Rule(10.0, "mm", f"power-side copper path ≤ 10 mm (proposal, S5, "
                                   f"after Quilter's bypass-cap path-length PRC)"),
    "decap_vias": Rule(2, "vias", "≤ 2 vias on the power-side path (proposal, S5, after "
                                  "Quilter's bypass-cap via-count PRC)"),
    "crystal_distance": Rule(5.0, "mm", "crystal pad to IC pin ≤ 5 mm (proposal, S5; "
                                        "Quilter's crystal PRC figure not confirmed)"),
    "width_span": Rule(0.10, "ratio", "Quilter PRC 'Invalid Width Span', ±10% "
                                      "(physics report: page not opened, unconfirmed)"),
    "ground_overlap": Rule(0.90, "fraction", "bus/clock track length over unbroken "
                                             "ground ≥ 90% (proposal, S5, after Quilter's "
                                             "ground-overlap PRC)"),
    "pair_spacing": Rule(0.10, "ratio", "Quilter PRC 'Uncoupled Spacing', ±10% "
                                        "(physics report: page not opened, unconfirmed)"),
}

IC_TYPES = {"microcontroller", "sensor", "transceiver", "regulator", "opamp",
            "modem", "optocoupler"}
EDGE_RATE_TYPES = {"spi_sck", "spi_mosi", "spi_miso", "spi_cs", "i2c_scl", "i2c_sda",
                   "uart_tx", "uart_rx", "pwm", "rs485_a", "rs485_b"}
_TOL = 0.06                     # copper closer than this is one piece (verify.CONTACT_TOL)


def _finding(*a, **k):
    from verify import Finding          # verify imports this module
    return Finding(*a, **k)


def _cite(name: str) -> str:
    r = RULES[name]
    return f"[{r.value:g} {r.unit}: {r.source}]"


def _layers_of(pad, board: Board) -> list[str]:
    return [l.name for l in board.layers] if pad.shape == "th" else [pad.layer]


def _typed(board: Board) -> bool:
    return any(c.attrs.get("type") for c in board.components)


# ── P.1 / P.1b — decoupling ─────────────────────────────────────────────────
def _decaps(board: Board, netlist: dict):
    """(cap, power pad, nearest IC pad on that rail, distance) per decoupling cap."""
    ground = netlist.get("ground_net")
    rails = {n for n in netlist.get("power_nets", []) if n and n != ground}
    out = []
    for c in board.components:
        if c.attrs.get("type") != "capacitor" or len(c.pads) != 2:
            continue
        nets = {p.net for p in c.pads}
        rail = next(iter(nets & rails), None)
        if rail is None or ground not in nets:
            continue
        cp = next(p for p in c.pads if p.net == rail)
        ic_pads = [p for o in board.components if o.attrs.get("type") in IC_TYPES
                   for p in o.pads if p.net == rail]
        if not ic_pads:
            continue
        ip = min(ic_pads, key=lambda p: math.dist(p.center, cp.center))
        out.append((c, cp, ip, math.dist(ip.center, cp.center)))
    return out


def _path(board: Board, net: str, a, b) -> tuple[float, int] | None:
    """Shortest copper path between pads a and b over the net's tracks and
    vias: (length mm, vias crossed), or None when no path is found. Track
    points join where they coincide, or where one lies on another segment."""
    nodes: list[tuple[float, float, str | None]] = []      # layer None = via
    edges: dict[int, list[tuple[int, float]]] = defaultdict(list)

    def add(x, y, layer):
        nodes.append((x, y, layer))
        return len(nodes) - 1

    def link(i, j, w):
        edges[i].append((j, w)); edges[j].append((i, w))

    segs = []                                    # (layer, i, j)
    for t in board.tracks:
        if t.net != net or len(t.points) < 2:
            continue
        ids = [add(x, y, t.layer) for x, y in t.points]
        for i, j in zip(ids, ids[1:]):
            link(i, j, math.dist(nodes[i][:2], nodes[j][:2]))
            segs.append((t.layer, i, j))
    point_ids = list(range(len(nodes)))
    vias = [add(v.x, v.y, None) for v in board.vias if v.net == net]
    ia, ib = add(*a.center, "pad"), add(*b.center, "pad")
    pads = {ia: a, ib: b}

    for i in point_ids:
        x, y, layer = nodes[i]
        for j in point_ids:
            if j > i and nodes[j][2] == layer and math.dist((x, y), nodes[j][:2]) <= _TOL:
                link(i, j, 0.0)
        for lay, s, e in segs:                   # T-junction onto a segment
            if lay != layer or i in (s, e):
                continue
            (sx, sy, _), (ex, ey, _) = nodes[s], nodes[e]
            L = math.dist((sx, sy), (ex, ey))
            if L and abs(math.dist((x, y), (sx, sy)) + math.dist((x, y), (ex, ey)) - L) <= _TOL:
                link(i, s, math.dist((x, y), (sx, sy)))
                link(i, e, math.dist((x, y), (ex, ey)))
        for v in vias:
            vv = next(o for o in board.vias if (o.x, o.y) == nodes[v][:2])
            if math.dist((x, y), nodes[v][:2]) <= vv.diameter / 2 + _TOL:
                link(i, v, math.dist((x, y), nodes[v][:2]))
        for k, p in pads.items():
            x0, y0, x1, y1 = p.bbox()
            if layer in _layers_of(p, board) and \
                    x0 - _TOL <= x <= x1 + _TOL and y0 - _TOL <= y <= y1 + _TOL:
                link(i, k, math.dist((x, y), p.center))

    dist = {ia: (0.0, 0)}
    heap = [(0.0, 0, ia)]
    while heap:
        d, nv, i = heapq.heappop(heap)
        if i == ib:
            return d, nv
        if dist.get(i, (math.inf, 0))[0] < d:
            continue
        for j, w in edges[i]:
            nd, nn = d + w, nv + (1 if nodes[j][2] is None else 0)
            if nd < dist.get(j, (math.inf, 0))[0]:
                dist[j] = (nd, nn)
                heapq.heappush(heap, (nd, nn, j))
    return None


def _check_decoupling(board: Board, netlist: dict) -> list:
    claim = "each decoupling capacitor sits close to the IC power pin it serves"
    if not _typed(board):
        return [_finding("P.1", claim, "unknown", "unknown",
                         "no part on the board carries its IR type, so no capacitor can "
                         "be identified as decoupling without guessing from its name",
                         unknown_kind="checkable, tool named",
                         tool="component types on the PCB netlist")]
    if not netlist.get("power_nets") or not netlist.get("ground_net"):
        return [_finding("P.1", claim, "unknown", "unknown",
                         "no netlist names the power and ground nets",
                         unknown_kind="checkable, tool named",
                         tool="power_nets and ground_net on the PCB netlist")]
    caps = _decaps(board, netlist)
    if not caps:
        return [_finding("P.1", claim, "rule check", "pass",
                         "no capacitor sits between a declared power net and ground "
                         "beside an IC; nothing to check")]
    lim = RULES["decap_distance"].value
    far = [f"{c.ref} is {d:.1f} mm from {ip.ref}.{ip.pin} ({cp.net})"
           for c, cp, ip, d in caps if d > lim]
    near = [f"{c.ref}→{ip.ref}.{ip.pin} {d:.1f} mm" for c, cp, ip, d in caps if d <= lim]
    out = [_finding("P.1", claim, "rule check", "fail" if far else "pass",
                    ("; ".join(far) if far else "; ".join(near)) + " " + _cite("decap_distance"),
                    [c.ref for c, *_ in caps])]

    plim, vlim = RULES["decap_path"].value, RULES["decap_vias"].value
    bad, good = [], []
    for c, cp, ip, _ in caps:
        p = _path(board, cp.net, cp, ip)
        if p is None:
            bad.append(f"{c.ref}→{ip.ref}.{ip.pin}: no {cp.net} copper path found")
        elif p[0] > plim or p[1] > vlim:
            bad.append(f"{c.ref}→{ip.ref}.{ip.pin}: {p[0]:.1f} mm, {p[1]} via(s)")
        else:
            good.append(f"{c.ref}→{ip.ref}.{ip.pin}: {p[0]:.1f} mm, {p[1]} via(s)")
    out.append(_finding(
        "P.1b", "each decoupling capacitor's power-side copper path is short, with few vias",
        "rule check", "fail" if bad else "pass",
        "; ".join(bad or good) + f" {_cite('decap_path')} {_cite('decap_vias')}",
        [c.ref for c, *_ in caps]))
    return out


# ── P.2 — crystals ──────────────────────────────────────────────────────────
def _check_crystals(board: Board) -> list:
    claim = "each crystal sits close to the IC pins it drives"
    if not _typed(board):
        return [_finding("P.2", claim, "unknown", "unknown",
                         "no part carries its IR type; a crystal is not guessed from its name",
                         unknown_kind="checkable, tool named",
                         tool="component types on the PCB netlist")]
    lim = RULES["crystal_distance"].value
    far, near = [], []
    for c in board.components:
        if c.attrs.get("type") != "crystal":
            continue
        for p in c.pads:
            ic = [q for o in board.components if o.attrs.get("type") in IC_TYPES
                  for q in o.pads if p.net and q.net == p.net]
            if not ic:
                continue
            q = min(ic, key=lambda q: math.dist(q.center, p.center))
            d = math.dist(q.center, p.center)
            (far if d > lim else near).append(f"{c.ref}.{p.pin}→{q.ref}.{q.pin} {d:.1f} mm")
    if not far and not near:
        return [_finding("P.2", claim, "rule check", "pass", "no crystal on the board")]
    return [_finding("P.2", claim, "rule check", "fail" if far else "pass",
                     "; ".join(far or near) + " " + _cite("crystal_distance"))]


# ── P.3 — width span ────────────────────────────────────────────────────────
def _check_width_span(board: Board) -> list:
    span = RULES["width_span"].value
    widths: dict[str, list[float]] = defaultdict(list)
    for t in board.tracks:
        if t.net and len(t.points) >= 2:
            widths[t.net].append(t.width)
    bad = [f"{n}: {min(w):g}-{max(w):g} mm" for n, w in sorted(widths.items())
           if (max(w) - min(w)) / min(w) > span + 1e-9]
    return [_finding("P.3", "each net keeps one track width", "rule check",
                     "fail" if bad else "pass",
                     ("; ".join(bad[:8]) if bad else f"{len(widths)} routed net(s), each one width")
                     + " " + _cite("width_span"), [b.split(":")[0] for b in bad][:12])]


# ── P.4 — ground under bus and clock nets ───────────────────────────────────
def _check_ground_overlap(board: Board, netlist: dict) -> list:
    claim = "bus and clock nets run over unbroken ground"
    types = netlist.get("net_types")
    if not types:
        return [_finding("P.4", claim, "unknown", "unknown",
                         "the netlist carries no IR signal type per net, so no net is known "
                         "to be a bus or clock", unknown_kind="checkable, tool named",
                         tool="net_types on the PCB netlist")]
    scope = {n for n, t in types.items() if t in EDGE_RATE_TYPES}
    tracks = [t for t in board.tracks if t.net in scope and len(t.points) >= 2]
    if not tracks:
        return [_finding("P.4", claim, "rule check", "pass", "no bus or clock net is routed")]
    ground = netlist.get("ground_net")
    lim = RULES["ground_overlap"].value
    covered: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for t in tracks:
        under = [p for p in board.pours if p.net == ground and p.layer != t.layer]
        for (ax, ay), (bx, by) in zip(t.points, t.points[1:]):
            L = math.dist((ax, ay), (bx, by))
            n = max(1, int(L / 0.05))
            for k in range(n):
                f = (k + 0.5) / n
                x, y = ax + f * (bx - ax), ay + f * (by - ay)
                hit = any(p.has_cell(*p.cell_of(x, y)) for p in under)
                covered[t.net][0] += L / n * hit
                covered[t.net][1] += L / n
    bad = [f"{n}: {c / L:.0%} of {L:.1f} mm over ground" for n, (c, L) in sorted(covered.items())
           if c / L < lim]
    good = [f"{n}: {c / L:.0%}" for n, (c, L) in sorted(covered.items()) if c / L >= lim]
    return [_finding("P.4", claim, "rule check", "fail" if bad else "pass",
                     "; ".join(bad or good) + " " + _cite("ground_overlap"),
                     [b.split(":")[0] for b in bad])]


# ── P.5 — differential pair spacing ─────────────────────────────────────────
def _seg_dist(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def _check_pair_spacing(board: Board) -> list:
    claim = "each differential pair keeps its declared gap"
    if not board.diff_pairs:
        return [_finding("P.5", claim, "rule check", "pass", "no differential pair is declared")]
    span = RULES["pair_spacing"].value
    bad, good = [], []
    for dp in board.diff_pairs:
        pt = [t for t in board.tracks if t.net == dp.net_p and len(t.points) >= 2]
        nt = [t for t in board.tracks if t.net == dp.net_n and len(t.points) >= 2]
        gaps = []
        for t in pt:
            for a, b in zip(t.points, t.points[1:]):
                L = math.dist(a, b)
                for k in range(max(1, int(L / 0.1))):
                    f = (k + 0.5) / max(1, int(L / 0.1))
                    x = (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
                    for u in nt:
                        if u.layer != t.layer:
                            continue
                        d = min(_seg_dist(x, c, e) for c, e in zip(u.points, u.points[1:]))
                        gap = d - (t.width + u.width) / 2
                        if gap < 3 * (dp.gap + dp.width):       # the coupled region only
                            gaps.append(gap)
        if not gaps:
            bad.append(f"{dp.name}: the two nets never run coupled")
            continue
        lo, hi = min(gaps), max(gaps)
        if abs(lo - dp.gap) > span * dp.gap or abs(hi - dp.gap) > span * dp.gap:
            bad.append(f"{dp.name}: gap {lo:.3f}-{hi:.3f} mm against {dp.gap} mm")
        else:
            good.append(f"{dp.name}: gap {lo:.3f}-{hi:.3f} mm")
    return [_finding("P.5", claim, "rule check", "fail" if bad else "pass",
                     "; ".join(bad or good) + " " + _cite("pair_spacing"))]


def check_layout_rules(board: Board, netlist: dict | None) -> list:
    netlist = netlist or {}
    return (_check_decoupling(board, netlist) + _check_crystals(board)
            + _check_width_span(board) + _check_ground_overlap(board, netlist)
            + _check_pair_spacing(board))
