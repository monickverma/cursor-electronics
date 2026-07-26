"""PCB netlist generator — CircuitIR → PCB Engine netlist dict."""

from typing import Any, Dict, List
from core.ir_schema import CircuitIR, SignalType


class PcbNetlistGenerator:
    """Translates CircuitIR into the JSON format expected by compile_board.py."""

    def generate(self, ir: CircuitIR) -> Dict[str, Any]:
        # 1. Identify ground net
        ground_node = next((n for n in ir.nodes if n.type == SignalType.GROUND), None)
        ground_net = ground_node.id if ground_node else "GND"

        # 2. Identify power nets (power and ground nodes)
        power_nets = [
            n.id for n in ir.nodes
            if n.type in (SignalType.POWER, SignalType.GROUND) or "VCC" in n.id.upper() or "GND" in n.id.upper()
        ]
        if not power_nets:
            power_nets = [ground_net]

        # Deduplicate while preserving order
        seen = set()
        power_nets_dedup = [x for x in power_nets if not (x in seen or seen.add(x))]

        # 3. Build component pin maps
        pin_map: Dict[str, Dict[str, str]] = {}
        for conn in ir.connections:
            pin_map.setdefault(conn.component_id, {})[str(conn.pin)] = conn.node_id

        components: List[Dict[str, Any]] = []
        for comp in ir.components:
            comp_entry: Dict[str, Any] = {
                "ref": comp.id,
                "mpn": comp.part_number,
                "pins": pin_map.get(comp.id, {})
            }
            if comp.package:
                comp_entry["package"] = comp.package
            components.append(comp_entry)

        # 4. Board dimensions heuristic based on component count
        num_comps = len(ir.components)
        width = max(63.5, round(20.0 + num_comps * 6.0, 2))
        height = max(45.72, round(18.0 + num_comps * 4.5, 2))

        name = f"board_{ir.circuit_id[:8]}"

        return {
            "name": name,
            "board": {
                "width": width,
                "height": height,
                "layers": 2
            },
            "ground_net": ground_net,
            "power_nets": power_nets_dedup,
            "components": components
        }
