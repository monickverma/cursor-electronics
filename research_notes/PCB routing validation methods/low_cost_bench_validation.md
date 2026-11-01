# Low-cost physical (bench) validation of PCB routing and traces — solo developer in India, 2026

Notes for the report writer. All prices were read on 2026-10-08 from web search results and vendor pages; most are
undated listings and must be re-quoted before ordering. Conversions use the rate the sources themselves imply
(USD 2 ≈ INR 170, i.e. about INR 85 per USD). "Inferences" are my own reasoning or arithmetic and are not sourced.
Tool-call budget was exhausted before every sub-question could be sourced; each such hole is listed under Gaps
rather than filled from memory.

Source-quality warning that applies throughout: much of the India-specific pricing comes from zbotic.in, an Indian
PCB vendor that competes with the fabs it compares. Its numbers are consistent across its own pages but are not
independent. I could not open its comparison page directly (HTTP 403); figures are from search-result extracts.

---

## 1. Cheapest ways to get a 2-layer prototype made (fabs and home methods)

### Takeaway
Five 100 x 100 mm 2-layer boards cost about USD 2 (INR 150-170) at JLCPCB or PCBWay before shipping, and roughly
INR 400-800 at Indian fabs with no customs step; landed cost from China is realistically INR 500-900 with economy
shipping, and duty on a small parcel is possible but not certain. Home etching or milling can reach about 8-10 mil
but is the wrong tool for validating a router, because the home process becomes the largest unknown.

### Cited Findings
- JLCPCB 5 pcs, 2-layer, 100 x 100 mm: USD 2 (about INR 170); PCBWay the same, with 7-14 day delivery to most Indian cities (guide dated March 2026 per the search extract) — [Zbotic order guide](https://zbotic.in/how-to-order-pcb-from-jlcpcb-and-pcbway-india-cost-guide/)
- Same spec (FR-4, 1.6 mm, HASL lead-free, green mask) listed as INR 150 at JLCPCB vs INR 600 at LionCircuits — [Zbotic comparison 2026](https://zbotic.in/jlcpcb-vs-pcbway-vs-lioncircuits-vs-zbotic-pcb-service-comparison-2026/)
- JLCPCB shipping to India: economy direct line 7-14 days at USD 3-8 for small packages; registered airmail 10-20 days at USD 3-5; DHL/UPS express 3-5 days at USD 25-45 — [Zbotic order guide](https://zbotic.in/how-to-order-pcb-from-jlcpcb-and-pcbway-india-cost-guide/); a second page from the same vendor gives DHL at USD 12-25 (INR 1,000-2,100), so the express figure is inconsistent — [Zbotic assembly cost guide](https://zbotic.in/pcb-assembly-service-india-jlcpcb-vs-local-fab-cost-guide/)
- Indian fabs, 5 pcs 2-layer 100 x 100 mm: LionCircuits about INR 500-800 with 3-5 day lead time; PCB Power about INR 400-700 with 3-7 days; general range INR 300-800 — [Zbotic Indian manufacturers compared 2026](https://zbotic.in/indian-pcb-manufacturers-compared-2026-price-quality-lead-time/)
- Rush service is priced separately: PCB Power 24-hour express for 5 boards INR 2,000-5,000; LionCircuits offers 48-hour prototypes — [Zbotic rush prototyping](https://zbotic.in/rush-pcb-prototyping-24-48-hour-options-in-india/)
- Forum reports: users recommend Robu and LionCircuits and report no problems; one report of a LionCircuits 2-layer order taking about a month; one unverified claim that Robu outsources fabrication to China — [TechEnclave thread](https://techenclave.com/threads/pcb-fabrication-within-india.224341/)
- Import duty: bare PCBs fall under HS 8534; the vendor source gives basic customs duty 10-20% plus 18% IGST, and elsewhere says total import cost can add 35-38% of declared value (the two figures do not agree) — [Zbotic assembly cost guide](https://zbotic.in/pcb-assembly-service-india-jlcpcb-vs-local-fab-cost-guide/)
- Small orders (5-10 boards, under about INR 3,000 value) are said to routinely clear without duty assessment, "not guaranteed"; for INR 5,000-50,000 orders the courier collects duty plus INR 500-3,000 brokerage on delivery — [Zbotic order guide](https://zbotic.in/how-to-order-pcb-from-jlcpcb-and-pcbway-india-cost-guide/)
- JLCPCB states all duties and taxes are the customer's responsibility and that it cannot predict them — [JLCPCB Customs, Duties and Taxes](https://jlcpcb.com/help/article/Customs,-Duties-and-Taxes)
- JLCPCB minimum design rules, 1-2 layer, 1 oz: trace/space 0.10/0.10 mm (4/4 mil); minimum via 0.15 mm hole / 0.25 mm diameter; PTH annular ring recommended 0.25 mm, absolute minimum 0.18 mm; board thickness tolerance ±10% for boards 1.0 mm and thicker. The page gives no finished-copper thickness tolerance — [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- Home toner transfer: traces below about 15 mil can be unreliable; experienced users report 10 mil reliably, 8 mil occasionally, one claims 6 mil with thorough copper cleaning — [EEVblog home-made PCBs thread](https://eevblog.com/forum/projects/home-made-pcb_s), [VanHack PCB wiki](https://vanhack.ca/wiki/hacks/pcb)
- Home UV photoresist: 0.15-0.2 mm (6-8 mil) claimed; a hobbyist who tried both got only 8-10 mil, limited by the artwork printer — [Zbotic photoresist guide](https://zbotic.in/photoresist-pcb-making-at-home-uv-exposure-and-developer/), [MySensors forum](https://forum.mysensors.org/post/81551)
- CNC isolation milling: one user reports 6 mil track / 6 mil isolation; another found 10 mil traces came out as 2-3 mil because a small Z-depth error almost removes the trace — [CNCArena thread](https://en.cncarena.com/forum/thread/120546-pcb-trace-isolation-minimum-track-and-isolation/), [Parallax forum](https://forums.parallax.com/discussion/comment/812859)

### Inferences
- Budget line for the first build: 5 boards from JLCPCB with economy shipping is about USD 5-10 (INR 450-850) if no duty is charged; allow up to about 40% of declared value extra if it is assessed. An Indian fab at INR 400-800 is the same order of cost with less schedule risk from customs. Either fits inside the USD 50-100 budget many times over, so ordering two or three board variants in one go (see section 7) is affordable.
- 100 x 100 mm is the size that gets the promotional price; a coupon panel plus the functional boards should be laid out to fit inside it.
- Home fabrication is not recommended for this purpose. The question being tested is "does the generated routing work when made by a normal process"; a home-etched board adds its own width loss, missing plated vias (home boards have no through-plating, so every via is a hand-soldered wire) and registration error. A failure could not be attributed to the router. Home methods are only a fallback for single-sided logic-level checks at 12 mil or wider.
- The generated layout should be checked against the fab's rules before ordering with margin, e.g. 0.2 mm or wider trace and space, since 4/4 mil is the fab's limit and not a comfortable default.

### Gaps
- No verified current price for Robu's PCB service or for PCBGOGO shipped to India was found. Both give instant quotes online; get a live quote.
- No official Indian customs source was reached for the HS 8534 duty rate or the low-value threshold. The roughly INR 5,000 de minimis figure comes only from a vendor page.
- Trace-width (etch) tolerance at JLCPCB and at the Indian fabs was not found on the pages read. It matters for section 3.
- Minimum design rules for PCB Power, LionCircuits and Robu were not retrieved.
- Whether the 2-layer price quoted by Indian fabs includes GST and shipping was not confirmed.

---

## 2. Continuity and isolation testing

### Takeaway
At JLCPCB a full flying-probe test for opens and shorts is free on orders under 50 pieces, so a 5-board prototype
order arrives already tested against the netlist derived from the Gerbers. That proves the copper matches the
Gerbers, not that the Gerbers match the schematic — the second is what the developer must test.

### Cited Findings
- JLCPCB's FAQ: the flying probe test is "the electrical test to check whether there are short circuits or open circuits"; for orders of no more than 50 pieces a full test of the whole order is free; 50 or more pieces costs extra — [JLCPCB Flying probe test FAQ](https://jlcpcb.com/quote/pcbOrderFaq/Flying%20probe%20test)
- JLCPCB lists the flying probe test as checking net-level opens and shorts only — [JLCPCB prototype assembly page](https://jlcpcb.com/solutions/pcb-prototype-assembly)
- Anecdotal counter-view: an EEVblog poster says boards without probe marks were not tested and that without paying for 100% test only a few panels are sampled — [EEVblog "I am done with JLC PCB" thread](https://www.eevblog.com/forum/manufacture/i-am-done-with-jlc-pcb/msg3416964/). This conflicts with the FAQ for small orders; the FAQ is the primary source, the post is older and unverified.
- Flying-probe testers in general can also do unpowered checks of capacitance, resistance, diodes and inductance, but JLCPCB's own description covers opens and shorts only — [MOKO Technology flying probe overview](https://www.mokotechnology.com/pcb-flying-probe-test-what-is-it/)
- Probe contact resistance depends on pressure and adds to a two-wire reading; consistent pressure and clean pads reduce it — [Industrial Monitor Direct, Kelvin probe note](https://industrialmonitordirect.com/ko/blogs/knowledgebase/kelvin-probe-pressure-effect-on-4-wire-resistance-measurement-accuracy)

### Inferences
- What the fab test proves: every net in the Gerber-derived netlist is continuous and no two nets are shorted, on the bare board. What it cannot prove: that the router connected the right pins (if the router wires pin A to the wrong net, the Gerbers say so too and the test passes), that footprints and pin orders are right, or anything about resistance, current capacity or signal quality. Uploading an IPC-D-356 netlist exported from the design, rather than letting the fab derive one from the Gerbers, would close the first hole, but I did not confirm that the cheap fabs accept one.
- Manual procedure with a multimeter, on the bare board before soldering: (1) print the net list as a table of pad pairs; (2) continuity beeper from each net's first pad to every other pad on that net; (3) isolation: resistance range (not the beeper) between each net and every other net, with power and ground first; expect over-range. For N nets there are N(N-1)/2 isolation pairs: 15 nets gives 105 pairs, about 20 minutes by hand. Record the meter model and range.
- The continuity beeper threshold on cheap meters is tens of ohms, so a beep says "connected" and nothing about quality; a hairline or over-etched trace still beeps. Trace quality needs section 3.
- Arduino netlist tester: one Uno pin per test point (a pogo-pin or header fixture). For each net, drive one pin LOW as output, set every other pin INPUT_PULLUP, and read them; pins that read LOW are connected to the driven one. Compare the resulting connectivity matrix to the expected netlist from the Board IR. An Uno has 20 usable I/O pins, which is enough for these small boards; larger boards need a shift register or analog multiplexer. Limits: the internal pull-up is tens of kilohms, so anything under a few kilohms reads as "connected" — it detects opens and hard shorts, it does not measure resistance, and it must be run on a bare board because populated components (LED, resistors, the MAX485) create real paths between nets.
- This tester is where the software can close the loop cheaply: the expected matrix is generated from the same Board IR that produced the Gerbers, but checked through an independent physical path.

### Gaps
- Whether PCBWay, PCB Power, LionCircuits and Robu include a free 100% electrical test on 5-piece orders was not confirmed.
- Whether JLCPCB or the Indian fabs accept a customer-supplied IPC-D-356 netlist on a prototype order was not found.
- No published, sourced Arduino netlist-tester design was retrieved; the procedure above is my own description of the standard pull-up scan.
- Continuity-beeper threshold values for specific cheap meters were not sourced.

---

## 3. Trace resistance measurement (4-wire / Kelvin)

### Takeaway
Force a known current through the trace from a bench or USB supply and read the millivolt drop with the meter on
separate sense points; a hobby meter gives the resistance of a 100 mΩ trace to a few percent. The comparison with
calculation is limited by not knowing the finished copper thickness and etched width (tens of percent), not by the
meter.

### Cited Findings
- Method: a constant current is applied to the part under test and a voltmeter reads the voltage across it; the voltage drop in the force wires does not matter because voltage is not measured on those wires — [Siborg, four-wire vs two-wire](https://siborg.com/?p=186)
- A single-tip probe puts all contact resistances into the reading and is pressure-sensitive; a true Kelvin probe with separate force and sense pins excludes force-side contact resistance. Thermal EMFs from dissimilar metals add a voltage offset — [Industrial Monitor Direct, Kelvin probe note](https://industrialmonitordirect.com/ko/blogs/knowledgebase/kelvin-probe-pressure-effect-on-4-wire-resistance-measurement-accuracy)
- Hobby milliohm-meter designs: precision current source plus an amplifier with gain about 100 into a DVM, with a trimmer to null the offset when the sense leads are shorted — [Eleccircuit DIY milliohm meter](https://www.eleccircuit.com/designing-diy-precision-milli-ohmmeter-circuit/), [Homemade Circuits milliohm tester](https://www.homemade-circuits.com/simple-milliohm-tester-circuit/)
- Typical cheap meter (UNI-T UT33D+): DC volts ±(0.5% + 2 digits), resistance ±(0.8% + 2 digits) — [Toolboom UT33D+](https://toolboom.com/en/digital-multimeter-uni-t-ut33dplus), [TME UT33D+](https://www.tme.eu/dk/en/details/ut33d+/portable-digital-multimeters/uni-t/); one retailer lists the 200 mV range as ±(0.7% + 3) at 0.1 mV resolution and 200 Ω as ±(1.0% + 2) at 0.1 Ω resolution, which conflicts — [goodstore.lv UT33D](https://goodstore.lv/en/product/universalais-meritajs-ut-33d-uni-t)
- Copper thickness: nominal 1 oz foil is about 34.3 µm; a 10% foil tolerance allows about 30.9 µm; processing may remove about 6 µm, leaving a 24.9 µm minimum for an unplated (inner) layer. Outer layers gain plating: IPC-6012 average plating 20 µm for Class 2, 25 µm for Class 3 — [NCAB, how much finished copper can be expected](https://www.ncabgroup.com/faq/how-much-finished-copper-can-be-expected/)
- A forum post citing IPC-6012E Class 2 gives 33.4 µm minimum for 1 oz outer layers with 35-38 µm typical; this does not reconcile with the NCAB arithmetic (about 45 µm) and is a secondary source — [EDAboard stack-up thread](https://www.edaboard.com/threads/stack-up-pcb.403397/)
- IPC-6012 specifies requirements from base copper weight, not finished copper — [Eurocircuits, tolerances on copper thickness](https://www.eurocircuits.com/tolerances-on-copper-thickness/)

### Inferences
- Expected values (my arithmetic, copper resistivity taken as 1.72e-8 Ω·m at 20 °C, 35 µm thick, about 0.49 mΩ per square): a 0.25 mm x 50 mm trace is 200 squares, about 98 mΩ; a 0.5 mm x 50 mm trace about 49 mΩ; a 1.0 mm x 50 mm trace about 25 mΩ. The board's real traces are a few centimetres, so 10-100 mΩ is the range to expect.
- Why the two-wire ohm range is useless here: 0.1 Ω resolution and ±2 digits on the 200 Ω range is ±0.2 Ω on a 0.1 Ω trace, before lead resistance of a few tenths of an ohm.
- Meter-only uncertainty for the four-wire method, using ±(0.5% + 2 digits) at 0.1 mV resolution: at 100 mA a 98 mΩ trace gives 9.8 mV ± 0.25 mV, about 2.5%; at 500 mA it gives 49 mV ± 0.45 mV, about 1%. The current reading, taken with the same meter in series or as the drop across a known 1% resistor, adds roughly 1-2%. Combined, about 2-4% on resistance. A second meter (one for current, one for voltage) removes the need to swap leads.
- The comparison uncertainty is far larger than that. Finished outer copper between roughly 33 and 45+ µm is a spread of about ±15% or more around the middle, and resistance scales inversely with thickness; etched width is also narrower than drawn by an unknown amount, which matters most on the narrowest traces. A measured resistance 20-30% away from a "35 µm" calculation is therefore not evidence of a routing fault. Copper's temperature coefficient (about 0.39% per °C, quoted in the search summary as general engineering knowledge, unsourced) adds 4% for a 10 °C lab temperature difference.
- What it can prove: relative comparisons on the same board are good to a few percent, because thickness is common to all traces. So "the router's trace from A to B is X squares long; a straight reference trace of the same width is Y squares; the measured ratio matches X/Y" is a strong, cheap test of whether the router's length and width are what the Board IR says. It also catches necked-down or damaged traces and bad vias. What it cannot prove: absolute copper thickness without a coupon, or anything about AC behaviour.
- Practical setup under INR 500 beyond the meter: a 5 V USB supply or the Uno's 5 V pin with a series power resistor (e.g. 10 Ω 5 W gives about 0.5 A), solder the force wires to the pads, touch the sense probes on the trace side of the force joints. Reverse the current and average the two readings to cancel thermal EMF offsets. Keep the current well below the trace's rating so self-heating does not shift the result (section 4).

### Gaps
- No source was found that states the fab's etched-width tolerance or measured finished copper for JLCPCB or Indian fabs.
- Prices and accuracy of ready-made cheap milliohm meters (e.g. the YR1035+ class) were not retrieved.
- Copper resistivity, temperature coefficient and via barrel resistance values are from general knowledge, not from a fetched source; cite a handbook before printing them.
- No published hobby measurement comparing measured trace resistance on cheap-fab boards with calculation was found.

---

## 4. Current-carrying / temperature-rise test

### Takeaway
A trace-heating test is easy to run but hard to compare tightly: the IPC charts are themselves conservative and
board-dependent, and cheap temperature sensing on a narrow trace has errors of several degrees. For these boards
(LED, logic and RS-485 currents of tens of milliamps) the test is close to unnecessary; it is worth one coupon, not
a campaign.

### Cited Findings
- IPC-2221's formula came from test boards where traces carried a known current and the temperature change was measured, for a single board type and copper weight; IPC-2152 extended the data to copper weight, plane presence, trace-to-plane distance and air vs vacuum — [Cadence, IPC-2152 vs IPC-2221](https://resources.system-analysis.cadence.com/blog/ipc-2152-vs-ipc-2221-which-to-use-for-pcb-thermal-analysis)
- Worked example in the same source: one case gives 54 °C rise by IPC-2221 and 41 °C by IPC-2152 with an adjacent plane, on 1 oz copper — a 13 °C difference between the two standards for the same trace — [Cadence, IPC-2152 vs IPC-2221](https://resources.system-analysis.cadence.com/blog/ipc-2152-vs-ipc-2221-which-to-use-for-pcb-thermal-analysis)
- IPC-2221's chart is reported to greatly overestimate temperature rise at all currents when compared with measured values — [Philip McGaw, IPC-2221 standard trace widths](https://philipmcgaw.com/ipc-2221-standard-trace-widths/)
- IPC-2152 nomographs also tend to overestimate the width needed — [Altium, using an IPC-2152 calculator](https://resources.altium.com/p/using-ipc-2152-calculator-designing-standards)
- IPC-2221 ignores cooling from nearby pours and planes; a calculator vendor claims IPC-2152 allows about 1.5-2x the current for the same rise (vendor curve fit, not verified against the standard) — [Salitronic trace width calculator](https://salitronic.com/pcb-trace-width-calculator/)
- IR measurement: solder mask emissivity is near 0.95, bare copper and solder often below 0.1; on shiny copper a ±0.05 emissivity uncertainty can make the reading wrong by about 100%, vs about 5% on a matte surface; the fix is matte black tape or paint with the instrument set to match — [PCBSync IR guide](https://pcbsync.com/?p=31928)
- Practitioners report IR readings on solder mask are roughly fine, metal surfaces unusable without correction, and that spot size and aim are a further uncertainty — [EEVblog, practical accuracy of IR thermometers on PCBs](https://eevblog.com/forum/metrology/practical-accuracy-of-ir-thermometers-on-pcbs/msg880292); a solder joint looked like a cold spot until painted — [Igor's Lab IR methodology](https://igorslab.de/en/infrared-measurement-methodology-so-we-test/3)

### Inferences
- Is it needed here? The circuits in scope carry an LED current of 10-20 mA, MCU supply current of tens of milliamps and RS-485 driver current of tens of milliamps into a 120 Ω termination. A 0.25 mm 1 oz trace at those currents dissipates microwatts per millimetre; no measurable rise is expected. A heating test therefore cannot fail on the real boards and tells nothing about the router. Say this plainly in the report.
- If the developer wants the capability demonstrated anyway (e.g. for a future power block), do it on a coupon: a 0.25 mm and a 0.5 mm trace, 50 mm long, on bare FR-4 with no pour underneath, driven at 0.5, 1.0 and 1.5 A.
- Cheapest good thermometer is the trace itself: measure its four-wire resistance cold at a small current, then at the test current once the reading settles; the fractional rise in resistance divided by about 0.0039 per °C is the average temperature rise. With 1% resistance repeatability that resolves about 2.5-3 °C, with no contact or emissivity error. It gives the average over the trace, not the hot spot.
- A K-type thermocouple on a cheap meter is typically specified to a few degrees and a bead on a narrow trace sinks heat and reads low; a single-spot IR thermometer has a spot larger than the trace and averages in cold board. Both are indicative only. Expect disagreement with IPC-2221 of tens of percent in the direction of the board running cooler than predicted; that is the documented behaviour of the standard, not a finding about the board.
- Safety: current-limit the supply, raise current in steps, stop at about 40-50 °C rise or any discolouration, keep the board on a non-flammable surface, do not touch — FR-4 near a fusing trace chars. A USB power bank is not a current-limited supply; use a series resistor or a bench supply with a current limit.

### Gaps
- The measurement method and uncertainty of the IPC-2152 test programme itself were not found; no peer-reviewed measured-vs-predicted scatter figure was retrieved.
- Prices in India for a current-limited bench supply, K-type thermocouple meters and entry thermal cameras were not retrieved. A bench supply and a thermal camera are likely to break the USD 50-100 budget on their own; flag as "above budget, borrow instead".
- Accuracy specifications of cheap thermocouple meters and IR thermometers were not sourced.
- The copper temperature coefficient is general knowledge here, not from a fetched primary source.

---

## 5. Test coupons

### Takeaway
A test coupon is a small pattern fabricated alongside the real board so the process can be measured without
touching the product; IPC-2221B Appendix A defines a family of them, of which the daisy-chain via coupon is the one
most relevant to resistance. A solo developer can put a home-made coupon strip on the same 100 x 100 mm order for
no extra cost.

### Cited Findings
- IPC-2221B Appendix A coupon family (from a secondary summary): AB/R general through-hole coupon; A/R for boards without vias; B for via structures and registration; D the daisy-chain via coupon for plated hole/via thermal stress; others (E, S, W, G, H, P, Z, K) cover insulation resistance, solderability, solder mask adhesion, surface insulation resistance, peel strength, controlled impedance and registration — [VSE, test coupons](https://www.vse.com/blog/test-coupon-look-inside-pcbs/)
- Daisy-chain coupons use via structures in a chain to measure resistance, typically as two independent chained nets — [Sierra Circuits, what are PCB test coupons](https://www.protoexpress.com/kb/what-are-pcb-test-coupons/)
- D coupons allow continuous four-wire resistance monitoring through thermal cycling; a commonly cited pass criterion is under 5% resistance change after stress (one fabricator's guidance) — [Atlas PCB, test coupon design](https://www.atlaspcb.com/pcb-test-coupon-design-ipc-standards/)
- In a daisy-chain pattern, tracks contribute about 80% of the resistance and plated barrels about 20% — [US patent 5172063](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5172063)
- IPC-TM-650 2.5.5.7: TDR impedance accuracy degrades when the line's impedance differs significantly from the 50 Ω measurement system — [IPC-TM-650 2.5.5.7a](https://www.electronics.org/sites/default/files/test_methods_docs/2-5-5-7a.pdf)

### Inferences
- Proposed coupon strip (my design, sized to fit along one edge of the 100 x 100 mm panel, roughly 100 x 20 mm), every structure with four pads (two force, two sense) on 2.54 mm pitch so header pins or probes fit:
  1. Width ladder: straight 50 mm traces at the router's minimum width, its default width, and 2x and 4x that (e.g. 0.2, 0.25, 0.5, 1.0 mm). Measured resistance vs 1/width should be a straight line; its slope gives the fab's sheet resistance (hence effective copper thickness) and its intercept on the width axis gives the etch loss. This turns the two biggest unknowns of section 3 into measured numbers for this batch.
  2. Length ladder: the default width at 25, 50 and 100 mm (serpentine for the longest). Checks linearity and gives a per-square figure independent of pad effects.
  3. Via chain: 10 and 20 vias in series at the router's via size, alternating layers, with the trace length between vias known. Subtract the trace part using the sheet resistance from item 1; the remainder divided by the via count is the per-via resistance. An open chain shows a via-size or annular-ring problem.
  4. Spacing comb: two interleaved combs at the router's minimum clearance and at 2x. Isolation test only (over-range on the highest resistance range, before and after soldering/flux cleaning).
  5. Router-output sample: two or three nets copied exactly from the generated layout (with their bends and vias), with Kelvin pads at each end, beside straight references of the same width and nominal length. This is the piece that tests the router and not the fab.
  6. Optional, only if a NanoVNA is available: one 50 mm trace over solid ground on the bottom layer with SMA edge-launch footprints. See section 6 for why its value is low on 1.6 mm two-layer boards.
- The official IPC coupons are for lot conformance at a fab with microsection and thermal-stress equipment; reproducing them is unnecessary. Borrow the idea (known geometry, four-wire pads, daisy chains), not the artwork.
- Ask for all five boards from the same panel where possible and label each coupon by board number, so board-to-board scatter can be measured (section 8).

### Gaps
- IPC-2221B Appendix A was not read directly (paywalled); the coupon list is from secondary summaries and should be labelled as such.
- No source was found giving a typical per-via resistance for a 0.3 mm plated via on a cheap 2-layer board.
- Whether cheap fabs object to or charge for coupon structures that look like "multiple designs" on one order was not checked; JLCPCB and others have had rules about panelised sub-designs.

---

## 6. Signal measurements on a budget (NanoVNA, logic analyser, pocket scope, Arduino as instrument)

### Takeaway
For these circuits the useful cheap instrument is a logic analyser (timing of DHT22 and RS-485 frames) and, for the
RC filter, the Arduino itself or a NanoVNA used as a low-frequency network analyser. RF-grade trace measurements —
characteristic impedance, TDR, S-parameters of the traces — are unnecessary here and would not be trustworthy on a
NanoVNA at these trace lengths anyway.

### Cited Findings
- NanoVNA-H4: 10 kHz to 1.5 GHz; dynamic range about 70 dB (50 kHz-300 MHz), 60 dB (300-900 MHz), 40 dB (0.9-1.5 GHz); 101 or 401 scan points; output about 0 dBm — [Eleshop NanoVNA-H4](https://eleshop.eu/nanovna-h4.html), [nanovna.com](https://nanovna.com/)
- NanoVNA prices (undated listings): NanoVNA-H EUR 33.02 and NanoVNA-H4 EUR 46.95 excluding VAT at a Dutch retailer; USD 189 at Newegg for the H4, so prices vary several-fold by seller — [Eleshop NanoVNA-H](https://eleshop.eu/nanovna-h.html), [Eleshop NanoVNA-H4](https://eleshop.eu/nanovna-h4.html), [Newegg](https://www.newegg.com/p/2VT-04DT-00001)
- Many clones exist; the maker's site warns that "2.7 GHz NanoVNA plus" units are usually fakes and that noise is substantial above 1.5 GHz — [nanovna.com](https://nanovna.com/)
- NanoVNA-Saver software has a TDR function intended for cable length, with an impedance display — [nanovna-saver on GitHub](https://github.com/msspad/nanovna-saver)
- TDR impedance measurement on a PCB needs a defined measurement zone away from the launch discontinuity, and is traceable only through air-line standards — [Keysight TDR PCB impedance example](https://helpfiles.keysight.com/csg/e5080b/Applications/Enhanced_Time_Domain_Analysis/Measurement_Examples/TDR_-_PCB_Impedance_Measurement.htm), [IPC-TM-650 2.5.5.7a](https://www.electronics.org/sites/default/files/test_methods_docs/2-5-5-7a.pdf)
- FX2-based 8-channel "24 MHz" logic analysers (Saleae clones, sigrok fx2lafw): 24 MHz maximum sample rate; maximum input 5.25 V; logic high at 2.0 V minimum and low at 0.8 V maximum; input over 100 kΩ, about 5 pF — [SparkFun USB Logic Analyzer 24MHz/8-channel](https://sparkfun.com/products/14789)
- The 24 MHz rate may be unstable: a reviewer reports the software frequently locked up at 24 MHz and lower rates worked fine — [lygte-info review](https://lygte-info.dk/review/Equipment%20Logic%20Analyzer%208%20channels%2024MHz%20UK.html); a manual for one clone says about 1.4 V threshold and reliable signals only to about 8 MHz (conflicts with the vendor spec, unverified) — [ShillehTek manual](https://shillehtek.com/blogs/shillehtek-product-manuals/24mhz-8-channel-usb-logic-analyzer-digital-debugger-for-arduino-manual)
- sigrok protocol decoders are Python modules in libsigrokdecode — [libsigrokdecode package page](https://build.opensuse.org/package/show/openSUSE/libsigrokdecode)
- Pocket scopes in India: FNIRSI DSO152, 200 kHz bandwidth, 2.5 MS/s, INR 3,395 incl. GST at Robu; FNIRSI DSO-TC3, 500 kHz, 10 MS/s, INR 6,690 at Robu (Amazon.in average about INR 6,818); FNIRSI DSO-153, 1 MHz, 5 MS/s. Bandwidths are advertised, not independently measured — [Robu DSO152](https://stgaws.robu.in/product/fnirsi-dso152-oscilloscope-2-8-tft-handheld-digital-oscilloscope-2-5ms-s-high-sampling-rate-200khz-bandwidth), [Robu DSO-153](https://stgaws.robu.in/product/fnirsi-dso-153-2-in-1-mini-digital-oscilloscope-with-signal-generator2-8-lcd-screen-5ms-s-sampling-rate-1mhz-bandwidth), [price-history.in DSO-TC3](https://price-history.in/product/fnirsi-dso-tc3-3-1-oscilloscope-gfShQmmb)
- DHT22/AM2302 bus: host start pulse low at least 800 µs in one datasheet copy, 1-10 ms in another; sensor answers 80 µs low then 80 µs high; 40 bits, MSB first, last byte a checksum of the other four — [Waveshare DHT22 wiki](https://waveshare.com/wiki/DHT22_Temperature-Humidity_Sensor), [SparkFun-hosted DHT22 datasheet](https://cdn.sparkfun.com/assets/f/7/d/9/c/DHT22.pdf)
- ATmega328P ADC: 10-bit, ±2 LSB absolute accuracy (typical), 0.5 LSB INL; an unreviewed datasheet summary gives 4.5 LSB maximum at a 200 kHz ADC clock — [CSULB ADC lecture](https://home.csulb.edu/~hill/ee444/Lectures%20-%20Deprecated/12%20ADC.pdf), [adom wiki ATmega328P](https://wiki.adom.inc/kyle/atmega328p)
- Arduino clock: input capture reads counters clocked at 16 MHz; a ceramic resonator is about ±0.5% and a crystal is much more accurate — [Joris van Rantwijk, Arduino frequency](https://jorisvr.nl/article/arduino-frequency), [Arduino forum, clock speed](https://forum.arduino.cc/t/arduino-clock-speed/127495)

### Inferences
- Why RF trace measurements are unnecessary: the fastest thing on these boards is the edge of a logic or RS-485 driver, some nanoseconds to tens of nanoseconds, on traces of a few centimetres whose propagation delay is a few tenths of a nanosecond. The traces are electrically short by a large factor, so characteristic impedance, reflections and S-parameters do not affect function. On an RS-485 node the bus cable and its termination matter; the 2 cm of PCB trace to the connector does not. Say this plainly.
- Why a NanoVNA could not do it well even if wanted: with a 1.5 GHz span the time-domain resolution is of the order of 10 cm of trace, longer than the traces; a 1.6 mm two-layer board gives microstrip far from 50 Ω at normal widths (a 50 Ω line would need a trace roughly 3 mm wide), which is exactly the condition IPC-TM-650 says degrades accuracy; and the launch dominates. Skip it.
- Where the NanoVNA is useful here: as a 10 kHz+ network analyser for the RC low-pass filter (S21 through the filter, read the -3 dB point). Caveats: its 50 Ω ports load the filter, so either the filter must be measured with series/shunt resistors and the loading de-embedded by calculation, or the cutoff must be above 10 kHz — the project's reference RC filter is at 1 kHz, below the instrument's range. For a 1 kHz filter the Arduino step-response method below is better.
- Logic analyser, about INR 400-900 for an FX2 clone (price not sourced): at 8-12 MS/s the time resolution is about 0.1 µs, ample for DHT22 bit cells of tens of microseconds and for RS-485 at 9600-115200 baud (bit times 104 µs down to 8.7 µs). It can show: every DHT22 pulse width against the datasheet windows, frame completeness and checksum; UART framing, baud error, and DE/RE turn-around timing on the MAX485's logic side. It cannot show: analog levels, rise time (it sees only a threshold crossing), ringing, or the differential bus voltage — and it must not be connected straight to the A/B lines of a bus that can exceed 0-5 V. A slow DHT22 rising edge from a weak pull-up or long cable appears only indirectly, as shortened high times.
- Pocket scope: a 200 kHz scope has a rise time of roughly 1.75 µs and a 500 kHz one about 0.7 µs (0.35/bandwidth rule, unsourced). That is enough to see the DHT22 pull-up RC rise (a 4.7-10 kΩ pull-up with 100 pF-1 nF of cable gives 0.5-10 µs time constants) and RS-485 levels at 9600 baud; it cannot show driver edge rates or ringing, and single-channel units cannot view A and B together. A used or entry bench scope (Rigol/Hantek class) exceeds the budget; borrow one (section 9).
- Arduino as an instrument: (1) DC voltages — divider output, LED forward voltage and resistor drop — to about ±2 LSB, i.e. ±10 mV on a 5 V reference, plus the reference error; the USB 5 V rail used as reference can be off by several percent, so measure AVcc with the multimeter and scale, or use the internal 1.1 V reference with a measured calibration. A divider with a high source impedance (above roughly 10 kΩ) needs a slow sample or a buffer. (2) Time — input capture at 62.5 ns resolution (one 16 MHz clock period, my arithmetic) with absolute accuracy set by the clock: fine for DHT22 pulse widths and for timing an RC charge between two thresholds with the analog comparator. The repository already has an Uno sketch for timing an RC (scripts/bench/rc_timer/), which is this method.
- The DHT22 bit timings commonly quoted (about 26-28 µs high for a 0, about 70 µs for a 1, each after about 50 µs low) are widely repeated but were not confirmed from the datasheet copies retrieved; verify before using them as pass/fail windows.

### Gaps
- Current India prices for NanoVNA-H/H4 and for FX2 logic-analyser clones were not found (only EU/US listings); the DSO138 kit was not found at all.
- No independent bandwidth measurements of the FNIRSI pocket scopes were retrieved.
- No source was found for whether sigrok ships a DHT/AM230x decoder; I believe it does (decoder "am230x") but this is unverified.
- No reputable write-up of NanoVNA TDR on short PCB traces was retrieved; the resolution argument above is my own.
- MAX485 driver rise time and the ATmega328P datasheet's own ADC and timer tables were not fetched.
- Rigol/Hantek entry-scope prices in India were not retrieved.

---

## 7. Functional validation and experiment design (A/B boards, controls)

### Takeaway
"The board works" is weak evidence about routing on circuits this slow, because almost any connected routing
works. The informative experiment compares the generated routing against a hand-routed reference and a breadboard
on the same measurements, and includes a deliberately bad board to show the measurements can detect a routing
fault at all.

### Cited Findings
- The fab's free electrical test covers opens and shorts only — [JLCPCB Flying probe test FAQ](https://jlcpcb.com/quote/pcbOrderFaq/Flying%20probe%20test)
- Five boards of a design cost about USD 2, so three design variants cost about USD 6 plus one shipping charge — [Zbotic order guide](https://zbotic.in/how-to-order-pcb-from-jlcpcb-and-pcbway-india-cost-guide/)
- Resistance changes under about 5% are treated as "no change" in daisy-chain coupon practice — [Atlas PCB, test coupon design](https://www.atlaspcb.com/pcb-test-coupon-design-ipc-standards/)

### Inferences
- Bring-up checklist (standard hobby practice, my wording): (1) visual inspection of each bare board against the layout render; (2) bare-board continuity/isolation per section 2, and power-to-ground resistance; (3) solder power parts only, apply power through a current-limited source or a series resistor, check rail voltages and idle current; (4) add the MCU, confirm it programs; (5) add one block at a time (LED, divider, RC, DHT22, RS-485) and test each before the next; (6) record every reading with instrument and range. The project's own build-check sheets (docs/BUILD_CHECK_SHEETS.md) already cover power-off resistance and powered voltage readings for wiring faults, so the PCB procedure can reuse them.
- Three-arm design, all from one order: A = generated placement and routing; B = same schematic, same placement, hand-routed (or routed by an established tool such as freerouting) as the reference; C = breadboard or perfboard with the same parts. Use the same individual components moved between arms where practical, or measure each resistor and capacitor first, so component tolerance is not mistaken for a routing effect.
- Negative control D = deliberately bad routing, to prove the measurement can see something: minimum-width power trace made several times longer than needed; no ground return near the DHT22 data line; RS-485 A and B split far apart with a long stub; the bypass capacitor placed far from the MCU. If A, B and D all give the same numbers, the honest conclusion is "these measurements cannot distinguish routing quality on this circuit", not "the routing is good".
- Measurements that can separate the arms at this budget: rail voltage drop under load at the far end of the power trace (millivolts, by section 3's method); trace resistance per net vs the Board IR's predicted squares; divider ratio and RC time constant against calculation from the measured component values; DHT22 read error rate over a few thousand reads and pulse-width margins from the logic analyser; RS-485 frame error rate over a long run at the highest baud rate that works on a real cable.
- Expected outcome, stated in advance: for DC and kilohertz-range circuits, A, B and C should agree within component tolerance, and only D should differ, mainly in voltage drop. That result supports a narrow claim — the generated routing is electrically equivalent to a reference for these circuits — and no claim about EMC, high-speed behaviour or manufacturability at volume.
- Write the pass/fail thresholds down before measuring (pre-registration in the small), since the project already grades simulation at a fixed 15% tolerance.

### Gaps
- No published example of a hobby-scale A/B routing experiment with a negative control was found; the design above is my own proposal and should be presented as such.
- No sourced bring-up checklist was retrieved (EEVblog/Hackaday write-ups were suggested but not fetched within the call budget).
- Typical DHT22 and RS-485 error rates on good boards, to set a baseline, were not found.

---

## 8. How many boards and repeats; writing down uncertainty

### Takeaway
Five boards from one order is enough to show repeatability within a batch but says nothing about another batch or
fab; state it that way. Uncertainty can be written honestly with two numbers per reading: the meter's specification
and the observed spread of repeats.

### Cited Findings
- Cheap-meter specification format: ±(percent of reading + digits), e.g. ±(0.5% + 2) on DC volts and ±(0.8% + 2) on resistance for the UT33D+ — [Toolboom UT33D+](https://toolboom.com/en/digital-multimeter-uni-t-ut33dplus), [TME UT33D+](https://www.tme.eu/dk/en/details/ut33d+/portable-digital-multimeters/uni-t/)
- Retail listings for the same meter family disagree on the 200 mV range specification, so the manual for the exact meter owned must be used — [goodstore.lv UT33D](https://goodstore.lv/en/product/universalais-meritajs-ut-33d-uni-t)
- Probe contact pressure changes low-resistance readings — [Industrial Monitor Direct, Kelvin probe note](https://industrialmonitordirect.com/ko/blogs/knowledgebase/kelvin-probe-pressure-effect-on-4-wire-resistance-measurement-accuracy)
- The minimum fab order is 5 pieces at the promotional price — [Zbotic order guide](https://zbotic.in/how-to-order-pcb-from-jlcpcb-and-pcbway-india-cost-guide/)

### Inferences
- Simple recipe: for each quantity take at least 5 repeats, lifting and re-placing the probes each time; report the mean, the standard deviation of the repeats (repeatability), and the meter's specification limit computed for that reading and range. Example for a 49.0 mV reading on a 200 mV range at ±(0.5% + 2 digits of 0.1 mV): ±(0.245 + 0.2) = ±0.45 mV. Combine independent contributions as the root of the sum of squares; for R = V/I add the relative uncertainties of V and I the same way. Report as "R = 98 mΩ ± 4 mΩ (meter specification, not calibrated)".
- A cheap meter's specification is the maker's claim for a new instrument; none of this equipment is calibrated. Two cheap cross-checks: read a 0.1% reference resistor and a fresh voltage reference module (both a few tens of rupees to a few hundred), and compare two different meters on the same quantity. Disagreement larger than the specifications means the specifications cannot be trusted.
- Number of boards: measure all five of each variant. With n = 5 the standard deviation is itself only known to roughly ±35%, so quote the range (min-max) as well as the mean. If all five generated boards and all five reference boards overlap on every measurement while the bad-routing control does not, that is a credible small claim. One board is an anecdote; five from one panel is "repeatable within one batch from one fab". A second order at a different fab is the cheapest way to extend the claim, about INR 500-800 more.
- Separate three things in the write-up: instrument uncertainty (specification), repeatability (probe placement, temperature), and board-to-board variation (process). The coupon in section 5 measures the third directly.
- The project's existing 15% tolerance for simulation-vs-bench is loose compared with what these methods achieve for ratios and DC voltages (1-3%), and about right for absolute trace resistance against a nominal-thickness calculation.

### Gaps
- No source was fetched for a simple uncertainty-budget method (e.g. the GUM or a university lab guide); the recipe above is standard practice from general knowledge and should be cited to such a guide in the final report.
- No data were found on board-to-board resistance variation within a cheap-fab batch.
- Prices of reference resistors and voltage-reference modules in India were not retrieved.

---

## 9. Free or cheap access to better instruments

### Takeaway
India has a national equipment-sharing portal (I-STEM) open to students and any citizen, but it is aimed at
research facilities and bookings may carry a fee; the realistic free route for a bench oscilloscope and supply is
the developer's own university electronics lab.

### Cited Findings
- I-STEM is a national portal of the Office of the Principal Scientific Adviser that helps researchers locate R&D facilities; any Indian citizen who intends to use research and testing facilities for experimentation, prototype development, testing or validation can be a user — [I-STEM about page](https://www.istem.gov.in/support/about-us), [PSA I-STEM page](https://www.psa.gov.in/CMS/web/i-stem)
- Booking flow: register as a researcher/user, request a listed instrument, the operator approves, then payment and invoicing are arranged with the operator; each request gets a 10-digit Facility Booking Record number — [I-STEM User Handbook](https://www.istem.gov.in/assets/user_handbook/I-STEM%20User%20Handbook.pdf), [I-STEM Quick Reference Guide](https://www.istem.gov.in/uploads/banner/Quick_Reference_Guide_for_Users.pdf)
- The portal has an R&D infrastructure map for locating facilities by place — [I-STEM infrastructure map](https://www.istem.gov.in/rd-infrastructure-map)

### Inferences
- The mention of payment and invoicing in the booking flow means I-STEM access is not necessarily free; it suits a one-off need for a specialised instrument (a thermal camera, an LCR meter, a bench VNA) more than routine scope use.
- The user's email context suggests a university affiliation; a department electronics or measurements lab will have 50-100 MHz oscilloscopes, bench supplies with current limit, function generators and bench multimeters, which cover every measurement in these notes that exceeds the hobby kit (rise times, RS-485 differential waveforms with two channels, RC filter Bode sweep, a current-limited heating test). Asking a lab instructor for supervised bench time is the highest-value zero-cost step.
- One afternoon on a two-channel bench scope plus function generator would also close the project's own outstanding simulation accuracy gate for the RC filter (cutoff within 15% of ngspice), which currently has no bench record.

### Gaps
- No search was completed for makerspaces, FabLabs, Atal Incubation/Tinkering centres or college-specific labs near the user, or for remote/shared labs (e.g. Virtual Labs, remote-instrument services); availability and cost are unknown.
- Whether basic instruments such as oscilloscopes are actually listed on I-STEM, and typical fees, was not confirmed.
- The user's actual institution and its lab-access policy are assumptions, not findings.

---

## Summary budget table (for the writer; every figure is cited above or marked as not sourced)

| Item | Cost | Status |
|---|---|---|
| 5 boards x up to 3 variants + coupon strip, JLCPCB, economy shipping | about USD 9-14 (INR 750-1,200) before any duty | board and shipping prices cited (section 1); total is my sum |
| Same from an Indian fab | about INR 400-800 per design | cited (section 1) |
| Multimeter with a 200 mV range | not priced here | gap |
| FX2 8-channel logic analyser | not priced here (believed a few hundred rupees) | gap |
| Pocket scope FNIRSI DSO152 / DSO-TC3 | INR 3,395 / INR 6,690 | cited (section 6); optional |
| NanoVNA-H / H4 | EUR 33 / EUR 47 ex-VAT abroad | cited (section 6); low value for this project |
| Bench supply, thermal camera, bench scope | above budget | borrow (section 9) |

Priority order implied by the findings: (1) order boards with coupon strip and A/B/control variants; (2) bare-board
continuity and isolation against the Board IR netlist; (3) four-wire resistance on coupons and router nets;
(4) functional bring-up with logic-analyser timing and Arduino DC/time measurements; (5) borrowed bench scope for
the RC filter and RS-485 waveforms. Heating tests and all RF-style trace measurements are optional or unnecessary.
