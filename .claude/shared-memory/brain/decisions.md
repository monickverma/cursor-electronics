# Decisions — LAYER 3

> Append-only. Never delete. Each entry answers: "why THIS way?"
> Format: decision → reason → alternatives rejected → date

---

## [2026-06-01] LLM writes JSON, not SPICE/KiCad/firmware directly

**Decision:** The LLM only ever produces CircuitIR JSON. Deterministic compilers
(Python functions) translate that JSON to SPICE, .kicad_sch, .ino, BOM.

**Reason:**
- LLM-generated SPICE hallucinates component models, wrong node names, broken syntax
- LLM-generated firmware uses wrong pin numbers, missing includes, imaginary libraries
- JSON → compiler is testable, reproducible, and debuggable
- One schema change (CircuitIR) updates all downstream formats simultaneously

**Alternatives rejected:**
- LLM writes SPICE directly — fails silently, no schema validation
- Template-free firmware — hallucinates DHT library function names

---

## [2026-06-01] tool_use mode only — never raw LLM text

**Decision:** All AI calls use `tool_choice={"type":"tool","name":"..."}` forcing
structured output. `response.content[0].input` is already a parsed dict.

**Reason:**
- Raw text responses require JSON extraction regex, markdown fence stripping
- tool_use eliminates the entire class of JSON parse errors
- Forces the model to produce a schema-conforming structure or fail cleanly

---

## [2026-06-01] ngspice not LTspice

**Decision:** ngspice is the SPICE engine.

**Reason:**
- LTspice EULA explicitly prohibits server-side automation and commercial use
- ngspice is BSD licensed — free for commercial SaaS
- ngspice is already integrated into KiCad

**Non-negotiable.** Do not add LTspice support.

---

## [2026-06-01] Jinja2 templates for firmware, not LLM generation

**Decision:** .ino files are rendered from Jinja2 templates (sensor_read.ino.j2,
modbus_master.ino.j2, base.ino.j2).

**Reason:**
- LLM-generated firmware hallucinates function names (DHT.readTemp vs dht.readTemperature)
- Templates produce identical output for identical input — testable
- arduino-cli compilation test can verify every template on every CI run

---

## [2026-06-01] Celery not inline simulation

**Decision:** All ngspice runs go through Celery tasks.

**Reason:**
- `await` releases the event loop but NOT the HTTP connection
- 30-second simulation would cause browser/load-balancer timeout
- Celery gives job_id → client polls → scales horizontally

---

## [2026-06-01] Static component_constraints.py not Qdrant RAG

**Decision:** Component constraints are a Python dict, not a vector database.

**Reason:**
- Datasheet excerpts are 4,000+ tokens each — $0.50–1.00 per generation call if embedded
- Python dict lookup is 0 tokens, 0 latency, 100% reliable
- Phase 2 adds Qdrant when breadth requires it

---

## [2026-06-01] Net labels in KiCad, not wire routing

**Decision:** KiCad schematic uses net labels to connect components, not wire routes.

**Reason:**
- Wire routing requires exact pin coordinates from KiCad symbol library for each component
- Net labels connect by name — generatable without a symbol library lookup
- Phase 3 adds proper wire routing

---

## [2026-06-01] bcrypt directly, not passlib

**Decision:** Password hashing uses `import bcrypt` directly.

**Reason:**
- passlib 1.7.4 is incompatible with bcrypt 4.x
- Direct bcrypt is simpler and avoids the dependency conflict

---

## [2026-06-01] No in-memory design storage

**Decision:** Every CircuitIR is persisted to PostgreSQL immediately after generation.

**Reason:**
- In-memory dict dies on server restart
- Breaks with multiple Celery workers
- Patch history and audit trail require persistent storage

---

## [2026-06-02] OpenRouter base_url must omit /v1

**Decision:** `ANTHROPIC_BASE_URL=https://openrouter.ai/api` (no /v1 suffix).

**Reason:**
- The Anthropic SDK appends `/v1/messages` to whatever base_url is set
- Setting base_url to `.../api/v1` results in `.../api/v1/v1/messages` → 404
- Verified by intercepting the HTTP request with custom httpx.HTTPTransport

**Applied in:** `backend/core/config.py`, `.env`, `.env.example`

---

## [2026-06-02] ngspice on Windows requires -o flag, not stdout pipe

**Decision:** `NgspiceRunner._run_sync()` uses `ngspice_con -b -o outfile.out infile.cir`
and reads the output file rather than capturing stdout.

**Reason:**
- ngspice_con.exe is a Windows console application that writes directly to the
  Windows console handle (CONOUT$), bypassing stdout/stderr pipes entirely
- `subprocess.run(capture_output=True)` always returns empty strings
- Verified: piping to file via `-o` captures all output correctly

**Applied in:** `backend/simulation/runner.py`

---

## [2026-06-02] ngspice AC output: magnitude = sqrt(real^2 + imag^2)

**Decision:** AC simulation values are computed as complex magnitude, not real part.

**Reason:**
- ngspice AC output format: `idx  freq  real,  imag` (complex pair, comma-separated)
- At 1kHz RC filter: real=2.502V, imag=-2.500V
- Real part alone = 2.502V (29% error vs expected 3.536V)
- sqrt(2.502^2 + 2.500^2) = 3.536V (exactly -3dB ✓)

**Applied in:** `backend/simulation/parser.py` → `_parse_ac_table()`

---

## [2026-06-02] ngspice emits separate table per variable even on single .print line

**Decision:** AC parser handles MULTIPLE tables (one per node) and merges by freq_idx.

**Reason:**
- `.print ac v(in) v(out)` — looks like one command
- ngspice still emits two separate tables, one for v(in), one for v(out)
- Plus paginates each table at ~55 rows repeating the header
- Parser must: find ALL headers, parse each table, merge by index into final result

**Applied in:** `backend/simulation/parser.py` → `_parse_ac_table()` full rewrite

---

## [2026-06-02] Celery on Windows Python 3.13 needs --pool=solo

**Decision:** Start Celery worker with `--pool=solo`.

**Reason:**
- Celery 5.x + billiard prefork + Python 3.13 on Windows fails with:
  `ValueError: not enough values to unpack (expected 3, got 0)` in fast_trace_task
- `--pool=solo` runs tasks in the main process, bypassing billiard
- Acceptable for single-machine dev; production Docker image (Linux) uses default pool

---

## [2026-06-02] Arduino Uno Modbus uses SoftwareSerial, not Serial1

**Decision:** `modbus_master.ino.j2` uses `SoftwareSerial` on pins 10/11 for RS-485.

**Reason:**
- Arduino Uno has only one hardware UART (`Serial` on pins 0/1)
- `Serial1` exists on Mega/Leonardo only
- `SoftwareSerial` is bit-banged on any two pins — works on Uno
- `Serial` (pins 0/1) stays free for debug output to Serial Monitor

---

## [2026-06-02] .env path resolved from config.py location, not CWD

**Decision:** `config.py` uses `Path(__file__).parent.parent.parent / ".env"`.

**Reason:**
- `env_file=".env"` resolves relative to CWD at runtime
- Running `uvicorn` from `backend/` directory looks for `backend/.env` (doesn't exist)
- The actual `.env` is at project root
- `Path(__file__)` always knows where config.py is, regardless of launch directory

---

## [2026-06-02] Rate limiting is IP-based (slowapi default)

**Decision:** Rate limits apply per IP address, not per user/token.

**Reason:**
- slowapi's default key function uses the request IP
- All localhost development traffic shares the 10/hour generate limit
- For production: override key function to use user ID from JWT

**Known limitation:** In dev, hitting the limit blocks all users from the same machine.
Use a second test account and wait 1 hour, or temporarily raise the limit in .env.

---

## [2026-08-07] Criterion 11 gate changed from bench measurement to analytical cross-check

**Decision:** The Phase 1 simulation-accuracy gate is an analytical cross-check
against closed-form circuit equations at 2% tolerance, not an oscilloscope
measurement at 15% tolerance.

**Reason:**
- No oscilloscope or function generator is available, and none is expected.
  The criterion had been blocking Phase 1 sign-off since 2026-06-02 with no path forward.
- The failure mode criterion 11 actually guards against is a netlist generator
  that emits plausible but incorrect SPICE. That risk lives in
  `backend/generators/netlist/spice.py` — code written here. ngspice itself is a
  mature, independently validated simulator; it is not the thing under test.
- Comparing ngspice output to `f = 1/(2πRC)` catches netlist-generation bugs
  directly, with no hardware dependency.

**Tolerance changed 15% → 2%:** the 15% figure existed to absorb physical
component tolerance (±5% resistors, ±10% capacitors) plus probe and breadboard
error. In a purely analytical comparison none of that exists, so a 15% gate
would pass a generator with a real scaling bug. Anything beyond ~2% is a defect.

**Recorded limitation:** this validates the netlist generator against
mathematics, not against physical reality. It cannot catch parasitic
capacitance, contact resistance, or a real component operating outside its
datasheet. Criterion 11 is therefore marked `met_by_substitute`, never `met`.
When lab access becomes available, run the original bench test and upgrade it.
The product's public claim is "simulates before it ships" — that claim is owed a
physical measurement eventually.

---

## [2026-08-07] Memory trackers require explicit module registration

**Decision:** Every new backend module must be registered in BOTH
`tools/regen_state.py` (`MODULES`) and `tools/progress_gen.py` (`PLANNED`) in the
same commit that introduces it.

**Reason:**
- Both tools iterate a hardcoded dict. An unregistered module is not reported as
  untested — it is not reported at all.
- `backend/pcb_engine/` (~2,400 lines across 7 modules) went untracked for
  roughly two months. During that time `progress.yaml` reported 84.4% verified.
  With the PCB engine registered, the honest figure is 48.3%.
- The reported number was never false. Its denominator was silently wrong, which
  is worse than a visibly failing test — it looks like health.

**Consequence:** entry count went 32 → 60 and verified percentage 84.4% → 48.3%
on 2026-08-07. The drop reflects better accounting, not a regression. Do not
"restore" the old number.

**Better fix, deferred:** make the trackers walk `backend/` and auto-discover
modules so this class of bug cannot recur. Not done yet — it is a larger change
to the tooling and was out of scope for the re-sync session.

---

## [2026-08-22] Phase gating targets visibility, not timing

**Decision:** Phase 2 work may proceed in parallel with Phase 1 sign-off. The
rule "Phase 2 does not start until v0.1.0 is tagged" is replaced by four
conditions: sign-off keeps priority, every new module is registered in both
trackers in the same commit, anything reaching the API or UI before the tag is
either tested or labelled experimental, and new scope is recorded here when it
starts rather than discovered later.

**Reason:**
- The original rule was written after the PCB engine appeared as undeclared
  Phase 3 scope during Phase 1. But the damage was not caused by building early.
  It was caused by ~2,400 lines that were untested, unregistered, and wired into
  the product UI while `progress.yaml` reported 84.4% verified.
- On 2026-08-22 that damage became concrete: the first real measurement of the
  placement pipeline found `footprints.py` had no SMD packages, so every 0402
  passive was silently dropped. Two of five templates compiled to empty boards.
  A shipping product tab had been rendering them for two months.
- A rule that says "don't build" gets ignored the moment someone is excited. A
  rule that says "register it, test it or label it" is one anyone can follow
  while still building.

**Consequence:** Phase 1 sign-off (criterion 12 outreach, PCB scope decision,
v0.1.0 tag) remains the priority queue, but is no longer a barrier to starting
Phase 2. `ROADMAP.md` §7 carries the user-facing version.

**Open question this does not answer:** which Phase 2 is Phase 2 —
`master_plan.md`'s Validation Engine or `PCB_STRATEGY.md`'s constraint layer.
The two documents describe different phases and neither references the other.
Recorded in `ROADMAP.md` §5 as an explicit decision still owed.

---

## [2026-08-22] Criterion 12 moved off the v0.1.0 gate

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
- Criterion 11 was already amended for a comparable reason (no oscilloscope).
  The pattern to avoid is not amendment; it is amending silently.

**What this deliberately does NOT do:** delete the criterion. PRODUCT_MASTER.md
Part 12 says the explanation layer is the product. It remains the only part of
the product with no verification from outside this repo, while the parts that
are not the differentiator carry 400+ tests. That is an odd risk allocation and
`PHASE1_COMPLETE.md` states it on its first page rather than burying it.

**Rejected alternatives:**
- *Drop it entirely.* Would make the criteria list something edited when
  inconvenient, which devalues the other eleven.
- *Substitute the agent panel* (`scripts/review_panel.py`). An LLM reading LLM
  output answers correctly from its own training whether or not the explanation
  said anything, so a descriptive and a consequential explanation score alike —
  and that difference is the entire product claim. The panel is a pre-screen and
  a regression metric, not evidence. Marking it as criterion 12 would be the
  quiet devaluation this decision is trying to avoid.

---

## [2026-08-22] PRODUCT_MASTER.md is canonical; Phase 2 is the Validation Engine

**Decision:** The `PRODUCT_MASTER.md` at the repo root is the spec. The
pre-build v1.0 is archived at `docs/PRODUCT_MASTER_v1.md` and must not be built
from. Phase 2 is the **Validation Engine**.

**Reason:**
- Two files named PRODUCT_MASTER.md were in circulation with different roadmaps:
  v1.0 has Phase 3 = "KiCad Workflow Layer" (freerouting, Gerber, DFM, fab APIs,
  industrial all bundled) and Pro at $29; the repo copy has Phase 3 =
  "Industrial Layer" with Gerber/DFM/fab moved to Phase 4, and Pro at $49.
- The repo copy is the later revision and both changes look deliberate. Moving
  the industrial vertical earlier and the manufacturing workflow later matches
  the argument in MENTAL_MODEL.md §9 that industrial rule libraries are the one
  area no competitor occupies. Reverting to v1.0 would have undone that silently.

**The fork that was not a fork.** An earlier draft of ROADMAP.md claimed
master_plan.md and PCB_STRATEGY.md described competing Phase 2s. They do not.
PCB_STRATEGY's routing thesis — "the router is a commodity you should consume,
not a product you should build" — is what PRODUCT_MASTER Phase 3 already said:
"PCB auto-layout via KiCad freerouting integration." The custom A* engine in
backend/pcb_engine/ was a deviation from BOTH documents, not a choice between
them. ROADMAP.md §5 is corrected.

**Consequence for Phase 3:** integrate freerouting rather than extending the A*
engine, and treat the constraint layer — net classes, differential pairs and
keepouts derived from SignalType and ApplicationClass, each carrying a
plain-English reason — as the differentiating deliverable of that phase. It is
the piece no competitor can build, because nobody else has intent → IR →
simulation in one system.

**Risks recorded against Phase 2 rather than discovered later:**
- Analog (op-amps, buck/boost, LDO) is a different validation problem, not an
  increment. Sequence it last.
- Free-form generation needs a low-confidence signal or it trades the
  reliability story for breadth.
- The "BOM within 5% of a manual engineer" KPI needs a manual engineer — the
  same dependency that kept criterion 12 open for twelve weeks.

---

## [2026-08-22] PCB engine is in scope, experimental, and labelled — option (b)

**Decision:** `backend/pcb_engine/` stays in the product, excluded from the
v0.1.0 gate, labelled experimental in the UI, and gated by a config flag.
Alternatives rejected: (a) in scope and tested, (c) out of scope for now.

Belatedly recorded here on 2026-08-24. The decision was taken on 2026-08-22 and
`plan/current_phase.md` Task 4 claimed it was "recorded in `brain/decisions.md`"
— it was not. Two files pointed at an entry that did not exist, which is the
same stale-copy failure the ownership table exists to prevent, in the one file
that owns the fact.

**Reason:**
- Gating v0.1.0 on ~2,400 untested lines of geometry code stalls Phase 1
  indefinitely. Deleting work that demos well is its own waste.
- An unlabelled experimental router inside a product whose whole pitch is
  "physics-validated" is a credibility risk. The label is the load-bearing part
  of (b) — without it, (b) is just (a) with the testing skipped.
- What made this concrete rather than theoretical is recorded in
  [2026-08-22] Phase gating targets visibility, not timing: the first
  measurement of the placement pipeline found `footprints.py` had no SMD
  packages at all.

**Consequence:** shipped 2026-08-24 in PR #1 (`2bd73c8`). `PCB_ENGINE_ENABLED`
resolves from `environment` — on in development, off in production, explicit
value overriding either way. Disabled, `POST /pcb/compile` returns 501 and
`/health` reports the flag so the frontend drops the tab instead of rendering
one that errors on every click.

The more consequential half of that PR was not the flag. An empty board rendered
as a clean rectangle and read as a successful compile, which is *why* the
dropped components went unnoticed for two months — the warnings existed and were
collapsed. A flag hides a feature; it does not make a silent failure audible.
`PCBViewer` now opens its warnings by default and says so explicitly when zero
components were placed.

**Not settled by this:** routing quality. `board_ir`, `kernel`, `router` and
`render_pretty` have no tests, and per `.claude/CLAUDE.md` the answer is
integrating freerouting in Phase 3 rather than testing lines slated for
replacement. Carried as a blocker in `plan/current_phase.md`.

---

## [2026-08-25] Criterion 12 deferred with a trigger; Phase 2 begins

**Decision:** Phase 1 closes at 11 of 12. Criterion 12 — an external engineer
reading an explanation cold — is **deferred, not dropped**, and reopens on a
named trigger: **before the first external user is shown a generated
explanation**, whichever comes first between a public launch, a demo to a
prospect, or onboarding anyone outside this repo.

It renders as `⏭` in `state.json` and does **not** count toward done.
`DEFERRED_CRITERIA` in `regen_state.py` is deliberately a separate set from
`SUBSTITUTE_CRITERIA`: a substitute criterion was met by a different gate, a
deferred one was not met at all, and collapsing the two would produce exactly
the quiet devaluation that [2026-08-22] Criterion 12 moved off the v0.1.0 gate
spends a page refusing.

**Reason:**
- The 2026-08-22 entry made it a Phase 2 *entry* condition. Holding Phase 2's
  start against a third party's calendar reproduces the original problem one
  phase later — it was open twelve weeks and no person had been identified.
- The trigger binds it to the event that actually makes it matter. The risk was
  never "we did not do a review"; it was "an outsider reads an explanation and
  it does not land." That risk arrives with the first outsider, not with the
  start of Phase 2.
- A deferral without a trigger is a deletion with better manners.

**What this does NOT change:** the risk allocation stays odd and stays stated.
The explanation layer is the product per `PRODUCT_MASTER.md` Part 12, and it
remains the only part with no verification from outside this repo while the
non-differentiating parts carry 400+ tests. `PHASE1_COMPLETE.md` says so on its
first page and is not being edited to soften it.

**Also settled here — Phase 2 is the Validation Engine.** `regen_state.py`
hardcoded the phase name as "Physical + External Validation", contradicting
[2026-08-22] PRODUCT_MASTER.md is canonical. That name described the leftover
Phase 1 gates rather than a phase, and with criterion 11 met by substitute and
criterion 12 deferred it now has no content at all. Renamed to match the
canonical roadmap.

---

## [2026-09-20] `predict()` is the per-request truth; ngspice becomes the regression check

**Decision:** Amends `PRODUCT_MASTER.md` Part 10, *"Why simulation must be the
truth, not the LLM's opinion."* A generator's `predict()` — closed-form physics —
answers any numerical claim about a design at request time. ngspice moves to CI,
where it runs the generator's full declared envelope grid and `predict()` must
agree with it to within 2%.

Recorded as amendment **X1** in `PHASE_2_PLAN_v2.md` §2, which is the owner of
the Phase 2 plan. This entry is the owner of *why*.

**Reason:**

- Part 10's sentence carries two readings that were identical in Phase 1 and come
  apart in Phase 2: *the numbers must not come from the LLM*, and *the numbers
  must come specifically from ngspice*. The first is the principle. Closed-form
  arithmetic is not the LLM either, so the principle survives intact.
- One nominal ngspice run is a statement about one point in parameter space. The
  same physics evaluated across a tolerance box — monotone corners, or z3 over
  component ranges — is a statement about every point in it. That is a stronger
  claim, not a weaker one, and it is the whole reason for the amendment.
- **Simulation is not removed, and it runs more than it does today.** One nominal
  run per design becomes an entire envelope grid per generator on every CI build,
  where a disagreement blocks a merge instead of producing a number that nothing
  was diffing against.

**Alternatives rejected:**

- *Keep ngspice as the per-request truth and add `predict()` beside it.* Two
  sources of numerical truth on the same design is the condition this project
  spent 2026-08 removing from its documentation, one layer down. When they
  disagree there is no rule for which wins.
- *Drop ngspice once `predict()` exists.* `predict()` is code written here, which
  makes it exactly the class of thing criterion 11 was written to guard. An
  independent implementation that disagrees is the only cheap defence, and
  ngspice is that implementation.

**Carried forward — the defeater fans out.** `predict()` validated against
mathematics rather than hardware is the same limitation criterion 11 carries as
`met_by_substitute`, now sitting under every user-facing number instead of one
test file. It is D1 in `PHASE_2_PLAN_v2.md` §7. Do not let it go quiet: the
bench measurement is still owed, and it is owed more broadly after this decision
than before it.

**Not settled by this:**

- *Whether per-request ngspice survives as an on-demand facility.* X1 says
  `predict()` is the truth and SPICE's role moves to CI; it does not say to
  delete `POST /design/{id}/simulation/{job_id}`, and X3 implies runtime ngspice
  still exists. The machinery is built and tested, so keeping it as optional
  corroboration costs nothing. Decide explicitly before Stage 0 closes.
- *The public claim.* "Simulates before it ships" becomes true of the
  **generator** — validated against ngspice across its declared envelope — rather
  than of the **instance** a user just generated. That is still a strong claim
  and arguably a better one, but it is a different sentence. Nothing is
  inaccurate today, because `predict()` does not exist yet; the restatement is
  owed at the moment the first generator ships with `predict()` answering, and
  `MENTAL_MODEL.md` §9 is where it lands.

---

## [2026-09-20] Explanation derivability: yes for the baseline, no for the domain layer

**The question** (`PHASE_2_PLAN_v2.md` §4.4, Task 0.5): given `predict()` output
and the requirements, is the explanation a template fill, or does it need a
model call? §4.4 calls this "the single highest-leverage experiment in Phase 2"
because a yes removes the dominant per-design cost and makes the product work
offline.

**Answer: a qualified yes, and the qualification is the useful part.**

Evidence: `scripts/explanation_derivability.py`, run 2026-09-20 over six
designs — one produced by the `rc_lowpass` generator, plus the five Phase 1
example IRs — scored on the consequential-language markers
`tests/test_explainer.py` already enforces, against live
`ExplanationEngine` output from the configured model.

```
  case                          derived (0 calls)        live model (6 calls)
  *rc_lowpass (generated)  4 mk / 2/2 cmp /  2562c PASS  6 mk / 2/2 cmp /  9045c PASS
   IR_001 dht22            5 mk / 4/4 cmp /  1472c PASS  6 mk / 4/4 cmp / 13739c PASS
   IR_002 led              6 mk / 4/4 cmp /  1657c PASS  8 mk / 4/4 cmp / 10453c PASS
   IR_003 rc_filter        4 mk / 2/2 cmp /   988c PASS  7 mk / 2/2 cmp / 12232c PASS
   IR_004 divider          4 mk / 2/2 cmp /  1018c PASS  6 mk / 2/2 cmp / 10168c PASS
   IR_005 modbus           5 mk / 6/6 cmp /  2118c PASS  8 mk / 6/6 cmp / 15717c PASS
```

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

**What is not derivable.** Reading the two side by side for the RC case, the
model supplies a layer of domain knowledge that is nowhere in the IR or the
prediction: that the output impedance should stay inside an ATmega-class ADC's
10 kΩ source-impedance limit, that a sample-and-hold will not charge within the
conversion window if it does not, why X7R rather than an electrolytic, that the
fix for a tighter corner is a ±2% C0G capacitor and not a tighter resistor, and
that a single-connection IN node means this is a filter fragment rather than a
finished netlist. Counterfactuals at specific alternative values — "34 kΩ drops
the cutoff 10× to ~100 Hz" — are also outside what `predict()` alone supports.

**Consequence for the cost model.** §4.4's per-design table can be satisfied:
the explanation becomes **0 calls** rather than "0 or 1", the product works
offline, and the model call becomes an optional enrichment on top of a
genuinely useful baseline rather than a requirement for having any explanation
at all. Whether to keep that enrichment, and on which tier, is a product
decision this entry does not make.

**Two caveats that must survive into any summary.**

1. **Only the `rc_lowpass` row is a real test.** The five example IRs carry
   justifications written by the LLM back in Phase 1, so a derived explanation
   over them is assembling model output, not deriving from requirements. They
   show what is recoverable from an IR alone, which is a weaker and different
   claim. The result generalises to a new generator only insofar as its author
   writes real justifications — which is now a standard to hold generators to,
   not an accident.
2. **Marker counting measures form, not quality.** `tests/test_explainer.py`
   says as much about itself. This experiment can say "clears the bar the test
   suite enforces"; it cannot say "as good as the model", and the side-by-side
   above shows it is not. **Criterion 12 — a human reading one cold — remains
   the only test of whether either version lands, and it is still open.**

**Alternatives rejected:** scoring by length (the model wins on length and that
proves nothing), and LLM-as-judge (an LLM reading LLM output answers from its
own training whether or not the text said anything — the same argument that
kept `scripts/review_panel.py` from being allowed to close criterion 12).

---

## [2026-09-21] Three defects in the X5 implementation, found by review and closed

**Decision:** the X5 guard is extended to cover `requirements.function`, the
truncation guard lost in the rewrite is restored, and the raw tool input is
persisted to `request_log.error`. Surfaced by a five-advisor review of the
[2026-09-21] X5 entry below; all three were verified against the code before
being treated as real, and two were reproduced against the pre-fix behaviour.

**1. The guard did not cover `function`, so it could be walked around.**
`_requested_values` flattened `targets`/`constraints`/`preferences` only.
`function` is the one *required* field and the only one outside a section.
Reproduced on the pre-fix code: a request for `band_pass_filter` at 1 kHz is
refused, the retry returns `low_pass_filter` at 1 kHz — **every target
byte-identical** — the add-only check sees no change, and the producer returns
a low-pass to someone who asked for a band-pass.
`test_retry_that_rewrites_the_request_is_refused` passed throughout. This is
the same failure shape as the Task 1.5 AST scanner that passed while the
violating module was still in the tree: a check with a hole is worth less than
no check, because it is believed.

**2. The truncation guard was lost in the rewrite.** `circuit_reasoner.py`
explicitly fast-failed on `stop_reason == "max_tokens"`, reasoning that
retrying a truncation makes it strictly worse. `intent_producer.py` did not
carry it over. Reproduced: a tool call cut off at the ceiling yields a partial
dict, fails `Requirements` for missing fields, and was filed as
`kind='schema'` — so a budget problem was recorded as evidence that "schema
failure is structurally impossible" had broken. Departure 1 exists to *measure*
that assumption; an instrument that reports the wrong cause is worse than none.
`Failure` now names each cause so the evidence is countable by kind.

**3. The evidence never reached storage.** Departure 1 attaches the raw tool
input to `IntentProductionError`; the route put `str(exc)` in a 422 and dropped
`exc.raw`. Verified: the log row had `error=None`. An exception announces a
broken assumption only to whoever is holding it.

**Why `request_log.error` rather than a new column.** `request_log` has no
JSONB slot for this and the repo has no migration tool — `schema.sql` runs only
on an empty data directory. Adding a column would make every INSERT fail on any
existing volume and silently push *all* logging to the JSONL sidecar until
someone applied the DDL by hand. `error` is TEXT, exists everywhere today, and
`as_log_entry()` writes a greppable `intent_production_failed[kind]: msg |
raw={...}` with the raw capped at 4000 chars so one runaway input cannot bloat
the table.

**What was NOT changed, though the review argued for it.** Four of five
advisors said the semantic retry should be **0**, not 1: with one generator the
guard leaves only the add-a-missing-field escape hatch, at 2 API calls per
refusal against a §4.4 table that budgets 1. That is a design change to X5, not
a defect in it, and the live case is real — the model omits a field *and* fails
to declare it `underdetermined`, which the retry does fix. The better answer is
probably a structured refusal kind on `EnvelopeDecision` (`missing_field` vs
`out_of_range`) so the retry fires only where it can help; `reason` is free text
today. Left for the user to decide, with Stage 3 the natural point.

Also left open, and the sharpest thing the review found: **nothing compares
attempt 1 against the user's prompt.** Every guard here preserves fidelity to
attempt 1, not to the request. A first-call mistranscription of 2 MHz as 1 kHz
passes every check, dispatches cleanly and ships. The 0/200 abstention figure
measured envelope matching, not transcription fidelity. That is A1's real
exposure and no local fix closes it.

---

## [2026-09-21] X5 accepted — schema retries retire, semantic retries survive with a guard

**Decision:** Amendment X5 of `PHASE_2_PLAN_v2.md` §2 is accepted. The retry
loop retires for **schema** failures and is retained for **semantic**
rejections. Implemented in `backend/ai/intent_producer.py`, not by editing the
old loop — Task 1.5 removed the module that held it.

Taken by the agent rather than the user, because the instruction was "do
complete stage 1" and X5 gates Task 1.4. The recommendation had been on record
in `plan/current_phase.md` since 2026-09-21 and is what was implemented. It is
recorded here rather than assumed so it can be reversed by reading one entry.

**Reason:**
- Forced `tool_choice` returns a parsed dict conforming to the tool schema, so
  the two schema branches of the old loop re-prompted for a failure that
  should not occur. Re-prompting for it hides how often it does.
- A refusal from `envelope()` is different in kind: it is a reason the producer
  can act on, and the request may simply have been mis-transcribed.

**Two departures from the plan as written, both deliberate.**

*A schema failure raises loudly and carries the evidence.* v2 §4.3 concedes
that "schema failure is structurally impossible" is only structural under
constrained decoding, which is unbuilt — today it is an empirical claim about
frontier models. So `IntentProductionError` carries the raw tool input. If the
assumption ever breaks, it announces itself rather than becoming a silent
one-shot failure. Same reasoning as the `regen_state.py` abort guard.

*A semantic retry may add, never rewrite.* This guard is not in the plan and
the implementation is unsafe without it. Told "no generator accepted this",
the fix most available to a model is to **alter the requirement until it
fits** — quietly turning "I need 2 MHz" into "1 kHz" and returning a design
the user never asked for. That would defeat A1, the single analytic claim the
architecture rests on. So a retry may supply a value it failed to record the
first time, which is the correction the retry exists for, but may not change
or drop one it already recorded. `test_retry_that_rewrites_the_request_is_refused`
pins it.

The consequence is intended: a request genuinely outside the catalogue is
**refused, not negotiated**. §4.2 wants users self-selecting against a visible
catalogue, and §4.6 defers the labelled ring precisely so uncovered requests
are refused rather than guessed at.

**Alternatives rejected:**
- *Retry on envelope refusal with no guard*, as a literal reading of X5
  suggests. Unsafe for the reason above.
- *No semantic retry at all.* Safe, and it discards the one case a re-prompt
  genuinely fixes: a mis-transcription the model can correct from the reason.

---

## [2026-09-21] The LLM → CircuitIR path is removed, and coverage narrows to the catalogue

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

**The consequence, stated plainly because it is a product regression.**
Generation is now bounded by the generator library, and the library has one
member. Requests for the DHT22, LED, Modbus and divider templates — four of the
five Phase 1 templates — are now **refused with a named reason** instead of
being generated by the model. They return to coverage in Stage 3, which
authors the remaining four generators.

This is the plan working as designed rather than an accident of sequencing:
§4.5 makes the refusal log the generator backlog ranked by frequency, and
§4.2 has users self-select against a visible catalogue. But it is a real loss
of function between Stage 1 and Stage 3 and should not be discovered later.

**What made the gate honest.** The first version of the AST scanner looked
only for `CircuitIR(...)` and **passed while the violating module was still in
the tree**, because the module used `CircuitIR.model_validate(last_raw)`. The
scanner now covers every Pydantic construction form and has a parametrised
negative control for each. A G1 claim resting on a check with a hole in it is
worth less than no claim at all.

---

## [2026-09-21] X2 + X4 accepted — patches apply to IntentIR; the CircuitIR patcher is removed

**Decision:** amendments X2 and X4 of `PHASE_2_PLAN_v2.md` §2 are accepted.
A patch is an RFC 6902 operation list over `IntentIR.requirements`; the design
is re-derived by the same `envelope() → generate() → predict()` gate a fresh
request goes through. `ai/patcher.py`, which let a model edit CircuitIR
component fields, is deleted. Stage 2.

Taken by the agent on the instruction "do stage 2". The five-advisor council
review of X2/X4 and two TypeSafe (Jev) passes found the direction right and
the amendments under-specified; every point below closes one of those gaps. It
is recorded here so it can be reversed by reading one entry.

**Found while reading, before writing anything: the Task 1.5 invariant had a
hole.** `ai/patcher.py` called a model and then wrote the model's output into a
CircuitIR through `ir.model_copy(update=...)`. That is exactly the path the One
Rule forbids, and `test_llm_cannot_write_circuit_ir.py` passed throughout
because it recognises constructors (`CircuitIR(...)`, `model_validate`, …) and
not `model_copy`. Same failure shape as the first version of that scanner: a
G1 claim resting on a check with a hole. The module is removed and the scanner
now treats `model_copy(update=...)` in a model-calling module that references
`CircuitIR` as a violation, with a negative control.

**The resolutions, one per gap the reviews found:**

1. **IntentIR lives on the design record.** `circuit_designs` gains
   `intent_ir JSONB` and `annotations JSONB`. Without it there is nothing to
   patch — until now the IntentIR existed only in `request_log`. A NULL
   `intent_ir` marks a design built before Stage 2; it cannot be patched and
   the route says so with a 409 rather than guessing a requirement back out of
   a circuit.

2. **The repo gets an idempotent startup migration.** The [2026-09-21] X5
   defects entry avoided a new column because `schema.sql` runs only on an
   empty data directory, so any DDL change breaks every existing volume. That
   constraint was going to recur at every stage. `db/migrations.py` holds
   `ADD COLUMN IF NOT EXISTS` statements run at startup, and `schema.sql`
   carries the same columns for fresh volumes. A migration that fails is
   logged and does not stop the app, matching today's behaviour when Postgres
   is down.

3. **`circuit_id` is derived, not random: `uuid5(namespace, intent_id)`.**
   The Stage 2 determinism gate cannot pass while `CircuitIR.circuit_id` is a
   fresh `uuid4`. Derived from `intent_id` and **not** from the generator
   version, departing from the protocol docstring's wording: `circuit_id` is
   the design record's key and survives patches, and folding the generator
   version in would change a design's identity every time its generator is
   upgraded. The version is recorded instead in a new `CircuitIR.generator`
   field (`name@version`, v2 §6). Stamping happens in one place,
   `generators/realize.py`, so no generator works around it locally.

4. **`IntentIR.revision`.** Each accepted patch is revision n+1, and
   `CircuitIR.version` equals it. `with_requirements()` increments it.
   `SCHEMA_VERSION` 2.0.0 → 2.1.0; old dumps without the field still load.

5. **A patch that changes nothing is not a version.** Idempotence gate: an
   empty patch, or one whose operations leave the requirements equal, returns
   the same IntentIR and a byte-identical CircuitIR. Phase 1 recorded an empty
   patch as a new version; that was a property of patching an output, not a
   virtue.

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

8. **Patching is LLM-optional.** The route takes either `command` (one model
   call) or `ops` (zero), the patch-side counterpart of the form producer.

9. **A refused patch keeps v(n).** Nothing is written until the new revision
   has passed `envelope()` and been realised. The user never loses a working
   design in exchange for a refusal.

10. **Annotations are a closed list:** `net_name`, `test_point`,
    `placement_hint`, `comment`, each anchored to a component, a node or the
    design. Merged after generation, never an input — asserted by a test that
    generation is byte-identical with and without them. An annotation whose
    anchor disappears is **orphaned and reported**, and kept, so it re-attaches
    if the anchor returns. Rendering them into KiCad output is not Stage 2.

11. **Locality is checked, and its grade is projected until Stage 3.** A
    CircuitIR component diff outside the declared `dependency_closure` of the
    changed requirement paths is a violation, reported with every patch and
    swept in CI. With one two-component generator a closure is close to the
    whole circuit, so passing proves little. It becomes evidence when a
    generator with more than two parts exists.

12. **Criterion 7 is re-earned at the IntentIR layer.** Its automation was
    `tests/test_patcher.py::test_five_sequential_patches_keep_ir_valid`, which
    patched CircuitIR directly and goes with the module. The replacement runs
    five sequential requirement patches, each re-derived, and asserts the same
    things: schema-valid, no dangling references, earlier edits survive, and
    history that reads as requirements. `CRITERIA_TEST_MAP` points at it.

13. **Old `patch_history` rows are frozen, not migrated.** They record
    CircuitIR component edits on designs that have no IntentIR, so there is
    nothing faithful to convert them into. New rows carry
    `schema: "intent_patch/1"` so a reader can tell the two apart.

14. **A stored design is never silently re-derived.** Its CircuitIR is the
    record. A patch regenerates with the installed generator, and if that
    differs from the one that built v(n), the response says so
    (`generator_changed`) alongside the `predict()` delta. The simulation job
    for each revision is stored with that revision's patch row, so results for
    v(n) cannot be read as results for v(n+1).

15. **The DS18B20 acceptance gate is deferred with a trigger.** *"Use a
    DS18B20 instead"* cannot pass anywhere in Phase 2: no stage builds a
    DS18B20 generator. Trigger: a temperature-sensor generator that offers it.
    The acceptance test that can pass today replaces it — *"make the cutoff
    2 kHz"* end to end, justified by the `predict()` delta rather than prose.

**Alternatives rejected:**
- *Keep the CircuitIR patcher as a tested legacy path.* It is an LLM → CircuitIR
  path, which Stage 1 exists to remove; keeping it tested would keep it working.
- *Store the IntentIR chain only in `patch_history`.* Uses an existing table and
  needs no DDL, but it makes the current requirement a query over a log.
- *`circuit_id` from a hash of the requirements.* Two users asking for the same
  filter would collide on a unique key.

**Found while building, both closed in the same change:**

- **`rc_lowpass.dependency_closure("constraints.supply_v")` was too narrow.**
  Stage 0 declared `{C1}` because only the capacitor carries a voltage rating.
  The locality sweep's first run showed a 20 V supply changing R1 too: the
  100 nF part is rated 16 V, so it drops out, another capacitor is chosen, and
  R1 is re-snapped around it. Fixed to `{R1, C1}`; a negative control
  reinstates the Stage 0 closure and must fail. A closure that is too narrow is
  worse than a conservative one, because the locality claim built on it is
  believed. This is the first evidence the locality gate is worth having, even
  graded projected.
- **The `model_copy` rule in the scanner needed imports counted as references.**
  Its first version looked for the name `CircuitIR` among `ast.Name` and
  `ast.Attribute` nodes; a module that only imports the type (`ast.alias`) was
  invisible to it. The new negative control caught that before anything
  shipped on it.

## [2026-09-21] Stage 2 verification — three defects closed, and the citation guard tightened

**Decision:** three defects found by an independent verification of Stage 2
are fixed, and item 7 of the X2 + X4 entry (the citation guard) is tightened.
Items 1–15 otherwise stand. Taken by the agent on the instruction "do 1–3"
after the verification report.

**1. Two patches in flight lost one of them.** The route read v(n), computed
v(n+1) and wrote it with `UPDATE … WHERE circuit_id = ?`. Two patches computed
from the same v(n) both returned 200 as "v2", history got two 1 → 2 rows, and
the second silently discarded the first while its user was told it had landed.
`crud.update_design_revision` now takes `expected_version` and adds
`AND version = ?`; under READ COMMITTED the second UPDATE waits on the first's
row lock, re-checks the predicate against the committed row, and matches
nothing. The route answers **409 `version_conflict`** and writes nothing else.
Verified against Postgres (a stale write returns False and changes nothing) and
by a route test that runs two patches concurrently.
The revision write **no longer rewrites annotations.** A patch never changes
the annotation set — orphans are kept, not dropped — so rewriting it could only
clobber a concurrent `PUT …/annotations`, and it reordered them besides.
*Rejected:* `SELECT … FOR UPDATE` on the read. It serialises correctly, but it
holds a row lock across the model call on the command path, and a conflict is
rare enough that failing fast with a reason is the better trade.

**2. The documented pin flow failed on every first pin.** The patcher is told
to emit `add /constraints/pinned/R1`; RFC 6902 §4.1 requires the parent to
exist, and a design never pinned has no `pinned` map, so the operation failed
with "/constraints/pinned does not exist". Each half was tested; the two were
never composed. `core/intent_patch.py` now declares `CONTAINERS` — the three
sections and `constraints.pinned` — whose absence means empty: an `add` into
one creates it, and emptying one removes it, so "no pins" has one spelling and
adding an empty pin set is not a version. Every other missing parent is still
refused. This extends the departure the module already made for sections; it
does not create a general "create intermediate objects" rule.

**3. The citation guard did not stop the case it was written for.** Item 7
said a model that also changes `supply_v` when the user mentioned only the
cutoff "is refused". It was refused only when the model quoted words absent
from the command: quoting the whole command, or `"e"`, put `supply_v: 5 → 12`
through. A substring check proves the quote exists, not that it asked for the
operation. The guard is now three mechanical rules:
- **whole words** — a citation starts and ends on word boundaries;
- **one span, one operation** — citations are assigned non-overlapping spans,
  so the words that justified one change cannot justify a second;
- **the value is in the span** — an operation that writes a value must cite
  words containing it, numbers compared as quantities under SI prefixes
  ("2 kHz" grounds 2000, not 20000; case decides milli versus mega).

The third rule also closes most of what item 7 listed as uncaught — a value
mis-transcribed from words that were cited.
**Cost, accepted:** a relative request ("double the cutoff") grounds no value
and is refused; the prompt now tells the model to ask for the value instead.
This matches "refused, not negotiated".
**Still not caught, pinned by tests so nobody reads the guard as covering it:**
values swapped between two operations whose spans each contain the other's
number, and a removal citing an unrelated whole word (a removal writes no value
to ground). The requirement diff returned with every patch remains the
mitigation. *Rejected again:* binding a span to a path by name — the lexical
heuristic item 7 already rejected.

**Not addressed here, from the same verification:** the Task 1.5 scanner is
per-module and misses model output reached through a wrapper or written by
in-place mutation (no such path exists today); `rc_lowpass` invents a part
number for an off-series pinned resistor and reads `"4.7K5"` as 5.2 kΩ; the
Stage 0 requirement readers accept `true` as a number; patch refusals are
logged without the requested IntentIR; a failed startup migration is silent;
and `brain/architecture.md` still describes the deleted `ai/patcher.py`.

## [2026-09-21] The Task 1.5 scanner becomes transitive; rc_lowpass reads its inputs strictly (0.2.1)

**Decision:** two of the open findings from the Stage 2 verification are
closed. Taken by the agent on the instruction "do 4 and 6".

**The "no code path lets the LLM write CircuitIR" scanner, third version.**
The G1 claim rested on a per-module check that recognised a model only by the
client factory's name. The verification wrote three modules it passed: one
reaching a model through `IntentPatcher`, one through
`ExplanationEngine().client`, and one mutating a design it was given
(`ir.components[0].value = raw`). None existed in the tree; the claim was
still stronger than the check, for the third time in the same shape.
`tests/test_llm_cannot_write_circuit_ir.py` now:
- computes **model-facing names to a fixed point across the repository** —
  a top-level function, class or module-level name that references the client
  factory, a `.messages.create(...)` call, or another model-facing name — with
  imports (including relative ones) resolved to the defining module, so two
  unrelated functions called `main` cannot contaminate each other;
- treats as a write, in any module that references a model-facing name:
  construction under any alias, `model_copy(update=...)` whatever the
  receiver, assignment / augmented assignment / deletion through a design field
  name, mutating calls on one, `setattr`, `object.__setattr__`, `__dict__`;
- takes exceptions only from `_REVIEWED`, keyed by file and exact source text,
  each with a reason; a stale entry fails the suite. Three entries today: the
  patch route rebuilding the stored record from Postgres, and two
  `ctx.generator = …` request-log writes that share a field name with
  CircuitIR.

Mutation-checked: without the fixed point the wrapper controls fail; without
write detection the mutation controls fail. **Still outside it**, and said so
in the file: a model reached only through a parameter whose class is never
named (unless it calls `.messages.create`), names built at runtime, and model
output that passes through storage before another process builds a design.
*Rejected:* intraprocedural taint tracking from model calls to design writes.
More precise, but unsound across calls in the same way and far more code to
trust; the conservative closure plus a reviewed allowlist fails loud instead.

**rc_lowpass 0.2.0 → 0.2.1: a written value is honoured or refused, never
replaced.** The Stage 0 readers returned the default for anything that was not
an int or float and accepted `True` as 1. Worse than first reported:
`supply_v: "12"` built a **5 V** design, `tolerance_pct: "1"` loosened to 5%,
and `tolerance_pct: NaN` accepted **every** design, since every comparison
with NaN is false. One reader, `_read_number`, now applies to all four inputs:
absent or null takes the default; present must be a real, finite number —
not a bool, not a string — and in range (cutoff, tolerance and supply above
zero; source impedance zero or more), else `envelope()` refuses naming the
path and value. Every intent 0.2.0 accepted with well-formed values yields the
same design; the version moves because the refused set changed, and a refusal
log has to be able to say which behaviour refused. Tests now read the version
from the module instead of spelling it.

---

## [2026-09-21] X6 + X8 accepted, the defeater register is renumbered, and Stage 3 is scoped

**Decision:** amendments X6 and X8 of `PHASE_2_PLAN_v2.md` §2 are accepted, the
defeater IDs are made unique, and the Stage 3 build is fixed as below. Taken by
the agent on the instruction "move to stage 3", after the council verdict on
X6/X8 and the TypeSafe pass that flagged X8 as due earlier than Stage 3. Written
before any Stage 3 code, per v2 §2.

**Found while reading, before deciding:**

- **X8's silent pass is wider than the council described.** The council's
  concern was that `HardwareRuleEngine.run()` skips rules a design does not
  list. Worse: four of the ten `ValidationRule` values have **no
  implementation anywhere** — `current_limits_ok`, `pullup_on_open_drain`,
  `power_supply_adequate`, `operating_temp_range`. `IR_001` lists two of them
  and `IR_002` lists one, and all three "pass" by never being run. A listed
  rule that nobody checks reads as a checked rule.
- **The LED template's simulation never lit the LED.** `IR_002`'s GPIO node has
  no source, so ngspice ties it down through 1 GΩ and the LED carries ~0 mA;
  and the netlist's single diode model (`Is=1e-9 n=1.8`) gives ~0.8 V forward
  drop, not the 2.0 V the design's justification reasons from. The Phase 1
  simulation of that template could not have confirmed its own claim.

### X6 — the MCU model becomes a declared scope

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

### X8 — validation rules become graded claims

Accepted with the council's conditions:
- **"Not assessed" is the catalogue minus what was actually checked** — every
  `ValidationRule` value, minus the rules that ran *and have an
  implementation*. Computing it from "the rules that ran" would let a design
  that checks less look better verified.
- **Grades follow from method, never typed per claim.** One table maps a
  method to a grade — `exact_graph_check` and `monotone_corners` → G1,
  `ngspice_nominal` → G5, `sampled` → G6, `asserted` → G7 — and each rule and
  each prediction declares its method. A rule reading a datasheet-derived table
  (`pwm_pin_valid`'s pin list, `voltage_ratings_ok`'s ratings) carries D7.
- **The four unimplemented rules are not implemented here.** They are shown as
  *not assessed* rows, which is the honest state. Where a generator's own
  claims cover the physics (the LED generator's GPIO-current claim covers what
  `current_limits_ok` was named for), the claim carries it and the rule row
  still says not assessed.
- **Rule IDs are kept**, so existing tests and stored designs still read.

### The X6 × X8 interaction

The council warned that an open D2 on every MCU design would flatten
`grade_floor`. It does not, under the weakest-link rule as EVIDENCE_CLASSES
§3.2 states it: a model assumption is a **defeater**, not a lower grade — "a G1
proof over an unvalidated model is G1 carrying a model defeater". So
`grade_floor` reports the worst *grade*, `open_defeaters` reports D2 separately,
and the two are never fused (§5). A claim with an open defeater has verdict
**holds, defeasible**, never plain "holds".

### The defeater register — one namespace

v2 §7 owns IDs D1–D7. Two other documents reused the namespace:
- EVIDENCE_CLASSES Table C's **D4** ("π is irrational; the z3 encoding must
  bracket it") becomes **D8**. Its status is *not yet applicable*: no claim is
  proved by z3 until Stage 4, which is where it gets eliminated.
- ARCHITECTURE_ASSURANCE_CASE's **D-G** ("a generator bug makes `predict()`
  confidently wrong, and nothing catches it") is imported as **D9**. v2 carried
  the harness that refutes it without registering the doubt. It is *eliminated
  per generator* by passing the M1 mutation matrix; a generator that has not
  passed it carries D9 open.

The register lives in code (`validation/defeaters.py`) so claims can cite IDs
and `regen_state.py` can count open defeaters and fan-out; v2 §7 is the prose
view of it.

### Stage 3 build decisions

1. **Four generators, one per Phase 1 template:** `voltage_divider`,
   `led_indicator`, `dht22_node`, `rs485_node`. Each on the Stage 0 contract,
   each with the pin/strict-input discipline `rc_lowpass` 0.2.1 set.
2. **What each predicts, and what ngspice checks.** The grid gate compares
   quantities a DC or AC run can measure; anything else is a closed-form claim
   with no simulation cross-check, and its row says so.
   - divider: `vout_v` (monotone corners), output impedance, bleed current,
     resistor dissipation.
   - LED: `led_current_ma` from the Shockley diode and a Thevenin GPIO pin,
     solved by bisection on a monotone scalar equation (exact to the float), so
     corners still bound it; GPIO current against the 20 mA recommended / 40 mA
     absolute limit.
   - DHT22: the pull-up's sink current with the line held low, idle data-line
     level, and rail current (under `mcu_as_100R` — D2).
   - RS-485: idle differential bus voltage `v_ab` against the ±200 mV receiver
     threshold (the fail-safe bias calculation), total bus load against the
     54 Ω the standard specifies a driver into.
3. **The netlist learns two models, both opt-in and backward compatible.**
   `spice.py` models (a) a node driven by an MCU *output* connection that
   carries a `voltage_nominal` as the pin's Thevenin source (`V_PIN_` + `R_PIN_`,
   `R_out` from the component table), and (b) an LED whose part number is in
   the component table with a diode model fitted to its datasheet forward
   voltage. A node without `voltage_nominal`, or an LED not in the table, emits
   exactly what it did before. **Correction, found on first run:** `IR_002`'s
   LED *is* the tabulated part, so its netlist changes — the generic
   `DLED (Is=1e-9 n=1.8)`, which drops ~0.8 V, becomes the fitted model, which
   drops 2.0 V at 20 mA. That is the fix the finding above calls for, not a
   regression; the other four example netlists are byte-identical. `predict()`
   and `spice.py` read the same table entry: one owner per fact.
4. **Test benches belong to the grid adapter, not the design.** Where the
   quantity only exists under a stimulus — the DHT22 line held low, the RS-485
   far-end terminator — the CI adapter appends probe elements to the design's
   own netlist, the way a scope probe attaches to a board. The product netlist
   is never altered. Adapters move to `backend/validation/grid_adapters.py` so
   `regen_state.py` and later stages can run the whole library.
5. **The parser reads branch currents** from ngspice's `Source Current` table.
6. **Claims** (`validation/claims.py`): four fields plus a verdict, generated by
   each generator's `claims()` from its prediction and the intent, plus rule
   claims from X8. `realize()` attaches `validation_coverage` to the CircuitIR —
   it is deterministic, so the byte-identity gate now covers the claims too.
   `claims()` is not added to the protocol's required members (every fake
   generator in the tests would break); every *registered* generator is
   required to implement it, by test.
7. **`GridSpec` gains `sections`**, mapping an axis to its requirement section.
   The form producer placed every grid axis in `targets`, which would have put a
   divider's `supply_v` in the wrong section.
8. **`grade_floor`** is derived in `regen_state.py` from each registered
   generator's claims at a canonical point of its grid, and printed at the top
   of the summary with `coverage_le_g2` and the open defeaters beside it.
9. **The waveform viewer** renders AC magnitude, DC node voltages, and
   transient traces from stored simulation data, as inline SVG — no chart
   dependency. The simulation task now stores the points, not only their count.

**Alternatives rejected:**
- *Implement the four missing rules now.* Each needs physics a generator
  already computes; a second, structural implementation would be a second
  source of truth for the same number. Not-assessed rows are honest.
- *Lower a claim's grade for an open model defeater.* Fuses two numbers
  EVIDENCE_CLASSES §5 says never to fuse, and makes every MCU design read G7.
- *Put LED Vf and pin resistance on `Component` as new fields.* Needs every
  downstream compiler touched (code-style.md) for data that belongs in the
  static component table, which already exists for exactly this.
- *Skip the grid gate for DHT22/RS-485 because DC idle states are trivial.*
  The mutation arm would then detect nothing on them — the pull-up is invisible
  at idle. Probes make the quantity that matters observable.

**Found while building Stage 3, all closed in it:**

- **Phase 1's `IR_005` wired the MAX485 to D0/D1** — the hardware UART —
  while `modbus_master.ino.j2` drives it with SoftwareSerial on D10/D11
  ([2026-06-02]). The schematic and the firmware disagreed about which pins
  carry the bus. `rs485_node` wires what the firmware drives, and a test
  checks the two against each other.
- **The RS-485 terminator must be 1206.** A driver can swing the pair to V_CC:
  5 V across 120 Ω is 208 mW, over three times an 0402's 62.5 mW. The Phase 1
  template placed an 0402.
- **Three dependency closures were too narrow, each found by the locality
  sweep on first run:** `led_indicator`'s `gpio_pin` (U1's justification
  names the pin), `rs485_node`'s `supply_v` (R1's justification states its
  dissipation at that supply), on top of `rc_lowpass`'s `supply_v` from
  Stage 2. The sweep is earning its place.
- **The validation report contradicted its own claims table.** With three
  checks not assessed, the old badge still said "✓ All rules passed … No issues
  found" — exactly the silent pass X8 exists to end. It now counts them.
- **The RS-485 M1 margin is thin:** a 5% terminator fault moves idle V_AB by
  2.3%, just over the 2% gate. Pinned by a test, so a model change that pushed
  it under would fail loudly instead of leaving the matrix blind.

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

**Found closing the stage: the tracker went blind again.** `progress_gen.py`
ran the suite under a 180 s timeout, Stage 3 pushed the suite past it, and the
timeout returned an empty result *silently* — every module read "untested",
the script exited 0, and `progress.yaml` reported **0/174 verified**. Fourth
instance of the same root cause (a fixed budget outgrown by the suite, failing
quietly). Now 1200 s, a timeout or an empty scan exits non-zero so
`regen_state.py` prints STALE, and the outer budget sits above the inner one.

---

## [2026-09-23] Stage 4 — the proof compiler: properties proved from the netlist, signed off, frozen

**Decision:** Stage 4 of `PHASE_2_PLAN_v2.md` is built as below. Taken by the
agent on the instruction "do stage 4". Written before any Stage 4 code, per
v2 §2. Dependencies approved by the user: z3-solver 5.1.0.0, sympy 1.14.0 and
mpmath 1.3.0 (1.4.1 was proposed; sympy 1.14 requires mpmath < 1.4).

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

1. **Where the bounds come from.** Each generator declares its properties
   through an optional `properties(intent)` (like `claims()`, not a protocol
   member): the quantity, in netlist terms, and bounds rounded *outward* from
   its predicted band to the three figures its English shows. The property
   proved is exactly the sentence the user reads — never tighter.
2. **Transcendentals are bracketed, then decided exactly.** π, ln 9 and the
   LED's logarithms enter as variables constrained to rational enclosures
   from `mpmath.iv` (outward-rounded interval arithmetic). If the negation is
   UNSAT with the bracket, it is UNSAT for the true value inside it. This is
   how v2 already treats π ("π bracketed", G1), and it eliminates **D8**.
3. **The LED is the one nonlinear element.** A single diode in an otherwise
   linear network: its Thevenin source (V_th, R_th) comes from nodal analysis
   with the diode removed, and because g(I) = I·R_th + n·V_t·ln(1 + I/I_s) is
   strictly increasing, "I ≤ c" holds exactly when g(c) ≥ V_th. The worst I_s
   for each direction is an end of its box — a monotonicity lemma the prover
   checks with z3 rather than assumes. What remains is polynomial in the
   resistances and decided exactly: G1. LED dissipation is proved from the
   proven current bound (P ≤ c²·R1), which is sound but not complete, so it
   stays **G2** and so does the library floor. The divider's dissipation *is*
   decided exactly and rises to G1.
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
6. **Frozen after sign-off; the refine loop cannot touch it.** The prover
   runs a list of strategies — direct decision, then box bisection when z3
   answers *unknown* — and after each one checks the result is for the frozen
   property's hash. A strategy that returns a proof of anything else, a
   weaker bound included, raises `FrozenPropertyViolation`. An edit to the
   requirement already drops the signature (Stage 1), so the only way to
   change a signed property is to ask for something different and sign again.
7. **Every property must be falsifiable by a wrong part.** The mutation test
   scales each toleranced part the property depends on, and each DC source
   in the design, by ×10⁻³, ×0.1, ×½, ×2, ×10 and ×10³ — a wrong neighbour, a
   wrong decade, a wrong multiplier letter — and re-runs the proof on the
   mutated netlist; at least one must be refuted. A property no wrong value
   can break says nothing, and fails the test. This is why rail-budget
   claims are not turned into properties: no single part swap moves a 55 mA
   rail past 500 mA. (Amended while building: ×0.1 … ×10 on parts alone
   cannot break a 62.5 mW rating on a low-current divider; a rail ten times
   too high can.)
8. **Test benches, as in Stage 3.** A property may add bench elements the
   board does not contain — the divider's load, the RS-485 far-end
   terminator, the DHT22's cable capacitance, a probe holding DATA low — with
   their own boxes. They are part of the property and its English.
9. **Performance.** Proofs run inside `realize()` so determinism covers them,
   cached on what a proof reads — the netlist, the parts, how they connect —
   never on the design's identity. Measured: 64 properties across every
   generator's CI grid prove in 4.4 s (15–40 ms each; the RS-485 pair
   ~250–400 ms); importing sympy costs ~1.7 s once per process.
10. **A refutation is certified, never inferred.** An obligation with a
   bracket in it is a relaxation, so a z3 counterexample to it can sit in the
   bracket's slack. Each such obligation carries a *refuter* — the same
   inequality with every bracket collapsed to its adverse end, and I_s taken
   inside its true box — and only a counterexample to that is `refuted`. The
   LED dissipation proof goes through a current bound, so a point where the
   bound fails is not a point where the dissipation does; there, a witness
   check evaluates I²·R > P_max exactly at the failing point and at every
   corner. What neither proves nor certifies is `unknown`, shown G7.
11. **A refuted proof is critical, signed or not.** Sign-off decides whether
   a property is the one the user wants; a certified counterexample to a
   property the system itself derived from `predict()` is a failure either
   way, and a disagreement between `predict()` and the netlist `generate()`
   emitted.
12. **Proofs do not inherit D9.** D9 doubts `predict()`. A proof is checked
   against the netlist `generate()` emitted, with bounds taken from
   `predict()` — so a generator bug that makes the two disagree is exactly
   what refutes it.

**Alternatives rejected:**
- *Prove the generator's `predict()` formula instead of the netlist.* Cheaper,
  and it proves only that predict() agrees with itself.
- *dReal or interval branch-and-bound for the LED.* Sound, but it would make
  every LED claim G2; the monotone reduction keeps the current claims exact.
- *Generate the English with a model.* Then the thing signed would not be
  guaranteed to be the thing proved.

**Found building it:**
- *The netlist writes 47 nF as `4.7000000000000004e-08`.* A tolerance box
  centred on that prints "42.31 nF" in the sentence a person signs. Boxes
  are centred on the part value to 12 significant figures, and the prover
  checks the netlist's own value lies inside the box.
- *Removing the diode to analyse a linear quantity would prove a different
  circuit.* `v()`, `i()`, `power()` on a network with a diode are refused,
  not approximated; the LED is reached only through `diode_current()` and
  `series_power()`.
- *The first cache key included `circuit_id`*, which derives from the
  intent's lineage — every new intent re-proved an identical circuit.
- *Bench elements read twice.* A boxed bench element appeared as a range and
  again as a condition ("every the far-end 120 Ω terminator … with the
  far-end 120 Ω terminator"). It now reads once, as a range with its own
  label and basis.
- *The route briefly wrote a CircuitIR copy in `patch.py`*, a module that
  calls a model; the Task 1.5 scanner caught it. The comparison moved to
  `realize.same_design()`, which writes nothing.
- *A property the prover cannot compile would have failed generation.* It
  is now a visible not-assessed row (G7), and a set containing one cannot be
  signed — the X8 rule: what was not checked is printed.

---

## [2026-09-23] Stage 3 + 4 verification — five defects, closed

**Decision:** On the instruction "test whether all the work done is fine … do a
rigorous check for all of Stage 3 and 4", Stages 3 and 4 were checked against
things that do not share their code, and five defects were fixed. Found and
fixed by the agent; the design choices below are recorded for the user to
overrule.

**How it was checked.** ngspice, driven through its own control language, not
the project's parser: every Stage 3 band against the corner extremes of the
same tolerance box (85 comparisons, exact to 10⁻⁵); every Stage 4 property at
every corner and random interior points (64 properties, 624 evaluations);
tightness (a bound 10⁻⁶ inside the observed extreme must be refuted, 10⁻⁶
outside proven); every mutation counterexample replayed as a real violation
(64/64). Designs and property hashes compared across four PYTHONHASHSEEDs
(identical — a signature survives a restart). A few hundred random
requirements fuzzed through `realize()`. Adversarial strategies against the
refine loop. Older IntentIR dumps (2.0.0, 2.1.0) load.

1. **The refine loop accepted a proof over a smaller box.** It checked the
   statement and obligation hashes, never the region decided: a strategy that
   decided only the nominal point returned "proven" for a property false over
   the box, and was accepted. Stage 4's adversarial-weakening gate was
   reported met; it was only partly met. Now every result carries a
   certificate — per obligation, the boxes decided UNSAT — and `prove()`
   checks they tile the frozen box (inside it, interiors disjoint, volumes
   summing to its volume) and re-decides each box itself. A box z3 cannot
   re-decide in time downgrades the result to `unknown`, never raises.
2. **Denominators were not proved non-zero.** z3 reads x/0 as any value. All
   89 denominators on the grid were positive, so no existing proof was wrong;
   nothing enforced it. Each distinct denominator is now a lemma.
3. **rc_lowpass 0.2.2: a declared source impedance was read and ignored.**
   The envelope accepted a source that moved f_c past tolerance, and
   `rc.source_loading` then failed on the design just produced. Now refused
   by name. *Rejected alternative:* compensating R1 by R_s — a better design
   for the user, but it changes every source-declaring design; left for the
   user to choose.
4. **led_indicator 0.1.1: R1 could overheat inside the envelope.** At 17 mA
   from a 5.25 V pin, ngspice puts the worst corner at 64.7 mW in a 62.5 mW
   part. The envelope checked pin and LED current, never dissipation. It now
   refuses when the sound (G2) bound exceeds the rating — the divider's test.
   This is conservative: 16.45 mA at 5.24 V (true worst 61.7 mW, bound
   62.9 mW) is now refused too. And LED1 carried its 5 V *reverse* rating as
   `supply_voltage_max`, so the voltage-rating rule failed every accepted LED
   above 5.0 V; it now has no supply rating.
5. **`realize()` ran on the event loop** in the generate and patch routes.
   With Stage 4 proofs that is 0.1–1.7 s of CPU per request blocking every
   other request. Both now use `run_in_threadpool`, as sign-off already did.

Kept as regressions: `tests/test_accepted_designs.py` (a seeded corpus; on
the pre-fix code it fails 10 designs, 4 RC and 6 LED), `tests/test_proof_oracle.py`
(ngspice at every corner of every default property, and every
counterexample replayed), certificate and denominator tests in
`tests/test_proof.py`, refusals in `tests/test_generator_library.py`, and
sign-then-patch through the routes in `tests/test_sign_off.py`.

**Existing tests changed, and why.** Three fixtures used a 600 Ω source as an
arbitrary "touches only R1" value: the criterion-7 patch chain
(`test_intent_patch.py`) and two locality / predict-delta tests
(`test_realize.py`). Against R1 ≈ 1.6 kΩ that is a 27% cutoff shift — those
designs had carried a failing `rc.source_loading` claim all along, unseen
because the tests do not read claims — and 0.2.2 now refuses them. They use
200 Ω and 60 Ω, inside tolerance; what each test checks is unchanged. Two
tests in `test_llm_cannot_write_circuit_ir.py` matched the route source for
the literal `realize(generator, intent)`; they now also accept
`run_in_threadpool(realize, generator, intent)`, the same path off the loop.

**Not verifiable here:** sign-off against a real PostgreSQL (no database in
this environment — the conditional UPDATE is the patch route's, whose
predicate is tested); live-LLM paths (no key); hardware (D1 stays open —
ngspice agreeing with the prover is model against model).

---

## [2026-09-23] RC source swamping (rc_lowpass 0.2.3) and the LED bound — decided with TypeSafe

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

---

## [2026-09-23] The unverified three — PostgreSQL, the live model, hardware

**Decision:** On the instruction to close what the Stage 3 + 4 verification
left unverified, each of the three was run as far as this machine allows.

**PostgreSQL — verified.** The project's own `db` container (cached
`postgres:16-alpine`), a separate `circuitos_test` database so development
data is untouched. `tests/test_postgres_signoff.py` runs the routes, `get_db`,
`crud` and the conditional UPDATE against it and reads every result back
through a fresh connection: the signature is stored and survives a restart
(the design rebuilt from the stored intent is identical and still signed);
a wrong hash writes nothing; signing twice writes once; sign-then-patch
stores an unsigned v2 and its history row; and a real race — writer 2's
UPDATE blocking on writer 1's row lock, then matching nothing — lands exactly
one. The existing `test_request_log.py` Postgres round trip, skipped until
now, passes too. Redis could not start: Windows reserves ports 6292–6391
(WinNAT), which covers 6379 — a system setting the agent does not change.

**The live model — two defects found and fixed; one decision for the user.**
Nothing had ever exercised the Phase 2 LLM paths live; `tests/test_live_llm_paths.py`
now does (auto-skipped without a key). Against the configured model
(`anthropic/claude-opus-5` via OpenRouter):

1. *The producer was told function names only,* so it invented field names
   (`targets.output_v` for `targets.vout_v`) and listed fields no generator
   reads as underdetermined — every plain request came back as questions.
   The prompt now carries each function's fields (path, units, required) from
   the form catalogue, and `underdetermined` keeps only what the model flags
   that is a *required* field of the chosen function and really unset. A
   missing field the model neither records nor flags still goes to the
   envelope and X5's one retry, unchanged. An uncatalogued function asks
   nothing — it is refused. After the fix: all five plain requests reach
   their generator and prove; a buck converter is refused, not bent; "2 kHz"
   becomes a cited operation; "double the cutoff" returns no operations and
   asks for the value; generate → sign-off → patch passes end to end on
   PostgreSQL.
2. *The explainer's 2048-token ceiling* was consumed by thinking: two calls in
   three returned no text, the third a report cut off mid-table, shown as if
   whole. Now 8192, and a call that stops at the ceiling raises instead of
   returning half a report (the route already treats explanation as
   best-effort).

**For the user:** with this model an explanation takes 110–130 s and ~$0.20,
and the largest design (RS-485) still exceeds 8192 tokens — so generation
cannot meet the 15 s launch target. The likely fix — thinking disabled for
the explainer call — could not be tried: the OpenRouter account returned 402
`in_flight_budget_exhausted` (credits). Options: top up and try it; a faster
model for explanations; or explanations off the request path.

**Hardware — cannot be done here.** `docs/BENCH_D1.md` is a one-hour bench
session for three designs (RC 1 kHz, divider, LED) with their exact parts,
the proven bands as pass criteria, and a results table. D1 stays open.

---

## [2026-09-24] Task 4.5 — exact LED dissipation; annotations drawn in the schematic

**Decision 1 — R1's dissipation is decided exactly (led_indicator 0.1.2).**
Scheduled at [2026-09-23] RC source swamping; done before Stage 5 lands.

- *The fact it rests on.* In V → R_out → R1 → LED, dP/dR1 =
  I²·(R_out + r_d − R1)/(R_out + R1 + r_d) with r_d = n·V_t/(I + I_s). The
  bracket falls strictly in R1 (r_d rises, but by less than R1 does), so
  I²·R1 has one peak, at R1 = R_out + r_d. At a fixed R1 the power rises with
  I, so R_out and V_f sit at the current band's corners.
- *predict() and envelope().* `r1_power_max_w` evaluates the peak if R1's
  range straddles it (bisection on the bracket) and the right end if not.
  Checked against a 20 001-point sweep, straddling ranges included: equal to
  the float. Method `monotone_corners`, G1. Gain as scheduled: 16.3–16.5 mA
  from a 5.25 V pin is accepted, true worst 62.0 mW in a 62.5 mW part.
- *The proof.* `series_power(R, D)` now proves a monotonicity lemma over the
  whole box — "R ≥ R_rest + n·V_t/I_lo" with I ≥ I_lo proved beside it (falls),
  or "R ≤ R_rest + n·V_t/(I_hi + I_s,max)" with I ≤ I_hi (rises) — and then
  decides the property at the end of R's range the lemma names: proved at
  ⌊√(P_max/R)⌋, refuted *for certain* at ⌈√(P_max/R)⌉. Lemma bounds are
  float guesses and are carried as obligations, so nothing trusts them
  unproven. Only a series R whose range straddles the peak falls back to the
  old current bound (`sound_enclosure`, G2, witness-certified refutation).
  The reduction applies only when ∂R_th/∂R = 1 and ∂V_th/∂R = 0 — R in series
  with the diode — checked symbolically, never assumed.
- *Result.* Every LED property G1 at every grid point; a P_max 0.01% above
  the true worst case is proven and 0.01% below is refuted with a certified
  point; the ngspice oracle (`test_proof_oracle.py`) passes unchanged. The
  library's signed floor is G1: the LED's `proof.led.r1_power` was the last
  G2 row. (Unsigned designs still show the divider's Stage 3 G2 interval
  bound until their proofs are signed — unchanged, by design.)

**Decision 2 — annotations appear in the schematic, as text only.**
Stage 2 left them "stored and returned but not drawn".

- `KiCadSchematicGenerator.generate(ir, annotations=())`. Merged after
  generation; `realize()` still takes none (X2), and with none the output is
  byte-identical to before.
- A net name is written *beside* the node's label, never as the label. In
  KiCad a label is connectivity: an annotation that renamed a net — or named
  it after another net — would merge nets, an input to the design by the
  back door. Test points, placement hints and comments sit by their anchor.
- Design comments, orphans and anything cut short inline go in an
  "Annotations" block under the parts, in up to two columns on the A4
  sheet; if even that overflows, the last row counts what did not fit. The
  full list is always in the API response. Orphans are drawn as ORPHANED,
  never dropped.
- `PUT /design/{id}/annotations` re-renders and stores the schematic (the
  drawing, not the design: circuit, version and claims untouched) and
  returns it. Patches draw the stored annotations into the new revision.

**Alternatives rejected:**
- *Split R1's box at the peak and prove each half.* The certificate checker
  requires every obligation to be decided over the frozen box; per-half
  obligations would need a domain field on `Obligation` and a tiling rule per
  field. The lemma reaches the same exactness with the checker unchanged.
- *Render a net name as the KiCad label.* Collides on connectivity (above).
