# Gerber read-back LVS: re-extracting connectivity from fabrication files and comparing it to the intended netlist

Evidence labels used throughout:

- **[LOCAL]** = I ran it on this machine on 2026-10-09 (Windows 11, KiCad 10.0.1 `kicad-cli`, Python 3.13.7 venv with gerbonara 1.6.3, shapely 2.2.0, klayout 0.30.12, pygerber 2.4.3). Test board: KiCad's bundled demo `C:\Program Files\KiCad\10.0\share\kicad\demos\pic_programmer\pic_programmer.kicad_pcb` (2-layer, through-hole + 2 SMD pads, 244 plated hits, 7 NPTH, 4 zones, 111 named nets). Scripts and outputs are in the session scratchpad `C:\Users\KIIT\AppData\Local\Temp\claude\C--Users-KIIT\1802d7c8-9f91-48fb-90bd-5518ec52daf2\scratchpad\` (`scripts\lvs.py`, `scripts\kl_lvs.py`, `scripts\seed.py`, `pp\out\`). The scratchpad is temporary; copy the scripts if they are wanted.
- **[DOC]** = read in a fetched primary page this session.
- **[SNIPPET]** = only seen in a search-result summary; not opened. Treat as a lead, not a fact.
- **[INFERRED]** = my reasoning, not stated by a source.

Caveat on the local test: the Python used was 3.13, not the project's 3.11. One board, four seeded defects. It shows the pipeline works end to end; it is not a soundness proof.

---

## Q1. Most practical route to get fabrication files out of a custom Board IR

### Takeaway
Write `.kicad_pcb` text yourself and call `kicad-cli` as a subprocess: it is the only route that gives Gerber X2, Excellon, IPC-D-356, IPC-2581, ODB++ and a second-opinion DRC from one input, and it was verified working headless on this machine. The KiCad IPC API (kipy) cannot do this on KiCad 9/10 because it needs a running GUI and has no export calls.

### Cited Findings
- **[LOCAL]** `kicad-cli` 10.0.1 at `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe` produced Gerber, Excellon, Gerber-format drill, IPC-D-356, IPC-2581, ODB++ and DRC JSON from a bare `.kicad_pcb` with no GUI. Hand-edited `.kicad_pcb` files (segment removed, via removed, segment inserted by text splice) loaded and exported without complaint. The file header is `(kicad_pcb (version 20260206) (generator "pcbnew") (generator_version "10.0")`; tracks are `(segment (start x y) (end x y) (width w) (layer "F.Cu") (net "NAME") (uuid ...))` and vias `(via (at x y) (size s) (drill d) (layers "F.Cu" "B.Cu") ... (net "NAME"))`. Note nets are referenced **by name string**, not by integer index, in this format version. — command reference: [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)
- **[SNIPPET]** The IPC API in KiCad 9 and 10 "only supports communication with a running instance of the KiCad GUI"; headless mode via `kicad-cli api-server` is tagged for KiCad 11; the API in 9/10 "has no support for plotting or exporting files" and users are told to call `kicad-cli`. — [kicad-python docs](https://docs.kicad.org/kicad-python/kicad.html), [KiCad dev docs: IPC API for add-on developers](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/index.html), [kicad-python on PyPI](https://pypi.org/project/kicad-python/)
- **[SNIPPET]** A CI write-up exists on forcing the IPC API to run in CI with a live editor. — [adamws: Using the new KiCad IPC API in a CI environment](https://adamws.github.io/using-the-new-kicad-ipc-api-in-a-ci-environment/)
- **[LOCAL]** Gerbonara 1.6.3 metadata: `License-Expression: Apache-2.0`; depends on click, quart, rtree. `pip download gerbonara==1.6.3 --python-version 3.11` fails with "No matching distribution found". — [gerbonara on PyPI](https://pypi.org/project/gerbonara/) (search summary states "Requires Python >=3.12"; releases 1.6.1 Dec 2025, 1.6.2 Mar 2026, 1.6.3 Apr 25 2026)
- **[SNIPPET]** gerber-writer (by Karel Tavernier, the Gerber format's long-time editor at Ucamco) targets "100% compliance with revision 2023.08 of the Gerber Layer Format Specification"; Snyk calls maintenance inactive with the last version it knows from April 2024, PyPI shows a 0.4.3.3. — [gerber_writer GitHub](https://github.com/Karel-Tavernier/gerber_writer), [gerber-writer on PyPI](https://pypi.org/project/gerber-writer)
- **[SNIPPET]** kiutils: dataclass-based parser "for KiCad 6.0 and up"; no source found confirming KiCad 9/10 format support. — [kiutils GitHub](https://github.com/mvnmgrx/kiutils)
- **[SNIPPET]** kicad-skip: "optimized for schematics, with some enhanced support for important elements of PCB layout files". — [kicad-skip GitHub](https://github.com/psychogenic/kicad-skip)
- **[SNIPPET]** kicad-pycbnew (arXiv, Sept 2026): Python >=3.10 library that generates `.kicad_pcb` "directly through structured text output". Very new. — [arXiv 2609.27522](https://arxiv.org/html/2609.27522v1)
- **[SNIPPET]** pygerber: stable 2.4.3 (Mar 2025), 3.0.0a4 pre-release, MIT. **[LOCAL]** pip metadata confirms 2.4.3, MIT. — [pygerber GitHub](https://github.com/Argmaster/pygerber)

### Inferences
- **Route (a) `.kicad_pcb` + `kicad-cli` is the recommended primary route.** The s-expression subset needed for hobby 2-layer boards is small (header, layers, setup, nets-by-name, footprints with pads, segments, vias, Edge.Cuts graphics, optionally zones). Writing it with plain string formatting avoids depending on kiutils/kicad-skip, whose KiCad 10 status I could not confirm.
- **Route (b) pcbnew SWIG / kipy: reject for now.** kipy needs a GUI on 9/10. The legacy `pcbnew` SWIG module still ships with KiCad's bundled Python but ties the backend to KiCad's interpreter; I did not test it.
- **Route (c) direct Gerber writing: keep as a second, independent emitter later.** It removes KiCad from the trust chain for the artwork, but then nothing produces IPC-D-356/IPC-2581/ODB++ and you own aperture/attribute correctness. Gerbonara cannot be imported on the project's Python 3.11 (see finding above) so (c) with Gerbonara forces either a Python bump to 3.12+ or a subprocess in a separate interpreter.
- **Independence matters more than convenience here.** If `kicad-cli` writes both the Gerbers and the IPC-D-356, the D356 is KiCad's opinion of the nets, derived from the same `.kicad_pcb`. The "intended netlist" for the compare must come from Circuit OS's own IR (ref, pin, net), with pad positions, not from the D356. Use the D356 only as a cross-check that the `.kicad_pcb` writer carried net assignments correctly.
- Licence: invoking `kicad-cli` (GPL-3.0-or-later) as a separate process from an AGPL-3.0 backend is aggregation, not linking. This is my reading of the usual FSF position; I did not fetch a licence source this session.

### Gaps
- pcbflow, SKiDL, atopile, tscircuit, circuit-synth, KicadModTree: not researched this session. No finding either way.
- Linux/Docker behaviour of `kicad-cli` 10 was not tested (only Windows). Whether KiCad 10 has an official headless Docker image was not checked.
- KiCad 11 release status unknown; the headless `api-server` would change the answer for route (b).
- kiutils/kicad-skip last-commit dates were not checked.

---

## Q2. Exact kicad-cli commands, flags, exit codes, JSON report shape, gotchas

### Takeaway
All seven exports and DRC work from one `.kicad_pcb`; DRC returns exit 5 on violations only when `--exit-code-violations` is passed, and exit 3 when the board fails to load. Three gotchas were found by running it: `--schematic-parity` silently degrades without a schematic, the IPC-D-356 is in a different coordinate frame from the Gerbers when an aux origin is set, and D356 net names are cut to their last 14 characters.

### Cited Findings
Flags below are from `kicad-cli <cmd> --help` on 10.0.1 **[LOCAL]** and match [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html) **[DOC]**.

- **Gerbers:** `kicad-cli pcb export gerbers -o OUTDIR -l "F.Cu,B.Cu,F.Mask,B.Mask,Edge.Cuts" [--no-x2] [--no-netlist] [--use-drill-file-origin] [--precision 5|6 (default 6)] [--no-protel-ext] [--check-zones] [--disable-aperture-macros] [--subtract-soldermask] [--board-plot-params] board.kicad_pcb`. X2 and netlist attributes are **on by default**; `--no-x2` / `--no-netlist` turn them off. A `.gbrjob` JSON job file is written alongside.
- **Drill:** `kicad-cli pcb export drill -o OUTDIR --format excellon|gerber --drill-origin absolute|plot --excellon-units mm|in (default mm) --excellon-zeros-format decimal|suppressleading|suppresstrailing|keep --excellon-oval-format route|alternate --excellon-separate-th [--generate-map --map-format pdf|gerberx2|ps|dxf|svg] [--generate-report --report-path F] board.kicad_pcb`. `--excellon-separate-th` yields `<name>-PTH.drl` and `<name>-NPTH.drl`.
- **IPC-D-356:** `kicad-cli pcb export ipcd356 -o out.d356 board.kicad_pcb`. No other options exist.
- **IPC-2581:** `kicad-cli pcb export ipc2581 -o out.xml [--version B|C (default C)] [--units mm|in] [--precision 6] [--compress] board.kicad_pcb`.
- **ODB++:** `kicad-cli pcb export odb -o OUT [--compression none|zip|tgz (default zip)] [--units mm|in] [--precision 2] board.kicad_pcb`.
- **Position:** `kicad-cli pcb export pos -o out.pos --side front|back|both --format ascii|csv|gerber --units in|mm (default **in**) [--use-drill-file-origin] [--smd-only] [--exclude-dnp] board.kicad_pcb`.
- **DRC:** `kicad-cli pcb drc --format json -o drc.json --schematic-parity --severity-all --exit-code-violations [--all-track-errors] [--refill-zones [--save-board]] [--units mm|in|mils] board.kicad_pcb`. Docs: `--exit-code-violations` gives 0 if no violations, 5 if any.
- **[LOCAL] Exit codes observed:** clean board with the flag: 0. Board with violations or unconnected items with the flag: 5. Nonexistent input file: 3 ("Failed to load board"). All successful exports: 0.
- **[LOCAL] DRC JSON shape** (`$schema: https://schemas.kicad.org/drc.v1.json`): top-level keys `$schema`, `coordinate_units` ("mm"), `date`, `kicad_version`, `source`, `included_severities` (list), `ignored_checks` (list of `{description, key}`), and three arrays `violations`, `unconnected_items`, `schematic_parity`. Each entry is `{type, severity, description, items: [{description, pos: {x, y}, uuid}, ...]}`. Example types seen: `shorting_items` ("Items shorting two nets (nets /CLOCK-RB6 and /DATA-RB7)"), `tracks_crossing`, `track_dangling`, `via_dangling`, `hole_clearance`, `starved_thermal`, `silk_edge_clearance`; opens appear in `unconnected_items` with type `unconnected_items` and description "Missing connection between items". Positions are in board coordinates (Y down, positive), not the Gerber frame.
- **[LOCAL] Gotcha 1, schematic parity:** on a board with no usable schematic the CLI prints "Failed to fetch schematic netlist for parity tests. Schematic parity tests require a fully annotated schematic.", still writes the report with `schematic_parity: []`, and the exit code is driven by the other violations only. An empty `schematic_parity` array therefore does not mean parity passed. With the demo project's schematic present it printed "Found 0 schematic parity issues".
- **[LOCAL] Gotcha 2, D356 coordinate frame:** the D356 coordinates are relative to the board's `aux_axis_origin` with Y pointing up, in units of 0.0001 inch. The demo has `(aux_axis_origin 62.23 153.67)`; pad JP1-1 at board (147.358, 97.79) appears as `X+033515Y+022000`. Default Gerbers use absolute coordinates with Y negated (`X..Y-110.49`). Mapping used in the prototype: `x_gbr = x356*25.4 + 62.23`, `y_gbr = y356*25.4 - 153.67`. With the wrong frame, 150 of 253 records landed off copper and the rest produced a nonsense 50-net "short".
- **[LOCAL] Gotcha 3, D356 net names:** 10.0.1 writes upper-cased names cut to the **last 14 characters** with no alias table: `/pic_sockets/VCC_PIC` became `OCKETS/VCC_PIC`, `unconnected-(U5-RA0-Pad17)` became `(U5-RA0-PAD17)`. `grep -c NNAME` on the file is 0, and the header is only `P  CODE 00`, `P  UNITS CUST 0`, `P  arrayDim   N`. This contradicts the current KiCad source as summarised from Doxygen, which describes `P NNAME` alias lines, a `P JOB` line and `P VER IPC-D-356A`. — [KiCad Doxygen export_d356.cpp](https://docs.kicad.org/doxygen/export__d356_8cpp_source.html). The Doxygen page tracks the development branch, so the difference is probably a version difference; I did not confirm which release introduced aliases.
- **[LOCAL] Gotcha 4, file names:** Gerber file names follow the board's user layer names, not canonical ones. The demo renames F.Cu/B.Cu to `top_layer`/`bottom_layer`, so `-l "F.Cu,B.Cu"` produced `pic_programmer-top_layer.gtl` and `pic_programmer-bottom_layer.gbl`. Read `%TF.FileFunction` or the `.gbrjob` `FilesAttributes` instead of globbing names.
- **[LOCAL] Gotcha 5, drill plating in Excellon:** plating is carried only in comments (`; #@! TF.FileFunction,Plated,1,2,PTH` and per-tool `; #@! TA.AperFunction,Plated,PTH,ViaDrill` / `ComponentDrill`). Gerbonara 1.6.3 reported `is_plated_tristate = None`, `plating_type = "unknown plating"` for this file. Parse the comment yourself or use `--format gerber`, where the drill file has a real `%TF.FileFunction,Plated,1,2,PTH,Drill*%` header.
- **[SNIPPET]** KiCad 10's `kicad-cli` has no Specctra DSN export verb. — [Konnect issue #473](https://github.com/mixelpixx/Konnect/issues/473)

### Inferences
- Set no aux origin in the generated `.kicad_pcb`, or pass `--use-drill-file-origin` to gerbers and `--drill-origin plot` to drill so every file shares one frame. I did not test those two flags; the frame mismatch itself is verified.
- Always pass `--exit-code-violations` and still parse the JSON; treat exit 3 and any exit other than 0/5 as an infrastructure failure, not a DRC result.
- To use `--schematic-parity` Circuit OS would need to emit a `.kicad_sch` too. Simpler: skip parity and compare against the IR directly.

### Gaps
- Exit codes other than 0, 3 and 5 are not documented on the CLI page and were not observed.
- Behaviour when severity flags are omitted is not stated in the docs; locally, omitting them still reported violations.
- `--refill-zones` and `--check-zones` were not exercised. If the IR emits unfilled zones, fills must be computed before plotting or the Gerber will lack the pour.

---

## Q3. What X2, IPC-D-356, IPC-2581 and ODB++ carry

### Takeaway
KiCad 10 writes net (`.N`), pin (`.P`) and component (`.C`) attributes into copper Gerbers by default, and a full pad-to-net table can be read back from them, but attributes are declarations by the CAD tool, not evidence of copper connectivity. The check has to derive connectivity from geometry and use the attributes or D356 only as labels to compare against.

### Cited Findings
- **[SNIPPET]** Ucamco's 2016 netlist extension attaches "the component reference designator, pin number and net name to the component pads in the outer copper layers" and a net name to "any conducting object on a copper layer"; attributes "do not affect the image" and a reader that does not need them "simply skip[s]" them. — [Ucamco: Gerber component and netlist attributes (PDF)](https://www.ucamco.com/files/downloads/file_en/189/gerber-component-and-netlist-final_en.pdf)
- **[SNIPPET]** "A Gerber reader will generate the correct image even if it ignores some or all attributes." Newest spec revision found in search is 2023-08. — [Gerber Layer Format Specification 2023-08 (PDF)](https://ucamco.com/files/downloads/file_en/456/gerber-layer-format-specification-revision-2023-08_en.pdf)
- **[SNIPPET]** KiCad's `GBR_NETLIST_METADATA` defines TO.P (pad), TO.N (net), TO.C (component); `.P` is for flashed pads on external copper layers. — [KiCad Doxygen GBR_NETLIST_METADATA](https://docs.kicad.org/doxygen/classGBR__NETLIST__METADATA.html)
- **[LOCAL]** KiCad 10.0.1 bottom-copper Gerber of the demo: file attributes `%TF.FileFunction,Copper,L2,Bot*%`, `%TF.FilePolarity,Positive*%`, `%TF.SameCoordinates,Original*%`; aperture attributes `ComponentPad` (27), `Conductor` (8), `SMDPad` (2), `ViaPad` (1), `NonConductor` (1). Object attributes look like `%TO.P,P3,1,1_1*%` followed by `%TO.N,/VPP{slash}MCLR*%`. Zone fills are `G36/G37` regions preceded by `%TA.AperFunction,Conductor*%` and `%TO.N,GND*%`. Unconnected pads carry names like `unconnected-(P3-Pad2)`; no-net objects get an empty `%TO.N,*%` or `N/C`.
- **[LOCAL]** The same file contains **zero** `%LPC` statements despite 4 zones with thermal reliefs: KiCad plots fills as already-resolved dark polygons. Gerbonara reported every object dark (786 of 786).
- **[LOCAL]** Gerbonara 1.6.3 exposes these as `obj.attrs`, e.g. `{'.P': ('C1', '1'), '.N': ('VCC',)}`. Counts on the bottom layer: 240 flashes with `.N`+`.P`, 6 flashes with `.N` only (vias), 305 lines with `.N`, **232 lines with no attributes**, and for the 3 Region objects `attrs` was not a dict at all (it returned the dataclass `Field` descriptor). So in 1.6.3, region net attributes are not readable through `Region.attrs`.
- **[LOCAL]** A netlist recovered from X2 flash labels alone gave 113 distinct names over 490 pad/via flashes; the same board's ODB++ cadnet lists 112 entries including `$NONE$`.
- **[DOC]** IPC-D-356 record layout as written by KiCad (`export_d356.cpp`): `"%03d%-14.14s %-6.6s%c%-4.4s%c"` = op code, 14-char net, 6-char refdes, `-` if a pin follows, 4-char pin, `M` for mid-point; hole `"D%04d%c"` with `P` plated / `U` unplated; `"A%02dX%+07dY%+07dX%04dY%04dR%03d"` = access code, X, Y, feature X size, Y size, rotation; then `" S%d"` soldermask code. Op codes: 327 SMD pad, 317 through pad or via, 367 NPTH, 307 blind/buried via, 027 continuation. Access code: 00 both sides, 01 front, back = copper layer count. `P UNITS CUST 0` means 0.0001 inch and degrees. Records padded to 80 columns; file ends `999`. Vias are emitted as mid-points with refdes `VIA`. **Tracks are not emitted** (no 378 conductor records). — [KiCad Doxygen export_d356.cpp](https://docs.kicad.org/doxygen/export__d356_8cpp_source.html)
- **[LOCAL]** Real records: `317/CLOCK-RB6       VIA        MD0236PA00X+050250Y+017000X0630Y0000R000S3`, `327VCC              JP1   -1          A02X+033515Y+022000X0118Y0118R000S1`, `367N/C              P101        D1693UA00X+006000Y+007000X1693Y0000R000S0`. The demo produced 244 `317`, 2 `327`, 7 `367`. Back-side SMD is `A02` on a 2-layer board.
- **[SNIPPET]** Other D356 codes: 099 test-point location tied to the previous record, 017/027 continuation; header starts with JOB then CODE, UNITS, TITLE, NUM, REV, VER. The official document is IPC-D-356B, superseding 356A (1998) and 356 (1992). — [IPC-D-356B table of contents](https://www.ipc.org/TOC/IPC-D-356B.pdf), [MSU-hosted IPC-356A net list summary](https://web.pa.msu.edu/hep/atlas/l1calo/hub/hardware/components/circuit_board/ipc_356a_net_list.pdf) (PDF returned empty to the fetcher; not read)
- **[SNIPPET]** A fab rejected a D356 that used 327 with blank net columns; it expects `N/C` in columns 4-6 for isolated points and strict 80-column layout. — [Autodesk forum: IPC-D-356 ULP issues](https://forums.autodesk.com/t5/fusion-electronics-forum/ipc-d-356-ulp-issues/m-p/13946333)
- **[SNIPPET]** "The IPC-D-356 format limits signal names to 14 characters maximum. Longer names are truncated, which can create duplicates." — [PCBSync: Understanding IPC-D-356](https://pcbsync.com/ipc-d-356/)
- **[SNIPPET]** Fab-side use: the flying-probe / fixture test checks the bare board against this netlist; via holes "are generally omitted, either because they are mid-points on the net, or because they are covered by non-conductive mask". — [I-Connect007: The Bare (Board) Truth: Netlist Mismatches Redux](https://iconnect007.com/article/55930/the-bare-board-truth-netlist-mismatches-redux/55933/design)
- **[LOCAL]** IPC-2581C from KiCad carries nets on features: `<Set net="/CLOCK-RB6" padUsage="VIA">`, `<Set net="/DATA-RB7">`, plus `<PinRef componentRef="POLY" pin="1"/>` entries, `<Component>`, `<Package>`, `<PadStackDef>` and `<Stackup>`. Full, untruncated net names.
- **[LOCAL]** ODB++ from KiCad has `steps/pcb/netlists/cadnet/netlist`: a header `H optimize n staggered n`, a net table (`$1 VCC`, `$4 /VPP{slash}MCLR`, `$13 /pic_sockets/VCC_PIC`, full names), then "Netlist points" lines `net_index radius x y side ...` in mm. Also `steps/pcb/eda/data` and per-layer feature directories including `drill_plated_top_layer-bottom_layer` and `drill_non-plated_top_layer-bottom_layer`.

### Inferences
- **X2 attributes alone give a label map, never a connectivity proof.** A cut trace still carries `.N`. In the seeded-defect test the labels were unchanged on the cut board and only the geometry revealed the open.
- **Best label source, in order:** (1) Circuit OS's own IR pad table (ref, pin, net, x, y, side), which is independent of KiCad; (2) X2 `.P`/`.N` on pad flashes, which share the Gerber frame exactly and carry full names; (3) IPC-2581 or ODB++ cadnet for full names; (4) IPC-D-356 last, because of the 14-character truncation and frame shift found above.
- Comparing (1) against (2) is itself a useful check on the `.kicad_pcb` writer: every IR pad should find a flash with the same ref/pin/net at the same place.
- Because KiCad emits no `%LPC` for zone fills, the hobby-class extractor can start with dark-only union. It must still refuse or correctly handle a file that does contain clear polarity rather than silently ignore it.

### Gaps
- The exact spec wording for `.N`/`.P`/`.C` semantics and any revision after 2023-08 was not read; the PDFs were only seen in search summaries.
- IPC-D-356A column positions from the standard itself were not read (PDF fetch returned nothing); the layout above is KiCad's implementation, not IPC text. Records 378 (conductor), 379 (adjacency) and 389 (outline) are not described by any source I opened. Gerbonara's `Netlist` object does expose `conductors`, `adjacency` and `outlines` attributes **[LOCAL]**, which suggests it parses them.
- Whether KiCad writes `.N` on lines that appeared attribute-less (232 on the bottom layer) or whether those are zone outline/hatch strokes was not determined.

---

## Q4. Algorithms for geometric connectivity extraction

### Takeaway
A vector approach worked on the first attempt: convert every dark Gerber object to a Shapely polygon, `unary_union` per copper layer, treat each resulting polygon as one electrical island, join islands across layers wherever a plated hole touches copper on both, then check labels against islands. It ran in about 1.1 s on the demo board and found all four seeded defects.

### Cited Findings
- **[LOCAL] Pipeline that was run** (`scratchpad\scripts\lvs.py`, about 130 lines):
  1. `GerberFile.open()`; for each object call `to_primitives(unit)`; primitives seen were `Line` (656), `Circle` (182), `Rectangle` (90), `ArcPoly` (26). Gerbonara resolves aperture macros (KiCad's `RoundRect` macro) into these primitives.
  2. `Line` -> `LineString.buffer(width/2)`; `Circle` -> `Point.buffer(r)`; others -> `to_arc_poly()`, `approximate_arcs(max_error)` if any arc centre is set, then `Polygon(outline)`.
  3. `shapely.ops.unary_union` per layer -> list of polygons (355 top, 152 bottom), indexed with `STRtree`.
  4. Each PTH hit from the Excellon file is a disc of the tool diameter; `tree.query(disc, predicate='intersects')` on both layers; union-find over `(layer, polygon index)`. All 244 hits touched copper on at least two islands on the clean board.
  5. Each label point (pad centre, net name, side) is located in an island; `net -> set(islands)` with more than one island is an **open**, `island -> set(nets)` with more than one named net is a **short**.
- **[LOCAL] Results**

  | Board | KiCad DRC | Shapely extractor (X2 labels) | Shapely extractor (D356 labels) | KLayout extractor |
  |---|---|---|---|---|
  | clean | 0 violations, 0 unconnected | 0 opens, 0 shorts | 0 / 0 | 0 / 0 |
  | one segment of `/CLOCK-RB6` deleted | 1 unconnected, `track_dangling`, `via_dangling`, exit 5 | open `/CLOCK-RB6` (2 islands) | same | same |
  | one via of `/CLOCK-RB6` deleted | 1 unconnected, `track_dangling` | open `/CLOCK-RB6` | same | same |
  | 2.54 mm bridge between vias of `/CLOCK-RB6` and `/DATA-RB7` | `shorting_items`, `tracks_crossing` | short `[/CLOCK-RB6, /DATA-RB7]` | same | same |
  | drill hit moved 3 mm in the `.drl` only (Gerbers untouched) | not applicable (fab-file edit) | open `/CLOCK-RB6`, 1 hit touching fewer than 2 islands | same | same |

  With D356 labels, 7 of 253 records were unlocated on copper; the file has exactly 7 `367` NPTH records, which is the expected cause, though I did not check them one by one.
- **[DOC]** The delta-gerber project's open issue (opened 2026-09-23, no comments, no linked PR) proposes the same design: per-layer connected components, join through plated holes ("a hole joins every component its centre lies in"), map each IPC-356 test point to the component containing it on its access side, report nets spanning more than one component as opens and components carrying more than one net as shorts, let the caller mark intentional net ties. Its acceptance test is a fixture with one track cut and one bridged. — [delta-gerber issue #25](https://github.com/Delta-Proto/delta-gerber/issues/25)
- **[DOC]** KLayout's Gerber import converts circular apertures to polygons with a configurable number of points per full circle, "trading accuracy for performance", and merges implicitly when clear layers are present. — [KLayout manual: Import Gerber PCB Files](https://klayout.de/doc/manual/import_gerber.html)

### Inferences
- **Soundness risks in the prototype, each needing an explicit decision:**
  - *Circle approximation.* `buffer(r, 16)` inscribes the polygon, so shapes are slightly smaller than true. Two features that touch tangentially can read as disconnected (a false open, the safe direction), and a true gap can never close. With 16 segments per quadrant the radial shortfall is `r(1 - cos(pi/64))`, about 0.12% of the radius (0.3 um on a 0.5 mm-wide track). Stating a minimum-overlap threshold is cleaner: require overlap area or depth above a tolerance for "connected", and report near-tangent contacts as a separate warning class.
  - *Hole-to-copper test.* "Hole disc intersects copper" will also join a neighbouring island that the drill merely grazes. Tighter rule: the hole centre must lie inside the island, and report any second island within the disc as a drill-breakout defect instead of a connection. The delta-gerber issue uses centre containment.
  - *Annular ring.* A plated hole whose disc removes all copper of a pad on one layer does not connect that layer. Subtracting hole discs from copper and requiring a remaining ring around the hole is the stricter model; the prototype does not do it.
  - *NPTH.* Non-plated hits must not join layers, and should be subtracted from copper since they cut it. Plating must come from the file header/comment, not be assumed.
  - *Clear polarity.* The correct order-dependent fold is `acc = (acc ∪ dark)` or `acc = acc − clear` in file order, not "union darks then subtract clears". Not exercised: the KiCad file had no `%LPC`.
  - *Arc strokes.* The prototype raises on `gp.Arc`; none occurred on this board. A real implementation must buffer an arc polyline with a bounded chord error.
  - *Zero-width and non-conductor objects.* Objects with `AperFunction,NonConductor` (text etched in copper) are still copper and must stay in the union; they can cause real shorts.
  - *Board outline.* Copper beyond Edge.Cuts is removed by routing; islands should be clipped by the profile before the compare. Not done in the prototype.
- **Clipper2 / pyclipper alternative.** Integer-coordinate clipping (scale mm to nm) gives exact, robust unions without floating-point degeneracy and is the usual choice for PCB polygons. Shapely/GEOS worked here and is BSD-3-Clause **[LOCAL]** (pip metadata); pick integer clipping if robustness issues appear. I did not benchmark or source this.
- **Raster alternative.** Render each layer to a bitmap and label connected components, joining layers at plated-hole pixels. Error bound: features closer than about one pixel merge and necks thinner than about one pixel break, so pixel size must be well under the smaller of minimum clearance and minimum width. At 10 um per pixel a 100 x 100 mm board is 10,000 x 10,000 px per layer, which is workable. It is a good *independent second implementation* for differential testing, because its failure modes differ from the vector path. pygerber (MIT) renders Gerber to raster. I did not build or source this path.
- **Scale.** Hobby boards have a few hundred to a few thousand primitives; a single `unary_union` is fine. No spatial partitioning is needed.

### Gaps
- No source was fetched for Boost.Polygon, Clipper2 or GEOS robustness guarantees; the remarks above are general knowledge.
- Thermal-relief spokes, solder-mask-defined pads, castellations and edge plating were not exercised.
- Slots (routed/oval holes): KiCad has `--excellon-oval-format route|alternate`; the extractor must handle routed slots as swept discs. Not tested.
- The prototype has not been run on a board with SMD-only nets on one layer plus vias-in-pad, nor on any board with clear polarity.

---

## Q5. Existing open-source tools that do part of this

### Takeaway
No open-source tool was found that does Gerber-to-netlist-to-compare end to end; the nearest are KLayout (extracts connectivity from imported Gerber, verified here) and an unimplemented feature request in delta-gerber. The parsing layer is well served by Gerbonara.

### Cited Findings

| Tool | What it does for this task | Licence | Status |
|---|---|---|---|
| Gerbonara | Parses Gerber (with X2 attributes), Excellon, IPC-356; resolves aperture macros to primitives. No connectivity extraction. **[LOCAL]** verified. Region `.attrs` broken and Excellon plating not detected from KiCad comments in 1.6.3 **[LOCAL]**. | Apache-2.0 **[LOCAL]** | Active: 1.6.3 on 2026-04-25; needs Python >=3.12. [PyPI](https://pypi.org/project/gerbonara/), [docs](https://gerbolyze.gitlab.io/gerbonara/) |
| KLayout (`klayout` pip) | Reads Gerber + drill through a `.pcb` XML project, extracts nets with `LayoutToNetlist`, probes nets by point. **[LOCAL]** verified headless. | GPL-3.0-or-later **[LOCAL]** | Active: 0.30.12 installed from PyPI. [manual](https://klayout.de/doc/manual/import_gerber.html) |
| delta-gerber | Has `CopperNets` (per-layer connectivity), `Ipc356Parser`, `PcbAnalyzer`; the opens/shorts-vs-D356 check is an **open issue**, not a feature. Language and licence not shown on the page. **[DOC]** | unknown | Issue opened 2026-09-23. [issue #25](https://github.com/Delta-Proto/delta-gerber/issues/25) |
| pcb-tools | Python Gerber/Excellon parser with an IPC-D-356 loader (`gerber/ipc356.py`). **[SNIPPET]** | not checked | Not checked this session; the earlier report should be relied on. [repo](https://github.com/curtacircuitos/pcb-tools/blob/master/gerber/ipc356.py) |
| pygerber | Gerber X3/X2 parser and 2D renderer; no netlist. Useful for a raster cross-check. | MIT **[LOCAL]** | Stable 2.4.3 (Mar 2025); 3.0 in alpha. [repo](https://github.com/Argmaster/pygerber) |
| gerber-writer | Writes spec-compliant Gerber. Output only. **[SNIPPET]** | not checked | Possibly stale. [repo](https://github.com/Karel-Tavernier/gerber_writer) |
| gerbv | Viewer. Its "netlist" is "a linked list of gerbv_net_t representing drawing operations", not an electrical netlist. **[SNIPPET]** | not checked | [deepwiki summary](https://deepwiki.com/gerbv/gerbv) |
| tracespace | JavaScript Gerber/drill to SVG; parser produces an AST. No connectivity. **[SNIPPET]** | not checked | [repo](https://github.com/tracespace/tracespace) |
| KiCad GerbView | Can select by component, net, attribute or D-code from X2 attributes, which is attribute lookup, not geometric extraction. **[SNIPPET]** | GPL-3.0+ | [KiCad forum](https://forum.kicad.info/t/guidance-for-gerber-viewer-in-5-99/30702) |

- **[SNIPPET]** Commercial tools exist that extract netlists from Gerber plus drill (Numerical Innovations; Artwork Conversion NETEX-G). Reference only. — [Numerical Innovations help](https://support.numericalinnovations.com/support/discussions/topics/14000002411), [Artwork NETEX-G](https://www.artwork.com/gerber/netex-g/netlist/index.htm)

### Inferences
- Build the extractor in-house (about 300-500 lines on Gerbonara + Shapely) and use KLayout as an independent oracle in tests. Two implementations with different geometry kernels agreeing is stronger evidence than either alone.
- Because Gerbonara needs Python 3.12+, the Gerber read-back step should run in its own interpreter/container stage if the main backend stays on 3.11. That also keeps it at arm's length from the code that produced the board.

### Gaps
- Not researched: FlatCAM, CAMotics, OpenBoardView, pcb2gcode, gerbolyze, the Ucamco reference viewer, "gerber2graph"-type projects, KiCad's D356 import. No finding either way.
- Licences for pcb-tools, gerbv, tracespace, gerber-writer and delta-gerber were not confirmed.
- Whether newer 2024-2026 projects beyond delta-gerber exist was covered by one extended search only.

---

## Q6. KLayout as a free Gerber LVS

### Takeaway
Yes, it works headless from plain Python: the `klayout` wheel read a hand-written `.pcb` project pointing at KiCad's Gerbers and Excellon drill, and `LayoutToNetlist` plus `probe_net` reproduced every result of the Shapely extractor on all five boards in about 2.8 s each. It is GPL-3.0-or-later, so keep it a test-time oracle or a separate process.

### Cited Findings
- **[LOCAL]** `pip install klayout` gave 0.30.12 (51 MB in site-packages, no Qt needed). `klayout.db.Layout().read("kl.pcb")` succeeded on Windows; reading a `.gbl` directly failed with "Stream has unknown format". `klayout.db.LayoutToNetlist` is present in the wheel.
- **[LOCAL]** Working `.pcb` project (free layer mapping): root `<pcb-project>` with `<invert-negative-layers>false`, `<border>5000`, `<free-layer-mapping>true`, `<layout-layers>` listing `1/0`, `2/0`, `3/0`, `<mounting>top`, `<num-metal-layers>0`, `<num-via-types>0`, empty `<artwork-files/>` and `<drill-files/>`, `<free-files>` with one `<free-file><filename>…</filename><layout-layers><index>N</index></layout-layers></free-file>` per file (top copper -> 0, PTH drill -> 1, bottom copper -> 2), `<explicit-trans>r0 *1 0,0`, `<num-circle-points>64`, `<merge-flag>true`, `<dbu>0.001`, `<cell-name>PCB`. File names resolve relative to the project file. Resulting layout: 615 / 244 / 579 shapes on top / via / bottom, coordinates in the Gerber frame in micrometres.
- **[LOCAL]** Extraction code that ran: `l2n = LayoutToNetlist(RecursiveShapeIterator(ly, top, []))`; `top_l, via, bot = l2n.make_layer(ly.layer(n,0), name)`; `l2n.connect(x)` for each; `l2n.connect(top_l, via)`; `l2n.connect(via, bot)`; `l2n.extract_netlist()`; nets via `l2n.netlist().top_circuit().each_net()`; lookup via `l2n.probe_net(region, DPoint(x_um, y_um))` and `net.cluster_id`. Net counts: 264 clean, 265 for each open, 263 for the short.
- **[DOC]** The import "supports a majority of the RS274X features" and several drill formats; in layer-stack mode "via layers connect only adjacent metal layers", the stack must have an odd number of layers, and each drill file is given a first and last metal layer. The `.pcb` file "can be specified on the command line" like a stream file. The manual does not publish the XML schema. — [KLayout manual: Import Gerber PCB Files](https://klayout.de/doc/manual/import_gerber.html)
- **[DOC]** Known failure: a drill file lacking an `INCH,TZ` header with zero-suppressed coordinates imported **no vias at all**, leaving via layers empty with nothing in the log; the workaround was re-exporting the drill file through gerbv. The maintainer called drill files "always a nuisance". The same thread shows the GUI net tracer's stack syntax (`cond1: 1/0 via: 2/0 cond2: 3/0`). — [KLayout forum: tracing nets in Gerber](https://www.klayout.de/forum/discussion/comment/4450)
- **[SNIPPET]** The maintainer says Gerber import "does not have a full API" and the way to script it is to generate `.pcb` project files, "which are simple XML". — [KLayout forum: Gerber file import scripting](https://www.klayout.de/forum/discussion/2733/gerber-file-import-scripting)
- **[SNIPPET]** A past bug: "PCB gerber import: Incorrect handling of D02 operations". — [KLayout issue #750](https://github.com/KLayout/klayout/issues/750)
- **[SNIPPET]** Device-less net extraction is an intended use of `LayoutToNetlist`. — [KLayout wiki 2018-12-31](https://github.com/KLayout/klayout/wiki/2018-12-31), [LayoutToNetlist API reference](https://www.klayout.de/doc/code/class_LayoutToNetlist.html)

### Inferences
- **Guard against the silent empty-via failure:** assert that the via layer's shape count equals the number of drill hits parsed independently (244 = 244 here) before trusting any KLayout result.
- KLayout does not distinguish plated from non-plated by itself; feed it only the PTH file. It also ignores X2 attributes, so labels must be supplied from outside, as done here.
- `import klayout.db` inside the AGPL backend process creates a combined work under GPL-3.0/AGPL-3.0. My understanding is that GPLv3 and AGPLv3 each have an explicit clause permitting combination with the other, so this is allowed, with the KLayout part staying GPL. Running it as a subprocess or only in the test suite avoids the question. I did not fetch a licence source this session; have this confirmed before shipping.
- Role recommendation: KLayout as the differential-test oracle and optional second opinion, not the primary implementation. Its circle approximation (64 points) and merge behaviour are outside your control, and its error reporting for malformed inputs is weak.

### Gaps
- Linux/Docker run of the `klayout` wheel with `.pcb` import was not tested.
- KLayout's handling of `%LPC`, aperture-macro edge cases and routed slots in Excellon was not tested.
- `NetlistComparer` / full LVS against a reference netlist was not tried; only extraction and point probing.

---

## Q7. Netlist comparison: names versus graph isomorphism

### Takeaway
When both sides carry names and pad positions, as they do here, compare by position-anchored labels with a bipartite net-to-island map; graph isomorphism adds cost and ambiguity and is only needed when the extracted side is anonymous.

### Cited Findings
- **[LOCAL]** The two-map compare (`net -> {islands}`, `island -> {nets}`) classified all five test boards correctly using only pad centre, side and net name per label.
- **[DOC]** The delta-gerber proposal uses the same two maps and adds: report positions, and let the caller declare intentional net ties as expected. — [delta-gerber issue #25](https://github.com/Delta-Proto/delta-gerber/issues/25)
- **[SNIPPET]** Altium: Gerbers "contain no net names or logical relationships", so extracted nets have to be matched to the netlist's names; in CAMtastic's result, "Missing Nets" that are single-pin or no-net can be ignored, "but the others are most likely issues with CAMtastic's extracted netlist". — [Altium KB: Generate IPC-D-356A and compare to extracted netlist](https://www.altium.com/documentation/knowledge-base/altium-designer/generate-ipc-d-356a-document-and-compare-to-extracted-netlist)
- **[SNIPPET]** Intentional shorts such as an analog-to-digital ground tie are a common source of false errors. — [I-Connect007: Netlist Mismatches Redux](https://iconnect007.com/article/55930/the-bare-board-truth-netlist-mismatches-redux/55933/design)

### Inferences
- **Recommended compare**, anchored on pads rather than names:
  1. Reference side: from the IR, a list of terminals `(ref, pin, net, x, y, side)`.
  2. Extracted side: each terminal is located in an island (after cross-layer union).
  3. Opens: a net whose terminals fall in more than one island. Report the partition of terminals per island and, for a useful message, the closest pair of points between the two islands (Shapely `nearest_points`), which points at the gap.
  4. Shorts: an island containing terminals of more than one net. Report the nets and the island's geometry; the bridge is usually near the narrowest neck between the two terminal groups.
  5. Unlocated terminals (pad centre not on copper): a missing pad. Fail, do not skip.
  6. Unlabelled islands (copper touching no terminal): floating copper. Warn.
  7. Single-terminal and no-connect nets: no open is possible; still check they are not shorted to anything.
  8. Allow-list for declared net ties.
- **Why not isomorphism here.** 1-WL colour refinement and VF2 answer "are these two unlabeled graphs the same shape", which is what IC LVS needs when the layout has no names. They can also be fooled by symmetry (two swapped but structurally identical nets look isomorphic). With pad positions as anchors, a swap is caught directly because the terminal at a known location lands in the wrong island.
- **Where a name-free compare still helps:** as a cross-check that does not trust the IR's own net names, compare the *partition of terminals* induced by the IR netlist with the partition induced by the islands. That is a set-partition equality test, not graph isomorphism, and it is immune to naming bugs such as the D356 truncation.
- Do not key anything on D356 net names from KiCad 10.0.1: last-14-character truncation can collide (two different nets ending in the same 14 characters would merge and hide a short, or split and fake one).

### Gaps
- No source was fetched on KLayout `NetlistComparer`, networkx VF2 or 1-WL in this session; the earlier report covers them.
- No measured example of a truncation collision; the risk is inferred from the observed truncation rule.

---

## Q8. How commercial CAM tools do it, and documented failure modes

### Takeaway
Commercial CAM follows the same shape (extract nets from Gerber plus drill, load IPC-D-356, diff) and the documented false-result causes are mostly data-agreement problems: plating status, intentional shorts, stray non-board graphics, registration, name truncation and D356 dialect differences. Evidence here is thin: search summaries only.

### Cited Findings (all **[SNIPPET]**)
- Altium CAMtastic workflow: extract a netlist from loaded Gerber/NC drill, import IPC-D-356A, produce a difference report; "in some cases the CAMtastic generated netlist could be incomplete". — [Altium KB](https://www.altium.com/documentation/knowledge-base/altium-designer/generate-ipc-d-356a-document-and-compare-to-extracted-netlist)
- **Non-plated holes -> false opens:** the IPC netlist may show mounting holes as connected (a screw completes the circuit after assembly) while the Gerbers and drawing call them non-plated, so CAM treats them as non-electrical and the net appears broken. — [I-Connect007](https://iconnect007.com/article/55930/the-bare-board-truth-netlist-mismatches-redux/55933/design)
- **Plane shorts:** typical mismatches include "missing relief pads on planes (shorts)" and "bridged isolation barriers (shorts)". — same source
- **Stray graphics -> false shorts:** if copper overhangs the fab outline and the outline is not removed before compare, the outline line bridges features. — same source
- **Registration:** mismatches arise "if the layers and netlist are not properly registered. Symmetrical boards are particularly susceptible". — same source
- **Dialect:** Valor tools reportedly read a Cadence Allegro IPC-D-356A differently from Cadence's interpretation; the workaround was another neutral format. — [Cadence community: IPC-D-356A netlist vs Gerber files](https://community.cadence.com/cadence_technology_forums/pcb-design/f/allegro-x-pcb-editor/57698/ipc-d-356a-netlist-vs-gerber-files)
- A PowerPCB script generates D356A specifically "for use with CAM350 to verify Gerber data". — [gist: IPC-D-356A Netlist Extractor](https://gist.github.com/bert/518609/c461468084cf431c5c79f307e95dedcfd54e62e5)
- Fab-side rationale for sending a netlist at all. — [Epec: What is a PCB netlist](https://blog.epectec.com/what-is-a-pcb-netlist-and-why-do-you-need-it), [Altium: Do you need an IPC-D-356 netlist?](https://resources.altium.com/p/do-you-need-ipc-d-356-netlist)

### Inferences
- Three of these were reproduced or nearly reproduced locally: registration (the aux-origin frame shift gave a 50-net false short), name truncation (KiCad 10.0.1), and plating ambiguity (Gerbonara could not tell PTH from NPTH in KiCad's Excellon). They are the first things to defend against.
- Mapping to hobby 2-layer boards: split planes and nested planes are out of scope; the relevant cases are NPTH mounting holes inside a ground pour, zones with thermal spokes that are the only connection to a pad, copper text, and copper past the board edge.

### Gaps
- No vendor documentation for Valor NPI, CAM350, UcamX/Integr8tor or BluePrint was opened. Their extraction algorithms are not documented in anything I read.
- Split planes, same-net spacing, edge plating, castellations and solder-mask-defined pads: no source found in this session. The earlier report's Altium nested-split-plane finding was not re-verified.

---

## Q9. How to test the extractor

### Takeaway
Seeded-defect mutation plus three-way differential testing (own extractor, KLayout, KiCad DRC) is practical today: it was run on one board with four mutations and all three agreed on every case.

### Cited Findings
- **[LOCAL]** Mutations applied by text-splicing balanced s-expressions in `.kicad_pcb` (`scratchpad\scripts\seed.py`): delete one `(segment …)`; delete one `(via …)`; insert a `(segment …)` between the closest pair of vias on different nets; and, at fab-file level, add 3.0 mm to one `X…Y…` hit in the Excellon file. Each mutated board exported cleanly through `kicad-cli`.
- **[LOCAL]** KiCad DRC as oracle: cut and via-delete each produced exactly one `unconnected_items` entry naming the two stranded track groups with positions; the bridge produced `shorting_items` "(nets /CLOCK-RB6 and /DATA-RB7)". Exit code 5 in all three. See the table in Q4.
- **[LOCAL]** The drill-shift mutation is invisible to KiCad DRC because it edits the fab file, not the board. Only the read-back extractors caught it. This is the class of defect that justifies the whole check.
- **[LOCAL]** Baseline noise: the unmodified mutated boards also reported `hole_clearance` (4), `starved_thermal` (4), `silk_edge_clearance` (4) once the stored exclusions were bypassed by `--severity-all`. Oracles must filter on `type`, not on total violation count.
- **[DOC]** delta-gerber's definition of done is the same test: clean fixture reports nothing; a fixture with one track cut and one bridged reports exactly one open and one short at the right locations. — [delta-gerber issue #25](https://github.com/Delta-Proto/delta-gerber/issues/25)

### Inferences
- **Test matrix to build:**
  - *Round trip:* IR -> `.kicad_pcb` -> Gerbers -> extractor partition must equal the partition from `verify.py`'s union-find on the IR. Any disagreement on an unmutated board is a bug in the writer, the exporter or one of the two extractors.
  - *Board-level mutations (KiCad DRC is an oracle):* cut segment, delete via, bridge two nets, shrink a track to zero overlap at a joint, move a pad off its track end.
  - *Fab-file mutations (no KiCad oracle; expected result known by construction):* shift or delete a drill hit, move a hit from PTH to NPTH file, drop one aperture flash, change an aperture diameter so a pad no longer reaches its track, swap top and bottom files, offset one layer by a few mm (registration), mirror one layer.
  - *Equivalence mutations (must NOT change the verdict):* re-export with `--precision 5`, with `--disable-aperture-macros`, with `--format gerber` drill, with `--use-drill-file-origin`; rotate/translate the whole board.
  - *Property-based:* generate random small boards from the IR generator, apply a random mutation with a known expected effect, assert the verdict. Hypothesis fits this; not tried here.
- Record for each case: verdict of own extractor, verdict of KLayout, KiCad `unconnected_items` and `shorting_items`. Any two-against-one split is a finding to triage, not an automatic failure of the minority.
- Mutation score (defects detected / defects seeded) per mutation class is the honest metric to report, alongside the false-positive rate on the equivalence set.
- Keep at least one hand-checked golden board with clear polarity, an arc track, an oval slot and an NPTH inside a pour, since the demo board exercised none of these.

### Gaps
- Only one board and four mutations were run; no near-miss cases (tangent contact, sub-10 um gaps, grazing drills) were tested, and those are where a geometric extractor is most likely to be wrong.
- No SMD-dense board (SOIC/0402) was tested; the demo is mostly through-hole.
- No published mutation-testing methodology for PCB CAM compare was found.
