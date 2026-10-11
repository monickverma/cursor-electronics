import re, math, sys, json, collections

mode = sys.argv[1]
if mode == 'seed':
    pp = sys.argv[2]
    src = open(pp + '/pic_programmer.kicad_pcb', encoding='utf-8').read()

    def blocks(kind):
        out = []
        for m in re.finditer(r'\n\t\(%s\n' % kind, src):
            i = m.start() + 2
            depth = 0
            j = i
            while True:
                if src[j] == '(':
                    depth += 1
                elif src[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out.append((i, j + 1))
        return out

    segs = blocks('segment')
    vias = blocks('via')
    tgt = [(i, j) for i, j in segs if '(net "/CLOCK-RB6")' in src[i:j]][0]
    open(pp + '/defect_cut.kicad_pcb', 'w', encoding='utf-8').write(src[:tgt[0]] + src[tgt[1]:])
    print('cut segment:', ' '.join(src[tgt[0]:tgt[1]].split())[:140])
    v = vias[0]
    open(pp + '/defect_via.kicad_pcb', 'w', encoding='utf-8').write(src[:v[0]] + src[v[1]:])
    print('deleted via:', ' '.join(src[v[0]:v[1]].split())[:90], re.search(r'\(net "[^"]*"\)', src[v[0]:v[1]]).group(0))
    vi = []
    for i, j in vias:
        t = src[i:j]
        a = re.search(r'\(at ([-\d.]+) ([-\d.]+)\)', t)
        n = re.search(r'\(net "([^"]*)"\)', t)
        vi.append((float(a.group(1)), float(a.group(2)), n.group(1)))
    best = min(((math.dist(a[:2], b[:2]), a, b) for a in vi for b in vi if a[2] != b[2]), key=lambda t: t[0])
    _, a, b = best
    seg = ('(segment\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(width 0.25)\n\t\t(layer "F.Cu")\n\t\t(net "%s")\n'
           '\t\t(uuid "11111111-2222-3333-4444-555555555555")\n\t)\n\t') % (a[0], a[1], b[0], b[1], a[2])
    open(pp + '/defect_short.kicad_pcb', 'w', encoding='utf-8').write(src[:segs[0][0]] + seg + src[segs[0][0]:])
    print('bridge:', a, b, 'len %.2f' % best[0])
elif mode == 'drcsum':
    d = json.load(open(sys.argv[2]))
    print('KiCad DRC types', dict(collections.Counter(v['type'] for v in d['violations'])), 'unconnected', len(d['unconnected_items']))
    for u in d['unconnected_items'][:2]:
        print('  UNCONN', json.dumps(u)[:420])
    for v in [v for v in d['violations'] if v['type'] in ('shorting_items', 'tracks_crossing', 'clearance')][:3]:
        print('  ', v['type'], v['description'][:120])
elif mode == 'shift':
    pp = sys.argv[2]
    L = open(pp + '/out/pic_programmer-PTH.drl').read().split('\n')
    i = next(k for k, l in enumerate(L) if re.match(r'X[-\d.]+Y[-\d.]+', l))
    m = re.match(r'X([-\d.]+)Y([-\d.]+)', L[i])
    print('shift hit', L[i])
    L[i] = 'X%.3fY%s' % (float(m.group(1)) + 3.0, m.group(2))
    open(pp + '/o_shift/pic_programmer-PTH.drl', 'w').write('\n'.join(L))
