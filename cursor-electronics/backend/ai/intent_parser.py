"""
Intent parser — converts a natural language hardware prompt into a structured
DesignSpec using Claude's tool_use mode with tool_choice forced.
No JSON parsing, no regex — the tool_use response is already a parsed dict.
"""

from __future__ import annotations

from ai.client import ai_model, make_client
from core.ir_schema import ApplicationClass, SafetyClass

SYSTEM_PROMPT = """\
You are a hardware design intent parser. Your only job is to extract structured
information from a natural language hardware project description.

Rules:
- Call extract_design_spec EXACTLY ONCE with the information extracted from the prompt.
- If a field is not mentioned, use the most reasonable default.
- application_class: "hobby_arduino" for DIY/maker projects, "iot_node" for connected
  devices, "industrial_io" for industrial/HVAC, "modbus_rtu" for RS-485 Modbus,
  "hvac_control" for HVAC specifically.
- safety_class: "general" unless the prompt mentions life safety, mains voltage,
  or safety-critical systems.
- Extract numeric constraints wherever mentioned (temperatures, voltages, baud rates).
- Identify the primary sensor or transceiver type if mentioned.
"""

_EXTRACT_TOOL = {
    "name": "extract_design_spec",
    "description": "Extract structured design specification from a hardware prompt.",
    "input_schema": {
        "type": "object",
        "required": ["intent", "application_class"],
        "properties": {
            "intent": {
                "type": "string",
                "description": "Clean restatement of the user's intent (1–2 sentences, present tense)",
            },
            "application_class": {
                "type": "string",
                "enum": [c.value for c in ApplicationClass],
            },
            "safety_class": {
                "type": "string",
                "enum": [s.value for s in SafetyClass],
                "default": "general",
            },
            "target_mcu": {
                "type": "string",
                "description": "Normalized MCU name: 'arduino_uno', 'esp32', 'stm32f4', or null",
            },
            "constraints": {
                "type": "object",
                "description": "Key-value pairs: supply_voltage, threshold_temp_celsius, modbus_baud, etc.",
            },
            "primary_sensor": {
                "type": "string",
                "description": "Sensor type if mentioned: 'dht22', 'bmp280', 'ds18b20', etc.",
            },
            "use_rs485": {
                "type": "boolean",
                "description": "True if RS-485 or Modbus RTU is mentioned",
            },
            "has_relay": {
                "type": "boolean",
                "description": "True if a relay or actuator output is mentioned",
            },
        },
    },
}


class DesignSpec:
    """Parsed design spec — a thin wrapper around the tool_use dict output."""

    def __init__(self, raw: dict):
        self.intent: str = raw["intent"]
        self.application_class: str = raw["application_class"]
        self.safety_class: str = raw.get("safety_class", "general")
        self.target_mcu: str | None = raw.get("target_mcu")
        self.constraints: dict = raw.get("constraints") or {}
        self.primary_sensor: str | None = raw.get("primary_sensor")
        self.use_rs485: bool = raw.get("use_rs485", False)
        self.has_relay: bool = raw.get("has_relay", False)

    def __repr__(self) -> str:
        return (
            f"DesignSpec(intent={self.intent!r}, "
            f"app={self.application_class}, mcu={self.target_mcu})"
        )


class IntentParser:
    def __init__(self):
        self.client = make_client()

    def parse(self, prompt: str) -> DesignSpec:
        response = self.client.messages.create(
            model=ai_model(),
            max_tokens=512,
            system=SYSTEM_PROMPT,
            tools=[_EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": "extract_design_spec"},
            messages=[{"role": "user", "content": prompt}],
        )
        tool_input: dict = response.content[0].input
        return DesignSpec(tool_input)
