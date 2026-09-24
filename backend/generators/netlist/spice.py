"""SPICE netlist generator — CircuitIR → ngspice-compatible netlist string."""

import re
from typing import Dict, List, Optional, Tuple

from core.ir_schema import CircuitIR, ComponentType, SignalType
from generators.netlist.models import (
    mcu_supply_ohms,
    led_model_name,
    led_parameters,
    load_ohms,
    pin_resistance,
)


_VCC_PIN_NAMES = frozenset({"VCC", "VDD", "AVCC", "3V3", "5V", "PWR", "V+"})
_GND_PIN_NAMES = frozenset({"GND", "VSS", "AGND", "GND2", "V-"})


def _parse_ohms(value: str) -> Optional[float]:
    """Parse a component value string into ohms. Returns None if not parseable."""
    v = value.strip().upper()
    m = re.match(r'^(\d+(?:\.\d+)?)R?$', v)
    if m and not any(v.endswith(s) for s in ("F", "H", "HZ")):
        return float(m.group(1))
    m = re.match(r'^(\d+(?:\.\d+)?)K(\d*)$', v)
    if m:
        integer = float(m.group(1))
        frac_str = m.group(2)
        frac = float(frac_str) / (10 ** len(frac_str)) if frac_str else 0.0
        return (integer + frac) * 1000.0
    m = re.match(r'^(\d+(?:\.\d+)?)MEG$', v)
    if m:
        return float(m.group(1)) * 1e6
    return None


def _parse_farads(value: str) -> Optional[float]:
    """Parse a component value string into farads. Returns None if not parseable."""
    v = value.strip().upper().rstrip("F")
    prefixes = {"P": 1e-12, "N": 1e-9, "U": 1e-6, "M": 1e-3}
    m = re.match(r'^(\d+(?:\.\d+)?)([PNUM]?)$', v)
    if m:
        return float(m.group(1)) * prefixes.get(m.group(2), 1.0)
    return None


class SpiceNetlistGenerator:
    """Translates a CircuitIR into an ngspice-compatible SPICE netlist string."""

    def generate(self, ir: CircuitIR) -> str:
        gnd_id = next((n.id for n in ir.nodes if n.type == SignalType.GROUND), None)

        def spice_node(node_id: str) -> str:
            if node_id == gnd_id:
                return "0"
            return re.sub(r'[^a-zA-Z0-9_]', '_', node_id.lower())

        pin_map: Dict[str, Dict[str, str]] = {}
        for conn in ir.connections:
            pin_map.setdefault(conn.component_id, {})[conn.pin] = conn.node_id

        analysis = (
            ir.simulation_spec.analyses[0]
            if (ir.simulation_spec and ir.simulation_spec.analyses)
            else None
        )
        is_ac = analysis is not None and analysis.type == "ac_sweep"

        lines: List[str] = [f"* Circuit OS — {ir.intent}", ""]

        # Track SPICE node connection count to detect floating nodes
        node_conns: Dict[str, int] = {}

        def touch(sn: str) -> None:
            if sn != "0":
                node_conns[sn] = node_conns.get(sn, 0) + 1

        # Voltage sources: POWER nodes always; ANALOG nodes only for AC sweep
        for node in ir.nodes:
            if node.type == SignalType.POWER and node.voltage_nominal is not None:
                sn = spice_node(node.id)
                lines.append(f"V_{node.id.upper()} {sn} 0 DC {node.voltage_nominal}")
                touch(sn)
            elif node.type == SignalType.ANALOG and is_ac and node.voltage_nominal is not None:
                sn = spice_node(node.id)
                lines.append(f"V_{node.id.upper()} {sn} 0 AC {node.voltage_nominal}")
                touch(sn)

        # GPIO pins driven high (`mcu_pin_thevenin`, Stage 3). A node an MCU
        # drives through an *output* connection and that declares a
        # `voltage_nominal` is the pin's Thevenin source: V behind the pin's
        # datasheet output resistance. Opt-in: a node without a declared
        # voltage emits nothing here, exactly as before — IR_002 and every
        # stored netlist are unchanged.
        mcus = {c.id: c for c in ir.components if c.type == ComponentType.MICROCONTROLLER}
        for node in ir.nodes:
            if node.voltage_nominal is None or node.type in (SignalType.POWER, SignalType.GROUND):
                continue
            driver = next(
                (conn for conn in ir.connections
                 if conn.node_id == node.id and conn.component_id in mcus
                 and conn.direction == "output"),
                None,
            )
            if driver is None:
                continue
            sn = spice_node(node.id)
            r_out = pin_resistance(mcus[driver.component_id].part_number)
            lines.append(f"V_PIN_{node.id.upper()} {sn}_src 0 DC {node.voltage_nominal}")
            lines.append(f"R_PIN_{node.id.upper()} {sn}_src {sn} {r_out}")
            touch(sn)

        lines.append("")

        # Component elements
        has_led = False
        led_models: Dict[str, str] = {}
        for comp in ir.components:
            pins = pin_map.get(comp.id, {})
            element = self._comp_to_spice(comp, pins, spice_node)
            if element:
                lines.append(element)
                # Positions 1 and 2 of every SPICE element are the two terminal nodes
                parts = element.split()
                for sn in parts[1:3]:
                    touch(sn)
            if comp.type == ComponentType.LED:
                params = led_parameters(comp.part_number)
                if params is None:
                    has_led = True
                else:
                    i_s, n = params
                    led_models[led_model_name(comp.part_number)] = f"(Is={i_s:.6e} N={n:g})"

        lines.append("")

        # Tie-down resistors: prevent floating nodes that cause singular matrix errors
        for node in ir.nodes:
            sn = spice_node(node.id)
            if sn == "0":
                continue
            if node_conns.get(sn, 0) < 2:
                lines.append(f"R_TIE_{node.id.upper()} {sn} 0 1G")

        lines.append("")

        # Analysis command
        if analysis:
            if analysis.type == "dc_op":
                lines.append(".op")
            elif analysis.type == "ac_sweep":
                lines.append(
                    f".ac dec {analysis.points_per_decade} {analysis.f_start} {analysis.f_stop}"
                )
            elif analysis.type == "transient":
                lines.append(f".tran {analysis.step_time} {analysis.stop_time}")
        else:
            lines.append(".op")

        lines.append("")

        # Print directives — one combined line so ngspice produces a single table
        # (multiple .print lines create separate tables which complicate parsing)
        mode_map = {"dc_op": "dc", "ac_sweep": "ac", "transient": "tran"}
        mode = mode_map.get(analysis.type, "dc") if analysis else "dc"

        non_gnd = [n for n in ir.nodes if n.id != gnd_id]
        if non_gnd:
            cols = " ".join(f"v({spice_node(n.id)})" for n in non_gnd)
            lines.append(f".print {mode} {cols}")

        if has_led:
            lines.append("")
            lines.append(".model DLED D (Is=1e-9 n=1.8 Vt=0.02585)")
        # Tabulated LEDs get a diode fitted to their datasheet forward voltage
        # (generators/netlist/models.py); predict() solves the same model.
        for name, params in sorted(led_models.items()):
            lines.append(f".model {name} D {params}")

        lines.append(".end")
        return "\n".join(lines)

    def _comp_to_spice(
        self, comp, pins: Dict[str, str], spice_node
    ) -> Optional[str]:
        ctype = comp.type.value if hasattr(comp.type, "value") else str(comp.type)

        if ctype == "resistor":
            if len(pins) < 2:
                return None
            node_a = spice_node(pins.get("A") or next(iter(pins.values())))
            others = [v for k, v in pins.items() if k != "A"]
            node_b = spice_node(others[0]) if others else "0"
            ohms = _parse_ohms(comp.value) if comp.value else 1000.0
            return f"R_{comp.id} {node_a} {node_b} {round(ohms or 1000.0, 4)}"

        if ctype == "capacitor":
            if not pins:
                return None
            node_p = spice_node(pins.get("+") or next(iter(pins.values())))
            node_m = spice_node(pins.get("-") or "0")
            farads = _parse_farads(comp.value) if comp.value else 100e-9
            return f"C_{comp.id} {node_p} {node_m} {farads or 100e-9}"

        if ctype == "led":
            if not pins:
                return None
            anode = spice_node(pins.get("ANODE") or next(iter(pins.values())))
            others = [v for k, v in pins.items() if k != "ANODE"]
            cathode = spice_node(others[0]) if others else "0"
            model = led_model_name(comp.part_number) if led_parameters(comp.part_number) else "DLED"
            return f"D_{comp.id} {anode} {cathode} {model}"

        # Active components (MCU, sensor, transceiver, etc.): resistive load between VCC and GND
        vcc_node = next(
            (spice_node(v) for k, v in pins.items() if k.upper() in _VCC_PIN_NAMES), None
        )
        gnd_node = next(
            (spice_node(v) for k, v in pins.items() if k.upper() in _GND_PIN_NAMES), None
        )
        if not vcc_node or not gnd_node:
            return None

        if ctype == "microcontroller":
            # MCU modelled as a resistive load (CLAUDE.md Rule 3): 100 Ω on the
            # Uno (5 V / 100 Ω = 50 mA); each part's own run-current model since Stage 5.
            return f"R_MCU_{comp.id} {vcc_node} {gnd_node} {mcu_supply_ohms(comp.part_number):g}"

        # Sensor, transceiver, relay, etc.: derive load from current_draw_ma if
        # available. The rule lives in models.load_ohms so predict() reads it too.
        load_r = int(load_ohms(comp.current_draw_ma, comp.supply_voltage_max))
        return f"R_LOAD_{comp.id} {vcc_node} {gnd_node} {load_r}"
