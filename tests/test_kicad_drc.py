"""
tests/test_kicad_drc.py — stage 4: KiCad's DRC as a second rule engine.

Each trap the plan names has a test: a rule file KiCad drops must refuse the
result (the sentinel), a check KiCad ignores by default must still run (the
policy table), a DRC that did not run must never read as clean. Seeded faults
must reach KiCad and the kernel alike, and the differential harness must see
the broad-phase bug the kernel had until 2026-10-17.
"""
import pytest

import pcb_engine  # noqa: F401  — puts the engine directory on sys.path
from board_ir import Board, Component, Layer, NetClass, Pad, Track
import kernel
import kicad_cli
import kicad_drc
from kicad_drc import (POLICY, REQUIRED, SENTINEL, SEVERITIES, compare_engines,
                       parse_report, write_dru)

requires_kicad = pytest.mark.skipif(not kicad_cli.available(),
                                    reason="kicad-cli not installed")

_SENTINEL_HIT = {"type": "assertion_failure", "severity": "error",
                 "description": f"Assertion failure (rule '{SENTINEL}')", "items": []}


def _resistor(ref, x, y, n1, n2):
    return Component(ref, x, y, courtyard_w=3.0, courtyard_h=1.4, pads=[
        Pad(ref, "1", x - 0.75, y, 0.8, 0.8, n1), Pad(ref, "2", x + 0.75, y, 0.8, 0.8, n2)])


def _board() -> Board:
    """Two nets, each routed between two resistors, nothing wrong."""
    b = Board(name="drc", outline_w=30, outline_h=20, layers=[Layer("F.Cu"), Layer("B.Cu")])
    b.components = [_resistor("R1", 5, 5, "A", "B"), _resistor("R2", 15, 5, "A", "B"),
                    _resistor("R3", 5, 15, "C", "D"), _resistor("R4", 15, 15, "C", "D")]
    b.net_classes = [NetClass("default", b.nets(), track_width=0.2, clearance=0.25)]
    b.tracks = [Track("F.Cu", "A", 0.2, [(4.25, 5), (4.25, 3), (14.25, 3), (14.25, 5)]),
                Track("F.Cu", "B", 0.2, [(5.75, 5), (5.75, 7), (15.75, 7), (15.75, 5)]),
                Track("F.Cu", "C", 0.2, [(4.25, 15), (4.25, 13), (14.25, 13), (14.25, 15)]),
                Track("F.Cu", "D", 0.2, [(5.75, 15), (5.75, 17), (15.75, 17), (15.75, 15)])]
    return b


# ─────────────────────────────────────────────────────────────────────────────
# policy and parsing, no KiCad needed
# ─────────────────────────────────────────────────────────────────────────────
def test_sentinel_is_always_the_last_rule():
    text = write_dru(['(rule "w" (constraint track_width (min 0.2mm)))'])
    assert text.startswith("(version 1)\n")
    assert text.rstrip().endswith('"A.Layer == \'F.Cu\'"))')
    assert text.index('(rule "w"') < text.index(SENTINEL)


def test_missing_sentinel_means_rules_not_loaded():
    res = parse_report({"violations": [], "unconnected_items": []}, 0)
    assert not res.ran and not res.ok
    assert "rules not loaded" in res.refusals[0]


@pytest.mark.parametrize("code", [1, 3, 139])
def test_a_drc_that_did_not_run_is_never_clean(code):
    res = parse_report({"violations": [_SENTINEL_HIT]}, code)
    assert not res.ok and "did not run" in res.refusals[0]


def test_counts_are_by_type_and_noise_never_gates():
    rep = {"violations": [_SENTINEL_HIT,
                          {"type": "lib_footprint_issues", "description": "", "items": []},
                          {"type": "via_dangling", "description": "", "items": []}],
           "unconnected_items": []}
    res = parse_report(rep, 5)
    assert res.ok and res.ran
    assert res.by_type == {"lib_footprint_issues": 1, "via_dangling": 1}
    assert [v["type"] for v in res.advisory] == ["via_dangling"]


def test_an_unknown_violation_type_fails_closed():
    rep = {"violations": [_SENTINEL_HIT,
                          {"type": "new_in_kicad_11", "description": "", "items": []}]}
    res = parse_report(rep, 5)
    assert not res.ok and res.unknown_types == ["new_in_kicad_11"]


def test_a_required_check_kicad_skipped_refuses():
    rep = {"violations": [_SENTINEL_HIT],
           "ignored_checks": [{"key": "missing_courtyard", "description": ""}]}
    res = parse_report(rep, 0)
    assert res.ignored_required == ["missing_courtyard"] and not res.ok


def test_policy_lifts_checks_kicad_demotes():
    """KiCad's defaults (board_design_settings.cpp) ignore missing courtyards
    and footprint type mismatches and only warn on slivers; the project file
    written for every board must say otherwise."""
    assert SEVERITIES["missing_courtyard"] == "error"
    assert SEVERITIES["copper_sliver"] == "error"
    assert SEVERITIES["footprint_type_mismatch"] == "warning"
    assert all(POLICY[k] == REQUIRED for k in ("clearance", "shorting_items",
                                                "unconnected_items", "tracks_crossing"))


def test_item_nets_reads_kicad_labels():
    v = {"items": [{"description": "Pad 2 [D] of R3 on F.Cu"},
                   {"description": "Track [<no net>] on F.Cu, length 1 mm"},
                   {"description": "Track [C] on F.Cu, length 10.0000 mm"}]}
    assert kicad_drc.item_nets(v) == ("D", "C")


# ─────────────────────────────────────────────────────────────────────────────
# through KiCad
# ─────────────────────────────────────────────────────────────────────────────
@requires_kicad
def test_clean_board_passes_with_the_sentinel_seen(tmp_path):
    b = _board()
    rt, res = kicad_drc.check_board(b, tmp_path, "clean")
    assert rt.ok, rt.problems
    assert res.ran and res.sentinel_fired
    assert res.ok, res.refusals
    assert res.ignored_required == []
    assert compare_engines(b, res)["agree"]


@requires_kicad
def test_a_rule_file_kicad_drops_refuses_the_result(tmp_path):
    rt, res = kicad_drc.check_board(_board(), tmp_path, "badrule",
                                    rules=['(rule "x" (layer "Q.Cu") (constraint clearance (min 0.2mm)))'])
    assert rt.ok
    assert not res.sentinel_fired
    assert any("rules not loaded" in r for r in res.refusals)


@requires_kicad
def test_a_custom_rule_that_loads_is_enforced(tmp_path):
    """The other side of the sentinel: a valid rule file is read and acted on."""
    rt, res = kicad_drc.check_board(_board(), tmp_path, "wide",
                                    rules=['(rule "wide" (constraint track_width (min 0.3mm)))'])
    assert res.sentinel_fired
    assert res.by_type.get("track_width", 0) > 0 and not res.ok


@requires_kicad
def test_a_cut_track_is_an_open_to_both_engines(tmp_path):
    b = _board()
    b.tracks[1].points = b.tracks[1].points[:2]           # net B no longer reaches R2
    rt, res = kicad_drc.check_board(b, tmp_path, "open")
    assert not res.ok and res.by_type.get("unconnected_items")
    cmp = compare_engines(b, res)
    assert cmp["open"]["kicad"] == ["B"] and cmp["open"]["agree"]


@requires_kicad
def test_a_bridge_is_a_short_to_both_engines(tmp_path):
    b = _board()
    b.tracks.append(Track("F.Cu", "A", 0.2, [(14.25, 5), (15.75, 5)]))   # R2.1 to R2.2
    rt, res = kicad_drc.check_board(b, tmp_path, "short")
    assert not res.ok and res.by_type.get("shorting_items")
    cmp = compare_engines(b, res)
    assert ["A", "B"] in cmp["short"]["kicad"]
    assert cmp["short"]["agree"], cmp["short"]


@requires_kicad
def test_harness_catches_the_old_broad_phase_bug(tmp_path):
    """0.2 mm tracks at a 0.25 mm clearance, 0.42 mm apart: a 0.22 mm gap, a real
    violation. Until 2026-10-17 the kernel's broad phase padded boxes by width
    alone and never measured this pair. KiCad sees it; replaying the old kernel
    result, the harness must report it as KiCad's alone."""
    b = _board()
    b.tracks[2].points = [(4.25, 15), (4.25, 9.42), (14.25, 9.42), (14.25, 15)]
    b.tracks[1].points = [(5.75, 5), (5.75, 9.0), (15.75, 9.0), (15.75, 5)]
    rt, res = kicad_drc.check_board(b, tmp_path, "parallel")
    assert ["B", "C"] in [sorted(kicad_drc.item_nets(v)) for v in res.of_type("clearance")]

    today = kernel.drc(b)
    assert ["B", "C"] in compare_engines(b, res, today)["clearance"]["kernel"]
    assert compare_engines(b, res, today)["clearance"]["agree"]

    old = [v for v in today if not (v.rule == "clearance.track_track"
                                    and set(v.nets) == {"B", "C"})]
    cmp = compare_engines(b, res, old)
    assert cmp["clearance"]["kicad_only"] == [["B", "C"]]
    assert not cmp["agree"]
