"""
compile_board.py — netlist in, PCB out. This is the connection.

    netlist JSON  ->  footprints  ->  placement  ->  routing  ->  SVG + report

Everything upstream of this file was engine parts. This is the pipe. Circuit OS
already has the netlist — it drew the schematic from one — so the only thing it
has to do is POST that JSON here and render the SVG that comes back.

    python compile_board.py netlist_dht22.json
    python compile_board.py netlist_dht22.json --serve 8000

WHY THE PLACER HERE IS GREEDY AND NOT THE GRADIENT ONE
------------------------------------------------------
`placer.py` implements the DREAMPlace objective and it measurably made routing
worse: wirelength fell 46%, routing completion fell by two thirds, because
minimising wirelength without a proper density solve packs everything into a
clump with no channels left. Rather than ship that, this pipeline uses
constructive placement: seed with the largest package, then insert each
remaining part at the legal position that minimises added wirelength.

It is a worse algorithm and a better result, which is the honest trade for now.
`placer.py` stays in the tree for when the density term is done properly; the
swap is one line in `place_constructive`.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field

from board_ir import Board, Layer, NetClass
import footprints
from kernel import drc, score
from router import AStarRouter, generate_candidates
from render_pretty import to_svg
from scene3d import board_scene
from verify import verify_board, unrouted_connections


# ─────────────────────────────────────────────────────────────────────────────
# 1. netlist -> Board IR with real footprints
# ─────────────────────────────────────────────────────────────────────────────
def from_netlist(nl: dict) -> tuple[Board, list[str]]:
    """Returns (board, warnings). Unknown packages are reported, not guessed."""
    warn: list[str] = []
    bd = nl.get("board", {})
    ground = nl.get("ground_net", "GND")

    b = Board(name=nl.get("name", "board"),
              outline_w=bd.get("width", 60.0),
              outline_h=bd.get("height", 45.0),
              layers=[Layer("F.Cu", "signal"),
                      Layer("B.Cu", "signal", plane_net=ground)])

    for c in nl["components"]:
        ref, mpn = c["ref"], c.get("mpn", "")
        pins = {str(k): v for k, v in c.get("pins", {}).items()}
        
        raw_pkg = c.get("package")
        pkg = footprints.normalize_package(raw_pkg) if raw_pkg else None
        specific = footprints.guess(mpn)
        if specific in footprints.PART_SPECIFIC:
            pkg = specific
        pkg = pkg or footprints.guess(mpn, len(pins))
        
        if not pkg:
            warn.append(f"{ref} ({mpn}): no footprint known — skipped. "
                        f"Supply \"package\" explicitly.")
            continue
        try:
            comp = footprints.build(ref, pkg, pins, warnings=warn, mpn=mpn)
        except KeyError as e:
            warn.append(f"{ref}: {e}")
            continue
        # What the part is, carried on the IR so every consumer (3D scene, a
        # later KiCad export) reads one answer instead of re-guessing it.
        # The pin labels too: IV.2 compares a label's function with the part's
        # datasheet, and a board verified without its netlist has only these.
        comp.attrs.update({k: v for k, v in (("package", pkg), ("mpn", mpn),
                                             ("type", c.get("type")),
                                             ("value", c.get("value")),
                                             ("pins", dict(pins))) if v})
        b.components.append(comp)

    power = [n for n in nl.get("power_nets", [ground]) if n]
    signal = [n for n in b.nets() if n not in power]
    b.net_classes = [
        NetClass("default", signal, track_width=0.3, clearance=0.25),
        NetClass("power", power, track_width=0.8, clearance=0.3, priority=10),
    ]
    return b, warn


# ─────────────────────────────────────────────────────────────────────────────
# 2. constructive placement
# ─────────────────────────────────────────────────────────────────────────────
def _legal(b: Board, i: int, x: float, y: float, margin: float) -> bool:
    c = b.components[i]
    if not (margin + c.courtyard_w / 2 <= x <= b.outline_w - margin - c.courtyard_w / 2):
        return False
    if not (margin + c.courtyard_h / 2 <= y <= b.outline_h - margin - c.courtyard_h / 2):
        return False
    for j, o in enumerate(b.components):
        if j == i or not getattr(o, "_placed", False):
            continue
        if (abs(x - o.x) < (c.courtyard_w + o.courtyard_w) / 2 + 0.4 and
                abs(y - o.y) < (c.courtyard_h + o.courtyard_h) / 2 + 0.4):
            return False
    return True


def _added_wirelength(b: Board, i: int, x: float, y: float) -> float:
    """How much bounding-box wirelength putting component i here would add,
    counting only nets that already touch something placed."""
    c = b.components[i]
    total = 0.0
    placed_pins: dict[str, list[tuple[float, float]]] = {}
    for j, o in enumerate(b.components):
        if j == i or not getattr(o, "_placed", False):
            continue
        for p in o.pads:
            if p.net:
                placed_pins.setdefault(p.net, []).append((p.x, p.y))
    for p in c.pads:
        pts = placed_pins.get(p.net)
        if not pts:
            continue
        px, py = x + (p.x - c.x), y + (p.y - c.y)
        total += min(abs(px - qx) + abs(py - qy) for qx, qy in pts)
    return total


def _decoupling(b: Board) -> dict[int, tuple[int, str]]:
    """Which capacitor decouples which IC supply pad: cap index -> (IC index,
    pad pin).

    A decoupling cap is a two-pad capacitor between one rail and ground. It
    serves the largest part (six pads or more) with a pad on that rail, at the
    first of that part's rail pads no earlier cap took — so two caps on an
    ATmega go to VCC and AVCC, not both to whichever is nearer. A cap between
    two signals (an RC filter's) is not one and is placed by wirelength."""
    grounds = b.plane_nets() or {"GND"}
    ics = sorted((j for j, c in enumerate(b.components) if len(c.pads) >= 6),
                 key=lambda j: -len(b.components[j].pads))
    taken: dict[tuple[int, str], int] = {}
    out: dict[int, tuple[int, str]] = {}
    for i, c in enumerate(b.components):
        nets = {p.net for p in c.pads}
        if c.attrs.get("type") != "capacitor" or len(c.pads) != 2 or len(nets) != 2:
            continue
        rails = [n for n in nets if n and n not in grounds]
        if len(rails) != 1 or not (nets - set(rails)) <= grounds:
            continue
        for j in ics:
            pins = sorted((p.pin for p in b.components[j].pads if p.net == rails[0]),
                          key=lambda s: (len(s), s))
            if pins:
                pin = min(pins, key=lambda s: taken.get((j, s), 0))
                taken[(j, pin)] = taken.get((j, pin), 0) + 1
                out[i] = (j, pin)
                break
    return out


def _beside(b: Board, i: int, target: tuple[int, str], margin: float,
            reach: float = 6.0, fine: float = 0.25) -> tuple[float, float] | None:
    """The legal position and turn (0 or 180 degrees), on a `fine` grid within
    `reach` mm of the supply pad, that puts cap i's rail pad nearest it; ties
    go to less wirelength. The half turn lets the rail pad face the pin instead
    of its ground pad. None when nothing within reach is legal (the caller
    falls back to wirelength)."""
    c = b.components[i]
    j, pin = target
    pad = next(p for p in b.components[j].pads if p.pin == pin)
    rail = next(p for p in c.pads if p.net == pad.net)
    best, best_cost = None, (float("inf"), float("inf"))
    n = int(reach / fine)
    for turn in (0, 180):
        _turn(c, turn)
        ox, oy = rail.x - c.x, rail.y - c.y
        for dy in range(-n, n + 1):
            for dx in range(-n, n + 1):
                # where the part's centre goes so that its rail pad lands here
                x = round(pad.x + dx * fine - ox, 4)
                y = round(pad.y + dy * fine - oy, 4)
                d = math.hypot(dx * fine, dy * fine)
                if d > reach or not _legal(b, i, x, y, margin):
                    continue
                cost = (round(d, 6), _added_wirelength(b, i, x, y))
                if cost < best_cost:
                    best, best_cost = (x, y, turn), cost
        _turn(c, -turn)
    return best


def _turn(c, degrees: int) -> None:
    """Turn a part by a half turn (or back) about its centre, pads with it."""
    if degrees % 360 == 0:
        return
    for p in c.pads:
        p.x, p.y = 2 * c.x - p.x, 2 * c.y - p.y
    c.rotation = (c.rotation + degrees) % 360


def place_constructive(b: Board, margin: float = 2.5, step: float = 1.27) -> Board:
    """Seed with the largest package, then insert each part at the legal grid
    position that adds the least wirelength.

    Greedy and unglamorous, but every intermediate state is legal by
    construction, so it cannot produce the dense unroutable clump that
    wirelength-only gradient descent converges to.

    A decoupling cap is the exception (F-S2-R001-6). Wirelength put a 100 nF
    cap next to whichever rail pad was nearest — 5 mm from the ATmega's AVCC,
    11 mm from its VCC, where the reference board has 1.65 mm. Each one is now
    placed right after its IC, on a fine grid around the supply pad it serves,
    at the legal spot nearest that pad."""
    decap = _decoupling(b)
    by_size = sorted((i for i in range(len(b.components)) if i not in decap),
                     key=lambda i: -len(b.components[i].pads))
    order = []
    for i in by_size:
        order.append(i)
        order += [k for k, (j, _) in sorted(decap.items()) if j == i]
    if not order:
        return b

    def move(i, x, y):
        c = b.components[i]
        dx, dy = x - c.x, y - c.y
        c.x, c.y = x, y
        for p in c.pads:
            p.x += dx; p.y += dy
        c._placed = True

    first = order[0]
    move(first, b.outline_w * 0.32, b.outline_h / 2)

    xs = [margin + k * step for k in range(int((b.outline_w - 2 * margin) / step) + 1)]
    ys = [margin + k * step for k in range(int((b.outline_h - 2 * margin) / step) + 1)]

    for i in order[1:]:
        best, best_cost = None, float("inf")
        if i in decap:
            spot = _beside(b, i, decap[i], margin)
            if spot:
                _turn(b.components[i], spot[2])
                move(i, spot[0], spot[1])
                continue
        for x in xs:
            for y in ys:
                if not _legal(b, i, x, y, margin):
                    continue
                cost = _added_wirelength(b, i, x, y)
                if cost < best_cost:
                    best, best_cost = (x, y), cost
        if best:
            move(i, *best)
        else:
            b.components[i]._placed = True      # nowhere legal; leave it put
    for c in b.components:
        if hasattr(c, "_placed"):
            del c._placed
    return b


# ─────────────────────────────────────────────────────────────────────────────
# 3. the compiler
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Result:
    board: Board
    svg: str
    stats: dict
    warnings: list[str]
    violations: list[str]
    # The independent verification report (verify.py). Empty until compile_board
    # fills it; a caller constructing a Result by hand gets the old behaviour.
    verification: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """False when a decidable check failed — the board should not ship."""
        return self.verification.get("ok", True)

    def to_dict(self) -> dict:
        return {"stats": self.stats, "warnings": self.warnings,
                "violations": self.violations, "svg": self.svg,
                "verification": self.verification,
                "board": json.loads(self.board.to_json(indent=None)),
                "scene": board_scene(self.board)}


def compile_board(netlist: dict, candidates: int = 4, theme: str = "green",
                  grid: float = 0.2) -> Result:
    b, warn = from_netlist(netlist)
    b = place_constructive(b)

    n = len(b.required_connections())
    if n:
        best = generate_candidates(b, AStarRouter(res=grid), n=candidates)[0]
        b, s = best.board, best.score
    else:
        s = score(b)

    vs = drc(b)
    # The completion count is the independent judge's, not the router's own.
    # `router_unrouted` is the router's (kernel.open_connections), kept visible
    # beside it: two implementations of one question, so any disagreement is a
    # bug in one of them. Until 2026-10-17 the router matched quantisation cells
    # and reported 4 of 12 open on the shipped board where the judge found 0.
    judge = unrouted_connections(b)
    rep = verify_board(b, netlist)
    stats = {
        "name": b.name,
        "size_mm": [b.outline_w, b.outline_h],
        "components": len(b.components),
        "pads": len(b.pads()),
        "nets": len(b.nets()),
        "connections": n,
        "routed": n - len(judge),
        "unrouted": len(judge),
        "router_unrouted": s.unrouted,
        "drc_errors": s.errors,
        "vias": s.vias,
        "copper_mm": round(s.length_mm, 1),
        "verified": rep.ok,
        "proven": rep.proven,
        "failed_checks": [f.check for f in rep.failed()],
    }
    title = (f"{b.name}   {stats['routed']}/{n} routed   "
             f"{s.errors} DRC errors   {s.vias} vias   {s.length_mm:.0f} mm")
    return Result(b, to_svg(b, scale=22.0, theme=theme, title=title),
                  stats, warn, [str(v) for v in vs[:20]],
                  verification=rep.to_dict())


# ─────────────────────────────────────────────────────────────────────────────
# 4. HTTP endpoint — what Circuit OS actually calls
# ─────────────────────────────────────────────────────────────────────────────
def serve(port: int = 8000):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                nl = json.loads(self.rfile.read(n) or b"{}")
                out = compile_board(nl).to_dict()
                code = 200
            except Exception as e:                       # noqa: BLE001
                out, code = {"error": f"{type(e).__name__}: {e}"}, 400
            body = json.dumps(out).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, *a):
            pass

    print(f"POST a netlist to http://localhost:{port}/  -> {{svg, stats, warnings}}")
    HTTPServer(("", port), H).serve_forever()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--serve" in args:
        serve(int(args[args.index("--serve") + 1]))
        sys.exit()

    path = args[0] if args else "netlist_dht22.json"
    netlist = json.load(open(path))
    r = compile_board(netlist)

    print(json.dumps(r.stats, indent=2))
    for w in r.warnings:
        print("  warning:", w)
    for v in r.violations[:5]:
        print("  ", v)

    out = netlist.get("name", "board")
    open(f"{out}.svg", "w").write(r.svg)
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=r.svg.encode(), write_to=f"{out}.png")
    except ImportError:
        pass
    print(f"\n-> {out}.svg")
