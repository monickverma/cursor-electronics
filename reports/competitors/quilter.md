# Quilter — competitor teardown

Written 2026-10-21 by S8 (competitors). Black-box only: public docs, changelog, pricing page, blog. This builds on `reports/Physics layout validation - what the market does and what Circuit OS can build.md` (the "physics report"). Facts already checked there are summarised and linked, not re-researched. New facts carry a label: **checked** (re-read by a second reader), **read** (primary page opened once), **summary** (search snippet only), **inference** (our reasoning).

Numeric targets for the benchmark loop are in `C:\Users\KIIT\cursor-electronics-alpha\corpus\targets.json`.

## What it computes

Quilter places and routes a board. It returns several layout candidates, ranked. It applies eight Physics Rule Checks (PRCs) to each candidate (physics report, Quilter section).

New this cycle, the three PRC pages the physics report did not open (read):

| PRC | Tolerance | Example acceptable range | Source |
|---|---|---|---|
| Invalid Width Span | width within 10% of nominal | 0-10% of net length out of tolerance; short nets 0-1 cm | [invalid-width-span](https://docs.quilter.ai/physics-rule-checks-prcs/invalid-width-span.md) |
| Uncoupled Spacing | pair spacing within 10% of nominal | 0-1 cm of uncoupled length | [uncoupled-spacing](https://docs.quilter.ai/physics-rule-checks-prcs/uncoupled-spacing.md) |
| Length Mismatch | — | 0-1 cm difference | [length-mismatch](https://docs.quilter.ai/physics-rule-checks-prcs/length-mismatch.md) |

The ±10% figures were unconfirmed in the physics report. They are now read.

Diff-pair impedances supported: 100 Ω differential (50 Ω single-ended) and 85 Ω differential (42.5 Ω) ([differential pairs](https://docs.quilter.ai/physics-constraints/differential-pairs.md), read).

## Method

- Placement and routing by a learned policy (ML heuristic rung; physics report).
- Impedance geometry from Simbeor, a commercial 2D quasi-static solver, since 2026-04-07 (checked).
- Power-net widths from IPC-2221 (checked). Defaults 200 mA below 3 V, 500 mA above 3 V.
- DC IR drop beta since 2026-08-31, "not yet a full power-integrity sign-off" (checked).
- Constraint detection from net names and topology ("Circuit Comprehension"; read).
- New router strategy "ALPHA" for boards under 400 pins, 2026-09-30 ([changelog](https://www.quilter.ai/changelog), read). No changelog entry after 2026-09-30 as of 2026-10-21.

## Guarantee type

| Output | Rung |
|---|---|
| Placement and routing | ML heuristic |
| PRCs | Rule check against example tolerances the user may change |
| Impedance geometry | Physics simulation (2D quasi-static, < 6 GHz) |
| DC IR drop | Physics simulation, beta |
| "Detailed physics simulations" in the FAQ | Marketing. No documented PRC supports it (physics report) |

Quilter says users stay responsible for signal simulation, design review and DRC (checked).

## Inputs and outputs

- **In:** Altium, Cadence, Siemens (Xpedition native zip since 2026-09-30) and KiCad board files ([prepare your input](https://docs.quilter.ai/using-quilter/prepare-your-input-board-file.md), read). The board must have exactly one closed outline. Quilter never creates or resizes it. Pre-placed parts inside the outline stay where they are. Pre-placing connectors is recommended, not required.
- **Out:** candidates "always returned in their original native file format" ([downloading candidates](https://docs.quilter.ai/downloading-candidates.md), read).
- **Layers:** 2 to 10+, "no fixed upper limit" ([FAQ](https://docs.quilter.ai/about-quilter/faq.md), checked).

## Limits

- 5,000 pins, 48 V, 10 A, < 6 GHz (checked).
- Avoids diff pairs on 2-layer stackups; no coplanar waveguide (read, differential pairs page). This confirms one of the "unverified" limits in the physics report.
- Through-vias only; blind and buried "in development" (**summary**: search snippet of a Quilter blog post; the sentence was not read on the page).
- Length matching exists as a check (Length Mismatch PRC), not as a general routing mode (read).
- No creepage or mains clearance check. The 48 V limit puts mains boards out of scope (checked).
- No pinout check: it uses the user's footprints as given (inference).

## Price

Per project, by the number of pins to route. Pre-routed pins are not charged. A BOM change within 10% stays the same project. Unlimited iterations. No dollar figure is published ([pricing](https://www.quilter.ai/pricing), read). The free tier is non-commercial and trains on uploads (physics report). Its limits are not stated.

## Automation

No API, CLI or scripting path in the docs (read; rests on absence). Upload and download happen in the web UI. Circuit OS cannot call Quilter from a pipeline.

## Their level, as numbers

| Metric | Quilter's level | Label |
|---|---|---|
| Routing completion | Goal 100%; an unfinished route is a failure. 98% on Speedrun (843 parts) | checked |
| DRC errors in a shown candidate | 0 (candidates with DRC errors are not surfaced) | checked |
| Board area | 1.0 × the given outline (never resized) | read |
| Vias on a decoupling/crystal path | 0-1 | checked |
| Decoupling pin distance | ≤ 10 mm (example range) | checked |
| Decoupling path length | ≤ 10 mm (example range) | checked |
| Power trace | IPC-2221 width; ≤ 10% of length above a 20 °C rise | checked |
| Mains clearance | none | checked |
| Time | 27 h + 38.5 h cleanup for 843 parts; no small-board figure | checked |

## How Circuit OS matches or beats it

| Area | Today | To match | To beat |
|---|---|---|---|
| Routing completion | DHT22 board 12/12 routed (status.md). IR_005 routes RS485_A into RS485_B (F-0002) | 100% with 0 shorts on every tier A reference | — |
| DRC | 7 geometric rules, own kernel | kicad-cli DRC as second engine, 0 errors (S6 stages 3-4) | Refuse to show a board with any error, as Quilter does, and say so |
| Outline | Circuit OS draws its own outline | Accept a given outline and keep pre-placed connectors fixed | — |
| PRCs | None in code | Physics report build item 2: the eight PRCs on the Board IR | Constraints come from the IR, which **knows** which cap decouples which pin. Quilter guesses from names and misses crystals with series resistors |
| Decoupling distance | Not measured | ≤ 10 mm | Plan target ≤ 6 mm, and ≤ reference + 2 mm |
| Power width | Not checked at layout level | IPC width for the current | Width from the current the z3 proofs compute, not a 200/500 mA default (build item 3) |
| DC IR drop | None | Build item 4 | Two engines, disagreement refuses |
| AC PDN | None | Quilter has none | Build item 5 goes past it |
| Mains | Decision 12: 2.5 mm (basic) | Quilter is out of scope above 48 V | Creepage derived from voltage and insulation class (≥ 5.0 mm reinforced at 250 V) — neither Quilter nor Altium does this (build item 3, F-0004) |
| Pinout | verify.py checks pins against the KiCad library | Quilter does not check | Already ahead, rung "exact" against the library |
| Impedance | None | Closed-form microstrip at least | — (Quilter ahead) |
| Scale | 2 layers, ≤ 40 parts | Out of reach this program | — (Quilter ahead) |
| Automation | Full HTTP API | Quilter has none | Already ahead |

Rung note: every "match" above means "matches Quilter's published rule check on these metrics". None of it proves a board works.

## Open questions

- Which solver runs the DC IR beta, and how accurate is it?
- The through-vias-only sentence needs a direct read of the blog page.
- Free-tier limits (pins, projects) are not published.
- Whether the ALPHA router (< 400 pins) changes completion on tier A boards. Only a free-tier run would show it, within the non-commercial terms, and uploads train their model — so do not upload third-party corpus designs.
