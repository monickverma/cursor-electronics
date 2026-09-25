"""Deterministic numeric pre-screen for prompt -> IntentIR transcription (the "semantic residue" arm).

Two checks, both zero-model:

* `snapshot_grounded(value, prompt)` - the snapshot's own `grounded()` verbatim
  (backend/ai/intent_patcher.py:246-261). It compares a value in the FIELD's unit with
  quantities that `quantities()` has converted to SI base units, so it is unit-blind:
  "10 mA" reads as 0.01 and "15 m" reads as 0.015 (milli, no unit).
* `unit_grounded(path, value, prompt)` - a unit-aware wrapper written for this study. It
  scales the field value into the unit `quantities()` produces (mA -> A) and rewrites a bare
  "<number> m" to "<number> metres" for length fields, so "15 m" grounds cable_length_m = 15.
  It still reuses the snapshot's `quantities()` parser for everything else.

Neither can bind a value to a FIELD: a value that appears anywhere in the prompt passes, so
values swapped between two fields, or an invented value that happens to equal another number
in the prompt, pass both checks. That residue is what the Jev arm is asked about.
"""
import math
import re

from snapshot import grounded, quantities

UNITS = {
    "targets.cutoff_hz": "Hz", "constraints.supply_v": "V", "targets.tolerance_pct": "%",
    "constraints.source_impedance_ohm": "ohm", "targets.vout_v": "V",
    "constraints.divider_current_ma": "mA", "constraints.load_ohm": "ohm",
    "targets.led_current_ma": "mA", "constraints.cable_length_m": "m",
    "preferences.alert_threshold_c": "°C", "preferences.poll_interval_ms": "ms",
    "constraints.baud": "baud", "constraints.mcu": "", "preferences.gpio_pin": "",
    "preferences.data_pin": "", "preferences.colour": "", "preferences.package": "",
    "constraints.far_end_terminated": "", "preferences.modbus_slaves": "",
}

# Scale from the field's unit into the SI unit quantities() reports.
_SCALES = {"mA": (1e-3,), "ms": (1.0, 1e-3), "m": (1.0,)}


def is_numeric_leaf(value):
    """Numbers, and lists/dicts whose leaves are all numbers (modbus_slaves). Not bools/strings."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, dict):
        return bool(value) and all(is_numeric_leaf(v) for v in value.values())
    if isinstance(value, list):
        return bool(value) and all(is_numeric_leaf(v) for v in value)
    return False


def _numbers(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _numbers(v)
    elif isinstance(value, list):
        for v in value:
            yield from _numbers(v)
    else:
        yield value


def unit_grounded(path, value, prompt):
    unit = UNITS.get(path, "")
    text = prompt
    if unit == "m":
        text = re.sub(r"(\d)\s*m(?![A-Za-z])", r"\1 metres", text)
    found = quantities(text)
    scales = _SCALES.get(unit, (1.0,))
    for number in _numbers(value):
        if not any(math.isclose(q, number * s, rel_tol=1e-9, abs_tol=1e-15) for q in found for s in scales):
            return False
    return True


def snapshot_grounded(value, prompt):
    return grounded(value, prompt)
