"""
tests/test_pcb_decoupling_placement.py — a decoupling cap is placed at the pin
it decouples (F-S2-R001-6).

The judge measured C1's rail pad 5.07 mm from the ATmega's AVCC and 10.98 mm
from its VCC; the Olimex reference board puts its cap 1.65 mm away. The placer
put each part where it added the least wirelength to the NEAREST placed pad of
each net, so a 100 nF cap on VCC_5V/GND sat next to whatever rail pad was
closest, which was rarely the IC's supply pin.

The gap rule (benchmark_loop_plan.md §6) is: within the reference + 2 mm and
within 6 mm. These tests hold the placer to 3 mm from the cap's rail pad to the
supply pin it serves, and give each cap a different supply pin when an IC has
several.
"""
import math

import pytest

from core import ir_examples
from generators.netlist.pcb import PcbNetlistGenerator
from pcb_engine import compile_board, from_netlist, place_constructive

NEAR_MM = 3.0


def _placed(nl):
    return place_constructive(from_netlist(nl)[0])


def _served(b, cap_ref, ic_ref="U1", ground="GND"):
    """{pin: mm} from the cap's rail pad to each IC pad on the same rail."""
    rail = next(p for p in b.component(cap_ref).pads if p.net != ground)
    return {p.pin: math.dist(rail.center, p.center)
            for p in b.component(ic_ref).pads if p.net == rail.net}


@pytest.mark.parametrize("name", ["IR_001", "IR_002", "IR_005"])
def test_the_template_decoupling_cap_sits_at_a_supply_pin(name):
    nl = PcbNetlistGenerator().generate(getattr(ir_examples, name))
    d = _served(_placed(nl), "C1")
    assert min(d.values()) <= NEAR_MM, d


def _two_caps(n_caps):
    comps = [
        {"ref": "U1", "mpn": "ATmega328P-PU", "package": "DIP-28", "type": "microcontroller",
         "pins": {"VCC": "VCC_5V", "AVCC": "VCC_5V", "GND": "GND", "D2": "SIG"}},
        {"ref": "U2", "mpn": "DHT22", "package": "4-pin SIP", "type": "sensor",
         "pins": {"VCC": "VCC_5V", "GND": "GND", "DATA": "SIG"}},
        {"ref": "R1", "mpn": "RC0402FR-0710KL", "package": "0402", "type": "resistor",
         "pins": {"A": "VCC_5V", "B": "SIG"}},
    ]
    comps += [{"ref": f"C{k}", "mpn": "CL05B104KO5NNNC", "package": "0402",
               "type": "capacitor", "pins": {"+": "VCC_5V", "-": "GND"}}
              for k in range(1, n_caps + 1)]
    return {"name": "t", "board": {"width": 63.5, "height": 45.72}, "ground_net": "GND",
            "power_nets": ["VCC_5V", "GND"], "components": comps}


def test_two_caps_serve_two_different_supply_pins():
    """VCC (pin 7) and AVCC (pin 20) of a DIP-28 are ~16 mm apart: one cap
    cannot serve both, two caps must not crowd the same one."""
    b = _placed(_two_caps(2))
    nearest = {}
    for cap in ("C1", "C2"):
        d = _served(b, cap)
        pin, mm = min(d.items(), key=lambda kv: kv[1])
        assert mm <= NEAR_MM, (cap, d)
        nearest[cap] = pin
    assert nearest["C1"] != nearest["C2"], nearest


def test_a_capacitor_between_two_signals_is_not_a_decoupling_cap():
    """A filter cap (IN/OUT) has no supply pin to sit at; it is placed as
    before, by wirelength, and the board still compiles."""
    nl = PcbNetlistGenerator().generate(ir_examples.IR_003)
    result = compile_board(nl)
    assert result.stats["unrouted"] == 0


def test_the_decoupled_boards_still_route_clean():
    nl = _two_caps(2)
    result = compile_board(nl)
    assert result.stats["unrouted"] == 0, result.stats
    assert result.stats["drc_errors"] == 0, result.violations
