"""Compare the Board IR's tracks to the emitted .kicad_pcb segments, and census widths.

Black-box: reads only the two files the product emitted in the board folder.
"""
import json
import re
from collections import Counter

BOARD = r"C:\Users\KIIT\cursor-electronics\tests\fixtures\alpha_known_bad\artifacts\board_01"
ir = json.load(open(BOARD + r"\board_ir.json", encoding="utf-8"))
txt = open(BOARD + r"\board_01.kicad_pcb", encoding="utf-8").read()

TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')


def parse(s):
    stack, cur = [], []
    for tk in TOK.findall(s):
        if tk == "(":
            new = []
            cur.append(new)
            stack.append(cur)
            cur = new
        elif tk == ")":
            cur = stack.pop()
        else:
            if tk.startswith('"'):
                tk = tk[1:-1]
            cur.append(tk)
    return cur[0]


root = parse(txt)


def kids(n, name):
    return [c for c in n if isinstance(c, list) and c and c[0] == name]


def first(n, name):
    k = kids(n, name)
    return k[0] if k else None


segs = []
for s in kids(root, "segment"):
    st, en, nn = first(s, "start"), first(s, "end"), first(s, "net")
    segs.append(dict(net=nn[1] if nn else "", layer=first(s, "layer")[1],
                     w=float(first(s, "width")[1]),
                     p1=(float(st[1]), float(st[2])), p2=(float(en[1]), float(en[2]))))

irt = []
for tr in ir["tracks"]:
    pts = tr["points"]
    for a, b in zip(pts, pts[1:]):
        irt.append(dict(net=tr.get("net", ""), layer=tr.get("layer", "F.Cu"),
                        w=float(tr.get("width", 0)),
                        p1=(a[0], a[1]), p2=(b[0], b[1])))

H = ir.get("outline_h", 45.72)


def flip(s):
    return dict(net=s["net"], layer=s["layer"], w=s["w"],
                p1=(s["p1"][0], H - s["p1"][1]), p2=(s["p2"][0], H - s["p2"][1]))


def same(a, b):
    return (a["net"] == b["net"] and a["layer"] == b["layer"]
            and abs(a["w"] - b["w"]) < 1e-6
            and max(abs(a["p1"][0] - b["p1"][0]), abs(a["p1"][1] - b["p1"][1]),
                    abs(a["p2"][0] - b["p2"][0]), abs(a["p2"][1] - b["p2"][1])) < 0.002)


print("IR tracks: %d   pcb segments: %d" % (len(irt), len(segs)))
un_pcb = [s for s in segs if not any(same(flip(s), i) for i in irt)]
un_ir = [i for i in irt if not any(same(flip(s), i) for s in segs)]
print("pcb segments with no matching IR track (after y-flip): %d" % len(un_pcb))
for s in un_pcb:
    print("    PCB:", s)
print("IR tracks with no matching pcb segment (after y-flip): %d" % len(un_ir))
for i in un_ir:
    print("    IR :", i)

n_nf = sum(1 for s in segs if any(same(s, i) for i in irt))
print("pcb segments matching an IR track WITHOUT the flip: %d" % n_nf)

print("\nwidth census (net, width) -> segment count")
for k, v in sorted(Counter((s["net"], s["w"]) for s in segs).items()):
    print("   %-18s w=%.2f  n=%d" % (k[0], k[1], v))
print("\nvia count: %d" % len(kids(root, "via")))
print("zone count: %d" % len(kids(root, "zone")))
print("footprints: %d" % len(kids(root, "footprint")))
