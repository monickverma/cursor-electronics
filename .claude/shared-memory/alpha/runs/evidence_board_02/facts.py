"""Consolidated evidence dump for the board_02 review (board folder only)."""
import json
import os
import re

ART = r"C:\Users\KIIT\cursor-electronics\tests\fixtures\alpha_known_bad\artifacts\board_02"
EV = r"C:\Users\KIIT\cursor-electronics\.claude\shared-memory\alpha\runs\evidence_board_02"
PCB = os.path.join(ART, "board_02.kicad_pcb")
PRO = os.path.join(ART, "board_02.kicad_pro")
IR = os.path.join(ART, "board_ir.json")

d = json.load(open(os.path.join(EV, "connectivity_analysis.json"), encoding="utf-8"))
pcb = open(PCB, encoding="utf-8").read()

print("### 1. components in the Board IR")
ir = json.load(open(IR, encoding="utf-8"))
for c in ir["components"]:
    print("   %-4s %-10s %-22s %s" % (c.get("ref"), c.get("package"), c.get("mpn", c.get("part_number", "")), c.get("value", "")))

print("\n### 2. nets in the Board IR and their pads")
for n, pads in sorted(ir.get("nets", {}).items()) if isinstance(ir.get("nets"), dict) else []:
    print("   %-18s %s" % (n, pads))

print("\n### 3. copper-graph components per net (from my own parser)")
for net, comps in d["net_components"].items():
    print("   %-18s %d component(s)" % (net, len(comps)))
    for c in comps:
        print("        %s" % ", ".join(c[:9]) + (" ..." if len(c) > 9 else ""))

print("\n### 4. the RELAY_CTRL break: every RELAY_CTRL segment, and the gaps")
rl = [t for t in d["tracks"] if t["net"] == "RELAY_CTRL"]
for t in rl:
    print("   seg (%.4f,%.4f)-(%.4f,%.4f) w=%.2f layer=%s" % (t["x0"], t["y0"], t["x1"], t["y1"], t["w"], t["layer"]))


def d_pt(t, x, y):
    dx, dy = t["x1"] - t["x0"], t["y1"] - t["y0"]
    L = (dx * dx + dy * dy) ** 0.5
    if L == 0:
        return 1e9
    tt = max(0.0, min(1.0, ((x - t["x0"]) * dx + (y - t["y0"]) * dy) / (dx * dx + dy * dy)))
    return ((x - (t["x0"] + tt * dx)) ** 2 + (y - (t["y0"] + tt * dy)) ** 2) ** 0.5


gaps = []
for i in range(len(rl)):
    for j in range(i + 1, len(rl)):
        a, b = rl[i], rl[j]
        best = 1e9
        for (px, py) in ((a["x0"], a["y0"]), (a["x1"], a["y1"])):
            for (qx, qy) in ((b["x0"], b["y0"]), (b["x1"], b["y1"])):
                best = min(best, ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5)
        if best < 0.001:
            gaps.append((best, a, b))
for g, a, b in sorted(gaps, key=lambda t: t[0]):
    print("   GAP %.6f mm between (%.4f,%.4f)-(%.4f,%.4f) and (%.4f,%.4f)-(%.4f,%.4f)"
          % (g, a["x0"], a["y0"], a["x1"], a["y1"], b["x0"], b["y0"], b["x1"], b["y1"]))

print("\n### 5. track widths per net vs the net class in the .kicad_pro")
pro = json.load(open(PRO, encoding="utf-8"))
for cls in pro.get("net_settings", {}).get("classes", []):
    print("   class %-10s clearance=%s track_width=%s patterns=%s"
          % (cls.get("name"), cls.get("clearance"), cls.get("track_width"), cls.get("patterns")))
for net in sorted(set(t["net"] for t in d["tracks"] if t["net"])):
    ws = sorted(set(round(t["w"], 3) for t in d["tracks"] if t["net"] == net))
    n = len([t for t in d["tracks"] if t["net"] == net])
    thin = len([t for t in d["tracks"] if t["net"] == net and t["w"] < 0.3])
    print("   %-18s %3d segments, widths %s, of which %d are below 0.3 mm" % (net, n, ws, thin))

print("\n### 6. design rules in the .kicad_pro")
for k, v in pro.get("design_settings", {}).get("rules", {}).items():
    print("   %-32s %s" % (k, v))
print("   rule_severities:", pro.get("design_settings", {}).get("rule_severities", {}))

print("\n### 7. zone and edge cuts")
for z in d["zones"]:
    print("   zone net=%s filled_polygon_present=%s polygon=%s" % (z["net"], z["filled"], z["pts"]))
for m in re.finditer(r'\(gr_rect \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\)(.*?)\(layer "([^"]+)"\)', pcb, re.S):
    print("   gr_rect (%.2f,%.2f)-(%.2f,%.2f) layer=%s" % (float(m.group(1)), float(m.group(2)),
                                                          float(m.group(3)), float(m.group(4)), m.group(6)))
print("   zone count in file:", len(re.findall(r'\(zone ', pcb)))
print("   filled_polygon blocks in file:", len(re.findall(r'\(filled_polygon', pcb)))

print("\n### 8. search the board for an LED, a connector, a crystal, a header")
for pat in (r'LED', r'led', r'CONN', r'Header', r'Terminal', r'XTAL', r'crystal', r'ICSP', r'Uno'):
    print("   %-10s in .kicad_pcb: %d   in board_ir.json: %d"
          % (pat, len(re.findall(pat, pcb)), len(re.findall(pat, open(IR, encoding='utf-8').read()))))

print("\n### 9. silkscreen / courtyard / pin-1 markers per footprint")
for m in re.finditer(r'\(footprint "([^"]+)"', pcb):
    print("   ", m.group(1))
print("   F.SilkS layer-table occurrences in file:", len(re.findall(r'\(layer "F\.SilkS"\)', pcb)))
print("   F.SilkS layer-table entries:", re.findall(r'\(layer "F\.SilkS"\)', pcb)[:2])
print("   fp_line/fp_poly/fp_arc blocks on F.SilkS:", len(re.findall(r'\(layer "F\.SilkS"\)', pcb)))
print("   pad shapes used:", sorted(set(p["shape"] for p in d["pads"])))

print("\n### 10. holes and annular rings")
for p in d["pads"]:
    if p["drill"]:
        pass
ann = sorted(set((round(p["sx"], 2), p["drill"], round((p["sx"] - p["drill"]) / 2, 3)) for p in d["pads"] if p["drill"]))
for a in ann:
    print("   pad %.2f mm, drill %.2f mm -> annular ring %.3f mm" % a)
