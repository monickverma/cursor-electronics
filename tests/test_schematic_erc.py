"""
tests/test_schematic_erc.py — the schematic the product emits must open in
KiCad, pass its ERC without an error, and say the same thing as the IR.

Finding F-S2-R001-3 (2026-10-21, S2's first judge run): the `.kicad_sch` did
not load in KiCad 10.0.1 — `kicad-cli sch erc` and `sch export netlist` exited
3 on every template. `global_label` used `(shape power_in)`, which is not a
KiCad shape, and the file held no symbol at all, so even patched it was an
empty design to ERC. These tests run KiCad on every template's schematic and
compare KiCad's own netlist with the IR, connection for connection.
"""
import json
import xml.etree.ElementTree as ET
from collections import defaultdict

import pytest

from core.ir_examples import ALL_EXAMPLES
from generators.schematic.kicad import KiCadSchematicGenerator
import pcb_engine  # noqa: F401  — puts the engine directory on sys.path
import kicad_cli

requires_kicad = pytest.mark.skipif(not kicad_cli.available(), reason="kicad-cli not installed")


def _write(tmp_path, ir):
    p = tmp_path / f"{ir.circuit_id[:8]}.kicad_sch"
    p.write_text(KiCadSchematicGenerator().generate(ir), encoding="utf-8")
    return p


def test_no_invented_label_shape():
    """KiCad's label shapes are input, output, bidirectional, tri_state and
    passive; power_in is a pin type, and a file using it does not load."""
    for ir in ALL_EXAMPLES:
        assert "power_in" not in KiCadSchematicGenerator().generate(ir)


@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_every_part_is_a_symbol_instance(ir):
    out = KiCadSchematicGenerator().generate(ir)
    for comp in ir.components:
        assert f'(symbol (lib_id "CircuitOS:{comp.id}")' in out
        assert f'(reference "{comp.id}")' in out


@requires_kicad
@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_kicad_erc_runs_without_an_error(tmp_path, ir):
    sch = _write(tmp_path, ir)
    out = tmp_path / "erc.json"
    p = kicad_cli.run(["sch", "erc", "--format", "json", "--severity-all",
                       "-o", str(out), str(sch)])
    assert p.returncode == 0, f"KiCad could not load the schematic: {p.stdout} {p.stderr}"
    rep = json.loads(out.read_text(encoding="utf-8"))
    errors = [v for sh in rep["sheets"] for v in sh["violations"] if v["severity"] == "error"]
    assert errors == [], [(v["type"], v["description"]) for v in errors]


@requires_kicad
@pytest.mark.parametrize("ir", ALL_EXAMPLES, ids=lambda i: i.circuit_id[:8])
def test_kicads_netlist_is_the_irs(tmp_path, ir):
    """KiCad's netlist export must group the same pins into the same nets as
    the IR's connections: the schematic is connectivity, not a picture."""
    sch = _write(tmp_path, ir)
    xml = tmp_path / "net.xml"
    p = kicad_cli.run(["sch", "export", "netlist", "--format", "kicadxml",
                       "-o", str(xml), str(sch)])
    assert p.returncode == 0, p.stderr
    root = ET.parse(xml).getroot()
    kicad = {}
    for net in root.iter("net"):
        pins = frozenset((n.get("ref"), n.get("pin")) for n in net.iter("node"))
        kicad[net.get("name").lstrip("/")] = pins
    want = defaultdict(set)
    for c in ir.connections:
        want[c.node_id].add((c.component_id, c.pin))
    assert kicad == {k: frozenset(v) for k, v in want.items()}
    assert {c.get("ref") for c in root.iter("comp")} == {c.id for c in ir.components}
