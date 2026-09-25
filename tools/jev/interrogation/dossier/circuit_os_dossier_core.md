# Circuit OS — project dossier (core)

A shorter version of the full dossier: the sections most relevant to open decisions, copied verbatim with the same
stable IDs. Built 2026-09-24 from the Circuit OS repository snapshot (phase2-stage0 at e803a99) and the owner's
handoff of 2026-09-25. Where the dossier does not state something, it is not known here.

Sections: [S01] What Circuit OS is; [S02] Rules nothing may break; [S10] The defeater register D1–D9; [S13] Stage 6 (BOM + substitution) and D7 provenance — uncommitted work in progress; [S20] Open issues; [S21] Decisions the owner holds, and other open decisions (facts and options only).

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
