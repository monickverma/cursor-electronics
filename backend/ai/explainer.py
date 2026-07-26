"""
Explanation engine — takes a validated CircuitIR plus optional simulation/validation
results and returns a plain English design report.

The system prompt enforces CONSEQUENTIAL explanation:
  "if you change R3 from 10kΩ to 4.7kΩ, LED current hits 42mA which exceeds
   the ATmega328P-PU's 40mA GPIO sink limit — simulation confirms."

Descriptive explanation ("I chose DHT22 because it measures temperature") is rejected.
"""

from __future__ import annotations

from ai.client import ai_model, make_client

from core.config import settings
from core.ir_schema import CircuitIR
from core.ir_validator import IRValidationResult
from validation.rule_engine import HardwareRuleEngine

SYSTEM_PROMPT = """\
You are a hardware design explainer. Your job is to produce a plain English report
about a generated circuit design that an engineer can read without any additional
briefing.

CRITICAL RULE — Consequential language only:
Every component explanation must answer "what would break if this were wrong?"
  WRONG: "R1 is a 10kΩ pull-up resistor for the DHT22 DATA pin."
  RIGHT: "R1 (10kΩ) pulls the DHT22 DATA line high between transmissions.
          Without it, the open-drain output never reaches logic HIGH and the MCU
          reads only timeout errors. A value below 3kΩ would exceed the DHT22's
          maximum sink current of 5mA at 5V supply."

Structure:
1. One-sentence circuit summary.
2. Component table: ID | Part | Why chosen | What breaks if removed/wrong.
3. Critical connections: explain each non-trivial net.
4. Risks and verification steps.
5. If simulation results are provided: reference the actual numbers.

Write for an engineer who knows electronics but has NOT seen this design.
They must understand every component choice without asking a follow-up question.
"""


class ExplanationEngine:
    def __init__(self):
        self.client = make_client()

    def explain(
        self,
        ir: CircuitIR,
        validation_result: IRValidationResult | None = None,
        simulation_results: dict | None = None,
    ) -> str:
        user_content = self._build_prompt(ir, validation_result, simulation_results)
        response = self.client.messages.create(
            model=ai_model(),
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text

    def _build_prompt(
        self,
        ir: CircuitIR,
        validation_result: IRValidationResult | None,
        simulation_results: dict | None,
    ) -> str:
        parts = [
            f"CIRCUIT INTENT: {ir.intent}",
            f"APPLICATION CLASS: {ir.application_class}",
            f"TARGET MCU: {ir.target_mcu or 'unspecified'}",
            "",
            "COMPONENTS:",
        ]
        for comp in ir.components:
            parts.append(
                f"  {comp.id}: {comp.part_number} ({comp.type}) "
                f"— confidence {comp.confidence:.0%}"
                f"{' — value: ' + comp.value if comp.value else ''}"
            )
            parts.append(f"    Justification: {comp.justification}")

        parts += ["", "NODES:"]
        for node in ir.nodes:
            parts.append(
                f"  {node.id}: {node.type}"
                + (f" @ {node.voltage_nominal}V" if node.voltage_nominal is not None else "")
            )

        parts += ["", "CONNECTIONS:"]
        for conn in ir.connections:
            parts.append(f"  {conn.component_id}.{conn.pin} → {conn.node_id} ({conn.direction})")

        if validation_result:
            parts += ["", "VALIDATION RESULT:"]
            if validation_result.is_valid:
                parts.append("  PASS — all rules satisfied")
            else:
                parts.append("  FAIL")
                for err in validation_result.errors:
                    parts.append(f"    ERROR [{err.field_path}]: {err.message}")
            for warn in validation_result.warnings:
                parts.append(f"    WARN [{warn.field_path}]: {warn.message}")

        if simulation_results:
            parts += ["", "SIMULATION RESULTS:"]
            for k, v in simulation_results.items():
                parts.append(f"  {k}: {v}")

        return "\n".join(parts)
