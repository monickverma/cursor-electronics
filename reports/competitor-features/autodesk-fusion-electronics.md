# Autodesk Fusion electronics (formerly EAGLE) — feature inventory
Read 2026-11-13/14. Vendor: Autodesk · Latest release found: Fusion October 2026 product update (eCAD drill and copper views); September 2026 update added schematic autorouting and module bus authoring · Earlier teardown: none

## In one paragraph

Fusion's Electronics workspace is the EAGLE engine moved inside Autodesk's MCAD product: schematic, 2D/3D PCB, an autorouter, ngspice simulation and tight ECAD–MCAD sync, sold as part of a Fusion subscription (USD 680/year) with a free personal-use tier capped at 2 schematic sheets and 2 layers. **EAGLE itself stopped being sold and supported on 7 June 2026**; everything now lives in Fusion. It is bought by mechanical-first product teams, makers and small companies who want the enclosure and the board in one tool. Its AI work in 2026 is mechanical or general (Autodesk Assistant, AutoTimeline, official MCP servers that connect Claude to Fusion) — **none is documented as touching the electronics workspace**. The paid Ansys-powered Signal Integrity Extension is marked "No longer available for new purchases".

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | Not found (electronics) | Autodesk Assistant and the Fusion MCP (Claude connects to a live Fusion session, announced 2026-04-28) exist; no document says they drive the Electronics workspace | summary | https://aps.autodesk.com/blog/bringing-fusion-claude-creative-work ; https://claude.com/connectors/autodesk-fusion |
| A2 | Structured spec / requirements input | Not found | October 2026 adds a no-code "System Modeler" (mechanical systems context; electronics link not stated) | summary | https://autodesk.com/products/fusion-360/blog/october-2026-major-product-update-whats-new (403 on fetch; search snippet) |
| A3 | Design as code | No | ULP scripts (EAGLE User Language) generate outputs; no design-as-code | summary | https://help.autodesk.com/cloudhelp/ENU/Fusion-ECAD/files/ECD-PREP-MFG-DATA.htm |
| A4 | Imports an existing design | Yes | EAGLE files "fully compatible"; direct Altium Designer project import (schematic, PCB, components, nets, layers) in the July 2026 update | summary | https://www.autodesk.com/solutions/eagle-subscription-faq ; https://www.autodesk.com/products/fusion-360/blog/de/highlights-im-fusion-update-vom-juli-2026/ |
| A5 | Requirement as its own artifact | Not found | — | not found (2026 update posts, help) | — |
| A6 | Clarifying questions / refusal | Not found | — | not found | — |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Schematic from intent | Not found | — | not found | 2026 update posts |
| B2 | AI copilot in schematic | Not found | — | not found | as A1 |
| B3 | Part selection with reasons | No | Attribute-based component search in the Place panel (March 2026); no justification | summary | https://www.autodesk.com/products/fusion-360/blog/march-2026-product-update-whats-new/ |
| B4 | Reusable modules | Yes | Design blocks / modules; module bus authoring (September 2026) | summary | https://www.autodesk.com/products/fusion-360/blog/september-2026-major-product-update-whats-new/ (403; search snippet) |
| B5 | ERC (voltage-aware?) | Yes, not voltage-aware | EAGLE-style ERC on pin directions; no voltage awareness found | summary (from memory, unverified) | — |
| B6 | Hierarchy / multi-sheet | Yes | Up to 999 schematic sheets paid, 2 in personal use | summary | https://www.autodesk.com/products/fusion-360/personal/compare (403; search snippet) |
| B7 | Library; datasheet-generated parts | Partial | Managed libraries; attach existing 3D models to footprints (March 2026); no datasheet-to-symbol AI found | summary | as B3 |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Yes, included | Bundled ngspice (spice3f5-based); four analyses: operating point, DC sweep, AC sweep, transient; digital primitives via ngspice-digital library. Altium's comparison page says it is "untouched since its EAGLE-era implementation" (competitor claim) | summary | https://help.autodesk.com/cloudhelp/ENU/Fusion-ECAD/files/ECD-SPICE-SIM-TYPES-CPT.htm ; https://www.altium.com/compare/autodesk/fusion/develop |
| C2 | Monte Carlo / worst case | Not found | Not among the four documented analyses | summary (absence in help list) | as C1 |
| C3 | Formal proof | Not found | — | not found | — |
| C4 | Signal integrity | Discontinued add-on | Signal Integrity Extension (Ansys-powered: SI, impedance, coupling, export to Ansys) — help page banner: **"No longer available for new purchases"**; Altium states EOL 2026-03-27 | read (banner) / summary (date) | https://help.autodesk.com/cloudhelp/ENU/Fusion-ECAD/files/ECD-PCB-SIM-TOOLS-CPT.htm ; https://www.altium.com/compare/autodesk/fusion/develop |
| C5 | Power integrity | Not found | — | not found | — |
| C6 | Thermal | Partial | Fusion has mechanical/thermal simulation (paid, cloud credits); PCB-specific thermal not verified | inference (Fusion simulation excluded from personal use) | https://www.autodesk.com/solutions/autodesk-fusion-subscription-faq |
| C7 | EMC / EMI | Not found | — | not found | — |
| C8 | Creepage from voltage | Not found | Clearance rules are user-typed (DRC) | summary | https://www.autodesk.com/products/fusion-360/blog/18-things-need-to-know-fusion-360-electronics/ |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Not found | — | not found | 2026 update posts |
| D2 | Automatic routing | Yes | EAGLE-heritage autorouter: route one signal or the whole board, follows DRC, effort levels give multiple results; no completion figures. September 2026: "schematic autorouting" (wires in the schematic) | summary | https://www.autodesk.com/products/fusion-360/blog/18-things-need-to-know-fusion-360-electronics/ |
| D3 | Constraint management | Partial | DRC rules and net classes | summary | as D2 |
| D4 | Stackup / impedance | Partial | Up to 16 layers paid (personal 2); Altium says up to 64 copper layers; impedance was in the SI extension | summary | https://www.altium.com/compare/autodesk/fusion/develop ; personal-use compare page (snippet) |
| D5 | DRC | Yes | Live DRC with Errors panel; DRC from the RULES tab | summary | https://help.autodesk.com/cloudhelp/ENU/Fusion-ECAD/files/ECD-PREP-MFG-DATA.htm |
| D6 | 3D and MCAD | Yes (its strength) | Native ECAD–MCAD in one product; 3D PCB; drill and copper views (October 2026) | summary | October 2026 update (snippet) |
| D7 | Length tuning / diff pairs | Yes | Push-and-shove, QuickRoute, diff pairs with meander tuning (per Altium's comparison) | summary (competitor page) | https://www.altium.com/compare/autodesk/fusion/develop |
| D8 | HDI / flex / rigid-flex | Partial | Flex/rigid-flex in Fusion's 3D PCB; plated through holes (Sept 2026); microvia details not verified | summary (from memory, unverified) | — |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | — | not found | 2026 update posts |
| E2 | Pin-mux | Not found | — | not found | — |
| E3 | Compiles firmware | Not found | — | not found | — |
| E4 | Protocol stacks | Not found | — | not found | — |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Not found | — | not found | — |
| F2 | Confidence grading | Not found | — | not found | — |
| F3 | Automated review | Partial | ERC + live DRC | summary | as D5 |
| F4 | Datasheet-grounded checks | Not found | — | not found | — |
| F5 | Audit trail of AI actions | Not found | — | not found | — |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Not found (electronics) | Fusion MCP is not documented for electronics | summary | as A1 |
| G2 | Version history | Yes | Fusion cloud data management versions every save; Fusion Data MCP exposes data management to AI clients | summary | https://www.autodesk.com/products/fusion-360/blog/introducing-the-autodesk-fusion-data-mcp-server/ |
| G3 | Comments / roles | Yes | Cloud hubs, sharing, built-in task management (October 2026) | summary | October 2026 update (snippet) |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | BOM output | summary | https://www.autodesk.com/products/fusion-360/blog/18-things-need-to-know-fusion-360-electronics/ |
| H2 | Live price and stock | Not found | — | not found | — |
| H3 | Alternates | Not found | — | not found | — |
| H4 | Fabrication outputs | Yes | CAM Processor: Gerber, Excellon drill, assembly, pick-and-place (via ULP), ODB++; IPC-2581 not found | summary | https://help.autodesk.com/cloudhelp/ENU/Fusion-ECAD/files/ECD-PREP-MFG-DATA.htm |
| H5 | DFM / DFA | Partial | DRC to manufacturing preferences | summary | as D2 |
| H6 | Order from a fab | Not found | — | not found | — |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Desktop (cloud-connected) | Fusion desktop client with cloud storage | summary | — |
| I2 | API / CLI / headless | Partial | Fusion Python API and MCP servers (mechanical and data); electronics scripted through ULPs and the EAGLE command line; no headless electronics API found | summary | https://claude.com/connectors/autodesk-fusion ; https://wiki.adom.inc/adom/fusion-bridge/files/skills/fusion-eagle-commands/SKILL.md (third party) |
| I3 | On-prem / certifications | Not found (electronics-specific) | Cloud product | not found | — |
| I4 | Pricing | USD 85/month, **USD 680/year**, USD 2,040/3 years per user (Autodesk listing, via search; fetch 403). Personal use free: < USD 1,000 revenue, non-commercial, 2 schematic sheets and 2 layers (paid: 999 sheets, 16 layers); 80 cm² board limit reported by third parties only; personal use excludes simulation and paid extensions | summary (all Autodesk pages returned 403; read 2026-11-13) | https://www.autodesk.com/solutions/autodesk-fusion-subscription-faq ; https://www.autodesk.com/products/fusion-360/personal/compare |
| I5 | Sold to | Mechanical-first product teams, makers, students | inference | — |
| I6 | Company facts | Autodesk (public). EAGLE sales and support ended 2026-06-07; licensing servers off | summary | https://www.autodesk.com/solutions/eagle-subscription-faq |
| I7 | KiCad / Altium / OrCAD interop | Partial | Imports EAGLE and (since July 2026) Altium; KiCad import/export not found | summary | as A4 |
| I8 | Open source | No | Proprietary | — | — |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | — |
| J2 | Power electronics | Partial | ngspice only | inference (C1) | — |
| J3 | RF / high-speed | Weakening | SI extension no longer sold | read | as C4 |
| J4 | Safety / regulatory | Not found | — | not found | — |
| J5 | Stated limits | Paid: 16 layers, 999 sheets (Autodesk); personal: 2 layers, 2 sheets | summary | personal-use compare page |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

**Fusion ahead:** one product for enclosure and board (Circuit OS has a 3D board view from its Board IR but no MCAD — `.claude/CLAUDE.md`); manual layout of real boards up to 16 layers; autorouter; fabrication outputs; cloud version history; official Claude MCP connection (mechanical side).

**Circuit OS ahead:** design generation from intent; proofs and graded claims; four-analysis ngspice in Fusion versus Circuit OS's scheduled, graded runs and tolerance proofs; compiled firmware; explanations; live pricing (Mouser, optional).

## Not verified

- Every Autodesk marketing and blog page returned HTTP 403 to the fetcher; product facts here rest on search snippets of Autodesk pages and on Autodesk help pages (only the SI-tools help page was read directly).
- Whether Autodesk Assistant or the Fusion MCP can operate on electronics designs.
- What "schematic autorouting" (September 2026) does.
- Exact EOL date of the SI extension (2026-03-27 is Altium's statement).
- IPC-2581 export; ERC behaviour; rigid-flex/HDI support in Fusion electronics.
