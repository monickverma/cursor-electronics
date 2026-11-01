# Software-testing and verification methodology for a PCB autorouter and layout engine (as of October 2026)

Scope note: research notes for a report writer. Every fact under "Cited Findings" carries a source. Anything from
general knowledge that I could not source in this pass is under "Inferences" or "Gaps" and is marked as such.
Local-code observations cite the file in this repository; they were read, not run.

Legend used below: **[E]** = established practice, **[R]** = research idea / thin evidence.

---

## 1. The oracle problem for routers: what can be checked independently, and how to build a checker that shares no code with the router

### Takeaway
A routing result is cheap to check even though it is hard to produce, so the right architecture is "check the answer, not the algorithm": the router emits geometry, and a separately written checker decides opens, shorts, clearance, board containment and via/layer legality. In this repository the router currently imports `drc` and `score` from the same kernel it is judged by, so the check is not yet independent.

### Cited Findings
- **[E]** A certifying algorithm "produces, with each output, a certificate or witness (easy-to-verify proof) that the particular output has not been compromised by a bug"; the user checks that the witness proves the output correct for the input. The authors' thesis is that for complex algorithmic tasks only certifying algorithms are satisfactory. (McConnell, Mehlhorn, Näher, Schweitzer, *Computer Science Review* 5(2), 2011, pp. 119-161.) — [ANU record of the paper](https://researchportalplus.anu.edu.au/en/publications/certifying-algorithms/)
- **[E]** The checker is a separate program C that accepts the triple (input x, output y, witness w) if and only if w is a valid witness for y = f(x); LEDA adopted exact computation and certifying algorithms as design principles in 1995. — [Mehlhorn slides, 2014](https://people.mpi-inf.mpg.de/~mehlhorn/ftp/UVMSept2014.pdf)
- **[E]** Canonical example of a two-sided certificate: a bipartiteness algorithm returns a two-colouring when the graph is bipartite and an odd cycle when it is not — both verdicts are checkable. — [UCI theory seminar abstract](https://ics.uci.edu/~theory/269/120127.html)
- **[R→E]** Follow-up work formally verified the checkers themselves (Alkassar, Böhme, Mehlhorn, Rizkallah, "A framework for the verification of certifying computations", *J. Automated Reasoning* 52(3):241-273, 2014). — [Mehlhorn talk abstract, UMD](https://www.cs.umd.edu/event/2014/08/certifying-computations-algorithmics-meets-software-engineering)
- **[E]** Differential testing: McKeeman, "Differential Testing for Software", *Digital Technical Journal* 10(1):100-107, 1998 — several implementations are run on the same input and a disagreement means at least one is wrong; the failing input is then reduced. — [DBLP record](https://dblp.org/pid/40/4856); [McKeeman patent describing the method](https://patents.google.com/patent/US5754860)
- **Local code:** `router.py` imports `drc, score, Score, Weights` from `kernel`, and its docstring states the design intent "Every output can be checked exactly by kernel.drc(). So you never have to trust the solver". — `C:\Users\KIIT\cursor-electronics\backend\pcb_engine\router.py` (lines 21-23, 53)
- **Local code:** `kernel.drc` works in floating-point millimetres with hand-written segment distance primitives and a bounding-box pre-filter. — `C:\Users\KIIT\cursor-electronics\backend\pcb_engine\kernel.py` (lines 34-76, 100-129)
- **Local state:** the project's own plan records that the A* router completes 6 of 14 room-monitor connections, the rest drawn as ratsnest. — `C:\Users\KIIT\cursor-electronics\.claude\shared-memory\plan\current_phase.md` (line 60)
- Shapely's `set_precision(geometry, grid_size, mode='valid_output')` snaps geometry to a fixed grid; default geometries are double precision (grid_size = 0); polygons narrower than the grid can collapse. — [Shapely docs](https://shapely.readthedocs.io/en/2.1.1/reference/shapely.set_precision.html)

### Inferences
- **Checkable properties of a routed board that need no knowledge of how it was routed** (the "specification" of routing):
  1. *Connectivity equals netlist.* Partition all copper (pads, track segments as buffered capsules, vias as discs on both layers) into electrically connected components. Required: every component contains pads of exactly one net (no shorts) and every net's pads fall in exactly one component (no opens). This is a pure graph statement — union-find over "touches on the same layer" plus "via joins layers".
  2. *Clearance.* For every pair of copper shapes in different components on the same layer, distance >= required clearance.
  3. *Containment.* Every copper shape lies inside the board outline shrunk by edge clearance.
  4. *Legality.* Widths >= minimum; vias only between existing layers, drill/annulus within limits; no copper on a layer the board does not have; track ends land on a pad or another same-net track (no dangling stubs); pads entered on the layer they exist on (SMD pad on bottom cannot be reached by a top track without a via).
  5. *Faithfulness.* Pads, footprints and outline in the output are bit-identical to the input (the router may add copper, never move parts or drop nets).
  6. *Honesty of the completion report.* The set the router says it failed to route equals the set of opens the checker finds.
- **Two cheap, mutually independent checker designs** (neither shares arithmetic with the A* grid or with `kernel.py`):
  - *Polygon checker (Shapely/GEOS):* `LineString(points).buffer(width/2)` for tracks, `Point.buffer(d/2)` for vias, pad rectangles as polygons; per layer build an `STRtree`; connectivity = union-find over `intersects` pairs; clearance = `a.distance(b) >= req` for different-component pairs; containment = `outline.buffer(-edge).covers(shape)`. Round caps are approximated by polygons, so the checker must state its chord error (e.g. 64 segments per quadrant) and treat results within that band as "undecided", not pass.
  - *Raster checker (numpy/scipy):* rasterise each layer at a pitch much finer than the router's 0.25 mm grid (e.g. 10-25 µm) and *not* an integer divisor of it, label connected components with `scipy.ndimage.label`, check each label covers pads of one net; clearance = dilate each net's mask by the clearance radius and test overlap with other nets. Resolution error is bounded by one pixel diagonal, which must be stated.
  - The two disagreeing on a board is itself a finding — this is 3-version voting among `kernel.drc`, the polygon checker and the raster checker.
- **Why independence matters here specifically:** the router's obstacle map and the kernel's DRC encode the *same* author's understanding of "clearance" (halo = clearance + half-widths). A misunderstanding shared by both (e.g. forgetting via annulus on the far layer, or measuring to track centreline) passes silently. The project already applies this reasoning elsewhere (ngspice vs `predict()`); the routing equivalent is a checker written against the Board IR spec only, ideally by reading the IR, not the router.
- **Candidate defect found by reading (to confirm with a test, not asserted as fact):** in `kernel.drc` the track-track pre-filter pads each bounding box by `t.width`, while the violation threshold is `clearance + w1/2 + w2/2`. Two boxes overlap only when the gap is <= w1 + w2, so a violation with centreline separation between `w1 + w2` and `clearance + (w1+w2)/2` would be skipped whenever `clearance > (w1+w2)/2` — e.g. two necked-down 0.127 mm tracks under a 0.2 mm clearance, separation 0.26-0.32 mm. This is exactly the class of false negative that an independent checker or seeded-violation test exposes.
- A known limit of independence: N-version experiments (Knight and Leveson, 1986) found that independently written versions fail on correlated inputs more often than independence predicts — so diverse *methods* (vector vs raster vs external tool) are worth more than diverse *authors* of the same method. (Unsourced in this pass; see Gaps.)

### Gaps
- I did not retrieve a primary source for Knight and Leveson's N-version experiment or for Blum and Kannan's "program checkers" in this pass; both are standard references the writer may cite from the literature directly (Knight & Leveson, IEEE TSE 12(1), 1986; Blum & Kannan, JACM 42(1), 1995) but I have not verified page-level claims.
- No published PCB router was found that ships a formally separate, independently authored result checker as a stated design principle; the closest documented practice is DRC-as-a-separate-engine inside the same tool (KiCad, Freerouting's `-drc` report).
- pyclipper (Clipper bindings, integer coordinates) is a plausible third polygon backend; I did not fetch its documentation or licence in this pass.

---

## 2. Differential testing against reference tools (Freerouting, KiCad) and comparing DRC verdicts fairly

### Takeaway
Freerouting is a practical second router and second DRC: GPL-3.0, headless via `--gui.enabled=false -de in.dsn -do out.ses`, with a `-drc` report in KiCad JSON format and a documented 0-1000 board score. KiCad's `kicad-cli pcb drc --exit-code-violations` gives a third DRC verdict; the repository already has a `to_dsn()` bridge, so the missing pieces are an SES reader and a `.kicad_pcb` writer.

### Cited Findings
- Freerouting is licensed GPL-3.0; it requires Java 25 (JRE from Adoptium); the README documents `-de [design input file]` (Specctra `.dsn`), `-do [design output file]` (`.ses`), `-inc [net class names]`; example `java -jar freerouting.jar -de MyBoard.dsn -do MyBoard.ses -inc GND,VCC`. — [freerouting/freerouting README](https://github.com/freerouting/freerouting)
- Headless and batch flags: `--gui.enabled=false`; `-mp <n>` maximum autorouter passes; `-mt <n>` optimizer threads (`0` disables route optimization); `-drc <file>` "writes the design rules check report as KiCad JSON DRC"; `-is <sequential|random|prioritized>` item selection strategy; `--router.optimizer.improvement_threshold=<percent>` (default 2.5). Exit codes are not documented. — [Freerouting command-line arguments](https://github.com/freerouting/freerouting/blob/master/docs/command_line_arguments.md)
- Freerouting has a REST API: hosted at `https://api.freerouting.app/v1` (beta, access on request) and self-hostable with `--api_server.enabled=true` (default bind `http://127.0.0.1:37864`, API-key auth on by default); official Python client `pip install freerouting-client`. — [Freerouting README](https://github.com/freerouting/freerouting); [command-line arguments](https://github.com/freerouting/freerouting/blob/master/docs/command_line_arguments.md)
- Freerouting publishes how it scores a board. Router score: `max(0, 1000 − W1·o1 − W2·o2 − W_C·(N_viol/D) − W_D·(…))` with unrouted-connection weights 333.3 and 666.7, 25 points per clearance-violation pair, a depth term over summed shortfall in micrometres, and scale `D = max(1, pins × signal layers)`. Optimizer score: `1000 − ΔL − ΔV − ΔB`, where wire length is compared with a lower bound from placement (100% over the minimum costs the full 1000), each extra via costs 2000/D and each extra bend 500/D; incomplete connections and DRC violations act as vetoes rather than score terms. — [Freerouting docs/scoring.md](https://github.com/freerouting/freerouting/blob/master/docs/scoring.md)
- `kicad-cli pcb drc` runs DRC on a board and writes a report; with `--exit-code-violations` the exit code is 0 if no violations are found and 5 if any are. — [KiCad 9.0 CLI reference](https://docs.kicad.org/9.0/en/cli/cli.html); [KiCad 10.0 CLI reference](https://docs.kicad.org/10.0/ca/cli/cli.html)
- One user report (not official): CLI DRC ignored GUI-configured exclusions and gave different counts from the GUI. — [KiCad forum thread](https://forum.kicad.info/t/cli-erc-drc-gives-different-output-than-running-manually-in-gui/55207)
- KiCad's own DRC regression test checks that a reported hole-to-hole error message contains the configured minimum value and *not* the value after "the DRC epsilon is subtracted" — i.e. KiCad's DRC applies an internal epsilon to thresholds. — [KiCad `test_drc_regressions.cpp`](https://docs.kicad.org/doxygen/test__drc__regressions_8cpp_source.html)
- **Local code:** the repository already contains `to_dsn(board)` and a `RouterBackend` protocol (`route(board, seed, time_budget_s) -> Board`); the plan lists Freerouting through DSN/SES as step B5 and `.kicad_pcb` export as B4. — `C:\Users\KIIT\cursor-electronics\backend\pcb_engine\router.py` (lines 59-63, 499); `C:\Users\KIIT\cursor-electronics\.claude\shared-memory\plan\current_phase.md` (lines 54-56)

### Inferences
- **A fair differential protocol** (same placement, three judges):
  1. Export one placement to DSN. Route with (a) the A* router, (b) Freerouting headless with fixed `-mp`, `-mt 0` for a first comparison without the optimizer, then with it.
  2. Import both results into the Board IR. Judge *both* with `kernel.drc`, with the independent checker from section 1, and — once B4 exists — with `kicad-cli pcb drc`. That gives a 2 routers × 3 checkers matrix; any cell that disagrees with its row or column is a bug in exactly one identifiable component.
  3. Compare: completion (connections routed / total), total length vs. Freerouting's placement lower bound, via count, violation count.
- **What each comparison can and cannot show.** "Freerouting routed it and we did not" is evidence of a false "unroutable" from A* *under Freerouting's rules*; it is only a fair verdict if rules were mapped identically. "Neither routed it" proves nothing (both are heuristics). "We routed it and Freerouting's DRC flags our result" is the most valuable cell: an independent engine disagreeing with `kernel.drc`'s pass.
- **Rule mapping checklist for fair DRC comparison:** same clearance per net class; same track width; same via pad and drill; same edge clearance (the kernel default is 0.3 mm, `drc(board, edge_clearance=0.3)`); same treatment of same-net spacing (usually unchecked); disable categories the other engine has no notion of (silkscreen, courtyard, library mismatch, unconnected-items if opens are compared separately). KiCad's own tests do exactly this — they set unrelated severities to ignore before counting (see section 10).
- **Tolerance policy:** compare *categories and locations*, not raw counts — engines group violations differently (per segment pair vs per track pair; `kernel.drc` breaks after the first segment pair per track pair). Match violations by (rule class, net pair, location within a few track widths). Classify each board as agree-clean / agree-dirty / disagree, and report a confusion matrix. Treat any violation whose measured shortfall is below a declared band (e.g. 1 µm, or the DSN export resolution) as "boundary" and report it separately — neither a pass nor a disagreement.
- **Licence hygiene:** Freerouting is GPL-3.0; invoking the jar as a separate process and exchanging DSN/SES files is the same arm's-length pattern the project uses for ngspice. Bundling it in a distributed image is a distribution question for the owner, not a testing question. (This is my reading, not legal advice, and not from a cited source.)
- Freerouting's `-is random` vs `sequential` item selection gives a built-in way to measure *its* order sensitivity for comparison with A*'s (section 5).
- Java 25 is a new runtime dependency for CI; a Docker image avoids installing it on the Windows dev machine.

### Gaps
- Freerouting's exit codes and how a headless run signals "incomplete" are not documented on the pages fetched; the SES file and `-drc` JSON must be parsed to learn the outcome.
- I did not find a document describing Freerouting's own automated test suite or regression fixtures (the README only points to scoring and CLI docs).
- I did not verify the KiCad Python API situation (the SWIG `pcbnew` module vs the newer IPC API `kicad-python`) in this pass; `kicad-cli` is the route I can source.
- No published study was found that differentially tests two PCB DRC engines against each other and reports disagreement rates.

---

## 3. Property-based testing with Hypothesis and metamorphic relations for routers and geometric code

### Takeaway
Metamorphic testing is the established answer to "no ground truth" and has been applied to grid path planners and multi-agent path finding with published fault-detection results, but I found no publication applying it to place-and-route; the relations transfer directly. Hypothesis supplies generation, shrinking to a minimal failing board, and stateful (rule-based) testing for edit sequences.

### Cited Findings
- **[E]** Segura, Fraser, Sánchez, Ruiz-Cortés, "A Survey on Metamorphic Testing", IEEE TSE 42(9):805-824, 2016 (DOI 10.1109/TSE.2016.2532875): metamorphic testing addresses the oracle problem by checking relations between the outputs of multiple executions; metamorphic relations were introduced in 1998. — [White Rose open-access copy](https://eprints.whiterose.ac.uk/110335/1/segura16-tse.pdf)
- **[E]** Chen, Kuo, Liu, Poon, Towey, Tse, Zhou, "Metamorphic Testing: A Review of Challenges and Opportunities", ACM Computing Surveys 51(1), 4:1-4:27, 2018 (DOI 10.1145/3143561). — [Nottingham ePrints](https://eprints.nottingham.ac.uk/51607)
- **[R, closest analogue]** Zhang, Zheng, Yin, Qiu, Liu, "Testing Graph Searching Based Path Planning Algorithms by Metamorphic Testing", IEEE PRDC 2019, pp. 158-167: a framework for designing metamorphic relations for graph-search path planning, six categories of relations, applied to 21 implementations of three path-planning algorithms from a released commercial software project; reports detecting dormant faults. — [Beihang record](https://research.buaa.edu.cn/en/publications/testing-graph-searching-based-path-planning-algorithms-by-metamor/)
- **[R]** Wu, Xi, Zheng, Li, "Application of Metamorphic Testing on UAV Path Planning Software", *Journal of Systems and Software* vol. 204, 2023: operation-based metamorphic relations for grid-search planners; injected faults were revealed and composed relations detected more than individual ones (as summarised in search results; I did not read the full text). — [Beihang record](https://research.buaa.edu.cn/en/publications/application-of-metamorphic-testing-on-uav-path-planning-software/)
- **[R]** MET-MAPF (ACM TOSEM 2024, DOI 10.1145/3669663; ASE 2025 journal-first): ten metamorphic relations for multi-agent path finding, over the environment, single-agent behaviour and agent interactions; finds violations not exposed by an oracle that only checks mission completion, and different relations expose different violations. The authors' motivation is that checking only collision-free arrival is insufficient because path quality matters. — [ASE 2025 listing](https://conf.researchr.org/details/ase-2025/ase-2025-journal-first-track/43/MET-MAPF-A-Metamorphic-Testing-Approach-for-Multi-Agent-Path-Finding-Algorithms)
- **[R]** MAPFFuzz (ICSE 2026): metamorphic fuzzing of MAPF solvers using metamorphic relations as oracles for solution quality; evaluated on PIBT, HCA, PIBT+ and LaCAM*. — [ICSE 2026 listing](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/313/Metamorphic-Fuzzing-for-Multi-Agent-Path-Finding-Algorithms)
- **[R]** "Mutation-Guided Metamorphic Testing of Optimality in AI Planning" (ICST 2025 journal-first): generates follow-up tests to detect non-optimal plans. — [ICST 2025 listing](https://conf.researchr.org/details/icst-2025/icst-2025-journal-first-papers/7/Mutation-Guided-Metamorphic-Testing-of-Optimality-in-AI-Planning)
- **[R, adjacent EDA]** Verismith fuzzes FPGA synthesis tools (Vivado, Yosys, Quartus) by generating random designs and equivalence-checking the output; its authors list metamorphic testing and later flow stages including place-and-route as future work. — [Verismith talk slides, Cambridge](https://www.cl.cam.ac.uk/~jpw48/talks/verismith_27nov2019.pdf)
- Hypothesis stateful testing: you define primitive actions as rules and Hypothesis "tries to generate not just data but entire tests"; `@invariant()` functions run after every step; a failure is reported as a very short program that reproduces it. — [Hypothesis stateful testing docs](https://hypothesis.readthedocs.io/en/latest/stateful.html)

### Inferences
- **Why MAPF is the right analogy:** multi-net routing on a grid is multi-agent path finding where each "agent" leaves its whole path behind as an obstacle. MET-MAPF's observation — completion-only oracles miss quality faults — applies verbatim to "all nets connected, DRC clean".
- **Generators (Hypothesis strategies), in increasing difficulty:**
  - *Routable by construction:* draw random non-crossing paths on a coarse grid first, then place pad pairs at their ends and delete the paths. Every generated board has a known witness routing, so "router says unroutable" is always a false negative. This is the single most useful generator because it manufactures ground truth.
  - *Random placements:* N two-pin footprints on a W×H board with rejection of overlaps; nets = random perfect matching over pads; then multi-pin nets.
  - *Adversarial shapes:* crossing pairs that force a via (X pattern), a pad ring with one gap, a corridor exactly one track + two clearances wide (and one grid step narrower), pads off the 0.25 mm grid.
  - Keep sizes tiny (2-6 nets, boards of a few hundred cells) — shrinking is only useful when the minimal failing board is readable.
- **Unconditional invariants (hold for every output):** the six checker properties of section 1; idempotence of re-checking; determinism (same board + same seed → byte-identical tracks; the router takes a `seed`); `route()` never mutates its input board; reported unrouted set equals checker opens; a board with zero nets returns zero tracks; routing an already-routed board adds nothing.
- **Metamorphic relations, with the honest strength of each** (a heuristic router need not be exactly invariant, so each relation is stated at the level that must hold):

  | Transformation of the input | Must hold exactly (checker verdicts) | Should hold statistically (quality) |
  |---|---|---|
  | Translate board by a multiple of the grid pitch | completion set identical, lengths identical | — (exact) |
  | Translate by a non-multiple of the pitch | output still DRC-clean | completion rate unchanged over many boards |
  | Rotate 90/180/270°, mirror X/Y | output still clean; for a *single* net, path length equal to the BFS optimum either way | multi-net completion equal in distribution |
  | Permute net order / relabel net names | output still clean; names must not affect geometry | completion varies — measure it (section 5) |
  | Swap start and goal of a 2-pin net | single-net length identical | — |
  | Remove one net from the request | every remaining route of the *previous* solution is still a valid solution → the smaller problem is routable; a router that now fails has a false negative | completion fraction non-decreasing |
  | Add an obstacle / component far from all route corridors (outside every net's bounding box plus margin) | previously routable stays routable | lengths unchanged |
  | Add an obstacle anywhere | — | optimal single-net length non-decreasing (exact, vs BFS) |
  | Enlarge the board outline | routable stays routable (old solution still valid) | — |
  | Reduce clearance or track width | routable stays routable (old solution still valid) | — |
  | Halve the grid pitch | old solution's cells are a subset of the finer grid → routable stays routable | length non-increasing for a single net |
  | Scale all geometry and rules by k | checker verdicts identical | — |
  | Feed the router's own output back as fixed copper and ask for the remaining nets | previous tracks untouched | — |

  The "old solution is still valid" rows are the strong ones: they are *theorems about the problem*, so a violation is a router false negative with a concrete witness in hand — no reference tool needed.
- **Metamorphic relations for the DRC kernel itself** (these should be exact up to the declared epsilon): verdict invariant under rigid motion; invariant under reversing a track's point order; invariant under splitting a segment at an interior point; invariant under permuting the track list; monotone in clearance (raising the requirement never removes a violation); symmetric (`d(a,b) = d(b,a)`); `seg_seg_dist` agrees with a brute-force sampled distance and with Shapely's `LineString.distance` within tolerance.
- **Stateful testing fits step B2** (board edits as patch operations re-checked by the DRC kernel): rules = move / rotate / flip / route / rip-up; invariants after every step = checker clean or violations reported, IR round-trips through JSON, undo restores the hash.
- Run sizes: a few hundred examples per property in CI, a nightly run with a much larger `max_examples` and a persisted example database so past failures are replayed first.

### Gaps
- I could not retrieve the list of the six relation categories (Zhang et al. 2019) or the three operation-based relations (Wu et al. 2023) — only abstract-level descriptions; the exact relations should be read from the full texts before being quoted.
- No paper applying metamorphic testing to PCB routing, VLSI detailed routing, or DRC engines was found; the relation table above is my derivation, not literature.
- Hypothesis's documentation of the shrinking algorithm itself was not on the page fetched.

---

## 4. Optimality checks on small instances: exact shortest paths and exact multi-net routing (SAT / ILP / SMT)

### Takeaway
Single-net optimality is fully checkable today (BFS/Dijkstra on the same grid is an exact oracle for A*). Exact multi-net routing by SAT is established in the literature for FPGA detailed routing, PCB escape routing and Numberlink-style puzzles, and its key benefit for this project is that an UNSAT result is a *proof* of unroutability on that grid — but I found no published exact formulation of full PCB detailed routing with design rules, and no Python/z3/CP-SAT PCB example.

### Cited Findings
- **[E]** SAT-based FPGA detailed routing (Nam, Sakallah, Rutenbar line of work, and Singhee/Rutenbar's search-based SAT formulation) considers all nets simultaneously, can prove unroutability, and was compared against ILP-based routing. — [IBM Research record](https://research.ibm.com/publications/a-new-fpga-detailed-routing-approach-via-search-based-boolean-satisfiability)
- **[E]** The stated advantage of SAT routing over sequential routers: "simultaneous embedding of all nets regardless of net ordering" and the ability to demonstrate infeasibility by proving the routing constraint function unsatisfiable. — [US patent 7,904,867 background](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7904867)
- **[E]** Luo and Wong, "Ordered Escape Routing Based on Boolean Satisfiability", ASP-DAC 2008: PCB escape routing cast as SAT (CNF) to solve it exactly; notes earlier (partly ILP-based) methods could miss feasible solutions such as ones needing a detour; industrial escape instances are moderate in size, which makes SAT viable. — [ASP-DAC 2008 paper](https://www.cecs.uci.edu/~papers/aspdac08/pdf/p244_3A-4.pdf)
- **[R]** Berkeley technical report ERL-99-16 (1999): multi-layer area routing for PCBs/MCMs as SAT, Boolean variables over predetermined candidate route patterns with 2 to 4 vias, nets routed simultaneously in clusters — a decomposition, not globally exact. — [UCB/ERL M99/16](https://www2.eecs.berkeley.edu/Pubs/TechRpts/1999/ERL-99-16.pdf)
- **[R]** Set-pair routing (a PCB problem) has exact ILP and SAT formulations; the SAT version needs a huge number of length-control constraints and runs out of memory when the routing area is large (IEICE 2023). — [IEICE technical report listing](https://ken.ieice.org/ken/paper/20231117KCYA/eng/)
- **[E]** Size reference for exact routing: Sulimma and Kunz, "An exact algorithm for solving difficult detailed routing problems" (ISPD 2001) — optimal channel routing for channels up to about 13 tracks within minutes. — [Frankfurt University record](https://publikationen.ub.uni-frankfurt.de/frontdoor/index/index/year/2006/docId/2884)
- **[E]** A 2014 IEEE TCAD paper routes standard cells with a Boolean formulation and a dedicated encoding to make large cells tractable. — [TCAD 2014 paper](https://www.cs.upc.edu/%7Ejordicf/gavina/BIB/files/tcad2014_Routing.pdf)
- **[R]** Single-layer escape routing is optimally solvable by max-flow; multi-layer is harder because vias are wider than wires (noted in a 2024 paper on DRAT proofs for SAT modulo monotonic theories — which also shows unsatisfiability proofs can themselves be emitted and checked). — [arXiv 2401.10703](https://arxiv.org/pdf/2401.10703)
- Numberlink / Flow Free (connect pin pairs on a grid with vertex-disjoint paths — the puzzle form of single-layer two-pin routing) has several exact encodings: a SAT-based constraint solver via Copris/Sugar/GlueMiniSat (IPSJ 2014); a Picat SAT model reported much faster than CP and MIP variants of the same model; a 2025 LIACS thesis on SAT for arbitrary Numberlink puzzles. — [IPSJ DAS 2014 paper](https://ipsj.ixsq.nii.ac.jp/record/102780/files/IPSJ-DAS2014040.pdf); [Picat numberlink model](https://hakank.org/picat/numberlink.pi); [LIACS thesis](https://theses.liacs.nl/pdf/2025-2026-LelipalyJJoshua.pdf)
- **Local code:** `astar(grid, start, goal, …)` has an inner heuristic `h(li, iy, ix)` and operates on `(layer, iy, ix)` cells of a `Grid` with resolution 0.25 mm. — `C:\Users\KIIT\cursor-electronics\backend\pcb_engine\router.py` (lines 69-76, 220-227)

### Inferences
- **Single-net oracle (do this first, it is an afternoon):** run plain Dijkstra with the *same* edge costs (step, diagonal, via, bend if costed) on the same obstacle mask and assert `cost(A*) == cost(Dijkstra)` for thousands of random start/goal/obstacle instances. A* returns optimal paths only if the heuristic never overestimates (admissible) and, when nodes are closed on first expansion, is consistent. The classic defects this catches: Manhattan heuristic with diagonal moves allowed (overestimates), heuristic ignoring that a via may be cheaper than its estimate, tie-breaking weights > 1 (deliberately inadmissible — then assert a bounded suboptimality factor instead), and bend penalties not carried in the search state (cost depends on arrival direction, so state must include direction or the result is not optimal even with Dijkstra on the reduced state). Admissibility itself is directly testable: for random cells assert `h(n) <= dijkstra_distance(n, goal)`; consistency: `h(n) <= c(n,m) + h(m)` for every edge.
- **Reachability oracle:** BFS on the passable mask decides whether *any* path exists; `astar` returning "no path" where BFS finds one is an unambiguous bug, and vice versa.
- **Exact multi-net formulation that fits tens of nets on a tiny 2-layer grid** (my design, modelled on the Numberlink encodings; not from a PCB paper): Boolean `x[v][n]` = cell v (layer, y, x) carries net n; at most one net per cell; each terminal of net n has `x=1` and exactly one same-net neighbour, each non-terminal used cell exactly two (path shape) — or a flow formulation for multi-pin nets; via edges between layers consume both cells; clearance handled by pre-dilating so that adjacent cells of different nets are forbidden. Degree constraints alone admit detached cycles, which is harmless for *feasibility* (delete the cycle) but must be excluded or ignored when minimising length. In OR-Tools CP-SAT, minimise the number of used cells (+ via weight) for the optimum; in z3 or PySAT, ask satisfiability for routability.
  - *Use 1 — optimality gap:* `(router_length − optimal_length) / optimal_length` per board, reported as a distribution.
  - *Use 2 — proof of unroutability:* UNSAT means no routing exists **on that grid with those move rules** — it does not prove the continuous board is unroutable (a gridless router may fit a track the grid cannot). State this scope on every such claim.
  - *Use 3 — false-negative count:* SAT but router failed = a concrete missed solution, with the witness to replay.
- **Trusting the exact solver:** its SAT answers are certificates — decode the model into tracks and run them through the independent checker of section 1. UNSAT answers are harder to trust; cross-check the encoding by (a) agreeing with BFS on single-net instances, (b) never returning UNSAT on routable-by-construction boards (section 3), (c) agreeing between two encodings or two solvers (CP-SAT vs z3) — differential testing of the oracle. This mirrors the project's existing "mutation gate" on its z3 prover.
- **Practical size limits (my estimate, not sourced):** variables ≈ cells × nets. A 20 mm × 15 mm board at 0.25 mm pitch on 2 layers is 9,600 cells; with 14 nets that is ~134k Booleans — plausibly within CP-SAT's reach for feasibility, uncertain for proven optimality. Coarsen the pitch (0.5 mm) or crop to the congested window for exact work. The literature points the same direction: exact methods are reported on channels of ~13 tracks, escape regions and single cells, not whole boards.
- Lower bounds without a solver: sum over nets of the obstacle-aware single-net shortest path (each net routed alone on an empty board) is a valid lower bound on total length — the same idea as Freerouting's `L_min` from placement (section 2) — so `router_length / lower_bound` is a cheap gap *upper bound* on any board size.

### Gaps
- No published exact SAT/ILP formulation of full PCB detailed routing with clearance, widths, layers and vias, with optimality results on small benchmark boards, was found.
- No source was found using z3, PySAT or OR-Tools CP-SAT for PCB or Numberlink routing specifically; the encoding above is adapted, and its scaling on real boards is unmeasured.
- I did not source the standard A* admissibility/consistency theorems (Hart, Nilsson, Raphael 1968; Dechter and Pearl 1985) in this pass — they are textbook results the writer can cite directly.
- OR-Tools (Apache-2.0), z3 (MIT) and PySAT (MIT) licences are stated from memory, not verified in this pass.

---

## 5. Detecting false "unroutable" verdicts and measuring order-dependence

### Takeaway
Order-dependence of sequential routing is a textbook weakness — "the success of a route is dependent not just on the choice of which nets to reroute, but also on the order" — and negotiated-congestion (PathFinder) reduces but does not remove it. It should be *measured* as a distribution over net-order permutations, and a "could not route" should be reported as "not routed by this heuristic" unless an exact method (section 4) or a constructed witness says otherwise.

### Cited Findings
- **[E]** PathFinder (McMurchie and Ebeling): nets may initially share resources; the cost of an overused resource rises with present sharing and with accumulated history, so congestion is negotiated away over iterations; in the original formulation every net is ripped up and rerouted every iteration. — [TU Darmstadt lecture notes on PathFinder](https://www.esa.informatik.tu-darmstadt.de/archive/twiki/pub/Lectures/AlgorithmenImChipEntwurfDe/router-pathfinder.pdf)
- **[E]** Rip-up-and-retry's basic weakness: success depends on the order of rerouting as well as on which nets are chosen. — [UPenn ESE 535 lecture slides](https://www.seas.upenn.edu/~ese5350/spring2011/lectures/day12_6up.pdf)
- **[E]** In rip-up-and-reroute global routing, "the routing order … affects the solution quality a lot"; BoxRouter avoids part of this by routing all nets inside a growing box around the most congested region jointly via ILP. — [ASP-DAC 2008 paper (FastRoute/BoxRouter context)](https://websrv.cecs.uci.edu/~papers/aspdac08/pdf/p232_3A-2.pdf)
- **[R]** A 2014 ReConFig paper changes rip-up order to prioritise nets with two, three and more than eleven pins, reporting that those have the largest effect on routing quality. — [2014 ReConFig reordering paper](https://www.dejazzer.com/doc/2014_reconfig_reordering.pdf)
- **[E]** SAT routing embeds all nets simultaneously "regardless of net ordering" and can prove infeasibility — the order-free reference. — [US patent 7,904,867](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7904867)
- Freerouting exposes its item-selection strategy as a flag (`-is sequential|random|prioritized`). — [Freerouting command-line arguments](https://github.com/freerouting/freerouting/blob/master/docs/command_line_arguments.md)
- **Local code:** the router's own docstring states "It is *order-dependent*. Route net A first and net B may have no path left. There is no single right answer, only a distribution of answers indexed by ordering"; `AStarRouter._route_pass(board, order)` takes an explicit order, `route(board, seed, …)` a seed, and `generate_candidates(board, backend, n=8, …)` produces several candidates in a process pool. — `C:\Users\KIIT\cursor-electronics\backend\pcb_engine\router.py` (lines 16-19, 348, 406, 462)
- **Local state:** 6 of 14 room-monitor connections completed. — `C:\Users\KIIT\cursor-electronics\.claude\shared-memory\plan\current_phase.md` (line 60)

### Inferences
- **Four independent ways to catch a false "unroutable":**
  1. *Witness by construction* — boards generated from a known routing (section 3). Any failure is false.
  2. *Witness by another solver* — Freerouting or the exact solver routes it under mapped rules.
  3. *Witness by permutation* — some other net order routes it. One success among K orders proves the failures in the other K−1 were false.
  4. *Witness by monotonicity* — the router solved a strictly harder version (superset of nets, tighter clearance, smaller board).
  And one way to confirm a *true* "unroutable": UNSAT from the exact model on the same grid, or a topological argument (e.g. on a single layer, two nets whose terminals interleave on the boundary of a simply-connected region cannot both be routed — the planarity obstruction; a cut whose capacity in tracks is below the number of nets that must cross it).
- **Measuring order sensitivity (a permutation test):** for each board in the corpus, route under K random permutations of the connection list (K = 30-100; the router is seeded, so this is reproducible). Report per board: min / median / max completion, fraction of orders that fully route, coefficient of variation of total length, and "best-of-K" as a function of K (the curve tells whether `generate_candidates(n=8)` is leaving completion on the table). A board whose completion ranges from 6/14 to 14/14 across orders is an *ordering* problem; one stuck at 6/14 for every order is a *search-space* problem (grid too coarse, no via escape, pads off grid, halo too large) — the two need different fixes, and the experiment separates them cheaply.
- **Diagnosing the 6/14 specifically:** for each of the 8 failed connections, run BFS on (a) the empty board with only pads as obstacles, (b) the board with the committed routes. Unreachable in (a) = modelling bug (pad not on grid, pad's own halo sealing it, layer mismatch) — not a routing problem at all. Reachable in (a) but not (b) = blocked by earlier nets → ordering / rip-up. This single experiment classifies every failure.
- Rip-up-and-reroute changes the test surface: add invariants that a ripped net's stamps are fully removed from the occupancy grid (stale-obstacle bugs are the characteristic failure — check by rebuilding the grid from the final track list and comparing with the incrementally maintained one) and that the loop terminates within its budget.
- Report language should follow the project's existing "an unchecked rule is never a passed one": three verdicts — *routed (checked)*, *proved unroutable on grid G (certificate)*, *not routed by heuristic (no claim)*.

### Gaps
- I found no published measurement of completion-rate variance across net orderings for PCB autorouters specifically (the cited statements are qualitative, from FPGA/VLSI routing teaching material and papers).
- I did not retrieve the original McMurchie and Ebeling PathFinder paper (FPGA 1995) or Lee's maze-router and rip-up literature as primary sources; lecture notes stand in for them.
- No source gives a formal order-independence guarantee for any practical sequential router.

---

## 6. Fault injection and mutation testing for the DRC kernel and connectivity checker

### Takeaway
A checker is only evidence if it is shown to fail when it should: seed known violations at controlled margins and measure detection rate (the board-level analogue of the project's existing M1 fault injection), and run a mutation tool over the geometry code to find comparisons no test pins. On this Windows machine, mutmut does not run natively (it needs `fork`; WSL required) — cosmic-ray is the native option.

### Cited Findings
- mutmut: "Mutmut must be run on a system with fork support" and "if you want to run on windows, you must run inside WSL"; mutmut 3+ mutates code inside functions and selects tests by which functions they exercise; example mutations: integer literals +1, `<` → `<=`, `break` ↔ `continue`; supports `mutate_only_covered_lines`, `do_not_mutate_patterns`, `# pragma: no mutate`, and a `type_check_command` to filter invalid mutants. — [boxed/mutmut README](https://github.com/boxed/mutmut)
- A third-party comparison (written by maintainers of a competing tool, pytest-gremlins — treat with care) lists mutmut as Unix/WSL-only and active (v3.5.0, Feb 2026), and cosmic-ray and mutatest as cross-platform; cosmic-ray supports distributed execution. — [pytest-gremlins comparison page](https://pytest-gremlins.readthedocs.io/en/latest/guide/comparison/)
- Guerino et al. (SBQS 2024), "Static and Dynamic Comparison of Mutation Testing Tools for Python": Cosmic Ray offers the richest functionality and customisation for mutant generation among the tools compared; its dynamic performance was slightly below MutPy's. — [SBQS 2024 paper](https://sol.sbc.org.br/index.php/sbqs/article/view/32948)
- Cosmic Ray was presented at EuroPython 2024 as an actively maintained Python mutation tester. — [EuroPython 2024 session](https://ep2024.europython.eu/session/mutation-testing-in-python-with-cosmic-ray)
- KiCad maintains *both* directions as separate regression suites: `DRCFalsePositiveRegressions` (boards that must yield zero errors) and `DRCFalseNegativeRegressions` (boards with an exact expected violation count, e.g. `issue1358` → 2, `issue2512` → 5, `issue12109` → 8, `issue18878` → 12), each board named after the bug report that produced it. — [KiCad `test_drc_regressions.cpp`](https://docs.kicad.org/doxygen/test__drc__regressions_8cpp_source.html)
- tscircuit maintains a dataset of autorouter inputs "with at least one measured Pipeline 9 relaxed DRC issue" (37 inputs) — a corpus selected *because* the checker flags them. — [tscircuit-autorouter README](https://github.com/tscircuit/tscircuit-autorouter)
- **Local code:** `kernel.drc` rule 1 compares `d < need` with `need = req + t1.width/2 + t2.width/2`, pre-filtered by bounding boxes padded with `t.width`; the project already has `validation/envelope_grid.py` described as "CI grid harness + M1 fault injection" and a "mutation gate" in `proof/prover.py`. — `C:\Users\KIIT\cursor-electronics\backend\pcb_engine\kernel.py` (lines 105-125); `C:\Users\KIIT\cursor-electronics\.claude\CLAUDE.md` (project structure)

### Inferences
- **Seeded-violation catalogue** (each injector takes a *clean* routed board and produces a board with exactly one known defect, plus the label):

  | Fault | Injector | Must be reported as |
  |---|---|---|
  | Clearance, track-track | translate one segment toward a foreign track until gap = req − δ | clearance |
  | Clearance, track-pad / track-via / via-via / via-pad | same, per pair type | clearance (each pair type separately — a kernel often implements only some) |
  | Short | add a segment joining two nets; or move a track to overlap a foreign pad | short / connectivity |
  | Open | delete one segment; shorten a track end by more than its width; delete a via | open |
  | Hairline open | shorten a track end so it stops δ short of the pad | open (catches "endpoint within tolerance" laxity) |
  | Missing via | put half of a route on the other layer without a via | open |
  | Wrong-layer pad entry | route to an SMD pad on the opposite layer | open |
  | Off board / edge clearance | translate a track across or to within edge − δ of the outline | edge |
  | Width | set width to min − δ | width |
  | Acute angle / zero-length segment / duplicate point | perturb one vertex | (if the rule exists; otherwise recorded as "not assessed") |
  | Dangling stub | add a same-net spur to nowhere | dangling (if assessed) |

- **Sweep δ, not just presence.** For each fault run δ ∈ {+10 µm, +1 µm, +1 nm, 0, −1 nm, −1 µm, −10 µm} around the threshold. The result is a detection curve per rule: the kernel must flag everything below the threshold by more than the declared epsilon and nothing above it by more than epsilon. The boundary behaviour (`<` vs `<=`, which side "exactly equal" falls on) becomes an explicit, tested decision rather than an accident — which is also precisely what `<` → `<=` mutants probe.
- **Report as a confusion matrix per rule** (injected vs detected; clean boards vs flagged) with detection rate and false-alarm rate and their confidence intervals (section 8). Rules with no injector are "not assessed", mirroring the project's G7 language for unimplemented validation rules.
- **Injection also tests the independent checker and the differential harness** — run the same seeded boards through Shapely/raster/Freerouting/KiCad; a fault that only one engine misses localises the bug.
- **Mutation testing targets and expectations:** point the tool at `kernel.py` (and later the independent checker) only, with the seeded-violation tests and property tests as the killing suite. Surviving mutants in geometry code fall into recognisable groups: (a) boundary mutants (`<`→`<=`) that survive because no test sits on the threshold → add δ=0 cases; (b) mutants in the bbox pre-filter that survive because the exact check behind it masks them (equivalent *for correctness*, not for speed) — unless the pre-filter is too tight, in which case they reveal false negatives (see the candidate defect in section 1); (c) arithmetic mutants in `_ccw` / projection `t` clamping, killed only by tests with crossing, collinear, T-junction and degenerate zero-length segments. Each survivor is either a missing test or a documented equivalent mutant.
- Mutation testing of the *router* is less informative than of the checker: many router mutants only change quality, and the checker (correctly) still passes them. Kill those with the Dijkstra optimality oracle and the metamorphic relations instead.
- Practical: cosmic-ray natively on Windows, or mutmut in WSL/the Linux CI container; restrict to one module to keep runtime to minutes; run nightly, not per commit.

### Gaps
- No published mutation-testing or fault-injection study of a PCB DRC engine or routing connectivity checker was found; the catalogue above is my construction from the rule list.
- mutmut's current version number comes from a competitor's comparison page, not from mutmut's own release notes.
- I did not find a published "DRC detection-rate" benchmark (seeded violations with labels) for PCB tools; IC physical verification has vendor qualification runsets, which I did not research.

---

## 7. Geometric robustness: floating point, integer units, exact predicates, epsilon policies, fuzzing geometry

### Takeaway
Mature tools avoid the problem at the representation level: KiCad stores coordinates as 32-bit integer nanometres, so equality and "touching" are exact, and applies an explicit DRC epsilon to thresholds. The local kernel uses float millimetres with unguarded `<` comparisons, so near-threshold verdicts depend on rounding; the low-cost fix is integer units in the checker plus one declared epsilon policy, with exact predicates as the heavier alternative.

### Cited Findings
- KiCad's "Board Internal Unit" plan (Dick Hollenbeck, 2011) moved pcbnew from deci-mils to nanometres; with nanometres "a 32 bit signed integer can only hold about 2 meters of positive length and 2 meters of negative length", and the note warns intermediate integer arithmetic (e.g. a hypotenuse) can overflow. — [KiCad `Documentation/biu-plan.txt` (mirror)](https://git.elphel.com/Elphel/kicad-source-mirror/blame/7413cfd160c953d0ec8729d04874fc4d72f87fb8/Documentation/biu-plan.txt)
- KiCad "uses 32 bit integers with nanometer resolution internally, and everything non metric is rounded / approximated". — [KiCad forum](https://forum.kicad.info/t/kicad-6-grid-units-to-inches/33852)
- A KiCad fork documents a concrete overflow: a squared distance accumulated in 32-bit arithmetic overflows once two points are more than about 46 µm apart, after which a nearest-item search compares wrapped negative values and picks the wrong item (a fork's finding, not upstream documentation). — [IHP Open ADK KiCad fork docs](https://ihp-open-adk-docs.readthedocs.io/en/latest/tools/01_kicad_adk_mod.html)
- KiCad's DRC subtracts an epsilon from thresholds internally and has a regression test that the *reported* required value is the configured one, not the epsilon-adjusted one. — [KiCad `test_drc_regressions.cpp`](https://docs.kicad.org/doxygen/test__drc__regressions_8cpp_source.html)
- Shewchuk, "Adaptive Precision Floating-Point Arithmetic and Fast Robust Geometric Predicates" (*Discrete & Computational Geometry*, 1997): exact orientation and incircle tests on ordinary IEEE doubles; adaptive — "their running time depends on the degree of uncertainty of the result, and is usually small". — [Shewchuk abstract](https://people.eecs.berkeley.edu/~jrs/papers/robust-predicates.abstract); [DOI](https://www.doi.org/10.1007/PL00009321)
- Python access to Shewchuk's 2D predicates exists as the `geompreds` package. — [PyPI geompreds](https://pypi.org/project/geompreds/)
- GEOS (behind Shapely) handles overlay robustness with "a series of increasingly aggressive (and slower) noding strategies", starting from floating precision and moving to snapping; snapping "may even introduce errors which were not present in the original data". — [GEOS `OverlayNGRobust.h`](https://libgeos.org/doxygen/OverlayNGRobust_8h_source.html); [GEOS `SnapOverlayOp`](https://libgeos.org/doxygen/classgeos_1_1operation_1_1overlay_1_1snap_1_1SnapOverlayOp.html)
- Shapely `set_precision` gives a fixed-precision grid; modes `valid_output` (default, always valid), `pointwise` (may be invalid), `keep_collapsed`; narrow polygons can collapse to empty. — [Shapely docs](https://shapely.readthedocs.io/en/2.1.1/reference/shapely.set_precision.html)
- **Local code:** `_ccw` is a plain float cross product; `seg_seg_dist` declares a crossing only when both products are strictly negative, otherwise takes the minimum of four endpoint-to-segment distances; violations are `d < need`; positions are float mm; the router grid is `res = 0.25`. — `C:\Users\KIIT\cursor-electronics\backend\pcb_engine\kernel.py` (lines 34-53, 119-120); `C:\Users\KIIT\cursor-electronics\backend\pcb_engine\router.py` (line 76)

### Inferences
- **Where float mm actually bites in this code:**
  - `to_mm(iy, ix)` produces coordinates like `k * 0.25 + origin`; 0.25 is exact in binary, but origins, pad offsets (e.g. 1.27, 2.54, 0.65 mm pitches) and rotations by non-right angles are not. Two points meant to coincide (track end and pad centre) can differ by ~1e-16, so connectivity must never be decided by `==` on floats.
  - A router that packs tracks at *exactly* the minimum spacing (a grid router does this constantly: adjacent tracks at halo distance) produces `d` values that sit on the threshold, where `d < need` flips on the last bit. That yields flaky DRC verdicts under translation/rotation — which the metamorphic "rigid motion" relation in section 3 will expose.
  - The strict `< 0` crossing test is safe for distance (touching and collinear cases fall through to an endpoint distance of 0), but sign errors in `_ccw` for nearly collinear segments can misclassify a crossing as a near miss with a tiny positive distance — still below `need`, so benign for clearance, but not for a "do these overlap" connectivity decision built on the same primitive.
- **Recommended policy (cheap, matches KiCad):** the *checker* converts to integer nanometres on input (`round(mm * 1e6)`), does all orientation/intersection tests in Python integers (arbitrary precision, so no overflow and no Shewchuk needed — the 32-bit overflow KiCad guards against does not arise), compares squared distances as exact integers where possible, and uses one named constant for threshold slack. State the policy in one sentence that tests enforce, e.g. "a clearance is violated iff measured < required − ε, ε = 1 nm; values within ±ε of the threshold are reported as boundary". The δ-sweep in section 6 is the test of that sentence.
- **Round-trip risk:** DSN/SES and `.kicad_pcb` exports quantise coordinates; a board clean in float mm can become dirty after export at a different resolution. Add a property: `check(import(export(board)))` equals `check(board)`, and quantise in the IR before checking rather than after.
- **Fuzzing geometry primitives with Hypothesis:** strategies biased to degenerate cases — zero-length segments, collinear overlap, shared endpoints, T-junctions, near-parallel segments at huge and tiny coordinates, coordinates that are multiples of 0.1 (not representable) — compared against (a) an exact rational reference using `fractions.Fraction` (slow, exact, a dozen lines: a true oracle for `seg_seg_dist²`), and (b) Shapely's distance. Properties: symmetry, non-negativity, zero iff intersect (per the exact reference), invariance under swapping endpoints, 1-Lipschitz under perturbation of an endpoint (|Δd| <= |Δp|) — a continuity property that catches sign-flip discontinuities.
- Arcs and round caps: buffered polygons approximate circles; a polygon checker's error is the chord sagitta `r(1 − cos(π/2n))` — choose n so this is below ε or carry it as explicit uncertainty.

### Gaps
- I could not confirm from a primary source which exact-arithmetic scheme GEOS uses for its orientation predicate (my recollection is double-double arithmetic, not Shewchuk expansions) — unverified.
- KiCad's current `base_units.h` constants and the numeric value of its DRC epsilon were not fetched; the 2011 plan and a Doxygen test file stand in.
- CGAL exact kernels (EPICK/EPECK) were in the suggested sources but not researched in this pass; CGAL's Python bindings and licence (GPL/LGPL per package) would need checking before recommending it.
- Freerouting's internal number representation was not researched.

---

## 8. Building a regression corpus: golden boards, open-hardware inputs, snapshot metrics, statistical reporting

### Takeaway
Three corpora serve three purposes: bug-derived golden boards with exact expected verdicts (KiCad's pattern), a benchmark set with tracked quality metrics and tolerance rules against a "last known good" (OpenROAD's pattern), and a seeded random population reported as rates with confidence intervals. Open-source routers already do the first two publicly.

### Cited Findings
- KiCad's DRC regression boards are named after issue numbers; false-positive boards must give zero errors, false-negative boards an exact count; unrelated checks are set to ignore before counting; zones are deliberately not refilled where the test targets the DRC engine rather than the zone filler. — [KiCad `test_drc_regressions.cpp`](https://docs.kicad.org/doxygen/test__drc__regressions_8cpp_source.html); [KiCad pcbnew DRC test directory](https://docs.kicad.org/doxygen/dir_2bd3f1f287c00961ddeb1acdd9f21397.html)
- OpenROAD-flow-scripts keeps, per design, `metadata-base-ok.json` ("golden" metrics from the last known good run) and `rules.json` (rules used to evaluate new runs); key metrics such as worst slack and number of DRCs are compared against golden values, and the reference is updated when a change legitimately improves or changes a metric. — [OpenROAD-flow-scripts metrics docs](https://openroad-flow-scripts.readthedocs.io/en/latest/contrib/Metrics.html)
- OpenROAD CI runs unit tests at tool level and flow-level tests on QoR; metrics are reported in the METRICS2.1 JSON format and validated per pull request against known golden metrics. — [OpenROAD Flow QoR and CI docs](https://openroad-flow-scripts.readthedocs.io/en/latest/user/Flow_QoR_CI.html)
- OpenROAD added real tape-out (MPW) designs to its CI to improve quality. — [The OpenROAD Project blog](https://theopenroadproject.org/mpw-designs-in-openroad-ci-improve-quality-for-everyone/)
- tscircuit: `bun run bug-report-with-test <bug-report-url>` downloads a bug report, creates the fixture and scaffolds a matching snapshot test under `tests/bugs`; routing performance is tracked on a public benchmark dashboard; dataset samples record source links and pinned revisions. — [tscircuit-autorouter README](https://github.com/tscircuit/tscircuit-autorouter)
- A community tscircuit dataset of twenty single-net problems exists purely to validate 45-degree obstacle support, ranging from diagonal tunnels to a ten-obstacle comb maze. — [dataset-srj11-45-degree](https://tscircuit.com/sangit/dataset-srj11-45-degree)
- **Local state:** the project already keeps golden placements (e.g. "golden placement for the DHT22 template regenerated") and derives its status files from test results rather than prose. — `C:\Users\KIIT\cursor-electronics\.claude\shared-memory\plan\current_phase.md` (lines 58-60); `C:\Users\KIIT\cursor-electronics\.claude\shared-memory\AGENTS.md`

### Inferences
- **Corpus A — golden boards (exact, small, hand-readable).** One board per behaviour or past bug: a two-pad straight shot; a forced via crossing; a one-track corridor; a provably unroutable single-layer crossing; the room-monitor board. Each stores the input IR and the *expected checker verdict* (clean / exact violation list), not the exact tracks — track geometry is allowed to change when the router improves. Every router or DRC bug found adds a board, named after the issue (KiCad and tscircuit both do this).
- **Corpus B — metric snapshots (OpenROAD's pattern).** For each benchmark board store completion, total length, via count, violation count, runtime, plus rules: completion must not decrease, violations must stay 0, length may not regress by more than X%. A change that worsens a metric fails CI until the golden file is consciously updated in the same commit — which fits the project's "derived files, one owner per fact" culture: the snapshot is the owner of "how good is the router".
- **Corpus C — seeded random population.** N boards from the Hypothesis-style generators with fixed seeds (so the population is reproducible), stratified by net count and density. Report *rates with intervals*, never bare percentages: for k successes in N, the Wilson score interval; e.g. 0 failures in N trials bounds the true failure rate below ≈ 3/N at 95% ("rule of three") — so 300 clean boards support "failure rate < 1%", not "no failures". Compare two router versions on the *same* boards with a paired test (McNemar on routed/not-routed pairs) rather than comparing two percentages.
- **Corpus D — real boards.** Open-hardware KiCad projects give realistic placements and netlists: strip the tracks, keep footprints and nets, re-route, and compare with the human routing (which is also a routability witness). Licences vary (CERN-OHL variants, CC-BY-SA, MIT, GPL) and derived test fixtures inherit them, so record source URL, revision and licence per board (tscircuit records source links and pinned revisions per sample) and prefer permissive ones, or fetch at test time instead of vendoring. Restrict to small 2-layer boards without zones to match the engine's scope.
- **Statistical hygiene:** fix and publish seeds; separate "tuning" boards from "reporting" boards (a router tuned on the corpus it is reported on overstates its rate); report runtime distributions (median, p95), not means; treat timeouts as failures and count them separately.
- Registering these test files in `tools/regen_state.py` / `tools/progress_gen.py` is required by the project's own bootstrap, otherwise the new coverage is invisible to `progress.yaml`.

### Gaps
- I did not research specific open-hardware board repositories or their licences in this pass (suggested: verify per project before vendoring); no curated, licence-clean "small 2-layer PCB routing benchmark" was found beyond the tscircuit datasets.
- The Wilson interval, rule of three and McNemar's test are standard statistics stated from general knowledge, not from a fetched source.
- The contents and licence of the tscircuit `dataset-srj33` samples were not inspected; the autorouter itself is MIT.

---

## 9. Formal verification and certificate checking for routing and DRC in the literature

### Takeaway
I found no formally verified PCB router or DRC engine. What the literature supports is the lighter pattern: untrusted solver + small trusted checker, with the checker itself optionally verified — plus machine-checkable UNSAT proofs when unroutability is established by SAT.

### Cited Findings
- **[E]** Certifying algorithms (McConnell, Mehlhorn, Näher, Schweitzer 2011): the certificate makes each individual output checkable without trusting the implementation; most LEDA programs are certifying. — [ANU record](https://researchportalplus.anu.edu.au/en/publications/certifying-algorithms/); [Mehlhorn ADFOCS abstract](https://conferences.mpi-inf.mpg.de/adfocs-08/Mehlhorn-abstract.txt)
- **[R→E]** Verifying the checker instead of the algorithm: "A framework for the verification of certifying computations", *J. Automated Reasoning* 52(3):241-273, 2014. — [Mehlhorn talk, UMD](https://www.cs.umd.edu/event/2014/08/certifying-computations-algorithmics-meets-software-engineering)
- **[R]** SAT-based routing yields infeasibility proofs: unsatisfiability of the routing constraint function demonstrates the instance cannot be routed. — [US patent 7,904,867](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7904867)
- **[R]** DRAT proofs of unsatisfiability have been extended to SAT modulo monotonic theories, with escape routing among the motivating applications — i.e. an "unroutable" verdict can come with a proof object an independent checker validates. — [arXiv 2401.10703](https://arxiv.org/pdf/2401.10703)
- **[E]** Exact routing of restricted problems exists (channel routing to ~13 tracks; ordered escape routing by SAT). — [Sulimma & Kunz, ISPD 2001](https://publikationen.ub.uni-frankfurt.de/frontdoor/index/index/year/2006/docId/2884); [Luo & Wong, ASP-DAC 2008](https://www.cecs.uci.edu/~papers/aspdac08/pdf/p244_3A-4.pdf)

### Inferences
- **The routing result is its own certificate for the positive claim.** "This board is routed" needs no proof about A*: the tracks are the witness, and the checker of section 1 is the certificate checker. The whole trust burden therefore falls on a few hundred lines of checker — which is where independence (section 1), fault injection (section 6) and exact arithmetic (section 7) should be spent. This is the same shape as the project's existing proofs: z3 proves properties of the netlist, not of the generator.
- **The negative claim ("unroutable") has no cheap certificate** except (a) UNSAT with a DRAT/LRAT proof from a proof-producing SAT solver, checked by an independent proof checker, valid for the stated grid model; or (b) a combinatorial cut/planarity argument that is itself checkable (a cut with capacity c and demand > c is a short witness — count the tracks that fit across the cut, count the nets that must cross it). Without one of these, the honest output is "not routed", not "unroutable".
- **A realistic formal target for this project:** prove (z3 or by exhaustive enumeration on small integer ranges) properties of the *checker's primitives*, not the router — e.g. that the integer segment-distance predicate "dist² < need²" agrees with its rational specification for all inputs in a bounded box, or that the grid halo rule `halo_cells(width)` is conservative: every pair of cells the router treats as compatible corresponds to copper at least `clearance` apart in the continuous model. The second is the bridge lemma between "legal by construction on the grid" and "legal in millimetres", and is the one place a proof would remove a whole class of bugs. It is bounded integer arithmetic, well within z3's reach.
- The router's docstring claim "every one it accepts is legal by construction" is exactly that bridge lemma stated without proof; the differential check `kernel.drc(route(board)) == []` over thousands of random boards is its empirical counterpart, and the z3 proof would be its formal one.

### Gaps
- No formally verified (Coq/Isabelle/Lean/Dafny) PCB router, maze router, or DRC kernel was found. Verified computational geometry exists as a research area (e.g. verified convex hull, verified floating-point predicates), but I did not research or source it in this pass.
- I did not find published "proof-carrying" or certificate-emitting PCB routers; the DRAT-for-routing work is in the IC/package escape-routing context.
- Which Python-accessible SAT solvers emit DRAT/LRAT proofs conveniently (e.g. CaDiCaL via PySAT) is not verified here.

---

## 10. How EDA vendors and open-source projects test their routers and DRC

### Takeaway
Publicly documented practice converges on three things: issue-derived regression boards with exact expected DRC outcomes (KiCad), golden quality-of-result metrics with tolerance rules enforced in CI (OpenROAD), and public benchmark datasets with DRC-failure corpora and dashboards (tscircuit). None of the sources found documents independent-oracle or metamorphic testing of a router — the project's proposed rigour would exceed published open-source practice.

### Cited Findings
- **KiCad:** DRC regression tests are Boost.Test files in the pcbnew QA tree, mostly named after GitLab issue numbers (creepage, Edge.Cuts text, custom rules silently skipped for pads, etc.). — [KiCad pcbnew DRC test directory](https://docs.kicad.org/doxygen/dir_2bd3f1f287c00961ddeb1acdd9f21397.html); [example: `test_drc_issue23469.cpp`](https://docs.kicad.org/doxygen/test__drc__issue23469_8cpp_source.html)
- **KiCad:** the board-level harness has separate false-positive and false-negative suites, filters unrelated severities, respects DRC exclusion markers when counting, and includes targeted checks (e.g. exactly one shorting-items violation involving a footprint field on `issue24649`). — [KiCad `test_drc_regressions.cpp`](https://docs.kicad.org/doxygen/test__drc__regressions_8cpp_source.html)
- **KiCad:** DRC is scriptable for CI through `kicad-cli pcb drc` with `--exit-code-violations` (0 clean, 5 violations). — [KiCad 9.0 CLI reference](https://docs.kicad.org/9.0/en/cli/cli.html)
- **KiCad (older, secondhand):** building with `KICAD_BUILD_QA_TESTS` yields a `qa_pcbnew_tools` binary that could run a subset of DRC checks from the command line. — [KiCad forum](https://forum.kicad.info/t/drc-from-python-scripting/22258)
- **OpenROAD:** regression scripts under `./test/`; per-tool tests under `src/<tool>/test`; flow tests compare results against reference values. — [OpenROAD Developer Guide](https://openroad.readthedocs.io/en/latest/contrib/DeveloperGuide.html)
- **OpenROAD-flow-scripts:** `metadata-base-ok.json` + `rules.json` per design; DRC count is one of the gated metrics; METRICS2.1 JSON; Jenkins CI validates each pull request's QoR against golden metrics; MPW tape-out designs added to CI. — [Metrics docs](https://openroad-flow-scripts.readthedocs.io/en/latest/contrib/Metrics.html); [Flow QoR and CI](https://openroad-flow-scripts.readthedocs.io/en/latest/user/Flow_QoR_CI.html); [OpenROAD blog](https://theopenroadproject.org/mpw-designs-in-openroad-ci-improve-quality-for-everyone/)
- **Freerouting:** documents a router score and an optimizer score (section 2), a `-drc` JSON report in KiCad's DRC format, and a REST API; GPL-3.0. — [scoring.md](https://github.com/freerouting/freerouting/blob/master/docs/scoring.md); [command-line arguments](https://github.com/freerouting/freerouting/blob/master/docs/command_line_arguments.md)
- **tscircuit autorouter (MIT):** `bun test` unit/integration suite; bug reports converted to fixtures and snapshot tests under `tests/bugs`; a public Autorouter Benchmark Dashboard; a DRC-failure dataset of 37 inputs (12 from the original benchmark, 25 from a later bug-report audit) with "exact DRC errors" recorded; distinguishes DRC from "relaxed DRC"; pipelines are versioned (Pipeline 7 baseline vs Pipeline 9). — [tscircuit-autorouter README](https://github.com/tscircuit/tscircuit-autorouter)
- **tscircuit in practice:** a user reproduction notes an autorouter effort setting of `1x` because `10x` exceeded a 300-second per-file build limit — runtime budgets are part of the test contract. — [tscircuit user repro project](https://tscircuit.com/0hmX/am62l-lpddr4-breakout-repro)
- **Adjacent (FPGA tools):** Verismith found bugs in Vivado, Yosys and Quartus synthesis by random design generation plus formal equivalence checking of the output — the differential/"check the answer" pattern applied to commercial EDA. — [Verismith slides](https://www.cl.cam.ac.uk/~jpw48/talks/verismith_27nov2019.pdf)
- **Adjacent (vendor practice, patent):** Altera describes generating randomised, diverse test designs with realistic attributes to test synthesis, simulation and place-and-route tools. — [US patent 8,065,128](https://patents.justia.com/patent/8065128)

### Inferences
- **Pattern summary — what to copy from whom:**
  - from KiCad: every DRC bug becomes a named board with an *exact expected count*, in two suites (must-be-clean, must-flag); filter out rule categories the test is not about.
  - from OpenROAD: QoR is a gated, versioned artefact (`*-ok.json` + rules), updated deliberately; real designs in CI.
  - from tscircuit: one command turns a bug report into a fixture; a corpus of *known DRC-failing* inputs is kept as a to-do list for the router; public dashboard over pipeline versions.
  - from Freerouting: publish the score formula, separate "legal and complete" (router score) from "efficient" (optimizer score against a lower bound), and use violations/opens as vetoes rather than as soft penalties.
- In IC routing research, contest infrastructure plays the independent-oracle role: routers are scored by an evaluator the contestants did not write, and DRC-clean-ness is judged by a commercial sign-off tool. That is the same separation the project wants, institutionalised. (General knowledge; not sourced in this pass — see Gaps.)
- Local kernel's `score()` mixes into one number what Freerouting keeps as two scores plus vetoes; for testing, the veto form is easier to assert on ("no candidate with a violation is ever ranked above one without").
- Given the project's stated plan to adopt Freerouting at B5 rather than extend the A* router, the durable investment is the *checker, corpus and harness* (sections 1, 6, 8) — they validate any `RouterBackend`, including Freerouting's output, and survive the router being replaced.

### Gaps
- KiCad's official developer testing page returned 404 at the URL tried; QA structure is described from Doxygen source listings and forum posts, not from the current developer handbook. Whether KiCad's QA includes fuzzing or tests of its interactive router (PNS) was not established.
- OpenROAD's detailed-router (drt / TritonRoute) specific golden files, and the ISPD 2018/2019 detailed-routing contest evaluator and its relation to regression checks, were not found in this pass.
- Horizon EDA and LibrePCB test practices were not researched (no sources fetched).
- No documentation of Freerouting's own automated tests was found.
- Commercial vendor (Cadence, Siemens, Altium, Zuken) router QA practice is essentially unpublished; only a patent-level description (Altera) was found.

---

## Cross-cutting summary for the report writer (inferences only; no new facts)

A staged plan consistent with the findings, ordered by evidence gained per unit of effort:

1. **Independent result checker** (Shapely polygon and/or fine raster; integer nm; shares nothing with `router.py` or `kernel.py`). Turns "routed" into a checked claim. *[E] pattern: certifying algorithms.*
2. **Seeded-violation suite with δ-sweep** against both `kernel.drc` and the new checker; confusion matrix per rule. Confirms or refutes the bbox pre-filter candidate defect. *[E] pattern: KiCad false-negative suite; project's own M1 fault injection.*
3. **Single-net exact oracles**: BFS reachability and Dijkstra cost vs `astar`; heuristic admissibility/consistency properties. *[E].*
4. **Hypothesis generators incl. routable-by-construction boards**; unconditional invariants; the "old solution still valid" metamorphic relations. *[R] for routing, [E] as a technique.*
5. **Order-sensitivity experiment** (K permutations per board) and the two-BFS diagnosis of the 6/14 result. *[E] problem, measurement is own design.*
6. **Differential run against Freerouting headless** (DSN out exists; SES in needed), 2 routers × 3 checkers. *[E] technique; no published PCB precedent found.*
7. **Exact multi-net model on tiny boards** (CP-SAT / z3) for optimality gap and grid-scoped unroutability proofs. *[R]; scaling unmeasured.*
8. **Mutation testing of the checker modules** (cosmic-ray on Windows, mutmut under WSL/CI). *[E] tool, no geometry-specific precedent found.*
9. **Corpora and snapshot metrics with intervals**, registered in the project's state tooling. *[E] pattern: OpenROAD, tscircuit, KiCad.*
10. **Optional formal bridge lemma** (grid halo ⇒ continuous clearance) in z3. *[R].*

Three verdict classes should be used throughout, matching the project's "an unchecked rule is never a passed one": *checked clean*, *proved (with scope: grid, rules, epsilon)*, *not assessed / not routed by heuristic*.
