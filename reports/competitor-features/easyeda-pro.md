# EasyEDA / EasyEDA Pro (JLC / LCSC) — feature inventory
Read 2026-11-13/14. Vendor: EasyEDA, part of JLC Digital Manufacturing (JLCPCB, LCSC; publicly listed 2026-08-04) · Latest release found: EasyEDA Pro V3.2.209 (2026-10-21) · Earlier teardown: none

## In one paragraph

EasyEDA is the free browser/desktop ECAD tool attached to the JLCPCB fab and the LCSC parts store, and the default for the hobbyist and maker segment Circuit OS started in. EasyEDA Pro (the current editor; "Standard" is legacy) does schematic, PCB, 3D, ngspice and Simulide simulation (since V3.2), a dual-engine **auto-placer and autorouter** (V3.0/V3.2.148), schematic DRC that checks pin and net types, and one-click upload of Gerber, BOM and pick-and-place to a JLCPCB order. Software features are free for commercial use; paid plans sell storage and services. There is **no built-in AI assistant**; instead an EasyEDA-organisation **API skill** (April 2026) lets external coding agents (Claude Code etc.) drive a running EasyEDA Pro client over a WebSocket bridge, and community extensions add copilots. With 7.37 million registered users (end of June 2026) it is the largest installed base in this group.

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | No (built in) / Partial (external agent) | No built-in assistant in any release note read. The `easyeda-api` skill lets an external agent run code in a live client and edit schematic, PCB and libraries; JLCPCB's own guide says each change must be checked in the native editor | read | https://pro.easyeda.com/page/update-record ; https://skills.sh/easyeda/easyeda-api-skill/easyeda-api ; https://jlcpcb.com/blog/ai-tools-for-pcb-design (2026-09-28, updated 2026-11-09) |
| A2 | Structured spec input | Not found | — | not found (release notes V3.0.x, update record) | — |
| A3 | Design as code | Partial | Extension and script API (120 classes, 70 interfaces per the skill); designs remain editor documents | read | https://skills.sh/easyeda/easyeda-api-skill/easyeda-api |
| A4 | Imports an existing design | Yes | DXF, Altium Designer, Eagle, KiCad, EasyEDA Std/Pro, Allegro/OrCAD, PADS (9.5), Protel, LTspice | read | https://prodocs.easyeda.com/en/introduction/std-vs-pro/ |
| A5 | Requirement artifact | Not found | — | not found | — |
| A6 | Clarifying questions / refusal | Not found | — | not found | — |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Schematic from intent | No (built in) | Community "EasyEDA Copilot" claims NL-to-schematic (undated, unofficial) | summary | https://backiee.wasmer.app/https_github_com/biosshot/easyeda-copilot |
| B2 | AI copilot in schematic | Partial (external) | API skill (1.1K GitHub stars, first seen 2026-04-20); community "EasyEDA Agent Connector" extension v0.12.0 (2026-07-14) | read (skill) / summary (connector) | https://skills.sh/easyeda/easyeda-api-skill/easyeda-api ; https://ext.lceda.cn/item/zhoushoujian/easyeda-agent-connector |
| B3 | Part selection with reasons | No | LCSC/JLC parts with stock and price in the library; no justification | summary | https://prodocs.easyeda.com/en/schematic/export-order-parts/ |
| B4 | Reusable modules | Partial | Public OSHWLab projects; assembly variants (V3.0) | read (variants) | https://prodocs.easyeda.com/en/release-note/v3.0.x/ |
| B5 | ERC (voltage-aware?) | Yes, not voltage-aware | Schematic design rules check pin types and net types (V3.2.148); colour-coded levels | read | https://pro.easyeda.com/page/update-record |
| B6 | Hierarchy | Yes | Multi-sheet and hierarchical design | summary (from memory, unverified) | — |
| B7 | Library; parts from datasheets | Partial | "More than 1 million free libraries" (marketing, undated); free part builds by EasyEDA staff: 2/month (free), 6/month (paid); 3D models generated automatically | read (part builds, 3D) / summary (1M) | https://easyeda.com/pricing ; https://prodocs.easyeda.com/en/introduction/std-vs-pro/ ; https://easyeda.com/page/about |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Yes, free | Since Pro V3.2: Simulide (real-time, entry level) and ngspice (transient and AC named). No IBIS; not for MCU/DSP/FPGA systems; no link to code tools. DISA simulation netlist support (V3.2.148) | read | https://prodocs.easyeda.com/en/simulation/introduction/ ; https://pro.easyeda.com/page/update-record |
| C2 | Monte Carlo / worst case | Not found | — | not found (simulation docs) | — |
| C3 | Formal proof | Not found | — | not found | — |
| C4 | Signal integrity | Not found | — | not found | — |
| C5 | Power integrity | Not found | — | not found | — |
| C6 | Thermal | Not found | — | not found | — |
| C7 | EMC / EMI | Not found | — | not found | — |
| C8 | Creepage from voltage | Not found | — | not found | — |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Yes | "Auto Component Placement" (V3.0); dual-engine auto placement (V3.2.148, 2026-06-01). No quality metrics | read | https://prodocs.easyeda.com/en/release-note/v3.0.x/ ; https://pro.easyeda.com/page/update-record |
| D2 | Automatic routing | Yes | Dual-engine autorouter incl. length-matched groups and equal-length diff pairs (V3.2.148); V3.2.206 (2026-10-12) fixed "low V4 auto-routing rate" and progress stalling at 5%. No completion rate published; a third party says 2–6 layers | read / summary (layers) | https://pro.easyeda.com/page/update-record ; https://sourceforge.net/app/easyeda-pro/ |
| D3 | Constraint management | Partial | Custom design rules (API can modify them, V3.2.148) | read | https://pro.easyeda.com/page/update-record |
| D4 | Stackup / impedance | Not found | — | not found | — |
| D5 | DRC | Yes | PCB DRC with real-time clearance hints; 2026 fixes for missed errors and missing footprints; DRC callable via the API | read | https://pro.easyeda.com/page/update-record ; https://prodocs.easyeda.com/en/release-note/v3.0.x/ |
| D6 | 3D and MCAD | Yes | STEP import/export, OBJ export, auto 3D models, 3D shell tools | read | https://prodocs.easyeda.com/en/introduction/std-vs-pro/ |
| D7 | Length tuning / diff pairs | Yes | Equal-length diff-pair autorouting | read | as D2 |
| D8 | HDI / flex | Partial | FPC descriptions in one-click order copy (V3.2.148); no HDI detail | read | https://pro.easyeda.com/page/update-record |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | — | not found | release notes |
| E2 | Pin-mux | Not found | — | not found | — |
| E3 | Compiles firmware | No | Simulation docs: no integration with code development tools | read | https://prodocs.easyeda.com/en/simulation/introduction/ |
| E4 | Protocol stacks | Not found | — | not found | — |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Not found | — | not found | — |
| F2 | Confidence grading | Not found | — | not found | — |
| F3 | Automated review | Partial | ERC (pin/net type) + DRC; schematic comparison tool (V3.0) | read | as B5, D5 |
| F4 | Datasheet-grounded checks | Not found | — | not found | — |
| F5 | Audit trail of AI actions | Partial | Operation logs kept 7 days (free) / 30 days (paid) — not AI-specific | read | https://easyeda.com/pricing |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Partial (external agent) | Via API skill only | read | as A1 |
| G2 | Version history / diff | Partial | Schematic comparison (V3.0); project locking and check-in/out; Git-like version management "planned for 2025" on the comparison page (status unknown) | read | https://prodocs.easyeda.com/en/introduction/std-vs-pro/ |
| G3 | Comments / roles | Partial | Teams, permissions, team libraries; no real-time collaboration in either edition; advanced permissions "coming soon" | read | https://prodocs.easyeda.com/en/introduction/std-vs-pro/ ; https://easyeda.com/pricing |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | BOM export; interactive BOM; BOM for SMT ordering | read | https://prodocs.easyeda.com/en/introduction/std-vs-pro/ |
| H2 | Live price and stock | Yes (one source) | LCSC/JLC stock and price in the parts library; JLCPCB assembles only parts in its own library, separate from LCSC stock | summary | https://prodocs.easyeda.com/en/faq/fabrication/ |
| H3 | Alternates | Not found | — | not found | — |
| H4 | Fabrication outputs | Yes | Gerber, ODB++ 8.2 (.tgz), IPC-D-356A, DXF, PDF with assembly drawings, T/DISA 4001-2025; IPC-2581C via API interface (V3.2.148) | read | https://prodocs.easyeda.com/en/release-note/v3.0.x/ ; https://pro.easyeda.com/page/update-record |
| H5 | DFM / DFA | Partial | DRC; production-draft confirmation by JLCPCB staff recommended for SMT | summary | https://prodocs.easyeda.com/en/faq/fabrication/ |
| H6 | Order from a fab | Yes | One-click: uploads Gerber, BOM and CPL to JLCPCB; one-click component ordering (LCSC) | read (std-vs-pro) / summary (FAQ) | https://prodocs.easyeda.com/en/introduction/std-vs-pro/ ; https://prodocs.easyeda.com/en/faq/fabrication/ |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Browser + desktop | Web editor and desktop client; semi-offline and fully offline modes | read | https://prodocs.easyeda.com/en/introduction/std-vs-pro/ |
| I2 | API / CLI / headless | Partial | Extension/script API; official-org agent skill over WebSocket bridge (needs running client); JLCPCB notes a 30 s timeout per call. No headless CLI found | read / summary (timeout) | https://skills.sh/easyeda/easyeda-api-skill/easyeda-api ; https://jlcpcb.com/blog/ai-tools-for-pcb-design |
| I3 | On-prem / certifications | Partial | On-premises hosting (Windows/Linux AMD64), "Request Quote"; private deployment documented for teams within 100 people. No certifications found | read / summary (100 people) | https://easyeda.com/pricing ; https://prodocs.easyeda.com/en/introduction/std-vs-pro/ |
| I4 | Pricing | Free for commercial use (all software features). Premium individual **USD 19.9/month, annual billing only** (10 GB, 30-day logs, 6 part builds/month); Enterprise USD 39.9/month per member "Coming Soon"; on-prem by quote. Read 2026-11-13; no effective date on page | read | https://easyeda.com/pricing |
| I5 | Sold to | Hobbyists, students, makers, small companies ordering from JLCPCB | inference (pricing and ordering model) | — |
| I6 | Company facts | EasyEDA: 7.37M registered users (end June 2026), 6.58M (end 2025, IPO filing); JLC platform 9.5M+ registered users and 21M+ orders in 2025; JLC Digital Manufacturing listed 2026-08-04 | read (JLC) / summary (EasyEDA counts, Chinese press) | https://jlcpcb.com/news/jlc-digital-manufacturing-announces-public-listing ; https://stock.10jqka.com.cn/20260922/c680156114.shtml |
| I7 | KiCad / Altium / OrCAD interop | Import yes; export Altium and PADS | Exports Altium Designer, PADS, EasyEDA Pro; no KiCad export listed | read | https://prodocs.easyeda.com/en/introduction/std-vs-pro/ |
| I8 | Open source | No | Proprietary, free | read (pricing) | — |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | — |
| J2 | Power electronics | Partial | ngspice transient/AC only | read | as C1 |
| J3 | RF / high-speed | Partial | Diff-pair autorouting; no SI | read | as D2 |
| J4 | Safety / regulatory | Not found | — | not found | — |
| J5 | Stated limits | Storage 0.5 GB free / 10 GB premium; projects, libraries, team members unlimited; simulation not for MCU systems | read | https://easyeda.com/pricing ; simulation docs |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

**EasyEDA ahead:** free, huge user base in exactly Circuit OS's original segment; auto-placement and autorouting on real boards; parts tied to stock; one-click fabrication and assembly order; full fabrication outputs; an official-organisation agent API that lets Claude Code edit designs today.

**Circuit OS ahead:** generated circuits from intent with an IR the LLM cannot bypass (`.claude/CLAUDE.md`, "The One Rule"); proved voltage/current properties; graded claims with refusals; firmware compiled before display (EasyEDA's simulator explicitly excludes MCU systems and code tools); consequential explanations. JLCPCB's own agent guide reports 50 association mismatches on a first native check of an agent-built design — the failure mode Circuit OS's architecture is built to prevent.

## Not verified

- Library size of LCSC/EasyEDA (only an undated "1 million" marketing figure).
- Autorouter completion rate, layer limit and speed.
- Whether the `easyeda` GitHub organisation's skill is formally official (hosted under the org; not labelled).
- Hierarchy support (B6) not re-read.
- Git-like version management status (planned 2025).
