# Independent DRC, netlist-vs-layout and fab DFM checks for a generated PCB (as of 2026-10)

Scope note for the report writer: every bullet under "Cited Findings" was read from the linked page during this
session (2026-10-08). Where a number came from a search-result summary rather than the page itself, the bullet says
"(search summary)". Anything I know but could not source in-session is under "Gaps" or marked as inference.
KiCad versions referenced: 8.0 (Feb 2024), 9.0 (docs built on 9.0.9), 10.0.0 (20 Mar 2026), 10.0.1 (Apr 2026).

## 1. KiCad as an independent checker (headless DRC, coverage, custom rules, Python API, writing a .kicad_pcb)

### Takeaway
`kicad-cli pcb drc` (available since KiCad 8.0) is the practical free, scriptable, independent DRC: it takes a
`.kicad_pcb`, writes a text or JSON report, and with `--exit-code-violations` returns 0 (clean) or 5 (violations).
Fab limits go in a `<project>.kicad_dru` custom-rules file; community MIT-licensed rule sets for JLCPCB/PCBWay exist.
The cost of entry is writing a valid `.kicad_pcb` (header, general, page, layers, setup, nets, then footprints /
segments / vias / Edge.Cuts graphics).

### Cited Findings

**Headless DRC command (KiCad 9.0 manual)**
- Usage is `kicad-cli pcb drc [options] INPUT_FILE`. Options: `-o/--output` (default: input name with `.rpt` or `.json`), `--format report|json` (default `report`), `--all-track-errors`, `--schematic-parity`, `--units mm|in|mils` (default mm), `--severity-all`, `--severity-error`, `--severity-warning`, `--severity-exclusions`, `-D/--define-var KEY=VALUE`, `--exit-code-violations`. — [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- Exit code with `--exit-code-violations`: "The exit code is 0 if no violations are found, and 5 if any violations are found." Without the flag the exit code does not reflect violations. — [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- The manual does not state which severities are reported when no `--severity-*` flag is given, so pass `--severity-all` (or the wanted set) explicitly. — [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- Sibling commands useful for the same pipeline: `kicad-cli sch erc` (same report/JSON/severity/exit-code-5 options), `kicad-cli sch export netlist -f kicadsexpr|kicadxml|cadstar|orcadpcb2|spice|spicemodel|pads|allegro`, `kicad-cli pcb export gerbers`, `pcb export drill`, `pcb export ipcd356`, `pcb export ipc2581`, `pcb export odb`. — [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- Version history: DRC and ERC from the CLI, with machine-readable JSON reports intended for CI, arrived in KiCad 8.0 (search summary of release coverage; the official 8.0.0 post was truncated in my results). — [KiCad 8.0.0 release post](https://www.kicad.org/blog/2024/02/Version-8.0.0-Released/); [mikrocontroller.net coverage](https://www.mikrocontroller.net/news/kicad-8-verfuegbar)
- A pre-8.0 nightly example shows the shape of real use: `kicad-cli-nightly pcb drc --all-track-errors --severity-all X.kicad_pcb -o drc.rpt`, printing counts of violations, unconnected items and schematic-parity issues (search summary). — [KiCad forum, kicad-cli nightly thread](https://forum.kicad.info/t/experimenting-with-kicad-cli-nightly/47819)
- A minimal CI form recommended from the manual's flags: `kicad-cli pcb drc --output drc.json --format json --severity-all --exit-code-violations board.kicad_pcb`. — [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- Known pitfalls: a forum thread exists titled "Cli ERC/DRC gives different output than running manually in GUI"; and a GitLab issue reports exclusions made through a custom rule in `.kicad_dru` showing as errors under `kicad-cli` while GUI exclusions (saved in the project file) behave as expected (search summaries; not read in full). — [KiCad forum thread](https://forum.kicad.info/t/cli-erc-drc-gives-different-output-than-running-manually-in-gui/55207); [KiCad GitLab issue 24264](https://gitlab.com/kicad/code/kicad/-/issues/24264)

**What KiCad DRC covers (KiCad 9.0 PCB Editor manual)**
- DRC detects "incorrect and missing connections, copper clearance and minimum width violations, and many other design issues." Results are grouped as rule violations, unconnected items, schematic differences, plus a list of ignored tests. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- DRC options: "Refill all zones before performing DRC" (turning it off "may result in incorrect DRC results"); "Report all errors for each track" (every clearance error per segment, slower; CLI `--all-track-errors`); "Test for parity between PCB and schematic" (no effect in standalone PCB Editor mode; CLI `--schematic-parity`). — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- The manual tabulates violation types with default severities by category. Examples read from it: Electrical — "Items shorting two nets" (Error), "Clearance violation" (Error), "Track has unconnected end" (Warning); Design for manufacturing — "Courtyards overlap" (Error), "Hole size out of range" (Error), "Copper sliver" (Warning); Schematic parity — "Duplicate footprints" (Warning), "Missing footprint" (Warning), "Missing connection between items" (Error); Signal integrity — track length / diff-pair gap out of range (Error); Readability — "Silkscreen overlap" (Warning), "Text height out of range" (Warning); Miscellaneous — "Items not allowed" (Error), "Footprint doesn't match copy in library" (Warning). — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- Each violation type can be set to error, warning or ignore; ignoring a type disables that check entirely. Board Setup's minimum clearance is an absolute floor no net class or custom rule can go below. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- Inspect > Clearance Resolution (two objects) and Constraints Resolution (one object) explain which rule produced a given requirement — useful when the two checkers disagree. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- KiCad 10.0.0 (20 Mar 2026) added a graphical DRC rule editor ("Rules created with the editor are fully compatible with the existing Custom Rules language") and suggested fix actions for DRC errors; the release post does not mention kicad-cli changes. — [KiCad 10.0.0 release post](https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/)
- KiCad 10.0.1 is a bug-fix release the project recommends upgrading to; one forum user reported DRC about five times slower after upgrading to 10 (anecdotal, search summary). — [KiCad 10.0.1 release post](https://www.kicad.org/blog/2026/04/KiCad-10.0.1-Release/); [PedalPCB forum thread](https://forum.pedalpcb.com/threads/kicad-version-10-released.28834/latest)

**Custom rules (`.kicad_dru`)**
- Stored in a separate `.kicad_dru` file beside the `.kicad_pcb`/`.kicad_pro`; header for KiCad 9 is `(version 1)`; each rule is `(rule <name> [(severity error|warning|ignore|exclusion)] [(layer <name>|outer|inner)] [(condition "<expr>")] (constraint <type> [(min ..)] [(opt ..)] [(max ..)]))`. Comments start with `#`. Syntax errors stop the design rule checker from running. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- Precedence: rules are evaluated in reverse file order; the first match wins, so specific rules go after general ones. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- Constraint types (29 in 9.0): `annular_width`, `assertion`, `clearance`, `creepage`, `connection_width`, `courtyard_clearance`, `diff_pair_gap`, `diff_pair_uncoupled`, `disallow`, `edge_clearance`, `hole_clearance`, `hole_size`, `hole_to_hole`, `length`, `min_resolved_spokes`, `physical_clearance`, `physical_hole_clearance`, `silk_clearance`, `skew`, `text_height`, `text_thickness`, `thermal_relief_gap`, `thermal_spoke_width`, `track_angle`, `track_segment_length`, `track_width`, `via_count`, `via_diameter`, `zone_connection`. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- Conditions test objects `A` and `B` with properties (`A.Type`, `A.NetClass`, `A.NetName`, `A.Pad_Type`, `A.Via_Type`, `A.Hole_Size_X`…) and functions (`intersectsArea()`, `intersectsCourtyard()`, `hasNetclass()`, `isPlated()`, `inDiffPair()`, `existsOnLayer()`…); units `mm`, `mil`, `in`. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- The manual says to edit rules in Board Setup rather than an external editor; community practice is nevertheless to copy a ready file into the project folder renamed `<project>.kicad_dru`, which KiCad loads automatically. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html); [kicad-druid README](https://github.com/Cimos/kicad-druid)
- Community fab rule sets: `kicad-druid` (MIT; fork of labtroll/KiCad-DesignRules; JLCPCB, PCBWay and a stricter-of-both "Generic"; variants `<FAB>-2L-1oz.kicad_dru`, 4L, 4L-2oz, 6L; KiCad 8 syntax, stated to work on 8, 9 and 10; test boards saved in KiCad 9 format). — [kicad-druid](https://github.com/Cimos/kicad-druid)
- `kicad-druid` notes KiCad can silently drop rules without reporting an error, so its CI appends a sentinel rule to prove the file compiled. — [kicad-druid](https://github.com/Cimos/kicad-druid)
- The original labtroll set (KiCad 7) ships a pass/fail test PCB for each rule "so that there were no false positives or false negatives"; a forum review found it aimed at 4+ layer boards and found a broken rule that used `track_width` to check silkscreen line thickness, which that constraint cannot do (search summary). — [labtroll/KiCad-DesignRules](https://github.com/labtroll/KiCad-DesignRules); [KiCad forum: Design rules for JLCPCB](https://forum.kicad.info/t/design-rules-for-jlcpcb/46087)

**Python API**
- The `pcbnew` Python module offers `LoadBoard()`, `SaveBoard()`, `GetBoard()`, and collection getters `GetFootprints()`, `GetTracks()`, `GetDrawings()`, `GetZones()`, `GetNetClasses()`; the manual states the API is tightly coupled to KiCad internals and not stable across versions. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- `WriteDRCReport()` is listed in the pcbnew Python namespace docs for 6.0, 7.0 and 8.0 (name only; signature and headless behaviour not confirmed in-session). — [pcbnew Python doxygen 8.0](https://docs.kicad.org/doxygen-python-8.0/namespacemembers_w.html)
- A new IPC API was introduced for KiCad 9.0 to replace the SWIG-based Python bindings. — [FOSDEM 2025: Bringing a new API to KiCad](https://archive.fosdem.org/2025/schedule/event/fosdem-2025-6802-bringing-a-new-api-to-kicad/)
- SWIG removal timing is unsettled in what I found: one forum user says SWIG is being turned off in KiCad 11; a third-party changelog says it would be removed in 10.0; the official 10.0.0 post is silent. Users also reported IPC plugins needing to be enabled in settings and not appearing in the toolbar in 10.0.0 (search summaries). — [PedalPCB forum thread](https://forum.pedalpcb.com/threads/kicad-version-10-released.28834/latest); [KiCad 10.0.0 release post](https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/)

**Writing a valid `.kicad_pcb` from a custom board model**
- Required sections: header `(kicad_pcb (version YYYYMMDD) (generator NAME) …)`, `general` (holds `thickness`), page, `layers`, `setup` (incl. `pad_to_mask_clearance` and plot params), and `net` declarations; footprints, graphic items, tracks (segment/via/arc), zones, groups are optional. — [KiCad dev docs: board file format](https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/index.html)
- Token forms: `(layers (ORDINAL "CANONICAL_NAME" TYPE ["USER_NAME"]))` with TYPE in `jumper|mixed|power|signal|user`; `(net ORDINAL "NET_NAME")`; `(segment (start X Y) (end X Y) (width W) (layer L) (net N) (tstamp UUID))`; `(via [TYPE] (at X Y) (size D) (drill D) (layers L1 L2) (net N) (tstamp UUID))`; pads carry `(net N "NAME")`. — [KiCad dev docs: board file format](https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/index.html)
- Third-party writers should not set `generator` to `pcbnew`, so their bugs are not mistaken for KiCad output; net class definitions live outside the board file (design rules/project file). — [KiCad dev docs: board file format](https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/index.html)
- The published format page documents KiCad 6-era syntax (e.g. `tstamp`) and does not describe KiCad 9/10 changes. — [KiCad dev docs: board file format](https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/index.html)

### Inferences
- Because net classes and severities live in `.kicad_pro` and fab limits in `.kicad_dru`, a faithful independent check needs the generator to emit three files (`.kicad_pcb`, `.kicad_pro`, `.kicad_dru`), not one. Without them KiCad checks against its own defaults, which are not the fab's limits.
- The safest way to learn the exact current syntax is to hand-make one tiny board in the installed KiCad version, save it, and treat that file as the template the exporter reproduces; then round-trip (load + save via `kicad-cli`/`pcbnew`) and diff.
- "Courtyards overlap", silk and "footprint doesn't match library" checks only mean something if the exporter writes real footprints (courtyard, silk, library link). A board exported as bare pads + tracks will exercise only the copper/hole/edge checks.
- "Unconnected items" is computed from the net numbers the file itself declares on pads and tracks. It therefore checks the copper against the exporter's net assignment, not against the original schematic — see section 2.
- The engine does not fill zones; if a zone is exported, `kicad-cli` DRC behaviour depends on zone fill state, so either export no zones or confirm fill handling in the CLI.

### Gaps
- Exact JSON schema of the DRC report (field names such as violations / unconnected_items / schematic_parity) was not read from a primary source in-session.
- Which severities `kicad-cli pcb drc` reports by default; whether the CLI refills zones before checking.
- Whether `kicad-cli pcb drc` gained options in 10.0 (the 10.0 CLI manual was not fetched).
- The full Board Setup > Constraints list with default values (min clearance, min track width, min annular width, copper-to-hole, copper-to-edge, hole-to-hole) was not captured; the excerpt fetched did not include it.
- Official SWIG removal schedule; whether the IPC API can run DRC headlessly (it needs a running KiCad instance, as far as I know, but I did not source that).
- Current-format details (`uuid` vs `tstamp`, whether KiCad 10 still wants numeric net ordinals) are undocumented on the page read; verify against a file saved by the installed version.

## 2. Connectivity / layout-versus-schematic: proving the copper implements the intended netlist

### Takeaway
There is no turnkey open-source "PCB LVS" that extracts a netlist from Gerbers and diffs it against a schematic
netlist; that flow exists in commercial CAM tools. The free route is KiCad itself: DRC's shorts / unconnected-items /
schematic-parity checks on a `.kicad_pcb`, plus an IPC-D-356 export for the fab's bare-board electrical test — and,
for true independence, a small home-written extractor over Gerber+drill geometry (parsed with Gerbonara) compared
against the intended netlist.

### Cited Findings
- KiCad DRC reports "Items shorting two nets" (Error) and "Missing connection between items" (Error), lists unconnected items separately, and has a schematic-parity group ("Duplicate footprints", "Missing footprint", …). — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- Parity needs the schematic: the GUI option "has no effect in standalone PCB Editor mode"; the CLI flag is `--schematic-parity`. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html); [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- KiCad's normal schematic→board transfer is "Update PCB from Schematic"; a netlist file is "no longer necessary". The schematic netlist can still be exported headlessly (`kicad-cli sch export netlist`). — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html); [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- IPC-D-356 export: File > Fabrication Outputs, no options; headless `kicad-cli pcb export ipcd356 [-o file.d356] INPUT`. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html); [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- An IPC-D-356 file is text listing every net, the pins/pads/test points on it, their coordinates and layer, and drill spans; it is strictly for connectivity test and carries no trace widths. It is what lets a fabricator find opens/shorts and verify the Gerber copper matches the intended connections. — [Altium: Do you need an IPC-D-356 netlist?](https://resources.altium.com/p/do-you-need-ipc-d-356-netlist)
- The commercial reference flow: load Gerbers + NC drill, extract a netlist from that geometry (connectivity traced layer to layer via the drill files), import the IPC-D-356A netlist, compare, and read the "Different Nets" section. Extracted nets have generic names until the CAD netlist is imported. — [Altium KB: Generate IPC-D-356A and compare to extracted netlist](https://www.altium.com/documentation/knowledge-base/altium-designer/generate-ipc-d-356a-document-and-compare-to-extracted-netlist)
- Net ties and etched components are a known false-positive source: a Gerber-vs-netlist compare can report a net tie as a short; Gerber has an `EtchedComponent` aperture function for such items (search summary). — [KiCad forum: NetTies and IPC-D-356](https://forum.kicad.info/t/using-netties-and-outputting-an-ipc-d-356-netlist-file/52316)
- Gerbonara (Python, v1.6.3) reads and writes Gerber, Excellon and IPC-356 netlist files, with a `LayerStack.open('dir')` that identifies layers from names/metadata; its docs describe no netlist-extraction or design-rule feature. — [Gerbonara docs](https://gerbolyze.gitlab.io/gerbonara/)
- KiCad GerbView can highlight items belonging to a selected net or component when the Gerbers carry X2 attributes (toolbar functions; search summary of the manual). — [KiCad 9.0 GerbView manual](https://docs.kicad.org/9.0/en/gerbview/gerbview.html)
- `kicad-cli pcb export gerbers` writes X2 with netlist attributes by default; `--no-x2` and `--no-netlist` turn them off. — [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- A targeted search for an open-source Gerber netlist extractor/comparator returned only commercial tools (Altium CAM editor, CAM350); HQDFM (free, vendor) claims detection of shorts and opens. — [Altium KB](https://www.altium.com/documentation/knowledge-base/altium-designer/generate-ipc-d-356a-document-and-compare-to-extracted-netlist); [NextPCB HQDFM](https://www.nextpcb.com/dfm-tool)

### Inferences
- Three distinct questions hide under "LVS", each needing a different reference:
  1. Does the copper match the net labels in the board file? (KiCad DRC shorts + unconnected items. Reference = the exporter's own net assignment.)
  2. Do the board's nets/footprints match the schematic? (KiCad schematic parity. Reference = `.kicad_sch`. In this project the `.kicad_sch` and the board come from the same CircuitIR, so parity checks the two compilers against each other — valuable, but a shared upstream bug passes both.)
  3. Do the fabrication files match the netlist? (Gerber/drill geometry → extracted connectivity vs IPC-D-356 or the IR netlist. Only this one checks what is actually sent to the fab.)
- The IPC-D-356 file written by KiCad is derived from the same board database as the Gerbers, so comparing KiCad's D-356 with KiCad's Gerbers proves export consistency, not design intent. For an independent check the reference netlist should come from the Board IR / CircuitIR directly (pad coordinates → intended net).
- A home-written geometric extractor is tractable for these boards: parse copper layers and drills with Gerbonara, union overlapping copper per layer (e.g. with a polygon library), join layers at plated holes, then check that each pad location's connected component maps one-to-one to an intended net (two nets in one component = short; one net in two components = open). It is a second implementation by the same author, so it is independent in code path but not in authorship; KiCad's connectivity engine is the independent-author check.
- Because KiCad's "unconnected" logic is ratsnest-based on declared nets, deliberately exporting a board with one track deleted and one cross-net bridge added is the quickest proof the check is live (see section 7).

### Gaps
- No confirmed open-source tool that extracts a netlist from Gerber/Excellon and diffs it against IPC-D-356. pcb-rnd / camv-rnd, gerbv and pcb-tools were searched for or considered; I found no evidence any of them does netlist extraction, and found no documentation at all for pcb-rnd/camv-rnd in-session.
- Whether KiCad can import an external IPC-D-356 file and compare it against a board (I found export only).
- Gerbonara's IPC-356 class names and API were not read.
- The exact Gerber object attributes for nets (`.N` net, `.P` pin, `.C` component) are what I understand X2 to use, but no fetched source confirmed the syntax.

## 3. Gerber / drill output validation

### Takeaway
Free scriptable Gerber tooling exists (Gerbonara in Python, gerbv CLI for rendering, KiCad GerbView and the Ucamco
Reference Gerber Viewer for inspection), but none of it is a rule checker: they validate parse-ability, layer
identification, bounds and visual sanity. Rule checking of Gerbers is done by fab DFM tools (section 4).

### Cited Findings
- Format lineage: Standard Gerber (RS-274-D subset, 1980) → Extended Gerber RS-274X (1998) → X2 attributes (revision J1, Feb 2014; Standard Gerber revoked Sept 2014) → netlist draft finalized 2016 → X3 component information (2020). Latest specification revision listed is 2024.05, dated 3 July 2024. — [Wikipedia: Gerber format](https://en.wikipedia.org/wiki/Gerber_format)
- X2 attributes state the file's function (e.g. top copper, top mask), the part (single PCB / array / coupon) and pad function (SMD pad, via pad, fiducial); they do not change the image, so X2 is backward compatible. — [Wikipedia: Gerber format](https://en.wikipedia.org/wiki/Gerber_format)
- Aperture function values seen in practice include `Conductor`, `ViaPad`, `ComponentPad` (search summary). — [JLCPCB help: misidentified layers / Gerber X2](https://api.jlcpcb.com/help/article/misidentified-layers-why-not-follow-gerber-x2-standards)
- X3 adds component layers identified by a `.FileFunction` of the form `Component,L<n>,Top|Bot`; X3 files remain readable by older systems, which use only the features they support. — [Eurocircuits: Gerber X3](https://www.eurocircuits.com/gerber-x3/)
- Recommendations: use X2 attributes rather than file-extension conventions; layers must be aligned and a profile (outline) layer is required; avoid "painting" pours and pads with strokes; check files with the Ucamco Reference Gerber Viewer. The spec, test files and reference viewer are published on Ucamco's site. — [Wikipedia: Gerber format](https://en.wikipedia.org/wiki/Gerber_format)
- Stackup/finish/material data go in a separate Gerber Job File; drill data is often sent in NC formats for historic reasons though Gerber drill files are "often of better quality". — [Wikipedia: Gerber format](https://en.wikipedia.org/wiki/Gerber_format)
- KiCad Gerber export knobs that matter for downstream checkers: `--no-x2`, `--no-netlist`, `--precision 5|6` (default 6), `--no-protel-ext` (use `.gbr`), `--use-drill-file-origin`, `--subtract-soldermask`, `--disable-aperture-macros`, `--board-plot-params`; `pcb export gerber` (singular) is deprecated in 9.0 and slated for removal in 10.0. — [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- KiCad drill export: `--format excellon|gerber`, `--drill-origin absolute|plot`, `--excellon-zeros-format decimal|suppressleading|suppresstrailing|keep`, `--excellon-units mm|in`, `--excellon-separate-th` (separate plated / non-plated files), `--excellon-oval-format route|alternate`, `--generate-map`. — [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- Gerbonara 1.6.3: read/write Gerber, Excellon, IPC-356; full aperture-macro support; SVG export; file-level offset/rotate/merge; `LayerStack.open('output/gerber')` then `stack.outline.size('mm')` for board size; CLI via `python -m gerbonara --help` / `python -m gerbonara render --help`; install `pip install --user gerbonara`. It is a fork of pcb-tools. — [Gerbonara docs](https://gerbolyze.gitlab.io/gerbonara/); [Gerbonara on PyPI](https://pypi.org/project/gerbonara/0.11.0/)
- gerbv: GPL-2 (some files GPL-2+), originally gEDA, now maintained separately at gerbv/gerbv on GitHub; headless export with `-x/--export png|pdf|ps|svg|rs274x|drill|idrill`, `-D/--dpi`, `-o/--output`, `-B/--border`, `-a/--antialias`; example `gerbv --export=png --dpi=600 --foreground=#ff0000ff file1.gbx file2.gbx`. Distribution packages list 2.10–2.13 (search summary). — [gerbv man page (openSUSE Tumbleweed 2.13.0)](https://manpages.opensuse.org/Tumbleweed/gerbv/gerbv.1.en.html); [Debian gerbv copyright](https://metadata.ftp-master.debian.org/changelogs/main/g/gerbv/stable_copyright)
- tracespace (JavaScript): the v5 parser README says "This package is still in development and is not yet published" (possibly an old snapshot); the v4-line packages (e.g. gerber-plotter 4.2.8) are the stable ones (search summary). — [@tracespace/parser 5.0.0-next.0 README](https://app.unpkg.com/@tracespace/parser@5.0.0-next.0/files/README.md)
- Free vendor viewers: JLCPCB online Gerber viewer; NextPCB HQDFM online viewer (no sign-up) accepting RS-274X, X2, ODB++, `.kicad_pcb` and Excellon as zip/rar. — [JLCPCB Gerber viewer](https://jlcpcb.com/RGE); [NextPCB HQDFM](https://www.nextpcb.com/dfm-tool)

### Inferences
- A cheap scripted Gerber lint for this project (all doable with Gerbonara): every expected layer present and identified (F.Cu, B.Cu, both masks, silk, Edge.Cuts/profile, PTH and NPTH drills); outline is one closed loop; copper/drill bounding boxes lie inside the outline; drill and copper share an origin and units (pad centres coincide with drill hits); drill diameters match the board model's tool list; no zero-size apertures; render to SVG/PNG for a human glance.
- Typical export errors worth a test each: drill file in inches/with zero suppression misread by the fab, drill origin differing from Gerber origin (`--drill-origin` vs `--use-drill-file-origin`), missing or open board outline, plated and non-plated holes merged, mirrored bottom layers, mask openings missing. (These are from general practice; I did not find one authoritative list in-session.)
- Round-trip check: export Gerbers from the KiCad-converted board, re-parse with Gerbonara, and compare pad centres / track endpoints with the Board IR. This catches exporter and unit errors that DRC on the `.kicad_pcb` cannot see.

### Gaps
- Gerbonara's licence and supported Python versions are not stated on the page read.
- The Ucamco specification itself (2024.05) was not opened; attribute syntax for `.N/.P/.C` is unconfirmed here.
- No free, offline, open-source Gerber DRC (min width/space measured on Gerber geometry) was identified. I did not find one; I cannot assert none exists.
- Current maintenance state of pcb-tools (the project Gerbonara forked) was not checked.

## 4. Fab capability rules and free DFM checks

### Takeaway
For hobby 2-layer 1 oz boards, a rule set of 0.2 mm track / 0.2 mm space, 0.3 mm via drill with 0.6 mm+ via pad,
0.3 mm copper-to-edge and 1.0 mm silk text passes every fab surveyed; published absolute minimums are roughly
0.10–0.15 mm track/space. Free automated DFM exists from JLCPCB (browser), NextPCB HQDFM (browser + Windows) and
Eurocircuits PCB Visualizer/Checker (browser), all tuned to their own factories.

### Cited Findings

**JLCPCB (capabilities page read 2026-10-08)**
- Min trace width / spacing 0.10 / 0.10 mm (4/4 mil) as reported for 1–2 layer 1 oz; min via hole 0.15 mm (preferred 0.20 mm), min via diameter 0.25 mm, via diameter should exceed hole by 0.10 mm (0.15 mm preferred). — [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- PTH annular ring: recommended ≥0.25 mm, absolute min 0.18 mm; NPTH pad ring ≥0.45 mm; min non-plated hole 0.50 mm; min plated slot 0.5 mm, non-plated slot 1.0 mm. — [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- Hole-to-hole: via 0.20 mm, pad holes 0.45 mm. Hole-to-track: via 0.20 mm, PTH 0.28 mm min (0.35 mm recommended), NPTH 0.20 mm. Pad-to-track 0.10 mm. — [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- Copper to board edge: ≥0.20 mm routed, ≥0.40 mm V-cut. Outline tolerance ±0.2 mm. — [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- Silkscreen: min line 0.15 mm, min text height 1.0 mm, pad-to-silk 0.15 mm. Solder-mask bridge 0.10 mm (green/red/yellow/blue/purple), 0.13 mm (black/white). — [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- Drill tolerance +0.13/−0.08 mm (PTH), hole position ±0.075 mm; FR-4 thickness 0.4–4.5 mm, standard 1.6 mm; min board 3 × 3 mm. — [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- Conflict: a JLCPCB blog advises designing to "5 mil trace/space at JLCPCB" as the standard capability (search summary), versus 4/4 mil on the capabilities table above. — [JLCPCB blog: design rule check](https://jlcpcb.com/blog/design-rule-check); contradicted by [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)

**PCBWay**
- Standard FR-4: min trace/space 0.1 mm (4 mil); drill 0.15–6.0 mm (holes <0.2 mm may cost extra); min annular ring 0.15 mm (6 mil); PTH tolerance ±0.08 mm, NPTH ±0.05 mm; outline tolerance ±0.2 mm (routing); silkscreen min width 0.15 mm, height 0.8 mm. — [PCBWay capabilities](https://www.pcbway.com/capabilities.html)
- From PCBWay's "advanced" table (normal process): 35 µm outer copper ≥5/6 mil trace/space; line-to-board-edge 0.25 mm (0.20 mm medium difficulty); hole-to-hole component holes ≥16 mil, vias ≥11 mil; green mask bridge 4 mil; hole position ±0.075 mm. — [PCBWay capabilities](https://www.pcbway.com/capabilities.html)

**OSH Park (2-layer prototype service)**
- Min trace 6 mil (0.1524 mm), min space 6 mil, min drill 10 mil (0.254 mm), min annular ring 5 mil (0.127 mm), board-edge keepout 15 mil (0.381 mm); 1 oz copper, 1.6 mm, ENIG, purple mask; mask web 4 mil; silk line 5 mil recommended; min slot 20 mil; drill tolerance max ±2.5 mil; min board 0.25 × 0.25 in. — [OSH Park 2-layer service](https://docs.oshpark.com/services/two-layer/)
- Overlapping drills allowed but not guaranteed (5 mil hole clearance recommended); no blind/buried vias. — [OSH Park 2-layer service](https://docs.oshpark.com/services/two-layer/)

**AISLER (values from search summaries of AISLER's community pages — verify on the live pages)**
- 35 µm copper: HASL 200/150 µm trace/space, ENIG 125/125 µm; 70 µm: HASL 225/225 µm, ENIG 175/175 µm; min PTH drill 0.3 mm (HASL) / 0.25 mm (ENIG). — [AISLER PCB design rules](https://community.aisler.net/t/pcb-design-rules/41)
- 2-layer 1.6 mm HASL sheet: via drill 0.3–0.45 mm, via annular ring 200 µm recommended (175 µm absolute floor), drills >0.45 mm treated as component PTH, copper-to-edge 300 µm. — [AISLER 2-layer 1.6 mm HASL design rules](https://community.aisler.net/t/2-layer-1-6mm-hasl-design-rules/3735)
- A community thread reports AISLER enlarges plated holes by 150 µm in production (a 0.65 mm drill becomes 0.8 mm, shrinking the ring) — user-reported, not a spec. — [AISLER community thread](https://community.aisler.net/t/through-hole-1-27mm-pin-header-manufacturing-min-annular-ring-size-not-reached/2781)

**Eurocircuits**
- Rules are expressed as a pattern class (smallest of track, gap, pad and annular-ring values, outer and inner) and a drill class (smallest production tool size, not finished hole size). The numeric table is published as an image. — [Eurocircuits classification](https://www.eurocircuits.com/pcb-design-guidelines-classification/); [classification table image](https://www.eurocircuits.com/content/uploads/2025/04/EC-classification-ENGLISH-5-2024-V3.png)
- Worked example: 0.60 mm pad with 0.25 mm finished PTH (tool = finished + 0.10 mm) gives a 0.125 mm annular ring, "pattern class 6 which is standard for our pooling services" (search summary). — [Eurocircuits classification / drill class](https://www.eurocircuits.com/pcb-classification-drill-class/)
- Hole-to-copper for unconnected holes (IPI) is at least inner annular ring + 0.075 mm with a 0.200 mm floor, measured from tool size; connected NPTH holes should have ≥0.30 mm ring; thicker copper needs wider isolation; do not design exactly at class limits. — [Eurocircuits classification](https://www.eurocircuits.com/pcb-design-guidelines-classification/)

**Free automated DFM**
- JLCPCB DFM (dfm.jlcpcb.com, also linked from JLCPCB help as "JLCDFM – DFM Check" at jlcdfm.com): browser-based, one-click upload, five analysis modules (traces, solder mask, drilling, silkscreen, component assembly), visual localisation, one-click PDF report; can apply ready-made rules or another supplier's rules (vendor description, search summary). — [JLCPCB DFM](https://dfm.jlcpcb.com); [JLCPCB help: JLCDFM](https://jlcpcb.com/help/article/jlcdfm-design-for-manufacturing-analysis-tool)
- NextPCB HQDFM: free online viewer (no download, no sign-up) plus a free Windows desktop build (~163 MB, no licence key, login with a NextPCB/HQ account); accepts RS-274X, X2, ODB++, `.kicad_pcb`, Excellon; detects shorts/opens, missing mask openings, clearance violations; vendor claims 1200+ DFM/DFA checks on desktop; downloadable report. — [NextPCB HQDFM](https://www.nextpcb.com/dfm-tool); [HQDFM download guide](https://www.nextpcb.com/hqdfm-download)
- Eurocircuits PCB Visualizer / PCB Checker: free smart tools; applies "over 700 predefined DRC & DFM rules" against the chosen pooling service; PCB Checker highlights annular-ring problems, hole sizes and distances, track width, isolation/clearance (search summary). — [PCD&F: Eurocircuits PCB Visualizer](https://pcdandf.com/pcdesign/index.php/editorial/menu-new-indust-prod/11599-eurocircuits-offers-pcb-visualizer-dfm-ordering-suite); [Eurocircuits: PCB Checker](https://www.eurocircuits.com/blog/pcb-checker-release-24-10-2012/)
- AdvancedPCB FreeDFM: browser upload of a zipped Gerber set, graphical report returned. — [AdvancedPCB FreeDFM](https://advancedpcb.com/en-us/tools/free-dfm-filecheck)
- KiCad-side fab rule sets on GitHub: kicad-druid (MIT; JLCPCB/PCBWay/Generic; 2L-1oz variant) and labtroll/KiCad-DesignRules (KiCad 7, JLCPCB). — [kicad-druid](https://github.com/Cimos/kicad-druid); [labtroll/KiCad-DesignRules](https://github.com/labtroll/KiCad-DesignRules)

**Side-by-side (2-layer, 1 oz, published minimums; mm)**

| Rule | JLCPCB | PCBWay | OSH Park | AISLER (HASL, 35 µm) |
|---|---|---|---|---|
| Track width | 0.10 | 0.10 (std table) / 0.127 (adv. table, 1 oz outer) | 0.152 | 0.20 |
| Spacing | 0.10 | 0.10 / 0.152 (adv. table) | 0.152 | 0.15 |
| Min drill | 0.15 (0.20 preferred) | 0.15 (0.20 no surcharge) | 0.254 | 0.30 |
| Annular ring | 0.18 abs / 0.25 rec. (PTH) | 0.15 | 0.127 | 0.20 (0.175 floor) |
| Copper to edge | 0.20 routed / 0.40 V-cut | 0.25 | 0.381 | 0.30 |

Sources as cited per fab above.

### Inferences
- A conservative "passes everywhere" profile for the engine, taking the strictest published value in each row plus margin: track ≥0.20 mm, space ≥0.20 mm, via drill ≥0.30 mm, via pad ≥0.70 mm (ring 0.20), component PTH ring ≥0.25 mm, copper-to-edge ≥0.40 mm, hole-to-hole ≥0.45 mm, PTH-to-track ≥0.35 mm, silk line ≥0.15 mm / text ≥1.0 mm, mask web ≥0.10 mm. Hobby THT/0805 boards lose nothing at these values.
- Fab minimums are "can be made", not "should be designed to"; the fabs' own pages distinguish recommended from absolute (JLCPCB ring 0.25 vs 0.18; Eurocircuits' "leave margin" advice).
- Fab DFM tools check the Gerber/drill files, so they are the only checks in this list that see the true fabrication output; but they need a browser upload (and for desktop HQDFM a login), so they are a manual gate, not a CI step.
- Annular ring must be computed from the fab's tool size, not finished hole size (Eurocircuits and the AISLER thread both show the fab enlarging the drill 0.10–0.15 mm). A home-made DRC that uses finished hole size overstates the ring.

### Gaps
- JLCPCB 1–2 layer trace/space: the fetched table gave 0.10/0.10 mm but JLCPCB's own blog says 5 mil; historically the 2-layer figure was 0.127 mm (my recollection, unsourced). Confirm on the live page before encoding.
- Eurocircuits numeric class table (track/gap per class, drill classes, copper-to-edge) is an image and was not read.
- AISLER values came via search summaries, not a direct page read; AISLER's upload-time automated checks and native KiCad upload were not confirmed.
- Whether any fab offers an API (not browser) DFM check usable from CI — none found.
- OSH Park's upload preview/checks and its published KiCad rule files were not found on the page read.
- The actual 2-layer values inside `JLCPCB-2L-1oz.kicad_dru` were not read (README points to `COMPARISON.md`).

## 5. IPC standards for trace sizing and spacing

### Takeaway
IPC-2221's current formula is `I = k · ΔT^0.44 · A^0.725` (A in mil², k = 0.048 external / 0.024 internal); for 1 oz
copper and a 10 °C rise it gives about 0.9 A at 0.25 mm and 1.4 A at 0.5 mm. IPC-2152 (2009) replaced the single
curve with charts that account for board thickness, copper planes and so on. The standards are paid documents; free
calculators (KiCad PCB Calculator, Saturn PCB Toolkit, online tools) implement them.

### Cited Findings
- IPC-2221 formula: I in amps, ΔT in °C above ambient, A cross-section in square mils; k = 0.048 for external traces and 0.024 for internal traces; derived from test boards with measured temperature rise. — [Altium: IPC-2221 calculator](https://resources.altium.com/p/ipc-2221-calculator-pcb-trace-current-and-heating)
- Limits of IPC-2221: derived under controlled conditions (single copper weight, specific board, still air); ignores stack-up, nearby planes, airflow; generally conservative. — [Cadence: IPC-2152 vs IPC-2221](https://resources.system-analysis.cadence.com/blog/ipc-2152-vs-ipc-2221-which-to-use-for-pcb-thermal-analysis)
- IPC-2152 (2009) is a ~97-page document built from extensive testing and simulation; instead of one formula it gives nomographs for an "unadjusted" cross-section plus corrections. — [Cadence: IPC-2152 vs IPC-2221](https://resources.system-analysis.cadence.com/blog/ipc-2152-vs-ipc-2221-which-to-use-for-pcb-thermal-analysis)
- Third-party calculator claims about IPC-2152 (not verified against the standard): typically 1.5–2× the IPC-2221 current at the same rise; a plane within ~0.5 mm raises ampacity ~40%; a curve-fit `I ≈ k·ΔT^0.5·A^0.65` with k ≈ 0.089 external / 0.063 internal (search summary). — [Salitronic trace width calculator](https://salitronic.com/pcb-trace-width-calculator/)
- IPC-2221B Table 6-1 minimum spacing, from secondary reproductions: 0–15 V and 16–30 V: B1 (internal) 0.05 mm, B2 (external uncoated, sea level to 3050 m) 0.1 mm, B4 (external, permanent polymer coating) 0.05 mm, A5 (external, conformal coat over assembly) 0.13 mm; 31–50 V and 51–100 V: B1 0.1 mm, B2 0.6 mm, B4 0.13 mm, A5 0.13 mm. Above 500 V a per-volt formula applies. — [Altair PollEx: IPC material/spacing table](https://help.altair.com/pollex/topics/pollex/verification/dfe_ipc_material_r.htm); [PCBSync IPC-2221 summary](https://pcbsync.com/ipc-2221/)
- Conflict: one PCBSync table lists A5 as 0.05 mm for 0–30 V where Altair's reproduction gives 0.13 mm; the PCBSync columns appear shifted. — [PCBSync](https://pcbsync.com/?p=31169); contradicted by [Altair PollEx](https://help.altair.com/pollex/topics/pollex/verification/dfe_ipc_material_r.htm)
- KiCad PCB Calculator (bundled, free/open source): Track Width tool computes width for a given current and temperature rise "using formulas from IPC-2221 (formerly IPC-D-275)"; Electrical Spacing tool tabulates minimum conductor distance per voltage range, with manual entry above 500 V. — [KiCad PCB Calculator manual](https://docs.kicad.org/master/en/pcb_calculator/)
- Saturn PCB Toolkit: freeware (donation-supported) Windows tool; conductor and via current per IPC-2152, minimum conductor spacing from IPC-2221A data, impedance, crosstalk etc.; versions seen 7.12 → 8.44–8.47 (search summary). One Cadence-forum user reported its IPC-2152 values differ from the IPC-2152 charts. — [PCD&F: Saturn PCB Toolkit](https://pcdandf.com/pcdesign/index.php/editorial/menu-new-indust-prod/14858-saturn-pcb-delivers-pcb-design-toolkit-v-7-12); [Cadence community thread](https://community.cadence.com/cadence_technology_forums/pcb-design/f/pcb-design/41084/calculating-trace-current)

**Computed with the cited IPC-2221 formula (my arithmetic, this session; 1 oz = 1.378 mil thick, external, k = 0.048)**

| Width | Area (mil²) | I at ΔT = 10 °C | I at ΔT = 20 °C |
|---|---|---|---|
| 0.25 mm (9.84 mil) | 13.56 | 0.88 A | 1.19 A |
| 0.50 mm (19.69 mil) | 27.13 | 1.45 A | 1.96 A |
| 1.00 mm (39.37 mil) | 54.25 | 2.39 A | 3.24 A |

Formula source: [Altium: IPC-2221 calculator](https://resources.altium.com/p/ipc-2221-calculator-pcb-trace-current-and-heating). The 1.378 mil thickness for 1 oz copper is the conventional figure (OSH Park lists outer copper as 1.4 mil — [OSH Park](https://docs.oshpark.com/services/two-layer/)).

### Inferences
- For this project's circuits (LED ~20 mA, RS-485 driver tens of mA, MCU rail ≤ ~0.1–0.5 A), a 0.25 mm signal track carries the load with an order of magnitude of margin under IPC-2221; a 0.5 mm power track covers ~1.4 A at 10 °C rise. Current capacity is not the binding constraint; fab minimums are.
- At 5 V / 3.3 V the IPC-2221 B2 spacing (0.1 mm) is at or below every fab's minimum spacing, so the fab rule dominates the electrical one. Voltage spacing only bites if a design carries >30 V (0.6 mm external uncoated).
- A DRC kernel can encode both as data: `min_width(net) = max(fab_min, ipc2221_width(I_net, ΔT))` and `min_clearance(netA, netB) = max(fab_min, ipc2221_spacing(|V_A − V_B|))`. That is a design-intent check KiCad will not do unless net classes or custom rules carry the same numbers.
- Sources disagree on which standard is "more conservative" (Cadence/Salitronic: IPC-2221 is conservative and 2152 allows more; a KiCad forum post calls 2152 "harsher"). It depends on conditions: with planes and thick boards 2152 allows more; for an isolated trace on a thin board it can allow less.

### Gaps
- IPC-2221B, IPC-2152 and IPC-A-600 are paid IPC documents (my understanding; I did not fetch IPC's store pages to cite prices or confirm current revision letters).
- IPC-A-600 (acceptability of printed boards) and IPC-6012 Class 1/2/3 definitions and their annular-ring/breakout allowances were not researched in-session; no sourced statement is offered. Hobby fabs generally build to Class 2, but I did not confirm that per fab.
- Table 6-1 values come from secondary reproductions that conflict in one cell; the B3 (external uncoated, above 3050 m) and A6/A7 columns were not captured.
- Whether KiCad 10's PCB Calculator added IPC-2152 was not checked.

## 6. What each check proves and what it leaves unproven

### Takeaway
Each check proves agreement with one reference under one set of rules: DRC proves geometry obeys the rules it was
given; connectivity proves copper matches a netlist; fab DFM proves the files are buildable at one factory. None
proves the netlist is the right circuit or that the built board works.

### Cited Findings
- KiCad DRC's scope is "incorrect and missing connections, copper clearance and minimum width violations, and many other design issues" against the constraints configured in Board Setup, net classes and custom rules; a violation type set to ignore is not tested at all. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- Custom rules with syntax errors stop the checker; and KiCad can silently drop rules, which is why kicad-druid compiles a sentinel rule in CI. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html); [kicad-druid](https://github.com/Cimos/kicad-druid)
- Without zone refill, DRC "may result in incorrect DRC results". — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
- IPC-D-356 is "strictly for testing network connectivity" — no widths, no component orientation. — [Altium: IPC-D-356](https://resources.altium.com/p/do-you-need-ipc-d-356-netlist)
- Gerbers carry no net names by themselves; an extracted netlist has topology with generic names until matched to a reference. — [Altium KB](https://www.altium.com/documentation/knowledge-base/altium-designer/generate-ipc-d-356a-document-and-compare-to-extracted-netlist)
- Fab DFM tools evaluate against that supplier's rule set ("ready-to-go DFM rules or … rules provided by your preferred supplier"). — [JLCPCB DFM](https://dfm.jlcpcb.com)
- IPC-2221 current numbers assume its test conditions (still air, one copper weight, no planes). — [Cadence: IPC-2152 vs IPC-2221](https://resources.system-analysis.cadence.com/blog/ipc-2152-vs-ipc-2221-which-to-use-for-pcb-thermal-analysis)

### Inferences

| Check | Proves (if it passes) | Does not prove |
|---|---|---|
| Own DRC kernel "0 errors" | The board satisfies the kernel's rules as the kernel implements them | That the kernel is correct; that the rules match a fab |
| KiCad DRC, default constraints | Geometry is self-consistent under KiCad's defaults; no shorts; no unconnected declared nets | Manufacturability at any fab (defaults ≠ fab limits) |
| KiCad DRC + fab `.kicad_dru` | Width, clearance, ring, hole, edge, silk limits of that rule file hold — judged by a second, independently written engine | That the rule file is the fab's current capability; anything the rule file omits (rules can be silently dropped) |
| Unconnected items / shorting items | Copper realises the net labels in the board file | That those labels equal the schematic's nets |
| Schematic parity | Board footprints/nets match the `.kicad_sch` | That the schematic is the intended circuit; pin-number-to-pad mapping errors inside a footprint that both files share (e.g. the SOT-23 B/E/C ordering bug this project already hit) |
| Gerber parse + lint | Files are syntactically valid, complete, aligned, in the expected units | Any spacing/width rule; electrical correctness |
| Gerber-extracted netlist vs intended netlist | The fabrication data, not just the CAD database, implements the netlist | Footprint/land-pattern correctness; that parts fit |
| Fab DFM upload | This factory's CAM accepts the files at these features | Function, signal integrity, thermal, assembly fit of real parts, long-term reliability |
| IPC-2221/2152 width & spacing | Tracks are sized for stated current/voltage under the standard's assumptions | Real temperature rise in the enclosure; creepage for safety standards |
| Fab bare-board e-test (from IPC-D-356) | The manufactured copper matches the netlist | Everything after bare board: parts, soldering, firmware, function |

- Two blind spots no tool in this list covers: (1) footprint correctness — land pattern, pin numbering, courtyard and body size versus the real part's datasheet; (2) the circuit itself — that is the job of the project's simulation/proof layers and, ultimately, a bench build.
- "Independent" has degrees: KiCad DRC is independent in authorship and code but consumes a file the same exporter wrote, so an exporter bug that mis-states geometry consistently (e.g. wrong pad size) is invisible to it. Comparing rendered Gerbers against the Board IR closes part of that gap.

### Gaps
- No single authoritative source enumerating "what DRC does not cover" was found; the table above is reasoning from the cited scopes, not a cited list.

## 7. Cross-checking a home-made DRC kernel against KiCad DRC (differential testing, seeded violations)

### Takeaway
Use KiCad as the oracle in a differential harness: export each board to `.kicad_pcb` with a matching `.kicad_dru`,
run `kicad-cli pcb drc --format json --severity-all --exit-code-violations`, normalise both tools' findings to
(rule class, object pair, location) and diff — on clean boards and on boards with one seeded violation each. KiCad's
own QA and the community fab rule sets already work this way.

### Cited Findings
- KiCad's own DRC regression suite runs DRC on stored boards and asserts counts: clean boards must give zero error-severity items; known-bad boards carry a hand-set expected count (e.g. issue1358 → 2, issue6879 → 6) because they "were at one time failing to catch DRC errors that they should have". — [KiCad doxygen: test_drc_regressions.cpp](https://docs.kicad.org/doxygen/test__drc__regressions_8cpp_source.html)
- Other KiCad tests assert exact counts by violation type (e.g. exactly 2 via-keepout, 1 track-keepout, 3 total) specifically to catch duplicate-marker regressions, assert marker position (violation located at the offending arc's coordinates), and show counts depend on the "report all track errors" flag. Fixtures live under `qa/data/pcbnew/...`. — [KiCad doxygen: test_drc_keepout_disallow.cpp](https://docs.kicad.org/doxygen/test__drc__keepout__disallow_8cpp_source.html); [test_drc_invalid_outline_issue24241](https://docs.kicad.org/doxygen/test__drc__invalid__outline__issue24241_8cpp_source.html); [test_solder_mask_bridge_all_tracks](https://docs.kicad.org/doxygen/test__solder__mask__bridge__all__tracks_8cpp_source.html)
- Community rule sets validate per rule with paired pass/fail objects: labtroll's set has "a pass/fail test PCB for each rule" to rule out false positives and negatives; kicad-druid ships a test board per fab with `TESTBOARD.md` describing what each object exercises, and runs `kicad-cli pcb drc` on it in CI. — [labtroll/KiCad-DesignRules](https://github.com/labtroll/KiCad-DesignRules); [kicad-druid](https://github.com/Cimos/kicad-druid)
- kicad-druid's CI gates on the rule file compiling (sentinel rule) because rules can be dropped silently. — [kicad-druid](https://github.com/Cimos/kicad-druid)
- Machine-readable output for the diff: `--format json`; one-violation-per-track vs all is controlled by `--all-track-errors`; severity filter flags decide what appears; exit code 5 on any violation. — [KiCad 9.0 CLI manual](https://docs.kicad.org/9.0/en/cli/cli.html)
- CLI and GUI results have been reported to differ, and custom-rule exclusions behaved differently under the CLI. — [KiCad forum thread](https://forum.kicad.info/t/cli-erc-drc-gives-different-output-than-running-manually-in-gui/55207); [KiCad GitLab issue 24264](https://gitlab.com/kicad/code/kicad/-/issues/24264)
- Arc/circle approximation in KiCad defaults to 0.005 mm maximum error, a floor on how closely two engines can agree near a limit. — [KiCad 9.0 PCB Editor manual](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)

### Inferences
A workable protocol (design, not sourced fact):

1. **One rule source, two renderings.** Keep the rule values as data (track, clearance, ring, hole, hole-to-hole, edge). Generate both the kernel's config and the `.kicad_dru` (plus Board Setup minimums in `.kicad_pro`) from it, so a disagreement is an engine disagreement, not a config drift.
2. **Corpus.** (a) every board the engine produces for the templates and composed projects; (b) hand-made minimal boards, one feature pair each (track–track, track–pad, track–via, via–via, pad–edge, hole–hole, pad ring); (c) randomly placed/routed boards for volume.
3. **Seeded violations (mutation testing of both checkers).** From a clean board apply exactly one mutation and expect exactly one new finding of the matching class: move a track to (clearance − ε); narrow a track to (min − ε); shrink a via pad so ring < min; enlarge a drill; move copper to (edge clearance − ε); place two holes closer than hole-to-hole; delete a segment (expect unconnected); add a bridge between two nets (expect short); overlap two courtyards. Also seed the just-legal twin at (limit + ε) and expect no finding — this is what catches off-by-epsilon and wrong-reference-point bugs (centre-to-centre vs edge-to-edge, finished hole vs tool size).
4. **Normalise before diffing.** Map each tool's rule names to a shared class; key findings by class + the unordered pair of object ids (or rounded location); collapse KiCad's per-segment duplicates unless `--all-track-errors` is mirrored in the kernel; compare sets, then counts. Use a tolerance band (a few µm) around every limit and classify differences inside the band as "numerical", outside as "real".
5. **Triage every disagreement three ways:** kernel bug, exporter bug (the `.kicad_pcb` does not describe the same geometry), or semantic difference (e.g. KiCad measuring to a hole's copper vs the kernel measuring to its drill). Clearance Resolution in the GUI explains KiCad's side. Record semantic differences as documented, tested exceptions.
6. **Prove the oracle is live.** A run where KiCad reports zero on a seeded board is a harness failure (rule dropped, severity ignored, zone not filled), not a pass — the sentinel-rule idea applied to every rule class.
7. **Gate.** CI fails on any un-triaged disagreement; pin the KiCad version (results can change between 9.0.x and 10.0.x) and re-baseline deliberately on upgrade.

- What this buys: a claim of the form "on N boards and M seeded faults the kernel and KiCad 9.0.x agree on every finding of classes C1…Ck", which is evidence about the kernel rather than about one board. What it does not buy: correctness on classes KiCad was never asked about, or on geometry the exporter cannot express.
- KiCad's own QA boards (`qa/data/pcbnew`) are a ready-made adversarial corpus in the opposite direction if the engine ever gains a `.kicad_pcb` importer.

### Gaps
- No published write-up of differential testing between an independent DRC engine and KiCad was found; the protocol above is constructed from how KiCad and the rule-set projects test themselves.
- The DRC JSON field names needed for the normaliser were not confirmed (see section 1 gaps).
- Licence terms for reusing KiCad's QA boards (KiCad is GPL, as far as I know) were not checked.
- KiCad is not known to be installed on the project machine; `kicad-cli --version` was not run in this session.
