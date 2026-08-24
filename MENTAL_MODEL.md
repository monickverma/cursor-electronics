# Circuit OS — Mental Model

> **What this file is for.** One picture of the whole project, readable in ten
> minutes, honest about what is real and what is not. When you have been away
> for two weeks and cannot remember where things stand, read this.
>
> Last updated: 2026-08-22. **Current counts live in `state.json`** — this
> file no longer restates them, because it carried 318 tests and 10/12 for
> two weeks after both changed.
>
> Not a replacement for `PRODUCT_MASTER.md` (the full spec) or
> `.claude/shared-memory/` (machine-verified state). This is the map; those are
> the territory.

---

## 1. The One Sentence

**You type what you want a circuit to do. The software designs it, wires it,
writes the firmware, simulates it, and tells you what will break — before you
touch a component.**

Everything below is detail on that sentence.

---

## 2. The Idea In One Diagram

```
        "Arduino reads DHT22, alert above 40°C"        ← plain English
                          │
                          ▼
                   ┌─────────────┐
                   │   THE LLM   │   writes JSON only. Never SPICE.
                   └─────────────┘   Never KiCad. Never .ino.
                          │
                          ▼
              ╔═══════════════════════╗
              ║      CircuitIR        ║   ← the contract everything reads
              ║  (one JSON schema)    ║     backend/core/ir_schema.py
              ╚═══════════════════════╝
                          │
        ┌────────┬────────┼────────┬─────────┐
        ▼        ▼        ▼        ▼         ▼
    ┌───────┐┌───────┐┌───────┐┌───────┐┌────────┐
    │ SPICE ││ KiCad ││ .ino  ││  BOM  ││  PCB   │   deterministic compilers
    │netlist││schem. ││firmwr ││ table ││ layout │   same input = same output
    └───────┘└───────┘└───────┘└───────┘└────────┘
        │
        ▼
    ┌────────────┐
    │  ngspice   │  actually runs the physics
    └────────────┘
        │
        ▼
    ┌─────────────────────────────────────────┐
    │  PASS / FAIL  +  plain English of why   │  ← the part users pay for
    └─────────────────────────────────────────┘
```

---

## 3. The One Rule That Explains Every Design Decision

> **The LLM never writes SPICE, KiCad, or firmware directly. It writes JSON
> against a schema you control. Deterministic compilers translate that JSON.**

Ask "why is it built this way?" about almost anything and the answer traces back
here.

| Question | Answer |
|---|---|
| Why an IR at all? | LLMs hallucinate syntax. They hallucinate schema fields far less, and a schema violation is *catchable* — SPICE that is subtly wrong is not. |
| Why Jinja2 firmware instead of LLM-written `.ino`? | LLM firmware invents function names and pin numbers. Templates give identical output for identical input. |
| Why only 5 circuit templates? | Five that work every time beat twenty that work 60% of the time. Trust compounds; breadth does not. |
| Why `tool_use` mode always? | `response.content[0].input` is already a parsed dict. No JSON parsing, no markdown-fence stripping, no whole class of errors. |
| Why net labels instead of wire routing in KiCad? | Wire routing needs exact pin coordinates from the symbol library. Net labels connect by name — generatable without a lookup. |

**If you ever find LLM output reaching ngspice, KiCad, or a `.ino` without
passing IR validation first, that is a bug, not a shortcut.**

---

## 4. What Exists Right Now — The Honest Version

Three tiers. Be clear about which is which, especially when demoing.

### ✅ Tier 1 — Real, tested, works

The whole Phase 1 pipeline, end to end:

- Prompt → `DesignSpec` → `CircuitIR` (3-attempt retry on schema failure)
- 5 templates: DHT22, RS-485 Modbus, LED, RC filter, voltage divider
- SPICE netlist → ngspice → parsed → graded pass/fail at 15% tolerance
- Arduino `.ino` — **compiles and flashes to real hardware**, confirmed via arduino-cli
- KiCad `.kicad_sch` export, static BOM
- 5 validation rules: floating nodes, voltage ratings, I2C pull-ups, RS-485 termination, PWM pins
- Conversational editing via diff-and-patch (never regenerates)
- JWT auth, rate limiting, Postgres persistence, Celery for simulation
- Generation ~15s end to end

The strongest single fact: **simulation correctly fails on deliberately wrong
values.** Swap the RC filter capacitor to 1nF and it reports FAIL. A validator
that only ever passes is worthless; this one says no.

### ⚠️ Tier 2 — Built and shipping, but unverified

**The PCB layout engine.** ~2,400 lines: A* router, DRC kernel, footprint
inference, candidate scoring, SVG rendering. Live at `POST /pcb/compile` with a
frontend tab, both gated by a flag and off in production.

Two things to know:

1. It is a **custom engine, not KiCad freerouting** — the roadmap says
   freerouting, so the roadmap will mislead you.
2. It was Phase 3 scope built during Phase 1. Declared as of 2026-08-22; before
   that it was undeclared, and undeclared scope is how Phase 1 stops finishing.

Placement and the route are tested; **routing quality is not** — that is what
keeps this in Tier 2. Per-module status is derived: read `progress.yaml`.

**Decided 2026-08-22, shipped 2026-08-24:** in scope, experimental, labelled,
behind a config flag. Rationale lives in `brain/decisions.md` — "[2026-08-22]
PCB engine is in scope, experimental, and labelled". Off in production, where
`POST /pcb/compile` returns 501 and the frontend hides the tab.

### ⬜ Tier 3 — Does not exist

Gerber export, live Digikey/LCSC pricing, ESP32/STM32 firmware, waveform graphs,
free-form generation beyond the 5 templates, RAG on datasheets, team features,
analog power electronics, DCV/hood/refrigeration boards, SCADA RTU.

All of it is roadmap. **Do not imply otherwise in a demo.**

---

## 5. Where The Project Actually Stands

A bar drawn here is a *picture* of the progress bar. The bar itself is
`progress.yaml` and `state.json` — read the fill level there:

```
phase1_criteria_done / phase1_criteria_total   → state.json
verified / total entries                       → progress.yaml
```

Phase 2 has not started.

**Phase 1 has been functionally complete since early June.** It has sat unsigned
for two months because the last two criteria needed things you did not have — an
oscilloscope and a reviewer — and instead of resolving those, the project built
a PCB engine.

That work is not wasted. But the gap between "done" and "signed off" is now
filled with untested code, and it widens.

| # | Criterion | Status |
|---|---|---|
| 1–10 | auth, speed, simulation, rules, firmware, patches, load, rate limits | ✅ |
| 11 | Simulation accuracy | ⏳ analytical cross-check, not yet written |
| 12 | External engineer cold-reads an explanation | ⏳ needs a person |

**Criterion 11 was changed on 2026-08-07.** Oscilloscope at 15% → closed-form
equations at 2%. Reason: no lab access, and the failure mode it really guards
against is a buggy netlist generator, which is code written here. ngspice itself
is mature and independently validated. Tolerance tightened because there is no
physical component tolerance to absorb.

**It is marked `met_by_substitute`, not `met`.** It checks the netlist generator
against mathematics, not reality. It cannot catch parasitic capacitance, contact
resistance, or a component behaving off-datasheet. Your public claim is
"simulates before it ships" — that claim is owed a physical measurement
eventually. Do not let `met_by_substitute` quietly become `met`.

---

## 6. Numbers, And Why One Of Them Dropped

Read them from `state.json` and `progress.yaml`. They are regenerated by
`tools/regen_state.py` and are right by construction; anything written here
would be right for one commit.

**On 2026-08-07 the verified figure went 84.4% → 48.3% → 56.7%.** Nothing broke.

The 84.4% was measured over 32 entries because the memory trackers iterate a
**hardcoded module list**, and the PCB engine was never added to it. It was not
counted as untested — it was not counted at all. Registering it moved the
denominator to 60 (→48.3%), then the new patcher and explainer tests earned it
back to 56.7%.

**The lesson worth keeping: a wrong denominator looks like health. That makes it
more dangerous than a failing test, which at least announces itself.**

Standing rule now in `AGENTS.md`: register every new module in **both**
`tools/regen_state.py` and `tools/progress_gen.py`, in the same commit.

---

## 7. The Codebase In One Table

| Where | What | Trust |
|---|---|---|
| `backend/core/ir_schema.py` | **The contract.** Every layer reads it. Never rename fields — `component_id`/`node_id`, not `component`/`node`. | ✅ |
| `backend/ai/intent_parser.py` | Prompt → `DesignSpec` | ✅ |
| `backend/ai/circuit_reasoner.py` | `DesignSpec` → `CircuitIR`, 3-attempt retry | ✅ |
| `backend/ai/patcher.py` | IR + command → **patch only, never full IR** | ✅ |
| `backend/ai/explainer.py` | IR → consequential plain English. **The product.** | ✅ |
| `backend/generators/` | SPICE, KiCad, Arduino, BOM compilers | ✅ |
| `backend/simulation/` | ngspice runner, parser, grader, monitor | ✅ |
| `backend/validation/rule_engine.py` | Hardware rules | ✅ |
| `backend/pcb_engine/` | A* router, DRC, footprints, SVG | ⚠️ untested |
| `frontend/` | Next.js, two-panel, kicanvas viewer | partial |
| `.claude/shared-memory/` | Machine-verified project state | ✅ |

**Run it:** `start.bat` at the project root. Docker for Postgres/Redis, then three
windows — backend :8000, Celery worker (`--pool=solo`, required on Windows),
frontend :3000. PCB engine has no separate port; it is inside the API.

---

## 8. Four Things That Will Bite You

Hard-won, all documented in `brain/decisions.md`. Each cost real debugging time.

1. **MCU in SPICE is a 100Ω resistor, not a voltage source.** Two voltage
   sources on one node = singular matrix = ngspice refuses to run. The MCU draws
   current; it does not supply voltage.
2. **ngspice batch output is columnar.** The regex `v(x) = y` does not match it.
   Costs an afternoon every time someone forgets.
3. **kicanvas must be `dynamic import` with `ssr: false`.** It touches
   `document` at module level; server-side rendering crashes.
4. **Simulation always goes through Celery.** `await` releases the event loop
   but keeps the HTTP connection open — a 30s simulation still times out the
   client. Note: the PCB engine currently violates the spirit of this by running
   in-process. If layout times grow, revisit.

---

## 9. Why This Wins (And Where It Doesn't)

Three real competitors. All three are good at something.

| | Flux.ai | Celus.io | Quilter | **You** |
|---|---|---|---|---|
| Natural language in | ✅ | ✅ | ❌ | ✅ |
| Schematic out | ✅ | ✅ | ❌ | ✅ |
| **SPICE simulation** | ❌ roadmap | ❌ | ❌ | **✅ shipping** |
| **Complete firmware** | ⚠️ pin maps only | ❌ | ❌ | **✅ flashable .ino** |
| **Consequential explanation** | ❌ | ❌ | ❌ | **✅** |
| PCB layout | ✅ | ❌ | ✅ best in class | ⚠️ untested |
| **Industrial rules** (RS-485, 4–20mA, UL 508A) | ❌ | ❌ | ❌ | roadmap |

**The wedge:** *"The only AI hardware tool that simulates before it ships — with
physics-validated results, consequential explanations, and industrial-grade rule
libraries for HVAC, refrigeration, and building automation."*

**Be honest about where you lose.** Flux beats you on breadth and polish today.
Quilter beats you on layout and it is not close. Celus has more component data.
You win on *depth of validation*, and only if the validation is genuinely
trustworthy — which is exactly why criterion 11 being a substitute matters and
why 2,400 untested lines in the PCB path is a real problem, not a bookkeeping one.

**The untouched ground:** none of the three has industrial rule libraries. No
RS-485 bias and termination, no 4–20mA loops, no 24VDC industrial supplies, no
DCV or refrigeration templates. That vertical is the highest-margin, most
defensible part of the plan and nobody is standing there.

---

## 10. The Product Differentiator, Stated Plainly

Any engineer can run ngspice. What no existing tool does is say:

> "I chose the DHT22 over the DS18B20 because your prompt specified digital
> output and you are on a 3.3V Arduino — the DS18B20 needs a pull-up to VCC and
> at 3.3V the logic levels are marginal. If you need higher accuracy, the SHT31
> is better but costs 3× more."

That is **consequential** explanation. Compare:

- ❌ Descriptive: *"R1 is a 10kΩ pull-up resistor for the DHT22 DATA pin."*
- ✅ Consequential: *"R1 pulls DATA high between transmissions. Without it the
  open-drain output never reaches logic HIGH and the MCU reads only timeouts.
  Below 3kΩ you exceed the DHT22's 5mA sink limit at 5V."*

Every sentence answers **"what breaks if this is wrong?"**

This is also the data flywheel: every explanation is a labeled training example.
And it is why criterion 12 is a *human* reading the output — no test can measure
whether an explanation is genuinely good. The tests catch prompt regressions,
not quality regressions.

---

## 11. What To Do Next

Shortest honest path to a tagged `v0.1.0`:

1. ~~Test debt on `patcher.py` and `explainer.py`~~ ✅ **done 2026-08-07**
2. **Write `tests/test_simulation_accuracy.py`** — closed-form comparison, 5+ R/C
   pairs across 100Hz–100kHz, 2% tolerance. Closes criterion 11. No dependencies.
3. **Decide the PCB engine's status** and record it. A decision, not code.
4. **Find one engineer** to cold-read a DHT22 explanation. Closes criterion 12.
5. `PHASE1_COMPLETE.md`, then `git tag v0.1.0`.

Steps 2 and 3 can happen today. Step 4 is the long pole — start looking now, it
has been open since June.

**Then stop and hold the line:** no Phase 2 work until v0.1.0 is tagged. The
PCB engine is what happens when that rule bends.

---

## 12. Where To Look For What

| Question | File |
|---|---|
| Full product spec | `PRODUCT_MASTER.md` |
| What am I working on right now | `.claude/shared-memory/plan/current_phase.md` |
| Machine-verified module state | `.claude/shared-memory/progress.yaml` |
| Why was X decided this way | `.claude/shared-memory/brain/decisions.md` |
| What happened when | `.claude/shared-memory/brain/timeline.md` |
| Module map and data flow | `.claude/shared-memory/brain/architecture.md` |
| Roadmap, all 5 phases | `.claude/shared-memory/plan/master_plan.md` |
| Coding rules | `.claude/rules/` |
| How an agent should boot up | `.claude/shared-memory/AGENTS.md` |

**Trust order when sources disagree:** test results → source code → `progress.yaml`
→ `current_phase.md` → `brain/*.md` → prose summaries (including this file).

Reality cannot lie. Everything else can go stale — as this project learned the
hard way in July.
