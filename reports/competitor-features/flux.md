# Flux (flux.ai) — feature inventory
Read 2026-11-13. Vendor: Flux (Flux.ai, Inc.) · Latest release found: "Circle it. Ask Flux. Markup mode is here" (blog, 2026-11-06); most recent capability post "Run SPICE on Your Imported Altium and Cadence Boards" (2026-11-08) · Earlier teardown: `C:\Users\KIIT\cursor-electronics\reports\competitors\flux.md` (2026-10-21)

## In one paragraph
Flux is a browser ECAD suite (schematic, PCB, and since autumn 2026 MCAD, enclosure and manufacturing quoting) driven by a cloud "AI hardware engineer" agent. It is sold per user (individual plans) and per editor (Teams), metered in Agent Compute Units (ACUs), to startups, small teams and increasingly enterprise hardware teams. The agent plans a device from a conversation, places and wires schematic parts, routes whole boards on request, runs ERC/DRC as it works, runs ngspice and (since October 2026) cloud full-wave EM, PDN and thermal analyses, checks Gerbers, compiles firmware, and gets fab quotes. Where it stops: every result is the agent's own work checked by the agent and the user; nothing is proved, no solver is named for EM/thermal, no accuracy or completion figure is published, whole-board placement is not documented, the board is limited to 8 layers in the editor, and native KiCad/Altium project export is not documented. Flux's own post says of its agent: "Do we always succeed? No."

October 2026 was a step change: between 2026-10-18 and 2026-11-11 the blog lists more than 50 posts, most of them new capabilities (EM/SI simulation, PDN, MCP server, agent teams, bring-your-own-software cloud computers, fab ordering, enclosure/MCAD). The 2026-10-21 teardown predates almost all of it.

## Features

Source key used below (all read 2026-11-13):
[price] https://www.flux.ai/pricing · [blog] https://www.flux.ai/p/blog · [home] https://www.flux.ai/ ·
[feb] https://www.flux.ai/p/blog/10x-faster-self-correcting-feb-2026-update (Feb 2026) ·
[spring] https://www.flux.ai/p/blog/spring-2026-updates-faster-ai-better-layouts-smarter-sourcing (2026-03-13) ·
[apr] https://www.flux.ai/p/blog/flux-april-2026-release-upgrades-that-make-a-real-difference (2026-04-02) ·
[summer] https://www.flux.ai/p/blog/summer-2026-updates-flux-mcp-server-and-chat-mode (2026-08-03) ·
[route] https://www.flux.ai/p/blog/agentic-routing (2026-10-28) · [routedoc] https://docs.flux.ai/tutorials/auto-layout ·
[posdoc] https://docs.flux.ai/reference/reference-positioning-routing · [port] https://www.flux.ai/docs/reference/data-portability ·
[review] https://www.flux.ai/p/blog/pcb-design-review-without-altium-license (Oct 2026) ·
[em] https://www.flux.ai/p/blog/em-simulation-of-your-routed-board (Oct 2026) ·
[si] https://www.flux.ai/p/blog/pcb-signal-integrity-simulation-every-board (Oct 2026) ·
[mc] https://www.flux.ai/p/blog/ltspice-monte-carlo (Nov 2026) · [imp] https://www.flux.ai/p/blog/spice-simulation-imported-altium-cadence-boards (2026-11-08) ·
[byos] https://www.flux.ai/p/blog/bring-your-own-software (Nov 2026) · [mcp] https://www.flux.ai/p/blog/flux-mcp-in-your-ai-tools (Oct 2026) ·
[fw] https://www.flux.ai/p/blog/embedded-unit-testing-before-hardware (Nov 2026) · [creep] https://www.flux.ai/p/blog/creepage-and-clearance-pcb (Nov 2026) ·
[gerber] https://www.flux.ai/p/blog/gerber-file-check (Oct 2026) · [fab] https://www.flux.ai/p/blog/automated-pcb-manufacturing-ai-design (Oct 2026) ·
[supply] https://www.flux.ai/p/blog/design-real-time-supply-chain-visibility-2026 (Jan 2026) ·
[know] https://www.flux.ai/p/blog/teach-flux-your-team-standards (Oct 2026) · [work] https://www.flux.ai/p/blog/ai-generated-hardware-designs-that-work (Oct 2026) ·
[eval] https://www.flux.ai/p/blog/how-to-evaluate-ai-pcb-design (Oct 2026) · [cost] https://www.flux.ai/p/blog/ai-hardware-design-more-work-per-credit (Oct 2026) ·
[raise] https://www.flux.ai/p/blog/we-raised-37m-to-take-the-hard-out-of-hardware (Feb 2026) ·
[sec] https://docs.flux.ai/faq/data-security-and-ip-protection · [vc] https://docs.flux.ai/reference/reference-version-control

### A. Input and intent
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | Yes | Agent mode completes design work from prompts; "Brainstorm" step turns a conversation into a project plan; voice dictation (Aug 2026) and phone dictation (Oct 2026) | read | [home], [summer], blog "EDA and MCAD on Your Phone" (2026-10-28, title only) |
| A2 | Structured form / spec input | Partial | Free "Chat" mode to "ask, plan, and spec your device" before building (2026-10-21); the spec is a chat/plan, no structured form found | read (home, summer); summary (chat post title only) | [home], [summer], [blog] |
| A3 | Design as code | No / Not found | Graphical editor; the agent writes "programs" on cloud computers for analysis, but no design-as-code language found | inference from [byos] and [port] | [byos] |
| A4 | Imports existing design | Yes | Altium, OrCAD/Allegro, KiCad, PADS/Xpedition, CADSTAR, Eagle, Fusion, EasyEDA, DipTrace (XML), SOLIDWORKS PCB, Proteus (SDF + Specctra), IPC-2581 rev B/C, IDF 2.0/3.0 board outlines; Eagle .sch editable since Q1 2026; PADS ASCII footprints. Blog shows a 12-layer, 858-part Altium import and a 6-layer, 459-part Allegro import. Whether layout imports for every format is not stated per format; earlier teardown found a docs FAQ saying layout/Gerber import unsupported (now contradicted). A post read 2026-11-14 says project import "is available to all users" from Altium, KiCad, EAGLE, EasyEDA, PADS, OrCAD, CADSTAR, DipTrace, Proteus, Fusion, EDIF, ODB++ and IPC-2581, and that imports carry over the PCB layout (Oct 2026) | read | [port], [apr], [imp], https://flux.ai/p/blog/ai-assistance-inside-every-ecad-tools |
| A5 | Requirement kept as its own artifact | Partial | Project plan from the Brainstorm step; "Interactive Pages in Flux Project Files" (2026-10-20, title only). No traceable requirement-to-design link found | read (plan); summary (pages) | [home], [blog] |
| A6 | Clarifying questions / refusal | Partial | "Flux now asks clarifying questions before jumping into action" (Aug 2026). No refusal of out-of-scope requests found; it admits "Do we always succeed? No." | read | [summer], [work] |

### B. Schematic
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Schematic from intent | Yes | Agent "turns the plan into a schematic"; places parts and wires; works iteratively "until the design passes its checks" | read | [home], [feb] |
| B2 | AI edits inside an existing schematic | Yes | Agent edits imported Altium/Cadence designs; Markup mode: circle something and ask (2026-11-06) | read ([imp]); summary (markup title) | [imp], [blog] |
| B3 | Part selection with reasons | Partial | Agent "reads the datasheet of every part and checks the design against its pinouts, ratings, and limits"; AI search for in-stock parts by requirement. No per-part stated reason or datasheet page citation found | read | [work], [spring] |
| B4 | Reusable modules / reference designs | Yes | Forkable reference designs, MCU platforms, manufacturer rule templates; team templates (Mar 2026); team "Knowledge" rules applied by trigger (Oct 2026) | read | [spring], [know] |
| B5 | ERC (voltage-aware?) | Yes (voltage-aware not found) | Agent runs ERC and DRC continuously; new ERCs added Feb 2026 (floating pins named). No voltage-domain ERC documented; datasheet "ratings" check is a vendor claim with no method | read | [feb], [spring], [work] |
| B6 | Hierarchy / multi-sheet | Not found | Feb 2026 "What's next" lists "tools for organizing complex projects" | read (roadmap only) | [feb] |
| B7 | Library; symbols/footprints from datasheets | Partial | Shared community library with LCSC/distributor part pages; parametric symbols/footprints; size not stated on current pages (older vision doc says 750K parts, unverified) | read (parametric, Apr 2026); not found (size) | [apr], [supply] |

### C. Simulation and analysis
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Yes | Built-in ngspice: operating point, AC sweep, transient, waveforms and plots; runs on imported Altium/Cadence designs, with networks modelled from ideal sources, R and C. The earlier "beta" label was not found on the 2026-11 pages | read | [mc], [imp] |
| C2 | Tolerance / Monte Carlo / worst-case | Partial | Not built in: the Nov 2026 post runs Monte Carlo (1,000 trials) and 8-corner worst case in LTspice installed on a Flux cloud Windows computer via bring-your-own-software; Flux's own simulator "compares explicit component-value cases" | read | [mc], [byos] |
| C3 | Formal proof / exhaustive verification | Not found | No proof or exhaustive check on any page read | not found ([review], [eval], [work]) | — |
| C4 | Signal integrity | Yes | Cloud full-wave EM on routed copper and stackup: S-parameters (S11/S21/SDD11/SDD21), Zdiff, TDR, crosstalk, eye diagrams up to 20 Gbps, near fields. Solver not named; no accuracy figure; no beta label | read | [em], [si] |
| C5 | Power integrity / IR drop | Yes (claimed) | PDN impedance vs frequency with vendor capacitor models (ESR/ESL), IR drop, plane resonance, load-step droop. Engine not named | read (vendor claim) | [review], blog "Decoupling capacitor selection with PDN simulation" (2026-10-30, title only) |
| C6 | Thermal | Partial (claimed) | "Estimates board temperatures from the operating conditions"; enclosure airflow and temperature. No solver, method or accuracy named | read (vendor claim) | [review] |
| C7 | EMC / EMI | Partial | Layout review of return paths, switching loops, crosstalk, connector placement; EM fields near a net. No radiated-emission prediction found | read | [review], [em] |
| C8 | Creepage/clearance from voltage | Partial | User supplies standard (IEC 62368-1 worked example), voltage, pollution degree and distances; Flux sets them as Keep Out rules and re-runs DRC. Distances are not derived automatically; creepage path is measured by the engineer | read | [creep] |

### D. PCB layout
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Partial | Agent "places components, routes connections, and verifies results at the same time" (Feb 2026); homepage: "lays out components". But the routing docs say "a routing request stays routing only unless you ask for placement work", and the positioning docs show only named-part placement. Whole-board auto-placement is not documented | read | [feb], [home], [routedoc], [posdoc] |
| D2 | Automatic routing | Yes | "Route this board" or named nets; keeps existing copper on request; asks approval before changing copper, rules or part positions; DRC + airwire check at the end. No completion rate, time or layer limit published for routing (earlier teardown: "10-15 minutes or even several hours") | read | [route], [routedoc] |
| D3 | Constraint management | Partial | Layout Rules panel (Q1 2026); object-specific rules created by moves; knowledge rules; post titled "DDR Routing Without a Constraint Manager" (2026-10-30) — rules through chat, not a constraint manager | read | [apr], [posdoc], [know] |
| D4 | Stackup / controlled impedance | Yes | Stackup editor; impedance-derived width/spacing rules (earlier teardown, checked); post-route EM verification now possible via [si] | read | [routedoc], [si] |
| D5 | DRC | Yes | Continuous DRC; Gerber check runs DRC on the exported board; categories per earlier teardown (width, clearance, courtyard, drill/annular ring, mask, silk) | read | [feb], [gerber] |
| D6 | 3D view and MCAD exchange | Yes | STEP export; live collaborative 3D/MCAD in Flux (2026-10-21); edit imported STEP; OpenUSD export (2026-10-27); IDF import; enclosure design | read ([port]); summary (titles) | [port], [blog] |
| D7 | Length tuning / differential pairs | Yes | USB, Ethernet, LVDS, MIPI, PCIe pairs with impedance, layer, skew; length matching to a target within a user tolerance (0.1 mm example); BGA/QFN fanout | read | [route] |
| D8 | HDI / flex / rigid-flex | Not found | — | not found ([port], [routedoc]) | — |

### E. Firmware
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Yes (drivers/tests) | Writes pin map, drivers and the hardware interface from the schematic; writes host unit tests (Unity; CMock, CppUTest, GoogleTest named). Complete application firmware not shown | read | [fw] |
| E2 | Pin-mux / peripheral config | Partial | Pin map built from MCU, sensor, bus and strapping pins in the schematic; no pin-mux tool described | read | [fw] |
| E3 | Compiles / tests before showing | Yes | Compiles for STM32, nRF, ESP32-class, RP2040, RISC-V, AVR and other ARM (GCC); reports flash/RAM; runs host unit tests on a "project computer"; CI on firmware repo changes | read | [fw] |
| E4 | Protocol stacks | Not found | Tests protocol logic (parsers, checksums, framing) in the user's code; no stack provided | read (absence on [fw]) | [fw] |

### F. Explanation, evidence, review
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains each choice | Partial | Conversational agent explains on request; no per-decision rationale artifact found | inference from chat-based workflow; not found on [work] | [work] |
| F2 | Confidence / evidence grading | No / Not found | Raise post: working to make the agent "clearer about when it is uncertain" — i.e. not shipped as of Feb 2026; nothing found since | read | [raise] |
| F3 | Automated design review | Yes | "Altium-level review": SI, PI, EMC, DFM, thermal, mechanical fit, in every plan; Gerber/BOM/P&P cross-check | read (vendor claim) | [review], [gerber] |
| F4 | Datasheet-grounded checks with cited pages | Partial | Reads every part's datasheet; no page citations found | read | [work] |
| F5 | Audit trail of AI actions | Partial | Change History lists previous versions and restores them; agent threads reviewable over MCP; no AI-action audit log documented | read ([vc] via search snippet; [mcp]) | [vc], [mcp] |

### G. Iteration and collaboration
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Yes | Steering mid-build; side threads, parallel agents, agents in other projects (2026-10-21); slash commands (2026-10-23) | read ([summer]); summary (titles) | [summer], [blog] |
| G2 | Version history / diff / branch / restore | Partial | Change History with restore; forking and cloning; no branch diff found | summary (docs search snippet) | [vc] |
| G3 | Comments / review / roles | Yes | Real-time browser collaboration, comments page in docs, project-level permissions, SSO, hidden workspaces (Enterprise) | read ([sec], [price]); summary (comments) | [sec], [price] |

### H. Supply chain and manufacturing
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | BOM export; MPN/manufacturer/part type added automatically (Q1 2026) | read | [port], [apr] |
| H2 | Live price and stock | Yes | Arrow, Mouser, DigiKey, LCSC, Verical, TME stock in the inspector; price and availability in part search; agent can call distributor APIs with the user's keys (2026-10-21) | read ([supply], [spring]); summary (keys post title) | [supply], [spring] |
| H3 | Alternates / substitution | Partial | AI replacement suggestions using project context and package/spec similarity; "Fix your BOM in hours" (Nov 2026). Checking method not described; no re-simulation of the substitute documented | read | [supply], [spring] |
| H4 | Fab outputs | Yes | Gerber, drill, BOM, pick-and-place, netlists (EDIF, D-356); IPC-2581C, ODB++ and STEP per docs search; fabrication drawing generated from the design (2026-11-04) | read ([port]); summary (IPC/ODB++ via search snippet of the same docs) | [port], [blog] |
| H5 | DFM / DFA | Partial | Agent checks against each fabricator's rules while it works; Gerber check (copper gaps, silkscreen, outline) with user-supplied fab rules; no built-in fab profiles in the Gerber post | read | [fab], [gerber] |
| H6 | Order from a fab inside the tool | Yes (claimed) | Agent gets quotes for PCB, assembly, 3D printing, CNC, sheet metal, moulding, harnesses and "places the order when you confirm"; fabs not named on that page; homepage shows seven manufacturer logos | read | [fab], [home] |

### I. Platform and business
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Browser | Browser app; cloud agent; mobile dictation | read | [home] |
| I2 | API / CLI / headless | Partial | Public MCP server (Aug 2026; extended Oct 2026) for Claude Code, Cursor, Codex, ChatGPT etc.: read projects, components, nets, BOM, layout; hand jobs to the Flux agent. No REST API or CLI documented | read | [summer], [mcp] |
| I3 | On-prem / certifications | Partial | Cloud only; "SOC 2-aligned cloud infrastructure" (not a SOC 2 report); encryption at rest/in transit; no training on customer data; SSO. A pricing tracker says Enterprise dropped "SOC2" from its feature list on 2026-11-01. No ITAR/FedRAMP found | read ([home], [sec]); summary (tracker) | [sec], https://pricingsaas.com/companies/flux/diffs/2026W45 |
| I4 | Pricing | Partial | Official page shows plans Explore, Build, Pro, Teams (per editor), Enterprise, with dollar fields blank when read; 7-day trial; private projects, export and AI need a paid plan; ACUs metered in Agent mode. Tracker (captured 2026-11-09): Build USD 80/mo, Pro USD 200/mo, extra ACU USD 2; Explore (USD 50, 40 ACUs) removed 2026-11-01; Build 200 ACUs and Pro 800 ACUs since 2026-10-18; Teams flat USD 500/mo for 5 seats from 2026-10-26. Flux says cost per 1,000 design changes fell from about USD 1,100 (late Aug) to about USD 330 (late Oct) | read ([price], [cost]); summary (tracker numbers) | [price], [cost], pricingsaas tracker |
| I5 | Sold to | — | Individuals, startups, teams, enterprise (SLA 2 h response, named account manager) | read | [price] |
| I6 | Company facts | — | USD 37M raised Feb 2026, led by 8VC (with Bain Capital Ventures, Liquid 2, Outsiders Fund); 1,099,361 builders and 6,425,482 projects (Feb 2026); named customers Agri-iO, AIRcable, Tilt Tracker; headcount not stated | read | [raise], [home] |
| I7 | Interop KiCad/Altium/OrCAD | Partial | Imports all three (Altium/Cadence on Pro per a community FAQ snippet); exports manufacturing formats only; no native KiCad or Altium project export documented ("Export to Altium" is an open feature request) | read ([port]); summary (plan gating, feature request) | [port] |
| I8 | Open source | No | Proprietary SaaS | inference (no licence or repo found) | — |

### J. Domain coverage
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces (RS-485, 4–20 mA, 24 V) | Not found | No industrial rule library found; general agent could draw these | not found ([blog] titles, [review]) | — |
| J2 | Power electronics | Partial | Isolated power board creepage example; PDN; SPICE on power circuits | read | [creep], [work] |
| J3 | RF / high-speed | Yes | Diff pairs to PCIe, DDR routing post, EM/SI to 20 Gbps eye, RF feeds | read | [route], [si] |
| J4 | Safety / regulatory standards | Partial | IEC 62368-1 creepage worked example; "prepares a safety analysis for the test lab" (claim) | read | [creep] |
| J5 | Stated limits | Partial | "Professional multi-layer PCBs up to eight layers" (yet 12-layer Altium import is shown in [imp]); 20 Gbps eye-diagram ceiling; no part-count or board-size limit found | read | [port], [si], [imp] |

## What changed since the 2026-10-21 teardown
- **Simulation went far past ngspice.** Cloud full-wave EM with S-parameters, TDR, crosstalk and eye diagrams (Oct 2026), PDN impedance and IR drop, thermal estimates. The teardown's "no post-route impedance, SI, PI or thermal analysis" is now wrong as a feature statement (still true that no solver, method or accuracy is published).
- **Agentic routing in chat** with diff pairs, length matching to a tolerance and BGA fanout (2026-10-28). Placement of the whole board is still not documented.
- **Firmware** is compiled and unit-tested on a cloud project computer for STM32, nRF, ESP32, RP2040, RISC-V and AVR (Nov 2026). The market page's "pin maps only" is out of date.
- **API question answered:** a public MCP server exists (Aug 2026, expanded Oct 2026). The teardown's "no public API, CLI or headless path" is now wrong for MCP; still no REST API or CLI found.
- **Bring-your-own-software cloud computers** (Nov 2026): Altium, SOLIDWORKS, Ansys, HyperWorks, OpenFOAM, LTspice can run next to the design.
- **Fab quoting and ordering** through the agent (Oct 2026); fabrication drawing generated from the design (2026-11-04); Gerber check (Oct 2026).
- **Pricing moved three times** in four weeks (ACU allowances doubled 2026-10-18, Teams flat price 2026-10-26, Explore removed 2026-11-01; tracker data). Flux claims about 70% lower cost per design change since August.
- **Exports:** IPC-2581C and ODB++ now appear in Flux's own docs per search snippet (teardown had them as summary). KiCad export still not documented.
- **Imports:** IPC-2581 B/C and IDF board import, so layout import is no longer unconfirmed.
- Scope widened to whole devices: enclosure, sheet-metal checks with OSH Cut, CNC/G-code, harness quoting, product videos.

## What the owner's market page gets wrong about this product
| Row | Page implies | Evidence (2026-11-13) |
|---|---|---|
| SPICE simulation | Flux: no / roadmap; "Only you" | Built-in ngspice (OP, AC, transient), runs even on imported Altium/Cadence boards [imp]. Not unique to Circuit OS |
| Complete firmware / protocol firmware | Flux: pin maps only | Drivers, pin map and unit tests, compiled with GCC for six MCU families [fw]. Still not a full protocol stack. Partial, not No |
| Physics layout validation | Only you / Flux none | Flux sells EM/SI, PDN, thermal review in every plan [review]. Circuit OS has none at layout level (physics report). The page is wrong in Flux's favour and in Circuit OS's disfavour |
| PCB auto-layout layers | 2-4 layer | Up to 8 layers in the editor; 12-layer import shown |
| Confidence scores | Only you | Flux has none (correct), but say "not found" rather than "No" |
| Consequential explanation | Only you | Flux has no per-decision rationale artifact found; its chat explains on request. The claim holds as "not found", not as proven absence |
| Gerber + fab export, DFM report | — | Flux: Gerber, drill, P&P, IPC-2581C, ODB++, fab drawing, Gerber check, ordering by agent |
| BOM with live pricing | — | Flux: six distributors live (Arrow, Mouser, DigiKey, LCSC, Verical, TME) vs Circuit OS: Mouser only, optional |
| Version history | — | Flux: change history with restore, fork/clone. Circuit OS: patch audit trail, no restore (physics report) |
| Audit trail | Only you | Partial at Flux (change history, MCP thread review). Circuit OS's requirement-level patch citations are more specific, but "only you" overstates |
| Safety-certification flagging | Only you | Flux sets user-supplied IEC 62368-1 distances as rules and prepares a "safety analysis" (claim). Circuit OS has no creepage check yet (F-0004 in the competitors README) |
| Industrial RS-485/4–20 mA rules | Only you | Not found at Flux — the page's claim survives for RS-485 (Circuit OS has an RS-485 rule); 4–20 mA is roadmap at Circuit OS, so "only you" is wrong there too |

## Where it is ahead of Circuit OS / where Circuit OS is ahead
Circuit OS side cites `MENTAL_MODEL.md` (dated 2026-08-22, partly stale), `.claude/CLAUDE.md` and the physics report's checked table ("What Circuit OS actually has today").

Flux ahead:
- Breadth: any circuit, any part, up to 8-layer boards with diff pairs and length matching; Circuit OS is a closed catalogue of blocks and an experimental 2-layer, ≤ 40-part board behind a flag (physics report; `MENTAL_MODEL.md` §4 Tier 2).
- Layout physics: EM/SI, PDN, thermal (vendor claims). Circuit OS has none at layout level (physics report table).
- Manufacturing: Gerber, ODB++, IPC-2581, fab ordering. Circuit OS: none (physics report; `MENTAL_MODEL.md` Tier 3).
- Supply chain: six live distributors vs Mouser optional (`.claude/CLAUDE.md`).
- Collaboration, version restore, MCP integration, imports from every major ECAD tool.
- Scale: about 1.1 M builders, USD 37M raised.

Circuit OS ahead:
- The LLM never writes the circuit; it writes a requirement JSON that deterministic generators realise, and out-of-catalogue requests are refused (`MENTAL_MODEL.md` §3; `.claude/rules/code-style.md`). Flux's agent edits the design directly and checks itself.
- Proofs: z3 proofs of currents/dissipation over tolerance boxes, per-claim rungs (physics report table). Flux has no proof or tolerance analysis built in (Monte Carlo only by running LTspice on a cloud computer).
- Firmware shown only once it compiles under PlatformIO, generated from templates and pinned by the wiring (`.claude/CLAUDE.md`, Stage 5). Flux also compiles now; parity on "compiles", Circuit OS ahead on determinism, behind on MCU breadth.
- Consequential, per-decision explanation and graded claims; Flux has no confidence grading (it says it is working toward "clearer about when it is uncertain").
- Industrial rules: RS-485 bias/termination rule exists; Flux has no industrial rule library found.
- HTTP API (`.claude/CLAUDE.md` routes) vs MCP only.

## Not verified
- Dollar prices: Flux's pricing page rendered blank price fields; the USD 80/200/500 figures are from a third-party tracker that itself conflicts (Build USD 80 vs USD 100).
- Whether the agent can place a whole board unprompted (Feb 2026 post says it "places components"; docs say routing-only unless asked; no whole-board placement example).
- The EM, PDN and thermal solvers' identity, accuracy and limits; whether they are beta.
- IPC-2581C/ODB++ export (search snippet of Flux docs; the page fetched listed only Gerber, drill, BOM, P&P, netlists).
- Library size; SOC 2 status (the tracker says Enterprise dropped "SOC2" from its listed features); which fabs take orders.
- Comments and fork/clone docs pages were not opened.
- Hierarchical/multi-sheet schematics.
