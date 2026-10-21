"""Reference metrics for one board of the benchmark corpus (S1, alpha loop).

Reads a .kicad_pcb (and its .kicad_sch when present), runs kicad-cli for the
DRC report and the netlist, and writes reference_metrics.json next to them.
How each number is computed is written in the corpus METHOD.md; keep the two
in step.

    python -I scripts/alpha/corpus_metrics.py <board.kicad_pcb> <out_dir> [--sch <root.kicad_sch>]

The board files are third-party designs: they stay in the corpus folder outside
the repo. Only this script is committed.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
METHOD_VERSION = "1"

# ── s-expression reader ─────────────────────────────────────────────────────

_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse_sexpr(text: str):
    stack: list[list] = [[]]
    for m in _TOKEN.finditer(text):
        tok = m.group(0)
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif tok[0] == '"':
            stack[-1].append(tok[1:-1].replace('\\"', '"').replace("\\\\", "\\"))
        else:
            stack[-1].append(tok)
    return stack[0][0]


def children(node, name):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == name]


def child(node, name):
    found = children(node, name)
    return found[0] if found else None


def xy(node):
    return float(node[1]), float(node[2])


# ── geometry ────────────────────────────────────────────────────────────────


def rotate(x: float, y: float, deg: float) -> tuple[float, float]:
    """KiCad's RotatePoint: y axis down, positive angle counter-clockwise on screen."""
    if not deg:
        return x, y
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return x * c + y * s, -x * s + y * c


def arc_length(start, mid, end) -> float:
    (x1, y1), (x2, y2), (x3, y3) = start, mid, end
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-12:
        return math.dist(start, end)
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    r = math.dist((ux, uy), start)
    chord = math.dist(start, end)
    theta = 2 * math.asin(min(1.0, chord / (2 * r)))
    # the arc passes through mid: if mid is on the far side of the chord, it is the major arc
    cross = (x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)
    cross_c = (x3 - x1) * (uy - y1) - (y3 - y1) * (ux - x1)
    if cross * cross_c > 0:
        theta = 2 * math.pi - theta
    return r * theta


# ── board metrics ───────────────────────────────────────────────────────────

GROUND = re.compile(r"(^|[/_\-])(A|D|P|S)?GND\w*$|^(GND|VSS|0V|EARTH)\w*$|^/?(GND|VSS)", re.I)
IC_REF = re.compile(r"^(U|IC)\d+", re.I)
CAP_REF = re.compile(r"^C\d+", re.I)


def edge_points(board) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []

    def collect(item, origin=(0.0, 0.0, 0.0)):
        layer = child(item, "layer")
        if not layer or layer[1] != "Edge.Cuts":
            return
        ox, oy, orot = origin
        local: list[tuple[float, float]] = []
        kind = item[0].split("_", 1)[-1]
        if kind in ("line", "rect", "arc"):
            for k in ("start", "mid", "end"):
                n = child(item, k)
                if n:
                    local.append(xy(n))
            if kind == "rect" and len(local) == 2:
                (x1, y1), (x2, y2) = local
                local += [(x1, y2), (x2, y1)]
        elif kind == "circle":
            c, e = xy(child(item, "center")), xy(child(item, "end"))
            r = math.dist(c, e)
            local += [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
        elif kind == "poly":
            pts_node = child(item, "pts")
            local += [xy(p) for p in children(pts_node, "xy")] if pts_node else []
        for x, y in local:
            rx, ry = rotate(x, y, orot)
            pts.append((ox + rx, oy + ry))

    for item in board[1:]:
        if isinstance(item, list) and item and item[0].startswith("gr_"):
            collect(item)
    for fp in children(board, "footprint"):
        at = child(fp, "at")
        origin = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0)
        for item in fp[1:]:
            if isinstance(item, list) and item and item[0].startswith("fp_"):
                collect(item, origin)
    return pts


def footprint_ref(fp) -> str:
    for p in children(fp, "property"):
        if p[1] == "Reference":
            return p[2]
    t = [c for c in children(fp, "fp_text") if c[1] == "reference"]
    return t[0][2] if t else "?"


def footprint_pads(fp):
    at = child(fp, "at")
    fx, fy = float(at[1]), float(at[2])
    frot = float(at[3]) if len(at) > 3 else 0.0
    for pad in children(fp, "pad"):
        pat = child(pad, "at")
        px, py = float(pat[1]), float(pat[2])
        rx, ry = rotate(px, py, frot)
        net = child(pad, "net")
        net_name = None
        if net is not None:
            net_name = net[-1] if len(net) > 2 else net[1]
        yield {"number": pad[1], "type": pad[2], "x": fx + rx, "y": fy + ry, "net": net_name}


def board_metrics(pcb_path: Path) -> dict:
    board = parse_sexpr(pcb_path.read_text(encoding="utf-8"))

    layers = child(board, "layers")
    copper = [l[1] for l in layers[1:] if isinstance(l, list) and l[1].endswith(".Cu")]

    pts = edge_points(board)
    if pts:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        outline = {"bbox_w_mm": round(w, 3), "bbox_h_mm": round(h, 3), "bbox_area_mm2": round(w * h, 2)}
    else:
        outline = {"bbox_w_mm": None, "bbox_h_mm": None, "bbox_area_mm2": None, "note": "no Edge.Cuts"}

    length_by_layer: dict[str, float] = defaultdict(float)
    segs = 0
    for s in children(board, "segment"):
        length_by_layer[child(s, "layer")[1]] += math.dist(xy(child(s, "start")), xy(child(s, "end")))
        segs += 1
    for a in children(board, "arc"):
        length_by_layer[child(a, "layer")[1]] += arc_length(xy(child(a, "start")), xy(child(a, "mid")), xy(child(a, "end")))
        segs += 1
    vias = children(board, "via")
    via_kinds = Counter((v[1] if len(v) > 1 and isinstance(v[1], str) else "through") for v in vias)

    fps = children(board, "footprint")
    refs, bom_parts, smd, tht = [], 0, 0, 0
    pads_by_net: dict[str, list] = defaultdict(list)
    for fp in fps:
        ref = footprint_ref(fp)
        refs.append(ref)
        attr = child(fp, "attr")
        flags = set(attr[1:]) if attr else set()
        if not ref.startswith("#") and not ({"board_only", "exclude_from_bom"} & flags):
            bom_parts += 1
        if "smd" in flags:
            smd += 1
        elif "through_hole" in flags:
            tht += 1
        for pad in footprint_pads(fp):
            if pad["net"]:
                pads_by_net[pad["net"]].append((ref, pad))

    decoupling = []
    for fp in fps:
        ref = footprint_ref(fp)
        if not CAP_REF.match(ref):
            continue
        pads = [p for p in footprint_pads(fp) if p["net"]]
        nets = {p["net"] for p in pads}
        if len(pads) != 2 or not any(GROUND.search(n) for n in nets):
            continue
        rail = [n for n in nets if not GROUND.search(n)]
        if len(rail) != 1:
            continue
        rail = rail[0]
        cap_pad = next(p for p in pads if p["net"] == rail)
        best = None
        for other_ref, ipad in pads_by_net[rail]:
            if IC_REF.match(other_ref):
                d = math.dist((cap_pad["x"], cap_pad["y"]), (ipad["x"], ipad["y"]))
                if best is None or d < best[0]:
                    best = (d, other_ref, ipad["number"])
        if best:
            decoupling.append({"cap": ref, "net": rail, "ic": best[1], "ic_pad": best[2], "distance_mm": round(best[0], 3)})
    decoupling.sort(key=lambda d: d["cap"])
    dist = [d["distance_mm"] for d in decoupling]

    nets = [n for n in children(board, "net") if len(n) > 2 and n[2]]
    return {
        "copper_layers": len(copper),
        "copper_layer_names": copper,
        "outline": outline,
        "footprints": len(fps),
        "bom_parts": bom_parts,
        "smd_footprints": smd,
        "tht_footprints": tht,
        "nets_in_board": len(nets) if nets else len(pads_by_net),
        "pads_on_nets": sum(len(v) for v in pads_by_net.values()),
        "vias": {"count": len(vias), "by_kind": dict(via_kinds)},
        "tracks": {
            "segments_and_arcs": segs,
            "length_mm_total": round(sum(length_by_layer.values()), 2),
            "length_mm_by_layer": {k: round(v, 2) for k, v in sorted(length_by_layer.items())},
        },
        "decoupling": {
            "pairs": decoupling,
            "count": len(decoupling),
            "max_mm": max(dist) if dist else None,
            "median_mm": sorted(dist)[len(dist) // 2] if dist else None,
        },
    }


# ── kicad-cli ───────────────────────────────────────────────────────────────


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([KICAD_CLI, *args], capture_output=True, text=True, timeout=600)


def drc(pcb: Path, out_dir: Path, parity: bool) -> dict:
    report = out_dir / "drc.json"
    args = ["pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", str(report)]
    if parity:
        args.append("--schematic-parity")
    proc = run([*args, str(pcb)])
    if not report.exists():
        return {"error": (proc.stderr or proc.stdout)[-500:]}
    data = json.loads(report.read_text(encoding="utf-8"))
    by_type: Counter = Counter()
    by_sev: Counter = Counter()
    for v in data.get("violations", []):
        by_type[v["type"]] += 1
        by_sev[v["severity"]] += 1
    parity_items = data.get("schematic_parity", [])
    return {
        "kicad_version": data.get("kicad_version"),
        "schematic_parity_checked": parity,
        "violations_total": sum(by_type.values()),
        "violations_by_severity": dict(by_sev),
        "violations_by_type": dict(by_type.most_common()),
        "unconnected_items": len(data.get("unconnected_items", [])),
        "schematic_parity_items": len(parity_items),
        "schematic_parity_by_type": dict(Counter(p["type"] for p in parity_items).most_common()),
        "report": report.name,
    }


def netlist(sch: Path | None, out_dir: Path, shipped: Path | None = None) -> dict:
    """Export the netlist from the schematic, or take the one the design ships
    (legacy KiCad 5 schematics, which kicad-cli 10 cannot read)."""
    out = out_dir / "reference.net"
    if shipped is not None:
        out.write_text(shipped.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        source = f"shipped by the design: {shipped.name}"
    else:
        proc = run(["sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(sch)])
        if not out.exists():
            return {"error": (proc.stderr or proc.stdout)[-500:]}
        source = f"kicad-cli sch export netlist: {sch.name}"
    tree = parse_sexpr(out.read_text(encoding="utf-8"))
    comps = child(tree, "components")
    nets = child(tree, "nets")
    net_list = children(nets, "net") if nets else []
    sizes = [len(children(n, "node")) for n in net_list]
    return {
        "file": out.name,
        "source": source,
        "components": len(children(comps, "comp")) if comps else 0,
        "nets": len(net_list),
        "nets_with_2plus_nodes": sum(1 for s in sizes if s >= 2),
        "nodes": sum(sizes),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pcb", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--sch", type=Path)
    ap.add_argument("--net", type=Path, help="use this shipped netlist instead of exporting one")
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    sch = a.sch or a.pcb.with_suffix(".kicad_sch")
    metrics = {
        "method_version": METHOD_VERSION,
        "board_file": a.pcb.name,
        "board": board_metrics(a.pcb),
        "drc": drc(a.pcb, a.out_dir, parity=sch.exists()),
        "netlist": (netlist(None, a.out_dir, a.net) if a.net
                    else netlist(sch, a.out_dir) if sch.exists() else {"error": "no schematic"}),
    }
    (a.out_dir / "reference_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    b = metrics["board"]
    print(json.dumps({
        "board": a.pcb.name, "layers": b["copper_layers"], "parts": b["bom_parts"],
        "area_mm2": b["outline"]["bbox_area_mm2"], "vias": b["vias"]["count"],
        "track_mm": b["tracks"]["length_mm_total"], "decap_max_mm": b["decoupling"]["max_mm"],
        "drc": metrics["drc"].get("violations_total"), "unrouted": metrics["drc"].get("unconnected_items"),
        "parity": metrics["drc"].get("schematic_parity_items"), "net_nets": metrics["netlist"].get("nets"),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
