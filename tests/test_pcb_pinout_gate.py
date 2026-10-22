"""
tests/test_pcb_pinout_gate.py — a pinout nobody compared must not reach the fab
(F-S0-0001).

The swapped-pins calibration board (Q1, a 2N2222A in TO-92, emitter and
collector transposed) was a false pass: KiCad has no symbol named 2N2222A, so
IV.2 said "no part could be compared", and the gate still emitted. Plan
decision 9: an unknown pinout blocks export. The board can still be shown.

The second half is the lookup. A part number is bridged to a pinout only by
the orderable part number plus its package — a KiCad symbol of that name, or a
page-cited datasheet record. Never by a similar name: PN2222A is E-B-C, and a
TO-92 "2N2222A" from another maker can be C-B-E.
"""
import json
from pathlib import Path

import pytest

from pcb_engine import verify_board
from board_ir import Board, Layer
import footprints
import part_pinouts as pp

FIXTURE = Path(__file__).parent / "fixtures" / "kicad_symbols"


@pytest.fixture
def fixture_lib(monkeypatch, tmp_path):
    monkeypatch.setenv("KICAD_SYMBOL_DIR", str(FIXTURE))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(pp, "RECORDS_FILE", tmp_path / "no_records.json")
    yield


@pytest.fixture
def records(monkeypatch, tmp_path):
    """Write datasheet pinout records for one test."""
    def write(*recs):
        path = tmp_path / "pinout_records.json"
        path.write_text(json.dumps({"records": list(recs)}), encoding="utf-8")
        monkeypatch.setattr(pp, "RECORDS_FILE", path)
    return write


def _record(mpn="QREC100TF", package="TO-92", pins=None, kicad_symbol=None):
    return {"mpn": mpn, "maker": "Example Semi", "package": package,
            "pins": pins or {"1": "E", "2": "B", "3": "C"},
            "source": {"title": "QREC100 datasheet rev 3", "url": "https://example.invalid/qrec100.pdf",
                       "page": 2, "retrieved": "2026-10-21"},
            "kicad_symbol": kicad_symbol}


def _board(ref, mpn, pkg, pins, nets=None):
    """One part. `pins` is the netlist (what the design says); `nets`, when
    given, is what the copper actually carries per pad."""
    nl = {"name": "t", "components": [{"ref": ref, "mpn": mpn, "package": pkg, "pins": pins}]}
    b = Board(name="t", outline_w=30, outline_h=30, layers=[Layer("F.Cu", "signal")])
    c = footprints.build(ref, pkg, pins, x=15, y=15, mpn=mpn)
    if nets:
        for p in c.pads:
            p.net = nets.get(p.pin, "")
    c.attrs.update({"package": pkg, "mpn": mpn})
    b.components.append(c)
    return b, nl


def _f(rep, check):
    return next((f for f in rep.findings if f.check == check), None)


# ── the gate ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("pins", [
    {"1": "GND", "2": "RELAY_CTRL", "3": "RELAY_COIL_NEG"},    # the design
    {"1": "RELAY_COIL_NEG", "2": "RELAY_CTRL", "3": "GND"},    # the swapped seed
])
def test_an_uncompared_pinout_blocks_export_but_the_board_is_shown(fixture_lib, pins):
    """Right or wrong, nothing compared it: both must stop at the gate."""
    rep = verify_board(*_board("Q1", "2N2222A", "TO-92", pins))
    emit, why = rep.gate()
    assert emit is False
    assert "IV.2b" in why and "pinout" in why
    assert rep.ok is True                      # shown, not failed
    assert rep.to_dict()["gate"]["emit"] is False


def test_no_symbol_library_blocks_a_part_whose_ends_differ(monkeypatch, tmp_path):
    monkeypatch.setenv("KICAD_SYMBOL_DIR", str(tmp_path / "missing"))
    monkeypatch.setattr(pp, "RECORDS_FILE", tmp_path / "no_records.json")
    rep = verify_board(*_board("Q1", "QBEC1234", "SOT-23",
                               {"B": "base", "E": "gnd", "C": "load"}))
    assert rep.gate()[0] is False
    assert _f(rep, "IV.2b").status == "unknown"


def test_a_board_of_plain_resistors_still_emits(fixture_lib):
    rep = verify_board(*_board("R1", "", "0603", {"1": "A", "2": "B"}))
    assert rep.gate()[0] is True


def test_a_compared_and_agreeing_pinout_emits(fixture_lib, monkeypatch):
    monkeypatch.setattr(footprints, "PART_PINMAPS",
                        [(r"^QBEC1234", "SOT-23", footprints._BJT_BEC)])
    rep = verify_board(*_board("Q1", "QBEC1234", "SOT-23",
                               {"B": "base", "E": "gnd", "C": "load"}))
    assert _f(rep, "IV.2").status == "pass"
    assert rep.gate()[0] is True


# ── the lookup ──────────────────────────────────────────────────────────────
def test_2n2222a_is_not_bridged_to_pn2222a_by_name():
    """The real library: PN2222A exists, 2N2222A does not, and a similar name
    is not the same part."""
    if pp.symbol_dir() is None:
        pytest.skip("KiCad symbol library not installed")
    r = pp.lookup("2N2222A", "TO-92")
    assert r.symbol is None
    assert "2N2222A" in r.reason


def test_a_datasheet_record_answers_for_its_part_number_and_package(fixture_lib, records):
    records(_record())
    r = pp.lookup("QREC100TF", "TO-92")
    assert r.symbol is not None and r.how == "datasheet"
    assert r.symbol.pins == {"1": "E", "2": "B", "3": "C"}
    assert "p. 2" in r.symbol.cite() and "QREC100 datasheet" in r.symbol.cite()


def test_a_record_for_another_package_is_refused(fixture_lib, records):
    records(_record())
    r = pp.lookup("QREC100TF", "SOT-23")
    assert r.symbol is None and "TO-92" in r.reason


def test_a_record_is_matched_by_the_whole_part_number_only(fixture_lib, records):
    records(_record())
    assert pp.lookup("QREC100", "TO-92").symbol is None
    assert pp.lookup("QREC100TFR", "TO-92").symbol is None


def test_a_record_without_a_page_is_not_a_record(fixture_lib, records):
    rec = _record()
    rec["source"]["page"] = None
    records(rec)
    r = pp.lookup("QREC100TF", "TO-92")
    assert r.symbol is None and "page" in r.reason


def test_a_record_and_its_kicad_symbol_must_agree(fixture_lib, records):
    """The trap, closed: the record says C-B-E, the KiCad symbol it names says
    E-B-C. Two citations that disagree refuse, and both are shown."""
    records(_record(pins={"1": "C", "2": "B", "3": "E"}, kicad_symbol="QEBC5678"))
    r = pp.lookup("QREC100TF", "TO-92")
    assert r.symbol is None
    assert "disagree" in r.reason and "QEBC5678" in r.reason and "p. 2" in r.reason


def test_a_record_that_agrees_with_its_kicad_symbol_cites_both(fixture_lib, records):
    records(_record(kicad_symbol="QEBC5678"))
    r = pp.lookup("QREC100TF", "TO-92")
    assert r.symbol is not None and r.how == "datasheet+kicad"
    assert "QEBC5678" in r.symbol.cite() and "p. 2" in r.symbol.cite()


def test_a_kicad_symbol_of_that_name_comes_before_a_record(fixture_lib, records):
    records(_record(mpn="QBEC1234", package="SOT-23"))
    assert pp.lookup("QBEC1234", "SOT-23").how == "exact"


def test_iv2_compares_a_board_against_a_datasheet_record(fixture_lib, records, monkeypatch):
    records(_record())
    monkeypatch.setattr(footprints, "PART_PINMAPS",
                        [(r"^QREC100", "TO-92", footprints._BJT_EBC)])
    pins = {"E": "GND", "B": "CTRL", "C": "LOAD"}
    good = verify_board(*_board("Q1", "QREC100TF", "TO-92", pins))
    assert _f(good, "IV.2").status == "pass" and good.gate()[0] is True
    swapped = verify_board(*_board("Q1", "QREC100TF", "TO-92", pins,
                                   nets={"1": "LOAD", "2": "CTRL", "3": "GND"}))
    assert _f(swapped, "IV.2").status == "fail" and swapped.gate()[0] is False


def test_the_shipped_record_file_is_well_formed():
    """Every shipped record names its part number, package, pins and a page."""
    data = json.loads(pp.RECORDS_FILE.read_text(encoding="utf-8"))
    for rec in data["records"]:
        assert rec["mpn"] and rec["package"] and rec["pins"]
        assert rec["source"]["page"] and rec["source"]["title"]
