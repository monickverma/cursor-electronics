# Is the board correct? A software-only verification tree

You asked one question — *"is the PCB correct or not?"* — and the honest first finding is that the
question has no single answer, and no free tool answers it. This report does three things. It
decomposes the question top-down, from *"this board works in real life"* to the individual claims
it rests on. For every branch it names the strongest check software can run today, the tool that
implements it, and the **rung of trust** that check stands on. And it states, plainly, the branches
where no software check exists and the honest answer is *unknown*.

It is the board-level companion to `Analog circuit formal verification.md` (which proves the
*circuit* right) and to `Validating the router in software.md` (which checks the *traces*). This one
asks the question neither of them asks: is the *board* — the physical object, its footprints, its
assembly, its copper as fabricated — the thing the design meant?

---

## The headline, before the tree

**Nothing in the current free and open stack proves a board works in real life.** Every check that
exists is one of two things: a geometric or constraint test (DRC, DFM, an IPC-D-356 comparison), or
a partial physical extraction (R and L, but not C). Each is *evidence*, not a proof. No verified
capability in this research claims otherwise ([finding 5](#sources)).

The commercial stacks agree, by construction. Cadence's DFM rules decompose board correctness into
five purely geometric categories — Outline, MASK, Annular Ring, Copper Spacing, Silkscreen — plus
separate Design-for-Assembly and Design-for-Test domains, with **no electrical or functional
category anywhere in the rules set** ([Cadence/FlowCAD rules guide](https://www.flowcad.de/AN/DesignTrueDFM_RulesGuide_17_2_QIR7.pdf)).
Altium's DRC is a rules-driven check against human-declared constraints, and its batch output is a
violation report — evidence, not a verdict ([Altium](https://www.altium.com/documentation/altium-designer/tutorial/verifying-board-design)).
Siemens HyperLynx is the one stack that adds electrical sign-off as its own layer — signal integrity,
power integrity, EMI/EMC (its own rules guide names six domains including analog and packaging) — and
it is sold as a *separate product from DFM* ([Siemens](https://www.siemens.com/en-us/products/pcb/hyperlynx/electrical-design-rule-check/)).
The industry's own split is the shape of the answer: **geometry is checkable and gets checked;
function is a different problem, solved (when at all) by separate, heavier tools.**

So the deliverable is not "a correct-or-not button". It is a tree in which each leaf is a claim, a
deterministic check, and a labelled guarantee — and the top of the tree carries a permanent
*unknown*, honestly marked, for the parts software cannot reach.

---

## Part 1 — The tree

The root claim is:

> **This board, fabricated and assembled with the parts in its BOM, does what the design intends,
> in the environment it will be used.**

It decomposes into seven branches. Two of them (VI, VII) are not about the board at all and are
handled elsewhere — they are shown because the root claim depends on them, and a verification layer
that forgot them would be lying by omission. The other five are the board's own.

| # | Branch — what it settles | Software check | Rung |
|---|---|---|---|
| **I** | **It can be made** — the artwork is fabricable | | |
| I.1 | Geometric rules hold (clearance, annular ring, drill, copper-to-edge, mask sliver, sliver copper) | KiCad DRC; independent re-check | Sound over-approximation *within the rule set* |
| I.2 | The fab will accept it at its published minimums | DFM rule profile | Sound over-approximation *within the profile* |
| I.3 | The shipped files match the intent | Gerber↔netlist LVS (IPC-D-356) | Evidence |
| **II** | **It can be assembled** — the bare board becomes a working assembly | | |
| II.1 | Courtyards don't overlap; nothing collides | KiCad courtyard rule; geometry | Sound (geometry only) |
| II.2 | The part can actually be placed (land pattern vs part) | see IV | — |
| II.3 | It won't tombstone / bridge (pad symmetry, thermal relief) | geometric check on pad-to-copper coupling | Sound over-approximation (rule-based) |
| II.4 | Polarity and pin-1 are right; the pick-and-place file matches | checkable where footprints declare orientation | Partial / evidence |
| **III** | **The copper is the schematic** — the layout realises the netlist | | |
| III.1 | Every net is connected (no opens) | union-find over copper geometry | **Exact** |
| III.2 | No two nets are shorted | same judge | **Exact** |
| III.3 | Every pad carries its intended net; no extra or netless pads | net-annotation check | **Exact** (if run) |
| III.4 | Symbol pin count and order match footprint pad count and order | pin-map check vs datasheet | Sound *if* the ground truth is external |
| **IV** | **The right part is in the right place** — footprint vs the real component | | |
| IV.1 | Land-pattern geometry matches the part | IPC-7351B or datasheet contact-figure check | Sound, *only* against an external ground truth |
| IV.2 | Pin numbering matches the real part | none reliably exists | **Unknown** today |
| IV.3 | Courtyard and body match the datasheet; it fits mechanically | footprint geometry vs datasheet | Sound against external ground truth |
| **V** | **As built, it behaves like the design** — the board doesn't break the circuit | | |
| V.1 | Board parasitics keep graded quantities in tolerance | back-annotate R/L into SPICE | **Bounded** (R, L only; no C, no mutual) |
| V.2 | Signal integrity is a non-issue at this speed/length | geometric rules (return path, crossings) | Evidence / unknown for this class |
| V.3 | Power integrity holds (IR drop, decoupling, PDN impedance) | DC network solve; DC IR drop | Bounded (DC only) |
| V.4 | Thermal rise is acceptable | IPC-2221 ΔT as a by-product | Bounded (isolated trace only) |
| V.5 | EMI/EMC passes | none sound | **Unknown** |
| V.6 | Safety clearances (creepage/clearance) hold | distance rules | Sound *within the rule table* |
| **VI** | **The design is right** — the circuit does what was asked | formal proofs over tolerance boxes | Exact (see the analog report) |
| **VII** | **It works in its environment** — cables, supply, firmware | generators + bench gate | Evidence (bench) |

The rungs are the ladder from `Analog circuit formal verification.md`, kept for consistency:

- **Exact** — decidable over a stated model and bounds; "unsat" is a proof.
- **Sound over-approximation** — a guaranteed enclosure; may be loose; may return *unknown*.
- **Bounded** — true up to named missing terms (e.g. R and L measured, C absent).
- **Evidence** — a report that found no violation. Absence of a counterexample is not proof.
- **Unknown** — no software check exists for this claim on this board class.

The tree is the answer to *"topple down from there"*. The rest of the report fills in each branch
with what the research actually found.

---

## Part 2 — What each branch can reach

### III. The copper is the schematic — the one branch that is already exact

This is the branch the project already owns, and it is the strongest. `Validating the router in
software.md` built a union-find judge over copper geometry that decides opens and shorts
independently of the router's own `unrouted()` — and it found that method wrong (it compared 0.35 mm
quantisation cells, not distances, and mis-reported a complete board as one-third open). Replacing
that with the geometric judge moves branch III.1 and III.2 to **exact**.

Two gaps remain inside the branch, and both are cheap and real:

**III.3 — the netless "ghost" pad.** KiCad's DRC flags a pad with no net as *standalone copper*: it
needs no connection and is not a short, so the report stays green while the board is electrically
wrong ([kicad-board-lint](https://github.com/94xhn/kicad-board-lint)). The research verified this as
a real blind spot (2-1). A pad that should carry a net but carries none is invisible to DRC. The
check is exact and trivial: every pad must be assigned to exactly the net the schematic says.

**III.4 — pin count and order.** A symbol with two pins placed on a footprint with four pads (the
class of the project's own SOT-23 ordering bug) passes DRC: the extra housing-ground pads are simply
left floating, and DRC sees nothing wrong. Only the opt-in, project-correlated Schematic Parity
provider flags a pad missing a schematic-assigned net — and only with `--schematic-parity`, and even
then it does not catch *extra* pads with no schematic pin ([kicad-board-lint](https://github.com/94xhn/kicad-board-lint)).
A deterministic check — symbol pin count vs footprint pad count, and pad-to-pin mapping — closes
this, and it is the highest-value exact check the project is missing.

### IV. Footprint vs the real part — checkable, but only against an external truth

The research found that the tools that exist are **self-consistent, not grounded**. `kicad-partspec`
does compare generated pads against datasheet values, test that pads reach the leads, and check
silkscreen and courtyard ([PyPI](https://pypi.org/project/kicad-partspec/)) — but it *generates* the
footprint from the datasheet's own example land pattern (not computed from IPC-7351B), it *skips*
parts with no explicit land pattern with only a `footprint.skipped` warning, and generation and check
consume the *same* extracted spec — so a misread datasheet both generates the footprint **and** passes
the check. That is the trap. A self-consistent check is evidence about the generator, not about the
part.

The stronger pattern is `EDA-Footprint-Generator`: a deterministic **generation-time gate** that checks
IPC-7351B geometry (pad-to-pad clearance and annular ring as errors; silkscreen-to-pad and courtyard as
warnings) and *aborts generation before any file is written* ([GitHub](https://github.com/PedroWall-e/EDA-Footprint-Generator)).
That architecture — check, then refuse to emit — is exactly what a generation-time verifier in Circuit
OS should be; the caveat is that its validation block is wrapped in a silent `try/except ImportError`,
so it can skip itself without saying so.

The wall is IV.2, **pin numbering**. One candidate does it — `kicad-partspec`'s *Footprint Audit
Engine* centroid-aligns real pad geometry against a datasheet-derived land pattern and compares pad
sequence and pin numbering ([DeepWiki](https://deepwiki.com/salitronic/eda-agent/5.1-footprint-audit-engine))
— but that engine is a helper inside a specific agent tool, not a general library, and its ground
truth is again an LLM-extracted datasheet spec. And I found a refutation in this run worth naming:
the claim that a commercial DFM tool brackets SMD pad extents on **both** a minimum and a maximum
against a datasheet *contact figure* (which would flag an oversized, bridging pad) was **killed 0-3** —
the source's own text does not support it. So even the "check both bounds" story is not established.

**Verdict for IV:** the branch can be raised to *sound over-approximation* **only** if the check runs
against a ground truth that is independent of the generator — a computed IPC-7351B land pattern, or a
validated datasheet contact figure with a page citation. No found tool fully does this for pin
numbering. This is the single most important thing to build next for branch IV.

### V. As built, it behaves like the design — the branch that is mostly *unknown*, by design

This is where "works in real life" gets hard, and where the research is most useful because it says
clearly what *cannot* be reached.

**V.1 — back-annotation.** Making a schematic-level proof a proof about the board requires the board's
parasitic R, L and C. Two free tools cover different, incomplete parts:

- **PyPEEC** — MPL-2.0, peer-reviewed (JOSS, DOI 10.21105/joss.06644), a 3D quasi-magnetostatic PEEC
  solver that ingests Gerber directly and returns resistive and inductive terms, self- and mutual-L.
  It **explicitly models no capacitive effects and no dielectric domains** ([PyPEEC](https://pypeec.otvam.ch/)).
- **kicad-parasitics** — computes net DC resistance by building a trace-resistance network and
  simulating it in ngspice (pads treated as ideal, mid-trace junctions not captured); auto-selects
  microstrip (outer) or stripline (inner); uses a lumped model below λ/20 and splits into distributed
  RLGC segments above it; extracts loop inductance with bfieldtools while **ignoring mutual inductance,
  capacitance, and metal-plane effects** ([GitHub](https://github.com/steffen-w/kicad-parasitics)).

Together they give **R and L, no C, no inter-trace coupling**. So any board-level electrical proof
must be labelled **bounded** — true up to the missing capacitance and mutual terms — never exact. The
gap is fillable with a FastCap/FasterCap-class capacitance extractor, but no one has assembled the
end-to-end path.

**V.2 — signal integrity is largely a non-issue at this class, and that is the honest finding.** For a
2-layer board below about 1 GHz with a continuous return path, loss and controlled impedance are
mostly irrelevant; the real risks are crosstalk from return-loop mutual inductance and power-rail
switching noise — not transmission-line impedance ([Bogatin, SI Journal](https://www.signalintegrityjournal.com/blogs/12-fundamentals/post/1207-seven-habits-of-successful-2-layer-board-designers)).
For the project's boards — hobby 2-layer, clocks well under 10 MHz, slow edges — a 2-layer stackup is
sufficient *provided* there are no impedance-controlled nets, no high-current switching nodes, and no
strict EMC limits ([PCB-Review](https://www.pcb-review.com/blog/pcb-stackup-design-guide.html)). This
is the useful reframe: **the expensive SI machinery would be answering a question this board does not
ask.** The checkable residue is geometric — is there a return path, do sensitive traces cross noisy
ones — not a field solve.

**V.3 — power integrity is load-bearing, and partly checkable.** DC IR drop is computable (a resistor
network, or the free padne/kipy-class solvers the prior notes list). But the sharper finding is that on
a **2-layer** board, decoupling-capacitor *distance* strongly degrades PDN impedance — a 100 nF cap even
10 mm away severely shrinks the sub-1-ohm band, where on a 4-layer board it would be nearly as effective
([jmw.name](https://jmw.name/projects/exploring-pdns/)). So component placement is a load-bearing
variable for PI on exactly this board class — which means the *placement* branch (which no tool scores)
and the *PI* branch are the same problem seen twice.

**V.5 — EMI/EMC has no sound software check, and the failure is not silent.** The Huygens'-Box method
underestimates radiated emission by **more than 10 dB at resonances** ([AAU](https://vbn.aau.dk/ws/portalfiles/portal/177758046/Influence_of_Resonances_on_the_Huygens_Box_Method.pdf)) —
a check that is *confidently wrong* in a specific band. For this project's class, EMI is out of scope
(no strict limits, slow edges), and the correct action is to mark it **unknown and out of scope**, not
to run a tool that lies at resonance.

### II. Assembly — the branch with real-world failure modes and partial coverage

The research found a genuine, checkable failure mode: **tombstoning** of small two-pad passives is
caused by asymmetric pad heating — one pad tied directly to a copper plane, the other reached through a
narrow trace — and is detectable in software by enforcing a thermal-relief connect style and
footprint-level pad symmetry ([Altium](https://resources.altium.com/p/common-dfm-problems)). That is a
rule-based, sound over-approximation, and it is worth having. Courtyard overlap is a KiCad rule.
Polarity, rotation and pick-and-place correctness are only checkable where the footprint declares its
orientation — partial, and evidence-grade.

### I. Manufacturability — the branch the project already knows well

Covered thoroughly in the prior `PCB routing validation methods` notes: KiCad DRC as an independent
engine, fab-minimum DFM profiles, and the fact that **no fab offers a CI/API DFM check** — the fab
tools are browser-upload, a manual gate, not an automated one. The one new finding here sharpens I.3:
Altium's IPC-D-356 netlist-vs-extracted comparison is **only a geometric contact check** (it tests
whether pad flashes on the two netlist layers touch, then verifies the name) and is documented as
**unsound when the extracted netlist is incomplete**, naming nested split planes as a known failure
case ([Altium](https://www.altium.com/documentation/knowledge-base/altium-designer/generate-ipc-d-356a-document-and-compare-to-extracted-netlist)).
So the "LVS against what ships" idea is real, but the off-the-shelf version carries a documented
false-positive mode.

**And there is still no free PCB Gerber→netlist extractor.** Gerbonara reads and writes Gerber,
Excellon and IPC-356 (Apache-2.0, AGPL-compatible) but performs **no** connectivity extraction, LVS,
or layer comparison — its netlist handling is limited to the IPC-356 format itself
([Gerbonara](https://gerbolyze.gitlab.io/gerbonara/)). The algorithms needed to build one are proven
and reusable: `vyges-tools/lvs` derives connectivity from pure geometric overlap with a uniform-grid
spatial index and matches netlists name-independently with 1-WL graph colour-refinement over a
device/net bipartite graph ([GitHub](https://github.com/vyges-tools/lvs)); KLayout ships an open LVS
framework with a `NetlistCrossReference` object that lists non-matching nets
([KLayout](https://www.klayout.de/doc/code/class_LayoutVsSchematic.html)). Both target IC/GDS, not
Gerber — transferable techniques, not off-the-shelf PCB tools.

---

## Part 3 — What the commercial stacks prove, and where they stop

The borrowable decomposition, verified across Altium, Cadence and Siemens:

| Vendor | How it decomposes "board correctness" | What is absent |
|---|---|---|
| Altium | Rules-driven: human declares constraints, DRC checks them (online or batch); batch output is a violation report | No derivation of correctness from a functional model |
| Cadence DFM | Five geometric categories (Outline, MASK, Annular Ring, Copper Spacing, Silkscreen) + DFA + DFT | **No electrical/functional category at all** |
| Siemens HyperLynx DRC | Electrical sign-off as its own layer: SI, PI, EMI/EMC (rules guide lists six domains incl. analog, packaging, compliance-safety), 90+ parameterisable rules | Sold separately from DFM; still rule-driven |

Two things follow. **The geometry checklist is proven and free to copy** — it is exactly branches I and
II. **The industry treats geometry and function as different products**, which corroborates the tree's
own split: III–IV are checkable and cheap; V is where the money goes, and even then it buys
rule-based evidence, not proof.

---

## Part 4 — What software cannot reach

Stated plainly, because a verification layer that hides these is worse than none.

1. **Whether the board works in real life.** No check in the free stack proves it. The top of the tree
   stays *unknown*.
2. **Pin numbering against the real part (IV.2)** — no reliable free ground truth exists today.
3. **Capacitance and mutual coupling of the routing (V.1)** — the C term is unfilled; the board model
   is bounded, not exact.
4. **EMI/EMC (V.5)** — no sound check, and the leading method is confidently wrong at resonance.
5. **Thermal at board level** — no free PCB-specific solver; only an isolated-trace ΔT by-product.
6. **AC power integrity** — DC only; no plane resonance or PDN impedance curve.
7. **Whether the placement is good** — no executable placement-quality metric; and per V.3, on a
   2-layer board placement is load-bearing for PI, so this is a real hole.
8. **The model-versus-hardware gap** — every result is a theorem about a model. The project's bench
   accuracy gate exists precisely here, and software cannot replace it.

---

## Part 5 — The move: a verification compiler, built in this order

The architecture follows the One Rule and the analog report's propose/dispose split: **the LLM never
writes the verification obligation; a deterministic compiler derives each check from the IR and the
Board IR, and every result carries its rung.** Concretely, a verification layer that runs at generation
time and refuses to emit a board that fails an *exact* or *sound* check.

Build order — cheapest, highest-evidence first:

1. ~~**Wire the exact connectivity judge into generation.**~~ **Built.** `pcb_engine/verify.py`
   (`unrouted_connections`) replaces the count `Board.unrouted()` feeds the product with the union-find
   judge; `compile_board` now reports the judge's number and keeps `stats["router_unrouted"]` beside it.
   On the shipped `dht22_relay_monitor` this reads **12/12 routed**, where the router's own count says
   8/12 — the phantom-unrouted mis-report, now a number in the payload instead of a rumour.
2. ~~**Add the netless-pad and pin-count/order checks (III.3, III.4).**~~ **Built.** `verify.py`
   re-derives every pin's net from the netlist and the declared `PINMAPS`, and reports the SOT-23 class:
   a label with no declared pinout is **unknown** (arbitrary free-pad assignment, unchecked against the
   real part), a pin collision or a named-but-netless pad is an **exact failure**.
3. ~~**Add the land-pattern gate against an external ground truth (IV.1, IV.3).**~~ **Built, as a
   registry — deliberately not as `sound`.** `pcb_engine/land_patterns.json` is a figure table written
   outside the generator; `verify.py` fails when the generated footprint's pad count disagrees with it,
   and reports **evidence / unknown** for every entry whose `verified` flag is false. Every entry ships
   false: the table can disagree with `footprints.py`, nothing yet makes it right. Filling it from
   datasheets is the work IV.1 still needs.
4. ~~**Add the assembly rules (II.3 tombstoning, courtyard).**~~ **Built.** Courtyard containment and
   overlap are **exact** (II.1, II.2); equal pad copper on two-terminal SMD parts is an **exact**
   tombstoning *precondition* (II.3); the reflow thermal model that decides the rest is a stated
   **unknown** (II.3b).
5. **Build the Gerber→netlist LVS extractor (I.3, III against what ships)** from geometric overlap plus
   1-WL matching, using Gerbonara to parse. The one check that sees the *fabrication* files. **Not built.**
6. **Build the layout→circuit back-annotation (V.1)** with PyPEEC for R/L and a capacitance extractor
   for C, then diff graded quantities against the ideal netlist. Label it **bounded**. **Not built.**
7. **Mark V.2, V.4, V.5 as explicit unknowns**, out of scope for this board class, with the reason
   recorded — a stated unknown, never a silent pass. **Done** — V, VI and VII are emitted as unknowns by
   every `verify_board` call.

Steps 1–4 are the harness, and they are in the tree (`backend/pcb_engine/verify.py`,
`land_patterns.json`) with tests in `tests/test_pcb_verify.py`. Steps 5–6 need new dependencies and are
the next build. One deviation from the sketch above: the layer is a flat module, not a `verify/`
package — `pcb_engine` imports its siblings by bare name and adds its own directory to `sys.path`, so a
subpackage would fight that convention. The seam is `verify_board(board, netlist) -> Report` either way.

---

## Sources

Commercial decomposition: [Altium DRC](https://www.altium.com/documentation/altium-designer/tutorial/verifying-board-design) ·
[Cadence DFM rules guide](https://www.flowcad.de/AN/DesignTrueDFM_RulesGuide_17_2_QIR7.pdf) ·
[Siemens HyperLynx DRC](https://www.siemens.com/en-us/products/pcb/hyperlynx/electrical-design-rule-check/).
Footprint: [kicad-partspec](https://pypi.org/project/kicad-partspec/) ·
[EDA-Footprint-Generator](https://github.com/PedroWall-e/EDA-Footprint-Generator) ·
[kicad-board-lint](https://github.com/94xhn/kicad-board-lint) ·
[Footprint Audit Engine](https://deepwiki.com/salitronic/eda-agent/5.1-footprint-audit-engine).
Parasitics: [PyPEEC](https://pypeec.otvam.ch/) · [kicad-parasitics](https://github.com/steffen-w/kicad-parasitics).
LVS: [Altium IPC-D-356](https://www.altium.com/documentation/knowledge-base/altium-designer/generate-ipc-d-356a-document-and-compare-to-extracted-netlist) ·
[Gerbonara](https://gerbolyze.gitlab.io/gerbonara/) · [vyges-tools/lvs](https://github.com/vyges-tools/lvs) ·
[KLayout LVS](https://www.klayout.de/doc/code/class_LayoutVsSchematic.html).
Physical limits: [Bogatin, 2-layer SI](https://www.signalintegrityjournal.com/blogs/12-fundamentals/post/1207-seven-habits-of-successful-2-layer-board-designers) ·
[PDN on 2-layer](https://jmw.name/projects/exploring-pdns/) ·
[stackup class](https://www.pcb-review.com/blog/pcb-stackup-design-guide.html) ·
[Huygens' Box resonances](https://vbn.aau.dk/ws/portalfiles/portal/177758046/Influence_of_Resonances_on_the_Huygens_Box_Method.pdf) ·
[tombstoning](https://resources.altium.com/p/common-dfm-problems).

**Provenance and limits of this research.** 27 sources fetched, 130 claims extracted, 25 adversarially
verified (22 confirmed, 3 killed). Three findings rest on very-low-traction, brand-new projects
(`kicad-partspec` v0.0.1, `EDA-Footprint-Generator` ~39 commits) whose claims are self-reported README
and source behaviour, not independently reproduced; `kicad-board-lint` is a one-star hobby linter whose
mechanism is nevertheless corroborated by KiCad's own tracker. Several LVS findings are IC/GDS-oriented
and apply to PCB only by analogy. All tool claims are current as of 2026 and the space moves fast. The
synthesis in Part 4 and the build order in Part 5 are this report's own inference from the corpus, not
directly verified claims.
