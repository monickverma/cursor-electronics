# Put Jev beside the gates, never inside

Use Jev as an **ordinal, stability-tested second opinion on judgment calls that nothing in the codebase can compute**. It can order human work, raise doubt, and pick labels from fixed enums that feed deterministic tables. It must never compute a number, pass a gate, close a defeater, change a grade, sign, approve, or stand in for the owner on a call the owner has reserved. For the owner this means about 9 ready-to-run decision requests: the RS-485 DE/RE pull-down, X7 live pricing, D1 bench timing, D7 verification order, proof `kind`, explainer budget, Stage 6 version bumps, the flaky-test policy, and Phase 3 scope order. In the product, the two most valuable places are the two gaps the project records as open with "no local fix": prompt→IntentIR transcription fidelity (`design.py:106`) and patch-op faithfulness (`intent_patcher.py:38-41`). At both, Jev may only turn "accept" into "ask the user", never the reverse. In Phase 3, Jev fits about eight classification slots (net role, install environment, isolation, standard-family triage, waiver and library-part triage) and none of the numeric ones. **Do not keep the current >0.9 / 0.5–0.9 / <0.5 protocol as written.** It thresholds on `confidence`, which is only the top probability rescaled by option count. It cannot be applied to Nouls at all, and it treats the 0.5–0.95 band as usable when independent studies find that band barely better than a coin. Replace it with bands based on top-probability, margin and cross-variant stability, and make every consultation a committed, re-runnable file. Before any of this, close one real hole: the One-Rule AST scanner does not recognise a TypeSafe client as a model. **No live Jev call could be made for this research.** api.typesafe.ai and the docs were blocked and no key was available, so every request in the appendix is a draft to run on the owner's machine, and this report contains no Jev outputs except those already recorded in `decisions.md`.

*Evidence base and limits.* The code evidence is the snapshot `p2/` = `origin/phase2-stage0` at **e803a99**. That is one commit behind 94b61c1 ("D2 derived") and **without** the uncommitted D7/Stage 6 work (`data/parts.py`, `data/figures.py`, `validation/figure_audit.py`, `generators/bom/substitution.py`, `scripts/verify_figures.py`). For those files this report relies on the owner's handoff of 2026-09-25. `PHASE_2_PLAN_v2.md`, `EVIDENCE_CLASSES.md` and `ARCHITECTURE_ASSURANCE_CASE.md` are not in the repo, so every request that depends on their text has a `<PASTE>` slot. Repo citations are `file:line` in the snapshot. Jev API facts come from the first-party `typesafe-sdk` 0.7.1 wheel ([PyPI](https://pypi.org/project/typesafe-sdk/)). Behavioural evidence comes from independent GitHub studies run in the two weeks after launch, mostly by one person each. The evidence is useful but thin, and some of it conflicts.

## Jev weighs consequences you already computed; its numbers are not probabilities of being right

Jev has one decision endpoint, `POST /v1/systemone`. A request carries one `state` (text or JSON) and a map of named questions. Each question is a **Noul** (P(yes)), a **Choice** (one label from a fixed, described set) or a **Score** (an ordered rubric starting at 0). The answer is numbers only: **no rationale, no sampling controls, no seed** ([typesafe-sdk 0.7.1](https://pypi.org/project/typesafe-sdk/), `_schemas/models.py:10-160`). Three wire facts shape everything below. First, **a Noul answer has no `confidence` field**, so a protocol keyed on confidence cannot be applied to Nouls. The 2026-09-23 entry nonetheless read Noul probabilities against the confidence bands. Second, the response's `model` "may differ from the alias supplied". The build string has already drifted from `jev-1.13.0` ([RINNECODER](https://github.com/RINNECODER/jev-behavior-study)) to `jev-1.13-20260917` ([priorbench](https://github.com/priorbench/jev)). A decision record must therefore store the returned model and the `x-typesafe-request-id`, not the requested alias. Third, the SDK default is the moving alias `jev-latest`, so an unpinned call cannot be reproduced.

**Choice `confidence` is not a separate uncertainty signal.** It is c = (k·p_max − 1)/(k − 1), the top probability normalised against a uniform prior over k options ([xxlya/evaljev](https://github.com/xxlya/evaljev); pre-registered test catalogued at [awesome-jev-robustness](https://github.com/Yifan-Lan/awesome-jev-robustness)). The two research notes that examined this agree on the formula. The project's own numbers confirm it with an unwelcome twist. `rc_option` (p = 0.87/0.13/0.00, recorded conf 0.83) and `led_option` (p = 0.58/0.36/0.06, recorded conf 0.44) fit the formula **only with k = 4**: 0.827 and 0.44. With the three options the log lists, the values would be 0.805 and 0.37 (`decisions.md:1446-1452`). So each Choice almost certainly had a **fourth, unlisted, near-zero option that inflated the recorded confidence**. It did not change a band this time. But a dead option can push a borderline answer across 0.9 with no change in the model or the facts. The same arithmetic produces a paradox for the current protocol: adding the `need_more_information` option that every good request should carry *raises* confidence for the same p_max.

Calibration depends on the domain. On support routing, pre-registered ECE was 0.075. On random 3-SAT the model said "satisfiable" almost regardless of the formula, and it gave P = 0.38 to `x AND NOT x` ([willkelly/jev-evaluation](https://github.com/willkelly/jev-evaluation)). Stated Choice confidence of 91.4% matched 76.1% actual accuracy, and **the 50–95% band was only 50–57% correct** ([AnthusAI/Jev-Calibration](https://github.com/AnthusAI/Jev-Calibration)). A 5,721-call pre-registered study found accuracy flat from 0.50 to 0.95, jumping only at 0.99: "gate at 0.99 or not at all" ([priorbench/jev](https://github.com/priorbench/jev)). A Noul and a two-option Choice asking the same thing differ by 0.125 on average, and P(x) + P(¬x) ranges from 0.71 to 1.42 ([jujumilk3](https://github.com/jujumilk3/jev-calibration-audit)). The LED answers show exactly this: P(exact_now) = 0.36 in the Choice against 0.47 in the matching Noul. The biggest lever is wording. Rewriting criteria moved accuracy from 70% to 96% ([RastislavDujava](https://github.com/RastislavDujava/jev-classification-prompting)). Removing the abstain option took accuracy on unanswerable items from 0.95 to 0.00 while confidence stayed at 0.79 ([jujumilk3](https://github.com/jujumilk3/jev-calibration-audit)). Authority cues ("the council concluded…") succeeded as attacks on 147 of 200 items ([willkelly](https://github.com/willkelly/jev-evaluation)). The evidence on option order conflicts: 88.0% vs 57.4% on arithmetic ([RINNECODER](https://github.com/RINNECODER/jev-behavior-study)), but 0 of 400 argmax flips on classification ([jujumilk3](https://github.com/jujumilk3/jev-calibration-audit)). That conflict is itself the reason to counterbalance.

For Circuit OS the implication is sharp. Its questions carry mA, mW, Ω and tolerance bands, which is Jev's documented failure zone. The 2026-09-23 decisions held up because the agent computed the physics itself (0 of 36 designs changed, exact dissipation figures) and gave Jev only values to weigh: reversibility, user impact, effort. **That split should become a written rule: tools compute, Jev weighs.** No independent evaluation of Jev on electronics or engineering-policy content exists. For rare one-off design decisions there are no labels to recalibrate against, so the only honest reading of a Jev answer is ordinal and stability-tested. *(Reconciliation: the Phase 3 note says "no independent calibration study exists". That came from an older note and is superseded by the calibration studies cited above. What does not exist is calibration on this domain.)*

## Fifteen findings the research surfaced, four of them about Jev itself

Four consultations are recorded in the snapshot. Only one, the 2026-09-23 RC swamping + LED bound, has questions and numbers, and none can be re-run from the repo. The script `typesafe_rc_led.py` lived in a session scratchpad. The two 2026-09-21 "TypeSafe passes" on X2/X4 and X6/X8 record no state, questions, probabilities or model (`decisions.md:760-775, 1033-1039`). The D1/D2/D7 uses the handoff names postdate the snapshot. The X2/X4 pass is also questionable in kind: "find gaps in a spec" is generative, and Jev cannot generate, so the fifteen gaps must have come from the agent's or the council's questions. Under the project's own trust order (tests > source > derived > … > prose), Jev's contribution so far exists only as prose.

| # | Finding | Evidence | Consequence / fix |
|---|---|---|---|
| 1 | **One-Rule scanner hole**: `test_llm_cannot_write_circuit_ir.py` recognises a model only via `ai.client:make_client`, `ai.openai_compat:OpenAICompatClient` or `.messages.create`. A TypeSafe/httpx client is invisible, and the scan guards CircuitIR only, not IntentIR, `apply_patch` or `sign_off` | `tests/test_llm_cannot_write_circuit_ir.py:25-50, 77, 100` | Add the TypeSafe client to `_SEEDS` with a negative-control fixture, plus a mirror rule: no Jev-reaching module constructs `IntentIR`/`PatchOp`/`Claim`/`ValidationCoverage`, touches `REGISTER`, calls `sign_off`, or writes `figure_verifications.json`. **Prerequisite for any Jev code under `backend/`** |
| 2 | **LED decision taken by the agent under 0.5.** The entry's own text said "<0.5 a person should decide". The agent chose the reversible status quo and wrote "the user may overrule", under the user's delegation "give it the whole scenario and then make the decision" | `decisions.md:1435-1437, 1467-1475` | A deviation from the text as written, mitigated by reversibility and disclosure. The later handoff wording legitimises it. Under the new protocol it is labelled `agent_decided_under_uncertainty`, not "decided with TypeSafe" |
| 3 | **Unlisted fourth option inflated both confidences** (LED 0.37→0.44, RC 0.805→0.83) | Arithmetic above; `decisions.md:1446-1452` | Record k. Never threshold on `confidence`. Rule-violating options go under `excluded_by_rule` in state, never as labels |
| 4 | No consultation is reproducible (no committed script, state, raw JSON, model string or request id) | grep: no `typesafe` import or dependency in the snapshot | `tools/jev/<date>_<slug>.{json,results.jsonl}` committed with the decision entry |
| 5 | **CI never runs on the working branch** (push triggers `main, master, develop`; PRs to `main, master`) and installs `arduino-cli`, while Stage 5 compiles with PlatformIO 6.2.0 | `.github/workflows/ci.yml:3-7, 52-58` | Add `phase2-stage0` (or `**`) and PlatformIO. Until then no CI-side check, Jev or otherwise, ever runs |
| 6 | **Unregistered modules**: 7 backend files absent from `MODULES` (`ai/openai_compat.py`, `core/ir_examples.py`, `data/component_constraints.py`, `db/models.py`, `main.py`, `middleware/rate_limit.py`, `worker.py`). 8 in `MODULES` but not `PLANNED` | `tools/regen_state.py:49-60`; `tools/progress_gen.py:49-56`; rule at `AGENTS.md:62-78` | Deterministic check plus an allowlist for intentional exclusions. Stage 6 modules are also still unregistered (handoff §8) |
| 7 | **Stale BENCH_D1**: names `led_indicator 0.1.1`, code is `0.2.0` | `docs/BENCH_D1.md:13-15` vs `generators/led_indicator.py:108` | Regenerate the sheet before any bench session. A version-string drift regex would have caught it |
| 8 | **Gerber Phase 3/4 contradiction**: the Phase 3 KPI is "prompt-to-ordered-PCB within one business day", but Gerber, fab APIs and DFM are Phase 4, while the tech stack says "JLCPCB API (Phase 3+)" | `PRODUCT_MASTER.md:358, 362-370, 411` | Owner decision: move minimal Gerber forward, or restate the KPI as "routed KiCad board handed to the fab by the user" |
| 9 | **No written Phase 2 exit gate** in the repo. Canonical Phase 2 deliverables (`PRODUCT_MASTER.md:332-344`) deliberately differ from the as-built Stages 0–6, and v2 is not in the repo | handoff §1, §5 | "Is Phase 2 done?" is first a definitional owner call (which list governs), then a deterministic checklist. Never a Jev question |
| 10 | **UL 508A is probably the wrong headline standard** for Phase 3 controller boards. UL 60730-1 covers automatic controls. UL 61010-1/-2-201 covers programmable controllers. UL 508A covers the *panel* | [UL Solutions](https://www.ul.com/resources/hvac-motor-controllers); [Intertek](https://www.intertek.com/standards-updates/transition-from-ul-508-to-ul-61010-1-and-ul61010-2-201/); `PRODUCT_MASTER.md:353` | Applicability is a liability one-way door for a person. Circuit OS should *flag* candidate families, never assert compliance |
| 11 | Commit convention conflicts ("conventional" vs `session:` vs `brain:`), and `/update-memory` hardcodes `c:/Users/KIIT/cursor-electronics` | handoff §3; `AGENTS.md:158-159`; `.claude/commands/update-memory.md:21, 63` | Owner reconciles. Then a regex enforces it |
| 12 | `Claim.kind` has **no computational reader**, `Kind.EMPIRICAL` is never used, and the analytic-vs-empirical reading never weighed the precedence rule v2 > assurance docs | `validation/claims.py:109-112, 237-265`; `frontend/lib/api.ts:98`; `decisions.md:1208-1212` | Cheap and reversible, but keeping `analytic` against v2 without a written v2 amendment is a silent precedence violation |
| 13 | The **criterion-12 trigger fires when Phase 3 starts**: "before … a demo to a prospect", and the Phase 3 KPI is "first enterprise contract" | `decisions.md:429-436`; `PRODUCT_MASTER.md:358` | Schedule the external cold read before any sales activity |
| 14 | The first-listed Phase 3 class (DCV) needs a 24VAC→3.3V switching supply. Switching converters and transients are out of Phase 2 scope | `PRODUCT_MASTER.md:178`; handoff §9 | A deterministic feasibility filter before any ranking of industrial classes |
| 15 | The old protocol cannot read Nouls (no confidence field), yet the 2026-09-23 entry banded Noul probabilities | SDK `models.py:74-104`; `decisions.md:1451-1452` | Nouls become diagnostics with both-polarity checks, never the governing question |

## Thirty-three uses, placed file by file, with one invariant: Jev can only subtract

Every use below obeys one testable property: **the set of requests that end in an accepted design, closed defeater, signed set, granted waiver or approved price with Jev enabled must be a subset of that set with Jev disabled.** A Jev judgment may make the case look more doubtful. It may queue a human, add a question, refuse a patch, or pick the stricter label. It may never make the case look better. Assurance-case practice supports this split. Eliminative argumentation and Assurance 2.0 build confidence by recording defeaters and eliminating them with evidence ([SEI 2015](https://www.sei.cmu.edu/documents/1248/2015_005_001_434813.pdf); [Assurance 2.0, arXiv 2405.15800](https://arxiv.org/html/2405.15800v1)). LLMs help *find* defeaters with a human in the loop ([CoDefeater, ASE '24](https://doi.org/10.1145/3691620.3695296)). NASA's 2025 review concludes that "much remains to be demonstrated" before models can produce or assess assurance arguments ([NASA TM-20250001849](https://ntrs.nasa.gov/api/citations/20250001849/downloads/NASA-TM-20250001849.pdf), via secondary summaries). No source treats a model judgment as evidence that discharges a claim. In Hawkins's terms, a Jev output belongs in the *confidence argument*, never in the safety argument's evidence ([Hawkins et al.](https://www-users.york.ac.uk/~rdh2/papers/HawkinsSSS11.pdf)).

### Owner and engineering decisions (developer-time, lowest risk, do now)

These are the uses the owner asked for, and they are the right place to start. They are offline, one request each, and nothing ships because of them. Four of the open decisions are **explicitly owner-owned product calls** (handoff §7): the RS-485 pull-down, X7, D1/D7 timing and explainer cost. For these, every band ends in "owner decides", and Jev only changes how strongly the recommendation is worded. For X7, no Jev output at any value can stand in for the required explicit approval.

| Use | Primitive (governing) | Plug-in | Who acts |
|---|---|---|---|
| O1 RS-485 DE/RE 10 kΩ pull-down | Choice `pulldown_option` + Noul `d2_drop_is_sound` + Score `blast_radius` | `tools/jev/`; decision entry before any `rs485_node` change | Owner, all bands. If `d2_drop_is_sound` is not stably ≥ 0.9, no recommendation may claim D2 removal |
| O2 X7 live pricing | Choice `x7_option` | same | Owner, all bands. Default stays static |
| O3 D1 bench timing | Choice `d1_when` | same | Owner. Agent may regenerate BENCH_D1 (finding 7) in any band |
| O4 D7 verification order | Deterministic tiering, then Score `verification_value` per figure as tie-break only | `scripts/verify_figures.py` input list | Agent prepares the list (fully reversible). Owner sets timing |
| O5 `kind` on exact proofs | Choice `kind_option` | `validation/claims.py` rows; v2 amendment | Owner holds it. Agent may draft the amendment text |
| O6 Explainer budget | Choice `first_step` | `ai/explainer.py:62` | Owner. Needs the owner's cost ceiling in state |
| O7 Stage 6 version bumps | Determinism byte-compare first. Choice `bump_policy` only for the residual (outputs identical, envelope widened) | `generators/*.py VERSION` | Agent on a stable Act band. A bump makes signed designs 409, so un-bumping is the one-way side |
| O8 Stage 6 status and 5% KPI | progress.yaml decides "done". Choice `kpi_5pct_disposition` + Choice `stage6_finish_before_phase3` | `plan/current_phase.md` | Agent with care (reversible scheduling) |
| O9 Flaky accuracy test policy | Choice `flake_policy` ("retry until green" excluded by rule) | `tests/test_simulation_accuracy.py`; `regen_state.py:56-57` | Agent with care |
| O10 Phase 3 scope order | Choice `phase3_order` + Score per industrial class after the feasibility filter + Noul on the Gerber KPI + Noul on criterion-12 timing | Phase 3 plan | Owner (sets 6–10 months) |

### Runtime and assurance layer (shadow first, promoted only on measured data)

The two notes disagree here. The runtime note ranks transcription fidelity as the highest-value runtime insertion. The owner-workflow note says "don't put Jev on the product request path". Both are right about different things. Jev must never enter the **generation chain** (tool_use → IntentIR → dispatch → realize → CircuitIR). A side-channel check that can only convert an accept into a question is a different thing. The resolution is a mode ladder per insertion point: `off → shadow (log only) → advisory (flag shown) → blocking-toward-refusal`. Promotion needs a seeded corpus with negative controls, and any Jev error or timeout must behave exactly like `off`. A Jev outage must never produce a 503 or 422, unlike the producer's APIError→503 rule.

| Use | Exact place | What Jev answers | Allowed effect | Must not |
|---|---|---|---|---|
| R1 **Transcription fidelity** (highest value) | `api/routes/design.py` between `:106` (`ctx.intent_ir`) and `:110` (underdetermined check) | Noul per leaf of `_requested_values`: "does the prompt state `targets.cutoff_hz = 1000`?" Choice over the 5 catalogue functions + `none_of_these`, compared with `requirements.function`. Noul "does the prompt ask for anything not represented?" | Stable low p → return the existing 422-underdetermined shape with a confirm question ("we read 1 kHz — confirm"). Middle → dispatch plus a flag | Auto-correct a value, write IntentIR, gate `envelope()` |
| R2 **Patch-op faithfulness** | `api/routes/patch.py` between `propose` (`:200-215`) and `apply_patch` (`:218`), `command` patches only | Per op: "in C, do words W_k ask to set `<path>` to `<value>`?" (or to remove it). Plus completeness | Refusal as a distinct `JUDGE_DOUBTS_OPERATION`, v(n) kept, user rephrases. Targets the documented swap and unrelated-removal gaps (`intent_patcher.py:38-41`) | Admit an op the deterministic guard refused, or be described as "a guard" (DEC:839 already rejected heuristics dressed as guards) |
| R3 X5 retry-added fields | `ai/intent_producer.py:312`, the `else` branch of the add-only check | "Is value v for field f stated in the prompt?" for keys added by the retry only | Stable low p → underdetermined on that field | Replace the deterministic add-only check |
| R4 D5 sign-off doubt hints | Computed at R1, persisted beside the design, rendered in the sign-off view (`patch.py:434-500`) | Reuses R1's per-field Nouls | Highlight fields as "check this". **Negative-only**: never a "Jev agrees" badge | Sign, pre-fill, gate sign-off, close D5, or live inside `SignOff` |
| R5 Catalogue-function disagreement | Shadow beside dispatch (`design.py:122-131`) | Which function the *prompt* asks for vs the LLM's `function` | Log, later flag | Veto or accept against the exact `envelope()` (0/200 false accepts, 0/200 false abstains) |
| R6 Extra underdetermined questions | `intent_producer.py:341` (`_questions`) | Noul per required field | May *add* a question | Remove one (that is the guess direction) |
| R7 Refusal backlog labelling | Offline over `request_log.refusal_reason` + `intent_ir` (`observability/request_log.py:24-26`) | Deterministic group-by first. Then a Choice over owner-defined Phase 3 labels + `none_of_these`, with counts in state | Orders the Phase 3 backlog (a D4 aid) | Measure authoring cost (D4's real closer), write `current_phase.md` |
| R8 D7 figure triage | Input to `verify_figures.py` (uncommitted) | Score per figure: tie-break inside deterministic tiers (gates a critical claim → stated_assumption/typical first → smallest audit margin) | Queue order | Write anything to `figure_verifications.json` or count as verification |
| R9 D3 explanation pre-screen | Offline, `scripts/review_panel.py` ablation design | Rubric score on explanation-only vs no-explanation arms | Regression metric and a pre-fix aid before the scarce human read | Feed criterion 12. The project already rejected LLM-as-judge on this ground (DEC:336-341, 602-605) |
| R10 D9 mutation-target ideas | Offline, `validation/grid_adapters.py:187-196` | Choice: which component fault would the 2% gate be least sensitive to? (The RS-485 margin is thin: a 5% fault moves V_AB 2.3%) | Becomes a seeded-fault test. The test is the evidence | Keep D9 closed or open it |
| R11 Substitute ordering | After Stage 6 gates, in `bom/substitution.py` | Choice over already-surfaced candidates with the user's stated preference | Sort order only. Surfaced set identical with Jev on and off | Surface, filter, gate, price or select |

Where a Jev judgment must be stored, it becomes a **separate, append-only `Judgment` record**, not a `Claim`. It holds `jev_model` (as returned), `request_id`, `request_hash`, a `state_ref`, the verbatim questions and raw outputs, k, the band, targets (`circuit_id`@version, claim, defeater or figure ids as *topics*), purpose, `action_taken` and `decided_by`. Its validator rejects any field named `status`, `eliminated_by`, `verdict` or `grade`. It lives in a `jev_judgment` table created through `db/migrations.py`, with a JSONL fallback like `request_log`, and it is counted separately from `api_calls` so the §4.4 LLM budget stays clean. If a judgment must ever appear in the claims table, it uses the combination the validator already permits: `verdict=not_assessed, grade=G7, critical=False, method=None` (`claims.py:159-169`). **Never add a `model_judgment` method to `METHOD_GRADE`**, because `graded()` would then hand a Jev row a holds or fails verdict.

### Phase 3: labels into tables, never numbers into the router

Phase 3 is three separable programmes: (A) the constraint layer + freerouting, which needs no customers; (B) industrial generators; and (C) enterprise features, which PCB_STRATEGY §9.3 gates on "ask three HVAC people" (`PCB_STRATEGY.md:280-304`). Freerouting 2.x runs headless. It takes net classes through the DSN `(network (class …))` block or `-dr` rules and emits a KiCad-schema DRC JSON with `-drc` ([freerouting CLI docs](https://github.com/freerouting/freerouting/blob/master/docs/command_line_arguments.md); [settings](https://github.com/freerouting/freerouting/blob/master/docs/settings.md)). Every router knob is numeric: passes, via costs, direction costs, ripup. All of them belong in a pinned, versioned profile table. The existing `to_dsn()` (`pcb_engine/router.py:499-562`) omits via padstacks, diff pairs, per-class layer rules and `Keepout.reason`, which is deterministic work. Competitors confirm the pattern. Quilter *reads* engineer-authored constraints and allows per-class impedance overrides ([Quilter 2026](https://www.quilter.ai/blog/pcb-autorouting-in-2026-a-review-of-traditional-tools-vs-quilters-ai-approach)). Flux turns *approved* suggestions into rules ([Flux](https://www.flux.ai/p/blog/teach-copilot-how-you-work-with-knowledge)). Neither derives constraints from intent, and none exposes a calibrated per-decision confidence.

The pattern is to keep Phase 2's shape. The only non-deterministic input is a **label from a code-defined enum**. A versioned `ConstraintRule` table maps (label, `SignalType`, fab profile) to numeric parameters and a **template-rendered reason**. The routed board is checked by freerouting DRC plus an independent geometric re-check, which becomes a `layout_constraint` claim (G1 when exact geometry is checked against a table value, G7 when emitted but unchecked). Four new defeaters carry the residual doubt. L1: the value is a house rule, not physics. L2: the input label was judged, not stated, closed by user sign-off like D5. L3: the router ignored or could not express the constraint. L4: standards applicability was judged. The numbers themselves are lookups: IEC 60664-1 creepage from voltage, pollution degree, material group and overvoltage category ([EMA table](https://www.ema-eda.com/ema-resources/blog/pcb-clearance-and-creepage-distance-table/)), IEC 61131-2 input thresholds by Type ([TI SLLA370](https://www.ti.com/lit/pdf/slla370)), and the RS-485 −7 to +12 V common-mode range ([EDN](https://www.edn.com/inside-an-isolated-rs-485-transceiver/)). The *inputs* to those lookups need judgment, and that is where Jev fits:

| Use | Primitive | Guardrail |
|---|---|---|
| P1 `net_role` for generic `digital`/`analog` nets in new industrial generators (0–10 V out, 4–20 mA loop, relay coil, 24 V field input) | Choice over enum + `undeclared` | The generator-declared role always wins. Cites L2. A runner-up mutation test must change the emitted constraint and be caught |
| P2 `env_label` (pollution degree, overvoltage category, indoor vs field-wired) from the user's description | Choice | **Use the stricter of {Jev label, conservative default} for dimensions until the user confirms, in every band** |
| P3 `isolation_needed` when ground-potential difference is undeclared | Noul | Anything short of a stable, confirmed "no" → the isolated design, stated as such |
| P4 Standard-family triage (60730 / 61010-2-201 / 508A-panel / none) and "possibly life-safety" | Choice + Noul | Output worded "flag". A person decides. Life-safety is person-only |
| P5 `component_role` for a library part without a declared role | Choice | Private libraries must declare roles. The Jev fallback is flagged |
| P6 DRC waiver triage {cosmetic, needs_review, safety_relevant} | Choice | Orders the review queue only. Every waiver is signed by a person. `safety_relevant` forces review at any probability |
| P7 Private-library admission triage {accept, needs_datasheet_check, reject} | Choice | Deterministic schema/pin/footprint/provenance checks pass first |
| P8 "Is 4-layer justified?" after 2-layer fails N candidates | Noul | Never auto-upgrade. A fab-cost one-way door, so a person confirms |

### Dev tooling and CI (deterministic first, Jev on the semantic residual, never a merge blocker)

Most tooling checks are deterministic and should be written as code: module registration (finding 6), version and number drift in prose (finding 7), commit format (after finding 11 is settled), staleness of `state.json` against HEAD, and first-pass failure triage from junit tracebacks. Jev earns four advisory, fail-open slots. **T1** `entry_covers_diff` (Choice), on PRs touching generators, proof, validation, `*_ir.py` or a `VERSION`, after the deterministic check that a new `## [date]` entry exists and `decisions.md` is append-only. It only ever posts a comment. **T2** `failure_class` (Choice) for tracebacks the deterministic classifier cannot match. A retry is allowed only if it says `infra_hiccup` stably and the test is not in an accuracy file, because "an accuracy disagreement never may" be retried (`current_phase.md:463`). Every classification is logged, which builds the diagnosis the flaky test has lacked since 2026-08-23. **T3** `contradicts_derived_fact` (Noul) per prose paragraph against `state.json` excerpts, run weekly or in `/update-memory` Step 5. The output is a to-fix list for a human, never an edit. **T4** `needs_owner_attention` (Choice) as a PR label, never an approval. Budget: one batched request per PR plus one per unmatched failure, a pinned model, and fail-open. None of it matters until finding 5 is fixed, because CI does not run on `phase2-stage0` today.

## Seven places Jev must never enter

The never-list follows from the register's own text: every `eliminated_by` in `validation/defeaters.py:49-122` names a non-model event. First, **anything that computes**: `envelope()`, `predict()`, claims, proofs, pin rules, the grid gate, the ngspice grader, the PlatformIO compile gate, BOM prices, freerouting parameters, creepage millimetres. A Jev input there would at best downgrade a G1 claim to G7, and at worst open a model→design path. Second, **`assess()` and `validation_coverage`**, which is "deterministic, no simulator, no model" (`claims.py:543-551`). Even a doubt-only input there would make coverage non-reproducible across model builds, so judgments sit beside it and a test asserts that `assess()` output is byte-identical with the judgment log empty or full. Third, **closing or softening any defeater**: D1 needs a bench, D2 reachset conformance, D3 a cold human read, D4 measured cost, D5 a signature, D7 per-parameter provenance with "no LLM-extracted rating gates a claim", and D9 the M1 matrix. Fourth, the **three human-closure points** (D3 review, D5 sign-off, D7 verification), where a positive Jev signal invites automation bias. Only negative-only annotations are allowed there. Fifth, the **zero-call paths**: `ai/form_producer.py` and `ops`-only patches, whose value is "0 model calls". Sixth, **approvals and certifications**: X7, DRC waivers, UL/IEC compliance, life-safety classification, library admission and the Phase 2 governing-list decision. Seventh, **questions a test already answers**: "is function X done", "did the suite pass", "what is the grade floor", "is the module registered", "did CircuitIR bytes change", "is this proof valid". Asking these invites a probability to outrank a measurement. The rule: **if a test can answer it, write the test.**

## A stability-gated protocol replaces the 0.5/0.9 confidence bands

The current protocol keeps a sound instinct: a person owns real uncertainty, and when a person is unavailable the reversible option wins and the choice is disclosed. Its mechanics fail on five counts established above. It keys on `confidence`, which moves with k. It cannot read Nouls. It treats the flat 0.5–0.95 band as actionable. It has no check against rephrasing until the answer is welcome. And it does not distinguish owner-owned calls, one-way doors or safety labels. The replacement below keeps the three bands but changes what they measure. The thresholds are **conservative proposals, not calibrated values**. Record them as a `decisions.md` entry before the first new request.

**Step 0: gate eligibility.** Is this a Jev question at all? Numbers, pass/fail, approvals, and anything a test answers are out. Otherwise classify it three ways: owner-owned (handoff §7 list, X7, and anything the owner reserves later) or delegated; one-way door (changes signed or stored data, hashes, public API, a generator's accepted set, fab cost, safety) or two-way; safety-relevant or not. **Step 1: build a committed request** in `tools/jev/<date>_<slug>.json`. The state is facts, not advocacy, decisive facts first, under about 3k tokens. Every option has identical fields (what changes, reversibility, blast radius, cost). There are no adjectives, no "the user wants", no council verdicts. Every label has a "choose when / not when" description. `need_more_information` is always present. Rule-violating options go under `excluded_by_rule`, never as labels. One decision per Choice, compound questions split into Nouls, and key Nouls asked in both polarities. Pin the model. **Step 2: run at least three variants**: original, labels reversed, and state paraphrased by a second agent or a neutral template. Optionally add two identical repeats and a state-blind control. Batching these costs little and shifts answers little (JS 0.006 ([xxlya/evaljev](https://github.com/xxlya/evaljev))). Log raw JSON, returned `model`, request id, usage and date. **Step 3: compute signals, never `confidence`**: k, minimum p_top across variants, minimum margin (p1 − p2), `argmax_stable`, maximum P(`need_more_information`), the Noul polarity sum (unstable outside 1 ± 0.15), and Noul-vs-Choice coherence. Also record whether the agent's independent analysis agrees, written *before* the call. **Step 4: band it** with the table below.

| Band | All must hold | Two-way door, delegated | One-way door, or owner-owned | Safety-relevant label |
|---|---|---|---|---|
| **Act** | argmax stable; min p_top ≥ 0.90; min margin ≥ 0.60; P(need_more_info) < 0.05; Nouls coherent; agent's prior analysis agrees | Act; log it | Recommendation to owner marked "strong"; agent does not act | Stricter option until a person confirms |
| **Act with care** | argmax stable; min p_top ≥ 0.60; min margin ≥ 0.25; P(need_more_info) < 0.20; argmax ≠ need_more_info; agent agrees | Act only after naming checks before code (tests, 0-of-N regression scan, negative control) and a dated review trigger | Recommendation "moderate" | Stricter option |
| **Owner decides** | anything else: argmax flips, margin < 0.25, need_more_info top or ≥ 0.20, polarity incoherent, Jev disagrees with the agent | Owner. If unavailable and blocking: most reversible option (usually the status quo), logged `agent_decided_under_uncertainty`, "owner may overrule", dated trigger. Never a one-way door | Owner; default stays | Stricter option; person |

Nouls never govern. They are **diagnostics**: stably ≥ 0.9 or ≤ 0.1 across variants and polarities reads as "decisive", and anything else as "unsettled". A high P(`need_more_information`) is a signal to add facts, and a re-ask is legitimate only when the state gains a named new fact. The re-ask is logged under the same `decision_id` with an incremented `attempt_n`. A new attempt with an unchanged `state_sha256` and only reworded questions or relabelled options is flagged as rephrase-shopping, and the decision entry reports all attempts. For **runtime** points (R1–R3, P1–P8), promotion from shadow to advisory needs a seeded corpus. Examples: 2 MHz→1 kHz, band-pass→low-pass, swapped values across ops, unrelated-word removals, dropped requirements, and faithful controls. Report detection and false-flag rates with κ against owner labels. Promotion to blocking-toward-refusal additionally needs the Act threshold met on held-out data, where the studies suggest 0.99, not 0.9, is the meaningful gate ([priorbench](https://github.com/priorbench/jev)). It also needs a mutation check proving the wiring: remove the Jev call and the negative-control tests must fail. **Step 5: the decision entry** links the request file and results rather than restating numbers ("one owner per fact", `AGENTS.md:90-99`). It carries the k/p_top/margin/stability table, band, action, who decided (`jev_supported` / `agent_decided_under_uncertainty` / `owner`), reversibility class and review trigger. **Step 6: retrospective.** Tag each outcome kept, reversed or defect-found. After about 30 decisions, check whether the Act band held. This is the only calibration Circuit OS can get. Applied retroactively, the RC call (margin 0.74, one variant) lands in Act with care on a two-way door, which matches what was done. The LED call (margin 0.22) lands in Owner decides, and the agent's fallback is exactly the logged exception the new protocol allows.

## Five moves, in order

**First**, close finding 1 (scanner seeds + IntentIR/sign-off mirror rule, each with a negative-control fixture) and finding 5 (CI on `phase2-stage0` with PlatformIO). Both are deterministic and unblock everything else. **Second**, commit `tools/jev/` with the harness in Appendix A and the protocol entry in `decisions.md`, and retro-file the 2026-09-23 consultation with its fourth option recovered from the owner's machine if the scratchpad survives. **Third**, run the owner requests O1–O9 on the owner's machine. O7 (version bumps) and O8 (Stage 6 finishing) unblock the Stage 6 commit. O1, O2, O3 and O6 end with the owner in every band. O5 is cheap and removes a latent precedence violation. Before O10, the owner settles findings 8, 9 and 10 by hand, since no Jev answer can fix a contradictory roadmap. **Fourth**, build the `Judgment` record and the `jev_judgment` table, then ship R1 and R2 in **shadow** only, against a new prompt→gold-IntentIR corpus with seeded mistranscriptions. The existing 0/200 corpus measures `envelope()`, not transcription. One owner decision gates this: whether storing raw prompt text is acceptable, since today only `prompt_hash` is kept. **Fifth**, in Phase 3, build the `ConstraintRule` table and L1–L4 defeaters deterministically, then wire P1–P3 as labels behind the stricter-option rule. Schedule the criterion-12 cold read before the first prospect demo.

## Conclusion

The research reframes what Jev is for in this project. The instinct behind the 2026-09-23 use was to let a calibrated model *settle* judgment calls. The evidence says Jev's probabilities are not calibrated for this domain, its `confidence` is arithmetic on the option count, and its mid band is close to noise. What Jev offers Circuit OS is cheap, typed, text-free *doubt*. That fits an assurance architecture built on eliminative argumentation, where confidence comes from naming doubts, not from asserting certainty. Used that way, Jev strengthens the product's differentiator instead of diluting it: a Jev flag that turns a silent 2 MHz→1 kHz mistranscription into a confirm question is exactly the "named doubt" the claims layer exists to surface.

The most consequential findings turned out not to be about Jev at all. The CI does not run on the working branch. The One-Rule scanner cannot see a new model client. The roadmap promises ordered PCBs in a phase that has no Gerber export and names a panel standard for a board. Phase 2 has no written exit gate. Each of these is a place where the project's own "tests over prose" discipline has not yet reached, and each should be fixed deterministically before any probability is asked to help.

---

## Appendix A — Harness to run the drafts (untested; written where api.typesafe.ai was unreachable)

Save as `tools/jev/run.py`. The API calls match the `typesafe-sdk` 0.7.1 public surface (`TypeSafeClient.system_one(state, questions, model=…)`, dict questions with `type` of `noul`/`choice`/`score`, and `response.model`, `.request_id`, `.usage`, `.answers[name]`). The harness has never been executed against the live API. Key: `TYPESAFE_API_KEY`, already a Windows user env var.

```python
"""tools/jev/run.py — run one decision request in counterbalanced variants and band it.
Usage: python tools/jev/run.py tools/jev/2026-09-26_rs485_de_re_pulldown.json [--repeats 2] [--blind]
Writes <request>.results.jsonl (append-only). Never edits code or decisions.md."""
import argparse, datetime, hashlib, json, pathlib
from typesafe_sdk import TypeSafeClient

PINNED_MODEL = "jev-1.13.0"          # pin; the returned model string is logged and compared
ABSTAIN = "need_more_information"

def sha(obj): return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()

def reversed_labels(questions):
    out = {}
    for name, q in questions.items():
        q = dict(q)
        if q["type"] == "choice":
            q["criteria"] = dict(reversed(list(q["criteria"].items())))
        out[name] = q
    return out

def signals(ans):
    if ans.type == "choice":
        p = sorted(ans.probabilities.values(), reverse=True)
        return {"type": "choice", "argmax": ans.choice, "k": len(ans.probabilities),
                "p_top": p[0], "margin": p[0] - (p[1] if len(p) > 1 else 0.0),
                "p_abstain": ans.probabilities.get(ABSTAIN, 0.0),
                "live_options": sum(v >= 0.05 for v in ans.probabilities.values()),
                "probabilities": ans.probabilities, "confidence_raw_do_not_threshold": ans.confidence}
    if ans.type == "noul":
        return {"type": "noul", "p_yes": ans.noul}
    return {"type": "score", "score": ans.score, "probabilities": ans.probabilities,
            "confidence_raw_do_not_threshold": ans.confidence}

def band(rows, agent_agrees):
    stable = len({r["argmax"] for r in rows}) == 1
    p_min = min(r["p_top"] for r in rows); m_min = min(r["margin"] for r in rows)
    abst = max(r["p_abstain"] for r in rows); top = rows[0]["argmax"]
    if stable and p_min >= .90 and m_min >= .60 and abst < .05 and agent_agrees: return "act"
    if stable and p_min >= .60 and m_min >= .25 and abst < .20 and top != ABSTAIN and agent_agrees: return "care"
    return "owner"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("request")
    ap.add_argument("--repeats", type=int, default=0); ap.add_argument("--blind", action="store_true")
    a = ap.parse_args(); path = pathlib.Path(a.request); req = json.loads(path.read_text())
    para = path.with_suffix(".paraphrase.json")        # state rewritten by a second author
    variants = [("original", req["state"], req["questions"]),
                ("reversed", req["state"], reversed_labels(req["questions"]))]
    if para.exists(): variants.append(("paraphrase", json.loads(para.read_text()), req["questions"]))
    variants += [(f"repeat{i}", req["state"], req["questions"]) for i in range(a.repeats)]
    if a.blind: variants.append(("blind", "No context is given. Judge from the options alone.", req["questions"]))
    log = path.with_suffix(".results.jsonl"); per_variant = []
    with TypeSafeClient() as client:
        for name, state, qs in variants:
            r = client.system_one(state, qs, model=PINNED_MODEL)
            row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "decision_id": req["decision_id"], "attempt_n": req.get("attempt_n", 1), "variant": name,
                   "model_requested": PINNED_MODEL, "model_resolved": r.model, "request_id": r.request_id,
                   "usage": r.usage.model_dump(), "state_sha256": sha(state), "questions_sha256": sha(qs),
                   "answers": {k: signals(v) for k, v in r.answers.items()}}
            with log.open("a", encoding="utf-8") as f: f.write(json.dumps(row) + "\n")
            if name != "blind": per_variant.append(row["answers"])
    g = req["governing"]
    rows = [v[g] for v in per_variant]
    for yes, no in req.get("polarity_pairs", []):          # both-polarity Noul coherence
        sums = [v[yes]["p_yes"] + v[no]["p_yes"] for v in per_variant]
        print(f"polarity {yes}/{no}: sums {['%.2f' % s for s in sums]}",
              "INCOHERENT" if any(abs(s - 1) > .15 for s in sums) else "ok")
    b = band(rows, req["agent_prior_agrees_with"] in {r["argmax"] for r in rows})
    if req.get("owner_owned") or req.get("door") == "one_way": b = f"{b} -> owner decides (recommendation only)"
    print(json.dumps({"governing": g, "rows": rows, "band": b}, indent=2))

if __name__ == "__main__": main()
```

Before each run, set `agent_prior_agrees_with` to the label the agent's own analysis favours, written before the call. Set it to `null` if there is no prior. The script then treats the answer as not agreeing, which caps the band at "owner".

## Appendix B — Ready-to-run decision requests

Every request file has this envelope. The shared state block goes in every request, so Jev knows the invariants and which options were excluded by rule.

```json
{
  "decision_id": "<slug>", "attempt_n": 1, "owner_owned": true, "door": "two_way|one_way",
  "governing": "<choice question name>", "agent_prior_agrees_with": "<label or null>",
  "polarity_pairs": [["<noul>", "<noul>__not"]],
  "state": {
    "project_invariants": ["LLM writes only IntentIR; deterministic generators write CircuitIR/SPICE/KiCad/firmware",
      "tool_use forced; X5 retries; patches edit requirements only (X2/X4)", "ngspice via Celery; MCU = resistor",
      "an accepted design never carries a failing claim; grade derives from method only",
      "a generator VERSION change makes signed designs return 409 generator_changed until patched",
      "Jev never overrides these rules"],
    "team": "one engineer, no oscilloscope; OpenRouter credits exhausted 2026-09-23",
    "decision": {"question": "...", "history": "...", "facts": [{"fact": "...", "source": "file:line"}],
      "options": [{"id": "...", "what_changes": "...", "benefits": "...", "costs": "...",
        "reversibility": {"how_to_undo": "...", "signatures_invalidated": false}}],
      "excluded_by_rule": [{"option": "...", "rule": "..."}]},
    "unknowns": ["..."]
  },
  "questions": { }
}
```

### B1 `rs485_de_re_pulldown` (owner-owned; one-way if default)

*State facts:* topology `U1 D2 → DE/RE`, `PIN_DE_RE = "D2"` (`rs485_node.py:1-35, 107`). Claims `rs485.failsafe_bias` (monotone_corners), `driver_load`, `termination_dissipation`, `rail_current`, with current defeaters (`:330-350`; D2 derived per claim since 94b61c1). D2 register text: "nothing in Phase 2 is scheduled to close it" (`defeaters.py:58-67`). Change = one 10 kΩ from the DE/RE net to GND. Idle current when driven high = 5 V/10 kΩ = 0.5 mA on the Uno, 0.33 mA at 3.3 V (arithmetic). `rs485_node` 0.2.0 → bump → signed RS-485 designs 409. Thin M1 margin (5% fault → 2.3% V_AB vs 2% gate). `<PASTE: DE/RE pin status from data/mcu_targets.py + pin_rules on all 3 boards>`. `<PASTE: D7 record or "stated assumption" for MAX485/MAX3485 DE/RE behaviour during MCU reset>`.

```json
{
  "pulldown_option": {"type": "choice",
    "instructions": "Which option should Circuit OS take for a DE/RE pull-down on the rs485_node generator?",
    "criteria": {
      "add_as_default_now": "Choose when the reboot-contention risk is material for most users and the cost of invalidating signed RS-485 designs is acceptable. Every new design gets R4; version bump.",
      "add_as_opt_in_constraint": "Choose when the benefit is real for some users but existing designs must stay byte-identical. constraints.de_re_pulldown defaults false; no signature impact.",
      "defer_with_trigger": "Choose when the risk only matters on multi-drop or flashed hardware not yet in use. Record trigger: first multi-drop bus or first flashed RS-485 board.",
      "do_not_add": "Choose when the state shows no material risk and the added part only costs.",
      "need_more_information": "Choose when a missing fact (pin status, transceiver reset behaviour) would change the answer."}},
  "reboot_contention_material": {"type": "noul",
    "instructions": "For a single-master Modbus RTU node on a bench or small bus, is a driver briefly enabled during MCU reset a material risk to other nodes' communication?",
    "criteria": {"true": "Material: plausible corrupted frames or bus lock on reboot.", "false": "Negligible for this use."}},
  "reboot_contention_material__not": {"type": "noul",
    "instructions": "For a single-master Modbus RTU node on a bench or small bus, is a driver briefly enabled during MCU reset negligible for other nodes' communication?"},
  "d2_drop_is_sound": {"type": "noul",
    "instructions": "Given the state, would adding the pull-down remove the reason D2 (simplified MCU model) is cited on the fail-safe claim, rather than just moving it to another claim?"},
  "blast_radius": {"type": "score", "instructions": "How far does the recommended change reach?",
    "criteria": ["No existing design changes", "Only new designs change", "Existing unsigned designs re-realise differently", "Signed designs are invalidated (409)"]}
}
```

*Band → action:* all bands → owner. If `d2_drop_is_sound` is not stably ≥ 0.9, the recommendation may not claim D2 removal. `blast_radius` ≥ 2.5 marks the option as a one-way door in the summary.

### B2 `x7_live_pricing` (owner-owned; explicit approval required)

*State:* `current_phase.md:751-758` verbatim. Stage 6 gates ("every price carries price_asof; pricing never gates validation"), which static exact-match pricing already meets. The 0402-vs-1206 mispricing as a *static* pricing bug. security.md static-pricing rule. Credits exhausted. One engineer. `<PASTE or "unknown": vendor, ToS on caching/display, key handling, rate limit>`. `excluded_by_rule`: "live pricing without explicit approval".

```json
{
  "x7_option": {"type": "choice", "instructions": "What should happen with live component pricing (X7)?",
    "criteria": {
      "approve_now_behind_flag": "Choose when vendor terms are known and a live fetch writing a price_asof cache row, never read by validation, is worth its ops cost now.",
      "approve_after_static_stage6_exit": "Choose when live pricing has value but Stage 6 should first close on static pricing.",
      "defer_to_phase3": "Choose when no Phase 2 gate needs it and the ops burden outweighs the value until customers exist.",
      "reject_keep_static": "Choose when static dated pricing meets every foreseeable need.",
      "need_more_information": "Choose when vendor terms, costs or rate limits are unknown."}},
  "stage6_gate_needs_live": {"type": "noul", "instructions": "Does any stated Stage 6 gate require a live price rather than a dated static one?"},
  "vendor_terms_known": {"type": "noul", "instructions": "Does the state contain the vendor's caching/display terms and rate limit?"},
  "ops_burden": {"type": "score", "instructions": "Operational burden of the live option",
    "criteria": ["No new secret or dependency", "New secret only", "New secret and rate limit", "Secret, rate limit, cache invalidation and ToS review"]}
}
```

*Mapping:* no band is approval. Act → "recommend <label>". Anything else → "Jev unsettled; the default stays static". If `vendor_terms_known` < 0.9, force `need_more_information`. If `stage6_gate_needs_live` > 0.5 against the gate text, the state is misleading: fix the state, not the decision.

### B3 `d1_bench_timing` (owner-owned)

*State:* BENCH_D1 equipment list (multimeter, bench supply, signal generator, oscilloscope) vs "no oscilloscope". D1 trigger "lab access". Evidence-record code decided 2026-09-24, not built. Every behavioural claim cites D1. BENCH_D1 is stale (0.1.1 vs 0.2.0). "No board flashed" (Stage 5). `<PASTE: v2 Phase 2 exit text, else omit d1_blocks_phase2_exit>`. `<CONFIRM: whether BENCH_D1 allows a no-scope DC-only partial session, else drop that label>`.

```json
{
  "d1_when": {"type": "choice", "instructions": "When should the D1 bench session happen?",
    "criteria": {
      "build_evidence_records_then_bench_when_scope_available": "Choose when records are needed first and the RC cutoff needs a scope.",
      "partial_session_now_without_scope": "Choose when meter+supply DC checks on divider/LED are worth doing now and the RC cutoff can wait.",
      "bench_before_phase2_exit": "Choose when the exit criteria require hardware evidence.",
      "defer_with_trigger_lab_access": "Choose when nothing scheduled depends on it before lab access.",
      "need_more_information": "Choose when exit criteria or equipment availability are unknown."}},
  "d1_blocks_phase2_exit": {"type": "noul", "instructions": "Given the pasted exit text, does Phase 2 exit require D1 closed?"}
}
```

### B4 `d7_verification_order` + `d7_when`

*Deterministic first:* tier 1 = figures gating a critical claim (`ClaimScope.figures`). Within a tier, `kind ∈ {stated_assumption, typical}` before `guaranteed`, then the smallest `figure_audit` margin. Jev scores figures only to break ties within a tier, in batches of up to 20. State per figure: id, kind, source, claims reading it, audit margin, "agent reading without datasheet" flag.

```json
{
  "vv_<figure_id>": {"type": "score", "instructions": "Value of verifying this figure against the manufacturer datasheet now",
    "criteria": ["No claim reads it", "Only non-critical claims read it", "A critical claim reads it with wide margin", "A critical signed claim's verdict could flip within plausible datasheet variance"]},
  "d7_when": {"type": "choice", "instructions": "When should the verification pass happen?",
    "criteria": {"before_stage6_commit": "Choose when Stage 6 substitution relies on unverified figures.",
      "interleave_one_family_per_session": "Choose when the work is best spread across sessions by part family.",
      "after_stage6": "Choose when Stage 6 does not depend on verification.",
      "need_more_information": "Choose when dependency of Stage 6 on figures is unclear."}}
}
```

*Mapping:* the ordered list may be prepared in any band (fully reversible). Timing is the owner's.

### B5 `proof_kind_label` (owner holds; cheap, reversible)

*State:* `decisions.md:1208-1212, 1266-1269` verbatim. `<PASTE: v2 Stage 4 table row saying empirical>`. `<PASTE: EVIDENCE_CLASSES §3.1 falsification test>`. Precedence v2 > PRODUCT_MASTER > assurance docs. The `Kind` docstring (`claims.py:8-9`). No code reads `kind`, `Kind.EMPIRICAL` is unused, and the UI does not render it. `kind` is not in the sign-off hash (`proof/properties.py:113-126`). D1 is cited on every proof row. v2 labels the grid gate "empirical, G5 ≤ 2%". `<VERIFY by test: whether kind appears in CircuitIR bytes>`.

```json
{
  "kind_option": {"type": "choice", "instructions": "Which kind label should exact proofs carry?",
    "criteria": {
      "keep_analytic_and_amend_v2_wording": "Choose when analytic is right and precedence must be respected by amending v2.",
      "switch_to_v2_empirical": "Choose when v2's label is deliberate and governs.",
      "split_by_object": "Choose when z3/closed-form statements over the model are analytic but tool-run observations (grid gate, compile gate) are empirical.",
      "need_more_information": "Choose when v2's intent cannot be read from the pasted text."}},
  "v2_label_is_deliberate": {"type": "noul", "instructions": "Is v2's empirical tag for z3-proved claims a considered classification rather than a drafting slip?"},
  "precedence_forces_v2": {"type": "noul", "instructions": "May a lower-precedence document's definition override v2's field value without amending v2?"},
  "external_reader_misreads_analytic": {"type": "noul", "instructions": "Would an external engineer read 'analytic' as 'validated on hardware'?"}
}
```

*Mapping:* Act and delegated → agent may apply. Care → agent drafts amendment text only. Owner band → status quo `analytic`, flagged. Any outcome that keeps `analytic` ships with a written v2 amendment.

### B6 `explainer_budget` (owner-owned; spend)

*State:* `EXPLANATION_MAX_TOKENS = 8192`, a stop at the ceiling raises (`explainer.py:62, 111-119`). 110–130 s, ~$0.20, RS-485 > 8192, the 15 s target unmet. The thinking-disabled fix untried (402). `derived_explainer` with 0 calls, 6/6 structural, domain layer not derivable. D3 deferred. `<PASTE: owner's per-generation cost ceiling>`.

```json
{
  "first_step": {"type": "choice", "instructions": "What is the next step for the explainer's cost and latency?",
    "criteria": {
      "experiment_thinking_disabled_when_credits": "Choose when the cheapest untried fix should be measured first.",
      "move_explanation_off_request_path": "Choose when latency, not cost, is the binding problem; run it async like simulation.",
      "derived_default_llm_opt_in": "Choose when the zero-call explanation is good enough as default.",
      "raise_ceiling_to_16384": "Choose when truncation, not latency, is the binding problem and cost is within ceiling.",
      "cheaper_faster_model_for_explainer": "Choose when a different model is likely to meet both targets.",
      "need_more_information": "Choose when the owner's cost ceiling is missing."}},
  "raising_ceiling_alone_meets_target": {"type": "noul", "instructions": "Would raising max_tokens alone bring generation under 15 s?"}
}
```

*Mapping:* owner in every band. A "yes" on `raising_ceiling_alone_meets_target` contradicts the measured facts, which means the state is misleading.

### B7 `pin_support_version_policy` (residual only)

*Deterministic first:* realise every grid point, the Phase 1 examples and the accepted corpus with and without the Stage 6 change, and byte-compare CircuitIR. Any byte change bumps that generator, and Jev is not asked. Diff `envelope()` accept/refuse on the refusal corpus. Jev gets only the residual case: bytes identical, envelope widened.

```json
{
  "bump_policy": {"type": "choice", "instructions": "Outputs are byte-identical but some generators now accept pinned-part inputs they used to refuse. What versioning policy applies?",
    "criteria": {
      "minor_bump_generators_whose_envelope_widened": "Choose when a widened accepted set is a behaviour change users should see in name@version.",
      "patch_bump_all_touched": "Choose when any touched generator should signal a change even if behaviour is identical.",
      "no_bump_outputs_identical": "Choose when identical outputs mean no version meaning changed; a later bump stays possible.",
      "need_more_information": "Choose when the envelope diff is incomplete."}}
}
```

*Mapping:* Act → act. Care → `no_bump` only (a later bump is possible; un-bumping after signatures is not). Owner band → owner.

### B8 `stage6_finish` (two questions; delegated, reversible)

*State:* the Stage 6 not-done list (GET /design/{id}/bom, BOMTable.tsx, api.ts BOMRow, registration, version decision, regen_state, current_phase tasks, commit). 5%-of-engineer KPI deferred. Reviewer rule `AGENTS.md:144-146`. "Done" is decided by progress.yaml, not by Jev.

```json
{
  "kpi_5pct_disposition": {"type": "choice", "instructions": "What should happen to the deferred 5%-of-engineer KPI?",
    "criteria": {"must_meet_before_stage6_done": "Choose when Stage 6's value claim depends on it.",
      "defer_with_named_trigger": "Choose when it can be measured later with a named trigger.",
      "amend_plan_to_drop": "Choose when it no longer measures anything the product needs.",
      "need_more_information": "Choose when the KPI's definition is unclear."}},
  "stage6_finish_before_phase3": {"type": "choice", "instructions": "How should unfinished Stage 6 work relate to Phase 3 start?",
    "criteria": {"finish_now": "Choose when Phase 3 depends on the BOM route or substitution.",
      "finish_in_parallel": "Choose when Phase 3 constraint-layer work is independent of Stage 6.",
      "defer_to_phase3": "Choose when remaining items are UI-only and Phase 3 will revisit them.",
      "need_more_information": "Choose when the dependency is unclear."}}
}
```

### B9 `accuracy_flake_policy` (delegated)

*State:* `timeline.md:90` (410/0 vs 409/1 with no code change). `current_phase.md:463` (no retry for accuracy disagreements). `regen_state.py:56-57` (one flake marks `generators/spice` broken). `excluded_by_rule`: "retry until green".

```json
{
  "flake_policy": {"type": "choice", "instructions": "How should the intermittent accuracy test failure be handled?",
    "criteria": {"diagnose_now_with_N_repeat_runs_seed_logged": "Choose when repeat runs to measure (not to turn green) can locate nondeterminism.",
      "mark_xfail_strict_with_issue": "Choose when a known cause exists and must be tracked without masking.",
      "leave_carried": "Choose when the failure is rare and diagnosis costs more than it reveals now.",
      "need_more_information": "Choose when the failing assertion and seed are unknown."}}
}
```

### B10 `phase3_scope` (owner-owned; run only after findings 8–10 are settled by hand)

*State:* the three sub-programmes (A constraint+freerouting, B industrial generators, C enterprise). PCB_STRATEGY §9 hypotheses. The Gerber KPI contradiction (as the owner resolved it). Criterion-12 trigger text. The feasibility filter already applied (drop classes needing switching converters or transients). Per surviving class: proof reuse, rule-library overlap with `rs485_node`, and whether transient simulation is needed. `<PASTE: any HVAC-customer conversation notes>`.

```json
{
  "phase3_order": {"type": "choice", "instructions": "Which Phase 3 programme should start first?",
    "criteria": {"constraints_first": "Choose when the constraint layer needs no customers and is the stated moat.",
      "industrial_first": "Choose when customer evidence makes a specific industrial class urgent.",
      "parallel": "Choose when one engineer can sustain both without either stalling.",
      "need_more_information": "Choose when customer evidence (PCB_STRATEGY §9.3) is missing."}},
  "fit_<class_id>": {"type": "score", "instructions": "Fit of this industrial class as the first Phase 3 generator",
    "criteria": ["Needs machinery Circuit OS lacks (transients, switching)", "Mostly new proofs and rules", "Reuses some proofs and rules", "Reuses most proofs, rules and the RS-485 library"]},
  "gerber_kpi_reachable": {"type": "noul", "instructions": "As the KPI is now worded, is it reachable in Phase 3 without Gerber export?"},
  "prospect_sees_explanation_early": {"type": "noul", "instructions": "Will a prospect see a generated explanation within the first Phase 3 milestone?"}
}
```

*Mapping:* owner. If `prospect_sees_explanation_early` > 0.5, schedule the criterion-12 cold read before sales. The trigger text itself is fixed and never overridden.

### B11 Runtime template `transcription_fidelity` (R1/R3/R4; shadow first)

*State (per request):* `{"prompt": <user text>, "requirements": <IntentIR.requirements>, "catalogue": {rc_lowpass, voltage_divider, led_indicator, dht22_node, rs485_node: one-line descriptions}}`. Numeric leaves are pre-screened deterministically with `quantities()`/`grounded()` (`intent_patcher.py:217-262`), and only the semantic residue goes to Jev.

```json
{
  "stated_<field_path>": {"type": "noul", "instructions": "Does the prompt state or directly imply <field_path> = <value> <unit>?",
    "criteria": {"true": "The words say it or leave no other reading.", "false": "The value is absent, different in scale/unit, or belongs to another field."}},
  "function_asked": {"type": "choice", "instructions": "Which catalogue function does the prompt ask for?",
    "criteria": {"rc_lowpass": "An RC low-pass filter.", "voltage_divider": "A resistive divider.", "led_indicator": "An LED with a current-limiting resistor.",
      "dht22_node": "A DHT22 temperature/humidity node.", "rs485_node": "An RS-485 Modbus node.", "none_of_these": "Anything else, including band-pass or high-pass."}},
  "unrepresented_request": {"type": "noul", "instructions": "Does the prompt ask for anything these requirements do not represent?"}
}
```

*Mode mapping:* shadow logs only. Advisory flags any field not stably ≥ 0.9, and a `function_asked` argmax different from `requirements.function`. Blocking-toward-refusal (after the corpus gate) returns the 422 confirm question when p < 0.5 on any field. Never auto-correct.

### B12 Runtime template `patch_op_faithful` (R2; shadow first)

```json
{
  "op_<k>": {"type": "noul", "instructions": "In the command '<C>', do the cited words '<W_k>' ask to <set <path> to <value> | remove <path>>?"},
  "command_fully_covered": {"type": "noul", "instructions": "Do these operations together make every change the command asks for, and nothing else?"}
}
```

*Mapping:* blocking only as a refusal (`JUDGE_DOUBTS_OPERATION`, v(n) kept). Never admits an op the citation guard refused. Seeded corpus: swapped values ("cutoff 2 kHz and supply 12 V"), unrelated-word removals, and faithful multi-op controls.

### B13 Offline `refusal_backlog` (R7)

```json
{
  "refusal_label": {"type": "choice", "instructions": "What does this refused request most need from Circuit OS?",
    "criteria": {"range_widen_existing": "An existing function refused on range; widen an envelope.",
      "high_pass_filter": "A new high-pass filter generator.", "band_pass_filter": "A new band-pass generator.",
      "op_amp_stage": "An op-amp stage.", "industrial_io": "24 V inputs, 4-20 mA, 0-10 V or relay I/O.",
      "out_of_scope": "Switching converters, PCB-only or free-form requests.", "ambiguous_request": "The request is unclear.",
      "none_of_these": "None of the above; a human should extend the label set."}}
}
```

*State:* the refusal row plus its deterministic group counts. `none_of_these` rows go to a human.

### B14 Phase 3 labels (P1–P4; stricter option until the user confirms)

```json
{
  "net_role": {"type": "choice", "instructions": "What role does net <name> play, given its connections?",
    "criteria": {"analog_0_10v_out": "Drives a 0-10 V control input.", "loop_4_20ma": "Part of a 4-20 mA current loop.",
      "relay_coil_drive": "Switches a relay coil.", "field_input_24v": "Receives a 24 V field signal.",
      "logic_local": "Board-local logic only.", "undeclared": "The connections do not determine the role."}},
  "env_label": {"type": "choice", "instructions": "Which install environment does the user's description indicate?",
    "criteria": {"pd2_ovc2_indoor_controlled": "Indoor, controlled, occasional condensation.", "pd3_ovc3_field_wired": "Field-wired, conductive pollution possible.",
      "pd1_sealed": "Sealed enclosure, no conductive pollution.", "need_more_information": "The description does not determine it."}},
  "isolation_needed": {"type": "noul", "instructions": "With ground-potential difference undeclared, could it exceed the RS-485 -7 V to +12 V common-mode range in this install?"},
  "standard_family_flag": {"type": "choice", "instructions": "Which standard family should a person review for this board?",
    "criteria": {"ul_60730": "Automatic electrical control for household or similar use.", "ul_61010_2_201": "Programmable controller.",
      "ul_508a_panel_only": "The board is a component of an industrial control panel.", "none_apparent": "No listed family apparent.",
      "need_more_information": "Product use is unclear."}},
  "possibly_life_safety": {"type": "noul", "instructions": "Could this board's failure plausibly affect life safety (gas valves, fire suppression, hood exhaust)?"}
}
```

*Mapping:* labels feed `ConstraintRule` tables and cite L2. Dimensions use the stricter of {Jev label, conservative default} until confirmed. `isolation_needed` short of a stable, confirmed "no" → isolated. `possibly_life_safety` > 0.1 → mandatory person review. Output is always worded as a flag.

### B15 CI `entry_covers_diff` and `failure_class` (T1/T2; advisory, fail-open)

```json
{
  "entry_covers_diff": {"type": "choice", "instructions": "Does the new decisions.md entry cover this diff?",
    "criteria": {"covers": "Every changed behaviour is named with its reason.", "partially_covers_missing_named_item": "Some change is not mentioned.",
      "unrelated": "The entry is about something else.", "need_more_information": "The diffstat is insufficient to judge."}},
  "failure_class": {"type": "choice", "instructions": "What kind of failure is this traceback?",
    "criteria": {"infra_hiccup": "Environment: timeout, missing binary, refused connection, tempfile/permission.",
      "accuracy_disagreement": "A numeric result outside its tolerance.", "test_nondeterminism_bug": "Order, seed or shared-state dependence in the test.",
      "unknown": "Cannot tell from the traceback."}}
}
```

*Mapping:* a comment or label only. A retry happens only if the deterministic classifier or a stable `infra_hiccup` says so **and** the test is not in an accuracy file.

### B16 `phase2_exit` (cannot be drafted faithfully yet)

Run this only after the owner records which deliverable list governs Phase 2 and pastes v2's exit text. Then, for each open defeater (D1, D2, D4, D7, and D9 where cited), ask one Choice `exit_<Dn>` over `acceptable_open_at_exit_with_trigger` / `must_close` / `need_more_information`, with the register text and trigger in the state. Whether each listed deliverable is done is checked deterministically against progress.yaml and never asked of Jev.
