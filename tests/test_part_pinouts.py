"""
tests/test_part_pinouts.py — pinouts by part number, from the KiCad symbol library.

Two halves. The first runs everywhere, against a small hand-written library in
tests/fixtures/kicad_symbols (the parser, extends chains, wildcards, prefixes,
ambiguity, and IV.2 in the verifier). The second runs only where KiCad is
installed and checks the generator's own per-part maps against the real
library: that comparison is the T1 witness verify.py's IV.2 relies on.
"""
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
    yield


# ── the reader, on a library written for the test ───────────────────────────
def test_extends_chain_two_deep_inherits_pins(fixture_lib):
    r = pp.lookup("XCVR485A")
    assert r.how == "exact"
    assert r.symbol.chain == ("XCVR485A", "XCVR8_MID", "XCVR8_BASE")
    assert r.symbol.pins["2"] == "~{RE}" and r.symbol.pins["6"] == "A"


def test_derived_symbol_keeps_its_own_empty_footprint(fixture_lib):
    """KiCad's MAX485E names no default footprint; its base names SOIC-8. The
    derived part must not inherit a package it never claimed."""
    assert pp.lookup("XCVR485A").symbol.footprint == ""


def test_orderable_suffix_matches_by_longest_prefix(fixture_lib):
    r = pp.lookup("XCVR485ACSA+T")
    assert r.how == "prefix" and r.symbol.name == "XCVR485A"


def test_prefix_must_not_run_into_a_digit(fixture_lib):
    """QBEC1234 is not QBEC12345's prefix: the part number goes on with a digit."""
    assert pp.lookup("QBEC12345").symbol is None


def test_wildcard_name_matches_its_family(fixture_lib):
    r = pp.lookup("REG17T-33AB/TT")
    assert r.how == "wildcard" and r.symbol.name == "REG17x-33xxTT"


def test_generic_symbol_never_matches_a_part_number(fixture_lib):
    """Device:R is a prefix of every resistor part number and says nothing."""
    assert pp.lookup("RC0402FR-0710KL").symbol is None


def test_package_tags_choose_between_pinouts(fixture_lib):
    amb = pp.lookup("REGA100XYZ")
    assert amb.symbol is None and "different pinouts" in amb.reason
    assert pp.lookup("REGA100XYZ", "TO-92").symbol.name == "REGA100_TO92"
    assert pp.lookup("REGA100XYZ", "SOT-23").symbol.name == "REGA100_SOT23"


def test_pad_lookup_normalises_names(fixture_lib):
    s = pp.lookup("XCVR485A").symbol
    assert pp.pads_for(s, "RE") == ["2"]
    assert pp.pads_for(s, "vcc") == ["8"]
    assert pp.pads_for(s, "NOT_A_PIN") is None
    assert pp.pads_for(pp.lookup("RELAYX12").symbol, "COM") is None


def test_no_library_is_said_so(monkeypatch):
    monkeypatch.setenv("KICAD_SYMBOL_DIR", str(FIXTURE / "missing"))
    r = pp.lookup("MAX485E")
    assert r.symbol is None and "not found" in r.reason


# ── IV.2 in the verifier, on the fixture library ────────────────────────────
def _one_part(ref, mpn, pkg, pins, wrong_map=None):
    nl = {"name": "t", "components": [
        {"ref": ref, "mpn": mpn, "package": pkg, "pins": pins}]}
    b = Board(name="t", outline_w=30, outline_h=30, layers=[Layer("F.Cu", "signal")])
    c = footprints.build(ref, pkg, pins, x=15, y=15, mpn=mpn)
    if wrong_map:
        for p in c.pads:
            p.net = wrong_map.get(p.pin, "")
    c.attrs.update({"package": pkg, "mpn": mpn})
    b.components.append(c)
    return verify_board(b, nl)


def _f(rep, check):
    return next((f for f in rep.findings if f.check == check), None)


def test_iv2_disagreement_with_the_library_fails(fixture_lib, monkeypatch):
    """The SOT-23 bug, caught: the generator's map says E-B-C, the library
    transcription says B-E-C. Two sources disagree, so the board is refused."""
    monkeypatch.setattr(footprints, "PART_PINMAPS",
                        [(r"^QBEC1234", "SOT-23", footprints._BJT_EBC)])
    rep = _one_part("Q1", "QBEC1234", "SOT-23", {"B": "base", "E": "gnd", "C": "load"})
    f = _f(rep, "IV.2")
    assert f.status == "fail" and "QBEC1234" in f.detail
    assert rep.gate()[0] is False


def test_iv2_agreement_is_evidence_not_proof(fixture_lib, monkeypatch):
    monkeypatch.setattr(footprints, "PART_PINMAPS",
                        [(r"^QBEC1234", "SOT-23", footprints._BJT_BEC)])
    rep = _one_part("Q1", "QBEC1234", "SOT-23", {"B": "base", "E": "gnd", "C": "load"})
    f = _f(rep, "IV.2")
    assert f.status == "pass" and f.rung == "evidence"
    assert "T1" in f.subjects[0]


def test_iv2_package_disagreement_fails(fixture_lib, monkeypatch):
    """The library says this part is a TO-92; the board built a SOT-23."""
    monkeypatch.setattr(footprints, "PART_PINMAPS",
                        [(r"^QEBC5678", "SOT-23", footprints._BJT_EBC)])
    rep = _one_part("Q1", "QEBC5678", "SOT-23", {"B": "base", "E": "gnd", "C": "load"})
    assert _f(rep, "IV.2").status == "fail"


def test_iv2_blank_library_names_stay_unknown(fixture_lib, monkeypatch):
    monkeypatch.setattr(footprints, "PART_PINMAPS",
                        [(r"^RELAYX12", "HEADER-3", {"COM": ["1"], "NO": ["2"], "NC": ["3"]})])
    rep = _one_part("K1", "RELAYX12", "HEADER-3", {"COM": "a", "NO": "b", "NC": "c"})
    assert _f(rep, "IV.2").status == "unknown"
    assert "no pin answering" in _f(rep, "IV.2b").detail


def test_iv2_reversed_diode_fails(fixture_lib):
    """A diode wired anode-first: KiCad says pad 1 is the cathode."""
    rep = _one_part("D1", "DIODE4007X", "DO-41", {"K": "rail", "A": "load"},
                    wrong_map={"1": "load", "2": "rail"})
    assert _f(rep, "IV.2").status == "fail"


def test_iv2_without_library_is_unknown(monkeypatch):
    monkeypatch.setenv("KICAD_SYMBOL_DIR", str(FIXTURE / "missing"))
    rep = _one_part("Q1", "MMBT2222A", "SOT-23", {"B": "b", "E": "e", "C": "c"})
    assert _f(rep, "IV.2").status == "unknown"


# ── the generator's maps against the real KiCad library ─────────────────────
real = pytest.mark.skipif(pp.symbol_dir() is None, reason="KiCad symbol library not installed")

# Each per-part map in footprints.PART_PINMAPS, with part numbers it serves.
_SERVED = [
    ("ATMEGA328P-PU", "DIP-28"),
    ("PN2222A", "TO-92"), ("2N3904", "TO-92"), ("S8050", "TO-92"),
    ("BC547BTA", "TO-92"), ("BC337", "TO-92"),
    ("MMBT2222ALT1G", "SOT-23"), ("MMBT3904", "SOT-23"), ("BC847", "SOT-23"),
    ("2N7002", "SOT-23"), ("BSS138", "SOT-23"),
    ("MAX485ECSA+T", "SOIC-8"), ("MAX3485ECSA+T", "SOIC-8"),
    ("1N4007", "DO-41"), ("1N4148W-7-F", "SOD-123"),
]


@real
@pytest.mark.parametrize("mpn,pkg", _SERVED)
def test_generator_map_agrees_with_kicad(mpn, pkg):
    """Every named pin the generator places, KiCad places on the same pad."""
    sym = pp.lookup(mpn, pkg).symbol
    assert sym is not None, mpn
    labels = ["K"] if pkg in ("DO-41", "SOD-123") else []
    mapping, source = footprints.pin_map(pkg, mpn, labels)
    assert source, f"{mpn}: no declared map"
    checked = 0
    for label, pads in mapping.items():
        kp = pp.pads_for(sym, label)
        if kp is None:
            continue
        checked += 1
        assert set(kp) <= set(pads), f"{mpn} {label}: ours {pads}, KiCad {kp} ({sym.cite()})"
    assert checked >= 2, f"{mpn}: nothing compared"


@real
def test_sot23_package_map_would_have_been_wrong_for_a_regulator():
    """Why a package cannot carry a pinout: the MCP1700 in SOT-23 is GND-VO-VI,
    nothing like the transistor order the old package map assumed."""
    sym = pp.lookup("MCP1700T-3302E/TT").symbol
    assert sym is not None
    assert [pp.norm_name(sym.pins[k]) for k in ("1", "2", "3")] == ["GND", "VO", "VI"]
