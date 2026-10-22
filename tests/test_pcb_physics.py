"""
tests/test_pcb_physics.py — the layout-physics steps of the physics report
(reports/Physics layout validation - what the market does and what Circuit OS
can build.md, build table steps 0-5).

Each test was written to fail before its step was built.
"""
import pytest

from pcb_engine import verify_board, Finding
import verify
from board_ir import Board, Layer, Track
import footprints


def _part(ref, x, y, pins, pkg="0603"):
    comp = footprints.build(ref, pkg, pins, x=x, y=y)
    comp.attrs["package"] = pkg
    return comp


def _clean_board():
    b = Board(name="test", outline_w=20, outline_h=20,
              layers=[Layer("F.Cu", "signal"), Layer("B.Cu", "signal")])
    b.components.extend([_part("R1", 6.0, 10.0, {"1": "SIG", "2": "GND"}),
                         _part("R2", 13.0, 10.0, {"1": "SIG", "2": "GND"})])
    r1, r2 = b.component("R1"), b.component("R2")
    b.tracks.append(Track("F.Cu", "SIG", 0.2, [
        (r1.pads[0].x, 10.0), (r1.pads[0].x, 8.0),
        (r2.pads[0].x, 8.0), (r2.pads[0].x, 10.0)]))
    b.tracks.append(Track("F.Cu", "GND", 0.2, [
        (r1.pads[1].x, 10.0), (r1.pads[1].x, 12.0),
        (r2.pads[1].x, 12.0), (r2.pads[1].x, 10.0)]))
    return b


def _check(rep, check):
    return next((f for f in rep.findings if f.check == check), None)


# ─────────────────────────────────────────────────────────────────────────────
# Step 0 — the "simulated" rung, and "unknown" split three ways
# ─────────────────────────────────────────────────────────────────────────────
class TestRungs:
    def test_ladder_has_simulated_between_bounded_and_evidence(self):
        r = verify.RUNGS
        assert "simulated" in r and "rule check" in r
        assert r.index("bounded") < r.index("simulated") < r.index("evidence")
        assert r.index("simulated") < r.index("rule check") < r.index("evidence")

    def test_unknown_has_three_kinds(self):
        assert set(verify.UNKNOWN_KINDS) == {
            "not checkable", "checkable by simulation, not run", "checkable, tool named"}

    def test_an_unknown_without_a_kind_is_refused(self):
        with pytest.raises(ValueError):
            Finding("X", "claim", "unknown", "unknown", "why")

    def test_a_simulated_finding_must_name_its_tool(self):
        with pytest.raises(ValueError):
            Finding("X", "claim", "simulated", "pass", "a number")
        Finding("X", "claim", "simulated", "pass", "a number", tool="ngspice 44")

    def test_a_rung_outside_the_ladder_is_refused(self):
        with pytest.raises(ValueError):
            Finding("X", "claim", "proven", "pass")

    def test_every_unknown_on_a_real_board_carries_a_kind(self):
        rep = verify_board(_clean_board())
        unknowns = [f for f in rep.findings if f.rung == "unknown"]
        assert unknowns
        for f in unknowns:
            assert f.unknown_kind in verify.UNKNOWN_KINDS, f.check
            if f.unknown_kind == "checkable, tool named":
                assert f.tool, f.check

    def test_report_counts_unknowns_by_kind(self):
        d = verify_board(_clean_board()).to_dict()
        assert set(d["unknowns"]) <= set(verify.UNKNOWN_KINDS)
        assert sum(d["unknowns"].values()) == sum(
            1 for f in d["findings"] if f["rung"] == "unknown")
        assert all("unknown_kind" in f for f in d["findings"])


class TestBranchV:
    """Branch V was one blanket unknown saying everything needs 'an EM solver or a
    bench measurement'. That was false for DC drop, trace current and clearance."""

    def test_v_is_split_into_its_six_branches(self):
        rep = verify_board(_clean_board())
        assert _check(rep, "V") is None
        for c in ("V.1", "V.2", "V.3", "V.4", "V.5", "V.6"):
            assert _check(rep, c) is not None, c

    def test_emc_is_the_one_not_checkable(self):
        rep = verify_board(_clean_board())
        assert _check(rep, "V.5").unknown_kind == "not checkable"

    def test_dc_drop_current_and_clearance_are_not_said_to_need_an_em_solver(self):
        rep = verify_board(_clean_board())
        for c in ("V.3", "V.4", "V.6"):
            f = _check(rep, c)
            if f.rung == "unknown":
                assert f.unknown_kind != "not checkable", c
            assert "EM solver" not in f.detail, c


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — one Stackup object, and the ground plane realised as copper
# ─────────────────────────────────────────────────────────────────────────────
import json
from pathlib import Path

import board_ir
import stackup as stackup_mod
from scene3d import board_scene

NETLIST = json.loads((Path(board_ir.__file__).parent / "netlist_dht22.json").read_text())


class TestStackup:
    def test_default_is_a_1_6_mm_two_layer_fr4(self):
        s = stackup_mod.default_stackup(2)
        assert s.total_mm == pytest.approx(1.6, abs=1e-9)
        assert [c.name for c in s.copper] == ["F.Cu", "B.Cu"]
        assert s.copper[0].thickness_mm == pytest.approx(0.035)
        assert s.dielectric_between("F.Cu", "B.Cu") == pytest.approx(1.53)
        er = s.dielectrics[0].er
        assert er.lo < er.hi and 3.5 < er.lo and er.hi < 5.0
        assert s.source            # every figure says where it came from

    def test_the_0_48_mm_dielectric_is_gone_from_the_board(self):
        b = _clean_board()
        assert b.stackup.dielectric_between("F.Cu", "B.Cu") == pytest.approx(1.53)

    def test_old_board_json_without_a_stackup_gets_the_default(self):
        d = json.loads(_clean_board().to_json())
        d.pop("stackup")
        b = Board.from_json(json.dumps(d))
        assert b.stackup.total_mm == pytest.approx(1.6)

    def test_round_trip_keeps_a_custom_stackup(self):
        b = _clean_board()
        b.stackup = stackup_mod.two_layer(total_mm=0.8, copper_mm=0.07)
        b2 = Board.from_json(b.to_json())
        assert b2.stackup.total_mm == pytest.approx(0.8)
        assert b2.stackup.copper[0].thickness_mm == pytest.approx(0.07)

    def test_scene_draws_the_stackup_it_is_given(self):
        b = _clean_board()
        b.stackup = stackup_mod.two_layer(total_mm=0.8, copper_mm=0.07)
        sc = board_scene(b)
        assert sc["board"]["thickness"] == pytest.approx(0.8)
        assert sc["board"]["copper"] == pytest.approx(0.07)
        z = {l["name"]: l["z"] for l in sc["layers"]}
        assert z["F.Cu"] == pytest.approx(0.8) and z["B.Cu"] == pytest.approx(0.0)

    def test_the_stackup_must_add_up(self):
        with pytest.raises(ValueError):
            stackup_mod.two_layer(total_mm=0.05, copper_mm=0.035)


@pytest.fixture(scope="module")
def compiled():
    from compile_board import compile_board
    return compile_board(NETLIST, candidates=1)


class TestPour:
    def test_compiled_board_carries_real_ground_copper(self, compiled):
        b = compiled.board
        pours = [p for p in b.pours if p.net == NETLIST.get("ground_net", "GND")]
        assert pours, "the plane is declared but no copper was poured"
        p = pours[0]
        assert p.layer == "B.Cu"
        # most of a mostly-empty bottom layer is copper
        assert p.area_mm2() > 0.5 * b.outline_w * b.outline_h

    def test_pour_round_trips_through_json(self, compiled):
        b2 = Board.from_json(compiled.board.to_json())
        assert b2.pours[0].area_mm2() == pytest.approx(compiled.board.pours[0].area_mm2())

    def test_verifier_checks_the_realised_pour(self, compiled):
        rep = verify_board(compiled.board, NETLIST)
        for c in ("III.1e", "III.1f"):
            f = _check(rep, c)
            assert f is not None and f.status == "pass", (c, f and f.detail)

    def test_a_pour_over_foreign_copper_fails(self, compiled):
        b = compiled.board.copy()
        p = b.pours[0]
        # pour a cell straight under a non-ground pad on the pour's layer
        foreign = next(pd for c in b.components for pd in c.pads
                       if pd.net and pd.net != p.net and pd.shape == "th")
        p.add_cell(*p.cell_of(foreign.x, foreign.y))
        f = _check(verify_board(b, NETLIST), "III.1e")
        assert f.status == "fail"

    def test_a_pour_cut_away_from_a_pad_fails_the_join(self, compiled):
        b = compiled.board.copy()
        p = b.pours[0]
        p.rows = [[] for _ in p.rows]          # no copper at all
        assert _check(verify_board(b, NETLIST), "III.1f").status == "fail"

    def test_scene_carries_the_pour(self, compiled):
        sc = board_scene(compiled.board)
        assert sc["pours"] and sc["pours"][0]["net"] == compiled.board.pours[0].net
        assert sc["pours"][0]["rects"]


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Quilter-equivalent physics rule checks, constraints from the IR
# ─────────────────────────────────────────────────────────────────────────────
import layout_rules
from board_ir import Component, Pad, Via, NetClass, DiffPair
from pour import fill_planes


def _ic(ref, x, y, pins, kind="microcontroller"):
    """A part with pads on a 2.54 mm column, pins {num: net}."""
    pads = [Pad(ref, n, x, y + k * 2.54, 1.0, 1.0, net)
            for k, (n, net) in enumerate(pins.items())]
    return Component(ref, x, y, courtyard_w=3, courtyard_h=2.54 * len(pins) + 1,
                     pads=pads, attrs={"type": kind})


def _cap(ref, x, y, a, b):
    return Component(ref, x, y, courtyard_w=2.0, courtyard_h=1.0, attrs={"type": "capacitor"},
                     pads=[Pad(ref, "1", x - 0.75, y, 0.8, 0.9, a),
                           Pad(ref, "2", x + 0.75, y, 0.8, 0.9, b)])


NL = {"ground_net": "GND", "power_nets": ["VCC", "GND"]}


def _rule_board(cap_x):
    b = Board(name="rules", outline_w=40, outline_h=20,
              layers=[Layer("F.Cu"), Layer("B.Cu", plane_net="GND")])
    b.components = [_ic("U1", 5.0, 5.0, {"1": "VCC", "2": "GND", "3": "SIG"}),
                    _cap("C1", cap_x, 5.0, "VCC", "GND")]
    b.net_classes = [NetClass("power", ["VCC", "GND"], track_width=0.5, clearance=0.3, priority=10)]
    c = b.component("C1")
    b.tracks.append(Track("F.Cu", "VCC", 0.5, [(5.0, 5.0), (c.pads[0].x, 5.0)]))
    b.vias += [Via(5.0, 7.54, "GND"), Via(c.pads[1].x, 5.0, "GND")]
    return b


def _rule(findings, check):
    return next((f for f in findings if f.check == check), None)


class TestLayoutRules:
    def test_thresholds_are_cited_not_bare(self):
        for name, rule in layout_rules.RULES.items():
            assert rule.value > 0 and rule.source, name

    def test_close_decoupling_cap_passes(self):
        f = _rule(layout_rules.check_layout_rules(_rule_board(8.0), NL), "P.1")
        assert f.rung == "rule check" and f.status == "pass", f.detail

    def test_far_decoupling_cap_fails(self):
        f = _rule(layout_rules.check_layout_rules(_rule_board(25.0), NL), "P.1")
        assert f.status == "fail" and "C1" in f.detail

    def test_decap_is_found_by_its_nets_and_type_not_its_name(self):
        b = _rule_board(25.0)
        b.component("C1").ref = "X9"
        for p in b.component("X9").pads:
            p.ref = "X9"
        f = _rule(layout_rules.check_layout_rules(b, NL), "P.1")
        assert f.status == "fail" and "X9" in f.detail

    def test_decap_path_reports_length_and_vias(self):
        f = _rule(layout_rules.check_layout_rules(_rule_board(8.0), NL), "P.1b")
        assert f is not None and f.rung == "rule check"
        assert "mm" in f.detail

    def test_without_part_types_the_rule_says_unknown(self):
        b = _rule_board(8.0)
        for c in b.components:
            c.attrs.pop("type")
        f = _rule(layout_rules.check_layout_rules(b, NL), "P.1")
        assert f.status == "unknown" and f.unknown_kind == "checkable, tool named"

    def test_crystal_far_from_its_ic_fails(self):
        b = _rule_board(8.0)
        b.components[0].pads.append(Pad("U1", "4", 5.0, 12.62, 1.0, 1.0, "XTAL1"))
        b.components.append(Component("Y1", 30.0, 10.0, attrs={"type": "crystal"}, pads=[
            Pad("Y1", "1", 29.0, 10.0, 1.0, 1.0, "XTAL1"),
            Pad("Y1", "2", 31.0, 10.0, 1.0, 1.0, "XTAL2")]))
        f = _rule(layout_rules.check_layout_rules(b, NL), "P.2")
        assert f.status == "fail" and "Y1" in f.detail

    def test_width_span_fails_when_a_net_changes_width(self):
        b = _rule_board(8.0)
        b.tracks.append(Track("F.Cu", "VCC", 0.2, [(5.0, 5.0), (5.0, 2.0)]))
        f = _rule(layout_rules.check_layout_rules(b, NL), "P.3")
        assert f.status == "fail" and "VCC" in f.detail

    def test_bus_net_over_a_pour_gap_fails_ground_overlap(self):
        b = _rule_board(8.0)
        b.tracks.append(Track("F.Cu", "SIG", 0.25, [(5.0, 10.08), (35.0, 10.08)]))
        b.tracks.append(Track("B.Cu", "VCC", 1.5, [(20.0, 1.0), (20.0, 19.0)]))  # cuts the pour
        fill_planes(b)
        nl = {**NL, "net_types": {"SIG": "spi_sck"}}
        f = _rule(layout_rules.check_layout_rules(b, nl), "P.4")
        assert f.status == "fail" and "SIG" in f.detail

    def test_bus_net_over_whole_pour_passes(self):
        b = _rule_board(8.0)
        b.tracks.append(Track("F.Cu", "SIG", 0.25, [(5.0, 10.08), (35.0, 10.08)]))
        fill_planes(b)
        nl = {**NL, "net_types": {"SIG": "spi_sck"}}
        f = _rule(layout_rules.check_layout_rules(b, nl), "P.4")
        assert f.status == "pass", f.detail

    def test_diff_pair_spacing_out_of_span_fails(self):
        b = _rule_board(8.0)
        b.diff_pairs = [DiffPair("D", "DP", "DN", width=0.2, gap=0.15)]
        b.tracks += [Track("F.Cu", "DP", 0.2, [(10.0, 15.0), (30.0, 15.0)]),
                     Track("F.Cu", "DN", 0.2, [(10.0, 15.6), (30.0, 15.6)])]
        f = _rule(layout_rules.check_layout_rules(b, NL), "P.5")
        assert f.status == "fail"

    def test_verify_board_runs_the_layout_rules(self):
        rep = verify_board(_rule_board(25.0), NL)
        assert _check(rep, "P.1").status == "fail"

    def test_netlist_carries_net_types_from_the_ir(self):
        from generators.netlist.pcb import PcbNetlistGenerator
        from core.ir_examples import IR_002
        nl = PcbNetlistGenerator().generate(IR_002)
        assert nl["net_types"] and set(nl["net_types"].values()) - {"power", "ground"}


def test_a_rule_check_failure_warns_but_does_not_refuse_fab_files():
    """Rule-check thresholds are proposals until the owner confirms them; a miss
    is shown and named in the gate, but only a decided failure refuses."""
    rep = verify_board(_rule_board(25.0), NL)
    assert _check(rep, "P.1").status == "fail"
    assert all(f.check != "P.1" for f in rep.failed())
    assert any(f.check == "P.1" for f in rep.warnings())
    emit, why = rep.gate()
    assert "P.1" in why


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — layout-level current, and clearance/creepage from the IEC tables
# ─────────────────────────────────────────────────────────────────────────────
import iec60664
import layout_vi


def _power_board(width):
    b = Board(name="vi", outline_w=40, outline_h=20, layers=[Layer("F.Cu"), Layer("B.Cu")])
    b.components = [_cap("C1", 5.0, 10.0, "VCC", "GND"), _cap("C2", 30.0, 10.0, "VCC", "GND")]
    b.tracks.append(Track("F.Cu", "VCC", width, [(4.25, 10.0), (29.25, 10.0)]))
    return b


class TestTraceCurrent:
    def test_ipc2221_width_for_2a_on_1oz_outer(self):
        # IPC-2221: I = 0.048 dT^0.44 A^0.725 (A in mil^2) -> about 0.78 mm at 2 A, 10 K
        w = layout_vi.required_width_mm(2.0, 0.035, external=True, rise_k=10)
        assert 0.70 < w < 0.86

    def test_narrow_trace_for_its_current_fails(self):
        nl = {**NL, "net_currents_a": {"VCC": 2.0}}
        f = _rule(layout_vi.check_trace_current(_power_board(0.2), nl), "V.4")
        assert f.rung == "rule check" and f.status == "fail" and "VCC" in f.detail

    def test_wide_enough_trace_passes(self):
        nl = {**NL, "net_currents_a": {"VCC": 2.0}}
        f = _rule(layout_vi.check_trace_current(_power_board(1.0), nl), "V.4")
        assert f.status == "pass", f.detail

    def test_thicker_copper_from_the_stackup_needs_less_width(self):
        b = _power_board(0.5)
        nl = {**NL, "net_currents_a": {"VCC": 2.0}}
        assert _rule(layout_vi.check_trace_current(b, nl), "V.4").status == "fail"
        b.stackup = stackup_mod.two_layer(copper_mm=0.070)
        assert _rule(layout_vi.check_trace_current(b, nl), "V.4").status == "pass"

    def test_without_currents_it_is_unknown_and_names_the_input(self):
        f = _rule(layout_vi.check_trace_current(_power_board(0.2), NL), "V.4")
        assert f.status == "unknown" and f.unknown_kind == "checkable, tool named"

    def test_netlist_carries_currents_and_voltages_from_the_ir(self):
        from generators.netlist.pcb import PcbNetlistGenerator
        from core.ir_examples import IR_001
        nl = PcbNetlistGenerator().generate(IR_001)
        assert nl["net_currents_a"] and all(v > 0 for v in nl["net_currents_a"].values())
        assert "net_voltages" in nl


def _mains_board(gap):
    """A 230 V pad and a 5 V pad, edge to edge `gap` mm apart on F.Cu."""
    b = Board(name="mains", outline_w=40, outline_h=20, layers=[Layer("F.Cu"), Layer("B.Cu")])
    b.components = [
        Component("J1", 10.0, 10.0, attrs={"type": "connector"},
                  pads=[Pad("J1", "1", 10.0, 10.0, 2.0, 2.0, "L", shape="th")]),
        Component("C1", 11.0 + gap + 0.4, 10.0, attrs={"type": "capacitor"},
                  pads=[Pad("C1", "1", 11.0 + gap + 0.4, 10.0, 0.8, 0.9, "VCC")])]
    return b


MAINS = {"ground_net": "GND", "power_nets": ["VCC", "GND"],
         "net_voltages": {"L": 230.0, "VCC": 5.0, "GND": 0.0}}


class TestInsulation:
    def test_table_is_cited_and_marked_unverified(self):
        assert iec60664.SOURCE and iec60664.VERIFIED is False
        assert iec60664.creepage_mm(250, pollution=2, group="III") == pytest.approx(2.5)

    def test_reinforced_is_derived_from_the_table_not_a_constant(self):
        basic = iec60664.creepage_mm(250, pollution=2, group="III")
        assert iec60664.creepage_mm(250, pollution=2, group="III",
                                    insulation="reinforced") == pytest.approx(2 * basic)
        # a different material group moves the reinforced figure with it
        assert iec60664.creepage_mm(250, pollution=2, group="I", insulation="reinforced") \
            == pytest.approx(2 * iec60664.creepage_mm(250, pollution=2, group="I"))

    def test_clearance_reinforced_uses_the_next_impulse_step(self):
        assert iec60664.clearance_mm(230, ovc="II", pollution=2) == pytest.approx(1.5)
        assert iec60664.clearance_mm(230, ovc="II", pollution=2,
                                     insulation="reinforced") == pytest.approx(3.0)

    def test_mains_to_selv_at_3mm_fails_reinforced(self):
        f = _rule(layout_vi.check_insulation(_mains_board(3.0), MAINS), "V.6")
        assert f.status == "fail" and "reinforced" in f.detail
        assert f.rung == "sound"
        assert "5.0" in f.detail          # the required figure, from the table

    def test_mains_to_selv_at_6mm_passes(self):
        f = _rule(layout_vi.check_insulation(_mains_board(6.0), MAINS), "V.6")
        assert f.status == "pass", f.detail
        assert "unverified" in f.detail

    def test_a_declared_basic_class_is_honoured(self):
        nl = {**MAINS, "insulation": [{"a": ["L"], "b": ["VCC"], "class": "basic"}]}
        assert _rule(layout_vi.check_insulation(_mains_board(3.0), nl), "V.6").status == "pass"

    def test_low_voltage_boards_are_out_of_scope(self):
        nl = {**MAINS, "net_voltages": {"VCC": 5.0, "GND": 0.0}}
        f = _rule(layout_vi.check_insulation(_mains_board(0.5), nl), "V.6")
        assert f.status == "pass" and "50 V" in f.detail

    def test_without_voltages_it_is_unknown(self):
        f = _rule(layout_vi.check_insulation(_mains_board(3.0), NL), "V.6")
        assert f.status == "unknown"

    def test_verify_board_runs_v4_and_v6(self):
        rep = verify_board(_mains_board(3.0), MAINS)
        assert _check(rep, "V.6").status == "fail"
        assert _check(rep, "V.4") is not None
        emit, _ = rep.gate()
        assert not emit                    # a safety spacing failure refuses fab files


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — DC IR drop on the copper, one engine (numpy); padne blocked
# ─────────────────────────────────────────────────────────────────────────────
import dc_drop
from stackup import COPPER_RESISTIVITY_OHM_M as RHO


def _two_part(length, width, amps=1.0, gnd_track=True):
    """Source J1 at x=2, load U1 at x=2+length; VCC and GND as straight tracks."""
    b = Board(name="drop", outline_w=length + 8, outline_h=12,
              layers=[Layer("F.Cu"), Layer("B.Cu")])
    x0, x1 = 2.0, 2.0 + length
    b.components = [
        Component("J1", x0, 6, attrs={"type": "connector"},
                  pads=[Pad("J1", "1", x0, 4.0, 1.0, 1.0, "VCC"),
                        Pad("J1", "2", x0, 8.0, 1.0, 1.0, "GND")]),
        Component("U1", x1, 6, attrs={"type": "sensor", "current_a": amps},
                  pads=[Pad("U1", "1", x1, 4.0, 1.0, 1.0, "VCC"),
                        Pad("U1", "2", x1, 8.0, 1.0, 1.0, "GND")])]
    b.tracks.append(Track("F.Cu", "VCC", width, [(x0, 4.0), (x1, 4.0)]))
    if gnd_track:
        b.tracks.append(Track("F.Cu", "GND", width, [(x0, 8.0), (x1, 8.0)]))
    return b


DROP_NL = {"ground_net": "GND", "power_nets": ["VCC", "GND"],
           "net_voltages": {"VCC": 5.0, "GND": 0.0}}


class TestDcDrop:
    def test_straight_track_matches_rho_l_over_a(self):
        b = _two_part(20.0, 0.5)
        r = RHO * 20e-3 / (0.5e-3 * 0.035e-3)
        drops = dc_drop.rail_drops(b, DROP_NL)
        d = drops["VCC"]["U1"]
        assert d["rail_v"] == pytest.approx(r * 1.0, rel=0.01)
        assert d["ground_v"] == pytest.approx(r * 1.0, rel=0.01)
        assert d["total_v"] == pytest.approx(2 * r, rel=0.01)

    def test_drop_scales_with_the_stackup_copper(self):
        b = _two_part(20.0, 0.5)
        b.stackup = stackup_mod.two_layer(copper_mm=0.070)
        d = dc_drop.rail_drops(b, DROP_NL)["VCC"]["U1"]
        assert d["rail_v"] == pytest.approx(RHO * 20e-3 / (0.5e-3 * 0.070e-3), rel=0.01)

    def test_ground_through_the_pour_is_bounded_by_sheet_resistance(self):
        b = _two_part(18.0, 0.5, gnd_track=False)
        b.layers = [Layer("F.Cu", plane_net="GND"), Layer("B.Cu")]
        for c in b.components:
            g = next(p for p in c.pads if p.net == "GND")
            g.h = 3.0
            g.y = 8.5
        b.outline_h = 11.0
        fill_planes(b)
        d = dc_drop.rail_drops(b, DROP_NL)["VCC"]["U1"]
        # never less than a full-width sheet between the pads; the model only drops copper
        sheet = RHO / 0.035e-3
        widest = b.outline_h            # no pour can be wider than the board
        assert d["ground_v"] >= sheet * 17.0 / widest * 0.99
        assert d["ground_v"] < sheet * 17.0 / 2.0      # and far below a 2 mm strip

    def test_thin_long_rail_fails_the_budget(self):
        b = _two_part(60.0, 0.2)
        f = _rule(dc_drop.check_dc_drop(b, DROP_NL), "V.3")
        assert f.status == "fail" and f.rung == "simulated" and f.tool
        assert "U1" in f.detail

    def test_short_wide_rail_passes(self):
        f = _rule(dc_drop.check_dc_drop(_two_part(10.0, 1.0), DROP_NL), "V.3")
        assert f.status == "pass", f.detail

    def test_an_unconnected_load_fails(self):
        b = _two_part(20.0, 0.5)
        b.tracks = [t for t in b.tracks if t.net != "VCC"]
        f = _rule(dc_drop.check_dc_drop(b, DROP_NL), "V.3")
        assert f.status == "fail" and "not connected" in f.detail

    def test_without_a_source_it_is_unknown(self):
        b = _two_part(20.0, 0.5)
        b.component("J1").attrs["type"] = "resistor"
        f = _rule(dc_drop.check_dc_drop(b, DROP_NL), "V.3")
        assert f.status == "unknown" and f.unknown_kind == "checkable, tool named"

    def test_a_declared_source_overrides(self):
        b = _two_part(20.0, 0.5)
        b.component("J1").attrs["type"] = "resistor"
        f = _rule(dc_drop.check_dc_drop(b, {**DROP_NL, "rail_sources": {"VCC": "J1"}}), "V.3")
        assert f.status == "pass"

    def test_netlist_carries_per_part_current_onto_the_board(self):
        from generators.netlist.pcb import PcbNetlistGenerator
        from core.ir_examples import IR_001
        from compile_board import from_netlist
        nl = PcbNetlistGenerator().generate(IR_001)
        assert any("current_a" in c for c in nl["components"])
        b, _ = from_netlist(nl)
        assert any(c.attrs.get("current_a") for c in b.components)

    def test_verify_board_reports_dc_drop_in_v3(self):
        rep = verify_board(_two_part(60.0, 0.2), DROP_NL)
        assert _check(rep, "V.3").status == "fail"
        assert _check(rep, "V.3b") is not None      # AC, separately


def test_a_load_with_no_ground_pad_is_judged_on_its_rail_alone():
    b = _two_part(20.0, 0.5)
    u = b.component("U1")
    u.pads = [p for p in u.pads if p.net != "GND"]     # a pull-up: returns through others
    d = dc_drop.rail_drops(b, DROP_NL)["VCC"]["U1"]
    assert d["ground_v"] == 0.0 and d["total_v"] == pytest.approx(d["rail_v"])
    assert _rule(dc_drop.check_dc_drop(b, DROP_NL), "V.3").status == "pass"


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 (partial) — closed-form lumped PDN loop impedance; PyPEEC blocked
# ─────────────────────────────────────────────────────────────────────────────
import pdn


class TestPdn:
    def test_capacitance_values_parse(self):
        assert pdn.parse_farads("100nF") == pytest.approx(1e-7)
        assert pdn.parse_farads("0.1uF") == pytest.approx(1e-7)
        assert pdn.parse_farads("10µF") == pytest.approx(1e-5)
        assert pdn.parse_farads("100n") == pytest.approx(1e-7)
        assert pdn.parse_farads("banana") is None

    def test_trace_inductance_grows_with_length_and_height(self):
        a = pdn.trace_over_plane_h(5.0, 0.5, 1.53)
        assert a > 0
        assert pdn.trace_over_plane_h(10.0, 0.5, 1.53) == pytest.approx(2 * a)
        assert pdn.trace_over_plane_h(5.0, 0.5, 0.2) < a

    def test_via_inductance_goldfarb(self):
        # Goldfarb & Pucel: L = 0.2 h (ln(4h/d) + 1) nH, h and d in mm
        h, d = 1.6, 0.4
        import math
        assert pdn.via_h(h, d) == pytest.approx(0.2e-9 * h * (math.log(4 * h / d) + 1))

    def test_series_rlc_minimum_is_at_resonance(self):
        import math
        L, C, R = 2e-9, 1e-7, 0.02
        f0 = 1 / (2 * math.pi * math.sqrt(L * C))
        assert abs(pdn.z_series(f0, R, L, C)) == pytest.approx(R, rel=1e-6)

    def _board(self, cap_x=8.0, value="100nF"):
        b = _rule_board(cap_x)
        b.component("C1").attrs["value"] = value
        b.component("U1").attrs["current_a"] = 0.05
        fill_planes(b)
        return b

    def test_without_a_bandwidth_it_is_unknown_but_shows_the_numbers(self):
        f = _rule(pdn.check_pdn(self._board(), {**NL, "net_voltages": {"VCC": 5.0}}), "V.3b")
        assert f.status == "unknown" and f.unknown_kind == "checkable, tool named"
        assert "C1" in f.detail and "nH" in f.detail

    def test_meets_a_generous_target_within_the_band(self):
        nl = {**NL, "net_voltages": {"VCC": 5.0}, "pdn_bandwidth_hz": {"U1": 10e6}}
        f = _rule(pdn.check_pdn(self._board(), nl), "V.3b")
        assert f.status == "pass" and f.rung == "simulated" and f.tool, f.detail

    def test_misses_a_target_when_the_band_is_far_above_resonance(self):
        b = self._board()
        b.component("U1").attrs["current_a"] = 5.0                    # tiny target
        nl = {**NL, "net_voltages": {"VCC": 5.0}, "pdn_bandwidth_hz": {"U1": 500e6}}
        f = _rule(pdn.check_pdn(b, nl), "V.3b")
        assert f.status == "fail" and "U1" in f.detail

    def test_verify_board_reports_v3b_from_the_model(self):
        nl = {**NL, "net_voltages": {"VCC": 5.0}, "pdn_bandwidth_hz": {"U1": 10e6}}
        rep = verify_board(self._board(), nl)
        assert _check(rep, "V.3b").rung == "simulated"


# Regression, S7 2026-10-22 (PHYS-STEP-4 reopened): a relay coil on a two-pin
# connector J1 {VCC_5V, SW_LOAD} is a load, not the rail's source. V.3 failed a
# good board as "not connected" because J1 was taken as the source and had no
# ground pad.
def _relay_board():
    b = Board(name="relay", outline_w=40, outline_h=20, layers=[Layer("F.Cu"), Layer("B.Cu")])
    b.components = [
        Component("U1", 5, 10, attrs={"type": "microcontroller", "current_a": 0.05},
                  pads=[Pad("U1", "5V", 5.0, 8.0, 1.0, 1.0, "VCC_5V"),
                        Pad("U1", "GND", 5.0, 12.0, 1.0, 1.0, "GND"),
                        Pad("U1", "D7", 5.0, 14.0, 1.0, 1.0, "RELAY_CTRL")]),
        Component("J1", 30, 10, attrs={"type": "connector"},
                  pads=[Pad("J1", "1", 30.0, 8.0, 1.0, 1.0, "VCC_5V"),
                        Pad("J1", "2", 30.0, 12.0, 1.0, 1.0, "SW_LOAD")]),
        Component("Q1", 20, 14, attrs={"type": "transistor"},
                  pads=[Pad("Q1", "1", 19.0, 16.0, 0.8, 0.8, "GND"),
                        Pad("Q1", "2", 20.0, 16.0, 0.8, 0.8, "RELAY_CTRL"),
                        Pad("Q1", "3", 21.0, 16.0, 0.8, 0.8, "SW_LOAD")]),
        Component("D1", 25, 10, attrs={"type": "diode"},
                  pads=[Pad("D1", "1", 24.0, 10.0, 0.8, 0.8, "VCC_5V"),
                        Pad("D1", "2", 26.0, 10.0, 0.8, 0.8, "SW_LOAD")])]
    b.tracks += [Track("F.Cu", "VCC_5V", 0.8, [(5.0, 8.0), (30.0, 8.0)]),
                 Track("F.Cu", "VCC_5V", 0.8, [(24.0, 8.0), (24.0, 10.0)]),
                 Track("F.Cu", "GND", 0.8, [(5.0, 12.0), (5.0, 17.0), (19.0, 17.0), (19.0, 16.0)])]
    return b


RELAY_NL = {"ground_net": "GND", "power_nets": ["VCC_5V", "GND"],
            "net_voltages": {"VCC_5V": 5.0, "GND": 0.0}}


class TestDcDropSource:
    def test_a_load_connector_is_never_taken_as_the_source(self):
        assert dc_drop._source(_relay_board(), RELAY_NL, "VCC_5V") is None

    def test_relay_board_with_no_declared_source_is_unknown_not_a_failure(self):
        f = _rule(dc_drop.check_dc_drop(_relay_board(), RELAY_NL), "V.3")
        assert f.status == "unknown", f.detail
        assert "no rail source declared" in f.detail
        assert "not connected" not in f.detail

    def test_relay_board_gate_still_emits(self):
        rep = verify_board(_relay_board(), RELAY_NL)
        assert _check(rep, "V.3").status == "unknown"
        assert all(f.check != "V.3" for f in rep.failed())

    def test_a_connector_with_rail_and_ground_pins_is_a_source(self):
        b = _relay_board()
        b.component("J1").pads.append(Pad("J1", "3", 30.0, 16.0, 1.0, 1.0, "GND"))
        assert dc_drop._source(b, RELAY_NL, "VCC_5V").ref == "J1"

    def test_a_declared_source_without_a_ground_pad_leaves_the_ground_unknown(self):
        nl = {**RELAY_NL, "rail_sources": {"VCC_5V": "J1"}}
        f = _rule(dc_drop.check_dc_drop(_relay_board(), nl), "V.3")
        assert f.status == "unknown", f.detail
        assert "no ground pad" in f.detail and "not connected" not in f.detail
