"""
Simulation results shaped for the waveform viewer. Stage 3.

PHASE_2_PLAN_v2.md Stage 3: *"Waveform viewer renders AC / transient / DC."*
Phase 1 stored only a count of AC points, so there was nothing to draw. This
turns a parsed ngspice run into one JSON-safe object the frontend can plot
without knowing anything about SPICE output formats:

    {"dc":   {"voltages": {node: V}, "currents": {source: A}},
     "ac":   {"x": [Hz, ...],  "series": {node: [|V|, ...]}},
     "tran": {"x": [s, ...],   "series": {node: [V, ...]}}}

A sweep is **downsampled by stride** to at most `max_points`, always keeping
the last sample: a result is stored in the Celery backend and returned on
every poll, and an unbounded transient could be tens of thousands of rows.
Nothing is interpolated — every plotted point is a real ngspice sample.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

MAX_POINTS = 400


def _stride(points: Sequence[Any], max_points: int) -> List[Any]:
    if len(points) <= max_points:
        return list(points)
    step = math.ceil(len(points) / max_points)
    kept = list(points[::step])
    if kept[-1] is not points[-1]:
        kept.append(points[-1])
    return kept


def _sweep(points: Sequence[Tuple[float, Dict[str, float]]], max_points: int) -> Dict[str, Any]:
    if not points:
        return {"x": [], "series": {}}
    kept = _stride(points, max_points)
    nodes = sorted({node for _, values in kept for node in values})
    return {
        "x": [x for x, _ in kept],
        # A node missing at a sample is None, not 0 — 0 V is a real reading.
        "series": {node: [values.get(node) for _, values in kept] for node in nodes},
    }


def _finite(mapping: Dict[str, float]) -> Dict[str, float]:
    return {k: v for k, v in mapping.items() if isinstance(v, (int, float)) and math.isfinite(v)}


def waveforms_from(parsed: Any, max_points: int = MAX_POINTS) -> Dict[str, Any]:
    """The viewer's input, from a `SimulationData`."""
    return {
        "dc": {
            "voltages": _finite(getattr(parsed, "dc_voltages", {}) or {}),
            "currents": _finite(getattr(parsed, "branch_currents", {}) or {}),
        },
        "ac": _sweep(getattr(parsed, "ac_points", []) or [], max_points),
        "tran": _sweep(getattr(parsed, "tran_points", []) or [], max_points),
    }
