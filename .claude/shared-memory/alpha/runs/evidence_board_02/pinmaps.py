"""Extract pin maps from KiCad stock libraries (reference data, not product source)."""
import os, re, sys

K = r"C:\Program Files\KiCad\10.0\share\kicad"


def blocks(path, name):
    """return list of (symbol_name, text) for top-level symbols whose name matches"""
    txt = open(path, encoding='utf-8', errors='replace').read()
    out = []
    for m in re.finditer(r'\n\t\(symbol "([^"]+)"', txt):
        nm = m.group(1)
        if nm != name:
            continue
        # find matching close paren
        i = txt.index('(', m.start())
        depth = 0
        j = i
        while j < len(txt):
            if txt[j] == '(':
                depth += 1
            elif txt[j] == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append((nm, txt[i:j + 1]))
    return out


def pins(txt):
    """(number, name, type) triples"""
    res = []
    for m in re.finditer(r'\(pin\s+(\w+)\s+\w+.*?\(name\s+"([^"]*)".*?\(number\s+"([^"]*)"', txt, re.S):
        res.append((m.group(3), m.group(2), m.group(1)))
    return res


def show(libfile, name):
    p = os.path.join(K, "symbols", libfile)
    if not os.path.exists(p):
        print("  !! missing", p); return
    bs = blocks(p, name)
    if not bs:
        print("  symbol %s not found in %s" % (name, libfile)); return
    for nm, txt in bs:
        print("  %s : %s" % (nm, libfile))
        ps = pins(txt)
        for num, pname, ptype in sorted(ps, key=lambda t: int(t[0]) if t[0].isdigit() else 0):
            print("     pin %-3s %-14s %s" % (num, pname, ptype))


targets = [
    ("MCU_Microchip_ATmega.kicad_sym", ["ATmega328P-PU", "ATmega328P-PU", "ATmega328P"]),
    ("Transistor_BJT.kicad_sym", ["2N2222A", "2N2222A_Vishay", "2N3904", "Q_NPN_CBE", "Q_NPN_BEC"]),
    ("Device.kicad_sym", ["D", "D_Zener"]),
    ("Relay.kicad_sym", ["Relay_1SPDT"]),
]
for lib, names in targets:
    print("=" * 60)
    for n in names:
        show(lib, n)

# footprint comparison
def fp_pads(path, want=None):
    txt = open(path, encoding='utf-8', errors='replace').read()
    res = []
    for m in re.finditer(r'\(pad "([^"]+)"\s+(\S+)\s+(\S+)\s*\(at ([-\d.]+) ([-\d.]+)', txt):
        res.append((m.group(1), m.group(2), m.group(3), float(m.group(4)), float(m.group(5))))
    return res

print("=" * 60)
for f in ["Package_DIP.pretty/DIP-28_W7.62mm.kicad_mod"]:
    p = os.path.join(K, "footprints", f)
    print(f, "->", os.path.exists(p))
    if os.path.exists(p):
        for pd in fp_pads(p):
            print("   ", pd)
for f in ["Package_TO_SOT_THT.pretty/TO-92_Inline.kicad_mod",
          "Package_TO_SOT_THT.pretty/TO-92_Inline_Horizontal.kicad_mod"]:
    p = os.path.join(K, "footprints", f)
    print(f, "->", os.path.exists(p))
    if os.path.exists(p):
        for pd in fp_pads(p):
            print("   ", pd)
