"""
Patch engine — takes an existing CircuitIR + user command, returns only the changed
fields as a compact patch list.

INVARIANT: CircuitPatcher.patch() NEVER returns a full IR.
           It returns only changed fields so patch_history stays meaningful and
           user customisations from earlier patches are not overwritten.

Patch format returned by the tool:
  {
    "changes": [
      {"component_id": "R1", "field": "value", "new_value": "4.7k"},
      {"component_id": "U2", "field": "part_number", "new_value": "DHT11"}
    ]
  }
"""

from __future__ import annotations

from typing import Any, List

from ai.client import ai_model, make_client
from core.ir_schema import CircuitIR


SYSTEM_PROMPT = """\
You are a circuit design patcher. You receive an existing circuit design (summarised
as component list + IDs) and a user change request. You return ONLY the fields that
must change — never the full design.

CRITICAL RULES:
1. Return ONLY a patch via apply_circuit_patch. Never re-generate the full IR.
2. component_id must exactly match an existing component ID shown in the design.
3. field must be a valid Component field name (part_number, value, manufacturer,
   package, supply_voltage_max, confidence, justification, sensor_type, etc.).
4. If the request requires adding new components, set changes=[] and explain in
   note_to_user. Do not invent component IDs that don't exist.
5. Keep changes minimal — only the fields the user explicitly asked to change.
"""

_PATCH_TOOL = {
    "name": "apply_circuit_patch",
    "description": "Return the minimal set of component field changes for the user request.",
    "input_schema": {
        "type": "object",
        "required": ["changes"],
        "properties": {
            "changes": {
                "type": "array",
                "description": "List of field-level changes. Empty if no patch is possible.",
                "items": {
                    "type": "object",
                    "required": ["component_id", "field", "new_value"],
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "Must match an existing component ID",
                        },
                        "field": {
                            "type": "string",
                            "description": "Component model field name to update",
                        },
                        "new_value": {
                            "description": "New value for the field (any JSON type)",
                        },
                    },
                },
            },
            "note_to_user": {
                "type": "string",
                "description": "Explanation when changes list is empty or incomplete",
            },
        },
    },
}


class PatchResult:
    """Parsed output from CircuitPatcher — a list of field changes."""

    def __init__(self, raw: dict):
        self.changes: List[dict[str, Any]] = raw.get("changes", [])
        self.note_to_user: str = raw.get("note_to_user", "")

    def apply_to(self, ir: CircuitIR) -> CircuitIR:
        """Apply this patch to an IR and return a new IR with version incremented."""
        updated = list(ir.components)
        index = {c.id: i for i, c in enumerate(updated)}

        for change in self.changes:
            cid = change.get("component_id", "")
            field = change.get("field", "")
            new_value = change.get("new_value")
            if cid not in index or not field:
                continue
            updated[index[cid]] = updated[index[cid]].model_copy(update={field: new_value})

        return ir.model_copy(update={"components": updated, "version": ir.version + 1})


class CircuitPatcher:
    def __init__(self):
        self.client = make_client()

    def patch(self, ir: CircuitIR, command: str) -> PatchResult:
        response = self.client.messages.create(
            model=ai_model(),
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[_PATCH_TOOL],
            tool_choice={"type": "tool", "name": "apply_circuit_patch"},
            messages=[{
                "role": "user",
                "content": f"CURRENT DESIGN:\n{self._summarize(ir)}\n\nCHANGE REQUEST: {command}",
            }],
        )
        return PatchResult(response.content[0].input)

    @staticmethod
    def _summarize(ir: CircuitIR) -> str:
        lines = [f"circuit_id: {ir.circuit_id}", f"intent: {ir.intent}", "", "components:"]
        for comp in ir.components:
            lines.append(
                f"  {comp.id}: {comp.part_number} ({comp.type})"
                + (f", value={comp.value}" if comp.value else "")
            )
        return "\n".join(lines)
