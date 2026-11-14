# Group C — established ECAD suites and the AI they have added
Researcher C. Read 2026-11-13 and 2026-11-14. Schema, labels and file format follow `competitor-brief.md`.

## Products covered (full files)

| Product | File | Depth | One-line verdict |
|---|---|---|---|
| Altium (Designer, 365, Develop, Agile) | `altium.md` | Deepest | Shipped AI only on requirements text (Oct 2026); built-in SPICE + SI; paid DC PI and SI add-ons; MCP "coming soon" |
| KiCad 9 / 10 | `kicad.md` | Deepest | Free, headless CLI for ERC/DRC/exports; no AI or autorouter in core; a crowded third-party MCP field; headless API arrives in 11 |
| Autodesk Fusion electronics (ex-EAGLE) | `autodesk-fusion-electronics.md` | Medium (Autodesk pages blocked the fetcher) | EAGLE ended 2026-06-07; ngspice with four analyses; SI extension no longer sold; AI and MCP are mechanical-side |
| EasyEDA / EasyEDA Pro | `easyeda-pro.md` | Full | Free, 7.37M users, auto-place + autoroute + one-click JLCPCB order; agent API skill, no built-in AI |
| OrCAD X (Capture, PSpice, editions) | `orcad-x.md` | Schematic/PSpice/pricing only; layout is researcher B's | PSpice Smoke and Monte Carlo in Professional Plus; OrCAD Xplore (2026-11-09) adds NL component AI |

## Products found and added (short entries)

### Proteus Design Suite 9.x (Labcenter) — short entry; **recommend a full file next round**

Why it matters: it is the incumbent that already does what Circuit OS pitches on firmware — **VSM co-simulates microcontroller firmware against the schematic** — and it has an AI assistant.
- **ProPilot (EDAi), since 9.1**: chat window with access to schematic context, design metadata and simulation settings; reviews schematics *and firmware*, flags likely problems, generates peripheral set-up code, explains component roles, helps with part selection and circuit calculations. Bring-your-own model: OpenAI, Anthropic Claude, DeepSeek, local Ollama, custom endpoints; Labcenter does not charge for ProPilot, model usage is billed by the provider. ProTutor for education. (summary of labcenter.com/whatsnew/9.1 — the page returned 403 to the fetcher; https://www.labcenter.com/whatsnew/9.1)
- **9.2** (free to customers with USC valid on 2026-05-01): ProPilot AI-assisted library part creation (beta, iterative), System Meter virtual multimeter in VSM, simulation support for BLE, RFID and STM32CubeIDE, Output Job Manager, full HDI microvia support (summary; https://www.labcenter.com/whatsnew/9.2/).
- Pricing: no official public figures (quotation wizard shows placeholders); reseller PCB Design Level 2 (1,000 pins) about 1,474 (likely CAD); VSM for AVR about USD 537 (summary; https://www.labcenter.com/quotation-wizard/ ; https://ca.robotshop.com/products/proteus-pcb-design-software-level-2-1000-pins).
- Against Circuit OS: Proteus *runs* the firmware in simulation and lets an LLM review it; Circuit OS *generates* the firmware from the wiring and compiles it before showing it, but does not execute it in a circuit simulation. Neither proves properties of the firmware.

### Huaqiu "KiCad Copilot" (华秋小助手) — short entry

Huaqiu (NextPCB's parent) ships a GPL-3.0 KiCad distribution tracking upstream, launched with a built-in Copilot in March 2026: "@project" parses the whole schematic and identifies key parts and buses (RS-485, CAN, SPI); checks pin connections; suggests layout and thermal fixes; generates symbols from datasheet screenshots and footprints from package-drawing images; looks up prices in Huaqiu's parts database. The version-10 build adds MCP to the Copilot panel; NL-to-schematic is described as experimental; PCB autorouting in the Copilot "temporarily unavailable". Huaqiu claims 8M+ engineers served. (read: https://news.pedaily.cn/20260326/126309.shtml dated 2026-03-26; summary for the MCP/distribution details.) Why it matters: the first *fab-backed* AI layer on KiCad, and it names RS-485 bus recognition — Circuit OS's industrial wedge — as a feature.

### DipTrace 5.3 (Novarm) — short entry, no AI

5.3 (2026-07-08): interactive push editing and a native XML project format for Git; 5.3.5 adds CADint import. No AI features found. Kept only as an EAGLE-refugee alternative. (summary; https://diptrace.com/diptrace-software/whats-new/)

### LibrePCB 2.x — short entry, no AI

2.0.0 (2026-01-28, NLnet/NGI funded), 2.1.0 (2026-05-19: cross-probing, net highlighting), 2.1.1 (2026-06-12). Free, open source, ERC/DRC, 3D. No AI. Positioned as an EAGLE-EOL alternative. (summary; https://librepcb.org/blog/2026-01-28_release_2.0.0/)

## Products dropped, and why

| Product | Decision | Why |
|---|---|---|
| Upverter (Altium) | Dropped | Legacy editor still online per a Feb 2026 Altium article; Altium's energy is in "Upverter Modular" (ex-Geppetto, module-based boards). No 2026 AI or verification features found. If the owner wants module-based board generators, Upverter Modular deserves a look in its own right |
| CircuitMaker (Altium) | Dropped | Free Altium-lite; nothing new in 2026 found |
| Horizon EDA | Dropped | Open source, no 2026 AI or verification news found |
| Siemens PADS / Xpedition, Zuken CR-8000 | Not covered here | Enterprise incumbents; assumed in researcher B's scope (Siemens Fuse AI agent; Zuken CR-8000 2026 adds AI schematic automation incl. automated schematic routing — summary, https://allaboutcircuits.com/news/zuken-bakes-ai-into-pcb-design-to-free-up-designer-for-creative-tasks). **Flag to coordinator** if B does not have them |
| Circuit Mind AVE (Oct 2026), Tomachie (Apr 2026), CELUS + Mouser (Nov 2026) | Not covered here | AI-native verification/generation tools, not ECAD suites; flag to coordinator for groups A/B. Circuit Mind AVE "starts a swarm of AI agents" to review schematics made in ECAD against datasheets, app notes and company rules — directly competes with Circuit OS's claims layer (summary, https://iconnect007.com/article/152189/circuit-mind-launches-aipowered-pcb-design-verification-platform/152186/design) |
| Distributor PCB tools (DigiKey Scheme-it, eDesignSuite) | Dropped | 2026 news is BOM-to-cart purchasing (DigiKey + ST + Ultra Librarian, Mar 2026), not AI design or verification |

## The facts from this group that most change the competitive picture

1. **No incumbent generates a circuit, but every one now lets an outside LLM drive it.** EasyEDA's own GitHub organisation publishes an agent API skill (April 2026, 1.1K stars); KiCad has community MCP servers with 100–219 tools; Altium lists official MCP servers as "Coming Soon" and has working third-party ones; Autodesk ships an official Fusion MCP for Claude (mechanical side). The "AI front end" is becoming a commodity *on top of* incumbents. Circuit OS's difference is not "AI in" but **what stops the AI from producing a wrong board**: JLCPCB's own guide to agent-driven EasyEDA design reports 50 association mismatches on the first native check and tells users to verify every change. Circuit OS's IR-plus-compilers rule, proofs and refusals answer exactly that failure.
2. **Altium's AI went to requirements, and it is the closest thing to Circuit OS's IntentIR in an incumbent.** Agentic Requirements Engineering (Oct 2026, included in every Develop and Agile Teams subscription) imports specs from PDFs, keeps requirements as traced artifacts and proposes edits for human approval. It does not generate or check the design from them. Circuit OS's claim "the requirement is materialized before the design, and the design is derived from it" is still unique, but "requirements as artifacts" no longer is.
3. **Several "only you" validation cells are wrong because of incumbents' simulators.** Altium includes SPICE with Monte Carlo and sensitivity; KiCad, Fusion and EasyEDA all ship ngspice free; OrCAD X Professional Plus has PSpice **Smoke** (component stress vs safe operating limits — a simulated voltage/current rating check) and Monte Carlo. Circuit OS's defensible edge is **proof over the whole tolerance box** plus graded, refusable claims and explanations — not "has SPICE" or "checks ratings".
4. **The maker segment's free tool already auto-places, auto-routes and orders.** EasyEDA Pro (7.37M users) added dual-engine auto-placement and an autorouter with equal-length diff pairs in 2026 and uploads Gerber/BOM/CPL to JLCPCB in one click. Circuit OS's experimental 2-layer, ≤ 40-part layout and lack of fabrication output put it behind the free default there; its edge in that segment is generation, firmware and explanation.
5. **Firmware is still almost empty ground among ECAD suites — except Proteus.** None of Altium, KiCad, Fusion, EasyEDA or OrCAD X generates firmware (EasyEDA's simulator explicitly excludes MCU systems). Proteus simulates MCU firmware in VSM and its ProPilot reviews firmware and generates peripheral set-up code. Circuit OS's compile-gated firmware for Uno/ESP32/Black Pill is a real differentiator against the big suites, but Proteus should be on the owner's page.

Also worth knowing: EAGLE's end on 2026-06-07 pushed a migration wave (Fusion, KiCad, LibrePCB, DipTrace all court it); Fusion's paid SI extension is no longer sold; KiCad's headless IPC API (needed for clean programmatic editing) is a KiCad 11 feature with no date.

## Not verified (group level)

- Official list prices: Altium Develop base price (USD 1,990/yr third party), all OrCAD X editions, Proteus. Autodesk and Labcenter pages returned 403 to the fetcher, so their facts rest on search snippets.
- Whether Altium Requirements AI or Fusion's assistant/MCP touch schematic or PCB data (documents say requirements and mechanical/data only).
- Autorouter completion rates for Altium Situs, Fusion and EasyEDA (none published).
