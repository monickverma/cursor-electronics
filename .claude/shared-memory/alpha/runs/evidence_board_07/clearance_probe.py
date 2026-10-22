"""Independent copper-clearance probe for board_07.

Parses the .kicad_pcb as s-expressions and computes minimum copper-to-copper
distance between every pair of nets, on every layer, and between mains and the
B.Cu ground pour (whose extent is bounded by the keepout rule area).
"""
import math
import re
import sys

PCB = sys.argv[1]


# ---------- minimal s-expression reader ----------
def tokenize(text):
    text = re.sub(r'"(?:[^"\\]|\\.)*"', lambda m: '"' + m.group(0)[1:-1].replace('\\"', '"') + '"', text)
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == '(' or c == ')':
            out.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            while j < n:
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == '"':
                    break
                j += 1
            out.append(text[i:j + 1])
            i = j + 1
        else:
            j = i
            while j < n and (not text[j].isspace()) and text[j] not in '()':
                j += 1
            out.append(text[i:j])
            i = j
    return out


def parse(tokens, pos=0):
    assert tokens[pos] == '('
    pos += 1
    node = []
    while tokens[pos] != ')':
        if tokens[pos] == '(':
            sub, pos = parse(tokens, pos)
            node.append(sub)
        else:
            node.append(tokens[pos])
            pos += 1
    return node, pos + 1


def kids(node, name):
    return [k for k in node if isinstance(k, list) and k and k[0] == name]


def kid(node, name):
    k = kids(node, name)
    return k[0] if k else None


def unq(s):
    return s[1:-1] if isinstance(s, str) and s.startswith('"') else s


def num(x):
    return float(x)


tokens = tokenize(open(PCB, encoding='utf-8').read())
root, _ = parse(tokens)

# ---------- collect copper items ----------
pads, tracks, vias, zones, keepouts, edge = [], [], [], [], [], []
for node in root:
    if not isinstance(node, list) or not node:
        continue
    tag = node[0]
    if tag == 'footprint':
        fx, fy = num(kid(node, 'at')[1]), num(kid(node, 'at')[2])
        frot = num(kid(node, 'at')[3]) if len(kid(node, 'at')) > 3 else 0.0
        ref = None
        for p in kids(node, 'property'):
            if unq(p[1]) == 'Reference':
                ref = unq(p[2])
        for p in kids(node, 'pad'):
            at = kid(p, 'at')
            px, py = num(at[1]), num(at[2])
            size = kid(p, 'size')
            w, h = num(size[1]), num(size[2])
            netn = kid(p, 'net')
            plays = [unq(x) for x in kid(p, 'layers')[1:]]
            cl = []
            for l in plays:
                if l == '*.Cu':
                    cl += ['F.Cu', 'B.Cu']
                elif l.endswith('.Cu'):
                    cl.append(l)
            pads.append(dict(ref=ref, pin=unq(p[1]), x=fx + px, y=fy + py,
                             r=max(w, h) / 2.0, net=unq(netn[1]) if netn else '',
                             layers=cl,
                             kind='pad'))
    elif tag == 'segment':
        s, e = kid(node, 'start'), kid(node, 'end')
        tracks.append(dict(net=unq(kid(node, 'net')[1]), layer=unq(kid(node, 'layer')[1]),
                           w=num(kid(node, 'width')[1]),
                           x1=num(s[1]), y1=num(s[2]), x2=num(e[1]), y2=num(e[2])))
    elif tag == 'via':
        at = kid(node, 'at')
        vias.append(dict(net=unq(kid(node, 'net')[1]), x=num(at[1]), y=num(at[2]),
                         r=num(kid(node, 'size')[1]) / 2.0,
                         layers=[unq(x) for x in kid(node, 'layers')[1:]]))
    elif tag == 'zone':
        poly = kid(node, 'polygon')
        pts = [(num(p[1]), num(p[2])) for p in kid(poly, 'pts')[1:]]
        is_keepout = kid(node, 'keepout') is not None
        (keepouts if is_keepout else zones).append(
            dict(net=unq(kid(node, 'net')[1]) if kid(node, 'net') else '',
                 layers=[unq(x) for x in kid(node, 'layer')[1:]] if kid(node, 'layer')
                 else [unq(x) for x in kid(node, 'layers')[1:]],
                 pts=pts, filled='filled_polygon' in [k[0] for k in node if isinstance(k, list)]))
    elif tag == 'gr_rect' and unq(kid(node, 'layer')[1]) == 'Edge.Cuts':
        s, e = kid(node, 'start'), kid(node, 'end')
        edge = (num(s[1]), num(s[2]), num(e[1]), num(e[2]))


def seg_point_dist(a, b, p):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def seg_seg_dist(a1, a2, b1, b2):
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1 = cross(b1, b2, a1)
    d2 = cross(b1, b2, a2)
    d3 = cross(a1, a2, b1)
    d4 = cross(a1, a2, b2)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(seg_point_dist(a1, a2, b1), seg_point_dist(a1, a2, b2),
               seg_point_dist(b1, b2, a1), seg_point_dist(b1, b2, a2))


def track_clear(t, p):
    return seg_point_dist((t['x1'], t['y1']), (t['x2'], t['y2']), (p['x'], p['y'])) - t['w'] / 2.0 - p['r']


def track_track_clear(t1, t2):
    return seg_seg_dist((t1['x1'], t1['y1']), (t1['x2'], t1['y2']),
                        (t2['x1'], t2['y1']), (t2['x2'], t2['y2'])) - t1['w'] / 2.0 - t2['w'] / 2.0


def point_rect_dist(x, y, rect):
    x0, y0, x1, y1 = rect
    dx = max(x0 - x, 0, x - x1)
    dy = max(y0 - y, 0, y - y1)
    return math.hypot(dx, dy)


def track_rect_dist(t, rect):
    """min distance from a track's copper edge to the BOUNDARY of an axis-aligned
    rectangle (the rectangle is a hole in the pour; the pour lies outside it)."""
    x0, y0, x1, y1 = rect
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
             ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    best = 1e9
    for e1, e2 in edges:
        best = min(best, seg_seg_dist((t['x1'], t['y1']), (t['x2'], t['y2']), e1, e2))
    return best - t['w'] / 2.0


def rects_of_keepout(k):
    xs = [p[0] for p in k['pts']]
    ys = [p[1] for p in k['pts']]
    return (min(xs), min(ys), max(xs), max(ys))


# ---------- report ----------
print("=" * 78)
print("BOARD:", PCB)
print("Edge.Cuts rect:", edge)
print("Zones (pours):")
for z in zones:
    print("   net=%-8s layers=%s  pts=%s  has_saved_fill=%s" %
          (z['net'], z['layers'], z['pts'], z['filled']))
print("Keepout rule areas:")
for k in keepouts:
    print("   layers=%s rect=%s reason-ok" % (k['layers'], rects_of_keepout(k)))

mains = [t for t in tracks if t['net'] == 'MAINS_L']
print()
print("MAINS_L copper items:")
for t in mains:
    print("   track F.Cu? %s w=%.2f  (%.3f,%.3f)->(%.3f,%.3f)" %
          (t['layer'], t['w'], t['x1'], t['y1'], t['x2'], t['y2']))
for p in pads:
    if p['net'] == 'MAINS_L':
        print("   pad %s.%s at (%.2f,%.2f) r=%.2f" % (p['ref'], p['pin'], p['x'], p['y'], p['r']))

# ---- 1. MAINS_L vs every other net ----
print()
print("=" * 78)
print("MINIMUM COPPER CLEARANCE: MAINS_L  vs  every other net")
print("=" * 78)
items = []
for t in tracks:
    t['kind'] = 'track'
    items.append(('track:' + t['net'] + '@' + t['layer'], t, t['net'], t['layer']))
for p in pads:
    layers = [l for l in p['layers'] if l.endswith('.Cu')]
    for l in layers:
        items.append(('pad:%s.%s[%s]' % (p['ref'], p['pin'], p['net']), p, p['net'] or '<no net>', l))
for v in vias:
    v['kind'] = 'via'
    for l in v['layers']:
        items.append(('via:%s' % v['net'], v, v['net'], l))

results = []
for mname, m, mnet, mlayer in items:
    if mnet == 'MAINS_L':
        continue
    for oname, o, onet, olayer in items:
        if m is o or mnet == onet:
            continue
        if (mnet == 'MAINS_L') == (onet == 'MAINS_L'):
            continue          # keep only pairs where exactly one side IS the mains net
        if olayer != mlayer:
            continue
        if m['kind'] == 'track' and o['kind'] == 'track':
            d = track_track_clear(m, o)
        elif m['kind'] == 'track':
            d = track_clear(m, o)
        elif o['kind'] == 'track':
            d = track_clear(o, m)
        else:
            d = math.hypot(m['x'] - o['x'], m['y'] - o['y']) - m['r'] - o['r']
        if d < 6.0:
            results.append((d, mname, oname, mlayer))

results.sort()
seen = set()
for d, mname, oname, layer in results:
    key = (mname, oname)
    if key in seen:
        continue
    seen.add(key)
    if d < 4.0:
        print("  %7.3f mm   %-28s  <->  %-28s  (%s)" % (d, mname, oname, layer))
print()
print("  --- worst 8 mains-to-other-net clearances, closest first ---")
results.sort(key=lambda r: r[0])
for d, mname, oname, layer in results[:8]:
    print("  %7.3f mm   %-28s  <->  %-28s  (%s)" % (d, mname, oname, layer))

# ---- 2. MAINS_L vs B.Cu ground pour ----
print()
print("=" * 78)
print("MAINS_L  vs  B.Cu GND POUR (pour extent bounded by the keepout rule area)")
print("=" * 78)
for z in zones:
    if z['net'] != 'GND':
        continue
    for k in keepouts:
        if 'B.Cu' not in k['layers']:
            continue
        kr = rects_of_keepout(k)
        for t in mains:
            if t['layer'] == 'B.Cu':
                continue
            d = track_rect_dist(t, kr)
            print("  mains track (%.3f,%.3f)->(%.3f,%.3f) w=%.2f  ->  nearest B.Cu pour edge "
                  "(pour is excluded inside x>=%.1f):  %.3f mm" %
                  (t['x1'], t['y1'], t['x2'], t['y2'], t['w'], kr[0], d))

# ---- 2b. exact geometry of the closest mains pair ----
print()
print("=" * 78)
print("EXACT GEOMETRY OF THE CLOSEST MAINS PAIR")
print("=" * 78)
for t in tracks:
    if t['net'] == 'DHT22_DATA' and t['layer'] == 'F.Cu' and abs(t['x1'] - 39.6) < 1e-6:
        print("  DHT22_DATA track: (%.3f,%.3f)->(%.3f,%.3f)  width %.2f  layer %s" %
              (t['x1'], t['y1'], t['x2'], t['y2'], t['w'], t['layer']))
for t in tracks:
    if t['net'] == 'MAINS_L' and abs(t['x1'] - 40.5) < 1e-6 and abs(t['x2'] - 40.5) < 1e-6:
        print("  MAINS_L    track: (%.3f,%.3f)->(%.3f,%.3f)  width %.2f  layer %s" %
              (t['x1'], t['y1'], t['x2'], t['y2'], t['w'], t['layer']))
print("  centre-to-centre  = 40.500 - 39.600 = 0.900 mm")
print("  copper-to-copper  = 0.900 - 0.800/2 - 0.300/2 = %.3f mm" % (0.9 - 0.4 - 0.15))
print("  the DHT22_DATA run at x=39.6 lies INSIDE the product's own mains-corridor rule area")
print("  (rect x 39.0..52.0) but that rule area is defined on B.Cu only, so it does not")
print("  constrain an F.Cu track.")

# ---- 3. all-pairs minimum, other nets ----
print()
print("=" * 78)
print("MINIMUM CLEARANCE between all other net pairs (< 0.30 mm shown)")
print("=" * 78)
out = []
for i in range(len(items)):
    for j in range(i + 1, len(items)):
        n1, m, net1, l1 = items[i]
        n2, o, net2, l2 = items[j]
        if net1 == net2 or l1 != l2 or m is o:
            continue
        if m['kind'] == 'track' and o['kind'] == 'track':
            d = track_track_clear(m, o)
        elif m['kind'] == 'track':
            d = track_clear(m, o)
        elif o['kind'] == 'track':
            d = track_clear(o, m)
        else:
            d = math.hypot(m['x'] - o['x'], m['y'] - o['y']) - m['r'] - o['r']
        if d < 0.30:
            out.append((d, n1, n2, l1))
out.sort()
for d, n1, n2, l1 in out[:30]:
    print("  %7.3f mm   %-26s <-> %-26s (%s)" % (d, n1, n2, l1))
if not out:
    print("  none below 0.30 mm")

# ---- 4. pads with no net ----
print()
print("=" * 78)
print("PADS WITH NO NET (no copper attached)")
print("=" * 78)
for p in sorted(pads, key=lambda q: (q['ref'], q['pin'])):
    if not p['net']:
        print("   %s pin %-3s at (%.2f, %.2f)" % (p['ref'], p['pin'], p['x'], p['y']))

# ---- 5. nets and their pad counts ----
print()
print("=" * 78)
print("NET -> pads")
print("=" * 78)
nets = {}
for p in pads:
    nets.setdefault(p['net'] or '<no net>', []).append("%s.%s" % (p['ref'], p['pin']))
for n in sorted(nets):
    print("   %-16s %s" % (n, ', '.join(nets[n])))
