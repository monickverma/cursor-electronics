# Verification ledger — PCB routing validation methods

This records the second, independent pass over `reports/PCB routing validation methods.md`.
Its purpose is to separate three things that the report itself does not always distinguish:
claims that were **checked against a source during this pass**, claims that were **executed
on this machine**, and claims that **still rest on the first pass alone**.

The first attempt at this pass ran as an automated workflow and stopped partway when the
account hit its monthly spend limit; 19 of its verifier panels never ran. This pass was
done directly instead: four independent verification agents working from primary sources
(papers, standards bodies, vendor documentation, project repositories), plus local
execution where the claim was testable on Windows.

---

## Executed on this machine (not read, run)

These were listed in the report as unverified. They are now measured.

| Fact | Result |
|---|---|
| Is KiCad installed? | Yes — **10.0.1**, at `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`. The report said this was unconfirmed. |
| `kicad-cli pcb drc --format json --exit-code-violations` on a board with violations | 28 violations found, **exit 5** |
| Same command where the report's violation set is empty | **exit 0** |
| Same board, 28 violations, **without** `--exit-code-violations` | **exit 0** — the flag is the entire gate |
| Malformed board file | **exit 3**, `Failed to load board` |
| DRC JSON fields | `violations`, `unconnected_items`, `schematic_parity`, `ignored_checks`, `included_severities`, `coordinate_units` (default `mm`), `kicad_version`, `date`, `source`, `$schema`. Each violation has `type`, `severity`, `description`, `items[]` with `pos` and `uuid`. |
| `kicad-cli pcb drc --help` flag list | Matches the report exactly, including `--schematic-parity`, `--severity-all|error|warning|exclusions`, `--refill-zones`, `--save-board`, `--units`, `-D/--define-var`. |
| Does the repo already export Specctra DSN? | Yes — `to_dsn()` at `backend/pcb_engine/router.py:499`, as the report states. |

### Second pass — executed against the router itself

Recorded in `reports/Validating the router in software.md`; the harness is the set of
scripts in the scratch `router_check/` directory.

| Claim | Result |
|---|---|
| `Board.unrouted()` is a faithful connectivity check | **REFUTED — executed.** It does not compare distances; it requires a track endpoint to quantise into the *same 0.35 mm cell* as the pad centre. Two points 0.002 mm apart cross a cell boundary and read as unjoined. A fixed 0.200 mm offset is reported unrouted for **57%** of positions — exactly offset/cell. |
| The demo board's routability under many net orders | Executed, 24 orderings: router's own count best 11 / median 13 / worst 16; independent union-find judge best 5 / median 7.5 / worst 12. At own = 13 the true count spans 5..12. |
| Every failed connection is a routing-search failure, not a model failure | Executed: **0 of 5** failed connections on the best seed lacked a path on an otherwise empty board. All are congestion and ordering. |
| The product's reported routed count is correct | **REFUTED on the shipped board.** `dht22_relay_monitor` is fully routed on all 16 seeds (judge: 0 unrouted); the router reports **4 unrouted every time**, so the UI says 8/12. Score ≈ 4149, of which **4000 is the phantom** (w.unrouted = 1000). All four connect with copper ending 0.054–0.127 mm from the pad centre. |
| The DRC broad phase cannot hide violations | **REFUTED — executed.** Boxes are padded by `t.width`; the narrow phase needs `clearance + w1/2 + w2/2`. At clearance 0.25 mm, separations 0.40–0.44 mm are real violations and `drc()` returns none; at 0.30 mm it misses 0.40–0.49 mm. Trigger: `clearance > (w1+w2)/2`. |
| The floor quoted in the report is a valid lower bound | **REFUTED — executed.** 365.8 mm was Manhattan summed over a Euclidean-chosen spanning tree. Correct floors for the demo board: rectilinear MST 358.6 mm; `max(span, ⅔·MST)` **307.9 mm**; octile **265.5 mm**; euclidean **250.0 mm**. The quote overstated the true floor by 46%. |
| The router's moves are Manhattan | **REFUTED.** A real track runs `(11.25,9.00)→(30.00,14.75)`, slope 0.307 — arbitrary angle. 30% of connections come in *under* the octile floor, so only straight-line distance is a universal bound. |
| `to_dsn()` can drive a two-layer reference router | **REFUTED — read and grepped.** The DSN contains no `(via ...)` padstack and no via rule, so Freerouting would be limited to one layer against a two-layer router. Pads are stamped on all signal layers. |
| Per-connection efficiency can be measured against a floor | **Executed, with a corrected method.** The first walker reported ratios below 1 (impossible): the router splits one copper run into several tracks and the walker charged zero for the inter-track hop — a 17 mm connection measured 2.6 mm across 307 junctions. Charging every join/pad/via edge its true length restores `pl ≥ gap`. Over 329 connections: p10 1.10×, median 1.28×, **0 below 1**. |
| The metamorphic relations hold | Executed: **40 of 40** checks across 8 seeds. Relaxing clearance improved the count on every seed (worst 12→7). |
| The verification layer catches what it claims | **Executed — built and tested.** `backend/pcb_engine/verify.py` + `tests/test_pcb_verify.py`, 17 tests. Each defect (unrouted connection, cross-net short, netless pad the netlist named, pin collision, pin-order-with-no-pinout, courtyard overlap/escape, asymmetric pads, land-pattern disagreement) is planted in a minimal board and the matching check is asserted to fail. The shipped `dht22_relay_monitor` passes every decidable check; generation now reports **12/12 routed** against the router's own 8/12. |

Test board: `interf_u.kicad_pcb` from KiCad's bundled demos. Run in a scratch directory;
nothing in the KiCad installation was modified.

**The trap worth carrying into the code:** a CI step that runs DRC without
`--exit-code-violations` exits 0 on a board with 28 real violations. If the export-then-check
path is added, the flag is not optional.

---

## Verified against sources

Verdicts are for the claim as the report states it.

### Routing quality metrics

| Claim | Verdict |
|---|---|
| Routability and wirelength are treated as distinct metrics in router evaluation | **Confirmed.** ISPD 2008 ranks on total overflow with wirelength as tie-breaker only; Groeneveld (IEEE-EDPS 2005) argues wirelength is less significant than overflow for routing. |
| The standard floor is a geometric lower bound (HPWL / RSMT) | **Confirmed**, with one correction below. |
| HPWL ≤ RSMT ≤ MST, and MST ≤ (3/2)·RSMT | **Confirmed** (Hwang's bound). |
| **MST and the 1-Steiner tree are lower bounds** | **REFUTED — this was the report's error.** Adding Steiner points can only shorten a tree, so RSMT ≤ MST: a spanning tree sits *above* the optimum as an estimate, not below it as a floor. Only HPWL and RSMT are genuine lower bounds. Corrected in the report. |
| FLUTE computes RSMT, is free and open | **Confirmed.** Exact up to nine pins, heuristic beyond (every net here is inside that). OpenROAD's `flute3` fork is BSD-3-Clause; the original Iowa State release uses an Attribution Assurance licence. |
| GeoSteiner is an exact RSMT solver, free for academic but not commercial use | **Confirmed.** CC BY-NC 4.0, © 1998–2023 Warme/Winter/Zachariasen. |
| BFS as a reachability oracle and Dijkstra as a cost oracle for a single net | **Confirmed.** The ISPD 2000 exact-switchbox work formalises "routable iff the exact formulation has a solution" and uses that to separate no-solution from heuristic failure. |
| Rip-up-and-reroute with net ordering is the standard technique | **Confirmed**, with the nuance that modern practice constructs topologies with FLUTE/RSMT and routes with maze search more often than with Prim. |

### Fabrication and DFM

| Claim | Verdict |
|---|---|
| IPC-2221 holds the conductor-width-versus-current charts | **Confirmed**, and the standard is paywalled though the charts circulate freely. |
| IPC-2152 (2009) supersedes those charts | **Confirmed.** IPC published it explicitly to replace 1950s-era data, adding board thickness, material and adjacent-copper effects; IPC-2221C now defers to it. |
| The IPC-2141A microstrip formulas are accurate to a fraction of a percent | **Corrected.** IPC-2141A's **2018 errata deleted its own printed ±2% / ±1.5% / ±1% accuracy claims**, and comparisons measure errors up to tens of percent for wide lines. Corrected in the report. |
| JLCPCB publishes 0.10/0.10 mm minimums | **Confirmed**, and this is the current minimum rather than a rounded-down one — so "5/5 mil" is the conservative figure, not the limit. Also confirmed: 0.15 mm minimum drill, ≥0.20 mm annular ring on plated holes. |
| PCBWay publishes comparable minimums | **Confirmed.** 0.10/0.10 mm, 0.15 mm drill, 0.15 mm minimum annular ring. |
| kicad-druid is a real, free, MIT-licensed KiCad rule-file set for fabs | **Confirmed** (JLCPCB, PCBWay, plus a generic set). Caveat: it is a small personal project, so "widely relied upon" would be unsupported. |
| IPC-356 netlist-versus-Gerber comparison | **Confirmed.** The format is IPC-D-356B, *Bare Substrate Electrical Test Data Format*, and Sierra Circuits' Better DFM performs exactly this comparison. The report's claim that no *open-source* tool does it stands — the working one found is hosted. |

### Trace parasitics and bench measurement

| Claim | Verdict |
|---|---|
| FastHenry2 is free, computes R and L of arbitrary 3D conductors, Windows build exists | **Confirmed** — Win64 bundle v5.2.0. Licence is **not** MIT as the original question assumed: sources are per-branch, largely LGPL. |
| FastCap2 / FasterCap are free capacitance extractors | **Confirmed**, same bundle and same licence caveat. |
| Trace R is tens of milliohms; trace L is a few nH/cm | **Confirmed.** 1 oz Cu ≈ 0.49 mΩ/square; 30 mm × 0.5 mm ≈ 60 squares ≈ 29 mΩ. Microstrip over a plane ≈ 3 nH/cm; an ungrounded wire can reach ~12 nH/cm, so "a few nH/cm" understates the no-plane case. |
| **Trace parasitics sit three or more orders of magnitude below component tolerance** | **PARTLY REFUTED — corrected in the report.** See the arithmetic below. |
| Four-wire Kelvin measurement resolves sub-milliohm | **Confirmed** in principle; a 6.5-digit bench DMM in 4-wire mode resolves tens of µΩ, and a documented DIY current-source-plus-DMM build reaches ~1 mΩ. |
| A NanoVNA's TDR cannot resolve features on a few-cm trace | **Confirmed.** Resolution is set by rise time (~0.35/BW); the realisable separation is comparable to or larger than the round-trip delay of a few cm of FR-4. |
| TI's RS-485 stub rule | **Confirmed exactly:** stub < 1/10 of the driver output rise time (SLLA272D). A companion note (SNLA042A) gives the more permissive 1/3 of transition time. |
| Trace-heating experiments at a few hundred mA are not meaningful | **Confirmed.** At 300 mA a 0.5–1 mm trace sees a rise on the order of 1 °C, dominated by ambient; IPC-TM-650 2.5.4.1 and TI SBOA533 both warn that copper traces are unsuitable for accurate low-current measurement. |

#### The one arithmetic correction

The report's opening line claimed trace parasitics sit "three or more orders of magnitude
below component tolerance." Using 29 mΩ for the reference trace against 1%-tolerance parts:

| Circuit | Part | 1% band | Trace R ÷ band | Orders |
|---|---|---|---|---|
| LED blink | 330 Ω series | ±3.3 Ω | 0.0088 | 2.1 |
| RC low-pass, 1 kHz | 1.59 kΩ | ±15.9 Ω | 0.0018 | 2.7 |
| Divider | 10 kΩ ×2 | ±100 Ω | 0.00029 | 3.5 |
| DHT22 node | 10 kΩ pull-up | ±100 Ω | 0.00029 | 3.5 |
| RS-485 node | 120 Ω termination | ±1.2 Ω | 0.024 | **1.6** |

The true range is **1.6 to 3.5 orders**, not "three or more". The inductive term is
negligible by comparison (36 nH at 1 kHz is ≈ 226 µΩ). The report's *conclusion* is
unaffected — trace parasitics are still far too small to make a bench test informative —
but the headline number was wrong and is now stated as a range with the RS-485 termination
named as the tightest case.

### Router software testing

| Claim | Verdict |
|---|---|
| Differential testing is recognised for EDA software | **Confirmed, and stronger than expected.** Cir-Fuzzer applies it across KiCad and ngspice tool chains with functionally equivalent circuit variants and found 12 real defects. Original technique: McKeeman 1998. |
| Metamorphic testing addresses the oracle problem and is applied to graphs and EDA | **Confirmed.** Shortest-path and MST are the motivating examples (Chen et al., ICSE'18); EDA applications exist in Verilog (VeriEQ) and shader compilers (FSHADER). |
| Property-based testing applies to graph/geometry invariants | **Confirmed.** Hypothesis, actively maintained, MPL-2.0. |
| Certifying algorithms are a named concept with a canonical reference | **Confirmed exactly.** McConnell, Mehlhorn, Näher & Schweitzer, *Computer Science Review* 5(2):119–161, 2011, DOI 10.1016/j.cosrev.2010.09.009. |
| Mutation testing for Python is free and available | **Confirmed.** `mutmut` BSD-3-Clause, `cosmic-ray` MIT, both releasing through 2026. |
| Benchmark corpora are the norm over random boards | **Confirmed.** ISPD contests, VTR circuit sets, PCBWorld. |
| Router testing fixes placement so only routing is under test | **Confirmed.** VPR/VTR documents a routing-only mode from a supplied `.place` file, and SPEC CPU 2026 formalises it (734.vpr_r). |
| Metamorphic testing has been applied to PCB routing specifically | **Not found** — unchanged from the first pass. The relation list in the report remains derived, not borrowed. |

---

## What still rests on the first pass alone

Stated plainly rather than smoothed over.

1. **Metamorphic testing applied to PCB routing.** No publication found, in either pass.
   The relations in the report are sound reasoning from the graph cases, but they are not
   borrowed from a routing paper.
2. **No source publishes a "good" wirelength-to-floor ratio for PCBs.** The report's
   "1.0 to 1.3 is probably fine" is judgement anchored on the spread across routers, and
   should be read as such.
3. **The licence of PCBWorld's bundled boards was never established.** Check before
   redistributing them.
4. **No published hobby-scale experiment of the generated-versus-reference-versus-control
   shape was found.** The proposed protocol is a proposal.
5. **No published error figures comparing free field solvers against measurement on FR-4.**
   Validate any FastHenry setup against a structure with a known analytic answer first.
6. **The claim that KiCad silently drops a custom rule file** comes from kicad-druid's own
   README and was not independently reproduced in this pass. It is plausible and cheap to
   test — the same sentinel-rule check the report recommends would settle it locally.
7. ~~**The suspected track-to-track pre-filter defect** in the DRC kernel is still a reading of
   the source, not a confirmed bug. It needs the seeded-violation test before it is believed.~~
   **Resolved — confirmed by execution.** The broad phase pads by `t.width` while the narrow
   phase requires `clearance + w1/2 + w2/2`; whenever `clearance > (w1+w2)/2` real violations
   are skipped unmeasured. Two parallel 0.2 mm tracks at clearance 0.25 mm: separations
   0.40–0.44 mm are violations and `drc()` reports none. See `drc_prefilter.py`.
8. **"Random test-case generation is only as good as the generator"** is widely implied but
   has no single canonical citation. Treat it as a working assumption, not a finding.
9. **Cost figures for fabrication in India** still come from an Indian vendor's own
   comparison page — undated, competing with the fabs it compares, and internally
   inconsistent on duty. No official customs source was reached.

None of these undermine the report's ladder, which rests on checks that are executable
locally and free. They mark where a claim is an informed judgement rather than a citation.
