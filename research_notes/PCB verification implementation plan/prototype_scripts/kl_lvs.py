import sys, glob, os, json, time, collections
import klayout.db as kdb

d = sys.argv[1]
t0 = time.time()
b = lambda pat: os.path.basename(glob.glob(d + '/' + pat)[0])
ff = ''.join(
    '<free-file><filename>%s</filename><layout-layers><index>%d</index></layout-layers></free-file>' % (b(p), i)
    for i, p in enumerate(('*top_layer.gtl', '*-PTH.drl', '*bottom_layer.gbl')))
xml = ('<?xml version="1.0" encoding="utf-8"?><pcb-project><invert-negative-layers>false</invert-negative-layers><border>5000</border>'
       '<free-layer-mapping>true</free-layer-mapping><layout-layers><layout-layer>1/0</layout-layer><layout-layer>2/0</layout-layer><layout-layer>3/0</layout-layer></layout-layers>'
       '<mounting>top</mounting><num-metal-layers>0</num-metal-layers><num-via-types>0</num-via-types><artwork-files/><drill-files/><free-files>' + ff +
       '</free-files><reference-points/><explicit-trans>r0 *1 0,0</explicit-trans><layer-properties-file></layer-properties-file>'
       '<num-circle-points>64</num-circle-points><merge-flag>true</merge-flag><dbu>0.001</dbu><cell-name>PCB</cell-name></pcb-project>')
open(d + '/kl.pcb', 'w').write(xml)
ly = kdb.Layout()
ly.read(d + '/kl.pcb')
top = ly.top_cell()
l2n = kdb.LayoutToNetlist(kdb.RecursiveShapeIterator(ly, top, []))
L = {n: l2n.make_layer(ly.layer(i, 0), n) for n, i in (('top', 1), ('via', 2), ('bot', 3))}
print('shapes', {n: r.count() for n, r in L.items()})
for r in L.values():
    l2n.connect(r)
l2n.connect(L['top'], L['via'])
l2n.connect(L['via'], L['bot'])
l2n.extract_netlist()
c = l2n.netlist().top_circuit()
print('klayout nets', len(list(c.each_net())))
net2grp, grp2net, miss = collections.defaultdict(set), collections.defaultdict(set), 0
for lay, x, y, n in json.load(open(d + '/labels.json')):
    found = False
    for l in lay:
        net = l2n.probe_net(L[l], kdb.DPoint(x * 1000, y * 1000))
        if net is not None:
            found = True
            net2grp[n].add(net.cluster_id)
            grp2net[net.cluster_id].add(n)
    miss += not found
opens = {n: len(g) for n, g in net2grp.items() if len(g) > 1 and n != 'N/C'}
shorts = [sorted(v) for v in grp2net.values() if len(v - {'N/C'}) > 1]
print('KLAYOUT: unlocated=%d OPENS=%s SHORTS=%s time %.2fs' % (miss, opens, shorts, time.time() - t0))
