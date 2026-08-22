# Circuit OS — Where You Are and What To Do Next

> **What this file is.** `MENTAL_MODEL.md` tells you what the project *is* and
> what's real. This file tells you what to *do*, in order, starting Monday.
> If you only read one thing, read §2.
>
> Last updated: 2026-08-22 · commit `36923cf`

---

## 1. Where you are, in four lines

- **Phase 1 is 11 of 12 criteria done.** ~410 tests passing, 0 failing.
- **The one thing left needs a person**, not code: an engineer reading an
  explanation cold. It has been open since 2026-06-02 — nearly twelve weeks.
- **The core pipeline is real**: prompt → IR → SPICE + KiCad + firmware + BOM,
  ~15 seconds, and it correctly *fails* on wrong values.
- **The PCB engine is not real yet.** As of today it is honestly measured for
  the first time, and the measurement was ugly. See §4.

---

## 2. The steps, in order

Each step says how long and who has to do it. Steps 1 and 2 are yours; nobody
else can do them.

### Step 1 — Send the criterion 12 outreach · **10 minutes · only you** · ⬜

Three messages to three EE-literate people who have not seen the project.
Templates and the review protocol are in `outreach-messages.md` and
`CRITERION_12_REVIEW.md`.

**Do this first, before any code.** It is the only task with multi-day latency.
Everything else on this list is same-day. Twelve weeks of this criterion sitting
open is twelve weeks where the outreach was never sent — not twelve weeks where
nobody replied.

### Step 2 — Decide the PCB engine's scope · **5 minutes · only you** · ⬜

Pick one and write it into `brain/decisions.md`:

- **(a) In scope, tested** — gate v0.1.0 on it
- **(b) In scope, experimental** — flag it, label it in the UI, exclude from the gate
- **(c) Out of scope** — leave it, don't advertise it

Recommendation is **(b)**, and §4 makes it more urgent than it looked yesterday.

### Step 3 — Tag v0.1.0 · **1 hour · after step 1 comes back** · ⬜

1. Write `PHASE1_COMPLETE.md` — evidence per criterion, criterion 11 marked
   **`met_by_substitute`** with its limitation spelled out, the step-2 decision
   recorded.
2. `python .claude/shared-memory/tools/regen_state.py`
3. `git tag v0.1.0 && git push --tags`

### Step 4 — Choose which Phase 2 is Phase 2 · **an afternoon of thinking** · ⬜

You have two different Phase 2s written down and nothing reconciles them. See
§5. This decision is worth more than a week of code and costs nothing but
attention.

### Step 5 — Build it. ⬜

---

## 3. What changed today

Worth knowing, because it moves two things on the list.

**Criterion 11 closed.** `tests/test_simulation_accuracy.py` compares the SPICE
netlist generator against closed-form equations across six R/C pairs from 100 Hz
to 100 kHz. Worst deviation **0.0003%** — your netlist generator is essentially
exact. Marked `met_by_substitute`, not `met`: it validates against mathematics,
not physical reality, and the bench measurement is still owed.

**The memory trackers were lying, and now aren't.** Criterion 11 was hardcoded
to `⏳` with no code path to `✅` — green tests could never have moved it. Resolved
blockers were still being published as live. Both fixed.

**The PCB engine turned out to be broken.** See §4.

---

## 4. The PCB engine — read this before demoing it

A placement harness was written today, on the reasoning that you cannot tell
whether a placement change helps without a way to measure placement. Its first
run said this:

| Template | Components placed |
|---|---|
| DHT22 | 2 of 4 |
| LED | 1 of 4 |
| RC filter | **0 of 2 — empty board** |
| Voltage divider | **0 of 2 — empty board** |
| Modbus | 1 of 6 |

`footprints.py` had no surface-mount packages at all — only DIP, TO-92, TO-220,
DO-41, AXIAL, RADIAL, HEADER and RELAY. Every example circuit specifies `0402`
for its passives, so every passive failed the footprint lookup and was skipped.
The engine warns, but the warning goes into a list the frontend never shows.

**The PCB tab has been shipping boards with most of the parts missing, and for
two of five templates, boards with nothing on them.**

Fixed today: SMD packages added, all five templates now place 100%. But the
wider point stands — this is what 2,400 lines with zero tests buys you, and it
went unnoticed for two months. It is a strong argument for **(b)** in step 2:
label it experimental until it has been measured properly.

Still broken and deliberately not fixed: SOIC-8 pin assignment. Pin 1 is RO on a
MAX485 and an output on an op-amp; there's no package-wide truth, so the MAX485
in the Modbus template still gets arbitrary pins. It warns. Per-part pinmaps are
the real fix.

---

## 5. The fork: which Phase 2 is Phase 2?

Two documents in your own repo describe different next phases, and neither
mentions the other.

| | `master_plan.md` — **Validation Engine** | `PCB_STRATEGY.md` — **Constraint layer** |
|---|---|---|
| Thesis | Broaden what it can generate | Own what nobody else can derive |
| Contents | Free-form generation (15+ circuits), ESP32/STM32, live BOM pricing, Qdrant RAG on datasheets, waveform viewer, version history UI | Net classes and differential pairs exported with a plain-English reason attached, annotated board viewer, KiCad/DSN export for designers |
| Bet | More users can use it for more things | Fewer users, but nobody can copy it |
| Risk | Every feature is one a competitor can also build | Might be a rationalisation for not competing on layout |

**The case for the constraint layer** (from `PCB_STRATEGY.md`, written
2026-08-07): your `CircuitIR` already knows that two nets are `rs485_a` and
`rs485_b` — a differential pair needing matched length, 120Ω termination at both
physical ends and nowhere else, TVS at the connector. Flux has design context but
no physics. Quilter only ever receives a netlist, so intent never reaches it.
Nobody else can derive layout constraints from intent, because nobody else has
intent → IR → simulation in one system. Constraints are portable across routers;
routers are not.

**The case for the Validation Engine**: it is what `PRODUCT_MASTER.md` promises,
it is what a $49/month tier is actually sold on, and free-form generation beyond
five templates is the difference between a demo and a product.

**An honest reading:** these aren't mutually exclusive, they're differently
sequenced. The constraint layer is the more defensible bet and the cheaper one to
start. The Validation Engine is the one users will pay for sooner. Pick based on
whether the next six months are about **revenue** or about **moat** — and write
the answer down, because right now the repo argues with itself.

---

## 6. The rest of the roadmap, briefly

| Phase | What it is | Honest note |
|---|---|---|
| **3 — Industrial** | DCV boards, refrigeration, RS-485 optoisolation, UL 508A, private component libraries, audit trail | Highest margin, zero competitors standing there, longest sales cycle. This is where the plan's real value sits. |
| **4 — Enterprise** | Gerber export, JLCPCB/PCBWay APIs, DFM report, SSO, ROI dashboard | The procurement checklist. Downstream of layout quality being trustworthy — premature until then. |
| **5 — Advanced** | Thermal sim, power electronics, MTBF, full data pipeline generation | Years out. Don't plan around it. |

---

## 7. The rule about phases, amended

The old rule read: *"Phase 2 does not start until Phase 1 v0.1.0 is tagged."*

That rule targets the wrong variable. The PCB engine did not hurt you because it
was built early. It hurt you because it was **undeclared, untested, and shipped
into the product UI** while the memory system reported 84.4% verified — and
today that turned out to mean a tab in your product rendering empty boards.

The amended rule:

> **Phase 2 work may start in parallel with Phase 1 sign-off. What may not
> happen is shipping unregistered, untested surface into the product.**
>
> Specifically:
> 1. Nothing displaces the criterion 12 outreach or the tag. Sign-off keeps priority.
> 2. Any new module is registered in both trackers in the same commit.
> 3. Anything reaching the API or the UI before v0.1.0 is either tested or
>    labelled experimental. Not neither.
> 4. New scope is written into `brain/decisions.md` when it starts, not discovered
>    two months later.

Build early if you want. Just don't build invisibly.

---

## 8. Where to look for what

| Question | File |
|---|---|
| What is this project, honestly | `MENTAL_MODEL.md` |
| Full product spec | `PRODUCT_MASTER.md` |
| Should we build our own router | `PCB_STRATEGY.md` |
| What am I working on right now | `.claude/shared-memory/plan/current_phase.md` |
| Machine-verified state | `.claude/shared-memory/state.json`, `progress.yaml` |
| Why was X decided | `.claude/shared-memory/brain/decisions.md` |
| How do I close criterion 12 | `CRITERION_12_REVIEW.md` |

**Trust order when sources disagree:** test results → source code → `progress.yaml`
→ `current_phase.md` → `brain/*.md` → prose, including this file.
