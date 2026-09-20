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


#: What "consequential rather than descriptive" is scored on, per
#: PRODUCT_MASTER.md Part 12. Owned here because it is a property of the
#: explanation layer, not of any one implementation of it — both
#: `ai/derived_explainer.py` and `tests/test_explainer.py` read it from here.
#: It previously existed as two identical copies, which is the stale-copy
#: failure this project has been bitten by repeatedly.
CONSEQUENTIAL_MARKERS = [
    "if ", "would ", "without", "exceed", "fail", "instead of",
    "otherwise", "breaks", "risk",
]

#: How many distinct markers an explanation must hit to count as consequential.
CONSEQUENTIAL_MARKER_BAR = 3


def consequential_markers(text: str) -> list[str]:
    """Which markers `text` hits. The scorer both explainers are measured by."""
    lowered = text.lower()
    return [m for m in CONSEQUENTIAL_MARKERS if m in lowered]


def _first_text(response) -> str:
    """
    The first text block, not blindly block zero.

    A reasoning-capable model answers a free-text request with a `ThinkingBlock`
    at index 0 and the prose after it, so `response.content[0].text` raises
    `AttributeError: 'ThinkingBlock' object has no attribute 'text'`. Observed
    2026-09-20 against the configured `AI_MODEL` while running the Task 0.5
    derivability experiment — every explanation call was failing.

    The tool_use modules are not affected and deliberately left alone: forced
    `tool_choice` suppresses thinking blocks, so `content[0].input` is correct
    there. Verified against the live API before narrowing this fix.
    """
    for block in response.content:
        text = getattr(block, "text", None)
        if text is not None:
            return text
    raise ValueError(
        "model returned no text block — content types were "
        f"{[getattr(b, 'type', type(b).__name__) for b in response.content]}"
    )


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
        return _first_text(response)

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
