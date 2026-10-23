"""
gerber_readback.py — read the fab files back into copper and compare with the IR.

Stage 7 of `reports/PCB verification implementation plan.md`. Runs in its OWN
Python 3.12 interpreter (Gerbonara does not install on 3.11; owner decision
2026-10-17), and imports nothing from the backend: the only thing it shares with
the code that made the board is the pad table it is handed. That distance is
the point — it judges the files a fab would receive, not the board model.

    python -I gerber_readback.py <fab_dir> <pads.json>     -> JSON on stdout

pads.json, in the files' frame (mm):
    {"copper": ["F.Cu", "B.Cu"], "min_ring": 0.05,
     "pads": [{"ref", "pin", "net", "x", "y", "layers": [...], "through": bool}],
     "vias": [{"net", "x", "y"}]}

Method (ported from the prototype `lvs.py`, which caught 4 of 4 seeded defects
on KiCad's pic_programmer demo): every dark object of each copper Gerber becomes
a Shapely polygon; each layer is unioned into islands; a plated hole joins the
islands it passes through on every layer; then every pad of the IR is placed in
an island. A net spread over more than one island group is an OPEN; a group
holding more than one net is a SHORT.

The guards the plan lists before this stage may carry more than evidence:
  * plating is taken from each drill file's X2 header, never assumed;
  * a plated hole joins only the island its centre lies in, and only if a ring
    of at least `min_ring` remains all round; a second island inside the hole's
    disc is reported as breakout;
  * non-plated holes are cut out of the copper and never join layers;
  * clear-polarity objects are applied in file order;
  * copper is clipped to the board outline, and copper outside it is reported;
  * arcs are flattened with a bounded chord error (CHORD_TOL);
  * the number of plated hits must equal the IR's plated pads plus vias (the
    guard against a drill file that silently imports nothing).
The X2 pad labels KiCad writes (.P ref/pin, .N net) are a second label set:
they check the writer and are compared with the IR, never keyed on.

Near-misses (tangent contact, grazing drills, gaps under 10 µm) are where a
geometric extractor is most likely wrong; contact is decided by Shapely's
exact predicates on the flattened geometry, so a gap below CHORD_TOL is not
resolved and is stated as such in the output.
"""
from __future__ import annotations

import collections
import glob
import json
import math
import os
import sys
import time
import warnings

warnings.simplefilter("ignore")

from gerbonara import ExcellonFile, GerberFile          # noqa: E402
from gerbonara.utils import MM                           # noqa: E402
import gerbonara.graphic_primitives as gp                # noqa: E402
from shapely import STRtree                              # noqa: E402
from shapely.geometry import LineString, Point, Polygon  # noqa: E402
from shapely.ops import polygonize, unary_union          # noqa: E402

CHORD_TOL = 0.002          # mm, maximum distance of a flattened arc from the true arc
AREA_EPS = 1e-6            # mm², below this an area is numerical noise


def _segs(r: float) -> int:
    """Quadrant segments so a circle of radius r stays within CHORD_TOL."""
    if r <= CHORD_TOL:
        return 4
    return max(4, math.ceil((math.pi / 2) / (2 * math.acos(1 - CHORD_TOL / r))))


def _arc_points(x1, y1, x2, y2, cx, cy, clockwise):
    r1, r2 = math.hypot(x1 - cx, y1 - cy), math.hypot(x2 - cx, y2 - cy)
    if abs(r1 - r2) > 1e-3:
        raise ValueError(f"arc radii disagree ({r1:.4f} vs {r2:.4f})")
    a1, a2 = math.atan2(y1 - cy, x1 - cx), math.atan2(y2 - cy, x2 - cx)
    sweep = a2 - a1
    if clockwise and sweep >= 0:
        sweep -= 2 * math.pi
    if not clockwise and sweep <= 0:
        sweep += 2 * math.pi
    step = 2 * math.acos(1 - CHORD_TOL / r1) if r1 > CHORD_TOL else math.pi / 4
    n = max(2, math.ceil(abs(sweep) / step))
    return [(cx + r1 * math.cos(a1 + sweep * i / n), cy + r1 * math.sin(a1 + sweep * i / n))
            for i in range(n + 1)]


def prim_geom(p):
    if isinstance(p, gp.Line):
        if p.x1 == p.x2 and p.y1 == p.y2:
            return Point(p.x1, p.y1).buffer(p.width / 2, _segs(p.width / 2))
        return LineString([(p.x1, p.y1), (p.x2, p.y2)]).buffer(p.width / 2, _segs(p.width / 2))
    if isinstance(p, gp.Circle):
        return Point(p.x, p.y).buffer(p.r, _segs(p.r))
    if isinstance(p, gp.Arc):
        pts = _arc_points(p.x1, p.y1, p.x2, p.y2, p.cx, p.cy, p.clockwise)   # centre absolute
        return LineString(pts).buffer(p.width / 2, _segs(p.width / 2))
    if not isinstance(p, gp.ArcPoly):
        p = p.to_arc_poly()
    if any(c is not None for c in p.arc_centers):
        p = p.approximate_arcs(CHORD_TOL)
    g = Polygon(p.outline)
    return g if g.is_valid else g.buffer(0)


def _one(fab: str, pattern: str) -> str | None:
    hits = sorted(glob.glob(os.path.join(fab, pattern)))
    return hits[0] if hits else None


def outline_polygon(path: str):
    g = GerberFile.open(path)
    lines = []
    for o in g.objects:
        for p in o.to_primitives(unit=MM):
            if isinstance(p, gp.Line):
                lines.append(LineString([(p.x1, p.y1), (p.x2, p.y2)]))
            elif isinstance(p, gp.Arc):
                lines.append(LineString(_arc_points(p.x1, p.y1, p.x2, p.y2, p.cx, p.cy, p.clockwise)))
    polys = list(polygonize(unary_union(lines)))
    return max(polys, key=lambda q: q.area) if polys else None


def copper_layer(path: str, npth, outline, problems: list, name: str):
    """Islands of one copper Gerber, polarity applied in file order, NPTH cut,
    clipped to the outline. Also the X2 pad labels it carries."""
    g = GerberFile.open(path)
    acc, run, run_dark, labels = None, [], True, []

    def flush():
        nonlocal acc, run
        if not run:
            return
        u = unary_union(run)
        acc = u if acc is None else (acc.union(u) if run_dark else acc.difference(u))
        run = []

    for o in g.objects:
        a = o.attrs if isinstance(o.attrs, dict) else {}
        if type(o).__name__ == "Flash" and ".P" in a:
            net = a[".N"][0] if a.get(".N") else ""
            net = "" if net == "N/C" else net      # KiCad's label for a pad on no net
            labels.append({"x": o.converted(MM).x if hasattr(o, "converted") else o.x,
                           "y": o.converted(MM).y if hasattr(o, "converted") else o.y,
                           "ref": a[".P"][0], "pin": a[".P"][1] if len(a[".P"]) > 1 else "",
                           "net": net})
        for p in o.to_primitives(unit=MM):
            if p.polarity_dark != run_dark:
                flush()
                run_dark = p.polarity_dark
            if acc is None and not run_dark:
                continue                       # clear on nothing clears nothing
            run.append(prim_geom(p))
    flush()
    copper = acc if acc is not None else Polygon()
    if npth is not None and not npth.is_empty:
        copper = copper.difference(npth)
    if outline is not None:
        outside = copper.difference(outline)
        if outside.area > AREA_EPS:
            c = outside.centroid
            problems.append({"kind": "outside_outline", "layer": name,
                             "area_mm2": round(outside.area, 4),
                             "at": [round(c.x, 3), round(c.y, 3)]})
        copper = copper.intersection(outline)
    islands = [q for q in (list(copper.geoms) if hasattr(copper, "geoms") else [copper])
               if q.area > AREA_EPS]
    return islands, labels


def drill_hits(path: str):
    e = ExcellonFile.open(path)
    out = []
    for o in e.objects:
        o = o.converted(MM)
        kind = type(o).__name__
        if kind == "Flash":
            r = o.aperture.diameter / 2
            out.append({"x": o.x, "y": o.y, "r": r, "geom": Point(o.x, o.y).buffer(r, _segs(r))})
        elif kind == "Line":                    # a routed slot
            r = o.aperture.diameter / 2
            out.append({"x": (o.x1 + o.x2) / 2, "y": (o.y1 + o.y2) / 2, "r": r,
                        "geom": LineString([(o.x1, o.y1), (o.x2, o.y2)]).buffer(r, _segs(r))})
        else:
            raise ValueError(f"drill object {kind} not understood")
    return out


def plating_of(path: str) -> str:
    text = open(path, encoding="utf-8", errors="replace").read(4000)
    if "TF.FileFunction,NonPlated" in text:
        return "nonplated"
    if "TF.FileFunction,Plated" in text:
        return "plated"
    return "unknown"


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def readback(fab: str, spec: dict) -> dict:
    t0 = time.time()
    problems: list[dict] = []
    copper_names = spec["copper"]
    min_ring = float(spec.get("min_ring", 0.05))

    edge = _one(fab, "*-Edge_Cuts.gm1")
    outline = outline_polygon(edge) if edge else None
    if outline is None:
        problems.append({"kind": "no_outline", "detail": "no closed board outline in the Edge.Cuts Gerber"})

    pth_path, npth_path = _one(fab, "*-PTH.drl"), _one(fab, "*-NPTH.drl")
    pth, npth = [], []
    if pth_path is None:
        problems.append({"kind": "plating", "detail": "no plated drill file"})
    else:
        if plating_of(pth_path) != "plated":
            problems.append({"kind": "plating", "detail": f"{os.path.basename(pth_path)} header "
                                                          f"does not declare plated holes"})
        pth = drill_hits(pth_path)
    if npth_path is not None:
        npth = drill_hits(npth_path)
        if npth and plating_of(npth_path) != "nonplated":
            problems.append({"kind": "plating", "detail": f"{os.path.basename(npth_path)} header "
                                                          f"does not declare non-plated holes"})
    npth_geom = unary_union([h["geom"] for h in npth]) if npth else None

    layers, trees, x2 = {}, {}, []
    for name in copper_names:
        path = _one(fab, f"*-{name.replace('.', '_')}.g*")
        if path is None:
            problems.append({"kind": "missing_layer", "layer": name})
            layers[name], trees[name] = [], STRtree([])
            continue
        islands, labels = copper_layer(path, npth_geom, outline, problems, name)
        layers[name], trees[name] = islands, STRtree(islands)
        for lab in labels:
            lab["layer"] = name
        x2 += labels

    def at_point(layer, x, y):
        return [int(i) for i in trees[layer].query(Point(x, y), predicate="intersects")]

    uf = UF()
    # plated holes: join the island the centre is in, if a ring remains all round
    want_hits = sum(1 for p in spec["pads"] if p["through"]) + len(spec.get("vias", []))
    if len(pth) != want_hits:
        problems.append({"kind": "hit_count", "detail": f"plated drill file has {len(pth)} hits, "
                                                        f"the IR has {want_hits} plated pads and vias"})
    for h in pth:
        joined = []
        for name in copper_names:
            centre = at_point(name, h["x"], h["y"])
            disc = h["geom"]
            inside = [int(i) for i in trees[name].query(disc, predicate="intersects")]
            for i in inside:
                if i not in centre:
                    problems.append({"kind": "breakout", "layer": name,
                                     "at": [round(h["x"], 3), round(h["y"], 3)],
                                     "detail": "a second copper island lies inside the hole"})
            for i in centre:
                ring = Point(h["x"], h["y"]).buffer(h["r"] + min_ring, _segs(h["r"] + min_ring))
                if layers[name][i].contains(ring):
                    joined.append((name, i))
                else:
                    problems.append({"kind": "breakout", "layer": name,
                                     "at": [round(h["x"], 3), round(h["y"], 3)],
                                     "detail": f"less than {min_ring} mm of copper rings the hole"})
        if not joined:
            problems.append({"kind": "hole_off_copper", "at": [round(h["x"], 3), round(h["y"], 3)]})
        for k in joined[1:]:
            uf.union(joined[0], k)

    # place every IR pad and via
    net_groups, group_nets = collections.defaultdict(set), collections.defaultdict(set)
    items = [dict(p, kind="pad") for p in spec["pads"]] + \
            [dict(v, kind="via", layers=[copper_names[0], copper_names[-1]], ref="via", pin="")
             for v in spec.get("vias", [])]
    for it in items:
        roots = []
        for name in it["layers"]:
            hits = at_point(name, it["x"], it["y"])
            if not hits:
                problems.append({"kind": "off_copper", "layer": name, "ref": it["ref"],
                                 "pin": it["pin"], "net": it["net"],
                                 "at": [round(it["x"], 3), round(it["y"], 3)]})
            roots += [uf.find((name, i)) for i in hits]
        if not it["net"]:
            continue
        for r in roots:
            net_groups[it["net"]].add(r)
            group_nets[r].add(it["net"])
    opens = {n: len(g) for n, g in sorted(net_groups.items()) if len(g) > 1}
    shorts = sorted({tuple(sorted(n)) for n in group_nets.values() if len(n) > 1})

    # the second label set: KiCad's X2 pad attributes against the IR
    ir_net = {(p["ref"], p["pin"]): p["net"] for p in spec["pads"]}
    seen = set()
    for lab in x2:
        key = (lab["ref"], lab["pin"])
        seen.add(key)
        if key not in ir_net:
            problems.append({"kind": "label", "detail": f"Gerber pad {key} is not in the IR"})
        elif ir_net[key] != lab["net"]:
            problems.append({"kind": "label", "ref": key[0], "pin": key[1],
                             "detail": f"Gerber labels net {lab['net']!r}, IR has {ir_net[key]!r}"})
    for key in ir_net:
        if key not in seen:
            problems.append({"kind": "label", "ref": key[0], "pin": key[1],
                             "detail": "no Gerber pad label for this IR pad"})

    for n, k in opens.items():
        problems.append({"kind": "open", "net": n, "groups": k})
    for s in shorts:
        problems.append({"kind": "short", "nets": list(s)})
    return {"engine": "gerber_readback (gerbonara + shapely)",
            "python": sys.version.split()[0],
            "ok": not problems, "opens": opens, "shorts": [list(s) for s in shorts],
            "problems": problems,
            "islands": {n: len(v) for n, v in layers.items()},
            "plated_hits": len(pth), "nonplated_hits": len(npth),
            "x2_labels": len(x2), "chord_tol_mm": CHORD_TOL, "min_ring_mm": min_ring,
            "unresolved": f"gaps below {CHORD_TOL} mm are not resolved",
            "time_s": round(time.time() - t0, 3)}


if __name__ == "__main__":
    fab_dir, spec_path = sys.argv[1], sys.argv[2]
    try:
        out = readback(fab_dir, json.load(open(spec_path, encoding="utf-8")))
    except Exception as e:                                   # noqa: BLE001
        out = {"ok": False, "error": f"{type(e).__name__}: {e}",
               "problems": [{"kind": "readback_failed", "detail": f"{type(e).__name__}: {e}"}]}
    json.dump(out, sys.stdout)
