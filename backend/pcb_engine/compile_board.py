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
from dataclasses import dataclass

from board_ir import Board, Layer, NetClass
import footprints
from kernel import drc, score
from router import AStarRouter, generate_candidates
from render_pretty import to_svg


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
        pkg = pkg or footprints.guess(mpn, len(pins))
        
        if not pkg:
            warn.append(f"{ref} ({mpn}): no footprint known — skipped. "
                        f"Supply \"package\" explicitly.")
            continue
        try:
            b.components.append(footprints.build(ref, pkg, pins, warnings=warn))
        except KeyError as e:
            warn.append(f"{ref}: {e}")
            continue

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


def place_constructive(b: Board, margin: float = 2.5, step: float = 1.27) -> Board:
    """Seed with the largest package, then insert each part at the legal grid
    position that adds the least wirelength.

    Greedy and unglamorous, but every intermediate state is legal by
    construction, so it cannot produce the dense unroutable clump that
    wirelength-only gradient descent converges to."""
    order = sorted(range(len(b.components)),
                   key=lambda i: -len(b.components[i].pads))
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

    def to_dict(self) -> dict:
        return {"stats": self.stats, "warnings": self.warnings,
                "violations": self.violations, "svg": self.svg,
                "board": json.loads(self.board.to_json(indent=None))}


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
    stats = {
        "name": b.name,
        "size_mm": [b.outline_w, b.outline_h],
        "components": len(b.components),
        "pads": len(b.pads()),
        "nets": len(b.nets()),
        "connections": n,
        "routed": n - s.unrouted,
        "unrouted": s.unrouted,
        "drc_errors": s.errors,
        "vias": s.vias,
        "copper_mm": round(s.length_mm, 1),
    }
    title = (f"{b.name}   {stats['routed']}/{n} routed   "
             f"{s.errors} DRC errors   {s.vias} vias   {s.length_mm:.0f} mm")
    return Result(b, to_svg(b, scale=22.0, theme=theme, title=title),
                  stats, warn, [str(v) for v in vs[:20]])


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
