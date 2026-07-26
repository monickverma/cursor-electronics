"""
KiCadSchematicGenerator tests.

Why this file exists
--------------------
This generator shipped without a test file and was marked `untested` in
progress.yaml. It was emitting coordinates in mils while the .kicad_sch format
at (version 20230121) expects MILLIMETRES, so every element landed 1–3 metres
from the origin — 3 to 14 A4 sheet-widths off the page. kicanvas parsed the
document fine but displayed an empty region of a giant sheet, which appeared in
the browser as a solid coloured rectangle.

The on-page bounds test below is the regression guard for that class of bug.

What is verified:
- Every coordinate stays inside the A4 sheet (297 x 210 mm)
- Output is deterministic: identical IR yields byte-identical output
- Structural validity: balanced parens, required top-level format tokens
- Every node produces a net label; every component produces a box and a ref
- (no_connect) is NOT used as a component placeholder (breaks KiCad ERC)
"""

import re

import pytest

from core.ir_examples import IR_001, IR_002, IR_003, IR_004, IR_005, ALL_EXAMPLES
from generators.schematic.kicad import KiCadSchematicGenerator

# A4 sheet, millimetres — must match the constants in kicad.py
SHEET_W = 297.0
SHEET_H = 210.0

_COORD_RE = re.compile(r'\((?:at|start|end) (-?[\d.]+) (-?[\d.]+)')


@pytest.fixture
def gen():
    return KiCadSchematicGenerator()


def _coords(text: str):
    return [(float(x), float(y)) for x, y in _COORD_RE.findall(text)]


# ── Geometry — the regression guard ──────────────────────────────────────────

@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_all_coordinates_fit_on_a4_sheet(gen, ir):
    """Every coordinate must land inside the A4 page.

    This is the test that would have caught the mils/millimetres bug.
    """
    out = gen.generate(ir)
    coords = _coords(out)
    assert coords, "generator emitted no coordinates at all"

    for x, y in coords:
        assert 0 <= x <= SHEET_W, f"x={x} outside A4 width {SHEET_W}mm"
        assert 0 <= y <= SHEET_H, f"y={y} outside A4 height {SHEET_H}mm"


@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_coordinates_are_millimetre_scale(gen, ir):
    """Guard against a regression back to mil-scale constants.

    Mil-scale output put the maximum coordinate in the thousands. Anything
    above one sheet-width means the units are wrong again.
    """
    out = gen.generate(ir)
    max_coord = max(max(x, y) for x, y in _coords(out))
    assert max_coord <= SHEET_W, (
        f"max coordinate {max_coord} exceeds a full sheet — "
        "constants have probably reverted to mils"
    )


# ── Determinism ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_output_is_deterministic(gen, ir):
    """Identical IR must yield byte-identical output.

    UUIDs are uuid5-derived from circuit_id, not random uuid4, precisely so
    this holds. Required by the 'deterministic compilers' rule.
    """
    assert gen.generate(ir) == gen.generate(ir)


def test_different_circuits_get_different_uuids(gen):
    a = gen.generate(IR_001)
    b = gen.generate(IR_002)
    uuid_re = re.compile(r'\(uuid "([0-9a-f-]{36})"\)')
    assert set(uuid_re.findall(a)).isdisjoint(uuid_re.findall(b))


# ── Structure ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_parens_balanced(gen, ir):
    out = gen.generate(ir)
    assert out.count('(') == out.count(')')


@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_required_format_tokens_present(gen, ir):
    out = gen.generate(ir)
    assert out.startswith('(kicad_sch')
    assert '(version 20230121)' in out
    assert '(generator circuit_os)' in out
    assert '(paper "A4")' in out
    assert '(lib_symbols)' in out
    assert '(title_block' in out
    assert out.rstrip().endswith(')')


@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_every_node_gets_a_net_label(gen, ir):
    out = gen.generate(ir)
    for node in ir.nodes:
        assert f'(label "{node.id}"' in out, f"no net label for node {node.id}"


@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_every_component_gets_a_box_and_reference(gen, ir):
    out = gen.generate(ir)
    assert out.count('(rectangle') >= len(ir.components), (
        "each component needs a visible box"
    )
    for comp in ir.components:
        assert f'{comp.id}: {comp.part_number}' in out, (
            f"no reference text for component {comp.id}"
        )


@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_no_connect_not_used_as_placeholder(gen, ir):
    """(no_connect) marks a pin as intentionally unconnected.

    The old generator emitted one per component as a stand-in for a symbol,
    which makes KiCad's ERC misreport the design. Components are drawn with
    (rectangle) instead.
    """
    assert '(no_connect' not in gen.generate(ir)


@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_every_element_has_a_uuid(gen, ir):
    """KiCad 7 expects a uuid on labels, global_labels, text and graphics."""
    out = gen.generate(ir)
    n_elements = (
        out.count('(label "')
        + out.count('(global_label "')
        + out.count('(text "')
        + out.count('(rectangle')
    )
    # +1 for the sheet-level uuid
    assert out.count('(uuid "') >= n_elements + 1


# ── Content escaping ─────────────────────────────────────────────────────────

def test_quotes_in_intent_are_escaped(gen):
    ir = IR_001.model_copy(update={"intent": 'A "quoted" intent string'})
    out = gen.generate(ir)
    title = re.search(r'\(title "([^"]*)"\)', out)
    assert title, "title_block did not parse — quote escaping is broken"
    assert '"quoted"' not in title.group(1)
