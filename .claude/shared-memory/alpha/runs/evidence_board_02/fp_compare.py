"""Per-footprint geometry dump of board_02 + comparison against KiCad stock footprints.

The board's own library ("CircuitOS") is not installed, so the footprints cannot be
checked by KiCad against any library (that is the 8 lib_footprint_issues DRC reports).
Here I extract each footprint's pad geometry, courtyard and graphics straight out of
the .kicad_pcb, and compare it with the closest KiCad 10 stock footprint, deciding
whether the board's footprint is the stock one, a rotation of it, or a MIRROR of it.
"""
import json
import os
import re

K = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"
EV = r"C:\Users\KIIT\cursor-electronics\.claude\shared-memory\alpha\runs\evidence_board_02"
PCB = r"C:\Users\KIIT\cursor-electronics\tests\fixtures\alpha_known_bad\artifacts\board_02\board_02.kicad_pcb"

text = open(PCB, encoding="utf-8").read()


def split_footprints(t):
    out = []
    idx = 0
    while True:
        i = t.find('(footprint "', idx)
        if i < 0:
            break
        depth = 0
        j = i
        while j < len(t):
            if t[j] == '(':
                depth += 1
            elif t[j] == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(t[i:j + 1])
        idx = j
    return out


def parse_fp(blk):
    name = re.search(r'\(footprint "([^"]+)"', blk).group(1)
    at = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', blk)
    rot = float(at.group(3)) if at and at.group(3) else 0.0
    pads = []
    for m in re.finditer(
            r'\(pad "([^"]+)"\s+(\S+)\s+(\S+)\s*\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\s*'
            r'\(size ([-\d.]+) ([-\d.]+)\)\s*\(drill ([^)]*)\)', blk):
        drill = m.group(9).strip()
        d = None
        if drill:
            dm = re.match(r'([\d.]+)(?:\s*\((.*)\))?', drill)
            d = float(dm.group(1))
        pads.append(dict(num=m.group(1), type=m.group(2), shape=m.group(3),
                         x=float(m.group(4)), y=float(m.group(5)),
                         rot=float(m.group(6)) if m.group(6) else 0.0,
                         sx=float(m.group(7)), sy=float(m.group(8)), drill=d))
    crtyd = []
    for m in re.finditer(
            r'\(fp_poly \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\)(.*?)\(layer "([^"]+)"\)',
            blk, re.S):
        if m.group(6) == "F.CrtYd":
            crtyd.append([float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))])
    silk = len(re.findall(r'\(layer "F\.SilkS"\)', blk))
    fab = len(re.findall(r'\(layer "F\.Fab"\)', blk))
    return dict(name=name, at=(float(at.group(1)), float(at.group(2))), rot=rot,
                pads=pads, crtyd=crtyd, silk=silk, fab=fab, raw=blk)


def stock(rel):
    p = os.path.join(K, rel)
    if not os.path.exists(p):
        return None
    return parse_fp(open(p, encoding="utf-8", errors="replace").read())


def norm(pads, mirror_x=False, mirror_y=False):
    """pad positions normalised on pad 1, with optional mirroring"""
    ref = [p for p in pads if p["num"] == "1"]
    if not ref:
        return {}
    ox, oy = ref[0]["x"], ref[0]["y"]
    d = {}
    for p in pads:
        x, y = p["x"] - ox, p["y"] - oy
        if mirror_x:
            x = -x
        if mirror_y:
            y = -y
        d[p["num"]] = (round(x, 4), round(y, 4))
    return d


def same(a, b, tol=1e-6):
    if set(a) != set(b):
        return False
    return all(abs(a[k][0] - b[k][0]) < tol and abs(a[k][1] - b[k][1]) < tol for k in a)


board_fps = [parse_fp(b) for b in split_footprints(text)]
report = []
for fp in board_fps:
    print("=" * 72)
    print("%s   at %s  rotation %s" % (fp["name"], fp["at"], fp["rot"]))
    print("  silk graphics: %d   F.Fab graphics: %d   courtyard polys: %d"
          % (fp["silk"], fp["fab"], len(fp["crtyd"])))
    for c in fp["crtyd"]:
        w = abs(c[2] - c[0])
        h = abs(c[3] - c[1])
        print("  courtyard  (%.2f,%.2f)-(%.2f,%.2f)  = %.2f x %.2f mm" % (c[0], c[1], c[2], c[3], w, h))
    print("  pads:")
    for p in sorted(fp["pads"], key=lambda q: (q["y"], q["x"])):
        print("     %-3s %-7s %-6s at (%7.3f,%7.3f)  size %5.2fx%-5.2f drill %s"
              % (p["num"], p["type"], p["shape"], p["x"], p["y"], p["sx"], p["sy"], p["drill"]))
    # lead pitch along a row
    xs = sorted(set(round(p["x"], 3) for p in fp["pads"]))
    if len(xs) > 1:
        print("  x positions:", xs, " -> pitch", [round(xs[i + 1] - xs[i], 3) for i in range(len(xs) - 1)])
    ys = sorted(set(round(p["y"], 3) for p in fp["pads"]))
    if len(ys) > 1:
        print("  y positions:", ys, " -> pitch", [round(ys[i + 1] - ys[i], 3) for i in range(len(ys) - 1)])

    # stock comparison for the ones with a stock equivalent
    for cand in ("Package_TO_SOT_THT.pretty/TO-92_Inline.kicad_mod",
                 "Diode.pretty/DO-41_SOD81_P10.16mm.kicad_mod",
                 "Package_DIP.pretty/DIP-28_W7.62mm.kicad_mod"):
        s = stock(cand)
        if not s:
            continue
        b = norm(fp["pads"])
        t = norm(s["pads"])
        verdict = None
        if same(b, t):
            verdict = "IDENTICAL to stock"
        elif same(b, {k: (-v[0], v[1]) for k, v in t.items()}):
            verdict = "MIRRORED IN X vs stock"
        elif same(b, {k: (v[0], -v[1]) for k, v in t.items()}):
            verdict = "MIRRORED IN Y vs stock"
        elif same(b, {k: (-v[0], -v[1]) for k, v in t.items()}):
            verdict = "ROTATED 180 vs stock"
        if verdict:
            print("  vs %-55s : %s" % (cand, verdict))
            print("     stock pad1-relative:", {k: t[k] for k in sorted(t, key=lambda z: int(z) if z.isdigit() else 0)})
            print("     board pad1-relative:", {k: b[k] for k in sorted(b, key=lambda z: int(z) if z.isdigit() else 0)})
    report.append({k: v for k, v in fp.items() if k != "raw"})

json.dump(report, open(os.path.join(EV, "footprint_geometry.json"), "w", encoding="utf-8"), indent=1)
print("\nwrote footprint_geometry.json")
