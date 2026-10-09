"""
tests/test_pcb_verify.py — the verification layer must catch the defects it
claims to catch, on boards built to contain exactly one of them.

Each test constructs a minimal board carrying one known fault and asserts the
matching check fails. A verifier that passes everything is worthless; these
tests are how it is held to the opposite.
"""
import sys
from pathlib import Path

import pytest

# Import the package first: pcb_engine/__init__.py puts the engine's own
# directory on sys.path, which is what makes `board_ir` and `footprints`
# importable by bare name below.
from pcb_engine import verify_board
import board_ir
from board_ir import Board, Component, Layer, Pad, Track
import footprints


def _finding(rep, check):
    return next((f for f in rep.findings if f.check == check), None)


def _part(ref, x, y, pins, pkg="0603"):
    """Build a component the way from_netlist does — package carried on the IR."""
    comp = footprints.build(ref, pkg, pins, x=x, y=y)
    comp.attrs["package"] = pkg
    return comp


def _board(components):
    b = Board(name="test", outline_w=20, outline_h=20,
              layers=[Layer("F.Cu", "signal"), Layer("B.Cu", "signal")])
    b.components.extend(components)
    return b


def _clean_board():
    """Two 0603s, both nets routed, each on its own lane so nothing shorts."""
    b = _board([_part("R1", 6.0, 10.0, {"1": "SIG", "2": "GND"}),
                _part("R2", 13.0, 10.0, {"1": "SIG", "2": "GND"})])
    r1, r2 = b.component("R1"), b.component("R2")
    b.tracks.append(Track("F.Cu", "SIG", 0.2, [
        (r1.pads[0].x, 10.0), (r1.pads[0].x, 8.0),
        (r2.pads[0].x, 8.0), (r2.pads[0].x, 10.0)]))
    b.tracks.append(Track("F.Cu", "GND", 0.2, [
        (r1.pads[1].x, 10.0), (r1.pads[1].x, 12.0),
        (r2.pads[1].x, 12.0), (r2.pads[1].x, 10.0)]))
    return b


def _single_net_board():
    """One net only — for tests that care about exactly one connection."""
    b = _board([_part("R1", 6.0, 10.0, {"1": "SIG"}),
                _part("R2", 13.0, 10.0, {"1": "SIG"})])
    r1, r2 = b.component("R1"), b.component("R2")
    b.tracks.append(Track("F.Cu", "SIG", 0.2,
                          [(r1.pads[0].x, 10.0), (r2.pads[0].x, 10.0)]))
    return b


def test_clean_board_passes_every_decidable_check():
    rep = verify_board(_clean_board())
    assert rep.ok, [f.line() for f in rep.failed()]
    assert _finding(rep, "III.1").status == "pass"
    assert _finding(rep, "III.2").status == "pass"
    assert rep.gate()[0] is True


# ── III.1 — a required connection with no copper between its pads ────────────
def test_unrouted_connection_is_a_failure():
    b = _clean_board()
    b.tracks.clear()
    rep = verify_board(b)
    f = _finding(rep, "III.1")
    assert f.status == "fail"
    assert "no copper path" in f.detail
    assert rep.gate()[0] is False


def test_unrouted_check_is_not_fooled_by_near_miss_copper():
    """The defect unrouted() misses: copper that stops 0.05 mm short of the pad.
    The union-find judge merges within the contact tolerance, so this is the
    case where the two judges can disagree — recorded here so the tolerance is
    a decision, not an accident."""
    b = _single_net_board()
    b.tracks.clear()
    a = b.component("R1").pads[0]
    c = b.component("R2").pads[0]
    # end the track 0.03 mm short of R2's pad centre: inside the contact tolerance
    b.tracks.append(Track("F.Cu", "SIG", 0.2,
                          [(a.x, a.y), (c.x - 0.03, c.y)]))
    rep = verify_board(b)
    assert _finding(rep, "III.1").status == "pass"   # merged at 0.06 mm


# ── III.2 — two nets sharing copper ─────────────────────────────────────────
def test_two_nets_touching_is_a_short():
    b = _clean_board()
    b.tracks.clear()
    r1p1 = b.component("R1").pads[0]     # SIG
    r2p2 = b.component("R2").pads[1]     # GND
    b.tracks.append(Track("F.Cu", "SIG", 0.2,
                          [(r1p1.x, r1p1.y), (r2p2.x, r2p2.y)]))
    rep = verify_board(b)
    f = _finding(rep, "III.2")
    assert f.status == "fail"
    assert "two or more nets" in f.detail


# ── III.3 — a pad the netlist named that came out netless (ghost copper) ─────
def test_netless_pad_named_by_the_netlist_is_a_failure():
    nl = {"name": "ghost", "components": [
        {"ref": "R1", "mpn": "0603", "package": "0603",
         "pins": {"1": "SIG", "2": "GND"}}]}
    b = _clean_board()
    b.component("R1").pads[1].net = ""     # the netlist named it; the pad lost it
    rep = verify_board(b, nl)
    f = _finding(rep, "III.3")
    assert f.status == "fail"
    assert "carry no net" in f.detail


def test_parity_mismatch_is_caught_against_the_netlist():
    nl = {"name": "swap", "components": [
        {"ref": "R1", "mpn": "0603", "package": "0603",
         "pins": {"1": "SIG", "2": "GND"}}]}
    b = _clean_board()
    b.component("R1").pads[0].net = "GND"   # generator swapped the pins
    b.component("R1").pads[1].net = "SIG"
    rep = verify_board(b, nl)
    assert _finding(rep, "III.4").status == "fail"


# ── III.4 — the SOT-23 class: an unrecognised pinout placed by luck ─────────
def test_undetermined_pinout_is_reported_unknown_not_pass():
    """A SOT-23 whose labels are not in any PINMAPS entry: build() puts them on
    free pads in list order. No free tool checks pin numbering, so the honest
    verdict is 'unknown', never 'pass'."""
    nl = {"name": "sot", "components": [
        {"ref": "Q1", "mpn": "MYSTERY-SOT", "package": "SOT-23",
         "pins": {"INPUT": "A", "OUTPUT": "B", "CTRL": "C"}}]}
    b = Board(name="sot", outline_w=20, outline_h=20,
              layers=[Layer("F.Cu", "signal")])
    b.components.append(footprints.build(
        "Q1", "SOT-23", {"INPUT": "A", "OUTPUT": "B", "CTRL": "C"}, x=10, y=10))
    rep = verify_board(b, nl)
    f = _finding(rep, "III.4d")
    assert f.status == "unknown"
    assert f.rung == "unknown"
    assert "arbitrary" in f.detail


def test_pin_collision_is_a_failure():
    """Two netlist pins resolving to the same footprint pad: one net is written
    over the other, silently. DIP-28 VCC->20 and AVCC->20 collide."""
    nl = {"name": "collide", "components": [
        {"ref": "U1", "mpn": "ATMEGA328P-PU", "package": "DIP-28",
         "pins": {"VCC": "P5V", "AVCC": "P3V3"}}]}
    b = Board(name="collide", outline_w=40, outline_h=40,
              layers=[Layer("F.Cu", "signal")])
    b.components.append(footprints.build(
        "U1", "DIP-28", {"VCC": "P5V", "AVCC": "P3V3"}, x=20, y=20))
    rep = verify_board(b, nl)
    assert _finding(rep, "III.4c").status == "fail"


# ── II — placement ──────────────────────────────────────────────────────────
def test_courtyard_outside_the_outline_is_a_failure():
    b = _clean_board()
    b.component("R2").x = 19.9        # courtyard runs off the right edge
    rep = verify_board(b)
    assert _finding(rep, "II.1").status == "fail"


def test_overlapping_courtyards_are_a_failure():
    b = _clean_board()
    b.component("R2").x = b.component("R1").x   # stacked on top of each other
    rep = verify_board(b)
    assert _finding(rep, "II.2").status == "fail"


# ── II.3 — tombstoning precondition ─────────────────────────────────────────
def test_asymmetric_pads_are_a_failure():
    b = _clean_board()
    b.component("R1").pads[0].w *= 1.5      # one pad much larger than the other
    rep = verify_board(b)
    f = _finding(rep, "II.3")
    assert f.status == "fail"
    assert "pad areas" in f.detail


# ── IV.1 — the land-pattern table can disagree with the generator ───────────
def test_land_pattern_table_disagreement_is_a_failure(monkeypatch, tmp_path):
    table = tmp_path / "land_patterns.json"
    table.write_text('{"0603": {"pad_count": 3, "verified": true}}')
    monkeypatch.setattr("verify.Path", lambda *a, **k: table)
    rep = verify_board(_clean_board())
    assert _finding(rep, "IV.1").status == "fail"


# ── the gate ────────────────────────────────────────────────────────────────
def test_gate_refuses_a_board_with_a_decidable_failure():
    b = _clean_board()
    b.tracks.clear()
    ok, why = verify_board(b).gate()
    assert ok is False
    assert "III.1" in why


def test_unknown_rungs_do_not_pass_but_do_not_refuse():
    """The board is emittable, but it is not proven. The distinction is the
    point of the whole ladder."""
    rep = verify_board(_clean_board())
    assert rep.ok is True
    assert any(f.rung == "unknown" for f in rep.findings)
    assert rep.proven is False


# ── the real shipped netlist ────────────────────────────────────────────────
def _dht22_netlist():
    import json
    path = Path(__file__).parent.parent / "backend" / "pcb_engine" / "netlist_dht22.json"
    return json.loads(path.read_text())


def test_shipped_dht22_netlist_has_no_decidable_failure():
    from pcb_engine import compile_board
    nl = _dht22_netlist()
    result = compile_board(nl)
    rep = verify_board(result.board, nl)
    assert rep.ok, [f.line() for f in rep.failed()]


def test_generation_reports_the_judges_count_not_the_routers():
    """The ledger's finding, pinned: the router's own `unrouted()` says 4 on a
    board that is fully routed. Generation now reports the judge's 0 and keeps
    the router's number beside it so the gap stays visible."""
    from pcb_engine import compile_board
    result = compile_board(_dht22_netlist())
    assert result.stats["unrouted"] == 0
    assert result.stats["routed"] == result.stats["connections"]
    assert result.stats["router_unrouted"] == 4
    assert result.ok is True
    assert result.to_dict()["verification"]["ok"] is True


def test_generation_of_a_broken_netlist_refuses_at_the_gate():
    """A netlist naming a pin the footprint has no pad for must not compile to a
    board the verifier passes."""
    from pcb_engine import compile_board
    nl = {"name": "short_pad", "board": {"width": 30, "height": 30},
          "ground_net": "GND", "components": [
              {"ref": "R1", "mpn": "", "package": "0603",
               "pins": {"1": "A", "2": "B", "3": "C"}}]}
    result = compile_board(nl)
    assert result.stats["verified"] is False
    assert "III.4b" in result.stats["failed_checks"]
