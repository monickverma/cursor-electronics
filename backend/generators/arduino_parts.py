"""
The Arduino Uno parts three Stage 3 generators share: the MCU, its decoupling
capacitor, and the rail-current model.

One place for each, for the same reason `generators/common.py` exists: the LED,
DHT22 and RS-485 generators all place an ATmega328P-PU and a 100 nF bypass
capacitor, and three hand-written copies of those components would drift.

The MCU's electrical model is amendment X6's `mcu_as_100R`: a 100 Ω load from
VCC to GND, never a voltage source. Every rail-current number derived from it
carries defeater D2, and `validation/claims.py` adds that from the netlist
itself rather than trusting a generator to remember.
"""

from __future__ import annotations

from typing import Sequence

from core.ir_schema import Component, ComponentType, Connection
from data.component_constraints import get_constraints
from generators.netlist.models import MCU_SUPPLY_OHMS

MCU_PART = "ATmega328P-PU"
DECOUPLING_PART = "CL05B104KO5NNNC"

#: The MCU's supply window as tabulated, and the one its GPIO model is
#: characterised at. Generators that model a pin refuse other rails.
MCU_VMIN = get_constraints(MCU_PART)["supply_voltage_min"]
MCU_VMAX = get_constraints(MCU_PART)["supply_voltage_max"]

#: Arduino Uno digital pins a generator may assign. D0/D1 are the USB serial
#: port; using them for a peripheral breaks uploads and the debug console.
UNO_DIGITAL_PINS = tuple(f"D{n}" for n in range(2, 14))

#: A USB-powered Uno's rail budget when a requirement names none: the 500 mA a
#: USB 2.0 port supplies. `constraints.supply_current_ma` overrides it.
DEFAULT_RAIL_BUDGET_MA = 500.0


def mcu(justification: str) -> Component:
    return Component(
        id="U1", type=ComponentType.MICROCONTROLLER, part_number=MCU_PART,
        manufacturer="Microchip", package="DIP-28",
        supply_voltage_min=MCU_VMIN, supply_voltage_max=MCU_VMAX, current_draw_ma=50,
        operating_temp_min=-40, operating_temp_max=85, confidence=0.97,
        justification=justification, lcsc_pn="C14877",
    )


def decoupling(target: str) -> Component:
    return Component(
        id="C1", type=ComponentType.CAPACITOR, part_number=DECOUPLING_PART,
        manufacturer="Samsung", package="0402", value="100nF", supply_voltage_max=16,
        confidence=0.99, lcsc_pn="C1525",
        justification=(
            f"100nF X7R bypass on {target}'s supply pin, placed close to it. It supplies the "
            f"fast edges the rail's trace inductance cannot; without it switching noise "
            f"couples into every line on the board. Rated 16 V against the 5 V rail."
        ),
    )


def power_connections(vcc: str = "VCC_5V", gnd: str = "GND") -> Sequence[Connection]:
    """U1 and C1 on the rail — the part every one of these designs shares."""
    return (
        Connection(component_id="U1", pin="VCC", node_id=vcc, direction="input"),
        Connection(component_id="U1", pin="GND", node_id=gnd, direction="input"),
        Connection(component_id="C1", pin="+", node_id=vcc),
        Connection(component_id="C1", pin="-", node_id=gnd),
    )


def mcu_rail_ma(supply_v: float) -> float:
    """The MCU's share of the rail under `mcu_as_100R`."""
    return supply_v / MCU_SUPPLY_OHMS * 1000.0
