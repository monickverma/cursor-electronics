"""
Component ablation (validation/ablation.py): open or short each part, ask ngspice
and the claims whether anything changed.

The fault constructors are pure and always run. The sweep needs ngspice; the
pinned rows are the ones the first run on 2026-10-21 found, so a change that
closes a gap shows up here as a test to update, not as silence.
"""

import shutil
from pathlib import Path

import pytest

from core.ir_examples import IR_003
from validation.ablation import NotTwoTerminal, open_component, short_component

_NGSPICE = shutil.which("ngspice_con") or shutil.which("ngspice") or (
    r"C:\msys64\ucrt64\bin\ngspice_con.exe" if Path(r"C:\msys64\ucrt64\bin\ngspice_con.exe").exists() else None)
requires_ngspice = pytest.mark.skipif(_NGSPICE is None, reason="ngspice not installed")


class TestFaults:
    def test_open_removes_the_part_and_its_connections_only(self):
        opened = open_component(IR_003, "C1")
        assert "C1" not in {c.id for c in opened.components}
        assert all(k.component_id != "C1" for k in opened.connections)
        assert {c.id for c in IR_003.components} - {c.id for c in opened.components} == {"C1"}

    def test_faults_never_touch_the_original(self):
        before = IR_003.model_dump_json()
        open_component(IR_003, "R1")
        short_component(IR_003, "R1")
        assert IR_003.model_dump_json() == before

    def test_a_short_is_a_milliohm_between_the_same_two_nodes(self):
        nodes = {k.node_id for k in IR_003.connections if k.component_id == "C1"}
        shorted = short_component(IR_003, "C1")
        part = next(c for c in shorted.components if c.id == "C1")
        assert part.value == "0.001"
        assert {k.node_id for k in shorted.connections if k.component_id == "C1"} == nodes

    def test_an_unknown_part_is_refused(self):
        with pytest.raises(ValueError):
            open_component(IR_003, "R99")

    def test_a_short_needs_two_terminals(self):
        from core.ir_examples import IR_001

        mcu = next(c.id for c in IR_001.components if c.type.value == "microcontroller")
        with pytest.raises(NotTwoTerminal):
            short_component(IR_001, mcu)


@requires_ngspice
class TestSweep:
    def test_every_rc_part_matters_and_an_open_is_caught(self):
        from validation.ablation import run_ablation

        rows = {(r.component, r.fault): r for r in run_ablation("rc_lowpass").rows}
        assert rows[("R1", "open")].verdict == "needed, and caught"
        assert rows[("C1", "open")].verdict == "needed, and caught"

    def test_a_shorted_bypass_cap_fails_the_rail_short_rule(self):
        # The rail into a 1 mΩ short: ngspice sees kiloamps. A gap on the first
        # run (2026-10-21); closed by rule.no_rail_short the same day.
        from validation.ablation import run_ablation

        rows = {(r.component, r.fault): r for r in run_ablation("led_indicator").rows}
        assert rows[("C1", "short")].physics_moved
        assert rows[("C1", "short")].verdict == "needed, and caught"
        assert "rule.no_rail_short" in rows[("C1", "short")].caught_by

    def test_the_remaining_gaps_are_pinned(self):
        # Faults ngspice sees that no claim fails. Closing one turns this red:
        # update the list, do not loosen the check.
        from validation.ablation import run_ablation

        gaps = {(name, r.component, r.fault)
                for name in ("rc_lowpass", "voltage_divider", "led_indicator",
                             "dht22_node", "rs485_node", "load_switch")
                for r in run_ablation(name).rows if r.verdict == "needed, NOT caught"}
        assert gaps == {
            ("rc_lowpass", "C1", "short"),       # proof.rc.cutoff goes silent, not fails
            ("led_indicator", "LED1", "short"),  # the LED proofs go silent
            ("dht22_node", "U1", "open"),        # only rail current moves; no claim reads it
            ("load_switch", "J1", "open"),       # the load is on no claim's path
        }
