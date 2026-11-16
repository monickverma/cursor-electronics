# SnapMagic (formerly SnapEDA; "SnapMagic Engineer", earlier "SnapMagic Copilot") — feature inventory
Read 2026-11-13 (homepage) and 2026-11-14 (products page, launch coverage). Vendor: SnapMagic (SnapEDA rebranded October 2023) · Latest release found: none dated; the AI product is now named **SnapMagic Engineer** ("agentic circuit design") and is **waitlist-only**; footer still "© 2023" · Earlier teardown: none

**Coverage note.** Homepage read 2026-11-13; products page and launch coverage read 2026-11-14. The decisive fact: the products page lists **SnapMagic Engineer (Copilot) behind "Join the Waiting List"** — three years after the October 2023 announcement it is still not generally available. Most cells are therefore `not found`, which here mostly means "not shipped".

[prod] https://www.snapmagic.com/products (read 2026-11-14; footer © 2023) · [es] https://www.electronicspecifier.com/news/latest/introducing-snapmagic-copilot-revolutionising-electronics-design/ (2023 launch; search snippet) · [job] https://careers.snapmagic.com/o/senior-full-stack-engineer-snapmagic-copilot-2 (search snippet)

## In one paragraph
SnapMagic is best known as SnapEDA, the free symbol/footprint/3D-model search used by a claimed "over 1 million engineers", paid for by component suppliers who buy visibility (an earlier repo report cites SnapMagic's pitch of 1.5 million engineers a year). Its AI product, launched as "SnapMagic Copilot" in October 2023 (TechCrunch, search snippet) and now marketed as **SnapMagic Engineer**, is a chat assistant that sits beside the user's existing ECAD tool (Altium, Fusion 360, Eagle, CircuitStudio, KiCad, Zuken logos), adds repetitive items such as bypass capacitors, "can even automate entire schematics from scratch", optimises a BOM for cost or power, flags out-of-stock parts with alternatives, and buys the BOM from distributor partners in one click (Mouser and Digi-Key logos). Where it stops: the AI product is behind a waiting list on the products page (read 2026-11-14); no simulation, layout, firmware or validation claims; no pricing; no dated 2026 release.

## Features

Source key: [home] https://www.snapmagic.com/ (read 2026-11-13; footer © 2023) · [tc] https://techcrunch.com/2023/10/10/snapeda-becomes-snapmagic-and-debuts-an-ai-copilot-to-help-automate-circuit-board-design (search snippet only) · [supp] https://www.snapmagic.com/for-component-suppliers (cited in `C:\Users\KIIT\cursor-electronics\reports\Circuit OS paying customer evidence.md`, not re-read)

### A. Input and intent
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt | Yes | Natural-language chat; "You can even automate entire schematics from scratch" | read | [home] |
| A2 | Structured spec | Not found | A third-party April 2026 directory mentions uploading a rough sketch (unverified) | summary | search snippet |
| A3 | Design as code | Not found | — | not found ([home]) | — |
| A4 | Imports existing design | Partial | "Works with the tool you already use" — operates inside the user's ECAD project; mechanism (plugin or file) not stated | read | [home] |
| A5 | Requirement as artifact | Not found | — | not found | — |
| A6 | Clarifying questions / refusal | Not found | — | not found | — |

### B. Schematic
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Schematic from intent | Partial (claimed, waitlist) | "Automate entire schematics from scratch"; 2023 launch demo: non-inverting amplifier with gain 2 "with orderable parts"; product is waitlist-only on [prod] | read ([home], [prod]); summary ([es]) | [home], [prod], [es] |
| B2 | AI edits existing schematic | Yes (claimed) | Automates repetitive tasks, e.g. adding bypass capacitors | read | [home] |
| B3 | Part selection with reasons | Partial | "Trained on datasheets"; suggests new components for cost/power; reasons not described | read | [home] |
| B4 | Reusable modules | Not found | — | not found | — |
| B5 | ERC | Not found | — | not found | — |
| B6 | Hierarchy | Not found | — | not found | — |
| B7 | Library | Yes | SnapMagic Search: CAD models "for millions of electronic components"; InstaBuild creates symbols and footprints from datasheets by computer vision and OCR "in minutes"; InstaPart delivers any custom symbol and footprint "in 24 hours"; a job ad cites a dataset of over 10 million components, symbols and footprints | read ([prod]); summary ([job]) | [prod], [job] |

### C. Simulation and analysis
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1–C8 | SPICE, tolerance, proof, SI, PI, thermal, EMC, creepage | Not found | Earlier repo research: SnapMagic does no post-layout physics | not found ([home]); read (physics report) | [home] |

### D. PCB layout
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1–D8 | Layout features | Not found | Layout stays in the user's ECAD tool | inference from [home] | — |

### E. Firmware
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1–E4 | Firmware | Not found | — | not found ([home]) | — |

### F. Explanation, evidence, review
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1–F5 | Explanation, grading, review, citations, audit | Not found | — | not found ([home]) | — |

### G. Iteration and collaboration
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Yes | Chat interface, user "in control" | read | [home] |
| G2–G3 | Version history, review | Not found (lives in the user's ECAD) | — | inference | — |

### H. Supply chain and manufacturing
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | BOM optimisation for cost or power | read | [home] |
| H2 | Live price and stock | Yes | SnapMagic Store (SnapPricing): pricing and availability from "hundreds of distributors"; Copilot claims to flag out-of-stock parts | read | [home], [prod] |
| H3 | Alternates | Yes | Suggests alternatives; how checked not stated | read | [home] |
| H4–H5 | Fab outputs, DFM | Not found | — | not found | — |
| H6 | Order inside the tool | Partial | One-click BOM purchase from distributor partners (Mouser, Digi-Key logos); parts, not boards | read | [home] |

### I. Platform and business
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Partial | Web search (snapeda.com) plus an assistant working alongside ECAD tools; plugin form not confirmed | read | [home] |
| I2 | API / CLI | Not found | — | not found | — |
| I3 | On-prem / certifications | Not found | — | not found | — |
| I4 | Pricing | Not found | No pricing on homepage or products page; supplier-funded model; a directory's "USD 49/month" is unattributed | read (absence); summary | [home], [prod], [supp] |
| I5 | Sold to | — | Engineers (free) and component suppliers (paying for reach) | read | [home], [supp] |
| I6 | Company facts | — | "Over 1 million engineers"; 14 customer logos without names in text | read | [home] |
| I7 | Interop | Yes | Altium, Fusion 360, Eagle, CircuitStudio, KiCad, Zuken (logos) | read | [home] |
| I8 | Open source | No | Proprietary | inference | — |

### J. Domain coverage
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1–J5 | Industrial, power, RF, safety, limits | Not found | — | not found ([home]) | — |

## What the owner's market page gets wrong about this product
Not on the page. Matters for distribution, not for validation: SnapMagic owns the parts-model audience Circuit OS would need for breadth.

## Where it is ahead of Circuit OS / where Circuit OS is ahead
SnapMagic ahead: part-model library and audience (over 1 M engineers); works inside every major ECAD tool; one-click BOM purchase; all major distributors vs Circuit OS's optional Mouser (`.claude/CLAUDE.md`).
Circuit OS ahead: simulation, proofs, compiled firmware, consequential explanation, refusal — none of which appear on SnapMagic's homepage.

## Not verified
The "CoDesigner" name seen on LinkedIn (search snippet); any 2026 release (none found); pricing; whether any waitlisted users have the AI product today. Verdict for the matrix: SnapMagic's AI design product is **announced, not shipped** as of 2026-11-14; its shipped products are the parts library, datasheet-to-footprint generation and distributor pricing.
