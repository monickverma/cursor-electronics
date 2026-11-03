"""S2 bench-judge: gap metrics for a board the product emitted, next to its reference.

Reads only files the product emitted (generate.json, pcb_compile.json, erc.json) and the
corpus reference_metrics.json. Usage: python -I board_metrics.py <run_dir> <corpus_ref_dir>
Writes board_metrics.json into <run_dir> and prints a short summary.
"""
import json
import math
import os
import sys

GROUND = ("GND", "AGND", "DGND", "PGND", "VSS", "0V")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def track_length(points):
    total = 0.0
    for a, b in zip(points, points[1:]):
        ax, ay = (a["x"], a["y"]) if isinstance(a, dict) else a
        bx, by = (b["x"], b["y"]) if isinstance(b, dict) else b
        total += math.hypot(bx - ax, by - ay)
    return total


def main(run, ref_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    pcb = load(os.path.join(run, "pcb_compile.json"))["body"]
    board, stats = pcb["board"], pcb["stats"]
    pads = [dict(p, ref=c["ref"]) for c in board["components"] for p in c["pads"]]
    ics = [p for p in pads if p["ref"].startswith(("U", "IC"))]

    # Decoupling: same rule as the corpus metric (C<n>, two pads, one on ground; centre to centre
    # from the rail pad to the nearest U/IC pad on that rail), plus the distance to every IC power pin.
    decoupling = []
    for c in board["components"]:
        if not c["ref"].startswith("C") or len(c["pads"]) != 2:
            continue
        nets = [p["net"] for p in c["pads"]]
        if not any(n.upper() in GROUND for n in nets):
            continue
        rail = next(p for p in c["pads"] if p["net"].upper() not in GROUND)
        same = [p for p in ics if p["net"] == rail["net"]]
        if not same:
            continue
        dist = {f'{p["ref"]}.{p["pin"]}': round(math.hypot(p["x"] - rail["x"], p["y"] - rail["y"]), 3)
                for p in same}
        nearest = min(dist, key=dist.get)
        decoupling.append({"cap": c["ref"], "net": rail["net"], "nearest": nearest,
                           "distance_mm": dist[nearest], "to_each_power_pin_mm": dist})

    widths = {}
    length = 0.0
    for t in board["tracks"]:
        length += track_length(t["points"])
        widths.setdefault(t["net"], set()).add(t["width"])

    ours = {
        "copper_layers": len(board["layers"]),
        "outline_mm": [board["outline_w"], board["outline_h"]],
        "area_mm2": round(board["outline_w"] * board["outline_h"], 2),
        "parts": len(board["components"]),
        "vias": len(board["vias"]),
        "track_length_mm": round(length, 2),
        "track_widths_mm_by_net": {k: sorted(v) for k, v in widths.items()},
        "routed": stats.get("routed"), "unrouted": stats.get("unrouted"),
        "drc_errors_product": stats.get("drc_errors"),
        "verification_ok": (pcb.get("verification") or {}).get("ok"),
        "verification_failed": [f["check"] for f in (pcb.get("verification") or {}).get("findings", [])
                                if f.get("status") == "fail"],
        "kicad_export": "kicad" in pcb,
        "decoupling": decoupling,
    }
    erc = os.path.join(run, "erc.json")
    ours["kicad_erc"] = (f'{len([v for s in load(erc).get("sheets", []) for v in s.get("violations", [])])} violations'
                         if os.path.exists(erc) else "schematic failed to load")

    ref = load(os.path.join(ref_dir, "reference_metrics.json"))["board"]
    rb = {"copper_layers": ref["copper_layers"], "area_mm2": ref["outline"]["bbox_area_mm2"],
          "parts": ref["bom_parts"], "vias": ref["vias"]["count"],
          "track_length_mm": ref["tracks"]["length_mm_total"],
          "decoupling_max_mm": ref["decoupling"].get("max_mm")}
    dec = max((d["distance_mm"] for d in decoupling), default=None)
    gaps = {
        "area_ratio": round(ours["area_mm2"] / rb["area_mm2"], 2),
        "area_pass": ours["area_mm2"] <= 1.3 * rb["area_mm2"],
        "via_ratio": round(ours["vias"] / rb["vias"], 2) if rb["vias"] else None,
        "track_ratio": round(ours["track_length_mm"] / rb["track_length_mm"], 2) if rb["track_length_mm"] else None,
        "vias_tracks_pass": (ours["vias"] <= 1.5 * rb["vias"] if rb["vias"] else ours["vias"] == 0)
                            and ours["track_length_mm"] <= 1.5 * rb["track_length_mm"],
        "decoupling_max_mm": dec,
        "decoupling_pass": None if dec is None else
            dec <= 6 and (rb["decoupling_max_mm"] is None or dec <= rb["decoupling_max_mm"] + 2),
        "routing_complete": ours["unrouted"] == 0,
    }
    out = {"ours": ours, "reference": rb, "gaps": gaps}
    with open(os.path.join(run, "board_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({"ours": {k: v for k, v in ours.items() if k not in ("decoupling", "track_widths_mm_by_net")},
                      "reference": rb, "gaps": gaps}))
    print("decoupling", json.dumps(decoupling))
    print("widths", json.dumps(ours["track_widths_mm_by_net"]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
