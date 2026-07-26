"""
render_pretty.py — presentation-grade board rendering.

The engineering renderer (render.py) exists to expose faults: flat colours, DRC
markers, ratlines. This one exists to be looked at. Same Board IR, different
audience.

What makes a PCB render read as real, roughly in order of payoff:

  1. Soldermask over copper, not copper on a green rectangle. Traces show as
     a *tint* through the mask, pads are the only bare metal. This single
     detail separates "CAD screenshot" from "photo of a board".
  2. ENIG gold pads with a warm gradient. Real finish is not flat yellow.
  3. Teardrops where a track meets a pad — a manufacturing feature that also
     happens to be the thing that makes routing look hand-drawn rather than
     machine-stamped.
  4. Silkscreen: component outlines and designators in off-white, slightly
     transparent, under a faint blur. Crisp white silk looks fake.
  5. Copper pour with subtle noise, and a soft vignette so the board has
     volume instead of sitting flat on the page.
"""
from __future__ import annotations

import math
from board_ir import Board, Point

# ── finishes ────────────────────────────────────────────────────────────────
THEMES = {
    "green":  dict(mask="#0b4f33", mask_hi="#126b45", copper="#5fd39a",
                   silk="#e8eee4", edge="#c9b46b"),
    "blue":   dict(mask="#0f3160", mask_hi="#17457f", copper="#6aa8f0",
                   silk="#eaf0f8", edge="#c9b46b"),
    "black":  dict(mask="#121418", mask_hi="#1b1e24", copper="#7d8794",
                   silk="#f2f4f7", edge="#b9a05c"),
    "purple": dict(mask="#33104a", mask_hi="#451763", copper="#b07fd8",
                   silk="#f0e8f8", edge="#c9b46b"),
    "red":    dict(mask="#5e1212", mask_hi="#7d1a1a", copper="#e07a7a",
                   silk="#f8eaea", edge="#c9b46b"),
}

GOLD_HI, GOLD_LO = "#f5d98a", "#c9a544"


def _teardrop(px: float, py: float, tx: float, ty: float,
              pad_r: float, w: float, S) -> str:
    """Fillet where a track enters a pad.

    Real teardrops exist to survive drill misregistration and thermal cycling.
    They are also, not coincidentally, what stops a layout looking like it was
    drawn with a ruler by something that has never held a soldering iron."""
    dx, dy = tx - px, ty - py
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return ""
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    reach = min(L, pad_r * 2.4)
    bw = max(w * 0.5, pad_r * 0.85)          # half-width at the pad
    ax, ay = px + nx * bw, py + ny * bw
    bx, by = px - nx * bw, py - ny * bw
    ex, ey = px + ux * reach, py + uy * reach
    cx1, cy1 = px + ux * reach * 0.55 + nx * bw * 0.75, py + uy * reach * 0.55 + ny * bw * 0.75
    cx2, cy2 = px + ux * reach * 0.55 - nx * bw * 0.75, py + uy * reach * 0.55 - ny * bw * 0.75
    return (f'<path d="M {S(ax,ay)} Q {S(cx1,cy1)} {S(ex,ey)} '
            f'Q {S(cx2,cy2)} {S(bx,by)} Z" fill="url(#cu)"/>')


def to_svg(board: Board, scale: float = 30.0, theme: str = "green",
           title: str = "", show_pour: bool = True) -> str:
    T = THEMES.get(theme, THEMES["green"])
    W, H = board.outline_w, board.outline_h
    m = 4.0
    Wp, Hp = (W + m * 2) * scale, (H + m * 2) * scale
    X = lambda x: (x + m) * scale
    Y = lambda y: (H - y + m) * scale
    S = lambda x, y: f"{X(x):.2f},{Y(y):.2f}"

    o: list[str] = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{Wp:.0f}" '
             f'height="{Hp:.0f}" viewBox="0 0 {Wp:.0f} {Hp:.0f}">')

    # ── defs: gradients, filters, texture ──
    o.append(f'''<defs>
  <linearGradient id="mask" x1="0" y1="0" x2="0.7" y2="1">
    <stop offset="0%"  stop-color="{T['mask_hi']}"/>
    <stop offset="55%" stop-color="{T['mask']}"/>
    <stop offset="100%" stop-color="{T['mask']}"/>
  </linearGradient>
  <linearGradient id="cu" x1="0" y1="0" x2="0.6" y2="1">
    <stop offset="0%" stop-color="{GOLD_HI}"/>
    <stop offset="100%" stop-color="{GOLD_LO}"/>
  </linearGradient>
  <radialGradient id="padg" cx="0.35" cy="0.3" r="0.85">
    <stop offset="0%" stop-color="#fdf0bd"/>
    <stop offset="45%" stop-color="{GOLD_HI}"/>
    <stop offset="100%" stop-color="{GOLD_LO}"/>
  </radialGradient>
  <radialGradient id="vig" cx="0.5" cy="0.45" r="0.78">
    <stop offset="55%" stop-color="#000" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000" stop-opacity="0.10"/>
  </radialGradient>
  <filter id="soft"><feGaussianBlur stdDeviation="{scale*0.012:.2f}"/></filter>
  <filter id="drop" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="{scale*0.13:.1f}" stdDeviation="{scale*0.22:.1f}"
                  flood-color="#000" flood-opacity="0.55"/>
  </filter>
  <clipPath id="board">
    <rect x="{X(0):.1f}" y="{Y(H):.1f}" width="{W*scale:.1f}"
          height="{H*scale:.1f}" rx="{2.4*scale:.1f}"/>
  </clipPath>
</defs>''')

    o.append(f'<rect width="100%" height="100%" fill="#0a0c10"/>')

    # ── substrate ──
    o.append(f'<rect x="{X(0):.1f}" y="{Y(H):.1f}" width="{W*scale:.1f}" '
             f'height="{H*scale:.1f}" rx="{2.4*scale:.1f}" fill="url(#mask)" '
             f'filter="url(#drop)"/>')

    o.append('<g clip-path="url(#board)">')

    # ── copper pour, seen through the mask ──
    if show_pour and any(l.plane_net for l in board.layers):
        o.append(f'<rect x="{X(0):.1f}" y="{Y(H):.1f}" width="{W*scale:.1f}" '
                 f'height="{H*scale:.1f}" fill="{T["copper"]}" opacity="0.13"/>')

    # ── tracks: bottom layer dimmer, as if seen through the substrate ──
    for layer, op, wmul in (("B.Cu", 0.42, 1.0), ("F.Cu", 1.0, 1.0)):
        for t in board.tracks:
            if t.layer != layer:
                continue
            pts = " ".join(S(x, y) for x, y in t.points)
            o.append(f'<polyline points="{pts}" fill="none" stroke="{T["copper"]}" '
                     f'stroke-width="{max(1.2, t.width*scale*wmul):.2f}" '
                     f'stroke-linecap="round" stroke-linejoin="round" '
                     f'opacity="{op}"/>')
        # specular highlight along the top layer only
        if layer == "F.Cu":
            for t in board.tracks:
                if t.layer != layer:
                    continue
                pts = " ".join(S(x, y) for x, y in t.points)
                o.append(f'<polyline points="{pts}" fill="none" stroke="#ffffff" '
                         f'stroke-width="{max(0.4, t.width*scale*0.22):.2f}" '
                         f'stroke-linecap="round" stroke-linejoin="round" '
                         f'opacity="0.22"/>')

    # ── silkscreen outlines, under the pads ──
    for c in board.components:
        if c.courtyard_w <= 1.2 and c.courtyard_h <= 1.2:
            continue
        cw, ch = c.courtyard_w * 0.86, c.courtyard_h * 0.86
        o.append(f'<rect x="{X(c.x-cw/2):.1f}" y="{Y(c.y+ch/2):.1f}" '
                 f'width="{cw*scale:.1f}" height="{ch*scale:.1f}" rx="{0.18*scale:.1f}" '
                 f'fill="none" stroke="{T["silk"]}" stroke-opacity="0.72" '
                 f'stroke-width="{max(0.7, 0.055*scale):.2f}" filter="url(#soft)"/>')

    # ── teardrops, then pads ──
    pad_at: dict[tuple[int, int], object] = {}
    for c in board.components:
        for p in c.pads:
            pad_at[(round(p.x, 2), round(p.y, 2))] = p
    for t in board.tracks:
        for end, nxt in ((t.points[0], t.points[1]),
                         (t.points[-1], t.points[-2])):
            p = pad_at.get((round(end[0], 2), round(end[1], 2)))
            if p and p.net == t.net:
                o.append(_teardrop(end[0], end[1], nxt[0], nxt[1],
                                   min(p.w, p.h) / 2, t.width, S))

    for c in board.components:
        for p in c.pads:
            if p.shape == "th":
                o.append(f'<circle cx="{X(p.x):.1f}" cy="{Y(p.y):.1f}" '
                         f'r="{p.w/2*scale:.2f}" fill="url(#padg)"/>')
                o.append(f'<circle cx="{X(p.x):.1f}" cy="{Y(p.y):.1f}" '
                         f'r="{p.w/4.4*scale:.2f}" fill="#0b0d10" opacity="0.92"/>')
            else:
                r = min(p.w, p.h) * 0.22 * scale
                o.append(f'<rect x="{X(p.x-p.w/2):.2f}" y="{Y(p.y+p.h/2):.2f}" '
                         f'width="{p.w*scale:.2f}" height="{p.h*scale:.2f}" '
                         f'rx="{r:.2f}" fill="url(#padg)"/>')

    # ── vias: mask-covered copper rings ──
    for v in board.vias:
        o.append(f'<circle cx="{X(v.x):.1f}" cy="{Y(v.y):.1f}" '
                 f'r="{v.diameter/2*scale:.2f}" fill="url(#cu)" opacity="0.75"/>')
        o.append(f'<circle cx="{X(v.x):.1f}" cy="{Y(v.y):.1f}" '
                 f'r="{v.drill/2*scale:.2f}" fill="#0b0d10" opacity="0.85"/>')

    # ── designators ──
    for c in board.components:
        if not c.ref:
            continue
        # Silk sits just outside the courtyard, clamped inside the board edge.
        # Scaling the offset by courtyard height put a DIP-28's designator 22 mm
        # away from the part, stranded at the board edge.
        fs = max(6.5, min(0.62, max(c.courtyard_w, 2.0) * 0.16) * scale)
        ly = min(H - 1.2, c.y + c.courtyard_h / 2 + 1.1)
        o.append(f'<text x="{X(c.x):.1f}" y="{Y(ly):.1f}" '
                 f'fill="{T["silk"]}" fill-opacity="0.95" '
                 f'font-family="Inter,Helvetica,sans-serif" font-size="{fs:.1f}" '
                 f'font-weight="600" letter-spacing="0.4" text-anchor="middle">'
                 f'{c.ref}</text>')

    # ── vignette only ──
    o.append(f'<rect x="{X(0):.1f}" y="{Y(H):.1f}" width="{W*scale:.1f}" '
             f'height="{H*scale:.1f}" fill="url(#vig)"/>')
    o.append('</g>')

    # ── bare-copper edge bevel ──
    o.append(f'<rect x="{X(0):.1f}" y="{Y(H):.1f}" width="{W*scale:.1f}" '
             f'height="{H*scale:.1f}" rx="{2.4*scale:.1f}" fill="none" '
             f'stroke="{T["edge"]}" stroke-opacity="0.55" stroke-width="1.4"/>')

    if title:
        o.append(f'<text x="{X(0):.1f}" y="{m*scale*0.55:.0f}" fill="#8b93a3" '
                 f'font-family="ui-monospace,monospace" font-size="{0.42*scale:.0f}">'
                 f'{title}</text>')
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    import sys
    from board_ir import demo_board
    from router import AStarRouter, generate_candidates
    from kernel import score

    b = demo_board()
    for l in b.layers:
        if l.name == "In1.Cu":
            l.plane_net = "GND"
        if l.name == "In2.Cu":
            l.plane_net = "+3V3"

    cands = generate_candidates(b, AStarRouter(), n=4)
    best = cands[0].board
    s = cands[0].score
    n = len(best.required_connections())
    title = (f"{n - s.unrouted}/{n} routed   {s.errors} DRC errors   "
             f"{s.vias} vias   {s.length_mm:.0f} mm")

    theme = sys.argv[1] if len(sys.argv) > 1 else "green"
    out = sys.argv[2] if len(sys.argv) > 2 else f"pretty_{theme}.svg"
    open(out, "w").write(to_svg(best, theme=theme, title=title))
    print(f"{out}  —  {title}")
