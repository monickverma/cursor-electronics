"""KiCad schematic generator — net labels only, no wire routing.

Net labels connect by name in KiCad's electrical rules check (ERC).
This is deterministic and correct without knowing pin coordinates from the
symbol library. Wire routing is Phase 3.

UNITS — READ THIS BEFORE CHANGING ANY CONSTANT
==============================================
The `.kicad_sch` format at (version 20230121) expresses every `(at x y)`
coordinate in MILLIMETRES, not mils. An A4 sheet is 297 x 210 mm.

A previous version of this file used `_START_X = 1000` with a comment claiming
"1 unit = 1 mil". That placed every element between 1000 and 2900 mm — roughly
1 to 3 METRES from the origin, i.e. 3 to 14 sheet-widths off the page. kicanvas
loaded the document correctly but showed an empty region of a giant sheet,
which rendered as a blank coloured rectangle in the browser.

Keep all geometry inside the A4 bounds defined below.

Elements are given deterministic UUIDs (uuid5 over circuit_id + element key) so
that identical IR input always produces a byte-identical schematic. That is
required by the project's "deterministic compilers" rule — a random uuid4 would
make the output unreproducible and untestable.

ANNOTATIONS
===========
The annotation layer (`core/annotations.py`) is merged here, after generation,
and only as text. A net name is written *beside* the node's label, never as
the label: in KiCad a label is connectivity, and an annotation that renamed or
merged a net would be an input to the design by the back door. Test points,
placement hints and comments sit next to the node or part they anchor to.
Design comments and orphaned annotations go in a block below the parts — an
orphan is shown, never dropped. With no annotations the output is
byte-identical to what it was without the layer.
"""

from __future__ import annotations

import math
import textwrap
import uuid
from typing import Dict, List, Sequence, Tuple

from core.annotations import Annotation, AnnotationKind, AnchorKind, attach
from core.ir_schema import CircuitIR, SignalType

# ── Sheet geometry, all values in MILLIMETRES (A4 = 297 x 210) ────────────────
_SHEET_W = 297.0
_SHEET_H = 210.0
_MARGIN = 20.0

# Net-label grid (top of sheet)
_LABEL_COLS = 4
_LABEL_COL_W = 62.0
_LABEL_ROW_H = 8.0

# Component boxes (below the net labels)
_COMP_COLS = 3
_COMP_COL_W = 85.0
_COMP_ROW_H = 34.0
_BOX_W = 42.0
_BOX_H = 20.0

_FONT = 1.27          # KiCad default text size in mm
_FONT_SMALL = 1.0
_STROKE = 0.254       # KiCad default line width in mm

# Deterministic UUID namespace for this generator
_NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


#: Inline annotation text is cut here to stay inside its column; the full text
#: is then repeated in the notes block.
_INLINE_CHARS = 56
_NOTE_ROW_H = 3.2
_BLOCK_CHARS = 110
_BLOCK_COL_W = 135.0
_BLOCK_COLUMNS = 2

_KIND_PREFIX = {
    AnnotationKind.NET_NAME.value: "net name",
    AnnotationKind.TEST_POINT.value: "test point",
    AnnotationKind.PLACEMENT_HINT.value: "placement",
    AnnotationKind.COMMENT.value: "note",
}


class KiCadSchematicGenerator:
    def generate(self, ir: CircuitIR, annotations: Sequence[Annotation] = ()) -> str:
        uid = _Uid(ir.circuit_id)
        report = attach(ir, annotations)
        by_anchor: Dict[Tuple[str, str], List[Annotation]] = {}
        for a in report.attached:
            key = "" if a.anchor.kind == AnchorKind.DESIGN.value else a.anchor.id
            by_anchor.setdefault((a.anchor.kind, key), []).append(a)
        block: List[str] = []           # lines for the notes block
        lines: List[str] = []

        lines.append('(kicad_sch (version 20230121) (generator circuit_os)')
        lines.append(f'  (uuid "{uid.of("sheet")}")')
        lines.append('  (paper "A4")')
        lines.append(f'  (title_block (title "{_esc(ir.intent)[:60]}")'
                     f' (date "") (rev "v{ir.version}"))')
        lines.append('')
        # Required by the format even when empty — we place no library symbols.
        lines.append('  (lib_symbols)')
        lines.append('')

        # ── Net labels, one per unique node ──────────────────────────────────
        node_positions: Dict[str, Tuple[float, float]] = {}
        for i, node in enumerate(ir.nodes):
            col = i % _LABEL_COLS
            row = i // _LABEL_COLS
            nx = _MARGIN + col * _LABEL_COL_W
            ny = _MARGIN + 5.0 + row * _LABEL_ROW_H
            node_positions[node.id] = (nx, ny)
            lines.append(_net_label(node.id, nx, ny, uid.of(f"label:{node.id}")))
            notes = by_anchor.get((AnchorKind.NODE.value, node.id), [])
            if notes:
                lines.append(_text(_inline(notes, block, node.id), nx, ny + 2.6, _FONT_SMALL,
                                   uid.of(f"ann:node:{node.id}")))

        lines.append('')

        # ── Power / ground symbols ───────────────────────────────────────────
        for node in ir.nodes:
            nx, ny = node_positions[node.id]
            if node.type == SignalType.POWER or node.type == "power":
                lines.append(_power_symbol("VCC", nx, ny - 4.0,
                                           uid.of(f"pwr:{node.id}")))
            elif node.type == SignalType.GROUND or node.type == "ground":
                lines.append(_power_symbol("GND", nx, ny + 4.0,
                                           uid.of(f"gnd:{node.id}")))

        lines.append('')

        # ── Component boxes ─────────────────────────────────────────────────
        label_rows = max(1, math.ceil(len(ir.nodes) / _LABEL_COLS))
        comp_base_y = _MARGIN + 5.0 + label_rows * _LABEL_ROW_H + 14.0

        for i, comp in enumerate(ir.components):
            col = i % _COMP_COLS
            row = i // _COMP_COLS
            cx = _MARGIN + col * _COMP_COL_W
            cy = comp_base_y + row * _COMP_ROW_H
            lines += _component_block(comp, ir, cx, cy, uid)
            notes = by_anchor.get((AnchorKind.COMPONENT.value, comp.id), [])
            if notes:
                lines.append(_text(_inline(notes, block, comp.id), cx, cy + _BOX_H + 3.0, _FONT_SMALL,
                                   uid.of(f"ann:comp:{comp.id}")))

        # ── Notes block: design comments, orphans, anything cut short above ──
        block += [f"{_KIND_PREFIX[a.kind]}: {_clean(a.text)}"
                  for a in by_anchor.get((AnchorKind.DESIGN.value, ""), [])]
        block += [f"ORPHANED {_KIND_PREFIX[a.kind]} on {a.anchor.kind} {a.anchor.id} "
                  f"(no longer in this design): {_clean(a.text)}" for a in report.orphaned]
        if block:
            comp_rows = max(1, math.ceil(len(ir.components) / _COMP_COLS))
            lines.append('')
            lines += _notes_block(block, comp_base_y + comp_rows * _COMP_ROW_H + 4.0, uid)

        lines.append('')
        lines.append(')')  # close kicad_sch
        return '\n'.join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

class _Uid:
    """Deterministic UUID factory — same circuit_id + key always yields the same
    UUID, so identical IR produces a byte-identical schematic."""

    def __init__(self, circuit_id: str) -> None:
        self._circuit_id = str(circuit_id)

    def of(self, key: str) -> str:
        return str(uuid.uuid5(_NS, f"{self._circuit_id}/{key}"))


def _esc(s: str) -> str:
    return str(s).replace('"', "'")


def _clean(text: str) -> str:
    """User text on one line, safe inside a KiCad string: no newlines, no bare backslash."""
    return " ".join(str(text).split()).replace("\\", "/")


def _inline(notes: Sequence[Annotation], block: List[str], anchor: str) -> str:
    """One line for everything anchored here; if cut, the full text goes to the block."""
    full = " · ".join(f"{_KIND_PREFIX[a.kind]}: {_clean(a.text)}" for a in notes)
    if len(full) <= _INLINE_CHARS:
        return full
    block.append(f"{anchor} — {full}")
    return full[:_INLINE_CHARS - 1] + "…"


def _notes_block(entries: Sequence[str], top: float, uid: "_Uid") -> List[str]:
    """
    The notes block: each entry wrapped, in up to two columns down to the
    sheet's bottom margin. If even that is not enough, the last row says how
    many rows did not fit — the sheet is A4, and the full list is always in
    the design's annotations. Short, never silent.
    """
    rows = [row for entry in entries
            for row in textwrap.wrap(entry, _BLOCK_CHARS, subsequent_indent="    ")]
    per_column = max(1, int((_SHEET_H - _MARGIN / 2 - top) // _NOTE_ROW_H))
    capacity = per_column * _BLOCK_COLUMNS
    if len(rows) > capacity:
        hidden = len(rows) - (capacity - 1)
        rows = rows[:capacity - 1] + [f"... and {hidden} more rows: the full list is in the design's "
                                      f"annotations"]
    out = [_text("Annotations", _MARGIN, top, _FONT, uid.of("ann:block"))]
    for k, row in enumerate(rows):
        column, line = divmod(k, per_column)
        out.append(_text(row, _MARGIN + column * _BLOCK_COL_W, top + (line + 1) * _NOTE_ROW_H,
                         _FONT_SMALL, uid.of(f"ann:block:{k}")))
    return out


def _fmt(v: float) -> str:
    """KiCad writes coordinates with at most 4 decimal places, no trailing zeros."""
    return f"{round(v, 4):g}"


def _net_label(name: str, x: float, y: float, uid: str) -> str:
    return (
        f'  (label "{_esc(name)}" (at {_fmt(x)} {_fmt(y)} 0) (fields_autoplaced yes)\n'
        f'    (effects (font (size {_FONT} {_FONT})) (justify left bottom))\n'
        f'    (uuid "{uid}"))'
    )


def _power_symbol(name: str, x: float, y: float, uid: str) -> str:
    return (
        f'  (global_label "{name}" (shape power_in) (at {_fmt(x)} {_fmt(y)} 0)\n'
        f'    (fields_autoplaced yes)\n'
        f'    (effects (font (size {_FONT} {_FONT})) (justify left))\n'
        f'    (uuid "{uid}"))'
    )


def _text(content: str, x: float, y: float, size: float, uid: str) -> str:
    return (
        f'  (text "{_esc(content)}" (at {_fmt(x)} {_fmt(y)} 0)\n'
        f'    (effects (font (size {size} {size})) (justify left bottom))\n'
        f'    (uuid "{uid}"))'
    )


def _rectangle(x1: float, y1: float, x2: float, y2: float, uid: str) -> str:
    return (
        f'  (rectangle (start {_fmt(x1)} {_fmt(y1)}) (end {_fmt(x2)} {_fmt(y2)})\n'
        f'    (stroke (width {_STROKE}) (type default))\n'
        f'    (fill (type none))\n'
        f'    (uuid "{uid}"))'
    )


def _component_block(comp, ir: CircuitIR, cx: float, cy: float,
                     uid: _Uid) -> List[str]:
    """A visible box per component, its ref/part number above it, and the net
    name of every connected pin listed inside."""
    lines: List[str] = []

    # Box outline — real graphics, so the component is actually visible.
    # The previous version emitted (no_connect) as a placeholder, which is
    # semantically wrong: (no_connect) marks a pin as intentionally unconnected
    # and makes KiCad's ERC misreport the design.
    lines.append(_rectangle(cx, cy, cx + _BOX_W, cy + _BOX_H,
                            uid.of(f"box:{comp.id}")))

    # Reference + part number above the box
    lines.append(_text(f'{comp.id}: {comp.part_number}', cx, cy - 1.5,
                       _FONT, uid.of(f"ref:{comp.id}")))

    # Connected net names inside the box, one per line
    pin_conns = [c for c in ir.connections if c.component_id == comp.id]
    for j, conn in enumerate(pin_conns):
        ty = cy + 4.0 + j * 3.2
        if ty > cy + _BOX_H - 1.0:      # box is full, stop rather than overflow
            break
        lines.append(_text(conn.node_id, cx + 2.0, ty, _FONT_SMALL,
                           uid.of(f"pin:{comp.id}:{conn.node_id}:{j}")))

    return lines
