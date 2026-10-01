"""
Arduino firmware generator — takes CircuitIR, returns complete .ino source.
Pure Jinja2 template rendering. No LLM involved. Deterministic.

Stage 5: one template family serves every board in `data/mcu_targets.py`,
all on the Arduino framework. What differs is data — the name firmware uses
for each pin, and which serial port the RS-485 design talks through — so pins
are resolved through the design's board, never by string surgery on a label.
The Uno's output is byte-identical to what it was before.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.ir_schema import CircuitIR, ComponentType, SignalType
from data.mcu_targets import DEFAULT_TARGET, Target, get_target

TEMPLATE_DIR = Path(__file__).parent / "templates"


class ArduinoFirmwareGenerator:
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape([]),  # no HTML escaping for .ino files
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(self, ir: CircuitIR) -> str:
        template_name, context = self._select_template(ir)
        template = self.env.get_template(template_name)
        return template.render(ir=ir, **context)

    def template_for(self, ir: CircuitIR) -> str:
        """Which template a design renders with — what decides its libraries."""
        return self._select_template(ir)[0]

    # ── The board ─────────────────────────────────────────────────────────

    @staticmethod
    def target(ir: CircuitIR) -> Target:
        from validation.pin_rules import design_target

        return design_target(ir) or get_target(DEFAULT_TARGET)

    def _fw_pin(self, ir: CircuitIR, pin: str) -> str:
        """The name firmware writes for a board pin: "13" on the Uno, "4" on the ESP32, "PB0" on the STM32."""
        resolved = self.target(ir).pin(pin)
        # A pin the board's table does not know (a Phase 1 fixture's label)
        # keeps the Phase 1 reading.
        return resolved.firmware if resolved else pin.replace("D", "").replace("d", "")

    def _mcu_pin_for(self, ir: CircuitIR, component_id: str, pin: str | None = None) -> str | None:
        """
        The MCU pin wired to `component_id` (to its `pin`, if given): on the
        same net, or across one series resistor — an LED's R1, never a pull-up
        to the rail, since supply and ground nets are not signal paths. None
        when no MCU signal pin reaches it.

        Stage 5: this replaced a walk that looked for the MCU on the LED's own
        net. The MCU drives R1's other end, so it was never found and every LED
        sketch said pin 13 — right on the Uno's default D13 by coincidence,
        wrong for any other pin and on every other board.
        """
        mcu_ids = {c.id for c in ir.components if c.type == ComponentType.MICROCONTROLLER}
        resistor_ids = {c.id for c in ir.components if c.type == ComponentType.RESISTOR}
        rails = {n.id for n in ir.nodes if n.type in (SignalType.POWER, SignalType.GROUND)}
        by_node: dict = {}
        for conn in ir.connections:
            by_node.setdefault(conn.node_id, []).append(conn)

        start = [conn.node_id for conn in ir.connections
                 if conn.component_id == component_id and (pin is None or conn.pin.upper() == pin.upper())]
        frontier = [n for n in start if n not in rails]
        for _hop in range(2):
            for node in frontier:
                for conn in by_node.get(node, ()):
                    if conn.component_id in mcu_ids:
                        return conn.pin
            frontier = [other.node_id
                        for node in frontier for conn in by_node.get(node, ()) if conn.component_id in resistor_ids
                        for other in ir.connections
                        if other.component_id == conn.component_id and other.node_id != node
                        and other.node_id not in rails]
        return None

    def _select_template(self, ir: CircuitIR) -> tuple[str, dict]:
        has_modbus = self._has_modbus(ir)
        has_dht = self._has_dht(ir)
        has_led_only = self._is_led_only(ir)

        if has_modbus:
            return "modbus_master.ino.j2", self._modbus_context(ir)
        if has_dht:
            return "sensor_read.ino.j2", self._sensor_context(ir)
        if has_led_only:
            return "led_blink.ino.j2", self._led_context(ir)
        return "base.ino.j2", self._base_context(ir)

    # ── Template selectors ────────────────────────────────────────────────

    def _has_modbus(self, ir: CircuitIR) -> bool:
        return any(
            c.type == ComponentType.TRANSCEIVER and "485" in c.part_number.upper()
            for c in ir.components
        )

    def _has_dht(self, ir: CircuitIR) -> bool:
        return any(
            c.sensor_type == "dht22" or "DHT" in c.part_number.upper()
            for c in ir.components
        )

    def _is_led_only(self, ir: CircuitIR) -> bool:
        has_led = any(c.type == ComponentType.LED for c in ir.components)
        has_complex = any(
            c.type in (ComponentType.SENSOR, ComponentType.TRANSCEIVER, ComponentType.MODEM)
            for c in ir.components
        )
        return has_led and not has_complex

    # ── Context builders ──────────────────────────────────────────────────

    def _sensor_context(self, ir: CircuitIR) -> dict:
        sensor = next(
            (c for c in ir.components if c.sensor_type == "dht22" or "DHT" in c.part_number.upper()),
            None,
        )
        dht_pin = "2"  # safe default
        if sensor:
            mcu_pin = self._mcu_pin_for(ir, sensor.id, "DATA")
            if mcu_pin:
                dht_pin = self._fw_pin(ir, mcu_pin)

        threshold = ir.constraints.get("threshold_temp_celsius")
        alert_pin = None
        alert_conn = next(
            (conn for conn in ir.connections
             if "ALERT" in conn.node_id.upper() or "RELAY" in conn.node_id.upper()),
            None,
        )
        if alert_conn:
            mcu = next(
                (c for c in ir.components if c.type == ComponentType.MICROCONTROLLER), None
            )
            if mcu:
                mcu_alert = next(
                    (c for c in ir.connections
                     if c.component_id == mcu.id and c.node_id == alert_conn.node_id),
                    None,
                )
                if mcu_alert:
                    alert_pin = self._fw_pin(ir, mcu_alert.pin)

        dht_type = "DHT22"
        if sensor and "DHT11" in sensor.part_number.upper():
            dht_type = "DHT11"

        return {
            "dht_pin": dht_pin,
            "dht_type": dht_type,
            "threshold_temp": threshold,
            "alert_pin": alert_pin,
        }

    def _modbus_context(self, ir: CircuitIR) -> dict:
        transceiver = next(
            (c for c in ir.components if c.type == ComponentType.TRANSCEIVER), None
        )
        de_re_pin = "2"  # default
        if transceiver:
            de_conn = next(
                (conn for conn in ir.connections
                 if conn.component_id == transceiver.id and conn.pin.upper() in ("DE", "RE")),
                None,
            )
            if de_conn:
                same_node_mcu_conn = next(
                    (c for c in ir.connections
                     if c.node_id == de_conn.node_id and c.component_id != transceiver.id),
                    None,
                )
                if same_node_mcu_conn:
                    de_re_pin = self._fw_pin(ir, same_node_mcu_conn.pin)

        slave_devices = ir.constraints.get("modbus_slaves", [
            {"address": 1, "register_start": 0, "register_count": 4, "name": "Device_1"}
        ])
        return {
            "de_re_pin": de_re_pin,
            "serial": self._rs485_serial(ir),
            "baud_rate": ir.constraints.get("modbus_baud", 9600),
            "devices": slave_devices,
            "poll_interval_ms": ir.constraints.get("poll_interval_ms", 5000),
        }

    def _led_context(self, ir: CircuitIR) -> dict:
        led = next((c for c in ir.components if c.type == ComponentType.LED), None)
        led_pin = "13"
        if led:
            mcu_pin = self._mcu_pin_for(ir, led.id)
            if mcu_pin:
                led_pin = self._fw_pin(ir, mcu_pin)
        return {
            "led_pin": led_pin,
            "on_time_ms": ir.constraints.get("on_time_ms", 1000),
            "off_time_ms": ir.constraints.get("off_time_ms", 1000),
        }

    def _rs485_serial(self, ir: CircuitIR) -> dict:
        """
        The serial port the Modbus master talks through: SoftwareSerial on the
        Uno (D0/D1 are the USB console), the board's hardware UART elsewhere.
        TX and RX are read from the design's UART nets, so the firmware drives
        the pins the schematic wires.
        """
        target = self.target(ir)
        mcu_ids = {c.id for c in ir.components if c.type == ComponentType.MICROCONTROLLER}

        def pin_on(node: str, default: str) -> str:
            conn = next((c for c in ir.connections if c.node_id == node and c.component_id in mcu_ids), None)
            # A label the board does not know (Phase 1's IR_005 wires "D0_RX")
            # keeps the Phase 1 pins; the pin rules report the wiring.
            resolved = target.pin(conn.pin) if conn else None
            return resolved.firmware if resolved else default

        if target.rs485_uart is None:
            kind = "software"
        elif target.uart_mode == "matrix":
            kind = "esp32"
        else:
            kind = "stm32"
        return {
            "kind": kind,
            "board": target.board,
            "uart": target.rs485_uart,
            "tx": pin_on("UART_TX", "11"),
            "rx": pin_on("UART_RX", "10"),
        }

    def _base_context(self, ir: CircuitIR) -> dict:
        return {
            "includes": [],
            "pin_definitions": {},
            "constants": [],
            "setup_lines": ['Serial.println("[CircuitOS] No specific template matched. Review IR.");'],
            "loop_lines": ['Serial.println("[CircuitOS] Running...");'],
            "loop_delay_ms": 1000,
        }
