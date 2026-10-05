"""
scene3d.py — Board IR in, a normalised 3D scene out. Deterministic; no model runs here.

The browser does not read the Board IR and guess what a part looks like. This
module decides, once, in testable Python: the stack-up, every pad and plated
hole, every track and via, a body for every component, and where the DRC kernel
found problems. The viewer only draws what is in the scene.

    board_scene(board) -> dict        JSON-ready; same board, same scene

Coordinates are the Board IR's: millimetres, origin bottom-left, y up. z is
height, with the bottom copper at z = 0 and the top copper at z = board
thickness. Mapping to a renderer's axes is the renderer's job.

WHY PARAMETRIC BODIES
---------------------
A body is built from the package (an 0805 is 2.0 x 1.25 x 0.5 mm with tinned
ends), the way tscircuit and pcb-scene3d-viewer draw parts they have no model
for. No STEP files, no licences, nothing to download, and the body moves with
the IR. Real manufacturer models come later through `kicad-cli pcb export glb`.

A package with no body here is drawn as its courtyard box and marked
``"model": "generic"``. It is never passed off as the real part — the same rule
footprints.py follows: a missing answer is a question, a wrong one is a board
that arrives unusable.

Body dimensions are nominal package outlines (JEDEC / IPC-7351 nominal, and
the DHT22 and SRD relay datasheets' outlines), rounded to 0.05 mm. They are
for seeing the board, not for mechanical clearance checks.
"""
from __future__ import annotations

import math
import re

from board_ir import Board, Component, Pad
from kernel import drc

SCENE_VERSION = "1.0.0"

BOARD_THICKNESS_MM = 1.6
ANNULAR_RING_MM = 0.25          # footprints.TH_PAD = 0.8 mm drill + 2 x 0.25 mm ring
MIN_DRILL_MM = 0.3


# ─────────────────────────────────────────────────────────────────────────────
# What a part is: from the netlist's component type, else its designator
# ─────────────────────────────────────────────────────────────────────────────
_KINDS = {
    "microcontroller", "resistor", "capacitor", "led", "sensor", "relay",
    "transistor", "regulator", "transceiver", "modem", "connector", "crystal",
    "diode", "inductor", "opamp", "optocoupler",
}

# Designator prefixes, longest first so "LED" wins over "L".
_PREFIX_KIND = [
    ("LED", "led"), ("SW", "connector"), ("J", "connector"), ("P", "connector"),
    ("R", "resistor"), ("C", "capacitor"), ("D", "diode"), ("Q", "transistor"),
    ("L", "inductor"), ("Y", "crystal"), ("X", "crystal"), ("K", "relay"),
    ("U", "ic"),
]


def component_kind(c: Component) -> str:
    declared = str(c.attrs.get("type", "")).lower()
    if declared in _KINDS:
        return declared
    ref = c.ref.upper()
    for prefix, kind in _PREFIX_KIND:
        if re.fullmatch(rf"{prefix}\d+", ref):
            return kind
    return "ic"


# ─────────────────────────────────────────────────────────────────────────────
# Body models. Sizes are (along x, along y, height) in the footprint's own frame
# — the frame footprints.py lays its pads out in.
# ─────────────────────────────────────────────────────────────────────────────
_COLOURS = {
    "resistor": "#1f1f1f", "capacitor": "#b89a6a", "inductor": "#3a3a3a",
    "ic": "#1b1b1d", "transistor": "#1b1b1d", "diode": "#2a2a2a",
    "led": "#e0282e", "crystal": "#c7c9cc", "connector": "#151515",
    "relay": "#1d4fa3", "sensor": "#f2f2ee", "regulator": "#1b1b1d",
}

_CHIPS = {  # package: (length, width, height)
    "0402": (1.00, 0.50, 0.35), "0603": (1.60, 0.80, 0.45),
    "0805": (2.00, 1.25, 0.50), "1206": (3.20, 1.60, 0.55),
    "1210": (3.20, 2.50, 0.55),
}


def _chip(pkg: str, kind: str) -> dict:
    l, w, h = _CHIPS[pkg]
    if kind == "led":
        # chip LED: white package, a clear coloured lens on top
        return {"shape": "chip_led", "size": [l, w, h], "standoff": 0.0,
                "color": "#f4f4f0", "lens_color": _COLOURS["led"]}
    return {"shape": "chip", "size": [l, w, h], "standoff": 0.0,
            "color": _COLOURS.get(kind, "#1f1f1f"), "terminal_color": "#c9ccd1",
            "terminal_len": round(l * 0.2, 2)}


def _dip(n: int) -> dict:
    per = n // 2
    row = 15.24 if n >= 40 else 7.62
    return {"shape": "dip", "size": [row - 1.27, per * 2.54, 3.3], "standoff": 0.5,
            "color": _COLOURS["ic"], "pin1_mark": True, "lead_len": 3.3}


def _soic(n: int) -> dict:
    per = n // 2
    return {"shape": "gullwing", "size": [3.9, per * 1.27 - 0.1, 1.5], "standoff": 0.1,
            "color": _COLOURS["ic"], "pin1_mark": True}


def body_for(package: str | None, kind: str, c: Component) -> tuple[dict, str]:
    """Returns (body, model) where model is "parametric" or "generic"."""
    pkg = (package or "").upper()
    if pkg in _CHIPS:
        return _chip(pkg, kind), "parametric"
    if m := re.fullmatch(r"DIP-(\d+)", pkg):
        return _dip(int(m.group(1))), "parametric"
    if m := re.fullmatch(r"SOIC-(\d+)", pkg):
        return _soic(int(m.group(1))), "parametric"
    if pkg == "SOT-23":
        return {"shape": "gullwing", "size": [2.9, 1.3, 1.0], "standoff": 0.1,
                "color": _COLOURS["transistor"], "pin1_mark": False}, "parametric"
    if pkg == "SOD-123":
        # 2.7 x 1.6 x 1.1 body, cathode band toward pad 1 (-x)
        return {"shape": "sod", "size": [2.7, 1.6, 1.1], "standoff": 0.05,
                "color": _COLOURS["diode"], "band_color": "#c9ccd1",
                "terminal_color": "#c9ccd1"}, "parametric"
    if pkg == "TO-92":
        # flat face toward -y, round back toward +y; leads along x
        return {"shape": "to92", "size": [4.8, 3.8, 4.8], "standoff": 2.0,
                "color": _COLOURS["transistor"], "lead_len": 2.0}, "parametric"
    if pkg == "TO-220":
        return {"shape": "to220", "size": [10.0, 4.5, 9.0], "standoff": 3.0,
                "color": _COLOURS["regulator"], "tab_color": "#c9ccd1",
                "lead_len": 3.0}, "parametric"
    if pkg in ("DO-41", "AXIAL"):
        diode = pkg == "DO-41" or kind == "diode"
        return {"shape": "axial", "size": [5.2 if diode else 6.3, 2.6 if diode else 2.5,
                                           2.6 if diode else 2.5],
                "standoff": 0.6, "color": "#202020" if diode else "#c8b48a",
                "band_color": "#c9ccd1" if diode else "#8b5a2b",
                "lead_len": 0.6}, "parametric"
    if pkg == "RADIAL-2":
        if kind == "capacitor" and str(c.attrs.get("mpn", "")).upper().startswith(("ECA", "UVR", "EEU")):
            return {"shape": "radial_can", "size": [6.3, 6.3, 11.0], "standoff": 0.5,
                    "color": "#1d2a52", "sleeve_mark": "#c9ccd1"}, "parametric"
        return {"shape": "radial_disc", "size": [5.0, 2.5, 6.0], "standoff": 1.0,
                "color": "#d18a2c"}, "parametric"
    if pkg == "RELAY-SRD":
        return {"shape": "box", "size": [19.0, 15.5, 15.0], "standoff": 0.0,
                "color": _COLOURS["relay"]}, "parametric"
    if pkg == "DHT22":
        # 15.1 wide along the pin row, 7.7 deep, 25.1 tall (Aosong outline)
        return {"shape": "dht", "size": [7.7, 15.1, 25.1], "standoff": 1.0,
                "color": _COLOURS["sensor"], "lead_len": 1.0}, "parametric"
    if m := re.fullmatch(r"HEADER-(\d+)", pkg):
        n = int(m.group(1))
        mpn = str(c.attrs.get("mpn", "")).upper()
        if kind == "sensor" and re.search(r"DHT(11|22)|AM2302", mpn):
            # DHT22 outline: 15.1 wide along the pin row, 7.7 deep, 25.1 tall
            return {"shape": "dht", "size": [7.7, 15.1, 25.1], "standoff": 1.0,
                    "color": _COLOURS["sensor"], "lead_len": 1.0}, "parametric"
        # footprints.HEADER-n puts its pins along y
        return {"shape": "header", "size": [2.54, n * 2.54, 2.5], "standoff": 0.0,
                "color": _COLOURS["connector"], "pin_len": 6.0}, "parametric"
    return ({"shape": "box", "size": [round(c.courtyard_w, 2), round(c.courtyard_h, 2), 1.0],
             "standoff": 0.0, "color": "#5a5f66"}, "generic")


# ─────────────────────────────────────────────────────────────────────────────
# The scene
# ─────────────────────────────────────────────────────────────────────────────
def drill_for(pad: Pad) -> float:
    return round(max(MIN_DRILL_MM, min(pad.w, pad.h) - 2 * ANNULAR_RING_MM), 3)


def _r(v: float) -> float:
    return round(float(v), 4)


def board_scene(board: Board) -> dict:
    t = BOARD_THICKNESS_MM
    layer_z = {"F.Cu": t, "B.Cu": 0.0}

    components, pads, holes = [], [], []
    for c in sorted(board.components, key=lambda c: c.ref):
        kind = component_kind(c)
        pkg = c.attrs.get("package")
        body, model = body_for(pkg, kind, c)
        nets = sorted({p.net for p in c.pads if p.net})
        components.append({
            "ref": c.ref, "kind": kind, "package": pkg, "mpn": c.attrs.get("mpn"),
            "x": _r(c.x), "y": _r(c.y), "rotation": _r(c.rotation), "side": c.side,
            "courtyard": [_r(c.courtyard_w), _r(c.courtyard_h)],
            "body": body, "model": model, "nets": nets, "pins": len(c.pads),
            "locked": c.locked,
        })
        for p in sorted(c.pads, key=lambda p: (len(p.pin), p.pin)):
            through = p.shape == "th"
            entry = {"ref": c.ref, "pin": p.pin, "x": _r(p.x), "y": _r(p.y),
                     "w": _r(p.w), "h": _r(p.h), "net": p.net,
                     "shape": "round" if through else ("round" if p.shape == "round" else "rect"),
                     "through": through,
                     "layer": "both" if through else p.layer}
            if through:
                entry["drill"] = drill_for(p)
                holes.append({"x": _r(p.x), "y": _r(p.y), "d": entry["drill"],
                              "plated": True, "ref": c.ref, "pin": p.pin})
            pads.append(entry)

    tracks = [{"layer": tr.layer, "net": tr.net, "width": _r(tr.width),
               "z": layer_z.get(tr.layer, t),
               "points": [[_r(x), _r(y)] for x, y in tr.points]}
              for tr in board.tracks if len(tr.points) >= 2]
    vias = [{"x": _r(v.x), "y": _r(v.y), "net": v.net, "drill": _r(v.drill),
             "diameter": _r(v.diameter)} for v in board.vias]
    for v in board.vias:
        holes.append({"x": _r(v.x), "y": _r(v.y), "d": _r(v.drill), "plated": True,
                      "ref": None, "pin": None})

    violations = [{"rule": v.rule, "severity": v.severity, "detail": v.detail,
                   "x": _r(v.at[0]), "y": _r(v.at[1]), "nets": list(v.nets),
                   "measured": v.measured, "required": v.required}
                  for v in drc(board)]

    # Connections the router did not complete, drawn as ratsnest lines so an
    # unfinished board never looks finished.
    ratsnest = [{"net": c.net, "a": [_r(c.a[0]), _r(c.a[1])], "b": [_r(c.b[0]), _r(c.b[1])]}
                for c in board.unrouted()]

    planes = [{"layer": l.name, "net": l.plane_net, "z": layer_z.get(l.name, 0.0)}
              for l in board.layers if l.plane_net]

    return {
        "version": SCENE_VERSION,
        "units": "mm",
        "axes": "x right, y up (board plane), z out of the top copper",
        "name": board.name,
        "board": {"w": _r(board.outline_w), "h": _r(board.outline_h),
                  "thickness": t, "copper": 0.035,
                  "soldermask": "#1f6b3a", "silkscreen": "#f4f4ee",
                  "finish": "#d4b26a"},
        "layers": [{"name": l.name, "type": l.type, "z": layer_z.get(l.name)}
                   for l in board.layers],
        "planes": planes,
        "components": components,
        "pads": pads,
        "holes": holes,
        "tracks": tracks,
        "vias": vias,
        "drc": violations,
        "ratsnest": ratsnest,
        "stats": {
            "components": len(components),
            "generic_bodies": sum(1 for c in components if c["model"] == "generic"),
            "pads": len(pads), "holes": len(holes), "tracks": len(tracks),
            "vias": len(vias), "drc_errors": sum(1 for v in violations if v["severity"] == "error"),
            "unrouted": len(ratsnest),
        },
    }


if __name__ == "__main__":
    import json
    import sys
    from compile_board import compile_board

    path = sys.argv[1] if len(sys.argv) > 1 else "netlist_dht22.json"
    r = compile_board(json.load(open(path)))
    s = board_scene(r.board)
    print(json.dumps(s["stats"], indent=2))
    print(f"generic bodies: {[c['ref'] for c in s['components'] if c['model'] == 'generic']}")
