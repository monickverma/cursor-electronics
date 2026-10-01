"""
What every generator shares: the preferred-value series, part-number encoding,
the strict requirement reader, and pinned parts.

Extracted from `rc_lowpass.py` when Stage 3 added four more generators. Each of
these is a fact with exactly one owner — a second copy of the E96 table in a
second generator is the stale-copy failure `AGENTS.md` says every drift in this
project has been. `rc_lowpass` re-exports what its tests already import.

Nothing here decides a design. It reads requirements, snaps values and names
parts; every choice stays in the generator that makes it.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, Mapping, NamedTuple, Optional, Sequence, Tuple

from data.parts import DEFAULT_RESISTOR_SERIES, RESISTOR_SERIES, resistor_series, resistor_value
from data.parts import capacitor as catalogue_capacitor
from data.parts import resistor_part as _catalogue_part
from data.parts import yageo_code as _catalogue_code
from generators.protocol import IntentLike

# E96 — the 1% series. E24 would be the wrong table for an F-code part.
E96 = (
    100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130,
    133, 137, 140, 143, 147, 150, 154, 158, 162, 165, 169, 174,
    178, 182, 187, 191, 196, 200, 205, 210, 215, 221, 226, 232,
    237, 243, 249, 255, 261, 267, 274, 280, 287, 294, 301, 309,
    316, 324, 332, 340, 348, 357, 365, 374, 383, 392, 402, 412,
    422, 432, 442, 453, 464, 475, 487, 499, 511, 523, 536, 549,
    562, 576, 590, 604, 619, 634, 649, 665, 681, 698, 715, 732,
    750, 768, 787, 806, 825, 845, 866, 887, 909, 931, 953, 976,
)

#: E24. Yageo's 1% (F) series come in E96 and E24 values; the 5% (J) series in E24 only.
E24 = (100, 110, 120, 130, 150, 160, 180, 200, 220, 240, 270, 300,
       330, 360, 390, 430, 470, 510, 560, 620, 680, 750, 820, 910)


def _mantissa(ohms: float) -> Optional[int]:
    if ohms <= 0:
        return None
    m = ohms
    while m >= 1000:
        m /= 10
    while m < 100:
        m *= 10
    rounded = round(m)
    return rounded if abs(m - rounded) < 1e-6 else None


def series_makes(code: str, ohms: float) -> bool:
    """Whether resistor series `code` is made in this value — E24 for a 5% series, E96 or E24 for 1%."""
    mantissa = _mantissa(ohms)
    if mantissa is None:
        return False
    return mantissa in E24 if RESISTOR_SERIES[code].tolerance > 0.01 else (mantissa in E96 or mantissa in E24)

#: Yageo RC0402FR — 1% thick film, 62.5 mW, 50 V. The resistor every generator
#: places; its figures are owned by `data/parts.py` (Stage 6) and read here.
_DEFAULT = RESISTOR_SERIES[DEFAULT_RESISTOR_SERIES]
RESISTOR_TOLERANCE = _DEFAULT.tolerance
RESISTOR_POWER_W = _DEFAULT.power_w
RESISTOR_VMAX = _DEFAULT.voltage_max


def snap_to_e96(ohms: float) -> float:
    """
    Nearest E96 value. Chooses in log space, because the series is
    logarithmic — picking by absolute distance biases toward the larger
    neighbour everywhere except the bottom of each decade.
    """
    if ohms <= 0:
        raise ValueError("resistance must be positive")
    decade = math.floor(math.log10(ohms))
    best: Optional[float] = None
    best_err = float("inf")
    for exponent in (decade - 1, decade, decade + 1):
        for mantissa in E96:
            candidate = mantissa * (10.0 ** (exponent - 2))
            err = abs(math.log10(candidate) - math.log10(ohms))
            if err < best_err:
                best_err, best = err, candidate
    return float(best)


def e96_values(lo: float, hi: float) -> Sequence[float]:
    """Every E96 value in [lo, hi], ascending. Deterministic candidate lists."""
    out = []
    exponent = math.floor(math.log10(lo)) - 1
    while True:
        for mantissa in E96:
            value = round(mantissa * (10.0 ** (exponent - 2)), 10)
            if value > hi:
                return tuple(out)
            if value >= lo:
                out.append(value)
        exponent += 1


def yageo_code(ohms: float) -> str:
    """Yageo's value encoding (1590 → 1K59); owned by `data/parts.py`."""
    return _catalogue_code(ohms)


def resistor_part(ohms: float) -> str:
    return _catalogue_part(ohms)


def value_string(ohms: float) -> str:
    """Plain ohms — unambiguous for `_parse_ohms` in the SPICE generator."""
    return f"{ohms:.10g}"


def requirements(intent: IntentLike) -> Mapping[str, object]:
    return intent.requirements or {}


class Unreadable(ValueError):
    """A requirement that was written but cannot be used. Carries the named reason."""


def read_number(
    intent: IntentLike,
    section: str,
    key: str,
    default: Optional[float],
    *,
    allow_zero: bool,
    what: str,
) -> Optional[float]:
    """
    A requirement read as a number. Absent (or null) gives `default`; present,
    it must be a real, finite number in range, or `Unreadable` names it.

    **Never a silent default for a value that was written.** Until the Stage 2
    verification these readers returned the default for anything that was not
    an int or float and accepted `True` as 1: `supply_v: "12"` built a 5 V
    design, `tolerance_pct: "1"` quietly loosened to 5%, `supply_v: true` built
    a 1 V one, and `tolerance_pct: NaN` accepted every design, because every
    comparison with NaN is false. Each of those hands back a design for a
    requirement nobody wrote. Patches made them easy to reach — a client or the
    patcher can send any JSON value — so envelope() now refuses them by name.
    """
    block = requirements(intent).get(section) or {}
    value = block.get(key) if isinstance(block, Mapping) else None
    if value is None:
        return default
    path = f"{section}.{key}"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Unreadable(
            f"{path}={value!r} is not a number — {what} is written as a bare number"
        )
    number = float(value)
    if not math.isfinite(number):
        raise Unreadable(f"{path}={value!r} is not a finite number — {what} must be one")
    if number < 0 or (number == 0 and not allow_zero):
        bound = "zero or more" if allow_zero else "greater than zero"
        raise Unreadable(f"{path}={number:g} is not usable — {what} must be {bound}")
    return number


def read_pins(intent: IntentLike, pinnable: Sequence[str]) -> Dict[str, Any]:
    """
    `constraints.pinned`, checked for shape and for naming only real parts.

    Returns the raw pinned values; the generator parses each with the parser
    the netlist will use, because only it knows which kind of part an id is.
    """
    constraints = requirements(intent).get("constraints") or {}
    pinned = constraints.get("pinned") if isinstance(constraints, Mapping) else None
    if pinned is None:
        return {}
    if not isinstance(pinned, Mapping):
        raise Unreadable(
            f"constraints.pinned must map part ids to values, e.g. "
            f"{{'R1': '4.7k'}}; got {type(pinned).__name__}"
        )
    unknown = sorted(set(pinned) - set(pinnable))
    if unknown:
        raise Unreadable(
            f"constraints.pinned names {unknown}; this generator's pinnable parts "
            f"are {list(pinnable)}"
        )
    return dict(pinned)


class PartPin(NamedTuple):
    """A pinned *part* (Stage 6): its value and its own figures, from `data/parts.py`."""

    part_number: str
    kind: str                      # resistor | capacitor
    value: float                   # ohms or farads
    tolerance: float
    power_w: Optional[float]       # resistors only
    voltage_max: float
    package: str
    manufacturer: str


def pinned_part(raw: object, pid: str = "part") -> Optional[PartPin]:
    """
    A part pin `{"part": "<part number>"}` resolved against the parts
    catalogue; None for a value pin. A part the catalogue does not hold is
    refused by name — without its figures no claim could be checked against it.
    """
    if not isinstance(raw, Mapping):
        return None
    number = raw.get("part")
    if set(raw) != {"part"} or not isinstance(number, str) or not number.strip():
        raise Unreadable(
            f"constraints.pinned.{pid} must be a value or {{'part': '<part number>'}}; got {dict(raw)!r}"
        )
    number = number.strip()
    series = resistor_series(number)
    ohms = resistor_value(number)
    if series is not None and ohms:
        # Only a part that is made: the canonical spelling of a value the series comes in.
        if number != _catalogue_part(ohms, series.code) or not series_makes(series.code, ohms):
            raise Unreadable(
                f"constraints.pinned.{pid}: {number} is not a part {series.code} is made as — the series "
                f"comes in {'E24' if series.tolerance > 0.01 else 'E96 and E24'} values, written "
                f"{_catalogue_part(ohms, series.code)} for {ohms:g} ohm"
            )
        return PartPin(number, "resistor", ohms, series.tolerance, series.power_w, series.voltage_max,
                       series.package, series.manufacturer)
    cap = catalogue_capacitor(number)
    if cap is not None:
        return PartPin(number, "capacitor", cap.farads, cap.tolerance, None, cap.voltage_max,
                       cap.package, cap.manufacturer)
    raise Unreadable(
        f"constraints.pinned.{pid}: {number} is not in the parts catalogue (data/parts.py), so its "
        f"tolerance and ratings are unknown and nothing about it could be checked"
    )


def pinned_parts(intent: IntentLike, pinnable: Sequence[str], kinds: Mapping[str, str]) -> Dict[str, PartPin]:
    """The part pins among `constraints.pinned`, each checked to be the kind of part its slot holds."""
    out = {}
    for pid, raw in read_pins(intent, pinnable).items():
        part = pinned_part(raw, pid)
        if part is None:
            continue
        if part.kind != kinds[pid]:
            raise Unreadable(f"constraints.pinned.{pid}: {part.part_number} is a {part.kind}; {pid} is a {kinds[pid]}")
        out[pid] = part
    return out


class PartFigures:
    """
    The figures of each placed passive: a pinned part's own, else the default
    0402 series'. One object per design, so tolerance, rating and package can
    never come from two different parts for the same slot.
    """

    def __init__(self, parts: Optional[Mapping[str, PartPin]] = None) -> None:
        self.parts: Dict[str, PartPin] = dict(parts or {})

    def tolerance(self, pid: str, default: float = RESISTOR_TOLERANCE) -> float:
        return self.parts[pid].tolerance if pid in self.parts else default

    def power_w(self, pid: str, default: float = RESISTOR_POWER_W) -> float:
        part = self.parts.get(pid)
        return part.power_w if part is not None and part.power_w is not None else default

    def voltage_max(self, pid: str, default: float = RESISTOR_VMAX) -> float:
        return self.parts[pid].voltage_max if pid in self.parts else default

    def resistor(self, pid: str, ohms: float, series: str = DEFAULT_RESISTOR_SERIES) -> Tuple[str, str, str]:
        """(part number, package, manufacturer) of the resistor in slot `pid`."""
        if pid in self.parts:
            p = self.parts[pid]
            return p.part_number, p.package, p.manufacturer
        s = RESISTOR_SERIES[series]
        return _catalogue_part(ohms, series), s.package, s.manufacturer


def pinned_number(raw: object, parse: Callable[[str], Optional[float]], pid: str = "part") -> Optional[float]:
    """
    A pin's value as a number, via the netlist's own parser, or a part pin's
    value. None if unreadable. `pid` is the slot, named in a refusal.
    """
    if isinstance(raw, Mapping):
        part = pinned_part(raw, pid)
        return part.value if part is not None else None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        number = float(raw)
    elif isinstance(raw, str) and raw.strip():
        number = parse(raw)
    else:
        return None
    if number is None or not math.isfinite(number) or number <= 0:
        return None
    return number


def worst_corners(fn: Callable[..., float], boxes: Sequence[Sequence[float]]) -> tuple:
    """
    min and max of `fn` over every corner of a box.

    Exact when `fn` is monotone in each argument separately — the condition
    each caller states and tests. 2^n evaluations; every generator here has
    n ≤ 4.
    """
    values = []
    def walk(i: int, args: list) -> None:
        if i == len(boxes):
            values.append(fn(*args))
            return
        for bound in boxes[i]:
            walk(i + 1, args + [bound])
    walk(0, [])
    return min(values), max(values)
