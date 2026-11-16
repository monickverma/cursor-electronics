# Group D — hardware as code, automated review / verification, firmware from hardware, general LLM assistants

Read 2026-11-13 and 2026-11-14. Researcher D. Schema, labels and format from the shared brief.

## Files written (full A–J tables)

| Product | File | Why full |
|---|---|---|
| JITX | `jitx.md` | Design as code with routing, SI and an HFSS loop; earlier teardown re-verified |
| atopile | `atopile.md` | Open design as code with a set-based constraint solver, the closest analogue to tolerance-box checking |
| tscircuit | `tscircuit.md` | Open TSX circuits with autorouter, SPICE elements and in-tool JLCPCB ordering |
| AllSpice (DRCY) | `allspice.md` | Leading datasheet-grounded AI review, with a published architecture paper |
| Cadstrom | `cadstrom.md` | Sells voltage, ratings and bus checks: the owner's "validation" rows |
| Traceformer (added) | `traceformer.md` | Self-serve "cite or abstain" datasheet review with published prices |
| Embedder (added) | `embedder.md` | Firmware from datasheets + schematic, built, flashed and tested on hardware |
| General LLM assistants | `general-llm-assistants.md` | The real substitute, with 2026 benchmark numbers |

Covered by other researchers, so not duplicated here: **Circuit Mind** (its AVE verification engine is in `circuit-mind.md`), **Diode Computers / Zener** (`diode-computers.md`), **ProtoFlow** (`protoflow.md`), **Siemens Xpedition** (`siemens-xpedition-pads.md`; its Schematic Analysis has 150+ voltage-aware rules per the physics report).

## Short entries (found, not given a full file)

| Product | What it is | Guarantee type | Why short | Label | Source |
|---|---|---|---|---|---|
| SKiDL | Python package describing schematics in code; outputs KiCad (KICAD10) netlists, XML BOM, schematic/SVG; ERC for unconnected pins, drive conflicts, power errors; SPICE via InSpice (replaced PySpice in 2.1.0). v3.0.0, 2026-10-16, MIT. No AI features (a CLAUDE.md documents the API for agents) | Rule check (pin-type ERC) + user-run SPICE | Hobby/research library, no company, no AI product | read | [pypi.org/project/skidl](https://pypi.org/project/skidl/) |
| Wokwi | Browser and VS Code simulator for Arduino, ESP32, STM32, Pi Pico; virtual WiFi/MQTT, logic analyser, GDB; Wokwi CI with heap-leak monitoring; **experimental MCP server** (`wokwi-cli mcp`) so AI agents run simulations and tests. Pricing €0 Community, €5.6 Hobby, €8.1 Hobby+, €20/seat Pro (2,000 CI min). No built-in AI assistant found | Firmware simulation (behavioural, not electrical) | It runs firmware; it does not generate firmware or design. Relevant as a test bench an agent, or Circuit OS, could call | read | [docs.wokwi.com](https://docs.wokwi.com), [MCP](https://docs.wokwi.com/wokwi-ci/mcp-support), [pricing](https://wokwi.com/pricing) |
| Embedd | London; turns datasheets and reference manuals into structured component models; generates drivers, HALs, BSPs and devicetree configs (MISRA / IEC 61508 targets claimed in 2024); partnering with Microchip; ~$2.7M (€2.3M) pre-seed led by Seedcamp, reported 2026-08-24. Site now says "software, tests and simulations generated deterministically" | Deterministic generation from a chip model (vendor claim); compilation or test evidence not stated | Sold to semiconductor vendors, not board designers | read (site, 2024 article); summary (funding) | [embedd.it](https://embedd.it/), [eeNews 2024](https://www.eenewseurope.com/en/ai-platform-generates-driver-software-from-component-datasheets/), [funding](https://therecursive.com/embedd-raises-eur2-31m-to-build-software-infrastructure-for-physical-ai) |
| Odem | macOS (Apple Silicon) desktop IDE launched on Product Hunt in 2026: one agent picks parts, draws the schematic, routes in KiCad, models a 3D-printable enclosure, and **writes and builds firmware with unit tests**; ERC, DRC, fit checks; Gerber/BOM/STEP/STL; uses the user's ChatGPT account; free in beta; "dense boards may leave some nets" | Tool checks (ERC/DRC) + firmware build | Only a Product Hunt listing found, no site or docs. **Watch:** it is the only other product found claiming prompt → board + firmware that builds | summary (maker's PH post) | [Product Hunt](https://www.producthunt.com/posts/1263017) |
| kicad-happy | MIT agent skills (Claude Code, Codex, Gemini CLI) + pure-Python analysers for KiCad: SPICE testbenches (ngspice/LTspice/Xyce) checked against calculated values with Monte Carlo; 44 EMC rules; derating; regulator Vout from feedback dividers; I2C rise time; datasheet extraction with quality scores; fab release gate; GitHub Action. Corpus of 5,857 repos checks "stability, not correctness" | Deterministic analysers + simulation, run by an agent | Open project, not a company; folded into `general-llm-assistants.md`. **Closest open equivalent of Circuit OS's checking stack** | read | [README](https://cdn.jsdelivr.net/gh/aklofas/kicad-happy@main/README.md) |
| CADY (CADY Solutions, distributed by Altair) | Schematic inspection: NLP and computer vision read datasheets; traces nets and pins against them; flags missing pull-ups and voltage-range violations (case: 3.3 V on a 4.75–5.25 V part) | AI-extracted datasheet rules + net tracing | Distributed inside Altair's portfolio; not re-read in depth | summary | [altair.com/cady](https://altair.com/cady) |
| NextPCB Design Validator | Cloud AI schematic review (KiCad, Altium, Eagle exports): unconnected pins, power violations, parts vs voltage/current/temperature limits, BOM mismatches; plain-English report with suggested fixes. Free 12 tasks/mo, $9.90 (+50), $99.90 (+500); page dated May 2026 | AI opinion; datasheet use not stated | Fab-house lead magnet; thin documentation | read | [nextpcb.com](https://www.nextpcb.com/blog/nextpcb-ai-schematic-validator-intro) |
| Probe (E-Sharp AB) | Review system: structured design model, selective retrieval, "cite or abstain", visible coverage (covered / partial / blind). Author's example: 16 rule hits → 4 real defects | Rules as leads + cited AI | Known only from its CEO's article (2026-11-10) | read | [Electronic Design](https://www.electronicdesign.com/55417978) |

## Dropped

- **Cirkit Designer**: a hobby wiring and simulation tool with AI code generation. Summary only, and it fits the maker-tool group better.
- **LabWired MCP, esp32sim-mcp, embeddedci-mcp**: firmware-emulator MCP servers, unverified listings.
- **Embedist**: an AI firmware IDE seen only on comparison sites.
- **galvano.ai**: a side project in a SKiDL discussion.
- **Polymorphic Blocks (Berkeley) and Google pcbdl**: research hardware-description languages without products.
- **Siemens Fuse and Cadence agent claims**: covered by the incumbent files.

## Verification guarantees, side by side

| Product | What it checks | Kind of guarantee | Published error rate |
|---|---|---|---|
| AllSpice DRCY | Schematic vs datasheets, pin by pin; ratings; interfaces | LLM opinion, multi-run consensus, page-cited | None ("some findings will be wrong") |
| Traceformer | Datasheet / application-level issues | LLM opinion, cite-or-abstain | None |
| Cadstrom | Voltage domains, buses, polarity, ratings, pins | AI + "expert-system rules and simulation" (undocumented) | None |
| Circuit Mind AVE | Connections and buses vs pin tables and voltages | Agents over a "physics-based engine" | None |
| NextPCB Validator | Pins, power, part limits, BOM | AI opinion | None |
| JITX | User-written checks; SI constraints in the router; HFSS | Rule check + constraint satisfaction + full-wave simulation | n/a |
| atopile | Assertions over toleranced parameters | Symbolic set-based constraint solving over declared equations | n/a |
| tscircuit | Placement / DRC; user-written SPICE | Geometric rules + simulation | n/a |
| kicad-happy | Derating, EMC rules, SPICE vs calculation, Monte Carlo | Deterministic analysers + simulation | Stability corpus only |
| Embedder | Firmware | Build + flash + tests on real hardware (empirical) | n/a |
| **Circuit OS** | Graph rules, ngspice, properties over tolerance boxes, compile gate | **Proof (z3) + simulation + rules, a stated rung per claim, "not assessed" when unchecked** (`.claude/CLAUDE.md`, `.claude/rules/simulation.md` X8) | Checked against mathematics and ngspice; no bench yet (`MENTAL_MODEL.md` §5) |

No product in this group claims a proof. atopile is the only one whose check covers tolerance ranges by construction, and it covers only the equations a designer writes.

## What the owner's page and project docs get wrong (from this group)

- "Plain-English validation report: only you". **Wrong.** Cadstrom (Design Analysis Report with severities), DRCY (review comments citing datasheet pages), NextPCB (plain-English report with fixes) and Traceformer all produce one.
- "Voltage/current rule checks: only you". **Wrong.** Cadstrom, DRCY, CADY, NextPCB, JITX's built-in checks (older docs) and Siemens Schematic Analysis all do voltage or rating checks. What is unique is that Circuit OS *proves* them over tolerances.
- "Full firmware: only you". **Not unique.** Embedder writes firmware from datasheet + schematic and tests it on hardware; Odem claims firmware that builds with unit tests. Circuit OS's distinct claim is deterministic, template-derived firmware tied to the same IR as the circuit, shown only after it compiles.
- vision.md, "ChatGPT/Claude: no simulation, no files, no validation". **Out of date.** Agents with KiCad MCP servers, kicad-happy and Wokwi's MCP produce files and run ERC, DRC, ngspice and firmware simulation. They give no guarantee that the checks were run, and no proof.

## The facts from this group that most change the competitive picture

1. **Datasheet-grounded AI review is now a crowded, cheap category.** DRCY (paper March 2026, enterprise), Circuit Mind AVE (launched 2026-10-28 with $25M), Cadstrom ($6.8M seed), Traceformer ($20/month), NextPCB ($9.90/month), CADY and Probe all exist. Every one is an LLM opinion with citations, and none publishes precision or recall. "We check designs" is no longer a differentiator. "We prove, and say exactly what we did not check" still is.
2. **The benchmarks back Circuit OS's architecture with numbers.** Free-form board design: best 8.15% pass (HWE-Bench, 300 tasks). Schema plus deterministic verifier: 81.3% (PCBSchemaGen, 227 tasks). LLM-extracted facts with generated deterministic arithmetic: 97.5% (Qiao & Dick). LLM netlist edits degrade with sequence length (NetlistBench). Circuit OS can cite these directly.
3. **The substitute got tools.** Frontier agents plus KiCad MCP servers, design-as-code skills (atopile, tscircuit, JITX, Zener) and kicad-happy, an open stack with ngspice Monte Carlo, derating and EMC rules, reach most of Circuit OS's *activities* for free. They lack the structural guarantees: requirement first, refusal, every rule run, proof.
4. **Firmware is moving to hardware-in-the-loop.** Embedder builds, flashes and tests on real boards across 600+ claimed platforms, and Odem claims prompt to board to firmware that builds. Circuit OS's compile gate is a lower rung than Embedder's flash-and-test. Wokwi's MCP server is a cheap way to add a simulated run-time test rung.
5. **JITX now documents an agent workflow and a real autorouter.** Design-as-code tools are converging on "the agent writes code, a deterministic engine builds it", which is Circuit OS's thesis. JITX applies it to layout and SI. atopile adds set-based constraint checking. Neither derives behaviour from the netlist or proves it.

## What could not be verified

- Precision and recall for any AI review product. None is published. DRCY's paper has no evaluation section.
- The full checks table in DRCY's hood post (an image), and DRCY's DFM scope (two AllSpice pages disagree).
- The atopile enterprise page, sidebar-agent status, solver internals (third-party summary only) and fab output formats.
- JITX's Python-era built-in checks, SPICE runner, BOM and Altium export.
- tscircuit pricing and funding. Cadstrom's rules and simulation. Odem beyond its launch post. Embedder funding.
- The specific models in the HWE-Bench and NetlistBench results.
