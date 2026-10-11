# What you can actually check, in software, this week

This answers one question: how much of the PCB router can be validated without
fabricating anything, and what specifically do you run. It builds on
`PCB routing validation methods.md` and its verification ledger and goes deeper
on the nine items the ledger says still rested on the first pass alone. Everything
here is free; nothing here needs a board, a part, or a purchase.

The short answer is that software can decide almost everything that matters about
this router, because a routing result is hard to produce but cheap to check — and
the very first check you write, an independent judge of connectivity, already
found a defect that the product ships today. Running it turned up not one but
four concrete faults, three of them executed and reproducible on this machine. So
this is not a menu of possibilities. It is what happened when the checks were
built and run, and then the ladder that follows from it.

## Part 1 — What running the checks actually found

The router's own success metric is wrong, and it is wrong on the board the
product ships.

`Board.unrouted(tol=0.35)` does not measure distances. It rounds each coordinate
to a 0.35 mm cell with `round(p / tol)` and reports a connection routed only if a
track endpoint lands in the **exact same cell** as the pad centre. Two points can
be fractions of a millimetre apart and still straddle a cell edge. The predicate
is "same cell", not "within 0.35 mm", and that is not a proxy for it.

This was reproduced from nothing on a board with one net, two pads, one track
drawn straight between them, moving the far pad away from the track end in
0.001 mm steps:

| pad B offset from the track end | router says | a judge that actually touches copper says | physically |
|---|---|---|---|
| 0.000–0.100 mm | ROUTED | ROUTED | touching |
| **0.160–0.490 mm** | **unrouted** | **ROUTED** | **touching** |
| 0.600 mm | unrouted | unrouted | apart |

From 0.16 mm the router calls a connection broken while the copper physically
overlaps the pad. The threshold is not the tolerance's 0.35 mm; it is wherever the
cell boundary happens to fall. Sweeping the pad across a full cell and holding the
offset fixed at 0.200 mm — comfortably inside the nominal tolerance — **57% of
positions are reported unrouted**, and that is exactly the predicted phase
fraction, 0.200 / 0.350. Traces at 0.002 mm separation are reported as different
cells when they straddle a boundary.

The count this corrupts is not a side number. `kernel.score` computes
`unrouted = len(board.unrouted())` and weights it at **1000 points**, against 250
for a DRC error and 2 for a via. `compile_board` then picks the winning candidate
with `generate_candidates(...)[0]`, ranked by that same score. So the defective
count drives candidate **selection**, not only the label in the UI.

On the real board the product compiles, `dht22_relay_monitor`, this is total. It
is 12 connections. Across 16 orderings the router reports **4 unrouted every time**
and the independent judge reports **0 every time** — the board is fully routed, on
every seed, and the product says 8 of 12. The reported score is about 4149 of
which **4000 is the phantom**; the real signal is the remaining ~150. Every one of
the four phantom failures has copper ending 0.054 to 0.127 mm from the pad centre,
well inside the pad and well inside the nominal tolerance:

| net | pad A | pad B | closest track end to pad A / pad B | judge |
|---|---|---|---|---|
| VCC_5V | (24.1, 26.7) | (29.3, 26.7) | 0.099 mm / 0.127 mm | connected |
| VCC_5V | (29.3, 26.7) | (27.9, 15.2) | 0.127 mm / 0.100 mm | connected |
| VCC_5V | (29.3, 26.7) | (46.9, 21.6) | 0.127 mm / 0.071 mm | connected |
| RELAY_COIL_NEG | (29.3, 36.7) | (33.0, 21.6) | 0.127 mm / 0.054 mm | connected |

Because the phantom is a constant 4 here, ranking among these seeds is unharmed —
the penalty cancels. On the demo board it is not constant: the router's own count
runs 11 to 16 across 24 orderings while the true count runs 5 to 12, so the two
disagree by 5 or 6 a board and the ranking is scrambled. At the router's own modal
value of 13, the true number ranges from 5 to 12. **The metric barely constrains
the quantity it exists to measure.**

Three more faults fell out of the same work.

*The DRC kernel silently misses real clearance violations.* Its broad phase pads
each track's bounding box by its full width, then requires a narrow-phase
separation of `clearance + w1/2 + w2/2`. Those disagree whenever
`clearance > (w1 + w2)/2`. Executed on two parallel 0.2 mm tracks: at clearance
0.25 mm, separations of 0.40 to 0.44 mm are genuine violations and the checker
reports none; at clearance 0.30 mm it misses 0.40 through 0.49 mm. Eight real
violations were skipped across the sweep, at distances it never measured. This was
a reading in the ledger; it is now a confirmed defect with an exact trigger, and
because the router scores candidates through this kernel, "0 DRC errors" cannot be
trusted at clearance 0.25 mm or above.

*The floor everyone quotes was not a floor.* The earlier harness summed Manhattan
distance over a Euclidean-chosen spanning tree and called it 365.8 mm. That is the
rectilinear MST, which sits **above** the optimum, and it was in Manhattan against
a router that moves at arbitrary angles. Recomputed: the rectilinear MST is
358.6 mm, the valid rectilinear floor `max(span, ⅔·MST)` is **307.9 mm**, the
octile floor is **265.5 mm**, and because the router emits segments like
`(11.25, 9.00)→(30.00, 14.75)` — slope 0.307, not 45° — the only universal floor
is straight-line distance, **250.0 mm**. The quoted figure overstated the true
floor by 46%.

*The DSN bridge cannot carry vias.* `to_dsn()` emits no `(via ...)` padstack and
no via rule, so a reference router fed this file is restricted to one layer while
this router uses two. It also stamps every pad on all signal layers, making SMD
pads look through-hole. Freerouting cannot serve as a fair reference until the
exporter is fixed — the blocker is the exporter, not Freerouting.

The metamorphic relations — the properties that must hold for a correct router
whatever its heuristic — all held: **40 of 40 checks across 8 seeds** (five
relations, eight orderings each). Relaxing clearance never made routing worse and
in fact improved it on every seed (worst case 12→7 unrouted); growing the outline
never made it worse; relabelling every net left the count identical; the same seed
reproduced a bit-identical board; reversing the net-class list changed nothing.
These are the checks that need no oracle, which is why they are cheap to trust —
though note what they cannot do: they detect a violation of a relation you thought
of, and nothing else.

## Part 2 — The ladder

Ranked by how much a rung changes what you can honestly claim, divided by what it
costs in hours. All of it is free. Effort is my estimate for one developer who
already has the Board IR and the router.

| # | Rung | Effort | Status | What a pass proves |
|---|---|---|---|---|
| 1 | Independent connectivity judge over copper geometry | half a day | **written and run** | Whether the board is connected, by a checker the router did not write |
| 2 | Correct floor + per-connection efficiency | hours | **written and run** | How far each route is above its geometric floor, on the connections that exist |
| 3 | Net-order permutation sweep and the isolation oracle | hours | **written and run** | Whether a failure is ordering, congestion, or modelling |
| 4 | Metamorphic relations | hours | **written and run** | Invariants a correct router must satisfy, with no ground truth needed |
| 5 | Seeded violations against the DRC kernel | a day | **partly run** | Whether the kernel fires when it should — one defect already found this way |
| 6 | Single-net exact oracles (BFS, Dijkstra) | a day | ready | That A* finds a path whenever one exists, and the cheapest one |
| 7 | Fix the DSN exporter, then Freerouting as reference | two days | blocked on rung 7a | Whether the board is routable at all, and a reference length and via count |
| 8 | Property-based fuzzing with Hypothesis | two days | ready | Minimal failing boards, shrunk automatically |
| 9 | A `.kicad_pcb` exporter, then KiCad as second judge | days | not started | Width, clearance, ring and edge limits per an engine you did not write |
| 10 | Corpus work — PCBWorld D3-A, importer, clean-pass rate | weeks | not started | A rate comparable with published baselines |

The ordering is not the same as the earlier report's, and the reason is the single
most useful structural fact this pass produced: **the whole KiCad arm is gated
behind a `.kicad_pcb` writer that does not exist.** The repository has `to_dsn()`
and nothing else — no `.kicad_pcb`, no Gerber, no SES reader. So KiCad's DRC, its
schematic parity, its Gerbers, the fab DFM tools and KiCad's own connectivity
engine all wait on one file format. Meanwhile the pure-Python arm — rungs 1 to 6
and 8 — is gated behind nothing and runs today. That is why the top of the ladder
is the Python work, and why the earlier "run KiCad DRC" rung has moved down: it is
not less valuable, it is simply blocked.

### Rung 1 — an independent connectivity judge

The router's connectivity check is the thing you least want to trust, and the
cheapest to replace. Buffer every track, via and pad of a net, union the shapes
that touch, and require that each net's pads fall in exactly one group. Shapely,
or a raster pass at a pitch finer than the 0.25 mm grid, both work; the judge
built here is about a hundred and fifty lines of plain Python, adding no new
dependency beyond the numpy the router already uses.

*It found four phantom failures on the shipped board and the mechanism behind
them.* This is the highest-value hour on the list.

### Rung 2 — a floor that is a floor, and efficiency on a complete board

Efficiency cannot be a single copper-over-floor ratio while the board is
incomplete: unrouted nets contribute floor and no copper, so the ratio measures
how much failed, not how well it routed. Two things fix it.

First, use a floor that is actually a lower bound. For a two-pin net it is
straight-line distance. For multi-pin nets it is `max(net span, ⅔ · rectilinear
MST)`, and never the MST itself — by Hwang's bound the MST is up to 3/2 of the
optimum, so it sits above. On the demo board the MST overstates the floor by up to
19.9 mm on a single nine-pad net (in the octile metric, which is where that sweep
ran).

Second, measure only the copper that exists: for each connection the judge calls
connected, walk the net's actual copper between the two pads and compare that
path length with the connection's own floor. That number means the same thing
whether or not other connections failed.

Run on the shipped board — which is fully connected, so the ratio is well defined
with no coverage caveat — the router's copper measures 167.9 mm against a
straight-line floor of 113.2 mm, an octile floor of 121.4 mm and a rectilinear
floor of 145.9 mm. That is **1.48× the euclidean bound, 1.38× the octile bound,
and 1.6% above the rectilinear minimum spanning tree.** The last comparison is
the informative one: since a spanning tree sits at or above the optimum, being
within 1.6% of it means this board's length is essentially as short as a
spanning-tree routing can be. The efficiency story on this board is that there is
almost nothing to win on length — the open questions are completion and vias, not
wirelength. Eleven vias across six nets is the other half of the picture, since
length and vias have to be read together.

Per-connection ratios — which connection is *individually* wasteful — are the
sharper measure, and they now hold up. On the demo board, over 329 connected
connections across twelve seeds, **every ratio is at or above 1** (p10 1.10×,
median 1.28×, p90 2.44×; 56% within 1.3× of their floor). The ratio cannot fall
below 1 without a phantom in the graph, and none does, which is the check on the
measurement itself.

Getting there took fixing the walker, and the fix is itself a finding about the
router's output. The first version reported ratios below 1 — physically
impossible — and the cause was not a subtle geometry bug but the router's own
shape: it splits one continuous copper run into several `Track` objects, and the
walker was charging zero for the hop between them. On a 17 mm connection that
splicing hid about 30 mm of travel across 307 junctions, and the measured path
came out at 2.6 mm. Charging each junction the distance it actually spans — along
with every pad and via edge — restores the invariant. The lesson generalises: any
tool that attributes copper by track, including the router's own length
accounting, has to say how it handles a net that is many tracks and not one.

The tail above ~3× is a real signal — those few connections do run several times
their straight-line floor — but read it in millimetres, not as a multiple: a
large ratio there is usually a very short connection whose floor is near zero,
so a 13× ratio can be a few millimetres of avoidable detour. The aggregate above
is on the shipped board and does not depend on any of this; the per-connection
distribution is the part that says *which* connections to look at.

### Rung 3 — ordering, and the isolation oracle

Route the same board under many random net orders and report best, median and
worst completion. A board that ranges across orders has an ordering and rip-up
problem; a board stuck at the same number under every order has a modelling
problem.

Then separate the third cause. For each connection the judge calls unrouted, route
it **alone on an otherwise empty board** with the same A*. A* with an admissible
heuristic is exact for existence, so a path found in isolation means the failure
was congestion — net-to-net interference the rip-up pass did not resolve — while
no path in isolation means the connection was never routable and the fault is in
the model, not the search.

On the demo board every failed connection had a path in isolation: **0 of 5 (best
seed) are modelling failures**. All of them are congestion and ordering. That is
the difference between a bug to fix and a heuristic to tune, and it took one
pass.

### Rung 4 — metamorphic relations

Five relations, none needing an oracle, all of which a correct router must satisfy:

- relaxing clearance cannot make routing worse
- growing the outline cannot make routing worse
- relabelling every net leaves feasibility identical
- the same seed reproduces a bit-identical board
- reversing the net-class list changes nothing

Each is a statement about what "routable" *means*, so a violation is a bug, not a
smell. All five held across the seeds tested. Note what this class of test cannot
do: it detects a violation of a relation you thought of, and nothing else. It is a
safety net, not a completeness proof.

### Rung 5 — prove the checkers are live

A checker that never fires is indistinguishable from a checker that finds nothing.
Apply one mutation from a clean board — move a track just under clearance, narrow
it just under minimum, shrink a via ring, delete a segment, bridge two nets, push
copper past the edge — and expect exactly one finding of the matching class, plus
the just-legal twin that must produce none. Sweep the margin so the boundary
becomes a tested decision.

This rung already paid: it is what turned the suspected DRC pre-filter defect from
a reading into a confirmation. The one test worth writing first is the pair of
parallel tracks above, at clearance 0.25 and 0.30 mm.

### Rung 6 — exact oracles for one net

Dijkstra on the same grid with the same costs is an exact oracle for a single
net's minimum cost; BFS is an exact oracle for reachability. A* disagreeing with
either on a single-net board is an unambiguous bug, with no judgement involved.
Boards generated from a known routing — draw non-crossing paths, put pads at the
ends, delete the paths — are routable by construction, so any failure on one is a
false negative. The caveat is scope: these are single-net oracles, so every net may
have a path and the board still be jointly unroutable through congestion. That is
what rung 3's isolation test is for.

### Rung 7 — the DSN exporter, then a reference router

Freerouting is the right reference: free, GPL-3.0, headless with
`--gui.enabled=false -de board.dsn -do board.ses -mp 100 -drc drc.json`. But it
cannot be one until `to_dsn()` emits vias, because a one-layer reference against a
two-layer router is not a comparison. Fixing the exporter — a via padstack, a via
rule, and pads only on their real layers — is the actual work; parsing the SES for
segment lengths and via counts needs no import step and no KiCad.

Two cautions that decide whether the comparison means anything. Rules must be
identical on both sides, since a reference routed at 0.2 mm clearance says nothing
about a router held to 0.3. And "neither router finished" proves nothing — both
are heuristics. The informative outcomes are "Freerouting routed it and this one
did not", which is a false "unroutable", and "Freerouting's checker flags a board
this kernel passed".

### Rung 8 — fuzzing

Hypothesis (MPL-2.0) generates boards, shrinks a failure to a minimal one, and
runs stateful tests of edit sequences. Applied to the connectivity judge it would
have found the quantisation bug from rung 1 automatically, by proposing nearby pad
positions. Property-based testing is free and current, and the shrinking is the
part that pays — a minimal failing board is a bug report you can act on.

## Part 3 — What software cannot settle

Stated plainly, because a ladder that oversells itself is worse than no ladder.

- **Nothing here knows whether the placement is good.** A poor route may be a
  placement fault. One study moved routed wirelength up to 25% and vias up to 50%
  through placement alone under the same router, so every comparison is valid only
  on an identical placement.
- **No software check knows whether a footprint matches the real part.** This is
  the class of bug the project already hit with SOT-23 pin order, and every tool
  on the ladder is blind to it.
- **A judge agreeing with you is not the router being right.** Work on FPGA
  place-and-route testing reports that equivalence checking *misses* real routing
  decision bugs — the same warning as the certifying-algorithm idea, that the
  trust burden sits on the checker, not on the router.
- **One judge is one author's understanding.** The union-find judge written here
  is a second opinion, not a certified oracle; it is more faithful than the
  router's endpoint test only because it measures the thing the endpoint test was
  trying to approximate.
- **There is no published "good" ratio** of wirelength to floor for PCBs. Any
  threshold is judgement; treat it as a tripwire, not a specification.
- **Nothing here validates the circuit electrically.** That is the schematic and
  simulation side, and on circuits this slow traces do not move the answer.

Three verdicts follow for every board the engine reports, instead of two:
**checked clean**, **proved within a stated scope** (this grid, these rules, this
epsilon — which is what the metamorphic relations give), and **not routed by this
heuristic**, which is not the same as unroutable.

## The harness

Every finding above came from scripts that run against the repository's own
modules with no new dependencies, in a scratch `router_check/` directory:

| Script | What it runs |
|---|---|
| `validate_router.py` | the union-find connectivity judge, the order sweep, the isolation oracle, per-connection floors |
| `repro_unrouted_bug.py` | the minimal one-net proof of the `unrouted()` defect and its phase sweep |
| `drc_prefilter.py` | the minimal proof of the DRC broad-phase defect |
| `real_board.py`, `real_board_diag.py` | the shipped `dht22_relay_monitor` board through both judges |
| `metamorphic.py` | the five sound relations over eight seeds |
| `efficiency.py` | floors per metric, and how far an MST overstates one |
| `pathlen.py` | shortest copper path between two pads, by sampling the copper |

None of them asks the router whether it succeeded. That is the whole design: the
router produces an output, the harness checks it, and the harness is authored
against the geometry rather than against the router's idea of it.

## The four fixes that follow, in order

1. Replace `Board.unrouted()` with the union-find judge. Until this is done the
   product reports a board as one-third open when it is complete, and the score it
   ranks candidates by is mostly phantom.
2. Fix the DRC broad phase to pad by `clearance + w/2`, not `w`, and add the two
   parallel-track tests at clearance 0.25 and 0.30 mm.
3. Use `max(span, ⅔·MST)` per net, and straight-line distance, as the floor.
4. Emit vias in `to_dsn()`, then run Freerouting as the reference.

None of the four needs a board, a part, or a rupee. All four are checkable against
the harness described above, which is the point: the investment is in the checker
and the export path, both of which survive the planned swap to Freerouting as a
backend.
