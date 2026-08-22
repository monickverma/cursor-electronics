"""Characterization harness for the PCB placement pipeline.

WHY THIS EXISTS
    `backend/pcb_engine/` is ~2,400 lines that shipped into the API with a
    frontend tab and zero tests. This file does not attempt to test all of it.
    It pins down one thing: **what placement currently does**, so that a change
    to it is visible rather than a matter of opinion.

    You cannot tell whether semantic placement rules improved a board without a
    way to measure placement first. That is the whole purpose here.

    Routing is deliberately out of scope — `generate_candidates` is the slow,
    numpy-heavy part, and placement is what the next round of work changes.

WHAT IT CAUGHT ON THE FIRST RUN
    `footprints.PACKAGES` contained no surface-mount entries at all. Every
    `0402` passive in all five example IRs failed the footprint lookup and was
    silently dropped by `from_netlist()`. IR_003 and IR_004 — the RC filter and
    the voltage divider — compiled to **completely empty boards**, and the PCB
    tab was shipping that. `test_every_component_reaches_the_board` is the
    regression guard.

THE GOLDEN FILE
    `fixtures/pcb_placement_golden.json` records each component's position and
    the board's half-perimeter wirelength. It is a snapshot, not a target: when
    placement legitimately changes, regenerate it and read the diff.

        PCB_GOLDEN_REGEN=1 python -m pytest tests/test_pcb_placement.py

    A diff in that file is the review artifact. Never regenerate it to make a
    red test go green without reading what moved and why.
"""

import json
import os
from pathlib import Path

import pytest

from core.ir_examples import IR_001, IR_002, IR_003, IR_004, IR_005
from generators.netlist.pcb import PcbNetlistGenerator
from pcb_engine import from_netlist, place_constructive
import footprints


GOLDEN_PATH = Path(__file__).parent / "fixtures" / "pcb_placement_golden.json"
REGEN = os.environ.get("PCB_GOLDEN_REGEN") == "1"

TEMPLATES = {
    "dht22":    IR_001,
    "led":      IR_002,
    "rc_filter": IR_003,
    "divider":  IR_004,
    "modbus":   IR_005,
}

# Placement is on a 1.27mm grid; positions are exact floats, so this is a guard
# against float formatting drift, not a real tolerance.
POS_TOL = 1e-6


# ── Helpers ──────────────────────────────────────────────────────────────────

def build_board(ir):
    """CircuitIR → placed Board. The real pipeline, minus routing."""
    netlist = PcbNetlistGenerator().generate(ir)
    board, warnings = from_netlist(netlist)
    return place_constructive(board), warnings


def hpwl(board) -> float:
    """Half-perimeter wirelength — the standard placement quality metric.

    Sum over nets of (bounding box width + height) of that net's pads. Lower is
    usually better, but only usually: semantic placement deliberately trades
    wirelength for loop inductance, thermal spread and edge access. Read it as a
    number that changed, not a score that must fall.
    """
    nets: dict[str, list[tuple[float, float]]] = {}
    for pad in board.pads():
        if pad.net:
            nets.setdefault(pad.net, []).append((pad.x, pad.y))
    total = 0.0
    for pts in nets.values():
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        total += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return round(total, 4)


def snapshot(board) -> dict:
    return {
        "board_mm": [board.outline_w, board.outline_h],
        "hpwl_mm": hpwl(board),
        "components": {
            c.ref: [round(c.x, 4), round(c.y, 4)]
            for c in sorted(board.components, key=lambda c: c.ref)
        },
    }


def load_golden() -> dict:
    if not GOLDEN_PATH.exists():
        return {}
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


# ── The bug this harness was written to catch ────────────────────────────────

class TestComponentCoverage:
    @pytest.mark.parametrize("name", sorted(TEMPLATES))
    def test_every_component_reaches_the_board(self, name):
        """No component may be silently dropped between IR and board.

        `from_netlist()` skips any component whose package has no footprint. It
        warns, but the warning goes to a list the frontend does not surface, so
        the visible result is simply a board with parts missing.
        """
        ir = TEMPLATES[name]
        board, warnings = build_board(ir)
        placed = {c.ref for c in board.components}
        expected = {c.id for c in ir.components}
        missing = expected - placed
        assert not missing, (
            f"{name}: {sorted(missing)} never reached the board. "
            f"Packages: "
            f"{ {c.id: c.package for c in ir.components if c.id in missing} }. "
            f"Warnings: {warnings}"
        )

    @pytest.mark.parametrize("name", sorted(TEMPLATES))
    def test_no_component_is_left_at_the_origin(self, name):
        """A part still at (0,0) was never placed — it sits off the board."""
        board, _ = build_board(TEMPLATES[name])
        stuck = [c.ref for c in board.components if c.x == 0.0 and c.y == 0.0]
        assert not stuck, f"{name}: {stuck} never moved from the origin"


class TestFootprintLibrary:
    @pytest.mark.parametrize("pkg", ["0402", "0603", "0805", "1206", "1210",
                                     "SOT-23", "SOIC-8", "SOIC-14", "SOIC-16"])
    def test_surface_mount_packages_exist(self, pkg):
        assert pkg in footprints.PACKAGES

    @pytest.mark.parametrize("alias,canonical", [
        ("0402", "0402"), ("R0402", "0402"), ("C0603", "0603"),
        ("0805", "0805"), ("SOT23", "SOT-23"), ("SOIC8", "SOIC-8"),
        ("DIP-28", "DIP-28"), ("TO-92", "TO-92"),
    ])
    def test_package_aliases_normalize(self, alias, canonical):
        assert footprints.normalize_package(alias) == canonical

    def test_smd_pads_are_not_through_hole(self):
        """`shape == "th"` means the router may approach from any layer
        (router.py) and DRC skips the layer check (kernel.py). Calling an SMD
        pad through-hole invites a track that reaches it through the board."""
        comp = footprints.build("R1", "0402", {"A": "N1", "B": "N2"})
        assert {p.shape for p in comp.pads} == {"rect"}

    def test_through_hole_pads_still_are(self):
        comp = footprints.build("U1", "DIP-28", {"VCC": "V", "GND": "G"})
        assert {p.shape for p in comp.pads} == {"th"}

    def test_two_terminal_pin_names_map_to_pads(self):
        """A/B, +/- and ANODE/CATHODE must land deterministically, not via the
        free-pad fallback — otherwise a resistor's ends swap between runs."""
        warnings: list[str] = []
        r = footprints.build("R1", "0402", {"A": "NET_A", "B": "NET_B"},
                             warnings=warnings)
        c = footprints.build("C1", "0402", {"+": "NET_P", "-": "NET_M"},
                             warnings=warnings)
        assert {p.pin: p.net for p in r.pads} == {"1": "NET_A", "2": "NET_B"}
        assert {p.pin: p.net for p in c.pads} == {"1": "NET_P", "2": "NET_M"}
        assert warnings == [], f"unexpected fallback: {warnings}"

    def test_soic8_pinout_is_a_known_gap(self):
        """Documented limitation, asserted so it cannot regress quietly.

        Pin 1 is RO on a MAX485 and an output on an op-amp — there is no
        package-wide truth, so build() falls back to free-pad assignment and
        warns. IR_005's MAX485 therefore has arbitrary pin positions. The fix is
        per-part pinmaps, not a per-package guess. Until then the warning is the
        contract: it must keep being emitted.
        """
        warnings: list[str] = []
        footprints.build("U2", "SOIC-8",
                         {"RO": "n1", "DI": "n2", "VCC": "v", "GND": "g"},
                         warnings=warnings)
        assert any("assigned unknown pin" in w for w in warnings), (
            "SOIC-8 pin assignment became silent — if per-part pinmaps landed, "
            "delete this test; if not, the warning must stay."
        )


# ── Placement invariants ─────────────────────────────────────────────────────

class TestPlacementLegality:
    @pytest.mark.parametrize("name", sorted(TEMPLATES))
    def test_components_sit_inside_the_outline(self, name):
        board, _ = build_board(TEMPLATES[name])
        for c in board.components:
            assert 0 <= c.x - c.courtyard_w / 2, f"{name}/{c.ref} off the left edge"
            assert 0 <= c.y - c.courtyard_h / 2, f"{name}/{c.ref} off the top edge"
            assert c.x + c.courtyard_w / 2 <= board.outline_w, f"{name}/{c.ref} off the right edge"
            assert c.y + c.courtyard_h / 2 <= board.outline_h, f"{name}/{c.ref} off the bottom edge"

    @pytest.mark.parametrize("name", sorted(TEMPLATES))
    def test_courtyards_do_not_overlap(self, name):
        """`_legal()` enforces a 0.4mm gap between courtyards during placement.
        If two parts overlap in the finished board, that invariant broke."""
        board, _ = build_board(TEMPLATES[name])
        comps = board.components
        for i, a in enumerate(comps):
            for b in comps[i + 1:]:
                dx = abs(a.x - b.x) - (a.courtyard_w + b.courtyard_w) / 2
                dy = abs(a.y - b.y) - (a.courtyard_h + b.courtyard_h) / 2
                assert dx >= -1e-9 or dy >= -1e-9, (
                    f"{name}: {a.ref} and {b.ref} courtyards overlap "
                    f"(dx={dx:.3f}, dy={dy:.3f})"
                )

    @pytest.mark.parametrize("name", sorted(TEMPLATES))
    def test_placement_is_deterministic(self, name):
        """Same input, same board — twice. Without this the golden file below
        is meaningless and every diff is noise."""
        a, _ = build_board(TEMPLATES[name])
        b, _ = build_board(TEMPLATES[name])
        assert snapshot(a) == snapshot(b)


# ── Golden snapshot ──────────────────────────────────────────────────────────

class TestGoldenPlacement:
    def test_golden_file_exists(self):
        assert GOLDEN_PATH.exists() or REGEN, (
            f"{GOLDEN_PATH.name} missing. Regenerate with "
            f"PCB_GOLDEN_REGEN=1 python -m pytest {Path(__file__).name}"
        )

    @pytest.mark.parametrize("name", sorted(TEMPLATES))
    def test_placement_matches_golden(self, name):
        board, _ = build_board(TEMPLATES[name])
        current = snapshot(board)

        if REGEN:
            pytest.skip("regenerating golden file")

        golden = load_golden()
        assert name in golden, f"{name} not in golden file — regenerate it"
        expected = golden[name]

        assert set(current["components"]) == set(expected["components"]), (
            f"{name}: component set changed. "
            f"added={set(current['components']) - set(expected['components'])} "
            f"removed={set(expected['components']) - set(current['components'])}"
        )

        moved = {
            ref: (expected["components"][ref], xy)
            for ref, xy in current["components"].items()
            if abs(xy[0] - expected["components"][ref][0]) > POS_TOL
            or abs(xy[1] - expected["components"][ref][1]) > POS_TOL
        }
        assert not moved, (
            f"{name}: placement changed.\n"
            + "\n".join(f"    {r}: {was} -> {now}" for r, (was, now) in sorted(moved.items()))
            + f"\n  HPWL {expected['hpwl_mm']} -> {current['hpwl_mm']} "
              f"({current['hpwl_mm'] - expected['hpwl_mm']:+.4f} mm)\n"
              f"  If this change is intended, regenerate with "
              f"PCB_GOLDEN_REGEN=1 and commit the diff."
        )


def test_regenerate_golden():
    """Writes the golden file when PCB_GOLDEN_REGEN=1, otherwise skips."""
    if not REGEN:
        pytest.skip("set PCB_GOLDEN_REGEN=1 to regenerate")
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {name: snapshot(build_board(ir)[0]) for name, ir in sorted(TEMPLATES.items())}
    GOLDEN_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {GOLDEN_PATH}")
