"""Black-box geometry/connectivity analysis of an emitted .kicad_pcb.

Rebuilds the copper graph per net from the file text and reports:
  * connected copper groups per net (opens)
  * copper of two different nets overlapping (shorts)
  * zone fill state
No product source is read; only the emitted board file.
"""
import math
import re
import sys
from collections import defaultdict

PATH = sys.argv[1]
txt = open(PATH, encoding="utf-8").read()

def parse(s):
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', s)
    stack, cur = [], []
    for t in toks:
        if t == "(":
            new = []
            cur.append(new)
            stack.append(cur)
            cur = new
        elif t == ")":
            cur = stack.pop()
        else:
            if t.startswith('"'):
                t = t[1:-1].replace('\\"', '"')
            cur.append(t)
    return cur[0]

root = parse(txt)

def kids(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]

def first(node, name):
    k = kids(node, name)
    return k[0] if k else None

def rot(x, y, ang):
    a = math.radians(ang)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)

pads, vias, segs, zones, fps = [], [], [], [], []

for fp in kids(root, "footprint"):
    ref = val = None
    for p in kids(fp, "property"):
        if p[1] == "Reference":
            ref = p[2]
        if p[1] == "Value":
            val = p[2]
    at = first(fp, "at")
    fx, fy = float(at[1]), float(at[2])
    fang = float(at[3]) if len(at) > 3 else 0.0
    fps.append((ref, val, fp))
    for pad in kids(fp, "pad"):
        pat = first(pad, "at")
        px, py = float(pat[1]), float(pat[2])
        dx, dy = rot(px, py, fang)
        size = first(pad, "size")
        n = first(pad, "net")
        lay = first(pad, "layers")[1:]
        pads.append(dict(ref=ref, num=pad[1], x=fx + dx, y=fy + dy,
                         net=(n[1] if n else ""),
                         w=float(size[1]), h=float(size[2]),
                         r=max(float(size[1]), float(size[2])) / 2.0,
                         type=("SMD" if pad[1] == "smd" else "TH"), layers=lay,
                         drill=(float(first(pad, "drill")[1]) if first(pad, "drill") else 0.0),
                         fp=(fx, fy)))

for s in kids(root, "segment"):
    st, en = first(s, "start"), first(s, "end")
    n = first(s, "net")
    segs.append(dict(net=(n[1] if n else ""), layer=first(s, "layer")[1],
                      w=float(first(s, "width")[1]),
                      p1=(float(st[1]), float(st[2])), p2=(float(en[1]), float(en[2]))))

for v in kids(root, "via"):
    at = first(v, "at")
    n = first(v, "net")
    vias.append(dict(net=(n[1] if n else ""), x=float(at[1]), y=float(at[2]),
                     r=float(first(v, "size")[1]) / 2.0,
                     drill=float(first(v, "drill")[1])))

for z in kids(root, "zone"):
    n = first(z, "net")
    pts, fpts = [], []
    poly = first(z, "polygon")
    if poly:
        p = first(poly, "pts")
        if p:
            pts = [(float(q[1]), float(q[2])) for q in kids(p, "xy")]
    for fp_ in kids(z, "filled_polygon"):
        p = first(fp_, "pts")
        if p:
            fpts = [(float(q[1]), float(q[2])) for q in kids(p, "xy")]
    zones.append(dict(net=(n[1] if n else ""), layer=first(z, "layer")[1],
                      outline=pts, filled_pts=fpts))

def pt_seg(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def seg_seg(p1, p2, q1, q2):
    return min(pt_seg(p1, q1, q2), pt_seg(p2, q1, q2),
               pt_seg(q1, p1, p2), pt_seg(q2, p1, p2))

class Item:
    def __init__(self, kind, net, key, pts, r, desc):
        self.kind, self.net, self.key, self.pts, self.r, self.desc = kind, net, key, pts, r, desc

items = []
for p in pads:
    items.append(Item("pad", p["net"], ("pad", p["ref"], p["num"]),
                      [(p["x"], p["y"])], p["r"],
                      "pad %s.%s net=%r at (%.3f,%.3f) %s" % (p["ref"], p["num"], p["net"], p["x"], p["y"], p["type"])))
for v in vias:
    items.append(Item("via", v["net"], ("via", round(v["x"], 3), round(v["y"], 3)),
                      [(v["x"], v["y"])], v["r"],
                      "via net=%r at (%.3f,%.3f) drill=%.2f" % (v["net"], v["x"], v["y"], v["drill"])))
for i, s in enumerate(segs):
    items.append(Item("seg", s["net"], ("seg", i), [s["p1"], s["p2"]], s["w"] / 2.0,
                      "track net=%r %s w=%.2f (%.3f,%.3f)->(%.3f,%.3f)" %
                      (s["net"], s["layer"], s["w"], s["p1"][0], s["p1"][1], s["p2"][0], s["p2"][1])))

def dist(a, b):
    if len(a.pts) == 1 and len(b.pts) == 1:
        return math.hypot(a.pts[0][0] - b.pts[0][0], a.pts[0][1] - b.pts[0][1])
    if len(a.pts) == 1:
        return pt_seg(a.pts[0], b.pts[0], b.pts[1])
    if len(b.pts) == 1:
        return pt_seg(b.pts[0], a.pts[0], a.pts[1])
    return seg_seg(a.pts[0], a.pts[1], b.pts[0], b.pts[1])

class DSU:
    def __init__(self): self.p = {}
    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]; a = self.p[a]
        return a
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb: self.p[ra] = rb

print("=" * 76)
print("ZONES (copper pour state as written in the file)")
for z in zones:
    print("  net=%-6s layer=%-5s outline_pts=%d  filled_polygon_pts=%d"
          % (z["net"], z["layer"], len(z["outline"]), len(z["filled_pts"])))
print("  'filled_polygon' token present anywhere in file:", "filled_polygon" in txt)

print("=" * 76)
print("PER-NET COPPER GROUPS")
by_net = defaultdict(list)
for it in items:
    by_net[it.net].append(it)

dsu = DSU()
for it in items:
    dsu.find(it.key)
edges = []
for net, lst in by_net.items():
    for i in range(len(lst)):
        for j in range(i + 1, len(lst)):
            a, b = lst[i], lst[j]
            d = dist(a, b)
            if d <= a.r + b.r + 1e-6:
                edges.append((a, b, d))
                if a.net == b.net:
                    dsu.union(a.key, b.key)

for net in sorted(by_net):
    lst = by_net[net]
    groups = defaultdict(list)
    for it in lst:
        groups[dsu.find(it.key)].append(it)
    pads_in = [it for it in lst if it.kind == "pad"]
    print("\nnet %-18s items=%d (pads %d, vias %d, tracks %d)  copper groups=%d"
          % (net, len(lst), len(pads_in),
             len([i for i in lst if i.kind == "via"]), len([i for i in lst if i.kind == "seg"]),
             len(groups)))
    for _, grp in groups.items():
        ps = ["%s.%s@(%s,%s)" % (g.desc.split()[1], g.desc.split()[2], round(g.pts[0][0], 3), round(g.pts[0][1], 3))
              for g in grp if g.kind == "pad"]
        vs = ["(%s,%s)" % (round(g.pts[0][0], 3), round(g.pts[0][1], 3)) for g in grp if g.kind == "via"]
        print("     group: pads=%s vias=%s tracks=%d" % (ps, vs, len([g for g in grp if g.kind == "seg"])))
    if len(groups) > 1:
        print("     >>> OPEN: %d isolated copper groups on this net" % len(groups))

print("=" * 76)
print("CROSS-NET COPPER OVERLAP (geometric short check)")
for i in range(len(items)):
    for j in range(i + 1, len(items)):
        a, b = items[i], items[j]
        if a.net == b.net:
            continue
        d = dist(a, b)
        if d <= a.r + b.r + 1e-6:
            print("   OVERLAP gap=%.4f mm  %s   ||   %s" % (d, a.desc, b.desc))

print("=" * 76)
print("TRACK ENDPOINTS THAT TOUCH NOTHING ON THEIR OWN NET")
for s in segs:
    for ep in (s["p1"], s["p2"]):
        ok = False
        for a, b, d in edges:
            if a.net != s["net"] and b.net != s["net"]:
                continue
            for it in (a, b):
                if it.net != s["net"]:
                    continue
                if dist(Item("x", it.net, None, [ep], 0.0, ""), it) <= it.r + 1e-6:
                    ok = True
                    break
            if ok:
                break
        if not ok:
            print("   net=%-18s %s w=%.2f endpoint (%.3f,%.3f) is isolated"
                  % (s["net"], s["layer"], s["w"], ep[0], ep[1]))
