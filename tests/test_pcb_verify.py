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
from board_ir import Board, Component, Layer, Pad, Track, Via
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


def _near_miss_board(gap):
    """R1 to R2 by one track whose copper edge stops `gap` mm short of the edge
    of R2's pad — edge to edge, the track's half-width included."""
    b = _single_net_board()
    b.tracks.clear()
    a = b.component("R1").pads[0]
    c = b.component("R2").pads[0]
    w = 0.2
    end_x = c.x - c.w / 2 - w / 2 - gap
    b.tracks.append(Track("F.Cu", "SIG", w, [(a.x, a.y), (end_x, c.y)]))
    return b


def test_unrouted_check_is_not_fooled_by_near_miss_copper():
    """The defect unrouted() misses: copper that stops just short of the pad.
    The union-find judge merges within the contact tolerance, so this is the
    case where the two judges can disagree — recorded here so the tolerance is
    a decision, not an accident."""
    rep = verify_board(_near_miss_board(0.03))
    assert _finding(rep, "III.1").status == "pass"   # merged at 0.06 mm


def test_near_miss_merge_is_the_tolerance_not_the_pad(monkeypatch):
    """The test above must be exercising CONTACT_TOL. With the tolerance at zero
    the same 0.03 mm gap is open; the 2026-10-12 review found the old version
    of that test ended inside the pad, so it passed at any tolerance."""
    monkeypatch.setattr("verify.CONTACT_TOL", 0.0)
    rep = verify_board(_near_miss_board(0.03))
    assert _finding(rep, "III.1").status == "fail"


def test_gap_wider_than_the_tolerance_is_open():
    rep = verify_board(_near_miss_board(0.10))
    assert _finding(rep, "III.1").status == "fail"


def test_same_net_tracks_crossing_mid_segment_are_connected():
    """Two tracks, one from each pad, whose only contact is a crossing in the
    middle of both segments — no endpoint near the other track."""
    b = _single_net_board()
    b.tracks.clear()
    a = b.component("R1").pads[0]
    c = b.component("R2").pads[0]
    mid = (a.x + c.x) / 2
    b.tracks.append(Track("F.Cu", "SIG", 0.2,
                          [(a.x, a.y), (a.x, 4.0), (mid, 4.0), (mid, 8.0)]))
    b.tracks.append(Track("F.Cu", "SIG", 0.2,
                          [(c.x, c.y), (c.x, 6.0), (mid - 2.0, 6.0)]))
    rep = verify_board(b)
    assert _finding(rep, "III.1").status == "pass"


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


def _iii2(b):
    return _finding(verify_board(b), "III.2").status


def test_crossing_tracks_of_two_nets_are_a_short():
    """The 2026-10-12 review's case: no endpoint of either track is near the
    other, so only a crossing test sees the contact."""
    b = _clean_board()
    b.tracks.append(Track("F.Cu", "A", 0.2, [(2.0, 2.0), (18.0, 2.0)]))
    b.tracks.append(Track("F.Cu", "B", 0.2, [(10.0, 0.5), (10.0, 5.0)]))
    assert _iii2(b) == "fail"


def test_crossing_tracks_on_different_layers_are_not_a_short():
    b = _clean_board()
    b.tracks.append(Track("F.Cu", "A", 0.2, [(2.0, 2.0), (18.0, 2.0)]))
    b.tracks.append(Track("B.Cu", "B", 0.2, [(10.0, 0.5), (10.0, 5.0)]))
    assert _iii2(b) == "pass"


def test_wide_tracks_overlapping_by_their_width_are_a_short():
    """Centrelines 0.5 mm apart, each 0.8 mm wide: 0.3 mm of shared copper."""
    b = _clean_board()
    b.tracks.append(Track("F.Cu", "A", 0.8, [(2.0, 2.0), (18.0, 2.0)]))
    b.tracks.append(Track("F.Cu", "B", 0.8, [(2.0, 2.5), (18.0, 2.5)]))
    assert _iii2(b) == "fail"


def test_wide_tracks_with_a_real_gap_are_not_a_short():
    b = _clean_board()
    b.tracks.append(Track("F.Cu", "A", 0.8, [(2.0, 2.0), (18.0, 2.0)]))
    b.tracks.append(Track("F.Cu", "B", 0.8, [(2.0, 3.0), (18.0, 3.0)]))
    assert _iii2(b) == "pass"


def test_track_running_through_a_foreign_pad_is_a_short():
    """Both ends of the track lie outside the pad; it crosses the pad's body."""
    b = _clean_board()
    b.tracks.clear()                        # so only the pad can be touched
    p = b.component("R1").pads[0]           # SIG
    b.tracks.append(Track("F.Cu", "OTHER", 0.2,
                          [(p.x, p.y - 3.0), (p.x, p.y + 3.0)]))
    assert _iii2(b) == "fail"


def test_via_overlapping_a_foreign_pad_is_a_short():
    """The via's centre is outside the pad; its 0.8 mm copper reaches 0.1 mm in."""
    b = _clean_board()
    b.tracks.clear()
    p = b.component("R1").pads[0]           # SIG
    b.vias.append(Via(p.x, p.y + p.h / 2 + 0.3, "OTHER", diameter=0.8))
    assert _iii2(b) == "fail"


def test_via_clear_of_a_foreign_pad_is_not_a_short():
    b = _clean_board()
    p = b.component("R1").pads[0]
    b.vias.append(Via(p.x - p.w / 2 - 0.6, p.y - 3.0, "OTHER", diameter=0.8))
    assert _iii2(b) == "pass"


# ── SOIC land pattern — the pads must not short their neighbours ────────────
@pytest.mark.parametrize("pkg", ["SOIC-8", "SOIC-14", "SOIC-16"])
def test_soic_neighbouring_pads_do_not_touch(pkg):
    n = footprints.pin_count(pkg)
    comp = footprints.build("U1", pkg, {str(i): f"N{i}" for i in range(1, n + 1)},
                            x=10.0, y=10.0)
    comp.attrs["package"] = pkg
    b = _board([comp])
    assert _iii2(b) == "pass"
    pitch = 1.27
    assert all(p.h < pitch for p in comp.pads)   # narrow along the pitch
    assert all(p.w > p.h for p in comp.pads)     # long across the row


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


# ── III.4 — the SOT-23 class: a pin no declared pinout places ───────────────
def test_undetermined_pinout_is_a_failure_not_a_guess():
    """A SOT-23 whose part number has no pinout: build() used to put its pins on
    free pads in list order and this said 'unknown'. It now leaves them
    unconnected, so the board is missing connections the design needs: fail."""
    nl = {"name": "sot", "components": [
        {"ref": "Q1", "mpn": "MYSTERY-SOT", "package": "SOT-23",
         "pins": {"INPUT": "A", "OUTPUT": "B", "CTRL": "C"}}]}
    b = Board(name="sot", outline_w=20, outline_h=20,
              layers=[Layer("F.Cu", "signal")])
    warnings: list[str] = []
    b.components.append(footprints.build(
        "Q1", "SOT-23", {"INPUT": "A", "OUTPUT": "B", "CTRL": "C"}, x=10, y=10,
        warnings=warnings, mpn="MYSTERY-SOT"))
    assert all(p.net == "" for p in b.components[0].pads), "a pin was guessed onto a pad"
    assert any("left unconnected" in w for w in warnings)
    rep = verify_board(b, nl)
    f = _finding(rep, "III.4d")
    assert f.status == "fail"
    assert f.rung == "exact"
    assert "MYSTERY-SOT" in f.detail
    assert rep.gate()[0] is False


def test_a_package_alone_does_not_decide_a_transistor_pinout():
    """B/C/E on a SOT-23 with no part number: the package says nothing about
    the order (39 pin maps share that footprint in the KiCad library)."""
    q = footprints.build("Q1", "SOT-23", {"B": "BASE", "C": "LOAD", "E": "GND"})
    assert all(p.net == "" for p in q.pads)


def test_pin_collision_is_a_failure():
    """Two netlist pins resolving to the same footprint pad: one net is written
    over the other, silently. DIP-28 VCC->20 and AVCC->20 collide."""
    nl = {"name": "collide", "components": [
        {"ref": "U1", "mpn": "ATMEGA328P-PU", "package": "DIP-28",
         "pins": {"VCC": "P5V", "AVCC": "P3V3"}}]}
    b = Board(name="collide", outline_w=40, outline_h=40,
              layers=[Layer("F.Cu", "signal")])
    b.components.append(footprints.build(
        "U1", "DIP-28", {"VCC": "P5V", "AVCC": "P3V3"}, x=20, y=20,
        mpn="ATMEGA328P-PU"))
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


@pytest.mark.parametrize("name", ["IR_001", "IR_002", "IR_003", "IR_004", "IR_005"])
def test_template_boards_route_fully_with_no_short_and_no_drc_error(name):
    """Every template board, end to end. Until 2026-10-17 the RS-485 board
    (IR_005) routed an RS485_A via 0.035 mm from an RS485_B pad: III.2 failed
    and the kernel DRC, with no via-to-pad rule, reported zero errors. Fixing
    the router's via placement then cost the DHT22 board (IR_001) its VCC_5V
    route into R1, which only a width-aware fallback recovers; and the new
    rule found the GND stitching via on every small passive too close to the
    part's other pad."""
    from core import ir_examples
    from generators.netlist.pcb import PcbNetlistGenerator
    from pcb_engine import compile_board
    nl = PcbNetlistGenerator().generate(getattr(ir_examples, name))
    result = compile_board(nl)
    assert result.stats["unrouted"] == 0, result.stats
    assert result.stats["drc_errors"] == 0, result.violations
    assert result.ok, result.stats["failed_checks"]


def test_generation_reports_the_judges_count_not_the_routers():
    """The ledger's finding, pinned: the router's own `unrouted()` said 4 on a
    board that is fully routed, because it matched quantisation cells. Generation
    reports the judge's count and keeps the router's beside it; since the router
    counts by connectivity too (2026-10-17) the two must agree, so a gap between
    them is a bug in one of them."""
    from pcb_engine import compile_board
    result = compile_board(_dht22_netlist())
    assert result.stats["unrouted"] == 0
    assert result.stats["routed"] == result.stats["connections"]
    assert result.stats["router_unrouted"] == result.stats["unrouted"]
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


# ── III.1c / III.1d — plane nets (left out of required_connections) ─────────
def _plane_board(vias=True, wall=False):
    """Two 0603s whose pad 2 is GND, on a board with a GND pour on B.Cu.
    With `vias`, each GND pad drops a via; with `wall`, a signal track on B.Cu
    runs the full height of the board between them and cuts the pour in two."""
    b = Board(name="plane", outline_w=20, outline_h=20,
              layers=[Layer("F.Cu", "signal"), Layer("B.Cu", "signal", plane_net="GND")])
    b.components.extend([_part("R1", 5.0, 10.0, {"1": "SIG", "2": "GND"}),
                         _part("R2", 15.0, 10.0, {"1": "SIG", "2": "GND"})])
    if vias:
        for ref in ("R1", "R2"):
            p = next(p for p in b.component(ref).pads if p.pin == "2")
            b.vias.append(Via(p.x + 1.2, p.y, "GND"))
            b.tracks.append(Track("F.Cu", "GND", 0.3, [(p.x, p.y), (p.x + 1.2, p.y)]))
    if wall:
        b.tracks.append(Track("B.Cu", "WALL", 0.3, [(10.0, 0.0), (10.0, 20.0)]))
    return b


def test_plane_pad_with_no_way_down_is_a_failure():
    rep = verify_board(_plane_board(vias=False))
    f = _finding(rep, "III.1c")
    assert f.status == "fail" and f.rung == "exact"
    assert set(f.subjects) == {"R1.2", "R2.2"}


def test_plane_joins_pads_that_drop_vias():
    rep = verify_board(_plane_board())
    assert _finding(rep, "III.1c").status == "pass"
    f = _finding(rep, "III.1d")
    assert f.status == "pass" and f.rung == "sound"
    assert "no thermal spokes" in f.detail          # the model is stated


def test_a_track_across_the_plane_splits_it():
    rep = verify_board(_plane_board(wall=True))
    assert _finding(rep, "III.1c").status == "pass"   # each pad still reaches B.Cu
    assert _finding(rep, "III.1d").status == "fail"   # but not the same piece of it


# ── IV.1 — pitch and row span, not only the pad count ───────────────────────
def test_land_pattern_pitch_disagreement_is_a_failure(monkeypatch):
    real = footprints.PACKAGES["0603"]
    monkeypatch.setitem(footprints.PACKAGES, "0603",
                        lambda: footprints._chip(1.75, 0.85, 0.95))   # table says 1.55
    rep = verify_board(_board([_part("R1", 10.0, 10.0, {"1": "A", "2": "B"})]))
    f = _finding(rep, "IV.1")
    assert f.status == "fail" and "pitch" in f.detail
    assert real is not None


def test_every_package_matches_its_table_row():
    """Pitch = smallest distance between consecutive pad numbers; row = pad 1 to
    pad N. SOT-23's pitch is 2e = 1.90 under that definition."""
    import json
    import verify
    table = json.loads((Path(verify.__file__).with_name("land_patterns.json")).read_text())
    for pkg in footprints.PACKAGES:
        row = table[pkg]
        pitch, span = verify._pitch_and_row(footprints.build("X", pkg, {}))
        if row["pitch_mm"] is not None:
            assert abs(pitch - row["pitch_mm"]) <= verify.LAND_TOL, pkg
        if row["row_mm"] is not None:
            assert abs(span - row["row_mm"]) <= verify.LAND_TOL, pkg


def test_courtyard_against_the_datasheet_is_an_explicit_unknown():
    rep = verify_board(_clean_board())
    f = _finding(rep, "IV.3")
    assert f.status == "unknown" and f.rung == "unknown"


def test_report_carries_the_gate():
    d = verify_board(_plane_board(vias=False)).to_dict()
    assert d["gate"]["emit"] is False and "III.1c" in d["gate"]["reason"]
