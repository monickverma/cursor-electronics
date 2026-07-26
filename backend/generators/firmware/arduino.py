"""
Arduino firmware generator — takes CircuitIR, returns complete .ino source.
Pure Jinja2 template rendering. No LLM involved. Deterministic.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.ir_schema import CircuitIR, ComponentType, SignalType

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
            data_conn = next(
                (conn for conn in ir.connections
                 if conn.component_id == sensor.id and conn.pin.upper() == "DATA"),
                None,
            )
            if data_conn:
                # Find what MCU pin connects to the same node as DATA
                data_node = data_conn.node_id
                mcu_conn = next(
                    (conn for conn in ir.connections
                     if conn.node_id == data_node and conn.component_id != sensor.id),
                    None,
                )
                if mcu_conn:
                    dht_pin = mcu_conn.pin.replace("D", "").replace("d", "")

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
                    alert_pin = mcu_alert.pin.replace("D", "").replace("d", "")

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
                    de_re_pin = same_node_mcu_conn.pin.replace("D", "").replace("d", "")

        slave_devices = ir.constraints.get("modbus_slaves", [
            {"address": 1, "register_start": 0, "register_count": 4, "name": "Device_1"}
        ])
        return {
            "de_re_pin": de_re_pin,
            "baud_rate": ir.constraints.get("modbus_baud", 9600),
            "devices": slave_devices,
            "poll_interval_ms": ir.constraints.get("poll_interval_ms", 5000),
        }

    def _led_context(self, ir: CircuitIR) -> dict:
        led = next((c for c in ir.components if c.type == ComponentType.LED), None)
        led_pin = "13"
        if led:
            led_conn = next(
                (conn for conn in ir.connections if conn.component_id == led.id), None
            )
            if led_conn:
                # Find the node that the LED's anode connects to (through resistor)
                anode_node = led_conn.node_id
                # Find which MCU pin drives that net (through the current-limit resistor)
                for conn in ir.connections:
                    if conn.node_id == anode_node:
                        mcu = next(
                            (c for c in ir.components
                             if c.id == conn.component_id and c.type == ComponentType.MICROCONTROLLER),
                            None,
                        )
                        if mcu:
                            led_pin = conn.pin.replace("D", "").replace("d", "")
                            break
        return {
            "led_pin": led_pin,
            "on_time_ms": ir.constraints.get("on_time_ms", 1000),
            "off_time_ms": ir.constraints.get("off_time_ms", 1000),
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
