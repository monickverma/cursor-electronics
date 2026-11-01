# Routing-quality metrics, lower bounds, reference comparisons and public benchmarks for a small 2-layer PCB autorouter (as of October 2026)

Scope note: written for a solo developer with a Python A* grid router on 2-layer hobby-class boards
("Routed 3/4, Vias 4, Copper 54.2 mm, 0 DRC errors"). Every cited finding carries its source; arithmetic
and judgement that I added myself is under "Inferences". Year is given for anything older than 2025.

---

## 1. What metrics are standard for judging routing quality? (definitions and formulas)

### Takeaway
The 2026 de-facto metric set for PCB routers is: clean pass (fully connected AND zero DRC violations),
routability (fraction of ratsnest connections closed), DRV count, total wirelength, via count and wall-clock
time — with wirelength and vias only compared among results that are complete and DRC-clean. Freerouting adds
a second, independent "how far above the geometric floor" score (length vs Manhattan MST, vias vs minimum
layer changes, bends vs minimum corners).

### Cited Findings
- PCBWorld (LG AI Research, KDD 2026 workshop, arXiv 2607.05915) scores routed boards with eight
  engine-checked measures: Clean Pass (CP, primary), Potential Gain, Routability, DRV count, Wirelength,
  Via count, Wallclock time, Parse-fail (LLM agents only). DRC status, connectivity, wirelength and via count
  are all computed by KiCad itself (KiCad 9.0.8, kicad-python 0.6.0). — [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4)
- PCBWorld formulas: Routability `rout = (R(s0) − R(s)) / R(s0)` where R counts remaining ratsnest edges;
  Clean Pass counts a board only if `rout = 1` and `DRV = 0`; potential
  `Φ(s) = −(f_drv(s) + λ_w·ℓ(s) + λ_v·n_via(s))` with default `(λ_w, λ_v) = (0.002, 0.1)` (ℓ = total
  wirelength, n_via = via count) — i.e. with those defaults one via is weighted like 50 units of wirelength;
  DRC penalty `f_drv = 3·ln(1 + x/2) + Σ_i ln(1 + x_i/2)` (x = number of nets with violations, x_i =
  per-net violation count). KiCad's DRC API covers 38 checks. — [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4)
- PCBWorld states that among DRV-free routings, quality is measured by total wirelength and via count, which
  correlate with signal delay and fabrication cost. — [PCBWorld arXiv PDF](https://arxiv.org/pdf/2607.05915)
- Freerouting (current docs, V2 scoring) reports two independent 0–1000 scores. Router score:
  `1000 − W1·o1 − W2·o2 − 25·(N_viol/D) − 300·((ΣL_um/1000)/D)`, where f = open/total connections,
  `o1 = clamp((f−0.5)/0.5, 0, 1)`, `o2 = min(1, f/0.5)`, W1 ≈ 333.3, W2 ≈ 666.7 (closing the last, hard half
  is worth more), and `D = max(1, pins × signal layers)` normalises for board size. Nothing routed = 0, half
  routed ≈ 333, all closed with no violations = 1000. — [Freerouting docs/scoring.md](https://github.com/freerouting/freerouting/blob/master/docs/scoring.md)
- Freerouting optimizer score: `1000 − ΔL − ΔV − ΔB`, with
  `ΔL = 1000·max(0, (L_actual − L_min)/max(L_min, 1 mm))`, `ΔV = 2000·max(0, V_actual − V_min)/D`,
  `ΔB = 500·max(0, B_actual − B_min)/D`. L_min, V_min, B_min are lower bounds from placement and netlist:
  Manhattan MST length, minimum layer changes, minimum corners. The doc says a legal production board
  usually will not reach 1000. Worked example in the doc: L_min 100 mm, L_actual 150 mm, 2 excess vias,
  5 excess bends, D = 20 gives 175. — [Freerouting docs/scoring.md](https://github.com/freerouting/freerouting/blob/master/docs/scoring.md)
- DeepPCB's vendor report defines completion rate as connected airwires / total airwires on the latest
  revision, time as wall-clock from job start to final revision, and reports "vias per airwire" (median 0.28
  over 32,000+ jobs) as its via-density figure. — [DeepPCB autorouter benchmark 2026](https://deeppcb.ai/pcb-autorouter-benchmark-2026/)
- NS-Place (Cheng, Ho, Holtz; arXiv 2022, DOI points to ASP-DAC 2022) evaluates placements by routing them
  with an open-source router and reporting routed wirelength, number of vias and number of DRVs over 14 PCB
  designs. — [arXiv 2210.14259](https://arxiv.org/abs/2210.14259)
- HPWL (half-perimeter wirelength = width + height of a net's pin bounding box) is exact for optimally
  routed 2-pin and 3-pin nets and a lower bound for larger nets; it can significantly underestimate
  higher-degree nets. This is IC-placement terminology that transfers directly. — [Kahng et al., VLSI Physical Design ch. 4](https://ifte.de/books/eda/chap4.pdf); [Chu, FLUTE paper](https://home.engineering.iastate.edu/cnchu/pubs/c28.pdf)

### Inferences
- A practical metric table for the reader's router, per board: (1) clean pass yes/no; (2) routability =
  closed ratsnest edges / total; (3) DRV count from an independent DRC (KiCad's, not the engine's own);
  (4) wirelength ratio = routed length / lower bound, per net and summed; (5) excess vias = vias − minimum
  necessary; (6) runtime. "Detour ratio" in the usual sense is (4) computed per net.
- "0 DRC errors" from the engine's own DRC is the weakest of the reported numbers: the benchmark convention is
  that violations are counted by an external engine (KiCad DRC), so that a router and its checker cannot share
  a blind spot.
- "Routed 3/4" is not a clean pass under any of the published definitions; under Freerouting's router score a
  board with 25% of connections open scores `1000 − 666.7·0.5 = ~667` (o1 = 0, o2 = 0.5). Wirelength and via
  figures on an incomplete board are not comparable with a complete one (the missing net costs nothing).
- Congestion/overflow metrics (IC global routing: overflow per grid edge) do not have an established PCB
  analogue in the sources found; on a tiny board they reduce to "did it complete".

### Gaps
- PCBWorld's exact wirelength definition (centre-line track length, whether via barrel length or arcs are
  included) was not visible in the text read. Check Appendix I before copying.
- No source found defining a standard "bend count" or "detour ratio" for PCB other than Freerouting's own
  scoring doc.

---

## 2. How are lower bounds computed in practice, what implementations exist, and what ratio is good?

### Takeaway
For nets of 2–3 pins (nearly every net on a hobby board) HPWL is already the exact rectilinear Steiner
optimum, so a simple MST or HPWL in a few lines of Python is a sufficient bound and FLUTE/GeoSteiner are
unnecessary. No source gives a published "good" ratio for PCB routing; the only concrete anchor is
Freerouting's scoring, which penalises every percent above the Manhattan MST linearly (50% over = −500 of 1000).

### Cited Findings
- HPWL equals the RSMT cost for 2- and 3-pin nets and is a lower bound above that. — [Kahng et al., ch. 4](https://ifte.de/books/eda/chap4.pdf)
- Hwang's result: the rectilinear MST is at most 3/2 times the rectilinear Steiner minimal tree, so
  `RMST/1.5 ≤ RSMT ≤ RMST`. (Euclidean case: Steiner tree ≥ (√3/2)·MST, Du and Hwang.) — [NTU lecture notes on Steiner trees](https://www.csie.ntu.edu.tw/~kmchao/tree21spr/Steiner.pdf)
- Freerouting uses the Manhattan MST length as L_min, "minimum layer changes" as V_min and "minimum
  corners" as B_min, all computed from placement and netlist. — [Freerouting docs/scoring.md](https://github.com/freerouting/freerouting/blob/master/docs/scoring.md)
- FLUTE (Chris Chu, Iowa State) is a lookup-table RSMT heuristic. The original code is under an "Attribution
  Assurance License (adapted from the original BSD license)" requiring attribution to Dr. Chris C. N. Chu;
  a Java port exists (Stefan Mücke, 2012). — [Flute.java header](https://home.engineering.iastate.edu/cnchu/Flute.java)
- OpenROAD ships Flute3 (based on Flute3.1 extracted from FastRoute4.1, with UFRGS/James Cherry changes),
  described as BSD-3 licensed as per the FastRoute site. — [OpenROAD Flute3 README](https://openroad.readthedocs.io/en/latest/main/src/stt/src/flt/README.html)
- GeoSteiner (exact Euclidean and rectilinear Steiner trees): the 2018 Mathematical Programming Computation
  paper says the code was released as GeoSteiner 5.0 under an open-source licence — [GeoSteiner computational study](https://opus4.kobv.de/opus4-mpc/frontdoor/index/index/year/2024/docId/147);
  but the Arch AUR package for 5.1 lists the licence as "custom" — [AUR geosteiner](https://aur.archlinux.org/pkgbase/geosteiner),
  and the Rust bindings crate states the licence is CC-BY-NC (non-commercial), applying to the bindings too —
  [docs.rs geosteiner](https://docs.rs/geosteiner). Treat GeoSteiner as non-commercial until the licence file is read.
- SteinerPy (`pip install steinerpy`) solves Steiner tree problems to proven optimality on NetworkX graphs
  (needs highspy; aimed at small-to-medium instances). — [SteinerPy docs](https://steinerpy.readthedocs.io/)
- `rsmt` / `rsmt-ts` on npm reimplement GeoSteiner's algorithms in JavaScript/TypeScript. — [npm rsmt-ts](https://npmjs.com/package/rsmt-ts)

### Inferences
- Recommended bound for this reader, zero dependencies: per net, compute pad-to-pad distances and take the
  MST (Prim, O(n²)). Because a PCB track may run at 45°, the correct metric for a router that allows
  diagonals is octile distance `max(dx,dy) + (√2−1)·min(dx,dy)`; for a strictly orthogonal router use
  Manhattan. A Manhattan bound applied to a router that uses 45° segments can be *beaten*, which makes the
  ratio meaningless — match the metric to the router's move set. Euclidean MST × (√3/2) is a universally
  valid floor for any geometry.
- For multi-pin nets (GND, VCC with 5+ pads) the true floor lies between MST/1.5 and MST (rectilinear).
  Report the ratio against MST and say so; that is what Freerouting does.
- Via lower bound for a 2-layer board: 0 for any net whose pads are all through-hole (present on both
  layers) or all SMD on the same side; 1 or more only when a net has SMD pads on opposite sides. With an
  Arduino-class through-hole MCU and mostly THT/same-side SMD parts, V_min is 0 for nearly every net, so
  every via is "excess" unless forced by a crossing. Whether a crossing is forced is a planarity question
  (a planar netlist needs no vias on one layer), which the simple bound does not capture — so V_min is a
  floor, not an achievable target.
- These bounds ignore obstacles (other pads, component bodies, keep-outs), so ratio = 1.0 is unreachable in
  general. A tighter, still honest floor for a grid router: route each net alone on the empty board (other
  nets removed, pads kept as obstacles) with the same A*; the sum of those lengths is an obstacle-aware
  lower bound for that grid, and the gap between it and the full routing isolates the cost of net-to-net
  interaction and net ordering.
- On what ratio is "good": the one hard data point located is PCBWorld Table 21 (see Q4) — the reference
  routings of 99 small real boards average 170.2 mm, Freerouting 156.2 mm and KiCadRoutingTools 142.8 mm,
  i.e. competent routers land within roughly ±15% of one another on small boards. A ratio to MST of
  ~1.0–1.3 on uncongested 2-pin nets would be consistent with that spread; a net at 2× its bound deserves a
  look. This threshold is my judgement, not a published standard.
- The reported "Copper 54.2 mm" cannot be judged at all without the MST sum for the same four nets. That one
  number (sum of per-net MST) is the cheapest missing piece.

### Gaps
- FLUTE's accuracy figures (optimal up to a low degree, sub-percent error above) could not be verified: the
  FLUTE project page returned "Request Rejected" on fetch. Not needed for 2–3-pin nets.
- No published PCB-specific threshold for an acceptable wirelength/lower-bound ratio was found.
- No pip-installable FLUTE wrapper was confirmed ("pyflute" did not turn up).

---

## 3. What public PCB routing benchmarks/datasets exist?

### Takeaway
PCBWorld-Bench (July 2026) is the first open benchmark that fits this use case: KiCad-native boards including
100 small real 2–4-layer boards with 2–13 nets, one evaluator, and published baselines for Freerouting and a
Rust A* router. The other 2026 benchmarks (PCB-Bench, OmniRouting, PCB-QA) target LLM reasoning rather than
classical routers; no ISPD-style contest for PCB routing was found.

### Cited Findings
- PCBWorld / PCBWorld-Bench: open-source, built on the KiCad engine, all data in `.kicad_pcb`. Repo:
  github.com/LGAI-Research/PCBWorld. — [arXiv 2607.05915](https://arxiv.org/abs/2607.05915); [Hugging Face paper page](https://huggingface.co/papers/2607.05915)
- PCBWorld dataset families — [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4):

  | Family | Instances | Nets | Pads | Layers |
  |---|---|---|---|---|
  | D1 grid, synthetic (Jumanji Connector-style) | 10,000 train / 128 / 128 | 5 | 10 | 1 |
  | D2 gridless, synthetic multi-pin | 10,000 train / 128 / 128 | 4–6 | 8–21 | 2 |
  | D3-A small, real | 100 test | 2–13 | 6–31 | 2–4 |
  | D3-B medium, real | 287 test | 5–42 | 31–100 | 2–4 |
  | D3-C large, real | 292 test | 6–451 | 101–2,103 | 2–8 |

- D3 (679 boards) is derived from PCBench's open-source PCB corpus, normalised to KiCad 9, populated with
  each board's stored design rules, and kept only when fully connected and DRV-free; the original routes
  serve as the reference. Evaluation used 99 D3-A boards and 10 D3-B boards (capped for LLM cost). — [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4)
- PCBWorld limitations stated: no copper-pour (zone) representation in the routable space; non-routing DRC
  warnings are excluded from the DRV count by design. — [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4)
- PCB-Bench (ICLR 2026 poster): LLM benchmark with ~3,700 expert-annotated text instances, ~500 multimodal
  problems and 170+ complete PCB projects (schematics, placement files, documentation); data linked from an
  anonymous repository. — [ICLR 2026 poster page](https://iclr.cc/virtual/2026/poster/10009621)
- OmniRouting (arXiv 2608.04434, Aug 2026): 1,681 industrial-grade schematic-coupled designs (board
  geometry, human placements, footprints, pads, netlists, stackup, constraints) for evaluating multimodal
  LLMs on routing; authors say data and code will be open-sourced. — [OmniRouting on alphaXiv](https://www.alphaxiv.org/abs/2608.04434)
- PCB-QA (arXiv 2606.23704) is a question-answer dataset built from PCB design files, not a routing
  benchmark; its related-work table lists PCB-Bench with 170 samples. — [PCB-QA](https://arxiv.org/pdf/2606.23704)
- NS-Place used 14 PCB designs evaluated through an open-source router (2022). — [arXiv 2210.14259](https://arxiv.org/abs/2210.14259)
- DeepPCB's "benchmark" is platform telemetry (100,000+ designs, 32,000+ completed jobs to April 2026), not
  a downloadable dataset, and contains no comparison with other routers. — [DeepPCB](https://deeppcb.ai/pcb-autorouter-benchmark-2026/)
- The Freerouting repo contains `fixtures` and `examples/tutorial_board` directories (DSN test boards). — [Freerouting GitHub](https://github.com/freerouting/freerouting)

### Inferences
- D3-A is the closest public match to the reader's boards (2–13 nets, 6–31 pads, 2–4 layers). Running a
  custom router against it requires: parse `.kicad_pcb` (pads, nets, outline, design rules) into the engine's
  Board IR, strip existing tracks/vias, route, write tracks/vias back into the `.kicad_pcb`, then let
  PCBWorld's evaluator (or plain KiCad DRC plus track-length sum) score it. The importer is the real work;
  the reader's B4 step (`.kicad_pcb` export) covers the write-back half.
- D2 (synthetic 2-layer, 4–6 nets) is useful as a smoke test because both Freerouting and KiCadRoutingTools
  score 1.00 clean pass on it — anything below 100% there is the router's fault, not the board's.
- Filtering D3-A to 2-layer boards only would give a like-for-like subset; the 2-layer count is not stated.

### Gaps
- Licence of the PCBWorld code and of the D3 boards was not in the text read (the CC0 label is the paper's
  arXiv licence). Real open-hardware boards usually carry per-project licences (CERN-OHL, CC-BY-SA); check
  the repo's LICENSE and Appendix P before redistributing anything.
- The original PCBench corpus (PCBWorld ref. [17]) could not be located as a standalone paper or repo:
  board count, licence and download location unknown.
- No ISPD/ICCAD-style contest for PCB routing was found. CircuitNet and the ISPD global/detailed routing
  contests are IC datasets; I found nothing showing them applied to hobby-class PCB routers and did not
  research them further.
- "DeepPCB" as a dataset name also refers to a PCB defect-image dataset unrelated to routing; I did not
  verify this in this session.

---

## 4. How is an autorouter compared against a reference, and what numbers have been published?

### Takeaway
The established method is: take already-routed open-hardware boards, strip the copper, re-route on the
identical placement and rules, and compare clean-pass rate, routability, wirelength and vias against both the
original routing and Freerouting. On 99 small real boards (2026), Freerouting gets an 80% clean pass with 91%
routability, slightly *shorter* wirelength and fewer vias than the original routings; a Rust A* router gets 74%.

### Cited Findings
- PCBWorld main table (CP / Routability / time), D2 synthetic · D3-A (99 small real) · D3-B (10 medium real) —
  [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4):

  | Method | D2 | D3-A | D3-B |
  |---|---|---|---|
  | Reference (original routes) | – | 1.00 / 1.00 | 1.00 / 1.00 |
  | Freerouting 2.1.0 | 1.00 / 1.00 / 2.69 s | 0.80 / 0.91 / 7.09 s | 0.78 / 1.00 / 9.94 s |
  | KiCadRoutingTools (Rust A*) | 1.00 / 1.00 / 0.82 s | 0.74 / 0.94 / 0.65 s | 0.20 / 0.86 / 3.27 s |
  | OrthoRoute (GPU, backplane-oriented) | 0.01 / 0.34 / 2.54 s | 0.02 / 0.53 / 2.20 s | 0.00 / 0.44 / 9.30 s |
  | PPO (RL, trained on synthetic only) | 1.00 / 1.00 / 0.43 s | 0.86 / 0.95 / 1.83 s | 0.45 / 0.85 / 10.77 s |
  | GPT-5.4 tool-using agent | 0.96 / 1.00 / 94 s | 0.65 / 0.91 / 231 s | 0.00 / 0.62 / 866 s |

- PCBWorld Table 21, mean wirelength (mm) and vias on the selected rollout, D3-A · D3-B: Reference 170.2 mm,
  1.18 vias · 570.3 mm, 6.70 vias; Freerouting 156.2 mm, 0.74 · 535.4 mm, 3.48; KiCadRoutingTools 142.8 mm,
  3.69 · 472.3 mm, 11.80; PPO 165.4 mm, 0.92 · 668.6 mm, 6.17. — [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4)
- Baseline set-up: Freerouting 2.1.0 jar with `-mp 10`, 4 GiB heap, OpenJDK 21, inputs converted to DSN,
  mean over 4 seeds; KiCadRoutingTools defaults with 0.1 mm grid step and 200,000 max iterations; OrthoRoute
  0.4 mm grid pitch. Deterministic routers run once. — [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4)
- OrthoRoute's own README confirms its 1%/30% (D2) and 2%/51% (D3-A) results, says Freerouting and
  KiCadRoutingTools "performed dramatically better", and notes the benchmark used small ordinary boards with
  upstream defaults rather than its intended large-backplane workload. — [OrthoRoute README](https://github.com/bbenchoff/OrthoRoute)
- KiCadRoutingTools is a Rust-accelerated A* autorouter for KiCad PCB files, compatible with KiCad 9 and 10. — [KiCadRoutingTools](https://github.com/atomic14/KiCadRoutingTools)
- DeepPCB (vendor, self-selected jobs, no external verification): median completion 100%, mean 95.6%; 86%
  of boards reach ≥95% completion; 2-layer boards with 1–50 airwires reach ≥95% completion 90.6% of the time,
  51–100 airwires 89.5%; median job time 4.6 min, 90th percentile 153 min. — [DeepPCB](https://deeppcb.ai/pcb-autorouter-benchmark-2026/)
- Single-board anecdotes: an 86-net board, manual 32 vias / 408 track segments vs Freerouting 23 vias / 427
  segments, with total length not reported and some "suspicious-looking" routes (Big Mess o' Wires, 2019) —
  [BMOW](https://www.bigmessowires.com/2019/03/27/pcb-autorouting/); a simple 2-layer BLDC driver, autorouter
  11 vias vs 18 manual (EEVblog, 2010) — [EEVblog](https://www.eevblog.com/forum/projects/can-you-route-better-than-an-autorouter/msg25819);
  a hobby board in TopoR, 100% routed with 20 vias instead of 35 and shorter connections — [KiCad forum](https://forum.kicad.info/t/topor-still-active-and-what-best-alternative-also-about-footprints-libs/26632).
- Freerouting minimises total trace length and via count but treats all vias equally and does not account
  for analog effects or length matching (BMOW, 2019). — [BMOW](https://www.bigmessowires.com/2019/03/27/pcb-autorouting/)
- NS-Place (2022): placement changes alone moved routed wirelength by up to 25%, vias by up to 50% and DRVs
  by 79% under the same router. — [arXiv 2210.14259](https://arxiv.org/abs/2210.14259)

### Inferences
- Wirelength ratios vs the original routing from Table 21 (my arithmetic): Freerouting 0.92 (D3-A) and 0.94
  (D3-B); KiCadRoutingTools 0.84 and 0.83; PPO 0.97 and 1.17. Caveat: these means are over each method's
  selected rollouts, and methods with lower clean-pass rates may be averaging over incomplete routings, which
  shortens wirelength artificially. KiCadRoutingTools' short length with 3× the vias shows the trade-off:
  length and vias must be read together (hence the weighted potential).
- The headline for the reader: even the mature open-source router fails a clean pass on 1 in 5 small real
  boards, and the hard, honest metric is clean pass, not net-level routability (0.91 routability coexists
  with 0.80 clean pass). A hobby A* router at 6/14 or 3/4 nets is far below both baselines; wirelength
  tuning is irrelevant until completion is fixed.
- Placement dominates: NS-Place's 25%/50% swings mean a router comparison is only valid on the *identical*
  placement, and that a poor wirelength number may be a placement fault, not a routing fault.
- The same-placement Freerouting run is the single cheapest reference: it yields, per board, whether the
  board is routable at all under those rules (if Freerouting also fails, blame placement/rules), and a
  reference length and via count.

### Gaps
- No controlled published comparison including TopoR, KiCad's interactive (push-and-shove) router as an
  autorouter, or commercial autorouters (Altium Situs, Cadence/Specctra) on a shared open board set was found.
  KiCad has no built-in autorouter per the forum sources.
- No published "wirelength overhead vs manual" percentage beyond PCBWorld Table 21 and the three anecdotes.
- How PCBWorld imports Freerouting's SES back to KiCad, and any wall-clock limit, were not specified in the
  text read.

---

## 5. For a tiny board (under ~20 nets): which metrics are meaningful, and what sample size supports "routes 90% of nets"?

### Takeaway
On one four-net board, completion, clean pass and per-net length-over-bound are meaningful; aggregate
percentages, runtime and "average vias" are noise. A claim like "routes 90%" needs on the order of 30 boards
with zero failures, or 100+ boards if some fail — and the unit should be boards (clean pass), not nets.

### Cited Findings
- Rule of three: with n trials and zero failures, the 95% upper bound on the failure rate is about 3/n
  (exact: `1 − 0.05^(1/n)`); the approximation is crude for small n (n = 10: 0.30 vs exact 0.259). — [John D. Cook](https://www.johndcook.com/blog/2023/08/30/first-time-seeing-a-rare-event/); [Pearson/Triola exercise](https://www.pearson.com/channels/statistics/asset/f7f2d220/no-failures-according-to-the-rule-of-three-when-we-have-a-sample-size-n-with-x0--f7f2d220)
- The Wilson score interval is the recommended default for binomial proportions at small n. — [MetricGate, Wilson vs Agresti-Coull vs Clopper-Pearson](https://metricgate.com/blogs/wilson-vs-agresti-coull-vs-clopper-pearson/)
- Published practice: PCBWorld evaluates on 99 small boards and treats 10 medium boards as a (cost-capped)
  sample; stochastic methods are run over 4 seeds, deterministic ones once. — [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4)
- Published practice treats board-level clean pass as the primary metric and net-level routability as
  secondary. — [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4)
- DeepPCB reports per-board completion distributions (share of boards at ≥95%) rather than a pooled net
  percentage. — [DeepPCB](https://deeppcb.ai/pcb-autorouter-benchmark-2026/)

### Inferences
- "3/4 routed" as an estimate of a rate: the 95% Wilson interval for 3 of 4 is roughly 30%–95% (my
  calculation). It supports no percentage claim at all.
- To state "≥90% clean pass" at 95% confidence: 29–30 boards with zero failures (0.9^29 ≈ 0.047). If the
  observed rate is about 95%, roughly 100–150 boards are needed for the lower bound to clear 90% (my
  approximation from the normal/Wilson formula). 14 nets from one board do not count as 14 samples: nets on
  a board compete for the same space, so failures are correlated and the effective sample is closer to 1.
- The corpus must vary what actually breaks a router: pin count per net, density (pads per cm²), THT vs SMD
  mix, crossings in the ratsnest. Five templates re-routed with small placement jitter are still about five
  designs. Jitter (random placement perturbation, rotated parts, shuffled net order) is nonetheless a cheap
  and valid *robustness* test: a result that flips with net ordering is a finding in itself.
- Meaningful at this scale: clean pass; which nets failed and why (blocked pad, no layer change available,
  ordering); per-net length / octile-MST; vias above the necessary minimum; independent DRC count;
  determinism (same input, same output). Noise at this scale: mean wirelength in mm across boards, runtime
  (all sub-second), vias-per-airwire averages, congestion maps, any pooled percentage from fewer than ~30
  boards.
- Net-ordering sensitivity deserves its own number for a sequential A* router without rip-up: route all N!
  orders when N ≤ 6 (or 50 random orders) and report best / median / worst completion. If the best order
  completes and the default does not, the router's defect is ordering/rip-up, not path search.

### Gaps
- No source prescribes a corpus size for autorouter claims; the figures above are standard binomial
  statistics applied by me, not a published EDA convention.

---

## 6. How to export from a custom engine so Freerouting or KiCad can route the identical placement

### Takeaway
The lowest-risk path in October 2026 is: write a `.kicad_pcb` from the engine, let KiCad's Python API export
the Specctra DSN, run Freerouting headless, then apply the SES either through `pcbnew.ImportSpecctraSES` or
by parsing the SES and writing tracks/vias yourself. `kicad-cli` reportedly has no Specctra subcommands.

### Cited Findings
- Freerouting is GPL-3.0, imports Specctra/Electra `.dsn` and exports `.ses`; JRE 25 is recommended by the
  current README (PCBWorld ran 2.1.0 on OpenJDK 21). A REST API (beta, access on request), a Python client
  (`freerouting-client`), Docker self-hosting and an MCP server also exist. — [Freerouting GitHub](https://github.com/freerouting/freerouting); [PCBWorld arXiv HTML](https://arxiv.org/html/2607.05915v4)
- Headless invocation and flags: `--gui.enabled=false`; `-de board.dsn` (input, optionally `+board.rules`);
  `-do board.ses` (output; `.dsn`, `.ses` or `.scr` by extension); `-mp N` max autorouter passes; `-mt N`
  optimizer threads (0 disables optimisation); `-inc GND,VCC` skip net classes; `-drc out.json` writes a DRC
  report in KiCad's JSON DRC schema; `-is sequential|random|prioritized` item selection; `-da` disables
  anonymous analytics; `--router.optimizer.improvement_threshold=` stop threshold. Example:
  `java -jar freerouting.jar --gui.enabled=false -da -de MyBoard.dsn -do MyBoard.ses -drc MyBoard-drc.json -mp 10 -mt 4`.
  The CLI doc lists no random-seed option, no routing time limit and no JSON routing-statistics output. — [Freerouting docs/command_line_arguments.md](https://github.com/freerouting/freerouting/blob/master/docs/command_line_arguments.md)
- KiCad's pcbnew Python API has `ExportSpecctraDSN` and `ImportSpecctraSES` overloads that take a board
  object and a path and are documented as usable in a standalone script without a PCB_EDIT_FRAME. — [KiCad doxygen, pcbnew_scripting_helpers](https://docs.kicad.org/doxygen/pcbnew__scripting__helpers_8h.html)
- Reported problems: a nightly-build user got `False` from `ExportSpecctraDSN("output.dsn")` while the GUI
  export worked — [KiCad forum](https://forum.kicad.info/t/python-apis-exportspecctradsn-broken-in-nightly/24011);
  a forum request describes SES import as requiring an active pcbnew window, with an xvfb workaround called
  brittle — [KiCad forum](https://forum.kicad.info/t/gui-agnostic-import-for-specctra-session-to-allow-headless-scripted-auto-routing/41063).
- A third-party project (kicad-mcp) states KiCad 10's `kicad-cli` has no Specctra subcommands and kipy has no
  Specctra support, and therefore applies the SES by injecting wires and vias directly into the `.kicad_pcb`
  with a pure-Python parser. — [kicad-mcp commit](https://git.supported.systems/MCP/kicad-mcp/commit/00fb40fbf46de8618a6e33ba70e4f29e4b20a598)
- A pure-Python, dependency-free port of the Freerouting engine ("freeroute", `freeroute board.dsn -o
  board.ses`) exists but is described as pre-alpha. — [freeroute README](https://git.supported.systems/warehack.ing/freeroute/src/branch/main/README.md)
- KiCadRoutingTools routes `.kicad_pcb` files directly (no DSN step), KiCad 9/10. — [KiCadRoutingTools](https://github.com/atomic14/KiCadRoutingTools)

### Inferences
- Pipeline for the reader (all free; Freerouting GPL-3.0 is used as a separate process on files, which does
  not affect the licence of the reader's own code):
  1. Board IR → `.kicad_pcb` (footprints with pads and net names, Edge.Cuts outline, net classes with the
     same clearance and track width the A* router uses, via size). This is the already-planned B4 step.
  2. `python -c "import pcbnew; b = pcbnew.LoadBoard('x.kicad_pcb'); assert pcbnew.ExportSpecctraDSN(b, 'x.dsn')"`
     using KiCad's bundled Python; check the return value.
  3. Freerouting headless with `-mp 10`–`20`, `-drc` for a second DRC opinion.
  4. Read results: either `ImportSpecctraSES` then sum track lengths and count vias through pcbnew and run
     `kicad-cli pcb drc`, or parse the SES directly (it is an S-expression listing wires as point paths and
     vias per net; lengths are a sum of segment lengths) — parsing the SES is enough to obtain reference
     wirelength and via count without any import step.
  5. In the other direction, write the A* router's own tracks into the `.kicad_pcb` and run KiCad DRC on it:
     that gives the independent DRC count and KiCad-measured length/vias on the same footing as the reference.
- Writing DSN directly from the Board IR is possible but DSN needs padstack and image (footprint)
  definitions, a structure block with layers/boundary/rules and a network block; letting KiCad generate it
  avoids a class of errors where the reference router sees different geometry than the custom router did.
- Because Freerouting exposes no seed and PCBWorld still averaged it over 4 seeds, run it a few times and
  with `-is random` to see the spread before treating one result as "the" reference.
- Units and rules must be identical on both sides (clearance, track width, via drill/diameter, allowed
  layers, grid): a reference routed with 0.2 mm clearance says nothing about a router held to 0.3 mm.
- Fairness detail for a grid router: also report results at the router's grid pitch, since KiCadRoutingTools
  was benchmarked at 0.1 mm and OrthoRoute at 0.4 mm, and a coarse grid alone can explain lost completion.

### Gaps
- Not verified on Windows with KiCad 9/10 in this session: whether `ExportSpecctraDSN(board, path)` and
  `ImportSpecctraSES(board, path)` work headless today (the bug reports are from older/nightly builds).
- Whether KiCad 9's `kicad-cli` has a Specctra command was not confirmed either way; only a secondary source
  says KiCad 10's does not.
- Freerouting's current release number/date and whether its CLI prints the V2 scores to the log were not
  confirmed.
