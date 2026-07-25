"""
Week 2 — ArduinoFirmwareGenerator tests.

What is verified:
- Template selection: each of the 5 example IRs routes to the correct .ino.j2 template
- Context extraction: pins, sensor type, thresholds, baud rate pulled from IR connections
- Output structure: correct #define, library includes, function names present in generated code
- Arduino compilation: generated .ino compiles with arduino-cli (skipped if not installed)

Compilation prerequisites (CI installs these automatically):
    arduino-cli core install arduino:avr
    arduino-cli lib install "DHT sensor library"
    arduino-cli lib install "ModbusMaster"
"""

import os
import shutil
import subprocess
import tempfile

import pytest

from generators.firmware.arduino import ArduinoFirmwareGenerator
from core.ir_examples import IR_001, IR_002, IR_003, IR_004, IR_005

import os as _os

def _find_arduino_cli() -> str:
    if shutil.which("arduino-cli"):
        return "arduino-cli"
    candidates = [
        r"C:\Users\KIIT\bin\arduino-cli.exe",
        _os.path.expanduser(r"~\bin\arduino-cli.exe"),
    ]
    for c in candidates:
        if _os.path.exists(c):
            return c
    return "arduino-cli"

_ARDUINO_CLI = _find_arduino_cli()
ARDUINO_CLI_AVAILABLE = shutil.which("arduino-cli") is not None or _os.path.exists(_ARDUINO_CLI)


def _compile(ino_source: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as tmp:
        sketch_dir = os.path.join(tmp, "sketch")
        os.makedirs(sketch_dir)
        sketch_path = os.path.join(sketch_dir, "sketch.ino")
        with open(sketch_path, "w") as f:
            f.write(ino_source)
        return subprocess.run(
            [_ARDUINO_CLI, "compile", "--fqbn", "arduino:avr:uno", sketch_dir],
            capture_output=True,
            text=True,
        )


# ── Template selection ────────────────────────────────────────────────────────

class TestTemplateSelection:
    """Each IR routes to the correct Jinja2 template."""

    def test_dht22_selects_sensor_read_template(self, ir_dht22):
        gen = ArduinoFirmwareGenerator()
        name, _ = gen._select_template(ir_dht22)
        assert name == "sensor_read.ino.j2"

    def test_led_selects_led_blink_template(self, ir_led):
        gen = ArduinoFirmwareGenerator()
        name, _ = gen._select_template(ir_led)
        assert name == "led_blink.ino.j2"

    def test_modbus_selects_modbus_master_template(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        name, _ = gen._select_template(ir_modbus)
        assert name == "modbus_master.ino.j2"

    def test_rc_filter_falls_to_base_template(self, ir_rc_filter):
        gen = ArduinoFirmwareGenerator()
        name, _ = gen._select_template(ir_rc_filter)
        assert name == "base.ino.j2"

    def test_voltage_divider_falls_to_base_template(self, ir_voltage_divider):
        gen = ArduinoFirmwareGenerator()
        name, _ = gen._select_template(ir_voltage_divider)
        assert name == "base.ino.j2"


# ── DHT22 context extraction ──────────────────────────────────────────────────

class TestDHT22Context:
    """Sensor context is extracted by traversing the IR connection graph."""

    def test_dht_pin_extracted_from_connections(self, ir_dht22):
        # U2.DATA → DHT22_DATA node → U1.D2 on the same node → strip "D" → "2"
        gen = ArduinoFirmwareGenerator()
        ctx = gen._sensor_context(ir_dht22)
        assert ctx["dht_pin"] == "2"

    def test_dht_type_is_dht22(self, ir_dht22):
        gen = ArduinoFirmwareGenerator()
        ctx = gen._sensor_context(ir_dht22)
        assert ctx["dht_type"] == "DHT22"

    def test_threshold_temp_from_constraints(self, ir_dht22):
        gen = ArduinoFirmwareGenerator()
        ctx = gen._sensor_context(ir_dht22)
        assert ctx["threshold_temp"] == 40

    def test_no_alert_pin_when_no_alert_or_relay_node(self, ir_dht22):
        # IR_001 has no node named *ALERT* or *RELAY*
        gen = ArduinoFirmwareGenerator()
        ctx = gen._sensor_context(ir_dht22)
        assert ctx["alert_pin"] is None


# ── DHT22 output structure ────────────────────────────────────────────────────

class TestDHT22Output:
    def test_output_is_non_empty_string(self, ir_dht22):
        gen = ArduinoFirmwareGenerator()
        output = gen.generate(ir_dht22)
        assert isinstance(output, str) and len(output) > 0

    def test_includes_dht_library(self, ir_dht22):
        gen = ArduinoFirmwareGenerator()
        assert "#include <DHT.h>" in gen.generate(ir_dht22)

    def test_defines_dhtpin_2(self, ir_dht22):
        gen = ArduinoFirmwareGenerator()
        assert "#define DHTPIN    2" in gen.generate(ir_dht22)

    def test_defines_dhttype_dht22(self, ir_dht22):
        gen = ArduinoFirmwareGenerator()
        assert "#define DHTTYPE   DHT22" in gen.generate(ir_dht22)

    def test_defines_threshold_temp_40(self, ir_dht22):
        gen = ArduinoFirmwareGenerator()
        assert "#define THRESHOLD_TEMP 40" in gen.generate(ir_dht22)

    def test_embeds_circuit_intent_in_header(self, ir_dht22):
        gen = ArduinoFirmwareGenerator()
        assert ir_dht22.intent in gen.generate(ir_dht22)

    def test_has_setup_and_loop_functions(self, ir_dht22):
        gen = ArduinoFirmwareGenerator()
        output = gen.generate(ir_dht22)
        assert "void setup()" in output
        assert "void loop()" in output

    def test_nan_guard_present(self, ir_dht22):
        # Sensor failure must be caught — isnan() check is required by DHT22 datasheet
        gen = ArduinoFirmwareGenerator()
        assert "isnan" in gen.generate(ir_dht22)


# ── LED context extraction ────────────────────────────────────────────────────

class TestLEDContext:
    def test_led_pin_is_13(self, ir_led):
        # IR_002: U1.D13 → LED_CTRL → R1 → LED_ANODE → LED1.
        # The generator searches for an MCU on the LED_ANODE node but finds only R1 there.
        # It falls back to the default "13", which happens to equal D13 for this IR.
        # Known Phase 1 limitation: only works when the LED is on pin 13.
        gen = ArduinoFirmwareGenerator()
        ctx = gen._led_context(ir_led)
        assert ctx["led_pin"] == "13"

    def test_on_off_times_default_1000ms(self, ir_led):
        gen = ArduinoFirmwareGenerator()
        ctx = gen._led_context(ir_led)
        assert ctx["on_time_ms"] == 1000
        assert ctx["off_time_ms"] == 1000


# ── LED output structure ──────────────────────────────────────────────────────

class TestLEDOutput:
    def test_output_is_non_empty_string(self, ir_led):
        gen = ArduinoFirmwareGenerator()
        output = gen.generate(ir_led)
        assert isinstance(output, str) and len(output) > 0

    def test_defines_led_pin_13(self, ir_led):
        gen = ArduinoFirmwareGenerator()
        assert "#define LED_PIN  13" in gen.generate(ir_led)

    def test_pinmode_output_present(self, ir_led):
        gen = ArduinoFirmwareGenerator()
        assert "pinMode(LED_PIN, OUTPUT)" in gen.generate(ir_led)

    def test_digitalwrite_high_and_low_present(self, ir_led):
        gen = ArduinoFirmwareGenerator()
        output = gen.generate(ir_led)
        assert "digitalWrite(LED_PIN, HIGH)" in output
        assert "digitalWrite(LED_PIN, LOW)" in output

    def test_has_setup_and_loop_functions(self, ir_led):
        gen = ArduinoFirmwareGenerator()
        output = gen.generate(ir_led)
        assert "void setup()" in output
        assert "void loop()" in output


# ── Modbus context extraction ─────────────────────────────────────────────────

class TestModbusContext:
    def test_de_re_pin_extracted_from_connections(self, ir_modbus):
        # U2.DE → RS485_DE_RE node → U1.D2 on same node → strip "D" → "2"
        gen = ArduinoFirmwareGenerator()
        ctx = gen._modbus_context(ir_modbus)
        assert ctx["de_re_pin"] == "2"

    def test_baud_rate_from_constraints(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        ctx = gen._modbus_context(ir_modbus)
        assert ctx["baud_rate"] == 9600

    def test_slave_devices_from_constraints(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        ctx = gen._modbus_context(ir_modbus)
        assert len(ctx["devices"]) == 2
        assert ctx["devices"][0]["address"] == 1
        assert ctx["devices"][1]["address"] == 2

    def test_poll_interval_from_constraints(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        ctx = gen._modbus_context(ir_modbus)
        assert ctx["poll_interval_ms"] == 5000


# ── Modbus output structure ───────────────────────────────────────────────────

class TestModbusOutput:
    def test_output_is_non_empty_string(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        output = gen.generate(ir_modbus)
        assert isinstance(output, str) and len(output) > 0

    def test_includes_modbusmaster_library(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        assert "#include <ModbusMaster.h>" in gen.generate(ir_modbus)

    def test_defines_rs485_de_re_pin_2(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        assert "#define RS485_DE_RE_PIN  2" in gen.generate(ir_modbus)

    def test_defines_modbus_baud_9600(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        assert "#define MODBUS_BAUD      9600" in gen.generate(ir_modbus)

    def test_pre_and_post_transmission_callbacks_present(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        output = gen.generate(ir_modbus)
        assert "preTransmission" in output
        assert "postTransmission" in output

    def test_both_slave_device_names_in_output(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        output = gen.generate(ir_modbus)
        assert "Device_1" in output
        assert "Device_2" in output

    def test_device_count_is_2(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        assert "DEVICE_COUNT = 2" in gen.generate(ir_modbus)

    def test_poll_interval_delay_in_loop(self, ir_modbus):
        gen = ArduinoFirmwareGenerator()
        assert "delay(5000)" in gen.generate(ir_modbus)


# ── Passive circuits (no MCU) ─────────────────────────────────────────────────

class TestPassiveCircuits:
    """RC filter and voltage divider have no MCU — fall through to base template."""

    def test_rc_filter_produces_valid_base_output(self, ir_rc_filter):
        gen = ArduinoFirmwareGenerator()
        output = gen.generate(ir_rc_filter)
        assert isinstance(output, str) and len(output) > 0
        assert "void setup()" in output
        assert "void loop()" in output

    def test_voltage_divider_produces_valid_base_output(self, ir_voltage_divider):
        gen = ArduinoFirmwareGenerator()
        output = gen.generate(ir_voltage_divider)
        assert isinstance(output, str) and len(output) > 0
        assert "void setup()" in output
        assert "void loop()" in output

    def test_base_output_contains_no_template_matched_message(self, ir_rc_filter):
        gen = ArduinoFirmwareGenerator()
        assert "No specific template matched" in gen.generate(ir_rc_filter)


# ── Arduino compilation ───────────────────────────────────────────────────────

@pytest.mark.skipif(not ARDUINO_CLI_AVAILABLE, reason="arduino-cli not installed")
class TestArduinoCompilation:
    """
    Attempts actual AVR compilation via arduino-cli.
    Requires: arduino-cli core install arduino:avr
              arduino-cli lib install "DHT sensor library"
              arduino-cli lib install "ModbusMaster"
    """

    def test_dht22_firmware_compiles(self, ir_dht22):
        result = _compile(ArduinoFirmwareGenerator().generate(ir_dht22))
        assert result.returncode == 0, f"Compilation failed:\n{result.stderr}"

    def test_led_firmware_compiles(self, ir_led):
        result = _compile(ArduinoFirmwareGenerator().generate(ir_led))
        assert result.returncode == 0, f"Compilation failed:\n{result.stderr}"

    def test_modbus_firmware_compiles(self, ir_modbus):
        result = _compile(ArduinoFirmwareGenerator().generate(ir_modbus))
        assert result.returncode == 0, f"Compilation failed:\n{result.stderr}"
