"""
iec60664.py — clearance and creepage figures from IEC 60664-1, as data.

No spacing in the product is a hard-coded number. A required distance is looked
up from the working voltage, the insulation class (functional, basic or
reinforced), the pollution degree, the material group, the overvoltage category
and the altitude, and the lookup names the table it came from.

VERIFIED = False: the figures below were transcribed by the agent from its
knowledge of IEC 60664-1:2020 Tables F.1, F.2, F.4 and A.2, not from the
standard's text, which is not in the repo. Every result built on them says so.
Only a qualified review against the standard settles a safety spacing; until one
signs this table off, a pass is "meets the table as transcribed", never
"compliant". The owner decision on the mains rule (finding F-0004) is open.

Reinforced insulation: creepage twice the basic figure (IEC 60664-1, 5.3.2.1);
clearance dimensioned for the next higher step of the preferred impulse series
(5.1.6). Functional insulation uses the basic figures here, which is
conservative for it.
"""
from __future__ import annotations

import bisect

VERIFIED = False
SOURCE = ("IEC 60664-1:2020 Tables F.1 (impulse), F.2 (clearance, case A, inhomogeneous "
          "field), F.4 (creepage), A.2 (altitude); reinforced per 5.1.6 and 5.3.2.1. "
          "Transcribed by an agent, unverified against the standard's text")

# Table F.4 — creepage (mm) for basic insulation, by rms working voltage (row:
# the next row up is used, never interpolated down), pollution degree and
# material group. Printed-wiring columns are not used: they assume a coating
# or CTI the IR does not record.
_F4_VOLTS = [50, 63, 80, 100, 125, 160, 200, 250, 320, 400, 500, 630, 800, 1000]
_F4 = {
    (1, "I"):   [0.18, 0.2, 0.22, 0.25, 0.28, 0.32, 0.42, 0.56, 0.75, 1.0, 1.3, 1.8, 2.4, 3.2],
    (2, "I"):   [0.6, 0.63, 0.67, 0.71, 0.75, 0.8, 1.0, 1.25, 1.6, 2.0, 2.5, 3.2, 4.0, 5.0],
    (2, "II"):  [0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.4, 1.8, 2.2, 2.8, 3.6, 4.5, 5.6, 7.1],
    (2, "III"): [1.2, 1.25, 1.3, 1.4, 1.5, 1.6, 2.0, 2.5, 3.2, 4.0, 5.0, 6.3, 8.0, 10.0],
    (3, "I"):   [1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.5, 3.2, 4.0, 5.0, 6.3, 8.0, 10.0, 12.5],
    (3, "II"):  [1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.8, 3.6, 4.5, 5.6, 7.1, 9.0, 11.0, 14.0],
    (3, "III"): [1.9, 2.0, 2.1, 2.2, 2.4, 2.5, 3.2, 4.0, 5.0, 6.3, 8.0, 10.0, 12.5, 16.0],
}

# Table F.1 — rated impulse voltage (V) by line-to-neutral voltage and
# overvoltage category.
_F1_VOLTS = [50, 100, 150, 300, 600, 1000]
_F1 = {"I":   [330, 500, 800, 1500, 2500, 4000],
       "II":  [500, 800, 1500, 2500, 4000, 6000],
       "III": [800, 1500, 2500, 4000, 6000, 8000],
       "IV":  [1500, 2500, 4000, 6000, 8000, 12000]}

# Preferred impulse series and Table F.2 clearance (mm), case A, by pollution degree.
_IMPULSE = [330, 500, 800, 1500, 2500, 4000, 6000, 8000, 12000]
_F2 = {1: [0.01, 0.04, 0.1, 0.5, 1.5, 3.0, 5.5, 8.0, 14.0],
       2: [0.2, 0.2, 0.2, 0.5, 1.5, 3.0, 5.5, 8.0, 14.0],
       3: [0.8, 0.8, 0.8, 0.8, 1.5, 3.0, 5.5, 8.0, 14.0]}

# Table A.2 — clearance correction factor by altitude (m).
_A2 = [(2000, 1.00), (3000, 1.14), (4000, 1.29), (5000, 1.48)]

INSULATION = ("functional", "basic", "reinforced")


def _row(volts: list[float], v: float) -> int:
    i = bisect.bisect_left(volts, abs(v))
    if i >= len(volts):
        raise ValueError(f"{v} V is above the transcribed table ({volts[-1]} V)")
    return i


def creepage_mm(v_rms: float, pollution: int = 2, group: str = "III",
                insulation: str = "basic") -> float:
    if insulation not in INSULATION:
        raise ValueError(insulation)
    col = _F4.get((pollution, group if pollution > 1 else "I"))
    if col is None:
        raise ValueError(f"no column for pollution degree {pollution}, group {group}")
    base = col[_row(_F4_VOLTS, v_rms)]
    return 2 * base if insulation == "reinforced" else base


def impulse_v(v_line_neutral: float, ovc: str = "II") -> int:
    return _F1[ovc][_row(_F1_VOLTS, v_line_neutral)]


def clearance_mm(v_line_neutral: float, ovc: str = "II", pollution: int = 2,
                 insulation: str = "basic", altitude_m: float = 2000) -> float:
    if insulation not in INSULATION:
        raise ValueError(insulation)
    k = _IMPULSE.index(impulse_v(v_line_neutral, ovc))
    if insulation == "reinforced":
        k += 1
    factor = next((f for alt, f in _A2 if altitude_m <= alt), None)
    if factor is None:
        raise ValueError(f"altitude {altitude_m} m is above the transcribed Table A.2")
    return round(_F2[pollution][k] * factor, 3)
