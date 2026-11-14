# Circuit OS is alone on proof, consequential explanation and requirement-first patching; it is behind or absent on most of the rest

Competitor feature matrix, 2026-11-14. Merged from the 26 product files and four group files in
[`competitor-features/`](competitor-features/). No new web research was done for this file: every
competitor cell comes from a product file, and every Circuit OS cell from the code at `master`
(369d94e) in this worktree. Where two files disagree, both readings are given (section 7).

Evidence labels, as in the product files: **r** read on the vendor's own page, docs, repo or release
notes; **s** summary, from a third party or a search snippet; **i** inference from what was read;
**n** looked for and not found. "not covered" means the product file has no row for that feature.
For Circuit OS, **r** means read in the code.

---

## 1. The answer in one page

### What the market has

The market already has nearly everything a hardware engineer asks of a tool, sold by somebody:

- **Prompt to schematic** (Flux, CELUS, Diode, ProtoFlow, Trace, SnapMagic, the general LLMs).
- **SPICE** in at least eight products (Flux, Altium, KiCad, ProtoFlow, EasyEDA, Fusion, tscircuit, OrCAD PSpice).
- **Compiled firmware** (Embedder, and Flux since November 2026).
- **Layout physics** in the incumbents (Siemens HyperLynx, Cadence Sigrity) and now claimed by Flux.
- **AI routing** (Quilter, DeepPCB, Flux, Altium Situs, and Freerouting under everyone).
- **Datasheet-grounded AI review** (AllSpice DRCY, Cadstrom, Traceformer, Circuit Mind AVE, NextPCB).
- **A fab order at the end** (Flux, Trace, EasyEDA, tscircuit, Diode).

Three things were found nowhere else:

- a formal proof of a design property;
- an explanation stated as consequences ("if you change R3, this breaks");
- a stored requirement that every edit must cite in the user's own words.

### Where Circuit OS stands

| Standing | Rows |
|---|---|
| **Alone** (only one other file has even a Partial, and that is a different thing) | C3 formal proof of circuit behaviour (atopile proves its declared equations are consistent, not behaviour; see 4.2) |
| **Alone in the strong form** (others have a weaker version) | F1 explanation stated as checked consequences (general LLMs explain on request, unchecked; reviewers explain findings, not choices); A5 + A6 + G1 requirement-first, refuse-not-negotiate, operations citing the user's words (CELUS Intent Document nearest); F2 per-claim evidence grades with "not assessed"; H3 substitutes re-proved (CELUS and SnapMagic suggest substitutes without saying how they are checked); J1 RS-485 bias and termination rules |
| **At parity** | A1, A2, B3, B5, C1, C2, E1, E2, E3, F3, H1, I2, J5 |
| **Behind** | B1, B2, B4, B7, D1, D2, D3, D5, D6, E4, F4, F5, G2, H2, I7 |
| **Absent** | A3, A4, B6, C4, C5, C6, C7, C8, D4, D7, D8, G3, H5, H6, I4 (no paying user), J2, J3, J4. H4 Gerber is on a branch, not released |

### The five facts that most change the picture

1. **Flux closed most of the gap the owner's page said it had.** It now has built-in ngspice. Since
   November 2026 it compiles firmware (STM32, nRF, ESP32-class, RP2040, RISC-V, AVR) and runs unit tests. It claims cloud EM/SI,
   PDN and thermal analysis, offers agentic routing, and takes fab orders
   ([flux.md](competitor-features/flux.md)).
2. **SPICE, compiled firmware, requirement artifacts and voltage-aware checks no longer set anyone
   apart.** Each one has at least two other vendors (matrix rows C1, E3, A5, B5).
3. **Datasheet-grounded AI review is crowded and cheap.** DRCY, Cadstrom, Traceformer ($20/month),
   Circuit Mind AVE, NextPCB Design Validator ($9.90) and others all sell it. None of them publishes
   precision or recall.
4. **A general LLM plus open tools is now the substitute.** The tools are KiCad MCP servers,
   kicad-happy, Freerouting MCP, the EasyEDA agent skill and Wokwi MCP. The published numbers still
   favour a schema plus a deterministic verifier:
   - 8.15% best pass on HWE-Bench;
   - 81.3% for PCBSchemaGen;
   - 97.5% for Qiao & Dick;
   - NetlistBench: accuracy falls as edit sequences lengthen;
   - long-horizon analog benchmark: 8–78%.

   That second point is Circuit OS's design
   ([general-llm-assistants.md](competitor-features/general-llm-assistants.md)).
5. **Everything ends in a fab order at consumer prices:**
   - ProtoFlow $0–19.99/month;
   - Trace $29.99;
   - Traceformer $20;
   - Flux Build about $80 (tracker);
   - EasyEDA free.

   The owner's market page is wrong on 10 of its 13 "Only you" cells (section 5).

### How far to trust it

- Most cells are **r**: read on the vendor's own pages between 2026-11-12 and 2026-11-14.
- **Cadence** rests mostly on second-hand reading: cadence.com returned 403, and only 4 of its 60
  rows were read first-hand. **Autodesk Fusion** rests wholly on second-hand reading: every Autodesk
  page returned 403.
- **SnapMagic** is thin on purpose: its AI is waitlist-only (announced, not shipped).
- **Trace and ProtoFlow** rest on vendor claims only.
- **Every benchmark here is run by its own vendor or author.** No product's accuracy has been
  checked independently.
- A "No" or "Not found" means the feature was looked for on public pages. It does not mean it does
  not exist behind a login.

---

## 2. The product map

26 products have their own file. Prices are as read on 2026-11-13/14 unless marked.

### Design from intent

| Product | What it is | Input | Output | Price | Stage / funding | File |
|---|---|---|---|---|---|---|
| Flux | Browser ECAD with an AI agent | Prompt, chat, imports | Schematic, layout, firmware, fab order | Plans shown without figures; tracker Build $80/mo, Pro $200/mo (s) | $37M (Feb 2026, 8VC); 1,099,361 builders claimed | [flux.md](competitor-features/flux.md) |
| CELUS | AI design assistant from requirements | Requirements, guided questions, sketches | Intent Document, block diagram, schematic, BOM, export to ECAD | No price page; AI Credits sold in-app, amounts not stated | Founded 2018, Munich; EUR 25M Series A 2022 (s, earlier teardown) | [celus.md](competitor-features/celus.md) |
| Circuit Mind | ACE design engine + AVE review | Block diagram + requirements | Schematic, BOM; AVE review of exported schematics | No price page | $25M announced 2026-10-28; $33.4M total | [circuit-mind.md](competitor-features/circuit-mind.md) |
| Diode | Design-as-code (Zener) plus a service | Description, block diagram, KiCad project | KiCad project, fab | Per-order quote; enterprise from $10,000 per design | a16z Series A, $11.4M reported (2025) | [diode-computers.md](competitor-features/diode-computers.md) |
| SnapMagic | Parts library (SnapEDA) + AI copilot | Prompt | Parts, symbols, footprints; schematic claimed | Not found | AI waitlist-only; "over 1 million engineers" | [snapmagic.md](competitor-features/snapmagic.md) |
| ProtoFlow | Desktop AI schematic + PCB tool | Prompt | Schematic, PCB, SPICE | $0 / $19.99 / $39.99 / $199.99 per month | "20k+ engineers"; funding not found | [protoflow.md](competitor-features/protoflow.md) |
| Trace | Desktop AI schematic + layout | Prompt | Multi-sheet schematic, layout, fab | Pro $29.99/mo, Ultra $169.99/mo | Founders Inc; "4,000+ engineers" | [trace.md](competitor-features/trace.md) |

### AI layout

| Product | What it is | Input | Output | Price | Stage / funding | File |
|---|---|---|---|---|---|---|
| Quilter | Physics-aware AI placement and routing service | Finished schematic + board outline | Routed board in native ECAD format | Per project by unrouted pins; no figures | $25M Series B (2025-10), about $40M total | [quilter.md](competitor-features/quilter.md) |
| DeepPCB | RL router (InstaDeep) | Board file | Routed board | $30 per hour; $280 for 10 h; $800 for 30 h | InstaDeep, owned by BioNTech | [deeppcb.md](competitor-features/deeppcb.md) |
| Freerouting | Open-source autorouter | DSN | SES | Free | v2.5.0 (2026-10-05), REST + MCP; one maintainer about 4 h/week | [freerouting.md](competitor-features/freerouting.md) |

### Incumbent suites

| Product | What it is | Input | Output | Price | Stage / funding | File |
|---|---|---|---|---|---|---|
| Altium | Altium Designer + Altium 365 | Manual design, requirements portal | Everything to fab | Develop: extra authors $995/yr; base about $1,990/yr (s) | Owned by Renesas | [altium.md](competitor-features/altium.md) |
| KiCad | Open-source ECAD | Manual | Everything to fab | Free (GPL) | 10.0.8 (2026-10-30); donor-funded | [kicad.md](competitor-features/kicad.md) |
| Autodesk Fusion Electronics | ECAD inside Fusion | Manual | Board + MCAD | $680/yr (s) | Autodesk; EAGLE ended 2026-06-07 | [autodesk-fusion-electronics.md](competitor-features/autodesk-fusion-electronics.md) |
| EasyEDA Pro | Browser/desktop ECAD tied to JLCPCB | Manual; agent skill | Everything to fab, JLC order | Free; premium $19.9/mo | 7.37M registered users (June 2026) | [easyeda-pro.md](competitor-features/easyeda-pro.md) |
| OrCAD X | Cadence's mid-range ECAD | Manual; Xplore component AI | Everything to fab | Standard about $1,280/yr (s) | Cadence (public); Xplore 2026-11-09 | [orcad-x.md](competitor-features/orcad-x.md) |
| Cadence Allegro X AI / AuraStack | High-end PCB with AI placement and routing | Placed schematic + stackup + constraints | Board | OrCAD X Standard $1,392–8,260 (s) | Cadence (public); mostly second-hand reading | [cadence-allegro-orcad-x.md](competitor-features/cadence-allegro-orcad-x.md) |
| Siemens Xpedition / PADS | High-end suite with HyperLynx, Valor | Manual; requirements in capture | Everything to fab, analysis | No prices found | Siemens AG | [siemens-xpedition-pads.md](competitor-features/siemens-xpedition-pads.md) |
| Zuken CR-8000 | High-end suite with AI-PR router | Manual | Board | AIPR add-on from $64K/yr (2023) | Zuken (public); Valeo AI work | [zuken-cr-8000.md](competitor-features/zuken-cr-8000.md) |

### Design as code

| Product | What it is | Input | Output | Price | Stage / funding | File |
|---|---|---|---|---|---|---|
| JITX | Python design-as-code | Code; external agent with skills | Schematic, board | Free for CERN-OHL-P designs; enterprise unpriced | $12M Series A (Sequoia, 2022) | [jitx.md](competitor-features/jitx.md) |
| atopile | `.ato` language + VS Code agent | Code, prompt via agent | KiCad board | Free (MIT); enterprise unpriced | YC W24 | [atopile.md](competitor-features/atopile.md) |
| tscircuit | TypeScript/React circuits | Code, external agent | Schematic, board, fab | Free; support unpriced | Funding not found | [tscircuit.md](competitor-features/tscircuit.md) |

Diode (above) is also design as code (Zener).

### Review and verification

| Product | What it is | Input | Output | Price | Stage / funding | File |
|---|---|---|---|---|---|---|
| AllSpice (DRCY) | Hardware Git + AI design review | Native ECAD files | Review findings, history | Enterprise only, no figures | $15M Series A (2025) | [allspice.md](competitor-features/allspice.md) |
| Cadstrom | AI schematic validation | ECAD files + datasheets | Report | Free to start; no figures | $6.8M seed (2024) | [cadstrom.md](competitor-features/cadstrom.md) |
| Traceformer | Datasheet-grounded schematic review | KiCad/Altium export | Report with cited pages | $0 / $20 / $50 per seat per month | Funding not found | [traceformer.md](competitor-features/traceformer.md) |

Circuit Mind AVE (above) also belongs here.

### Firmware

| Product | What it is | Input | Output | Price | Stage / funding | File |
|---|---|---|---|---|---|---|
| Embedder | Firmware agent in VS Code with hardware-in-the-loop tests | Prompt + datasheets | Compiled, flashed, tested firmware | Free (non-commercial); Startup and Enterprise custom | YC S25, 6 people | [embedder.md](competitor-features/embedder.md) |

### General LLM assistants

| Product | What it is | Input | Output | Price | Stage / funding | File |
|---|---|---|---|---|---|---|
| General LLMs + tools | Frontier chat/agent models driving KiCad, Freerouting, Wokwi through MCP and skills | Prompt | Whatever the tools produce | Model subscription; tools free | n/a | [general-llm-assistants.md](competitor-features/general-llm-assistants.md) |

### Also found (short entries in the group files, no own file)

These are mentioned in [`_group-a.md`](competitor-features/_group-a.md) to
[`_group-d.md`](competitor-features/_group-d.md), mostly from summaries.

| Entry | What the files say |
|---|---|
| siliXon (UK) | Claims prompt to schematic, layout, BOM and Gerbers; $1.5M seed; no working website found. Summary |
| Cherry Blossom, PCBEditor, Skimatly | Browser prompt-to-schematic tools (two also to PCB), beta or about $20/month; known only from ProtoFlow's comparison page. Summary |
| Proteus 9.x with ProPilot | VSM simulates firmware against the schematic; bring-your-own model. Summary only |
| Huaqiu KiCad Copilot | Recognises RS-485 buses. Summary |
| DipTrace 5.3 | Incumbent, no AI |
| LibrePCB 2.x | Incumbent, no AI |
| SKiDL 3.0.0 | Python netlists (2026-10-16) |
| Wokwi | Firmware simulation with MCP; €0–20 |
| Embedd | Firmware/BSP from datasheets; $2.7M |
| Odem | Prompt to board plus firmware that builds. Product Hunt only |
| kicad-happy | Open-source agent skills for KiCad |
| CADY (CADY Solutions, sold through Altair) | Reads datasheets; flags missing pull-ups and voltage-range violations. Summary |
| NextPCB Design Validator | AI review; $9.90/month |
| Probe (E-Sharp AB) | Review with "cite or abstain" and visible coverage; known from its CEO's article, 2026-11-10 |
| PCBWorld-Bench (LG AI) | Benchmark, 679 boards |
| GPT-6 "Astra" demo | Routed via Freerouting |
| EasyEDA agent skill | Lets an LLM drive EasyEDA |
| Upverter Modular | Dropped |
| Tomachie | Mentioned only |

**Count:** 26 products with their own file. The "also found" list has 21 names; four of them are a
benchmark, a demo, a skill and a dropped product, not competitors.

---

## 3. The matrix

Each cell gives the verdict, a few words from the product file, and the evidence label. Notes are
cut short; the product file has the full sentence and its source. The Circuit OS column comes from
the code.

Ten products have their own column:

- Flux, CELUS, Circuit Mind and Diode (design from intent);
- Quilter (AI layout);
- Altium, KiCad and Siemens (incumbents);
- JITX (design as code);
- AllSpice (review).

The last column lists every other product file whose verdict on that row is Yes or Partial, with
names only.

### A. Input and intent

| Row | Circuit OS | [Flux](competitor-features/flux.md) | [CELUS](competitor-features/celus.md) | [Circuit Mind](competitor-features/circuit-mind.md) | [Diode](competitor-features/diode-computers.md) | [Quilter](competitor-features/quilter.md) | [Altium](competitor-features/altium.md) | [KiCad](competitor-features/kicad.md) | [Siemens](competitor-features/siemens-xpedition-pads.md) | [JITX](competitor-features/jitx.md) | [AllSpice](competitor-features/allspice.md) | Other products |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A1** Natural-language prompt to design | Yes: IntentProducer, tool_use writes IntentIR only (r) | Yes: Agent mode completes design work from prompts; "Brainstorm"... (r) | Yes: Design Assistant takes "requirements, sketches, or vague... (r) | Not found: ACE starts "from a simple block diagram" and engineering... (r) | Yes: Self-serve input: "A description, block diagram or KiCad... (r) | No: Input is a completed schematic plus a board file with one... (r) | No (for designs) / Partial (for requirements): No prompt-to-schematic or prompt-to-board. The Requirements... (r) | No (core) / Partial (third party): Nothing in core or in the 10.0 release notes. Community MCP... (r/s) | Partial: Not a prompt: the CELUS-powered front end starts from... (r) | Partial: No built-in prompt box. An external agent with the JITX... (r) | No: Review and collaboration platform; DRCY Chat answers... (r/i) | Yes: Embedder, General LLMs, ProtoFlow, SnapMagic, Trace; Partial: atopile, OrCAD X, tscircuit |
| **A2** Structured form / spec input | Yes: form producer, 0 model calls (r) | Partial: Free "Chat" mode to "ask, plan, and spec your device"... (r/s) | Yes: Guided questions on interfaces, power budget, cost... (r) | Yes: Block diagram + requirements; customer AML, preferred... (r) | Partial: Block diagram input; testbenches encode requirements such... (r) | Partial: Setup flow (four pages since 2026-03-26) where the user... (r) | Yes: Requirements Portal: structured requirements with ID... (r) | No: — (n) | Yes: Requirements tabs in Xpedition design capture (reorganised... (r/s) | Yes: Requirements, constraints, stackups and rules are expressed... (r) | Partial: Teams load their own review checklists and an optional... (r) | Yes: atopile, Cadence Allegro, Zuken; Partial: DeepPCB, Embedder, Freerouting, General LLMs, ProtoFlow, Trace, Traceformer, tscircuit |
| **A3** Design as code | No: by design, JSON IR not code (r) | No / Not found: Graphical editor; the agent writes "programs" on cloud... (i) | No / Not found: Block-diagram canvas and CUBO library; no language (n) | Not found: — (n) | Yes: Zener (Starlark), open source (MIT); modules, interfaces... (r) | Not found: No language or scripting page in the 74-page docs index (n) | No: Scripting exists (DelphiScript; a C#/C++ "Altium Designer... (r/s) | No (core): Files are open S-expressions, which code-first tools... (i) | Partial: HyperLynx DRC is scriptable in Python, with action scripts... (r) | Yes: Python (≥ 3.12), jitx 4.6.x; earlier versions used the... (r/s) | No: Works on native ECAD files (r) | Yes: atopile, General LLMs, tscircuit; Partial: Cadence Allegro, EasyEDA |
| **A4** Imports existing design | No: imported-design checker retracted (r) | Yes: Altium, OrCAD/Allegro, KiCad, PADS/Xpedition, CADSTAR... (r) | Partial: "Improved KiCad import and export" (release notes... (r) | Yes (for review): AVE reviews schematics "exported from your ECAD system" or... (r) | Yes: KiCad project as input; AI reviewer reads schematics... (r) | Yes: Schematic + board from Altium, KiCad, Cadence Allegro (BRD... (r) | Yes: Import Wizard: KiCad (legacy and current... (r) | Yes: Altium, Eagle, CADSTAR, EasyEDA (earlier); new in 10.0:... (r) | Yes: Rival-format importers are table stakes; Quilter and... (s) | Not found: Pricing page lists "KiCad and Altium integration" without... (n) | Yes: Native schematics from Altium, KiCad, OrCAD, Allegro System... (r) | Yes: Fusion, Cadence Allegro, Cadstrom, DeepPCB, EasyEDA, Embedder, Freerouting, General LLMs, OrCAD X, ProtoFlow, Trace, Traceformer, tscircuit; Partial: SnapMagic, Zuken |
| **A5** Requirement kept as its own artifact | Yes: IntentIR hashed; design derived from it (r) | Partial: Project plan from the Brainstorm step; "Interactive Pages... (r/s) | Yes: Intent Document with step-by-step plan; the assistant... (r) | Partial: Block diagram and requirements drive generation; Interface... (r) | Partial: Requirement testbenches in the reference-design pipeline... (r) | Partial: Constraints live per job and are reviewed before... (i) | Yes: Requirements are first-class objects in Altium 365, traced... (r) | No: — (n) | Yes: Requirements management in design capture, with a... (r) | Partial: Requirements live as code in the design repository, but not... (i) | Not found: — (n) | Partial: atopile, Embedder, Trace, Zuken |
| **A6** Clarifying questions / refusal | Yes: asks for missing fields; refuses by name; retry may not rewrite (r) | Partial: "Flux now asks clarifying questions before jumping into... (r) | Yes (questions); Partial (refusal): Asks questions "until the design intent is complete"... (r) | Not found: — (n) | Not found: Reviewer instructed not to "invent findings without... (r) | Partial: Does not ask; constraints it does not recognise are routed... (r) | Not found: The assistant "proposes" changes for approval; no... (n) | No: Not an AI product (i) | Partial: Fuse claims "built-in validation and guardrails" and "human... (r) | Not found: — (n) | Not found: Interactive real-time discussion during review is "planned... (r) | Partial: atopile, Cadstrom, DeepPCB, Embedder, General LLMs, Traceformer |

### B. Schematic

| Row | Circuit OS | [Flux](competitor-features/flux.md) | [CELUS](competitor-features/celus.md) | [Circuit Mind](competitor-features/circuit-mind.md) | [Diode](competitor-features/diode-computers.md) | [Quilter](competitor-features/quilter.md) | [Altium](competitor-features/altium.md) | [KiCad](competitor-features/kicad.md) | [Siemens](competitor-features/siemens-xpedition-pads.md) | [JITX](competitor-features/jitx.md) | [AllSpice](competitor-features/allspice.md) | Other products |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **B1** Schematic from intent | Partial: 6 generators + composition (r) | Yes: Agent "turns the plan into a schematic"; places parts and... (r) | Yes: Block diagram → CUBOs resolved → reference schematic + BOM (r) | Yes: Functional schematic with supporting circuitry, multiple... (r) | Yes: "Your requirements become a schematic and layout, written... (r) | No: "Does Quilter generate schematics? No" — the schematic must... (r) | No: Not offered; the 2026 AI scope is requirements only (r) | No (core): Third-party: Huaqiu Copilot claims an experimental "natural... (s) | Partial: CELUS front end: block diagram to reference schematic and... (r) | Yes: "generates routing, fencing, pin assignments, and schematic... (r) | No: Reviews only (r) | Yes: General LLMs, ProtoFlow, Trace, tscircuit; Partial: atopile, SnapMagic, Zuken |
| **B2** AI edits inside an existing schematic | Partial: patches its own designs only (r) | Yes: Agent edits imported Altium/Cadence designs; Markup mode:... (r/s) | Partial: Editable blocks, CUBO lock/unlock, component replacement... (r) | Partial: AVE reviews existing schematics (flags, does not edit) (r) | Yes: Agent skill writes and edits Zener; edits checked in pull... (r/s) | No: "Quilter is not a copilot" (r) | No (first party) / Partial (third party): No first-party schematic copilot. Third-party MCP servers... (r/s) | No (core) / Partial (third party): MCP servers: mixelpixx/kicad-mcp-server (~1K stars, 100–122... (s) | Partial: Product Support Copilot answers documentation questions in... (r) | Yes: jitx design session + jitx design exec let an agent inspect... (r) | Partial: DRCY Chat explains circuits, traces nets, locates... (r) | Yes: atopile, General LLMs, ProtoFlow, SnapMagic, Trace; Partial: EasyEDA, OrCAD X, tscircuit |
| **B3** Part selection with reasons | Yes: justification per part + explainer (r) | Partial: Agent "reads the datasheet of every part and checks the... (r) | Yes: Each component recommendation "links to the datasheet... (r) | Partial: "Deterministic, physics-based algorithms and component... (r) | Partial: Agent reads datasheets; pcb CLI searches components and... (s) | No: Uses the user's parts and footprints as given (r) | Partial: Live pricing, stock, lifecycle, risk and alternates shown... (r/s) | No: — (n) | Partial: CELUS front end picks "suitable solutions"; reasons not... (r) | Partial: Ordered provider chain (company database → CSV of preferred... (r) | No: Not a design tool; "BOM intelligence" and COGS reports from... (r) | Partial: atopile, Cadence Allegro, General LLMs, OrCAD X, ProtoFlow, SnapMagic, Trace, tscircuit, Zuken |
| **B4** Reusable modules / reference designs | Partial: composition of blocks (r) | Yes: Forkable reference designs, MCU platforms, manufacturer... (r) | Yes: CUBOs (smallest reusable functional block) authored by... (r) | Yes: Customer "validated design blocks" calibrate the platform (r) | Yes: Zener modules; about 250 reference designs drafted in two... (r) | Not found: Nothing in the docs index (n) | Yes: Design Reuse panel (enhanced, open beta 26.5)... (r/s) | Yes: Design Blocks (9.0, schematic) extended to the PCB editor... (r) | Yes: Hierarchical design and reusable blocks; physical reuse and... (r) | Yes: Docs ship "reusable components, substrates, and patterns"... (r) | Not found: — (n) | Yes: atopile, Fusion, Cadence Allegro, OrCAD X, tscircuit, Zuken; Partial: EasyEDA, Embedder, General LLMs, Trace |
| **B5** ERC (voltage-aware?) | Yes: voltage-aware rules; proved over tolerances (r) | Yes (voltage-aware not found): Agent runs ERC and DRC continuously; new ERCs added Feb... (r) | Partial: Rule-based port-type matching (I2C to I2C, SPI needs supply... (r) | Yes (AVE): AVE flags incorrect pin connections, voltage violations... (r) | Partial: Static checks on the full netlist: "power paths, signal... (r) | No: "Quilter doesn't check schematic logic or design intent... (r) | Yes, not voltage-aware: Pin-type connection matrix (Fatal / Error / Warning / No... (r) | Yes, not voltage-aware: Pin-type matrix and power-pin checks; 10.0 adds a warning... (r) | Yes, add-on: **Xpedition Schematic Analysis** (ex-Valydate): "over 150... (r) | Partial: Built-in checks for voltage input/output correctness... (s) | Partial: DRCY flags voltage mismatches, pin swaps, polarity, pull-up... (r) | Yes: Fusion, Cadstrom, EasyEDA, ProtoFlow, Trace; Partial: atopile, Cadence Allegro, General LLMs, OrCAD X, tscircuit, Zuken |
| **B6** Hierarchy / multi-sheet | Not found: one net-label sheet (i) | Not found: Feb 2026 "What's next" lists "tools for organizing complex... (r) | Partial: Blocks and modules; multi-sheet output not documented (i) | Not found: — (n) | Yes: Modules compose hierarchically in code (r) | Partial: Parses hierarchical schematics; no symmetric layout for... (r) | Yes: Hierarchical and multi-channel design listed in Develop (r) | Yes: Hierarchical sheets; design variants (10.0) (r) | Yes: Table stakes; multi-board systems (s) | Yes: "Design Hierarchy" concept page (r) | Yes (read): DRCY sees nets, components, properties, hierarchy... (r) | Yes: atopile, Fusion, Cadence Allegro, EasyEDA, General LLMs, OrCAD X, Trace, tscircuit, Zuken; Partial: Traceformer |
| **B7** Library; symbols/footprints from datasheets | No: 100-entry DB; 31 land patterns, none verified (r) | Partial: Shared community library with LCSC/distributor part pages... (r/n) | Partial: "Millions of components" (meta description); CUBO library... (r/s) | Yes: ELIXIR: datasheet → symbol, footprint, parameters; tens of... (r) | Partial: KiCad library as base; internal Registry (not public)... (r) | No: Keeps the footprints defined in the user's ECAD tool... (r) | Partial: Cloud part libraries, Manufacturer Part Search, IPC-7351B... (r/s) | Partial: Official libraries: 10.0 added 952 symbols, 1,216... (r/n) | Partial: Active-model wizard builds part models from Designer... (r) | Not found: No database size stated; a CSV datasheet column is copied... (r) | No: Not a library tool (i) | Yes: OrCAD X, ProtoFlow, SnapMagic, Trace; Partial: atopile, Fusion, EasyEDA, Embedder, General LLMs, tscircuit |

### C. Simulation and analysis

| Row | Circuit OS | [Flux](competitor-features/flux.md) | [CELUS](competitor-features/celus.md) | [Circuit Mind](competitor-features/circuit-mind.md) | [Diode](competitor-features/diode-computers.md) | [Quilter](competitor-features/quilter.md) | [Altium](competitor-features/altium.md) | [KiCad](competitor-features/kicad.md) | [Siemens](competitor-features/siemens-xpedition-pads.md) | [JITX](competitor-features/jitx.md) | [AllSpice](competitor-features/allspice.md) | Other products |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **C1** SPICE | Yes: ngspice via Celery, 15% grader; crash recorded as success (open defect) (r) | Yes: Built-in ngspice: operating point, AC sweep, transient... (r) | Not found: No simulation on any page read (n) | Not found: — (n) | Partial: Blog: "each module can run SPICE simulations... (r/n) | No: User remains responsible for "Signal simulation and... (r) | Yes, included: Built-in Mixed Simulation, SPICE3f5-compatible, reads... (r/s) | Yes, built in: ngspice embedded in the schematic editor: OP, DC sweep, AC... (r/s) | Yes, add-on: HyperLynx AMS (analog/mixed-signal) is named among... (r) | Partial: spice statement attaches ngspice-syntax models to... (s) | Not found: — (n) | Yes: Fusion, Cadence Allegro, EasyEDA, General LLMs, OrCAD X, ProtoFlow, tscircuit; Partial: Cadstrom |
| **C2** Tolerance / Monte Carlo / worst-case | Yes by proof over tolerance boxes; no Monte Carlo (r) | Partial: Not built in: the Nov 2026 post runs Monte Carlo (1,000... (r) | Not found: — (n) | Partial: Derating analysis (component stress vs ratings); no Monte... (r) | Not found: — (n) | Not found: PRC tolerances are example acceptable ranges, not a... (n) | Yes (Monte Carlo, sensitivity): Monte Carlo varies component values randomly across... (s) | Partial: Possible only through raw ngspice control scripts (.control... (i) | Not found: Not checked this pass for HyperLynx AMS (n) | Partial: Net voltages are toleranced values checked against part... (s) | Partial: "Derating analysis" named as a DRCY capability; method not... (r) | Yes: Cadence Allegro, OrCAD X; Partial: atopile, Cadstrom, General LLMs, tscircuit |
| **C3** Formal proof / exhaustive verification | Yes: sympy MNA + z3; 64/64 mutants caught; 12 properties unsigned (r) | Not found: No proof or exhaustive check on any page read (n) | Not found: — (n) | Not found: "Provable accuracy" / "self-verifying algorithms" claimed... (r) | Not found: Testbench assertions on requirements (not proof) (r) | Not found: — (n) | Not found: Searched docs and release notes; nothing beyond simulation... (n) | No: — (n) | Not found: — (n) | Not found: No proof claimed; earlier teardown found none (n) | No: Paper and posts describe LLM agents with consensus; no... (r) | Partial: atopile |
| **C4** Signal integrity | No (r) | Yes: Cloud full-wave EM on routed copper and stackup:... (r) | Not found: — (n) | Not found: — (n) | No (left to engineers): "Engineers still handle routing strategy and signal... (r) | Partial: **Before routing:** trace geometry for impedance from... (r) | Yes (included) + paid add-on: Included: reflection and crosstalk simulator, 13 SI rules... (r) | Partial: IBIS models in the simulator; time-domain track tuning and... (r) | Yes, add-on: HyperLynx SI: DDRx (parallel batch, CUDIMM), SerDes /... (r) | Yes: Impedance-keyed routing structures, diff pairs... (r) | No: DRCY "cannot check … trace widths, clearances, impedance" (r) | Yes: Cadence Allegro, OrCAD X, Zuken; Partial: Cadstrom, tscircuit |
| **C5** Power integrity / IR drop | No (r) | Yes (claimed): PDN impedance vs frequency with vendor capacitor models... (r) | Not found: Intent captures "power budget" but no check described (r) | Partial: Power analysis (budget), not PDN or IR drop (r) | not covered | Partial: **After routing:** "Voltage drop for power pours "... (r) | Paid add-on, DC only: **Power Analyzer by Keysight**: DC voltage drop, current... (r) | No (core): Third party: KiCad-Parasitics (DC R via ngspice), padne (DC... (r) | Yes, add-on: HyperLynx PI: DC drop with DC Metrics Viewer, DC Shared... (r) | Partial: Homepage says the closed loop "extends to SPICE, power, and... (r) | Not found: — (n) | Yes: Cadence Allegro, OrCAD X, Zuken; Partial: Cadstrom |
| **C6** Thermal | No (r) | Partial (claimed): "Estimates board temperatures from the operating... (r) | Not found: — (n) | Not found: — (n) | not covered | Partial: **Before routing:** power-net widths from IPC-2221 heating... (r) | Not found: No native board thermal solver (physics report). Not found... (n) | No (core): Third party: ThermalSim plugin (r) | Partial: Board-level thermal co-simulation in HyperLynx PI (VX.2.10... (s) | Partial: Same homepage claim; no doc page found (r) | Partial: Example finding: regulator thermal pad needs via stitching... (s) | Yes: Cadence Allegro, OrCAD X; Partial: Fusion, Cadstrom, General LLMs, Zuken |
| **C7** EMC / EMI | No (r) | Partial: Layout review of return paths, switching loops, crosstalk... (r) | Not found: — (n) | Not found: — (n) | not covered | Not found: FAQ says PRCs cover "considerations such as thermal... (n) | Third party: EMIStream extensions (NEC) and Ansys SIwave via EDB export... (r) | No: — (n) | Partial: HyperLynx DRC: 90+ rules across SI, PI, EMI and safety... (r) | Not found: — (n) | Partial: "Missing ESD protection" listed as an example catch (r) | Yes: Zuken; Partial: Cadence Allegro, General LLMs |
| **C8** Creepage/clearance from voltage | No: verifier passed a 0.35 mm mains gap (582771b, on a branch) (r) | Partial: User supplies standard (IEC 62368-1 worked example)... (r) | Not found: — (n) | Not found: — (n) | not covered | No: "doesn't currently support the constraints needed for... (r) | Partial: Creepage Distance rule measures surface path between chosen... (r) | Partial: Creepage custom-rule constraint since 9.0, user-typed... (r) | Yes: Creepage clearance validation in the Xpedition layout... (r) | Not found: — (n) | Not found: — (n) | Partial: General LLMs |

### D. PCB layout

| Row | Circuit OS | [Flux](competitor-features/flux.md) | [CELUS](competitor-features/celus.md) | [Circuit Mind](competitor-features/circuit-mind.md) | [Diode](competitor-features/diode-computers.md) | [Quilter](competitor-features/quilter.md) | [Altium](competitor-features/altium.md) | [KiCad](competitor-features/kicad.md) | [Siemens](competitor-features/siemens-xpedition-pads.md) | [JITX](competitor-features/jitx.md) | [AllSpice](competitor-features/allspice.md) | Other products |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **D1** Automatic placement | Partial, experimental: <=40 parts, 2 layers; flag off in production (r) | Partial: Agent "places components, routes connections, and verifies... (r) | No: KiCad/Altium packages include a board file, but "it is time... (r) | not covered | Partial: Claude proposes decoupling-cap placement, groups bulk caps... (r) | Yes: Reinforcement-learning placement; pre-placed parts kept... (r) | Not found (first party): No auto-placement or AI placement in docs or 2026 release... (s/n) | No (meaningful): Legacy footprint spreading only; no auto-placement in 10.0... (r) | Partial: Placement planning improvements (2604); "thermal-aware... (r/s) | Partial: Agent-driven placement scripts (place_component.py... (r/s) | No: Not a layout tool; layout files are versioned and diffed... (r) | Yes: Cadence Allegro, EasyEDA, OrCAD X, ProtoFlow, Trace; Partial: atopile, DeepPCB, General LLMs, tscircuit, Zuken |
| **D2** Automatic routing | Partial, experimental: A* router, 6/14 connections (r) | Yes: "Route this board" or named nets; keeps existing copper on... (r) | Not found: — (n) | not covered | Not found: Engineers route; pcb layout emits .kicad_pcb for KiCad (r) | Yes: Layers: "2-layer boards to stack-ups of 10 or more", "no... (r) | Yes, rules-based: **Situs** topological autorouter routes the whole board... (r) | No (core): Interactive router only (push-and-shove, walkaround). Third... (s) | Partial: Sketch routing / sketch planner and trunk router... (r/s) | Yes: Topological autorouter: press Q to find "as many legal... (r) | No: Not a layout tool (r/i) | Yes: Fusion, DeepPCB, EasyEDA, Freerouting, ProtoFlow, Trace, tscircuit; Partial: Cadence Allegro, General LLMs, Zuken |
| **D3** Constraint management | Partial: NetClass only (r) | Partial: Layout Rules panel (Q1 2026); object-specific rules created... (r) | Not found: — (n) | not covered | Not found: — (n) | Yes: "Circuit Comprehension" detects power nets, diff pairs... (r) | Yes: Constraint Manager with Simple/Advanced clearance modes... (r) | Yes: Netclasses, custom-rule language, component classes (9.0)... (r) | Yes: Multi-user constraint editing (s) | Yes: Layout Constraints, Design Constraints and SI Constraints... (r) | No: Not a layout tool (r/i) | Yes: Cadence Allegro, OrCAD X, Zuken; Partial: atopile, Fusion, DeepPCB, EasyEDA, Freerouting, General LLMs, Trace, tscircuit |
| **D4** Stackup / controlled impedance | No: stackup fields unread (r) | Yes: Stackup editor; impedance-derived width/spacing rules... (r) | Not found: — (n) | not covered | Not found: 10-layer showcase boards (r) | Yes: Stackup material properties drive Simbeor impedance per... (r) | Yes: Layer Stack Manager with Simbeor field solver; via... (r) | Partial: Board stackup manager; PCB Calculator transmission-line... (s) | Yes: Table stakes; HyperLynx field solvers (s) | Yes: "Substrate & Stackup"; routing structures selected by... (r) | No: DRCY "cannot check … impedance" (r) | Yes: Cadence Allegro, Zuken; Partial: atopile, Fusion, General LLMs, tscircuit |
| **D5** DRC | Yes: own DRC kernel + verify.py rungs; KiCad DRC on a branch, not released (r) | Yes: Continuous DRC; Gerber check runs DRC on the exported... (r) | Not found: — (n) | not covered | Yes: "Every design is checked against the fab's rules before... (r) | Partial: Candidates with DRC errors are not surfaced; fab rules are... (r) | Yes: Online and batch DRC on user-typed geometric rules; no... (r) | Yes, headless: kicad-cli pcb drc with JSON output, --schematic-parity... (r) | Yes: Layout DRC plus HyperLynx DRC (electrical, 90+ rules... (r) | Partial: Issues list with satisfied flags; docs say fab spacing... (r) | Partial: DRCY does not do layout review ("reviews schematics only")... (r) | Yes: atopile, Fusion, Cadence Allegro, DeepPCB, EasyEDA, Freerouting, General LLMs, OrCAD X, ProtoFlow, Trace, Zuken; Partial: tscircuit |
| **D6** 3D view and MCAD exchange | Partial: 3D view, no MCAD exchange (r) | Yes: STEP export; live collaborative 3D/MCAD in Flux... (r/s) | Not found: Layout preview in CUBO view (2025) only (r) | not covered | Not found (KiCad provides): — (i) | Not found: Candidate Reviewer is a 2D view with layer presets; no 3D... (n) | Yes: Native 3D; ECAD-MCAD CoDesign included in Develop... (r) | Yes: 3D viewer; kicad-cli pcb export to STEP, STPZ, GLB, STL... (r) | Yes: MCAD co-design highlighted in Xpedition 2610 (s) | Partial: STEP export (r) | Not found: — (n) | Yes: Fusion, Cadence Allegro, EasyEDA, General LLMs, ProtoFlow, Trace, tscircuit, Zuken |
| **D7** Length tuning / differential pairs | No: DiffPair type never filled (r) | Yes: USB, Ethernet, LVDS, MIPI, PCIe pairs with impedance... (r) | Not found: — (n) | not covered | not covered | Partial: Diff pairs routed coupled; any differential impedance... (r) | Yes: Interactive diff-pair routing; Interactive Length Tuning... (r/s) | Yes: Diff-pair routing; time-domain tuning overhaul with... (r) | Yes: Table stakes (s) | Yes: Router adds deskew bumps and serpentine "signal tuning" to... (r) | No: Not a layout tool (r/i) | Yes: Fusion, Cadence Allegro, EasyEDA, Trace, Zuken; Partial: DeepPCB |
| **D8** HDI / flex / rigid-flex | No (r) | Not found: — (n) | Not found: — (n) | not covered | not covered | Partial: Speedrun was built as 8-layer HDI, but the router places... (r) | Yes: Rigid-Flex (Advanced) mode with substacks; microvia... (r) | Partial: Pad stacks and via tenting (9.0); microvias supported; no... (r/n) | Yes: IPC-4761 via protection native (2604); Valor profiles for... (r) | Not found: — (n) | No: Not a layout tool (r/i) | Yes: Cadence Allegro; Partial: Fusion, EasyEDA |

### E. Firmware

| Row | Circuit OS | [Flux](competitor-features/flux.md) | [CELUS](competitor-features/celus.md) | [Circuit Mind](competitor-features/circuit-mind.md) | [Diode](competitor-features/diode-computers.md) | [Quilter](competitor-features/quilter.md) | [Altium](competitor-features/altium.md) | [KiCad](competitor-features/kicad.md) | [Siemens](competitor-features/siemens-xpedition-pads.md) | [JITX](competitor-features/jitx.md) | [AllSpice](competitor-features/allspice.md) | Other products |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **E1** Generates firmware | Yes: Jinja2 templates for Uno, ESP32, Black Pill (r) | Yes (drivers/tests): Writes pin map, drivers and the hardware interface from the... (r) | Not found: — (n) | not covered | Partial: Claude "can draft bring-up firmware"; "not fully solved" (r) | No: Product is PCB layout from a finished schematic only (r) | Not found: No firmware generation in Altium Designer or 365 docs... (n) | No: No firmware features in core (i) | Not found: — (n) | Not found: Not mentioned on home or docs index (n) | No: Out of scope; "misconfigured registers" listed as a review... (r) | Yes: Embedder, General LLMs |
| **E2** Pin-mux / peripheral config | Yes: pin_rules (pin-mux, conflicts, strapping) (r) | Partial: Pin map built from MCU, sensor, bus and strapping pins in... (r) | Partial: Port/interface assignment on links ("only interfaces common... (r) | not covered | not covered | No: Same: layout only (r) | Not found: — (n) | No: Pin/gate swap with back-annotation (10.0) is layout... (r/i) | Not found: — (n) | Yes: MCU pin functions declared as @provide options (e.g. RP2040... (r) | Partial: Reviews pin usage and interface configuration against... (r) | Yes: Embedder; Partial: Cadstrom, General LLMs |
| **E3** Compiles / tests before showing | Yes, compile only: 21/21 variants; never flashed (r) | Yes: Compiles for STM32, nRF, ESP32-class, RP2040, RISC-V, AVR... (r) | Not found: — (n) | not covered | not covered | No: Same (r) | Not found: — (n) | No: — (i) | Not found: — (n) | Not found: — (n) | No: — (i) | Yes: Embedder; Partial: General LLMs, OrCAD X |
| **E4** Protocol stacks | Partial: Modbus RTU master only; no MQTT/AT (r) | Not found: Tests protocol logic (parsers, checksums, framing) in the... (r) | Not found: — (n) | not covered | not covered | No: Same (r) | Not found: — (n) | No: — (i) | Not found: — (n) | Not found: — (n) | No: — (i) | Yes: General LLMs; Partial: Cadstrom, Embedder |

### F. Explanation and evidence

| Row | Circuit OS | [Flux](competitor-features/flux.md) | [CELUS](competitor-features/celus.md) | [Circuit Mind](competitor-features/circuit-mind.md) | [Diode](competitor-features/diode-computers.md) | [Quilter](competitor-features/quilter.md) | [Altium](competitor-features/altium.md) | [KiCad](competitor-features/kicad.md) | [Siemens](competitor-features/siemens-xpedition-pads.md) | [JITX](competitor-features/jitx.md) | [AllSpice](competitor-features/allspice.md) | Other products |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **F1** Explains each choice | Yes: consequential explanation (r) | Partial: Conversational agent explains on request; no per-decision... (i/n) | Partial: Datasheet link per recommendation; answers questions about... (r) | Partial: Trade studies across options; per-part reasons not shown (r) | Not found: — (n) | Partial: Per-PRC pages explain why a check failed; no per-decision... (r) | No (design): Requirements carry a "rationale" field written by people or... (r) | No: — (n) | Not found: — (n) | Not found: — (n) | Partial: Explains what a part or net does when asked (e.g. why a... (r) | Yes: General LLMs; Partial: Cadstrom, DeepPCB, Embedder, ProtoFlow, Traceformer |
| **F2** Confidence / evidence grading | Yes: claims graded G0-G7, defeaters, "not assessed"; 0-1 confidence is a constant (r) | No / Not found: Raise post: working to make the agent "clearer about when... (r) | Not found: — (n) | Partial: AVE QA pass "critiquing every finding so only the ones that... (r) | Partial: Reviewer ranks findings critical / warning / note (r) | Partial: Per-candidate Pass/Warn/Fail counts (2026-09-30); sorts... (r) | Not found: — (n) | No: — (n) | Partial: Valor DFSC: pass/fail per IPC profile (Class 1-3, Level A-C) (r) | Not found: Issues carry satisfied and checks_complete flags... (r) | Partial: Findings link to "the datasheet section, pin requirement... (r) | Partial: Cadstrom, Embedder, Freerouting, Traceformer, Zuken |
| **F3** Automated design review | Yes: own designs only (r) | Yes: "Altium-level review": SI, PI, EMC, DFM, thermal... (r) | Partial: Agent checks design against the Intent Document and... (r) | Yes: AVE against datasheets, app notes, checklists, design... (r) | Yes: Read-only AI EE reviewer; found 22 or 24 bugs (figures... (r) | Yes: Eight PRCs (Pin Distance, Trace Path Length, Layer Switch... (r) | Partial: ERC (pin type), DRC (geometry), SI rules; "Background... (r) | Partial: ERC + DRC + schematic parity; reports in JSON (r) | Yes: Schematic Analysis (voltage-aware), HyperLynx DRC, Valor... (r) | Partial: rd.issues() returns error count, issue text and a... (r) | Yes: Five-agent pipeline: netlist augmentation, component... (r) | Yes: Cadstrom, OrCAD X, Trace, Traceformer, Zuken; Partial: atopile, Fusion, Cadence Allegro, DeepPCB, EasyEDA, Freerouting, General LLMs, ProtoFlow, tscircuit |
| **F4** Datasheet-grounded checks with cited pages | Partial: page-cited figure provenance, person-verified; D7 open on 4 generators (r) | Partial: Reads every part's datasheet; no page citations found (r) | Partial: Citations to the datasheet or specification per... (r) | Yes: Each AVE issue linked "to its component, connection, and... (r) | Partial: Reviewer reads datasheets; citations not described (r) | No: "We don't automatically review datasheets" (r) | Not found: — (n) | No: — (n) | Partial: Schematic Analysis builds models from manufacturer part... (?) | Not found: — (n) | Yes: "Every finding cites the datasheet page it came from" (e.g... (r/s) | Yes: Traceformer; Partial: atopile, Cadstrom, Embedder, General LLMs, OrCAD X, Trace |
| **F5** Audit trail of AI actions | Partial: patch history with cited words + sign-off hash; no UI (r) | Partial: Change History lists previous versions and restores them... (r) | Partial: Plan approval gate; MCP changes need user confirmation. No... (r) | Not found: — (n) | Yes (by construction): Designs in version control with code review and pull... (r) | Partial: Console drawer of job messages and errors (2026-04-07)... (r) | Partial: Every AI change is previewed side by side and needs... (r) | No (r) | Partial: Fuse claims role-based access, audit trails, human... (r) | Partial: Code edits are versionable; runtime layout edits by the... (r) | Yes: Findings are review comments alongside humans'; engineers... (r) | Partial: atopile, EasyEDA, Embedder, Freerouting, General LLMs, ProtoFlow, Trace, Traceformer, tscircuit |

### G. Collaboration and editing

| Row | Circuit OS | [Flux](competitor-features/flux.md) | [CELUS](competitor-features/celus.md) | [Circuit Mind](competitor-features/circuit-mind.md) | [Diode](competitor-features/diode-computers.md) | [Quilter](competitor-features/quilter.md) | [Altium](competitor-features/altium.md) | [KiCad](competitor-features/kicad.md) | [Siemens](competitor-features/siemens-xpedition-pads.md) | [JITX](competitor-features/jitx.md) | [AllSpice](competitor-features/allspice.md) | Other products |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **G1** Conversational edits | Yes: RFC 6902 ops, each citing the user's words (r) | Yes: Steering mid-build; side threads, parallel agents, agents... (r/s) | Yes: Engineer can "stop, redirect, or edit at any step"; Claude... (r) | Not found: — (n) | Partial: Agent edits Zener on request (self-serve) (i) | Not found: Iteration is "edit and iterate": change inputs and resubmit (n) | No (design) / Partial (requirements): Requirement edits by chat, approved by a person (r) | No (core): Via third-party MCP only (s) | Not found: Copilots answer documentation questions only (r) | Partial: Through an external agent; the task author restricts what... (r) | No: Chat answers; no edits (r) | Yes: atopile, Embedder, General LLMs, ProtoFlow, SnapMagic, Trace; Partial: DeepPCB, EasyEDA, tscircuit |
| **G2** Version history / diff / branch / restore | Partial: GET /history; no rollback, diff or UI (r) | Partial: Change History with restore; forking and cloning; no branch... (s) | Partial: Project clone via MCP; no version history found (r/n) | Not found: — (n) | Yes: Git: diffs, branches, review (r) | Partial: Projects group every job of one design (2026-04-07)... (r) | Yes: Git-based version control in Altium 365; visual diff of... (r) | Partial: KiCad 10 has built-in Git support in the project manager:... (s) | Yes: Xpedition EDM: revisions, check-in/out, approval workflows... (r) | Partial: Design is code in git; parts.lock.json committed so builds... (r/i) | Yes: Git-based revision control with visual diffs and history... (r) | Yes: atopile, Fusion, Cadence Allegro, OrCAD X, ProtoFlow, Trace, tscircuit; Partial: Cadstrom, DeepPCB, EasyEDA, Embedder, General LLMs, Traceformer |
| **G3** Comments / review / roles | No (r) | Yes: Real-time browser collaboration, comments page in docs... (r/s) | Not found: — (n) | Partial: "Your team makes the final call on every flag" (r) | Yes: Pull-request review; enterprise Slack channel (r) | Partial: Notes on jobs and projects by users and permitted Quilter... (r) | Yes: Develop: comments, tasks, unlimited free workspace users... (r) | No: Desktop, single user (i) | Yes: Collaboration notes (2604); access control and approvals in... (r) | Not found: — (n) | Yes: Comments on source files, approvals, milestones, per-unit... (r) | Yes: Fusion, OrCAD X, ProtoFlow, Trace; Partial: atopile, Cadence Allegro, DeepPCB, EasyEDA, Embedder, Traceformer, tscircuit, Zuken |

### H. Supply chain and fabrication

| Row | Circuit OS | [Flux](competitor-features/flux.md) | [CELUS](competitor-features/celus.md) | [Circuit Mind](competitor-features/circuit-mind.md) | [Diode](competitor-features/diode-computers.md) | [Quilter](competitor-features/quilter.md) | [Altium](competitor-features/altium.md) | [KiCad](competitor-features/kicad.md) | [Siemens](competitor-features/siemens-xpedition-pads.md) | [JITX](competitor-features/jitx.md) | [AllSpice](competitor-features/allspice.md) | Other products |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **H1** BOM | Yes: dated static prices (r) | Yes: BOM export; MPN/manufacturer/part type added automatically... (r) | Yes: BOM spreadsheet, CSV with extra component information (r) | Yes: BOM in minutes (r) | Yes: Sourcing of every part by Diode (r) | No: Uses the user's BOM; a BOM change above 10% starts a new... (r) | Yes: ActiveBOM in Designer; BOM Portal in 365 (Develop... (r) | Yes: kicad-cli sch export bom with presets, fields, grouping... (r) | Yes: CELUS front end outputs a BOM; Valor BOM Manager (r) | Partial: BOM as xlsx/tsv in the 2026-10-21 teardown (PyPI, read... (r) | Partial: BOM cross-referencing and COGS reports; release packages (r) | Yes: atopile, Fusion, Cadence Allegro, EasyEDA, General LLMs, OrCAD X, ProtoFlow, SnapMagic, Trace, tscircuit, Zuken |
| **H2** Live price and stock | Partial: Mouser only, optional key (r) | Yes: Arrow, Mouser, DigiKey, LCSC, Verical, TME stock in the... (r/s) | Yes: Mouser price breaks, stock, order quantity, line total... (r) | Partial: Uses customer stock and negotiated pricing; ERP and... (r) | Partial: Instant fab and assembly quotes; distributors not named (r) | Not found: — (n) | Yes: Octopart / IHS Markit data across 100+ suppliers (Digi-Key... (r/s) | No (core): Third-party plugins (e.g. KiCost) and database/HTTP... (s) | Partial: Designer supply-chain client re-engineered (2604)... (r) | No: Stock is handled by curating the CSV or a company provider... (r) | Partial: COGS reports pulling from DigiKey, SiliconExpert "or other... (r) | Yes: Cadence Allegro, EasyEDA, OrCAD X, SnapMagic, Trace; Partial: atopile, General LLMs, ProtoFlow, tscircuit |
| **H3** Alternates / substitution | Yes for passives: substitutes re-proved through the gate (r) | Partial: AI replacement suggestions using project context and... (r) | Yes: Alternatives for passive, electromechanical and... (r) | Partial: Options optimised for cost/size/power and supply... (r/s) | Not found: — (n) | Not found: — (n) | Partial: Alternates suggested from supply data; "evaluate... (r) | No: — (n) | Not found: — (n) | Partial: parts-check flags ideal parts and pinned parts the current... (r) | Not found: — (n) | Yes: SnapMagic; Partial: atopile, General LLMs, OrCAD X |
| **H4** Fab outputs | On a branch, not released (Gerber writer on alpha-program) (r) | Yes: Gerber, drill, BOM, pick-and-place, netlists (EDIF, D-356)... (r/s) | No / Not found: Outputs are ECAD projects, PDF report, BOM; no Gerber (r) | not covered | Yes (via KiCad): KiCad project; Diode fabricates (i) | Partial: Returns candidates in the native ECAD format (Altium... (r) | Yes: Gerber, Gerber X2, NC drill, ODB++ (with IP protection... (r/s) | Yes, headless: Gerber, drill, ODB++, IPC-2581, IPC-D-356, GenCAD, position... (r) | Yes: Blueprint (powered by Valor) generates release... (r/s) | Partial: legacy-odb++, legacy-step, legacy-kicad, legacy-edx... (r) | Partial: Automated release packages via Actions; formats depend on... (r/i) | Yes: Fusion, Cadence Allegro, EasyEDA, General LLMs, ProtoFlow, Trace, tscircuit, Zuken; Partial: atopile |
| **H5** DFM / DFA | No (r) | Partial: Agent checks against each fabricator's rules while it... (r) | Not found: — (n) | not covered | Yes: Manufacturability checks before fab (r) | Partial: Fabricator rule sets preloaded and editable; trace/space... (r) | Partial: Geometric manufacturing rules; Assembly Assistant (INR... (r) | Partial: DRC against fab rules typed or imported as custom rules; no... (i) | Yes: Valor NPI 1,000+ checks; DFSC free in all Valor NPI... (r) | Partial: Manufacturing rules, vias, clearances encoded in design... (r) | Partial: Claimed on AI-agent page ("reference IPC or ISO... (r) | Yes: OrCAD X, Trace, Zuken; Partial: Fusion, Cadence Allegro, EasyEDA, General LLMs, ProtoFlow |
| **H6** Order from a fab inside the tool | No (r) | Yes (claimed): Agent gets quotes for PCB, assembly, 3D printing, CNC... (r) | Not found: — (n) | not covered | Yes: Self-serve quote and order; in-house assembly in Brooklyn... (r) | Not found: A "Pre-supported fabs" page exists in the index; no... (n) | Partial: "Push to Manufacturing" / manufacturing portal for release... (r) | No (core): Fab plugins in the PCM (JLCPCB, PCBWay, Aisler etc.) (r/s) | Not found: Siemens–Xometry partnership seen in search, not tied to PCB... (n) | Not found: — (n) | Not found: — (n) | Yes: EasyEDA, Trace, tscircuit; Partial: General LLMs, OrCAD X, ProtoFlow, SnapMagic |

### I. Platform and business

| Row | Circuit OS | [Flux](competitor-features/flux.md) | [CELUS](competitor-features/celus.md) | [Circuit Mind](competitor-features/circuit-mind.md) | [Diode](competitor-features/diode-computers.md) | [Quilter](competitor-features/quilter.md) | [Altium](competitor-features/altium.md) | [KiCad](competitor-features/kicad.md) | [Siemens](competitor-features/siemens-xpedition-pads.md) | [JITX](competitor-features/jitx.md) | [AllSpice](competitor-features/allspice.md) | Other products |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **I1** Form factor | Browser + HTTP API (r) | Browser: Browser app; cloud agent; mobile dictation (r) | Browser: app.celus.io; phone support (2026-10); embedded "Design... (r) | Browser / enterprise deploy: ace.circuitmind.io login; managed cloud, private cloud... (r) | Browser + CLI: build.diode.computer; pcb CLI (r) | Yes: Browser submission-and-review web app; no plugin (r) | Desktop + browser: Altium Designer on Windows; Altium 365 in browser for... (r) | Desktop: Windows, macOS, Linux (r) | Yes: Desktop, with cloud connectivity (r) | Desktop: Local Python + native runtime + optional board editor... (r) | Browser hub (managed cloud) plus a local sync client (r) | descriptive row; see product files |
| **I2** API / CLI / headless | Yes: HTTP API (r) | Partial: Public MCP server (Aug 2026; extended Oct 2026) for Claude... (r) | Partial: MCP: manufacturer product data reaches agents over MCP... (r) | Not found: PLM, ERP and ECAD integrations named; no API docs (r) | Yes: pcb build, pcb layout; agent skill for Claude (r) | Not found: No API, CLI or scripting page in docs, FAQ or pricing... (n) | Partial: Altium 365 GraphQL API, Altium Designer SDK (C#/C++)... (r) | Yes (CLI) / Partial (API): kicad-cli: sch erc/export, pcb drc/export/import/render... (r) | Partial: HyperLynx DRC Python scripts; Valor Python; Fuse uses MCP... (r) | Yes: jitx CLI (build, export, session, exec); experimental... (r) | Yes: Actions built on GitHub Actions (py-allspice); DRCY runs as... (r/s) | Yes: atopile, Embedder, Freerouting, General LLMs, ProtoFlow, Trace, tscircuit; Partial: Fusion, Cadence Allegro, DeepPCB, EasyEDA, OrCAD X |
| **I3** On-prem / certifications | Partial: self-hostable (i); no certifications (r) | Partial: Cloud only; "SOC 2-aligned cloud infrastructure" (not a SOC... (r/s) | Not found: — (n) | Yes: On-prem and air-gapped; AVE can run on the customer's own... (r) | Not found: — (n) | Yes: Cloud on AWS is "SOC 2 Type 2 compliant" (independent audit... (r) | Yes: SOC 2 Type 2; Altium 365 GovCloud (AWS GovCloud, US... (s) | Yes (local software) / not applicable: Runs locally; no certifications (i) | Partial: Desktop/on-prem; cloud data can be geo-located... (r) | Partial: Enterprise: locally hosted, air-gapped install. SOC 2 /... (r) | Yes: SOC 2 Type 2, SOC 3; Enterprise Self-Hosted tier; GovCloud... (r/s) | Yes: Embedder, Freerouting, Zuken; Partial: Cadence Allegro, Cadstrom, DeepPCB, EasyEDA, General LLMs, ProtoFlow, Trace, tscircuit |
| **I4** Pricing | None: nobody shown to pay (r) | Partial: Official page shows plans Explore, Build, Pro, Teams (per... (r/s) | Partial: No pricing page. AI Credits introduced 2026-07-08 and "can... (r/s) | Not found: No pricing page (n) | Partial: Self-serve: per-order quote; enterprise "From $10,000 per... (r) | Partial: Per project, priced by unrouted pins at upload; pre-routed... (r) | See below: **Develop**: 1 author + workspace + unlimited workspace... (r/s) | Free: GPL, no paid tiers. Paid support from KiCad Services... (r/s) | Partial: No prices found. PADS Pro Essentials "entry-level"... (r) | Yes: Free and Open: free indefinitely for designs under CERN... (r) | Partial: All plans Enterprise, demo required: Core (revision control... (r) | descriptive row; see product files |
| **I5** Sold to | No customer yet (r) | Individuals, startups, teams, enterprise (SLA 2 h response, named account... (r) | Hardware engineers (users) and component manufacturers/distributors (payers):... (r) | Enterprise electronics teams; defence (BAE Systems), industrial (Emerson... (r) | Hardware startups and robotics/defence-adjacent teams (Physical Intelligence... (r) | Yes: Hardware teams; press names defense contractors... (s) | Professional PCB teams, from individuals (Develop) to regulated enterprises... (r) | Everyone; hobbyists through professional teams; CERN pays KSC for support (s) | Yes: Enterprise (Xpedition), SMB and startups (PADS Pro... (r) | Expert hardware teams in aerospace/defence and large OEMs; founder: not a "push... (r/s) | Enterprise hardware teams (EE, PCB, firmware) (r) | descriptive row; see product files |
| **I6** Company facts | not assessed in this pass | USD 37M raised Feb 2026, led by 8VC (with Bain Capital Ventures, Liquid 2... (r) | Founded 2018 in Munich by Tobias, Alexander Pohl and André Alcalde; funding and... (r) | USD 25M announced 2026-10-28 (USD 18.5M Series A led by Norwest + previously... (r) | Founded 2024 by Davide Asnaghi and Lenny Khazan; Series A led by a16z, July... (r/s) | Yes: $25M Series B led by Index Ventures (2025-10-07), about... (r/s) | Renesas completed the A$9.1bn / US$5.9bn acquisition (announced 2024-02-15)... (s) | 2025 fund drive raised over USD 100,000 from 2,500+ donors (funded KiCad 10)... (r/s) | Partial: Part of Siemens AG; bought ASTER (PCB test) per search (s) | $12M Series A led by Sequoia, Sept 2022 (YC, FundersClub, Liquid 2); no later... (r/s) | $15M Series A, 2025-06-24, led by Rethink Impact; ~$25M total. Customers... (s) | descriptive row; see product files |
| **I7** Interop KiCad/Altium/OrCAD | Partial: .kicad_sch out; .kicad_pcb on a branch (r) | Partial: Imports all three (Altium/Cadence on Pro per a community... (r/s) | Yes: Altium project (.PrjPCB with schematic and board), KiCad... (r) | Yes: Export to Altium, OrCAD, Cadence System Capture, Siemens... (r) | Yes (KiCad): Outputs KiCad; requires KiCad 10.x for layout (r) | Yes: Round trip in native format for Altium, Allegro, Xpedition... (r) | Import yes, export no: Imports KiCad, OrCAD, Allegro; no export to KiCad found (r) | Import yes: Imports Altium, Allegro, PADS (10.0), CADSTAR, Eagle... (r) | Yes: Native Xpedition/PADS; ODB++; Quilter returns native... (r) | Partial: KiCad export; Altium and KiCad "integration" on both plans... (r) | Yes: Altium, KiCad, OrCAD, Allegro System Capture, DeHDL... (r) | Yes: Cadence Allegro, Cadstrom, DeepPCB, Freerouting, General LLMs, ProtoFlow, SnapMagic, Trace; Partial: atopile, Fusion, Embedder, Traceformer, tscircuit, Zuken |
| **I8** Open source | AGPL-3.0 licence file; repo visibility not checked (r) | No: Proprietary SaaS (i) | No: Proprietary SaaS (i) | No: Proprietary (i) | Yes (toolchain): Zener and pcb under MIT; service and agent proprietary (r) | No: Proprietary hosted service (i) | No: Proprietary; a Master Services Agreement replaced the EULA... (r) | Yes, GPL: Code GPL; KSC's modifications also GPLv3 (r/s) | No: Proprietary (i) | No: Proprietary runtime; the free tier requires the *design* to... (r) | No: Proprietary hub; py-allspice client library exists (r/i) | Yes: atopile, Freerouting, tscircuit; Partial: DeepPCB, General LLMs, Trace, Traceformer |

### J. Domain coverage

| Row | Circuit OS | [Flux](competitor-features/flux.md) | [CELUS](competitor-features/celus.md) | [Circuit Mind](competitor-features/circuit-mind.md) | [Diode](competitor-features/diode-computers.md) | [Quilter](competitor-features/quilter.md) | [Altium](competitor-features/altium.md) | [KiCad](competitor-features/kicad.md) | [Siemens](competitor-features/siemens-xpedition-pads.md) | [JITX](competitor-features/jitx.md) | [AllSpice](competitor-features/allspice.md) | Other products |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **J1** Industrial interfaces (RS-485, 4–20 mA, 24 V) | Partial: RS-485 bias + termination rules; no 4-20 mA or 24 V (r) | Not found: No industrial rule library found; general agent could draw... (n) | Not found: No RS-485 / 4–20 mA content found; possible as CUBOs (n) | Partial: Industrial customers (Emerson PSS, Schneider); no rule... (i) | Not found: — (n) | Not found: No RS-485, 4-20 mA or 24 V I/O constraint type (n) | Not found: General-purpose tool; no industrial rule library (n) | No: General tool (n) | Not found: — (n) | Not found: — (n) | Not found: — (n) | Partial: Cadstrom, Embedder, General LLMs |
| **J2** Power electronics | No: out of scope (r) | Partial: Isolated power board creepage example; PDN; SPICE on power... (r) | Partial: RECOM power designs added as CUBOs (2026-10-13) (r) | Not found: Power analysis is budget-level (r) | Partial: 3-phase BLDC motor controller reference design (r) | Partial: ≤48 V, ≤10 A recommended; switching-converter placement... (r) | Partial: SPICE with LTspice/PSpice models; DC PI add-on; no... (i) | Partial: ngspice; IPC-2221 width calculator (r) | Partial: HyperLynx PI and AMS; creepage checks (r) | Not found: — (n) | Partial: Regulator feedback-divider error example (flagged a divider... (r) | Yes: OrCAD X; Partial: Fusion, Cadence Allegro, EasyEDA, General LLMs, Zuken |
| **J3** RF / high-speed | No (r) | Yes: Diff pairs to PCIe, DDR routing post, EM/SI to 20 Gbps eye... (r) | Partial: SoM and edge-AI processor CUBOs (NXP i.MX, μSMARC); no SI (r) | Not found: — (n) | Yes (service): 10-layer SDR 70 MHz–6 GHz; Jetson carrier (r) | Partial: Under 6 GHz; diff pairs (USB, PCIe-class), LPDDR4 trained... (r) | Yes: SI simulator, impedance solver, 128 signal layers (beta)... (r) | Partial: Diff pairs, time-domain tuning, IBIS; no field solver (r) | Yes: SerDes to 112G PAM4, PCIe Gen 7 (r) | Yes: 56 GHz PCIe gen-7 launch example; SI constraint system... (r) | Not found: — (n) | Yes: Cadence Allegro, OrCAD X, Zuken; Partial: EasyEDA, Embedder, General LLMs, tscircuit |
| **J4** Safety / regulatory standards | No (r) | Partial: IEC 62368-1 creepage worked example; "prepares a safety... (r) | Partial: Intent capture asks about "compliance"; no standards check (r) | Partial: FMEA template and derating (reliability practice), no... (r) | Not found: — (n) | No: No creepage, dielectric breakdown or arcing constraints... (r) | Partial: IPC-7351B footprints, IPC-2581 output, GovCloud for ITAR... (r/i) | Partial: User-typed creepage rule; no standard derivation (r) | Yes: IPC-6012/IPC-A-600 class profiles in Valor DFSC; IPC-4761... (r) | Partial: Tutorial check example tests AEC-Q200 ratings on passives... (s) | Partial: DFM/DFA findings "reference IPC or ISO standards" (r) | Partial: General LLMs, OrCAD X, Zuken |
| **J5** Stated limits | Yes: stated limits, "not assessed" printed (r) | Partial: "Professional multi-layer PCBs up to eight layers" (yet... (r) | Partial: Bounded by CUBO coverage; KiCad v7–v9 only; earlier... (r) | Not found: — (n) | Not found: — (n) | Yes: ≤5,000 pins; pin density >20% best done manually; ≤48 V... (r) | Develop: up to 5 author seats per workspace (1 + 4); "unlimited signal layers"... (r) | None: No board, layer or part limits (free, unrestricted) (r/i) | Not found: — (n) | Not found: Layer counts, board size and part limits not stated... (r/n) | Yes: Schematics only; no layout review; no real-time discussion... (r) | Yes: DeepPCB, General LLMs, Traceformer; Partial: atopile, Cadence Allegro, Embedder, ProtoFlow, tscircuit |

---

## 4. Where Circuit OS stands, row by row

"Shared with" names products whose file says Yes. "Behind" says by how much. The evidence for each
competitor is the cell in section 3.

### 4.1 Every row

| Row | Circuit OS | Standing | Shared with / ahead of it |
|---|---|---|---|
| A1 Prompt | Yes | Parity | Flux, CELUS, Diode, ProtoFlow, Trace, SnapMagic (waitlist), Embedder (firmware), general LLMs |
| A2 Form / spec | Yes | Parity | CELUS, Circuit Mind, Altium, Siemens, JITX, atopile, Cadence, Zuken |
| A3 Design as code | No (by design) | Absent | JITX, atopile, tscircuit, Diode, general LLMs |
| A4 Import | No | Absent | Nearly every product: Flux, Quilter, Altium, KiCad, AllSpice, Circuit Mind AVE, DeepPCB, reviewers |
| A5 Requirement artifact | Yes | Shared; strong form alone | Altium Requirements Portal, Siemens requirements, CELUS Intent Document are Yes. None was found that derives the design from a hashed requirement |
| A6 Questions / refusal | Yes | Shared; strong form alone | CELUS asks until intent is complete (refusal Partial); Flux asks. None refuses by name or forbids a retry from rewriting the request |
| B1 Schematic from intent | Partial | Behind, far | Flux, CELUS, Circuit Mind, Diode, ProtoFlow, Trace, JITX, general LLMs are open-ended; Circuit OS has 6 generators plus composition |
| B2 AI edits existing schematic | Partial | Behind | Flux, Diode, JITX, atopile, ProtoFlow, Trace, SnapMagic edit any schematic; Circuit OS only its own |
| B3 Part choice with reasons | Yes | Parity | CELUS Yes (datasheet link per recommendation); many Partial |
| B4 Reusable modules | Partial | Behind | Altium, Siemens, CELUS (CUBOs), Circuit Mind, Diode, JITX, atopile, KiCad, Cadence, Zuken, tscircuit |
| B5 ERC (voltage-aware) | Yes | Parity; distinct in being proved over tolerances | Flux, Circuit Mind, Altium, KiCad, Siemens, EasyEDA, Cadstrom, ProtoFlow, Trace, Fusion (most not voltage-aware) |
| B6 Hierarchy | Not found | Absent | Altium, KiCad, Siemens, Diode, JITX, AllSpice, atopile, EasyEDA, Cadence, Zuken, tscircuit, Trace |
| B7 Library | No | Behind, far | Circuit Mind, SnapMagic, Trace, OrCAD X, ProtoFlow; Altium Octopart claims 95M+ parts; Circuit OS has 100 entries |
| C1 SPICE | Yes | Parity | Flux, Altium, KiCad, Siemens, Cadence, Fusion, EasyEDA, OrCAD X, ProtoFlow, tscircuit, general LLMs |
| C2 Tolerance / MC | Yes (proof) | Parity, different method | Altium, Cadence, OrCAD X Yes (Monte Carlo); Flux via LTspice on a cloud PC |
| C3 Formal proof | Yes | **Alone** | atopile Partial (consistency of declared equations, not behaviour); Circuit Mind claims "provable accuracy" with no method published |
| C4 SI | No | Absent | Altium, Siemens, Cadence, Flux (claimed), JITX, OrCAD X, Zuken |
| C5 PI | No | Absent | Siemens, Cadence, Flux (claimed), OrCAD X, Zuken; Quilter DC IR beta |
| C6 Thermal | No | Absent | Cadence, OrCAD X Yes; Flux, Quilter, Siemens Partial |
| C7 EMC | No | Absent | Zuken Yes; Siemens, Cadence, Flux Partial |
| C8 Creepage from voltage | No | Absent | Siemens Yes; Flux, Altium, KiCad Partial with user-typed distances. Circuit OS's own verifier passed a 0.35 mm mains gap (on a branch) |
| D1 Placement | Partial, experimental | Behind, far | Quilter, Cadence, EasyEDA, OrCAD X, ProtoFlow, Trace |
| D2 Routing | Partial, experimental | Behind, far | Quilter, DeepPCB, Flux, Altium, Fusion, EasyEDA, Freerouting, ProtoFlow, Trace, JITX, tscircuit; Circuit OS routes 6 of 14 room-monitor connections |
| D3 Constraints | Partial | Behind | Altium, Siemens, Cadence, KiCad, OrCAD X, Quilter, JITX, Zuken |
| D4 Stackup / impedance | No | Absent | Flux, Altium, Siemens, Cadence, JITX, Quilter, Zuken |
| D5 DRC | Yes, experimental | Behind in maturity | Every layout tool |
| D6 3D / MCAD | Partial | Behind | Altium, Flux, Siemens, Cadence, KiCad, Fusion, EasyEDA, ProtoFlow, Trace, tscircuit, Zuken |
| D7 Length / diff pairs | No | Absent | Altium, Flux, Siemens, Cadence, KiCad, JITX, EasyEDA, Fusion, Trace, Zuken |
| D8 HDI / flex | No | Absent | Altium, Siemens, Cadence |
| E1 Firmware | Yes | Parity | Flux (drivers and tests), Embedder, general LLMs |
| E2 Pin-mux | Yes | Parity | Embedder, JITX |
| E3 Compile / test gate | Yes (compile only) | Parity with Flux; behind Embedder by one rung | Embedder flashes and tests on hardware; Flux compiles and runs unit tests |
| E4 Protocol stacks | Partial (Modbus RTU) | Behind | General LLMs Yes; Embedder Partial (CAN) |
| F1 Explains choices | Yes | Strong form alone | General LLMs Yes (on request, unchecked); reviewers explain findings, not choices |
| F2 Evidence grading | Yes | Strong form alone | Severity labels (Cadstrom, Diode), Pass/Warn/Fail (Quilter), consensus (DRCY, AVE). None grades each claim or prints "not assessed" |
| F3 Automated review | Yes, own designs | Parity on its own designs; behind in scope | AllSpice, Cadstrom, Circuit Mind, Diode, Flux, Quilter, Siemens, Traceformer, OrCAD X, Zuken review any design |
| F4 Datasheet-cited checks | Partial | Behind in breadth, ahead in verification | AllSpice, Circuit Mind, Traceformer Yes on any design; Circuit OS's figure provenance is narrow but checked by a person |
| F5 Audit of AI actions | Partial | Behind | AllSpice, Diode Yes |
| G1 Conversational edits | Yes | Parity; distinct in citing the user's words | Flux, CELUS, atopile, Embedder, ProtoFlow, SnapMagic, Trace, general LLMs |
| G2 Version history | Partial | Behind | Altium, AllSpice, Siemens, Diode, Fusion, Cadence, OrCAD X, ProtoFlow, Trace, tscircuit, atopile |
| G3 Review / roles | No | Absent | Altium, AllSpice, Flux, Diode, Siemens, Fusion, OrCAD X, ProtoFlow, Trace |
| H1 BOM | Yes | Parity | Nearly all |
| H2 Live price | Partial (Mouser, optional) | Behind | Flux, CELUS, Altium, Cadence, EasyEDA, OrCAD X, SnapMagic, Trace |
| H3 Substitution | Yes, passives | Strong form alone | CELUS, SnapMagic Yes, with no checking method stated |
| H4 Fab outputs | On a branch, not released | Absent in release | Every layout tool |
| H5 DFM | No | Absent | Diode, OrCAD X, Siemens Valor, Trace, Zuken Yes |
| H6 Fab order | No | Absent | Diode, EasyEDA, Flux, Trace, tscircuit |
| I2 API | Yes | Parity | AllSpice, atopile, Diode, Embedder, Freerouting, general LLMs, KiCad, JITX, ProtoFlow, Trace, tscircuit |
| I3 On-prem / certs | Partial | Behind | Altium, AllSpice, Circuit Mind, Embedder, Quilter, KiCad, Zuken, Freerouting |
| I4 Pricing | None | Absent | Every paid product |
| I7 Interop | Partial | Behind | Most |
| I8 Open source | AGPL-3.0 file | Shared | KiCad, atopile, Diode (Zener), tscircuit, Freerouting |
| J1 Industrial | Partial (RS-485) | Strong form alone | Partial: Circuit Mind (industrial customers, no published rules), Cadstrom, Embedder (CAN), general LLMs. Huaqiu KiCad Copilot recognises RS-485 buses (summary, also-found list) |
| J2 Power electronics | No | Absent | OrCAD X Yes; many Partial |
| J3 RF / high speed | No | Absent | Altium, Siemens, Cadence, Diode, Flux, JITX, OrCAD X, Zuken |
| J4 Safety standards | No | Absent | Siemens Yes; Flux, CELUS, Altium, AllSpice, KiCad, Circuit Mind Partial |
| J5 Stated limits | Yes | Parity | AllSpice, DeepPCB, Quilter, Traceformer, general LLMs |

I1, I5 and I6 are descriptive, not features.

### 4.2 Where Circuit OS is truly alone, with the evidence

| Row | What Circuit OS does (code) | Nearest competitor, and why it is not the same |
|---|---|---|
| C3 | `backend/proof/`: sympy nodal analysis of the netlist, z3 over tolerance boxes; the mutation gate caught 64 of 64 mutants. 12 properties are not yet signed | atopile proves its declared equations are consistent, not how the circuit behaves ([atopile.md](competitor-features/atopile.md), C3, r). Circuit Mind says "provable accuracy" but publishes no method ([circuit-mind.md](competitor-features/circuit-mind.md)). No vendor in any file claims a proof |
| F1 (strong form) | `ai/explainer.py`: consequences ("if you change R3…"), tied to checked claims | General LLMs explain on request without checking; Flux has no per-decision rationale artifact; reviewers explain findings, not choices |
| F2 (strong form) | `validation/claims.py`: grades G0–G7, defeaters D1–D9, unchecked rules printed "not assessed (G7)" | Severity labels and pass/fail counts only (Cadstrom, Diode, Quilter, Traceformer). Probe (also-found list) has "visible coverage", from one article |
| A5 + A6 + G1 (strong form) | IntentIR materialised and hashed before the design; refusal by name; a retry may add but never rewrite; patches are RFC 6902 operations over the requirement, each citing the user's words; 409 on a lost race | CELUS's Intent Document and question loop ([celus.md](competitor-features/celus.md), A5/A6, r) is nearest. Altium and Siemens keep requirements as objects but do not generate from them |
| H3 (strong form) | `bom/substitution.py`: a substitute passive is re-derived and re-proved through the gate | CELUS, SnapMagic, Flux, Altium, OrCAD Xplore suggest substitutes; none says how a substitute is checked electrically |
| J1 (strong form) | `rule_engine.py`: RS-485 termination (100–150 Ω) and fail-safe bias; Modbus RTU master firmware | No other file has a published RS-485 rule. Huaqiu's Copilot recognises RS-485 buses (summary); Circuit Mind sells to Emerson and Schneider |

### 4.3 Where Circuit OS is absent

A3, A4, B6, C4, C5, C6, C7, C8, D4, D7, D8, G3, H5, H6, I4, J2, J3, J4. H4 (Gerber) is on a branch,
not released. B7 is so far behind (100 entries, 31 unverified land patterns) that it is close to absent.

---

## 5. The owner's market page, corrected

Source: `market_comparison_2026.html` (the owner's Downloads folder), five columns and 27 rows.
"Page" gives the five cells in the order You / Flux / CELUS / Quilter / Altium. "Now" is what the
code and the product files say on 2026-11-14. Files: [flux](competitor-features/flux.md),
[celus](competitor-features/celus.md), [quilter](competitor-features/quilter.md),
[altium](competitor-features/altium.md); schema rows in brackets.

| Page row | Page | Now: Circuit OS | Now: Flux | Now: CELUS | Now: Quilter | Now: Altium | Best competitor now |
|---|---|---|---|---|---|---|---|
| NL prompt (A1) | Yes / Yes / Yes / No / No | Yes | Yes | Yes | No | No for designs; Partial for requirements (2026-10-14) | Flux, CELUS, Diode, Trace, ProtoFlow |
| Topology selection (B1; no own row) | Yes / Partial / Partial / No / No | Yes, within its catalogue (registry dispatch) | Agent turns a plan into a schematic | Block diagram resolved to CUBOs | No | No | Circuit Mind (trade studies across options), CELUS |
| Schematic generation (B1) | Yes / Yes / Yes / No / Manual only | **Partial**: 6 generators + composition | Yes | Yes | No | No (manual) | Flux, CELUS, Circuit Mind, Diode |
| Component selection with justification (B3) | **Only you** / Shows reasoning / Spec matching / No / No | Yes: justification field per part | Partial: reads datasheets, no per-part reason | **Yes**: datasheet link per recommendation | No | Partial: supply data, no engineering reason | CELUS. **"Only you" false** |
| Confidence scores 0–1 (F2) | **Only you** / — / — / — / — | Field exists but is a hand-written constant per generator (e.g. 0.97, 0.92, 0.9); not a computed score | No | Not found | Partial: Pass/Warn/Fail per candidate | Not found | Nobody computes one. **"Only you" false as written**; "per-claim evidence grade with 'not assessed'" survives |
| PCB auto-layout (D1, D2) | Phase 2+ / Yes 2–4 layer / Yes / Yes physics-driven / Semi-auto | Partial, experimental, off in production | Placement Partial; routing Yes | **No**: user places parts | Yes | Routing Yes (Situs); AI placement not found | Quilter, Cadence Allegro X AI, DeepPCB |
| SPICE (C1) | **Only you** / No, planned / No / No / External SPICE only | Yes | **Yes**: built-in ngspice | Not found | No | **Yes**: built in, with Monte Carlo | Altium, Siemens, OrCAD PSpice. **"Only you" false** |
| Physics layout validation (C4–C6) | Phase 2+ / No / No / Yes best-in-class / Paid add-on | No | **Yes, claimed**: EM/SI, PDN; thermal Partial; solvers unnamed | Not found | **Partial**: Simbeor impedance, IPC-2221 widths, 8 PRCs, DC IR beta | Included SI + paid Keysight power/signal | Siemens HyperLynx, Cadence Sigrity. Quilter is not best-in-class |
| Sim-driven auto-correction (none) | **Only you** / — / — / — / — | **Not in the code.** The loop that let the model rewrite CircuitIR was deleted 2026-09-21 | Agent iterates "until the design passes its checks" | Not found | No | No | Flux. **"Only you" false** |
| V/I rule checks (B5) | Yes / Basic ERC/DRC / Compatibility only / Layout-level only / Yes | Yes, voltage-aware, proved over tolerances | Yes, voltage-aware not documented | Partial | No (no schematic checks) | **Pin-type ERC only**, not voltage-aware | Siemens Schematic Analysis, Circuit Mind AVE, Cadstrom, PSpice Smoke |
| Plain-English validation report (F3) | **Only you** / Shows steps / No / Physics scorecard / Error codes only | Yes | Yes: "Altium-level review" in every plan | Partial | Yes: PRC pages explain failures | Partial | Cadstrom, DRCY, Traceformer, NextPCB. **"Only you" false** |
| Consequential explanation (F1) | **Only you** / — / — / — / — | Yes | Partial: explains on request | Partial | Partial | No | **Survives** (not found elsewhere) |
| Full firmware (E1, E3) | Yes / Assists firmware devs only / No / No / No | Yes: 3 boards, compile gate; never flashed | **Yes**: drivers + unit tests; compiles for STM32, nRF, ESP32-class, RP2040, RISC-V and AVR (Nov 2026) | Not found | No | Not found | Embedder (flashes and tests on hardware) |
| Protocol firmware Modbus/MQTT/AT (E4) | Yes, Phase 3 / — / — / — / — | **Partial**: Modbus RTU master only (exists now); no MQTT or AT | Not found (tests protocol logic) | Not found | No | Not found | General LLMs; Embedder Partial (CAN) |
| Stateful diff-and-patch (G1) | **Only you** / Regenerates from scratch / No / No / Manual edit only | Yes: RFC 6902 operations on the requirement, each citing the user's words | **Edits in place** (steering, slash commands); "regenerates from scratch" is wrong | Yes: "stop, redirect, or edit at any step" | Edit and resubmit | No (design) | **Survives, narrowed** to requirement-level patches that cite the user's words |
| Version history + diff (G2) | Yes, Phase 2 / Basic / No / No / Yes | **Partial**: `GET /history`; no diff, rollback or UI | Partial: restore, no diff | Partial | Partial | Yes: visual diff | Altium, AllSpice |
| RS-485/Modbus rules (J1) | **Only you** / — / — / — / — | Yes: termination + bias rules | Not found | Not found | Not found | Not found | **Survives**; Huaqiu Copilot recognises RS-485 buses (summary) |
| 4–20 mA / 24 VDC (J1) | **Only you** / — / — / — / — | **No code** | Not found | Not found | Not found | Not found | Nobody found. **"Only you" false** |
| HVAC boards (none) | **Only you** / — / — / — / — | **No**: an enum value (`HVAC_CONTROL`) only, no generator | not covered | not covered | not covered | not covered | not covered. **"Only you" false** |
| Safety certification flagging (J4) | **Only you** / — / — / MIL-STD/ITAR only / — | **No code** | Partial: IEC 62368-1 creepage example | Partial: asks about compliance | No | Partial | Siemens (creepage validation). **"Only you" false** |
| Cellular RTU/SCADA (none) | **Only you** / — / — / — / — | **No**: SIM7070G modem is a data entry only | not covered | not covered | not covered | not covered | not covered. **"Only you" false** |
| BOM live pricing Digikey/LCSC (H2) | Yes, Phase 2 / Yes / Yes / No / Yes | **Partial: Mouser only**, optional; DigiKey/LCSC part numbers are fields only | Yes (six distributors) | Yes (Mouser, 2026-11-05) | Not found | Yes (Octopart) | Altium, SnapMagic, Flux |
| Gerber + fab API (H4, H6) | Yes, Phase 2 / Yes / EDA export only / Yes / Yes | **On a branch, not released** | Yes + ordering (claimed) | No Gerber | **Native ECAD files only**; Gerber not mentioned | Yes; no fab checkout | Flux, Trace, EasyEDA, tscircuit, Diode |
| DFM report (H5) | Yes, Phase 3 / Basic DFM tips / No / Layout-level DRC / Yes | No | Partial | Not found | Partial: fab rule sets, not a report | Partial | Siemens Valor |
| Private component libraries (B7) | Yes, Phase 3 / Team libraries / No / No / Yes | No | Partial (shared library) | Partial ("your catalog" for alternatives) | No (uses the user's own) | Partial: cloud libraries | Circuit Mind AML, Altium |
| Audit trail (F5, I3) | Yes, Phase 4 / No / No / ITAR/FedRAMP / Altium 365 lifecycle | **Partial**: patch history with cited words and sign-off hash; no UI | Partial | Partial (plan approval gate) | Partial; SOC 2 Type 2, self-host, GovCloud; **no ITAR or FedRAMP certification claimed** | Partial; SOC 2 Type 2, GovCloud | AllSpice, Altium Agile |
| ROI dashboard (none) | **Only you** / — / — / — / — | **No code** | not covered | not covered | not covered | not covered | not covered (not in the schema). **"Only you" false** |

### 5.1 The 13 "Only you" cells

| Verdict | Cells |
|---|---|
| **False (10)** | Component selection with justification (CELUS has it); confidence scores as written (a constant field); SPICE; sim-driven auto-correction (not in code); plain-English validation report; 4–20 mA / 24 VDC (no code); HVAC boards (enum only); safety certification flagging (no code); cellular RTU/SCADA (data entry only); ROI dashboard (no code) |
| **Survive (3)** | Consequential explanation; stateful patching, narrowed to requirement-level patches citing the user's words; RS-485/Modbus rules |

A reworded fourth cell would also survive: "per-claim evidence grade, with unchecked rules printed
'not assessed'" (row F2).

### 5.2 What the page claimed for Circuit OS that is not in the code

- A computed confidence score. The field is a constant.
- Simulation-driven auto-correction.
- 4–20 mA / 24 VDC, HVAC boards, cellular RTU/SCADA, safety-certification flagging and an ROI dashboard.
- MQTT and AT-command firmware. Only Modbus RTU exists.
- DigiKey/LCSC live pricing. Only Mouser exists.
- Gerber and a fab API. On a branch, not released.
- A DFM report, private libraries, and version diff.

The page also understates two things that do exist: Modbus RTU firmware (marked "Phase 3") and
experimental PCB layout (marked "Phase 2+").

### 5.3 What the page got wrong about competitors

- **Flux:**
  - SPICE "No" is wrong: it has built-in ngspice.
  - Firmware "assists only" is out of date: it compiles and runs unit tests.
  - Physics "No" is wrong: it claims EM/SI, PDN and thermal.
  - "Regenerates from scratch" is wrong: it edits designs in place.
  - "300k+ engineers" conflicts with Flux's 1,099,361 builders (Feb 2026).
- **CELUS:**
  - Auto-layout "Yes" is wrong: the user places parts.
  - Component selection "spec matching" undersells it: each recommendation links the datasheet.
- **Quilter:**
  - Physics "best-in-class" overstates it: impedance from Simbeor, IPC-2221 widths, eight checks and a DC IR beta.
  - Gerber "Yes" is not supported: it returns native ECAD files.
  - "ITAR/FedRAMP": it holds SOC 2 Type 2 and self-hosts, and claims no ITAR or FedRAMP certification.
- **Altium:**
  - "External SPICE only" is wrong: SPICE is built in, with Monte Carlo.
  - V/I "Yes" overstates it: its ERC checks pin types only.
  - "Manual only" layout is wrong: Situs autoroutes.
- "Celus 23k engineers" is not covered by any product file.

---

## 6. What moved since the 2026-10-21 teardowns

Dates are as the product files give them. A few just before 10-21 are included because the
teardowns did not have them.

| Date | Product | Move | File |
|---|---|---|---|
| 2026-10-05 | Freerouting | v2.5.0: REST API, MCP, Docker, native executables | [freerouting.md](competitor-features/freerouting.md) |
| 2026-10-12, 10-21 | EasyEDA Pro | V3.2.206 and V3.2.209 | [easyeda-pro.md](competitor-features/easyeda-pro.md) |
| 2026-10-14 | Altium | Agentic Requirements Engineering (Requirements Portal assistant); AD 26.11 | [altium.md](competitor-features/altium.md) |
| 2026-10-16 | SKiDL | 3.0.0 | [_group-d.md](competitor-features/_group-d.md) |
| 2026-10-18 | Flux | Agent compute (ACU) allowances doubled | [flux.md](competitor-features/flux.md) |
| 2026-10-20 | Zuken | CR-8000 2026 | [zuken-cr-8000.md](competitor-features/zuken-cr-8000.md) |
| 2026-10-21 | Flux | Chat mode; 3D/MCAD; side threads and parallel agents | flux.md |
| 2026-10-26 | Flux | Teams plan, $500 for 5 seats (tracker) | flux.md |
| 2026-10-26 | Siemens | HyperLynx 2610, Valor 2610 | [siemens-xpedition-pads.md](competitor-features/siemens-xpedition-pads.md) |
| 2026-10-27 | Flux | OpenUSD export | flux.md |
| 2026-10-27 | Qiao & Dick | Paper v2 (97.5% with a schema plus verifier) | [general-llm-assistants.md](competitor-features/general-llm-assistants.md) |
| 2026-10-28 | Flux | Agentic routing | flux.md |
| 2026-10-28/29 | Circuit Mind | $25M announced; AVE review launched | [circuit-mind.md](competitor-features/circuit-mind.md) |
| 2026-10 | Flux | EM/SI, PDN and thermal analysis; fab ordering; Gerber check (claimed) | flux.md |
| 2026-10-29 | CELUS | Agentic beta (datasheet link per recommendation) | [celus.md](competitor-features/celus.md) |
| 2026-10-29 | AllSpice | DRCY "under the hood" post | [allspice.md](competitor-features/allspice.md) |
| 2026-10-30 | KiCad | 10.0.8 | [kicad.md](competitor-features/kicad.md) |
| 2026-11-01 | Flux | Explore tier removed | flux.md |
| 2026-11-04 | Flux | Fabrication drawing generated from the design | flux.md |
| 2026-11-05 | CELUS | Mouser price, stock and lead time | celus.md |
| 2026-11 | Flux | Firmware compile and unit tests; bring-your-own-software (LTspice Monte Carlo on a cloud PC); "Fix your BOM" | flux.md |
| 2026-11-06 | Flux | Markup mode | flux.md |
| 2026-11-08 | Flux | SPICE on imported Altium/Cadence boards | flux.md |
| 2026-11-09 | Cadence | OrCAD Xplore (component AI, sourcing) | [orcad-x.md](competitor-features/orcad-x.md) |
| 2026-11-09 | JLCPCB | AI tools list updated | [easyeda-pro.md](competitor-features/easyeda-pro.md) |
| 2026-11-10 | JITX | Agent note | [jitx.md](competitor-features/jitx.md) |
| 2026-11-10 | E-Sharp | Probe article (cite or abstain, visible coverage) | [_group-d.md](competitor-features/_group-d.md) |
| 2026-11-10 | JLCPCB | EasyEDA agent blog updated | easyeda-pro.md |
| 2026-11-12 | CELUS | Claude connector | celus.md |
| since 2026-09-30 | Quilter | Nothing new found | quilter.md |

---

## 7. Not verified

Ordered by how much the answer would change. Duplicates across product files are merged.

1. **No independent accuracy figure exists for any AI product.** Every benchmark is run by its vendor
   or author: Quilter, DeepPCB, Flux, HWE-Bench, PCBSchemaGen, Qiao & Dick and the atopile EEBench
   claim. No review tool publishes precision or recall.
2. **Flux's physics and fab ordering are claims.** No solver is named, no accuracy is stated, and the
   fabs are not named on the ordering page.
3. **Cadence and Autodesk Fusion rest on second-hand reading.** cadence.com returned 403 (4 of 60
   rows read first-hand), and every Autodesk page returned 403. Open questions:
   - whether crosstalk analysis is in OrCAD X Professional;
   - which OrCAD X tier includes AI placement.
4. **Circuit Mind's "provable accuracy"** has no published method. The LANL paper it cites was not
   found.
5. **DeepPCB completion figures disagree:**
   - deeppcb.md: 32,000+ jobs, mean 95.6%, 86% of boards ≥95%;
   - kicad.md: "95.6% of 27,721 boards reached ≥95%".
6. **Quilter: the product files disagree, or the vendor's own pages do.**
   - One stackup per job, or several.
   - Impedance targets: 50/75 Ω only, or any value. The 2026-06-30 changelog says any differential target.
   - Founded in 2019 or 2021.
   - "Speedrun" is described as HDI, yet the router uses through-vias only.
   - Whether it outputs Gerbers in any form.
   - The master report read the 2026-05-31 blind/buried-via entry as weakening the through-vias limit;
     quilter.md reads the same entry as confirming the limit.
7. **Flux pricing.**
   - The official page showed plans with blank dollar fields.
   - The tracker gives Build at USD 80 in one place and USD 100 in another.
   - A tracker says Enterprise dropped SOC 2.
   - Flux states an 8-layer limit but showed a 12-layer import.
   - "300k+ engineers" (owner's page) against 1,099,361 builders (Flux, Feb 2026).
8. **Zuken AI placement**: shipping in CR-8000 2026, or still in development with Valeo.
9. **AllSpice DRCY DFM scope**: two AllSpice pages disagree.
10. **Altium "ML router"**: AtlasPCB claims one; altium.md found none in first-party sources. A
    claimed Altium 365 "placement assistant" also has no primary source.
11. **Diode bug count** in its own case study: 22 or 24.
12. **atopile EEBench (Claude Opus 5 at 61.6%)** appears only as a summary in `_group-a.md`;
    atopile.md does not mention it.
13. **SnapMagic's AI** is waitlist-only. Every SnapMagic AI cell describes an announcement, not a
    shipped product.
14. **Trace and ProtoFlow** rest on vendor claims only. Cherry Blossom, PCBEditor and Skimatly are
    known only from ProtoFlow's comparison page.
15. **Cadstrom's rules and simulation** are undocumented.
16. **Not covered by any file:**
    - "Celus 23k engineers";
    - the ROI dashboard, cellular RTU/SCADA and HVAC rows of the owner's page (not in the schema);
    - Circuit OS's own company facts (I6).
17. **Circuit OS items not checked in this pass:**
    - whether the GitHub repository is public (the AGPL-3.0 licence file exists);
    - whether self-hosting works outside the developer's machine.
