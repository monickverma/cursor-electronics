"""
The MCU parts three Stage 3 generators share: the MCU, its decoupling
capacitor, and the rail-current model — for whichever board the requirement
targets (Stage 5: `constraints.mcu`, default the Arduino Uno).

One place for each, for the same reason `generators/common.py` exists: the LED,
DHT22 and RS-485 generators all place an ATmega328P-PU and a 100 nF bypass
capacitor, and three hand-written copies of those components would drift.

The MCU's electrical model is amendment X6's `mcu_as_100R`: a 100 Ω load from
VCC to GND, never a voltage source. Every rail-current number derived from it
carries defeater D2, and `validation/claims.py` adds that from the netlist
itself rather than trusting a generator to remember.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from core.ir_schema import Component, ComponentType, Connection
from data.component_constraints import get_constraints
from data.mcu_targets import DEFAULT_TARGET, TARGETS, Target, get_target
from generators.common import Unreadable, requirements
from generators.netlist.models import mcu_supply_ohms

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


#: What the component list says about each target's MCU.
_MCU_PARTS: Mapping[str, dict] = {
    "arduino_uno": {"manufacturer": "Microchip", "package": "DIP-28", "lcsc_pn": "C14877"},
    "esp32_devkitc": {"manufacturer": "Espressif", "package": "module", "lcsc_pn": None},
    "blackpill_f411ce": {"manufacturer": "STMicroelectronics", "package": "UFQFPN-48", "lcsc_pn": None},
}


def read_target(intent) -> Target:
    """The board the requirement targets: `constraints.mcu`, default the Uno."""
    constraints = requirements(intent).get("constraints") or {}
    raw = constraints.get("mcu", DEFAULT_TARGET) if isinstance(constraints, Mapping) else DEFAULT_TARGET
    target = get_target(raw)
    if target is None:
        raise Unreadable(f"constraints.mcu={raw!r} is not a board this system targets; "
                         f"choose one of {sorted(TARGETS)}")
    return target


#: Every board an MCU generator designs for. CI sweeps each generator's grid
#: on each (Stage 5), so the form can offer them as exercised.
BOARDS = tuple(TARGETS)


def grid_target(board: str | None) -> Target:
    """The board a declared grid is for; None is the default board."""
    target = get_target(board or DEFAULT_TARGET)
    if target is None:
        raise ValueError(f"no grid is declared for board {board!r}; the boards are {list(BOARDS)}")
    return target


def mcu(justification: str, target: Target = TARGETS[DEFAULT_TARGET]) -> Component:
    entry = get_constraints(target.mcu_part)
    meta = _MCU_PARTS[target.id]
    return Component(
        id="U1", type=ComponentType.MICROCONTROLLER, part_number=target.mcu_part,
        manufacturer=meta["manufacturer"], package=meta["package"],
        supply_voltage_min=entry["supply_voltage_min"], supply_voltage_max=entry["supply_voltage_max"],
        current_draw_ma=round(mcu_rail_ma(target.logic_v, target.mcu_part)),
        operating_temp_min=-40, operating_temp_max=85, confidence=0.97,
        justification=justification, lcsc_pn=meta["lcsc_pn"],
    )


def decoupling(label: str, rail_v: float = 5.0) -> Component:
    return Component(
        id="C1", type=ComponentType.CAPACITOR, part_number=DECOUPLING_PART,
        manufacturer="Samsung", package="0402", value="100nF", supply_voltage_max=16,
        confidence=0.99, lcsc_pn="C1525",
        justification=(
            f"100nF X7R bypass on {label}'s supply pin, placed close to it. It supplies the "
            f"fast edges the rail's trace inductance cannot; without it switching noise "
            f"couples into every line on the board. Rated 16 V against the {rail_v:g} V rail."
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


def mcu_rail_ma(supply_v: float, mcu_part: str = MCU_PART) -> float:
    """The MCU's share of the rail under its supply-load model (`mcu_as_100R` on the Uno)."""
    return supply_v / mcu_supply_ohms(mcu_part) * 1000.0
