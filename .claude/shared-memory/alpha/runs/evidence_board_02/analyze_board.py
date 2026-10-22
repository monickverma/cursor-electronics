"""
Independent connectivity analysis of artifacts/board_02/board_02.kicad_pcb.
Reads ONLY the board folder + KiCad stock libraries (for pin/footprint reference).
No product source is touched.

Method:
  1. Parse the s-expression board file into pads, tracks, vias, zones.
  2. Build a copper graph per net: pad <-> track <-> via connectivity.
  3. Report connected components per net: which refs/pins are joined, which are islands.
"""
import json, math, re, sys, os
from collections import defaultdict

ART = r"C:\Users\KIIT\cursor-electronics\tests\fixtures\alpha_known_bad\artifacts\board_02"
PCB = os.path.join(ART, "board_02.kicad_pcb")
KICAD = r"C:\Program Files\KiCad\10.0\share\kicad"


# ---------- tiny s-expression parser ----------
def tokenize(text):
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "()":
            out.append(c); i += 1
        elif c == '"':
            j = i + 1; buf = []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j+1]); j += 2
                else:
                    buf.append(text[j]); j += 1
            out.append(('str', ''.join(buf))); i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()"':
                j += 1
            out.append(('sym', text[i:j])); i = j
    return out


def parse(text):
    toks = tokenize(text)
    pos = 0

    def rd():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == '(':
            lst = []
            while toks[pos] != ')':
                lst.append(rd())
            pos += 1
            return lst
        return t

    out = []
    while pos < len(toks):
        out.append(rd())
    return out


def sym(x):
    return x[1] if isinstance(x, tuple) else None


def val(x):
    return x[1] if isinstance(x, tuple) else None


def find_all(node, name):
    """all direct children lists whose head symbol == name"""
    res = []
    if isinstance(node, list) and node and sym(node[0]) == name:
        res.append(node)
    if isinstance(node, list):
        for c in node:
            if isinstance(c, list):
                res.extend(find_all(c, name))
    return res


def kids(node, name):
    return [c for c in node if isinstance(c, list) and sym(c[0]) == name]


def kid(node, name):
    k = kids(node, name)
    return k[0] if k else None


def rot_pt(x, y, deg):
    a = math.radians(deg)
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def pt_in(node):
    p = node if sym(node[0]) == 'xy' else kid(node, 'xy')
    return (float(val(p[1])), float(val(p[2])))


tree = parse(open(PCB, encoding='utf-8').read())
root = tree[0]

# ---------- collect ----------
pads, tracks, vias, zones, footprints = [], [], [], [], []
for fp in find_all(root, 'footprint'):
    at = kid(fp, 'at')
    ox, oy = float(val(at[1])), float(val(at[2]))
    rot = float(val(at[3])) if len(at) > 3 else 0.0
    ref = val(kid(kid(fp, 'property'), 'property')[0]) if False else None
    ref = None
    for p in kids(fp, 'property'):
        if val(p[1]) == 'Reference':
            ref = val(p[2])
    libid = val(fp[1]) if isinstance(fp[1], tuple) else fp[1]
    for p in kids(fp, 'pad'):
        pat = kid(p, 'at')
        px, py = float(val(pat[1])), float(val(pat[2]))
        prot = float(val(pat[3])) if len(pat) > 3 else 0.0
        size = kid(p, 'size')
        sx, sy = float(val(size[1])), float(val(size[2]))
        netn = kid(p, 'net')
        shape = val(p[1]) if isinstance(p[1], tuple) else 'circle'
        ptype = val(p[2]) if isinstance(p[2], tuple) else ''
        pnet = val(netn[1]) if netn else None
        rx, ry = rot_pt(px, py, rot)
        pads.append(dict(ref=ref, lib=libid, num=val(p[1]), shape=shape, ptype=ptype,
                         x=ox + rx, y=oy + ry, sx=sx, sy=sy,
                         w=ptype, net=pnet, rot=(rot + prot) % 360,
                         layers=[val(l) for l in (kid(p, 'layers')[1:] if kid(p, 'layers') else [])]))
    footprints.append(dict(ref=ref, lib=libid, x=ox, y=oy, rot=rot))
    for s in kids(fp, 'fp_line'):
        lay = kid(s, 'layer')
        if lay and val(lay[1]) == 'F.SilkS':
            print("SILK line found on", ref)

for s in find_all(root, 'segment'):
    st, en = kid(s, 'start'), kid(s, 'end')
    netn = kid(s, 'net')
    w = kid(s, 'width')
    lay = kid(s, 'layer')
    tracks.append(dict(x0=float(val(st[1])), y0=float(val(st[2])),
                       x1=float(val(en[1])), y1=float(val(en[2])),
                       w=float(val(w[1])), net=val(netn[1]) if netn else None,
                       layer=val(lay[1])))

for v in find_all(root, 'via'):
    at = kid(v, 'at')
    netn = kid(v, 'net')
    size = kid(v, 'size')
    tracks_v = tracks
    vias.append(dict(x=float(val(at[1])), y=float(val(at[2])),
                     size=float(val(size[1])), net=val(netn[1]) if netn else None))

for z in find_all(root, 'zone'):
    netn = kid(z, 'net')
    filled = kid(z, 'filled_polygon')
    poly = kid(z, 'polygon')
    pts = [pt_in(p) for p in find_all(poly, 'xy')] if poly else []
    zones.append(dict(net=val(netn[1]) if netn else None,
                      filled=bool(filled), pts=pts))

print("== parsed ==")
print("footprints:", [(f['ref'], f['lib']) for f in footprints])
print("pads:", len(pads), "tracks:", len(tracks), "vias:", len(vias))
for z in zones:
    print("zone net=%s filled_polygon_present=%s pts=%s" % (z['net'], z['filled'], z['pts']))

# ---------- copper graph ----------
def seg_pt_dist(x0, y0, x1, y1, px, py):
    dx, dy = x1 - x0, y1 - y0
    if dx == 0 and dy == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def pad_r(p):
    return max(p['sx'], p['sy']) / 2.0


def pad_hits(p, x, y):
    """is point (x,y) on the pad's copper? circle/oval approx via ellipse test"""
    if p['shape'] == 'oval' or p['shape'] == 'rect':
        dx = (x - p['x']) / (p['sx'] / 2.0)
        dy = (y - p['y']) / (p['sy'] / 2.0)
        return (dx * dx + dy * dy) <= 1.0
    return math.hypot(x - p['x'], y - p['y']) <= pad_r(p) + 1e-6


parent = {}

def find(a):
    parent.setdefault(a, a)
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a

def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb

# nodes: ('pad', i), ('t', i), ('v', i)
net_nodes = defaultdict(list)
for i, p in enumerate(pads):
    if p['net']:
        net_nodes[p['net']].append(('pad', i))
for i, t in enumerate(tracks):
    if t['net']:
        net_nodes[t['net']].append(('t', i))
for i, v in enumerate(vias):
    if v['net']:
        net_nodes[v['net']].append(('v', i))

for net, nodes in net_nodes.items():
    for nd in nodes:
        find(nd)
    # pad <-> track
    for (ki, i) in list(nodes):
        if ki != 'pad':
            continue
        p = pads[i]
        for (tj, j) in nodes:
            if tj != 't':
                continue
            t = tracks[j]
            if pad_hits(p, t['x0'], t['y0']) or pad_hits(p, t['x1'], t['y1']) \
               or seg_pt_dist(t['x0'], t['y0'], t['x1'], t['y1'], p['x'], p['y']) <= pad_r(p) + 1e-6:
                union(('pad', i), ('t', j))
    # pad <-> via
    for (ki, i) in list(nodes):
        if ki != 'pad':
            continue
        p = pads[i]
        for (vj, j) in nodes:
            if vj != 'v':
                continue
            v = vias[j]
            if math.hypot(p['x'] - v['x'], p['y'] - v['y']) <= pad_r(p) + v['size'] / 2.0:
                union(('pad', i), ('v', j))
    # track <-> track (shared endpoint / endpoint on other segment)
    for a in range(len(nodes)):
        for b in range(a + 1, len(nodes)):
            if nodes[a][0] == 't' and nodes[b][0] == 't':
                t1, t2 = tracks[nodes[a][1]], tracks[nodes[b][1]]
                d = min(seg_pt_dist(t1['x0'], t1['y0'], t1['x1'], t1['y1'], t2['x0'], t2['y0']),
                        seg_pt_dist(t1['x0'], t1['y0'], t1['x1'], t1['y1'], t2['x1'], t2['y1']),
                        seg_pt_dist(t2['x0'], t2['y0'], t2['x1'], t2['y1'], t1['x0'], t1['y0']),
                        seg_pt_dist(t2['x0'], t2['y0'], t2['x1'], t2['y1'], t1['x1'], t1['y1']))
                if d <= 1e-6:
                    union(nodes[a], nodes[b])
    # track <-> via
    for (ki, i) in list(nodes):
        if ki != 't':
            continue
        t = tracks[i]
        for (vj, j) in nodes:
            if vj != 'v':
                continue
            v = vias[j]
            if seg_pt_dist(t['x0'], t['y0'], t['x1'], t['y1'], v['x'], v['y']) <= v['size'] / 2.0 + 1e-6:
                union(('t', i), ('v', j))
    # via <-> via
    for a in range(len(nodes)):
        for b in range(a + 1, len(nodes)):
            if nodes[a][0] == 'v' and nodes[b][0] == 'v':
                v1, v2 = vias[nodes[a][1]], vias[nodes[b][1]]
                if math.hypot(v1['x'] - v2['x'], v1['y'] - v2['y']) <= (v1['size'] + v2['size']) / 2.0:
                    union(nodes[a], nodes[b])

report = {}
for net, nodes in sorted(net_nodes.items()):
    comps = defaultdict(list)
    for nd in nodes:
        comps[find(nd)].append(nd)
    entry = []
    for rootid, members in comps.items():
        labels = []
        for (k, i) in members:
            if k == 'pad':
                p = pads[i]
                labels.append("%s.%s" % (p['ref'], p['num']))
            elif k == 'v':
                v = vias[i]
                labels.append("via(%.2f,%.2f)" % (v['x'], v['y']))
            else:
                t = tracks[i]
                labels.append("track(%.3f,%.3f)-(%.3f,%.3f)" % (t['x0'], t['y0'], t['x1'], t['y1']))
        entry.append(sorted(labels))
    entry.sort(key=len, reverse=True)
    report[net] = entry
    print("\n== NET %s : %d component(s)" % (net, len(entry)))
    for e in entry:
        print("   -", ", ".join(e))

# ---------- track gap analysis (endpoints that do not meet) ----------
print("\n== dangling track endpoints (F.Cu/B.Cu) ==")
for net, nodes in net_nodes.items():
    ts = [tracks[i] for (k, i) in nodes if k == 't']
    for a in range(len(ts)):
        for b in range(a + 1, len(ts)):
            t1, t2 = ts[a], ts[b]
            d = min(seg_pt_dist(t1['x0'], t1['y0'], t1['x1'], t1['y1'], t2['x0'], t2['y0']),
                    seg_pt_dist(t1['x0'], t1['y0'], t1['x1'], t1['y1'], t2['x1'], t2['y1']),
                    seg_pt_dist(t2['x0'], t2['y0'], t2['x1'], t2['y1'], t1['x0'], t1['y0']),
                    seg_pt_dist(t2['x0'], t2['y0'], t2['x1'], t2['y1'], t1['x1'], t1['y1']))
            if 1e-6 < d < 0.001:
                print("   net %s: gap %.6f mm  t1(%.4f,%.4f)-(%.4f,%.4f)  t2(%.4f,%.4f)-(%.4f,%.4f)"
                      % (net, d, t1['x0'], t1['y0'], t1['x1'], t1['y1'],
                         t2['x0'], t2['y0'], t2['x1'], t2['y1']))

out = dict(
    footprints=footprints,
    pads=[{k: v for k, v in p.items() if k != 'layers'} for p in pads],
    tracks=tracks, vias=vias,
    zones=[{k: (v if k != 'pts' else v) for k, v in z.items()} for z in zones],
    net_components=report,
)
open(os.path.join(os.path.dirname(PCB), "..", "..", "..", "..", "..",
                   ".claude", "shared-memory", "alpha", "runs", "evidence_board_02",
                   "connectivity_analysis.json"), "w", encoding="utf-8").write(
    json.dumps(out, indent=1))
print("\nwrote connectivity_analysis.json")
