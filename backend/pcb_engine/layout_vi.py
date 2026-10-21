"""
layout_vi.py — voltage and current at layout level (physics report, build step 3).

The schematic-level proofs say how much current flows and at what voltage; until
2026-10-21 nothing asked whether the copper could carry it or keep the voltages
apart. Two checks:

  V.4  each trace is wide enough for its net's current, by the IPC-2221 formula
       I = k·ΔT^0.44·A^0.725 (k 0.048 outer, 0.024 inner; A in mil²), with the
       copper thickness read from the board's Stackup. Rung: rule check — an
       empirical fit with stated conditions, its own error unbounded. IPC-2152's
       charts are the newer reference and are not encoded (they are charts, not
       in the repo); IPC-2221 is the conservative one for most outer traces.

  V.6  copper of two nets keeps the clearance and creepage IEC 60664-1 requires
       for their working voltage and insulation class. Mains to SELV defaults to
       reinforced insulation. Distances are measured edge to edge with round
       pads taken as their box, so they are never over-estimated (sound);
       the requirement is the IEC table as transcribed (iec60664.VERIFIED is
       False), and the finding says so.

Currents and voltages come from the IR (net_currents_a, net_voltages on the PCB
netlist), not from net names. Where the netlist carries none, the check is
unknown and names the missing input.
"""
from __future__ import annotations

import math
from collections import defaultdict

from board_ir import Board
from kernel import seg_rect_dist, seg_seg_dist
import iec60664

MIL_MM = 0.0254
RISE_K = 10.0                   # allowed temperature rise, K (proposal, S5; common allowance)
SOURCE_I = (f"IPC-2221 conductor sizing formula, ΔT ≤ {RISE_K:g} K (the rise is a proposal "
            f"until the owner confirms it)")
SELV_V = 60.0                   # a net at or below this is the safe side of mains
SCOPE_V = 50.0                  # pairs closer than this are functional spacing, DRC's job
ENV = {"pollution": 2, "group": "III", "ovc": "II", "altitude_m": 2000}


def _finding(*a, **k):
    from verify import Finding          # verify imports this module
    return Finding(*a, **k)


# ── V.4 — current ───────────────────────────────────────────────────────────
def required_width_mm(amps: float, copper_mm: float, external: bool = True,
                      rise_k: float = RISE_K) -> float:
    k = 0.048 if external else 0.024
    area_mil2 = (amps / (k * rise_k ** 0.44)) ** (1 / 0.725)
    return area_mil2 / (copper_mm / MIL_MM) * MIL_MM


def rise_k(amps: float, width_mm: float, copper_mm: float, external: bool = True) -> float:
    k = 0.048 if external else 0.024
    area_mil2 = (width_mm / MIL_MM) * (copper_mm / MIL_MM)
    return (amps / (k * area_mil2 ** 0.725)) ** (1 / 0.44)


def check_trace_current(board: Board, netlist: dict | None) -> list:
    claim = "each trace carries its net's current within the allowed temperature rise"
    currents = (netlist or {}).get("net_currents_a")
    if not currents:
        return [_finding("V.4", claim, "unknown", "unknown",
                         "the netlist carries no current per net", unknown_kind="checkable, tool named",
                         tool="net_currents_a on the PCB netlist (from the IR)")]
    st = board.stackup
    outer = {st.copper[0].name, st.copper[-1].name} if st else {"F.Cu", "B.Cu"}
    worst: dict[str, tuple[float, float, float, str]] = {}
    for t in board.tracks:
        amps = currents.get(t.net)
        if not amps or len(t.points) < 2:
            continue
        cu = st.copper_mm(t.layer) if st else 0.035
        need = required_width_mm(amps, cu, t.layer in outer)
        margin = t.width / need
        if t.net not in worst or margin < worst[t.net][0]:
            worst[t.net] = (margin, t.width, need, t.layer)
    if not worst:
        return [_finding("V.4", claim, "rule check", "pass",
                         "no routed net carries a declared current")]
    bad, good = [], []
    for net, (m, w, need, layer) in sorted(worst.items()):
        cu = st.copper_mm(layer) if st else 0.035
        dt = rise_k(currents[net], w, cu, layer in outer)
        text = (f"{net} {currents[net]:.3g} A: {w:g} mm on {layer} "
                f"(needs {need:.2f} mm; ΔT ≈ {dt:.1f} K)")
        (bad if m < 1 else good).append(text)
    return [_finding("V.4", claim, "rule check", "fail" if bad else "pass",
                     "; ".join(bad or good) + f" [{SOURCE_I}; copper from the board's stackup; "
                     f"currents are the IR's declared draws, not yet the z3 proofs' intervals]",
                     [b.split()[0] for b in bad])]


# ── V.6 — clearance and creepage ────────────────────────────────────────────
def _shapes(board: Board) -> dict[str, list]:
    """net -> [(layers or None for all, ('rect', box) | ('cap', a, b, r))]"""
    out: dict[str, list] = defaultdict(list)
    for p in board.pads():
        if p.net:
            out[p.net].append((None if p.shape == "th" else {p.layer}, ("rect", p.bbox())))
    for t in board.tracks:
        for a, b in zip(t.points, t.points[1:]):
            out[t.net].append(({t.layer}, ("cap", a, b, t.width / 2)))
    for v in board.vias:
        out[v.net].append((None, ("cap", (v.x, v.y), (v.x, v.y), v.diameter / 2)))
    for pr in board.pours:
        for r in pr.rects():
            out[pr.net].append(({pr.layer}, ("rect", r)))
    return out


def _gap(s, u) -> float:
    if s[0] == "rect" and u[0] == "rect":
        a, b = s[1], u[1]
        return math.hypot(max(0.0, a[0] - b[2], b[0] - a[2]), max(0.0, a[1] - b[3], b[1] - a[3]))
    if s[0] == "rect":
        s, u = u, s
    if u[0] == "rect":
        return max(0.0, seg_rect_dist(s[1], s[2], u[1]) - s[3])
    return max(0.0, seg_seg_dist(s[1], s[2], u[1], u[2]) - s[3] - u[3])


def _distance(sa: list, sb: list) -> float:
    best = math.inf
    for la, a in sa:
        for lb, b in sb:
            if la is not None and lb is not None and not (la & lb):
                continue
            best = min(best, _gap(a, b))
    return best


def _declared(netlist: dict, a: str, b: str) -> str | None:
    for rule in netlist.get("insulation", []):
        if (a in rule["a"] and b in rule["b"]) or (b in rule["a"] and a in rule["b"]):
            return rule["class"]
    return None


def check_insulation(board: Board, netlist: dict | None) -> list:
    claim = "clearance and creepage hold for each working voltage"
    netlist = netlist or {}
    volts = netlist.get("net_voltages")
    if not volts:
        return [_finding("V.6", claim, "unknown", "unknown",
                         "the netlist carries no voltage per net", unknown_kind="checkable, tool named",
                         tool="net_voltages on the PCB netlist (from the IR)")]
    env = {**ENV, **netlist.get("insulation_env", {})}
    shapes = _shapes(board)
    nets = sorted(n for n in shapes if volts.get(n) is not None)
    pairs = [(a, b) for i, a in enumerate(nets) for b in nets[i + 1:]
             if abs(volts[a] - volts[b]) > SCOPE_V]
    tail = (f" Environment: pollution degree {env['pollution']}, material group "
            f"{env['group']}, overvoltage category {env['ovc']}, ≤{env['altitude_m']} m. "
            f"Figures: {iec60664.SOURCE}"
            + ("" if iec60664.VERIFIED else " — meets the table as transcribed, not 'compliant'."))
    if not pairs:
        return [_finding("V.6", claim, "sound", "pass",
                         f"every net with a declared voltage is within {SCOPE_V:g} V of the "
                         f"others; IEC 60664-1 spacings are not in scope (functional spacing "
                         f"is the DRC's)")]
    bad, good = [], []
    for a, b in pairs:
        va, vb = volts[a], volts[b]
        hazardous = max(abs(va), abs(vb))
        cls = _declared(netlist, a, b) or (
            "reinforced" if min(abs(va), abs(vb)) <= SELV_V < hazardous else "basic")
        work = abs(va - vb)
        need_cr = iec60664.creepage_mm(work, env["pollution"], env["group"], cls)
        need_cl = iec60664.clearance_mm(hazardous, env["ovc"], env["pollution"], cls,
                                        env["altitude_m"])
        need = max(need_cr, need_cl)
        d = _distance(shapes[a], shapes[b])
        text = (f"{a}–{b} ({work:g} V, {cls}): {d:.2f} mm, needs {need_cr:.1f} mm creepage "
                f"and {need_cl:.1f} mm clearance")
        (bad if d < need else good).append(text)
    return [_finding("V.6", claim, "sound", "fail" if bad else "pass",
                     "; ".join(bad or good) + ". Distances are edge to edge on a shared layer, "
                     "round pads as their box (never over-estimated); no slots modelled." + tail,
                     sorted({n for t in bad for n in t.split(" ")[0].split("–")}))]


def check_layout_vi(board: Board, netlist: dict | None) -> list:
    return check_trace_current(board, netlist) + check_insulation(board, netlist)
