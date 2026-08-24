# Current Phase: Phase 2 — Validation Engine

> Worker's instruction sheet. Set by the planner after each session.
> Last updated: 2026-08-25 (Phase 1 closed; Phase 2 opened)
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
