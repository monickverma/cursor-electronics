"""
tests/test_pcb_kernel.py — the router's own geometry must be right about the
two questions it decides for itself: is this connection joined (it picks the
winning candidate by that count), and are these tracks far enough apart.

Each test builds a minimal board carrying one known case. The connectivity tests
mirror test_pcb_verify.py on purpose: kernel.open_connections and verify.py's
judge are two independent implementations of one question, and must agree.
"""
import pytest

# Import the package first: pcb_engine/__init__.py puts the engine's own
# directory on sys.path, which is what makes the bare-name imports below work.
from pcb_engine import compile_board  # noqa: F401
from board_ir import Board, Component, Keepout, Layer, NetClass, Pad, Track, Via
import kernel
from kernel import drc, open_connections, score
from router import to_dsn


def _board(*pads, outline=(40.0, 24.0)):
    b = Board(name="t", outline_w=outline[0], outline_h=outline[1],
              layers=[Layer("F.Cu", "signal"), Layer("B.Cu", "signal")])
    for i, p in enumerate(pads):
        b.components.append(Component(p.ref, p.x, p.y, pads=[p]))
    return b


def _pad(ref, x, y, net="SIG", w=1.0, h=1.0, layer="F.Cu", shape="rect"):
    return Pad(ref, "1", x, y, w, h, net, layer, shape)


# ── connectivity ─────────────────────────────────────────────────────────────
def test_copper_ending_inside_the_pad_across_a_cell_boundary_is_joined():
    """The shipped-board defect, reduced. The track ends 0.13 mm from pad B's
    centre — inside the pad — but the two points round into different 0.35 mm
    cells, which the old endpoint matcher read as open."""
    b = _board(_pad("R1", 20.0, 14.75), _pad("R2", 29.91, 14.65))
    b.tracks.append(Track("F.Cu", "SIG", 0.2, [(20.0, 14.75), (30.00, 14.75)]))
    # The case really straddles a cell boundary (else it proves nothing).
    assert round(30.00 / 0.35) != round(29.91 / 0.35)
    assert b.unrouted() == []


def test_two_stubs_that_never_meet_are_open():
    """Endpoint matching's other failure: a stub at each pad, no copper between
    them. Both pads 'have a track end', so the old check called it routed."""
    b = _board(_pad("R1", 10.0, 10.0), _pad("R2", 20.0, 10.0))
    b.tracks.append(Track("F.Cu", "SIG", 0.2, [(10.0, 10.0), (14.0, 10.0)]))
    b.tracks.append(Track("F.Cu", "SIG", 0.2, [(16.0, 10.0), (20.0, 10.0)]))
    assert len(b.unrouted()) == 1


def test_one_run_split_into_several_tracks_is_one_connection():
    """The router's neck-down cuts a run into head, body and tail tracks."""
    b = _board(_pad("R1", 10.0, 10.0), _pad("R2", 20.0, 10.0))
    b.tracks += [Track("F.Cu", "SIG", 0.2, [(10.0, 10.0), (10.8, 10.0)]),
                 Track("F.Cu", "SIG", 0.4, [(10.8, 10.0), (19.2, 10.0)]),
                 Track("F.Cu", "SIG", 0.2, [(19.2, 10.0), (20.0, 10.0)])]
    assert b.unrouted() == []


def _layer_hop_board(with_vias: bool):
    b = _board(_pad("R1", 10.0, 10.0), _pad("R2", 20.0, 10.0))
    b.tracks += [Track("F.Cu", "SIG", 0.2, [(10.0, 10.0), (13.0, 10.0)]),
                 Track("B.Cu", "SIG", 0.2, [(13.0, 10.0), (17.0, 10.0)]),
                 Track("F.Cu", "SIG", 0.2, [(17.0, 10.0), (20.0, 10.0)])]
    if with_vias:
        b.vias += [Via(13.0, 10.0, "SIG"), Via(17.0, 10.0, "SIG")]
    return b


def test_a_layer_change_needs_a_via():
    assert len(_layer_hop_board(with_vias=False).unrouted()) == 1
    assert _layer_hop_board(with_vias=True).unrouted() == []


def test_a_bottom_track_under_top_pads_does_not_join_them():
    """An SMD pad is on one layer. Only a through-hole pad meets the B.Cu track."""
    smd = _board(_pad("R1", 10.0, 10.0), _pad("R2", 20.0, 10.0))
    smd.tracks.append(Track("B.Cu", "SIG", 0.2, [(10.0, 10.0), (20.0, 10.0)]))
    assert len(smd.unrouted()) == 1

    th = _board(_pad("R1", 10.0, 10.0, shape="th"), _pad("R2", 20.0, 10.0, shape="th"))
    th.tracks.append(Track("B.Cu", "SIG", 0.2, [(10.0, 10.0), (20.0, 10.0)]))
    assert th.unrouted() == []


def _near_miss(gap):
    """Copper that stops `gap` mm (edge to edge) short of R2's pad."""
    b = _board(_pad("R1", 10.0, 10.0), _pad("R2", 20.0, 10.0))
    end_x = 20.0 - 0.5 - 0.1 - gap
    b.tracks.append(Track("F.Cu", "SIG", 0.2, [(10.0, 10.0), (end_x, 10.0)]))
    return b


def test_a_gap_inside_the_contact_tolerance_is_joined():
    assert _near_miss(0.03).unrouted() == []
    # ...and it is the tolerance doing it, not the copper reaching the pad.
    assert len(open_connections(_near_miss(0.03), tol=0.0)) == 1


def test_a_gap_wider_than_the_contact_tolerance_is_open():
    assert len(_near_miss(0.10).unrouted()) == 1


def test_the_kernel_tolerance_is_the_verifiers():
    """Two judges with two tolerances would disagree on exactly the near misses."""
    import verify
    assert kernel.CONTACT_TOL == verify.CONTACT_TOL


def test_foreign_copper_does_not_join_a_net():
    """A track of another net bridging both pads is a short, not a connection."""
    b = _board(_pad("R1", 10.0, 10.0), _pad("R2", 20.0, 10.0))
    b.tracks.append(Track("F.Cu", "OTHER", 0.2, [(10.0, 10.0), (20.0, 10.0)]))
    assert len(open_connections(b)) == 1


def test_pads_at_one_point_on_two_layers_are_not_joined_by_position():
    """Two pads of one net at the same coordinates, one per side, no via. A
    lookup by (net, centre) folds them into one entry and calls the connection
    joined; asking about the pads themselves does not."""
    b = _board(_pad("U1", 10.0, 10.0, layer="F.Cu"),
               _pad("U2", 10.0, 10.0, layer="B.Cu"))
    assert len(b.required_connections()) == 1
    assert len(b.unrouted()) == 1
    b.vias.append(Via(10.0, 10.0, "SIG"))
    assert b.unrouted() == []


def test_required_pairs_are_the_required_connections():
    b = _board(_pad("R1", 10.0, 10.0), _pad("R2", 20.0, 10.0),
               _pad("R3", 15.0, 15.0))
    assert [(a.center, c.center) for a, c in b.required_pairs()] == \
           [(k.a, k.b) for k in b.required_connections()]


def test_score_counts_open_connections_by_connectivity():
    b = _board(_pad("R1", 20.0, 14.75), _pad("R2", 29.91, 14.65))
    b.tracks.append(Track("F.Cu", "SIG", 0.2, [(20.0, 14.75), (30.00, 14.75)]))
    assert score(b).unrouted == 0
    b.tracks.clear()
    assert score(b).unrouted == 1


def test_the_kernel_and_the_judge_agree_on_a_partly_routed_board():
    """The demo board leaves several connections open on every seed, so this
    compares the two implementations on both answers, connection by connection."""
    from board_ir import demo_board
    from router import AStarRouter
    from verify import unrouted_connections
    b = AStarRouter().route(demo_board(), seed=0)
    key = lambda c: (c.net, c.a, c.b)
    mine = {key(c) for c in open_connections(b)}
    assert mine, "the demo board should leave something open to compare"
    assert mine == {key(c) for c in unrouted_connections(b)}


# ── DRC ──────────────────────────────────────────────────────────────────────
def _pair(sep, clearance=0.3, width=0.2):
    b = _board()
    b.net_classes.append(NetClass("wide", ["A", "B"], track_width=width,
                                  clearance=clearance))
    b.tracks += [Track("F.Cu", "A", width, [(5.0, 10.0), (20.0, 10.0)]),
                 Track("F.Cu", "B", width, [(5.0, 10.0 + sep), (20.0, 10.0 + sep)])]
    return b


def test_drc_measures_pairs_whose_clearance_exceeds_their_widths():
    """0.2 mm tracks at a 0.3 mm clearance need 0.5 mm centre to centre. At 0.45
    the old broad phase (boxes grown by the width alone, 0.4 mm in all) culled
    the pair before it was measured, and DRC reported nothing."""
    vs = [v for v in drc(_pair(0.45)) if v.rule == "clearance.track_track"]
    assert len(vs) == 1
    assert vs[0].measured == pytest.approx(0.45)
    assert vs[0].required == pytest.approx(0.5)


def test_drc_passes_the_same_pair_once_it_is_clear():
    assert not [v for v in drc(_pair(0.55)) if v.rule == "clearance.track_track"]


def test_drc_measures_a_via_against_a_foreign_pad():
    """The RS-485 short, reduced: an A via 0.035 mm from a B pad of an 0603.
    The kernel had no via-to-pad rule, so the board scored zero DRC errors and
    only verify.py's III.2 saw the short."""
    b = _board(_pad("R1", 13.135, 10.12, net="B", w=0.6, h=0.65))
    b.vias.append(Via(12.4, 10.4, net="A", drill=0.4, diameter=0.8))
    vs = [v for v in drc(b) if v.rule == "clearance.via_pad"]
    assert len(vs) == 1 and vs[0].nets == ("A", "B")


def test_drc_measures_a_via_on_either_layer():
    """A via is plated through: a pad on B.Cu is as close as one on F.Cu."""
    b = _board(_pad("R1", 10.0, 10.0, net="B", layer="B.Cu"))
    b.vias.append(Via(11.0, 10.0, net="A", drill=0.4, diameter=0.8))
    assert [v for v in drc(b) if v.rule == "clearance.via_pad"]


def test_drc_passes_a_via_clear_of_foreign_pads():
    b = _board(_pad("R1", 10.0, 10.0, net="B"))
    b.vias.append(Via(12.0, 10.0, net="A", drill=0.4, diameter=0.8))
    b.vias.append(Via(10.0, 10.0, net="B", drill=0.4, diameter=0.8))
    assert not [v for v in drc(b) if v.rule.startswith("clearance.via_")]


def test_drc_measures_two_vias_of_different_nets():
    b = _board(_pad("R1", 30.0, 10.0))
    b.vias += [Via(10.0, 10.0, net="A", drill=0.4, diameter=0.8),
               Via(10.9, 10.0, net="B", drill=0.4, diameter=0.8)]
    vs = [v for v in drc(b) if v.rule == "clearance.via_via"]
    assert len(vs) == 1 and vs[0].measured == pytest.approx(0.9)


# ── pad ↔ pad (F-0002) ───────────────────────────────────────────────────────
# The kernel had no pad-to-pad rule. Two parts whose pads touched, two pads of
# one footprint that overlapped, a through-hole pad over a bottom-side SMD pad:
# each scored zero DRC errors while verify.py's III.2 failed it.
def _part(ref, *pads, x=10.0, courtyard=1.0, side="top"):
    return Component(ref, x, 10.0, side=side, courtyard_w=courtyard,
                     courtyard_h=courtyard, pads=list(pads))


def _pads_board(*parts):
    b = Board(name="t", outline_w=30, outline_h=30,
              layers=[Layer("F.Cu", "signal"), Layer("B.Cu", "signal")])
    b.components.extend(parts)
    return b


def _short_boards():
    return {
        "two parts touch": _pads_board(
            _part("R1", Pad("R1", "1", 10.0, 10.0, 1.6, 1.0, "A")),
            _part("R2", Pad("R2", "1", 11.5, 10.0, 1.6, 1.0, "B"), x=11.5)),
        "one footprint overlaps": _pads_board(
            _part("U1", Pad("U1", "1", 10.0, 10.0, 1.0, 1.0, "A"),
                  Pad("U1", "2", 10.9, 10.0, 1.0, 1.0, "B"), courtyard=4.0)),
        "th over bottom smd": _pads_board(
            _part("J1", Pad("J1", "1", 10.0, 10.0, 1.6, 1.6, "A", "F.Cu", "th")),
            _part("R3", Pad("R3", "1", 11.2, 10.0, 1.0, 1.0, "B", "B.Cu"),
                  x=11.2, side="bottom")),
    }


@pytest.mark.parametrize("case", list(_short_boards()))
def test_drc_reports_pads_of_two_nets_that_touch(case):
    vs = [v for v in drc(_short_boards()[case]) if v.rule == "short.pad_pad"]
    assert len(vs) == 1 and set(vs[0].nets) == {"A", "B"}
    assert vs[0].severity == "error"


@pytest.mark.parametrize("case", list(_short_boards()))
def test_the_kernel_reports_every_pad_short_the_judge_finds(case):
    """Two implementations of one question: the router must not ship a board
    the judge refuses for a short the router could have measured."""
    from verify import verify_board
    b = _short_boards()[case]
    judged = next(f for f in verify_board(b).findings if f.check == "III.2")
    assert judged.status == "fail"
    assert any(v.severity == "error" and set(v.nets) == {"A", "B"} for v in drc(b))


def test_drc_passes_smd_pads_on_opposite_sides():
    """Top and bottom SMD pads at one point share no copper."""
    b = _pads_board(
        _part("R1", Pad("R1", "1", 10.0, 10.0, 1.0, 1.0, "A", "F.Cu")),
        _part("R2", Pad("R2", "1", 10.0, 10.0, 1.0, 1.0, "B", "B.Cu"), side="bottom"))
    assert not [v for v in drc(b) if v.rule.endswith("pad_pad")]


def test_drc_measures_pads_of_two_parts_closer_than_the_clearance():
    b = _pads_board(
        _part("R1", Pad("R1", "1", 10.0, 10.0, 1.0, 1.0, "A")),
        _part("R2", Pad("R2", "1", 11.1, 10.0, 1.0, 1.0, "B"), x=12.0))
    vs = [v for v in drc(b) if v.rule == "clearance.pad_pad"]
    assert len(vs) == 1 and vs[0].measured == pytest.approx(0.1)


def test_drc_leaves_a_footprints_own_pitch_to_the_footprint():
    """A 0.1 mm gap between two pads of one part is the land pattern's design,
    not something placement or routing chose; only contact is reported."""
    b = _pads_board(_part("U1", Pad("U1", "1", 10.0, 10.0, 1.0, 1.0, "A"),
                          Pad("U1", "2", 11.1, 10.0, 1.0, 1.0, "B"), courtyard=4.0))
    assert not [v for v in drc(b) if v.rule.endswith("pad_pad")]


# ── DSN export ───────────────────────────────────────────────────────────────
def _dsn_board():
    b = _board(_pad("R1", 10.0, 10.0), _pad("R2", 20.0, 10.0, shape="th"))
    b.net_classes.append(NetClass("power", ["SIG"], track_width=0.4,
                                  via_diameter=0.6, via_drill=0.3))
    b.keepouts.append(Keepout("wire", None, 1.0, 1.0, 2.0, 2.0))
    return b


def _block(dsn, head):
    """The lines of one `(padstack "name"` block, up to its `(attach off))`."""
    lines = dsn.splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip().startswith(head))
    j = next(k for k in range(i, len(lines)) if "(attach off))" in lines[k])
    return lines[i:j + 1]


def test_dsn_coordinates_are_in_the_declared_unit():
    """KiCad's exporter writes `(unit um)` and micrometres. This one declared mm
    and wrote ten-thousandths, so a 40 mm board went out 400 m wide."""
    dsn = to_dsn(_dsn_board())
    assert "(unit um)" in dsn and "(resolution um 10)" in dsn
    assert "(boundary (rect pcb 0 0 40000 24000))" in dsn


def test_dsn_declares_vias_and_each_class_uses_one():
    """Without a via Freerouting cannot change layer, so a two-layer comparison
    against this router would be one layer against two."""
    dsn = to_dsn(_dsn_board())
    assert '(via "Via[0-1]_800:400_um" "Via[0-1]_600:300_um")' in dsn
    stack = _block(dsn, '(padstack "Via[0-1]_600:300_um"')
    assert any("(circle F.Cu 600)" in l for l in stack)
    assert any("(circle B.Cu 600)" in l for l in stack)
    assert '(class power "SIG" (circuit (use_via "Via[0-1]_600:300_um"))' in dsn


def test_dsn_puts_an_smd_pad_on_its_own_layer_only():
    dsn = to_dsn(_dsn_board())
    smd = " ".join(_block(dsn, '(padstack "ps_R1_1"'))
    th = " ".join(_block(dsn, '(padstack "ps_R2_1"'))
    assert "F.Cu" in smd and "B.Cu" not in smd
    assert "F.Cu" in th and "B.Cu" in th


def test_dsn_keepout_on_no_layer_covers_every_layer():
    dsn = to_dsn(_dsn_board())
    assert '(keepout "" (rect F.Cu 1000 1000 3000 3000))' in dsn
    assert '(keepout "" (rect B.Cu 1000 1000 3000 3000))' in dsn


def test_dsn_is_balanced():
    dsn = to_dsn(_dsn_board())
    assert dsn.count("(") == dsn.count(")")
