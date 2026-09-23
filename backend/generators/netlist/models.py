"""
Device models shared by the SPICE netlist and by `predict()`.

Stage 3 needs `predict()` and ngspice to describe the same circuit, or the grid
gate compares two different things and its agreement means nothing. So every
electrical model a generator reasons with lives here, once, and both sides read
it: the netlist emits it, `predict()` solves it in closed form.

Every value here comes from `data/component_constraints.py` (datasheet-derived:
defeater D7) or is a stated modelling simplification (the ATmega328P ones are
defeater D2). The model names are what a claim's `scope.model` records.
"""

from __future__ import annotations

import math
import re
from typing import Optional, Tuple

from data.component_constraints import get_constraints

#: Thermal voltage at 27 °C (300.15 K), which is ngspice's default TEMP. Using
#: 25 °C here would put a 0.7% disagreement into every diode comparison before
#: any real error is measured.
K_BOLTZMANN = 1.380649e-23
Q_ELECTRON = 1.602176634e-19
SPICE_TEMP_K = 300.15
VT = K_BOLTZMANN * SPICE_TEMP_K / Q_ELECTRON

#: The MCU supply model (CLAUDE.md Rule 3, amendment X6): a 100 ohm resistor
#: between VCC and GND. Never a voltage source — that makes a singular matrix.
MCU_SUPPLY_OHMS = 100.0

#: Fallback when an MCU is not in the component table.
DEFAULT_PIN_OHMS = 25.0

MODEL_MCU_SUPPLY = "mcu_as_100R"
MODEL_MCU_PIN = "mcu_pin_thevenin"
MODEL_LED = "shockley_diode"


# ── LEDs ─────────────────────────────────────────────────────────────────────

def led_parameters(part_number: str, forward_voltage: str = "typ") -> Optional[Tuple[float, float]]:
    """
    (Is, n) for a tabulated LED, fitted so V_f at the test current equals the
    datasheet's `min` / `typ` / `max` forward voltage. None if not tabulated —
    the netlist then falls back to its generic diode, exactly as before Stage 3.
    """
    entry = get_constraints(part_number)
    if not entry or "forward_voltage_v" not in entry:
        return None
    n = float(entry.get("ideality", 2.0))
    vf = float(entry["forward_voltage_v"][forward_voltage])
    i_test = float(entry["test_current_ma"]) / 1000.0
    return i_test / math.expm1(vf / (n * VT)), n


def led_model_name(part_number: str) -> str:
    return "DLED_" + re.sub(r"[^A-Za-z0-9]", "_", part_number).upper()


def diode_voltage(current: float, i_s: float, n: float) -> float:
    """Shockley forward drop at `current`."""
    return n * VT * math.log1p(current / i_s)


def solve_series_diode(v_source: float, r_series: float, i_s: float, n: float) -> float:
    """
    Current in V → R → diode → ground: the root of
    f(I) = I·R + n·Vt·ln(1 + I/Is) − V.

    f is strictly increasing in I, so bisection on [0, V/R] converges to the
    unique root; 200 halvings is below float resolution. Deterministic and
    exact to the float — which is what lets the LED generator's corner
    evaluation still bound the band: I is monotone in V, R and Is.
    """
    if v_source <= 0:
        return 0.0
    lo, hi = 0.0, v_source / r_series
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if mid * r_series + diode_voltage(mid, i_s, n) < v_source:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ── ATmega328P ───────────────────────────────────────────────────────────────

def pin_resistance(mcu_part: Optional[str], which: str = "typ") -> float:
    """Output resistance of a GPIO driven high (`mcu_pin_thevenin`)."""
    entry = get_constraints(mcu_part or "") or {}
    table = entry.get("gpio_output_resistance_ohm")
    if not table:
        return DEFAULT_PIN_OHMS
    return float(table[which])


# ── Other active parts ───────────────────────────────────────────────────────

def load_ohms(current_draw_ma: Optional[float], supply_voltage_max: Optional[float]) -> float:
    """
    The resistive load a sensor, transceiver or relay is modelled as between
    VCC and GND: its rated current at its maximum supply. Phase 1's rule,
    moved here unchanged so `predict()` can read the same number.
    """
    if current_draw_ma and current_draw_ma > 0:
        supply_v = supply_voltage_max or 5.0
        return float(max(100, int(supply_v / (current_draw_ma / 1000))))
    return 10000.0
