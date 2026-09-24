# Current Phase: Phase 2 — Validation Engine

> Worker's instruction sheet. Set by the planner after each session.
> Last updated: 2026-09-24 (Stage 5 done; Stage 6 next, unplanned)
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

- ~~**Annotations are not rendered**~~ — drawn in the KiCad schematic since
  2026-09-24, as text beside their anchor (never as a label). Not in the BOM.
  `test_schematic_generator.py`; `brain/decisions.md` [2026-09-24].
- **The citation guard does not catch values swapped between two operations**
  whose cited words each contain the other's number, **nor a removal citing an
  unrelated word**. Mis-transcription (2 kHz → 20000) *is* caught since the
  verification below. The diff is shown to the user.
- ~~**No live-API test of the LLM patcher.**~~ — `tests/test_live_llm_paths.py`
  since 2026-09-23 (skipped without a key, like every live test).
- **The design route's own coverage is thin:** one test, that generate stores
  the requirement. It stays `test: None` in the trackers rather than being
  counted as verified on one case.

## Stage 2 verification — 2026-09-21

An independent check of Stage 2 (suite green, then probes past it) confirmed
determinism across processes and a JSONB round trip, locality over 443 random
patches, atomicity, and the version chain. It found three defects, **closed**,
with the reasoning in `brain/decisions.md` [2026-09-21] "Stage 2 verification":

1. Concurrent patches lost one of them → conditional revision write, 409 `version_conflict`.
2. The patcher's own pin form (`add /constraints/pinned/R1`) failed on every first pin → `constraints.pinned` is a container.
3. The citation guard let an uncited change through → whole words, one span per operation, value grounded in its span.

Also closed, second pass — `brain/decisions.md` [2026-09-21] "The Task 1.5
scanner becomes transitive":

4. The CircuitIR scanner followed model calls only within one file → model-facing names to a fixed point across the repo, in-place writes counted, reviewed exceptions by exact text.
6. `rc_lowpass` read `"12"` as the 5 V default, `true` as 1 and accepted a NaN tolerance → strict reader, named refusals; 0.2.0 → 0.2.1.

**Open from the same check, not yet done:** `rc_lowpass` pin parsing and
invented part numbers, patch refusals logged without their IntentIR, silent
migration failure, and stale `brain/architecture.md` / `MENTAL_MODEL.md`
entries for `ai/patcher.py`.

*Update 2026-09-21 (/update-memory):* the stale `brain/architecture.md` and `MENTAL_MODEL.md` entries are fixed — that item is closed.

**Carried from 2026-08-23, never diagnosed:** one test in `test_simulation_accuracy.py` was flaky (timeline, 2026-08-23). It passed in every full run on 2026-09-21; that is not a diagnosis. An infrastructure hiccup may be retried; an accuracy disagreement never may.

---

# Phase 2 — Stage 3: The generator library, claim objects, grade floor ✅ DONE 2026-09-23

> Gates in `PHASE_2_PLAN_v2.md` §5 Stage 3. The decisions — X6, X8, the
> defeater renumbering, and how each generator is checked — are in
> `brain/decisions.md` [2026-09-21] **X6 + X8**, written before any code.
> Backend committed as `9a4ecc6`; viewer and claims UI in the commit after.

## Task 3.1 — Record X6 + X8 before code ✅

Also renumbered the defeater register into one namespace (EVIDENCE_CLASSES' π
defeater → D8, the assurance case's D-G → D9) and fixed the build plan: what
each generator predicts, and what ngspice can check.

## Task 3.2 — Four generators on the contract ✅

`voltage_divider` (TPL_005), `led_indicator` (TPL_003), `dht22_node`
(TPL_001), `rs485_node` (TPL_002), registered after `rc_lowpass`. Shared
helpers in `generators/common.py` and `generators/arduino_parts.py`; device
models in `generators/netlist/models.py`, read by the netlist **and**
`predict()`. `tests/test_generator_library.py`.

## Task 3.3 — Grid gate for all five ✅

`validation/grid_adapters.py` — one adapter per generator, probes as CI test
benches. **Met:** every generator within 2% of ngspice at every grid point
(worst 0.0004%); every M1 seeded fault (P5, P20, X10) detected. Thinnest
margin: a 5% RS-485 terminator fault moves idle V_AB 2.3% — pinned by a test
so it cannot silently fall under the gate.

## Task 3.4 — Claim objects (X6, X8) ✅

`validation/claims.py`, `validation/defeaters.py`; `realize()` attaches
`validation_coverage`. Grades derived from method; open defeaters force
"holds, defeasible"; every `ValidationRule` accounted for on every design;
MCU models read from the netlist. `tests/test_claims.py`.

## Task 3.5 — grade_floor in regen_state.py ✅

Derived per generator and for the library, printed first in the summary with
coverage and defeater fan-out beside it. **Library floor today: G2** — the
divider's and LED's resistor-dissipation bounds (interval arithmetic: sound,
not tight). Everything else is G1.

## Task 3.6 — Visible rows and the waveform viewer ✅

`frontend/components/ClaimsTable.tsx` renders every claim, with *not assessed*
and *out of scope* as rows, most urgent first. `WaveformChart.tsx` draws AC
(log frequency) and transient traces as inline SVG; DC stays tabular. The
backend stores the points (`simulation/waveforms.py`, transient parsing in
`simulation/parser.py`). Checked in the browser against real ngspice output.
`tests/test_waveforms.py`.

## Stage 3 gates

| Gate | Result |
|---|---|
| All five at the Stage 0 grid gate (G5 ≤ 2%) | ✅ `test_generator_library.py::TestGridGate` |
| Every design emits claims with kind/grade/scope/defeaters | ✅ at every grid point of every generator |
| `grade_floor` derived in `regen_state.py`, reported first | ✅ G2 |
| "Not assessed" and "out of scope" rendered as visible rows | ✅ `ClaimsTable.tsx`, browser-checked |
| Waveform viewer renders AC / transient / DC | ✅ browser-checked with real ngspice data |

## Stage 3 — not done, and why

- ~~**No automated frontend test.**~~ — `frontend/e2e/validation.spec.ts` since
  2026-09-24 (`npm run test:e2e`): claims ordering, not-assessed and
  out-of-scope rows, sign-off and its 409, the AC waveform. The backend is
  mocked with JSON exported from the real pipeline
  (`scripts/export_ui_fixtures.py`); re-export when a response shape changes.
  Each test was seen to fail against a deliberately broken component.
- **Two claims sit at G2.** Resistor dissipation is not monotone in R, so it is
  bounded by interval arithmetic. Evaluating the interior critical point
  (R1 = R2′) alongside the corners would make it exact — G1. *Since then:*
  the divider's is decided exactly by its signed Stage 4 proof; the LED's is
  exact everywhere since Task 4.5.
- **`kind` is `analytic` for exact closed-form claims.** That answers, for
  Stage 3, the open question about the Stage 4 gate table (which says
  `empirical`) — flagged for the user rather than settled.
- **The DHT22 rise-time and sink limits are stated assumptions** (component
  table, D7), not datasheet figures; Aosong publishes neither.
- **Generated designs are simulated as DC operating points.** Only the RC
  filter produces an AC sweep; nothing yet produces a transient, so the
  transient view shows data only for a netlist that asks for one.

## Task 4.1 — Record Stage 4 before code ✅

`brain/decisions.md` [2026-09-23]: proofs from the design's own netlist, not
from `predict()`; bounds from `properties(intent)` rounded outward;
transcendentals bracketed; the LED by monotone reduction; sign-off by hash;
the frozen refine loop; the mutation gate. Dependencies approved by the user:
z3-solver 5.1.0.0, sympy 1.14.0, mpmath 1.3.0 (1.4.1 conflicts with sympy).

## Task 4.2 — The proof compiler ✅

`backend/proof/`: `brackets.py` (π, ln, expm1 as exact rational enclosures,
128-bit interval arithmetic), `netlist.py` (the SPICE text back into exact
elements; anything unreadable refused), `mna.py` (sympy nodal analysis: DC,
transfer function, Thevenin), `properties.py` (specs, statements, English,
hashes), `prover.py` (compile → z3 obligations → refine loop → certified
verdict; `falsify` for the mutation gate). `tests/test_proof.py`.

## Task 4.3 — Properties on all five generators ✅

13 properties per default design set, 64 across the CI grids, all proven:
divider V_out band and both dissipations (G1); LED current band, 20 mA pin
limit, 25 mA LED rating (G1) and R1 dissipation (G2, through a proven
current bound); RC cutoff band with π bracketed (G1); DHT22 rise time and
sink current (G1, cable capacitance and a DATA-low probe as test benches);
RS-485 fail-safe bias and driver load (G1, the far-end terminator in its own
1% box).

## Task 4.4 — Sign-off and freeze ✅

`IntentIR` 2.2.0: `SignOff.properties_hash`. `POST /design/{id}/sign-off`
takes the hash the user was shown — 409 on any other, on a generator
version change, or on a lost race; nothing written. Signed proofs become
critical, retire the Stage 3 claims they re-derive at an equal or better
grade, and remove D5. An edit drops the signature (Stage 1). The panel in
`frontend/components/PropertiesPanel.tsx` shows each sentence and signs the
set. `tests/test_sign_off.py`.

## Stage 4 gates

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

## Stage 4 — not done, and why

- **The LED dissipation stays G2.** Deciding I(R1)²·R1 ≤ P_max exactly needs
  the diode equation and R1 together, not a bound on I then a bound on R1.
  P peaks where R1 equals the rest of the loop's resistance; splitting R1's
  box there would leave each half monotone, and exact.
- **`kind` stays `analytic`** for the proofs, against v2's `empirical`, by
  EVIDENCE_CLASSES §3.1's own test; one field if the user wants v2's word.
- **The property set is signed whole.** Signing some properties and not
  others is not supported; a set with one refuted property can be signed,
  and its failure then stands as a signed, critical row.
- **No proof checker (G0).** z3's UNSAT is trusted; no certificate is checked
  independently.
- **Termination dissipation (RS-485) and the rail budgets are not
  properties.** The first needs a driven-bus bench; the second no single
  wrong part can break (decision item 7).
- ~~**No automated frontend test**~~ — see Stage 3: Playwright since 2026-09-24.

## Stage 3 + 4 verification — 2026-09-23

Checked against things that share no code with what they check; details and
the design choices in `brain/decisions.md` [2026-09-23] Stage 3 + 4
verification.

| Check | Result |
|---|---|
| Full suite before the fixes | 1446 passed, 15 skipped (live API ×13, test DB ×1, PCB golden regen ×1) |
| Full suite after the fixes | 1588 passed, 0 failing, 15 skipped (same three reasons) |
| Stage 3 bands vs ngspice corner extremes | 85/85 exact to 10⁻⁵ |
| Stage 4 properties vs ngspice (corners + interior) | 64 properties, 624 evaluations, 0 outside the proven bounds |
| Tightness (10⁻⁶ inside refuted, outside proven) | 83 refuted + 1 undecided (LED enclosure, by design); 42/42 proven |
| Mutation counterexamples replayed in ngspice | 64/64 real violations |
| Determinism and hashes across 4 hash seeds | identical, every signature accepted |
| Fuzzed requirements through `realize()` | 549 accepted designs clean after the fixes |
| Next.js production build | compiles, types and lint pass |

**Defects found and fixed:** (1) the refine loop accepted a proof over a
smaller box — the Stage 4 weakening gate was only partly met; (2)
denominators were not proved non-zero (none was zero; nothing enforced it);
(3) rc_lowpass 0.2.2 refuses a source that moves f_c past tolerance (0.2.3,
decided afterwards, swamps it with a larger R1 first); (4)
led_indicator 0.1.1 refuses an R1 that can exceed its rating (64.7 mW at
17 mA / 5.25 V was accepted) and drops the reverse-voltage figure it carried
as a supply rating; (5) `realize()` moved off the event loop in the generate
and patch routes.

**Not verified here:** sign-off against a real PostgreSQL (none available);
live-LLM paths; hardware (D1). *Closed the same day, as far as possible:*
PostgreSQL verified (`tests/test_postgres_signoff.py`); the live Phase 2 LLM
paths verified after fixing two producer defects (`tests/test_live_llm_paths.py`);
the explainer's truncation fixed, its latency with the configured model left
to the user (OpenRouter credits exhausted); hardware as a bench sheet,
`docs/BENCH_D1.md`. `brain/decisions.md` [2026-09-23] The unverified three.

## Decided after the verification — 2026-09-23

With TypeSafe (Jev), `brain/decisions.md` [2026-09-23] RC source swamping:

- **rc_lowpass 0.2.3** swamps a large declared source with a larger R1 (a
  smaller capacitor) before refusing. Implemented; designs that passed are
  unchanged.
- **LED dissipation stays conservative for now.** Scheduled below.

## Task 4.5 — Exact LED dissipation ✅ DONE 2026-09-24

led_indicator 0.1.2. `envelope()`, `predict()` / `led.resistor_dissipation`
and the `series_power` proof decide I²·R1 exactly — a proven monotonicity
lemma instead of splitting the box, same result, certificate checker
unchanged. 16.3–16.5 mA at 5.25 V accepted (true worst 62.0 mW); LED
dissipation G1; the library's signed floor G1. `test_proof.py`,
`test_sign_off.py`. Why the lemma: `brain/decisions.md` [2026-09-24].

---

# Phase 2 — Stage 5: Multi-MCU firmware ✅ DONE 2026-09-24

v2 §5 Stage 5. Decisions and findings: `brain/decisions.md` [2026-09-23]
Stage 5. User choices: PlatformIO with all three toolchains; the WeAct Black
Pill (STM32F411CEU6); the ESP32-DevKitC (WROOM-32E) as the ESP32 default.

## Task 5.1 — Record Stage 5 before code ✅

Targets as data, pins as claims, compile before display; the board a
constraint defaulting to the Uno, so every existing design is unchanged.

## Task 5.2 — Targets as data ✅

`data/mcu_targets.py`: `arduino_uno`, `esp32_devkitc`, `blackpill_f411ce` —
PlatformIO environment, logic rail, and a pin table (capabilities, reserved
pins and why, strapping pins and what they strap, UART routing, defaults).
Electrical figures (pin output resistance, recommended current, supply
model) in `component_constraints.py`; MAX3485 for 3.3 V buses.

## Task 5.3 — Pins are claims ✅

`validation/pin_rules.py`: `pin_assignment_valid`, `peripheral_conflict_free`,
`strapping_pins_safe` — exact checks of the design graph against the table
(G1, D7), run on every design by `claims.assess`. Generators refuse a bad
pin by name with the reason. Labelled set: `tests/fixtures/pin_assignments.json`.

## Task 5.4 — Generators on three boards ✅

led_indicator 0.2.0, dht22_node 0.2.0, rs485_node 0.2.0 read
`constraints.mcu`: rail, MCU supply model (`mcu_as_<R>R`, the Uno still
`mcu_as_100R`), pin Thevenin table, current limits, transceiver. Each
declares `boards` and `grid(board)`; the ngspice grid gate, the M1 matrix and
the Stage 4 proofs run on every board. The form and the LLM catalogue offer
the board, derived from the generators.

## Task 5.5 — Compile before display ✅

`generators/firmware/project.py` (PlatformIO project, pinned platforms and
libraries, SHA-256), `compile_gate.py`, `tasks/firmware_task.py` (Celery),
`firmware_builds` table (migration + schema.sql + model), and
`api/routes/firmware.py::firmware_view` — the one gate the generate, patch
and `GET /design/{id}/firmware` routes go through: source only once built;
otherwise compiling / failed (with the log) / unavailable. Stale builds are
dispatched again. `FirmwareViewer` polls while it compiles.
`platformio==6.2.0` in requirements; toolchain volumes in docker-compose.

## Stage 5 gates

| Gate | Result |
|---|---|
| 100% of emitted firmware compiles under PlatformIO before display (G1) | ✅ 21/21 — every generator variant on every board, and the Phase 1 examples; nothing is displayed unbuilt |
| Pin-mux, peripheral-conflict, strapping-pin checks on a labelled set (G1) | ✅ 56 labelled cases, zero disagreements |

## Stage 5 — found while building it

- **The LED sketch drove pin 13 whatever the design wired** — a Phase 1 bug,
  right on the Uno's default by coincidence. Fixed; every pin `#define` is
  now checked against the wiring on every board.
- **The worker did not load the compile task**, and **a lost result would
  have read "compiling" forever**. Both fixed and tested.
- ~~**Black Pill at 13 mA: the R1 dissipation proof is G2**~~ — G1 since the
  "falls" lemma was guarded (`brain/decisions.md` [2026-09-24] Task 4.5,
  amended). Pinned: no grid design falls back.

## Stage 5 — not done, and why

- **No board has been flashed.** Compiling proves the sketch is well-formed
  for the board, not that it runs; that is bench work, like D1.
- **The pin labels are the agent's own**, from the datasheets. An independent
  labeller would strengthen gate 2; D7 stays open on every MCU design.
- **The Docker worker is not exercised here.** Toolchains download on a
  board's first build into the `platformio` volume.
- **Strapping-pin checks are conservative**: any external connection to a
  strapping pin is refused, even where a careful design could use one.

## Next — Stage 6, BOM and substitution

Not yet planned at function level. Gates (v2 §5): no substitution surfaces
that fails the original's checks (G1); every price carries `price_asof`, and
pricing never gates validation (G1). Amendment X7 (live pricing supersedes
the static-BOM rule) says "Stage 5 only", but its content is Stage 6's
second gate; it is treated as Stage 6's. Live pricing is an authenticated,
rate-limited external dependency — ask the user before adding it.

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
pytest tests/ -q                    # current counts: state.json — not restated here

# Memory re-sync (run after every meaningful change)
python .claude/shared-memory/tools/regen_state.py
```

Test accounts: `test@circuitos.dev` / `TestPass123!`
ngspice: `C:\msys64\ucrt64\bin\ngspice_con.exe`
arduino-cli: `C:\Users\KIIT\bin\arduino-cli.exe`
AI: the model named by `AI_MODEL` in `.env`, via OpenRouter (`ANTHROPIC_BASE_URL=https://openrouter.ai/api`) — read `.env`, not this line
