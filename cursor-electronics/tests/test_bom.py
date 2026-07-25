"""
BOM compiler tests.
All tests are unit tests — no API key, no database required.
"""

import pytest
from core.ir_examples import IR_001, IR_002, IR_003, IR_004, IR_005, ALL_EXAMPLES
from core.ir_schema import Component, ComponentType
from generators.bom.compiler import (
    BOMCompiler,
    _parse_capacitance,
    _parse_resistance,
)


def _component(**kw):
    """Minimal valid Component — override any field via kwargs."""
    defaults = dict(
        id="X1",
        type=ComponentType.RESISTOR,
        part_number="RC0402FR-0710KL",
        manufacturer="Yageo",
        package="0402",
        value="10k",
        confidence=0.9,
        justification="test fixture component with a sufficiently long justification",
    )
    defaults.update(kw)
    return Component(**defaults)


class _StubIR:
    """Stands in for CircuitIR — compile() only reads .components."""

    def __init__(self, components):
        self.components = components


class TestBOMCompiler:
    def test_returns_list_for_dht22_ir(self):
        rows = BOMCompiler().compile(IR_001)
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_row_count_matches_component_count(self):
        for ir in ALL_EXAMPLES:
            rows = BOMCompiler().compile(ir)
            assert len(rows) == len(ir.components), (
                f"IR {ir.circuit_id}: expected {len(ir.components)} rows, got {len(rows)}"
            )

    def test_every_row_has_required_fields(self):
        rows = BOMCompiler().compile(IR_001)
        required = {"id", "part_number", "manufacturer", "package", "quantity",
                    "unit_price_usd", "total_price_usd"}
        for row in rows:
            missing = required - set(row.keys())
            assert not missing, f"Row {row.get('id')} missing fields: {missing}"

    def test_component_id_preserved(self):
        rows = BOMCompiler().compile(IR_001)
        ids = {r["id"] for r in rows}
        expected_ids = {c.id for c in IR_001.components}
        assert ids == expected_ids

    def test_part_number_preserved(self):
        rows = BOMCompiler().compile(IR_001)
        row_map = {r["id"]: r for r in rows}
        for comp in IR_001.components:
            assert row_map[comp.id]["part_number"] == comp.part_number

    def test_quantity_always_one(self):
        rows = BOMCompiler().compile(IR_001)
        for row in rows:
            assert row["quantity"] == 1

    def test_lcsc_pn_included_when_present(self):
        rows = BOMCompiler().compile(IR_001)
        row_map = {r["id"]: r for r in rows}
        u1 = row_map["U1"]
        assert u1["lcsc_pn"] == "C14877"

    def test_known_price_populated_for_atm328p(self):
        rows = BOMCompiler().compile(IR_001)
        mcu = next(r for r in rows if r["id"] == "U1")
        assert mcu["unit_price_usd"] > 0

    def test_total_price_equals_unit_times_qty(self):
        rows = BOMCompiler().compile(IR_001)
        for row in rows:
            assert abs(row["total_price_usd"] - row["unit_price_usd"] * row["quantity"]) < 1e-9

    def test_total_cost_nonzero_for_dht22_ir(self):
        rows = BOMCompiler().compile(IR_001)
        total = BOMCompiler().total_cost(rows)
        assert total > 0

    def test_total_cost_sum_of_rows(self):
        rows = BOMCompiler().compile(IR_001)
        expected = sum(r["total_price_usd"] for r in rows)
        actual = BOMCompiler().total_cost(rows)
        assert abs(actual - expected) < 1e-6

    def test_modbus_ir_has_transceiver_row(self):
        rows = BOMCompiler().compile(IR_005)
        part_numbers = [r["part_number"] for r in rows]
        assert "MAX485ECSA" in part_numbers

    def test_passive_circuit_no_mcu(self):
        rows = BOMCompiler().compile(IR_003)
        mcu_rows = [r for r in rows if "ATmega" in r["part_number"]]
        assert len(mcu_rows) == 0

    def test_value_field_passed_through_for_resistors(self):
        rows = BOMCompiler().compile(IR_001)
        r1 = next((r for r in rows if r["id"] == "R1"), None)
        assert r1 is not None
        assert r1["value"] == "10k"

    @pytest.mark.parametrize("ir", ALL_EXAMPLES)
    def test_all_examples_compile_without_error(self, ir):
        rows = BOMCompiler().compile(ir)
        assert isinstance(rows, list)
        assert len(rows) == len(ir.components)


class TestValueParsing:
    """Numeric value parsing is what lets a Yageo CFR-25JB-52-10K be priced from
    a database RC0402FR-0710KL — both are 10000 ohms."""

    @pytest.mark.parametrize("raw,expected", [
        ("10k", 10_000), ("10K", 10_000), ("4K7", 4_700), ("4.7k", 4_700),
        ("100R", 100), ("100", 100), ("1K59", 1_590), ("1M", 1_000_000),
        ("1k", 1_000), ("  10K  ", 10_000), ("10kΩ", 10_000), ("470R", 470),
    ])
    def test_parse_resistance(self, raw, expected):
        assert _parse_resistance(raw) == pytest.approx(expected)

    @pytest.mark.parametrize("raw,expected", [
        ("100nF", 100e-9), ("1uF", 1e-6), ("22pF", 22e-12),
        ("4.7nF", 4.7e-9), ("10uF/25V", 10e-6), ("100pF", 100e-12),
    ])
    def test_parse_capacitance(self, raw, expected):
        assert _parse_capacitance(raw) == pytest.approx(expected)

    @pytest.mark.parametrize("bad", [None, "", "abc", "not-a-value"])
    def test_unparseable_returns_none(self, bad):
        assert _parse_resistance(bad) is None
        assert _parse_capacitance(bad) is None


class TestPricingLookup:
    """Regression tests for the $0.00 BOM bug.

    The old compiler keyed prices on Component.lcsc_pn, which the AI usually
    leaves empty, so every row fell through to 0.0 and the UI reported a
    confident 'Estimated total: $0.00 USD'.
    """

    def test_exact_part_number_is_priced_without_lcsc_pn(self):
        """The core regression: no lcsc_pn on the IR must still yield a price."""
        row = BOMCompiler().compile(_StubIR([
            _component(id="U2", type=ComponentType.SENSOR, part_number="DHT22",
                       manufacturer="Aosong", package="4-PIN", value=None)
        ]))[0]
        assert row["lcsc_pn"] is None or row["lcsc_pn"]  # backfilled from db
        assert row["unit_price_usd"] > 0
        assert row["price_known"] is True
        assert row["price_source"] == "part_number"

    def test_lcsc_pn_backfilled_from_database(self):
        """Blank LCSC PN columns in the UI were unpopulated IR fields."""
        row = BOMCompiler().compile(_StubIR([
            _component(id="U2", type=ComponentType.SENSOR, part_number="DHT22",
                       manufacturer="Aosong", package="4-PIN", value=None)
        ]))[0]
        assert row["lcsc_pn"] == "C19528"

    def test_part_number_prefix_resolved_via_package(self):
        """'ATmega328P' matches both -PU (DIP-28) and -AU (TQFP-32);
        the package disambiguates."""
        row = BOMCompiler().compile(_StubIR([
            _component(id="U1", type=ComponentType.MICROCONTROLLER,
                       part_number="ATmega328P", manufacturer="Microchip",
                       package="DIP-28", value=None)
        ]))[0]
        assert row["price_source"] == "part_number_prefix"
        assert row["priced_as"] == "ATmega328P-PU"
        assert row["unit_price_usd"] == pytest.approx(1.85)

    def test_ambiguous_prefix_without_package_is_not_guessed(self):
        """Picking an arbitrary package would put the wrong part on an order."""
        row = BOMCompiler().compile(_StubIR([
            _component(id="U1", type=ComponentType.MICROCONTROLLER,
                       part_number="ATmega328P", manufacturer="Microchip",
                       package="NOT-A-REAL-PACKAGE", value=None)
        ]))[0]
        assert row["price_known"] is False
        assert row["price_source"] == "unknown"

    @pytest.mark.parametrize("pn,value,ctype", [
        ("CFR-25JB-52-10K", "10k", ComponentType.RESISTOR),
        ("CFR-25JB-52-1K", "1k", ComponentType.RESISTOR),
        ("K104K15X7RF53L2", "100nF", ComponentType.CAPACITOR),
    ])
    def test_unknown_passive_priced_from_equivalent(self, pn, value, ctype):
        """Parts absent from the database are priced from an equivalent."""
        row = BOMCompiler().compile(_StubIR([
            _component(id="R1", type=ctype, part_number=pn, value=value,
                       manufacturer="Yageo", package="0.25W")
        ]))[0]
        assert row["price_source"] == "equivalent_value"
        assert row["unit_price_usd"] > 0
        assert row["priced_as"] is not None

    def test_active_parts_are_never_value_substituted(self):
        """An ATmega328P is not interchangeable with an ATmega2560."""
        row = BOMCompiler().compile(_StubIR([
            _component(id="U9", type=ComponentType.MICROCONTROLLER,
                       part_number="TOTALLY-MADE-UP-MCU",
                       manufacturer="Nobody", package="DIP-28", value=None)
        ]))[0]
        assert row["price_known"] is False
        assert row["price_source"] == "unknown"

    def test_unknown_part_flagged_not_silently_free(self):
        """The whole point: unpriced must be distinguishable from $0.00."""
        row = BOMCompiler().compile(_StubIR([
            _component(id="Z1", type=ComponentType.CONNECTOR,
                       part_number="NO-SUCH-PART-12345",
                       manufacturer="Nobody", package="N/A", value=None)
        ]))[0]
        assert row["price_known"] is False
        assert row["unit_price_usd"] == 0.0

    def test_screenshot_bom_is_fully_priced(self):
        """End-to-end: the 9-component circuit that reported $0.00 in the UI."""
        spec = [
            ("U1", ComponentType.MICROCONTROLLER, "ATmega328P", "DIP-28", None),
            ("U2", ComponentType.SENSOR, "DHT22", "4-PIN", None),
            ("K1", ComponentType.RELAY, "SRD-05VDC-SL-C", "RELAY-5PIN", None),
            ("Q1", ComponentType.TRANSISTOR, "2N2222A", "TO-92", None),
            ("D1", ComponentType.DIODE, "1N4007", "DO-41", None),
            ("R1", ComponentType.RESISTOR, "CFR-25JB-52-10K", "0.25W", "10k"),
            ("R2", ComponentType.RESISTOR, "CFR-25JB-52-1K", "0.25W", "1k"),
            ("C1", ComponentType.CAPACITOR, "K104K15X7RF53L2", "RADIAL", "100nF"),
            ("C2", ComponentType.CAPACITOR, "K104K15X7RF53L2", "RADIAL", "100nF"),
        ]
        comps = [_component(id=i, type=t, part_number=p, package=k, value=v)
                 for i, t, p, k, v in spec]

        compiler = BOMCompiler()
        rows = compiler.compile(_StubIR(comps))
        coverage = compiler.pricing_coverage(rows)

        assert coverage["complete"], f"unpriced: {coverage['unpriced_ids']}"
        assert compiler.total_cost(rows) > 0


class TestPricingCoverage:
    def test_coverage_reports_all_priced(self):
        compiler = BOMCompiler()
        rows = compiler.compile(IR_001)
        cov = compiler.pricing_coverage(rows)
        assert cov["total"] == len(IR_001.components)
        assert cov["priced"] + len(cov["unpriced_ids"]) == cov["total"]

    def test_coverage_flags_unpriced_component(self):
        compiler = BOMCompiler()
        rows = compiler.compile(_StubIR([
            _component(id="Z1", type=ComponentType.CONNECTOR,
                       part_number="NO-SUCH-PART-98765",
                       manufacturer="Nobody", package="N/A", value=None)
        ]))
        cov = compiler.pricing_coverage(rows)
        assert cov["complete"] is False
        assert cov["unpriced_ids"] == ["Z1"]

    @pytest.mark.parametrize("ir", ALL_EXAMPLES)
    def test_every_example_row_declares_price_provenance(self, ir):
        for row in BOMCompiler().compile(ir):
            assert "price_known" in row
            assert row["price_source"] in {
                "part_number", "lcsc_pn", "part_number_prefix",
                "equivalent_value", "unknown",
            }
