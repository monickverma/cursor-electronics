# Manufacturability (DFM) and Assembly (DFA) Gate for Small PCBs: Engines, Rule Values, Formats, Automation Flows (as of 2026-10-09)

Reading conventions used throughout these notes:

- **[P]** = the page/file was fetched directly in this research session (2026-10-09) and the figure was read from it.
- **[S]** = taken from a search-engine summary of the page, or from a secondary/vendor-blog source; verify before hard-coding.
- All fab figures carry the access date 2026-10-09 unless a page date is given.
- "Brief" = a fact the assignment brief states was verified earlier by the project (kicad-cli exit code 5, JSON keys, 0.10/0.10 mm, 0.15 mm drill, kicad-druid MIT, no fab CI DFM API). These are not re-cited.
- Anything I could not source is in a Gaps list, sometimes with an explicitly labelled "unverified recall" pointer so the next person knows where to look. Do not treat those as findings.

---

## 1. Writing a .kicad_pcb from a custom IR so KiCad DRC acts as an independent second engine

### Takeaway
There is no officially supported standalone Python library for writing KiCad boards: KiCad's own position is IPC-API-only (GUI must be running in KiCad 9/10; headless arrives in KiCad 11) and the SWIG `pcbnew` module is slated for removal in KiCad 11. The lowest-risk path for Circuit OS is to emit the s-expression file directly from the `Board` IR (or via the KiCad-10-bundled `pcbnew` SWIG module as an interim), then normalise and check it with `kicad-cli pcb upgrade` and `kicad-cli pcb drc --refill-zones` as a separate GPL process.

### Cited Findings
- **[P]** `kicad-cli pcb drc` options in KiCad 10: `-o/--output`, `-D/--define-var`, `--format report|json`, `--all-track-errors`, `--schematic-parity`, `--units mm|in|mils`, `--severity-all`, `--severity-error`, `--severity-warning`, `--severity-exclusions`, `--exit-code-violations`, `--refill-zones` ("Refill all zones before running DRC. The board will not be saved after refilling zones unless `--save-board` is also used."), `--save-board`. — [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)
- **[P]** `kicad-cli pcb upgrade INPUT_FILE [--force]` re-saves a board in the current file format ("Re-save the input board file even if it is already in the current file format"). — [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)
- **[P]** `kicad-cli pcb export gerbers` has `--check-zones` ("Check zone fills and refill zones, if required, prior to export. Any zone fill updates are not saved in the board file"), `--no-x2`, `--no-netlist`, `--subtract-soldermask`, `--precision 5|6`, `--no-protel-ext`, `--use-drill-file-origin`, `--board-plot-params`, `--variant`. — [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)
- **[P]** `kicad-cli pcb export drill` supports `--format excellon|gerber`, `--drill-origin absolute|plot`, `--excellon-separate-th`, `--excellon-oval-format route|alternate`, `--generate-map`, `--generate-report`. — [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)
- **[P]** `kicad-cli pcb export pos` supports `--side front|back|both`, `--format ascii|csv|gerber`, `--units in|mm` (default **in**), `--bottom-negate-x`, `--use-drill-file-origin`, `--smd-only`, `--exclude-fp-th`, `--exclude-dnp`, `--variant`. — [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)
- **[P]** Other headless exports available: `pcb export ipc2581` (version B or C, default C; BOM column mapping flags), `pcb export odb` (zip/tgz), `pcb export ipcd356` (netlist for bare-board test), `pcb import` (pads/altium/eagle/cadstar/fabmaster, with `--report-format json`), and `jobset run -f <file.kicad_jobset> [--stop-on-error] [--output <dest>]`. — [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)
- **[S]** KiCad developer docs: the IPC API in KiCad 9 and 10 only talks to a running KiCad GUI instance; headless use is added for KiCad 11; there are no plans for a standalone file-manipulation library outside the IPC model; the SWIG bindings are planned for removal in KiCad 11.0. — [KiCad dev docs: APIs and bindings](https://dev-docs.kicad.org/en/apis-and-binding/index.html), [PCB Python bindings](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/index.html), [IPC API for add-on developers](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/)
- **[S]** `kicad-python` (official IPC bindings, "kipy"): requires KiCad 9.0+ running with the API server enabled; "it is not possible to use kicad-python to manipulate KiCad design files without KiCad running"; release 0.7.0 dated 2026-04-17 (features requiring KiCad 10) and 0.8.0 dated 2026-08-30. — [kicad-python on PyPI](https://pypi.org/project/kicad-python/)
- **[S]** Real-world IPC friction on KiCad 10: a plugin attaching on KiCad 9 failed on KiCad 10 (March 2026 forum thread); a KiCAD-MCP-Server PR reports kicad-python 0.7.1 + KiCad 10.0.5 connection failures needing code changes. — [KiCad forum thread](https://forum.kicad.info/t/kicad-ipc-api-attached-to-kicad-9-but-not-to-kicad-10/68030), [KiCAD-MCP-Server PR #378](https://github.com/mixelpixx/KiCAD-MCP-Server/pull/378)
- **[P]** `kiutils` (mvnmgrx): licence **GPL-3.0**; self-description "Simple and SCM-friendly KiCad file parser based on Python dataclasses for KiCad 6.0 and up"; the repo page makes no statement about KiCad 8/9/10; 478 commits, 10 open issues; no release date visible. — [kiutils GitHub](https://github.com/mvnmgrx/kiutils)
- **[S]** A separate `atait/kicad-python` project describes itself as a "Cross-version python API for KiCAD pcbnew v5-v10" for action plugins and headless use (wraps SWIG pcbnew; name collides with the official IPC package). — [atait/kicad-python](https://github.com/atait/kicad-python)
- **[P]** Official Docker image: `kicad/kicad` on Docker Hub, mirrored on GitHub Packages under the KiCad org; intended for `kicad-cli` only; "Using the GUI environment via Docker is not supported". The download page does not document the tag scheme. — [kicad.org Docker page](https://www.kicad.org/download/docker/)
- **[S]** Tags `kicad/kicad:9.0` and `kicad/kicad:9.0.3` are used in community CI configs (GitLab job running `kicad-cli jobset run`). No source found in this session that lists a `10.0` tag. — [Docker Hub kicad namespace](https://hub.docker.com/u/kicad)
- **[P]** kicad-druid warns that custom-rule layer names must be the file-format names (e.g. `F.SilkS`, not `F.Silkscreen`): "An unrecognised layer makes KiCad reject the whole rule file, and `kicad-cli` reports nothing." — [kicad-druid README](https://github.com/Cimos/kicad-druid)

### Inferences
- Because `kiutils` is GPL-3.0, importing it into an AGPL-3.0 backend is licence-compatible in the GPLv3/AGPLv3 combination sense, but it is unconfirmed on KiCad 9/10 formats; a self-written emitter has no licence or staleness exposure. The `.kicad_pcb` format is plain s-expressions, and Circuit OS only needs a small subset (header, general thickness, layers table, setup, nets, footprints with pads and courtyard graphics, segments, vias, Edge.Cuts graphics, optional zones). Recommendation: own minimal writer targeting one pinned format version, immediately round-tripped through `kicad-cli pcb upgrade --force` so KiCad itself rewrites it canonically; fail the gate if upgrade fails.
- Net classes, clearance/track-width minimums, and DRC severities live in the sibling `.kicad_pro` (JSON) and custom rules in `<project>.kicad_dru`; the exporter must write all three with the same basename, or KiCad DRC will silently run with KiCad defaults. (Basename requirement is supported by the labtroll instruction "rename it to match your project name your-project.kicad_dru" — [labtroll/KiCad-DesignRules](https://github.com/labtroll/KiCad-DesignRules).)
- `--refill-zones` on `pcb drc` and `--check-zones` on gerber export together answer "can zones be refilled headless": yes, in KiCad 10, without a GUI. Use `--save-board` only on a scratch copy so the fill becomes part of the artefact that is later plotted.
- Running `kicad-cli` (GPL-3.0-or-later) as a subprocess or a Docker container and exchanging files/JSON is an arm's-length use; it does not make KiCad part of the AGPL work. The same reasoning applies to Freerouting (GPL-3.0) and KiBot (AGPL-3.0, which is the same licence as the backend anyway). This is the standard "separate process" reading, not legal advice.
- On Windows the same binary is `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`; the gate should locate it by env var and record `kicad-cli version` in every report, because DRC behaviour differs across 8/9/10 (see section 2 forum reports).
- The existing Specctra DSN exporter's missing via padstack matters twice: Freerouting cannot place vias without one, and the reimported board would then have no via geometry for KiCad to check.

### Gaps
- I did not fetch the KiCad file-format developer page (unverified recall: `https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/`), so the exact token list for KiCad 10 (`(version ...)`, `(generator ...)`, `(net ...)`, `(footprint ... (pad ...))`, `(segment ...)`, `(via ...)`, `(zone ...)`, `(gr_line ... (layer "Edge.Cuts"))`) is not source-verified here. Generate a reference board in KiCad 10.0.1 and diff against it.
- Not researched in this session (no sourced claims): `kicad-skip`, `KicadModTree`, `kicad-sexp`, `pcbflow`, `circuit-synth`, atopile's and tscircuit's KiCad writers. Their licences, maintenance state and KiCad-10 compatibility remain unknown.
- kiutils' latest release date and whether it round-trips KiCad 9/10 boards could not be determined from the repo page.
- Whether a `kicad/kicad:10.0` Docker tag exists was not confirmed; check `hub.docker.com/r/kicad/kicad/tags`.
- Whether `--exit-code-violations` counts warnings, or only the severities selected with `--severity-*`, was not confirmed from the docs (the description was truncated). Parse the JSON instead of trusting the exit code.

---

## 2. KiCad DRC as an oracle: check types, default severities, blind spots, custom rule language

### Takeaway
KiCad master defines 76 DRC violation types in seven groups, and several that matter for a DFM/DFA gate are **not errors by default** (copper sliver, connection width, hole-to-hole, silk checks are warnings; missing courtyard and footprint-type mismatch are ignored), so the gate must write explicit severities into `.kicad_pro` and request `--severity-all`. The custom-rule language covers fab minimums well (kicad-druid's 2-layer JLCPCB file is a working example) but a rule-file syntax or layer-name error is swallowed silently by `kicad-cli`, which is why a sentinel rule is mandatory.

### Cited Findings
- **[P]** Complete machine-name list from KiCad master `drc_item.cpp` (group in brackets):
  - Electrical: `shorting_items`, `clearance`, `creepage`, `tracks_crossing`, `starved_thermal`, `via_dangling`, `track_dangling`.
  - Design for Manufacturing: `copper_edge_clearance`, `hole_clearance`, `hole_to_hole`, `holes_co_located`, `connection_width`, `track_width`, `track_angle`, `track_segment_length`, `annular_width`, `drill_out_of_range`, `via_diameter`, `microvia_drill_out_of_range`, `malformed_microvia_stack_span`, `microvia_stack_not_filled`, `microvia_stack_depth`, `microvia_aspect_ratio`, `microvia_crosses_core`, `courtyards_overlap`, `missing_courtyard`, `malformed_courtyard`, `invalid_outline`, `via_stitch_overlap`, `copper_sliver`, `solder_mask_bridge`, `tuning_profile_track_geometries`, `track_on_post_machined_layer`, `track_not_centered_on_via`.
  - Schematic Parity: `unconnected_items`, `duplicate_footprints`, `missing_footprint`, `extra_footprint`, `net_conflict`, `footprint_symbol_mismatch`, `footprint_filters_mismatch`, `footprint_symbol_field_mismatch`.
  - Signal Integrity: `length_out_of_range`, `net_chain_stub_length`, `net_chain_return_path`, `net_chain_tuning_profiles`, `skew_out_of_range`, `too_many_vias`, `diff_pair_gap_out_of_range`, `diff_pair_uncoupled_length_too_long`.
  - Readability: `silk_over_copper` (title "Silkscreen clipped by solder mask"), `silk_edge_clearance`, `silk_overlap` (title "Silkscreen clearance"), `text_height`, `text_thickness`, `mirrored_text_on_front_layer`, `nonmirrored_text_on_back_layer`.
  - Miscellaneous: `items_not_allowed`, `text_on_edge_cuts`, `isolated_copper`, `padstack`, `pth_inside_courtyard`, `npth_inside_courtyard`, `item_on_disabled_layer`, `lib_footprint_issues`, `lib_footprint_mismatch`, `unresolved_variable`, `assertion_failure`, `footprint`, `footprint_type_mismatch`, `through_hole_pad_without_hole`, `footprint_scaled_with_pads`, `missing_tuning_profile`.
  - Internal (no user severity): `padstack_invalid`, `generic_warning`, `generic_error`.
  — [KiCad source: pcbnew/drc/drc_item.cpp (master)](https://gitlab.com/kicad/code/kicad/-/raw/master/pcbnew/drc/drc_item.cpp)
- **[P]** Default severities from the `BOARD_DESIGN_SETTINGS` constructor (everything not listed is ERROR):
  - WARNING: `holes_co_located`, `hole_to_hole`, `track_dangling`, `via_dangling`, `microvia_crosses_core`, `microvia_stack_not_filled`, `copper_sliver`, `isolated_copper`, `padstack`, `footprint_scaled_with_pads`, `missing_footprint`, `duplicate_footprints`, `extra_footprint`, `net_conflict`, `footprint_symbol_mismatch`, `footprint_symbol_field_mismatch`, `silk_overlap`, `silk_over_copper`, `silk_edge_clearance`, `text_height`, `text_thickness`, `connection_width`, `lib_footprint_issues`, `lib_footprint_mismatch`, `mirrored_text_on_front_layer`, `nonmirrored_text_on_back_layer`, `missing_tuning_profile`.
  - IGNORE: `missing_courtyard`, `footprint_filters_mismatch`, `footprint_type_mismatch`, `tuning_profile_track_geometries`, `track_not_centered_on_via`.
  - Explicit ERROR: `pth_inside_courtyard`, `npth_inside_courtyard`.
  — [KiCad source: pcbnew/board_design_settings.cpp (master)](https://gitlab.com/kicad/code/kicad/-/raw/master/pcbnew/board_design_settings.cpp)
- **[P]** Board-level DRC minimums stored in board settings (names): `m_MinClearance`, `m_MinConn` (connection width), `m_TrackMinWidth`, `m_ViasMinAnnularWidth`, `m_ViasMinSize`, `m_MinThroughDrill`, `m_HoleClearance`, `m_HoleToHoleMin`, `m_CopperEdgeClearance`, `m_SilkClearance`, `m_MinSilkTextHeight`, `m_MinSilkTextThickness`, `m_SolderMaskMinWidth`, `m_SolderMaskToCopperClearance`, `m_MinResolvedSpokes`. Numeric defaults are macros in headers not read here. — [board_design_settings.cpp](https://gitlab.com/kicad/code/kicad/-/raw/master/pcbnew/board_design_settings.cpp)
- **[P]** Each rule can be set to error, warning or ignored; custom rules "will only be applied if there are no errors in the custom rules definitions". — [KiCad 10 PCB editor manual](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)
- **[P]** Custom-rule constructs shown in the KiCad 10 manual's examples: constraints `clearance`, `courtyard_clearance`; expression members `A.hasComponentClass('...')`, `A.intersectsArea(...)`, `A.memberOfSheet(...)`, `A.getField(...)`, `A.Reference`, `A.Layer`, `A.Orientation`, `A.Library_Link`. Example: `(rule "Power component clearance" (condition "A.hasComponentClass('Power_Stage')") (constraint clearance (min 0.3mm)))`. — [KiCad 10 PCB editor manual](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)
- **[P]** Constraint types exercised by a real, CI-tested 2-layer fab file (kicad-druid `JLCPCB-2L-1oz.kicad_dru`, 38 rules): `hole_size` (min/max), `annular_width`, `via_diameter`, `assertion`, `hole_to_hole`, `clearance`, `hole_clearance`, `track_width`, `physical_clearance` (present but commented out, for same-net spacing 0.25 mm), `diff_pair_gap`, `text_thickness`, `text_height`, `silk_clearance`, `edge_clearance`; a `(layer "?.SilkS")` clause for legend rules; `opt` values used for advisory impedance widths. The file notes that KiCad applies the **last matching rule**, so general rules are placed before the specific ones. — [kicad-druid JLCPCB-2L-1oz.kicad_dru](https://raw.githubusercontent.com/Cimos/kicad-druid/main/JLCPCB/JLCPCB-2L-1oz.kicad_dru)
- **[P]** Examples of `assertion` usage in that file: SMD pad both dimensions >= 0.125 mm; vias must not be blind/buried/micro; plated slot length >= 2x width. — [kicad-druid JLCPCB-2L-1oz.kicad_dru](https://raw.githubusercontent.com/Cimos/kicad-druid/main/JLCPCB/JLCPCB-2L-1oz.kicad_dru)
- **[S]** Further forms seen in forum/docs excerpts: file starts with `(version 1)`; `(severity warning|error|exclusion|ignore)`; `(constraint assertion "A.Line_Width >= 0.15mm")` on a silkscreen layer; `A.enclosedByArea('Shield*')`; `A.existsOnLayer('In2.Cu')`; `A.intersectsCourtyard('U14')`; constraints `edge_clearance`, `thermal_spoke_width`, `skew`. — [KiCad forum: custom design rules examples](https://forum.kicad.info/t/custom-design-rules-examples/43987), [KiCad forum: custom rules in 9.0.3](https://forum.kicad.info/t/custom-rules-in-v9-0-3/63073)
- **[S]** Version-drift evidence: a KiCad 9.0.0 user reported `A.intersectsCourtyard('U14')` conditions that worked in KiCad 8 no longer behaving; another 9.x thread reports a rule ignoring an Edge.Cuts distance and falling back to the board-setup clearance. — [KiCad forum: custom DRC KiCad 8 vs 9](https://forum.kicad.info/t/custom-drc-bga-breakout-clearance-kicad-8-vs-kicad-9/59353), [KiCad forum: DRC Edge.Cuts problem KiCad 9](https://forum.kicad.info/t/drc-edge-cuts-problem-kicad9/61585)
- **[S]** On 1- or 2-layer boards, inner-layer rules in the fab rule sets are simply never selected. — [KiCad forum: design rules for JLCPCB](https://forum.kicad.info/t/design-rules-for-jlcpcb/46087)
- **[S]** Starved thermals "are often missed by basic design rule checks" in general EDA tools (vias pass spacing while spokes are interrupted). — [Siemens: 4 less obvious PCB DFM violations](https://blogs.sw.siemens.com/electronic-systems-design/2020/03/16/4-less-obvious-pcb-dfm-violations/)

### Inferences
- What KiCad DRC covers natively for this project's scope (from the item list): clearance, hole clearance, hole-to-hole, annular width, track width, via diameter, drill range, copper-to-edge, courtyard overlap/missing/malformed, PTH/NPTH in courtyard, solder-mask bridge between different nets, silk clipped by mask/edge, silk overlap, text height/thickness, copper sliver, connection width (neck-down), starved thermal, isolated copper, dangling track/via, track angle (new item: usable for acute-angle checks), footprint type mismatch, library mismatch, schematic parity.
- What the item list shows it does **not** have: no paste/stencil checks (no area-ratio item), no acid-trap item as such (only `track_angle` and `copper_sliver` as proxies), no solder-mask **sliver/web width between same-net openings** item separate from `solder_mask_bridge` (the board setting `m_SolderMaskMinWidth` modifies generated mask rather than reporting), no copper balance, no panel/rail/fiducial/tooling-hole checks, no component height or shadowing, no tombstone/thermal-symmetry check, no pick-and-place rotation check, no test-point access check. These must be written in Circuit OS or delegated.
- Gate configuration implied by the default severities: set `missing_courtyard`, `footprint_type_mismatch` to error; promote `copper_sliver`, `connection_width`, `hole_to_hole`, `silk_over_copper`, `silk_overlap`, `text_height`, `text_thickness`, `isolated_copper`, `track_dangling`, `via_dangling` to error (or keep as warning but fail the gate on a policy table keyed by machine name). Always invoke with `--severity-all --format json --all-track-errors`.
- Since Circuit OS has no schematic file, `--schematic-parity` cannot be used; connectivity parity must instead come from `unconnected_items` in the JSON plus the project's own netlist comparison (and optionally an IPC-D-356 export compared with the IR netlist).
- Oracle caveat for the trust ladder: KiCad DRC is an independent implementation (different geometry kernel, different broad phase), so agreement raises confidence, but it is "evidence", not "sound": it has version-specific regressions (forum reports above) and silently drops a broken rule file.

### Gaps
- The official custom-rules reference (full constraint table, every expression function, `disallow` item types, `zone_connection`, `min_resolved_spokes`, `solder_mask_expansion`, `solder_paste_abs_margin`, `courtyard_clearance` semantics) was **not retrieved**: the 733k-character manual page truncated before that section and the source help file URL returned 404. The names `insideCourtyard`, `insideFrontCourtyard`, `isPlated`, `Pad_Type`, `Fabrication_Property` are therefore unverified in these notes. Authoritative source: Board Setup > Design Rules > Custom Rules > Syntax Help in the installed KiCad 10.0.1.
- The numeric values of KiCad's default minimums (DEFAULT_MINCLEARANCE etc.) were not read.
- No primary source was found stating explicitly "KiCad DRC does not check acid traps / paste / copper balance"; the blind-spot list above is derived from absence in the item list.
- KiCad 9 vs 10 differences in the item list were not diffed (the list above is `master`, which may include items newer than 10.0.1, e.g. the net-chain and tuning-profile items).

---

## 3. Fab capability data and machine-readable rule sets; conservative common-denominator profile

### Takeaway
JLCPCB and PCBWay sit at 0.10/0.10 mm and 0.15 mm drill; OSH Park, Aisler (HASL) and Lion Circuits are materially looser-capable (0.15 to 0.20 mm features, 0.25 to 0.40 mm drills, 0.3 to 0.38 mm edge clearance), so a single portable profile must be driven by the weakest fab per parameter. kicad-druid (MIT) is the best maintained machine-readable source: TOML capability files generating `.kicad_dru` per fab and layer count, with paired test boards and CI.

### Cited Findings

**JLCPCB, 1-2 layer FR-4 [P], accessed 2026-10-09** — [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- Track/space 1 oz: 0.10/0.10 mm; 2 oz: 0.16/0.16 mm; track width tolerance +/-20%.
- Min drill 0.15 mm (2-layer); min via 0.15 mm hole / 0.25 mm diameter; preferred min via hole 0.2 mm; via diameter should exceed hole by 0.10 mm (0.15 mm preferred); 1-layer: 0.3 mm hole / 0.5 mm via.
- Hole tolerance PTH +0.13/-0.08 mm; hole position tolerance +/-0.075 mm; average hole plating 18 um.
- PTH annular ring (2-layer, 1 oz): 0.25 mm recommended, 0.18 mm absolute minimum; NPTH pad ring >= 0.45 mm recommended.
- Via hole-to-hole 0.2 mm; pad hole-to-hole 0.45 mm; via-to-track 0.2 mm; PTH-to-track 0.28 mm min (0.35 mm recommended); NPTH-to-track 0.2 mm; pad-to-track 0.1 mm; SMD pad-to-pad (different nets) 0.15 mm; same-net track spacing 0.25 mm.
- Copper to routed edge 0.2 mm; to V-cut edge 0.4 mm.
- Solder mask bridge at 1 oz: 0.10 mm (green/red/yellow/blue/purple), 0.13 mm (black/white); 2 oz: 0.20 mm; mask expansion 1:1 (fab applies its own); mask opening to neighbouring trace >= 0.09 mm.
- Silkscreen: line width 0.15 mm, text height 1.0 mm, width:height 1:6, pad-to-silk 0.15 mm.
- Thickness 0.4/0.6/0.8/1.0/1.2/1.6/2.0 mm (tolerance +/-10% at >= 1.0 mm); outer copper 1/2/2.5/3.5/4.5 oz.
- Slots: plated min width 0.5 mm (length >= 2x width); non-plated min 1.0 mm; min NPTH 0.50 mm.
- Castellated holes: diameter >= 0.5 mm, hole to board edge >= 1 mm, hole-to-hole >= 0.5 mm, min board 10 x 10 mm, min thickness 0.6 mm.
- V-cut: copper clearance 0.4 mm, panel 70 x 70 mm min to 475 x 475 mm max, groove angle 25 deg, min V-cut spacing 2 mm. Mouse bites: hole 0.5 to 0.8 mm, spacing 0.2 to 0.3 mm, tab >= 4 mm (5 mm with mouse bites), board spacing 1.6 or 2 mm, tooling edge >= 3 mm (5 mm for SMT assembly).
- Board size min 3 x 3 mm; routed outline tolerance +/-0.2 mm. The page is internally inconsistent on 2-layer max size (670 x 600 mm vs 1020 x 600 mm) and thickness range (0.4 to 3.2 vs 0.4 to 4.5 mm).

**PCBWay, "Standard PCB" tier [P], accessed 2026-10-09** — [PCBWay capabilities](https://www.pcbway.com/capabilities.html)
- Track/space 0.1/0.1 mm; min drill 0.15 mm (sub-0.2 mm may cost extra); min annular ring 0.15 mm; PTH tolerance +/-0.08 mm, NPTH +/-0.05 mm.
- Thickness 0.2 to 3.2 mm; outer copper 1 to 8 oz; max size 600 x 1200 mm (1-2 layer); min 3 x 3 mm; outline tolerance +/-0.2 mm routed, +/-0.5 mm V-score.
- Silkscreen min width 0.15 mm, min height 0.8 mm, ratio 1:5; min plated half-hole 0.4 mm; break-routing spacing between boards >= 1.6 mm.
- Only listed under the "Advanced PCB" tier ("normal process" column): hole-to-hole >= 16 mil for component holes, >= 11 mil for vias <= 0.45 mm; line to board edge (CNC) 0.25 mm; plated slot >= 0.5 mm, non-plated >= 0.8 mm; castellated hole >= 0.5 mm with >= 0.3 mm edge-to-edge; green mask bridge 4 mil (< 2 oz), 5 mil (>= 2 oz); mask opening >= 2 mil; V-score board thickness 0.6 to 2.4 mm, remaining web >= 0.25 mm.

**OSH Park, 2-layer service [P], accessed 2026-10-09** — [OSH Park two-layer service](https://docs.oshpark.com/services/two-layer/)
- Track/space 6/6 mil (0.1524 mm); min drill 10 mil (0.254 mm); annular ring 5 mil (0.127 mm); recommended hole-to-hole 5 mil; min slot 20 mil (0.508 mm, drilled slots only).
- Board edge clearance 15 mil (0.381 mm); mask minimum web 4 mil (0.1016 mm), mask alignment up to 3 mil (0.0762 mm); silkscreen line 5 mil recommended (3 mil for short features).
- 1.6 mm nominal, 1 oz copper; min board 0.25 x 0.25 in, max 16 x 22 in; drill size tolerance max +/-2.5 mil, positional max 2 mil; outline mill 1.72 mm, interior mill 1.01 mm. No KiCad rule file is linked from this page.

**Aisler, 2-layer [P for the community rules post; S for the rest]** — [Aisler community: PCB design rules](https://community.aisler.net/t/pcb-design-rules/41), [Aisler community: 2-layer 1.6 mm HASL rules](https://community.aisler.net/t/2-layer-1-6mm-hasl-design-rules/3735)
- 35 um copper: HASL 200 um trace / 150 um space; ENIG 125/125 um. 70 um copper: HASL 225/225 um; ENIG 175/175 um. Min drill >= 0.3 mm HASL, >= 0.25 mm ENIG. Castellated holes not allowed on HASL (ENIG required). Post dated 2021-12-17; a search summary describes a rules page "last updated 05/12/2024" with the same figures [S].
- [S] Recommended via annular ring 200 um; drill spacing 300 um; staff state plated holes are compensated by 150 um in CAM (a 0.65 mm drill becomes 0.8 mm), and that the specified drill is the finished size. — [Aisler community: annular ring thread](https://community.aisler.net/t/through-hole-1-27mm-pin-header-manufacturing-min-annular-ring-size-not-reached/2781)
- [S] Aisler says it provides KiCad templates / design-rule files on its GitHub. — [Aisler community: KiCad PCB templates](https://community.aisler.net/t/kicad-pcb-templates-for-download/3033)
- The old help URL `aisler.net/help/design-rules-and-specifications/design-rules` now 301-redirects to the community site (observed 2026-10-09).

**Eurocircuits [P]** — [Eurocircuits PCB design guidelines: classification](https://www.eurocircuits.com/pcb-design-guidelines-classification/)
- Pattern classes (track, gap, outer and inner annular ring; the smallest feature sets the class) and drill classes (based on production TOOLSIZE, not finished ENDSIZE) are published only as an image ("May 2024 V3"); values not machine-readable from the page.
- Text rules: minimum inner-pad isolation = IAR + 0.075 mm with a 0.200 mm floor; connected non-plated holes should have >= 0.30 mm annular ring; design with margin above class limits.

**Lion Circuits (India), rigid PCB [P], accessed 2026-10-09** — [Lion Circuits manufacturing capabilities](https://lioncircuits.com/pcb-manufacturing-capabilities)
- Service tiers MII / Custom / Rush. Track/space at 1 oz: 6/6 mil (MII, Custom), 8/8 mil (Rush). Mechanical drill 0.35 to 6.3 mm (MII), 0.25 to 6.3 mm (Custom), 0.4 to 6.3 mm (Rush).
- Annular ring 0.152 mm; via-to-via 12 / 10 / 14 mil; via-to-trace 12 / 10 / 14 mil; circuit-to-edge 0.3 mm; solder mask dam 0.152 mm (Rush 0.25 mm); silkscreen height 0.5842 mm, line 0.152 mm; silk-to-pad 6 mil (Rush 8 mil); min slot 0.8 mm; min board 3 x 3 mm; castellation only in Custom; MII covers 2- and 4-layer.

**PCB Power (India) [S, weak]** — [PCB Power customer response hosted on TI E2E (undated)](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/234/PCB_5F00_Manf_5F00_comments.doc)
- An undated customer-inquiry response lists 1 oz outer track/space 0.10/0.10 mm, 2 oz 0.125/0.125 mm, minimum annular ring 0.100 to 0.105 mm, minimum finished via 0.150 mm, TOOLSIZE = ENDSIZE + 0.10 mm (vias), + 0.15 mm (PTH), + 0.05 mm (NPTH), with annular ring computed from the tool diameter. Not a published capability sheet.

**Machine-readable rule sets**
- **[P]** kicad-druid (Cimos), **MIT**: folders `JLCPCB/`, `PCBWay/`, `Generic/` (stricter of the two fabs per limit); files `<FAB>.kicad_dru` (4L 1 oz), `<FAB>-2L-1oz.kicad_dru`, `<FAB>-4L-2oz.kicad_dru`, `<FAB>-6L-1oz.kicad_dru`; generated from `capabilities/<FAB>.toml` by `tools/generate_dru.py` (do not hand-edit); KiCad 8 syntax, "forward-compatible with KiCad 9 and 10"; test boards saved in KiCad 9 format with intentionally passing and failing footprints (`JLCPCB/TESTBOARD.md`); CI: `generate_dru.py --check`, `tools/lint_dru.py` (s-expr syntax, version header, duplicate names, fab prefixes, lowercase item types, layer names), and a `kicad-cli pcb drc` workflow over all twelve files in which "a sentinel rule must fire or the job fails". — [kicad-druid](https://github.com/Cimos/kicad-druid)
- **[P]** kicad-druid JLCPCB 2-layer values actually encoded: hole 0.15 to 6.3 mm; via hole >= 0.15; via annular >= 0.05 (!); PTH annular >= 0.18; NPTH annular >= 0.45; NPTH hole >= 0.5; castellated hole >= 0.5; SMD pad >= 0.125 both ways; plated slot >= 0.5 with length >= 2x width; non-plated slot >= 1.0; via-via hole 0.2; pad-pad hole 0.45; same-net hole-hole 0.254; pad/via copper clearance 0.127; SMD pad-pad 0.15; via hole-to-trace 0.2; PTH hole-to-trace 0.28; NPTH-to-trace 0.2; TH pad-to-trace 0.2; track width 0.1; track spacing 0.1; text thickness 0.15; text height 1.0; pad-to-silk 0.15; track-to-edge 0.2. No severity clauses; the published 2L file itself contains no sentinel rule. — [kicad-druid JLCPCB-2L-1oz.kicad_dru](https://raw.githubusercontent.com/Cimos/kicad-druid/main/JLCPCB/JLCPCB-2L-1oz.kicad_dru)
- **[S]** `Cimos/KiCad-CustomDesignRules` is the predecessor (moved to kicad-druid; old issues not migrated); it was forked from `labtroll/KiCad-DesignRules` (Morten Hattesen), a KiCad 7 JLCPCB rule set. `ziteh/kicad-design-rules` also exists. — [Cimos/KiCad-CustomDesignRules](https://github.com/Cimos/KiCad-CustomDesignRules), [labtroll/KiCad-DesignRules](https://github.com/labtroll/KiCad-DesignRules), [ziteh/kicad-design-rules](https://github.com/ziteh/kicad-design-rules)
- **[S]** An Adom wiki project generates `.kicad_dru` for multiple fabs with each number citing the vendor page and read date. — [Adom wiki: PCB design rules](https://wiki.adom.inc/adom/pcb-design-rules/skills)
- **[P]** KiKit (MIT) advertises "manufacturer presets" for automated gerber and assembly-data export. — [KiKit GitHub](https://github.com/yaqwsx/KiKit)

### Inferences
- **Recommended conservative profile "hobby-2L-portable"** (derived by taking the weakest published value per parameter among JLCPCB, PCBWay standard, OSH Park, Aisler HASL, Lion MII, then rounding up; Lion "Rush" is excluded and gets its own stricter overlay):

| Parameter | Value | Binding fab(s) and reasoning |
|---|---|---|
| Min track width | 0.20 mm (default route 0.25 mm) | Aisler HASL 0.20; Lion/OSH 0.152 |
| Min copper spacing | 0.20 mm | Aisler HASL 0.15, Lion/OSH 0.152; rounded up; Lion Rush needs 0.2032 (8 mil), so use 0.21 if Rush is in scope |
| Min via drill | 0.40 mm | Lion MII 0.35, Aisler HASL 0.30, OSH 0.254 |
| Min via diameter | 0.80 mm (0.20 mm ring) | Aisler 0.20 ring recommendation; Lion 0.152 |
| PTH pad annular ring | 0.25 mm | JLCPCB recommended 0.25 (0.18 absolute) |
| Hole-to-hole (wall to wall) | 0.50 mm | JLCPCB pad holes 0.45; PCBWay component holes 16 mil (0.406) |
| Hole-to-copper (other net) | 0.35 mm | JLCPCB PTH-to-track recommended 0.35; Lion via-to-trace 12 mil (0.305) |
| Copper to routed edge | 0.40 mm | OSH Park 0.381; Lion 0.30; equals JLCPCB V-cut 0.40 |
| Solder mask web/dam | 0.16 mm | Lion 0.152; others 0.10 |
| Silk line width | 0.16 mm | Lion 0.152; JLCPCB/PCBWay 0.15 |
| Silk text height | 1.0 mm | JLCPCB 1.0 |
| Silk to exposed pad | 0.16 mm | JLCPCB 0.15; Lion 6 mil |
| Plated slot width | 0.8 mm; non-plated 1.0 mm | Lion 0.8; JLCPCB NPTH slot 1.0 |
| Min NPTH | 0.5 mm | JLCPCB |
| SMD pad-to-pad (other net) | 0.20 mm | JLCPCB 0.15 plus mask-dam feasibility |
| Stackup | 1.6 mm, 1 oz | Common to all (OSH Park fixed) |
| Board size | >= 10 x 10 mm; <= 250 x 250 mm if JLCPCB-assembled | JLC castellation minimum; JLC assembly panel limit (section 7) |
| Castellations | disallowed in portable profile | Not on Aisler HASL / Lion MII |

- The kicad-druid `Via Annular Ring >= 0.05 mm` is far below the 0.18/0.25 mm PTH figures on the JLCPCB page; treat kicad-druid as "absolute fab limit" data and layer the conservative profile on top rather than adopting its numbers as targets.
- Model the profile the way kicad-druid does: one TOML per fab with `source_url` and `accessed` date per field, a generator emitting both the `.kicad_dru` and the native Circuit OS rule table, and a `--check` drift test. The "fab-rules" file should be data, never hand-edited rules.
- Drill semantics differ by fab (Aisler: finished size, +150 um compensation; PCB Power/Eurocircuits: annular ring computed from tool size, tool = finished + 0.10 to 0.15 mm; JLCPCB PTH tolerance +0.13/-0.08). The profile should therefore compute annular ring on `drill + 0.15 mm` as worst case; that is why 0.25 mm nominal ring is recommended even where 0.15 mm is published.

### Gaps
- Eurocircuits pattern-class and drill-class numbers (image only) were not extracted.
- No official OSH Park KiCad rule file was found on the service page; Aisler's actual GitHub rule file was not opened, so its values are unverified.
- PCBWay's standard-tier table omits hole-to-hole, copper-to-edge, mask dam and slot values; the advanced-tier "normal process" values were used as a proxy.
- PCB Power's current public capability sheet was not found; Robu and other Indian fabs were not researched.
- Aisler copper-to-edge, mask and silkscreen limits were not found; OSH Park and Aisler mask-expansion conventions not confirmed.
- The PCBWay kicad-druid file was not opened; "JLCPCB-Kicad-DRC" naming in the brief corresponds to the Cimos lineage as far as I could tell, but I did not find a separate repo by that exact name.

---

## 4. IPC classes and standards relevant to DFM

### Takeaway
Publicly summarised numbers converge on: IPC-2221 minimum external annular ring 0.05 mm (2 mil) as a finished requirement for all classes, with IPC-6012 Class 2 additionally tolerating up to 90 degrees of hole breakout and Class 3 none; hobby boards are reasonably treated as Class 2 design intent with Class 1/2 acceptance. All of these are secondary summaries; the standards themselves are paywalled.

### Cited Findings
- **[S]** IPC-2221 minimum annular ring commonly summarised as 2 mil external / 1 mil internal for Classes 1 to 3; IPC-6012 Class 2 permits breakout up to 90 degrees on external layers; Class 3 permits none ("lifted or fractured rings and drill breakouts are not allowed"). — [Altium: IPC-6012 Class 3 annular ring](https://resources.altium.com/p/meeting-standards-ipc-6012-class-3-annular-ring)
- **[S]** Conflict: JLCPCB's summary lists 0.050 mm for both external and internal layers in every class and 90 degrees for Class 1 external, whereas Altium's table gives Class 1 "less than 180 degrees". — [JLCPCB blog: annular rings](https://jlcpcb.com/blog/annular-rings-pcb-design); contradicted in part by [Altium](https://resources.altium.com/p/meeting-standards-ipc-6012-class-3-annular-ring)
- **[S]** IPC-2221 producibility levels: Level A general (preferred), Level B moderate (standard), Level C high (reduced). — [PCB Libraries forum](https://pcblibraries.com/forum/topic2586.html)
- **[S]** IPC-2222-derived through-hole sizing: minimum hole = maximum lead diameter + 0.25 mm (Level A), + 0.20 mm (Level B), + 0.15 mm (Level C); use the diagonal for square/rectangular leads. — [PCB-3D tutorial on IPC-7251/2222/2221 hole sizing](https://www.pcb-3d.com/tutorials/how-to-calculate-pth-hole-and-pad-diameter-sizes-according-to-ipc-7251-ipc-2222-and-ipc-2221-standards/)
- **[S]** IPC-7351 courtyard excess per side, commonly quoted: Level A (most) 0.50 mm, Level B (nominal) 0.25 mm, Level C (least) 0.10 mm; family-specific tables differ (e.g. chip components below 0603: 0.20 / 0.15 / 0.10 mm). Level B recommended as default. — [PCBSync: IPC-7351 guide](https://pcbsync.com/ipc-7351/), [Linked Electronics: courtyard clearance](https://www.linkedpcba.com/blog/component-courtyard-clearance-guide.html); a differing set (0.40 / 0.20 / 0.10) is cited at [PCB Libraries forum](https://www.pcblibraries.com/forum/placement-courtyard-excess_topic3372.html)
- **[P]** KiCad can export IPC-2581 revision B or C and IPC-D-356 headlessly. — [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)

### Inferences
- The fab-published annular rings (0.127 to 0.25 mm) are design values that already include drill wander and registration; the IPC 0.05 mm figure is what must remain on the finished board. With JLCPCB's stated hole position tolerance +/-0.075 mm and PTH size tolerance +0.13 mm, a designed 0.18 mm ring can finish near 0.18 - 0.075 - 0.065 = 0.04 mm, i.e. at the Class 2 edge; the 0.25 mm recommendation leaves about 0.11 mm. This supports encoding "ring >= 0.25 mm" as the gate threshold and "0.18 to 0.25 mm" as a warning band.
- Target statement for the project: design to IPC-2221 Level A/B producibility, Class 2 intent; never claim IPC conformance in output, since none of the numeric tables were read from the standards.

### Gaps
- IPC-2221B electrical clearance table (B1 to B4 voltage spacing), IPC-6012 and IPC-A-600 acceptance text, and the IPC-7351B courtyard tables were not read from primary documents (paywalled). For hobby low-voltage boards the fab spacing dominates, but mains-voltage creepage is out of scope here.
- No sourced statement was found on which IPC class hobby prototype fabs build to by default.

---

## 5. Classic DFM defects: who checks each, and algorithm sketches

### Takeaway
KiCad DRC already covers roughly half of the classic list (slivers, neck-downs, starved thermals, isolated copper, dangling stubs, mask bridges, silk-on-pad, hole and edge clearances); the rest (acid traps, mask slivers between same-net openings, annular-ring-after-wander, teardrops, via-in-pad tenting, fiducials, panel features) must be written against the `Board` IR, and all are simple polygon or raster operations at this board size.

### Cited Findings
- **[S]** Acid traps: acute or odd copper angles where etchant pools and can over-etch into opens; keep trace-to-pad angles at 45 or 90 degrees. — [EMA: top DFM issues](https://www.ema-eda.com/ema-resources/blog/top-dfm-issues-to-check-and-avoid-during-pcb-layout/)
- **[S]** Slivers: narrow wedges of copper or solder resist that can detach and redeposit, causing shorts; mitigate with a minimum photoresist width and same-net spacing rules (figure quoted: below 3 mil is problematic). — [Altium: preventing top DFM errors](https://resources.altium.com/p/preventing-top-dfm-errors-your-pcb-design)
- **[S]** Starved thermals: spokes interrupted so a pad or via is poorly or not connected to its plane while passing ordinary spacing checks; commonly missed by basic DRC. — [Siemens: 4 less obvious DFM violations](https://blogs.sw.siemens.com/electronic-systems-design/2020/03/16/4-less-obvious-pcb-dfm-violations/)
- **[P]** KiCad DRC item names that map to this list: `copper_sliver`, `connection_width`, `starved_thermal`, `isolated_copper`, `track_dangling`, `via_dangling`, `solder_mask_bridge`, `silk_over_copper`, `silk_overlap`, `silk_edge_clearance`, `hole_clearance`, `hole_to_hole`, `holes_co_located`, `annular_width`, `copper_edge_clearance`, `track_angle`, `track_not_centered_on_via`, `courtyards_overlap`, `pth_inside_courtyard`, `npth_inside_courtyard`. — [KiCad drc_item.cpp](https://gitlab.com/kicad/code/kicad/-/raw/master/pcbnew/drc/drc_item.cpp)
- **[P]** Fab numbers that parameterise the geometric tests: JLCPCB hole position tolerance +/-0.075 mm; PTH tolerance +0.13/-0.08 mm; same-net track spacing 0.25 mm; mask bridge 0.10 mm (0.13 black/white); mask opening to neighbouring trace 0.09 mm; recommended minimum PTH 0.5 mm to avoid mask or tin in the hole. — [JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- **[P]** OSH Park: mask web 4 mil, mask misalignment up to 3 mil; drill positional tolerance max 2 mil. — [OSH Park two-layer](https://docs.oshpark.com/services/two-layer/)
- **[S]** JLCPCB adds fiducials itself for SMT orders; its own guidance is a minimum of two, three recommended, 1 mm fiducials 3.85 mm from the panel edge, 2 mm tooling holes, 5 mm process edges. — [JLCPCB assembly FAQ](https://jlcpcb.com/help/article/pcb-assembly-faqs), [JLCPCB: process edges and positioning holes](https://jlcpcb.com/help/article/specifications-for-adding-process-edges-and-positioning-holes), [JLCPCB blog: fiducial marks](https://jlcpcb.com/blog/fiducial-marks)

### Inferences
Defect-by-defect decision table (KiCad = `kicad-cli pcb drc`; "write" = implement in Circuit OS against the IR, using Shapely or pyclipper on per-layer copper unions; all sketches are mine):

| Defect | Who checks | Algorithm sketch |
|---|---|---|
| Acid trap (acute angle) | Write (KiCad `track_angle` custom constraint as partial second opinion) | Per net and layer build a graph of segment endpoints; at each shared endpoint compute the interior angle between segment directions; flag < 90 deg. For track-to-pad entry, flag when the angle between the track axis and the pad edge it crosses is < 45 deg. Polygon version: union copper per layer, walk vertices, flag concave vertices with interior wedge angle < 60 deg whose arms are longer than ~2x min track. |
| Copper sliver / peelable | KiCad `copper_sliver` (warning by default) plus write | Morphological opening: `opened = copper.buffer(-w/2).buffer(+w/2)`; `slivers = copper.difference(opened)`; drop pieces with area below epsilon; `w` = profile min track. Do the same on the copper complement (gap slivers of resist) with `w` = min spacing. |
| Neck-down / narrow connection | KiCad `connection_width` | Same opening per net: if erosion by `w/2` splits one connected net polygon into several, the minimum connection is below `w`. |
| Starved thermal | KiCad `starved_thermal` (needs filled zones, so use `--refill-zones`) | Count spokes whose far end intersects the filled zone polygon; compare to minimum resolved spokes (2). |
| Solder-mask sliver / dam between fine-pitch pads | KiCad `solder_mask_bridge` covers different-net exposure only; write the web-width test | Mask openings = pad shape buffered by mask expansion. Web = distance between adjacent openings; flag when 0 < web < profile dam (0.16 mm). Also raster or opening test on the mask-positive polygon for slivers. Scope: SOIC (1.27 mm pitch) and SOT-23 pass easily; mainly a guard for future fine pitch. |
| Annular-ring breakout from drill wander | KiCad `annular_width` for nominal; write the tolerance version | Worst-case ring = (pad_dia - (drill + plating_comp + size_tol)) / 2 - position_tol. With JLCPCB numbers: comp 0.15, size_tol 0.13, position 0.075. Require >= 0.05 mm (IPC summary). Report as "bounded" rung because tolerances are published, not measured. |
| Teardrops | Write (advisory) | For each track-to-pad/via junction where track width < 0.5 x pad diameter and pad has a hole, recommend teardrop; purely advisory since fabs may add them (section 9). |
| Same-net spacing | Write, or KiCad `physical_clearance` custom rule | Pairwise distance between non-adjacent same-net primitives that are not connected within N hops; JLCPCB says 0.25 mm. Avoids resist slivers in U-turns. |
| Isolated copper island | KiCad `isolated_copper` | Zone-fill connected components with no pad or via. |
| Unterminated stub / antenna | KiCad `track_dangling`, `via_dangling` | Graph degree-1 endpoints not coincident with a pad or via. |
| Via-in-pad without tenting/plugging | Write | Via centre inside an SMD pad polygon and via not plugged: flag (solder wicking). Trivial point-in-polygon. |
| Silkscreen on pads | KiCad `silk_over_copper`, `silk_overlap` plus custom `silk_clearance` | Silk geometry intersect (mask openings buffered by 0.15 mm). |
| Missing fiducials | Write (advisory) | Count fiducial footprints per assembled side; advisory only because JLCPCB adds them. |
| Copper balance / thieving | Write (info only) | Copper area ratio top vs bottom from polygon union area; report, do not gate. |
| Hole-to-copper, NPTH clearance | KiCad `hole_clearance` plus custom rules | Distance from hole wall (drill radius) to other-net copper; values per section 3. |
| Component to board edge | Write, or KiCad custom `edge_clearance` on courtyards | Distance from courtyard polygon to outline; JLCPCB assembly: 2.5 mm body-to-edge (section 7). |
| Panel rails / tooling holes | Write if panelised; else skip | Boolean presence checks on the panel artefact. KiKit builds these. |
| Hole too close to hole | KiCad `hole_to_hole` (warning by default) | Wall-to-wall distance >= 0.5 mm. |

- For a <40-part, 2-layer board, exact polygon booleans are cheap; rasterisation is unnecessary. This matters for the trust ladder: buffer/union results are exact up to arc tessellation, and the tessellation error is boundable (choose chord error <= 1 um and report "bounded").
- The known broad-phase bug in the custom kernel (hidden track-to-track violations when clearance > (w1+w2)/2) is precisely the class of error an exact pairwise-distance pass over unioned copper, plus KiCad `clearance`, will expose; see section 12.

### Gaps
- No primary quantitative source was found for acid-trap angle thresholds or minimum sliver widths at the target fabs; the Sierra Circuits DFM handbook was not retrieved.
- No source found on whether copper balance matters for 2-layer 1.6 mm boards; whether the listed fabs add thieving on their own is unknown.
- No source found for a fab-published requirement on via-in-pad tenting at hobby tier.
- Whether KiCad's `copper_sliver` test covers track/pad copper or only zone fills was not verified.

---

## 6. Free DFM/CAM tools and what can be automated headless

### Takeaway
Only locally run open-source tools (KiCad DRC, plus Gerber libraries not verified here) are automatable under clear terms; every fab-provided checker found is either a GUI desktop program behind an account login (HQDFM), a browser tool (Eurocircuits Visualizer), or an order/quote API that requires an approved partner application and was not shown to return DFM findings.

### Cited Findings
- **[S]** HQDFM (NextPCB/HQ): free Windows desktop tool (~163 MB), accepts Gerber, ODB++ and KiCad files, advertises 1200+ DFM and DFA checks, requires login with a NextPCB/HQ Online account; described as Windows-only; no CLI or API documented in any result found. — [NextPCB: HQDFM download](https://www.nextpcb.com/hqdfm-download), [NextPCB: HQDFM user manual](https://www.nextpcb.com/blog/HQDFM-User-Manual)
- **[S]** JLCPCB API platform: developer portal at api.jlcpcb.com; free API access by application, reviewed against the applicant's order history and business; the PCB API "allows users to upload Gerber files, perform automated pricing, create PCB orders, and track production progress"; partners may not use the JLCPCB trademark/logo or "JLC" in URLs, with suspension of API access and associated accounts for violations. — [JLCPCB API platform](https://api.jlcpcb.com/), [JLCPCB online API access application](https://jlcpcb.com/help/article/jlcpcb-online-api-available-now)
- **[S]** `hatlabs/jlcpcb-cli` reads JLCPCB order data via browser login and direct HTTP requests; it is unofficial. — [hatlabs/jlcpcb-cli](https://github.com/hatlabs/jlcpcb-cli)
- **[S]** PCBWay partner API: PCB quotation, status review, place order, order tracking; assembly API listed as under construction; positioned as partner "API cooperation". — [PCBWay API cooperation](https://www.pcbway.com/api_cooperation.html), [PCBWay API for partners PDF](http://api-partner.pcbway.com/PCBWay%20API%20for%20Partners.pdf)
- **[S]** Aisler: no public API spec; in a February 2026 community thread Aisler staff said access keys are provided on a case-by-case basis; `AislerHQ/PushForKiCad` is its KiCad upload plugin. — [Aisler community: public API spec question](https://community.aisler.net/t/is-there-a-public-api-spec-for-part-service-and-assembly-upload/5528), [AislerHQ/PushForKiCad](https://github.com/AislerHQ/PushForKiCad/issues/49)
- **[S]** Eurocircuits PCB Visualizer: "fully automated interactive web tool integrated in the Eurocircuits customer account", HTML5 client, "over 700 predefined DRC & DFM rules"; no API found. — [Eurocircuits: how PCB Visualizer works](https://www.eurocircuits.com/how-does-pcb-visualizer-work/), [Eurocircuits Visualizer user guides](https://www.eurocircuits.com/user-guides/visualizer-user-guides/)
- **[S]** Lion Circuits advertises a free DFM check with orders. — [Lion Circuits: Make in India PCB](https://www.lioncircuits.com/make-in-india-pcb)
- **[P]** Fabrication export automation tools: KiKit (MIT; manufacturer presets, panelisation with mouse bites / V-cuts, stencils); KiBot (AGPL-3.0; see section 9). — [KiKit](https://github.com/yaqwsx/KiKit), [KiBot](https://github.com/INTI-CMNB/KiBot)
- **[S]** bennymeg's Fabrication Toolkit / JLC-Plugin-for-KiCad generates JLCPCB-format gerbers, BOM and CPL from the KiCad GUI and reads per-part rotation/offset fields. — [bennymeg/Fabrication-Toolkit](https://github.com/bennymeg/Fabrication-Toolkit), [bennymeg/JLC-Plugin-for-KiCad](https://github.com/bennymeg/JLC-Plugin-for-KiCad)

### Inferences
- Automation verdicts for the gate:
  - KiCad `kicad-cli` DRC: yes, headless on Linux Docker and Windows; GPL-3 as a separate process.
  - HQDFM: no. Windows GUI plus account login; no documented CLI; driving it by UI automation would be fragile and its terms were not reviewed. Use it manually as a human pre-order step.
  - JLCPCB / PCBWay APIs: quoting and ordering only, gated by partner approval; no evidence of DFM results in responses. Not usable as a CI check. Scraping the browser upload flow is not an accepted automation path (the brief already established no fab offers a CI DFM check).
  - Eurocircuits Visualizer and Aisler: browser/account tools; no automation path.
- Consequence: "fab DFM feedback" can only be a manual, recorded gate step (upload, screenshot/export, attach to the release record), ranked "evidence" at best on the trust ladder; the automated gate must stand on KiCad DRC plus the project's own geometric checks.
- A second independent artefact-level check is still possible offline: parse the exported Gerber/Excellon back into polygons and compare against the IR (round-trip equivalence), which catches exporter bugs that board-level DRC cannot see.

### Gaps
- Not researched (no sourced claims): JLCDFM (existence, capabilities, automation), gerbv, Gerbonara, pcb-tools, tracespace, Sierra Circuits Better DFM, InstantDFM, MacroFab API, CircuitHub, OSH Park upload preview, kicad-jlcpcb-tools (Bouni). Licences and maintenance status of the Gerber libraries need a dedicated check before adoption (unverified recall: Gerbonara is the maintained successor to pcb-tools; gerbv is GPL; confirm).
- Project-specific consequence: `plan/current_phase.md` (2026-10-09) records Gerber export "moved forward, with Gerbonara" as an open owner decision for verifier step 5. These notes contain **no sourced facts about Gerbonara** (licence, maintenance, KiCad-10 Gerber X2 compatibility); that decision still needs its own check. The alternative these notes do support with primary sources is exporting Gerbers with `kicad-cli pcb export gerbers` from the generated `.kicad_pcb`, leaving a Gerber library only for the read-back comparison.
- The actual terms of service for HQDFM, Eurocircuits Visualizer and the fab web uploaders regarding automated use were not read.
- Whether the JLCPCB API response includes any DFM/engineering-question data was not determined (documentation is behind the application).

---

## 7. DFA (assembly) rules with numeric thresholds

### Takeaway
Hard, assembler-published numbers found for the target fab are few: JLCPCB requires 2.5 mm from component body to board edge, 5 mm process rails with 2 mm tooling holes and 1 mm fiducials (which it will add itself), and a 250 x 250 mm panel limit; everything else (courtyard excess, hole = lead + 0.15 to 0.25 mm, stencil area ratio >= 0.66 and aspect ratio >= 1.5, thermal-symmetry rules for tombstoning) comes from secondary summaries of IPC standards and vendor blogs and should be encoded as warnings with their provenance.

### Cited Findings
- **[S]** JLCPCB assembly terms: minimum 2.5 mm between component body and board edge. — [JLCPCB assembly terms and conditions](https://jlcpcb.com/help/article/Terms-and-Conditions-of-JLCPCB-Assembly-Service)
- **[S]** JLCPCB process edge guidance for SMT: 5 mm process edges, 2 mm tooling holes, 1 mm fiducials placed 3.85 mm from the panel edge; too-narrow rails make edge components collide with conveyor guides. — [JLCPCB: process edges and positioning holes](https://jlcpcb.com/help/article/specifications-for-adding-process-edges-and-positioning-holes)
- **[S]** Fiducials: minimum two, three "strongly recommended" for global fiducials. — [JLCPCB blog: fiducial marks](https://jlcpcb.com/blog/fiducial-marks)
- **[P]** JLCPCB will add fiducial marks for SMT itself; maximum assembly panel 250 x 250 mm; Economic assembly requires mouse-bite panelisation, Standard accepts mouse bites or V-cut; orders above 30 boards can be panelised. — [JLCPCB PCB assembly FAQs](https://jlcpcb.com/help/article/pcb-assembly-faqs)
- **[P]** JLCPCB parts economics: basic parts carry no feeder-loading charge; extended parts cost $3 each (manual feeder load); "Preferred Extended" parts are exempt under Economic assembly; library about 698 basic and 300k+ extended; setup fee $8, stencil $1.50, $0.0017 per SMT joint; wave-soldered through-hole $3.50 labour plus $0.0173 per joint. — [JLCPCB PCB assembly FAQs](https://jlcpcb.com/help/article/pcb-assembly-faqs)
- **[P]** JLCPCB tooling edge for panels: >= 3 mm, 5 mm for SMT assembly; SMD pad-to-pad (different nets) 0.15 mm; solder-mask bridge 0.10 mm. — [JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- **[S]** Courtyard excess per side (IPC-7351 summaries): 0.50 / 0.25 / 0.10 mm for density levels A / B / C; small chip parts 0.20 / 0.15 / 0.10 mm; these definitions are for reflow soldering. — [PCBSync: IPC-7351](https://pcbsync.com/ipc-7351/), [Linked Electronics](https://www.linkedpcba.com/blog/component-courtyard-clearance-guide.html)
- **[S]** Through-hole: hole = max lead diameter + 0.25 / 0.20 / 0.15 mm for IPC-2222 Levels A / B / C; diagonal for rectangular leads. — [PCB-3D tutorial](https://www.pcb-3d.com/tutorials/how-to-calculate-pth-hole-and-pad-diameter-sizes-according-to-ipc-7251-ipc-2222-and-ipc-2221-standards/)
- **[S]** Stencil (IPC-7525B/C summaries): area ratio (aperture area / wall area) >= 0.66; aspect ratio (aperture width / stencil thickness) >= 1.5, 1.7+ preferred for difficult pastes; a 2007 report on the draft: below 0.5 redesign, 0.5 to 0.66 electroformed, 0.66 to 0.9 laser-cut. — [JLCPCB blog: stencil aperture design](https://jlcpcb.com/blog/stencil-aperture-design-geometry-area-ratio-tips), [Circuits Assembly 2007: stencil design standard goes to vote](https://circuitsassembly.com/ca/news/292-news/2007-news/13365-stencil-design-standard-goes-to-vote.html)
- **[S]** Tombstoning mechanism and layout rules: one end reflows first and surface tension levers the part up; lighter parts (0201, 0402) are vulnerable while 1206 has enough mass to resist; both pads should be identical in size, shape and copper connection with equal trace widths and equal via counts; the classic failure is one pad on a wide pour and the other on a 0.2 mm trace; use thermal relief on the pour side; paste-volume imbalance and placement offset are co-factors. — [NextPCB blog: SMT passive assembly, tombstoning](https://www.nextpcb.com/blog/smt-passive-assembly-tombstoning-solder-balling-0201-0402), [Electrical Codidact: thermal relief discussion](https://electrical.codidact.com/posts/293359)
- **[S]** Vendor thermal-relief dimensions: for 0402/0603, spokes 0.10 to 0.20 mm with 0.20 to 0.30 mm gap; for 0805/SOT-23, spokes 0.20 to 0.30 mm with 0.25 to 0.40 mm gap; the article attributes a 0.2 mm spoke floor and four-spoke maximum to IPC-2221B (attribution unconfirmed). — [JLCPCB blog: thermal relief pad design](https://jlcpcb.com/blog/thermal-relief-pad-design)
- **[P]** JLCPCB silkscreen limits relevant to polarity/pin-1 marks: 0.15 mm line, 1.0 mm text height, 0.15 mm pad-to-silk. — [JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- **[P]** KiCad DRC items usable for DFA: `courtyards_overlap`, `missing_courtyard` (ignored by default), `malformed_courtyard`, `pth_inside_courtyard`, `npth_inside_courtyard`, `footprint_type_mismatch` (ignored by default); custom `courtyard_clearance` constraint exists. — [KiCad drc_item.cpp](https://gitlab.com/kicad/code/kicad/-/raw/master/pcbnew/drc/drc_item.cpp), [KiCad 10 manual](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)

### Inferences
- Proposed DFA rule table for the gate (thresholds trace to the findings above; severities are my recommendation):

| Rule | Threshold | Severity | Engine |
|---|---|---|---|
| Courtyard overlap | no overlap; courtyards drawn at >= 0.25 mm excess (0.15 mm for 0402/0603) | error | KiCad `courtyards_overlap` + own check |
| Every footprint has a closed courtyard | required | error | KiCad `missing_courtyard` / `malformed_courtyard` promoted |
| Component body to board edge | >= 2.5 mm if JLCPCB-assembled; else >= 1.0 mm | error / warning | own check; KiCad custom rule as second opinion |
| Hole in foreign courtyard | none | error | KiCad `pth_inside_courtyard`, `npth_inside_courtyard` |
| TH hole vs lead | lead_max + 0.20 to 0.25 mm; flag < +0.15 or > +0.40 | warning | own check (needs lead diameter in part data) |
| TH annular ring | >= 0.25 mm | error | KiCad `annular_width` + own tolerance model |
| Two-pad passive pad symmetry (0402/0603) | equal pad area; equal mask opening | error | own check |
| Two-pad passive thermal symmetry | per pad: sum of connected track widths and zone-connection style; flag solid pour on one pad vs track on other, or connected-copper width ratio > 2:1 | warning (0402/0603), info (0805+) | own check |
| Thermal relief on pours for TH and small SMD pads | spokes present; >= 2 resolved | error if starved | KiCad `starved_thermal` + own |
| SMD pad gap vs mask dam | gap - 2 x expansion >= 0.16 mm | warning | own check |
| Stencil ratios (if stencil ordered) | area ratio >= 0.66; aspect ratio >= 1.5 | info for this part mix | own check; trivially passes for 0402+ and 1.27 mm pitch on 0.10 to 0.12 mm foil |
| Fiducials | advisory: 2 to 3 x 1 mm, if not using JLCPCB's auto-added marks | info | own check |
| Polarity / pin-1 marking | every polarised part has silk or fab-layer pin-1 mark outside the body outline, not covered by pads | warning | own check on footprint metadata |
| Orientation consistency | polarised parts of same type share 0/90 orientation set | info | own check |
| Single assembly side | all SMD on one side for Economic assembly | warning | own check |
| Panel size | <= 250 x 250 mm | error if JLC-assembled | own check |

- Tombstone detection from the IR is feasible with existing data: for each two-pad chip part, compute per pad (a) pad copper area, (b) total width of copper leaving the pad boundary (tracks plus zone spokes or solid connection), (c) presence of an in-pad or adjacent via; flag asymmetry. This is a heuristic proxy for thermal mass, so it belongs on the "evidence" rung.
- For hobby hand soldering, the brief's package floor (0402 to 1206, SOT-23, SOIC, DIP) already avoids the classes where stencil ratios bind; keep the stencil check implemented but informational.

### Gaps
- No assembler-published **component-to-component** minimum spacing table (by package class) was found for JLCPCB or PCBWay; MacroFab and Screaming Circuits DFA guides were not retrieved.
- No primary application note (Indium, Kester, AIM) on tombstoning was retrieved; all tombstoning numbers above are vendor-blog or forum level.
- Tall-component shadowing rules for wave/selective soldering, rework-access clearances, mixed-technology side rules, and DFT test-pad size/spacing for flying probe or pogo pins: no sources retrieved; nothing sourced to encode.
- IPC-7525 aperture-reduction percentages not sourced; IPC revision (B vs C) wording differs between summaries.
- IPC-7351 pin-1/polarity marking conventions not sourced.

---

## 8. Assembly output correctness: BOM, CPL, rotation conventions

### Takeaway
Rotation is the dominant assembly-file failure mode: KiCad's footprint zero orientation, the assembler's interpretation, and tape-and-reel orientation all differ, bottom-side handling differs (KiCad mirrors, JLCPCB does not), and the correction databases are regex tables of "common cases" that cannot be complete. The gate should apply a versioned correction table, then independently verify by rendering or recomputing pin-1 positions, and still require a human look at the fab's placement preview.

### Cited Findings
- **[P]** KiBot documentation: the rotation in a position file depends on how KiCad orients footprints (pin 1 generally top-left), how the manufacturer interprets the angle, and tape-reel orientation, which varies by manufacturer and can differ for the same part; "KiCad mirrors components on the bottom side, but JLCPCB doesn't (november 2023)". — [KiBot: notes about the position file](https://kibot.readthedocs.io/en/master/notes_position.html)
- **[P]** KiBot's internal rotation database is a list of footprint-name regexes to angles, first match wins, e.g. `^QFN-` -> 270, `^SOT-23` -> 180, `^LED_WS2812B_PLCC4` -> 180, `^SOP-(?!(18_|4_))` -> 270; offsets table e.g. `^PinHeader_2x03_P1\.27mm_Vertical` -> (-1.27, -0.64); the database "is just a list of common cases" and two parts with the same footprint can need different rotations. — [KiBot: notes about the position file](https://kibot.readthedocs.io/en/master/notes_position.html)
- **[P]** KiBot `rot_footprint` filter options: `rotations` ([regex, angle]), `offsets` ([regex, "X,Y"] in mm), `rotations_and_offsets` (match on any field, takes precedence over the database), `extends` (can drop the built-in database), `negative_bottom`, `mirror_bottom`, `rot_fields` / `offset_fields`; default per-part fields `JLCPCB Rotation Offset` / `JLCRotOffset` and `JLCPCB Position Offset` / `JLCPosOffset` (case-insensitive); `bennymeg_mode` for compatibility with JLC-Plugin-for-KiCad. — [KiBot: notes about the position file](https://kibot.readthedocs.io/en/master/notes_position.html), [KiBot: footprint rotator filter](https://kibot.readthedocs.io/en/master/configuration/filters/rot_footprint.html)
- **[S]** KiBot documents a bottom-side discrepancy in JLC-Plugin-for-KiCad v3.1.0: correct computation is `(180 - component_rot) + angle` but the plugin does `180 - (component_rot + angle)`. — [KiBot: footprint rotator filter](https://kibot.readthedocs.io/en/master/configuration/filters/rot_footprint.html)
- **[S]** Fabrication Toolkit per-part fields: `FT Rotation Offset` (positive = counter-clockwise degrees), fallbacks `Rotation Offset`, `RotOffset`; JLC Plugin fields `JLCPCB Rotation Offset`, `JlcRotOffset`, `JLCRotOffset`. — [bennymeg/Fabrication-Toolkit](https://github.com/bennymeg/Fabrication-Toolkit), [bennymeg/JLC-Plugin-for-KiCad](https://github.com/bennymeg/JLC-Plugin-for-KiCad)
- **[P]** JLCPCB's own orientation-fix guide: BOM and CPL accepted as XLS, XLSX or CSV; CPL gives X, Y and orientation per designator; the fix workflow is edit rotation or Mid X/Y in the CPL, re-upload, and check the assembly viewer (example: U1 changed from 90 to 0; Mid X from 32 to 28.96); only SMD parts in the JLCPCB parts library are assembled; the page states JLCPCB "doesn't currently accept assembly for both sides of the board" (page may be dated). — [JLCPCB orientation-fix repo](https://github.com/JLCPCB/JLCPCB-SMT-Assembly-Components-orientation-fix)
- **[S]** CPL columns as documented by a third-party guide: `Designator, Mid X, Mid Y, Layer, Rotation` (example row `U1,25.4,12.7,Top,0`), rotation counter-clockwise, coordinates are component centres; JLCPCB recommends millimetres for all exports and requires CPL designators to match the BOM exactly. — [Schemalyzer: JLCPCB assembly guide](https://www.schemalyzer.com/en/blog/manufacturing/jlcpcb/jlcpcb-assembly-guide), [JLCPCB blog: files needed for PCB assembly](https://jlcpcb.com/blog/files-needed-for-pcb-assembly)
- **[P]** KiCad's native position export: `kicad-cli pcb export pos --format csv --units mm --side both [--use-drill-file-origin] [--exclude-dnp] [--smd-only] [--bottom-negate-x]`; default units are inches. — [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)
- **[S]** Community-derived typical corrections: +180 for SOT-23/SOT-223, +90 or +270 for SOIC-8/16, +90 for QFN; symmetric two-pad parts can hide 180-degree errors. — [KiCad forum: JLCPCB plugin position offset](https://forum.kicad.info/t/jlcpcb-plugin-position-offset/40054)
- **[P]** Basic vs extended parts: see section 7 ($3 per extended part type; about 698 basic parts). — [JLCPCB PCB assembly FAQs](https://jlcpcb.com/help/article/pcb-assembly-faqs)

### Inferences
- Circuit OS already owns placement in its IR, so the CPL should be generated natively (designator, centroid mm, side, rotation) rather than through KiCad; the KiCad `.pos` export from the generated `.kicad_pcb` then becomes an independent cross-check (same designators, centroids within tolerance, angles equal modulo the correction table).
- Verification design that does not depend on any correction database being right:
  1. For each placed part, compute the board-frame position of pad 1 from (centroid, rotation, side, footprint pad-1 offset).
  2. Independently, from the CPL row plus the part's declared zero-orientation convention (per LCSC part or package family), recompute where pin 1 lands as the assembler would interpret it.
  3. Flag any part where the two disagree by more than half the pad pitch. For two-pad non-polarised parts accept 180-degree equivalence; for polarised two-pad parts (diodes, tantalum, LEDs) require an explicit polarity record.
  4. Render a placement preview (pad 1 highlighted) into the release artefacts for human sign-off, and still require a check of JLCPCB's order-page viewer. Step 2's convention data is only "evidence": the tape orientation is not published per part in a machine-readable form that I found.
- Store rotation corrections keyed first by LCSC part number, then by footprint regex, mirroring the KiBot precedence (`rotations_and_offsets` over database); record the database version in the report.
- With <40 parts and an Economic single-sided run, the bottom-side mirroring discrepancy is avoidable by policy: forbid bottom-side SMD in the JLCPCB-assembly profile.
- BOM gate: every assembled designator has an LCSC part number; count distinct extended parts and report the feeder fee ($3 each) so the compiler can prefer basic parts.

### Gaps
- JLCPCB's official CPL/BOM sample file (column headers, units, rotation sign convention) was not read from a primary page; the column list is third-party.
- `cpl_rotations_db.csv` (JLCKicadTools) format and Bouni's kicad-jlcpcb-tools correction handling and KiCad 9/10 support were not retrieved; licences of Fabrication Toolkit, JLCKicadTools and kicad-jlcpcb-tools not confirmed.
- No machine-readable source of per-part tape/reel zero orientation (EIA-481 quadrant data per LCSC part) was found, so fully automatic rotation proof is not achievable from public data found here.
- Whether JLCPCB currently accepts double-sided assembly (the GitHub guide says no; it may be outdated) was not confirmed.

---

## 9. Named open-source automation frameworks and flows

### Takeaway
KiBot (AGPL-3.0, same licence as the backend) is the most complete KiCad CI framework, with preflights for DRC/ERC/zone fill and JLCPCB position-file fixes, but it is Linux/Docker-centric and its documented images are KiCad 7/8; for a project that generates boards itself, a thin Python 3.11 orchestrator calling `kicad-cli` directly (works on Windows and in the official Docker image) plus KiKit for panelisation and Freerouting 2.x headless for routing is the smaller and more portable choice.

### Cited Findings
- **[P]** KiBot (formerly KiPlot): licence **AGPL-3.0**; the repo contains Dockerfiles suffixed `_k5` to `_k10` and `_dk5` to `_dk10`, an `action.yml` and `entrypoint.sh` for GitHub Actions. — [KiBot GitHub](https://github.com/INTI-CMNB/KiBot)
- **[P]** KiBot installation docs: Docker images `ghcr.io/inti-cmnb/kicad8_auto_full:latest` (or `kicad7_auto_full`), smaller `kicad8_auto`, `dev` tag for development code; dependency notes reference KiCad 7 to 10; pinned companions KiAuto v2.3.6, KiKit v1.5.1, KiDiff v2.5.3, KiBoM v1.9.1, InteractiveHtmlBom v2.7.0, KiCost v1.1.8; "For Windows you'll need to install tools to mimic a Linux environment, like WSL2"; Docker runs it on Windows/macOS/Linux. — [KiBot installation](https://kibot.readthedocs.io/en/latest/installation.html)
- **[P]** KiBot preflights (master docs): Annotate PCB, Annotate Power, Check Fields, Check Zone Fills, Consolidate PCBs, Draw (Fancy) Stackup, DRC, ERC, Fill Zones, Filters, Include Table, Set Text Variables, Update Footprint, Update PCB Characteristics, Update QR, Update Stackup, Update XML; deprecated: ERC Warnings, Ignore Unconnected, PCB Replace, Run DRC and Run ERC (deprecated for KiCad 8), SCH Replace. Filter entries have `filter`, `error`, `regex`; ignored errors are still reported as warnings. — [KiBot: the preflight section](https://kibot.readthedocs.io/en/master/configuration/preflight.html)
- **[S]** From KiBot 1.7.0 the `drc` and `erc` preflights replace `run_drc` / `run_erc` for KiCad 8+, supporting multiple formats and separating unconnected items from warnings; the older `run_drc` could not test schematic parity; a "CheckZoneFill" internal template can abort when refilling changes a layer significantly. — [KiBot changelog](https://kibot.readthedocs.io/en/master/Changelog.html), [KiBot preflight docs v1.7.0](https://kibot.readthedocs.io/en/v1.7.0/configuration/preflight.html)
- **[P]** KiBot ships a JLCPCB position-file pipeline (`_rot_footprint_jlcpcb` filter, rotation/offset database, per-part fields). — [KiBot: notes about the position file](https://kibot.readthedocs.io/en/master/notes_position.html)
- **[P]** KiKit: **MIT**; panelisation by appending boards and substrate bridges, arbitrary board shapes, mouse-bite and V-cut separation; automated export of gerbers and assembly data with manufacturer presets; board presentation pages; multi-board file splitting; 3D-printed and steel stencil generation; 68 open issues / 30 open PRs; author states sponsorship is what lets him allocate maintenance time. — [KiKit GitHub](https://github.com/yaqwsx/KiKit)
- **[S]** KiKit has an open issue on KiCad 10 variants support (issue #892), indicating KiCad 10 compatibility work is in progress rather than complete. — [KiKit issue #892](https://github.com/yaqwsx/KiKit/issues/892)
- **[P]** Freerouting: **GPL-3.0**; requires Java JRE 25; reads Specctra/Electra `.dsn`, writes `.ses`; Docker image `ghcr.io/freerouting/freerouting` (tags `latest`, version tags, `nightly`; linux/amd64, arm64, arm/v7); hosted API root `https://api.freerouting.app/v1` is beta and full access requires a request; official Python client `freerouting-client`; self-hosting documented in `docs/self-hosting.md`; basic CLI `java -jar freerouting.jar -de MyBoard.dsn -do MyBoard.ses -inc GND,VCC`. — [Freerouting GitHub](https://github.com/freerouting/freerouting)
- **[P]** Freerouting CLI detail: `-de` (DSN in, optional SES and RULES joined with `+`), `-do` (output DSN/SES/SCR by extension), `-dr` (.rules file; auto-loads adjacent `<board>.rules`), **`-drc [file]` writes a DRC report in KiCad JSON format**, `-mp` (max autorouter passes), `-mt` (optimizer threads; 0 disables optimisation), `--router.optimizer.improvement_threshold` (default 2.5 %), `-inc`, `-us greedy|global|hybrid`, `-is sequential|random|prioritized`, `-da` (disable anonymous analytics; **enabled by default**), `-dct` (dialog timeout, default 20 s), `--gui.enabled=false`, `--router.via_costs`, `--router.layers.routable`, `--api_server.enabled`, `--api_server.endpoints` (default `http://127.0.0.1:37864`), `--api_server.authentication.enabled` (default true), env-var form `FREEROUTING__...`, `--user_data_path`. — [Freerouting command line arguments](https://raw.githubusercontent.com/freerouting/freerouting/master/docs/command_line_arguments.md)
- **[S]** Freerouting has ongoing KiCad 10 integration work (PR #938: IPC progress dialog and REST API bridge for KiCad 10+). — [Freerouting PR #938](https://github.com/freerouting/freerouting/pull/938)
- **[S]** kicad-happy (aklofas): **MIT**; AI-assisted design review "skills" for Claude Code and OpenAI Codex covering schematic, PCB layout and Gerber analysis, DRC/ERC, DFM, BOM, SPICE, EMC; claims KiCad 5 to 10 support; standalone Python 3.10+ scripts with zero dependencies; each finding carries a confidence label and evidence source with a `trust_summary` rollup; a GitHub Action for PR reviews exists. — [kicad-happy GitHub](https://github.com/aklofas/kicad-happy)
- **[P]** KiCad itself has a jobset runner: `kicad-cli jobset run -f <file.kicad_jobset> [--stop-on-error]`. — [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)

### Inferences
- Recommended flow for Circuit OS (all GPL/AGPL tools as subprocesses):
  1. `Board` IR -> own `.kicad_pcb` + `.kicad_pro` + `.kicad_dru` writer (profile-generated, sentinel rule included).
  2. Optional routing branch: fix the DSN exporter (via padstack), run `java -jar freerouting.jar --gui.enabled=false -de b.dsn -do b.ses -mp N -da -drc fr_drc.json` or the Docker image; import the SES into the IR with an own parser (the `.ses` carries wires and vias; KiCad's SES import is a GUI/SWIG function and not exposed in `kicad-cli pcb import`, whose formats are pads/altium/eagle/cadstar/fabmaster per the CLI docs).
  3. `kicad-cli pcb upgrade --force` then `kicad-cli pcb drc --refill-zones --save-board --severity-all --all-track-errors --format json` on a scratch copy.
  4. Own DRC kernel + `verify.py` on the IR; differential comparison with step 3 (section 12).
  5. Own DFM/DFA checks (sections 5 and 7).
  6. `kicad-cli pcb export gerbers/drill/pos/ipc2581/ipcd356`; Gerber round-trip comparison.
  7. Optional KiKit panelisation and fab preset packaging; KiBot only if its richer outputs (iBoM, diffs, PcbDraw) are wanted, run via its Docker image in CI.
- Why not KiBot as the backbone: on the evidence above it needs WSL2 or Docker on Windows, its documented images are KiCad 7/8 (KiCad 10 Dockerfiles exist in the repo but image names for 9/10 were not confirmed), and its DRC preflight is a wrapper over the same `kicad-cli`. Its value is breadth of outputs, not an extra checking engine.
- Freerouting's `-drc` KiCad-JSON output is a cheap third opinion on clearance after routing, in the same schema the gate already parses. Pin `-da` in CI, since analytics are on by default.
- kicad-happy's "confidence label + evidence source + trust_summary" output model is close to the project's trust-rung reporting and worth reading for report design; its checks are script heuristics plus LLM review, so on the trust ladder they are "evidence", never "sound".

### Gaps
- Not researched (no sourced claims): KiCad Automation Scripts (KiAuto) details, KiDiff/kiri, InteractiveHtmlBom, PcbDraw, kicad-text-injector, public kicad-ci templates, atopile build/CI, tscircuit checks, JITX design-rule checks, Flux/Quilter/DeepPCB validation claims, and 2024-2026 LLM "PCB design review" tools other than kicad-happy.
- KiBot's current version number, its KiCad 9/10 Docker image names, and the full option list of the new `drc` preflight were not retrieved.
- KiKit's latest release, exact preset names, and KiCad 10 status beyond the open issue were not confirmed.
- Freerouting's latest version number/date and the hosted API's terms of use were not retrieved; how KiCad 10 imports SES headlessly was not verified (claim above about `kicad-cli pcb import` formats is from the CLI doc's listed options, which were truncated after `fabmaster`).

---

## 10. Release-gate patterns and what fab CAM changes silently

### Takeaway
Fab CAM routinely modifies incoming data for yield (etch compensation, mask expansion, drill compensation, sometimes teardrops and scaling), usually without telling the customer, while genuine capability failures become engineering queries or rejections; a pre-fab gate should therefore distinguish "fab will compensate" parameters from "fab will reject or build wrong" parameters, and ship a netlist (IPC-D-356 or IPC-2581) so the fab can catch opens and shorts its edits introduce.

### Cited Findings
- **[S]** CAM "edits the data to survive the process — etch compensation, solder mask expansion, teardrops, copper balancing, and scaling"; CAM checks trace width/spacing, annular ring, drill-to-copper, mask clearance and copper-to-edge against real capability; CAM should not have silent authority to change circuit function, approved dimensions, stackup intent, impedance or materials; sending a netlist (IPC-D-356, or embedded in ODB++/IPC-2581) lets CAM catch shorts and opens that Gerbers alone cannot reveal. — [PCBSync: CAM processing](https://pcbsync.com/cam-processing-pcb/)
- **[S]** "Over 90% of the time, your fabricator will edit the Gerber files to improve their yield, and most of the time, you don't know what they change" (2012 vendor blog; anecdotal), with an example of a technician spreading traces for clearance and disturbing a differential pair. — [Siemens blog 2012: are you sure your manufacturing outputs are good](https://blogs.sw.siemens.com/electronic-systems-design/2012/07/30/are-you-sure-your-manufacturing-outputs-are-good/)
- **[S]** Typical guidance: solder-mask openings expanded about 50 um beyond the pad all round; keep legend a further ~75 um from mask openings. — [PCD&F: designing for PCB manufacturability](https://pcdandf.com/pcdesign/index.php/current-issue/241-designer-s-notebook/17910-designing-for-pcb-manufacturability)
- **[P]** JLCPCB states mask expansion as a 1:1 pad-to-opening ratio in customer data (the fab applies its own expansion). — [JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- **[S]** Aisler compensates plated holes by +150 um in CAM (0.65 mm becomes 0.8 mm tool), reducing the effective annular ring by 75 um per side. — [Aisler community thread](https://community.aisler.net/t/through-hole-1-27mm-pin-header-manufacturing-min-annular-ring-size-not-reached/2781)
- **[S]** PCB Power: tool size = finished size + 0.10 mm (vias) / + 0.15 mm (PTH) / + 0.05 mm (NPTH); annular ring is computed from the production tool diameter. — [PCB Power response (undated)](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/234/PCB_5F00_Manf_5F00_comments.doc)
- **[P]** Eurocircuits likewise classifies by production TOOLSIZE rather than finished ENDSIZE. — [Eurocircuits classification](https://www.eurocircuits.com/pcb-design-guidelines-classification/)
- **[P]** KiCad's gerber export has `--subtract-soldermask` ("Remove silkscreen from areas without soldermask"), i.e. silkscreen clipping can be done deterministically on the design side. — [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)
- **[S]** A quality-systems column recommends a company acceptance spec clause that deviations or modifications to supplied design data "shall be approved in writing ... prior to the initiation of PCB fabrication". — [I-Connect007: Dana on Data, DFM issue reduction](https://mail.iconnect007.com/article/132111/dana-on-data-dfm-issue-reductioncompanyspecific-pcb-acceptance-specifications/132114/design)
- **[S]** The practical difference between a real and a shallow fab DFM pass is whether flagged issues are sent back for confirmation rather than silently auto-corrected. — [PCBCart: PCBA DFM check thoroughness](https://www.pcbcart.com/article/content/pcba-dfm-check-thoroughness)

### Inferences
- Classification for the gate's report (my synthesis from the above):
  - **Fab compensates, do not pre-distort**: etch compensation of track widths, solder-mask expansion (submit 1:1 or small expansion), drill size compensation for plating (specify finished size), panel scaling.
  - **Fab may silently "fix", so make it deterministic yourself**: silkscreen over pads (clip with `--subtract-soldermask`), teardrops, removal of non-functional pads, thieving. Anything the fab might do differently per order destroys reproducibility, so the gate should make the data unambiguous.
  - **Fab queries or rejects**: track/space or drill below capability, annular ring below minimum after their compensation, copper too close to outline or V-cut, missing/ambiguous outline, unplated vs plated ambiguity, missing drill file.
  - **Fab silently accepts (your risk)**: acid traps, marginal slivers, thermal asymmetry (tombstoning), wrong CPL rotations (they place what the file says unless an engineer notices), starved thermals, wrong footprint for the part.
  The last class is where an automated gate adds the most value, because no one downstream is checking.
- Release-gate pattern to adopt: (1) immutable release bundle (gerbers, drills, IPC-D-356 netlist, IPC-2581, BOM, CPL, the DRC JSONs, profile TOML with source dates, tool versions); (2) golden "known-good board" regression: one board that has actually been fabricated and assembled, whose bundle hash and DRC results are pinned; (3) first-article inspection checklist filled against the first physical batch and fed back as profile corrections; (4) a manual recorded step for the fab's web DFM result.

### Gaps
- ECSS-Q-ST-70-12C, NASA workmanship standards, IPC-2221 checklists, Altium/Cadence pre-fab checklists and the Sierra Circuits DFM handbook were not retrieved; no sourced checklist content is included.
- No quantitative source on respin causes or DFM defect statistics was found (the brief's suggested white papers were not located).
- No fab-specific statement was found on which edits JLCPCB or PCBWay make without an engineering question at hobby tier; the classification above is generic.

---

## 11. Proving the gate works

### Takeaway
The strongest directly sourced pattern is kicad-druid's: paired test boards that intentionally contain passing and failing footprints, a generator drift check, a linter, and a CI DRC run in which "a sentinel rule must fire or the job fails", motivated by the fact that `kicad-cli` silently ignores an invalid rule file. Everything else (mutation, differential and property-based testing) is standard software-testing practice applied here by inference.

### Cited Findings
- **[P]** kicad-druid CI: `generate_dru.py --check` fails if committed rule files drift from the TOML sources; `tools/lint_dru.py` checks s-expression syntax, version header, duplicate rule names, fab prefixes, lowercase item types and layer names; a DRC workflow runs `kicad-cli pcb drc` on all twelve `.kicad_dru` files where violations are informational "but a sentinel rule must fire or the job fails". — [kicad-druid README](https://github.com/Cimos/kicad-druid)
- **[P]** Reason the sentinel is needed: an unrecognised layer name "makes KiCad reject the whole rule file, and `kicad-cli` reports nothing". — [kicad-druid README](https://github.com/Cimos/kicad-druid)
- **[P]** KiCad's own statement: custom rules "will only be applied if there are no errors in the custom rules definitions". — [KiCad 10 PCB editor manual](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)
- **[P]** kicad-druid test boards "intentionally contain passing and failing footprints", documented per object in `JLCPCB/TESTBOARD.md`, saved in KiCad 9 format. — [kicad-druid README](https://github.com/Cimos/kicad-druid)
- **[P]** The published `JLCPCB-2L-1oz.kicad_dru` itself contains no sentinel rule, so the sentinel is injected or defined elsewhere in CI. — [kicad-druid JLCPCB-2L-1oz.kicad_dru](https://raw.githubusercontent.com/Cimos/kicad-druid/main/JLCPCB/JLCPCB-2L-1oz.kicad_dru)
- **[P]** KiCad's `assertion` constraint yields a distinct violation type `assertion_failure`, and `--severity-all` plus JSON output make any rule's firing machine-detectable. — [KiCad drc_item.cpp](https://gitlab.com/kicad/code/kicad/-/raw/master/pcbnew/drc/drc_item.cpp), [KiCad 10 CLI docs](https://docs.kicad.org/10.0/en/cli/cli.html)
- **[P]** Freerouting can emit its own DRC report in KiCad JSON format (`-drc`), giving a third implementation for differential comparison of routed boards. — [Freerouting command line arguments](https://raw.githubusercontent.com/freerouting/freerouting/master/docs/command_line_arguments.md)
- **[S]** KiCad DRC behaviour has changed between major versions for identical rules (KiCad 8 vs 9 reports), so oracle results must be pinned to a KiCad version. — [KiCad forum: custom DRC KiCad 8 vs 9](https://forum.kicad.info/t/custom-drc-bga-breakout-clearance-kicad-8-vs-kicad-9/59353)

### Inferences
- **Sentinel rule design** (applies the kicad-druid pattern): append to every generated `.kicad_dru`, as the last rule, an always-false assertion on a known object, e.g. a rule named `__sentinel_rules_loaded__` with a condition matching a dedicated sentinel footprint reference or simply every via/pad, and an assertion that cannot hold. The gate then requires exactly the expected sentinel violation(s) in the JSON, removes them from the result set, and fails with "rule file not loaded" if absent. Place it last and keep it independent of other rules, because KiCad applies the last matching rule and a sentinel on a shared constraint type could mask real rules; `assertion` is the safest constraint type since it does not compete with clearance resolution. Verify this interaction empirically on KiCad 10.0.1.
- **Seeded-violation fixtures**: for each rule in the profile, one minimal board just inside the limit (expected pass) and one just outside (expected fail), generated from the IR by the same exporter. Expected results are a table keyed by rule name; CI fails on any mismatch in either direction. This doubles as an exporter test.
- **Mutation testing of the rule set**: mutate one numeric value in the TOML profile at a time (for example relax min spacing from 0.20 to 0.10) and confirm at least one seeded fixture changes outcome; a mutation that no fixture detects reveals an untested rule. Also mutate severities to catch rules demoted to ignore.
- **Differential testing against the custom kernel**: generate boards, run the custom DRC kernel and KiCad DRC, normalise both into (rule class, item pair, layer, measured distance), and compare. Tolerances: KiCad reports in mm at its internal 1 nm resolution, so compare distances with an epsilon and exclude near-threshold cases within the epsilon. Classify disagreements: kernel-miss (KiCad flags, kernel silent) is a potential soundness bug; kernel-only is either a false positive or a KiCad blind spot. The known broad-phase bug gives a concrete acceptance test: two parallel tracks with required clearance c > (w1+w2)/2 and gap g where g < c must be flagged by both engines; today the kernel should fail this test, proving the differential harness detects the bug before it is fixed.
- **Property-based generation (Hypothesis)**: strategies for pairs of primitives (track-track, track-pad, via-via, pad-edge) with gap drawn from `clearance + delta` where delta is sampled densely in [-5 um, +5 um] and coarsely beyond; widths and clearances sampled so that both sides of (w1+w2)/2 are covered; random rotation and translation to exercise grid alignment; shrinking will reduce counterexamples to minimal geometry. Oracle is the exact analytic segment-to-segment distance (the "exact" rung), with KiCad as the second opinion.
- **Regression corpus**: KiCad's bundled demo projects and kicad-druid's test boards (MIT, with documented expected pass/fail objects) are ready-made inputs with known KiCad DRC results; pin the JSON per KiCad version and diff on upgrade.
- **Gate self-check in every run**: record kicad-cli version, rule-file hash, profile hash, sentinel-fired flag, count of rules parsed, and zone-refill flag; a run missing any of these is reported as "unknown" on the trust ladder, not as pass. Also assert that exit code and JSON agree (the brief found exit 0 with 28 violations when `--exit-code-violations` is omitted).

### Gaps
- No published methodology was found for mutation testing or property-based testing of PCB DRC engines specifically; the designs above are inference.
- The exact form of kicad-druid's sentinel rule and how its CI asserts on it were not read (the workflow file was not opened).
- Whether the KiCad demo boards ship with expected DRC result files was not verified.
- The sentinel's interaction with last-match-wins rule resolution in KiCad 10 was not tested.

---

## 12. Cross-cutting: licences and AGPL-3.0 compatibility of everything named

### Takeaway
Nothing in the recommended chain blocks an AGPL-3.0 backend: MIT components can be imported directly, and the GPL-3.0 tools are used as separate processes over files and JSON.

### Cited Findings
- **[P]** KiBot: AGPL-3.0. — [KiBot GitHub](https://github.com/INTI-CMNB/KiBot)
- **[P]** KiKit: MIT. — [KiKit GitHub](https://github.com/yaqwsx/KiKit)
- **[P]** Freerouting: GPL-3.0. — [Freerouting GitHub](https://github.com/freerouting/freerouting)
- **[P]** kiutils: GPL-3.0. — [kiutils GitHub](https://github.com/mvnmgrx/kiutils)
- **[P]** kicad-druid: MIT. — [kicad-druid GitHub](https://github.com/Cimos/kicad-druid)
- **[S]** kicad-happy: MIT. — [kicad-happy GitHub](https://github.com/aklofas/kicad-happy)
- **[P]** KiCad's official Docker images are for `kicad-cli` use only (GUI in Docker unsupported). — [kicad.org Docker page](https://www.kicad.org/download/docker/)

### Inferences
- Usage mode per tool: KiCad (`kicad-cli`, subprocess or container), Freerouting (JVM subprocess or container), KiBot (container) are all invoked at arm's length; MIT data and code (kicad-druid TOML/rules, KiKit, kicad-happy scripts) may be vendored or imported with attribution; kiutils (GPL-3.0) may be imported into an AGPL-3.0 work under the GPLv3 section 13 combination allowance, but is not needed if the project writes its own emitter.
- Fab capability numbers are facts, not copyrightable expression in most jurisdictions, but record source URL and access date per value for auditability; rule-file text copied from kicad-druid carries its MIT notice.
- Hosted fab tools (HQDFM, Visualizer, web uploaders, fab APIs) are excluded from CI on the evidence in section 6; keep them as manual, recorded steps.

### Gaps
- KiCad's exact licence string (GPL-3.0-or-later) and the Docker image's licence metadata were not re-verified from a primary page in this session (the brief states GPL-3).
- Licences of Fabrication Toolkit, kicad-jlcpcb-tools, JLCKicadTools, InteractiveHtmlBom, KiDiff, PcbDraw, Gerbonara, gerbv, pcb-tools and tracespace were not checked.
- This is an engineering reading of licence interaction, not legal advice.
