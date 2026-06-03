# Decisions — Circuit OS

> Append-only. Never delete. Format: decision → reason → alternatives → date.
> Answers: "why did we do it THIS way?"

---

## [2026-06-01] ngspice over LTspice as the simulator

**Decision:** ngspice is the only permitted simulation engine.

**Reason:**
- LTspice EULA explicitly prohibits commercial redistribution and server-side automation
- ngspice is BSD-licensed — fully legal in SaaS, scriptable via subprocess
- Industry-standard SPICE format; KiCad also ships with ngspice
- Outputs columnar text format easily parsed without external libraries

**Alternatives rejected:**
- LTspice — legally blocked for SaaS use
- Qucs-S — less mature, smaller ecosystem
- PySpice — adds abstraction layer, harder to debug convergence

---

## [2026-06-01] IR schema as the canonical JSON contract

**Decision:** All LLM output is JSON validated against `backend/core/ir_schema.py`.
No LLM output touches ngspice, KiCad, or .ino directly.

**Reason:**
- LLMs hallucinate component values that don't exist in standard series
- LLMs write SPICE syntax ngspice cannot parse
- Schema validation rejects bad output before it reaches simulation
- Retry loop re-prompts with the specific field that failed — not a generic error
- This single rule separates a reliable tool from an AI toy

**Alternatives rejected:**
- Free-text LLM → SPICE directly — cannot be validated, fails unpredictably
- Custom JSON format — IR schema IS the custom format, standardized once

---

## [2026-06-01] Jinja2 templates for firmware, never LLM-generated .ino

**Decision:** Arduino firmware uses Jinja2 templates in `backend/generators/firmware/`.

**Reason:**
- LLM-generated firmware hallucinates function names, wrong pin numbers, missing includes
- Jinja2 templates produce identical output for identical input — deterministic and testable
- Templates can be version-controlled and unit-tested independently of the AI layer

**Alternatives rejected:**
- LLM writes .ino directly — fails reliability requirement
- Code DSL with transpiler — unnecessary complexity for Phase 1 scope

---

## [2026-06-01] Static component_constraints.py over RAG for Phase 1

**Decision:** Component constraints are a Python dict, not a vector database.

**Reason:**
- Datasheet excerpts are 4,000+ tokens each; embedding 20 components adds $0.50–1.00/call
- A Python dict lookup costs 0 tokens, 0 latency, 0 dollars, 100% reliability
- Qdrant RAG is Phase 2 once template system is proven

**Alternatives rejected:**
- Qdrant with datasheet excerpts in Phase 1 — expensive, fragile, slows development
- Full datasheets in system prompt — exceeds context budget, $1/call extra

---

## [2026-06-01] Celery + Redis for all simulation runs

**Decision:** Simulation jobs are submitted to Celery, never run inline in HTTP handlers.

**Reason:**
- ngspice runs take 2–30 seconds; `await` releases the event loop but keeps the
  HTTP connection open — client browsers, load balancers, and mobile SDKs time out
- Celery allows polling (job_id pattern) and scales horizontally across workers

**Alternatives rejected:**
- `await subprocess_run()` inline — keeps HTTP connection open 30s, causes timeouts
- Thread pool in FastAPI — does not scale across processes, no job state persistence

---

## [2026-06-01] Claude tool_use mode only, never raw text output

**Decision:** All three AI modules use `tool_use` / function calling. Never raw `.text`.

**Reason:**
- `response.content[0].input` is already a parsed Python dict — no json.loads() needed
- Eliminates the entire class of JSON parse errors from markdown-fenced responses
- Forces schema-compliant output at the API level, not post-hoc

**Alternatives rejected:**
- Raw text + regex to strip ```json fences — brittle, fails on edge cases
- Asking LLM to "return valid JSON" in system prompt — still produces free text

---

## [2026-06-01] Patcher returns changed fields only, never full IR

**Decision:** `CircuitPatcher.patch()` returns only the changed fields, not the full IR.

**Reason:**
- Returning a full IR from the patcher overwrites user customizations
- Surgical patches preserve design history and make `patch_history` meaningful
- Reduces token count per patch call by 60–80%

**Alternatives rejected:**
- Full IR regeneration on each patch — destroys user changes, expensive

---

## [2026-06-01] 5 templates only for Phase 1 (no free-form generation)

**Decision:** Phase 1 supports exactly 5 circuit templates. Free-form is Phase 2.

**Reason:**
- 5 templates that work 100% of the time beat 20 templates that work 60% of the time
- Volume of use cases builds test coverage and the circuit pattern database
- Breadth before depth = nothing works reliably

**Templates:** TPL_001 (DHT22), TPL_002 (MAX485), TPL_003 (LED), TPL_004 (RC filter), TPL_005 (voltage divider)

---

## [2026-06-01] KiCad net labels, not wire routing, for Phase 1

**Decision:** `backend/generators/schematic/kicad.py` uses net labels only.

**Reason:**
- Wire routing requires knowing exact pin coordinates from KiCad symbol library for
  every component — that lookup is not available in Phase 1
- Net labels connect by name — deterministically generatable without library lookup
- Phase 3 adds wire routing and auto-layout via KiCad freerouting

---

## [2026-06-01] MCU modeled as 100Ω resistor in SPICE

**Decision:** ATmega328P and all MCUs are modeled as `R_MCU VCC_5V GND 100` in SPICE.

**Reason:**
- Two voltage sources on the same node (power supply + MCU voltage source) creates a
  singular matrix — ngspice refuses to simulate
- MCU draws current, it does not supply voltage
- 100Ω gives 50mA at 5V — close to ATmega328P typical quiescent draw

**Alternatives rejected:**
- `VMCU VCC_5V GND DC 5` — singular matrix, ngspice error
- Ignoring the MCU — leaves floating nodes, also a singular matrix

---

## [2026-06-03] pytest with test naming convention for progress_gen.py

**Decision:** Every public function `foo()` in backend/ should have a matching
`test_foo()` in tests/, so `progress_gen.py` can map them automatically.

**Reason:**
- Lets `progress.yaml` show per-function verified/broken/stub/untested status
- Forces coverage discipline without additional tooling

---

## TEMPLATE — How to add a new decision

```
## [YYYY-MM-DD] Brief title

**Decision:** One sentence.

**Reason:**
- bullet points

**Alternatives rejected:**
- Name — why not

**Known issues / tradeoffs:** (optional)
```
