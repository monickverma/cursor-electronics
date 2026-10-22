import re, json
STOCK = r"C:\Program Files\KiCad\10.0\share\kicad\footprints\Package_DIP.pretty\DIP-28_W7.62mm.kicad_mod"
PROD  = r"C:\Users\KIIT\cursor-electronics\tests\fixtures\alpha_known_bad\artifacts\board_02\board_02.kicad_pcb"

def pads_from_mod(path):
    t = open(path, encoding='utf-8', errors='replace').read()
    out = {}
    for m in re.finditer(r'\(pad "([^"]+)"\s+(\S+)\s+(\S+)\s*\(at ([-\d.]+) ([-\d.]+)', t):
        out[int(m.group(1))] = (float(m.group(4)), float(m.group(5)))
    return out, t

def prod_u1_pads():
    t = open(PROD, encoding='utf-8', errors='replace').read()
    i = t.index('(footprint "CircuitOS:DIP-28"')
    j = t.index('\n\t)', i)
    blk = t[i:j]
    out = {}
    for m in re.finditer(r'\(pad "([^"]+)"\s+(\S+)\s+(\S+)\s*\(at ([-\d.]+) ([-\d.]+)', blk):
        out[int(m.group(1))] = (float(m.group(4)), float(m.group(5)))
    return out, blk

stock, stxt = pads_from_mod(STOCK)
prod, pblk = prod_u1_pads()

# normalise: put pad 1 at origin, preserve handedness
def norm(d):
    ox, oy = d[1]
    return {k: (round(v[0]-ox, 4), round(v[1]-oy, 4)) for k, v in d.items()}

s, p = norm(stock), norm(prod)
mirror_y = {k: (v[0], -v[1]) for k, v in s.items()}
mirror_x = {k: (-v[0], v[1]) for k, v in s.items()}
rot180  = {k: (-v[0], -v[1]) for k, v in s.items()}

def same(a, b, tol=1e-6):
    return all(abs(a[k][0]-b[k][0]) < tol and abs(a[k][1]-b[k][1]) < tol for k in a)

print("STOCK DIP-28_W7.62mm (KiCad reference), pad1 at origin:")
for k in (1,2,13,14,15,16,27,28): print("   pad %-2d %s" % (k, s[k]))
print("PRODUCT CircuitOS:DIP-28, pad1 at origin:")
for k in (1,2,13,14,15,16,27,28): print("   pad %-2d %s" % (k, p[k]))
print()
print("product == stock          :", same(p, s))
print("product == stock mirrored in Y :", same(p, mirror_y))
print("product == stock mirrored in X :", same(p, mirror_x))
print("product == stock rotated 180  :", same(p, rot180))
print()
print("### stock silk (notch / pin-1 marker) ###")
for m in re.finditer(r'\(fp_line \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\)(.*?)\(layer "([^"]+)"', stxt, re.S):
    if m.group(6) in ("F.SilkS","F.Fab"):
        print("   %-8s (%.2f,%.2f)-(%.2f,%.2f)" % (m.group(6), float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))))
print()
print("### product silk for U1 ###")
print("   F.SilkS occurrences:", pblk.count("F.SilkS"))
