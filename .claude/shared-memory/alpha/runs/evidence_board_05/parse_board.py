"""Parse board_05.kicad_pcb and print, for every footprint, the absolute position and the
net of every pad.  This is the raw evidence for the pin/net findings."""
import json
import os
import re

PCB = r"C:\Users\KIIT\cursor-electronics\tests\fixtures\alpha_known_bad\artifacts\board_05\board_05.kicad_pcb"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pad_net_table.txt")


def tokenize(text):
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "()":
            out.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n:
                if text[j] == "\\":
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if text[j] == '"':
                    break
                buf.append(text[j])
                j += 1
            out.append(('str', "".join(buf)))
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and (not text[j].isspace()) and text[j] not in '()"':
                j += 1
            out.append(('sym', text[i:j]))
            i = j
    return out


def parse(text):
    toks = tokenize(text)
    pos = 0

    def rd():
        nonlocal pos
        t = toks[pos]
        pos += 1
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


def num(v):
    return float(v[1])


def find(node, key):
    for x in node:
        if isinstance(x, list) and x and x[0] == ('sym', key):
            return x
    return None


def findall(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == ('sym', key)]


tree = parse(open(PCB, encoding="utf-8").read())
board = tree[0]
lines = []

for fp in findall(board, "footprint"):
    lib = fp[1][1]
    at = find(fp, "at")
    ox, oy = num(at[1]), num(at[2])
    rot = num(at[3]) if len(at) > 3 else 0.0
    ref = val = None
    for p in findall(fp, "property"):
        nm = find(p, "name")
        if nm is None:
            continue
        key = nm[1][1]
        v = find(p, "value")
        if key == "Reference":
            ref = v[1][1]
        elif key == "Value":
            val = v[1][1]
    lines.append("FOOTPRINT %s  (%s)  ref=%s value=%s  at=(%.3f, %.3f) rot=%.1f"
                 % (lib, fp[2][1] if len(fp) > 2 else "", ref, val, ox, oy, rot))
    for pad in findall(fp, "pad"):
        numid = pad[1][1]
        pat = find(pad, "at")
        px, py = num(pat[1]), num(pat[2])
        net = find(pad, "net")
        if net is None:
            netname, netnum = "(no net)", "-"
        elif len(net) >= 3 and net[2][0] == "str":
            netname, netnum = net[2][1], net[1][1]
        else:
            netname, netnum = net[1][1], "-"
        size = find(pad, "size")
        drill = find(pad, "drill")
        lines.append("   pad %-3s abs=(%7.3f, %7.3f)  size=%sx%s drill=%s  net=%-18s (#%s)"
                     % (numid, ox + px, oy + py, size[1][1], size[2][1],
                        drill[1][1] if drill is not None else "-", netname, netnum))

for ln in lines:
    print(ln)
open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\nwritten to", OUT)
