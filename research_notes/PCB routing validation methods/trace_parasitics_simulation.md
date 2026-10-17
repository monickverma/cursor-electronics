# Validating the electrical behaviour of PCB traces by simulation with free/open-source tools (as of Oct 2026)

Reader context: 2-layer, 1.6 mm FR-4, 1 oz copper, Arduino-class boards (LED, 1 kHz RC filter, divider, DHT22 on a cable, MAX485 node); schematic already simulated in ngspice; Python A* router; Windows 11 with WSL/Docker; no commercial tools.

Conventions used in these notes:
- "Cited Findings" carry a link. Anything I computed myself, or state from standard textbook knowledge without having fetched a source in this session, is under "Inferences" and labelled so.
- Worked numbers assume: w = 0.25 mm, l = 50 mm, t = 35 um, h = 1.6 mm, FR-4 er = 4.5, copper rho = 1.68e-8 ohm.m at 20 C.

---

## 1. Closed-form estimates (R, L, C, Z0, vias) and their accuracy; worked numbers for 0.25 mm x 50 mm, 1 oz

### Takeaway
DC resistance is the one trace parasitic that closed-form maths gets right to within copper-thickness tolerance (about 96 mohm for the reference trace); L, C and Z0 are good to a few percent only when a continuous ground plane sits under the trace, and on a 2-layer board with no plane the "microstrip" numbers do not apply at all, because inductance is set by the loop the return current actually takes.

### Cited Findings
- Sheet resistance of 1 oz copper is about 0.48 mohm/square at 20 C (rho 1.68e-8 ohm.m over a nominal 34.8 um); resistance = sheet resistance x (length / width), "counting squares". "1 oz" is nominal: plating and etching shift the finished thickness. — [JLCPCB copper weight article](https://jlcpcb.com/blog/304-copper-weight-and-trace-width-finding-the-optimal-balance); [DigiKey forum, Resistance Values of PCBs](https://forum.digikey.com/t/resistance-values-of-pcbs/2082)
- Temperature scaling: R(T) = R20 x [1 + 0.00393 x (T - 20)]. An alternative convention in circulation uses 1.72 uohm.cm at 25 C with 0.00385/C; the two differ by reference temperature, so pick one and use it consistently. — [DigiKey forum, Resistance Values of PCBs](https://forum.digikey.com/t/resistance-values-of-pcbs/2082)
- IPC-2141 microstrip formula is less accurate than Wheeler/Wadell-type equations; Altium cites a Polar Instruments comparison in which Wheeler's equations were within about 0.7% of numerical solutions, roughly ten times better than IPC-2141. The IPC-2141 form is still what many online calculators implement. — [Altium, Clearing Up Trace Impedance Calculators and Formulas](https://resources.altium.com/p/clearing-up-trace-impedance-calculators-and-formulas)
- Burkhardt, Gregg and Staniforth (Polar Instruments, "Calculation of PCB Track Impedance") report a surface-microstrip geometry where IPC-2141 was about 30% low while the Wadell-based result was within about 0.3% of a numerical field solution; they note IPC-2141 is "quoted as 2% accurate" but diverges from Wadell for some configurations. — [Scribd copy of the IPC 1999 paper](https://www.scribd.com/doc/50700390/IPC1999)
- Wheeler-type equations are piecewise in w/h, so they are discontinuous and less trustworthy where width is close to height. — [Altium, same article](https://resources.altium.com/p/clearing-up-trace-impedance-calculators-and-formulas)
- KiCad's built-in PCB Calculator has a Trans Line tool (microstrip model cites H. A. Atwater, "Simplified Design Equations for Microstrip Line Parameters", Microwave Journal 1989), and notes its models are frequency-dependent so they disagree with simpler formulas at high frequency. It also has Track Width (IPC-2221) and Via Size tools (electrical and thermal properties of a plated through-hole). — [KiCad nightly PCB Calculator manual](https://docs.kicad.org/master/en/pcb_calculator/); [KiCad 9.0 manual](https://docs.kicad.org/9.0/en/pcb_calculator/pcb_calculator.html)
- For a trace over a solid plane, inductance per unit length = Z0 x delay per unit length (and, by the same relation, C per length = delay / Z0), so no separate rule of thumb is needed once Z0 and delay are known. — [Howard Johnson, Trace Inductance (sigcon.com)](https://sigcon.com/Pubs/news/3_8.htm)
- Rules of thumb for trace inductance disagree: about 1 nH/mm is widely quoted for a thin lead or trace, while Altium quotes 5-10 nH per inch (0.2-0.4 nH/mm); Cadence's position is that there is no simple rule because inductance is tied to impedance, delay and return path. — [Altium, PCB trace inductance and width](https://resources.altium.com/p/pcb-trace-inductance-and-width-how-wide-too-wide); [Cadence, Is there a PCB trace inductance rule of thumb](https://resources.system-analysis.cadence.com/blog/msa2021-is-there-a-pcb-trace-inductance-rule-of-thumb)
- Via inductance closed form (Johnson): L = 5.08 h [ln(4h/d) + 1] nH with h, d in inches; length dominates, diameter matters little; Johnson calls it a gross approximation because it ignores where the return current flows. Cadence's "2.5 pH per mil" rule is only right for one aspect ratio. — [Howard Johnson, Via Inductance (sigcon.com)](https://www.sigcon.com/Pubs/news/6_04.htm); [Cadence, via inductance rule of thumb](https://resources.system-analysis.cadence.com/blog/msa2021-is-there-a-via-inductance-rule-of-thumb)
- Clemson (Hubing et al.) technical report gives closed-form partial-inductance estimates for simple trace, via and plane configurations. — [Clemson CVEL TR01-1-030](https://cecas.clemson.edu/cvel/pdf/TR01-1-030.pdf)

### Inferences (my calculations; formulas are the standard textbook forms, not fetched in this session)
Worked numbers, 0.25 mm x 50 mm x 35 um trace:

| Quantity | Formula | Value |
|---|---|---|
| DC resistance, 20 C | rho l / (w t) = 200 squares x 0.48 mohm | **96 mohm** |
| DC resistance, 85 C | x (1 + 0.00393 x 65) | **about 120 mohm** |
| Effective permittivity (Hammerstad, w/h = 0.156) | (er+1)/2 + (er-1)/2 [(1+12h/w)^-0.5 + 0.04(1-w/h)^2] | **about 3.0** |
| Z0, Hammerstad narrow-strip (t = 0) | 60/sqrt(eeff) x ln(8h/w + w/4h) | **about 136 ohm** |
| Z0, IPC-2141 | 87/sqrt(er+1.41) x ln(5.98h/(0.8w+t)) | **about 133 ohm** |
| Propagation delay | sqrt(eeff)/c = 5.8 ns/m | **0.29 ns** for 50 mm |
| Loop inductance over a plane | Z0 x delay = about 0.79 nH/mm | **about 39 nH** |
| Capacitance to plane | delay / Z0 = about 42 pF/m | **about 2.1 pF** |
| Partial self-inductance, no plane (Ruehli/Grover flat-strip form 2l[ln(2l/(w+t)) + 0.5 + 0.2235(w+t)/l] nH, l in cm) | | **about 64 nH** |
| Via, 1.6 mm long, 0.3 mm drill, inductance (Johnson) | 5.08 h [ln(4h/d)+1] | **about 1.3 nH** |
| Via barrel resistance, assuming 25 um plating | rho h / (pi (d+tp) tp) | **about 1 mohm** |

- For this geometry IPC-2141 and Hammerstad agree to about 3%; the 30%-off IPC-2141 cases reported by Polar are at other width/height ratios. A 0.25 mm trace on 1.6 mm FR-4 is a roughly 135 ohm line; a 50 ohm microstrip on 1.6 mm FR-4 needs a trace about 3 mm wide, which is why nobody does controlled impedance on this stackup for ordinary signals.
- The dominant error in DC resistance is not the formula but finished copper thickness and etch undercut (order 10-20% on cheap boards) plus temperature (+25% from 20 C to 85 C). The dominant error in Z0/C is FR-4 er (4.2-4.8 by supplier and frequency) and actual core thickness.
- On a 2-layer hobby board without a ground pour under the trace, there is no microstrip: use partial inductance (the 64 nH row) or a field solver with the real return conductor. The "about 1 nH/mm" rule is the no-plane figure; the "0.2-0.4 nH/mm" rule is the thin-dielectric multilayer figure; the 0.79 nH/mm above is in between because 1.6 mm is a thick dielectric. That is the reason the published rules of thumb disagree.

### Gaps
- I did not fetch the Hammerstad-Jensen 1980 paper or Wadell's book; the stated Hammerstad-Jensen accuracy (commonly quoted as better than 0.2% for Z0 over a wide w/h range) is not verified here. No source found comparing Hammerstad-Jensen directly against IPC-2141 on 1.6 mm FR-4.
- The validity range usually quoted for IPC-2141 (0.1 < w/h < 2.0) and the Ruehli/Grover partial-inductance form are from memory; no URL fetched.
- Via plating thickness (25 um) is an assumption; fabs commonly specify 18-25 um.
- The exact formulas inside KiCad's Via Size tool were not retrieved (they are in the KiCad source, not the manual).

---

## 2. When do trace parasitics matter? Rules of thumb and an assessment of each circuit

### Takeaway
For every circuit in the reader's catalogue the routed traces change the simulated behaviour by far less than component tolerance; the only places layout matters on these boards are the decoupling-capacitor loop, the crystal's stray capacitance, and the return path of the fastest MCU edges, and none of those is in the schematic simulation today.

### Cited Findings
- One-sixth rule: if the propagation delay of an interconnect exceeds one-sixth of the signal rise time, lumped analysis is no longer valid and it must be treated as a transmission line. — [NI, Transmission Lines](https://www.ni.com/docs/en-US/bundle/ni-hsdio/page/transmission-lines.html)
- The threshold is contested: published "critical length" fractions range from 1/2 to 1/20 of the rise time, usually with no stated context; Siemens treats 1/3 as common and 1/6 as conservative; Altium argues against quoting any critical-length rule and for checking allowable impedance deviation instead. — [Altium, Why is there a transmission line critical length](https://resources.altium.com/p/why-there-transmission-line-critical-length); [Altium, Can we all stop quoting the critical length rule](https://resources.altium.com/p/can-we-all-stop-quoting-critical-length-rule); [Siemens, Fundamentals of SI part 2](https://blogs.sw.siemens.com/electronic-systems-design/2010/05/03/fundamentals-of-si-part-2-transmission-lines/)
- RS-485 stub rule (TI): the electrical length (round-trip delay) of a stub should be under one-tenth of the driver's 10/90 rise time, L_stub <= 0.1 x tr x v x c; TI calls it a conservative guideline. Tabulated examples: 100 ns rise time allows about 7 ft, 250 ns about 19 ft, 500 ns about 38 ft on 78%-velocity cable. — [TI SLLA272D, RS-485 Design Guide](https://www.ti.com/document-viewer/lit/html/SLLA272D/GUID-D689C67D-ED23-477F-BC1E-F680139458AB); [TI THVD1428 datasheet, stub length](https://www.ti.com/document-viewer/THVD1428/datasheet/stub-length-sllsei9862)
- Crystal oscillators: the Pierce oscillator node is high impedance and the swing is under about 1 V, so it is susceptible to coupled noise; keep crystal traces as short and wide as possible and keep switching lines away. — [Atmel AVR186, Best practices for the PCB layout of oscillators](https://www.insidegadgets.com/wp-content/uploads/2013/02/Best-Practices-for-the-PCB-layout-of-oscillators.pdf)
- Microchip: put load capacitors beside the crystal on the same side, ground pour around it, and keep the oscillator within about 12 mm (half an inch) of the pins. — [Microchip, External Oscillator Layout Guidance](https://onlinedocs.microchip.com/oxy/GUID-E48B4A26-F201-4F0A-BCBA-16461582816A-en-US-4/GUID-AA04B64F-3C38-4E1C-8B51-49DE3CFE2419.html)
- Decoupling without power planes: put a local capacitor between each device's supply and ground pins and minimise the area of the capacitor-device loop; even a well-mounted capacitor on a board with planes has 1-3 nH of connection inductance. — [LearnEMC, Decoupling for boards without power planes](https://learnemc.com/decoupling-for-boards-without-power-planes); [LearnEMC, EMC question of the week 2021-05-17](https://learnemc.com/qotw-210517)

### Inferences (my arithmetic, using the section 1 numbers for the 0.25 mm x 50 mm trace)

| Circuit | Trace effect | Size | Verdict |
|---|---|---|---|
| RC low-pass, 1 kHz (R 1590 ohm, C 100 nF) | 96 mohm in series with R; 2 pF in parallel with C; 39-64 nH has 0.25-0.4 mohm reactance at 1 kHz | cutoff shifts by about 0.006% (R) and 0.002% (C); resistor is 1%, capacitor 10% | Negligible by three orders of magnitude. The first trace effect to appear is far above the passband: series L with C resonates near 2 MHz, heavily damped by R |
| LED, 10 mA | IR drop 0.96 mV; dissipation about 10 uW; IPC-2221 temperature rise far below 0.01 C | LED Vf spread is hundreds of mV | Negligible |
| Voltage divider | Trace R adds to each leg | 0.1 ohm against kilo-ohms: under 0.01% | Negligible unless the divider is tens of ohms or the load current returns through a shared ground trace (then compute the ground IR drop) |
| DHT22 single-wire, pull-up 4.7k-10k | 2 pF of PCB trace against tens to hundreds of pF of cable; adds about 10-20 ns to a rise time measured in microseconds | under 1% of the cable's contribution | Negligible; the cable (already modelled by the generator) is the whole story |
| RS-485, 9600-115200 baud, 50 mm PCB stub | Bit time 8.7 us at 115200. Stub limit from TI's rule with a 15 ns driver edge and v of about 0.58c on FR-4 is about 0.26 m; with a slew-limited driver it is metres | 50 mm is 5x inside even the fast-edge limit; 0.1 ohm against a 54-60 ohm bus load is 0.2% | Negligible on the PCB. Termination, bias and the cable decide the waveform |
| 16 MHz crystal | Wavelength in FR-4 is about 11 m, so lambda/10 is over 1 m: never a transmission line. But about 0.4 pF per 10 mm of trace over a plane adds to an 18-22 pF load capacitor | a few percent of CL per cm, i.e. a few ppm of frequency pull; plus noise pickup at a high-impedance node | Matters modestly; it is a layout rule (short, guarded, under 12 mm), not something worth extracting. Not in the SPICE netlist anyway |
| Decoupling capacitor loop | 10 mm of trace each way with no plane is roughly 10 nH; with 100 nF it resonates near 5 MHz (2 nH would give 11 MHz); a 20 mA / 5 ns edge across 10 nH is 40 mV of rail bounce | tens of mV on a 5 V rail | The most real effect on the list, and still benign for an ATmega328P. It grows for the ESP32 (faster edges, 300+ mA radio bursts): there it is worth a check |

- Edge-rate screening for these MCUs: with 5.8 ns/m on this stackup, a 5 ns edge (AVR-class GPIO) has a one-sixth critical length of about 145 mm; a 2 ns edge (ESP32/STM32 at high drive strength) about 58 mm. Hobby boards with traces under 50 mm are lumped for AVR and borderline-lumped for fast 32-bit GPIO.
- Frequency-domain equivalent (lambda/10): 50 mm is lambda/10 at about 350 MHz on this board. Nothing in the catalogue has intentional content there; only edge harmonics do.
- Current threshold: IR drop becomes a 1% effect on a 5 V rail (50 mV) at about 0.5 A through the reference trace; temperature rise reaches 10 C at about 0.9 A (section 5). Below about 100 mA neither is visible.
- Honest summary for the product: a back-annotated simulation of these five templates will report "no change" every time. Its value is as a proof obligation that scales (a claim such as "trace R shifts the cutoff by less than 0.01%" computed from the Board IR), not as a bug finder.

### Gaps
- MAX485 driver rise/fall time and DHT22 bit timing were not looked up in this session; the 15 ns edge is an assumption for a non-slew-limited transceiver. Check against the datasheet figures the project already holds.
- AVR/ESP32 GPIO edge rates (5 ns, 2 ns) are typical values, not sourced here; they depend on load and drive-strength setting.
- I did not find Howard Johnson's or Bogatin's own text for the knee-frequency (0.5/tr or 0.35/tr) rule in this session.
- ST AN2867 (crystal oscillator design guide) was searched for and not retrieved.

---

## 3. Open-source field solvers and extraction tools

### Takeaway
For this reader the tools that earn their keep are plain Python formulas, FastHenry (inductance and AC resistance of the real routed geometry, including no-plane loops), FasterCap or atlc (capacitance), and a DC FEM/FDM tool for IR drop; full-wave solvers (openEMS, Palace, Elmer's wave solvers) answer questions that begin near 100 MHz and are overkill for a 1.6 mm two-layer board at kHz to low MHz.

### Cited Findings
- **openEMS**: free and open FDTD field solver, scripted from Matlab/Octave or Python; Windows builds on the GitHub releases page, Linux build instructions provided. — [openEMS project site](https://www.openems.de/)
- **gerber2ems (Antmicro)**: Python script that takes Gerbers, drill files and stackup and builds an openEMS model to compute S-parameters and trace impedance; combined with PyBERT for eye diagrams. Repo examples are slices of Antmicro's open Signal Integrity Test Board and selected examples ship VNA measurements (vna.csv) for comparison. It pins a specific openEMS commit as the last tested. — [antmicro/gerber2ems](https://github.com/antmicro/gerber2ems); [Antmicro blog, Nov 2023](https://antmicro.com/blog/2023/11/open-source-signal-integrity-analysis)
- gerber2ems limitations stated by its authors in 2023: ports and terminations placed by hand, uniform mesh, passives approximated through geometry. A 2025 update describes an adaptive grid that is dense near the simulated geometry and sparse elsewhere, and a 2024 post describes automated net selection via a KiCad wrapper. — [Antmicro blog, Nov 2023](https://antmicro.com/blog/2023/11/open-source-signal-integrity-analysis); [Antmicro blog, Jul 2025](https://antmicro.com/blog/2025/07/recent-improvements-to-antmicros-signal-integrity-simulation-flow); [Antmicro blog, Jul 2024](https://antmicro.com/blog/2024/07/automated-pcb-trace-selection-for-si-simulation)
- Antmicro's posts say the test board lets them verify simulation against measurement but publish no error figures in the blog text. — [Antmicro blog, Nov 2023](https://antmicro.com/blog/2023/11/open-source-signal-integrity-analysis)
- **Other KiCad to openEMS routes**: pcbmodelgen (KiCad PCB to Octave/openEMS model with automatic mesh lines) appears unmaintained, with users reporting no output on later files; KiCad's native HyperLynx export feeds openEMS through hyp2mat, with reported losses (copper thickness ignored, graphic-shape copper ignored); a STEP to FreeCAD to STL route works with KiCad 9; a 2025 forum thread asking for the best KiCad 9 workflow closed without a clear plugin answer. Qucs-RFlayout (Open-RFlab) exports microstrip schematics to KiCad layouts and openEMS scripts. — [KiCad forum, Export PCB board to OpenEMS](https://forum.kicad.info/t/export-pcb-board-to-openems/7619); [KiCad forum, Best workflow to simulate KiCad PCB in OpenEMS](https://forum.kicad.info/t/best-workflow-to-simulate-kicad-pcb-in-openems/66410); [Open-RFlab](https://github.com/Open-RFlab/Open-RFlab)
- **FastHenry / FasterCap / FastFieldSolvers**: FastHenry computes frequency-dependent self and mutual inductance and resistance of conductors of arbitrary shape; FasterCap is a 2D/3D capacitance extractor; the FastFieldSolvers bundle is published as open source under permissive (MIT or LGPL) licences. — [FastFieldSolvers software page](https://fastfieldsolvers.com/software.htm); [FastHenry User Guide](https://www.fastfieldsolvers.com/Download/FastHenry_User_Guide.pdf)
- **EM Workbench for FreeCAD**: GUI front end; supports FastHenry input creation, beta support for VoxHenry, Python-only support for FasterCap input. — [EM Workbench README (mirror)](https://gitea.suzanne.soy/suzanne.soy/EM-Workbench-for-FreeCAD/raw/branch/master/README.md)
- **KiCad to FastHenry in practice**: no packaged exporter was found; a published project reads a .kicad_pcb with KiCad's bundled Python (pcbnew), writes FastHenry input for the nets of a buck converter's commutation loop on both layers, and reports about 5.3 nH. The FastHenry sources are legacy K&R C and need extra compiler flags. — [cadlab.io project, spice/extract](https://cadlab.io/project/28816/main/files/spice/extract)
- **atlc**: finite-difference 2D solver for transmission lines of arbitrary cross-section and any number of dielectrics; outputs Z0, L and C per metre, velocity factor; input is a bitmap of the cross-section; GPLv2; upstream stable release dates from 2003 (distro packages at 4.6.1). — [atlc on SourceForge](https://sourceforge.net/p/atlc); [GNU directory entry](https://ftp.gwdg.de/pub/gnu/www/directory/all/atlc.html)
- **scikit-rf**: `MLine` models a microstrip from width, thickness, height and er, derived from the Qucs technical documentation, with a Djordjevic/Svensson wideband Debye dielectric model for causal time-domain response; it warns that its loss model is over-optimistic when the strip is thinner than 3 skin depths. — [scikit-rf MLine source](https://scikit-rf.readthedocs.io/en/latest/_modules/skrf/media/mline.html); [scikit-rf Media tutorial](https://scikit-rf.readthedocs.io/en/latest/tutorials/Media.html)
- **Elmer FEM**: multiphysics FEM (electrostatics, static current conduction, magnetics, heat); GPL v2 or later; precompiled Windows binaries. — [Elmer FEM, Wikipedia](https://en.wikipedia.org/wiki/Elmer_FEM_solver); [CSC Elmer page](https://research.csc.fi/eosc-services/elmer)
- **Palace (AWS)**: open-source parallel 3D full-wave FEM code built on MFEM and libCEED, released for quantum-hardware electromagnetics. — [LLNL news on Palace](https://software.llnl.gov/news/2023/02/22/aws)
- **Sparselizard**: a KiCad branch using it provides current density, voltage drop and capacitance simulation in a native KiCad interface (mentioned in forum discussion; not a mainline KiCad feature). — [KiCad forum, Open source power analysis tool](https://forum.kicad.info/t/open-source-power-analysis-tool/21652)
- **KiCad PCB Calculator**: built-in, no install; transmission-line, track-width, via tools (see section 1). — [KiCad PCB Calculator manual](https://docs.kicad.org/master/en/pcb_calculator/)

### Inferences (comparison table; licence, platform and runtime entries marked * are from my own knowledge, not verified this session)

| Tool | Computes | Input | Licence | Windows | Learning curve / runtime | Fit for this reader |
|---|---|---|---|---|---|---|
| Python closed forms | R, Z0, L, C, delay, IR drop, temp rise | Board IR segments | own code | yes | hours / microseconds | **Use first.** Sufficient for all five templates |
| KiCad PCB Calculator | same, interactively | typed dimensions | GPL* | yes | minutes | Good cross-check of the Python formulas |
| FastHenry | L, mutual L, AC R (skin/proximity), magnetoquasistatic, arbitrary 3D filaments, optional ground plane | text .inp (nodes, segments with w/h, ports) | permissive (MIT-style*) | yes (FastFieldSolvers binaries*; or WSL build) | a day / under a second for a few nets | **Best value.** The Board IR's track segments map one-to-one onto FastHenry segments; gives loop inductance without assuming a plane |
| FasterCap / FastCap | C matrix, 2D or 3D, with dielectrics | text panel files | LGPL* / MIT-style* | yes* | 1-2 days (panel meshing of dielectric interfaces is fiddly) / seconds to minutes | Worth it only if coupling capacitance between specific nets matters |
| atlc | per-length Z0, L, C of any 2D cross-section | bitmap | GPLv2 | builds under WSL* | hours / seconds to minutes | Simple way to get L', C' of a trace with no plane or an offset return; old code |
| scikit-rf | network algebra, microstrip media, S-parameter to time domain, plotting vs measured Touchstone | Python | BSD* | yes | hours | Glue: compare solver output with formulas or VNA files |
| openEMS (+ python-openEMS, pyEMS, gerber2ems) | full-wave S-parameters, Z0 vs f, fields, radiation | Octave/Python script (CSXCAD); Gerbers via gerber2ems | GPLv3* | yes (binaries) | 1-2 weeks to trustworthy results; minutes to hours per trace, mesh-dependent | **Overkill** below about 100 MHz. FDTD time step is set by the smallest cell, so simulating kHz behaviour directly is impractical |
| Elmer FEM | static conduction (IR drop), electrostatics (C), heat, also wave equation | mesh (Gmsh etc.) + .sif | GPL v2+ | yes | 1-2 weeks; needs a meshing pipeline | Capable for DC and thermal; heavy for what a 2D resistor grid does |
| Palace | 3D full-wave / eigenmode / electrostatic / magnetostatic FEM | mesh + JSON | Apache-2.0* | WSL/Docker* | steep; HPC-oriented | Overkill |
| Sparselizard | general FEM library (C++) | code | GPL* | WSL* | steep | Overkill unless building a custom solver |
| Qucs-S | schematic-level simulator with microstrip and coupled-line models, drives ngspice | GUI | GPL* | yes | hours | Useful for sanity-checking a line model; not an extractor |
| Sonnet Lite | planar MoM | GUI | **freeware, not open source***; size limits | Windows only | days | Outside the reader's constraints for automation; fine as a one-off reference |
| pcb-rnd / Ringdove | PCB editor with scripting and exporters | own formats | GPL* | partial* | n/a | No extraction capability confirmed in this session (see Gaps) |

- Typical runtimes are my estimates for a 2-layer board with a handful of nets on a laptop, not published benchmarks.
- A quasi-static solver (FastHenry/FasterCap) is physically the right tool whenever the board is much shorter than lambda/10, which is always true here; full-wave adds radiation and delay effects that are absent at these frequencies.

### Gaps
- Licences marked * (openEMS GPLv3, CSXCAD LGPL, scikit-rf BSD-3, Palace Apache-2.0, Sparselizard GPL, Qucs-S GPL, FastHenry/FastCap MIT-style, FasterCap LGPL) are from memory; the fetched openEMS and FastFieldSolvers pages confirmed only "free and open" and "MIT or LGPL" respectively. Verify each LICENSE file before bundling.
- No published quantitative openEMS-versus-VNA error figures were found; the closest is the measured vna.csv data in the gerber2ems examples, which the reader would have to plot themselves. FR-4 simulation-versus-measurement papers found used CST, HFSS or AWR, not openEMS.
- No published measurement validation of FastHenry on PCB traces was retrieved (it is widely used as a reference in the literature, but I did not fetch a paper).
- Nothing reliable found on pcb-rnd/Ringdove field-solver exporters, on pyEMS's current maintenance status, or on a maintained Elmer exporter for KiCad.
- Current version numbers and last-release dates for openEMS, FasterCap and Palace were not retrieved.

---

## 4. Back-annotation: from a routed net to R/L/C in an ngspice netlist

### Takeaway
For these boards one lumped pi section per routed net (series R + L, half the capacitance at each end) is already more resolution than the physics needs; ngspice also offers lossless (T), lossy (O/LTRA, Y/TXL) and coupled (P/CPL, or K-coupled inductors) line elements, which become appropriate only when a trace's delay approaches a tenth of the edge time.

### Cited Findings
- The ngspice manual's transmission-line chapter covers lossless lines (6.1), lossy lines/LTRA (6.2), uniform distributed RC lines/URC (6.3) and KSPICE lossy lines (6.4: 6.4.1 single lossy line TXL, 6.4.2 coupled multiconductor line CPL). Pole-zero analysis does not support transmission lines. — [ngspice HTML manual](https://ngspice.sourceforge.io/docs/ngspice-html-manual/manual.xhtml)
- ngspice's DEVICES file lists the distributed elements CPL ("Simple Coupled Multiconductor Lines", KSPICE), LTRA, TRA, TXL ("Simple Lossy Transmission Line", KSPICE, class Y) and URC; older copies of the file describe CPL as undocumented and note possible memory leaks. — [ngspice DEVICES file (Debian sources)](https://sources.debian.org/src/ngspice/24-1/DEVICES)
- KSPICE implements lossy and coupled multiconductor lines by recursive convolution, and its authors present TXL and CPL as replacements for SPICE3's LTRA; a forum post quoting the manual says they are preferred because they run faster. — [Berkeley KSPICE page](https://ptolemy.berkeley.edu/projects/embedded/Software/spice/kspice.html); [EasyEDA forum quoting the manual](https://easyeda.com/forum/topic/Add_lossy__coupled_transmission_lines_-53Xf8qI0U)
- A third-party TXL example: `Y1 in 0 out 0 ymod LEN=2` with `.model ymod txl R=... L=... G=... C=... length=...`, flagged by its author as usable in transient analysis only. — [EasyEDA component note](https://easyeda.com/component/bd1eff2c4a12436ebf5307364b34e8c2)
- `ngmultidec` ships with ngspice and generates subcircuits for coupled multiconductor lines out of uncoupled lossy lines, from length, capacitance, resistance, conductance and coupling parameters. — [ngmultidec man page](https://linux.die.net/man/1/ngmultidec)
- Per-unit-length L and C for any line model follow from Z0 and delay (L' = Z0 x td', C' = td' / Z0). — [Howard Johnson, Trace Inductance](https://sigcon.com/Pubs/news/3_8.htm)

### Inferences
Proposed flow for the reader's pipeline (deterministic, consistent with "compilers translate the IR"):

1. From the Board IR, take each net's routed segments (layer, width, length) and vias. Split the net at pads into branches (pad-to-junction, junction-to-pad).
2. Per branch compute R (squares x sheet resistance at the chosen temperature, + about 1 mohm per via), and either L', C' from the microstrip formulas when there is a plane beneath, or L from FastHenry / partial-inductance formulas when there is not. C to "ground" without a plane is small (sub-pF) and can be bounded rather than computed.
3. Emit a second netlist beside the ideal one, in which each schematic node is split into one node per pad and each branch becomes a subcircuit, e.g. a pi section:
   ```spice
   * net DHT22_DATA, branch U1.pad4 -> R1.pad1 : 0.25 mm x 50 mm, 1 oz, over plane
   R_TR_1 n_u1_4 n_tr1 0.096
   L_TR_1 n_tr1  n_r1_1 39n
   C_TR_1a n_u1_4 0 1.05p
   C_TR_1b n_r1_1 0 1.05p
   ```
4. Run both netlists through the existing grader and report the delta per claim. A design passes "layout does not change behaviour" when every graded quantity moves by less than a declared fraction of its tolerance.

ngspice element forms (from my knowledge of the manual's chapter 6 and the inductor section; the chapter text could not be fetched this session because the single-page manual is about 4.8 MB, so check the syntax against the PDF before coding):
- Lossless: `Txxx n1 n2 n3 n4 Z0=136 TD=0.29n`
- Lossy LTRA: `Oxxx n1 n2 n3 n4 mname` with `.model mname ltra r=... l=... c=... g=0 len=...` (per-unit-length values; supported combinations are RLC, RC, LC and RG)
- KSPICE single line: `Yxxx n1 0 n2 0 mname len=...` with `.model mname txl r=... l=... g=... c=... length=...`
- KSPICE coupled lines: `Pxxx in1 in2 ... gnd out1 out2 ... gnd mname len=...` with a `cpl` model carrying R, L, G, C matrices
- Lumped coupling between two trace inductors: `Kxxx L_TR_1 L_TR_2 0.3` (coefficient k = M / sqrt(L1 L2)); mutual capacitance as an ordinary capacitor between the two nets. FastHenry returns M directly.

Choosing the model and the segment count:
- Standard guidance (Bogatin-style; not fetched this session): one lumped LC section is valid while the branch delay is under about a tenth of the fastest rise time; beyond that use n >= 10 x (branch delay / rise time) sections, or switch to a T/O/Y element. Equivalent frequency form: 10 sections per shortest wavelength of interest.
- Applied here: a 50 mm branch has 0.29 ns delay. With 5 ns edges, delay/tr = 0.06, so n = 1. With 2 ns edges, 0.15, so n = 2. A 300 mm trace at 2 ns would need about 9 sections, at which point a single `T` or `Y` element is simpler and faster.
- For AC analysis of the RC filter or divider, n = 1 is exact for all practical purposes up to tens of MHz.
- Prefer lumped RLC for this project: it works in DC, AC and transient alike, parses back into exact elements for the sympy/z3 proof layer, and avoids the transient-only caveat reported for TXL and the small-time-step cost that any 0.3 ns delay element imposes on a millisecond-scale transient.
- Cost warning: adding nH and pF elements to a circuit simulated over milliseconds makes the system stiff; ngspice handles it but may shorten time steps. Keep the back-annotated run as a separate, optional job (Celery, as for all ngspice runs).

### Gaps
- Exact parameter names and AC-analysis support for TXL and CPL in the current ngspice release were not verified from the manual text; the "transient only" remark comes from a third-party component note.
- The segment-count rule is quoted from memory of Bogatin's "Signal and Power Integrity - Simplified"; no URL fetched.
- No open tool was found that performs layout-to-SPICE back-annotation for KiCad boards end to end (the cadlab.io FastHenry script is the nearest example and is project-specific).

---

## 5. Free power-integrity / DC IR-drop tools and trace temperature rise

### Takeaway
Several free KiCad-native DC solvers now exist (padne, the kipy-based zone-resistance plugin, nikfemm, kicad_pdn_fem3d), all hobby-grade and thinly validated; for boards drawing tens of mA the hand calculation is enough, and IPC-2221 (what KiCad implements) is a conservative bound for temperature rise.

### Cited Findings
- **padne**: KiCad-native DC power-delivery analysis using a 2.5D finite-element solution of Laplace's equation; sources and sinks are declared as text directives in the schematic; interactive voltage-drop and current-density viewer; GPL-3.0; distributed as a Linux x64 all-in-one binary (about 200 MB, bundles KiCad), via pipx, or from source; no validation against measurement documented in the README. The author describes it as a side project that he has used on high-current designs. — [atx/padne on GitHub](https://github.com/atx/padne); [KiCad forum announcement](https://forum.kicad.info/t/presenting-padne-a-tool-for-dc-power-delivery-network-analysis/64966)
- **KiCad zone-resistance / PDN plugin**: DC and AC resistance, power and via currents of copper fills with a multi-layer finite-difference solver, built on the IPC API (kipy); requires KiCad 10.0.1 or later. — [KiCad forum, Resistance and PDN plugin](https://forum.kicad.info/t/resistance-and-pdn-plugin/70648)
- **nikfemm + KiCad plugin**: dependency-free, fast 2.5D approach (coupled 2D simulations per layer); a reviewer notes the plugin assumes two copper layers of 35 um. — [KiCad forum, FEM Voltage drop simulator](https://forum.kicad.info/t/fem-voltage-drop-simulator/57710)
- **kicad_pdn_fem3d**, a Sparselizard-based KiCad branch, FEMM (free 2D solver; import the plane as DXF; much manual setup) and FreeCAD FEM via fcad_pcb are the other free routes discussed; FreeCAD's thermal-analogy workaround shows voltage but not current density. — [KiCad forum, Open source power analysis tool](https://forum.kicad.info/t/open-source-power-analysis-tool/21652); [KiCad forum, FEM Voltage drop simulator, page 2](https://forum.kicad.info/t/fem-voltage-drop-simulator/57710?page=2)
- IPC-2221 trace current formula: I = k x dT^0.44 x A^0.725 (A in square mils, dT in C), k = 0.048 external, 0.024 internal; valid for 0-35 A, widths to 10.16 mm, rises 10-100 C, 0.5-3 oz copper; it ignores nearby copper and planes and so over-sizes traces. — [Altium, IPC-2221 calculator article](https://resources.altium.com/it/p/ipc-2221-calculator-pcb-trace-current-and-heating); [mbedded.ninja IPC-2221A calculator](https://ninjacalc.mbedded.ninja/calculators/electronics/pcb-design/track-current-ipc2221a)
- KiCad's Track Width tool uses the IPC-2221 (formerly IPC-D-275) formulas. — [KiCad 9.0 PCB Calculator manual](https://docs.kicad.org/9.0/en/pcb_calculator/pcb_calculator.html)
- IPC-2152 is based on newer test data covering copper weight, internal/external layers, board thickness and environment, and is published as charts, not one formula; online "IPC-2152 formulas" are third-party curve fits. One source says it typically allows 1.5-2x the IPC-2221 current for the same rise. — [Cadence, IPC-2152 vs IPC-2221](https://resources.system-analysis.cadence.com/blog/ipc-2152-vs-ipc-2221-which-to-use-for-pcb-thermal-analysis); [smps.us PCB calculator](https://smps.us/pcb-calculator.html); [Altium, Using an IPC-2152 calculator](https://resources.altium.com/p/using-ipc-2152-calculator-designing-standards)
- Elmer FEM provides heat-transfer and static-conduction solvers under GPL v2+ with Windows binaries, i.e. an open route to coupled electro-thermal analysis. — [Elmer FEM, Wikipedia](https://en.wikipedia.org/wiki/Elmer_FEM_solver)

### Inferences (my calculations)
- Reference trace (0.25 mm, 1 oz, external; cross-section 13.6 sq mil), IPC-2221: 10 C rise at about **0.87 A**; 20 C at about 1.2 A. At 50 mA the formula gives about 0.015 C, at 10 mA under 0.001 C (both far below the formula's 10 C validity floor, i.e. "no measurable rise").
- IR drop of the reference trace: 0.96 mV at 10 mA, 4.8 mV at 50 mA, 48 mV at 0.5 A. A full ESP32 transmit burst (hundreds of mA) through 50 mm of 0.25 mm trace costs tens of mV: the first case in the catalogue where a wider power trace is a real recommendation.
- For a router that produces tracks, not pours, a DC "solver" is a resistor network: each segment is a resistor, each via about 1 mohm, each load a current source. That is an ngspice `.op` on an auto-generated netlist, or a few lines of numpy. A 2D FEM/FDM tool only adds value when current spreads in copper pours.
- All four KiCad-native tools need a `.kicad_pcb`, which the project plans (step B4); until then the resistor-network approach works directly on the Board IR. padne on Windows means WSL or Docker.
- Validation of any of these: compare against the analytic resistance of a rectangle (squares x sheet resistance) and of a known annulus or L-bend before trusting a pour result.

### Gaps
- No published measurement validation (4-wire resistance or thermal camera) was found for padne, nikfemm, the zone-resistance plugin or kicad_pdn_fem3d.
- No open-source implementation of the actual IPC-2152 charts was confirmed; available calculators are curve fits with unverified licences.
- No free, PCB-specific thermal solver (board import to temperature map) was identified beyond general FEM packages (Elmer, FreeCAD FEM).
- KiCad version compatibility of padne and Windows support were not stated in its README.

---

## 6. Signal-integrity checks relevant to small boards: return path, crosstalk, RS-485 termination

### Takeaway
On a 1.6 mm two-layer board the useful SI checks are geometric rather than simulated: does every signal have a nearby return conductor (loop area), is each decoupling loop small, are fast edges kept away from high-impedance nodes; crosstalk formulas built for multilayer boards say adjacent traces are strongly coupled here, but short lengths and slow edges keep the absolute numbers small.

### Cited Findings
- Crosstalk between microstrip traces is commonly approximated as proportional to 1/(1 + (s/h)^2), with s the spacing and h the height above the plane; it ignores width and thickness but is reasonably accurate. Below a quarter wavelength, crosstalk is proportional to coupled length. Spacing of at least 3x the height above the plane generally keeps worst-case crosstalk at -20 dB or lower. — [LearnEMC, EMC question of the week 2025-09-29](https://learnemc.com/qotw-250929)
- Howard Johnson uses K = 1/[1 + (D/H)^2] as the crosstalk factor for closely spaced single-ended traces, with a separate proportionality constant covering structure, rise time and coupled length. — [Howard Johnson, Differential Crosstalk (sigcon.com)](https://www.sigcon.com/Pubs/news/3_20.htm); [Mentor note hosted by MSU](https://web.pa.msu.edu/hep/atlas/l1calo/hub/hardware/components/circuit_board/mentor_crosstalk_single_end_and_diff.pdf)
- With a ground plane, a decoupling capacitor's current returns in the plane directly beneath, forming the smallest possible loop; without planes the designer must minimise the capacitor-device loop explicitly, and place bulk capacitance where power enters the board. — [LearnEMC, Decoupling for boards without power planes](https://learnemc.com/decoupling-for-boards-without-power-planes)
- RS-485: stubs should have a round-trip delay under one-tenth of the driver rise time (formula and table in section 2); the TI design guide covers termination and stub length together. — [TI SLLA272D](https://www.ti.com/document-viewer/lit/html/SLLA272D/GUID-D689C67D-ED23-477F-BC1E-F680139458AB)
- Oscillator nodes: keep switching lines away from the crystal connections; use a guard ring or ground pour tied to the oscillator ground. — [Atmel AVR186](https://www.insidegadgets.com/wp-content/uploads/2013/02/Best-Practices-for-the-PCB-layout-of-oscillators.pdf); [Microchip oscillator layout guidance](https://onlinedocs.microchip.com/oxy/GUID-E48B4A26-F201-4F0A-BCBA-16461582816A-en-US-4/GUID-AA04B64F-3C38-4E1C-8B51-49DE3CFE2419.html)

### Inferences
- Applying K = 1/(1+(D/H)^2) with H = 1.6 mm: at 0.5 mm spacing K = 0.91, at 1.6 mm K = 0.5, and the 3H rule would demand 4.8 mm between traces. On this stackup the bottom-layer "plane" is too far away to shield neighbours, so adjacent traces couple mostly to each other. The formula gives only the geometric factor; the absolute level scales with coupled length over edge length, which is about 0.06 for 50 mm and 5 ns.
- A lumped estimate is more informative here: with an assumed 1 pF mutual capacitance between two 50 mm neighbours (assumption, order of magnitude; FasterCap or atlc would give the real figure), a 5 V edge injects into (a) the RC filter output node, bypassed by 100 nF: about 50 uV; (b) a DHT22 data line with about 100 pF of cable and a 10k pull-up: about 45 mV, decaying in about 1 us; (c) a crystal pin with about 20 pF: about 240 mV, which is why that is the node layout guides fence off.
- Checks the PCB engine could compute deterministically from the Board IR, in rough order of value: (1) loop area or loop inductance of each IC's decoupling path (pad-to-capacitor-to-pad, FastHenry or the partial-inductance formula); (2) for each signal net, distance to its nearest return conductor and the enclosed loop area; (3) parallel-run length and spacing between any fast-edge net and any high-impedance net (crystal, sensor line, divider tap); (4) ground-return sharing: IR drop on ground segments shared by a load current and a measurement reference; (5) RS-485: termination present at the connector end, stub from transceiver to connector far below the TI limit, bias network next to the transceiver.
- RS-485 termination itself (120 ohm at each cable end, fail-safe bias) is a cable-level decision the project's generator already makes; the PCB contributes only a short stub, which at these baud rates is immaterial (section 2).
- A ground pour on the bottom layer under signal traces converts most of these concerns into non-issues and makes the microstrip formulas of section 1 valid; recommending it is cheaper than simulating its absence.

### Gaps
- The 1 pF mutual capacitance is an assumed order of magnitude, not extracted; no closed-form source for coplanar trace-to-trace capacitance on a thick two-layer board was retrieved.
- Johnson's value for the proportionality constant and his original text (High-Speed Digital Design) were not fetched.
- No source was found that quantifies crosstalk specifically for two-layer 1.6 mm boards without a plane.

---

## 7. How trustworthy are these simulations without a measurement, and how is a solver setup validated?

### Takeaway
Without a measurement, a field-solver result is trustworthy only to the extent that the same setup reproduces structures with known analytic answers and is insensitive to mesh and boundary changes; for FR-4 the material data (er, loss tangent, real copper thickness), not the solver, is usually the largest error, so quasi-static R/L/C can be believed to roughly 5-10% while absolute S-parameter agreement needs a fabricated test coupon.

### Cited Findings
- Recommended validation procedure for EM simulation against measurement: model measured (not nominal) trace widths, dielectric thickness and via sizes; use measured er and loss tangent because datasheet values are often the largest error source for FR-4; calibrate the VNA (SOLT, TRL or ECal) and verify with a check standard; keep radiation boundaries more than a quarter wavelength from the structure and size ports correctly; model or de-embed the connector launch, for instance with TRL standards fabricated on the same board. — [RF Essentials, How do I validate EM simulation results against measured data](https://rfessentials.com/rf-knowledge-base/how-do-i-validate-my-electromagnetic-simulation-results-against-measured-data/)
- Suggested canonical test structures: a straight 50 ohm microstrip 5-10 cm long for attenuation and phase velocity, plus an open and a short stub pair for extracting material properties. — [RF Essentials, validating a PCB simulation model with S-parameters](https://rfessentials.com/rf-knowledge-base/how-do-i-validate-my-pcb-simulation-model-by-comparing-s-parameters-to-measured-/)
- A ready-made open benchmark exists: the gerber2ems examples are slices of Antmicro's open-hardware Signal Integrity Test Board, some with VNA data (vna.csv) alongside, so an openEMS setup can be compared with measurement without building anything; `stub_short` is a small starting case. — [antmicro/gerber2ems](https://github.com/antmicro/gerber2ems)
- Closed-form impedance equations themselves are validated against numerical field solutions (Wheeler within about 0.7%, Wadell within about 0.3% for the cited geometry), which makes them usable as the analytic reference for a solver check. — [Altium](https://resources.altium.com/p/clearing-up-trace-impedance-calculators-and-formulas); [Polar Instruments paper (Scribd copy)](https://www.scribd.com/doc/50700390/IPC1999)
- Practitioners using low-cost VNAs (LibreVNA) with openEMS openly ask how to establish confidence in model-to-hardware agreement for 1.3-2.4 mm traces, i.e. this is an unsolved-by-default problem at hobby level, not a documented success. — [EDAboard thread](https://edaboard.com/posts/1772842/)
- scikit-rf's own microstrip model flags a regime (strip thinner than 3 skin depths) where its loss prediction is over-optimistic: an example of a tool declaring its validity limits. — [scikit-rf MLine source](https://scikit-rf.readthedocs.io/en/latest/_modules/skrf/media/mline.html)

### Inferences
A measurement-free validation ladder for this project (each step checks the tool against something with a known answer):

1. **DC resistance**: straight trace = squares x sheet resistance (exact). Any DC solver must reproduce it to under 1%.
2. **Capacitance**: parallel-plate with fringing bounded; microstrip C' from Hammerstad/Wadell versus FasterCap or atlc on the same cross-section; expect agreement within 1-2%.
3. **Inductance**: FastHenry versus the closed-form partial inductance of a straight rectangular bar and of a rectangular loop; microstrip L' = Z0 x td versus FastHenry with a ground plane.
4. **Line impedance**: 2D solver (atlc) and, if used, openEMS on a straight microstrip versus Hammerstad-Jensen/Wadell and KiCad's calculator; expect about 1-3%.
5. **Convergence**: halve the mesh (or double the filament count / panel count) and move the boundaries outward; the answer should change by less than the accuracy being claimed.
6. **Conservation checks**: passivity and reciprocity of S-parameters; DC limit of the AC result equals the DC resistance; L' x C' consistent with the expected velocity.
7. **Cross-solver agreement**: two independent methods (for example FastHenry and the closed form, or openEMS and atlc) on the same structure.
8. **External benchmark**: reproduce the gerber2ems test-board example against its vna.csv.

- What stays unknown after all of that: the board's actual er and copper thickness, solder-mask loading, etch profile and plating. For the kHz to low-MHz circuits here these enter only through DC resistance (thickness, about 10-20%) and small capacitances (er, about 10%), and both effects are orders of magnitude below component tolerance, so the conclusion "the traces do not change behaviour" is robust to them even though any individual parasitic value is not accurate to better than about 10-20%.
- Fit to the project's own vocabulary: an extracted parasitic is a simulated figure with a declared scope (plane present or not, nominal copper, 20 C), not bench evidence. The cheapest real measurement that would turn it into evidence is a 4-wire resistance of one long trace on a fabricated board (checks sheet resistance) and a capacitance-meter reading between two nets (checks er and geometry); an RF coupon and VNA are unnecessary at these frequencies.
- Reporting a bound instead of a value is the honest form: "trace resistance at most 0.15 ohm at 85 C with -20% copper; cutoff shift at most 0.01%" survives every uncertainty listed.

### Gaps
- No published, quantitative openEMS-versus-measurement comparison on FR-4 microstrip with stated error figures was found; nor one for FastHenry/FasterCap on PCB traces. The accuracy ranges in the ladder (1-3%, 5-10%, 10-20%) are my engineering estimates, not cited figures.
- The RF Essentials pages are an unsigned knowledge-base, weaker than a textbook or IEEE source; the procedure they describe is standard practice but should not be cited as authoritative.
- No IPC or IEEE benchmark-geometry set for validating PCB field solvers (for example the IEEE P370 or IEEE EMC Society TC-9 benchmark problems) was retrieved in this session; they exist and would be the place to look for formal benchmark structures.
