"""Overlooker analysis of artifacts/board_06 — reads only the board folder + KiCad stock libs."""
import json, re, sys, os

BOARD = sys.argv[1]
IR    = sys.argv[2]
STD   = sys.argv[3]          # KiCad stock DIP-28_W7.62mm.kicad_mod
OUT   = sys.argv[4]

t = open(BOARD, encoding='utf-8').read()

def blocks(pattern, src):
    """Return list of (start,end) spans of balanced (...) groups matching a head pattern."""
    out = []
    for m in re.finditer(pattern, src):
        i = m.start()
        depth = 0
        for j in range(i, len(src)):
            if src[j] == '(':
                depth += 1
            elif src[j] == ')':
                depth -= 1
                if depth == 0:
                    out.append(src[i:j+1])
                    break
    return out

fps = {}
for b in blocks(r'\(footprint "', t):
    name = re.search(r'\(footprint "([^"]+)"', b).group(1)
    at   = re.search(r'\(at ([-\d.]+) ([-\d.]+)\)', b).group(1, 2)
    ox, oy = float(at[0]), float(at[1])
    ref  = re.search(r'\(property "Reference" "([^"]+)"', b).group(1)
    val  = re.search(r'\(property "Value" "([^"]+)"', b).group(1)
    mpn  = re.search(r'\(property "MPN" "([^"]+)"', b)
    pads = []
    for pb in blocks(r'\(pad "', b):
        pn   = re.search(r'\(pad "([^"]+)"', pb).group(1)
        pat  = re.search(r'\(at ([-\d.]+) ([-\d.]+)\)', pb)
        px, py = float(pat.group(1)), float(pat.group(2))
        net  = re.search(r'\(net "([^"]*)"\)', pb)
        pads.append(dict(pin=pn, x=ox+px, y=oy+py, lx=px, ly=py,
                          net=(net.group(1) if net else "")))
    fps[ref] = dict(lib=name, ref=ref, value=val, mpn=(mpn.group(1) if mpn else ""),
                    x=ox, y=oy, pads=pads)

ir = json.load(open(IR, encoding='utf-8'))
irc = {c['ref']: c for c in ir['components']}
H = ir['outline_h']

L = []
def w(s=''): L.append(s)

w('=' * 78)
w('A. board_06.kicad_pcb  vs  board_ir.json  — do they describe the same board?')
w('=' * 78)
w(f"{'ref':5} {'pcb (x,y)':>18} {'board_ir (x,y)':>18} {'45.72-ir_y':>11} {'match':>8}")
allmirror = True
for ref in fps:
    p = fps[ref]; i = irc[ref]
    my = H - i['y']
    ok = (abs(p['x'] - i['x']) < 1e-6 and abs(p['y'] - my) < 1e-6)
    allmirror &= ok
    w(f"{ref:5} {f'({p[chr(120)]:.2f},{p[chr(121)]:.2f})':>18} "
      f"{f'({i[chr(120)]:.2f},{i[chr(121)]:.2f})':>18} {f'({i[chr(120)]:.2f},{my:.2f})':>11} "
      f"{'MIRROR' if ok else 'NO':>8}")
w(f"\nEVERY component position in the .kicad_pcb equals board_ir with y -> {H} - y : "
  f"{allmirror}\n")

w('=' * 78)
w('B. Footprint pad layouts — is each pad layout also mirrored?')
w('   (compare pcb footprint local coords with board_ir pad coords, both re-centred)')
w('=' * 78)
for ref in fps:
    p = fps[ref]; i = irc[ref]
    pl = {q['pin']: (q['lx'], q['ly']) for q in p['pads']}
    il = {q['pin']: (q['x'] - i['x'], q['y'] - i['y']) for q in i['pads']}
    pairs = [(k, pl[k], il[k]) for k in pl if k in il]
    mir = all(abs(a[0]-b[0]) < 1e-6 and abs(a[1]+b[1]) < 1e-6 for _, a, b in pairs)
    same = all(abs(a[0]-b[0]) < 1e-6 and abs(a[1]-b[1]) < 1e-6 for _, a, b in pairs)
    w(f"{ref:5} ({p['lib']}):  pads mirrored in y = {mir}   identical = {same}")
w("")

w('=' * 78)
w('C. U1 DIP-28 footprint vs KiCad stock Package_DIP:DIP-28_W7.62mm')
w('=' * 78)
st = open(STD, encoding='utf-8').read()
sp = {}
for m in re.finditer(r'\(pad "(\d+)"[^\n]*\n\s*\(at ([-\d.]+) ([-\d.]+)\)', st):
    sp[m.group(1)] = (float(m.group(2)), float(m.group(3)))
# stock: pin1 at (0,0) top-left, pins 1..14 down +y, 15..28 up the right column.
# re-centre both on the body centre, x re-centred to +/-3.81
sy = (min(v[1] for v in sp.values()) + max(v[1] for v in sp.values())) / 2
sx = (min(v[0] for v in sp.values()) + max(v[0] for v in sp.values())) / 2
stock = {k: (v[0]-sx, v[1]-sy) for k, v in sp.items()}
w(f"stock footprint body centre: x=0 y=0 (stock pad1 at {(stock['1'][0], stock['1'][1])}, "
  f"pad14 at {stock['14']}, pad15 at {stock['15']}, pad28 at {stock['28']})")
w(f"board  footprint U1: pad1 local {fps['U1']['pads'][0]['lx']},{fps['U1']['pads'][0]['ly']}  "
  f"pad14 {fps['U1']['pads'][13]['lx']},{fps['U1']['pads'][13]['ly']}  "
  f"pad15 {fps['U1']['pads'][14]['lx']},{fps['U1']['pads'][14]['ly']}  "
  f"pad28 {fps['U1']['pads'][27]['lx']},{fps['U1']['pads'][27]['ly']}")
w("")
w("Where does each BOARD pad sit, in stock-footprint terms?")
occ = {}
for k, (bx, by) in stock.items():
    hit = [q for q in fps['U1']['pads'] if abs(q['lx']-bx) < 1e-6 and abs(q['ly']-by) < 1e-6]
    if hit:
        occ[k] = hit[0]['pin']
w(f"  stock pin -> board pad : {occ}")
inv = {v: k for k, v in occ.items()}
w("  => board pad N sits where stock pin " +
  ", ".join(f"{n}->{inv[n]}" for n in sorted(inv, key=int)) +
  " sit, i.e. the footprint is the y-MIRROR of a stock DIP-28.")
w("  => no 180 deg rotation reproduces it (a rotation would put pad1 at x=+3.81).")
w("")

w('=' * 78)
w('D. Which ATmega328P-PU lead lands in which board pad, for every legal insertion')
w('   (ATmega328P-PU DIP-28 per Atmel/Microchip doc 8271I: 1 PC6/RESET 2 PD0 3 PD1 4 PD2')
w('    5 PD3 6 PD4 7 VCC 8 GND 9 PB6/XTAL1 10 PB7/XTAL2 11 PD5 12 PD6/AIN0 13 PD7/AIN1')
w('    14 PB0 15 PB1 16 PB2/SS 17 PB3/MOSI 18 PB4/MISO 19 PB5/SCK 20 AVCC 21 AREF 22 GND')
w('    23 PC0/ADC0 24 PC1/ADC1 25 PC2/ADC2 26 PC3/ADC3 27 PC4/ADC4 28 PC5/ADC5)')
w('=' * 78)
L28 = {1:'PC6/RESET',2:'PD0/RXD',3:'PD1/TXD',4:'PD2/D2',5:'PD3/D3',6:'PD4/D4',7:'VCC',
       8:'GND',9:'PB6/XTAL1',10:'PB7/XTAL2',11:'PD5',12:'PD6/AIN0',13:'PD7/AIN1',
       14:'PB0',15:'PB1',16:'PB2/SS',17:'PB3/MOSI',18:'PB4/MISO',19:'PB5/SCK',
       20:'AVCC',21:'AREF',22:'GND/AGND',23:'PC0/ADC0',24:'PC1/ADC1',25:'PC2/ADC2',
       26:'PC3/ADC3',27:'PC4/ADC4',28:'PC5/ADC5'}
# board pad -> hole position in board coords
holes = {q['pin']: (q['x'], q['y']) for q in fps['U1']['pads']}
netof = {q['pin']: q['net'] for q in fps['U1']['pads']}
left  = {p: holes[p] for p in holes if abs(holes[p][0]-16.51) < 1e-6}
right = {p: holes[p] for p in holes if abs(holes[p][0]-24.13) < 1e-6}
left_by_y  = sorted(left.items(),  key=lambda kv: kv[1][1])
right_by_y = sorted(right.items(), key=lambda kv: kv[1][1])

for rot, desc in ((0, 'chip pin1 at top-left (standard)'), (180, 'chip pin1 at bottom-right')):
    w(f"  --- chip inserted {rot} deg ({desc}) ---")
    w(f"      chip lead -> board pad -> board net   [board net of the LEAD, not the pad]")
    bad = []
    for cp in range(1, 29):
        if rot == 0:
            bp = (left_by_y[cp - 1][0] if cp <= 14 else right_by_y[28 - cp][0])
        else:
            bp = (right_by_y[14 - cp][0] if cp <= 14 else left_by_y[28 - cp][0])
        net = netof[bp]
        if net in ('VCC_5V', 'GND'):
            bad.append(f"chip pin {cp} ({L28[cp]}) -> board pad {bp} net {net}")
        if cp in (4, 5, 7, 8, 19, 20, 21, 22, 23, 1):
            w(f"      pin {cp:2} {L28[cp]:9} -> pad {bp:2} net '{net}'")
    w(f"      *** power pins landed on the wrong net: {len(bad)}")
    for b in bad:
        w(f"          {b}")
    w("")

w('=' * 78)
w('E. Every net: which pads carry it, and is there any copper on it?')
w('=' * 78)
segs = []
for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([-\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"', t):
    segs.append(dict(x1=float(m.group(1)), y1=float(m.group(2)), x2=float(m.group(3)),
                      y2=float(m.group(4)), w=float(m.group(5)), layer=m.group(6),
                      net=m.group(7)))
vias = []
for m in re.finditer(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)\s+\(size ([-\d.]+)\)\s+\(drill ([-\d.]+)\)\s+\(layers "([^"]+)" "([^"]+)"\)\s+\(net "([^"]+)"', t):
    vias.append(dict(x=float(m.group(1)), y=float(m.group(2)), net=m.group(7)))
nets = {}
for ref, f in fps.items():
    for q in f['pads']:
        if q['net']:
            nets.setdefault(q['net'], []).append(f"{ref}.{q['pin']}")
w(f"{'net':16} {'pads':46} {'segs':>5} {'vias':>5}  F.Cu/B.Cu")
for n in sorted(nets):
    ns = [s for s in segs if s['net'] == n]
    nv = [v for v in vias if v['net'] == n]
    w(f"{n:16} {','.join(nets[n])[:46]:46} {len(ns):>5} {len(nv):>5}  "
      f"{sorted(set(s['layer'] for s in ns))}")
w("")
w("nets with NO track and NO via at all:")
for n in sorted(nets):
    if not any(s['net'] == n for s in segs) and not any(v['net'] == n for v in vias):
        w(f"   {n}  -> {nets[n]}")
w("")
w("F.Cu net VCC_5V / GND track widths seen: "
  f"{sorted(set(s['w'] for s in segs if s['net'] in ('VCC_5V','GND')))}")
w("GND tracks on F.Cu: %d   GND tracks on B.Cu: %d"
  % (len([s for s in segs if s['net'] == 'GND' and s['layer'] == 'F.Cu']),
     len([s for s in segs if s['net'] == 'GND' and s['layer'] == 'B.Cu'])))
w(f"zone blocks: {t.count('(zone')}   filled_polygon blocks: {t.count('filled_polygon')}")
w("")
w('=' * 78)
w('F. Silkscreen / fab content')
w('=' * 78)
w(f"fp_line / fp_text / fp_circle count in board file: "
  f"{len(re.findall(r'\(fp_line', t))} / {len(re.findall(r'\(fp_text', t))} / "
  f"{len(re.findall(r'\(fp_circle', t))}")
w(f"gr_text (board silkscreen text): {len(re.findall(r'\(gr_text', t))}")
w("F.Silkscreen gerber D-code operations: 0   (see analysis of gerbers/)")
w("")
w('=' * 78)
w('G. Parts the request asked for, vs parts on the board')
w('=' * 78)
for ref, f in sorted(fps.items()):
    w(f"  {ref:4} {f['lib']:22} value='{f['value']}' mpn='{f['mpn']}'")
w("  request: 'reads a DHT22 sensor on a 2 metre cable with a 100 nF decoupling "
  "capacitor, drives a relay through a 2N2222A, and lights an LED on the same board'")
w("  -> LED on the board?       " + str(any('LED' in f['value'].upper() for f in fps.values())))
w("  -> 100 nF cap on board?    " + str(any('100N' in f['value'].upper().replace(' ', '')
                                             for f in fps.values())))
w("  -> C1 value                " + fps['C1']['value'] + ' / mpn ' + fps['C1']['mpn'])
w("  -> connector / terminal?   " + str(any('CONN' in f['lib'].upper() or 'HDR' in f['lib'].upper()
                                              or 'TERM' in f['lib'].upper() for f in fps.values())))
w("  -> relay contact pads with a net: " +
  str([f"K1.p{p['pin']}" for p in fps['K1']['pads'] if p['net']]))
w("  -> U2 (DHT22) fitted on-board; pads with no net: " +
  str([f"U2.p{p['pin']}" for p in fps['U2']['pads'] if not p['net']]))

open(OUT, 'w', encoding='utf-8').write("\n".join(L) + "\n")
print("\n".join(L))
