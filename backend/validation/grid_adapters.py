"""
Grid adapters for the whole generator library. Stage 3.

`validation/envelope_grid.py` is the harness; an adapter is the circuit-class-
specific glue it takes: how a grid point becomes an intent, how to measure the
quantities `predict()` names in an ngspice run of the generated design, and
which part to perturb for the M1 fault-injection arms. Stage 0 kept the RC
adapter in its test; Stage 3 moves every adapter here so `regen_state.py`, the
claims layer and later stages can run the library, not one generator.

**Probes are test benches, never the design.** Some quantities exist only
under a stimulus: the DHT22 pull-up's sink current appears when something
holds DATA low, and an RS-485 bus is biased against the terminator at the far
end, which is not on this board. `with_probes()` appends those elements to the
design's *own* netlist, the way a scope probe attaches to a board. The product
netlist and the BOM never contain them. `brain/decisions.md` [2026-09-21]
X6 + X8, Stage 3 item 4.

`M1_COVERED` is the set of generators with an adapter here — the ones whose
`predict()` is checked against a seeded fault in CI. `validation/claims.py`
reads it to decide whether a design's claims carry defeater D9.
"""

from __future__ import annotations

import asyncio
import math
from typing import Callable, Dict, Mapping, NamedTuple, Optional, Sequence

from core.ir_schema import CircuitIR
from generators.netlist.spice import SpiceNetlistGenerator
from validation.envelope_grid import GridAdapter


class _Requirements:
    """A grid point dressed as an intent: only `requirements`, per IntentLike."""

    __slots__ = ("requirements",)

    def __init__(self, requirements: Mapping[str, object]) -> None:
        self.requirements = requirements


def intent_at(function: str, point: Mapping[str, float], sections: Mapping[str, str],
              base: Optional[Mapping[str, Mapping[str, object]]] = None) -> _Requirements:
    """Place each grid axis in the section its generator declares."""
    req: Dict[str, object] = {"function": function, "targets": {}, "constraints": {}, "preferences": {}}
    for section, values in (base or {}).items():
        req[section] = dict(values)
    for axis, value in point.items():
        req[sections.get(axis, "targets")][axis] = value
    return _Requirements(req)


def with_probes(netlist: str, probes: Sequence[str]) -> str:
    """The design's netlist with test-bench elements added before `.end`."""
    lines = netlist.rstrip().splitlines()
    if not lines or lines[-1].strip().lower() != ".end":
        raise ValueError("netlist does not end in .end — refusing to guess where probes go")
    return "\n".join(lines[:-1] + ["* test bench (CI probe, not part of the design)"]
                     + list(probes) + [lines[-1]])


def simulate(netlist: str):
    from simulation.parser import SpiceResultParser
    from simulation.runner import NgspiceRunner

    result = asyncio.run(NgspiceRunner().run(netlist))
    data = SpiceResultParser().parse(result["stdout"], result["stderr"])
    if not (data.dc_voltages or data.ac_points or data.branch_currents):
        raise RuntimeError(
            "ngspice produced no parseable output — an infrastructure failure, not a "
            f"prediction error. stderr: {(result.get('stderr') or '')[:300]}\nnetlist:\n{netlist}"
        )
    return data


def netlist_of(ir: CircuitIR) -> str:
    return SpiceNetlistGenerator().generate(ir)


# ── Measurements, one per generator ──────────────────────────────────────────

def _log_crossing(points, node: str, target: float) -> Optional[float]:
    series = [(f, v[node]) for f, v in points if node in v]
    for (f_lo, m_lo), (f_hi, m_hi) in zip(series, series[1:]):
        if m_lo >= target >= m_hi and m_lo != m_hi:
            frac = (m_lo - target) / (m_lo - m_hi)
            return 10 ** (math.log10(f_lo) + frac * (math.log10(f_hi) - math.log10(f_lo)))
    return None


def measure_rc(ir: CircuitIR) -> Dict[str, float]:
    supply = ir.constraints["supply_voltage"]
    crossing = _log_crossing(simulate(netlist_of(ir)).ac_points, "out", supply / math.sqrt(2.0))
    return {"cutoff_hz": crossing if crossing is not None else math.nan}


def measure_divider(ir: CircuitIR) -> Dict[str, float]:
    data = simulate(netlist_of(ir))
    return {
        "vout_v": data.dc_voltages.get("vout", math.nan),
        "supply_current_ma": -data.branch_currents.get("v_vin", math.nan) * 1000.0,
    }


def measure_led(ir: CircuitIR) -> Dict[str, float]:
    data = simulate(netlist_of(ir))
    pin = -data.branch_currents.get("v_pin_led_ctrl", math.nan)
    rail = -data.branch_currents.get("v_vcc_5v", math.nan)
    # The pin's Thevenin source stands in for current that physically comes
    # from VCC, so the rail is the two sources together.
    return {"led_current_ma": pin * 1000.0, "supply_current_ma": (rail + pin) * 1000.0}


def measure_dht22(ir: CircuitIR) -> Dict[str, float]:
    # Hold DATA low, as the MCU's start pulse or the sensor's reply does.
    data = simulate(with_probes(netlist_of(ir), ["V_PROBE dht22_data 0 DC 0"]))
    sink = data.branch_currents.get("v_probe", math.nan)
    rail = -data.branch_currents.get("v_vcc_5v", math.nan)
    return {
        "pullup_sink_current_ma": sink * 1000.0,
        # The idle rail excludes the probe's pull-up current.
        "supply_current_ma": (rail - sink) * 1000.0,
    }


def measure_rs485(ir: CircuitIR) -> Dict[str, float]:
    probes = ["R_FAR rs485_a rs485_b 120"] if ir.constraints.get("far_end_terminated", True) else []
    data = (simulate(with_probes(netlist_of(ir), probes)) if probes else simulate(netlist_of(ir)))
    v = data.dc_voltages
    return {
        "v_ab_idle_mv": (v.get("rs485_a", math.nan) - v.get("rs485_b", math.nan)) * 1000.0,
        "supply_current_ma": -data.branch_currents.get("v_vcc_5v", math.nan) * 1000.0,
    }


# ── The library ──────────────────────────────────────────────────────────────

class AdapterSpec(NamedTuple):
    build: Callable[[], GridAdapter]
    #: The passive the M1 arms perturb. Chosen as the part the measured
    #: quantity is most sensitive to, so a 5% fault is a 5%-class signal.
    mutate: str


def _adapter(generator_cls, function: str, measure, base=None) -> Callable[[], GridAdapter]:
    def build() -> GridAdapter:
        generator = generator_cls()
        sections = generator.grid().sections
        return GridAdapter(
            generator=generator,
            intent_for=lambda point: intent_at(function, point, sections, base),
            measure=measure,
        )
    return build


def _library() -> Dict[str, AdapterSpec]:
    from generators.dht22_node import DHT22NodeGenerator
    from generators.led_indicator import LedIndicatorGenerator
    from generators.rc_lowpass import RCLowPassGenerator
    from generators.rs485_node import RS485NodeGenerator
    from generators.voltage_divider import VoltageDividerGenerator

    return {
        "rc_lowpass": AdapterSpec(_adapter(
            RCLowPassGenerator, "low_pass_filter", measure_rc,
            base={"targets": {"tolerance_pct": 5.0},
                  "constraints": {"supply_v": 5.0, "source_impedance_ohm": 50.0}},
        ), "C1"),
        "voltage_divider": AdapterSpec(_adapter(
            VoltageDividerGenerator, "voltage_divider", measure_divider), "R2"),
        "led_indicator": AdapterSpec(_adapter(
            LedIndicatorGenerator, "led_indicator", measure_led), "R1"),
        "dht22_node": AdapterSpec(_adapter(
            DHT22NodeGenerator, "temperature_humidity_sensor", measure_dht22), "R1"),
        "rs485_node": AdapterSpec(_adapter(
            RS485NodeGenerator, "modbus_rtu_master", measure_rs485), "R1"),
    }


ADAPTERS: Dict[str, AdapterSpec] = _library()

#: Generators under the M1 matrix. Claims from any other generator carry D9.
M1_COVERED = frozenset(ADAPTERS)
