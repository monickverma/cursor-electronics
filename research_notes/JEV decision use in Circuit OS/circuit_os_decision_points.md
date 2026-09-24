# Circuit OS: Current State and Decision-Point Inventory (for applying JEV)

Scope: internal research on the local repo `/home/user/cursor-electronics` at HEAD `f54752f` (2026-09-17). All sources are repo files cited as `path:line`. "Verified" means the claim comes from derived tracker files (`progress.yaml`, `state.json`) or directly from source code I read. "Prose" means it comes from a hand-written document, which the project's own trust order ranks lowest (`.claude/shared-memory/AGENTS.md:47-60`). I could not run the test suite: `pytest` is not installed in this environment, so no test count here was re-measured by me.

---

## Q1. What is the actual current phase status?

### Takeaway
The repo is **at the start of Phase 2 (Validation Engine), not at the end of it**. Phase 1 closed on 2026-08-25 at 11 of 12 criteria: #11 met by a substitute test, #12 deferred until a named trigger. No Phase 2 tasks have been written yet. The only work since then (2026-09-17) is an AMD/vLLM open-model backend, an AGPL relicense and hackathon slides. Phase 3 is planned only in prose.

### Cited Findings
- `state.json` (derived, generated 2026-08-24 from commit `cec1a25`) reports `phase.current: 2`, `name: "Validation Engine"`, `status: in_progress`, `phase1_status: closed_with_deferral`, 11/12 criteria. — [.claude/shared-memory/state.json:8-17]
- `state.json` reports tests at **425 passed, 0 failed, 22 skipped**. — [state.json test_summary]. The figure is derived and I did not re-run it. The prose files disagree with it and with each other: `PHASE1_COMPLETE.md:50` says 358 passing, `current_phase.md:331` says "expect 318 passed", and `.claude/rules/testing.md` says 171 passed. The rule files and the snapshot documents are stale.
- `phase1_criteria_deferred: [11]` in state.json is a **0-indexed** value. It means criterion 12. `regen_state.py` holds `SUBSTITUTE_CRITERIA = {10}` (criterion 11) and `DEFERRED_CRITERIA = {11}` (criterion 12). — [.claude/shared-memory/tools/regen_state.py:115,127]. This is easy to misread.
- Criterion 12 is rendered `⏭`, and criterion 11 is `✅*` with `met_by_substitute: true`. — [state.json phase1_criteria]
- `plan/current_phase.md` is titled "Current Phase: Phase 2 — Validation Engine" and was last updated 2026-08-25. It holds only the Phase 1 tasks, kept as history, and tells the next planner to "write Phase 2 tasks above this line". **No Phase 2 task list exists.** — [.claude/shared-memory/plan/current_phase.md:1-14]
- `progress.yaml` (generated 2026-08-23) lists 60 entries: 42 verified_done, 18 untested, 0 broken, 70.0% verified. All 18 untested entries are in the PCB engine (`board_ir`, `router`, `kernel`, `render_pretty`) and in `api/routes/pcb`. The PCB route was later tested and shows `verified_done` in state.json. — [.claude/shared-memory/progress.yaml:612-619; state.json modules]
- Modules that state.json lists as **untested / no_test** include `core/config`, `ai/client`, `simulation/monitor`, `tasks/simulation_task`, `api/routes/design`, `api/routes/patch`, `api/routes/simulate` and `db/crud`. — [state.json modules]. These are the routes where most runtime accept/reject decisions are combined (see Q3).
- **No `v0.1.0` git tag exists in the local clone.** `git tag` returned nothing, although `PHASE1_COMPLETE.md:1` is titled "Circuit OS v0.1.0" and its sign-off steps include `git tag v0.1.0` (`PHASE1_COMPLETE.md:168`). — verified with `git tag`
- The last 30 commits (`git log --oneline -30`) are mostly memory and brain bookkeeping, PCB gating (PR #1, `2bd73c8`), the simulation accuracy gate (`c926fe6`) and the ngspice runner race fix (`4ac5f32`). The two newest are `11185ff` "Run on AMD GPUs via vLLM, and license under AGPL-3.0" and `f54752f` "Add lablab submission cover and slides", both dated 2026-09-17.
- `11185ff` adds `backend/ai/openai_compat.py` (227 lines), `AI_PROVIDER=openai_compat`, `scripts/amd_benchmark.py` (it reports the valid-IR rate, model calls per prompt and latency), `docs/AMD.md` and `tests/test_openai_compat.py`. — [git show --stat 11185ff; docs/AMD.md:1-24,87-94]. This work was **not recorded in `brain/decisions.md`**, and state.json predates it, so the trackers do not reflect it.
- `brain/vision.md:53,66` still says "Current Phase: Phase 1 … 10/12 criteria done". `master_plan.md:24-25` still says Phase 1 is "🔄 10/12" and Phase 2 is "⬜ Not started". — prose, stale.
- The flaky-test incident: `brain/timeline.md` records that on 2026-08-23 one accuracy test was flaky (409/1 vs 410/0) and that the tag was "not until it is reproducible". Commit `4ac5f32` "ngspice runner discarded its own errors and raced its output file" appears to address it. — [.claude/shared-memory/brain/timeline.md (tail); git log]

### Inferences
- The requested framing ("end of Phase 2 / start of Phase 3") does not match the repo. Phase 2 was opened in name on 2026-08-25, but none of its deliverables have been started. The one Phase-3-flavoured asset that exists is the experimental PCB engine, which was built early.
- The trackers' own rule ("register it in both trackers in the same commit", `AGENTS.md:68`) was not followed for `ai/openai_compat.py`. It is the same failure mode the project has already hit twice.

### Gaps
- I could not re-run `pytest` because the module is not installed, so 425/22 is unconfirmed.
- I cannot tell whether `v0.1.0` was tagged on the remote and not fetched, or never tagged.
- No benchmark output exists in `docs/benchmarks/`, so the open-model valid-IR rate is unknown.

---

## Q2. What does Phase 2 contain, what is left, and what exactly is planned for Phase 3?

### Takeaway
Phase 2 (the Validation Engine) is all still to do. Its scope is free-form generation, ESP32/STM32, live BOM, Qdrant RAG, waveforms, version history and component substitution, and it comes with three sequencing warnings. Phase 3 (the Industrial Layer) is planned as: integrate freerouting (do not extend the A* engine), build a **constraint layer** (net classes, differential pairs and keepouts, each with a plain-English reason) as the differentiator, KiCad wire routing, and industrial rule libraries (HVAC/DCV, RS-485 optoisolation, UL 508A). Only `to_dsn()` exists toward any of this.

### Cited Findings
- Canonical Phase 2 deliverables: free-form generation (15 templates total), ESP32 and STM32 firmware, live BOM pricing with a nightly cache, version history with a timeline UI, Qdrant RAG over 500 datasheet excerpts, a Plotly waveform viewer, and a component substitution engine. KPIs: 3 paying pilot teams, IoT node design in under 45 minutes, BOM accuracy within 5%. — [PRODUCT_MASTER.md:332-344]
- Phase 2 has an entry condition, criterion 12, which was later relaxed into a trigger. — [plan/master_plan.md:106-110; brain/decisions.md:429-452]
- Three sequencing risks are recorded against Phase 2: (1) do analog last, because it is "a different validation problem, not an increment"; (2) **free-form generation needs a low-confidence / "out of my depth" signal**; (3) the BOM 5% KPI needs a human engineer. — [brain/decisions.md:376-382; ROADMAP.md:162-179; master_plan.md:123-137]
- Canonical Phase 3 deliverables: DCV board generation, kitchen hood controllers, refrigeration control (EEV, superheat, defrost), RS-485 I/O with optoisolation (PC817), UL 508A flagging and safety-class enforcement, "PCB auto-layout via KiCad freerouting (basic, 2–4 layer)", private component libraries, and an audit trail (ISO 13485/26262). KPIs: first enterprise contract, prompt-to-ordered-PCB within one business day. — [PRODUCT_MASTER.md:346-359]
- The Phase 3 PCB approach was settled on 2026-08-22: "integrate freerouting rather than extending the A* engine, and treat the constraint layer — net classes, differential pairs and keepouts derived from SignalType and ApplicationClass, each carrying a plain-English reason — as the differentiating deliverable." — [brain/decisions.md:369-374; master_plan.md:165-180]
- KiCad schematic wire routing (instead of net labels) is slated for Phase 3. — [brain/decisions.md:84-91]
- Source documents conflict on where the constraint layer belongs. `PCB_STRATEGY.md` §8 puts "constraint layer as a first-class output. Annotated viewer. Designer-facing export" in **Phase 2** and semantic placement in Phase 1 (`PCB_STRATEGY.md:265-276`). `brain/decisions.md:369-374` and `ROADMAP.md:151-160` put it in **Phase 3**. `PHASE1_COMPLETE.md:159` still lists "Two documents describe different Phase 2s … unreconciled", even though decisions.md says the question was resolved.
- The PCB_STRATEGY build order is: semantic placement rules (decoupling caps next to power pins, connectors at the edge, TVS at the entry, transceivers next to connectors, crystals, analog/switching separation, thermal spread), then constraints as an artifact (extend `to_dsn()`), then the annotated viewer. Routing quality is "not yet". — [PCB_STRATEGY.md:200-245]
- PCB_STRATEGY lists five named ways the strategy could be wrong: layout quality may be the real buying trigger, Quilter/Flux may ship intent-aware constraints, HVAC buyers may want finished boards, "how near" constraints are a hard engineering problem, and semantic rules may not generalise past the templates. Each comes with a proposed test (e.g. "show two hobbyists…", "ask three real HVAC controls people"). — [PCB_STRATEGY.md:280-304]
- A Specctra DSN exporter for freerouting already exists: `to_dsn(board)`, whose docstring gives the freerouting docker invocation. SES import is described but not implemented. — [backend/pcb_engine/router.py:499-507]
- Carried-forward limitations: criterion 12 unmet, criterion 11 validated against mathematics only, Celery `--pool=solo`, SOIC-8 pins assigned arbitrarily (MAX485 has the wrong pins), PCB routing quality unmeasured. — [PHASE1_COMPLETE.md:149-159]
- `ROADMAP.md` Steps 1 (send criterion 12 outreach), 2 (PCB scope) and 3 (tag) are still marked ⬜ in a file dated 2026-08-22. Step 2 was completed later. — [ROADMAP.md:33-74]

### Inferences
- The largest unmade Phase 2 decision is how free-form generation will decide it is out of its depth. `Component.confidence` exists but is never used to gate anything (see Q3). This is a natural first target for a typed decision tool.
- The constraint layer is by design a set of typed, reasoned decisions (constraint + reason + source signal type). It matches the shape of a structured decision record directly.

### Gaps
- There is no Phase 2 task breakdown, timeline or owner assignment in the repo.
- There is no Phase 3 design document beyond PCB_STRATEGY prose. I found no schema for constraints and no freerouting integration code beyond `to_dsn`.

---

## Q3. Runtime decision points inside the product

### Takeaway
There are about 20 runtime decision points. The LLM makes the **consequential design choices**: topology, parts, values, which validation rules apply, what the simulation should expect, patch contents and the explanation text. Deterministic code then **accepts or rejects** that output, but only in narrow places. The retry loop gates on the Pydantic schema plus `validate_ir`. The rule engine, the simulation grade and confidence scores are advisory only and never block persistence or delivery. Several gates are quietly self-referential: the LLM chooses which rules to run and what values the grader checks against.

### Cited Findings: decision-point inventory

Legend: **LLM** = model decides; **DET** = deterministic code decides; **Typed** = output validated against a schema/type.

| # | Decision point (file:line) | What is decided | Inputs → outputs | LLM/DET | Typed? | Failure modes / uncertainty |
|---|---|---|---|---|---|---|
| R1 | Intent parse, `backend/ai/intent_parser.py:97-107` (tool `_EXTRACT_TOOL` :28-70, prompt :12-26) | application_class, safety_class, target_mcu, constraints, primary_sensor, use_rs485, has_relay | prompt str → `DesignSpec` | LLM (forced tool_use) | **Partly.** The JSON schema has enums, but `DesignSpec` (:73-90) is a plain class with **no Pydantic validation**; `constraints` is a free dict | Misclassification propagates. `safety_class` is stored but never enforced downstream (only `db/crud.py:44`). No retry and no confidence |
| R2 | Constraint injection, `circuit_reasoner.py:83-92` | Which component datasheet constraints are shown to the LLM | `spec.primary_sensor`, `spec.use_rs485` → prompt text | DET | n/a | Only the primary sensor and MAX485 are ever looked up. The dict has about 17 parts (`data/component_constraints.py:7-245`). Other parts get "(no specific constraints loaded)" |
| R3 | Circuit generation, `circuit_reasoner.py:82-178` (tool schema = `CircuitIR.model_json_schema()` :63-67; prompt :35-61) | Topology, all components, part numbers, values, nodes, connections, `validation_rules`, `simulation_spec.expected_outputs`, per-component `confidence` + `justification` | `DesignSpec` → `CircuitIR` | LLM | **Yes**, Pydantic `CircuitIR` (`core/ir_schema.py:140-178`) | Hallucinated parts and values that are schema-valid pass. **There is no template gating in code**: a grep for `TPL_`/`template` in `backend/ai` and `backend/api` finds nothing, although the docs say generation is limited to 5 templates (`PHASE1_COMPLETE.md:144-145`) |
| R4 | Retry / accept-reject loop, `circuit_reasoner.py:100-178` | Accept IR, re-prompt with a correction, or give up | raw dict → IR or `CircuitGenerationError` | DET gate | Yes | MAX_ATTEMPTS=3 (:28). APIError is not retried (:147-149). JSON/KeyError (:151-159), Pydantic ValidationError with field paths (:161-168; formatter :220-225), and `validate_ir` failure via ValueError (:170-176) are each re-prompted. Truncation at `max_tokens` fails fast rather than retrying (:118-125, budget 8192 :33). **The hardware rule engine is not in the loop** |
| R5 | Spec→IR field override, `circuit_reasoner.py:129-136` | Whether spec fields overwrite LLM fields | `setdefault` only fills missing values | DET | — | The LLM value wins over the parsed spec when both are present |
| R6 | Structural validation, `backend/core/ir_validator.py:36-104` | Connection ref integrity, orphan nodes (error) and 1-connection nodes (warning only), component voltage rating vs `constraints.supply_voltage` (default 5.0), I2C pull-ups | IR → `IRValidationResult` (dataclass, severity critical/warning) | DET | Dataclass, not Pydantic | The floating-node check is a *warning* at count==1 (:67-71), so the documented "≥2 connections" rule is not blocking. The voltage check skips parts with `supply_voltage_max=None`. The default supply 5.0V is assumed |
| R7 | Rule engine, `backend/validation/rule_engine.py:39-51` | Which hardware rules run, and pass/fail | IR → `IRValidationResult` | DET checks, but the **rule selection is LLM-chosen** (`ir.validation_rules`, :47) | Enum `ValidationRule` (`ir_schema.py:62-72`) | Only **3 of 10** enum rules have handlers: RS-485 termination (:55-86), bias (:90-120), Uno PWM pins (:124-141). `CURRENT_LIMITS_OK`, `OPERATING_TEMP_RANGE`, `POWER_SUPPLY_ADEQUATE`, `PULLUP_ON_OPEN_DRAIN` and the others silently no-op. If the LLM omits a rule from `validation_rules`, that rule never runs. An out-of-range termination value is only a warning (:71-78) |
| R8 | Post-generation gating, `backend/api/routes/design.py:92-140` | Whether the design is persisted and returned | val + rule results → response | DET | Response is a Pydantic model | **Rule-engine errors do not block**: the design is saved (:118) and returned with `validation.passed=false`. Firmware exceptions are swallowed (:101-104), explainer failures are swallowed (:111-115), and the explainer receives only `val_result`, not `rule_result` (:113) |
| R9 | Firmware template choice, `backend/generators/firmware/arduino.py:29-40` | modbus / dht sensor / led / base template | IR heuristics (transceiver present, DHT in part number, LED-only) | DET | — | Falls back to `base.ino.j2` with a "No specific template matched" comment (:182). Pin mapping uses name heuristics (e.g. node id contains "ALERT"/"RELAY", :93) |
| R10 | SPICE netlist decisions, `backend/generators/netlist/spice.py:44-193` | Element models, defaults, tie-downs, analysis mode | IR → netlist | DET | — | **Silent defaults**: a resistor without a value becomes 1kΩ (:154), a capacitor becomes 100nF (:162). MCU = 100Ω (:183-185). Sensor load comes from current_draw (:190). 1GΩ tie-down on floating nodes (:107). These can mask LLM omissions |
| R11 | Simulation dispatch, `design.py:126-131`; `patch.py:121-123` | Whether to simulate | `ir.simulation_spec` present (LLM-authored); for patches also `changes` non-empty | DET on LLM data | — | No simulation spec → no simulation, and nothing flags it |
| R12 | Simulation grading, `backend/simulation/grader.py:27-47` (tolerance :14; AC closest-point :58-66) | pass/fail per expected node | `SimulationData` + `ir.simulation_spec.expected_outputs` → `GradeResult` | DET, but the **expected values are LLM-authored** | Dataclass | Passes automatically when no expected outputs exist (:28-29). 15% tolerance: a 5% netlist error passes silently (`PHASE1_COMPLETE.md:67-69`). AC is evaluated at the nearest sweep point to `constraints["cutoff_hz"]` |
| R13 | Grade persistence on poll, `backend/api/routes/simulate.py:86-102` | Write `simulation_passed` back to IR | on GET poll | DET | — | Grading only happens when a client polls. Every exception is swallowed (`except Exception: pass`, :101-102). The parser receives empty stderr (:90) |
| R14 | Sim monitor launch gate, `backend/simulation/monitor.py:122-140`; recorder `tasks/simulation_task.py:39-47` | ≥90% success over ≥5 runs per circuit type | `sim_monitor.jsonl` | DET | Dataclass | `success=True` means ngspice ran and parsed, **not that the grade passed**. The module is untested (state.json) |
| R15 | Patch generation, `backend/ai/patcher.py:105-117` (prompt :26-39, tool :41-75) | Which component fields change, to what | IR summary + command → `PatchResult` | LLM (forced tool_use) | **Weak.** `field` is a free string and `new_value` is "any JSON type" (:60-64) | The summary sent to the LLM contains only id, part number, type and value (:119-127). Adding components is impossible (returns `[]` + note) |
| R16 | Patch application, `patcher.py:85-98` | Apply or skip each change | changes → new IR (version+1) | DET | **No re-validation**: `model_copy(update=…)` bypasses Pydantic (:96) | Unknown component_id or empty field is **silently skipped** (:94-95). A test pins this behaviour (`tests/test_patcher.py:266`), although the plan asked for rejection (`current_phase.md:110`). An invalid type or unknown field name can enter the IR |
| R17 | Post-patch gating, `backend/api/routes/patch.py:84-117` | Persist the patched IR | val + rules → response | DET | — | Validation errors **do not block** the save (:105). The patch record is persisted regardless |
| R18 | Explanation, `backend/ai/explainer.py:50-63` (prompt :21-43) | Report content, including "what breaks if wrong" | IR + validation (+ optional sim) → str | LLM, **raw text, no tool_use** | **No** | Breaks the project's "tool_use only" rule (`.claude/rules/code-style.md`). Only keyword checks exist (`current_phase.md:125-127`). No external validation (criterion 12). Confidence is shown to the model (:81) but not acted on |
| R19 | BOM matching / pricing, `backend/generators/bom/compiler.py:25-36` (lookup :139-199) | Which DB entry prices each part | IR component → row with `price_source`, `price_known`, `confidence` (:274) | DET | Dict rows | 5-step cascade: exact PN → LCSC → prefix (returns None if ambiguous) → category+value (cheapest) → `price_known=False`. Component *selection* itself is the LLM's (R3) |
| R20 | AI provider choice, `backend/ai/client.py:32-60`; `core/config.py:24` | anthropic vs openai_compat (vLLM) | env | DET config | pydantic-settings | Changes how reliable R1/R3/R15 are. Open models are "more likely to invent a pin" (`docs/AMD.md:12-15`). `ai/client` is untested |
| P1 | PCB engine gate, `backend/api/routes/pcb.py:65-70`; `core/config.py:42-74` | Endpoint enabled or 501 | `PCB_ENGINE_ENABLED` / `environment` | DET | — | On in dev, off in prod (decisions.md:409-413) |
| P2 | Footprint inference, `backend/pcb_engine/footprints.py:194-209`; skip in `compile_board.py:43-79` | Package for each part, or skip | MPN/package regex rules → package or None | DET | — | "None when unsure — never a guess". Skipped parts become warnings. Before 2026-08-22 this dropped every 0402 part (ROADMAP.md:98-121). SOIC-8 pinmap is arbitrary |
| P3 | Placement, `compile_board.py:121-160` | Grid position per part | greedy, pad-count order, minimum added wirelength | DET | — | Optimises wirelength only and ignores SignalType/intent (PCB_STRATEGY.md:13-18, 99-102) |
| P4 | Candidate selection, `router.py:462-497` (sort ~:490); `compile_board.py:190`; weights `kernel.py:231-243` | Which routed layout wins | n seeded A* runs → sorted by `Score.total` | DET, **hand-tuned weights** | Dataclass `Weights` | Weights: unrouted=1000, drc_error=250, drc_warning=15, via=2, length_mm=0.4, layer_used=60, skew_mm=30. Arbitrary and untested (`kernel`, `router` untested per progress.yaml:450-531) |

### Cited Findings: other facts
- `Component.confidence` (`ir_schema.py:90`, `Field(ge=0.0, le=1.0)`) is only ever *read* by the explainer prompt (`explainer.py:81`) and the BOM row (`compiler.py:274`). A grep across `backend/` finds no threshold or gating logic that uses it. — verified by grep
- `SafetyClass` (`ir_schema.py:56-59`) is produced by the intent parser and stored (`db/crud.py:44`), but no rule reads it. — verified by grep
- The PRODUCT_MASTER vision describes automatic remediation ("If simulation says a component will overheat, the system automatically swaps it for a better-rated alternative and re-simulates"). **This does not exist.** Simulation results never feed back into generation. — [PRODUCT_MASTER.md:74-83; design.py:124-131]
- PRODUCT_MASTER says the reasoner "Selects circuit topology from the topology library". No topology library exists in code. — [PRODUCT_MASTER.md:245]
- The criterion 11 test found that the 15% grader accepts a 5% netlist error that the 2% analytical gate catches (13/34 tests fail). — [current_phase.md:183-185]

### Inferences
- The accept/reject boundary for LLM output is **schema + four structural checks**, and nothing more. Everything "physics-validated" happens after the design is already accepted and persisted, and it is advisory.
- Three decisions let the LLM grade its own work: which validation rules apply (R7), what the simulation should output (R12), and whether to simulate at all (R11). These are strong candidates for a structured, auditable decision layer, for example deriving required rules and expected outputs deterministically from the IR topology.
- There is no "out of my depth" signal. `confidence` is declared and populated but never used, which is exactly the gap that decisions.md:379-380 flags for Phase 2.

### Gaps
- I did not read `openai_compat.py`, `kicad.py`, `parser.py` or `db/crud.py` line by line. There may be more minor decision points in them.
- There is no runtime data on how often each retry branch fires. `amd_benchmark.py` would measure this, but no results are committed.

---

## Q4. Process and engineering decisions: logged, open and pending

### Takeaway
The project already has a disciplined, append-only decision log with decision, reason, rejected alternatives and date. It contains 20 entries. The open items are: criterion 12 (deferred with a trigger), the bench test owed for criterion 11, tracker auto-discovery (deferred), rate limiting per user rather than per IP, SOIC-8 pinmaps, the Celery solo pool, and the unwritten Phase 2 plan. It also has well-formed but untested strategic hypotheses (PCB_STRATEGY §9).

### Cited Findings: logged decisions (`.claude/shared-memory/brain/decisions.md`)
- 2026-06-01, architectural invariants: the LLM writes JSON only (:8-21); tool_use only (:25-33); ngspice, not LTspice, "Non-negotiable" (:37-46); Jinja2 firmware (:50-58); Celery for simulation (:62-69); a static constraints dict instead of Qdrant (:73-80); KiCad net labels, with wire routing in Phase 3 (:84-91); bcrypt directly (:95-101); no in-memory storage (:105-112).
- 2026-06-02, operational: OpenRouter base_url (:116-125), ngspice `-o` flag on Windows (:129-140), AC magnitude = sqrt(re²+im²) (:144-154), multi-table AC parser (:158-168), Celery `--pool=solo` (:172-180), SoftwareSerial for Modbus on Uno (:184-192), `.env` path (:196-204). **IP-based rate limiting, with a note that production should key on user ID. This is still open** (:208-218).
- 2026-08-07: criterion 11 changed from the bench test to an analytical cross-check at 2% and labelled `met_by_substitute`. "When lab access becomes available, run the original bench test." (:222-249). Trackers now require explicit module registration; **auto-discovery is deferred** (:253-274).
- 2026-08-22: phase gating targets visibility, not timing, through four conditions (:278-307). Criterion 12 moved off the v0.1.0 gate, and using the agent panel as a substitute was explicitly rejected (:311-341). PRODUCT_MASTER.md is canonical, Phase 2 is the Validation Engine, Phase 3 integrates freerouting and builds the constraint layer, and three Phase 2 risks are recorded (:345-382). PCB engine option (b): experimental and labelled; "Not settled by this: routing quality" (:386-425).
- 2026-08-25: criterion 12 deferred with the trigger "before the first external user is shown a generated explanation … public launch, a demo to a prospect, or onboarding anyone outside this repo" (:429-452). Phase 2 renamed to Validation Engine in `regen_state.py` (:460-465).
- **Not logged:** the 2026-09-17 decisions to add an open-model provider (vLLM/AMD) and to relicense under AGPL-3.0 (commit `11185ff`). The project's own rule says "New scope is written into `brain/decisions.md` when it starts" (ROADMAP.md:212-213).

### Cited Findings: launch gates and criterion reviews
- The 12 Phase 1 criteria are owned by `regen_state.py` `PHASE1_CRITERIA` and rendered in state.json. Criteria 8 ("20 prompts") and 9 were manual one-offs on 2026-06-02; criterion 8 had "6 fully verified, remainder rate-limited". — [PHASE1_COMPLETE.md:35-48]
- The criterion 12 protocol: three EE-literate reviewers read a DHT22 explanation cold. PASS requires rubric rows 2 (consequence of omission) and 3 (consequence of wrong value) to be stated unaided by at least 2 of 3 reviewers. — [CRITERION_12_REVIEW.md:80-102]
- `scripts/review_panel.py` is an LLM-agent pre-screen with an ablation: arm A sees the explanation, arm B sees only the schematic and BOM. Each rubric row is tagged FROM_TEXT or PRIOR_KNOWLEDGE, and the A−B gap measures whether the explanation is "load-bearing". Its docstring says it cannot close criterion 12. — [scripts/review_panel.py:1-45]
- `SimulationMonitor.check_launch_gate(min_rate=0.90, min_runs=5)`. — [backend/simulation/monitor.py:122-140; .claude/rules/testing.md]
- The testing.md launch checklist (12 unchecked boxes, including "Simulation accuracy gate passed (bench vs ngspice within 15%)") is stale relative to the amended gates. — [.claude/rules/testing.md]
- Phase 1 KPIs in PRODUCT_MASTER that nobody tracks: 100 beta users and 3 "it caught my mistake" testimonials. — [PRODUCT_MASTER.md:329; master_plan.md:47-51]

### Cited Findings: open questions and pending trade-offs
- Criterion 12 is deferred and has not been done. ROADMAP Step 1 (send the outreach) is still ⬜. — [ROADMAP.md:33-42]
- The criterion 11 bench measurement is still owed. — [decisions.md:243-249]
- SOIC-8 per-part pinmaps are unfixed. — [PHASE1_COMPLETE.md:125-128]
- Routing quality: freerouting in Phase 3 rather than testing the A* engine. — [decisions.md:422-425; current_phase.md:301]
- Celery `--pool=solo`, "revisit at concurrency". — [PHASE1_COMPLETE.md:155]
- The PCB engine runs in-process, which "violates the spirit" of the Celery rule. "If layout times grow, revisit." — [MENTAL_MODEL.md:235-237]
- The BOM 5% KPI needs a manual engineer: "Line someone up early or rewrite the KPI." — [ROADMAP.md:176-179]
- PCB_STRATEGY §9 has five falsifiable hypotheses with suggested experiments. — [PCB_STRATEGY.md:280-304]
- PCB_STRATEGY §4 notes the "designer" audience step should be a credibility play, not revenue: "If you are counting on designer seat revenue, reconsider." — [PCB_STRATEGY.md:148-164]
- Regulatory, commercial and legal: AGPL-3.0 licensing (commit `11185ff`) against enterprise and Team-tier plans (`PRODUCT_MASTER.md:476-498`). I found no document discussing this trade-off.

### Inferences
- The decision log is already structured enough (decision / reason / alternatives rejected / date / consequence) to map onto a typed decision record. What it lacks is explicit criteria weights, confidence, and a review trigger for every entry. Only criterion 12 has a trigger.
- Recurring decision patterns that could be templated: "gate depends on an unavailable external resource → substitute or defer with a trigger" (criteria 11 and 12, the BOM KPI), and "undeclared scope → (a) tested / (b) experimental / (c) out of scope" (PCB engine).

### Gaps
- No decision document covers the vLLM/AMD provider or the AGPL license.
- There are no written criteria for choosing among Phase 2 deliverables, only the three sequencing warnings.

---

## Q5. Where does typed / structured-output infrastructure already exist for a typed decision tool to plug into?

### Takeaway
There is strong existing infrastructure: a Pydantic v2 `CircuitIR` with enums, used as the tool_use JSON schema for generation; forced tool_choice on three of the four LLM calls; field-path error feedback in the retry loop; dataclass validation results with severity; and enum-keyed rule dispatch. The weak spots are the untyped `DesignSpec` and `PatchResult`, the raw-text explainer, and validation-result dataclasses that are not Pydantic.

### Cited Findings
- `CircuitIR` and its submodels (`Component`, `Node`, `Connection`, `SimulationSpec`, `PatchRecord`) plus the enums `ComponentType`, `SignalType`, `ApplicationClass`, `SafetyClass` and `ValidationRule`. `Component.confidence` is bounded [0,1] and `justification` has a minimum of 20 characters. — [backend/core/ir_schema.py:10-178]
- `CircuitIR.model_json_schema()` is passed directly as the tool `input_schema`. — [circuit_reasoner.py:63-67]
- Forced `tool_choice` is used in the intent parser (`intent_parser.py:97-106`), the reasoner (`circuit_reasoner.py:102-109`) and the patcher (`patcher.py:105-117`). **It is not used in the explainer** (`explainer.py:57-63`).
- Pydantic errors are converted to field-path feedback (`circuit_reasoner.py:220-225`), and correction turns are appended as a tool_result (:195-217).
- `IRValidationError(field_path, message, severity)` / `IRValidationResult` are dataclasses. — [ir_validator.py:13-33]
- `HardwareRuleEngine._HANDLERS` is keyed by the `ValidationRule` enum. — [rule_engine.py:39-43]
- `GradeResult` (dataclass) — [grader.py:17-21]; PCB `Weights`/`Score` (dataclasses) — [kernel.py:231-260]
- The provider abstraction maps an OpenAI-compatible backend onto the Anthropic SDK surface. vLLM guided decoding enforces the tool schema. — [ai/client.py:32-60; docs/AMD.md:16-18,87-92]
- Persistence of the IR as JSON plus a patch record (`record_patch` with from/to version and the change JSON) — [api/routes/patch.py:105-113]; `PatchRecord` model — [ir_schema.py:132-137]
- Derived-state tooling (`regen_state.py`, `progress_gen.py`) produces machine-readable status. — [AGENTS.md:114-125]

### Inferences
- Natural insertion points for a typed decision tool:
  - (a) Replace `DesignSpec` with a Pydantic model.
  - (b) Add a typed "generation decision" or "out-of-depth" verdict next to R3/R4 that uses the unused `confidence`.
  - (c) Make rule selection and `expected_outputs` deterministic, or record them as typed decisions, rather than letting the LLM author them.
  - (d) Give the explainer a structured tool schema (per-component `why`, `what_breaks`, `uncertainty`) so criterion 12's rubric rows can be checked structurally.
  - (e) Model Phase 3 constraints as typed records carrying a reason.
  - (f) Convert `brain/decisions.md` entries into typed records with triggers.
- `PatchResult.apply_to` bypassing validation (R16) is where typed checks are cheapest to add, and a missing check there is most likely to corrupt data.

### Gaps
- I found no internal documentation of "JEV" or typesafe.ai in the repo. Any fit assessment against JEV's actual API has to be done separately.
