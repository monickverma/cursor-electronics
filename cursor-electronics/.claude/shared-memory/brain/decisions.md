# Decisions — Circuit OS

> Append-only. Never delete. Format: decision → reason → alternatives → date.
> Answers the question: "why did we do it THIS way?"

---

## [2025-09-20] LLM outputs JSON only — never SPICE/KiCad/.ino directly

**Decision:** All LLM output is validated JSON (CircuitIR). Deterministic compilers
translate IR to every downstream format. The LLM never writes a netlist, schematic,
or firmware file directly.

**Reason:** LLMs hallucinate component values that don't exist in standard series,
write SPICE syntax ngspice cannot parse, and generate firmware with wrong pin numbers.
Pydantic v2 strict validation at the IR boundary catches all of this before it reaches
any compiler. The retry loop re-prompts with the specific failing field path — not a
generic "invalid JSON" message — so Claude can fix the exact problem in the next attempt.

**Alternatives rejected:**
- LLM → SPICE directly — passes through unvalidated, fails unpredictably in production
- Custom IR not based on SPICE concepts — more work, no industry tooling benefit

---

## [2025-09-20] ngspice over LTspice

**Decision:** ngspice is the only permitted simulation engine.

**Reason:** LTspice's EULA explicitly prohibits commercial redistribution and
server-side automation. Cannot legally call LTspice in a SaaS product without
a separate commercial agreement. ngspice is BSD-licensed — fully legal, scriptable
via subprocess, and already ships inside KiCad.

**Alternatives rejected:**
- LTspice — legally blocked for SaaS use
- Qucs-S — less mature, smaller ecosystem, fewer tutorials to reference
- PySpice — adds an abstraction layer that makes convergence debugging harder

---

## [2025-09-20] Jinja2 for firmware — never LLM-generated .ino

**Decision:** Arduino firmware is generated from Jinja2 templates
(`backend/generators/firmware/templates/`). The LLM never writes `.ino` code.

**Reason:** LLM-generated firmware hallucinates function names (`Wire.readByte()`
doesn't exist), wrong pin numbers, missing `#include` statements. Jinja2 templates
produce identical output for identical input — deterministic, testable, diffable.
Templates are versioned independently of the AI layer and can be unit-tested in
isolation.

**Alternatives rejected:**
- LLM generates .ino directly — fails the reliability requirement for an engineering tool
- Code AST builder — more complexity, same determinism benefit as Jinja2

---

## [2025-09-20] Celery + Redis for all simulation — never inline in HTTP handler

**Decision:** Every simulation job is submitted to Celery and returns a `job_id`
immediately. The client polls `GET /design/{id}/simulation/{job_id}`.

**Reason:** ngspice runs take 2–30 seconds. `await subprocess_run()` in FastAPI
releases the Python event loop but keeps the HTTP connection open. Client browsers,
load balancers, and mobile SDKs time out after 10–30s. Celery scales horizontally
across workers and persists job state across server restarts.

**Alternatives rejected:**
- `await` inline — keeps HTTP connection open, guaranteed client timeouts at scale
- Thread pool in FastAPI — doesn't scale across processes, no job state persistence

---

## [2025-09-20] Claude tool_use mode only — response.content[0].input, never .text

**Decision:** All three AI modules (IntentParser, CircuitReasoner, CircuitPatcher)
use `tool_use` with `tool_choice={"type": "tool", "name": ...}`. Output is read
from `response.content[0].input` — already a parsed Python dict.

**Reason:** `.input` is already a Python dict — no `json.loads()`, no markdown-fence
stripping, no regex. Eliminates the entire class of JSON parse errors that come from
the model wrapping output in ````json ... ```` fences or adding explanatory prose
before the JSON block.

**Alternatives rejected:**
- Raw text + regex to strip fences — brittle on every edge case
- Asking the model to "return valid JSON" as a prompt instruction — still free text

---

## [2025-09-20] Patcher returns changed fields only — never full IR

**Decision:** `CircuitPatcher.patch()` returns only the changed fields
(`{"changes": [{"component_id": "R1", "field": "value", "new_value": "4.7k"}]}`).
It never returns a full new IR.

**Reason:** Full IR regeneration overwrites user customizations made between the
initial generation and the patch. The `patch_history` list would be meaningless if
every patch is a full replacement. Surgical patches preserve the exact design the
user has been working with.

**Alternatives rejected:**
- Re-generate full IR on each patch — destroys user edits, 2–3x more tokens per call

---

## [2025-09-20] Static component_constraints.py for Phase 1 — no RAG

**Decision:** Component electrical constraints are a Python dict
(`backend/data/component_constraints.py`). No vector database in Phase 1.

**Reason:** Datasheet excerpts are 4,000+ tokens each. Embedding 20 components in
every system prompt adds $0.50–1.00 per generation call and pushes context budgets
on complex circuits. A Python dict lookup costs 0 tokens, 0 latency, 0 dollars,
and is 100% reliable with no network dependency. Qdrant RAG is Phase 2 once the
template system proves reliable.

**Alternatives rejected:**
- Qdrant with full datasheets in Phase 1 — expensive and fragile for an unproven system

---

## [2025-09-20] KiCad net labels only — no wire routing in Phase 1

**Decision:** `KiCadSchematicGen` emits net labels that connect by name. No wire
routing, no pin coordinate lookup.

**Reason:** Wire routing requires knowing exact pin coordinates from the KiCad symbol
library for every component. That lookup is not implemented in Phase 1. Net labels
connect nodes by matching label text — generatable without any symbol library.

**Phase plan:** Wire routing added in Phase 3 alongside the PCB layout module.

---

## [2025-09-20] MCU modeled as 100Ω resistor in SPICE

**Decision:** ATmega328P and all MCUs = `R_MCU_U1 VCC_5V GND 100` in generated SPICE.

**Reason:** If both the power supply and the MCU are voltage sources on the same node,
ngspice produces a singular matrix and refuses to simulate. The MCU is a current
consumer, not a voltage supplier. 100Ω ≈ 50mA at 5V, which is close to ATmega328P
typical operating current.

**Alternatives rejected:**
- `VMCU VCC_5V GND DC 5` — singular matrix error, zero output
- Ignoring MCU entirely — leaves floating nodes, also a singular matrix

---

## [2025-09-20] bcrypt directly — not passlib

**Decision:** Password hashing uses `import bcrypt` directly.

**Reason:** passlib 1.7.4 is incompatible with bcrypt 4.x — it calls an internal
`._private_rounds()` method that no longer exists in newer bcrypt. Rather than pin
passlib to an old version or wait for a fix, bcrypt is called directly.

---

## [2026-06-03] Brain scaffold in .claude/shared-memory/ — not project root

**Decision:** All Claude session context files (brain/, plan/, tools/) live in
`.claude/shared-memory/` rather than the project root.

**Reason:** The project root is already crowded with real project files. Co-locating
Claude tooling with other `.claude/` config (CLAUDE.md, rules/, settings.json) makes
the AI layer self-contained and clearly separated from production code.

---

## TEMPLATE — adding a new decision

```
## [YYYY-MM-DD] Brief title

**Decision:** One sentence stating what was chosen.

**Reason:**
- Bullet points — include the forcing constraint, not just the preference

**Alternatives rejected:**
- Name — specific reason it was rejected

**Known tradeoffs:** (optional)
```
