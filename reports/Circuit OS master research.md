# Circuit OS has the rare front half; the next proof and the next sale both run through one built board

*Master research report, a snapshot dated 2026-11-13, corrected 2026-11-14 against the November competitor pass ([what changed](#what-the-november-competitor-pass-changed-2026-11-14)). It rests on eleven earlier reports and on the code-level record of the project. It adds no new market research; one claim was re-checked on the web and is labelled.*

## The answer in one page

**What exists in the world.** Four different things are sold as "validation", and they are routinely confused: formal proof, physics simulation, rule checks, and machine-learned layout ([§3.1](#31-four-things-are-called-validation-and-only-one-is-proof)). Board-level physics simulation (signal integrity, power delivery, thermal, EMC scans) is widely sold by Siemens, Cadence, Ansys, Keysight and Altium, and much of it can be reproduced with free tools. No vendor, free or paid, claims to prove that a board works ([§3.3](#33-every-commercial-stack-stops-at-a-model-and-says-so)). The AI-board competitors split at the schematic. Quilter lays out boards someone else designed and checks them with eight geometric rules. Flux drafts a design in a browser; since October–November 2026 it also runs built-in ngspice, claims EM/SI, PDN and thermal analysis, compiles firmware and takes fab orders. CELUS keeps the requirement as an Intent Document, and Circuit Mind's AVE reviews existing schematics. None publishes per-claim verification, and none claims proofs ([§3.1](#31-four-things-are-called-validation-and-only-one-is-proof); corrected 2026-11-14).

**What Circuit OS has that is real.** The front half works and goes further than anything a competitor publishes ([§4](#4-what-circuit-os-has-checked-against-the-code-record)):
- the requirement is fixed before any design is made, and requests outside the catalogue are refused;
- deterministic generators build the circuit;
- z3 proves properties over the full component tolerance ranges;
- every claim is graded and names its defeaters;
- firmware is shown only once it compiles.

The board half is experimental. It is two layers and at most 40 parts. None of its land patterns is verified, it has no fab profile, and its nets carry no voltage, current or role. Fabrication export exists only on the `alpha-program` branch, and it is not wired to any user. Nothing has been built, measured or flashed (defeater D1). The MCU model and most datasheet figures are unverified (D2, D7).

**Where to move** ([§7](#7-where-to-move-forward)):
1. Ask today's users to pay before building anything new.
2. Build and measure one Circuit OS board, and offer it per design. That single act closes D1, gives the only physical evidence in this market, and runs the most informative sales test.
3. Fix part truth and net meaning on the board. This is the feature spec's P0 work, and it is where Circuit OS can be first: creepage derived from working voltage, and trace width checked against currents the proofs computed. (Narrowed 2026-11-14: Siemens now validates creepage, and Quilter sizes widths from typed currents; what stays first is deriving both from proved quantities, [§7.3](#73-give-the-board-its-part-truth-and-its-net-meaning).)
4. Merge and expose the release package that already exists on a branch.
5. Relabel what the verifier says, so "unknown" stops meaning "impossible".
6. Only then add the cheap physics that matches Quilter: physics rule checks and DC IR drop.

**What to stop considering** ([§7.8](#78-what-not-to-build-and-why)):
- the checker for imported designs (retracted by the paying-customer report);
- the $49 hobbyist subscription and the word "unlimited";
- industrial/HVAC as an "uncontested moat";
- integrating Quilter;
- extending the A* router instead of using Freerouting;
- field solvers and PyPEEC for today's board class;
- widening the catalogue before a named payer asks for a block.

**The plainest bad news.**
- Nobody has yet been shown to pay for what Circuit OS does (R9, opening).
- The owner's market page is wrong in both directions. It overstates Quilter's physics, understates Flux and Altium, and marks Circuit OS "Only you" on rows where it has nothing in code or where rivals have the same thing (R6, §"Corrections to the owner's market page"). Counted 2026-11-14: 10 of its 13 "Only you" cells are false; consequential explanation, requirement-level patching and RS-485 rules survive ([matrix §5](<Competitor feature matrix.md#5-the-owners-market-page-corrected>)).
- `ROADMAP.md` and `MENTAL_MODEL.md` still describe the project as of August 2026 ([§4.5](#45-three-documents-the-owner-reads-first-are-out-of-date)).

---

## What the November competitor pass changed (2026-11-14)

A product-by-product pass read 26 competitors' own pages on 2026-11-12 to 2026-11-14. It is in
[`competitor-features/`](competitor-features/) and merged in
[`Competitor feature matrix.md`](<Competitor feature matrix.md>). This report was written from the
2026-10-21 teardowns; where the pass contradicts it, the text below was corrected in place and says
so. Nothing was deleted. The recommendations and their order are unchanged; three of them rest on
changed reasoning.

| Where | Edit | Why |
|---|---|---|
| One-page answer | Flux, CELUS and Circuit Mind sentence; "first" claim narrowed; "Only you" count added | Flux now simulates, compiles firmware and orders boards; CELUS has an Intent Document; Circuit Mind launched AVE; Siemens validates creepage |
| §2.3 | "Being written separately" pointer replaced with links | The inventory now exists |
| §3.1 table and Flux bullet | Flux's simulator is built-in ngspice, not beta; Flux claims EM/SI, PDN and thermal; placement no longer manual; MCP server exists | [flux.md](competitor-features/flux.md) C1, C4–C6, D1, I2 |
| §3.1 Quilter bullet | The 2026-11-13 "weakens the through-vias limit" reading withdrawn; SOC 2 Type 2 and self-hosting added | [quilter.md](competitor-features/quilter.md) D2, D8, I3: blind/buried vias are "in active development" |
| §3.1 Altium bullet | Keysight Signal Analyzer described as a paid add-on; Requirements AI added | [altium.md](competitor-features/altium.md) C4, A5 (2026-10-14) |
| §3.1 schematic-side checkers | AVE, DRCY, Traceformer, NextPCB, CADY added | Review is now a crowded, cheap category ([_group-d.md](competitor-features/_group-d.md)) |
| §3.1 JITX bullet | Narrowed: the only one with a *named* full-wave solver | Flux claims full-wave EM without naming a solver |
| §3.1 evidence paragraph | NetlistBench, Long-Horizon Analog Bench, Qiao & Dick, Diode × Anthropic, E-Sharp added | [general-llm-assistants.md](competitor-features/general-llm-assistants.md) |
| §3.2 SPICE | List of products with SPICE widened | Matrix row C1: eleven products |
| §3.3 | Circuit Mind's "provable accuracy" noted | A proof-like claim with no published method |
| §3.5 | Flux tracker prices and plan moves; DeepPCB per hour, not per minute; new price points; AllSpice shows no figures now | Product files I4 |
| §4.5 | Market-page bullets corrected: the confidence field exists, as constants; more claims with no code | Code read 2026-11-14 |
| §5 ledger | R6 market-page row, R8 Flux-price row and R10 physical-evidence row updated | Matrix §5; Embedder flashes and tests on hardware |
| §6 items 8–9 | Flux prices and the via limit re-judged | Product files disagree with R9 and with the 2026-11-13 re-check |
| §7.2 | Embedder noted under evidence | Hardware-in-the-loop *firmware* testing exists; a built *board* still does not |
| §7.3 | "Nobody does" reasoning revised; recommendation stands | Siemens validates creepage; Flux, Altium and KiCad take user-typed distances |
| §7.7 | Parity target revised; recommendation stays last | Flux claims physics in every plan |
| §7.8 | Freerouting and imported-checker items strengthened; industrial item gains two facts; Quilter API absence confirmed again | Freerouting v2.5.0 REST/MCP; review crowded; Huaqiu Copilot, Circuit Mind's industrial customers |

---

## 2. How to read this

### 2.1 The eleven sources and how far each can be trusted

Short names R1–R11 are used throughout. "Run" means the authors executed something. "Read" means they opened primary pages. "Summary" means they worked from search snippets.

| # | Report | Date | Method | Trust |
|---|---|---|---|---|
| R1 | `Analog circuit formal verification.md` | Committed 2026-10-09. Its recommendations describe a proof compiler like the one built in Stage 4, recorded in `decisions.md` [2026-09-23] (inference that it predates the build) | Literature reading, mostly peer-reviewed papers | High for the theory (decidability and complexity results are theorems). Its novelty claim rests on absence from a search |
| R2 | `Is the board correct - a software-only verification tree.md` | 2026-10-09, corrected 2026-10-17 | 27 sources, 130 claims, 25 checked adversarially (22 confirmed, 3 killed) | Good for the tree and the rungs. Its "unknown / cannot reach" wording is **corrected by R6** |
| R3 | `PCB routing validation methods.md` | 2026-10-09 | Reading, plus KiCad DRC actually run | Good. One headline number corrected by R4 |
| R4 | `PCB routing validation methods - verification ledger.md` | 2026-10-09, updated 2026-10-17 | Second-pass check against primary sources, **plus local execution** | Highest of the PCB set: it separates run, checked and first-pass claims |
| R5 | `PCB verification implementation plan.md` | 2026-10-11 | Library parsing, `kicad-cli` exports and a read-back extractor **run**; methods read or summarised | High for what was run. Its pipeline design is labelled inference. Partly corrected by R6 |
| R6 | `Physics layout validation - what the market does and what Circuit OS can build.md` | 2026-10-16/17 | Eight researchers; claims sent to two checkers; 31 second-pass claims (14 confirmed as written, 17 partly supported and reworded); code audit with PCB tests run | The best-sourced market report. It corrects R2, R3, R5, `PCB_STRATEGY.md` and the owner's market page |
| R7 | `Validating the router in software.md` | 2026-10-09, status note 2026-10-17 | **Run**: harness scripts against the repository's own router | Highest. It found four executed defects, now regression tests |
| R8 | `Circuit OS customers and business model.md` | Notes gathered 2026-10-12 | Mostly search summaries; few pages opened | Low to medium. Its top recommendation is **retracted by R9** |
| R9 | `Circuit OS paying customer evidence.md` | Notes dated 2026-10-12, written after R8 | Price pages read in a browser; a 10-board tally the researcher graded; demand threads read | Medium. The strongest business source, but the 10-board tally is one researcher's judgement |
| R10 | `Generative EDA tool feature spec.md` | Code scored 2026-10-22 | Wide reading; Circuit OS scored from code and tests, not from ledgers | Medium-high. Its status column is the most recent code audit among the reports |
| R11 | `Where Circuit OS sits in the consulting reports.md` | 2026-10-17 | Consultancy reports, some read only in summary | Direction only. R11 itself says it says nothing about demand |

### 2.2 The secondary sources

The secondary material is:
- six competitor teardowns plus a matrix, dated 2026-10-21 (`reports/competitors/`);
- the code review of 2026-10-12, with 134 findings, 14 rated high;
- the ablation sketch of 2026-10-21.

The ground truth on what exists comes from:
- `state.json` (generated 2026-10-09 at commit `7584fba`);
- `brain/decisions.md` (entries to 2026-10-22);
- `plan/current_phase.md`;
- git history.

Trust order where sources disagree: tests and code, then `state.json`, then plans, then prose.

### 2.3 Two cautions about the record itself

**Branches.** The `alpha-program` branch of the main checkout (last commit 2026-10-23) holds work that `master` (369d94e, merged 2026-11-02) does not. That work is:
- the `.kicad_pcb` writer;
- KiCad DRC as a second engine;
- Gerber export that refuses a failed board;
- the Uno shield;
- component ablation;
- the seeded-board calibration gate.

Checked: `git merge-base --is-ancestor 8fd87b9 369d94e` returns false. "Exists" below means "exists on that branch" unless it says master.

**The derived counts are stale.** The derived numbers in `state.json` predate everything from 2026-10-17 onward, so they are quoted as a 2026-10-09 snapshot.

**The web re-check.** One claim was re-checked on the web on 2026-11-13: Quilter's changelog. It is labelled where it is used.

The companion product-by-product feature inventory now exists (2026-11-14): 26 product files in [`competitor-features/`](competitor-features/), merged in [`Competitor feature matrix.md`](<Competitor feature matrix.md>). Use it for feature-level detail. This report was written from the 2026-10-21 teardowns and corrected against the inventory where they disagree ([what changed](#what-the-november-competitor-pass-changed-2026-11-14)).

---

## 3. What exists in the world

### 3.1 Four things are called "validation", and only one is proof

R6 (§"The core confusion") separates four guarantees:

| Kind | What a pass means | Who has it |
|---|---|---|
| **Formal proof** | True for every value in a stated model | Circuit OS: z3 over tolerance boxes, at schematic level. No PCB vendor claims it |
| **Physics simulation** | A solver predicts this behaviour for this model | HyperLynx, Sigrity, SIwave, Keysight PIPro, Altium's analyzers, Quilter's impedance solver and DC IR beta, Flux's built-in ngspice and its claimed cloud EM/SI, PDN and thermal analysis (solvers unnamed; corrected 2026-11-14). Free: ngspice, openEMS, padne, PyPEEC, FasterCap, ThermalSim |
| **Rule check** | Geometry is inside a threshold someone chose | Every DRC and DFM tool, Quilter's eight PRCs, HyperLynx DRC, the SIwave EMI Scanner |
| **ML heuristic** | A learned policy produced this layout | Quilter's placer and router, Allegro X AI |

The earlier PCB reports collapsed physics simulation into "unknown". The owner's market page collapsed simulation and rule checks into "physics validation". R6 says both lose information.

**The products, and what each automates.** The sources are R6 §"What each commercial capability actually does", R10 §"AI tools split at the schematic", and the teardowns.

- **Quilter** places and routes a finished schematic with a learned policy.
  - It checks candidates with eight Physics Rule Checks: pin distance, path length, via count, ground overlap, width span, pair spacing, length mismatch, and overheated length from IPC-2221.
  - Its impedance geometry comes from the Simbeor 2D solver (since 2026-04-07). DC IR drop is in beta (since 2026-08-31), and Quilter calls it "not yet a full power-integrity sign-off".
  - It does no SI, AC power-delivery, EMC or board-thermal simulation. Its own docs say "Quilter is an implementer, not a proofreader".
  - Limits: 5,000 pins, 48 V, 10 A, under 6 GHz. Pricing is per pin and unpublished.
  - No public API was found. **Web re-check, 2026-11-13:** Quilter's changelog has no entry after 2026-09-30 and none mentions an API or headless submission. The changelog page does list a "Blind and Buried Vias" entry dated 2026-05-31; this weakens the "through-vias only" limit the teardown took from a snippet (title seen, entry not read in detail). **Corrected 2026-11-14:** the November pass read the entry. Blind and buried vias are "in active development", and the router still places through-vias only, so the limit stands ([quilter.md](competitor-features/quilter.md) D2, D8). It also confirms no API, CLI or scripting page (I2).
  - Enterprise posture: SOC 2 Type 2 (independent audit announced 2026-03-10), self-hosting on Kubernetes including air-gapped, and isolated AWS/GovCloud. No ITAR or FedRAMP certification is claimed (I3).
  - Real-hardware evidence (vendor-run): Project Speedrun. 843 parts, 98% routed, 27 h of runtime plus 38.5 h of human cleanup against 428 h quoted, booted Linux. The fab's own recalculation moved a 50 Ω target to 62 Ω (R6).
- **Flux** is a browser ECAD tool with an LLM agent, up to 8 layers (a 12-layer import was also shown).
  - ~~It has a beta ngspice simulator, prompt-driven since March 2026. Its impedance support is pre-route width rules only.~~
  - ~~Placement is manual. There is no post-route physics and no API (R6; Flux teardown).~~
  - **Corrected 2026-11-14** ([flux.md](competitor-features/flux.md)):
    - SPICE is built-in ngspice (operating point, AC, transient), and since 2026-11-08 it also runs on imported Altium/Cadence designs (C1).
    - It claims cloud full-wave EM/SI (S-parameters, TDR, crosstalk, eye diagrams), PDN impedance and IR drop, and board thermal estimates. The solvers are unnamed and no accuracy is stated (C4–C6).
    - The agent places parts (Partial) and routes on request (agentic routing, 2026-10-28) (D1, D2).
    - Firmware: it writes drivers and unit tests, and compiles for STM32, nRF, ESP32-class, RP2040, RISC-V and AVR (November 2026) (E1, E3).
    - It claims fab ordering: quotes, then "places the order when you confirm" (H6).
    - It has a public MCP server; no REST API or CLI is documented (I2).
- **Altium** ships a built-in SI simulator, a Simbeor-based impedance solver and SPICE3f5-compatible mixed simulation.
  - Paid add-ons: Keysight SI (Open Beta) and a Power Analyzer that is DC only. EMI is third-party. (2026-11-14: [altium.md](competitor-features/altium.md) reads the Signal Analyzer by Keysight as a paid add-on with a 14-day trial and does not call it a beta.)
  - Since 2026-10-14 its Requirements Portal has an AI assistant that proposes requirement edits for a person to approve. Requirements are traced to the design, but they do not generate or check it (A1, A5).
  - Its ERC has no voltage or current awareness, and it has no CI path for DRC, SI or PI (R6).
- **Sign-off stacks** are all quote-only, in the tens of thousands of dollars (R6):
  - Siemens HyperLynx PI and HyperLynx DRC (90+ rules);
  - Cadence Sigrity PowerSI, OptimizePI, PowerDC, Celsius and Clarity;
  - Ansys SIwave with Icepak;
  - Keysight PIPro and SIPro.
- **Schematic-side checkers:**
  - Siemens Xpedition Schematic Analysis (ex-Valydate, 150+ voltage-aware rules);
  - Cadence PSpice "Smoke" stress simulation;
  - Cadstrom (voltage compatibility, ratings; "AI plus deterministic checks", no public technical docs);
  - Circuit Mind (stress, derating, FMECA reports);
  - added 2026-11-14, all datasheet-grounded AI review, none publishing precision or recall: Circuit Mind AVE (launched 2026-10-28), AllSpice DRCY, Traceformer ($20/month), NextPCB Design Validator ($9.90/month) and CADY (sold through Altair) ([_group-d.md](competitor-features/_group-d.md)).

  These weaken any "only you" claim on voltage and current checks (R6).
- **JITX** is the only AI-PCB tool found with a full 3D solver (Ansys HFSS) in the loop (R6). (Narrowed 2026-11-14: the only one with a *named* full-wave solver. Flux now claims full-wave EM without naming its solver.)
- **Celus, DeepPCB, Diode and SnapMagic** do no post-layout physics (R6).
- **Free KiCad 10** emits Gerber X2, ODB++, IPC-2581, IPC-D-356 and STEP from a headless CLI, and runs DRC with JSON output (R10; run in R4 and R5). Mainstream tools share deep table stakes and sell analysis, DFM and collaboration as add-ons (R10).

**Evidence of what AI can do is thin and mostly vendor-run** (R10):
- On HWE-Bench's 300 board-level tasks, the best model was fully correct 8.15% of the time.
- A schema-constrained model judged by a deterministic verifier passed 81.3% of a different suite.
- The suites are not comparable. Both show that a deterministic checker catches most model errors.
- Added 2026-11-14 ([general-llm-assistants.md](competitor-features/general-llm-assistants.md)); all are author-run:
  - **NetlistBench** (2,342 SPICE-netlist cases): local edits 96–100%, device addition 41–83%, equivalence judgement 49–90%. Accuracy falls sharply as edit sequences lengthen.
  - **Long-Horizon Analog Design Bench** (50 transistor-level tasks): full-spec pass 8.0–78.0%. Most failures are legal designs that fail electrical acceptance.
  - **Qiao & Dick** (v2, 2026-10-27): 97.5% on interface-compatibility checks across 7 designs and 34 datasheets. The LLM extracts the facts and generated deterministic scripts do the arithmetic.
  - **Diode × Anthropic**: engineers preferred Sonnet 4.5's reference designs 8 times in 10; test-set size not stated.
  - **E-Sharp** (2026-11-10, vendor author): on one commercial board, AI review gave 16 rule hits, 6 relevant, 4 genuine defects.
  - atopile's **EEBench** (Claude Opus 5 at 61.6%) is known only from a summary.

  Each one that pairs a model with a deterministic step scores higher. That is Circuit OS's architecture.

### 3.2 The techniques, and what each can deliver

**Formal verification of analog circuits** (R1). Some questions are provably impossible:
- reachability for linear and non-initialised hybrid automata, which covers switched-mode supplies;
- sign conditions on expressions mixing exp and sin (Richardson's theorem);
- sound worst-case bounds under Gaussian noise.

Polynomial real arithmetic is decidable but doubly exponential, and stability of cubic ODEs is strongly NP-hard. More compute does not move these walls; restricting the question does.

The trust ladder runs: theorem prover, then exact decision (z3 nlsat, Routh-Hurwitz, Kharitonov), then sound enclosure, then SOS (sound only after exact re-check), then bounded model checking, then STL monitoring, then falsification.

Circuit OS's catalogue sits in decidable territory: dividers, RC filters, LED current, and DC sensor checks. Linear op-amp stages stay cheap. Saturation, comparators and switching supplies are research projects. Every published sound analog result covers 2 to 5 continuous states.

**SPICE.** ngspice is mature and BSD-licensed. Circuit OS's netlist generator agrees with closed-form equations to 0.0003% (`ROADMAP.md` §3, criterion 11, met by substitute). Flux, Altium and KiCad all embed SPICE, so SPICE is not a differentiator (R6, market-page corrections). The November pass widens the list: Siemens, Cadence/OrCAD PSpice, Fusion, EasyEDA, ProtoFlow and tscircuit also have it, ten products plus general LLMs driving ngspice through tools ([matrix row C1](<Competitor feature matrix.md#c-simulation-and-analysis>)).

**Layout physics** (R6 §"What Circuit OS can build"; R10 §1):
- **SI.** Simulate a line longer than about one-sixth of the rise time. On a 68 × 53 mm Uno shield, slow buses are electrically short.
- **PI.** On two layers the decoupling capacitor's own loop is the whole power-delivery network: a mount drops from about 1.1 nH to 0.7 nH by moving its vias together. Placement therefore decides PI (R2 V.3; R10).
- **Thermal.** IPC-2221 is a conservative empirical formula; IPC-2152 charts are copyrighted.
- **EMC.** Every tool does rule scans plus an optional full-wave solve that an engineer compares by hand. Board-level prediction carries order-10 dB uncertainty.

Free tools exist for every branch: KiCad ThermalSim, padne, PyPEEC, FasterCap, gerber2ems/openEMS and KiCad-Parasitics. None publishes an error against measurement on FR-4, except the KiCad Fill Resistance plugin (within 20% of a micro-ohm meter) (R6 §"What nobody can claim").

**DRC, LVS and DFM.**
- Every DFM tool examined is a geometric check against a capability table (R6).
- Fab limits for two-layer, 1 oz boards cluster at 0.10–0.15 mm track and space (R3, confirmed in R4). R5 derives a portable profile of 0.20 mm track and space, 0.40 mm via drill and 0.40 mm copper-to-edge.
- No fab offers a documented, licensed DFM API. NextPCB has an undocumented HTTP endpoint, Aisler a CLI that uploads only, and Boardera an API known from trade press (R6, correcting R3, R2 and R5).
- No open-source Gerber-to-netlist comparison existed until R5 prototyped one: 130 lines, run, 4 of 4 seeded defects caught, including a moved drill hit that KiCad DRC cannot see.

**Routing validation** (R3, R4, R7). Check the output, not the router:
- an independent connectivity judge;
- a valid geometric floor (straight-line distance, or max(span, ⅔·rectilinear MST); never the MST itself);
- net-order sweeps and isolation oracles;
- metamorphic relations;
- seeded violations;
- Freerouting on the identical placement.

The honest unit is boards, not nets. Freerouting reached 80% clean pass on 99 small real boards (R3, citing PCBWorld).

### 3.3 Every commercial stack stops at a model, and says so

No vendor claims proof. (2026-11-14: Circuit Mind markets "provable accuracy" but publishes no method, and the paper it cites was not found ([circuit-mind.md](competitor-features/circuit-mind.md)). Until a method appears, this sentence stands.) The strongest stated guarantee is vendor-published correlation to lab measurement on specific fixtures, for example Clarity to 50 GHz on one IEEE P370 fixture. No published percent-error figure was found for DC IR drop or PDN impedance against measurement (R6 §"The sign-off stacks").

Every vendor disclaims liability. Traceformer's terms cap it at twelve months' fees or US$100 (R9 §"Liability"). The industry sells geometry checks and physics simulation as separate products (R2 Part 3, as corrected by R6).

### 3.4 What software cannot settle at all

R6 (§"What nobody can claim") and R5 (§"What each branch reaches") agree on this list:
- **That a board works.** Every result is about a model.
- **EMC compliance.** Only a chamber settles it.
- **The accuracy of free tools against measurement.** It is unpublished.
- **Pin-map correctness from physics.** A wrong pinout passes every simulator, DRC, read-back, optical inspection and flying probe. Only an independent pin source or a powered test catches it. R6 calls this "still the most likely way for one of our boards to fail".
- **The fab's real limits and silent CAM edits; reflow behaviour; tape rotation per part.**
- **The model-versus-hardware gap.** Only a bench closes it.

The undecidability results of R1 apply only once switching or modes enter the catalogue.

### 3.5 What the money looks like

**Hobbyists.** They pay €5.6–8.1 a month (Wokwi) or $6.99 (Arduino Cloud). Flux's individual tier is $40 a month annually or $50 monthly. That proves the price is asked, not that individuals pay it (R9 §"three negative findings"). (2026-11-14: Flux removed its Explore tier on 2026-11-01. Its official page showed plans with blank dollar fields. A tracker captured 2026-11-09 gives Build $80 and Pro $200 a month, and also $100 for Build, a conflict it does not explain. Teams is $500 for 5 seats from 2026-10-26 (tracker). Whether Explore was R9's $40 tier is not stated ([flux.md](competitor-features/flux.md) I4). New consumer price points: ProtoFlow $0/19.99/39.99, Trace $29.99, Traceformer $20, EasyEDA Pro free with premium at $19.9, Wokwi €0–20.)

**Retention.** For AI-native products under $50 a month, gross revenue retention is 23%, against 70% above $250 (ChartMogul, primary, R9).

**Rivals meter.** Every funded rival meters AI work:
- Flux in compute units;
- Traceformer with prepaid credits;
- Quilter per pin;
- DeepPCB per minute (R9). (Corrected 2026-11-14: per hour, $30 for 1 hour, $280 for 10 and $800 for 30, read 2026-11-13 ([deeppcb.md](competitor-features/deeppcb.md) I4).)
- Added 2026-11-14: CELUS sells AI Credits in-app (amounts not stated); ProtoFlow, Trace and Traceformer meter by messages, requests or credits.

**Verification.** At least ten automated review offerings exist, and none publishes revenue, a customer count, churn or a paying-user review. The only visible purchases are human reviews on Fiverr at roughly $50–600 (R9 §"Ten review vendors"). AllSpice starts at $34,800 a year for five or more designers; its $15M Series A followed a collaboration product, not standalone review (R9). (2026-11-14: AllSpice's site now shows only enterprise plans, demo required, priced by team size and "AI review credits", with no figures; the $34,800 cannot be re-read there ([allspice.md](competitor-features/allspice.md) I4). Traceformer at $20 a month and NextPCB at $9.90 a month now publish self-serve review prices, still with no customer counts.)

**Per-board design.**
- Automated steps are priced at $1–250.
- Human-backed designs start at $10,000 (Diode).
- Fiverr's average PCB job is $157 and 22 days.
- Indian list prices are ₹5,000–10,000 a board.
- Nothing was found publicly priced between about $300 and $3,000 for a complete automated small board (R9 §"Per-board money").

**Free substitutes.** Chip vendors give away simulated small circuits and reference designs: TI WEBENCH, ADI Precision Studio, TI RS-485 and 4–20 mA designs (R8, R9).

**Market size.** PCB and MCM tool revenue was $484.6M in Q4 2025 and $419.2M in Q1 2026 (SEMI, R9).

**Consultancy framing** (R11). McKinsey and BCG say generative AI has worked in software and stalled in hardware, and both split generation from evaluation. The Global Electronics Association lists validation as an open challenge. These describe direction, not demand.

---

## 4. What Circuit OS has, checked against the code record

Grades: **Real** means code with passing tests. **Unverified** means built but not checked against reality or not reachable by users. **Roadmap** means not in code.

### 4.1 The front half: intent, circuit, proof, firmware

| Capability | Grade | Source |
|---|---|---|
| Requirement as a typed, hashed IntentIR before any design. LLM through `tool_use` or a form with zero model calls. Retries may add, never rewrite | Real | R10 A1; `.claude/rules/code-style.md` (X5, 2026-09-21) |
| Refusal of under-specified or out-of-catalogue requests, naming the missing fields; 200-case labelled corpus | Real | R10 A2 |
| Requirement patches (RFC 6902) citing the user's words, 409 on a lost race, sign-off bound to the properties hash | Real, with a defect: the code review found unit grounding broken ("15 mA" accepted as 0.015); fix unconfirmed | R10 A3; code review area 6 |
| Six generators on one contract: RC low-pass, divider, LED, DHT22 node, RS-485 node, load switch. `predict()` within 2% of ngspice across CI grids | Real | R10 A10; `decisions.md` [2026-10-03] M3 |
| Composition: blocks on one board, behaviour rules, one sketch. The room-monitor sentence produces a board on Uno, ESP32 and Black Pill | Real in code. Shown live on 2026-10-04. Not built on a bench | `current_phase.md` (Composition) |
| Proofs: sympy nodal analysis plus z3 over tolerance boxes; 64 of 64 mutants caught. z3 is trusted without an independent checker | Real. 12 proven properties, unsigned. Signing lifts the library floor to G1 | R10 A11; `decisions.md` [2026-10-02] |
| Graded claims G0–G7, defeaters D1–D9, "not assessed" rows | Real | R10 A12; `state.json` `validation` |
| Pin rules (mux, peripheral conflicts, strapping) | Real, 56 labelled cases | R10 A7 |
| Component ablation: 43 faults, 10 gaps found, 6 closed, 4 pinned | Real (`alpha-program`) | R10 A15; `ablation-sketch-2026-10-21.md` |
| Firmware from templates, compiled under PlatformIO before display; 21 of 21 variants on three boards | Real. The real-worker path first worked on 2026-10-04. No board flashed with this firmware | R10 A16–A17; `decisions.md` [2026-10-04] |
| Build check (which listed wiring fault a multimeter reading implies) | Real against ngspice: none of 2,400 simulated correct boards charged to D1. Unverified on hardware | `decisions.md` [2026-10-08] |
| Real-data check: 11 published circuits, ngspice as judge | Real (simulated) | `current_phase.md` [2026-10-08] |
| BOM: static dated prices, live Mouser optional, passive substitutes re-proved | Real. Two LCSC codes each map to two parts (code review area 12) | R10 A9, C11 |
| Explanation: queued out of the request, read back | Real. Generate ~10 s, explanation ~80 s | `decisions.md` [2026-10-05] |

**Derived snapshot.** `state.json`, generated 2026-10-09 at `7584fba`:
- 2,625 tests passed, 0 failed, 32 skipped;
- Phase 2 gates 27 of 29 met, 2 deferred;
- Phase 1 at 11 of 12 criteria, with criterion 11 met by substitute and criterion 12 (external engineer read) deferred.

These predate everything since 2026-10-17.

### 4.2 The open defeaters

From `state.json` → `validation.open_defeaters` (2026-10-09):

- **D1, no bench measurement.** Open on all six generators. `docs/BENCH_D1.md` is ready; the session has not been run (`current_phase.md`).
- **D2, the MCU model.** Open on DHT22, LED, load switch and RS-485. The MCU is modelled as a resistor (100 Ω on the Uno, per part since Stage 5), and claims that depend on it name it.
- **D7, unverified datasheet figures.** Open on the same four. Specifically:
  - the Black Pill board rows (WeAct documents not read);
  - the ATmega/Uno supply figure;
  - the LED's assumed V_F minimum of 1.6 V;
  - the transistor's nine figures, which are "recalled, not read" because the onsemi datasheet could not be fetched (`decisions.md` [2026-10-02], [2026-10-03] M3).

A board passing every check today is, honestly worded, "exact on a model nobody has measured" (R5 §"The plan rests on three borrowed ideas", "model validity").

### 4.3 The board half: what "experimental" means

"Experimental" here means three things (`decisions.md` [2026-08-22], [2026-10-06]; `MENTAL_MODEL.md` §4):
- it sits behind `pcb_engine_enabled`, labelled in the UI;
- it is off in production, where `POST /pcb/compile` returns 501;
- its router is "not production routing", and Freerouting remains the plan.

| Capability | Grade | Source |
|---|---|---|
| Greedy placement and A* router: 2 layers, ≤ 40 parts. Room monitor 6 of 14 connections; DHT22 relay board 12 of 12 | Unverified as quality. R7's four executed defects are fixed and pinned as tests | R6 code table; `current_phase.md` B1; R7 status note |
| Independent verifier with rungs (exact, sound, bounded, evidence, unknown): connectivity, shorts, netless pads, pin collisions, courtyards, pad symmetry, plane-net reachability (III.1c exact, III.1d sound), keepouts (II.4) | Real | `decisions.md` [2026-10-09], [2026-10-17], [2026-10-22] |
| Pinouts by orderable part number from the KiCad symbol library (IV.2, rung evidence/T1); free-pad guessing removed; diode pad 1 = cathode | Real. Modules and relays (DHT22, SRD relay) have no library symbol | `decisions.md` [2026-10-17] |
| Land patterns: 31 entries, **none verified**; ESP32 module and Black Pill UFQFPN-48 have no footprint, so U1 is dropped | Unverified | R10 A8, B1 |
| `.kicad_pcb` writer, KiCad 10.0.1 DRC as second engine with sentinel and policy table, Gerber/drill/pos/IPC-D-356 export refused for a failed board | Real on `alpha-program` (commits 8d63e3b, 283bed8, 5c3a2fc, 2026-10-21). **Not on master; not wired to API or UI.** All eight board-level KiCad minimums are exported as 0 | git log; R10 C1, C9 |
| Gerber read-back (R5 stage 7) | Roadmap. Gerbonara approved 2026-10-17; nothing imports it | `decisions.md` [2026-10-17]; R10 C13 |
| Uno designs compile to an Uno R3 shield; the BOM orders the Uno (mating) and the header kit | Real on `alpha-program`. The schematic still draws "U1: ATmega328P-PU" | `decisions.md` [2026-10-22] |
| Net meaning on the board (voltage, current, role) | Roadmap. `NetClass` holds width, clearance and vias only | R10 B2 |
| Layout physics (impedance, IR drop, trace current, thermal) | Roadmap. The "score" is a weighted count with no physical quantity, though `progress.yaml` calls it a "Physics scorecard" | R6 code table |
| Stackup | Fields unread. The default dielectric of 0.48 mm contradicts the 1.6 mm board drawn in 3D | R6 code table |
| Fab profile, fab notes, silkscreen, revision stamp, mounting holes | Roadmap | R10 C1, C2, C10, C12, B14 |
| Version history | Requirement-level audit trail only: no rollback, no board diff, no UI, Board IR never stored | R6 code table; R10 D7 |
| 3D board view | Real (package-shaped bodies, flagged `generic` where no model) | `decisions.md` [2026-10-06] |
| Seeded-board calibration: 7 defective boards; the review agent ("overlooker") detected 7 of 7 with 0 false passes | Real on `alpha-program` (582771b). It measures the reviewing agent, not the product | git log 582771b |

**The product's own verifier fails the mains case.** In that calibration set the mains trace sits 0.35 mm from a logic net. The verifier returns `ok=True`, the kernel DRC reports zero violations, and KiCad DRC reports the same findings as on the clean board (582771b commit message; findings F-0004 and F-0024 open).

### 4.4 Known defects that bear on trust

The code review of 2026-10-12 named three "fix first" items:
- an ngspice crash or timeout recorded as a successful simulation;
- the simulation poll overwriting a concurrent patch;
- requirement text reaching the `.ino` unescaped.

No commit since 2026-10-12 touches `backend/tasks/simulation_task.py` or `simulate.py` except a rate-limit change (git log, all branches). On `alpha-program`, `simulation_task.py` still records `success=True` without checking ngspice's return code (read at lines 40–51; not run). Inference: the first item is still open, and the other two are not confirmed fixed.

### 4.5 Three documents the owner reads first are out of date

`ROADMAP.md` and `MENTAL_MODEL.md` are dated 2026-08-22.

- **MENTAL_MODEL.md.** Its competitor table marks Flux "SPICE ❌ roadmap" and calls industrial rules "untouched ground". R6 corrects the first and R8/R9 the second.
- **ROADMAP.md.** It places Gerber in Phase 4. The owner moved minimal Gerber forward on 2026-10-17.
- **The market page** (`Downloads/market_comparison_2026.html`) has more problems:
  - it still says "Simulation-driven auto-correction: swaps components when sim fails — Only you". That describes the LLM-to-CircuitIR retry path deleted on 2026-09-21 (`code-style.md`, "Amended 2026-09-21");
  - it lists "Confidence scores per decision — Only you", which none of the reports finds in code; (corrected 2026-11-14: `Component.confidence` is a 0–1 field in `ir_schema.py`, printed by the explainer, but each generator sets it as a hand-written constant such as 0.97 or 0.9. It exists; it is not a computed score);
  - it lists live Digikey/LCSC pricing, while the code has Mouser only;
  - added 2026-11-14: it marks "Only you" on 4–20 mA / 24 VDC, HVAC boards, safety-certification flagging, cellular RTU/SCADA and an ROI dashboard. None has code: HVAC is an enum value (`HVAC_CONTROL`) and the SIM7070G modem a data entry. Gerber is on a branch, and MQTT/AT firmware, DFM, private libraries and version diff do not exist. All 27 rows are corrected in [matrix §5](<Competitor feature matrix.md#5-the-owners-market-page-corrected>).
- **A fourth, added 2026-11-14: `vision.md`.** Its competitor row ("ChatGPT/Claude: hallucinates circuit values, no simulation, no files, no validation") is out of date. General LLMs now drive KiCad, Freerouting, EasyEDA and Wokwi through MCP servers and skills ([general-llm-assistants.md](competitor-features/general-llm-assistants.md)). The benchmarks in §3.1 are the honest answer to them.

---

## 5. Ledger of the reports' conclusions

Status: **Stands**; **Corrected** (by which report, how); **Contradicted**; **Overtaken** (by a decision); **Untested**.

| Report | Conclusion | Status on 2026-11-13 |
|---|---|---|
| R1 | Catalogue circuits are decidable; exact proofs over tolerance with sympy and z3 take days | **Overtaken by building it**: Stage 4 prover, 64/64 mutants (R10 A11) |
| R1 | Freeze the property after sign-off; refinement may change the abstraction, never the property; mutation-test every proof | **Stands**, adopted (Stage 4, "frozen refine loop") |
| R1 | No LLM analog-design agent uses a formal engine; claim "first integration", not a new method | **Stands, untested since** (search-based). R10 adds that no product claims proofs |
| R1 | Switching supplies are research-grade (undecidable in general) | **Stands**. Power electronics stays out of scope (`.claude/CLAUDE.md`) |
| R2 | Seven-branch tree with rungs; III exact, IV needs external truth | **Stands**, built as `verify.py` |
| R2 | "Unknown = no software check exists"; thermal, AC PI and placement unreachable; HyperLynx "the one stack" with electrical sign-off | **Corrected by R6**: split *unknown* into three; thermal, AC PI and placement checks exist; Cadence, Ansys, Keysight and Altium also sell electrical analysis |
| R2 | The layer refuses a board that fails an exact check | **Overtaken** by the owner on 2026-10-17: show the board, refuse its fab files |
| R2 | Back-annotate with PyPEEC plus a capacitance extractor | **Corrected by R5** ("not now", closed-form intervals); PyPEEC still an open owner decision |
| R2, R3 | No free Gerber-to-netlist extractor; no fab CI/API DFM | First half **overtaken** (R5 prototyped one). Second **corrected by R6** ("out of date as written"; still no documented licensed gate) |
| R3 | Trace parasitics sit "three or more orders" below tolerance | **Corrected by R4**: 1.6–3.5 orders, RS-485 120 Ω tightest. Conclusion unchanged |
| R3 | MST and 1-Steiner are lower bounds | **Corrected by R4** (only HPWL and RSMT are floors); executed in R7 (quoted floor overstated by 46%) |
| R3 | Completion, not wirelength, is the router's problem | **Stands**; R7 measured the shipped board at 1.6% above rectilinear MST |
| R3 | A fabricated board says little about routing on slow circuits without reference and control boards | **Stands**; carried into R5's coupon |
| R3 | Run KiCad DRC as a second judge | **Built** on `alpha-program`; not on master |
| R4, R7 | `Board.unrouted()` wrong (cell test); shipped board read 8/12 when it was 12/12; DRC broad phase missed violations; DSN carried no vias | **Fixed in code 2026-10-17**, pinned as tests (R7 status note) |
| R7 | All failed connections are congestion and ordering, not modelling (0 of 5) | **Stands** for the demo board |
| R7 | The KiCad arm is gated behind a `.kicad_pcb` writer that does not exist | **Overtaken**: writer built 2026-10-21 on `alpha-program` |
| R5 | Pinouts from the part number, never the package; diode pad 1 = cathode; unknown pinout blocks export | **Adopted** 2026-10-17 |
| R5 | Gerber via `kicad-cli`, own writer, KiCad as second engine; Gerbonara for read-back in Python 3.12 | **Adopted** 2026-10-17; writer and export built; read-back **not built** |
| R5 | "No field solver is needed" (Stage 8); a solver float cannot be a proof premise | **Corrected by R6**: true "for this board class"; the closed-form margin is equally an assumption |
| R5 | `kicad-parasitics` could not be found | **Contradicted by R6** (it exists, GPL-3.0) |
| R5 | Mains: refuse below 2.5 mm, warn below 5.0 mm | **Contradicted in substance** by R6 (mains-to-SELV needs reinforced, about 5 mm; 2.5 mm is basic only). F-0004 open; standards unread by anyone |
| R5 | One five-board coupon order after stage 7; predictions committed first | **Untested**; stage 7 not built |
| R6 | Add the *simulated* rung; split *unknown*; fix `verify.py` V text and the `progress.yaml` label | **Untested** (no decision or commit found) |
| R6 | Corrections to the market page (Quilter overstated; Altium, Flux SPICE, Flux layers understated; "Only you" wrong on validation rows) | **Stands, extended** 2026-11-14 by the matrix: 10 of 13 "Only you" cells false; Flux simulation, firmware and physics now understated further; page not updated |
| R6 | Build list 0–12: stackup, PRCs, layout V/I, DC IR, AC PDN, ThermalSim, parasitics, SI lane, EMC screen, history, ODB++, coupons | **Untested**; none in code |
| R6 | `PCB_STRATEGY.md`'s "Quilter a full generation past us; intent never reached it" is overstated | **Stands**; Quilter detects constraints from names and topology, and Circuit OS's edge narrows to constraints from proven quantities |
| R8 | Hobbyists won't pay $49; every rival meters; industrial "unadvertised, not uncontested"; India is users, not first revenue | **Stands**, confirmed by R9 with nine figures corrected |
| R8 | First customer: small teams and design houses buying verification over imported KiCad designs | **Retracted by R9** (catalogue covers 8.4% of real sub-circuits; no evidence anyone pays for automated review) |
| R8 | Flux $20–40, OpenView "5% median in six months", Quilter free tier "non-commercial", DeepPCB "$1 per credit", Altium seat prices | **Corrected by R9** (Flux $40/$80/$200 annual; OpenView no median or window; Quilter <10 people and <$50K revenue; DeepPCB implied only; Altium unverified). 2026-11-14: Flux's Explore tier removed 2026-11-01, page figures blank, tracker Build $80 or $100; DeepPCB now read at $30/hour |
| R9 | The most likely payer is a buyer of a finished small board on a supported module who cannot review it; per design | **Untested inference** |
| R9 | Six ordered tests with stop rules; stop after about 90 days and 70 asks with no paying stranger | **Untested**; test 1 not run |
| R10 | 58 features: 10 have, 24 partial, 24 missing; 16 P0 in five work packages (part truth, net meaning, fab target, board context and safety, release package) | **Stands**; partly advanced (shield B1 for Uno) |
| R10 | Physical evidence is the one rung nobody in the market has reached | **Stands for boards**; Circuit OS has not reached it either. Narrowed 2026-11-14: Embedder builds, flashes and tests *firmware* on real hardware ([embedder.md](competitor-features/embedder.md) E3), so the unclaimed rung is a measured *board* |
| R11 | "Verification-first compiler for the long tail of low-volume electronics" | **Stands as framing only**; R11 itself defers demand to R9 |
| `MENTAL_MODEL.md` §9 | Flux has no SPICE; industrial is "untouched ground, nobody standing there" | **Contradicted** (R6; R8, R9) |
| `PCB_STRATEGY.md` | The constraint layer, not the router, is the bet | **Stands**, sharpened by R6/R10: constraints from proven currents and voltages |

---

## 6. Where the reports disagree, and which side the evidence favours

1. **Who pays: teams buying checking (R8), or buyers of finished boards (R9)?** R9 is later and better sourced. It read the threads and price pages R8 summarised, and it measured catalogue coverage on real boards. **R9 wins.** Neither is demand data; no one has been asked to pay.

2. **The industrial vertical.** Three positions:
   - `MENTAL_MODEL.md`, `ROADMAP.md` §6 and the market page call it the biggest moat, with zero competitors;
   - R8 and R9 call it unadvertised, served free by TI and Microchip reference designs, certification-bound, and with no data on how OEMs buy;
   - R11's McKinsey long-tail thesis supports low-volume markets in general.

   **R8/R9 win on the facts.** R11 supports direction, not this segment.

3. **Field solvers and parasitics.**
   - R2 planned PyPEEC plus capacitance extraction.
   - R5 says not now: parasitics are negligible on this board class.
   - R3 and R4 give the arithmetic: 1.6–3.5 orders below tolerance.
   - R6 adds DC IR drop, AC PDN and thermal as market-parity items, not as back-annotation.

   These answer different questions. **For proving today's catalogue, R5 wins.** For matching Quilter's and Altium's offer, R6's items 4–5 are the route, and only once the board carries net meaning.

4. **"Unknown" versus "not run".** R2 and R5 treat AC PI, thermal and EMC as unknown in software. R6 shows they are computable but unproven. **R6 wins**; the proof caveats in R2 still stand.

5. **Mains clearance.** R5 says refuse below 2.5 mm. R6 says reinforced insulation of about 5 mm or more is needed at 250 V between mains and SELV, and that 2.5 mm is basic only. R10 cites 2.5 mm basic from a secondary source. **R6's direction is safer.** All figures are secondary, and no report read IEC 62368-1 or 60664-1; R10 itself says they must be checked against the standard before anything ships. Meanwhile the product passes a 0.35 mm mains gap (582771b).

6. **Is the ground plane real copper?**
   - R6 (2026-10-16) says it is "never realised as copper".
   - R10 (2026-10-22) says plane zones, stitching vias and a sound pour-continuity check exist.
   - `decisions.md` [2026-10-17] records III.1c/III.1d.

   The later source is likely right for the pour as checked geometry. Whether any physics model reads it is a separate question, and the answer there is no. Inference; re-read `router.py` before acting.

7. **Respin cost.** R8 quotes 2.9 respins and $82,000 overrun (an old Mentor release; study not located). R10 quotes $28,000–46,000 per respin at 2.9 respins, tracing all of them to one Lifecycle Insights study from about 2018. **Treat all as one vendor-cited study.** R8 itself warns these describe complex boards beyond the catalogue.

8. **Flux prices.**
   - R8: conflicting third-party figures.
   - The Flux teardown (2026-10-21): a snippet of $20 / $142 / $158, marked unverified.
   - R9: read the pricing page, $40 / $80 / $200 annual and $50 / $100 / $250 monthly, Teams $120 / $158.

   **R9 is the best-sourced.** (2026-11-14: R9's figures can no longer be re-read. Flux's page now shows its plans without dollar figures, and the Explore tier was removed on 2026-11-01. A tracker captured 2026-11-09 gives Build $80 a month in one place and $100 in another, and Pro $200 ([flux.md](competitor-features/flux.md) I4). R9 stands as a dated reading; the current price is unsettled.)

9. **Quilter's free tier and limits.**
   - R6 says "non-commercial"; R9 read the primary terms: under 10 people and under $50K revenue, trains on uploads.
   - R6 marked "through-vias only" unverified; the teardown had it as "in development" from a snippet; the 2026-11-13 web check found a "Blind and Buried Vias" changelog entry dated 2026-05-31.

   **Primary reads win; the via limit is probably out of date.** (Reversed 2026-11-14: the November pass read the entry itself. Blind and buried vias are "in active development", and the router still places through-vias only, so the limit stands ([quilter.md](competitor-features/quilter.md) D2, D8). The free-tier finding is unchanged.)

10. **Who scores placement.** R2 says no tool does. R6 says Quilter applies pass/fail placement rule checks, but no tool produces a continuous physics-based score. **R6 wins.**

---

## 7. Where to move forward

The directions are ranked by evidence per unit of cost. Each reuses what exists. The ranking is this report's inference from the reports.

### 7.1 Ask current users to pay, this week

- **Opportunity.** Learn in days whether anyone pays for today's output, before building anything for an imagined buyer.
- **Evidence.** R9 test 1 is the cheapest test, and it has not been run. No report knows how many people use the deployed product (R9 §"An ordered set of tests"). R9 also finds that the visible money is per design, not per seat.
- **Builds on.** The deployed site, the export of schematic, firmware and BOM, and the stored designs in PostgreSQL that list who generated what.
- **Smallest step and cost.** One to two days and a payment account (R9):
  - look up active users for the last 60 days;
  - put a per-design payment link in front of the next export;
  - write personally to everyone who generated a design.

  If there are fewer than 30 active users, record "no audience" and go to 7.2.
- **Who would pay.** Unknown. That is the point of the test.
- **What would prove it wrong.** R9's rule: 0 of 30 pay $5 or more. Then do not tune the price; move on.

### 7.2 Build one Circuit OS board, measure it, and offer it per design

- **Opportunity.** One fabricated, flashed, measured board does five things:
  - closes D1;
  - tests the export chain where real bugs live;
  - gives the only physical-evidence rung in this market;
  - provides the R5 coupon;
  - becomes the product for R9 test 2.
- **Evidence.**
  - R10 conclusion: physical evidence "cannot be copied as quickly".
  - R5: one five-board coupon order turns "model not validated" into per-quantity measurement.
  - R3: include a reference board and a bad control, or the board says nothing about routing.
  - R9 test 2: build two or three variants, then offer at $150–500 per design.
  - R9: a guarantee becomes affordable only on variants the founder has built and measured.
  - Added 2026-11-14: Embedder already builds, flashes and tests *firmware* on real hardware ([embedder.md](competitor-features/embedder.md) E3), so the claim "the only physical evidence in this market" is narrowed to a board measured against committed predictions (inference; Quilter's vendor-run Speedrun shows a board that booted, not one measured against predictions).
- **Builds on.**
  - the room-monitor composition and the Uno shield (`alpha-program`);
  - the build check and its bench sheets (`docs/BUILD_CHECK_SHEETS.md`);
  - `docs/BENCH_D1.md` and the `rc_timer` sketch;
  - Gerber export with refusal;
  - the compile gate.
- **Smallest step and cost.**
  - First, the bench session on a breadboard (owner only, hours, parts on hand).
  - Second, the paper fit of every footprint (free, R5 Stage 0).
  - Third, one five-board order with a coupon strip, after read-back works. About INR 750–1,200 in fabrication per R3, before duty; Lion Circuits from ₹799 for five per R9. Plus a multimeter and a home-made 4-wire adapter. Three to five weeks.
  - Commit predictions before ordering.
- **Who would pay.** Per R9, software and IoT teams without an electrical engineer, and Fiverr buyers, at freelancer prices. This is inference.
- **What would prove it wrong.**
  - Measured quantities fall outside the predicted bands. That is a model finding, still valuable.
  - Fewer than 2 orders in 60 days.
  - Orders arrive only when the founder does custom work. R9 says to log it as consulting, not product revenue.

### 7.3 Give the board its part truth and its net meaning

- **Opportunity.** Two checks nobody in the competitor set does: creepage derived from working voltage and insulation class, and trace width checked against currents the proofs already computed (competitor matrix, 2026-10-21). They also close the failure mode most likely to kill a Circuit OS board, a wrong pinout. **Reasoning revised 2026-11-14; the recommendation stands.** "Nobody does" is no longer true as written:
  - Siemens now validates creepage in the Xpedition layout editor and HyperLynx DRC; how it derives the distance is not stated ([siemens-xpedition-pads.md](competitor-features/siemens-xpedition-pads.md) C8).
  - Flux, Altium and KiCad check creepage distances that the user types in. Flux's worked example cites IEC 62368-1.
  - Quilter sizes power-net widths by IPC-2221 from currents the user sets (C6).

  What stays unclaimed is deriving both from quantities the design has *proved*: working voltage from the net, current from the z3 bounds. The case for doing it is unchanged: it is Circuit OS's own failure (582771b), and it is P0 in R10.
- **Evidence.**
  - R10's P0 work packages 1 and 2 (A7, A8, B2, B3, B7, B8, D3).
  - R5 stage 1 and its T/G trust ladders.
  - R6 build items 2–3.
  - R6 §"What nobody can claim": pin-map errors are the likeliest failure.
  - `PCB_STRATEGY.md` §3: the IR already knows signal types (`rs485_a`/`rs485_b`) that the placer ignores.
  - The 582771b result: the product cannot see a 0.35 mm mains gap because no net carries a voltage (F-0024).
- **Builds on.**
  - `part_pinouts.py` (KiCad library by part number);
  - `land_patterns.json` (registry, all unverified);
  - the D7 provenance machinery (`data/figures.py`);
  - the z3 currents;
  - `verify.py` rungs;
  - the `DiffPair` type, which is never filled from RS-485 A/B (R10 B4).
- **Smallest step and cost.** About two to four weeks of agent work in total (inference from R6 item sizes of 2–5 days each):
  1. Move every `land_patterns.json` entry to G1 mechanically against KiCad footprints (R5).
  2. Add hand-written, page-cited pin records for the DHT22 module and SRD relay.
  3. Add `voltage`, `max_current` and `role` to Board IR nets, filled by the generators.
  4. Add a decoupling-distance claim using Microchip's 6 mm citation (R5).
  5. Add trace width against proven current, using IPC-2221 as the conservative formula (R10).
  6. Refuse any mains net without an expert's sign-off until derived creepage exists (R10 B9).
- **Who cares.** Anyone ordering the board in 7.2. R9 notes that practitioners object to non-determinism and want voltage ratings and pin functions checked.
- **What would prove it wrong.** The seeded calibration set grows (swapped pins, reversed diode, mains gap) and the product's verifier, not the review agent, still passes them (R10 B7, D3).

### 7.4 Merge and expose the release package that already exists

- **Opportunity.** The export (KiCad writer, second DRC engine, Gerber with refusal) and the shield are built and invisible: on a branch, not wired to the API, behind a flag that is off in production.
- **Evidence.** R10 §"Manufacturing, test and release exist in code but not in the product". R10 P0 work package 5 (C2, C9–C12). Owner decision 2026-10-17 (refuse fab files for a failed board).
- **Builds on.** Commits 8d63e3b, 283bed8 and 5c3a2fc; `Report.gate()`; the SHA-256 manifest.
- **Smallest step and cost.** About two to three weeks of agent work (inference):
  - merge `alpha-program` into master after the test suite passes;
  - wire export to the API behind the gate;
  - add a fab profile as data (portable profile plus JLCPCB and Lion Circuits overlays; R5 decision 8), so the KiCad minimums stop being 0;
  - add fab notes, silkscreen with polarity and revision, and the BOM inside the package;
  - add Gerber read-back (R5 stage 7) in a Python 3.12 process, since it is the only check that sees the shipped files.
- **Who cares.** It is a prerequisite for 7.2. Fiverr-style buyers expect files.
- **What would prove it wrong.** The read-back disagrees with the Board IR on a real export. That is a finding to fix, not a reason to stop.

### 7.5 Say what the verifier actually knows

- **Opportunity.** Hours of work that answer most of the owner's objection to "unknown" and remove claims a sceptic would catch.
- **Evidence.** R6 build item 0 and its corrections table. The market page corrections (R6). R5's wording lint ("verified", "correct", "works" never without a rung).
- **Builds on.** `verify.py` rungs and `claims.py` grades.
- **Smallest step and cost.** Hours (R6):
  - add the *simulated* rung;
  - split *unknown* into "not checkable", "checkable by simulation, not run (reason)" and "checkable, tool named";
  - fix the `verify.py` branch V text and the `progress.yaml` "Physics scorecard" label;
  - rewrite the market page from R6's table;
  - start one release scorecard joining circuit claims and board checks (R10 D1).
- **Who cares.** The criterion-12 reader, buyers, and investors. R10 notes that 61% of surveyed decision-makers say transparency would raise their trust.
- **What would prove it wrong.** Nothing much; this is hygiene.

### 7.6 Fix the trust defects the code review found

- **Opportunity.** The product's core claim is "checked by simulation". A crashed ngspice run recorded as success breaks that claim silently.
- **Evidence.** Code review "Fix first", items 1–3. The `simulation_task.py` reading in [§4.4](#44-known-defects-that-bear-on-trust). The firmware-injection item is the one direct break of Critical Rule 1 the review found.
- **Smallest step and cost.** About a day per item (inference). Each comes with a regression test.
- **What would prove it wrong.** The items turn out already fixed on a branch not inspected here. Re-read the code first.

### 7.7 Then, the cheap physics that matches Quilter

- **Opportunity.** Parity with Quilter's eight PRCs and its DC IR beta on the boards Circuit OS can route, with a better source for its constraints. R6 says items 0–4 reach this.
- **Evidence.** R6 build items 1, 2 and 4 (stackup and plane 2–4 days; PRCs 3–5 days; DC IR drop 1–2 weeks with two engines). Item 5, AC PDN by PyPEEC plus an ngspice AC sweep, would go past Quilter and native Altium.
- **Builds on.** Board IR, Shapely, scipy.sparse, and the 7.3 net meaning.
- **Cost.** Two to four weeks. New dependencies need owner approval (`decisions.md` [2026-10-09]).
- **Who cares.** Only someone who already uses the boards. Order matters: R10 ranks data integrity over physics because data errors dominate fab holds.
- **What would prove it wrong.** R6 itself: impedance synthesis would still lag Quilter, and scale (2 layers, ≤ 40 parts against 5,000 pins) stays far behind.
- **Reasoning revised 2026-11-14; the recommendation stays last.** The parity target has moved. Flux now claims full-wave EM/SI, PDN impedance, IR drop and thermal estimates "in every plan" ([flux.md](competitor-features/flux.md) C4–C6, F3). Matching Quilter's eight PRCs and DC IR would no longer reach parity with the cheapest AI rival. Flux names no solver and states no accuracy, so its claim is unverified. A Circuit OS physics rung that states its model and its error band is still a different offer. What changed is the case for building it soon; it is weaker, not stronger.

### 7.8 What not to build, and why

- **The checker for imported KiCad designs.** Retracted by R9:
  - the catalogue fully addresses 12 of 143 sub-circuits (8.4%) on ten real boards;
  - catalogue rules raised false alarms where intent was absent;
  - symbols named the wrong parts;
  - the catalogue knows 2 of about 60 ICs.

  Reopen only if R9 test 3 (the 84,000-schematic count) finds more than about 15% of designs shaped like "supported module plus catalogue blocks".

  Strengthened 2026-11-14: the category is now crowded and cheap. Circuit Mind AVE, AllSpice DRCY, Cadstrom, Traceformer ($20/month), NextPCB ($9.90/month), CADY and Probe all review imported designs against datasheets. None publishes precision or recall ([_group-d.md](competitor-features/_group-d.md)).
- **A $49 hobbyist subscription, three-seat team minimums, or "unlimited".** R8 and R9: hobby prices are $7–12, retention under $50 is 23%, and every rival meters. If pricing is tested, price before each action and do not charge for a refusal (R8 §"$1M ARR"; R9 test 5).
- **Industrial/HVAC as the lead market, or any compliance claim.** R8 and R9 show the vertical is served by free reference designs, needs certification, and has no procurement data. Owner call 2 (UL family) waits until people use the tool (`decisions.md` [2026-10-03]). Never assert compliance (`current_phase.md`). Two facts added 2026-11-14, both pointing the same way:
  - Circuit Mind sells to industrial customers (Emerson, Schneider), though it publishes no RS-485 or 4–20 mA rule library ([circuit-mind.md](competitor-features/circuit-mind.md) J1).
  - Huaqiu's KiCad Copilot recognises RS-485 buses (summary, [_group-c.md](competitor-features/_group-c.md)).

  Circuit OS's RS-485 bias and termination rules are still not found elsewhere. The 4–20 mA, 24 V, HVAC and cellular rows on the market page have no code at all.
- **Supplier-paid design-ins or design registration.** These are closed to a small audience (R9).
- **Quilter as a backend.** No API, as re-checked 2026-11-13, and confirmed again in the November pass: no API, CLI or scripting page ([quilter.md](competitor-features/quilter.md) I2). Its free tier trains on uploads and per-pin pricing is unpublished (R6).
- **More A* router work.** Freerouting is the plan (`ROADMAP.md` §5; `decisions.md` [2026-10-06]). R3 and R7 say invest in the checker and the export path, which survive the swap. Strengthened 2026-11-14:
  - Freerouting v2.5.0 (2026-10-05) ships a REST API, an MCP server, Docker images and native executables ([freerouting.md](competitor-features/freerouting.md)).
  - KiCad users, LLM agents (a GPT-6 demo board) and several products route through it.

  Routing is therefore not a differentiator for anyone. Freerouting is GPL-3.0, so Circuit OS should call it as a separate process or service and not link it. Its maintainer has about four hours a week, which is a supply risk to watch, not a reason to build.
- **PyPEEC, FasterCap or openEMS for today's catalogue.** Parasitics are 1.6–3.5 orders below tolerance (R4). R6 says openEMS would take days per port for PDN on two layers. Revisit for nodes near 100 kΩ, crystals, or controlled impedance (R5 decision 4; R6).
- **Widening the catalogue before a named payer asks.** R9's stopping rule: "the one path the evidence argues against". R10 adds that every new block adds unverified footprints and pinouts.
- **Free-form generation, switching power stages, or analog proofs beyond linear stages.** These need research-grade methods, and R1 calls the general question undecidable (`ROADMAP.md` §5: "Do analog last").

---

## 8. A sequence

This reconciles `current_phase.md` (Composition exit met in code; the "For the owner" items) with `ROADMAP.md`. `ROADMAP.md` is dated 2026-08-22 and its own scope note says `current_phase.md` wins.

**Recommended changes to `ROADMAP.md`:**
- record that Gerber moved forward (2026-10-17);
- replace "Phase 3 — Industrial: zero competitors standing there" with R9's finding;
- add a "physical evidence" step ahead of any Phase 3;
- refresh `MENTAL_MODEL.md` §9 against R6.

### 8.1 What an agent can do now, in order

1. **Reconcile branches.** Merge `alpha-program` into master: writer, KiCad DRC, export, shield, ablation, calibration set. Re-run `regen_state.py` so `state.json` stops reporting 2026-10-09.
2. **Fix the code review's three "fix first" items** (7.6), with tests.
3. **Relabel** (7.5):
   - the *simulated* rung and the split of *unknown*;
   - the `verify.py` V text and the `progress.yaml` label;
   - draft a corrected market page for the owner to approve;
   - update `ROADMAP.md` and `MENTAL_MODEL.md` (prose; the owner reviews).
4. **Part truth** (7.3, steps 1–2): land patterns to G1, DHT22 and relay pin records, and footprint comparison with the mirror test (R5).
5. **Net meaning on the board** (7.3, steps 3–6), plus mains refusal.
6. **Release package** (7.4): fab profile, notes, silkscreen, revision stamp, BOM in the package, Gerber read-back, API wiring.
7. **Prepare the evidence campaign.** Draft the coupon board through the pipeline. Write the predictions file. Prepare the R9 test 1 payment link and message (the owner sends it).
8. **Then the Quilter-parity physics** (7.7), only after an owner yes on new dependencies.

### 8.2 What only the owner can do

These are in order of latency; start the slow ones first.

1. **Look up active users and send the 30 asks** (R9 test 1).
2. **Send the criterion-12 cold-read outreach.** It has been open since 2026-06-02 (`ROADMAP.md` step 1). Phase 3 call 3 requires it before any prospect.
3. **Run the bench session** in `docs/BENCH_D1.md`. That closes or reopens D1 per generator, and turns every "simulated" in `docs/REAL_DATA_CHECK.md` into a measurement (`current_phase.md`).
4. **Do the D7 spot-check:** Black Pill rows, the Uno supply figure, the LED V_F minimum, and the transistor figures not read. Then sign the 12 proven properties, which lifts the floor to G1.
5. **Order the coupon,** after 7.4's read-back works, and measure it.
6. **Run the redesigned design-house conversations** (R9 test 4). Ask for a requirement, not a schematic, and ask who owns the schematics.
7. **Make the decisions listed in §9.**

---

## 9. Open questions and decisions waiting on the owner

Gathered from all reports and `current_phase.md`, deduplicated.

**Decisions:**
1. **`Verdict.reopens_d1`:** confirm or reverse it. It keeps D1 closed when a power-off resistance reads off (`decisions.md` [2026-10-08] item 4).
2. **RS-485 bias:** keep 549 Ω, or size at the rail's low end. TI's 523 Ω holds 250 mV at 4.75 V; the generator gives 240 mV (`current_phase.md`).
3. **PyPEEC for verifier step 6:** R5 recommends closed-form intervals instead; never put to the owner (`decisions.md` [2026-10-17]).
4. **Mains policy:** refuse all mains nets until derived creepage exists (R10 B9), or R5's 2.5 / 5.0 mm thresholds. R6 says 2.5 mm is basic insulation only (F-0004).
5. **Default stackup:** 1.6 mm FR-4, 1 oz, Er as an interval (R6 open questions).
6. **The calibration gate as a release criterion:** 90% recall, no false pass on critical classes, scored against the product's verifier and not only the review agent (R10 D3).
7. **New dependencies:** Shapely, scipy.sparse, padne, ThermalSim (R6 items 1–6).
8. **Phase 3 call 2:** the UL family (60730-1 or 61010). R9 suggests it can wait.
9. **Whether to keep the $1M ARR goal and the subscription tiers in the plan.** R9: no solo precedent.
10. **Approve the corrected market page and the refreshed `ROADMAP.md` and `MENTAL_MODEL.md`.**
11. **The schematic still draws U1 as ATmega328P-PU on shield designs:** the circuit, board and order disagree (`decisions.md` [2026-10-22]).

**Open questions no report answered:**
- How many people use the deployed product (R9)?
- Do Flux or Celus produce a correct biased, terminated RS-485 node on request? An afternoon's test (R8).
- What share of real designs are "supported module plus catalogue blocks"? (R9 test 3, the 84,000-schematic dataset; its licence is unchecked.)
- Who owns a design house's schematics, and does a client have to consent (R9)?
- What does an Indian fab or distributor pay for a design-originated order (R8, R9)?
- Does ThermalSim run headless on exported files? Does KiCad 10's ngspice include TXL/CPL? (R6)
- Does the sentinel rule survive KiCad 10's last-match-wins rule ordering? What does each fab's electrical test reference: Gerbers or a netlist? (R5)
- What is the KiCad library's own error rate? No source gives one (R5).
- What do the IEC 62368-1 / 60664-1 tables give for creepage? Never read (R5, R6, R10).
- Does Quilter have any job-submission API? Absence confirmed again on 2026-11-13, but absence only. Which solver runs its DC IR beta, and how accurate is it? (R6)
- Will NextPCB allow third-party use of its DFM endpoint? Do Boardera's API docs exist as reported? (R6)
- What do firmware compilation and simulation cost per generation (R8)?
- Does a buyer of a simple board pay more for verification? No survey or price experiment exists (R9).

**Not covered by any report.** The owner may want these, and none of the eleven reports addresses them:
- usage, retention or funnel data from the deployed site;
- a competitor's actual output on the same prompt as Circuit OS (no head-to-head run exists);
- legal terms for selling a design (liability wording, refund policy) beyond reading one vendor's terms;
- the cost of running the stack in production per design;
- hiring or partnering: what a second person would do first;
- the investor document `Circuit OS decisions for investors.pdf` (outside this report's scope; not read).

---

## 10. Appendix: digest of each report

### R1 — Analog circuit formal verification ("Bounds, not compute, make analog proofs tractable")

**Question:** why is analog formal verification hard, and what can Circuit OS prove?

**Method:** literature review of decidability, complexity and tools.

**Findings:**
- There are three walls: impossible (hybrid-automaton reachability, Richardson, Gaussian noise), expensive (doubly exponential real arithmetic, NP-hard stability) and practically hard (wrapping, dimensionality).
- Compute does not move the first two.
- The catalogue is decidable: exact z3 over tolerance boxes, π bracketed, monotone corners. Freeze properties after sign-off and mutation-test them.
- The LLM-plus-solver loop is prior art; an analog front end with a formal engine was not found.

**Still good for:** deciding what any new block can be proved about. Its tier table (0–4) is the gate for widening into op-amps, comparators or power.

### R2 — Is the board correct? A software-only verification tree

**Question:** is the board, not just the circuit, correct?

**Method:** decomposition into seven branches; 25 claims checked adversarially.

**Findings:**
- III (copper is the schematic) can be exact.
- IV (footprint is the part) is sound only against an external truth.
- V (as-built behaviour) was labelled unknown or bounded; VI and VII are the circuit and the environment.
- Steps 1–4 were built as `verify.py`.

**Corrected by R6:** "unknown", HyperLynx as "the one stack", and the thermal, AC PI and placement claims. The refusal model was overtaken by the 2026-10-17 decision.

**Still good for:** the tree itself and the rung vocabulary, which the product uses.

### R3 — PCB routing validation methods ("Check the answer, not the router")

**Question:** how to validate the router cheaply.

**Method:** reading, plus KiCad DRC run.

**Findings:**
- Ten methods ranked by confidence per cost: independent judges, geometric floors, seeded violations, Freerouting as reference.
- A physical board says little about routing on slow circuits unless it carries reference and control boards.
- Clean pass is the unit. Completion, not wirelength, is the problem.

**Corrected by R4:** the parasitic orders and the MST-as-floor error.

**Still good for:** the router test plan, and the warning that a fabricated board tests the export chain more than the routing.

### R4 — Verification ledger for R3

**Question:** which of R3's claims hold?

**Method:** four verification agents on primary sources, plus local execution.

**Findings:**
- KiCad 10.0.1 DRC exit codes: 5 on violations, 0 clean, 3 for a malformed board. Without `--exit-code-violations` it exits 0 on a board with 28 violations.
- The router defects confirmed by execution.
- Parasitic orders are 1.6–3.5. Only HPWL and RSMT are floors.
- Nine claims still rest on the first pass.

**Still good for:** the trap list for CI, and as the model of how to label what was run.

### R5 — PCB verification implementation plan ("Check the shipped files, then build one coupon")

**Question:** how to validate boards as strongly as free technology allows.

**Method:** translation validation, chip sign-off practice, independence through different inputs. The library parse, `kicad-cli` exports and a 130-line read-back extractor were run.

**Findings:**
- One SOT-23 footprint carries 39 pin assignments across 334 parts, so package-wide pin maps are wrong.
- The read-back caught a moved drill hit that KiCad cannot see.
- A nine-stage pipeline and twenty decisions; the first three were adopted on 2026-10-17.
- A coupon order with predictions committed first.

**Corrected by R6:** the solver stance, kicad-parasitics, and the DFM API.

**Still good for:** the build order of the board pipeline, the read-back stage, and the coupon design.

### R6 — Physics layout validation: what the market does and what Circuit OS can build

**Question:** what physics layout validation is sold, and what Circuit OS can build.

**Method:** eight researchers, two checkers per claim, the 74-page Quilter documentation read, code audited and tests run.

**Findings:**
- Four meanings of "validation".
- Quilter's physics is eight rule checks, a 2D solver and a DC IR beta; it is no sign-off tool.
- Sign-off physics is widely sold and partly free; nobody proves a board works.
- Circuit OS has no layout physics in code.
- Corrections to R2, R3, R5, `PCB_STRATEGY.md` and the market page.
- A twelve-item build list with rungs and sizes.

**Still good for:** the factual baseline on competitors' physics, the correction tables, and items 0–5 when the time for physics parity comes.

### R7 — Validating the router in software

**Question:** how much of the router can be validated without fabrication.

**Method:** a harness run against the repository.

**Findings:**
- `Board.unrouted()` used a cell test; the shipped board read 8/12 when it was 12/12, and 4,000 of its ~4,149 score was phantom.
- The DRC broad phase missed real violations.
- The quoted floor was 46% high, and the DSN exporter carried no vias.
- 40 of 40 metamorphic checks held. The shipped board is 1.6% above the rectilinear MST.
- All fixed and pinned by 2026-10-17.

**Still good for:** proof that independent checkers pay. Its three-verdict vocabulary: checked clean, proved within scope, not routed by this heuristic.

### R8 — Customers and business model ("Teams pay for verification; hobbyists don't")

**Question:** who pays, and at what price.

**Method:** mostly search summaries (notes 2026-10-12).

**Findings that stand:**
- hobbyists pay $7–12;
- rivals meter usage;
- churn under $50 is severe;
- $1M ARR arithmetic: about 1,700 Pro subscribers or about 280 teams;
- industrial is unadvertised, not uncontested;
- India gives users, not first revenue.

**Retracted by R9:** its top recommendation, the imported-design checker sold to teams.

**Still good for:** pricing-shape arguments (price before each action, no charge for refusals) and the India go-to-market framing.

### R9 — Paying customer evidence ("New evidence retracts the checker-first plan")

**Question:** does anyone pay for what Circuit OS does?

**Method:** price pages read, demand threads read, a ten-board composition tally.

**Findings:**
- Nobody has been shown to pay.
- Catalogue coverage of real boards is 8.4% full, and the covered blocks are not leading respin causes.
- No automated review vendor publishes revenue.
- Per-board money exists at $1–250 and $10,000+, with a gap between.
- Confidentiality favours generation over review; liability means "verified" sells as evidence, not as a guarantee.
- Six ordered tests with a 90-day, 70-ask stopping rule.

**Still good for:** the business sequence. It is the most decision-relevant report in the set.

### R10 — Generative EDA tool feature spec ("Prove the board, not just the circuit")

**Question:** what a great generative EDA tool needs, and where Circuit OS stands.

**Method:** wide reading on board quality, failure causes, tools and engineer trust; Circuit OS scored from code on 2026-10-22.

**Findings:**
- Most failed first boards are data errors: footprints, pin maps, BOM and revision drift, missing notes.
- Engineers trust checks, citations and refusals: 13% highly trust AI for part selection.
- 58 features: 10 have, 24 partial, 24 missing.
- 16 P0 items in five work packages: part truth, net meaning, fab target, board context and safety, release package.

**Still good for:** the product backlog for the board half, and the recommended metric: the share of the release checklist proved, or checked by a named rule.

### R11 — Where Circuit OS sits in the consulting reports

**Question:** do McKinsey, BCG, Capgemini, the Global Electronics Association and others describe Circuit OS's gap?

**Method:** reading, some in summary only.

**Findings:**
- Generative AI has stalled in hardware because evaluation is the bottleneck.
- Generate-versus-verify splits appear in McKinsey and BCG.
- Lower design cost opens low-volume markets.
- Only 15% of executives think AI replaces engineers.

**Caveat (its own):** direction, not demand.

**Still good for:** investor and positioning language: "engineer plus verifier", "verification-first compiler for the long tail". Use it only alongside R9.
