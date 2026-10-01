"""
Passive parts as data — the one owner of every passive part's figures.

Until Stage 6 these figures were constants in five places: the 0402
resistor's 1% / 62.5 mW / 50 V in `generators/common.py`, the 1206
terminator's 250 mW in `rs485_node.py`, the capacitor catalogue in
`rc_lowpass.py`, the bypass capacitor's 16 V in `arduino_parts.py`, and the
tolerance codes in `proof/prover.py`. A substitute part has to be judged on
*its* figures, and defeater D7 needs each figure to have one address a
provenance record can point at (`data/figures.py`), so they live here now.
`brain/decisions.md` [2026-09-24] D1, D2, D7, and Stage 6.

Values only. What a figure is — guaranteed limit, typical, derived — and
where it comes from is `data/figures.py`'s. Prices are the BOM's
(`data/component_db.json`), never read by anything that validates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class ResistorSeries:
    """A thick-film resistor family: every value in it shares these figures."""

    code: str             # the part-number prefix, e.g. "RC0402FR"
    manufacturer: str
    package: str
    tolerance: float      # relative
    power_w: float        # rated power at 70 °C ambient
    voltage_max: float    # maximum working voltage


@dataclass(frozen=True)
class Capacitor:
    part_number: str
    manufacturer: str
    package: str
    farads: float
    label: str            # the value as a person writes it, e.g. "100nF"
    dielectric: str
    tolerance: float      # relative
    voltage_max: float    # rated voltage


#: Yageo RC_L series. Tolerance letter F = ±1%, J = ±5%; the size sets power
#: and working voltage.
RESISTOR_SERIES: Dict[str, ResistorSeries] = {s.code: s for s in (
    ResistorSeries("RC0402FR", "Yageo", "0402", 0.01, 0.0625, 50.0),
    ResistorSeries("RC0402JR", "Yageo", "0402", 0.05, 0.0625, 50.0),
    ResistorSeries("RC0603FR", "Yageo", "0603", 0.01, 0.1, 75.0),
    ResistorSeries("RC0805FR", "Yageo", "0805", 0.01, 0.125, 150.0),
    ResistorSeries("RC1206FR", "Yageo", "1206", 0.01, 0.25, 200.0),
)}

#: The series every generator places unless a part is pinned.
DEFAULT_RESISTOR_SERIES = "RC0402FR"

#: Samsung CL series ceramics the generators use. The part number encodes
#: size (CL05 = 0402, CL10 = 0603), dielectric (A = X5R, B = X7R, C = C0G),
#: tolerance (J 5%, K 10%, M 20%) and rated voltage (Q 6.3 V, P 10 V,
#: O 16 V, A 25 V, B 50 V); each entry states its own figures.
CAPACITORS: Dict[str, Capacitor] = {c.part_number: c for c in (
    Capacitor("CL05B104KO5NNNC", "Samsung", "0402", 100e-9, "100nF", "X7R", 0.10, 16.0),
    Capacitor("CL05B103KB5NNNC", "Samsung", "0402", 10e-9, "10nF", "X7R", 0.10, 50.0),
    Capacitor("CL05A105KQ5NNNC", "Samsung", "0402", 1e-6, "1uF", "X5R", 0.10, 6.3),
    Capacitor("CL05B102KB5NNNC", "Samsung", "0402", 1e-9, "1nF", "X7R", 0.10, 50.0),
    Capacitor("CL05B223KO5NNNC", "Samsung", "0402", 22e-9, "22nF", "X7R", 0.10, 16.0),
    Capacitor("CL05A224KQ5NNNC", "Samsung", "0402", 220e-9, "220nF", "X5R", 0.10, 6.3),
    Capacitor("CL05B472KB5NNNC", "Samsung", "0402", 4.7e-9, "4.7nF", "X7R", 0.10, 50.0),
    Capacitor("CL05B473KO5NNNC", "Samsung", "0402", 47e-9, "47nF", "X7R", 0.10, 16.0),
)}

_RESISTOR_PART = re.compile(r"^(RC\d{4}[FJ]R)-07([0-9RKM]+)L$")


def resistor_series(part_number: Optional[str]) -> Optional[ResistorSeries]:
    """The series a resistor part number belongs to, or None if it is not tabulated."""
    m = _RESISTOR_PART.match(part_number or "")
    return RESISTOR_SERIES.get(m.group(1)) if m else None


def capacitor(part_number: Optional[str]) -> Optional[Capacitor]:
    return CAPACITORS.get(part_number or "")


def yageo_code(ohms: float) -> str:
    """
    Yageo's value encoding: the unit letter stands in for the decimal point.
    1590 → 1K59, 10000 → 10K, 100 → 100R.
    """
    if ohms >= 1e6:
        scaled, unit = ohms / 1e6, "M"
    elif ohms >= 1e3:
        scaled, unit = ohms / 1e3, "K"
    else:
        scaled, unit = ohms, "R"
    text = f"{scaled:.10g}"
    if "." in text:
        whole, frac = text.split(".")
        return f"{whole}{unit}{frac}"
    return f"{text}{unit}"


def resistor_part(ohms: float, series: str = DEFAULT_RESISTOR_SERIES) -> str:
    return f"{series}-07{yageo_code(ohms)}L"


def resistor_value(part_number: str) -> Optional[float]:
    """Ohms from a Yageo part number (`RC1206FR-07120RL` → 120.0); None if unreadable."""
    m = _RESISTOR_PART.match(part_number or "")
    if not m:
        return None
    code = m.group(2)
    for unit, scale in (("R", 1.0), ("K", 1e3), ("M", 1e6)):
        if unit in code:
            whole, _, frac = code.partition(unit)
            return float(f"{whole or 0}.{frac or 0}") * scale
    return None


def passive_figures(part_number: Optional[str]) -> Optional[Tuple[str, float, Optional[float], float]]:
    """(figure owner id, tolerance, power in W or None, voltage max) for a tabulated passive."""
    series = resistor_series(part_number)
    if series is not None:
        return series.code, series.tolerance, series.power_w, series.voltage_max
    cap = capacitor(part_number)
    if cap is not None:
        return cap.part_number, cap.tolerance, None, cap.voltage_max
    return None
