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
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

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

#: Yageo RC0402FR — 1% thick film, 62.5 mW, 50 V. The resistor every generator
#: places, so its limits are stated once.
RESISTOR_TOLERANCE = 0.01
RESISTOR_POWER_W = 0.0625
RESISTOR_VMAX = 50.0


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


def resistor_part(ohms: float) -> str:
    return f"RC0402FR-07{yageo_code(ohms)}L"


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


def pinned_number(raw: object, parse: Callable[[str], Optional[float]]) -> Optional[float]:
    """A pin's value as a number, via the netlist's own parser. None if unreadable."""
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
