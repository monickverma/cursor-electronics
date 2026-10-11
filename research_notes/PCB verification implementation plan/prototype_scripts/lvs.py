"""Prototype Gerber read-back LVS: gerbonara parse -> shapely union -> union-find through PTH -> compare with IPC-D-356."""
import sys, time, glob, collections, warnings, json
warnings.simplefilter('ignore')
from gerbonara import GerberFile, ExcellonFile, Netlist
import gerbonara.graphic_primitives as gp
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from shapely import STRtree

d = sys.argv[1]


def one(pat):
    return glob.glob(d + '/' + pat)[0]


def prim_geom(p):
    if isinstance(p, gp.Line):
        if p.x1 == p.x2 and p.y1 == p.y2:
            return Point(p.x1, p.y1).buffer(p.width / 2, 16)
        return LineString([(p.x1, p.y1), (p.x2, p.y2)]).buffer(p.width / 2, 16)
    if isinstance(p, gp.Circle):
        return Point(p.x, p.y).buffer(p.r, 16)
    if isinstance(p, gp.Arc):
        raise NotImplementedError('arc stroke')
    if not isinstance(p, gp.ArcPoly):
        p = p.to_arc_poly()
    if any(c is not None for c in p.arc_centers):
        p = p.approximate_arcs(0.002)
    g = Polygon(p.outline)
    return g if g.is_valid else g.buffer(0)


def layer_components(path):
    g = GerberFile.open(path)
    dark, labels, clear = [], [], 0
    for o in g.objects:
        a = o.attrs if isinstance(o.attrs, dict) else {}
        for p in o.to_primitives(unit=g.unit):
            if not p.polarity_dark:
                clear += 1
                continue
            dark.append(prim_geom(p))
        if '.N' in a and type(o).__name__ == 'Flash':
            labels.append((o.x, o.y, a['.N'][0] if a['.N'] else '', a.get('.P')))
    u = unary_union(dark)
    comps = list(u.geoms) if hasattr(u, 'geoms') else [u]
    return comps, STRtree(comps), labels, clear


t0 = time.time()
layers = {'top': layer_components(one('*top_layer.gtl')), 'bot': layer_components(one('*bottom_layer.gbl'))}
print('components per layer', {k: len(v[0]) for k, v in layers.items()}, 'clear prims', {k: v[3] for k, v in layers.items()})
parent = {}


def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def union(a, b):
    parent[find(a)] = find(b)


def locate(layer, x, y, r=0.0):
    comps, tree, _, _ = layers[layer]
    q = Point(x, y) if r == 0 else Point(x, y).buffer(r)
    return [(layer, int(i)) for i in tree.query(q, predicate='intersects')]


pth = ExcellonFile.open(one('*-PTH.drl'))
dangling = 0
for o in pth.objects:
    if type(o).__name__ != 'Flash':
        continue
    hits = locate('top', o.x, o.y, o.aperture.diameter / 2) + locate('bot', o.x, o.y, o.aperture.diameter / 2)
    if len(hits) < 2:
        dangling += 1
    for h in hits[1:]:
        union(hits[0], h)
print('PTH hits', len(pth.objects), 'touching <2 copper comps', dangling)

nl = Netlist.open(one('*.d356'))


def run(labelsrc):
    net2grp, grp2net, miss = collections.defaultdict(set), collections.defaultdict(set), 0
    for (lay, x, y, net, who) in labelsrc:
        hits = []
        for l in lay:
            hits += locate(l, x, y)
        if not hits:
            miss += 1
            continue
        for h in hits:
            r = find(h)
            net2grp[net].add(r)
            grp2net[r].add(net)
    opens = {n: len(g) for n, g in net2grp.items() if len(g) > 1 and n not in ('N/C', '')}
    shorts = [sorted(n) for n in grp2net.values() if len(n - {'N/C', ''}) > 1]
    return miss, opens, shorts, len(net2grp)


pinpos = {}
for lay in layers:
    for (x, y, net, pin) in layers[lay][2]:
        if pin:
            pinpos[(pin[0], pin[1])] = (x, y)
votes = collections.Counter()
for r in nl.test_records:
    k = (r.ref_des, str(r.pin_num) if r.pin_num is not None else None)
    if k in pinpos:
        for sy in (-1, 1):
            votes[(sy, round(pinpos[k][0] - r.x * 25.4, 2), round(pinpos[k][1] - sy * r.y * 25.4, 2))] += 1
last = nl.test_records[-1]
print('D356->Gerber transform votes (sy,dx,dy):', votes.most_common(3), 'sample rec', last.ref_des, last.pin_num)
(sy, dx, dy) = votes.most_common(1)[0][0] if votes else (1, 62.23, -153.67)
src = []
for r in nl.test_records:
    lay = {0: ('top', 'bot'), 1: ('top',)}.get(r.access_layer, ('bot',))
    src.append((lay, r.x * 25.4 + dx, sy * r.y * 25.4 + dy, r.net_name or 'N/C', r.ref_des))
miss, opens, shorts, nn = run(src)
print(f'D356 labels: records={len(src)} unlocated={miss} nets={nn} OPENS={opens} SHORTS={shorts}')
json.dump([[list(l), x, y, n] for (l, x, y, n, _) in src], open(d + '/labels.json', 'w'))

src2 = []
for lay in layers:
    for (x, y, net, pin) in layers[lay][2]:
        src2.append(((lay,), x, y, net, pin))
miss, opens, shorts, nn = run(src2)
print(f'X2 .N flash labels: labels={len(src2)} unlocated={miss} nets={nn} OPENS={opens} SHORTS={shorts}')
print('time %.2fs' % (time.time() - t0))
