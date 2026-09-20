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
