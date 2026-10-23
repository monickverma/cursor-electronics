"""
kicad_export.py — Board IR -> a KiCad 10 project (.kicad_pcb, .kicad_pro, .kicad_dru).

Stage 3 of `reports/PCB verification implementation plan.md`. The board leaves
Circuit OS as plain text written here, then KiCad itself re-saves it
(`kicad_cli.round_trip`), so everything downstream — KiCad's DRC, the Gerbers,
the drill files — reads a board KiCad has loaded and rewritten in its own form.
A board KiCad cannot load or re-save is a bug in this file, never in the board.

WHY OUR OWN EMITTER
-------------------
KiCad's IPC API needs a running GUI on 9 and 10 and has no export calls, the
SWIG bindings go away in 11, and kiutils is GPL-3.0 with no stated support for
KiCad 10 (plan, decision 7). The subset written here is small: footprints with
pads, segments, vias, plane zones, rule areas for keepouts, the outline.

FRAME
-----
Board IR is millimetres, origin bottom-left, y up. KiCad is millimetres, y down.
One mapping, used by every writer and every reader of what KiCad writes back:

    X = x            Y = outline_h - y

No auxiliary origin is set, so every exported file (Gerber, drill, position,
IPC-D-356) shares this one frame (plan, stage 6).

DETERMINISM
-----------
Same board in, same bytes out: every uuid is a uuid5 of what the item is, and
nothing reads the clock. That is what lets a hash of the written board stand
for the board in a verdict.

What the file does NOT carry: diff-pair intent (KiCad keeps that in net names
and rules, not in the board) and silkscreen (none is generated, so none is
judged). Both are stated rather than faked.
"""
from __future__ import annotations

import json
import math
import uuid

from board_ir import Board, Component, Keepout, Pad, Track, Via
from footprints import th_drill

KICAD_VERSION = "10.0.1"        # the kicad-cli this writer was proven against
FILE_VERSION = 20260206         # header KiCad 10.0.1 writes on a re-save

_NS = uuid.UUID("6f0c3e9a-2b51-4c8e-9d3a-c1e0b5a7d401")

# Canonical copper names and their KiCad 10 layer ordinals: F.Cu 0, B.Cu 2,
# In<n>.Cu 2 + 2n.
_USER_LAYERS = [
    (9, "F.Adhes", "user", "F.Adhesive"), (11, "B.Adhes", "user", "B.Adhesive"),
    (13, "F.Paste", "user", None), (15, "B.Paste", "user", None),
    (5, "F.SilkS", "user", "F.Silkscreen"), (7, "B.SilkS", "user", "B.Silkscreen"),
    (1, "F.Mask", "user", None), (3, "B.Mask", "user", None),
    (17, "Dwgs.User", "user", "User.Drawings"), (19, "Cmts.User", "user", "User.Comments"),
    (25, "Edge.Cuts", "user", None), (27, "Margin", "user", None),
    (31, "F.CrtYd", "user", "F.Courtyard"), (29, "B.CrtYd", "user", "B.Courtyard"),
    (35, "F.Fab", "user", None), (33, "B.Fab", "user", None),
]


class ExportError(ValueError):
    """The Board IR holds something this writer cannot express faithfully."""


# ─────────────────────────────────────────────────────────────────────────────
# small helpers
# ─────────────────────────────────────────────────────────────────────────────
def _n(v: float) -> str:
    """A number as KiCad writes it: fixed point, no trailing zeros, no -0."""
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _uuid(*key) -> str:
    return str(uuid.uuid5(_NS, "|".join(str(k) for k in key)))


def to_kicad(board: Board, x: float, y: float) -> tuple[float, float]:
    """Board IR point -> KiCad point (see FRAME)."""
    return x, board.outline_h - y


def from_kicad(board: Board, X: float, Y: float) -> tuple[float, float]:
    """KiCad point -> Board IR point; the inverse of `to_kicad`."""
    return X, board.outline_h - Y


def copper_layers(board: Board) -> list[str]:
    """The board's copper layers in KiCad's names, top to bottom. A board with
    no layers declared is the two-layer default every netlist board starts as."""
    names = [l.name for l in board.layers] or ["F.Cu", "B.Cu"]
    for nm in names:
        if not (nm in ("F.Cu", "B.Cu") or
                (nm.startswith("In") and nm.endswith(".Cu") and nm[2:-3].isdigit())):
            raise ExportError(f"copper layer {nm!r} has no KiCad name")
    if names[0] != "F.Cu" or names[-1] != "B.Cu":
        raise ExportError(f"copper stack must run F.Cu .. B.Cu, got {names}")
    return names


def _ordinal(name: str) -> int:
    if name == "F.Cu":
        return 0
    if name == "B.Cu":
        return 2
    return 2 + 2 * int(name[2:-3])


# ─────────────────────────────────────────────────────────────────────────────
# .kicad_pcb
# ─────────────────────────────────────────────────────────────────────────────
def _header(board: Board, cu: list[str]) -> list[str]:
    out = ["(kicad_pcb",
           f"\t(version {FILE_VERSION})",
           '\t(generator "circuit_os")',
           f'\t(generator_version "{KICAD_VERSION[:4]}")',
           "\t(general", "\t\t(thickness 1.6)", "\t\t(legacy_teardrops no)", "\t)",
           '\t(paper "A4")',
           "\t(title_block", f"\t\t(title {_q(board.name)})", "\t)",
           "\t(layers"]
    for nm in cu:
        kind = "signal"
        ir = next((l for l in board.layers if l.name == nm), None)
        if ir is not None and ir.type in ("power", "mixed"):
            kind = "power" if ir.type == "power" else "mixed"
        out.append(f"\t\t({_ordinal(nm)} {_q(nm)} {kind})")
    for ordn, nm, kind, alias in _USER_LAYERS:
        out.append(f"\t\t({ordn} {_q(nm)} {kind}" + (f" {_q(alias)})" if alias else ")"))
    out += ["\t)",
            "\t(setup",
            "\t\t(pad_to_mask_clearance 0)",
            "\t\t(allow_soldermask_bridges_in_footprints no)",
            "\t\t(pcbplotparams",
            "\t\t\t(usegerberextensions no)",
            "\t\t\t(usegerberattributes yes)",
            "\t\t\t(usegerberadvancedattributes yes)",
            "\t\t\t(creategerberjobfile yes)",
            "\t\t\t(useauxorigin no)",
            '\t\t\t(outputdirectory "")',
            "\t\t)",
            "\t)"]
    return out


def _pad_lines(board: Board, c: Component, p: Pad, idx: int) -> list[str]:
    """One pad, in its footprint's local frame.

    KiCad stores a pad's position relative to its footprint, unrotated, and its
    angle as the absolute orientation. The IR's pads are absolute and axis
    aligned, so the local position is the absolute offset rotated back by the
    footprint angle, and the pad angle is 0. `kicad_cli.round_trip` checks this
    against KiCad's own placement of every pad."""
    PX, PY = to_kicad(board, p.x, p.y)
    FX, FY = to_kicad(board, c.x, c.y)
    dx, dy = PX - FX, PY - FY
    th = math.radians(c.rotation)
    # KiCad: absolute = F + R(local), R(t) = [[cos, sin], [-sin, cos]] in y-down
    lx = dx * math.cos(th) - dy * math.sin(th)
    ly = dx * math.sin(th) + dy * math.cos(th)
    if p.shape == "th":
        kind = "thru_hole"
        shape = "circle" if abs(p.w - p.h) < 1e-9 else "oval"
        layers = '"*.Cu" "*.Mask"'
        drill = f"\t\t\t(drill {_n(th_drill(p.w, p.h))})"
    else:
        kind = "smd"
        shape = "circle" if p.shape == "round" else "rect"
        side = p.layer.split(".")[0] if p.layer in ("F.Cu", "B.Cu") else None
        if side is None:
            raise ExportError(f"{p.ref}.{p.pin}: SMD pad on {p.layer!r}; "
                              f"KiCad SMD pads sit on F.Cu or B.Cu only")
        layers = f'"{side}.Cu" "{side}.Paste" "{side}.Mask"'
        drill = None
    out = [f"\t\t(pad {_q(p.pin)} {kind} {shape}",
           f"\t\t\t(at {_n(lx)} {_n(ly)})",
           f"\t\t\t(size {_n(p.w)} {_n(p.h)})"]
    if drill:
        out.append(drill)
    out.append(f"\t\t\t(layers {layers})")
    if p.net:
        out.append(f"\t\t\t(net {_q(p.net)})")
    out += [f'\t\t\t(uuid "{_uuid("pad", c.ref, p.pin, idx)}")', "\t\t)"]
    return out


def _footprint(board: Board, c: Component) -> list[str]:
    side = "B" if c.side == "bottom" else "F"
    FX, FY = to_kicad(board, c.x, c.y)
    lib = c.attrs.get("package", "CircuitOS")
    th = any(p.shape == "th" for p in c.pads)
    hw, hh = c.courtyard_w / 2, c.courtyard_h / 2
    out = [f'\t(footprint {_q("CircuitOS:" + str(lib))}',
           f'\t\t(layer "{side}.Cu")',
           f'\t\t(uuid "{_uuid("fp", c.ref)}")',
           f"\t\t(at {_n(FX)} {_n(FY)}" + (f" {_n(c.rotation)})" if c.rotation else ")")]
    for key, val, dy in (("Reference", c.ref, -hh - 1), ("Value", str(c.attrs.get("value") or c.attrs.get("mpn") or c.ref), hh + 1)):
        out += [f"\t\t(property {_q(key)} {_q(val)}",
                f"\t\t\t(at 0 {_n(dy)} {_n(c.rotation)})",
                f'\t\t\t(layer "{side}.Fab")',
                f'\t\t\t(uuid "{_uuid("prop", c.ref, key)}")',
                "\t\t\t(effects (font (size 1 1) (thickness 0.15))" +
                (" (justify mirror))" if side == "B" else ")"),
                "\t\t)"]
    if c.attrs.get("mpn"):
        out.append(f'\t\t(property "MPN" {_q(str(c.attrs["mpn"]))} (at 0 0 0) (layer "{side}.Fab") (hide yes)'
                   f' (uuid "{_uuid("prop", c.ref, "MPN")}") (effects (font (size 1 1))))')
    out.append(f"\t\t(attr {'through_hole' if th else 'smd'})")
    if c.courtyard_w > 0 and c.courtyard_h > 0:
        # Courtyard in the footprint frame. The IR's courtyard is axis aligned
        # in board space, so for a rotated part it is rotated back like a pad.
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        t = math.radians(c.rotation)
        loc = [(x * math.cos(t) - y * math.sin(t), x * math.sin(t) + y * math.cos(t))
               for x, y in corners]
        pts = " ".join(f"(xy {_n(x)} {_n(y)})" for x, y in loc)
        out += ["\t\t(fp_poly",
                f"\t\t\t(pts {pts})",
                "\t\t\t(stroke (width 0.05) (type solid))",
                "\t\t\t(fill no)",
                f'\t\t\t(layer "{side}.CrtYd")',
                f'\t\t\t(uuid "{_uuid("crtyd", c.ref)}")',
                "\t\t)"]
    for i, p in enumerate(c.pads):
        out += _pad_lines(board, c, p, i)
    out.append("\t)")
    return out


def _segments(board: Board, t: Track, ti: int) -> list[str]:
    out = []
    for si, (a, b) in enumerate(zip(t.points, t.points[1:])):
        if math.dist(a, b) < 1e-9:
            continue                           # KiCad drops zero-length segments
        A, B = to_kicad(board, *a), to_kicad(board, *b)
        out += ["\t(segment",
                f"\t\t(start {_n(A[0])} {_n(A[1])})",
                f"\t\t(end {_n(B[0])} {_n(B[1])})",
                f"\t\t(width {_n(t.width)})",
                f"\t\t(layer {_q(t.layer)})",
                f"\t\t(net {_q(t.net)})",
                f'\t\t(uuid "{_uuid("seg", ti, si)}")',
                "\t)"]
    return out


def _via(board: Board, v: Via, vi: int, cu: list[str]) -> list[str]:
    X, Y = to_kicad(board, v.x, v.y)
    return ["\t(via",
            f"\t\t(at {_n(X)} {_n(Y)})",
            f"\t\t(size {_n(v.diameter)})",
            f"\t\t(drill {_n(v.drill)})",
            f'\t\t(layers "{cu[0]}" "{cu[-1]}")',
            f"\t\t(net {_q(v.net)})",
            f'\t\t(uuid "{_uuid("via", vi)}")',
            "\t)"]


def _poly(pts: list[tuple[float, float]]) -> str:
    return " ".join(f"(xy {_n(x)} {_n(y)})" for x, y in pts)


def _outline_pts(board: Board) -> list[tuple[float, float]]:
    W, H = board.outline_w, board.outline_h
    return [(0, 0), (W, 0), (W, H), (0, H)]


def _plane_zone(board: Board, layer: str, net: str) -> list[str]:
    nc = board.net_class_for(net)
    return ["\t(zone",
            f"\t\t(net {_q(net)})",
            f"\t\t(layer {_q(layer)})",
            f'\t\t(uuid "{_uuid("plane", layer, net)}")',
            f"\t\t(name {_q('plane ' + net)})",
            "\t\t(hatch edge 0.5)",
            f"\t\t(connect_pads (clearance {_n(nc.clearance)}))",
            "\t\t(min_thickness 0.25)",
            "\t\t(filled_areas_thickness no)",
            "\t\t(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))",
            f"\t\t(polygon (pts {_poly(_outline_pts(board))}))",
            "\t)"]


def _keepout_zone(board: Board, k: Keepout, ki: int, cu: list[str]) -> list[str]:
    X0, Y0 = to_kicad(board, k.x, k.y + k.h)
    pts = [(X0, Y0), (X0 + k.w, Y0), (X0 + k.w, Y0 + k.h), (X0, Y0 + k.h)]
    na = "not_allowed"
    tracks = na if k.kind in ("wire", "all") else "allowed"
    vias = na if k.kind in ("via", "all") else "allowed"
    fps = na if k.kind in ("placement", "all") else "allowed"
    layers = " ".join(_q(l) for l in ([k.layer] if k.layer else cu))
    return ["\t(zone",
            f"\t\t(layers {layers})",
            f'\t\t(uuid "{_uuid("keepout", ki)}")',
            f"\t\t(name {_q(('keepout ' + k.reason).strip())})",
            "\t\t(hatch edge 0.5)",
            "\t\t(connect_pads (clearance 0))",
            "\t\t(min_thickness 0.25)",
            f"\t\t(keepout (tracks {tracks}) (vias {vias}) (pads allowed)"
            f" (copperpour {na if k.kind != 'placement' else 'allowed'}) (footprints {fps}))",
            f"\t\t(polygon (pts {_poly(pts)}))",
            "\t)"]


def write_pcb(board: Board) -> str:
    """The board as `.kicad_pcb` text. Raises ExportError when the IR holds
    something KiCad cannot represent as written here."""
    cu = copper_layers(board)
    for t in board.tracks:
        if t.layer not in cu:
            raise ExportError(f"track on {t.layer!r}, not a copper layer of this board")
    out = _header(board, cu)
    for c in sorted(board.components, key=lambda c: c.ref):
        out += _footprint(board, c)
    W, H = board.outline_w, board.outline_h
    out += ["\t(gr_rect",
            f"\t\t(start 0 0)",
            f"\t\t(end {_n(W)} {_n(H)})",
            "\t\t(stroke (width 0.05) (type solid))",
            "\t\t(fill no)",
            '\t\t(layer "Edge.Cuts")',
            f'\t\t(uuid "{_uuid("outline")}")',
            "\t)"]
    for ti, t in enumerate(board.tracks):
        out += _segments(board, t, ti)
    for vi, v in enumerate(board.vias):
        out += _via(board, v, vi, cu)
    for l in board.layers:
        if l.plane_net:
            out += _plane_zone(board, l.name, l.plane_net)
    for ki, k in enumerate(board.keepouts):
        out += _keepout_zone(board, k, ki, cu)
    out += ["\t(embedded_fonts no)", ")", ""]
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# .kicad_pro — net classes; without it KiCad silently runs its defaults
# ─────────────────────────────────────────────────────────────────────────────
def write_pro(board: Board, name: str, severities: dict[str, str] | None = None) -> str:
    """The sibling project file: net classes, net-class patterns, and the rule
    severities (the policy table decides those, `kicad_drc.SEVERITIES`)."""
    def cls(nm, tw, cl, vd, vdr, prio):
        return {"name": nm, "clearance": cl, "track_width": tw,
                "via_diameter": vd, "via_drill": vdr,
                "microvia_diameter": 0.3, "microvia_drill": 0.1,
                "diff_pair_gap": cl, "diff_pair_via_gap": cl, "diff_pair_width": tw,
                "bus_width": 12, "wire_width": 6, "line_style": 0,
                "pcb_color": "rgba(0, 0, 0, 0.000)",
                "schematic_color": "rgba(0, 0, 0, 0.000)",
                "tuning_profile": "", "priority": prio}
    default = next((n for n in board.net_classes if n.name.lower() == "default"), None)
    classes = [cls("Default",
                   default.track_width if default else 0.2,
                   default.clearance if default else 0.2,
                   default.via_diameter if default else 0.8,
                   default.via_drill if default else 0.4, 2147483647)]
    patterns = []
    for i, nc in enumerate(sorted((n for n in board.net_classes
                                   if n.name.lower() != "default"),
                                  key=lambda n: -n.priority)):
        classes.append(cls(nc.name, nc.track_width, nc.clearance,
                           nc.via_diameter, nc.via_drill, i))
        patterns += [{"netclass": nc.name, "pattern": n} for n in sorted(nc.nets)]
    pro = {
        "board": {"design_settings": {
            "defaults": {},
            "rule_severities": dict(sorted((severities or {}).items())),
            "rules": {"min_clearance": 0.0, "min_track_width": 0.0,
                      "min_via_diameter": 0.0, "min_through_hole_diameter": 0.0,
                      "min_via_annular_width": 0.0, "min_copper_edge_clearance": 0.0,
                      "min_hole_clearance": 0.0, "min_hole_to_hole": 0.0},
        }},
        "meta": {"filename": f"{name}.kicad_pro", "version": 3},
        "net_settings": {"classes": classes, "meta": {"version": 5},
                         "net_colors": None, "netclass_assignments": None,
                         "netclass_patterns": patterns},
    }
    return json.dumps(pro, indent=2) + "\n"
