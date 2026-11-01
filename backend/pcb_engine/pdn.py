"""
pdn.py — AC power-delivery impedance of each decoupling loop, lumped and in
closed form (physics report, build step 5, the part buildable without PyPEEC).

Per decoupling capacitor (found from the IR as layout_rules does), the loop from
its power pad to the IC's power pin and back through the ground plane is one
series R-L-C:

    Z(f) = ESR + R_copper + j·2πf·(L_loop + ESL) + 1/(j·2πf·C)

  L_loop  the power-side copper path over the plane, per unit length
          μ0/2π·ln(8h/w + w/4h) for w ≤ h, else μ0·h/w (Wheeler's microstrip
          approximations), plus each via on the path and the two ground vias,
          L = 0.2·h·(ln(4h/d) + 1) nH, h and d in mm (Goldfarb & Pucel 1991).
          Swept ±30%: an assumed range, not a derived one.
  ESL/ESR assumed ranges per package (no part's datasheet figure is recorded).
  C       from the part's value, ±20% (assumed; covers X7R tolerance, not DC bias).

The target is Z_t = ripple·V / I (the target-impedance method): ripple 5% of the
rail (proposal) and I the IC's declared current, taken whole as the transient
(an assumption). |Z| is held to Z_t over the decade below the IC's bandwidth
(pdn_bandwidth_hz on the netlist); the IR carries no edge rate, so without it the
check reports the numbers and says unknown.

Rung: simulated, closed-form model. What it omits, stated: plane and cavity
modes, spreading inductance across the pour, mutual coupling, other caps in
parallel, the regulator. PyPEEC (loop R(f), L(f) from the copper) and an ngspice
sweep are the physics report's route and wait on the owner's approval.
"""
from __future__ import annotations

import itertools
import math
import re

from board_ir import Board
from stackup import COPPER_RESISTIVITY_OHM_M as RHO

MU0 = 4e-7 * math.pi
RIPPLE = 0.05                      # proposal, S5
L_SPREAD = 0.30                    # ±30%, assumed
C_TOL = 0.20                       # ±20%, assumed
ESR = (0.005, 0.1)                 # Ω, assumed
ESL = {"0402": (0.3e-9, 0.7e-9), "0603": (0.4e-9, 1.0e-9), "0805": (0.5e-9, 1.2e-9),
       "1206": (0.6e-9, 1.5e-9)}
ESL_OTHER = (1.0e-9, 5.0e-9)       # leaded or unknown package
TOOL = ("pdn.py closed-form lumped loop (Wheeler microstrip, Goldfarb via), own code; "
        "PyPEEC awaits approval")

_PREFIX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "": 1.0}


def _finding(*a, **k):
    from verify import Finding          # verify imports this module
    return Finding(*a, **k)


def parse_farads(value) -> float | None:
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([pnuµμm]?)\s*F?\s*", str(value or ""))
    return float(m.group(1)) * _PREFIX[m.group(2)] if m else None


def trace_over_plane_h(length_mm: float, width_mm: float, height_mm: float) -> float:
    """Inductance (H) of a trace over a plane."""
    w, h = width_mm, height_mm
    per_m = (MU0 / (2 * math.pi) * math.log(8 * h / w + w / (4 * h)) if w <= h
             else MU0 * h / w)
    return per_m * length_mm * 1e-3


def via_h(height_mm: float, drill_mm: float) -> float:
    return 0.2e-9 * height_mm * (math.log(4 * height_mm / drill_mm) + 1)


def z_series(f: float, r: float, l: float, c: float) -> complex:
    w = 2 * math.pi * f
    return complex(r, w * l - 1 / (w * c))


def _loop(board: Board, cap, cp, ip):
    """(L nominal H, R Ω, words) for one decap loop, or (None, None, why)."""
    from layout_rules import _path
    st = board.stackup
    path = _path(board, cp.net, cp, ip)
    if path is None:
        return None, None, "no power-side copper path"
    length, vias = path
    ground_layers = {p.layer for p in board.pours}
    trace_layer = cp.layer if cp.shape != "th" else st.copper[0].name
    others = [l for l in ground_layers if l != trace_layer]
    if not others:
        return None, None, "no ground pour on another layer to return through"
    h = st.dielectric_between(trace_layer, others[0])
    widths = [t.width for t in board.tracks if t.net == cp.net and len(t.points) >= 2]
    w = min(widths) if widths else min(cp.w, cp.h)
    drill = min((v.drill for v in board.vias), default=0.4)
    l_vias = (vias + 2) * via_h(st.total_mm, drill)          # path vias + two to ground
    L = trace_over_plane_h(max(length, 0.01), w, h) + l_vias
    R = RHO * length * 1e-3 / (w * 1e-3 * st.copper_mm(trace_layer) * 1e-3)
    return L, R, f"{length:.1f} mm over {h:.2f} mm, {vias + 2} via(s)"


def _band_points(f_hi: float) -> list[float]:
    lo = f_hi / 10
    return [lo * 10 ** (k / 50) for k in range(51)]


def check_pdn(board: Board, netlist: dict | None) -> list:
    from layout_rules import _decaps
    claim = "each IC pin's supply impedance stays under its target across frequency (AC PDN)"
    netlist = netlist or {}
    volts = netlist.get("net_voltages") or {}
    band = netlist.get("pdn_bandwidth_hz") or {}
    if not netlist.get("power_nets") or not netlist.get("ground_net"):
        return [_finding("V.3b", claim, "unknown", "unknown", "no netlist names the rails",
                         unknown_kind="checkable, tool named",
                         tool="power_nets and ground_net on the PCB netlist")]
    caps = _decaps(board, netlist)
    if not caps:
        return [_finding("V.3b", claim, "unknown", "unknown",
                         "no decoupling capacitor is identified from the IR, so no loop to model",
                         unknown_kind="checkable by simulation, not run",
                         tool="PyPEEC + ngspice (awaits approval)")]
    bad, good, open_ = [], [], []
    for c, cp, ip, _ in caps:
        C = parse_farads(c.attrs.get("value"))
        L, R, words = _loop(board, c, cp, ip)
        ic = board.component(ip.ref)
        if C is None or L is None:
            open_.append(f"{c.ref}: " + ("no capacitance value" if C is None else words))
            continue
        esl = ESL.get(c.attrs.get("package"), ESL_OTHER)
        f0 = 1 / (2 * math.pi * math.sqrt((L + sum(esl) / 2) * C))
        text = (f"{c.ref}→{ip.ref}.{ip.pin}: loop {L * 1e9:.2f} nH ({words}), "
                f"ESL {esl[0] * 1e9:g}-{esl[1] * 1e9:g} nH, C {C * 1e9:g} nF, "
                f"resonance ≈ {f0 / 1e6:.1f} MHz")
        amps, v = ic.attrs.get("current_a"), volts.get(cp.net)
        f_hi = band.get(ip.ref)
        if not (amps and v and f_hi):
            open_.append(text + " (no target: needs the IC's current, the rail voltage "
                                "and pdn_bandwidth_hz)")
            continue
        zt = RIPPLE * v / amps
        worst = max(
            abs(z_series(f, r_esr + R, (L * k) + l_esl, C * kc))
            for f in _band_points(f_hi)
            for r_esr, k, l_esl, kc in itertools.product(
                ESR, (1 - L_SPREAD, 1 + L_SPREAD), esl, (1 - C_TOL, 1 + C_TOL)))
        text += (f"; worst |Z| {worst:.3g} Ω vs target {zt:.3g} Ω over "
                 f"{f_hi / 10 / 1e6:g}-{f_hi / 1e6:g} MHz")
        (bad if worst > zt else good).append(text)
    model = (f" Target ripple {RIPPLE:.0%} (proposal); loop L ±{L_SPREAD:.0%}, C ±{C_TOL:.0%}, "
             f"ESL/ESR assumed; omits plane modes, spreading inductance, parallel caps.")
    if not bad and not good:
        return [_finding("V.3b", claim, "unknown", "unknown", "; ".join(open_) + model,
                         [c.ref for c, *_ in caps], unknown_kind="checkable, tool named",
                         tool="pdn_bandwidth_hz and per-IC current_a on the netlist")]
    detail = "; ".join(bad or good) + ("; not judged: " + "; ".join(open_) if open_ else "")
    return [_finding("V.3b", claim, "simulated", "fail" if bad else "pass", detail + model,
                     [t.split("→")[1].split(".")[0] for t in bad], tool=TOOL)]
