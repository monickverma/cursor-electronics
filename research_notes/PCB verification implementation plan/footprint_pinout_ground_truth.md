# Independent ground truth for PCB footprints and per-part pinouts (free/open sources, 2026)

Evidence labels used throughout:
- **[LOCAL]** = measured in this session on the locally installed KiCad 10.0.1 libraries (`C:\Program Files\KiCad\10.0\share\kicad\{symbols,footprints}`) with a throwaway s-expression parser. Primary evidence, reproducible.
- **[PRIMARY]** = read in the owner's own page/document this session.
- **[SECONDARY]** = search-result summary, vendor blog, or forum; not read in full or not the owner's document.
- **[ANECDOTAL]** = individual forum reports.

---

## 1. KiCad official libraries as ground truth (licence, format, parsing, KLC, per-part pin maps)

### Takeaway
The KiCad symbol library is the best free per-PART pinout oracle available: 22,728 symbols, 79% carrying a default footprint, each concrete part carrying pin number -> pin name plus a datasheet URL; the footprint library (15,430 footprints, 78% script-generated) is a good per-PACKAGE geometry reference. The licence (CC-BY-SA 4.0 + design exception) is fine for *checking against* and for generated designs, but redistributing the library data itself (e.g. serving a cached copy/derived table to users) triggers share-alike and attribution.

### Cited Findings

**Licence**
- [PRIMARY] "The KiCad libraries are licensed under the Creative Commons CC-BY-SA 4.0 License, with the following exception: To the extent that the creation of electronic designs that use 'Licensed Material' can be considered to be 'Adapted Material', then the copyright holder waives article 3 of the license with respect to these designs and any generated files which use data provided as part of the 'Licensed Material'." — [KiCad library licence](https://www.kicad.org/libraries/license/)
- [PRIMARY] The same page states KiCad "does not wish to exert any control over designs produced using the library data"; no attribution or disclosure is required inside a design. But the exception does NOT apply "if you wish to redistribute the KiCad libraries, or parts thereof (including in modified form) as a collection" — a redistributed collection must stay under the same licence and keep attribution/licence documents. — [KiCad library licence](https://www.kicad.org/libraries/license/)

**Size and format [LOCAL]** (KiCad 10.0.1 install; upstream repos are [kicad-symbols](https://gitlab.com/kicad/libraries/kicad-symbols) and [kicad-footprints](https://gitlab.com/kicad/libraries/kicad-footprints))
- 222 `.kicad_sym` symbol libraries, 22,728 symbols, 18,003 (79.2%) with a non-empty default `Footprint` property; 234 MB on disk. — [kicad-symbols](https://gitlab.com/kicad/libraries/kicad-symbols)
- 155 `.pretty` footprint libraries, 15,430 `.kicad_mod` files, 197 MB on disk; 12,012 (77.8%) carry `(generator "kicad-footprint-generator")`. The rest are hand-drawn (`(generator "pcbnew")`). — [kicad-footprints](https://gitlab.com/kicad/libraries/kicad-footprints)
- Footprints relevant to Circuit OS that are **script-generated**: `Package_TO_SOT_SMD:SOT-23` (descr "SOT, 3 Pin (JEDEC TO-236 Var AB ...)", property `KiLib_Generator = package/gullwing`), `Resistor_SMD:R_0603_1608Metric` (descr "... IPC-7351 nominal, (Body size source: IPC-SM-782 page 72 ...)"), `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` (descr "SOIC, 8 Pin (JEDEC MS-012AA, <Analog Devices package PDF>)"). **Hand-drawn**: `Package_TO_SOT_THT:TO-92_Inline` (descr cites "NXP sot054_po.pdf"), `Diode_SMD:D_SOD-123` (descr is just "SOD-123" — no source cited), `Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C` (cites sanyourelay SRD.pdf), `Sensor:Aosong_DHT11_5.5x12.0_P2.54mm` (cites DHT11.pdf). — [kicad-footprints](https://gitlab.com/kicad/libraries/kicad-footprints)
- Reference numbers for spot checks: KiCad `SOT-23` pads = 1 at (-0.9375, -0.95), 2 at (-0.9375, +0.95), 3 at (+0.9375, 0), each 1.475 x 0.6 mm roundrect; `R_0603_1608Metric` pads at x = +/-0.825, 0.8 x 0.95 mm. (KiCad Y axis points down, so pad 1 is top-left.) — [kicad-footprints](https://gitlab.com/kicad/libraries/kicad-footprints)
- File format is s-expression; a symbol is `(symbol "NAME" (extends "PARENT")? (property "Footprint" "Lib:Name") (property "Datasheet" "url") ... (symbol "NAME_1_1" (pin <etype> <shape> ... (name "B") (number "1"))))`. Derived symbols (`extends`) inherit pins from the parent, so a parser MUST resolve the `extends` chain (it can be 2 deep: `MAX485E -> MAX481E -> LTC2850xS8`). — [kicad-symbols](https://gitlab.com/kicad/libraries/kicad-symbols)
- `kicad-cli` 10.0.1 ships with the install; `kicad-cli fp` offers only `export` (SVG) and `upgrade` — there is no CLI footprint-compare or footprint-DRC command, so comparison must be done in own code. A bundled Python 3.11 (`bin/python.exe`, `_kipython.dll`) is present. — [KiCad](https://www.kicad.org/)

**Per-part pin maps actually present [LOCAL]** — [kicad-symbols](https://gitlab.com/kicad/libraries/kicad-symbols)

| Symbol | Pins (number=name) | Default footprint | Datasheet field |
|---|---|---|---|
| Transistor_BJT:MMBT2222A | 1=B 2=E 3=C | Package_TO_SOT_SMD:SOT-23 | Nexperia MMBT2222A.pdf |
| Transistor_BJT:MMBT3904 / BC847 / SS8050 | 1=B 2=E 3=C | SOT-23 | onsemi / Infineon / Secos |
| Transistor_BJT:2N3904, 2N3906, PN2222A, S8050 | 1=E 2=B 3=C | TO-92_Inline | onsemi / UTC |
| Transistor_BJT:BC547, BC337 | 1=C 2=B 3=E | TO-92_Inline | onsemi / Diotec |
| Transistor_FET:2N7002, BSS138, AO3400A | 1=G 2=S 3=D | SOT-23 | onsemi / AOS |
| Transistor_FET:AO3401A, BSS84, IRLML6402 | 1=G 2=S 3=D | SOT-23 | AOS / Nexperia / Infineon |
| Transistor_FET:2N7000 | 1=S 2=G 3=D | TO-92_Inline | Vishay |
| Transistor_FET:BS170 | 1=D 2=G 3=S | TO-92_Inline | onsemi |
| Transistor_FET:IRF540N | 1=G 2=D 3=S | TO-220-3_Vertical | IR |
| Regulator_Linear:AMS1117-3.3, LM1117MP-3.3 | 1=GND 2=VO 3=VI | SOT-223-3_TabPin2 | AMS / TI |
| Regulator_Linear:LM7805_TO220 | 1=VI 2=GND 3=VO | TO-220-3_Vertical | onsemi |
| Regulator_Linear:LM317_TO-220 | 1=ADJ 2=VO 3=VI | TO-220-3_Vertical | TI |
| Regulator_Linear:L78L05_TO92, LM78L05_TO92, LP2950-3.3_TO92 | 1=VO 2=GND 3=VI | TO-92_Inline | ST / onsemi / TI |
| Regulator_Linear:MCP1700x-330xxTO | 1=GND 2=VI 3=VO | TO-92_Inline | Microchip 20001826D |
| Regulator_Linear:MCP1700x-330xxTT, XC6206PxxxMR | 1=GND 2=VO 3=VI | SOT-23 / SOT-23-3 | Microchip / Torex |
| Regulator_Linear:AP2112K-3.3 | 1=VIN 2=GND 3=EN 4=NC 5=VOUT | SOT-23-5 | Diodes |
| Timer:NE555D / NE555P | 1=GND 2=TRIG 3=OUT 4=~RST 5=CONT 6=THRES 7=DISCH 8=VCC | SOIC-8 / DIP-8_W7.62mm | TI ne555.pdf |
| Interface_UART:MAX485E | 1=RO 2=~RE 3=DE 4=DI 5=GND 6=A 7=B 8=VCC | **empty** | Maxim |
| Amplifier_Operational:LM358 | 1=(blank) 2=- 3=+ 4=V- 5=+ 6=- 7=(blank) 8=V+ | **empty** | TI lm2904-n.pdf |
| MCU_Microchip_ATmega:ATmega328P-P | 28 pins, 1=~RESET/PC6 ... 28=PC5 | Package_DIP:DIP-28_W7.62mm | Microchip |
| MCU_Microchip_ATmega:ATmega328P-A | 32 pins, 1=PD3 ... 32=PD2 | Package_QFP:TQFP-32_7x7mm_P0.8mm | Microchip |
| Sensor:DHT11 | 1=VDD 2=DATA 3=NC 4=GND | Sensor:Aosong_DHT11_5.5x12.0_P2.54mm | Aosong |
| Relay:SANYOU_SRD_Form_C | 5 pins, **all names blank** | Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C | Sanyou |
| Diode:1N4148W, 1N4007 | 1=K 2=A | D_SOD-123 / D_DO-41_SOD81_P10.16mm_Horizontal | Vishay |
| Diode:BAT54S | 1=A 2=K 3=COM | SOT-23 | Diodes |
| Diode:BAT54A, BAT54C | 3 pins, **all names blank** | SOT-23 | Diodes |

- Library-level coverage [LOCAL]: Transistor_BJT 391 symbols (242 with footprint), Transistor_FET 608 (583), Regulator_Linear 1,625 (1,472), Timer 67 (59), Interface_UART 168 (134), Amplifier_Operational 425 (279), MCU_Microchip_ATmega 440 (440), Diode 763 (763), Relay 257 (210), Sensor 16 (15). — [kicad-symbols](https://gitlab.com/kicad/libraries/kicad-symbols)

**KLC rules** (klc.kicad.org returned HTTP 403 to direct fetch; the following is from search-result extracts of the KLC pages — [SECONDARY], re-read before quoting)
- F4.2: pin 1 in the upper-left, following IPC-7351; if it cannot be the most top-left pad it must be in the top-left quadrant; two-terminal and single-row footprints put pin 1 on the left; packages with pin 1 mid-side (some PLCC/QFN) align pin 1 to the top. — [KLC F4.2](https://klc.kicad.org/footprint/f4/f4.2)
- F4.1 is titled "Datasheet recommendations take priority" (title only retrieved). — [KLC index](https://klc.kicad.org/history)
- F5.3: courtyard on F.CrtYd, 0.05 mm line, 0.01 mm grid; default clearance 0.25 mm, 0.15 mm for parts smaller than 1.5 mm in any dimension, 0.5 mm for connectors (beyond mating clearance), canned capacitors and crystals, 1.0 mm for BGA. — [KLC F5.3](https://klc.kicad.org/footprint/f5/f5.3/)
- S5.1: symbols with a default footprint must link to a valid footprint file; S5.2: footprint filters must produce no false suggestions. — [KLC S1 / index](https://klc.kicad.org/symbol/s1)

**Python parsers**
- `kiutils` describes itself as a "Simple and SCM-friendly KiCad file parser based on Python dataclasses for KiCad 6.0 and up" and lists `.kicad_mod`, `.kicad_sym`, `.kicad_pcb`, `.kicad_sch` as supported; PyPI page found was 1.4.8; a `FlashPCB/kiutils` fork exists. — [kiutils on PyPI](https://pypi.org/project/kiutils/1.4.8), [FlashPCB/kiutils](https://github.com/FlashPCB/kiutils)
- `kicad-skip` targets "kicad 7+ s-expression schematic, netlist and PCB files" (not footprint/symbol library files); a third-party tracker reported its last push as 2024-05-26. — [kicad-skip on PyPI](https://pypi.org/project/kicad-skip)
- [LOCAL] A ~25-line hand-written s-expression tokenizer parsed all 222 KiCad 10 symbol libraries (file `version 20260206` format) without error in this session; no third-party library is required for read-only extraction of pins/pads. — [kicad-symbols](https://gitlab.com/kicad/libraries/kicad-symbols)

### Inferences
- Trust level as a **pinout oracle: medium-high, independent of Circuit OS code** — human-contributed, KLC-reviewed, each part linked to a manufacturer datasheet URL; but it is itself a transcription (not the datasheet), with no published error rate. Treat it as one witness in a 2-of-N scheme, not as final truth; the D7 datasheet record remains the top rung.
- Known oracle holes, all observed [LOCAL]: (a) blank pin names (BAT54A/C, SRD relay, op-amp outputs) — these symbols encode function graphically, so a name-based check cannot work and needs an electrical-type or hand-authored map; (b) empty default footprint for multi-package parts (MAX485E, LM358) — only the pin numbering is usable, package must come from the MPN suffix; (c) pin-name vocabulary is not normalised (VI/VIN/IN/V_{IN}, VO/VOUT/OUT, ~{RST}) so a synonym table is required before comparing with netlist labels like "VCC"/"DATA".
- Trust level as a **geometry oracle: medium-high for generator-produced footprints** (cite JEDEC outline + IPC density in `descr`), **medium for hand-drawn ones** (TO-92_Inline, D_SOD-123, SRD relay, DHT11 — exactly the hobby parts Circuit OS uses most). D_SOD-123 cites no source at all.
- AGPL compatibility: using the libraries as a server-side comparison reference and emitting pass/fail verdicts is "use in a design / generated files" territory and is unproblematic. Storing a parsed copy in PostgreSQL is internal use. If Circuit OS **ships or serves** the parsed table (or a modified subset) to users, that is redistribution "as a collection": keep that dataset under CC-BY-SA 4.0 with attribution, as a separately licensed data artefact alongside the AGPL code. CC-BY-SA 4.0 data and AGPL code can coexist as separate works (data file vs program); do not paste library content into AGPL source files. This is a licence reading, not legal advice.
- Cheapest robust design: read the libraries from the user's/server's KiCad install or a pinned git checkout at runtime (record commit hash + file SHA-256 in the D7-style provenance record) rather than vendoring a transformed copy.

### Gaps
- Could not fetch klc.kicad.org directly (403); exact wording of F4.1, F5.x fab-layer rules, S4.x pin-numbering rules and the pad-numbering rule number were not verified. Could not confirm how library merge requests are reviewed (CI `check_symbol.py`/`check_footprint.py` in kicad-library-utils is known practice but not verified this session).
- Could not retrieve the kicad-footprint-generator IPC parameter YAML (`ipc_definitions.yaml`) — the old GitLab path 404s; the repo layout has changed (footprints now carry `KiLib_Generator` e.g. `package/gullwing`, `SMD_2terminal_chip...`). The actual toe/heel/side numbers KiCad uses are therefore unverified here.
- No published error rate for KiCad library pinouts was found. Maintenance status of kiutils/kicad-skip against the KiCad 10 file format is unconfirmed; test before depending on them.
- Did not check whether a DHT22/AM2302 footprint or symbol exists in the KiCad 10 library (only DHT11 was confirmed).

---

## 2. IPC-7351B/C land-pattern calculation (formulas, tables, implementations, status of 7351C / 7352)

### Takeaway
The three land-pattern equations are public and simple; the per-family fillet tables are the paywalled part, and the only table values retrieved this session come from a 2004 IPC presentation (pre-7351B values) whose text extraction was column-scrambled. IPC-7351C was abandoned; IPC-7352 (2023) is the current guideline and adds through-hole.

### Cited Findings
- [PRIMARY] Equations as given by IPC's Dieter Bergman ("Principles of Land Pattern Design", PDF created 2004-10-18): `Zmax = Lmin + 2*JT + sqrt(CL^2 + F^2 + P^2)`; `Gmin = Smax - 2*JH - sqrt(CS^2 + F^2 + P^2)`; `Xmax = Wmin + 2*JS + sqrt(CW^2 + F^2 + P^2)`. Z = overall land-pattern length, G = gap between lands, X = land width; L = overall component length, S = distance between terminations (heel-to-heel), W = lead/termination width; JT/JH/JS = toe/heel/side land protrusion; C = component tolerance (CL = Lmax-Lmin etc.), F = board fabrication tolerance, P = placement tolerance (diameter of true position). (The slide text prints CL in all three equations; the constituent list on the next slide defines CS and CW.) — [IPC presentation, Bergman 2004](https://www.electronics.org/system/files/technical_resource/E31%26S01-3_Dieter.pdf)
- [PRIMARY] Heel-to-heel S is usually not given by manufacturers and must be derived: `Smax = Lmax - 2*Tmin`, and the tolerance on S is RSS-accumulated: `S_tol = sqrt(Ltol^2 + 2*Ttol^2)` with Ltol = Lmax-Lmin, Ttol = Tmax-Tmin. — [IPC presentation, Bergman 2004](https://www.electronics.org/system/files/technical_resource/E31%26S01-3_Dieter.pdf)
- [PRIMARY] JITX's Python land-pattern library documents the same three equations (attributed to IPC-7351B) and states its implementation uses `F = P = 0`; density levels A = maximum land protrusion, B = median/nominal, C = minimum. — [JITX `jitxlib.landpatterns.ipc`](https://docs.jitx.com/en/latest/jitxlib-standard/jitxlib.landpatterns.ipc.html)
- [PRIMARY, with caveat] Fillet tables in the 2004 presentation (Level 1/2/3 = max/median/min = A/B/C), units mm. `pdftotext` shifted the median column down one row; values below are de-shifted and agree with an independent search-engine reading for the gull-wing table. **These are 2004 (IPC-7351 first edition / IEC 61188-5-1 era) values, not confirmed IPC-7351B values.** — [IPC presentation, Bergman 2004](https://www.electronics.org/system/files/technical_resource/E31%26S01-3_Dieter.pdf)

| Family | Toe A/B/C | Heel A/B/C | Side A/B/C | Courtyard A/B/C |
|---|---|---|---|---|
| Gull-wing / flat ribbon, pitch > 0.625 | 0.8 / 0.5 / 0.2 | 0.5 / 0.35 / 0.2 | 0.05 / 0.05 / 0.03 | 0.5 / 0.25 / 0.05 |
| Gull-wing, pitch <= 0.625 | 0.8 / 0.5 / 0.2 | 0.5 / 0.2 / 0.2 (as extracted; uncertain) | 0.0 / 0.0 / 0.0 (uncertain) | 0.5 / 0.25 / 0.05 |
| J-lead (toe/heel roles reversed) | 0.2 / 0.2 / 0.2 | 0.8 / 0.6 / 0.4 | 0.1 / 0.05 / 0.0 | 1.5 / 0.8 / 0.2 |
| Rectangular/square-end chip (R, C) | 0.6 / 0.4 / 0.2 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.5 / 0.25 / 0.05 |
| MELF | 1.0 / 0.4 / 0.2 (uncertain) | 0.2 / 0.1 / 0.0 (uncertain) | 0.2 / 0.1 / 0.0 (uncertain) | 0.5 / 0.25 / 0.05 (uncertain) |

- [PRIMARY] Rounding in that presentation: Level A and B round to nearest 0.5 (some tables 0.05 for B), Level C to nearest 0.05. "Worst case analysis considers component basic dimensions at maximum and the land at its minimum." Courtyard = component/pattern maximum boundary + courtyard excess; a further "manufacturing allowance" is added on top by the assembler. — [IPC presentation, Bergman 2004](https://www.electronics.org/system/files/technical_resource/E31%26S01-3_Dieter.pdf)
- [PRIMARY] IPC's own table of contents exists for IPC-7352 "Generic Guideline for Land Pattern Design", copyright 2023. — [IPC-7352 TOC](https://www.ipc.org/TOC/IPC-7352-TOC.pdf)
- [SECONDARY] PCB Libraries forum admin (Tom Hausherr's company): the committee scrapped six years of IPC-7351C work, reverted to 7351B and enhanced it with through-hole as IPC-7352; 7352 "adds through-hole guidelines, updates surface mount guidelines and completely replaces IPC-7351". The 7351C naming convention (pin count at the front) was not adopted; 7352 keeps the 7351B placement (pin count at the end) and extends names with thermal-pad size etc. PCB Libraries kept the abandoned 7351C convention as its own proprietary naming. — [PCB Libraries forum, "new release of IPC-7351C"](https://www.pcblibraries.com/forum/do-we-have-a-new-release-of-ipc7351c_topic3150_page4.html), [naming convention thread](https://www.pcblibraries.com/forum/naming-convention_topic3182_page2.html)
- [SECONDARY] A 2026 vendor blog citing IPC's revision table reports IPC-7351B (June 2010) as no longer maintained. — [bestpcbs blog](https://www.bestpcbs.com/blog/2026/09/ipc-7351/)
- [SECONDARY/opinion] A PCB Libraries forum poster argues IPC-7351 is a guideline, and that IPC J-STD-001 solder-joint acceptance takes priority for fillet goals. — [PCB Libraries forum TID 785](https://www.pcblibraries.com/FORUM/printer_friendly_posts.asp?TID=785)
- [PRIMARY] A manufacturer application note (Micron TN-12-25) works a 1206 chip example with the same equations using fillet goals toe 0.35 / heel 0.00 / side 0.00 — i.e. real-world notes pick their own goals. — [Micron TN-12-25](https://web.pa.msu.edu/people/edmunds/Disco_Kraken/Components/Flash_Memory/micron_tn1225_land_pad_design.pdf)
- [SECONDARY] KiCad's own chip footprints follow a contributor decision: e.g. 0603 toe taken as 0.35 mm ("Toe is defined in the table as 0.35mm for 0603"), and nominal terminal length is "given by the manufacturer", not by IPC. — [KiCad forum, IPC compliance thread](https://forum.kicad.info/t/why-are-the-kicad-library-conventions-non-ipc-compliant/3678?page=4)
- [LOCAL] KiCad's generated `R_0603_1608Metric` self-describes as "IPC-7351 nominal" with body size from IPC-SM-782 (a freely circulated older standard), pads 0.8 x 0.95 at +/-0.825. — [kicad-footprints](https://gitlab.com/kicad/libraries/kicad-footprints)

### Inferences
- A lead-coverage verifier does NOT need the paywalled tables to be sound. Invert the equations: given datasheet package dimensions (Lmin/Lmax, Tmin/Tmax, Wmin/Wmax, pitch) compute the *achieved* fillets of the board's footprint: `Jt = (Z - Lmax)/2` (worst case), `Jh = (Smin - G)/2`, `Js = (X - Wmax)/2`, and check them against thresholds held as *named, cited parameters* (D7-style records). Any free table (Bergman 2004, KiCad generator YAML, manufacturer app notes) can supply the thresholds, with its trust level recorded.
- Because hobby boards are hand- or reflow-soldered at Level A/B, the practical pass band is wide; the checks that actually catch respins are: pad count, pitch (must match to ~0.05 mm), row span Z/G bracketing the lead span (pad must cover the lead foot: `G <= Smin` and `Z >= Lmax`), and pin-1 position. Fillet magnitude is a warning-level check.
- Using F = P = 0 (as JITX does) is a defensible simplification for a checker; state it.
- IPC documents (7351B, 7352) are paywalled; equations are reproduced widely, the complete per-family tables and the naming-convention document are the paywalled content. Cite IPC-7352 as current when naming a standard; cite the actual free source for every number used.

### Gaps
- Exact IPC-7351B table values were NOT obtained from a primary source. Commonly quoted 7351B numbers (gull-wing > 0.625 mm: toe 0.55/0.35/0.15, heel 0.45/0.35/0.25, side 0.05/0.03/0.01, courtyard 0.5/0.25/0.1; chip >= 0603: toe 0.55/0.35/0.15, heel ~0, side 0.05/0/-0.05; chip < 0603: toe 0.3/0.2/0.1, courtyard 0.2/0.15/0.1) are from the researcher's memory only, uncited — verify against KiCad's generator YAML or a 7351B copy before use.
- IPC-7352's exact publication month and whether it formally "supersedes" 7351B: IPC's TOC "Supersedes" field reportedly names only an earlier IPC-7352 (June 2010); the supersession chain is unconfirmed.
- Free implementations not verified this session: QEDA (JavaScript, believed stale), LibrePCB generators, pcblibraries.com Footprint Expert free tier, EasyEDA's footprint wizard. Only JITX's (proprietary-licensed, licence not stated on the docs page) and KiCad's generator were touched. No standalone maintained "ipc-7351" PyPI package was found.
- Rounding rules and courtyard excess for 7351B/7352 specifically were not verified.

---

## 3. JEDEC / manufacturer outlines and why pin maps must be per-PART

### Takeaway
Measured on the KiCad library, a single package has dozens of distinct pin assignments (SOT-23: 39; TO-92: 30; SOT-223: 15; SOIC-8: 298), so a per-package `PINMAPS` dict is structurally unsound; Circuit OS's SOT-23 assumption (1=B/G, 2=E/S, 3=C/D) matches only 113 of 334 SOT-23 parts in the KiCad library.

### Cited Findings
All counts below are [LOCAL], grouping every KiCad symbol by default footprint and comparing pin number -> name maps. — [kicad-symbols](https://gitlab.com/kicad/libraries/kicad-symbols)

- **`Package_TO_SOT_SMD:SOT-23`: 334 symbols, 39 distinct pin maps.** Top: 84x `1=G 2=S 3=D` (2N7002 etc.); 61x `1=GND 2=VO 3=VI` (AP2127N, MCP1700 SOT-23); 29x `1=B 2=E 3=C` (BC817 etc.); 28x `1=VI 2=VO 3=GND` (AP7381); 22x `1=IN 2=OUT 3=GND` (MAX6001 references); 20x `1=VO 2=GND 3=VI` (APE8865NL); 10x `1=A 2=NC 3=K` (BAS19, BAR43); 9x `1=D 2=S 3=G` (BSR56/57/58 JFETs); 7x `1=K 2=A 3=NC` (LM4040DBZ); 6x `1=VCC 2=OUT 3=GND` (DRV5033 hall); 6x `1=VDD 2=VOUT 3=GND` (MCP9700); 5x `1=K 2=K 3=A`; 4x `1=VO 2=VI 3=GND` (LM3480).
- Three-terminal SOT-23 regulators alone show at least four different orders: GND-VO-VI (MCP1700, XC6206, AP2127N), VI-VO-GND (AP7381), VO-GND-VI (APE8865NL), VO-VI-GND (LM3480).
- **`Package_TO_SOT_THT:TO-92_Inline`: 151 symbols, 30 distinct pin maps.** BJTs: 25x `1=C 2=B 3=E` (BC237/BC547 family), 8x `1=E 2=B 3=C` (2N3904/2N3906/PN2222A/S8050), 4x `1=E 2=C 3=B` (2SA1015, 2SC1815 — Japanese ECB). FETs: 2N7000 `1=S 2=G 3=D`, BS170 `1=D 2=G 3=S`, BF244 `1=D 2=G 3=S`, BF245 `1=G 2=S 3=D`. Regulators: 26x `1=VO 2=GND 3=VI` (78L05, LP2950), 14x `1=GND 2=VI 3=VO` (79L05, MCP1700 TO-92). Sensors: DS18B20 `1=GND 2=DQ 3=VDD`; DRV5033 `1=VCC 2=GND 3=OUT`.
- So MCP1700 (TO-92: GND, VIN, VOUT) vs LP2950 / 78L05 (TO-92: VOUT, GND, VIN) is a real, library-confirmed swap hazard: dropping an MCP1700 into a 78L05 footprint reverses the regulator.
- **`Package_TO_SOT_SMD:SOT-223-3_TabPin2`: 107 symbols, 15 distinct pin maps.** 30x `1=GND 2=VO 3=VI` (AMS1117-x.x, LM1117MP, AP1117) and 6x `1=ADJ 2=VO 3=VI`; versus 24x `1=VI 2=GND 3=VO` (AP7361C), 14x `1=IN 2=GND 3=OUT` (AZ1117CH2), 7x `1=OUT 2=GND 3=IN` (MCP1804), 2x `1=OUT 2=IN 3=GND` (LT1175), plus FETs `1=G 2=D 3=S` and BJTs `1=B 2=C 3=E`.
- **AMS1117 and LM1117 SOT-223 have the SAME pin map in the KiCad library (1=GND/ADJ, 2=VO, 3=VI)**; the SOT-223 "1117-style" trap is instead AZ1117**C**H2 / AP7361C / LM78xx-style parts (1=IN, 2=GND, 3=OUT). The brief's "AMS1117 vs LM1117" example is not supported by this source.
- **`Package_TO_SOT_THT:TO-220-3_Vertical`: 159 symbols, 16 distinct pin maps.** 29x `1=VI 2=GND 3=VO` (78xx-style), 16x `1=GND 2=VI 3=VO` (79xx), 8x `1=GND 2=VO 3=VI` (LD1117V), 4x `1=ADJ 2=VO 3=VI` (LM317), 3x `1=ADJ 2=VI 3=VO` (LM337); 31x BJT `1=B 2=C 3=E`; 16x FET `1=G 2=D 3=S`; 29x triac `1=A1 2=A2 3=G`.
- **`Package_TO_SOT_SMD:SOT-23-5`: 645 symbols, 109 distinct pin maps.** Even single op-amps come in two mirror pinouts: 39x `1=OUT 2=V- 3=+ 4=- 5=V+` vs 9x `1=OUT 2=V+ 3=+ 4=- 5=V-` (the "R" reverse-pinout variants MCP6001R, MCP601R, MCP6401RT).
- **`Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`: 883 symbols, 298 distinct pin maps.**
- JEDEC outline identifiers are embedded in KiCad generated footprint descriptions (SOT-23 = "JEDEC TO-236 Var AB", SOIC-8 = "JEDEC MS-012AA") with links to the JEDEC document search / a manufacturer package PDF, giving a traceable package-outline reference per footprint. — [kicad-footprints](https://gitlab.com/kicad/libraries/kicad-footprints)
- [ANECDOTAL] EasyEDA forum: an IRF3205S library part had drain and source interchanged, discovered only after fabrication and assembly ("after a month's wait ... the board was worthless"). — [EasyEDA forum](https://easyeda.com/forum/topic/Wrong-pin-maping-to-footprint-for-MOSFET-irf3205s-310bcca41bf14898816a3dd13da3e81d)

### Inferences
- The pin map must be keyed by **orderable part number including package suffix** (MCP1700-3302E/**TO** vs /**TT**; LM1117**MP** vs **T**; MCP6001 vs MCP6001**R**), not by package and not even by base part name.
- SOIC-8 falling back to "first free pad" is the highest-risk path in the current code: 298 distinct maps means essentially every 8-pin IC is its own case. That fallback should be a hard verification failure, not a default.
- The project's SOT-23 map is correct for the *majority transistor case* (113/334) and wrong for every regulator, reference, diode, JFET and sensor in that package — consistent with the SOT-23 bug that already occurred.
- A robust lookup order: exact MPN in KiCad symbol lib -> KiCad symbol with wildcard name (`MCP1700x-330xxTT`, `XC6206PxxxMR` — KiCad uses `x` wildcards, so matching needs a pattern matcher) -> second source -> D7 datasheet record. Refuse to route if nothing resolves.
- Same-manufacturer same-part different-vendor swaps (e.g. second-source TO-92 BJTs with different lead orders) are not captured by KiCad's single symbol per name; the datasheet URL in the symbol identifies which vendor's pinout was transcribed, and should be surfaced.

### Gaps
- JEDEC access terms (free registration for MO/MS/TO outline PDFs) were not verified this session. Manufacturer package-outline/land-pattern PDFs (TI, Nexperia, onsemi, Diodes, ST) were not individually fetched; only their URLs inside KiCad symbols were observed.
- No "2N2222" (TO-18) symbol was returned by the query, so the 2N2222-vs-PN2222 comparison was not checked. AO3401 non-A, S8050 vendor variants, and BC547 vendor variants with alternate lead orders were not checked.
- No primary datasheet was opened to confirm any KiCad pin map; the tables above show what KiCad says, not what the silicon vendors say.

---

## 4. Machine-readable per-part pinout/footprint sources (terms, quality)

### Takeaway
No commercial/distributor source found is cleanly usable as cached, redistributable ground truth in an AGPL SaaS: SnapMagic files are CC-BY-SA with tight redistribution limits, EasyEDA/LCSC data is ToS-bound and partly user-contributed with documented wrong pinouts, and Nexar/Mouser terms were not retrievable. KiCad's library remains the only source with a clear open licence.

### Cited Findings
- **SnapMagic (SnapEDA)** [SECONDARY, from its own help/FAQ pages via search]: individual symbols/footprints/3D models are CC BY-SA 4.0 with a "Design Exception 1.0" allowing boards built with them to be conveyed under your own terms without attribution; public sharing of the files requires attribution; the site says you cannot use the search website to share the content on the internet or within an EDA tool; an older staff answer limited standalone library redistribution to "under 10 SnapEDA library files" without permission. API access is under a commercial Master Services Agreement (last revised 2025-04-03). — [SnapMagic licence article](https://support.snapmagic.com/en/articles/2957814-what-is-the-license-for-symbols-and-footprints), [SnapEDA licensing Q&A](https://www.snapeda.com/questions/question/clarification-on-licensing), [SnapMagic MSA](https://www.snapmagic.com/msa), [Design Exception 1.0 text](https://scancode-licensedb.aboutcode.org/snapeda-design-exception-1.0.LICENSE)
- **SnapMagic quality** [ANECDOTAL, vendor-acknowledged]: SnapEDA staff state that where no model exists it "sometimes links footprints to parts based on package details" automatically, and that such a footprint "had not been checked against the datasheet"; users report wrong pitch/pad size and a pin assignment "completely wrong" versus the datasheet. — [SnapEDA Q&A "wrong footprint"](https://www.snapeda.com/questions/question/wrong-footprint-4/), [SnapEDA Q&A pitch mismatch](https://www.snapeda.com/questions/question/this-foot-print-is-not-correct/), [SnapEDA Q&A "who verified this package"](https://api.snapeda.com/questions/question/who-verified-this-package)
- **EasyEDA / LCSC / JLCPCB library** [SECONDARY]: `easyeda2kicad` converts LCSC/EasyEDA components (symbol, footprint, 3D) to KiCad libraries by LCSC part number; its README forbids "any use that is outside the EasyEDA Terms of Use". — [easyeda2kicad on PyPI](https://pypi.org/project/easyeda2kicad/0.6.1)
- **EasyEDA quality** [ANECDOTAL]: forum staff say responsibility depends on whether a part is from the System, LCSC or JLCPCB libraries and that the companies "are not responsible for user-contributed content". Reported errors: IRF3205S drain/source swapped (board scrapped); LCSC C91816 (LH05-10B05 AC-DC module) footprint pin order differing from the datasheet, which would have reversed VCC/GND (LCSC corrected it); LCSC C34677 RJ45 footprint spacing and symbol pins wrong (corrected); a 2x20 header symbol linked to a 46-pad footprint; a 1N914 with reversed cathode marking; and a thread titled "RELAY SL-SRD schematic and PCB pin orientations are WRONG" (the SRD relay family Circuit OS uses). — [EasyEDA forum IRF3205S](https://easyeda.com/forum/topic/Wrong-pin-maping-to-footprint-for-MOSFET-irf3205s-310bcca41bf14898816a3dd13da3e81d), [EasyEDA forum C91816](https://www.easyeda.com/forum/topic/Library-LCSC-C91816-Wrong-official-pinout-on-the-PCB-footprint-a8b7d34c57ff42bbaddcc0b8eb0e0c80), [EasyEDA forum C34677](https://easyeda.com/forum/topic/Incorrect-Footprint-for-C34677-HY951180A-5c52e1eec0fd42da90a1e077bcb7ee2d), [EasyEDA forum header mismatch](https://easyeda.com/forum/topic/Differences_between_Schematic_and_PCB_layout-I641ZljhD), [EasyEDA forum 1N914](https://easyeda.com/forum/topic/1N914-PCB-footprint-is-incorrect-for-the-first-selection-in-the-library-c856480e71b745e79c5d13b75568a7f9), [EasyEDA forum SRD relay](https://www.easyeda.com/forum/topic/RELAY-SL-SRD-schematic-and-PCB-pin-orientations-are-WRONG-f246680ca9f044a19ae35ff494763595)
- **Ultra Librarian** [SECONDARY]: operated by EMA Design Automation; downloads require accepting site T&Cs; a manufacturer-specific wrapper (Toshiba) restricts use to design work and prohibits incorporating the data into your products or systems. Digi-Key offers unlimited access to Ultra Librarian models via its site. — [Toshiba UL consent page](https://toshiba.semicon-storage.com/ap-en/semiconductor/product/agree-ul.html), [eeNews on Digi-Key/UL](https://www.eenewseurope.com/en/unlimited-access-to-ultra-librarian-eda-cad-models-at-digi-key/)
- **SamacSys / Component Search Engine** [SECONDARY]: operated by Supplyframe; governed by the site's Standard End User Terms; the Toshiba wrapper requires destroying the data on termination. — [Toshiba SamacSys consent page](https://toshiba.semicon-storage.com/us/semiconductor/product/agree-ss.html)
- **Nexar (Octopart) API** [SECONDARY]: terms are titled "Altium API License Terms of Use"; the licence is conditioned on payment of fees and compliance; Altium may change the terms by posting a new version. — [Nexar API legal](https://nexar.com/api/legal)
- **Mouser Search API** [SECONDARY]: API terms last modified 2013-03-11 (per search extract); prohibit use competitive with Mouser, combining Mouser content with third-party content, and omitting attribution. — [Mouser API terms](https://www.mouser.com/apiterms/)

### Inferences
- Mouser's "no combining with third-party content" clause (if still current) is directly hostile to a cross-source triangulation table; treat the existing Mouser key as usable for *resolving an MPN to a manufacturer datasheet URL and package string* (a pointer), not as a pinout source. Mouser/Digi-Key/Nexar parametric APIs generally expose package name, pin count and datasheet URL — not pin-number-to-function maps or pad geometry (inference from API scope; not verified this session).
- The CAD-model aggregators (SnapMagic, UL, SamacSys, EasyEDA) do hold per-part pin maps and footprints, but (a) their terms prevent building a redistributable cache, and (b) their quality is the *same class of unverified transcription* Circuit OS is trying to check, with vendor-acknowledged automatic package-based linking. They are useful only as a transient, per-request, non-stored **disagreement detector**, and only if each ToS permits automated access.
- Ranking for an AGPL SaaS: KiCad libs (open, cacheable, attribution + share-alike on redistribution) >> everything else. A second independent witness realistically has to be the datasheet itself (D7 record), not another aggregator.
- For modules and MCU boards (DHT22, relay modules, Arduino/ESP dev boards) no aggregator is reliable; hand-authored D7 records are required.

### Gaps
- Not retrieved: full Nexar terms (page rendered empty), full Mouser terms (timeout), EasyEDA/LCSC Terms of Use text, Ultra Librarian's own T&Cs, Component Search Engine's Standard End User Terms, Digi-Key API terms. Caching limits, free-tier quotas and commercial-use clauses for all of these are therefore UNVERIFIED — read each before any integration.
- Not researched this session (no findings): PartsBox, TraceParts, CADENAS, Wikidata, JLC2KiCad_lib, STM32CubeMX pin XML database, Zephyr/Linux devicetree pinctrl, Arduino `pins_arduino.h` variants, ESP-IDF `soc` pin headers. (From general knowledge only, unverified: the MCU sources are permissively/openly licensed and are the best machine-readable MCU pin-function data; licences of easyeda2kicad, JLC2KiCad_lib and kicad-jlcpcb-tools were not confirmed.)
- No source publishes a measured error rate for any library; all quality evidence is anecdotal.

---

## 5. Datasheet extraction as a source (LLM/VLM state of the art, 2024-2026)

### Takeaway
Published work treats footprint geometry extraction from datasheets as an unsolved perception problem for current multimodal models, and no retrieved paper reports a pinout-table accuracy figure; pipelines that do extract pin tables protect themselves with structural cross-checks (row count vs package pin count) rather than trusting the model.

### Cited Findings
- [PRIMARY, abstract only] Wang et al., "A Large Language Model Powered Integrated Circuit Footprint Geometry Understanding", arXiv:2508.03725 (submitted 2025-07-30): decomposes footprint understanding into (1) pin count, (2) pin centre coordinates, (3) pin dimensions; releases ICGeo8K with 8,608 labelled samples (4,138 hand-crafted + 4,470 synthetic); states that current large multimodal models "severely suffer from inaccurate geometric perception"; their LLM4-IC8K model outperforms state-of-the-art LMMs on the benchmark. No numeric accuracy is given on the abstract page. — [arXiv:2508.03725](https://arxiv.org/abs/2508.03725)
- [SECONDARY] PCBSchemaGen (arXiv:2602.00510): a layout-aware parser recovers (pin, name, description) tuples from the datasheet PDF, and "the parsed row count is compared against the package header" before an LLM assigns roles. — [arXiv:2602.00510](https://arxiv.org/pdf/2602.00510)
- [SECONDARY] D2S-FLOW (arXiv:2502.16540) extracts datasheet parameters for SPICE model generation; DocEDA (arXiv:2412.05301) uses LLM chain-of-thought to extract component parameters from documents. — [arXiv:2502.16540](https://arxiv.org/pdf/2502.16540), [arXiv:2412.05301](https://arxiv.org/abs/2412.05301?context=cs)
- [SECONDARY] An academic paper on a datasheet parameter extractor/verifier for PCB development reports a survey in which 61.5% of library errors came from footprint dimensions (sample and method not retrieved). — [IJEECS article](https://ijeecs.iaescore.com/index.php/IJEECS/article/view/26833)
- [SECONDARY] Community practice exists: a KiCad forum thread shares an LLM prompt to generate a symbol pin table from a datasheet; a `datasheet-cli` Rust crate and a "ds2sf" (datasheet to symbol/footprint) tool exist. — [KiCad forum thread](https://forum.kicad.info/t/llm-prompt-to-generate-symbol-pin-table-from-datasheet/71370), [datasheet-cli](https://docs.rs/crate/datasheet-cli/0.1.2), [ds2sf](https://wiki.adom.inc/kyle/ds2sf)

### Inferences
- Pin TABLES (text rows: number, name, type, description) are a far easier extraction target than package DRAWINGS (dimension letters referenced from a figure to a min/nom/max table). Use LLM extraction for the pin table; for geometry, extract only the dimension table (symbol -> min/nom/max) and let deterministic code apply the Section 2 equations, rather than asking a model for pad coordinates.
- Cheap structural validators that make extraction errors loud (all deterministic): pin numbers form the complete set 1..N for the package's N; no duplicate numbers; every netlist label resolves to exactly one extracted pin; exactly the expected count of power/ground pins; package name in the ordering code matches the table's column header (multi-package datasheets list several pinouts side by side — the commonest extraction failure); extracted pitch x (N/2 - 1) is consistent with body length.
- The existing D7 pattern (agent's page-cited evidence + human verification bound to record hash) is the right human-in-the-loop shape; the extension needed is a per-MPN "pinout record" and a per-package "outline dimension record", each with page citation, plus an automatic cross-check against the KiCad symbol so the human only reviews disagreements and KiCad-absent parts.
- Two extractions by the same model family from the same PDF are not independent witnesses; KiCad-library-vs-datasheet-extraction is a genuinely independent pair (different transcriber, different time, human-reviewed).

### Gaps
- No numeric error rates were retrieved for LLM/VLM pin-table or dimension-table extraction; the ICGeo8K paper body and PCBSchemaGen results were not read.
- Not researched: Docling, Marker, Unstructured, table-transformer, pdfplumber/camelot comparative accuracy on datasheets; commercial products (Flux Copilot, CELUS, Altium/Cadence AI part creation, SnapMagic Copilot, Circuit Mind, Quilter, JITX part models) — no accuracy claims or verification workflows were found or checked.

---

## 6. Cross-source agreement as a soundness mechanism; how librarians verify

### Takeaway
No precedent was found for automated N-version verification of library parts; the documented professional safeguards are manual (datasheet review, checklists, controlled "golden" libraries), which leaves triangulation as a defensible but novel design.

### Cited Findings
- [SECONDARY] Cadence argues respins caused by uncontrolled, divergent library data "get classified as design errors or manufacturing process breakdowns" and that the structural cause "rarely surfaces in a corrective action report"; cites Aberdeen research that designers spend roughly 24% of their time correcting data-integrity issues. — [Cadence blog](https://resources.pcb.cadence.com/blog/why-pcb-data-management-is-an-engineering-problem)
- [SECONDARY] Flux's design-review guidance lists "footprint mismatch" with root cause "wrong land pattern assigned in schematic library" as a standard defect category, alongside swapped RX/TX. — [Flux blog](https://flux.ai/p/blog/pcb-design-review-process)
- [ANECDOTAL, vendor-acknowledged] SnapEDA links footprints to parts by package details without datasheet check in some cases — i.e. an aggregator's footprint may be the generic package footprint, not an independent per-part observation. — [SnapEDA Q&A](https://www.snapeda.com/questions/question/wrong-footprint-4/)
- [SECONDARY] KLC encodes "datasheet recommendations take priority" (F4.1 title) and requires a valid footprint link for symbols with a default footprint (S5.1). — [KLC index](https://klc.kicad.org/history), [KLC S1](https://klc.kicad.org/symbol/s1)

### Inferences
- Independence analysis for Circuit OS witnesses: (W1) `footprints.py` + `PINMAPS` — the system under test; (W2) KiCad symbol/footprint — independent human transcription of a datasheet; (W3) D7 datasheet record — independent, strongest when human-verified; (W4) aggregator CAD model — may be auto-linked by package, so it is often NOT independent of "generic package footprint" and adds little beyond W2 for geometry; it can add value for pinout.
- Suggested trust ladder for a part's pin map: T0 = PINMAPS/"first free pad" only (unverified, block for ICs); T1 = agrees with KiCad symbol for exact MPN; T2 = T1 + agent-extracted datasheet pin table with page citation agrees; T3 = T2 + human sign-off bound to record hash. For geometry: G0 = pad count only (today); G1 = pad count + pitch + row span match KiCad footprint within tolerance; G2 = G1 + lead-coverage check against a datasheet outline dimension record; G3 = human-verified.
- Disagreement between W2 and W3 must fail closed and be surfaced with both citations; that event is exactly the class of bug (SOT-23 pin order) to be caught.
- The `land_patterns.json` registry entries (`verified: false`) can be promoted mechanically to G1 by a KiCad comparison and carry `source: kicad-footprints@<commit>` — an honest intermediate state between "unverified" and "datasheet-verified".

### Gaps
- No published library-audit checklist from Altium, Cadence or PCB Libraries Inc. was retrieved; no documented "golden library" process description was read in a primary source. No academic or industrial precedent for N-version library verification was found (absence of evidence from a limited search, not evidence of absence).

---

## 7. Geometric comparison algorithms

### Takeaway
No open implementation of footprint-vs-footprint or footprint-vs-package-outline comparison was found (KiCad's CLI offers none); the algorithm has to be written, and it is small because hobby-class footprints are low pad count with pad numbers available on both sides.

### Cited Findings
- [LOCAL] `kicad-cli fp` (10.0.1) exposes only `export` (SVG) and `upgrade`; no compare/check subcommand. — [KiCad](https://www.kicad.org/)
- [LOCAL] KiCad footprints give, per pad: number (string), type (`smd`/`thru_hole`), shape, `(at x y [rot])`, `(size w h)`, drill; origin at the footprint centre for the generated SMD parts checked (SOT-23 pads symmetric at x = +/-0.9375; 0603 at +/-0.825). — [kicad-footprints](https://gitlab.com/kicad/libraries/kicad-footprints)
- [PRIMARY] The lead-coverage relations needed for footprint-vs-package checks are exactly the Section 2 equations (Z vs L, G vs S, X vs W with S derived as L - 2T). — [IPC presentation, Bergman 2004](https://www.electronics.org/system/files/technical_resource/E31%26S01-3_Dieter.pdf)
- [PRIMARY] The arXiv ICGeo8K task decomposition (pin count -> pin centres -> pin dimensions) is a usable staging for comparison metrics as well. — [arXiv:2508.03725](https://arxiv.org/abs/2508.03725)

### Inferences (proposed algorithm; not from a cited implementation)
1. **Normalise**: convert both footprints to mm, Y-up or Y-down consistently (KiCad is Y-down), translate each to the centroid of pad centres (not the file origin — THT parts like TO-92_Inline and DIP are often anchored on pad 1).
2. **Count gate**: number of electrically distinct pads and the multiset of pad numbers must match (handle duplicated numbers: SOT-223 tab shares "2"; mounting/NPTH pads excluded).
3. **Pose search**: try the 8 elements of the dihedral group D4 (4 rotations x mirror). For each, match pads **by pad number** (primary); compute max centre error. Accept the pose with minimal error. A match that only succeeds under a *mirror* is a hard failure (bottom-view vs top-view drawing error — classic TO-92/TO-220/relay/module mistake); a match only under a non-zero *rotation* is a warning (orientation convention difference, Section 8).
4. **Numbering-independent check**: repeat the match ignoring pad numbers (Hungarian assignment or simple nearest-neighbour for N <= 40) to separate "geometry right, numbering wrong" from "geometry wrong". If geometry matches under identity but the induced permutation of pad numbers is not identity, report the permutation (e.g. "pads 2 and 3 swapped") — this is the SOT-23 bug detector.
5. **Tolerances**: centre error <= max(0.05 mm, 10% of pitch) for SMD; pad size within a band (e.g. -20%/+50%) as a warning, since density level A/B/C legitimately changes pad length by 0.3-0.6 mm (Section 2 table); drill diameter >= lead max + 0.2 mm for THT as an error. IoU of pad rectangles is a convenient single score for reporting but a poor gate (sensitive to legitimate toe differences); gate on pitch, row span and coverage instead.
6. **Footprint vs package outline** (independent of any library): require `G <= Smin`, `Z >= Lmax`, `X >= Wmax` (pad covers the whole lead foot), pitch equal to datasheet `e` within 0.02-0.05 mm, pin count equal; then report achieved Jt/Jh/Js against the chosen threshold table.
7. **Pin-1 identification**: KLC puts pin 1 top-left / left (Section 1); verify the generated footprint's pad "1" lies in the upper-left quadrant after normalisation and that numbering proceeds counter-clockwise for dual-row parts (DIP/SOIC) as seen from the top.

### Gaps
- No open-source footprint diff/compare library was found; KiCad's footprint-editor "compare with library" feature and KiBot/kidiff-style visual diff tools were not investigated. Tolerance values above are engineering proposals, not sourced.

---

## 8. Polarity / orientation and pick-and-place rotation

### Takeaway
Rotation "zero" is convention-dependent (IPC-7351 Level A pin 1 upper-left vs IEC 61188-7 / Level B pin 1 lower-left) and JLCPCB's expected rotation is tape-and-reel dependent and **part-specific**, so rotation must be handled by a per-part correction table plus a visual review, and kept out of the footprint-correctness verdict.

### Cited Findings
- [SECONDARY] Eurocircuits: IPC-7351 "typically defines pin 1 in the upper left corner of multi-pin components when viewed from above" (Level A); IEC 61188-7 positions pin 1 in the lower-left (Level B). A PCB Libraries admin states IPC-7351 Level B and IEC 61188-7 are identical zero orientations. — [Eurocircuits](https://www.eurocircuits.com/technical-guidelines/pcb-assembly-guidelines/defining-pin-1-zero-point-rotation/), [PCB Libraries forum TID 1515](https://www.pcblibraries.com/FORUM/topic1515.html)
- [SECONDARY] Zero orientation by type: chip capacitors/resistors/inductors pin 1 on the left; SOT, SOIC-J, QFP, LCC, BGA pin 1 upper-left. — [Sierra Circuits (protoexpress)](https://www.protoexpress.com/blog/features-of-ipc-7351-standards-to-design-pcb-component-footprint/)
- [PRIMARY-doc] KiBot documentation: the rotation in a position file depends on how KiCad orients footprints, how the assembler interprets angles, and how parts sit on the tape; "the internal database of rotations is just a list of common cases"; two components with the same footprint can need different rotations; and "KiCad mirrors components on the bottom side, but JLCPCB doesn't (november 2023)". — [KiBot position-file notes](https://kibot.readthedocs.io/en/latest/notes_position.html)
- [SECONDARY] Bouni's kicad-jlcpcb-tools reuses matthewlai's JLCKicadTools rotation-correction data and adds a Rotation manager for user corrections; the Fabrication Toolkit (bennymeg) uses per-component fields `JLCPCB Rotation Offset` (degrees, positive = counter-clockwise) and a position offset. — [kicad-jlcpcb-tools summary](https://awesome.ecosyste.ms/projects/github.com%2Fbouni%2Fkicad-jlcpcb-tools), [Fabrication Toolkit](https://github.com/bennymeg/Fabrication-Toolkit)
- [ANECDOTAL] KiCad forum: "the orientation is part-specific, not footprint-specific"; the problem "has not been solved universally"; users check JLCPCB's placement preview. — [KiCad forum](https://forum.kicad.info/t/is-there-a-simple-way-to-update-all-my-footprints-to-use-the-jlcpcb-orientations/38931), [KiCad forum](https://forum.kicad.info/t/wrong-components-alignment-for-jlcpcb-no-clue-if-due-to-kicad-or-due-to-script/43772)
- [LOCAL] KiCad diode symbols number the cathode as pin 1 (`Diode:1N4148W` and `1N4007`: 1=K, 2=A), and three-pin diodes vary (BAT54S 1=A 2=K 3=COM; LM4040DBZ 1=K 2=A 3=NC; BAS19 1=A 2=NC 3=K). — [kicad-symbols](https://gitlab.com/kicad/libraries/kicad-symbols)
- [ANECDOTAL] EasyEDA library 1N914 (DO-35) part reported with reversed cathode marking. — [EasyEDA forum](https://easyeda.com/forum/topic/1N914-PCB-footprint-is-incorrect-for-the-first-selection-in-the-library-c856480e71b745e79c5d13b75568a7f9)

### Inferences
- Circuit OS should fix one internal convention (KiCad/IPC Level A: pin 1 upper-left, two-terminal pin 1 left, **diode pad 1 = cathode**) and assert it in the verifier; then apply a per-LCSC-part rotation correction only at CPL export time. A netlist using "A"/"K" labels with a per-package map that assumes pad 1 = anode would silently reverse every diode — add an explicit test.
- Polarised two-terminal parts (diodes, LEDs, electrolytics, tantalums) need a polarity record separate from pad numbering: which pad is marked on silk/fab, and which physical feature marks it on the part (LED: cathode mark; tantalum: bar marks the POSITIVE end; aluminium electrolytic: stripe marks NEGATIVE) — these opposite conventions are a known assembly-error source (stated from general knowledge; no source retrieved this session).
- Because rotation is tape-dependent, a footprint-correctness verdict must be rotation-invariant (Section 7 pose search) while mirror remains an error.

### Gaps
- The actual rotation DB files (matthewlai's CSV; Bouni's corrections) and their size/format/licence were not opened. JLCPCB's official rotation documentation was not found. No sourced reference for LED/tantalum/electrolytic marking conventions was retrieved.

---

## 9. Real-world incidents and statistics (prioritisation)

### Takeaway
No rigorous statistic isolating wrong footprints or pinouts as a share of respins was found; circulating figures (30%, 60%, 61.5%) are unsourced or thinly sourced, so prioritisation should rest on the measured pin-map diversity (Section 3) and concrete incident reports.

### Cited Findings
- [SECONDARY, single paper, method unknown] "61.5% of [library] errors come from footprint dimensions" per a survey cited in an IJEECS paper. — [IJEECS](https://ijeecs.iaescore.com/index.php/IJEECS/article/view/26833)
- [SECONDARY, unsourced vendor claims] "design errors, which include footprint mistakes, can account for up to 60% of PCB prototype failures" (PCBCart, LCSC blog); "over 30% of PCB design errors stem from incorrect footprints" (AllPCB, citing unnamed "industry studies"). — [PCBCart](https://www.pcbcart.com/article/content/common-pcb-footprint-errors-and-preventi), [LCSC blog](https://www.lcsc.com/blog/footprint-solutions-in-pcb-design-standards-challenges-and-best-practices/), [AllPCB](https://www.allpcb.com/ar-SA/allelectrohub/the-ultimate-checklist-for-flawless-pcb-footprint-design)
- [SECONDARY] PCD&F/Circuits Assembly salary survey as cited by Cadence: nearly 60% of designers produce one to five respins annually (frequency, not cause). — [Cadence blog](https://resources.pcb.cadence.com/blog/why-pcb-data-management-is-an-engineering-problem)
- [ANECDOTAL] Concrete incidents: IRF3205S D/S swap scrapping an assembled board; LH05-10B05 module footprint that would have reversed VCC/GND; RJ45 wrong spacing; header symbol/footprint pin-count mismatch (40 vs 46); SRD relay pin orientation thread; 1N914 reversed cathode; SnapEDA wrong pitch and wrong pin assignment reports. — [EasyEDA forum IRF3205S](https://easyeda.com/forum/topic/Wrong-pin-maping-to-footprint-for-MOSFET-irf3205s-310bcca41bf14898816a3dd13da3e81d), [EasyEDA forum C91816](https://www.easyeda.com/forum/topic/Library-LCSC-C91816-Wrong-official-pinout-on-the-PCB-footprint-a8b7d34c57ff42bbaddcc0b8eb0e0c80), [EasyEDA forum SRD relay](https://www.easyeda.com/forum/topic/RELAY-SL-SRD-schematic-and-PCB-pin-orientations-are-WRONG-f246680ca9f044a19ae35ff494763595), [SnapEDA Q&A](https://www.snapeda.com/questions/question/this-foot-print-is-not-correct/)
- [LOCAL] Structural exposure measured in the KiCad library: 39 pin maps for SOT-23, 30 for TO-92, 15 for SOT-223, 16 for TO-220-3, 109 for SOT-23-5, 298 for SOIC-8. — [kicad-symbols](https://gitlab.com/kicad/libraries/kicad-symbols)

### Inferences
- Priority order for Circuit OS, by (likelihood x silent-failure severity): (1) per-part pin maps for 3-terminal SOT-23/TO-92/SOT-223/TO-220 parts — power reversal or dead transistor, undetectable by pad-count checks; (2) removing the SOIC-8 "first free pad" fallback; (3) mirror/bottom-view errors on THT modules and relays (DHT22, SRD-05VDC — hand-authored footprints with the weakest external references, and the SRD relay has a known library-error thread and blank pin names in KiCad); (4) diode/LED polarity convention; (5) pitch/row-span geometry; (6) fillet-size compliance (lowest — rarely causes a respin at hobby density).
- Do not quote the 30%/60% figures in user-facing material; the 61.5% figure may be cited only with its caveat.

### Gaps
- No primary survey data on respin causes was located. EEVblog/Hackaday post-mortems were not searched specifically. No incident data specific to KiCad official-library errors was found (which would calibrate W2's trust level).
