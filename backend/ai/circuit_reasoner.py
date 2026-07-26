"""
Circuit reasoner — converts a DesignSpec into a validated CircuitIR.

Error budget (3 distinct failure types):
  1. anthropic.APIError  → do NOT retry; raise immediately → caller returns 503
  2. json.JSONDecodeError → re-prompt with position of error (tool_use makes this rare)
  3. pydantic.ValidationError → re-prompt with specific field paths (most common)

Maximum 3 attempts total. On all-fail → raise CircuitGenerationError → caller returns 422.
"""

from __future__ import annotations

import json
from typing import Optional

import anthropic
from ai.client import ai_model, make_client
from pydantic import ValidationError

from core.config import settings
from core.ir_schema import CircuitIR, ValidationRule
from core.ir_validator import validate_ir
from data.component_constraints import format_for_prompt

from .intent_parser import DesignSpec

MAX_ATTEMPTS = 3

# The largest reference IR (IR_005) serialises to ~1,960 tokens, so this leaves
# roughly 4x headroom for a verbose model. Retries append the previous IR to the
# conversation, so later attempts need more room than the first, not less.
MAX_OUTPUT_TOKENS = 8192

SYSTEM_PROMPT = """\
You are Circuit OS, an AI hardware compiler. You produce electronics circuit designs
as structured JSON against a locked schema.

ABSOLUTE RULES — violating any of these produces a broken design:
1. Every component needs a unique ID (R1, R2, C1, U1 — sequential within type).
2. Every connection.component_id must reference an existing component ID.
3. Every connection.node_id must reference an existing node ID.
4. justification must be ≥ 20 characters and explain WHY the component was chosen.
5. confidence must be 0.0–1.0.
6. supply_voltage_max on passive components (resistors, capacitors) is the maximum
   working voltage — NOT forward voltage. For a 100nF ceramic capacitor rated 16V,
   supply_voltage_max = 16.0. For a 10kΩ resistor rated 50V, supply_voltage_max = 50.0.
7. For MCUs modeled in simulation, they are represented as resistive loads (100Ω),
   never as voltage sources.
8. RS-485 buses require: 120Ω termination between A and B lines,
   560Ω bias resistors (A to VCC, B to GND).
9. I2C buses require: 4.7kΩ pull-up resistors on both SDA and SCL to VCC.
10. DHT22 DATA pin requires a 10kΩ pull-up resistor to VCC.
11. Every power rail node and every ground node must have ≥2 connections.
12. Use real manufacturer part numbers. No placeholder values.

COMPONENT CONSTRAINTS FOR THIS DESIGN:
{constraints}

Call generate_circuit_ir exactly once with the complete circuit design.
"""

_GENERATE_TOOL = {
    "name": "generate_circuit_ir",
    "description": "Generate a complete CircuitIR JSON object for the hardware design.",
    "input_schema": CircuitIR.model_json_schema(),
}


class CircuitGenerationError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, attempts: list[str]):
        self.attempt_errors = attempts
        super().__init__(f"Circuit generation failed after {len(attempts)} attempts")


class CircuitReasoner:
    def __init__(self):
        self.client = make_client()

    def generate(self, spec: DesignSpec) -> CircuitIR:
        constraint_parts = []
        if spec.primary_sensor:
            text = format_for_prompt([spec.primary_sensor.upper()])
            if text:
                constraint_parts.append(text)
        if spec.use_rs485:
            text = format_for_prompt(["MAX485ECSA"])
            if text:
                constraint_parts.append(text)
        constraint_text = "\n".join(constraint_parts) or "(no specific constraints loaded)"

        system = SYSTEM_PROMPT.format(constraints=constraint_text)
        messages: list[dict] = [{"role": "user", "content": self._build_user_prompt(spec)}]

        attempt_errors: list[str] = []
        last_raw: Optional[dict] = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.client.messages.create(
                    model=ai_model(),
                    max_tokens=MAX_OUTPUT_TOKENS,
                    system=system,
                    tools=[_GENERATE_TOOL],
                    tool_choice={"type": "tool", "name": "generate_circuit_ir"},
                    messages=messages,
                )

                # A tool call cut off at the token ceiling yields a partial dict,
                # which then fails schema validation for *missing fields* — the
                # symptom looks identical to the model getting the schema wrong.
                # Retrying makes it strictly worse: _append_correction adds the
                # previous IR to the context, so each attempt has less room than
                # the last. Fail loudly and immediately instead of burning three
                # attempts on an error no re-prompt can fix.
                if response.stop_reason == "max_tokens":
                    raise CircuitGenerationError([
                        f"Model output hit the {MAX_OUTPUT_TOKENS}-token ceiling and was "
                        f"truncated mid-tool-call, so the design is incomplete. "
                        f"This is a budget problem, not a schema problem — raise "
                        f"MAX_OUTPUT_TOKENS in circuit_reasoner.py, or use a model "
                        f"that writes more concisely (current: '{ai_model()}')."
                    ])

                last_raw = response.content[0].input

                # Override intent/application_class from spec to ensure consistency
                last_raw.setdefault("intent", spec.intent)
                last_raw.setdefault("application_class", spec.application_class)
                last_raw.setdefault("safety_class", spec.safety_class)
                if spec.target_mcu:
                    last_raw.setdefault("target_mcu", spec.target_mcu)
                if spec.constraints:
                    last_raw.setdefault("constraints", spec.constraints)

                ir = CircuitIR.model_validate(last_raw)
                val_result = validate_ir(ir)
                if not val_result.is_valid:
                    raise ValueError(
                        "IR failed cross-field validation: "
                        + "; ".join(e.message for e in val_result.errors)
                    )
                return ir

            except anthropic.APIError:
                # API down / rate limited — do not retry
                raise

            except (json.JSONDecodeError, KeyError) as exc:
                # tool_use returns a dict, so JSONDecodeError is rare, but guard anyway
                err = f"Attempt {attempt}: JSON/key error — {exc}"
                attempt_errors.append(err)
                messages = self._append_correction(
                    messages, last_raw,
                    f"Your response could not be parsed as JSON: {exc}. "
                    f"Return the tool call with valid JSON only."
                )

            except ValidationError as exc:
                err = f"Attempt {attempt}: schema validation — {self._format_pydantic_errors(exc)}"
                attempt_errors.append(err)
                messages = self._append_correction(
                    messages, last_raw,
                    f"The JSON you returned failed schema validation. Fix these specific fields:\n"
                    + self._format_pydantic_errors(exc)
                )

            except ValueError as exc:
                err = f"Attempt {attempt}: IR validation — {exc}"
                attempt_errors.append(err)
                messages = self._append_correction(
                    messages, last_raw,
                    f"The circuit design has logical errors that must be fixed:\n{exc}"
                )

        raise CircuitGenerationError(attempt_errors)

    def _build_user_prompt(self, spec: DesignSpec) -> str:
        lines = [
            f"Design a circuit for: {spec.intent}",
            f"Application class: {spec.application_class}",
        ]
        if spec.target_mcu:
            lines.append(f"Target MCU: {spec.target_mcu}")
        if spec.constraints:
            lines.append(f"Constraints: {json.dumps(spec.constraints)}")
        if spec.use_rs485:
            lines.append("Include RS-485 Modbus RTU interface with full termination and bias network.")
        if spec.has_relay:
            lines.append("Include relay output for switching loads.")
        return "\n".join(lines)

    def _append_correction(
        self,
        messages: list[dict],
        last_raw: Optional[dict],
        correction: str,
    ) -> list[dict]:
        """Add assistant turn (with last output) + user correction to messages list."""
        updated = list(messages)
        if last_raw is not None:
            updated.append({
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "corr", "name": "generate_circuit_ir", "input": last_raw}],
            })
            updated.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "corr", "content": correction}],
            })
        else:
            updated.append({
                "role": "user",
                "content": correction,
            })
        return updated

    @staticmethod
    def _format_pydantic_errors(exc: ValidationError) -> str:
        lines = []
        for err in exc.errors():
            loc = " → ".join(str(p) for p in err["loc"])
            lines.append(f"  • {loc}: {err['msg']}")
        return "\n".join(lines)
