# Circuit OS — project dossier (full)

Built 2026-09-24 for a Jev consultation. Everything below is taken from the Circuit OS repository snapshot (branch
phase2-stage0 at commit e803a99), the owner's handoff of 2026-09-25 (which describes one later commit, 94b61c1, and
uncommitted Stage 6 / D7 work), the earlier research report on Jev, and the first live Jev results. Each section has a
stable ID in square brackets and names its sources. Text is verbatim where marked; credentials and personal contact
details are removed. Where the dossier does not state something, it is not known here.

Sections: [S01] What Circuit OS is; [S02] Rules nothing may break; [S03] Process rules, trust hierarchy, one owner per fact; [S04] Environment, stack and history; [S05] Architecture and data flow; [S06] Module map (selected backend modules); [S07] The five generators (the entire catalogue); [S08] IntentIR, patches and retries (X2, X4, X5); [S09] Claims, verdicts and grades G0–G7; [S10] The defeater register D1–D9; [S11] Proofs (Stage 4): properties proved from the netlist, signed, frozen; [S12] Multi-MCU firmware (Stage 5); [S13] Stage 6 (BOM + substitution) and D7 provenance — uncommitted work in progress; [S14] Phase 1 — the twelve criteria and what v0.1.0 does not certify; [S15] Phase 2 — stages, gates, and what each stage left not done; [S16] Phase 2 deliverables: the canonical list versus what was built; [S17] Phase 3 and later — the canonical roadmap; [S18] PCB and CAD strategy (PCB_STRATEGY.md), including §9 'How this could be wrong'; [S19] Competitive position and product claims; [S20] Open issues; [S21] Decisions the owner holds, and other open decisions (facts and options only); [S22] Reasoning on record — closing Phase 1 (brain/decisions.md, verbatim, trimmed); [S23] Reasoning on record — predict() as per-request truth; explanation derivability; [S24] Reasoning on record — the LLM -> CircuitIR path removed; [S25] Reasoning on record — X6 + X8, the defeater namespace, `kind` and the library floor; [S26] Reasoning on record — RC swamping and the LED bound (decided with TypeSafe); the unverified three; [S27] Criterion 12 review protocol and the D1 bench sheet; [S28] The earlier research report — headline and fifteen findings; [S29] The earlier research report — thirty-three proposed Jev uses; [S30] The first live Jev run (2026-09-25) on seven small decision states; [S31] Domain facts and formulas.

## [S01] What Circuit OS is
*Sources: HANDOFF §1; PRODUCT_MASTER.md Part 1; brain/vision.md*

Circuit OS is an "AI hardware compiler": plain English (or a form) → validated circuit design with SPICE netlist, KiCad schematic, firmware that has actually compiled, BOM, simulation, and a consequential plain-English explanation. Single engineer owner, no oscilloscope. Canonical spec PRODUCT_MASTER.md (5-phase roadmap). Precedence: PHASE_2_PLAN_v2.md > PRODUCT_MASTER.md > assurance docs. Differentiator: explanation layer and increasingly the assurance layer: every design carries graded claims, named doubts (defeaters) and proofs.

> A software platform that turns a plain English hardware description into a complete, validated, simulation-tested, manufacture-ready electronics design — including the circuit, the firmware, the bill of materials, and the safety analysis — before a single physical component is touched.

**The explanation layer is the product.** (PRODUCT_MASTER.md Part 12)

Any engineer can run ngspice. Any engineer can open KiCad.
What no tool in existence does is look at a circuit design and say:

> "I chose this component for this reason. This is what will fail if you change it.
>  This is what you need to check before ordering. Here is what I am not certain about and why."

That reasoning — applied to every component, every connection, every decision — is what
earns engineer trust. It is what turns a junior engineer into a productive one.
It is what an enterprise buyer points to when justifying the seat license.

## [S02] Rules nothing may break
*Sources: HANDOFF §2 (verbatim)*

- LLM never writes SPICE, KiCad, firmware, or CircuitIR. Since Stage 1 the LLM writes only IntentIR (the requirement). Deterministic generator writes CircuitIR. tests/test_llm_cannot_write_circuit_ir.py enforces via transitive AST scan.
- AI calls: tool_use forced tool_choice only; model from AI_MODEL env. Explainer free-text must find first text block.
- Retries (X5): API error → no retry (503). Schema failure → no retry, 422 with raw tool input. Semantic refusal → retry once, may add values but never change/drop what the user asked. Out-of-catalogue refused.
- Patches edit the requirement, never the circuit (X2/X4): RFC 6902 ops over IntentIR.requirements, re-derived through same gate. No retries; every LLM op must cite command words; no-op is not a version; 409 version_conflict.
- ngspice via Celery only; predict() closed form synchronous.
- MCU in SPICE = resistor (100Ω Uno, 41Ω ESP32-WROOM-32E, 132Ω STM32F411).
- Postgres persistence, CORS, JWT, slowapi limits. Static pricing; live pricing (X7) needs user approval. IR field names locked. Only generators/realize.py stamps circuit_id (uuid5(intent_id)), version, generator. Firmware shown only after PlatformIO compile.

## [S03] Process rules, trust hierarchy, one owner per fact
*Sources: HANDOFF §3; .claude/shared-memory/AGENTS.md*

Bootstrap: .claude/shared-memory/AGENTS.md → vision → architecture → plan/current_phase.md → progress.yaml → git log. Trust: tests > source > derived yaml/json > current_phase > brain/*.md > prose. Register new modules in tools/regen_state.py and tools/progress_gen.py. Decision entry in brain/decisions.md written BEFORE code (append-only). Every gate has a negative control / mutation check; unevaluable point = failure. Verification passes beyond green suite.
**TypeSafe (Jev) is installed and has been used to settle judgement calls (RC source swamping, D1/D2/D7). Protocol: >0.9 act, 0.5–0.9 act with care, <0.5 a person decides or take the most reversible option and say so. Key is a Windows user env var. TypeSafe never overrides tool_use/IR rules.**
Commits conventional; commit/push only when asked.

Trust hierarchy (AGENTS.md), highest first: test results + simulation outputs; source code via AST scan; progress.yaml + state.json (derived); plan/current_phase.md; brain/*.md files; agent-written prose summaries (lowest).

One owner per fact (AGENTS.md): every drift this project has suffered was a stale copy, not a missing check. Why a choice was made lives in brain/decisions.md (append-only; the entry is written before the code it governs). Every new module is registered in tools/regen_state.py (MODULES) and tools/progress_gen.py (PLANNED) in the same commit; an unregistered module does not show up as untested, it does not show up at all.

## [S04] Environment, stack and history
*Sources: HANDOFF §4 and §6 (verbatim)*

Windows 11, branch phase2-stage0 (never merged to master), tag v0.1.0 = Phase 1 close. Stack: FastAPI, Pydantic v2 strict, SQLAlchemy async + Postgres, Celery + Redis, ngspice, Jinja2 + PlatformIO 6.2.0, z3 5.1.0.0 / sympy 1.14 / mpmath, Next.js 14, Playwright. AI via OpenRouter (credits exhausted 2026-09-23); can run on vLLM/AMD ROCm. AGPL-3.0.

Phase 1 closed 2026-08-25 (v0.1.0, 11/12; criterion 11 met_by_substitute, criterion 12 deferred). PCB engine (custom A* router) experimental, flag-gated; Phase 3 will use freerouting.

## [S05] Architecture and data flow
*Sources: HANDOFF §5 (verbatim)*

Prompt → ai/intent_producer.py (1 tool_use) / Form → ai/form_producer.py (0 calls) → IntentIR (core/intent_ir.py; frozen; revision; sign-off) → generators/registry.py dispatch (each generator envelope() accepts or refuses by name; refusals collected = backlog) → generators/realize.py (generate + stamp, locality check, predict() delta, validation_coverage via validation/claims.py + proof/) → CircuitIR → netlist/spice.py (Celery ngspice → grader → waveforms), firmware/arduino.py → firmware/project.py (PlatformIO compile_gate), schematic/kicad.py, bom/compiler.py (+ bom/substitution.py Stage 6 WIP), ai/explainer.py (LLM) / ai/derived_explainer.py (0 calls).
Patch: IntentIR v(n) –RFC6902 (client ops or ai/intent_patcher.py)→ v(n+1) → same gate. Sign-off: user signs hash of property sentences; signed proofs become critical claims. Boards: arduino_uno | esp32_devkitc | blackpill_f411ce.
Five generators (entire catalogue; free-form out of scope): rc_lowpass 0.2.3 (TPL_004), voltage_divider 0.1.0 (TPL_005), led_indicator 0.2.0 (TPL_003), dht22_node 0.2.0 (TPL_001), rs485_node 0.2.0 (TPL_002). generators/protocol.py: name, version, envelope(), generate(), predict() (Interval bands), grid(), dependency_closure().
Assurance: claims (validation/claims.py) — every implemented rule runs on every design (X8); each claim has kind, verdict, grade from method (G0 proof-checked, G1 z3/monotone/closed-form/exact-graph, G2 sound enclosure, … G5 ngspice nominal, G6 sampled, G7 asserted/not assessed), scope (model, measures, assumes, figures), cited defeaters. grade_floor = worst critical claim. Proofs (proof/): sympy MNA + z3 over tolerance box; frozen refine; mutation gate. Pin rules (validation/pin_rules.py) G1. Grid gate (validation/envelope_grid.py): predict() vs ngspice within 2% at every grid point + seeded faults.
Defeaters (validation/defeaters.py): D1 validated vs maths/ngspice not hardware (open; bench sheet docs/BENCH_D1.md; evidence-record code not built). D2 MCU simplified model (open, derived per claim). D3 no external engineer read explanation (=criterion 12, deferred with trigger). D4 coverage may outrun one engineer (open). D5 LLM-written IntentIR untrusted (open per design; closed by user sign-off). D6 block proofs may not compose (n/a). D7 datasheet figures unverified (open; provenance records + verify tool built uncommitted). D8 π bracketed (eliminated). D9 generator bug makes predict() confidently wrong (open per generator until under M1 matrix).
Routes: /design/generate, /design/list, /design/{id}/patch, annotations, history, sign-off, firmware, simulation start/poll, auth, /pcb/compile (experimental flag).

## [S06] Module map (selected backend modules)
*Sources: brain/architecture.md Module Map (snapshot e803a99), trimmed*

ai/
  client.py make_client() — supports Anthropic direct + OpenRouter
  ai_model() — reads AI_MODEL env var
  intent_parser.py Prompt → DesignSpec via tool_use (forced, no raw text)
  intent_producer.py Prompt → IntentIR (X5 retry rules; removed the
  LLM → CircuitIR path entirely, 2026-09-21)
  form_producer.py Form → IntentIR — reference producer, 0 API calls
  intent_patcher.py IntentIR + command → RFC 6902 ops. Each op cites whole words
  of the command containing its value; never imports CircuitIR
  derived_explainer.py Structural explanation derived from the design, 0 API calls
  explainer.py IR → consequential plain English report

 validation/
  rule_engine.py HardwareRuleEngine — RS-485 termination, PWM pins
  claims.py Claim objects + validation_coverage; every rule on every
  design, graded G0–G7; grade_floor = worst critical claim
  defeaters.py The defeater register, D1–D9 (D8 eliminated by Stage 4)
  pin_rules.py Stage 5 — pin-mux, peripheral conflict, strapping pins (G1, D7)
  envelope_grid.py CI sweep: predict() vs ngspice over grid(board), seeded-fault arms
  grid_adapters.py Per-generator ngspice adapters; board_cases() for CI

 proof/ Stage 4 — properties proved from the design's own netlist
  brackets.py π, ln, expm1 as exact rational enclosures
  netlist.py SPICE text back into exact elements
  mna.py sympy nodal analysis: DC, transfer, Thevenin
  properties.py PropertySpec → Statement; English by template; hashes
  prover.py z3 over tolerance boxes; frozen refine loop; mutation gate

## [S07] The five generators (the entire catalogue)
*Sources: generators/*.py VERSION/FUNCTION constants; HANDOFF §5; brain/decisions.md 2026-09-21..24; current_phase.md*

| Generator | VERSION | Phase 1 template | FUNCTION | Boards | What it predicts and notable facts |
|---|---|---|---|---|---|
| rc_lowpass | 0.2.3 | TPL_004 | low_pass_filter | no MCU | Cutoff f_c over the tolerance box (π bracketed, G1); AC sweep in ngspice. 0.2.0 added pinned R1/C1 (`constraints.pinned`); 0.2.2 refuses a declared source that moves f_c past tolerance; 0.2.3 first swamps a large declared source with a larger R1 (smaller C) before refusing (decided with TypeSafe 2026-09-23). |
| voltage_divider | 0.1.0 | TPL_005 | voltage_divider | no MCU | vout_v (monotone corners), output impedance, bleed current, resistor dissipation. Its dissipation is decided exactly by its signed Stage 4 proof. |
| led_indicator | 0.2.0 | TPL_003 | led_indicator | arduino_uno, esp32_devkitc, blackpill_f411ce | led_current_ma from the Shockley diode and a Thevenin GPIO pin; GPIO current against the 20 mA recommended / 40 mA absolute limit; exact R1 dissipation since Task 4.5 (led_indicator 0.1.2, then 0.2.0 at Stage 5). |
| dht22_node | 0.2.0 | TPL_001 | temperature_humidity_sensor | arduino_uno, esp32_devkitc, blackpill_f411ce | Pull-up sink current with the line held low, idle data-line level, rail current (under mcu_as_100R, D2); pull-up vs cable rise time. DHT22 rise-time and sink limits are stated assumptions (Aosong publishes neither). |
| rs485_node | 0.2.0 | TPL_002 | modbus_rtu_master | arduino_uno, esp32_devkitc, blackpill_f411ce | Idle differential bus voltage v_ab against the ±200 mV receiver threshold (fail-safe bias), total bus load against the 54 Ω a driver is specified into. Terminator must be 1206: 5 V across 120 Ω is 208 mW, over three times an 0402's 62.5 mW. MAX3485 on a 3.3 V board. Thin M1 margin: a 5% terminator fault moves idle V_AB by 2.3% against the 2% gate (1.16× the gate on the Uno, 1.13× on 3.3 V boards). The Uno firmware drives the transceiver with SoftwareSerial on D10/D11. |

Generator protocol (generators/protocol.py): name, version, envelope() (accept or refuse by name), generate(), predict() (Interval bands), grid(), dependency_closure(). Registered generators must also implement claims() and may declare properties(intent). Free-form generation is out of scope: a request outside every envelope is refused, and the refusals are the backlog.

The MCU is represented in SPICE by a resistor sized from its run current: 100 Ω on the Uno (mcu_as_100R), 41 Ω for the ESP32-WROOM-32E, 132 Ω for the STM32F411. The DE/RE default pin of rs485_node is D2 on the Uno, GPIO4 on the ESP32-DevKitC and PB0 on the Black Pill.

## [S08] IntentIR, patches and retries (X2, X4, X5)
*Sources: backend/core/intent_ir.py docstring; brain/decisions.md [2026-09-21] X5 accepted; [2026-09-21] X2 + X4 accepted*

IntentIR — the user's requirement, materialized before the design exists.

PHASE_2_PLAN_v2.md §6 gives the schema; Stage 1 Task 1.1 builds it.

`ARCHITECTURE_ASSURANCE_CASE.md` §2 makes this the single analytic claim the
whole architecture rests on:

> **A1** *(analytic)*: Only Architecture C materializes the user's requirement
> as an inspectable artifact that exists before the design does.

SCHEMA_VERSION = "2.2.0" — 2.1.0 (Stage 2) added `revision`; 2.2.0 (Stage 4) added `SignOff.properties_hash`; older dumps still load.

From [2026-09-21] X5 accepted:
**Decision:** Amendment X5 of `PHASE_2_PLAN_v2.md` §2 is accepted. The retry
loop retires for **schema** failures and is retained for **semantic**
rejections. Implemented in `backend/ai/intent_producer.py`, not by editing the
old loop — Task 1.5 removed the module that held it.
*A semantic retry may add, never rewrite.* This guard is not in the plan and
the implementation is unsafe without it. Told "no generator accepted this",
the fix most available to a model is to **alter the requirement until it
fits** — quietly turning "I need 2 MHz" into "1 kHz" and returning a design
the user never asked for. That would defeat A1, the single analytic claim the
architecture rests on. So a retry may supply a value it failed to record the
first time, which is the correction the retry exists for, but may not change
or drop one it already recorded. `test_retry_that_rewrites_the_request_is_refused`
pins it.

From [2026-09-21] X2 + X4 accepted:
**Decision:** amendments X2 and X4 of `PHASE_2_PLAN_v2.md` §2 are accepted.
A patch is an RFC 6902 operation list over `IntentIR.requirements`; the design
is re-derived by the same `envelope() → generate() → predict()` gate a fresh
request goes through. `ai/patcher.py`, which let a model edit CircuitIR
component fields, is deleted. Stage 2.

3. **`circuit_id` is derived, not random: `uuid5(namespace, intent_id)`.**
   The Stage 2 determinism gate cannot pass while `CircuitIR.circuit_id` is a
   fresh `uuid4`. Derived from `intent_id` and **not** from the generator
   version, departing from the protocol docstring's wording: `circuit_id` is
   the design record's key and survives patches, and folding the generator
   version in would change a design's identity every time its generator is
   upgraded. The version is recorded instead in a new `CircuitIR.generator`
   field (`name@version`, v2 §6). Stamping happens in one place,
   `generators/realize.py`, so no generator works around it locally.

6. **Pinned parts are requirements: `constraints.pinned`.** The most common
   engineer edit, *"use the 4.7 k, it's what I have in the drawer"*, is not a
   target and must not become an annotation, because annotations are never an
   input to generation. A generator either honours every pin or refuses naming
   the pin. `rc_lowpass` supports R1 and C1 (0.1.0 → 0.2.0; unpinned output is
   unchanged).

7. **The LLM patcher's guard: every operation cites the command.** X5's "a
   retry may add, never rewrite" cannot govern a patch, which is a rewrite by
   definition. The guard is instead that each operation carries a verbatim
   quote from the user's command that asked for it, checked mechanically. An
   operation with no textual basis — the model also changing `supply_v` when
   the user only mentioned the cutoff — is refused. It does **not** catch a
   mis-transcribed value (2 kHz recorded as 20 kHz); the readable diff returned
   with every patch is the mitigation there, and the exposure is the same one
   the X5 defects entry names. **No semantic retry on patches**: a refused
   patch is reported and the user rephrases, because a retry is where
   negotiation would happen. A lexical check that the path name appears in the
   command was rejected — it is a heuristic presented as a guard.

9. **A refused patch keeps v(n).** Nothing is written until the new revision
   has passed `envelope()` and been realised. The user never loses a working
   design in exchange for a refusal.

14. **A stored design is never silently re-derived.** Its CircuitIR is the
    record. A patch regenerates with the installed generator, and if that
    differs from the one that built v(n), the response says so
    (`generator_changed`) alongside the `predict()` delta. The simulation job
    for each revision is stored with that revision's patch row, so results for
    v(n) cannot be read as results for v(n+1).

## [S09] Claims, verdicts and grades G0–G7
*Sources: backend/validation/claims.py (docstring and tables, verbatim)*

Every design carries a statement of which properties hold, over which
parameter ranges, under which model — or says plainly that it was not checked.
A claim has four independent fields and a verdict:

- `kind`   — analytic (true of the model by mathematics), empirical (measured),
             or projected (not yet an artifact)
- `grade`  — G0 (proof-checked) … G7 (asserted). **Derived from `method`**
             through one table, never typed per claim: a hand-assigned G1 is a G7.
- `scope`  — what it quantifies over, including the **model**
- `defeaters` — recorded doubts, by ID from `validation/defeaters.py`

**A claim with an open defeater is defeasible**, and its verdict says so:
`holds_defeasible`, never plain `holds`. The model validator enforces it.

**Nothing is averaged** (§5). `ValidationCoverage` reports three numbers side by
side — `coverage_le_g2`, `grade_floor`, `open_defeaters` — and never fuses them.

**What was not checked is printed** (§4, and amendment X8). Every
`ValidationRule` is accounted for on every design: run and graded; not
applicable, with the reason; covered by a generator's physics claim; declared
out of scope; or **not assessed**, as a visible, critical row graded G7. The
set is the catalogue minus what was actually checked — never the rules that
happened to run — so a design that checks less cannot look better verified.

```python
#: The one place a grade comes from. EVIDENCE_CLASSES §3.2.
METHOD_GRADE: Dict[str, str] = {
 "proof_checked": "G0",
 "z3_unsat": "G1",
 "monotone_corners": "G1", # exact when monotone in every argument
 "closed_form": "G1", # exact at the declared (nominal) scope
 "exact_graph_check": "G1", # exhaustive over the design as written
 "sound_enclosure": "G2",
 "certificate": "G3",
 "bounded_model_check": "G4",
 "ngspice_nominal": "G5",
 "sampled": "G6",
 "asserted": "G7",
}

#: v2 §3's declared out-of-scope list, printed on every design.
OUT_OF_SCOPE: Tuple[Tuple[str, str], ...] = (
 ("rf_gt_100mhz", "RF above 100 MHz"),
 ("emi_emc", "EMI / EMC"),
 ("thermal", "thermal behaviour, including operating temperature range"),
 ("manufacturing_yield", "manufacturing yield"),
 ("switching_converters", "switching converters"),
)

class Kind(str, Enum):
 ANALYTIC = "analytic"
 EMPIRICAL = "empirical"
 PROJECTED = "projected"
class Verdict(str, Enum): holds, holds_defeasible, fails, not_applicable, not_assessed, out_of_scope
```

## [S10] The defeater register D1–D9
*Sources: backend/validation/defeaters.py (REGISTER rendered verbatim); HANDOFF §5*

A defeater is a recorded doubt about a claim. Assurance 2.0's standard is
indefeasibility — no credible new information would change the claim — and a
claim that carries an open defeater is not "high confidence with a caveat", it
is **defeasible**, and is reported that way.

| ID | Doubt | Applies to | Status | Eliminated by | Trigger |
|---|---|---|---|---|---|
| D1 | predict() is validated against mathematics and ngspice, not hardware | every closed-form or simulated claim about circuit behaviour | open | a bench measurement agreeing within tolerance | lab access; criterion 11 is met_by_substitute until then |
| D2 | the MCU is represented by simplified electrical models — a resistive supply load sized from its run current (mcu_as_100R on the Uno, mcu_as_<R>R on other boards) and a Thevenin GPIO pin (mcu_pin_thevenin) — not the device | claims whose scope.model names an MCU model | open | reachset conformance against the real device | nothing in Phase 2 is scheduled to close it |
| D3 | no external engineer has read a generated explanation cold | the explanation layer | deferred | criterion 12's review | before the first external user is shown an explanation |
| D4 | coverage growth cost may outrun one engineer | the generator library as a whole | open | measured authoring cost per generator (Stage 3 onward) | — |
| D5 | an LLM may write the IntentIR, so the specification is untrusted | designs whose IntentIR provenance is llm and whose properties nobody has signed | open | per design: a person signs the back-translated properties (POST /design/{id}/sign-off), which are then frozen | — |
| D6 | block proofs may not compose into board claims | any design built from more than one generator | not_yet_applicable | interface contracts, first tested when two generators share a rail | — |
| D7 | datasheet parameters feeding predict() and the rule tables are unverified | claims that read ratings, forward voltages or pin tables | open | provenance per parameter; no LLM-extracted rating gates a claim | — |
| D8 | pi is irrational, so a z3 encoding of f_c must bracket it | z3-proved claims involving pi or another transcendental (Stage 4) | eliminated | rational bracketing in the proof compiler: proof/brackets.py encloses pi, ln 9 and the LED logarithms with outward-rounded interval arithmetic, and a refutation is certified at the bracket's adverse end | — |
| D9 | a generator bug makes predict() confidently wrong and nothing catches it | every generator not yet under the M1 mutation matrix | open | the M1 matrix detecting seeded faults in that generator's output | — |

Status per the owner's handoff (§5, after the snapshot): D1 open (bench sheet docs/BENCH_D1.md; evidence-record code not built). D2 open, derived per claim since commit 94b61c1. D3 = criterion 12, deferred with trigger. D4 open. D5 open per design; closed by user sign-off. D6 n/a. D7 open (provenance records + verify tool built, uncommitted). D8 eliminated. D9 open per generator until under the M1 matrix.

## [S11] Proofs (Stage 4): properties proved from the netlist, signed, frozen
*Sources: brain/decisions.md [2026-09-23] Stage 4; plan/current_phase.md Stage 4 gates and not-done*

**What a proof is here.** A *property* is a statement about one realised
design — "for every R1 in [a, b] and R2 in [c, d], V(VOUT) stays within
[lo, hi]" — and it is proved **from the design's own SPICE netlist**, not from
the generator's `predict()`. The netlist is parsed into elements, each
toleranced part becomes a variable over its tolerance box, symbolic nodal
analysis (sympy) gives the quantity as a rational function of those
variables, and z3 decides the negation over the box: UNSAT is a proof, SAT is
a counterexample. That independence is the point: Stage 3's claims restate
what the generator predicts; Stage 4's re-derive it from what the generator
actually built, per design rather than per CI grid point.

4. **`kind` is `analytic`.** v2's Stage 4 table tags these `empirical`; by
   EVIDENCE_CLASSES §3.1's own test (can a measurement falsify a z3 UNSAT over
   a box? no) they are analytic, and model-versus-hardware stays with D1. Same
   reading Stage 3 used and flagged; one field if the user wants v2's word.
5. **A property counts only once signed off.** Every property is
   back-translated to English by template — deterministic, no model — and the
   set is hashed. `POST /design/{id}/sign-off` takes the hash the user was
   shown; a mismatch is a 409, so nobody signs a statement they did not read.
   `SignOff` gains `properties_hash` (IntentIR 2.1.0 → 2.2.0). Until signed, a
   proof is shown but is not critical and does not move the floor. Signed,
   it is critical and the design stops carrying **D5** (an LLM wrote the
   spec): a person has agreed to the property in words. Sign-off never
   re-derives the design: if the installed generator differs from the one
   that built it, sign-off is refused and the user is told to patch first.

##### Stage 4 gates

| Gate | Result |
|---|---|
| Divider and LED claims proven over full tolerance (G1) | ✅ every grid point; LED dissipation G2 by construction |
| RC cutoff proven over full tolerance, π bracketed (G1) | ✅ all 7 grid points; the bracket checked against π at 80 digits |
| Every property back-translated and signed off before it counts (G1) | ✅ unsigned proofs are non-critical; floor moves only on a signature |
| Adversarial weakening: the refine loop cannot change a frozen property (G1) | ✅ looser bound, weakened obligation, dropped obligation, **smaller box** all raise `FrozenPropertyViolation` — the last only since the verification below |
| Every proven property fails under an injected wrong value (G1) | ✅ 64/64, each by a certified counterexample |

**D8 eliminated.** **Divider floor G1 once signed**; the library floor stays
**G2** — the LED's R1 dissipation is proved through a current bound, which is
sound and not complete.

## [S12] Multi-MCU firmware (Stage 5)
*Sources: brain/decisions.md [2026-09-23] Stage 5; plan/current_phase.md Stage 5 gates and not-done*

**Decision:** Stage 5 of `PHASE_2_PLAN_v2.md` is built as below. Written before
any Stage 5 code. The user chose, on being asked: install PlatformIO and all
three toolchains; the STM32 target is the WeAct Black Pill (STM32F411CEU6).
The ESP32 target is the ESP32-DevKitC (ESP32-WROOM-32E) — the common default.

1. **Three targets, one framework.** `arduino_uno` (ATmega328P, PlatformIO
   `atmelavr`/`uno`), `esp32_devkitc` (`espressif32`/`esp32dev`),
   `blackpill_f411ce` (`ststm32`/`blackpill_f411ce`), all on the Arduino
   framework, so one template family serves all three; what differs is data.

5. **Pins are claims.** Three rules join the catalogue, each an exact check of
   the design graph against the target table (G1, D7): `pin_assignment_valid`
   (exists, not reserved, can do what the connection needs),
   `peripheral_conflict_free` (one net per pin, one user per hardware
   peripheral, nothing on the console UART), `strapping_pins_safe`
   (conservative: no external connection to a strapping pin). Generators pick
   defaults that pass and refuse a requested pin that fails, by name.

##### Stage 5 gates

| Gate | Result |
|---|---|
| 100% of emitted firmware compiles under PlatformIO before display (G1) | ✅ 21/21 — every generator variant on every board, and the Phase 1 examples; nothing is displayed unbuilt |
| Pin-mux, peripheral-conflict, strapping-pin checks on a labelled set (G1) | ✅ 56 labelled cases, zero disagreements |

- **No board has been flashed.** Compiling proves the sketch is well-formed
  for the board, not that it runs; that is bench work, like D1.
- **The pin labels are the agent's own**, from the datasheets. An independent
  labeller would strengthen gate 2; D7 stays open on every MCU design.

## [S13] Stage 6 (BOM + substitution) and D7 provenance — uncommitted work in progress
*Sources: HANDOFF §8 (verbatim); plan/current_phase.md 'Next — Stage 6'; facts as stated in the first live run's request files*

D7 provenance built: backend/data/parts.py (all passive figures), backend/data/figures.py (155 records: kind guaranteed/typical/derived/standard/stated assumption, source, agent's reading written without opening datasheet; record hash), scripts/verify_figures.py + figure_verifications.json (empty), ClaimScope.figures, validation/figure_audit.py (perturb each figure; 145 pairs clean); found RS-485 1206 terminator boxed with 0402 tolerance (fixed).
Stage 6 BOM + substitution in progress. Gates: no substitution surfaces that fails original checks (G1); every price carries price_asof; pricing never gates validation. 5%-of-engineer KPI deferred. Found: BOM priced unknown parts as any same-value part (RS-485 ordered 62.5mW 0402 instead of 250mW 1206). Done: exact match pricing with price_asof, constraints.pinned.<id>, substitution.py tries each same-value catalogue part as a patch through apply_patch → dispatch → realize, surfaces only if envelope accepts, netlist byte-identical, no claim regresses, floor not worse, all properties re-prove. Not done: GET /design/{id}/bom; BOMTable.tsx; api.ts BOMRow; module registration; generator version bumps decision; regen_state; current_phase Stage 6 tasks; commit. D1 evidence records decided 2026-09-24, not built.

Stage 6 plan text (current_phase.md):
Not yet planned at function level. Gates (v2 §5): no substitution surfaces
that fails the original's checks (G1); every price carries `price_asof`, and
pricing never gates validation (G1). Amendment X7 (live pricing supersedes
the static-BOM rule) says "Stage 5 only", but its content is Stage 6's
second gate; it is treated as Stage 6's. Live pricing is an authenticated,
rate-limited external dependency — ask the user before adding it.

Also stated in the first live run's request files (tools/jev/requests/stage6_finish.json, pin_support_version_policy.json, x7_live_pricing.json), citing the owner's handoff: the suite on the working tree is 2123 passed, 30 skipped, 0 failed, with the uncommitted work green but unregistered; all 49 CI grid designs are byte-identical before and after the parts refactor; Stage 6 changed all five generators to honour constraints.pinned.<id> and left their VERSION strings unchanged; static exact-match prices carry price_asof 2026-07-25.

## [S14] Phase 1 — the twelve criteria and what v0.1.0 does not certify
*Sources: PHASE1_COMPLETE.md §2, §3, §5 (verbatim, trimmed)*

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | JWT auth — all routes protected | ✅ met | `tests/test_auth.py` + live session, 2026-06-02 |
| 2 | Full generation under 30s | ✅ met | ~15s measured end-to-end, 2026-06-02 |
| 3 | SPICE simulation runs and grades | ✅ met | RC filter 3.536V at 1kHz, 2026-06-02 |
| 4 | Simulation fails on wrong values | ✅ met | 1nF capacitor → FAIL grade, 2026-06-02 |
| 5 | Rule engine catches violations | ✅ met | `tests/test_rule_engine.py` |
| 6 | Firmware compiles to real Arduino | ✅ met | arduino-cli, 3 templates, 2026-06-02 |
| 7 | 5 sequential patches — no corruption | ✅ met | v1→v6; automated by `tests/test_patcher.py`, 2026-08-07 |
| 8 | 20 prompts — zero crashes | ✅ met | 6 fully verified, remainder rate-limited, 2026-06-02 |
| 9 | 100 requests — zero HTTP 500s | ✅ met | 100×200 OK in 3.2s, 2026-06-02 |
| 10 | Rate limiting — 11th returns 429 | ✅ met | IP-based, confirmed 2026-06-02 |
| 11 | Simulation vs closed-form ≤2% | **✅\* met_by_substitute** | `tests/test_simulation_accuracy.py`, 2026-08-22 — see §3 |
| 12 | External engineer reads explanation cold | **⏳ NOT MET** | moved to Phase 2 entry — see §3 |

The original criterion was a bench measurement — signal generator into an RC
filter, oscilloscope on the output. No lab access exists and none is expected,
so on 2026-08-07 it was replaced by an analytical cross-check: the netlist
emitted by `SpiceNetlistGenerator`, run through real ngspice, compared against
closed-form equations at **2%** across six R/C pairs spanning 100Hz–100kHz.

It passes with room to spare — worst measured deviation **0.0003%**, which is
ngspice's print precision rather than disagreement. Injecting a deliberate 5%
error into resistor emission fails 13 of the 34 tests, while the 15% simulation
grader passes the same error silently.

No engineer outside this repository has read an explanation and confirmed they
understood why each component was chosen and what would break if it changed.

`PRODUCT_MASTER.md` Part 12, `MENTAL_MODEL.md` §10 and `vision.md` all say the
same thing: the explanation layer *is* the product. It is what distinguishes
this from Flux.ai and Celus.io. **So the one component the company is staked on
has zero external verification, while the parts that are not the differentiator
carry four hundred tests.** That is an uncomfortable risk allocation and it is
stated plainly here so nobody has to discover it later.

## [S15] Phase 2 — stages, gates, and what each stage left not done
*Sources: HANDOFF §6; plan/current_phase.md (Stage 0–5 gates, verification tables)*

Stage history (HANDOFF §6): Phase 2 Validation Engine: Stage 0 instrumentation; Stage 1 IntentIR + abstention corpus (0/200 false accept, 0/200 false abstain); Stage 2 patch v2; Stage 3 library + claims; Stage 4 proofs (64 properties, 64/64 mutation refutations, sign-off, D8 eliminated); 4.5 exact LED dissipation; Stage 5 multi-MCU (21/21 builds, 56/56 pin cases); D2 derived (94b61c1). Suite 2063 passed. Library signed grade floor G1.

Stage 0 grid gate (Task 0.4): control rc_lowpass@0.1.0: 7/7 points within 2%, worst 0.0000%; seeded fault P5 detected at 7/7 points outside 2%, worst 4.8403%. Stage 0 log gate: every request produces a complete log row (G1, schema-enforced).

##### Stage 2 gates

| Gate | Result |
|---|---|
| Determinism: same IntentIR + version → byte-identical CircuitIR | ✅ `test_realize.py::TestDeterminism` |
| Idempotence: empty patch → identical output | ✅ `test_intent_patch.py::TestIdempotence` |
| Locality: diff ⊆ declared closure | ✅ swept — **projected** until a >2-part generator |
| Orphaned annotations surfaced, never dropped | ✅ `test_annotations.py::TestOrphans` |
| "Use a DS18B20 instead" end to end | ⏭ **deferred with a trigger** — no Phase 2 stage builds a DS18B20 generator. Replaced by *"make the cutoff 2 kHz"* with a `predict()`-delta justification: ✅ `test_realize.py::TestAcceptanceMakeTheCutoff2kHz` |

- **The citation guard does not catch values swapped between two operations**
  whose cited words each contain the other's number, **nor a removal citing an
  unrelated word**. Mis-transcription (2 kHz → 20000) *is* caught since the
  verification below. The diff is shown to the user.

##### Stage 3 gates

| Gate | Result |
|---|---|
| All five at the Stage 0 grid gate (G5 ≤ 2%) | ✅ `test_generator_library.py::TestGridGate` |
| Every design emits claims with kind/grade/scope/defeaters | ✅ at every grid point of every generator |
| `grade_floor` derived in `regen_state.py`, reported first | ✅ G2 |
| "Not assessed" and "out of scope" rendered as visible rows | ✅ `ClaimsTable.tsx`, browser-checked |
| Waveform viewer renders AC / transient / DC | ✅ browser-checked with real ngspice data |

- **The LED sketch drove pin 13 whatever the design wired** — a Phase 1 bug,
  right on the Uno's default by coincidence. Fixed; every pin `#define` is
  now checked against the wiring on every board.

## [S16] Phase 2 deliverables: the canonical list versus what was built
*Sources: PRODUCT_MASTER.md Part 6 Phase 2; ROADMAP.md §5; brain/decisions.md [2026-08-22]; HANDOFF note*

###### Phase 2 — "Validation Engine" (Months 3–8)
Target users: Serious makers, IoT startup teams, freelance hardware engineers.
Deliverables:
- Free-form circuit generation (beyond 5 templates, 15 total)
- ESP32 and STM32 firmware support
- Live BOM pricing via Digikey/LCSC API (nightly cache sync)
- Design version history with timeline UI
- Qdrant RAG on 500 datasheet excerpts
- Simulation waveform viewer (Plotly.js)
- Component substitution engine

KPIs: 3 paying pilot teams. Average IoT node design under 45 minutes. BOM accuracy within 5%.
Revenue: Pro tier at $49/month.

ROADMAP.md §5: **Phase 2 is the Validation Engine**, per `PRODUCT_MASTER.md` (confirmed
canonical 2026-08-22): free-form generation beyond the five templates,
ESP32/STM32 firmware, live BOM pricing, waveform viewer, version history,
component substitution, and analog circuits.

**Do analog last.** "Op-amps, buck/boost, LDO" is not an increment on what
Phase 1 validated. Everything so far is DC operating point and AC sweep over
passive networks; a switching converter needs transient analysis with real
device models, and the grader is built around `expected_outputs` per node.

**The BOM accuracy KPI needs a person.** "Within 5% of a manual engineer's
component selection" requires a manual engineer. That is the same shape as
criterion 12, which sat open for twelve weeks for precisely that reason. Line
someone up early or rewrite the KPI.

What was built instead is Stages 0–6 of PHASE_2_PLAN_v2.md (S15). PHASE_2_PLAN_v2.md, EVIDENCE_CLASSES.md and ARCHITECTURE_ASSURANCE_CASE.md are not in the repository. Precedence (set 2026-09-20): PHASE_2_PLAN_v2.md > PRODUCT_MASTER.md > EVIDENCE_CLASSES.md / ARCHITECTURE_ASSURANCE_CASE.md. No written Phase 2 exit gate exists in the repository.

## [S17] Phase 3 and later — the canonical roadmap
*Sources: PRODUCT_MASTER.md Part 3 Tier 3, Part 6 Phases 3–5, Part 7 External APIs, Part 9 pricing (verbatim, trimmed)*

###### Tier 3 — Phase 3 (Months 8–18)

**Industrial and HVAC control.** This is where the product becomes enterprise-grade:

**Demand Controlled Ventilation (DCV) boards:**
CO2 sensor interface (SCD30/SCD41 over I2C, or Telaire 6004 analog), microcontroller PID control loop, 0–10V analog output circuit driving a VFD, relay output for damper actuator, RS-485 Modbus RTU transceiver for BMS communication, 24VAC-to-3.3V power supply, fail-safe logic (defaults to maximum ventilation if sensor fails). The system generates the circuit, the PID firmware, and calculates energy savings.

**Commercial Kitchen Hood Controllers:**
Variable speed exhaust fan control via 0–10V VFD signal, makeup air fan balancing, duct temperature sensor input for fire detection, UV sensor input for flame presence, dry contact inputs from Ansul fire suppression system, relay outputs for gas valve shutoff and equipment lockout, human interface with alarm display. The system flags UL 508A requirements and life-safety design rules.

###### Phase 3 — "Industrial Layer" (Months 8–18)
Target users: HVAC controls companies, commercial kitchen equipment, refrigeration OEMs.
Deliverables:
- DCV board generation
- Commercial kitchen hood controller board generation
- Advanced refrigeration control
- RS-485 industrial I/O with optoisolation
- UL 508A flagging and safety class enforcement
- PCB auto-layout via KiCad freerouting (basic, 2–4 layer boards)
- Private component libraries per organization
- Audit trail (ISO 13485/26262 ready)

KPIs: First enterprise contract signed. One customer prompt-to-ordered-PCB within one business day.
Revenue: Team tier at $99/seat/month.

###### Phase 4 — "Enterprise Platform" (Months 18–30)
Target users: OEMs, SCADA integrators, building automation vendors.
Deliverables:
- Full SCADA RTU board generation (Modbus RTU master + LTE-M cellular)
- PLC-style control board generation
- Gerber export + JLCPCB/PCBWay API integration
- DFM report
- SSO/SAML enterprise identity
- ROI dashboard
- Fine-tuned domain model on accumulated design data

KPIs: $1M ARR. Average 40% prototype cycle reduction documented.
Revenue: Enterprise contracts, custom pricing.

**Pro — $49/month:** Unlimited generations, unlimited simulation, BOM with live pricing, Gerber export (Phase 2+), version history. Target: freelance engineers, serious makers, IoT startup founders.

**Team — $99/seat/month:** Everything in Pro, private component libraries, team workspace, design review workflow, audit trail, priority support, API access. Minimum 3 seats. Target: small hardware product companies, engineering consultancies.

## [S18] PCB and CAD strategy (PCB_STRATEGY.md), including §9 'How this could be wrong'
*Sources: PCB_STRATEGY.md §3, §4, §5, §7, §8, §9, §10 (verbatim, trimmed)*

> "This is an RS-485 bus. A/B is a differential pair, 120Ω termination at both
> physical ends of the bus and nowhere else, TVS at the connector entry, minimum
> 8mm from the switching regulator, bias resistors near the master."

Not because a router inferred it from geometry — because **you knew it was
RS-485 at the intent stage.**

**So: the moat is the constraint layer. The router is a commodity you should
consume, not a product you should build.**

This also resolves your competitive position with Quilter. Stop being a weaker
version of them. Become the thing that feeds them — and feeds freerouting, and
feeds KiCad, and feeds a human. Constraints are portable. Routers are not.

---

Audience sequence chosen: hobbyist -> PCB designer -> HVAC/controls. **The important observation:** all three want the constraint layer and the
explanation. Only the *surface* differs.

- Hobbyist: constraints applied silently, board just comes out better
- Designer: constraints exported to their tool, plus a validation report
- HVAC: constraints plus a guided editor, because they have no tool at all

Four steps. You are on step one.

| Step | What it is | Who needs it | Cost |
|---|---|---|---|
| 1. **Viewer** | `render_pretty.py` → SVG. Done. | everyone | done |
| 2. **Annotated viewer** | Shows *why* each part is where it is; DRC violations inline with consequences | everyone | weeks |
| 3. **Constrained editor** | Drag parts, rules enforced live, immediate feedback on what you just broke | HVAC, some designers | months |
| 4. **General CAD** | Replace KiCad | HVAC only | years |

**Step 2 is the one to build, and it is uniquely yours.** It is your explanation layer applied to geometry.

##### 7. Explicit non-goals

Writing these down so they stop consuming attention:

- **Beating Quilter at autorouting.** Not winnable, not necessary, not your moat.
- **General-purpose CAD before the HVAC phase.** Building for the audience you
  reach last, at the highest cost.
- **Gerber export and fab APIs right now.** Real value, but downstream of layout
  quality being trustworthy. Premature.
- **Multi-layer beyond 2–4 layers.** Your circuit classes do not need it.
- **RF, controlled impedance, high-speed digital.** Your simulator cannot
  validate above ~100MHz, so you would be generating constraints you cannot
  check. Say so out loud rather than quietly generating them.

---

##### 9. How this could be wrong

Take these seriously; each would change the conclusion.

1. **If layout quality is the actual buying trigger**, constraints are a
   consolation prize and this whole document is a rationalisation for not
   competing. Test it: show two hobbyists a good board with no explanation and a
   mediocre board with a great explanation. See which one they want.

2. **If Quilter or Flux ships intent-aware constraints**, the moat closes fast.
   Flux is closest — they have design context and would only need to add physics.
   Watch for it.

3. **If HVAC customers want finished boards, not designs**, then CAD never
   matters and you should be a design service with software leverage. Worth
   asking three real HVAC controls people before committing to step 3 or 4.

4. **The constraint layer may be harder than it looks.** "Decoupling cap near
   the pin" is easy. "How near, given this supply, this load step, this
   tolerance" is a real engineering problem. If the constraints are vague, the
   explanation is vague, and the differentiator evaporates.

5. **Semantic placement rules may not generalise past your five templates.**
   They are hand-written heuristics. Beyond the templates they may be wrong more
   often than wirelength. Watch for it as breadth grows.

---

> **Stop trying to lay out boards better than Quilter. Start being the only tool
> that knows *why* a board should be laid out that way — and sell that to
> everyone, including Quilter's users.**

## [S19] Competitive position and product claims
*Sources: brain/vision.md; MENTAL_MODEL.md §9 (verbatim, trimmed)*

Three real competitors. All three are good at something.

| | Flux.ai | Celus.io | Quilter | **You** |
|---|---|---|---|---|
| Natural language in | ✅ | ✅ | ❌ | ✅ |
| Schematic out | ✅ | ✅ | ❌ | ✅ |
| **SPICE simulation** | ❌ roadmap | ❌ | ❌ | **✅ shipping** |
| **Complete firmware** | ⚠️ pin maps only | ❌ | ❌ | **✅ flashable .ino** |
| **Consequential explanation** | ❌ | ❌ | ❌ | **✅** |
| PCB layout | ✅ | ❌ | ✅ best in class | ⚠️ untested |
| **Industrial rules** (RS-485, 4–20mA, UL 508A) | ❌ | ❌ | ❌ | roadmap |

**The wedge:** *"The only AI hardware tool that simulates before it ships — with
physics-validated results, consequential explanations, and industrial-grade rule
libraries for HVAC, refrigeration, and building automation."*

**Be honest about where you lose.** Flux beats you on breadth and polish today.
Quilter beats you on layout and it is not close. Celus has more component data.
You win on *depth of validation*, and only if the validation is genuinely
trustworthy — which is exactly why criterion 11 being a substitute matters and
why 2,400 untested lines in the PCB path is a real problem, not a bookkeeping one.

**The untouched ground:** none of the three has industrial rule libraries. No
RS-485 bias and termination, no 4–20mA loops, no 24VDC industrial supplies, no
DCV or refrigeration templates. That vertical is the highest-margin, most
defensible part of the plan and nobody is standing there.

## [S20] Open issues
*Sources: HANDOFF §9 (verbatim); plan/current_phase.md; brain/timeline.md*

Only nominal DC op point simulated (RC gets AC); no transients. No G0 proof checker (z3 UNSAT trusted). Property sets signed whole. Citation guard can't catch swapped values between ops or a removal citing unrelated word. design.py coverage thin; several modules untested. One flaky accuracy test. No board flashed. Strapping-pin rule conservative. DHT22 rise-time/sink figures are stated assumptions. Out of Phase 2: switching converters, PCB layout, foreign-netlist recognition, fine-tuning, team features.

Flaky test (timeline.md 2026-08-23): **Open:** one test in `test_simulation_accuracy.py` is flaky. Regen at `2edfbc8` reported 410 passing / 0 failing; regen at `f5fbd3d` reported 409 / 1 failing with no code change between them. Criterion 11 shows `❌` and `generators/spice`, `simulation/runner`, `simulation/parser` show `broken`. Do not tag v0.1.0 until it is reproducible.

**Carried from 2026-08-23, never diagnosed:** one test in `test_simulation_accuracy.py` was flaky (timeline, 2026-08-23). It passed in every full run on 2026-09-21; that is not a diagnosis. An infrastructure hiccup may be retried; an accuracy disagreement never may.

## [S21] Decisions the owner holds, and other open decisions (facts and options only)
*Sources: HANDOFF §7 (verbatim); tools/jev/requests/*.json states; PRODUCT_MASTER.md; PCB_STRATEGY.md; earlier report findings*

Handoff §7 — decisions the user still owns (verbatim):
- RS-485 DE/RE pull-down (10kΩ): keeps rebooting node off the bus; would let fail-safe claim drop D2. Product call.
- Live pricing (X7): needs explicit approval.
- Bench session (D1) and datasheet verification pass (D7): when engineer chooses.
- `kind` on exact proofs is analytic vs v2's empirical — flagged, unsettled.
- Raising explainer max_tokens (cost).

###### D-1 RS-485 DE/RE pull-down
*Question:* Should the rs485_node generator add a 10 kOhm pull-down from the transceiver DE/RE net to GND?
*Facts:*
- Topology U1 pin D2 drives the MAX485/MAX3485 DE and /RE pins together; PIN_DE_RE = 'D2'.
- Claims on the design: rs485.failsafe_bias (monotone corners), driver_load, termination_dissipation, rail_current; D2 is cited per claim where the real MCU can reach it.
- D2 register text: nothing in Phase 2 is scheduled to close it.
- Added idle current when DE/RE is driven high: 5 V / 10 kOhm = 0.5 mA on Uno; 3.3 V / 10 kOhm = 0.33 mA on 3.3 V boards.
- Changing the default output means rs485_node 0.2.0 -> version bump -> every signed RS-485 design returns 409 until re-patched.
- M1 seeded-fault margin on this generator is thin: a 5% component fault moves V_AB by 2.3% against a 2% gate.
- DE/RE default pin per board: Uno D2, ESP32-DevKitC GPIO4, Black Pill F411 PB0. None is a strapping pin (ESP32 straps are GPIO0, 2, 5, 12, 15; F411 strap is PB2/BOOT1) and none is reserved.
- Stated assumption, not datasheet-verified: during MCU reset the GPIO driving DE/RE is a high-impedance input, and the MAX485/MAX3485 DE and /RE inputs are not specified to default to a safe state, so the driver may be enabled while the MCU reboots. The catalogue records only 'DE and RE tied, driven by one MCU GPIO; HIGH = transmit'. D7 (datasheet figures unverified) applies.
*Options on the table:*
- `add_as_default_now` — Every new RS-485 design gets R4 10k DE/RE->GND; generator version bump. Costs: Signed RS-485 designs invalidated (409); one more part; 0.33-0.5 mA idle. Invalidates signatures.
- `add_as_opt_in_constraint` — constraints.de_re_pulldown (default false) adds R4 when set. Costs: Another constraint to test and document.
- `defer_with_trigger` — Nothing now; record trigger: first multi-drop bus or first flashed RS-485 board. Costs: Risk stays for anyone who flashes a node on a shared bus.
- `do_not_add` — Close the question. Costs: Loses the option if the risk is real.
- Unknown: How many users will put a node on a shared multi-drop bus in Phase 2/3.

###### D-2 Live pricing (X7)
*Question:* Should Circuit OS add live component pricing (amendment X7)?
*Facts:*
- Stage 6 gates: no substitution surfaces that fails the original's checks (G1); every price carries price_asof; pricing never gates validation (G1).
- Static exact-match pricing with price_asof 2026-07-25 already meets the Stage 6 price gates.
- The worst pricing bug found (RS-485 1206 250 mW terminator ordered as a 62.5 mW 0402) was a static matching bug, fixed without live data.
- Project rule: Phase 1 static pricing only; live Digikey/LCSC calls create an authenticated, rate-limited dependency.
- No live-pricing vendor has been chosen; vendor caching/display terms, key handling, rate limits and cost are unknown.
*Options on the table:*
- `approve_now_behind_flag` — Live fetch writes a price_asof cache row; never read by validation. Costs: New secret, rate limit, ToS review, cache invalidation.
- `approve_after_static_stage6_exit` — Close Stage 6 static, then add live pricing. Costs: Same ops cost later.
- `defer_to_phase3` — Revisit when customers exist. Costs: Prices age.
- `reject_keep_static` — Static dated pricing only. Costs: Prices age; manual refresh.
- Excluded by rule: Enable live pricing without the owner's explicit approval (X7 / plan: ask the owner).

###### D-3 D1 bench session timing
*Question:* When should the D1 bench session (hardware validation) happen?
*Facts:*
- BENCH_D1 equipment list includes an oscilloscope and signal generator; the owner has neither (multimeter + Uno available).
- BENCH_D1 names led_indicator 0.1.1; the code is 0.2.0, so the sheet is stale.
- Every behavioural claim cites D1; D1's trigger is lab access.
- No board has been flashed yet; compile != runs.
- Criterion 11 was met by an analytic substitute (2%), never by bench measurement.
- BENCH_D1 lists a multimeter, bench supply, signal generator and oscilloscope. Only the RC low-pass check needs the generator and scope; the divider check needs only a supply and meter, and the LED check a meter and an Uno pin driven high.
*Options on the table:*
- `build_evidence_records_then_bench_when_scope_available` — Build D1 evidence-record code now; bench when a scope is available. Costs: Code before evidence.
- `partial_session_now_without_scope` — Multimeter DC checks on divider and LED now; RC cutoff later. Costs: Partial; needs the record code.
- `bench_before_phase2_exit` — Make D1 a Phase 2 exit condition. Costs: Blocks exit on equipment.
- `defer_with_trigger_lab_access` — Keep the lab-access trigger. Costs: D1 stays open on every claim.
- Unknown: The PHASE_2_PLAN_v2 exit criteria are not available, so whether Phase 2 exit requires D1 closed is unknown.

###### D-4 D7 datasheet verification pass: timing and order
- Provenance is built but uncommitted: data/parts.py, data/figures.py (155 records, each with a kind — guaranteed, typical, derived, standard or stated assumption — a source, and the agent's reading written without opening the datasheet), scripts/verify_figures.py with an empty figure_verifications.json, and validation/figure_audit.py (perturb each figure; 145 pairs clean). Verification means a person opens each datasheet.
- Order proposed in the earlier report: deterministic tiers first — figures that gate a critical claim; within a tier, stated_assumption and typical before guaranteed; then the smallest figure_audit margin. A judgment model would only break ties inside a tier.
- Stage 6 substitution re-proves every property with the substitute part's figures before surfacing it.
- The DHT22 rise-time and sink limits and the MAX485 DE/RE reset behaviour are stated assumptions.

###### D-5 `kind` label on exact proofs
*Question:* Which `kind` label should claims proven exactly (z3 / closed form over the tolerance box) carry: analytic or empirical?
*Facts:*
- PHASE_2_PLAN_v2's Stage 4 table tags z3-proved claims 'empirical' (the document itself is not available to quote; this is how the decision log reports it).
- EVIDENCE_CLASSES §3.1 classifies a claim as empirical if a measurement could falsify it, analytic otherwise (as paraphrased in the decision log; the document is not available to quote).
- No code reads Claim.kind; Kind.EMPIRICAL is never used; the UI does not render kind.
- kind is not part of the sign-off hash.
- D1 (not validated on hardware) is cited on every proof row.
- v2 labels the grid gate (predict vs ngspice within 2%) 'empirical, G5'.
- kind lives inside CircuitIR.validation_coverage. same_design() drops validation_coverage before comparing, so changing kind does not change the circuit identity check, but it does change the full serialized CircuitIR.
*Options on the table:*
- `keep_analytic_and_amend_v2_wording` — Keep code; write a v2 amendment. Costs: Needs an amendment to respect precedence.
- `switch_to_v2_empirical` — Change enum value on proof rows. Costs: Label may mislead (no data was sampled).
- `split_by_object` — Proof statements analytic; tool-run observations (grid gate, compile gate) empirical. Costs: Two labels to maintain.

###### D-6 Explainer budget (max_tokens, cost, latency)
*Question:* What is the next step on the LLM explainer's cost and latency?
*Facts:*
- EXPLANATION_MAX_TOKENS = 8192; a stop at the ceiling raises.
- Measured 110-130 s and about $0.20 per explanation; the RS-485 explanation exceeds 8192 tokens.
- The fix of disabling thinking is untried (credits exhausted, HTTP 402).
- ai/derived_explainer.py makes 0 calls; the structural layer is derivable 6/6, the domain layer is not.
- D3 (no external engineer has read an explanation) is deferred until before the first external user.
- The owner has not stated a per-generation cost ceiling.
*Options on the table:*
- `experiment_thinking_disabled_when_credits` — Measure thinking-disabled first. Costs: Needs credits.
- `move_explanation_off_request_path` — Run explanation async like simulation. Costs: UI polls.
- `derived_default_llm_opt_in` — Zero-call explanation by default; LLM on request. Costs: Domain layer missing by default.
- `raise_ceiling_to_16384` — Double max_tokens. Costs: Slower, costlier.
- `cheaper_faster_model_for_explainer` — Different model for explainer only. Costs: Quality unknown; D3 unaffected.

###### D-7 Generator VERSION bumps after the Stage 6 pin-support change
*Question:* Residual case only: after the Stage 6 part-pin change, generator outputs are byte-identical but some generators now accept pinned-part inputs they used to refuse. Which version policy applies?
*Facts:*
- A VERSION bump makes signed designs of that generator return 409 generator_changed; un-bumping after signatures is not possible.
- All 49 CI grid designs are byte-identical before and after the parts refactor.
- The deterministic byte-compare over the uncommitted Stage 6 code (grid points, Phase 1 examples, accepted corpus) and the envelope accept/refuse diff on the refusal corpus have not been run.
*Options on the table:*
- `minor_bump_generators_whose_envelope_widened` — Bump only generators whose accepted set grew. Costs: Signed designs of those generators 409. Invalidates signatures.
- `patch_bump_all_touched` — Bump all five. Costs: All signed designs 409. Invalidates signatures.
- `no_bump_outputs_identical` — Leave versions. Costs: Widened acceptance not visible in version.

###### D-8 Stage 6 finishing versus Phase 3 start; the deferred 5%-of-engineer KPI
*Question:* How should the remaining Stage 6 work and the deferred 5%-of-engineer KPI be handled relative to starting Phase 3?
*Facts:*
- Not done: GET /design/{id}/bom with dated rows and checked substitutes; BOMTable.tsx; lib/api.ts BOMRow shape; Playwright fixture re-export; registering data/parts, data/figures, validation/figure_audit, generators/bom/substitution in regen_state.py and progress_gen.py; version-bump decision; regen_state run; current_phase Stage 6 tasks; commit.
- The 5%-of-engineer KPI is deferred with trigger: an engineer available.
- Suite on the working tree: 2123 passed, 30 skipped, 0 failed; the uncommitted work is green but unregistered.
- Phase 3's first programme (constraint layer + freerouting) does not read the BOM route.
*Options on the table:*
- `finish_now` — Complete all Stage 6 items before Phase 3. Costs: Delays Phase 3.
- `finish_in_parallel` — Phase 3 constraint work alongside Stage 6 UI. Costs: Two streams for one engineer.
- `defer_to_phase3` — Leave UI items for Phase 3. Costs: Unregistered modules linger.

###### D-9 The flaky accuracy test
*Question:* How should the intermittent failure in tests/test_simulation_accuracy.py be handled?
*Facts:*
- The flake record: 410/0 vs 409/1 with no code change.
- Rule: infra hiccups may be retried; accuracy disagreements never.
- One failure marks generators/spice broken in the derived tracker.
*Options on the table:*
- `diagnose_now_with_N_repeat_runs_seed_logged` — Run N times with seeds logged to find nondeterminism. Costs: Hours of runs.
- `mark_xfail_strict_with_issue` — xfail(strict) with a tracked issue. Costs: Needs a known cause.
- `leave_carried` — Leave as is. Costs: Tracker may show broken.
- Excluded by rule: Retry until green (accuracy disagreements are never retried (current_phase.md:463)).

###### D-10 Phase 3 programme order
- Phase 3 splits into three programmes: (A) the constraint layer + freerouting integration, which needs no customers; (B) industrial generators (DCV, kitchen hood, refrigeration, RS-485 industrial I/O with optoisolation); (C) enterprise features (private libraries, audit trail), which PCB_STRATEGY §9.3 gates on asking three HVAC controls people.
- The first-listed Phase 3 class (DCV) needs a 24VAC-to-3.3V switching supply; switching converters and transient simulation are out of Phase 2 scope.
- One engineer; Phase 3 is planned at months 8–18.

###### D-11 The Gerber / Phase 3 KPI contradiction
- Phase 3 KPI: 'One customer prompt-to-ordered-PCB within one business day.'
- Gerber export + JLCPCB/PCBWay API integration and the DFM report are Phase 4 deliverables.
- Part 7 lists 'JLCPCB API (Phase 3+)'.
- The Pro pricing tier text says 'Gerber export (Phase 2+)'.
- PCB_STRATEGY §7 lists Gerber export and fab APIs 'right now' as a non-goal.

###### D-12 Which Phase 2 deliverable list governs Phase 2 exit
- PRODUCT_MASTER's Phase 2 list (free-form generation to 15 templates, ESP32/STM32, live BOM pricing, version history UI, Qdrant RAG on 500 excerpts, waveform viewer, substitution engine) differs from what was built (Stages 0–6 of PHASE_2_PLAN_v2).
- Precedence: PHASE_2_PLAN_v2 > PRODUCT_MASTER. PHASE_2_PLAN_v2 is not in the repository. No written Phase 2 exit gate exists in the repository.

###### D-13 Standard family to flag for Phase 3 boards
- PRODUCT_MASTER Phase 3 names 'UL 508A flagging and safety class enforcement'; the kitchen-hood class 'flags UL 508A requirements and life-safety design rules'.
- The earlier report (finding 10): UL 60730-1 covers automatic electrical controls; UL 61010-1 / 61010-2-201 cover programmable controllers; UL 508A covers the industrial control panel. Applicability is a liability decision for a person; Circuit OS should flag candidate families, never assert compliance.

###### D-14 Criterion-12 timing
- Trigger (decisions.md 2026-08-25): before the first external user is shown a generated explanation — a public launch, a demo to a prospect, or onboarding anyone outside the repo.
- Phase 3 KPI: first enterprise contract signed.
- The review costs about ten minutes of one EE-literate person's time; the protocol asks for three reviewers.

###### D-15 Storing raw prompt text (needed for a live transcription-fidelity check, R1)
- Today request_log stores prompt_hash, not the prompt text.
- R1 in shadow mode on live traffic needs the raw prompt; a seeded prompt->gold-IntentIR corpus does not.
- The existing 0/200 corpus measures envelope(), not transcription.

###### D-16 Commit convention
- HANDOFF §3: 'Commits conventional; commit/push only when asked.'
- AGENTS.md worker mode: `git commit -m "session: <brief description>"`.
- Memory commits use `brain:`; the last 40 commits on phase2-stage0 mix `feat(phase2):` (8), `brain:` (7), `fix(...)`, `test(...)`, `memory:` and `regen`.
- The /update-memory command hardcodes a Windows user path.

## [S22] Reasoning on record — closing Phase 1 (brain/decisions.md, verbatim, trimmed)
*Sources: brain/decisions.md [2026-08-22] criterion 12 moved; PRODUCT_MASTER canonical; [2026-08-25] criterion 12 deferred*

#### [2026-08-22] Criterion 12 moved off the v0.1.0 gate

**Decision:** v0.1.0 is tagged at 11 of 12 criteria. Criterion 12 — an external
engineer reading an explanation cold — remains on the list as openly unmet and
becomes an entry condition for Phase 2 rather than an exit condition for Phase 1.

**Reason:**
- It is the only criterion whose completion depends on a third party's calendar.
  Every other one can be unblocked by work in this repo.
- It has been open since 2026-06-02. Phase 1 has been functionally complete for
  most of that time. The tag did not happen because the gate was unreachable,
  not because the software was unready — and an unreachable gate stops being a
  standard and starts being an excuse.

**Rejected alternatives:**
- *Drop it entirely.* Would make the criteria list something edited when
  inconvenient, which devalues the other eleven.
- *Substitute the agent panel* (`scripts/review_panel.py`). An LLM reading LLM
  output answers correctly from its own training whether or not the explanation
  said anything, so a descriptive and a consequential explanation score alike —
  and that difference is the entire product claim. The panel is a pre-screen and
  a regression metric, not evidence. Marking it as criterion 12 would be the
  quiet devaluation this decision is trying to avoid.

#### [2026-08-22] PRODUCT_MASTER.md is canonical; Phase 2 is the Validation Engine

**Decision:** The `PRODUCT_MASTER.md` at the repo root is the spec. The
pre-build v1.0 is archived at `docs/PRODUCT_MASTER_v1.md` and must not be built
from. Phase 2 is the **Validation Engine**.

**Consequence for Phase 3:** integrate freerouting rather than extending the A*
engine, and treat the constraint layer — net classes, differential pairs and
keepouts derived from SignalType and ApplicationClass, each carrying a
plain-English reason — as the differentiating deliverable of that phase. It is
the piece no competitor can build, because nobody else has intent → IR →
simulation in one system.

#### [2026-08-25] Criterion 12 deferred with a trigger; Phase 2 begins

**Decision:** Phase 1 closes at 11 of 12. Criterion 12 — an external engineer
reading an explanation cold — is **deferred, not dropped**, and reopens on a
named trigger: **before the first external user is shown a generated
explanation**, whichever comes first between a public launch, a demo to a
prospect, or onboarding anyone outside this repo.

**Reason:**
- The 2026-08-22 entry made it a Phase 2 *entry* condition. Holding Phase 2's
  start against a third party's calendar reproduces the original problem one
  phase later — it was open twelve weeks and no person had been identified.
- The trigger binds it to the event that actually makes it matter. The risk was
  never "we did not do a review"; it was "an outsider reads an explanation and
  it does not land." That risk arrives with the first outsider, not with the
  start of Phase 2.
- A deferral without a trigger is a deletion with better manners.

## [S23] Reasoning on record — predict() as per-request truth; explanation derivability
*Sources: brain/decisions.md [2026-09-20] (two entries, verbatim, trimmed)*

#### [2026-09-20] `predict()` is the per-request truth; ngspice becomes the regression check

**Decision:** Amends `PRODUCT_MASTER.md` Part 10, *"Why simulation must be the
truth, not the LLM's opinion."* A generator's `predict()` — closed-form physics —
answers any numerical claim about a design at request time. ngspice moves to CI,
where it runs the generator's full declared envelope grid and `predict()` must
agree with it to within 2%.

- Part 10's sentence carries two readings that were identical in Phase 1 and come
  apart in Phase 2: *the numbers must not come from the LLM*, and *the numbers
  must come specifically from ngspice*. The first is the principle. Closed-form
  arithmetic is not the LLM either, so the principle survives intact.
- One nominal ngspice run is a statement about one point in parameter space. The
  same physics evaluated across a tolerance box — monotone corners, or z3 over
  component ranges — is a statement about every point in it. That is a stronger
  claim, not a weaker one, and it is the whole reason for the amendment.

**Carried forward — the defeater fans out.** `predict()` validated against
mathematics rather than hardware is the same limitation criterion 11 carries as
`met_by_substitute`, now sitting under every user-facing number instead of one
test file. It is D1 in `PHASE_2_PLAN_v2.md` §7. Do not let it go quiet: the
bench measurement is still owed, and it is owed more broadly after this decision
than before it.

#### [2026-09-20] Explanation derivability: yes for the baseline, no for the domain layer

**Answer: a qualified yes, and the qualification is the useful part.**

Evidence: `scripts/explanation_derivability.py`, run 2026-09-20 over six
designs — one produced by the `rc_lowpass` generator, plus the five Phase 1
example IRs — scored on the consequential-language markers
`tests/test_explainer.py` already enforces, against live
`ExplanationEngine` output from the configured model.

Derived: 6/6 clear the marker bar, 6/6 name every component, **zero API calls**.

**What is derivable.** The structural explanation: what was asked for, what was
chosen and by what rule, what the design will do over the whole tolerance box,
which tolerance dominates the result, what margin each part has, and what the
claim does not cover. It reads as consequential rather than descriptive without
any prompting, and it clears the bar the test suite enforces on the model.

The reason this works is architectural rather than clever templating: **a
deterministic generator already knows why it chose what it chose.**
`rc_lowpass` writes the selection rule into each component's `justification` as
it builds the design, and `predict()` supplies the consequences in closed form.
The explainer assembles reasons that already exist as data; it invents none.

## [S24] Reasoning on record — the LLM -> CircuitIR path removed
*Sources: brain/decisions.md [2026-09-21] (verbatim, trimmed)*

#### [2026-09-21] The LLM → CircuitIR path is removed, and coverage narrows to the catalogue

**Decision:** `backend/ai/circuit_reasoner.py` is deleted. `POST /design/generate`
now runs prompt → IntentIR → registry dispatch → generator → CircuitIR, with no
model in the design path. Stage 1 Task 1.5.

**Reason:** the Stage 1 gate is *"no code path lets the LLM write CircuitIR —
asserted by test"*, graded **analytic, G1**. An analytic claim is one no
measurement can falsify, so it has to be true of the code rather than of the
paths a test happened to exercise. Leaving the module importable would leave
the path; the gate would then be "nothing currently calls it", which is a
different and much weaker statement.

`tests/test_llm_cannot_write_circuit_ir.py` asserts it by AST across the whole
backend: no module may both talk to a model and construct a `CircuitIR`.

**What made the gate honest.** The first version of the AST scanner looked
only for `CircuitIR(...)` and **passed while the violating module was still in
the tree**, because the module used `CircuitIR.model_validate(last_raw)`. The
scanner now covers every Pydantic construction form and has a parametrised
negative control for each. A G1 claim resting on a check with a hole in it is
worth less than no claim at all.

## [S25] Reasoning on record — X6 + X8, the defeater namespace, `kind` and the library floor
*Sources: brain/decisions.md [2026-09-21] X6 + X8 (verbatim, trimmed)*

#### [2026-09-21] X6 + X8 accepted, the defeater register is renumbered, and Stage 3 is scoped

**Decision:** amendments X6 and X8 of `PHASE_2_PLAN_v2.md` §2 are accepted, the
defeater IDs are made unique, and the Stage 3 build is fixed as below. Taken by
the agent on the instruction "move to stage 3", after the council verdict on
X6/X8 and the TypeSafe pass that flagged X8 as due earlier than Stage 3. Written
before any Stage 3 code, per v2 §2.

##### X6 — the MCU model becomes a declared scope

Accepted with the council's conditions:
- **Derived, never remembered.** A claim's `scope.model` gains `mcu_as_100R`
  whenever the design's own netlist contains an `R_MCU_` element, computed from
  the netlist text; a test fails if a design with an MCU produces a claim
  without it. Likewise `mcu_pin_thevenin` whenever it contains an `R_PIN_`
  element (below).
- **"Promote" does not mean "delete".** The rule that the MCU must never be a
  voltage source stays as an implementation rule; it is why this model exists.
- **D2 is widened to name both simplifications** — the 100 Ω supply load and
  the Thevenin GPIO pin — since both are "the ATmega328P represented by a
  model, not the device", and both are eliminated by the same future work.
  Nothing is scheduled to close D2 in Phase 2; the register says so.

##### The X6 × X8 interaction

The council warned that an open D2 on every MCU design would flatten
`grade_floor`. It does not, under the weakest-link rule as EVIDENCE_CLASSES
§3.2 states it: a model assumption is a **defeater**, not a lower grade — "a G1
proof over an unvalidated model is G1 carrying a model defeater". So
`grade_floor` reports the worst *grade*, `open_defeaters` reports D2 separately,
and the two are never fused (§5). A claim with an open defeater has verdict
**holds, defeasible**, never plain "holds".

##### The defeater register — one namespace

v2 §7 owns IDs D1–D7. Two other documents reused the namespace:
- EVIDENCE_CLASSES Table C's **D4** ("π is irrational; the z3 encoding must
  bracket it") becomes **D8**. Its status is *not yet applicable*: no claim is
  proved by z3 until Stage 4, which is where it gets eliminated.
- ARCHITECTURE_ASSURANCE_CASE's **D-G** ("a generator bug makes `predict()`
  confidently wrong, and nothing catches it") is imported as **D9**. v2 carried
  the harness that refutes it without registering the doubt. It is *eliminated
  per generator* by passing the M1 mutation matrix; a generator that has not
  passed it carries D9 open.

**Two things settled here that were open, flagged for the user to reverse:**

- **`kind` for exact closed-form claims is `analytic`.** v2's Stage 4 table
  tags z3-proved claims `empirical`; by EVIDENCE_CLASSES §3.1's own test (could
  a measurement falsify it? no) they are analytic, and the model-versus-reality
  gap is carried by D1 instead. Stage 3's claims follow that reading. If the
  user prefers v2's wording, it is one field per generator.
- **The library floor is G2**, set by the two resistor-dissipation claims:
  dissipation is not monotone in R, so they use interval arithmetic
  (`sound_enclosure`). Adding the interior critical point to the corner
  evaluation would make them exact and the floor G1.

## [S26] Reasoning on record — RC swamping and the LED bound (decided with TypeSafe); the unverified three
*Sources: brain/decisions.md [2026-09-23] (two entries, verbatim, trimmed)*

#### [2026-09-23] RC source swamping (rc_lowpass 0.2.3) and the LED bound — decided with TypeSafe

**Decision:** The two calls the Stage 3 + 4 verification left to the user were
put to TypeSafe (Jev, `jev-1.13.0`) with the whole scenario as state, on the
user's instruction ("give it the whole scenario and then make the decision").
The agent then decided, reading the answers against TypeSafe's own confidence
guidance (>0.9 act, 0.5–0.9 act with care, <0.5 a person should decide).

**What was sent.** About 10.6k characters of state: how a design is made and
graded, the invariant that an accepted design never carries a failing claim,
versioning, the one-engineer team, and for each decision its history, the
measured facts and every option with its benefits and costs side by side.
The request script is `typesafe_rc_led.py` (session scratchpad). Questions:
two Choices and three Nouls. Raw answers:

| Question | Answer |
|---|---|
| `rc_option` (choice) | **swamp_with_larger_r1 0.87**, refuse 0.13, compensate 0.00 — confidence 0.83 |
| `led_option` (choice) | **conservative_now_exact_later 0.58**, exact_now 0.36, keep_conservative 0.06 — confidence 0.44 |
| `rc_refusal_blocks_common_requests` (noul) | 0.62 |
| `led_loss_is_material` (noul) | 0.26 |
| `led_grade_upgrade_worth_doing_now` (noul) | 0.47 |

1. **RC: swamp with a larger R1 — implemented, rc_lowpass 0.2.3.** Confidence
   0.83, and the agent's own reading agrees: designs that pass today do not
   change (0 of 36 checked), the design stays right if the declared source is
   somewhat off, and it is what the generator's comment always claimed.
   When the source would move f_c past tolerance, the closest catalogue pair
   that keeps both the source shift and its own error inside tolerance is
   taken — a smaller capacitor, a larger R1. Refused when none does, or when
   a pin fixes R1. Largest source at 5%: 179 Ω → 1.79 kΩ at 1 kHz, 1.79 →
   3.76 kΩ at 100 Hz; unchanged at 100 kHz (83 Ω). `dependency_closure` for
   `constraints.source_impedance_ohm` widens to {R1, C1}: the source can now
   change the capacitor. *Rejected:* compensating R1 by R_s (Jev 0.00) —
   every source-declaring design changes, and correctness hangs on a declared
   value with no tolerance that an LLM may have written (D5).
2. **LED: keep the conservative bound now; exact worst case scheduled.**
   Confidence 0.44 is below TypeSafe's own threshold for acting, so the agent
   decided, taking the reversible option: the wrongly refused requests do not
   matter to users (0.26 — only 16.3–16.5 mA at 5.25 V, true worst 62.0 mW),
   and doing the G1 upgrade now is a coin flip (0.47). Recorded as a
   scheduled task in `plan/current_phase.md`. **The user may overrule** — the
   cost of doing it now is one generator, its claim and its proof.

#### [2026-09-23] The unverified three — PostgreSQL, the live model, hardware

**For the user:** with this model an explanation takes 110–130 s and ~$0.20,
and the largest design (RS-485) still exceeds 8192 tokens — so generation
cannot meet the 15 s launch target. The likely fix — thinking disabled for
the explainer call — could not be tried: the OpenRouter account returned 402
`in_flight_budget_exhausted` (credits). Options: top up and try it; a faster
model for explanations; or explanations off the request path.

**Hardware — cannot be done here.** `docs/BENCH_D1.md` is a one-hour bench
session for three designs (RC 1 kHz, divider, LED) with their exact parts,
the proven bands as pass criteria, and a results table. D1 stays open.

## [S27] Criterion 12 review protocol and the D1 bench sheet
*Sources: CRITERION_12_REVIEW.md §0–§3; docs/BENCH_D1.md (verbatim, trimmed)*

#### 0. The one rule

**Say nothing.** No framing, no context, no "does this make sense?", no
apologising for length, no "it's a first draft". The moment you explain anything,
the test is void — you cannot tell afterwards whether they understood the
document or understood you.

Paste the text. Ask the questions in §3. Stay quiet.

---

**Get three, not one.** The criterion says one. One tells you almost nothing —
a single confused reader might be a bad explanation or a distracted afternoon.
Three costs thirty minutes total and turns a coin flip into a signal.

#### Bench check for defeater D1

D1: *predict() and the proofs are validated against mathematics and ngspice,
not hardware.* Every behavioural claim cites it, and no amount of software can
close it — ngspice agreeing with the prover is one model checked against
another. This sheet is the smallest bench session that puts hardware evidence
behind three of the library's designs. It needs a multimeter, a bench supply,
a signal generator and an oscilloscope, and about an hour.

The designs are what the generators produce today (rc_lowpass 0.2.3,
voltage_divider 0.1.0, led_indicator 0.1.1). The bands are the Stage 4
proven properties — the sentences a user signs.

#### Procedure

**RC low-pass.** Drive IN with a 1 V sine from a low-impedance source (the
proof assumes an ideal source; a generator's 50 Ω output moves f_c by 1.4%).
Sweep and find the frequency where OUT is 0.707 of IN.
Proven band: **896 Hz – 1.12 kHz**.

## [S28] The earlier research report — headline and fifteen findings
*Sources: reports/Jev decisions for Circuit OS Phase 3.md (verbatim; findings table without its evidence column)*

Use Jev as an **ordinal, stability-tested second opinion on judgment calls that nothing in the codebase can compute**. It can order human work, raise doubt, and pick labels from fixed enums that feed deterministic tables. It must never compute a number, pass a gate, close a defeater, change a grade, sign, approve, or stand in for the owner on a call the owner has reserved. For the owner this means about 9 ready-to-run decision requests: the RS-485 DE/RE pull-down, X7 live pricing, D1 bench timing, D7 verification order, proof `kind`, explainer budget, Stage 6 version bumps, the flaky-test policy, and Phase 3 scope order. **Do not keep the current >0.9 / 0.5–0.9 / <0.5 protocol as written.** It thresholds on `confidence`, which is only the top probability rescaled by option count. It cannot be applied to Nouls at all, and it treats the 0.5–0.95 band as usable when independent studies find that band barely better than a coin. Replace it with bands based on top-probability, margin and cross-variant stability, and make every consultation a committed, re-runnable file. Before any of this, close one real hole: the One-Rule AST scanner does not recognise a TypeSafe client as a model.

| # | Finding | Consequence / fix |
|---|---|---|
| 1 | **One-Rule scanner hole**: `test_llm_cannot_write_circuit_ir.py` recognises a model only via `ai.client:make_client`, `ai.openai_compat:OpenAICompatClient` or `.messages.create`. A TypeSafe/httpx client is invisible, and the scan guards CircuitIR only, not IntentIR, `apply_patch` or `sign_off` | Add the TypeSafe client to `_SEEDS` with a negative-control fixture, plus a mirror rule: no Jev-reaching module constructs `IntentIR`/`PatchOp`/`Claim`/`ValidationCoverage`, touches `REGISTER`, calls `sign_off`, or writes `figure_verifications.json`. **Prerequisite for any Jev code under `backend/`** |
| 2 | **LED decision taken by the agent under 0.5.** The entry's own text said "<0.5 a person should decide". The agent chose the reversible status quo and wrote "the user may overrule", under the user's delegation "give it the whole scenario and then make the decision" | A deviation from the text as written, mitigated by reversibility and disclosure. The later handoff wording legitimises it. Under the new protocol it is labelled `agent_decided_under_uncertainty`, not "decided with TypeSafe" |
| 3 | **Unlisted fourth option inflated both confidences** (LED 0.37→0.44, RC 0.805→0.83) | Record k. Never threshold on `confidence`. Rule-violating options go under `excluded_by_rule` in state, never as labels |
| 4 | No consultation is reproducible (no committed script, state, raw JSON, model string or request id) | `tools/jev/<date>_<slug>.{json,results.jsonl}` committed with the decision entry |
| 5 | **CI never runs on the working branch** (push triggers `main, master, develop`; PRs to `main, master`) and installs `arduino-cli`, while Stage 5 compiles with PlatformIO 6.2.0 | Add `phase2-stage0` (or `**`) and PlatformIO. Until then no CI-side check, Jev or otherwise, ever runs |
| 6 | **Unregistered modules**: 7 backend files absent from `MODULES` (`ai/openai_compat.py`, `core/ir_examples.py`, `data/component_constraints.py`, `db/models.py`, `main.py`, `middleware/rate_limit.py`, `worker.py`). 8 in `MODULES` but not `PLANNED` | Deterministic check plus an allowlist for intentional exclusions. Stage 6 modules are also still unregistered (handoff §8) |
| 7 | **Stale BENCH_D1**: names `led_indicator 0.1.1`, code is `0.2.0` | Regenerate the sheet before any bench session. A version-string drift regex would have caught it |
| 8 | **Gerber Phase 3/4 contradiction**: the Phase 3 KPI is "prompt-to-ordered-PCB within one business day", but Gerber, fab APIs and DFM are Phase 4, while the tech stack says "JLCPCB API (Phase 3+)" | Owner decision: move minimal Gerber forward, or restate the KPI as "routed KiCad board handed to the fab by the user" |
| 9 | **No written Phase 2 exit gate** in the repo. Canonical Phase 2 deliverables (`PRODUCT_MASTER.md:332-344`) deliberately differ from the as-built Stages 0–6, and v2 is not in the repo | "Is Phase 2 done?" is first a definitional owner call (which list governs), then a deterministic checklist. Never a Jev question |
| 10 | **UL 508A is probably the wrong headline standard** for Phase 3 controller boards. UL 60730-1 covers automatic controls. UL 61010-1/-2-201 covers programmable controllers. UL 508A covers the *panel* | Applicability is a liability one-way door for a person. Circuit OS should *flag* candidate families, never assert compliance |
| 11 | Commit convention conflicts ("conventional" vs `session:` vs `brain:`), and `/update-memory` hardcodes `[user folder]/cursor-electronics` | Owner reconciles. Then a regex enforces it |
| 12 | `Claim.kind` has **no computational reader**, `Kind.EMPIRICAL` is never used, and the analytic-vs-empirical reading never weighed the precedence rule v2 > assurance docs | Cheap and reversible, but keeping `analytic` against v2 without a written v2 amendment is a silent precedence violation |
| 13 | The **criterion-12 trigger fires when Phase 3 starts**: "before … a demo to a prospect", and the Phase 3 KPI is "first enterprise contract" | Schedule the external cold read before any sales activity |
| 14 | The first-listed Phase 3 class (DCV) needs a 24VAC→3.3V switching supply. Switching converters and transients are out of Phase 2 scope | A deterministic feasibility filter before any ranking of industrial classes |
| 15 | The old protocol cannot read Nouls (no confidence field), yet the 2026-09-23 entry banded Noul probabilities | Nouls become diagnostics with both-polarity checks, never the governing question |

## [S29] The earlier research report — thirty-three proposed Jev uses
*Sources: reports/Jev decisions for Circuit OS Phase 3.md (verbatim; some table columns dropped)*

Every use below obeys one testable property: **the set of requests that end in an accepted design, closed defeater, signed set, granted waiver or approved price with Jev enabled must be a subset of that set with Jev disabled.** A Jev judgment may make the case look more doubtful. It may queue a human, add a question, refuse a patch, or pick the stricter label. It may never make the case look better.

Owner and engineering decisions (O1–O10):
| Use | Who acts |
|---|---|
| O1 RS-485 DE/RE 10 kΩ pull-down | Owner, all bands. If `d2_drop_is_sound` is not stably ≥ 0.9, no recommendation may claim D2 removal |
| O2 X7 live pricing | Owner, all bands. Default stays static |
| O3 D1 bench timing | Owner. Agent may regenerate BENCH_D1 (finding 7) in any band |
| O4 D7 verification order | Agent prepares the list (fully reversible). Owner sets timing |
| O5 `kind` on exact proofs | Owner holds it. Agent may draft the amendment text |
| O6 Explainer budget | Owner. Needs the owner's cost ceiling in state |
| O7 Stage 6 version bumps | Agent on a stable Act band. A bump makes signed designs 409, so un-bumping is the one-way side |
| O8 Stage 6 status and 5% KPI | Agent with care (reversible scheduling) |
| O9 Flaky accuracy test policy | Agent with care |
| O10 Phase 3 scope order | Owner (sets 6–10 months) |

Runtime and assurance layer (R1–R11), shadow first:
| Use | Allowed effect |
|---|---|
| R1 **Transcription fidelity** (highest value) | Stable low p → return the existing 422-underdetermined shape with a confirm question ("we read 1 kHz — confirm"). Middle → dispatch plus a flag |
| R2 **Patch-op faithfulness** | Refusal as a distinct `JUDGE_DOUBTS_OPERATION`, v(n) kept, user rephrases. Targets the documented swap and unrelated-removal gaps (`intent_patcher.py:38-41`) |
| R3 X5 retry-added fields | Stable low p → underdetermined on that field |
| R4 D5 sign-off doubt hints | Highlight fields as "check this". **Negative-only**: never a "Jev agrees" badge |
| R5 Catalogue-function disagreement | Log, later flag |
| R6 Extra underdetermined questions | May *add* a question |
| R7 Refusal backlog labelling | Orders the Phase 3 backlog (a D4 aid) |
| R8 D7 figure triage | Queue order |
| R9 D3 explanation pre-screen | Regression metric and a pre-fix aid before the scarce human read |
| R10 D9 mutation-target ideas | Becomes a seeded-fault test. The test is the evidence |
| R11 Substitute ordering | Sort order only. Surfaced set identical with Jev on and off |

Phase 3 labels (P1–P8):
| Use | Guardrail |
|---|---|
| P1 `net_role` for generic `digital`/`analog` nets in new industrial generators (0–10 V out, 4–20 mA loop, relay coil, 24 V field input) | The generator-declared role always wins. Cites L2. A runner-up mutation test must change the emitted constraint and be caught |
| P2 `env_label` (pollution degree, overvoltage category, indoor vs field-wired) from the user's description | **Use the stricter of {Jev label, conservative default} for dimensions until the user confirms, in every band** |
| P3 `isolation_needed` when ground-potential difference is undeclared | Anything short of a stable, confirmed "no" → the isolated design, stated as such |
| P4 Standard-family triage (60730 / 61010-2-201 / 508A-panel / none) and "possibly life-safety" | Output worded "flag". A person decides. Life-safety is person-only |
| P5 `component_role` for a library part without a declared role | Private libraries must declare roles. The Jev fallback is flagged |
| P6 DRC waiver triage {cosmetic, needs_review, safety_relevant} | Orders the review queue only. Every waiver is signed by a person. `safety_relevant` forces review at any probability |
| P7 Private-library admission triage {accept, needs_datasheet_check, reject} | Deterministic schema/pin/footprint/provenance checks pass first |
| P8 "Is 4-layer justified?" after 2-layer fails N candidates | Never auto-upgrade. A fab-cost one-way door, so a person confirms |

Dev tooling (T1–T4):
Jev earns four advisory, fail-open slots. **T1** `entry_covers_diff` (Choice), on PRs touching generators, proof, validation, `*_ir.py` or a `VERSION`, after the deterministic check that a new `## [date]` entry exists and `decisions.md` is append-only. It only ever posts a comment. **T2** `failure_class` (Choice) for tracebacks the deterministic classifier cannot match. A retry is allowed only if it says `infra_hiccup` stably and the test is not in an accuracy file, because "an accuracy disagreement never may" be retried (`current_phase.md:463`). Every classification is logged, which builds the diagnosis the flaky test has lacked since 2026-08-23. **T3** `contradicts_derived_fact` (Noul) per prose paragraph against `state.json` excerpts, run weekly or in `/update-memory` Step 5. The output is a to-fix list for a human, never an edit. **T4** `needs_owner_attention` (Choice) as a PR label, never an approval. Budget: one batched request per PR plus one per unmatched failure, a pinned model, and fail-open. None of it matters until finding 5 is fixed, because CI does not run on `phase2-stage0` today.

## [S30] The first live Jev run (2026-09-25) on seven small decision states
*Sources: tools/jev/RESULTS_2026-09-25.md (verbatim)*

#### Jev run — 2026-09-25 (attempt 1)

Model `jev-1.13.0` (pinned; `jev-latest` also resolves to it). Four variants per request: original,
labels reversed, one repeat, and a state-blind control. Raw answers are in `requests/*.results.jsonl`.
Every blind control fell to `need_more_information`, so these answers depend on the stated facts.
The prior was written into each request before the call.

| Decision | Jev (all 3 context variants) | p_top min | margin min | Prior | Band |
|---|---|---|---|---|---|
| RS-485 DE/RE pull-down | `add_as_opt_in_constraint` | 0.79 | 0.68 | same | care → **owner decides** |
| X7 live pricing | `need_more_information` | 0.51 | 0.24 | defer_to_phase3 | **owner** (vendor terms unknown) |
| D1 bench timing | `partial_session_now_without_scope` | 0.57 | 0.32 | build records first | **owner** (Jev ≠ prior) |
| `kind` of exact proofs | `keep_analytic_and_amend_v2_wording` | 0.66 | 0.49 | same | care → **owner decides** |
| Explainer next step | `move_explanation_off_request_path` | 0.69 | 0.56 | same | care → **owner decides** |
| 5% KPI | `defer_with_named_trigger` | 1.00 | 1.00 | same | **act** |
| Stage 6 vs Phase 3 | `finish_in_parallel` | 0.92 | 0.88 | finish_now | **owner** (Jev ≠ prior) |
| Accuracy flake | `diagnose_now_with_N_repeat_runs_seed_logged` | 0.82 | 0.69 | same | **care** |

Diagnostics (Nouls, stable across variants):
- RS-485: `reboot_contention_material` 0.40 (polarity pair sums 1.03–1.04, coherent) and `d2_drop_is_sound` 0.41 — both unsettled, so no recommendation may claim the pull-down removes D2.
- X7: `vendor_terms_known` 0.04, `stage6_gate_needs_live` 0.05 — static pricing meets the Stage 6 gates; `ops_burden` 2.97/3.
- `kind`: `precedence_forces_v2` 0.20, `v2_label_is_deliberate` 0.59 (unsettled), `external_reader_misreads_analytic` 0.28.
- Explainer: `raising_ceiling_alone_meets_target` 0.05 — raising max_tokens alone will not fix latency.

Not run: `pin_support_version_policy` — the deterministic byte-compare over the uncommitted Stage 6
code must come first. Slots only the owner can fill (vendor terms, cost ceiling, v2 and EVIDENCE_CLASSES
text) were stated as unknown in the state, not guessed.

## [S31] Domain facts and formulas
*Sources: brain/knowledge.md; PCB_STRATEGY.md §3 enums*

##### RC low-pass filter
- Cutoff frequency: `f_c = 1 / (2π × R × C)`
- At cutoff: gain = -3 dB (V_out = 0.707 × V_in = 3.536V for 5V AC input)
- Phase 1 reference: R=1590Ω, C=100nF → f_c = 1000 Hz

##### Voltage divider
- V_out = V_in × R2 / (R1 + R2)
- Phase 1 reference: V_in=12V, R1=7kΩ, R2=5.1kΩ → V_out ≈ 5.07V

##### LED current limiting
- I_LED = (V_supply - V_forward) / R_limit
- Typical: V_forward = 2.0V (red LED), I_LED = 20mA → R = (5-2)/0.02 = 150Ω
- Arduino Uno GPIO sink limit: 40mA per pin

---

SignalType values in ir_schema.py: power, ground, digital, analog, i2c_sda, i2c_scl, spi_mosi, spi_miso, spi_sck, spi_cs, uart_tx, uart_rx, rs485_a, rs485_b, pwm, one_wire. ApplicationClass: hobby_arduino, iot_node, industrial_io, hvac_control, modbus_rtu.
