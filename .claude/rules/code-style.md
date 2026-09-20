# Code Style — Circuit OS

## IR Schema: Canonical Field Names (Never Rename)

`backend/core/ir_schema.py` is the contract between every layer. All generators, all AI modules, all tests read from it.

```
connection.component_id   ← correct
connection.node_id        ← correct

connection.component      ← WRONG — do not use
connection.node           ← WRONG — do not use
```

Do not rename fields. Do not add fields without updating every downstream generator (SPICE, KiCad, firmware, BOM).

---

## AI Layer Pattern: tool_use Only

Every AI module (intent_parser, intent_producer, patcher) uses the same pattern. Never deviate from it.

```python
# CORRECT — tool_use forces structured output, response is already a parsed dict
response = self.client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4000,
    system=SYSTEM_PROMPT,
    tools=[schema_tool],
    tool_choice={"type": "tool", "name": tool_name},
    messages=[{"role": "user", "content": user_content}]
)
tool_result = response.content[0].input  # already a dict — no json.loads() needed

# WRONG — never take the raw text output to any downstream compiler
response = client.messages.create(...)
spice_netlist = response.content[0].text  # NO. This is not how Circuit OS works.
```

`response.content[0].input` is already a parsed Python dict. No `json.loads()`. No regex to strip markdown fences. This eliminates the entire class of JSON parse errors.

---

## Retry: Schema Never, Semantics Once — and a Retry May Not Rewrite the Request

> **Amended 2026-09-21.** `circuit_reasoner.py` and its 3-attempt loop are
> **deleted** — it was the path by which the LLM wrote `CircuitIR`, which Stage 1
> Task 1.5 removes. The rules below govern `ai/intent_producer.py`, which writes
> `IntentIR` instead. Amendment X5 of `PHASE_2_PLAN_v2.md`; rationale in
> `.claude/shared-memory/brain/decisions.md` [2026-09-21].

| Failure type | Response |
|---|---|
| `anthropic.APIError` | Do NOT retry. Raise immediately → 503 |
| **Schema failure** (tool input does not fit the schema) | Do NOT retry. Raise `IntentProductionError` **carrying the raw tool input** → 422 |
| **Semantic rejection** (`envelope()` refused, with a reason) | Retry **once**, subject to the guard below |

**Why schema failures no longer retry.** Forced `tool_choice` returns a parsed
dict conforming to the tool schema, so re-prompting for a schema failure
re-prompts for something that should not happen — and hides how often it does.
That "should not happen" is an empirical claim about frontier models, not a
structural one, so the error carries the raw input: if the assumption breaks it
must announce itself.

**The guard: a retry may add, never rewrite.**

```python
# CORRECT — the retry supplies a value it failed to record the first time
before = {"targets.cutoff_hz": 2_000_000}
after  = {"targets.cutoff_hz": 2_000_000, "targets.tolerance_pct": 5}

# WRONG — the retry altered what the user asked for so it would fit
before = {"targets.cutoff_hz": 2_000_000}
after  = {"targets.cutoff_hz": 1_000}      # refused: IntentProductionError
```

Told "no generator accepted this", the fix most available to a model is to
**change the requirement until it fits**, handing back a design the user never
asked for. That defeats the one analytic claim the architecture rests on — that
the requirement is materialized before the design. A request genuinely outside
the catalogue is **refused, not negotiated**.

---

## Pydantic v2: Attribute Access Rules

```python
# WRONG — hasattr always returns True for declared Optional fields
if hasattr(component, 'sensor_type'):
    ...

# CORRECT — check the value, not the attribute existence
if component.sensor_type is not None:
    ...

# Also acceptable for defensive code
sensor = getattr(component, 'sensor_type', None)
```

`Component.sensor_type` is declared as `Optional[str] = None`. Pydantic v2 strict models do not support dynamic attribute assignment. `hasattr` tells you whether the field is declared, not whether it has a meaningful value.

---

## Component Constraints: Python Dict, Not Token Budget

```python
# CORRECT — zero tokens, zero latency, zero cost
from data.component_constraints import format_for_prompt
constraint_text = format_for_prompt(["DHT22", "MAX485ECSA"])  # ~300 tokens injected

# WRONG — embedding full datasheets in system prompt
system_prompt = SYSTEM_PROMPT + all_datasheets_text  # 40,000+ tokens, $1/call extra
```

`component_constraints.py` is a Python dict. Look up only the components actually needed for the current design. Inject ~200–500 tokens of constraints, not 40,000.

Phase 2: Qdrant RAG with full datasheet excerpts. Phase 1: static dict only.

---

## Patcher Invariant

`CircuitPatcher.patch()` **never** returns a full IR. It returns only changed fields.

```python
# CORRECT — patch returns only what changed
{"changes": [{"component_id": "R1", "field": "value", "new_value": "4.7k"}]}

# WRONG — patcher re-generating the entire design
{"circuit_id": "...", "components": [...all components...], "nodes": [...]}
```

Returning a full IR from the patcher overwrites user customizations and makes `patch_history` meaningless. The patcher's job is surgical: change exactly what was requested, preserve everything else.

---

## Key Design Decisions

**Why Jinja2 for firmware instead of LLM generation?**
LLM-generated firmware hallucinates function names, wrong pin numbers, missing includes. Jinja2 templates produce identical output for identical input. Deterministic, testable, correct.

**Why 5 templates instead of free-form?**
Five templates that work 100% of the time beat twenty templates that work 60% of the time. Breadth expands in Phase 2 once the template system is proven.

**Why net labels in KiCad instead of wire routing?**
Wire routing requires knowing exact pin coordinates from the KiCad symbol library for every component. Net labels connect by name — deterministically generatable without a symbol library lookup. Phase 3 adds wire routing.

**Why static `component_constraints.py` instead of Qdrant in Phase 1?**
Datasheet excerpts are 4,000+ tokens each. Embedding 20 components' datasheets adds $0.50–1.00 per generation. A Python dict lookup is 0 tokens, 0 latency, 0 cost, 100% reliable.

---

## Common Mistakes

**Adding a new circuit type before all 5 templates pass tests.**
Breadth before depth = nothing works reliably. Finish the template system first.

**Calling Digikey/LCSC API in Phase 1.**
Static pricing only. Live API integration is Phase 2. Adding it early creates an authenticated, rate-limited, cacheable dependency that slows development.

**Writing descriptive instead of consequential explanations.**
Weak: "I chose DHT22 because it measures temperature."
Strong: "If you change R3 from 10kΩ to 4.7kΩ, LED current hits 42mA, exceeding the ATmega328P-PU's 40mA GPIO sink limit. Simulation confirms."
The explainer system prompt must enforce consequential language. That is the product differentiator.

**Using `await` and expecting the HTTP connection to not time out.**
`await sim_runner.run()` releases the event loop but keeps the HTTP connection open. A 30-second simulation will still cause client-side timeouts. Use Celery — submit a job, return a job_id, poll for results.
