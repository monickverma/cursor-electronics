# Where a Jev (TypeSafe) typed judgment fits in Circuit OS's assurance layer

Scope note. The code evidence comes from the snapshot `scratchpad/p2`, which is `origin/phase2-stage0` @ e803a99. It is one commit behind 94b61c1 ("D2 derived") and does not include the uncommitted D7/Stage 6 work (`data/parts.py`, `data/figures.py`, `validation/figure_audit.py`, `generators/bom/substitution.py`, `scripts/verify_figures.py`). Anything about those files comes from `HANDOFF_2026-09-25.md` §8 and is marked [handoff]. The snapshot does not contain `EVIDENCE_CLASSES.md`, `PHASE_2_PLAN_v2.md` or `ARCHITECTURE_ASSURANCE_CASE.md`, so their section numbers are known only through code comments. File paths below are relative to `p2/`. Jev was not called. There are no Jev outputs here except those already recorded in `brain/decisions.md`. The web egress proxy blocked arxiv.org, csl.sri.com, ntrs.nasa.gov and sos-vo.org, so the literature findings rest on search-result abstracts and snippets, not full texts. This is flagged under Gaps.

## Q1. How are grades, verdicts, kinds, scope and defeater citations computed today, and who reads grade_floor?

### Takeaway
Every assurance output is computed by deterministic code with no model in it. The grade is looked up from `method` in one table. The verdict comes from a boolean and the open status of the cited defeaters. D2, D5 and D9 are added by `assess()` itself, not by generators. `grade_floor` is the worst grade among critical, applicable claims. Today it is read only for display and state reporting: `ClaimsTable.tsx`, `regen_state.py` and an e2e test. The Stage 6 substitution gate ("floor not worse") will read it [handoff]. A Jev judgment has no structural entry point today, and it should stay that way.

### Cited Findings (code; each is its own source)
- **Grade is derived, never typed.** `METHOD_GRADE` is at `backend/validation/claims.py:59-71` (proof_checked→G0; z3_unsat, monotone_corners, closed_form and exact_graph_check→G1; sound_enclosure→G2; certificate→G3; bounded_model_check→G4; ngspice_nominal→G5; sampled→G6; asserted→G7). The `Claim._consistent` validator rejects any grade that does not follow from `method` (`claims.py:150-158`): "grades are derived, never typed". The same validator also refuses unregistered defeater IDs (`claims.py:147-149`). A claim with a verdict of holds, holds_defeasible or fails must have a method and a scope (`claims.py:159-161`). A not_assessed claim must be G7 (`claims.py:168-169`).
- **Verdict.** `graded()` at `claims.py:173-198` sets holds→`HOLDS_DEFEASIBLE` when any cited defeater is open, and otherwise `HOLDS`; a false result gives `FAILS`. The validator rejects plain `holds` alongside an open defeater (`claims.py:162-167`). The six verdicts are at `claims.py:115-121`. A defeater counts as open when its status is OPEN or DEFERRED (`backend/validation/defeaters.py:44-46`).
- **Kind.** `Kind` is analytic, empirical or projected (`claims.py:109-112`). `graded()` defaults to `Kind.ANALYTIC` (`claims.py:181`). Proof rows are hard-coded `Kind.ANALYTIC` (`claims.py:479, 498`). `Kind.EMPIRICAL` is defined and never used by any backend claim (grep of `backend/`). No code computes anything from `kind`: `summarise` ignores it (`claims.py:237-265`), and the frontend only types it (`frontend/lib/api.ts:98`). `ClaimsTable.tsx` does not render it.
- **Scope.** `ClaimScope` has four fields: `parameters`, `horizon`, `model` and `inputs` (`backend/generators/protocol.py:153-172`). `model` is required ("An undeclared model is how a G1 proof gets presented as ground truth", `protocol.py:161-164`). The D7 work adds `ClaimScope.figures` [handoff §8]. `_with_models` appends the netlist-derived MCU models and D2 to behavioural claims (`claims.py:290-307`, X6). Proof scope is `netlist_mna` plus the MCU and LED models (`claims.py:486-487`).
- **Defeater citation.** Defeaters are cited in three ways. Generators cite their own in `claims()`. Proofs cite D1 always, D2 when there are MCU models, D7 when a statement uses datasheet figures, and D8 when bracketed (`claims.py:488-495`). `assess()` adds D5 when `provenance.producer == "llm"` and the set is unsigned (`claims.py:565-568`), and adds D9 when `generator.name not in M1_COVERED` (`claims.py:572-573`). Proofs never inherit D9: "a proof is checked against the netlist generate() emitted" (`claims.py:569-571`). `M1_COVERED = frozenset(ADAPTERS)` (`backend/validation/grid_adapters.py:199-202`). In the snapshot all five generators have adapters (`grid_adapters.py:183-196`), so D9 is not cited on current library designs.
- **Sign-off.** A set counts as signed when a hash exists, a signature exists, the intent is intact, and `signature.properties_hash == set_hash` (`claims.py:559-563`). Proof rows are `critical=signed or refuted` (`claims.py:506-508`). Signed proofs supersede Stage 3 claims of equal or worse grade (`_supersede`, `claims.py:518-538`). `IntentIR.sign_off(by, properties_hash)` is at `backend/core/intent_ir.py:236-251`.
- **grade_floor.** `summarise()` takes the critical claims whose verdict is not not_applicable or out_of_scope, and sets floor = the max grade by `GRADES` index. It sets `coverage_le_g2` = (critical rows with grade ≤ G2) / (critical rows), and `open_defeaters` = the open IDs cited by any claim (`claims.py:245-258`). The three are "never fused" (`claims.py:18-19, 219`). Readers: the headline stat in `frontend/components/ClaimsTable.tsx:47`; `frontend/e2e/validation.spec.ts:85`; the per-generator floor, library floor and "weakest" listing in `.claude/shared-memory/tools/regen_state.py:442-472, 610-613`; and the tests `test_claims.py`, `test_sign_off.py`, `test_generator_library.py` and `test_postgres_signoff.py`. The Stage 6 substitution gate surfaces a substitute only if the "floor [is] not worse" [handoff §8].
- **Where it is computed.** `realize.py` calls `assess(generator, intent, circuit)` and stores the result as `validation_coverage` (`backend/generators/realize.py:92-93`). Only `realize.py` stamps `circuit_id` (uuid5 of intent_id), version and generator (`realize.py:9-10, 54-68, 84`). `assess()` documents itself as "Deterministic, no simulator, no model" (`claims.py:543-551`).
- **One owner per fact.** Each fact has exactly one owner, and every other place links to it (`.claude/shared-memory/AGENTS.md:90-99`). "Why a choice was made" is owned by `brain/decisions.md`. Derived numbers are owned by `state.json`/`progress.yaml` ("Do not write a number into prose that a derived file already carries", `AGENTS.md:101`). At code level, "`spice.py` read[s] the same table entry: one owner per fact" (`brain/decisions.md:1146`).
- **Enforcement of the One Rule.** A static AST scan fails any module that "talks to a model *and* writes a `CircuitIR`", and model access is transitive (`tests/test_llm_cannot_write_circuit_ir.py:1-35`). The scanner "recognised a model only by the client factory's name" until it was made transitive (same file, lines 27-33).

### Inferences
- The claims layer already has two defences against a model silently improving assurance. Grade comes only from `method`, and verdict comes only from the booleans and the register. A Jev probability can only enter by one of three routes: a new `METHOD_GRADE` entry, a change of status in `REGISTER`, or a change to `signed_off`. Each of these is a single choke point that a test can guard.
- `assess()` is deterministic and model-free by design. Putting any Jev call inside it, even one that only adds a defeater, would make `validation_coverage` non-reproducible across runs and model versions, and it would put a model into the realize path. Jev outputs should sit beside `validation_coverage`, not inside it.
- The One-Rule scanner keys on the model client. The TypeSafe SDK is a different client, so it would not be recognised unless the scanner's definition of "model" is extended. That extension is a prerequisite for any Jev module under `backend/`.

### Gaps
- `EVIDENCE_CLASSES.md` §3.1–§5 (the definitions of kind, grade and scope, and Table A) is not in the snapshot. Only the code paraphrases it.
- `substitution.py`'s actual floor comparison was not inspectable (uncommitted).

## Q2. Defeaters D1–D9: what closes each, what it waits on, where Jev helps, and where Jev is dangerous

### Takeaway
Jev adds value only in doubt-surfacing and in ordering human work: triage, prioritisation, and flags that send a case to a person. It never adds value in closing a defeater. Every `eliminated_by` in the register names a non-model event: a bench measurement, reachset conformance, an external engineer, measured authoring cost, a human signature, interface contracts, per-parameter provenance with "no LLM-extracted rating gates a claim", or the M1 matrix. So a Jev judgment used to close a defeater would contradict the register's own text. Jev is most useful for D5 (a drift flag before sign-off), D7 (ordering 155 figure verifications), D4 (clustering the refusal backlog) and owner product calls. It is least useful, and most dangerous, for D3 (the project has already rejected LLM-as-judge for explanations) and D9 (already closed mechanically).

### Cited Findings
- The register and its closure conditions are at `backend/validation/defeaters.py:49-122`:
  - D1 (validated against maths and ngspice, not hardware): OPEN. Closed by "a bench measurement agreeing within tolerance". Trigger: lab access (`defeaters.py:50-57`). Bench sheet `docs/BENCH_D1.md`. The evidence-record code was decided on 2026-09-24 and has not been built [handoff §5, §8].
  - D2 (MCU simplified model): OPEN. Closed by "reachset conformance against the real device". "Nothing in Phase 2 is scheduled to close it" (`defeaters.py:58-68`). It is derived per claim from `R_MCU_`/`R_PIN_` in the netlist (`claims.py:28-30, 273-307`). There is an open owner product call on the RS-485 DE/RE 10 kΩ pull-down, "would let fail-safe claim drop D2" [handoff §7].
  - D3 (no external engineer has read an explanation cold): DEFERRED, so it still counts as open. Closed by "criterion 12's review". Trigger: "before the first external user is shown an explanation" (`defeaters.py:69-76`).
  - D4 (coverage growth may outrun one engineer): OPEN. Closed by "measured authoring cost per generator" (`defeaters.py:77-83`). The refusal backlog is the set of collected refusals ("that set is the backlog entry", `backend/generators/registry.py:15-19, 70-71`), persisted in `request_log.refusal_reason` (`backend/db/models.py:166`).
  - D5 (LLM may write the IntentIR): OPEN per design. Closed "per design: a person signs the back-translated properties" (`defeaters.py:84-91`). Properties are "back-translated to English by template — deterministic, no model" (`brain/decisions.md:1270-1272`). `Provenance` stores `producer`, `model` and `prompt_hash` only (`backend/core/intent_ir.py:118-139`). `request_log` stores `prompt_hash` and `intent_ir` (`models.py:161-163`). `circuit_designs.intent` is a Text column (`models.py:57`) that appears to hold the user's request text; this was not verified.
  - D6 (block proofs may not compose): NOT_YET_APPLICABLE (`defeaters.py:92-98`).
  - D7 (datasheet figures unverified): OPEN. Closed by "provenance per parameter; no LLM-extracted rating gates a claim" (`defeaters.py:99-105`). WIP: 155 records, each with a kind (guaranteed, typical, derived, standard or stated assumption), a source, "agent's reading written without opening datasheet", and a record hash. `figure_verifications.json` is empty. `figure_audit.py` perturbs each figure (145 pairs clean) and found the RS-485 1206 terminator boxed with the 0402 tolerance [handoff §8]. D7 is cited by five rule checks (`claims.py:86-94`) and by proofs that use datasheet data (`claims.py:492-493`). "DHT22 rise-time and sink limits are stated assumptions … Aosong publishes neither" (`plan/current_phase.md:545-546`).
  - D8 (π bracketing): ELIMINATED by rational bracketing in `proof/brackets.py` (`defeaters.py:106-114`).
  - D9 (a generator bug makes predict() confidently wrong): OPEN per generator until that generator is under M1 (`defeaters.py:115-121`). M1 = the seeded-fault grid gate at 2% (`backend/validation/envelope_grid.py:7-11, 63, 283-393`). All five generators are in `ADAPTERS` (`grid_adapters.py:183-196`).
- **Project precedent against model-judged explanations.** `scripts/review_panel.py` is "an automated pre-screen for criterion 12 … It does NOT close criterion 12. An LLM reading LLM output fills gaps from training" (`scripts/review_panel.py:1-12`). It uses an A/B ablation (explanation vs schematic+BOM only) with FROM_TEXT / PRIOR_KNOWLEDGE tags (`review_panel.py:18-28`). Substituting it for criterion 12 was rejected: "a descriptive and a consequential explanation score alike … The panel is a pre-screen and a regression metric, not evidence" (`brain/decisions.md:336-341`). LLM-as-judge for derived explanations was rejected on the same grounds (`brain/decisions.md:602-605`).
- **Jev precedent in this project.** On 2026-09-23 two Choice questions and three "noul" (yes/no probability) questions were sent with about 10.6k chars of state (`brain/decisions.md:1431-1475`). Answers: `rc_option` swamp 0.87, confidence 0.83 → implemented as rc_lowpass 0.2.3. `led_option` confidence 0.44 → "below TypeSafe's own threshold for acting, so the agent decided, taking the reversible option". "The user may overrule". The protocol is >0.9 act, 0.5–0.9 act with care, <0.5 a person decides or the most reversible option is taken [handoff §3]. Two earlier Jev passes reviewed X2/X4 (`decisions.md:768-770`), and one flagged X8 as due earlier (`decisions.md:1038`). The handoff also says Jev settled calls on D1, D2 and D7 [handoff §3]. Those entries are later than the snapshot and not visible here.
- **Literature on model help with defeaters.** CoDefeater (Gohar, Hunter, Lutz, Cohen; ASE '24) reports that LLMs "can efficiently find known and unforeseen feasible defeaters to support safety analysts" in a human-in-the-loop process — [CoDefeater, ACM](https://doi.org/10.1145/3691620.3695296); [arXiv 2407.13717](https://arxiv.org/abs/2407.13717). A 2026 paper notes that validating the quality of LLM-generated defeaters "remains predominantly manual and subjective" — [arXiv 2607.06039](https://arxiv.org/html/2607.06039). "Defeater Cards" (2026) characterises the management of defeaters — [arXiv 2606.11462](https://arxiv.org/pdf/2606.11462). Only the title and snippet were seen.

### Per-defeater map (inference, built on the findings above)

| D | Closed only by | Jev can help with (advisory, ordering, or flag-to-human) | Where Jev must never enter |
|---|---|---|---|
| D1 | Bench measurement within tolerance | Ranking which claims or grid points a scarce bench session should measure first (choice over claim ids: "which measurement most reduces doubt?"). Low value: 5 generators and a short list. | Any "hardware would agree" probability standing in for a measurement. Never reword D1 as "unlikely". |
| D2 | Reachset conformance | Framing the owner's RS-485 DE/RE pull-down product call as a Choice, as with the RC precedent. | Dropping D2 from a claim. D2 is derived from the netlist (X6) and must stay derived. |
| D3 | External engineer's cold read | Triage only: ordering which captured explanation to hand a human reviewer first, or pre-flagging explanations likely to be descriptive rather than consequential (a rubric score) so the author fixes them before the scarce human read. Use the review_panel ablation framing (score the explanation-only arm vs the no-explanation arm, per rubric row). | Closing, deferring or relabelling D3, or feeding criterion 12. The project already rejected this for LLM panels (`decisions.md:336-341`). The same argument applies to Jev: a model reading text answers from its own priors. It is not generative, but it is still a model. |
| D4 | Measured authoring cost | Classifying each refusal in `request_log.refusal_reason` against a label set (widen-envelope vs new-generator vs out-of-scope vs spec-error) to prioritise the backlog. Low risk, because it only orders human work. | Measuring authoring cost. D4's eliminator is a measurement. |
| D5 | Human signature over the back-translated property hash | The highest-value spot: a pre-sign-off drift flag. State = the original request text, the IntentIR requirements, and the template back-translated properties. Questions: "does any property contradict or add to the request?" (noul per property) and "which requirement is least supported by the request's words?" (choice). Show the flag next to the sign-off button. A low probability must never suppress or pre-fill the signature. | Signing, or substituting for the signature. Removing D5. Editing the IntentIR (this would re-open the LLM→requirement path that X2/X4/X5 guard). A Jev "looks faithful" risks automation bias exactly where the human is the defeater's only closer. |
| D6 | Interface contracts | None today (n/a). | — |
| D7 | Per-parameter provenance; no LLM-extracted rating gates a claim | Ordering the 155 records for verification by expected impact. Inputs: kind (stated assumption and typical first), fan-out (how many critical claims read the figure; `ClaimScope.figures` gives this), `figure_audit` sensitivity (how close a perturbation comes to flipping a verdict), and the "agent reading without datasheet" flag. A deterministic score may do most of this. Jev adds a noul per record ("is the agent's reading likely to disagree with the manufacturer's datasheet?") as a tie-break. | Writing any value into `figure_verifications.json`, or a Jev "plausible" counting as verification. The register's own eliminator forbids a model-derived rating gating a claim. |
| D8 | Eliminated | None. | — |
| D9 | M1 matrix detection of seeded faults | Little. All five generators are under M1. A possible use is suggesting new mutation targets beyond the one component per adapter (`grid_adapters.py:187-196`) ("which component fault would the 2% gate be least sensitive to?"). The RS-485 margin is thin: a 5% fault moves V_AB by 2.3% (`decisions.md:1200-1203`). The answer becomes a seeded-fault test, which then is the evidence. | "Suspicion of a generator bug" at a low probability must never keep D9 closed. Conversely, a high probability should open a human investigation, not flip the register, which is keyed on M1 membership. |

### Inferences
- Jev inputs should be asymmetric. A judgment may make the case look more doubtful: a flag, a queue position, an escalation to a person. It may never make it look better: close a defeater, raise a grade, drop a critical row. Even the "more doubtful" direction should not change `validation_coverage`, because that would bring nondeterminism into `assess()`. The escalation has to pass through a human, who then changes code or data under the usual gates.
- The dangerous zone is precisely the three human-closure points: D3 (review), D5 (sign-off) and D7 (verification). Jev placed there invites automation bias. It must be shown as a separate "a model's doubt" annotation and never as a pre-filled answer.

### Gaps
- No measured base rates exist for requirement drift in LLM-written IntentIRs. The abstention corpus reports 0/200 false accept and 0/200 false abstain [handoff §6], which is about refusal, not drift. Jev's value for D5 therefore cannot be quantified yet.
- The D1/D2/D7 Jev decisions the handoff mentions are not in the snapshot's `decisions.md`, so their states and outputs could not be checked.

## Q3. Proposed representation of a Jev judgment

### Takeaway
Do not make a Jev judgment a `Claim`. Make it a separate, append-only `Judgment` record that cites claim ids and defeater ids. It lives outside `validation_coverage` and is never read by `summarise()`, the substitution gate or sign-off. If it must appear in the claims table, show it as a non-critical G7 annotation. It must never carry a method that maps above G7.

### Cited Findings
- Adding a method to `METHOD_GRADE` automatically gives that method a grade, and verdicts of holds or fails require a method (`claims.py:59-71, 159-161`). A non-critical row is ignored by the floor and by coverage (`claims.py:245-252`). A not_assessed row must be G7 (`claims.py:168-169`).
- The existing Jev log format in `decisions.md`: model id `jev-1.13.0`, state size, the request script name, the question types, and a table of raw answers with confidence (`brain/decisions.md:1433-1451`).
- One-owner table: `AGENTS.md:90-99`.

### Proposal (inference; for the owner to decide)
1. **Evidence class.** Add a new class "advisory model judgment", outside G0–G7 and outside `Kind`. It is neither analytic nor empirical (it is not a measurement of the circuit). If it is ever placed in the claims table as a visible row, it uses `verdict=not_assessed`, `grade="G7"`, `critical=False`, and `method=None`, which the validator already permits. Do not add `"model_judgment"` to `METHOD_GRADE`, because that would let `graded()` give a Jev row a holds or fails verdict.
2. **Record shape (frozen Pydantic).** Fields:
   - `judgment_id`
   - `jev_model` (e.g. `jev-1.13.0`)
   - `request_hash` = sha256 of the canonical state plus the questions
   - `state_ref`: a pointer to the stored state text, not an inline copy
   - `questions[]`: type noul, choice (with labels) or rubric
   - `raw_outputs[]`, verbatim: the probability and the choice distribution
   - `confidence`
   - `policy_band`: act, act with care, or person decides
   - `targets`: `circuit_id` plus version, and claim ids, defeater ids or figure record hashes
   - `purpose`: triage, doubt, priority or drift_flag
   - `action_taken` and `decided_by` (a person or the agent), with timestamps
3. **Citing defeaters.** A judgment cites defeater ids as *topics*, e.g. `about: ["D5"]`. It never carries a status. The model validator should reject any judgment field named `status`, `eliminated_by`, `verdict` or `grade`.
4. **Owner.** A single table or JSONL (`judgment_log`, analogous to `request_log` and `sim_monitor.jsonl`) owns the raw outputs. `brain/decisions.md` links to the judgment id when a Jev answer informed a decision and does not restate the numbers. This is a small tension with the 2026-09-23 entry, which restated the table. Per-design judgments (D5 drift flags) are stored against `circuit_id` and version, like annotations. They are never part of `validation_coverage`, so sign-off hashing and `realize.py` stay untouched.
5. **Invariant tests (each with a negative control, as the process rules require).**
   - (a) Extend `test_llm_cannot_write_circuit_ir.py`'s model definition to include the TypeSafe client, and add a mirror scan: no module that reaches a Jev client writes `Claim`, `ValidationCoverage`, `REGISTER`, `SignOff`/`sign_off`, or `figure_verifications.json`. Negative control: a fixture module that does so must fail the scan.
   - (b) `assess()` output is byte-identical with the judgment log populated and empty.
   - (c) `METHOD_GRADE` contains no judgment method.
6. **Kind of the judgment itself.** If a fourth `Kind` is ever needed, "advisory" is a better name than "empirical". Reusing "empirical" would blur the owner-unsettled question in Q4.

### Gaps
- `EVIDENCE_CLASSES.md` was not available to check whether it already defines an expert-judgment or reviewer-opinion class that this should map to.

## Q4. The unsettled "`kind` on exact proofs: analytic vs v2's empirical" question, framed as a Jev request

### Takeaway
This is a naming and semantics call with no computational effect today. No code reads `Claim.kind`, and `Kind.EMPIRICAL` is never used. It is reversible (it is "one field per generator"). Under the project's protocol, a result below 0.5 defaults to the status quo (analytic), which is also the most reversible option. Several of its sub-questions are facts to be settled by grep, not by Jev, and they should be put in the state as facts rather than asked.

### Cited Findings
- The agent's settled-pending reading: "by EVIDENCE_CLASSES §3.1's own test (could a measurement falsify it? no) they are analytic, and the model-versus-reality gap is carried by D1 instead … If the user prefers v2's wording, it is one field per generator" (`brain/decisions.md:1208-1212`). This is repeated for Stage 4 at `decisions.md:1266-1269`, and flagged at `plan/current_phase.md:542-544, 608-609`.
- The `Kind` docstring: "analytic (true of the model by mathematics), empirical (measured), or projected (not yet an artifact)" (`claims.py:8-9`).
- v2 labels other gates "empirical, G1" (firmware compiles; pin checks on a labelled set, `decisions.md:1540-1541`) and the grid gate "empirical, G5 ≤ 2%" (`envelope_grid.py:7`, `rc_lowpass.py:5`). The Task 1.5 gate is labelled "analytic, G1" by the same §3.1 test (`tests/test_llm_cannot_write_circuit_ir.py:4-17`).
- There are no computational readers of `kind` (grep). The frontend type is `kind: 'analytic' | 'empirical' | 'projected'` (`frontend/lib/api.ts:98`), and it is not rendered in `ClaimsTable.tsx`.

### Draft request (not sent)
**The state must include:**
- The verbatim `EVIDENCE_CLASSES.md` §3.1 definition and its falsification test. This is not in the repo snapshot and must come from the owner's copy.
- v2's Stage 4 gate table row that says `empirical`, verbatim.
- The `Kind` docstring (`claims.py:8-9`).
- The facts that no code reads `kind`, that `Kind.EMPIRICAL` is unused, and that the UI does not render it.
- D1's text, and that D1 is cited on every proof row (`claims.py:488`).
- v2's other uses of "empirical" (compile gate, pin labelled set, grid gate).
- Who reads the label: external reviewers and the criterion-12 reader, and future Assurance-2.0-style readers.
- The cost of each option: one field per generator, plus tests.
- The reversibility of each option.

Do not include agent opinions phrased as facts.

**Questions:**
- `kind_for_exact_proofs` (choice): `analytic` | `empirical` | `split_by_object` (analytic for z3/closed-form statements over the model; empirical for the ngspice grid gate and compile gates, which are observations of a tool run).
- `v2_label_is_deliberate` (noul): "Is v2's `empirical` tag for z3-proved claims a considered classification rather than a drafting slip?"
- `external_reader_misreads_analytic_as_hardware_validated` (noul).
- `split_by_object_adds_confusion` (noul).

**Decision rule:** >0.9 act; 0.5–0.9 act with care and record it; <0.5 keep analytic (the status quo and the most reversible option) and leave it with the owner. The owner holds this call [handoff §7], so even a >0.9 result is a recommendation to the owner. The agent must not act on it alone.

### Inferences
- The ngspice grid gate (G5, a tool observation) arguably is "empirical" in v2's sense. v2 may mean "empirical about the tool", not "about hardware". The split option captures that, and it is the one Jev might distinguish.

### Gaps
- v2's exact wording is not available in the snapshot.

## Q5. Assurance-case literature: expert judgment and ML-assessed evidence

### Takeaway
The literature supports three things: (1) recording defeaters and their resolution explicitly; (2) using LLMs to *find* defeaters and to *pre-review* cases, with a human in the loop; (3) treating confidence as multi-perspective and non-fused. No source found treats an LLM or model judgment as evidence that discharges a claim. NASA's review is explicitly cautious. Precedent therefore exists for triage and doubt generation, not for evidence grading.

### Cited Findings
- Eliminative argumentation (Goodenough, Weinstock, Klein; SEI 2013/2015) holds that confidence grows as doubts (defeaters) are identified and eliminated. Its components are claims, evidence, inference rules, defeaters (rebutting, undercutting, undermining) and argument terminators — [SEI 2015 TR](https://www.sei.cmu.edu/documents/1248/2015_005_001_434813.pdf); [SEI 2013](https://www.sei.cmu.edu/documents/1426/2013_021_001_88010.pdf); [Toward a Theory of Assurance Case Confidence](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=28067).
- Assurance 2.0 (Bloomfield & Rushby) aims for indefeasible confidence assessed from logical, probabilistic, dialectical and residual-risk perspectives. Confidence "cannot be reduced to a single attribute or measurement". Developers "should vigorously explore potential defeaters … and should record them and their resolution". Tool support is Clarissa — [Assurance 2.0 page](https://www.csl.sri.com/users/rushby/assurance2.0); [Assessing Confidence with Assurance 2.0, arXiv 2205.04522](https://arxiv.org/abs/2205.04522); [Confidence in Assurance 2.0 Cases, arXiv 2409.10665](https://arxiv.org/abs/2409.10665); [Defeaters and Eliminative Argumentation in Assurance 2.0, arXiv 2405.15800](https://arxiv.org/html/2405.15800v1). These come from search abstracts; the full text was blocked. The project already cites Assurance 2.0's indefeasibility standard (`defeaters.py:4-7`).
- Assured safety arguments (Hawkins, Kelly et al.) pair the safety argument with a separate confidence argument about its evidence and inferences — [Hawkins et al., SSS'11](https://www-users.york.ac.uk/~rdh2/papers/HawkinsSSS11.pdf). A survey covers Bayesian and subjective-logic approaches to confidence and uncertainty — [Springer survey](https://link.springer.com/chapter/10.1007/978-3-319-63194-3_5).
- NASA TM-20250001849 (Graydon & Lehman, NASA Langley, 2025) reviewed 14 works on LLMs and assurance arguments. Secondary summaries report that LLMs aim for plausible-sounding, truth-indifferent output, and that "much remains to be demonstrated before LLMs can be considered fit for producing or assessing assurance arguments" — [NASA NTRS](https://ntrs.nasa.gov/api/citations/20250001849/downloads/NASA-TM-20250001849.pdf); [SoS-VO mirror](https://www.sos-vo.org/node/109473); a secondary summary at [Substack](https://p4sc4l.substack.com/p/much-remains-to-be-demonstrated-before). The primary PDF was blocked; the claims come from search snippets and secondary sources.
- LLMs as judges for GSN review (Yu, Sivakumar, Belle, et al.; Nov 2025 and JSS 2026) use predicate-based rules and a 1–5 rating. DeepSeek-R1 and GPT-4.1 perform best, and "human reviewers are still needed to refine the reviews" — [arXiv 2511.02203](https://arxiv.org/abs/2511.02203); [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0164121226002694).
- CoDefeater: LLMs find known and novel defeaters to support analysts — [ACM](https://doi.org/10.1145/3691620.3695296).

### Inferences
- Jev's typed outputs (a probability, a label distribution, a rubric score) fit the "LLM as pre-reviewer or defeater finder, human decides" pattern better than free-text LLM review does. They are quantifiable and calibratable, and they cannot hallucinate a citation, because they never generate text. That removes NASA's "invented citation" failure mode. It does not remove truth-indifference about the input.
- In Hawkins-style terms, a Jev judgment belongs in the confidence argument (doubt about the evidence and the process), never in the safety argument's evidence.

### Gaps
- No source was found on using calibrated probabilistic classifiers (as opposed to generative LLMs) as graded assurance evidence, or on regulator acceptance of that. There is also no located precedent for model-driven *review prioritisation* in safety cases specifically, although the LLM-judge papers imply it.

## Q6. Calibration: how to validate a Jev-derived item before trusting it

### Takeaway
Treat each Jev use as a gate that needs its own golden set, a negative control and a mutation check. This is the project's existing rule: every gate has a negative control, and an unevaluable point counts as a failure. It also needs a risk-controlled abstention threshold. The confidence bands (0.5 and 0.9) are TypeSafe's own and have not been validated on Circuit OS data.

### Cited Findings
- Project rule: "Every gate has a negative control / mutation check; unevaluable point = failure" [handoff §3]. This exists already for M1 seeded faults (`envelope_grid.py:283-393`, including the guard against a "fault" that is really a parse error, at lines 270, 311-317) and for proofs (64/64 mutation refutations [handoff §6]).
- LLM-judge calibration practice: calibrate thresholds on held-out human labels so that the error rate is bounded, and abstain to a human below the threshold — [Judge, Retrieve, or Abstain, arXiv 2608.17994](https://arxiv.org/pdf/2608.17994); [Calibrated Abstention, arXiv 2608.07517](https://arxiv.org/pdf/2608.07517). Report chance-corrected agreement (Cohen's κ / Krippendorff's α), not only raw agreement — [Galileo guide](https://galileo.ai/blog/calibrate-llm-judge-human-annotations) (vendor blog, lower authority). LLM judges show an agreeableness bias — [arXiv 2510.11822](https://arxiv.org/pdf/2510.11822).

### Proposed validation per use (inference)
- **D5 drift flag.**
  - Golden set: IntentIRs from the Stage 1 abstention corpus paired with their prompts, labelled faithful by the owner.
  - Mutation set: deterministic seeded drifts. Change a numeric target by 2× or more, drop a requirement, add an unrequested constraint, swap a board.
  - Gate: at least N% of seeded drifts flagged, and at most M% of faithful ones flagged.
  - Negative control: an identity "mutation" must not raise the flag rate.
  - Unevaluable (Jev unavailable or low confidence): shown as "not assessed", never as "no drift".
- **D7 prioritisation.** Retrospective. Once `figure_verifications.json` fills, measure whether Jev's order found disagreements earlier than the deterministic order (fan-out × sensitivity) or a random one. If it does not beat the deterministic baseline, drop it.
- **D3 triage.** Use the `review_panel.py` ablation design. Jev's rubric score on the explanation-only arm must separate known-consequential from known-descriptive explanations (a seeded pair, e.g. the `derived_explainer` versus the model output side by side in `decisions.md:595-600`). Negative control: the no-explanation arm must score lower. Otherwise Jev is grading its own priors.
- **D4 refusal classification.** A labelled sample of refusals, with κ against the owner's labels.
- **General.**
  - Pin `jev_model`. Re-run the golden set on any version change.
  - Log every judgment, including abstentions.
  - Never tune thresholds on the set used to report them.
  - Treat a Jev outage as "not assessed". It is never a pass.

### Gaps
- There is no labelled data yet for any of these sets. Jev's calibration on electronics requirement-drift tasks is unknown. TypeSafe's own calibration evidence was not available to this researcher.
