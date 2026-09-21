# Current Phase: Phase 2 — Validation Engine

> Worker's instruction sheet. Set by the planner after each session.
> Last updated: 2026-09-21 (Stage 2 done; Stage 3 next)
>
> **Phase 1 closed 2026-08-25 at 11 of 12 criteria.** Criterion 11 met by
> substitute, criterion 12 deferred with a trigger. Neither is met — see
> `state.json` for status and `brain/decisions.md` for why. Phase 2 is the
> Validation Engine per `PRODUCT_MASTER.md`.
>
> **The Phase 1 tasks below are kept, not archived.** Task 3 is deferred with a
> live trigger and Task 4 is closed; the rest record how Phase 1 finished. The
> next planner should write Phase 2 tasks above this line rather than editing
> history underneath it.
>
> Context: Phase 1 software is done. Since the last memory update the project also
> shipped a PCB layout engine (Phase 3 scope, pulled forward) and deployed to Railway.
> Neither was tracked by the memory system until 2026-08-07.

---

# Phase 2 — Stage 0: Instrumentation, harness, contract

> Opened 2026-09-20. Plan of record is `PHASE_2_PLAN_v2.md` §5 Stage 0 — read it
> for the gates; this file carries the tasks at function level.
>
> **Precedence, set 2026-09-20:** `PHASE_2_PLAN_v2.md` > `PRODUCT_MASTER.md` >
> `EVIDENCE_CLASSES.md` / `ARCHITECTURE_ASSURANCE_CASE.md`. PRODUCT_MASTER is
> the general flow; v2 refines Phase 2 inside its shape.
>
> Amendments X1–X8 in v2 §2 each need a `brain/decisions.md` entry **before**
> the code they touch. X1 and the `predict()` half of X3 are recorded
> ([2026-09-20]). X2, X4–X8 are not — do not start Stage 1 or Stage 2 work
> until the ones they depend on are.

## Task 0.1 — Log the rows ✅ DONE 2026-09-20

v2 §8 action 1, and §4.5: *"Data not logged is gone permanently."*

- `backend/observability/request_log.py` — `RequestLogRow`, `RequestLogContext`,
  `RequestLogger`, `prompt_hash()`, `log_ctx()`
- `backend/middleware/instrumentation.py` — `RequestLogMiddleware.dispatch()`
- `backend/db/models.py` — `RequestLog` table; DDL in `db/schema.sql`
- Hooked into `api/routes/design.py:generate_design`

**Success criterion:** `tests/test_request_log.py` passes. Met — 35 tests.

Two design decisions worth not re-litigating, both recorded in the module
docstring: the logger opens its **own** session rather than the request's,
because `get_db()` rolls back on exception and the rows most worth having come
from requests that failed; and a write that cannot reach Postgres lands in a
JSONL sidecar rather than raising, because observability must not be able to
fail the thing it observes.

**Gate status.** v2's Stage 0 gate is *"every request produces a complete log
row — G1, schema-enforced."* Completeness is enforced in `RequestLogRow` at
construction, keyed on what the request did rather than which route it hit. The
required set is deliberately narrow today and **tightens in Stage 1**: when
IntentIR exists, `intent_ir` and `generator` join the requirement for
`COMPLETED`, and `LOG_SCHEMA_VERSION` bumps in the same commit.

## Task 0.2 — `Generator` protocol, interface-contract fields included ✅ DONE 2026-09-20

v2 §8 action 2, and `ARCHITECTURE_ASSURANCE_CASE.md` §8.1: done **before** five
generators calcify the return type.

`backend/generators/protocol.py` — `Generator` is a structural
`typing.Protocol`: `name`, `version`, `envelope()`, `generate()`, `predict()`,
`grid()`, `dependency_closure()`.

**Success criterion:** `tests/test_generator_protocol.py` passes. Met — 34 tests.

**Two invariants are enforced by validators, not convention**, because both are
stated as G1 gates and a G1 claim that depends on everyone remembering is not
G1. A refusal cannot be constructed without a named reason — §4.5 makes the
refusal log the backlog, so the reason is a specification, not an error
message. An acceptance cannot be constructed without at least one
`PortContract` — if the interface contract were optional it would be skipped,
and Stage 3 composition would begin by editing all five generators.

**Front-loaded on purpose.** `PortContract` (composition, Stage 3+),
`ClaimScope` (claim objects, Stage 3), `grid()` (Task 0.4) and
`dependency_closure()` (locality, Stage 2) are all unused today and all exist
so that adding them later does not mean touching every generator. That is the
entire justification for doing this task second rather than last.

**`Interval` is amendment X1 in one type.** `predict()` returns bands, not
points: a statement about every component value in tolerance rather than one
nominal run. `ClaimScope.model` is required, so the MCU-as-100Ω assumption
(X6, defeater D2) has somewhere to live from the first generator onward.

**Scope note — a wrinkle in v2's own ordering.** v2 §5 puts the concrete
IntentIR schema in Stage 1 but this protocol, which consumes it, in Stage 0.
Resolved with `IntentLike`, a structural Protocol covering only what a
generator reads (`requirements`). Stage 1's concrete model satisfies it with
no change here. **Task 1.1 is unchanged** — it still owns the real schema,
validation, `underdetermined` semantics, sign-off/freeze and provenance.

## Task 0.3 — Port the RC low-pass generator and prove `predict()` ✅ DONE 2026-09-20

The first real generator, and the one that makes X1 concrete rather than
documentary.

`backend/generators/rc_lowpass.py` on the Task 0.2 contract.
`tests/test_rc_lowpass_generator.py` — 55 tests, ngspice harness reused from
`tests/test_simulation_accuracy.py`.

**Gate met.** `predict()` versus ngspice at all seven declared grid points,
100 Hz – 100 kHz: **worst deviation 0.0000%**, the residual being ngspice's
7-significant-figure print precision rather than disagreement. Same result the
criterion-11 harness reports for the netlist generator, which is the expected
outcome — both sides are the same mathematics, and that is exactly why the
negative control below is the part that carries weight.

**Three things worth not re-deriving:**

- **The gate compares like with like.** `predict()` returns a band over the
  tolerance box; ngspice simulates one nominal netlist. Asserting the
  simulated point falls inside a ±10% band would pass on almost any
  prediction. The gate therefore pins the box to the netlist's exact component
  values via degenerate intervals and compares point against point. The band
  is asserted separately, against the worked example in the research report
  (R ∈ [1574, 1606] Ω, C ∈ [90, 110] nF → 900.7–1123.3 Hz).
- **There is a negative control.** A 20% capacitor shift must push the
  measured cutoff outside the 2% gate. A gate that only ever passes tests
  nothing — the same argument that put the injected-5%-error check in
  `test_simulation_accuracy.py`.
- **`method="monotone_corners"`, not `sampled`.** `f_c` is monotone decreasing
  in both R and C, so the band edges are opposite corners of the box and two
  evaluations give the exact worst case. EVIDENCE_CLASSES §3.2 grades those
  differently, and it is the difference between a G1 claim and a G6 one.

**Component choice is deterministic**: fixed capacitor catalogue in declaration
order, R snapped to E96 in log space, ties broken by catalogue position. Note
E96 ≠ E24 — 4.7 kΩ is not a 1% value, and the nearest are 4.64 k and 4.75 k.
`IR_003`'s justification claims 1.59 kΩ is "E24 nearest", which is wrong on
both counts; this generator does not copy that.

**Byte-identical determinism is still blocked on Task 2.3.** `circuit_id`
defaults to a fresh `uuid4` per instantiation. `test_deterministic_modulo_circuit_id`
asserts everything the generator controls is reproducible and will be the test
that proves full byte-identity when 2.3 lands. Deliberately not worked around
locally.

## Task 0.4 — CI envelope-grid harness with a mutation check ✅ DONE 2026-09-20

**M1** in `ARCHITECTURE_ASSURANCE_CASE.md` §7, and the refutation of defeater
**D-G** — *"a generator bug makes `predict()` confidently wrong, and nothing
catches it."* That document ranks it the highest-priority doubt to close.

`backend/validation/envelope_grid.py` — a module rather than test-local code,
because Stage 3 runs the same sweep across the generator library and Stage 3's
claim objects will want the results as evidence.
`tests/test_envelope_grid.py` — 24 tests.

**Both gates met:**

```
control: rc_lowpass@0.1.0: 7/7 points within 2%, worst 0.0000%
P5:  DETECTED — 7/7 points outside 2%, worst  4.8403%
P20: DETECTED — 7/7 points outside 2%, worst 16.7323%
X10: DETECTED — 7/7 points outside 2%, worst 90.0000%
```

**The design decision that mattered, and the number that justifies it.** The
gate is the deviation from `Interval.nominal` — the generator's claim at its
intended component values — *not* whether the measurement lands inside the
tolerance band. Under the P5 arm every failing point reports **`in-band
True`**: a 5% capacitor fault sits comfortably inside a band that is ±10% wide
because the capacitor is a 10% part. **A harness gated on band containment
would have passed the entire seeded fault.**
`test_band_containment_would_not_have_caught_the_fault` pins exactly that, and
will start failing if the band ever tightens enough to make the point moot.

**A blindness bug caught in design, before it was written.** An earlier draft
read the realized component values back out of the generated design and pinned
`predict()` to them. Under a mutation arm that reads the *mutated* values, so
the claim and the design would have agreed again and the harness would have
been blind to the one fault it exists to catch. The claim under test is what
the generator predicts **from the intent**, compared against what the design it
produced actually does.

**A point that cannot be evaluated is a failure, never a skip** — a refused
grid point, a generator crash, a non-finite measurement, or a `measure()` whose
names do not intersect `predict()`'s. A harness that quietly drops what it
cannot handle reports a clean sweep over whatever happened to work.

**`MatrixReport.passed` requires both arms.** The clean design must pass *and*
every seeded fault must be caught. A detector that fails everything is not a
detector, and each half alone is satisfiable by a broken harness.

## Task 0.5 — The explanation-derivability test ✅ DONE 2026-09-20 — **qualified yes**

v2 §8 action 3 and §4.4, "the single highest-leverage experiment in Phase 2".

`scripts/explanation_derivability.py` · `backend/ai/derived_explainer.py` ·
`tests/test_derived_explainer.py` (24 tests).

**Answer recorded in full in `brain/decisions.md` [2026-09-20] — read it there,
not here.** In one line: the structural explanation is derivable with **zero API
calls** and clears the bar `tests/test_explainer.py` enforces (6/6 cases); the
domain-knowledge layer is not.

Six designs, derived versus live model, scored on the repo's existing markers.
Derived: 6/6 clear the bar, 6/6 name every component, 0 calls. The reason it
works is architectural — a deterministic generator already knows why it chose
what it chose, and `rc_lowpass` writes that rule into each `justification` as it
builds. Nothing is invented; reasons that already exist as data are assembled.

**What the model still supplies** and `predict()` cannot: ADC source-impedance
limits, sample-and-hold charging, X7R versus electrolytic, "use a ±2% C0G, not a
tighter resistor", and that a single-connection IN node means a filter fragment
rather than a finished netlist.

**Two caveats that must survive into any summary.** Only the `rc_lowpass` row is
a real test — the five example IRs carry Phase 1 LLM-written justifications, so
a derived explanation over them assembles model output rather than deriving
anything. And marker counting measures form, not quality: **criterion 12 is
still the only test of whether either version lands, and it is still open.**

### Found while running it — two defects in the shipping explainer

1. **`explainer.py` crashed on every call.** `response.content[0].text` assumed
   block zero is text; the configured `AI_MODEL` reasons first, so block zero is
   a `ThinkingBlock` and every explanation raised `AttributeError`. Fixed with
   `_first_text()`; `tests/test_explainer.py::TestReasoningModelResponses`
   pins it. The tool_use modules were **verified against the live API and left
   alone** — forced `tool_choice` suppresses thinking blocks, so
   `content[0].input` is correct there.
2. **`max_tokens=2048` is too small for a reasoning model** — some calls spent
   the whole budget thinking and returned no text block at all. Not changed:
   raising it is a product decision with a cost attached. The experiment widens
   the budget for its own calls only, so the comparison measures the model's
   explanation rather than truncation.

### Also found — an environment trap

`ANTHROPIC_BASE_URL` is exported in the Claude Code shell as
`https://api.anthropic.com`, and **pydantic-settings gives environment variables
precedence over `.env`** — so the OpenRouter routing in `.env` is silently
ignored and an OpenRouter key goes to Anthropic, which rejects it as invalid.
Anyone debugging "API key is invalid" should check this first.

---

# Phase 2 — Stage 1: IntentIR, registry, form, hard abstention

> Opened 2026-09-21. Gates in `PHASE_2_PLAN_v2.md` §5 Stage 1.

## Task 1.1 — IntentIR schema ✅ DONE 2026-09-21

`backend/core/intent_ir.py` · `tests/test_intent_ir.py` (27 tests).

The artifact `ARCHITECTURE_ASSURANCE_CASE.md` §2 rests the architecture on:
only this architecture materializes the requirement before the design exists.
Where it is not written down, *"this circuit does what was asked"* is not
verified badly — it is inexpressible.

**`requirements` is validated through `Requirements` and stored as a mapping.**
Generators read it through the `IntentLike` protocol frozen in Task 0.2, which
types it as a `Mapping`. Keeping it a mapping is what lets every generator
consume an IntentIR without reopening that protocol —
`test_a_real_generator_accepts_it_end_to_end` drives `RCLowPassGenerator`
through envelope → generate → predict on a real IntentIR, which is the
evidence that the Stage 0 ordering call was right.

**Three invariants worth not re-deriving:**

- **Frozen after construction.** An editable record makes `property_hash`
  meaningless and the Stage 2 patch chain unreadable. Edits go through
  `with_requirements()`, which returns a new version.
- **An incomplete specification cannot be signed**, at the schema level and
  not only in the helper. A signature on a spec still missing pieces looks
  like agreement, which is what sign-off exists to prevent.
- **A signature does not survive an edit to what it signed.** Changed
  requirements are by definition not the ones agreed to. This is the cheap
  version of Stage 4's freeze and the mitigation for defeater **D-B**.

`requirements_hash()` is key-order stable, so two producers that asked for the
same thing hash the same — required for the §4.4 cache and for sign-off to
survive a round trip.

## Task 1.2 — Generator registry and dispatch ✅ DONE 2026-09-21 (`2c53a3c`)

- `backend/generators/registry.py` — register generators, dispatch an intent
  to the ones whose `envelope()` accepts it
- Deterministic dispatch keyed on circuit class. The research report is
  explicit that an LLM adds nothing to solver choice at tiers 0–2 and that a
  deterministic dispatcher is easier to defend.
- Refusals from every registered generator are collected, not just the first —
  §4.5 makes the refusal log the backlog, and "nothing accepted this" is a
  weaker backlog entry than the set of reasons.

**Success criterion:** `tests/test_registry.py` — an intent inside one
generator's envelope dispatches to it; an intent outside every envelope is
refused with all the reasons; a non-conforming generator is rejected at
registration with the gaps named (`conformance_gaps` already does this).

## Task 1.3 — Form producer, generated from the registry ✅ DONE 2026-09-21 (`2c53a3c`)

- `backend/ai/form_producer.py` — build the field set from the registry so the
  form *is* the envelope catalogue
- Zero API calls. This is what makes the system provably LLM-optional (§4.2).

**Success criterion:** `tests/test_form_producer.py` — produces a valid
IntentIR for every registered generator with 0 API calls, and the field set
matches what the registry declares.

## Task 1.4 — LLM producer, and X5 ✅ DONE 2026-09-21 (`2c53a3c`, defects closed in `3122e30`)

X5 accepted — `brain/decisions.md` [2026-09-21]. The text below is the pre-decision note, kept.

Blocked on the X5 entry in `brain/decisions.md`. Recommendation on record:
accept X5, but make a schema failure a **loud** 422 carrying the raw tool
input rather than a silent one-shot failure — "schema failure is structurally
impossible" is an empirical claim about frontier models (§4.3 concedes it is
only structural under constrained decoding, which is unbuilt), so it should
announce itself if it ever breaks.

Note the interaction with Task 1.5: `circuit_reasoner.py` *is* a path by which
the LLM writes CircuitIR, so X5 may apply to the new IntentIR producer rather
than to that module's `except` clauses.

## Task 1.5 — Remove every path by which the LLM can write CircuitIR ✅ DONE 2026-09-21 (`2c53a3c`)

**Reopened and closed again in Stage 2:** `ai/patcher.py` was a second such path, written through `model_copy(update=...)`, which the scanner did not recognise. See Stage 2 below.

**Success criterion:** a test asserts it, rather than prose claiming it. This
is the architecture's load-bearing invariant and currently has no mechanical
guard.

## Task 1.6 — Labelled 200-case corpus, false-acceptance rate ✅ DONE 2026-09-21 (`2c53a3c`)

Reported **as a rate, with the corpus named** — v2 §1.2 calls the original
"false acceptance at zero" unmeasurable as written.

## Task 1.7 — Tighten the request-log row ✅ DONE 2026-09-21 (`2c53a3c`, LOG_SCHEMA_VERSION 1.1.0)

`intent_ir` and `generator` join the required set for a row that produced a
design; bump `LOG_SCHEMA_VERSION` in the same commit. The Stage 0 gate
ratchets as promised.

---

# Phase 2 — Stage 2: Patch model v2 ✅ DONE 2026-09-21

> Gates in `PHASE_2_PLAN_v2.md` §5 Stage 2. Every design decision, including
> the fifteen gaps the council and TypeSafe reviews found in X2/X4, is in
> `brain/decisions.md` [2026-09-21] **X2 + X4** — read it there, not here.

## Task 2.1 — Record X2 + X4 before code ✅

Decision entry written first, per v2 §2. Criterion 7's disposition, IntentIR on
the design record, and deterministic `circuit_id` are in it.

## Task 2.2 — IntentIR on the design record ✅

`circuit_designs.intent_ir` + `.annotations` (JSONB). `backend/db/migrations.py`
adds them to existing volumes at startup — the repo's first migration
mechanism, because `schema.sql` only runs on an empty data directory.
`tests/test_migrations.py`. A design with NULL `intent_ir` predates Stage 2 and
the patch route answers 409 rather than guessing a requirement.

## Task 2.3 — Deterministic `circuit_id` ✅

`generators/realize.py::realize` — the one place that turns an IntentIR into a
stored CircuitIR. `circuit_id = uuid5(namespace, intent_id)`; `version` =
`IntentIR.revision`; new `CircuitIR.generator` = `name@version`. **Determinism
gate met:** byte-identical across calls and across a serialisation round trip
(`tests/test_realize.py`). Derived from `intent_id`, not the generator version,
so a design keeps its identity through patches and generator upgrades.

## Task 2.4 — RFC 6902 patching on IntentIR ✅

`core/intent_patch.py` — `apply_patch`, atomic, restricted to `requirements`.
**Idempotence gate met:** a no-op is not a version and realises a byte-identical
design. **Readable history met:** `targets.cutoff_hz: 1000 → 2000`.
`tests/test_intent_patch.py`, which also re-earns **criterion 7** (five
sequential requirement patches) and is wired to it in `CRITERIA_TEST_MAP`.

## Task 2.5 — Locality ✅ (grade: projected)

`realize.check_locality` — CircuitIR component diff ⊆ declared closure, swept
over every declared path. **It found a real bug on its first run:**
`rc_lowpass.dependency_closure("constraints.supply_v")` said `{C1}`, but above
16 V the 100 nF part drops out and R1 is re-snapped. Fixed to `{R1, C1}`, with
a negative control that reinstates the Stage 0 closure and must fail. Graded
projected because two parts is nearly the whole circuit; it becomes evidence
with a larger generator.

## Task 2.6 — Annotation layer ✅

`core/annotations.py` — four kinds, anchored, merged after generation, never an
input (`realize` takes no annotations; asserted). **Orphans gate met:** kept
and reported, re-attach when the anchor returns. `tests/test_annotations.py`.
Rendering into KiCad output is not done — Stage 3 or later.

## Task 2.7 — Pinned parts ✅

`rc_lowpass` 0.1.0 → 0.2.0: `constraints.pinned` for R1 and C1, honoured or
refused by name, parsed with the SPICE netlist's own parsers. Unpinned output
checked identical to 0.1.0 over 150 accepted intents.

## Task 2.8 — LLM patcher and route ✅

`ai/intent_patcher.py` replaces `ai/patcher.py` (deleted — it was an LLM →
CircuitIR path; the AST scanner now catches `model_copy(update=...)`). Every
operation cites the command; no retries. `api/routes/patch.py` takes `command`
(1 call) or `ops` (0), refuses without writing, returns the requirement diff,
`predict()` delta, locality report and annotations; adds `PUT …/annotations`
and `GET …/history`. `tests/test_intent_patcher.py`, `tests/test_patch_route.py`
(mutation-checked: writing before the envelope check fails it).

## Stage 2 gates

| Gate | Result |
|---|---|
| Determinism: same IntentIR + version → byte-identical CircuitIR | ✅ `test_realize.py::TestDeterminism` |
| Idempotence: empty patch → identical output | ✅ `test_intent_patch.py::TestIdempotence` |
| Locality: diff ⊆ declared closure | ✅ swept — **projected** until a >2-part generator |
| Orphaned annotations surfaced, never dropped | ✅ `test_annotations.py::TestOrphans` |
| "Use a DS18B20 instead" end to end | ⏭ **deferred with a trigger** — no Phase 2 stage builds a DS18B20 generator. Replaced by *"make the cutoff 2 kHz"* with a `predict()`-delta justification: ✅ `test_realize.py::TestAcceptanceMakeTheCutoff2kHz` |

## Stage 2 — not done, and why

- **Annotations are not rendered** into KiCad/BOM output. They are stored,
  returned and carried; showing them in a schematic is output work.
- **The citation guard does not catch a mis-transcribed value** under a
  correct citation (2 kHz → 20000). The diff is shown to the user; the exposure
  is the one the X5 defects entry names.
- **No live-API test of the LLM patcher.** All its tests use a scripted client.
- **The design route's own coverage is thin:** one test, that generate stores
  the requirement. It stays `test: None` in the trackers rather than being
  counted as verified on one case.

---

## Not in Stage 0 — do not start

IntentIR, the form producer, registry dispatch (Stage 1) · patching on IntentIR
(Stage 2) · claim objects and `grade_floor` (Stage 3) · the proof compiler
(Stage 4). And per v2 §5: no buck/boost, no labelled ring, no PCB work, no
fine-tuning.

---

## Read This First — What Changed On 2026-08-07

A re-sync audit found the memory system had drifted badly from the repo:

| | Memory claimed | Reality at commit `1ae8f34` |
|---|---|---|
| Tests | 177 passed / 18 skipped | **257 passed / 24 skipped / 0 failing** |
| Snapshot commit | `9dfacd9` | `1ae8f34` (5 commits ahead) |
| Tracked entries | 32 | **60** |
| Verified | 84.4% | **48.3%** |
| Last timeline entry | 2026-06-03 | ~2 months of untracked work |

**Root cause:** `regen_state.py` and `progress_gen.py` track a hardcoded module
list. Anything not manually registered is invisible — it does not appear as
untested, it does not appear at all. The PCB engine (~2,400 lines) sat outside
the memory system for roughly two months while `progress.yaml` reported 84.4%
verified.

The 84.4% was never false. Its denominator was just wrong. The honest number is
**48.3%**, and it dropped because the tracker got more honest, not because
anything broke.

**Standing rule going forward:** when you add a module, register it in BOTH
`tools/regen_state.py` (MODULES) and `tools/progress_gen.py` (PLANNED) in the
same commit. An unregistered module is an invisible module.

---

## Phase Goal

Close out Phase 1 honestly, then tag v0.1.0.

Three workstreams, in priority order:

1. **Test debt on `explainer.py` and `patcher.py`** — blocking, and self-inflicted
2. **Criterion 11 via analytical cross-check** — the oscilloscope is not coming
3. **Criterion 12 external review** — still needs a human

---

## What Is Already Done (Phase 1 Software — do not redo)

| # | Criterion | Verified | How |
|---|-----------|---------|-----|
| 1 | JWT auth — all routes protected | ✅ 2026-06-02 | test_auth.py + live session |
| 2 | Full generation under 30s | ✅ 2026-06-02 | ~15s measured end-to-end |
| 3 | SPICE simulation runs and grades | ✅ 2026-06-02 | RC filter 3.536V at 1kHz |
| 4 | Simulation fails on wrong values | ✅ 2026-06-02 | 1nF capacitor → FAIL grade |
| 5 | Rule engine catches violations | ✅ 2026-06-02 | test_rule_engine.py |
| 6 | Firmware compiles to real Arduino | ✅ 2026-06-02 | arduino-cli, 3 templates |
| 7 | 5 sequential patches — no corruption | ✅ 2026-06-02 | v1→v6, manual only — see Task 1 |
| 8 | 20 prompts — zero crashes | ✅ 2026-06-02 | 6 fully verified, rest rate-limited |
| 9 | 100 requests — zero HTTP 500s | ✅ 2026-06-02 | 100×200 OK in 3.2s |
| 10 | Rate limiting — 11th request → 429 | ✅ 2026-06-02 | IP-based, confirmed |

Criteria 11 and 12 remain open. See Tasks 2 and 3.

---

## Task 1 — Pay Down Test Debt on the Explanation and Patch Layers ✅ DONE 2026-08-07

**Why this is first:** `PRODUCT_MASTER.md` Part 12 says the explanation layer *is*
the product. It has no test file. Criterion 12 is a cold read of its output by an
external engineer — so an untested `explainer.py` is a direct dependency of an
open criterion. Do not book someone's time to review output you have not pinned
down.

Criterion 7 has the same shape: 5 sequential patches passed by hand on 2026-06-02,
but `patcher.py` has no regression test. A manual pass that cannot be re-run is
not a criterion that stays met.

**Create `tests/test_explainer.py`:**

- Explanation is non-empty and exceeds a minimum length for each of the 5 templates
- Every component ID in the IR appears somewhere in the explanation text
- Explanation is **consequential, not descriptive** — assert on causal markers
  ("if you", "exceeds", "would fail", "instead of"). This is the differentiator;
  test it as one.
- Low-confidence decisions (confidence field below threshold) surface as warnings
- Simulation failures appear in the explanation rather than being silently dropped

**Create `tests/test_patcher.py`:**

- `patch()` returns only changed fields — assert the result is NOT a full IR.
  This is the invariant in `.claude/rules/code-style.md`; it is currently unguarded.
- `PatchResult.apply_to()` increments version
- Unchanged components are preserved byte-for-byte after a patch
- 5 sequential patches leave the IR schema-valid — automates criterion 7
- A patch referencing a nonexistent component_id is rejected, not silently ignored

**Success criterion:** both files pass, `entries_untested` for `ai/patcher` and
`ai/explainer` drops to 0, criterion 7 becomes reproducible rather than anecdotal.

**RESULT 2026-08-07 — done.** `tests/test_patcher.py` (19) and
`tests/test_explainer.py` (42, 3 live). Suite 257 → 318 passing, 0 failing.
Verified 48.3% → 56.7%. Criterion 7 is now automated.

Correction to the framing above: both modules already had 8 unit + 6 live tests
in `test_ai_layer.py`. They reported `untested` partly because the trackers
mapped them to `test_file: None`. The real gap was narrower — no deterministic
coverage of `patch()` or `explain()` without an API key, and no test at all on
the patcher invariant. Both are now closed.

Still open and NOT closed by this work: whether an explanation is actually
*good*. Keyword checks catch a prompt regression, not a quality regression.
Criterion 12 still needs a human — deferred 2026-08-25 with a trigger, not
done. See Task 3.

---

## Task 2 — Criterion 11 via Analytical Cross-Check (replaces bench test) ✅ DONE 2026-08-22

**Decision 2026-08-07:** no oscilloscope or function generator is available and
none is expected. The physical bench test is replaced as the Phase 1 gate.
Rationale recorded in `brain/decisions.md`.

**What criterion 11 was actually protecting against:** a netlist generator that
emits plausible-looking but wrong SPICE. It was never really about ngspice's own
numerical accuracy — ngspice is a mature, widely validated simulator. The risk
lives in `backend/generators/netlist/spice.py`, which is code written here.

An analytical cross-check catches exactly that failure mode.

**Create `tests/test_simulation_accuracy.py`:**

1. For each RC/RL/voltage-divider case, compute the closed-form expected value:
   - RC low-pass cutoff: `f = 1 / (2πRC)` → for R=1590Ω, C=100nF, f ≈ **1000.7 Hz**
   - Divider output: `Vout = Vin · R2/(R1+R2)`
   - Magnitude at cutoff: `Vout = Vin / √2` (−3.01 dB)
2. Generate the netlist through `SpiceNetlistGenerator`, run ngspice, parse.
3. Assert ngspice result is within **2%** of the analytical value.

Use 2%, not 15%. The 15% tolerance exists to absorb real component tolerance
(±5% resistors, ±10% capacitors) on a physical bench. There is no physical
component here, so anything beyond a couple of percent is a bug in the netlist
generator, not measurement noise. A loose gate on an exact comparison tests nothing.

**Also sweep the parameter space:** at least 5 R/C pairs spanning decades
(100Hz to 100kHz). A single 1kHz point can pass on a generator that has a
scaling bug.

**Success criterion:** all analytical cases within 2%. Criterion 11 is marked
`met_by_substitute`, not `met` — the distinction matters and must survive into
`PHASE1_COMPLETE.md`.

**State the limitation plainly.** This validates the netlist generator against
mathematics. It does not validate against physical reality — it cannot catch
parasitic capacitance, breadboard contact resistance, or a component behaving
outside its datasheet. Your public positioning is "simulates before it ships,"
so when lab access does appear, run the bench test and upgrade the criterion.
Do not let `met_by_substitute` quietly become `met` in a later summary.

---

**RESULT 2026-08-22 — done.** `tests/test_simulation_accuracy.py`: 34 tests, all
passing against ngspice-42. Six R/C pairs with cutoffs from 100Hz to 100kHz (81
sweep points each) plus five divider ratios, every point compared against the
closed-form transfer function. Worst measured deviation **0.0003%** — the
residual is ngspice's 7-significant-figure print precision, not disagreement.

Negative controls included: a capacitor wrong by a decade and a divider with the
wrong ratio must both blow the gate, and are asserted to. Separately verified by
injecting a 5% error into resistor emission — 13 of the 34 tests fail, while the
15% grader passes the same error silently. That gap is why the file exists.

Criterion 11 is `met_by_substitute`, tracked as `✅*` by `regen_state.py`. It has
NOT become `met`. The bench measurement is still owed if lab access appears.

---

## Task 3 — External Engineer Review (Criterion 12) — DEFERRED WITH A TRIGGER

> **Amended again 2026-08-25.** No longer a Phase 2 entry condition either —
> holding Phase 2's start against a third party's calendar reproduces the same
> problem one phase later. It is deferred with a **trigger: before the first
> external user is shown a generated explanation**, whichever comes first
> between a public launch, a demo to a prospect, or onboarding anyone outside
> this repo. See `brain/decisions.md` [2026-08-25].
>
> Deferred is not dropped. If the trigger fires and this has not been done, it
> is blocking at that moment — that is the whole point of naming one.
>
> **Amended 2026-08-22.** This no longer blocks v0.1.0. It gated the tag on
> another person's availability, which is why it stayed open for twelve weeks.
>
> The work below is unchanged and still worth doing — `CRITERION_12_REVIEW.md`
> has the protocol and scoring sheet, `outreach-messages.md` has the messages.
> `scripts/review_panel.py` gives an automated pre-screen in the meantime; it
> measures whether the explanation is load-bearing, which is a different and
> weaker claim, and it cannot close this criterion.



Unchanged from the 2026-06-02 plan, but **do Task 1 first** — reviewing output
from an untested explainer wastes the one thing that is hardest to get, which is
a qualified reader's attention.

1. Generate a DHT22 circuit: "Arduino reads DHT22 and alerts above 30°C"
2. Copy the explanation text verbatim. No prompting, no framing, no context.
3. Give them 10 minutes.
4. Ask: "Do you understand why each component was chosen, and what would break
   if it were changed?"
5. **PASS if they answer correctly with no help from you.**

If they are confused, the `explainer.py` system prompt needs stronger
consequential language — every sentence should answer "what breaks if this is wrong."

Candidate reviewers if none is identified: any EE final-year student or faculty
member, a local makerspace, or r/AskElectronics / EEVblog forums for an
asynchronous read.

---

## Task 4 — Decide The PCB Engine's Status ✅ DONE 2026-08-22 — **(b) experimental**

`backend/pcb_engine/` is ~2,400 lines: A* routing, DRC, footprint inference,
scoring, SVG rendering. It ships in the API and has a frontend tab. It has
**zero tests**.

The master plan puts PCB auto-layout in Phase 3 (months 8–18). It exists now.
That is not necessarily wrong — but it is undeclared, and undeclared scope is
how Phase 1 stops ever finishing.

Pick one and record it in `brain/decisions.md`:

- **(a) In scope, tested** — write PCB tests, add to the Phase 1 gate, accept the delay
- **(b) In scope, experimental** — ship behind a flag, label it clearly in the UI,
  exclude from the v0.1.0 gate, test in Phase 2
- **(c) Out of scope for now** — leave it, do not advertise it, revisit in Phase 3

**Recommendation: (b).** It is real work and demoing it is worth something, but
gating v0.1.0 on 2,400 untested lines of geometry code will stall Phase 1
indefinitely. An unlabeled experimental router in a tool whose entire pitch is
"physics-validated" is a credibility risk — the label is the important part.

**RESULT 2026-08-22 — (b) chosen.** Recorded in `brain/decisions.md` and
`PHASE1_COMPLETE.md` §4. What made it obvious rather than theoretical: the
placement pipeline was measured for the first time and `footprints.py` had no
SMD packages at all, so every 0402 passive was dropped. The RC filter and the
voltage divider compiled to empty boards, and the frontend tab had been
rendering them for roughly two months. Fixed — SMD packages added,
`tests/test_pcb_placement.py` guards it with 52 tests — but the experimental
label is the load-bearing part of the decision.

**CLOSED 2026-08-24 — UI labelling shipped.** PR #1, merged as `2bd73c8`.
`PCB_ENGINE_ENABLED` defaults to `None` and resolves from `environment`: on in
development, off in production, explicit value overriding either way. Disabled,
`POST /pcb/compile` returns 501 and `/health` reports the flag so the frontend
drops the tab rather than rendering one that errors on every click. Enabled, the
tab reads "PCB (experimental)". `tests/test_pcb_route.py` — 15 tests — pins the
gate and the ordering around it (auth before the gate, the gate before body
validation).

The label was the load-bearing part of (b), so this closes Task 4 outright.

Also shipped there, and the more important half: an empty board used to render
as a clean rectangle and read as a successful compile, which is how the dropped
components went unnoticed for two months. `PCBViewer` now opens its warnings
footer by default and shows an explicit banner when zero components placed.

---

## Task 5 — Final Sign-off

1. Check all 12 criteria, marking 11 as `met_by_substitute` with its limitation
2. Create `PHASE1_COMPLETE.md` with evidence per criterion, the PCB scope
   decision, and known limitations going into Phase 2
3. Run `/update-memory`
4. `git tag v0.1.0 && git push --tags`
5. Update this file to "Phase 2 — Validation Engine Planning"

---

## Current Blockers

| Blocker | Since | Resolution Path |
|---------|-------|-----------------|
| ~~No test coverage on explainer.py~~ | resolved 2026-08-07 | `tests/test_explainer.py` — 42 tests |
| ~~No test coverage on patcher.py~~ | resolved 2026-08-07 | `tests/test_patcher.py` — 19 tests, criterion 7 automated |
| PCB routing untested (`board_ir`, `kernel`, `router`, `render_pretty`) | ~2026-07 | Narrowed 2026-08-24. Scope and labelling are closed by Task 4 (PR #1); placement and `api/routes/pcb` are tested. Routing quality is not, and per `.claude/CLAUDE.md` the fix is freerouting in Phase 3, not tests for these 2,400 lines |
| ~~No oscilloscope access~~ | resolved 2026-08-22 | **Resolved by substitution** — `tests/test_simulation_accuracy.py`, 34 tests |
| ~~No external engineer identified~~ | deferred 2026-08-25 | Not resolved — **deferred with a trigger**: before the first external user sees a generated explanation. Task 3, and `brain/decisions.md` [2026-08-25]. Struck here so it stops reading as work in flight; it is not struck because it is done |
| OpenRouter rate limit (10/hr IP) | 2026-06-02 | 2s delay between calls in test scripts |
| Memory trackers need manual registration | 2026-08-07 | Register modules in both tools per commit |

---

## Environment to Start the App

**Use `start.bat` at the project root.** One click, brings up everything.

```bat
start.bat
```

It runs `docker-compose up -d db redis`, waits 6s for Postgres, then opens three
terminal windows: backend (uvicorn :8000), Celery worker (`--pool=solo`, required
on Windows/Python 3.13), and frontend (:3000). The PCB engine no longer has its
own port — it lives inside the API at `POST /pcb/compile`.

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Stop: close the 3 windows, then `docker-compose down`

Manual equivalents are in `brain/architecture.md` if you need to start one piece
alone.

```bash
# Tests
pytest tests/ -q                    # expect 318 passed, 27 skipped

# Memory re-sync (run after every meaningful change)
python .claude/shared-memory/tools/regen_state.py
```

Test accounts: `test@circuitos.dev` / `TestPass123!`
ngspice: `C:\msys64\ucrt64\bin\ngspice_con.exe`
arduino-cli: `C:\Users\KIIT\bin\arduino-cli.exe`
AI: `anthropic/claude-3-5-haiku-20241022` via OpenRouter (`ANTHROPIC_BASE_URL=https://openrouter.ai/api`)
