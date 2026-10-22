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

SYMBOLS, NOT BOXES (2026-10-21, finding F-S2-R001-3)
===================================================
Until 2026-10-21 each part was a drawn rectangle with text, the nets were a
grid of labels touching nothing, and power was a `global_label` with
`(shape power_in)`, a shape KiCad does not have. KiCad 10.0.1 refused to load
the file (`kicad-cli sch erc` exit 3), and even patched it held no symbol, so
ERC and netlist export saw an empty design.

Now every part is a real symbol, embedded in `lib_symbols` (no library lookup,
so still deterministic): a body with one passive pin per distinct pin the IR
connects, the pin's number and name both the IR's pin name. A net label sits on
each pin's end, so connectivity is still by net label only, with no wires, and
KiCad's own netlist export reproduces the IR's connections exactly
(tests/test_schematic_erc.py). Pins are `passive` because the IR does not
record electrical pin types; ERC therefore checks connectivity, not drive.
Every connection point is on the 1.27 mm grid KiCad connects on.

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
from core.ir_schema import CircuitIR

# ── Sheet geometry, all values in MILLIMETRES (A4 = 297 x 210) ────────────────
_SHEET_W = 297.0
_SHEET_H = 210.0
_MARGIN = 20.0

# Net-label grid (top of sheet)
_LABEL_COLS = 4
_LABEL_COL_W = 62.0
_LABEL_ROW_H = 8.0

# Symbols (below the net legend). KiCad connects only on its 1.27 mm grid.
_GRID = 1.27
_COMP_COLS = 3
_COMP_COL_W = 87.63              # 69 grid steps
_PIN_PITCH = 2.54
_PIN_LEN = 2.54
_BODY_HW = 7.62                  # half the symbol body's width
_PIN_REACH = _BODY_HW + _PIN_LEN + 22.0   # room left of the body for pin labels
_ROW_GAP = 7.62

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

        sheet = uid.of("sheet")
        lines.append('(kicad_sch (version 20230121) (generator circuit_os)')
        lines.append(f'  (uuid "{sheet}")')
        lines.append('  (paper "A4")')
        lines.append(f'  (title_block (title "{_esc(ir.intent)[:60]}")'
                     f' (date "") (rev "v{ir.version}"))')
        lines.append('')
        pins_of = _pins_by_component(ir)
        lines.append('  (lib_symbols')
        for comp in ir.components:
            lines += _lib_symbol(comp, pins_of[comp.id])
        lines.append('  )')
        lines.append('')

        # ── Net legend: each node's name, with its annotations beside it ─────
        # Plain text, not labels: a label touching nothing is a dangling net.
        for i, node in enumerate(ir.nodes):
            col = i % _LABEL_COLS
            row = i // _LABEL_COLS
            nx = _MARGIN + col * _LABEL_COL_W
            ny = _MARGIN + 5.0 + row * _LABEL_ROW_H
            lines.append(_text(f"net {node.id}", nx, ny, _FONT, uid.of(f"label:{node.id}")))
            notes = by_anchor.get((AnchorKind.NODE.value, node.id), [])
            if notes:
                lines.append(_text(_inline(notes, block, node.id), nx, ny + 2.6, _FONT_SMALL,
                                   uid.of(f"ann:node:{node.id}")))

        lines.append('')

        # ── Symbols, a net label on the end of every pin ─────────────────────
        label_rows = max(1, math.ceil(len(ir.nodes) / _LABEL_COLS))
        top = _snap(_MARGIN + 5.0 + label_rows * _LABEL_ROW_H + 6.0)
        for r0 in range(0, len(ir.components), _COMP_COLS):
            row = ir.components[r0:r0 + _COMP_COLS]
            h = max(_body_h(len(pins_of[c.id])) for c in row)
            cy = _snap(top + 2.54 + h / 2)
            for j, comp in enumerate(row):
                cx = _snap(_MARGIN + _PIN_REACH + j * _COMP_COL_W)
                lines += _symbol_instance(comp, pins_of[comp.id], cx, cy, sheet, uid)
                notes = by_anchor.get((AnchorKind.COMPONENT.value, comp.id), [])
                if notes:
                    lines.append(_text(_inline(notes, block, comp.id), cx - _BODY_HW,
                                       cy + h / 2 + 4.0, _FONT_SMALL,
                                       uid.of(f"ann:comp:{comp.id}")))
            top = _snap(cy + h / 2 + _ROW_GAP)

        # ── Notes block: design comments, orphans, anything cut short above ──
        block += [f"{_KIND_PREFIX[a.kind]}: {_clean(a.text)}"
                  for a in by_anchor.get((AnchorKind.DESIGN.value, ""), [])]
        block += [f"ORPHANED {_KIND_PREFIX[a.kind]} on {a.anchor.kind} {a.anchor.id} "
                  f"(no longer in this design): {_clean(a.text)}" for a in report.orphaned]
        if block:
            lines.append('')
            lines += _notes_block(block, top, uid)

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


def _text(content: str, x: float, y: float, size: float, uid: str) -> str:
    return (
        f'  (text "{_esc(content)}" (at {_fmt(x)} {_fmt(y)} 0)\n'
        f'    (effects (font (size {size} {size})) (justify left bottom))\n'
        f'    (uuid "{uid}"))'
    )


def _snap(v: float) -> float:
    return round(round(v / _GRID) * _GRID, 4)


def _body_h(npins: int) -> float:
    return max(2, npins + 1) * _PIN_PITCH


def _pins_by_component(ir: CircuitIR) -> Dict[str, List[Tuple[str, List[str]]]]:
    """Each component's distinct pins in first-seen order, with the node(s)
    each one connects to. A pin on two nodes gets a label for each; KiCad then
    shows those nets joined, which is what the IR says."""
    out: Dict[str, List[Tuple[str, List[str]]]] = {c.id: [] for c in ir.components}
    for conn in ir.connections:
        pins = out.setdefault(conn.component_id, [])
        for name, nodes in pins:
            if name == conn.pin:
                if conn.node_id not in nodes:
                    nodes.append(conn.node_id)
                break
        else:
            pins.append((conn.pin, [conn.node_id]))
    return out


def _prefix(ref: str) -> str:
    letters = "".join(ch for ch in ref if ch.isalpha())
    return letters or "U"


def _pin_y(i: int, n: int) -> float:
    """Pin i's y in the symbol's own frame (y up), centred on the body."""
    return round(((n - 1) / 2 - i) * _PIN_PITCH, 4)


def _lib_symbol(comp, pins) -> List[str]:
    """The part's own symbol, embedded: a body and one passive pin per pin."""
    name = _esc(comp.id)
    hh = _body_h(len(pins)) / 2
    out = [f'    (symbol "CircuitOS:{name}" (pin_names (offset 0.508)) (in_bom yes) (on_board yes)',
           f'      (property "Reference" "{_prefix(comp.id)}" (at 0 {_fmt(hh + 1.27)} 0)'
           f' (effects (font (size {_FONT} {_FONT}))))',
           f'      (property "Value" "{_esc(comp.part_number)}" (at 0 {_fmt(-hh - 1.27)} 0)'
           f' (effects (font (size {_FONT} {_FONT}))))',
           f'      (property "Footprint" "" (at 0 0 0) (effects (font (size {_FONT} {_FONT})) hide))',
           f'      (property "Datasheet" "" (at 0 0 0) (effects (font (size {_FONT} {_FONT})) hide))',
           f'      (symbol "{name}_0_1"',
           f'        (rectangle (start {_fmt(-_BODY_HW)} {_fmt(hh)}) (end {_fmt(_BODY_HW)} {_fmt(-hh)})',
           f'          (stroke (width {_STROKE}) (type default)) (fill (type background))))',
           f'      (symbol "{name}_1_1"']
    for i, (pin, _) in enumerate(pins):
        out.append(f'        (pin passive line (at {_fmt(-_BODY_HW - _PIN_LEN)} {_fmt(_pin_y(i, len(pins)))} 0)'
                   f' (length {_fmt(_PIN_LEN)})'
                   f' (name "{_esc(pin)}" (effects (font (size {_FONT_SMALL} {_FONT_SMALL}))))'
                   f' (number "{_esc(pin)}" (effects (font (size {_FONT_SMALL} {_FONT_SMALL})))))')
    out += ['      )', '    )']
    return out


def _symbol_instance(comp, pins, cx: float, cy: float, sheet: str,
                     uid: _Uid) -> List[str]:
    """The placed symbol, then a net label on the end of each of its pins."""
    hh = _body_h(len(pins)) / 2
    value = comp.value or comp.part_number
    out = [f'  (symbol (lib_id "CircuitOS:{_esc(comp.id)}") (at {_fmt(cx)} {_fmt(cy)} 0) (unit 1)',
           '    (in_bom yes) (on_board yes) (dnp no)',
           f'    (uuid "{uid.of("sym:" + comp.id)}")',
           f'    (property "Reference" "{_esc(comp.id)}" (at {_fmt(cx)} {_fmt(cy - hh - 1.27)} 0)'
           f' (effects (font (size {_FONT} {_FONT}))))',
           f'    (property "Value" "{_esc(value)}" (at {_fmt(cx)} {_fmt(cy + hh + 1.27)} 0)'
           f' (effects (font (size {_FONT} {_FONT}))))',
           f'    (property "Footprint" "" (at {_fmt(cx)} {_fmt(cy)} 0)'
           f' (effects (font (size {_FONT} {_FONT})) hide))',
           f'    (property "Datasheet" "" (at {_fmt(cx)} {_fmt(cy)} 0)'
           f' (effects (font (size {_FONT} {_FONT})) hide))',
           # The package is not a KiCad footprint id; the board writer
           # (pcb_engine/kicad_export.py) owns footprints, so it is kept apart.
           f'    (property "Package" "{_esc(comp.package)}" (at {_fmt(cx)} {_fmt(cy)} 0)'
           f' (effects (font (size {_FONT} {_FONT})) hide))',
           f'    (property "MPN" "{_esc(comp.part_number)}" (at {_fmt(cx)} {_fmt(cy)} 0)'
           f' (effects (font (size {_FONT} {_FONT})) hide))']
    for pin, _ in pins:
        out.append(f'    (pin "{_esc(pin)}" (uuid "{uid.of("pin:" + comp.id + ":" + pin)}"))')
    out += ['    (instances',
            f'      (project "circuit_os" (path "/{sheet}" (reference "{_esc(comp.id)}") (unit 1))))',
            '  )']
    # Schematic y runs down; the symbol's own frame runs up.
    px = _fmt(cx - _BODY_HW - _PIN_LEN)
    for i, (pin, nodes) in enumerate(pins):
        py = _fmt(cy - _pin_y(i, len(pins)))
        for node in nodes:
            out.append(f'  (label "{_esc(node)}" (at {px} {py} 180) (fields_autoplaced yes)\n'
                       f'    (effects (font (size {_FONT} {_FONT})) (justify right bottom))\n'
                       f'    (uuid "{uid.of("label:" + comp.id + ":" + pin + ":" + node)}"))')
    return out
