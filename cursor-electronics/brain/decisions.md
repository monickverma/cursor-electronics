# Decisions — Circuit OS

> Append-only. Never delete. Format: decision → reason → alternatives → date.
> Answers: "why did we do it THIS way?"

---

## [2026-06-01] ngspice over LTspice as the simulator

**Decision:** ngspice is the only permitted simulation engine.

**Reason:**
- LTspice EULA explicitly prohibits commercial redistribution and server-side automation
- ngspice is BSD-licensed — fully legal in SaaS, scriptable via subprocess
- Industry-standard SPICE format; KiCad also ships ngspice
- Outputs columnar text format parseable without extra libraries

**Alternatives rejected:**
- LTspice — legally blocked for SaaS use without a commercial agreement
- Qucs-S — less mature, smaller ecosystem
- PySpice — adds abstraction layer, harder to debug convergence

---

## [2026-06-01] IR schema as the canonical JSON contract

**Decision:** All LLM output is JSON validated against `backend/core/ir_schema.py`.
No LLM output touches ngspice, KiCad, or .ino directly.

**Reason:**
- LLMs hallucinate component values outside standard series (e.g. 1.7kΩ resistor)
- LLMs write SPICE syntax ngspice cannot parse
- Pydantic v2 strict validation rejects bad output before reaching simulation
- Retry loop re-prompts with the specific failing field, not a generic error

**Alternatives rejected:**
- LLM → SPICE directly — unvalidatable, fails unpredictably in production
- Custom IR not based on SPICE concepts — would duplicate work, no industry tooling

---

## [2026-06-01] Jinja2 templates for firmware, never LLM-generated .ino

**Decision:** Arduino firmware is generated from Jinja2 templates in `backend/generators/firmware/`.

**Reason:**
- LLM-generated firmware hallucinates function names, wrong pin numbers, missing includes
- Jinja2 templates produce identical output for identical input — testable and deterministic
- Templates are version-controlled independently of the AI layer

**Alternatives rejected:**
- LLM writes .ino directly — fails reliability requirement for an engineering tool

---

## [2026-06-01] Static component_constraints.py over RAG for Phase 1

**Decision:** Component constraints are a Python dict, not a vector database.

**Reason:**
- Datasheet excerpts are 4,000+ tokens each; embedding 20 components adds ~$0.50–1.00 per call
- Python dict lookup = 0 tokens, 0 latency, 0 cost, 100% reliability
- Qdrant RAG is Phase 2 once template system is proven at scale

**Alternatives rejected:**
- Qdrant with datasheets in Phase 1 — costly, adds fragile network dependency
- Full datasheets in system prompt — exceeds context budget, $1/call extra

---

## [2026-06-01] Celery + Redis for all simulation runs

**Decision:** Simulation is submitted to Celery, never run inline in HTTP handlers.

**Reason:**
- ngspice runs take 2–30 seconds; `await subprocess` holds the HTTP connection open
- Client browsers, load balancers, mobile SDKs time out after ~10–30s
- Celery enables polling (job_id) and scales horizontally

**Alternatives rejected:**
- `await sim_runner.run()` inline — keeps HTTP connection open, causes client timeouts

---

## [2026-06-01] Claude tool_use mode only — never raw text

**Decision:** All AI modules use `tool_use` / function calling; `response.content[0].input` only.

**Reason:**
- `.input` is already a parsed Python dict — no `json.loads()` needed
- Eliminates markdown-fence stripping errors entirely
- Forces schema-compliant output at the API level, not post-hoc

**Alternatives rejected:**
- Raw text + regex to strip ```json fences — brittle on edge cases
- Asking model to "return valid JSON" in prose — still free text, still parses

---

## [2026-06-01] Patcher returns changed fields only — never full IR

**Decision:** `CircuitPatcher.patch()` returns only the changed fields.

**Reason:**
- Full IR regeneration overwrites user customizations
- Surgical patches preserve design history and make `patch_history` meaningful
- Reduces token count per patch call by 60–80%

**Alternatives rejected:**
- Regenerate full IR on each edit — destroys user changes, expensive per call

---

## [2026-06-01] 5 templates only for Phase 1

**Decision:** Phase 1 supports exactly 5 circuit templates. Free-form is Phase 2.

**Reason:**
- 5 templates that work 100% of the time beat 20 that work 60%
- Hobbyist volume builds the circuit pattern database and training flywheel faster
- "Breadth before depth = nothing works reliably"

---

## [2026-06-01] KiCad net labels only — no wire routing in Phase 1

**Decision:** `backend/generators/schematic/kicad.py` emits net labels, not wires.

**Reason:**
- Wire routing requires knowing exact pin coordinates from KiCad symbol library per component
- Net labels connect by name — generatable without any symbol library lookup
- Phase 3 adds wire routing after the PCB layout module is built

---

## [2026-06-01] MCU modeled as 100Ω resistor in SPICE

**Decision:** ATmega328P (and all MCUs) = `R_MCU VCC_5V GND 100` in SPICE.

**Reason:**
- Two voltage sources on the same node → singular matrix → ngspice refuses to simulate
- MCU draws current, does not supply voltage
- 100Ω ≈ 50mA at 5V, close to ATmega328P typical quiescent draw

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
