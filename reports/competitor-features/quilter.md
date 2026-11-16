# Quilter — feature inventory
Read 2026-11-13. Vendor: Quilter AI (Los Angeles) · Latest release found: changelog entry 2026-09-30 (new router strategy [ALPHA], Pass/Warn/Fail counts, native Xpedition files); no changelog or newsroom item dated October or November 2026 was found · Earlier teardown: `C:\Users\KIIT\cursor-electronics\reports\competitors\quilter.md` (2026-10-21), and the Quilter section of `reports/Physics layout validation - what the market does and what Circuit OS can build.md` (2026-10-16)

## In one paragraph

Quilter is a cloud (or self-hosted) service that places and routes a printed circuit board from a **finished schematic and board file** made in Altium, KiCad, Cadence Allegro or Siemens Xpedition, and returns several ranked layout candidates in the same native format. It is sold per project, priced by the number of unrouted pins, to hardware teams (defense, automotive and distributors are named) and has SOC 2 Type II and a self-hosted Kubernetes option. What it automates is placement, BGA fanout, routing, power pours and stackup-aware trace geometry. Its "physics" is three things: a commercial 2D quasi-static field solver (Simbeor) that sets impedance-controlled widths, IPC-2221 width and heating rules for power nets, and eight Physics Rule Checks (PRCs) that measure geometry against example tolerances; since 2026-08-31 it adds a beta point-to-point DC IR-drop simulation. It stops at the layout: it does not draw or check the schematic, choose parts, simulate signals, check EMC or creepage, write firmware, or emit Gerbers, and its own docs tell users to keep running their own signal simulation, DRC and design review. Stated envelope: up to 5,000 pins, 48 V, 10 A, signals under 6 GHz, through-vias only.

## Features

Sources used repeatedly: [changelog](https://www.quilter.ai/changelog) · [what Quilter does well](https://docs.quilter.ai/about-quilter/what-quilter-does-well.md) · [what Quilter isn't](https://docs.quilter.ai/about-quilter/what-quilter-isnt.md) · [FAQ](https://docs.quilter.ai/about-quilter/faq.md) · [pricing](https://www.quilter.ai/pricing) · [newsroom](https://www.quilter.ai/newsroom) · [docs index](https://docs.quilter.ai/llms.txt). All read 2026-11-13 unless the cell says otherwise.

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | No | Input is a completed schematic plus a board file with one closed outline; Quilter calls itself "not a CAD tool" but a submission and review interface | read | [what Quilter isn't](https://docs.quilter.ai/about-quilter/what-quilter-isnt.md), [design your schematic](https://docs.quilter.ai/using-quilter/design-your-schematic.md) |
| A2 | Structured form / spec input | Partial | Setup flow (four pages since 2026-03-26) where the user states physics constraints: power-net max current, impedance targets and overrides (2026-05-01), component-to-pin proximity (2026-05-01), floorplan [BETA] (2026-06-30), keepouts, regions | read | [changelog](https://www.quilter.ai/changelog), [physics constraints](https://docs.quilter.ai/physics-constraints/overview.md) |
| A3 | Design as code | Not found | No language or scripting page in the 74-page docs index | not found | [docs index](https://docs.quilter.ai/llms.txt) |
| A4 | Imports an existing design | Yes | Schematic + board from Altium, KiCad, Cadence Allegro (BRD, XML, QLT; DSN schematic since 2026-06-30), Siemens Xpedition (zipped native project since 2026-09-30). Zuken CR-8000 and EasyEDA have doc pages under "Other CAD tools" whose content could not be read | read | [changelog](https://www.quilter.ai/changelog), [docs index](https://docs.quilter.ai/llms.txt) |
| A5 | Requirement kept as its own artifact | Partial | Constraints live per job and are reviewed before submission; Projects (2026-04-07) group every job of one design. No separate requirement document or trace from requirement to candidate | inference (from the setup flow and Projects entries) | [changelog](https://www.quilter.ai/changelog) |
| A6 | Asks clarifying questions or refuses | Partial | Does not ask; constraints it does not recognise are routed as "generic, low-speed digital signals". Out-of-envelope work (above 48 V, >20% pin density) is "best handled manually". Candidates with DRC errors are not surfaced | read | [physics constraints](https://docs.quilter.ai/physics-constraints/overview.md), [what Quilter does well](https://docs.quilter.ai/about-quilter/what-quilter-does-well.md), [candidate details](https://docs.quilter.ai/candidate-review/candidate-details.md) (read 2026-10-16) |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates a schematic from intent | No | "Does Quilter generate schematics? No" — the schematic must be finished first | read | [design your schematic](https://docs.quilter.ai/using-quilter/design-your-schematic.md) |
| B2 | AI copilot in an existing schematic | No | "Quilter is not a copilot" | read | [what Quilter isn't](https://docs.quilter.ai/about-quilter/what-quilter-isnt.md) |
| B3 | Part selection with reasons | No | Uses the user's parts and footprints as given | read | [FAQ](https://docs.quilter.ai/about-quilter/faq.md) |
| B4 | Reusable modules / reference designs | Not found | Nothing in the docs index | not found | [docs index](https://docs.quilter.ai/llms.txt) |
| B5 | ERC (voltage-aware?) | No | "Quilter doesn't check schematic logic or design intent beyond what you specify"; it does not review datasheets for floating pins | read | [what Quilter isn't](https://docs.quilter.ai/about-quilter/what-quilter-isnt.md) |
| B6 | Hierarchy / multi-sheet | Partial | Parses hierarchical schematics; no symmetric layout for multi-channel designs | read | [design your schematic](https://docs.quilter.ai/using-quilter/design-your-schematic.md) |
| B7 | Library size; symbols/footprints from datasheets | No | Keeps the footprints defined in the user's ECAD tool; generates none | read | [FAQ](https://docs.quilter.ai/about-quilter/faq.md) |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | No | User remains responsible for "Signal simulation and validation"; no circuit simulator in docs | read | [what Quilter isn't](https://docs.quilter.ai/about-quilter/what-quilter-isnt.md) |
| C2 | Tolerance / Monte Carlo / worst case | Not found | PRC tolerances are example acceptable ranges, not a statistical analysis | not found | [PRC overview](https://docs.quilter.ai/physics-rule-checks-prcs/overview.md) |
| C3 | Formal proof / exhaustive verification | Not found | — | not found | [docs index](https://docs.quilter.ai/llms.txt) |
| C4 | Signal integrity | Partial | **Before routing:** trace geometry for impedance from Simbeor (Simberian), a commercial 2D quasi-static solver, since 2026-04-07; any differential target since 2026-06-30; per-net overrides since 2026-05-01. Accuracy stated only below 6 GHz. **After routing:** PRCs Invalid Width Span (±10% of nominal), Uncoupled Spacing, Length Mismatch, Ground Plane Overlap. No reflection, crosstalk or eye simulation. Included in the per-project price | read | [changelog](https://www.quilter.ai/changelog), [single-ended impedance](https://docs.quilter.ai/physics-constraints/single-ended-impedance-control.md), [what Quilter does well](https://docs.quilter.ai/about-quilter/what-quilter-does-well.md) |
| C5 | Power integrity / IR drop | Partial | **After routing:** "Voltage drop for power pours [BETA]" (2026-08-31): point-to-point DC IR drop on power nets, source and sink set by the user, "not yet a full power-integrity sign-off". Solver not named. No AC PDN impedance, plane resonance or decap optimisation found in the changelog | read | [changelog](https://www.quilter.ai/changelog) |
| C6 | Thermal | Partial | **Before routing:** power-net widths from IPC-2221 heating (named in the 2026-03-26 changelog; the power-nets page says only "IPC calculations"); default 200 mA below 3 V, 500 mA above. **After routing:** Overheated Length PRC flags segments whose estimated rise exceeds 20 °C. No board-level thermal simulation | read | [power nets](https://docs.quilter.ai/physics-constraints/power-nets.md), [changelog](https://www.quilter.ai/changelog) |
| C7 | EMC / EMI | Not found | FAQ says PRCs cover "considerations such as thermal management, EMI, and impedance control", but no EMI PRC is documented; Ground Plane Overlap is the nearest return-path check. Three future checks are listed by name only: Top Plane Ground Pour, Neck Downs, Trace Proximity (no dates) | not found | [FAQ](https://docs.quilter.ai/about-quilter/faq.md), [future PRC2s](https://docs.quilter.ai/physics-rule-checks-prcs/future-prc2s.md) |
| C8 | Creepage / clearance from voltage | No | "doesn't currently support the constraints needed for dielectric breakdown, creepage, and arcing"; high-voltage signals must be separated manually. Region ground pours "for isolation and high-voltage sections" since 2026-03-26 | read | [what Quilter does well](https://docs.quilter.ai/about-quilter/what-quilter-does-well.md), [changelog](https://www.quilter.ai/changelog) |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Yes | Reinforcement-learning placement; pre-placed parts kept; placement regions, single-sided placement, floorplan [BETA]; experimental placement engines tagged [BETA] (2026-07-31) "may ignore some constraints"; power pins oriented to pours (2026-08-31) | read | [changelog](https://www.quilter.ai/changelog), [docs index](https://docs.quilter.ai/llms.txt) |
| D2 | Automatic routing | Yes | Layers: "2-layer boards to stack-ups of 10 or more", "no fixed upper limit". Through-vias only (blind/buried "in active development", entry dated 2026-05-31). Completion: goal 100%; 98% on Project Speedrun (843 parts, 8 layers, Dec 2025). Time: "first candidates often within the first hour", "fab-ready designs in under 4 hours" (vendor claims). New router [ALPHA] for boards under 400 pins (2026-09-30). Automated BGA fanout (2026-05-01; press 2026-07-08, beta) | read | [FAQ](https://docs.quilter.ai/about-quilter/faq.md), [pricing](https://www.quilter.ai/pricing), [changelog](https://www.quilter.ai/changelog), [press](https://www.quilter.ai/newsroom/quilter-bga-fanout-automation-2026-releases) |
| D3 | Constraint management | Yes | "Circuit Comprehension" detects power nets, diff pairs, crystals, converters, bypass caps from net classes, names, pins and topology; single-ended impedance is manual; timing-sensitive length matching "coming soon". Clearance constraints [BETA] read from input files, Altium only (2026-05-01) | read | [physics constraints](https://docs.quilter.ai/physics-constraints/overview.md), [changelog](https://www.quilter.ai/changelog) |
| D4 | Stackup and controlled impedance | Yes | Stackup material properties drive Simbeor impedance per layer. Contradiction: "How does Quilter work" says it explores several stack-ups at once; the 2026-03-26 changelog says "Each job now builds one stackup". The single-ended page still lists only 50 Ω and 75 Ω at 5%, while the July 2026 press release says the target limit was removed | read | [how Quilter works](https://docs.quilter.ai/about-quilter/how-does-quilter-work.md), [changelog](https://www.quilter.ai/changelog), [single-ended impedance](https://docs.quilter.ai/physics-constraints/single-ended-impedance-control.md) |
| D5 | DRC | Partial | Candidates with DRC errors are not surfaced; fab rules are loaded per fabricator and drawn to scale (2026-07-31). Docs still make "running DRCs" the user's job | read | [candidate details](https://docs.quilter.ai/candidate-review/candidate-details.md) (2026-10-16), [what Quilter isn't](https://docs.quilter.ai/about-quilter/what-quilter-isnt.md) |
| D6 | 3D view and MCAD exchange | Not found | Candidate Reviewer is a 2D view with layer presets; no 3D or STEP page in the docs index | not found | [docs index](https://docs.quilter.ai/llms.txt) |
| D7 | Length tuning / differential pairs | Partial | Diff pairs routed coupled; any differential impedance (2026-06-30); Length Mismatch PRC checks within a pair (0-1 cm example). No general length tuning; avoids diff pairs on 2-layer boards; no coplanar waveguide | read | [changelog](https://www.quilter.ai/changelog), [differential pairs](https://docs.quilter.ai/physics-constraints/differential-pairs.md) (2026-10-21) |
| D8 | HDI / flex / rigid-flex | Partial | Speedrun was built as 8-layer HDI, but the router places through-vias only; blind/buried vias not shipped. Flex / rigid-flex: not found | read | [changelog](https://www.quilter.ai/changelog), [Speedrun](https://www.quilter.ai/project-speedrun) (2026-10-16) |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | No | Product is PCB layout from a finished schematic only | read | [design your schematic](https://docs.quilter.ai/using-quilter/design-your-schematic.md) |
| E2 | Pin-mux / peripheral configuration | No | Same: layout only | read | as E1 |
| E3 | Compiles / tests firmware | No | Same | read | as E1 |
| E4 | Protocol stacks | No | Same | read | as E1 |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains each choice | Partial | Per-PRC pages explain why a check failed; no per-decision rationale for placement or routing | read | [PRC overview](https://docs.quilter.ai/physics-rule-checks-prcs/overview.md) |
| F2 | Confidence / evidence grading per decision | Partial | Per-candidate Pass/Warn/Fail counts (2026-09-30); sorts "Recommended", "Best PRCs", "Easiest to Fab", "Fewest Layers". Not per decision | read | [changelog](https://www.quilter.ai/changelog), [sorting](https://docs.quilter.ai/candidate-review/sorting.md) (2026-10-16) |
| F3 | Automated design review | Yes | Eight PRCs (Pin Distance, Trace Path Length, Layer Switch Count, Ground Plane Overlap, Invalid Width Span, Uncoupled Spacing, Length Mismatch, Overheated Length), DRC filter, unrouted-net review (2026-06-30) | read | [PRC overview](https://docs.quilter.ai/physics-rule-checks-prcs/overview.md), [changelog](https://www.quilter.ai/changelog) |
| F4 | Checks grounded in datasheets | No | "We don't automatically review datasheets" | read | [what Quilter isn't](https://docs.quilter.ai/about-quilter/what-quilter-isnt.md) |
| F5 | Audit trail of AI actions | Partial | Console drawer of job messages and errors (2026-04-07); job/project notes (2026-07-31); Projects keep iterations. Not an audit of AI decisions | read | [changelog](https://www.quilter.ai/changelog) |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Not found | Iteration is "edit and iterate": change inputs and resubmit | not found | [docs index](https://docs.quilter.ai/llms.txt) |
| G2 | Version history, diff, branch, restore | Partial | Projects group every job of one design (2026-04-07); unlimited iterations within a 10% BOM change. No diff found | read | [changelog](https://www.quilter.ai/changelog), [pricing](https://www.quilter.ai/pricing) |
| G3 | Comments / review workflow / roles | Partial | Notes on jobs and projects by users and permitted Quilter staff (2026-07-31); identity-provider sign-in on self-host. Roles not found | read | [changelog](https://www.quilter.ai/changelog), [pricing](https://www.quilter.ai/pricing) |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | No | Uses the user's BOM; a BOM change above 10% starts a new (paid) project | read | [pricing](https://www.quilter.ai/pricing) |
| H2 | Live price and stock | Not found | — | not found | [docs index](https://docs.quilter.ai/llms.txt), [pricing](https://www.quilter.ai/pricing) |
| H3 | Alternates / substitution | Not found | — | not found | [docs index](https://docs.quilter.ai/llms.txt) |
| H4 | Fabrication outputs | Partial | Returns candidates in the native ECAD format (Altium, Allegro, Xpedition, KiCad); Gerber, ODB++ or IPC-2581 not mentioned; fabrication is the user's job | read | [pricing](https://www.quilter.ai/pricing), [what Quilter isn't](https://docs.quilter.ai/about-quilter/what-quilter-isnt.md) |
| H5 | DFM / DFA | Partial | Fabricator rule sets preloaded and editable; trace/space and via/drill minimums drawn to scale (2026-07-31); "Easiest to Fab" sort. A geometric constraint set, not a DFM report | read | [changelog](https://www.quilter.ai/changelog), [fabricators](https://docs.quilter.ai/design-parameters/fabricators.md) (index) |
| H6 | Order from a fab inside the tool | Not found | A "Pre-supported fabs" page exists in the index; no ordering flow found | not found | [docs index](https://docs.quilter.ai/llms.txt) |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Yes | Browser submission-and-review web app; no plugin | read | [what Quilter isn't](https://docs.quilter.ai/about-quilter/what-quilter-isnt.md) |
| I2 | API, CLI, headless | Not found | No API, CLI or scripting page in docs, FAQ or pricing; upload and download are in the web UI | not found | [docs index](https://docs.quilter.ai/llms.txt), [FAQ](https://docs.quilter.ai/about-quilter/faq.md) |
| I3 | Self-host; certifications | Yes | Cloud on AWS is "SOC 2 Type 2 compliant" (independent audit announced 2026-03-10). Self-hosted: Kubernetes Helm chart (EKS named), NVIDIA GPUs with ≥16 GB VRAM, air-gapped supported, IdP sign-in. Isolated AWS / GovCloud. ITAR named as a reason for on-prem; no ITAR or FedRAMP certification claimed | read | [pricing](https://www.quilter.ai/pricing), [FAQ](https://docs.quilter.ai/about-quilter/faq.md), [newsroom](https://www.quilter.ai/newsroom) |
| I4 | Pricing | Partial | Per project, priced by unrouted pins at upload; pre-routed pins free; unlimited iterations within 10% BOM change; guided onboarding. No figures. Enterprise usage tracked against annual commitments. Self-host costs more. Free Non-Commercial tier: its terms permit training on inputs; paying customers' designs are not trained on | read | [pricing](https://www.quilter.ai/pricing), [FAQ](https://docs.quilter.ai/about-quilter/faq.md) |
| I5 | Who it is sold to | Yes | Hardware teams; press names defense contractors (spaceflight qualification), a Tier-1 automotive supplier, an electronics distributor | summary | [iConnect007, Oct 2025](https://iconnect007.com/article/147236/quilter-secures-25m-series-b-to-eliminate-manual-pcb-design-with-physicsdriven-ai/147233/design) |
| I6 | Company facts | Yes | $25M Series B led by Index Ventures (2025-10-07), about $40M raised in total, investors incl. Benchmark, Coatue, Root; founded 2019 (some sources say 2021). Eric Bogatin named first Technical Fellow 2026-09-09. Partners named on pricing page: AWS, NVIDIA, Siemens | summary (funding); read (Bogatin, partners) | [BusinessWire](https://www.businesswire.com/news/home/20251007165399/en), [newsroom](https://www.quilter.ai/newsroom), [pricing](https://www.quilter.ai/pricing) |
| I7 | Interop with KiCad, Altium, OrCAD/Allegro | Yes | Round trip in native format for Altium, Allegro, Xpedition and KiCad. Supported the KiCad 10 Allegro importer (KiCad blog, 2026-02) | read | [pricing](https://www.quilter.ai/pricing); KiCad blog via `Generative EDA tool feature spec.md` |
| I8 | Open source | No | Proprietary hosted service | inference (no source repository; licence terms on pricing/FAQ) | [pricing](https://www.quilter.ai/pricing) |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | No RS-485, 4-20 mA or 24 V I/O constraint type | not found | [physics constraints](https://docs.quilter.ai/physics-constraints/overview.md) |
| J2 | Power electronics | Partial | ≤48 V, ≤10 A recommended; switching-converter placement constraint; power pours planned to connect same-net vias (2026-08-31) | read | [what Quilter does well](https://docs.quilter.ai/about-quilter/what-quilter-does-well.md), [changelog](https://www.quilter.ai/changelog) |
| J3 | RF / high speed | Partial | Under 6 GHz; diff pairs (USB, PCIe-class), LPDDR4 trained on Speedrun; no coplanar waveguide | read | [what Quilter does well](https://docs.quilter.ai/about-quilter/what-quilter-does-well.md), [Speedrun](https://www.quilter.ai/project-speedrun) (2026-10-16) |
| J4 | Safety / regulatory standards | No | No creepage, dielectric breakdown or arcing constraints; IPC-2221 for trace heating only | read | [what Quilter does well](https://docs.quilter.ai/about-quilter/what-quilter-does-well.md) |
| J5 | Stated limits | Yes | ≤5,000 pins; pin density >20% best done manually; ≤48 V; ≤10 A; <6 GHz; through-vias only; ALPHA router <400 pins | read | [what Quilter does well](https://docs.quilter.ai/about-quilter/what-quilter-does-well.md), [changelog](https://www.quilter.ai/changelog) |

## Quilter's physics, precisely (for the C and D comparison)

| What | Computed by | When | Included or add-on | Guarantee type |
|---|---|---|---|---|
| Impedance-controlled trace width and pair spacing | Simbeor (Simberian) 2D quasi-static field solver, from stackup material properties | Before routing (geometry is chosen from it) | Included | Physics simulation, stated accurate only below 6 GHz |
| Power-net trace width | IPC-2221 heating calculation from copper weight and current (defaults 200/500 mA) | Before routing | Included | Empirical chart rule |
| DC IR drop on power pours | Unnamed solver, point-to-point, user-chosen source and sink | After routing, beta since 2026-08-31 | Included (beta) | Physics simulation, "not a full power-integrity sign-off" |
| Eight PRCs | Geometry measurement against example tolerances; Overheated Length uses an analytic temperature-rise estimate | After routing, on every candidate | Included | Rule check |
| DRC | Fab rule set per fabricator | After routing; failing candidates hidden | Included | Rule check |
| SI simulation, AC PI, EMC, board thermal, creepage | — | — | Not offered | — |

Quilter's own pages describe this as "physics-driven reinforcement learning ... evaluating them with Physics Rule Checks" (FAQ) and say users remain responsible for signal simulation and validation ([what Quilter isn't](https://docs.quilter.ai/about-quilter/what-quilter-isnt.md)). Hiring Eric Bogatin (2026-09-09) signals SI/PI ambitions; no SI/PI feature tied to it has shipped (inference from the changelog ending 2026-09-30).

## What changed since the 2026-10-21 teardown

- **No new product release.** The changelog still ends at 2026-09-30, and the newsroom's latest item is 2026-09-09 (read 2026-11-13).
- **Facts the teardown did not have:** SOC 2 Type II audit (press release 2026-03-10); a self-hosted deployment with stated hardware (Helm chart, NVIDIA GPUs ≥16 GB, air-gapped supported); isolated AWS / GovCloud; enterprise annual commitments with a usage dashboard; paying customers' data not used for training; Eric Bogatin as Technical Fellow (2026-09-09); vendor time claims ("first candidates within the first hour", "fab-ready under 4 hours"); stated pin-density limit (>20% best done manually).
- **Through-vias only is now read, not summary**: the changelog states "Quilter currently routes through-vias only" in an in-progress entry dated 2026-05-31. The teardown marked this as a search snippet.
- **Contradictions found in Quilter's docs:** stack-up exploration (several per job on one page, one per job in the changelog), and impedance targets (50/75 Ω only on the single-ended page against "any differential impedance" and a removed limit in the changelog and press).
- **The FAQ's wording has moved toward the PRCs.** The physics report quoted the FAQ as claiming "detailed physics simulations". Today's read attributes thermal, EMI and impedance to the PRCs instead. That phrase may still be on the page: the fetch tool summarises, so check the exact wording before quoting either version.

## What the owner's market page gets wrong about this product

Only the cells the earlier reports recorded are judged here. The page's other Quilter cells were not available to this researcher.

| Row | Page says | Evidence says |
|---|---|---|
| Physics layout validation | Yes, best-in-class | Impedance geometry from a commercial 2D solver, IPC-2221 width rules, eight geometric PRCs and a **beta** DC IR drop. No SI, AC PI, EMC, thermal or creepage simulation. It is best among the AI layout tools on declared constraints. The best in class are Siemens HyperLynx, Cadence Sigrity/Clarity/Celsius, Ansys SIwave and Keysight PIPro (see `siemens-xpedition-pads.md` and `cadence-allegro-orcad-x.md`) |
| Explanation | Physics scorecard | A per-candidate Pass/Warn/Fail count of rule checks, plus four sort orders. The word "scorecard" is not used |
| Version history | No | Partial: Projects group iterations (2026-04-07) and notes were added (2026-07-31); no diff |
| Schematic generation, component selection, SPICE, firmware, BOM pricing | (if marked Yes or Partial anywhere) | All No: Quilter starts from a finished schematic and returns a layout |
| Gerber + fab export, DFM report | (if marked Yes) | Native ECAD files only, with no Gerber. "DFM" here means loaded fab rules and an "Easiest to Fab" sort, not a report |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

Circuit OS side: `MENTAL_MODEL.md` §4 (PCB engine experimental, flag-gated, off in production); the code table in `reports/Physics layout validation - what the market does and what Circuit OS can build.md` (checked against code 2026-10-16); `.claude/CLAUDE.md` project structure (proof/, firmware compile gate, verify.py).

**Quilter ahead**
- Scale: 5,000 pins and 10+ layers, against Circuit OS's greedy placer and A* router (2 layers, at most 40 parts, behind a flag).
- Impedance: Simbeor-computed geometry. Circuit OS has no impedance computation, and its stackup fields are unread.
- Layout physics shipped: IPC-2221 widths, 8 PRCs, DC IR drop beta. Circuit OS has none at layout level.
- Native round trip with four commercial ECAD tools; automated BGA fanout; power pours; real fabricated boards (Speedrun).
- Enterprise posture: SOC 2 Type II, self-host, GovCloud.

**Circuit OS ahead**
- The front half: English or form → IntentIR → CircuitIR → schematic, firmware (compiled before shown), SPICE and BOM. Quilter starts after all of that.
- Voltage and current checks proved with z3 over tolerance boxes, at schematic level. Quilter has no schematic checks, and its power-net currents default to 200/500 mA unless typed in.
- Constraints known from the IR (which capacitor decouples which pin) rather than guessed from net names.
- Pin-map check against the KiCad library in `pcb_engine/verify.py`; Quilter uses footprints as given.
- An HTTP API. No Quilter API was found.

**Neither:** creepage derived from voltage, EMC, AC PDN impedance.

## Not verified

- Which solver runs the DC IR beta, and its accuracy.
- Whether Quilter outputs Gerbers in any form (only "native format" is stated).
- Zuken CR-8000 and EasyEDA support status: the doc pages exist but their content could not be read.
- Free-tier limits (pins, jobs) and any price figure.
- Whether the FAQ still says "detailed physics simulations" (wording changed between reads, or the fetch summarised it).
- The 8-layer HDI build of Speedrun against the "through-vias only" router statement: perhaps HDI vias were added by hand or by the fab. Not established.
- The 2025-10 funding total ($40M) and founding year (2019 or 2021): sources conflict.
