# Jev (TypeSafe) insertion points in the Circuit OS Phase 2 runtime and Stage 6

Sources are local files. `P2` = the code snapshot `/tmp/claude-0/-home-user-cursor-electronics/d7f1ec44-0d48-5872-8bcf-575641baec98/scratchpad/p2` (origin/phase2-stage0 @ e803a99). `HANDOFF` = `.../scratchpad/HANDOFF_2026-09-25.md`. `DEC` = `P2/.claude/shared-memory/brain/decisions.md`. Stage 6 / D7 files (`bom/substitution.py`, `data/parts.py`, `data/figures.py`, `validation/figure_audit.py`) are NOT in the snapshot; statements about them rest on HANDOFF §8 only. No Jev call was made; no Jev output below is real except the ones quoted from DEC.

## Q0. Ranked inventory of runtime decision points (the objective)

### Takeaway
Jev has real value at the two points the project itself names as unguarded: prompt→IntentIR transcription fidelity (no check compares attempt 1 against the prompt) and patch-op faithfulness (swapped values, removals citing unrelated words). Everywhere the decision is already deterministic (envelope, predict, claims, proofs, pin rules, compile gate, substitution gates, pricing), Jev must not be used. Jev may only ever push toward "ask the user / refuse / flag", never toward "accept".

### Cited Findings
- Project's own Jev protocol: >0.9 act, 0.5–0.9 act with care, <0.5 a person decides or take the most reversible option; "TypeSafe never overrides tool_use/IR rules" — [HANDOFF §3](HANDOFF); same thresholds applied in the RC/LED decision — [DEC:1431-1478](DEC:1431). So far Jev has been used only for developer-time judgement calls (RC swamping 0.87, LED 0.58/conf 0.44), never at runtime — [DEC:1446-1478](DEC:1446).
- Assurance grades: G0 proof-checked, G1 z3/monotone/closed-form/exact-graph, … G5 ngspice nominal, G6 sampled, G7 asserted/not assessed; grade_floor = worst critical claim — [HANDOFF §5](HANDOFF).

Ranked table (value × inverse risk; line numbers in P2):

| # | Decision point (file:line) | What is decided | Current mechanism | Known failure mode | Verdict |
|---|---|---|---|---|---|
| 1 | `backend/api/routes/design.py:89` → `:106` (after `ctx.intent_ir`, before the underdetermined check `:110` and dispatch `:122`) | Is the IntentIR a faithful transcription of the prompt? | Nothing. LLM tool_use (`ai/intent_producer.py:265-337`), guards only compare retry vs attempt 1 | "A first-call mistranscription of 2 MHz as 1 kHz passes every check, dispatches cleanly and ships" — DEC:663-670 | **Jev fits as an advisory fidelity flag** (yes/no per requested value + one for `function`); p<0.5 → convert to a question for the user (422 underdetermined-style), never auto-correct. Highest value. |
| 2 | `backend/ai/intent_patcher.py:289-354` (after `_assign` at `:344`) or `api/routes/patch.py:215-218` (before `apply_patch`) | Does each RFC 6902 op implement the words it cites? | Deterministic citation guard: verbatim whole-word span, one span per op, value grounded in span | Cannot catch values swapped between two ops or a removal citing an unrelated word — `intent_patcher.py:38-41` | **Jev fits as a per-op yes/no check**, shadow first, then may refuse (refusal keeps v(n), user rephrases). Must be labelled probabilistic, not "a guard" (DEC:839). |
| 3 | `backend/ai/intent_producer.py:303-324` (X5 retry comparison) and `:332-335` (retry trigger) | May the retry's result be dispatched? Should a retry fire? | Deterministic `_requested_values` add-only check (`:222-252`), `MAX_SEMANTIC_RETRIES = 1` (`:76`) | Added values are unchecked against the prompt (add-only escape hatch); retry fires on any refusal though it helps only for missing fields — DEC:653-661 | **Jev fits as advisory on added fields** ("is value v for field f stated in the prompt?"); p<0.5 → ask the user. Retry-firing classification: **shadow only** — the right fix is a deterministic structured refusal kind (DEC:659). |
| 4 | `api/routes/design.py:122-131` (dispatch/out_of_envelope) | In/out of catalogue | Deterministic `envelope()` via `generators/registry.py:179-214`; 0/200 corpus | Corpus measures envelope() over IntentIR, not prompt transcription (`tests/test_abstention_corpus.py:1-30`) | **Jev must not gate envelope** (deterministic, exact). Jev as an independent "which catalogue function does the *prompt* ask for (5 labels + none)" classifier compared with the LLM's `function` → **shadow/advisory disagreement flag**. |
| 5 | `intent_producer.py:341` (`_questions`) | Which fields to ask about | LLM `underdetermined` filtered to required, unset fields | Model omits a field and fails to flag it (DEC:655-658) | **Jev may add questions, never remove them** (removing a question is the guess direction). Low-medium value. |
| 6 | Offline over `request_log.refusal_reason` + `intent_ir` (`observability/request_log.py:24-26`, `generators/registry.py:15-21,105-111`) | Which refusals become Phase 3 generators | Nothing yet beyond "ranked by frequency" | Free-text reasons; raw prompts not stored (only `prompt_hash`, `db/models.py:161`) | **Jev fits offline** (choice-from-human-defined-labels per refusal). Zero runtime risk. |
| 7 | `api/routes/patch.py:434-500` sign-off; `core/intent_ir.py:236-254`; D5 `validation/defeaters.py:84-90` | Does the user agree to the proved properties | Human signs a hash of displayed sentences | Automation bias; prompt text is not available at sign-off time | **Jev as a pre-computed negative-only hint**; must not sign, must not close D5, must not show a positive "Jev agrees" badge. |
| 8 | `api/routes/design.py:155-161` explanation; `ai/explainer.py:62,102-122`; `ai/derived_explainer.py:69-100` | Is the explanation consequential; keep LLM enrichment?; max_tokens | Marker counting (`explainer.py:52-55`); human review for criterion 12 | Markers measure form not quality (DEC:~590-600) | **Shadow/telemetry only.** LLM-as-judge explicitly rejected as evidence for criterion 12 (DEC:336-341, 602-605). max_tokens is an owner cost decision. |
| 9 | Stage 6 `generators/bom/substitution.py` (not in snapshot; HANDOFF §8) | Which same-value substitutes surface | Deterministic G1 gates: re-dispatch, envelope, byte-identical netlist, no claim regression, floor not worse, all properties re-prove | BOM priced unknown parts as any same-value part (fixed) — HANDOFF §8 | **Jev fits only for ordering already-surfaced substitutes by stated user preference**; must not surface, filter or gate. |
| 10 | Stage 6 generator version-bump decision (HANDOFF §8 "generator version bumps decision") | Bump rc_lowpass etc.? | Agent/owner judgement | — | **Jev fits as a developer-time decision aid** (the D1/D2/D7 pattern, recorded in DEC), not runtime. |
| 11 | Pricing / `price_asof` / X7 live pricing (`generators/bom/compiler.py:236-270`; `plan/current_phase.md:751-758`) | Price shown | Static DB; X7 needs owner approval | — | **Jev must not be used**: pricing never gates validation and a probability has no place in a price. |
| 12 | envelope(), predict(), claims, proofs, pin rules, grid gate, ngspice grader, PlatformIO compile gate, realize stamping | Correctness | Deterministic G0–G5 | — | **Jev must not be used**: any Jev input would downgrade a G1 claim to at best "asserted" (G7) and create a model→design path. |
| 13 | `ai/form_producer.py` (0 calls) and `ops`-only patches (`patch.py:198-199`) | — | Deterministic, zero model calls | — | **Jev must not be used**: these are the LLM-optional paths (DEC item 8, ~line 845); adding a model call would break "0 calls". |

### Inferences
- Rank rationale: #1 and #2 close gaps the project records as open with "no local fix" (DEC:663-670; `intent_patcher.py:38-41`), and they act on the LLM-written IntentIR layer, which is already D5-untrusted, so an advisory probability does not lower any grade. #4–#6 are cheap but duplicate deterministic machinery or are offline. #7–#10 have real automation-bias or gating risk if misused.
- Universal safety property to enforce in tests: for every point, the set of requests that end in an accepted design with Jev enabled ⊆ that set with Jev disabled (Jev can only subtract/ask/flag).

### Gaps
- No Jev API contract in the repo (question types beyond "choice"/"noul" seen in DEC:1446-1452, request format, latency, pricing, version pinning). The ~70–500 ms / cheap figures come from the task brief, not a source I could read.
- No calibration data for Jev on this domain; DEC only records 5 developer-time answers.

## Q1. intent_producer.py, X5, abstention corpus — second-opinion abstention / retry fidelity

### Takeaway
The 0/200 corpus measures deterministic `envelope()` over hand-built IntentIRs, not prompts, so a Jev "second opinion" on abstention adds nothing there. The value is upstream, at transcription: an independent Jev yes/no per requested value (and a catalogue-label choice for `function`) at `design.py:106`, and a Jev check on values the X5 retry *added* at `intent_producer.py:312`.

### Cited Findings
- X5 as implemented: schema failure → no retry, raises with raw input; semantic refusal → one retry; retry "may add, never change or drop" — `P2/backend/ai/intent_producer.py:11-56`, loop `:279-337`, `MAX_SEMANTIC_RETRIES = 1` at `:76`, truncation check `:406-415`.
- The add-only comparison: `first_requested` vs `current`, raising `Failure.RETRY_REWROTE_REQUEST` — `intent_producer.py:303-324`; `_requested_values` flattens targets/constraints/preferences and (after the defect fix) `function` — `:222-252`; DEC:611-627 (band-pass→low-pass walk-around reproduced before the fix).
- Retry fires on any dispatch refusal: `result = self._registry.dispatch(intent); if result.accepted or attempt == MAX_SEMANTIC_RETRIES: return intent` then `_append_refusal` — `intent_producer.py:332-336`.
- Four of five advisors wanted 0 retries; proposed fix is a structured refusal kind (`missing_field` vs `out_of_range`) on `EnvelopeDecision`, left for the user — DEC:653-661.
- "Nothing compares attempt 1 against the user's prompt … A first-call mistranscription of 2 MHz as 1 kHz passes every check … The 0/200 abstention figure measured envelope matching, not transcription fidelity. That is A1's real exposure and no local fix closes it." — DEC:663-670.
- The corpus labels derive from the generator's declared envelope and call `RCLowPassGenerator().envelope(intent)` directly; it measures whether the implementation honours its declaration — `P2/tests/test_abstention_corpus.py:1-30,160-171`.
- The route: `IntentProducer(registry).produce` at `design.py:89`; APIError → 503 at `:92-93`; `ctx.intent_ir` at `:106`; underdetermined → 422 questions at `:110-117`; dispatch at `:122-131`.
- Underdetermined filter: `_questions` keeps only required, unset fields of the chosen function — `intent_producer.py:341-363`; DEC:1501-1510 (live defect: invented field names, spurious questions).

### Inferences
- **Insertion A (highest value): transcription fidelity, `design.py` between `:106` and `:110`.** Questions (all yes/no or choice; Jev never writes a value):
  - per leaf of `_requested_values(intent.requirements)`: "Does the prompt state or directly imply `targets.cutoff_hz = 1000` (Hz)?";
  - choice over the catalogue function labels + `none_of_these` for "which function does the prompt ask for?", compared with `requirements.function` (would have caught the band-pass→low-pass class of error at attempt 1, not just on retry);
  - optional: "Does the prompt ask for anything not represented in these requirements?" (catches silent drops of a whole requirement).
  Action: p<0.5 on any → do not dispatch; return the same 422 shape as underdetermined with a question naming the field ("You wrote X; we read cutoff 1 kHz — confirm"). 0.5–0.9 → dispatch, attach a flag to the response and to the sign-off view. This is reversible (the user just confirms) and consistent with "underdetermined → ask, never guess".
- **Insertion B: X5 retry, `intent_producer.py:312` (inside the `else` branch).** The deterministic check stays primary and unchanged. For keys present in `current` but absent from `first_requested` (the "added" set), ask Jev "is value v for field f stated in the prompt?"; p<0.5 → return the intent as underdetermined on that field instead of dispatching. This closes the add-only escape hatch without touching the guard. Because `produce()` is synchronous and in a threadpool, a blocking HTTP call with a ~1 s timeout fits.
- **Retry-firing classifier (shadow only):** Jev choice over {missing_field, out_of_range, wrong_function, other} on `result.refusal_summary()` could decide whether the retry is worth its API call, but DEC:659 names the deterministic fix; Jev here should only log disagreement with that future field.
- **Out-of-catalogue second opinion on envelope: must not be used as a gate.** envelope() is exact and 0/200 on its own declaration; a probabilistic veto could only add false abstentions, and a probabilistic accept would violate the false-acceptance-zero asymmetry (`test_abstention_corpus.py:10-17`).
- A new corpus is needed to evaluate A/B: prompt text → gold IntentIR, with seeded mistranscriptions (unit scale ×1000, swapped fields, function substitution, dropped constraint). The existing corpus cannot measure it.

### Gaps
- Whether storing the raw prompt (needed to run A later or re-run calibration) is acceptable: today only `prompt_hash` is stored (`request_log.py:113`, `db/models.py:161`). Owner/privacy decision.
- Jev's accuracy on unit/scale questions ("2 MHz" vs 2e6) is unknown; the deterministic `quantities()`/`grounded()` from `intent_patcher.py:217-262` could pre-screen numeric leaves and leave only non-numeric/semantic ones to Jev.

## Q2. registry.py refusal log as backlog — clustering/prioritising for Phase 3

### Takeaway
Jev fits as an offline batch classifier over refused rows, mapping each refusal to a human-authored label set of Phase 3 candidates plus `none/other`, with a rubric score for priority. It must group deterministically first, and cannot invent cluster names (it does not generate text).

### Cited Findings
- Every refusal is collected, not just the first, because the set of reasons is the backlog entry — `P2/backend/generators/registry.py:15-21`; `DispatchResult.refusal_summary()` joins `generator: reason` — `:105-111`; a generator crash is recorded as a refusal — `:195-205`.
- "The out-of-envelope log is the generator backlog (§4.5): a refused request is a specification for the next generator. That is why `refusal_reason` is a first-class column" — `P2/backend/observability/request_log.py:24-26`; `Outcome.REFUSED` "feeds the backlog" — `:61-71`; row has `intent_ir`, `refusal_reason`, `prompt_hash`, `generator` — `:113-125`.
- Routes write `ctx.refuse(dispatch.refusal_summary())` at `design.py:124` and `patch.py:260`.
- `reason` is free text today — DEC:659-660.
- Out of Phase 2: switching converters, PCB layout, foreign-netlist recognition — [HANDOFF §9]; Phase 1 no-go list in `CLAUDE.md` (buck/boost, ESP32/STM32 now added in Stage 5).

### Inferences
- Pipeline: (1) deterministic group by `(intent_ir.requirements.function, refusing generator, normalized reason)`; (2) Jev choice over labels such as `band_pass_filter`, `high_pass_filter`, `buck_converter`, `boost_converter`, `op_amp_stage`, `sensor_node_other`, `range_widen:<generator>`, `none_of_these` for rows whose `function` is outside the catalogue; (3) Jev rubric "how much of Circuit OS's existing machinery (predict/proof/claims) would this candidate reuse" as a secondary rank next to frequency. Store answers; a human reads `none_of_these` rows and extends the label set.
- Distinguish "widen an envelope" (range refusal on an existing function) from "new generator" (uncatalogued function) — the registry docstring says that distinction is why all reasons are kept (`registry.py:18-21`); Jev should not blur it: range refusals are best counted deterministically.
- Risk is near zero (offline, no user path) but value is limited until traffic exists: OpenRouter credits exhausted 2026-09-23 (HANDOFF §4), so the refusal table is probably small. Scheduling this for Phase 3 planning is appropriate.

### Gaps
- Actual volume/content of `request_log` refusals is unknown (no DB access here).
- Because only `prompt_hash` is stored, clustering sees the LLM's transcription (`function` string) not the user's words; a mis-named function in the IntentIR propagates into the backlog.

## Q3. intent_patcher.py citation guard gaps — per-op Jev check

### Takeaway
A per-op Jev yes/no "does op k (path, value) faithfully implement the cited words W of command C?" plus one "does C ask for a change none of the ops makes?" directly targets the two documented gaps. It should start in shadow, then may become a one-directional refusal (the patch is refused, v(n) kept, user rephrases), explicitly recorded as a probabilistic check layered on, not replacing, the deterministic guard.

### Cited Findings
- Guard rules: verbatim whole-word citation; one span per op; value grounded in span — `P2/backend/ai/intent_patcher.py:14-32`; enforced in `propose` at `:289-354` (UNCITED_OPERATION `:314-320`, UNGROUNDED_VALUE `:327-339`, SHARED_CITATION `:344-350`).
- Documented gaps: "values swapped between two operations whose spans each contain the other's number ('cutoff 2 kHz and supply 12 V' recorded as cutoff 12, supply 2000), and a removal citing an unrelated whole word — a removal writes no value to ground." Binding spans to paths "was considered and rejected as a heuristic dressed as a guard" — `intent_patcher.py:38-44`; DEC:836-839.
- Mitigation today is the readable requirement diff returned with every patch — `intent_patcher.py:42-43`; `patch.py:80`.
- No retries of any kind on patches — `intent_patcher.py:46-49`; a refused patch keeps v(n) — DEC item 9 (~line 850).
- The command is persisted as `prompted_by` in `patch_history` — `patch.py:329`, `db/models.py:121` — so shadow judgments can be re-run later against real commands.
- Patcher `MAX_OUTPUT_TOKENS = 2048` — `intent_patcher.py:64`.

### Inferences
- Insertion: after `_assign(candidates)` succeeds (`intent_patcher.py:344`), or in the route between `propose` (`patch.py:200-215`) and `apply_patch` (`:218`). The route location is better: it keeps `IntentPatcher` a single-model-call module and puts Jev beside the request context for logging. Only for `command` patches; `ops` patches (zero calls) are untouched.
- Questions per op k: yes/no "In C, do the words W_k ask to set `<path>` to `<value>`?" (for replace/add) and "In C, do the words W_k ask to remove `<path>`?" (for remove). For the swap case each op is asked against its own path, so "cutoff 2 kHz" vs op `cutoff=12` should score low. Plus a completeness question to catch silently dropped requests.
- Why blocking is acceptable here but not elsewhere: blocking only produces a refusal, which is already the designed outcome of every guard failure, keeps v(n), and the user rephrases or sends `ops` — so false positives cost a retype, false negatives cost what they cost today. It must never *admit* an op the deterministic guard refused.
- DEC:839's objection (a heuristic presented as a guard) applies to Jev too: the decision entry must state the error rate measured on a seeded corpus (swap pairs, unrelated-word removals, plus correct multi-op patches as negative controls for false refusal), and the PatchFailure kind should be distinct (e.g. `JUDGE_DOUBTS_OPERATION`) so it is counted separately.
- Cost: ops per patch are few; N parallel Jev calls at 70–500 ms each is small next to the patcher LLM call.

### Gaps
- No measured Jev performance on swapped-number detection; must be measured before any blocking mode.

## Q4. Sign-off (D5) — Jev check that IntentIR represents the prompt

### Takeaway
Jev must not sign, must not close D5, and must not show a positive endorsement. It can supply negative-only flags computed at generation time (the prompt text is not available at sign-off), shown next to the property sentences the user reads.

### Cited Findings
- D5: "an LLM may write the IntentIR, so the specification is untrusted"; eliminated "per design: a person signs the back-translated properties" — `P2/backend/validation/defeaters.py:84-90`.
- Sign-off route checks hash of displayed sentences, generator unchanged, then `intent.sign_off(by=user.email, …)` — `P2/backend/api/routes/patch.py:434-500`; `IntentIR.sign_off` refuses while underdetermined ("a signature on an incomplete specification is worse than none: it looks like agreement") — `P2/backend/core/intent_ir.py:236-254`.
- Only `prompt_hash` is in provenance/log — `intent_producer.py:297-300`, `request_log.py:113`.

### Inferences
- Insertion: compute at Q1 insertion A (`design.py:106`), persist per-field flags with the design (new column via `db/migrations.py`, or the Jev table in Q7), and return them in the sign-off view data so fields with p<0.9 are highlighted ("check this: we read 1 kHz").
- The main risk is automation bias: a "verified by Jev" badge would make users sign without reading, quietly converting D5's human elimination into a model's. Showing only doubts (never "Jev agrees") and never storing Jev output inside `SignOff` avoids that.
- Jev never gates sign-off; a user may sign over a flag (it is their requirement).

### Gaps
- Whether the frontend sign-off UI can render per-field flags (not inspected; frontend out of scope).

## Q5. explainer.py vs derived_explainer.py — rubric scoring, criterion 12, max_tokens

### Takeaway
Jev rubric scoring is telemetry only. The project has twice rejected LLM-as-judge as evidence for explanation quality; Jev is a model and falls under the same argument. It cannot close criterion 12 or decide the max_tokens cost call.

### Cited Findings
- "LLM-as-judge (an LLM reading LLM output answers from its own training whether or not the text said anything — the same argument that kept `scripts/review_panel.py` from being allowed to close criterion 12)" rejected — DEC:602-605; the panel "is a pre-screen and a regression metric, not evidence" — DEC:336-341.
- Consequential markers list — `P2/backend/ai/explainer.py:46-55`; `EXPLANATION_MAX_TOKENS = 8192`, truncation raises — `:57-62, :117-121`; derived explainer 0 calls, 6/6 clear the marker bar; "Marker counting measures form, not quality … Criterion 12 — a human reading one cold — remains the only test" — DEC:~540-600.
- Live explanation takes 110–130 s and ~$0.20; RS-485 still exceeds 8192 tokens; raising max_tokens is an owner decision — DEC:~1512-1515; HANDOFF §7.
- Explanation is best-effort in the route — `design.py:155-161`.

### Inferences
- Allowed: an offline or shadow rubric (e.g. "does the text state a consequence of changing a component value", 0–N) run on both derived and live outputs as a regression metric alongside the markers, and as input to the owner's "keep the LLM enrichment?" decision. Labelled as a pre-screen, like `review_panel.py`.
- Criterion-12 triage use (choosing which designs' explanations to hand the external engineer) is low value; the engineer reading cold is the test, and the choice should be the whole library.
- max_tokens: Jev could be asked, as a developer-time decision aid per the protocol, but it is a cost/product call the handoff reserves for the owner.

### Gaps
- None beyond the absence of any Jev-vs-human agreement data on explanations.

## Q6. Stage 6 substitution and pricing

### Takeaway
All substitution gates are deterministic G1 and must stay the only gate. Jev fits only for (a) ordering already-surfaced substitutes by a stated user preference and (b) developer-time version-bump advice. Pricing never gates validation, and X7 live pricing is owner-approval only; Jev must not touch prices.

### Cited Findings
- Stage 6 gates: "no substitution surfaces that fails the original's checks (G1); every price carries `price_asof`, and pricing never gates validation (G1)"; X7 treated as Stage 6's; "Live pricing is an authenticated, rate-limited external dependency — ask the user before adding it" — `P2/.claude/shared-memory/plan/current_phase.md:751-758`.
- Substitution (uncommitted): tries each same-value catalogue part as a patch through apply_patch → dispatch → realize; surfaces only if envelope accepts, netlist byte-identical, no claim regresses, floor not worse, all properties re-prove; `constraints.pinned.<id>`; not done: GET /design/{id}/bom, BOMTable.tsx, api.ts BOMRow, module registration, generator version-bump decision — [HANDOFF §8]. Live pricing (X7) needs explicit approval — [HANDOFF §7].
- Current BOM compiler: static DB lookup, `price_known`/`price_source` so unpriced ≠ free — `P2/backend/generators/bom/compiler.py:12-36, 215-270`.
- Pins are requirements; a generator honours every pin or refuses naming it — DEC item 6 (~line 818).

### Inferences
- (a) Ranking: after the gate list is final, a Jev choice over the surfaced candidate IDs with a user preference string ("prefer through-hole", "what's in my drawer", "cheapest") → per-label probabilities used only as sort order; the list membership, and every claim, is unchanged. Test: set of surfaced substitutes is identical with Jev on/off.
- (b) Lifecycle/availability words: the catalogue is static JSON; flagging NRND/EOL is better as a deterministic field in `component_db.json`/`data/parts.py`. Jev over free-text notes is at most a telemetry flag.
- (c) Version bump: whether substitution-driven changes need a generator version bump is a developer-time call — a Jev choice {bump_patch, bump_minor, no_bump} with the scenario as state, recorded in DEC before code, is the established pattern (DEC:1431-1478). Note: a bump invalidates sign-off (`generator_changed` 409 at `patch.py` sign-off route), which should be in the state sent.
- Selecting a substitute on the user's behalf would be a requirement edit (it becomes `constraints.pinned`); if ever offered, it must go through the ops path with the user's explicit click, never a Jev decision.

### Gaps
- substitution.py code is not in the snapshot; line numbers for Stage 6 insertion cannot be cited.

## Q7. request_log — logging Jev answers for calibration

### Takeaway
Log Jev answers in a separate `jev_judgment` table (created via `db/migrations.py`, JSONL fallback like `request_log`), keyed by `request_id`, so each answer can later be joined to an outcome label (user confirmed/edited, rephrased, signed, abandoned). Do not overload `request_log.error` or `api_calls`.

### Cited Findings
- Two rules: a log write must never fail a request (JSONL fallback); a log write must never be lost because the request failed (own session) — `P2/backend/observability/request_log.py:9-22`; `RequestLogger.record` / `write_fallback` — `:255-300`.
- Row schema: `request_id`, `api_calls`, `prompt_hash`, `intent_ir`, `underdetermined`, `generator`, `refusal_reason`, `status_code`, `error` — `:74-125`; outcomes COMPLETED/REFUSED/FAILED/ABANDONED/PATCHED — `:61-71`.
- Earlier no-new-column reasoning (no migration tool) — DEC:644-651; superseded by `db/migrations.py` idempotent `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS` at startup — DEC item 2 (~line 792); `P2/backend/db/migrations.py:35-38`.
- `api_calls` counts model calls against §4.4's per-design budget — DEC:655-656; `ctx.count_api_call()` at `design.py:88`, `patch.py:199`.

### Inferences
- Columns: `request_id`, `point` (e.g. `transcription_fidelity`, `patch_op_faithful`, `retry_added_field`, `backlog_label`), `question_key`, `jev_model_version`, `answer` JSONB (probabilities as returned), `confidence`, `mode` (shadow/advisory/blocking), `action_taken`, `latency_ms`, `error`. Outcome labels are joined later, not written by Jev.
- Count Jev calls in their own counter so the §4.4 LLM-budget measurement stays clean.
- Calibration target: reliability curve per `point` before promoting shadow → advisory → blocking, using the protocol thresholds.

### Gaps
- Retention/privacy of storing question text that embeds prompt content is unresolved (see Q1 gap).

## Q8. Integration mechanics under project rules

### Takeaway
Optional `TYPESAFE_API_KEY` with a mode flag defaulting to off; one Jev client module registered in both state tools; the AST scanner must learn the Jev client as a model seed (it currently would not); every point must degrade to "off" when Jev is down; tests with fake-client negative controls and a monotonicity property.

### Cited Findings
- Required settings fail fast (`anthropic_api_key`, `database_url`, `redis_url`, `secret_key`); optional ones have defaults — `P2/backend/core/config.py:9-40`. Key is a Windows user env var — [HANDOFF §3] (pydantic-settings reads process env).
- Registration: `MODULES` at `P2/.claude/shared-memory/tools/regen_state.py:49` (e.g. `ai/intent_patcher` at `:111`), `CRITERIA_TEST_MAP` at `:178`; `PLANNED` at `tools/progress_gen.py:49` (e.g. `:405-407`); unregistered modules are invisible — `P2/.claude/shared-memory/AGENTS.md` (TRUST HIERARCHY section).
- AST scan: seeds are only `ai.client:make_client` and `ai.openai_compat:OpenAICompatClient` plus any `.messages.create` — `P2/tests/test_llm_cannot_write_circuit_ir.py:77`; writes = CircuitIR constructions, `model_copy(update=)`, attribute writes; scope `backend/` and `scripts/` — `:25-50, :72`; `_REVIEWED` allowlist — `:100`. Explicitly outside it: model output that goes through storage before a separate process builds a design — `:45-50`.
- Anthropic APIError in the producer path → 503 — `design.py:92-93`; client timeout default 45 s — `P2/backend/ai/client.py:12-37`.
- Decision entry before code; every gate has a negative control — [HANDOFF §3].

### Inferences
- Config: `typesafe_api_key: str = ""`, `typesafe_base_url: str = ""`, `jev_mode: str = "off"` (off|shadow|advisory|blocking, per point if needed), `jev_timeout_seconds: float = 1.0`. Empty key ⇒ off, like the `requires_api` pattern in tests.
- Module `backend/ai/jev_judge.py` (name illustrative): returns only typed floats/labels; exposes `judge_*` functions per insertion point; registered in `MODULES`, `PLANNED`, with its test file; not in `CRITERIA_TEST_MAP` (it closes no criterion).
- **Scanner hole to close first:** a Jev client using httpx would not be a seed, so a module that calls Jev and writes CircuitIR would pass `test_llm_cannot_write_circuit_ir.py`. Add the Jev client factory to `_SEEDS` with a negative-control fixture (module that calls Jev and constructs `CircuitIR` must fail). Separately add a narrower rule: Jev-facing modules may not construct `IntentIR`/`PatchOp`, call `with_requirements`, `apply_patch`, or `sign_off` — enforcing "Jev never writes IntentIR" structurally, since the existing scanner guards CircuitIR only.
- Fallback: any Jev error/timeout ⇒ behave exactly as mode off, log `jev_unavailable`, never 503/422 because of Jev. Unlike the producer's APIError→503, Jev is never required.
- Tests: (1) mode off ⇒ byte-identical responses and CircuitIR on the existing suite; (2) fake client returning each extreme (0.0/1.0/raise/timeout) ⇒ accepted-design set with Jev ⊆ without; (3) seeded negative controls: swapped-value patch, unrelated-word removal, 2 MHz→1 kHz transcription, band-pass→low-pass — fake client low ⇒ refused/asked; fake client high ⇒ existing behaviour; (4) mutation: remove the Jev call ⇒ negative-control tests fail (proves wiring); (5) live Jev tests auto-skipped without `TYPESAFE_API_KEY`.

### Gaps
- Jev SDK/HTTP interface and request schema not available here; the client shape above is a proposal, not verified against Jev.
