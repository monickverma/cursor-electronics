# Jev decisions for Circuit OS Phase 3: Phase 3 decision map

Research date: 2026-09-24. Researcher scope: what Phase 3 (Industrial Layer + PCB via freerouting + constraint layer) must decide, which decisions are deterministic, which belong to a person, and where a calibrated Jev (TypeSafe) judgment helps.

Method notes:
- Repo citations use `p2/` = the snapshot `/tmp/claude-0/-home-user-cursor-electronics/d7f1ec44-0d48-5872-8bcf-575641baec98/scratchpad/p2` (origin/phase2-stage0 at e803a99). `HANDOFF` = `scratchpad/HANDOFF_2026-09-25.md` (the owner's handoff text). Uncommitted WIP and later commits (94b61c1 "D2 derived", `data/figures.py`, Stage 6 substitution) are known only from HANDOFF.
- The egress proxy blocked ti.com, intertek.com, docs.flux.ai and community.quilter.ai. Claims from those domains come from search-result summaries, not full reads, and are marked "(search summary)". freerouting's docs and releases were read in full on github.com.
- This builds on `/home/user/cursor-electronics/research_notes/JEV decision use in Circuit OS/decision_patterns_ai_eda.md` (earlier notes, reused and cited as "earlier notes"). Its Q4 already covers KiCad DRC waivers (`drc_exclusions`, `.kicad_dru`, kicad-tools waiver JSON) and Quilter/DeepPCB/Allegro/Diode/atopile/JITX patterns. Those findings are not repeated in detail here.
- Jev facts (Noul / Choice / Score primitives, `confidence` field, no text generation) are from `.../JEV decision use in Circuit OS/jev_typesafe_ai.md` (first-party SDK source, typesafe-sdk 0.7.1). The project's protocol is: >0.9 act, 0.5–0.9 act with care, <0.5 a person decides or take the most reversible option and say so. TypeSafe never overrides tool_use/IR rules (HANDOFF:21; applied in p2/.claude/shared-memory/brain/decisions.md:1431-1474). No live Jev calls were made for this research.

---

## 1. What exactly is Phase 3 per PRODUCT_MASTER.md and PCB_STRATEGY.md, and what are its entry gates from Phase 2?

### Takeaway
Canonical Phase 3 is the "Industrial Layer": DCV, kitchen-hood and refrigeration boards, RS-485 I/O with optoisolation, UL 508A flagging with safety-class enforcement, basic 2–4 layer freerouting auto-layout, private component libraries, and an audit trail. Two documents add a constraint layer (net classes, diff pairs and keepouts derived from `SignalType`/`ApplicationClass`, each with a plain-English reason) as the phase's differentiating deliverable. No document states a formal Phase 2→3 exit gate. The closest things are an unmet Phase 2 "entry condition" (criterion 12), which a later decision deferred with a trigger, and a canonical Phase 2 deliverable list that the built Phase 2 deliberately does not match.

### Cited Findings
- Phase 3 "Industrial Layer" (Months 8–18) deliverables: DCV board generation, commercial kitchen hood controller, advanced refrigeration control, "RS-485 industrial I/O with optoisolation", "UL 508A flagging and safety class enforcement", "PCB auto-layout via KiCad freerouting (basic, 2–4 layer boards)", "Private component libraries per organization", "Audit trail (ISO 13485/26262 ready)". KPIs: "First enterprise contract signed. One customer prompt-to-ordered-PCB within one business day." Team tier $99/seat/month. — p2/PRODUCT_MASTER.md:346-359
- Tier 3 circuit content:
  - DCV: SCD30/SCD41 I2C or Telaire 6004 analog CO2, PID, 0–10V VFD output, damper relay, RS-485 Modbus, 24VAC→3.3V supply, fail-safe to max ventilation.
  - Kitchen hood: 0–10V VFD, duct temp, UV flame sensing, Ansul dry contacts, gas-valve relays. "The system flags UL 508A requirements and life-safety design rules".
  - Refrigeration: NTC/PT100/PT1000, 4–20mA transducers, DRV8825 EEV driver.
  - PLC-style: PC817 24VDC inputs, 4–20mA, watchdog.
  — p2/PRODUCT_MASTER.md:174-190
- Tension to resolve: the Phase 3 KPI "prompt-to-ordered-PCB within one business day" (p2/PRODUCT_MASTER.md:358) needs Gerber/fab output, but Gerber export + JLCPCB/PCBWay API + DFM are Phase 4 deliverables (p2/PRODUCT_MASTER.md:362-370). The tech-stack list says "JLCPCB API (Phase 3+)" (p2/PRODUCT_MASTER.md:411). The v1.0 copy bundled freerouting/Gerber/DFM into Phase 3 and was superseded on purpose (p2/PRODUCT_MASTER.md:5-8; p2/.claude/shared-memory/brain/decisions.md:345-360).
- Quilter positioning: "In Phase 3, Circuit OS adds basic auto-routing for 2–4 layer industrial control boards and recommends Quilter for high-complexity RF or high-speed digital boards." — p2/PRODUCT_MASTER.md:452
- PCB_STRATEGY thesis: "the moat is the constraint layer. The router is a commodity you should consume, not a product you should build." — p2/PCB_STRATEGY.md:115-116. Constraint set to build: net classes (width/clearance per signal type), diff pairs (impedance, length matching), keepouts (analog islands, antenna zones, HV clearance), placement groups, and "A plain-English reason attached to every constraint … That last bullet is the product." — p2/PCB_STRATEGY.md:221-233
- PCB_STRATEGY's own phase mapping puts the constraint layer and the designer-facing export in Phase 2. Phase 3 gets the "constrained editor" plus "Industrial rule libraries — … UL 508A, 4–20mA, RS-485 bias and termination, 24VDC supply patterns" — p2/PCB_STRATEGY.md:265-276. Later superseded: ROADMAP and decisions moved the constraint layer and freerouting to Phase 3 — p2/ROADMAP.md:150-155; p2/.claude/shared-memory/brain/decisions.md:369-374 ("treat the constraint layer … each carrying a plain-English reason — as the differentiating deliverable of that phase").
- Non-goals: beating Quilter; general CAD before HVAC; Gerber/fab APIs "right now"; more than 2–4 layers; "RF, controlled impedance, high-speed digital. Your simulator cannot validate above ~100MHz … Say so out loud rather than quietly generating them." — p2/PCB_STRATEGY.md:249-261
- Falsifiable hypotheses (§9), each of which would change the conclusion:
  1. layout quality, not explanation, is the buying trigger (test: two hobbyists, good-board-no-explanation vs mediocre-board-great-explanation);
  2. Quilter/Flux ship intent-aware constraints;
  3. HVAC customers want finished boards, not designs ("ask three real HVAC controls people before committing to step 3 or 4");
  4. constraint layer harder than it looks ("How near, given this supply, this load step, this tolerance");
  5. semantic placement rules don't generalise past five templates.
  — p2/PCB_STRATEGY.md:280-304
- Current PCB state: custom A* engine (~2,143 lines across 7 modules in the snapshot), experimental, flag-gated (`PCB_ENGINE_ENABLED`; `/pcb/compile` returns 501 when disabled). It has no tests for board_ir/kernel/router/render. The documented answer is "integrating freerouting in Phase 3 rather than testing lines slated for replacement." — p2/.claude/shared-memory/brain/decisions.md:386-427; `wc -l p2/backend/pcb_engine/*.py`
- Entry gates:
  - master_plan makes criterion 12 (external engineer reads an explanation cold) a Phase 2 *entry condition*: "Phase 2 does not *close* with the product's central claim still unverified by anyone outside this repo" — p2/.claude/shared-memory/plan/master_plan.md:104-110.
  - The later decision defers criterion 12 "with a trigger: before the first external user is shown a generated explanation" — p2/.claude/shared-memory/brain/decisions.md:429-445.
  - Neither sets a Phase 3 entry gate explicitly.
- Canonical Phase 2 deliverables are free-form generation (15 total), ESP32/STM32, live BOM pricing, version-history UI, Qdrant RAG, waveform viewer, substitution engine (p2/PRODUCT_MASTER.md:332-344). The as-built Phase 2 (HANDOFF §6, §9) is Stages 0–5 done plus Stage 6 (BOM/substitution) in progress. Free-form generation is "out of scope" and the catalogue is five generators. Live pricing (X7) awaits user approval. HANDOFF §1 says PHASE_2_PLAN_v2.md takes precedence over PRODUCT_MASTER, but that file is not in the repo snapshot.
- current_phase.md: "Last updated: 2026-09-24 (Stage 5 done; Stage 6 next, unplanned)" — p2/.claude/shared-memory/plan/current_phase.md:4, :751

### Inferences
- Phase 3 has three sub-programmes that can be ordered independently: (A) the constraint layer + freerouting (a compiler extension, needs no customers); (B) industrial circuit classes (new generators, each needing envelope/predict/proofs like the Phase 2 five); (C) enterprise features (private libraries, audit trail, UL flagging), which are driven by customers. PCB_STRATEGY §9.3 ("ask three HVAC people") is a precondition for (C) and for committing to CAD steps 3–4, but not for (A).
- The "prompt-to-ordered-PCB" KPI contradicts the Phase 4 placement of Gerber/fab. Phase 3 must either (i) move minimal Gerber export forward or (ii) restate the KPI as "prompt-to-routed-KiCad-board handed to the fab by the user". This is a person's product decision. Jev can at most estimate how blocking it is (Noul).
- There is no written Phase 2 exit gate. "Is Phase 2 done?" is therefore first a definitional decision for a person (which document's deliverable list governs), then a deterministic check against that list.

### Gaps
- PHASE_2_PLAN_v2.md, ARCHITECTURE_ASSURANCE_CASE.md and EVIDENCE_CLASSES.md are not in the snapshot (HANDOFF:5). Their Phase 2 exit criteria, if any, are unknown to this research.
- No document names the *first* industrial circuit class. The order DCV → hood → refrigeration in PRODUCT_MASTER is list order, not a stated priority.

---

## 2. Freerouting: headless/CLI invocation and parameters, how rules are passed, and where choices exist

### Takeaway
Freerouting 2.x runs headless (`--gui.enabled=false`), as a REST API server, or through Docker/MCP. Circuit OS would drive it with `-de board.dsn -do board.ses -mp N`, plus router settings (`--router.via_costs`, `--router.plane_via_costs`, `--router.start_ripup_costs`, preferred/undesired direction costs, `-us`, `-is`, `-inc` to skip net classes), and get a KiCad-schema JSON DRC report with `-drc`. Net classes, widths and clearances go in through the DSN `(network (class …))` block or a `.rules` file (`-dr`). The existing `to_dsn()` already emits per-class width/clearance but omits via padstacks, diff pairs, per-class layer restrictions and placement/via keepouts. Every router knob is a numeric parameter that should come from a deterministic profile table. None of them is a place for a Jev judgment.

### Cited Findings
- CLI flags (verbatim descriptions):
  - `-de` "Loads a design file at startup … Specctra board (`.dsn`), Specctra session file (`.ses` - optional), Freerouting design rules file (`.rules` - optional)"
  - `-do` "Saves the routing results … `.dsn`, `.ses`, … `.scr`"
  - `-dr` "Reads design rules from an explicit `.rules` file. Supports design rules, net classes, clearances, via definitions"
  - `-drc` "Writes the design rules check report in KiCad JSON DRC schema format"
  - `-mp` "upper limit for the number of autorouter passes"
  - `-mt` threads
  - `--router.optimizer.improvement_threshold`
  - `-inc` "Lists net classes to ignore during autorouting"
  - `-us [greedy | global | hybrid]`, `-hr [m:n]`, `-is [sequential | random | prioritized]`
  - `-da` disables analytics
  - `--gui.enabled=false`, `--api_server.enabled`

  — [freerouting docs/command_line_arguments.md](https://github.com/freerouting/freerouting/blob/master/docs/command_line_arguments.md)
- Router settings and defaults: `router.default_preferred_direction_trace_cost` 1.0, `…undesired_direction_trace_cost` 2.5, `router.autorouter.max_passes` 100, `router.improvement_threshold` 2.5, `router.via_costs` 50, `router.plane_via_costs` 5, `router.plane_nets` ["GND","VCC"], `router.start_ripup_costs` 100, `router.automatic_neckdown` true, `router.allowed_via_types` true. — [freerouting docs/settings.md](https://github.com/freerouting/freerouting/blob/master/docs/settings.md)
- Settings precedence (low→high): defaults 0, `freerouting.json` 10, "RULES file overrides" 40, env vars `FREEROUTING__ROUTER__*` 55, CLI `--router.*` 60, "REST API caller — highest priority" 70. — [settings.md](https://github.com/freerouting/freerouting/blob/master/docs/settings.md)
- Releases: v2.4.1 (3 Sep 2025) was the latest listed at fetch time, with a hardened REST API and non-root Docker UID 10001. v2.3.0 (7 Aug 2025) added "dedicated MCP server" and parsing of "Specctra `.rules` autoroute settings". v2.2.0 added `-drc` JSON and `GET /v1/jobs/{jobId}/drc`, and a "layered `SettingsMerger` with nine priority levels". — [freerouting releases](https://github.com/freerouting/freerouting/releases). (The earlier notes cite issue #848 saying `.rules` autoroute settings were not parsed; per the release notes, v2.3.0 addressed this.)
- Past bug: `-mp` was ignored in 2.0.1 CLI mode (`--gui.enabled=false`); fixed later. — [freerouting issue #376](https://github.com/freerouting/freerouting/issues/376)
- KiCad integration risk: "Both DSN and JSON/API will break when KiCad removes SWIG (expected KiCad 11 / nightly)". The migration moves to KiCad protobuf IPC while "keeping Freerouting's JSON schema and REST API as the stable inner boundary". — [freerouting issue #787](https://github.com/freerouting/freerouting/issues/787) (search summary). KiCad's own DSN export has fidelity bugs, e.g. "copper to hole clearance" is not exported — [KiCad #14439](https://gitlab.com/kicad/code/kicad/-/issues/14439); net-class clearances saved incorrectly — [KiCad #14713](https://gitlab.com/kicad/code/kicad/-/issues/14713) (titles only).
- Practitioner defaults: via minimisation on, via cost ≥3, limit layers to essential pairs, set widths/clearances/vias before routing — earlier notes Q4 citing [Sierra Circuits](https://www.protoexpress.com/blog/how-to-autoroute-pcb-layout-in-kicad-using-freerouting-plugin/).
- Circuit OS's current bridge: `to_dsn(board)` (p2/backend/pcb_engine/router.py:499-562). Its docstring gives the Docker invocation `-de /work/board.dsn -do /work/board.ses -mp 100` (:500-507). It emits:
  - signal layers
  - a board-wide default `(rule (width 0.2)(clearance min-class-clearance))` (:522-523)
  - wire keepouts only (`kind in ("wire","all")`, :524-527)
  - `(class name nets (rule (width)(clearance)))` per NetClass (:554-557)

  It emits **no** via padstack, **no** `DiffPair`, **no** per-class layer rule, **no** via/placement keepouts, and does not use the `Keepout.reason` field. The router module says to "implement `RouterBackend` against Freerouting" (router.py:27-32).
- Board IR already has typed slots:
  - `Keepout(kind, layer, x,y,w,h, reason)` (p2/backend/pcb_engine/board_ir.py:103-110)
  - `NetClass(name, nets, track_width=0.2, clearance=0.15, via_drill=0.4, via_diameter=0.8, priority)` (:117-124)
  - `DiffPair(net_p, net_n, width, gap, target_impedance, max_skew_mm)` (:128-135)

  Today `from_netlist` only creates "default" (0.3/0.25) and "power" (0.8/0.3) classes (p2/backend/pcb_engine/compile_board.py:74-78), and hardcodes 2 layers with B.Cu as ground plane (:52-53).

### Inferences
- Freerouting parameters fall into three groups:
  - **Board facts**: layer count/stackup, plane nets, via padstack. These are deterministic from the constraint layer and fab profile.
  - **Router effort** (`-mp`, `-mt`, improvement threshold, `-us`/`-is`). Deterministic defaults. Reversible, so tune by running N candidates and grading them, the way the A* engine's `generate_candidates` already does.
  - **Cost weights** (via cost, direction costs, ripup). Deterministic profile per board class.

  None of these is judgment-shaped. Jev should never emit a number that goes into freerouting.
- Pass rules through the DSN `(network (class …))` block that Circuit OS generates itself, not through KiCad's DSN export, because of the KiCad exporter bugs and the SWIG removal. Use `-drc` JSON as the machine-readable check that feeds claims. Pin a freerouting version, since settings precedence and `.rules` parsing changed across 2.2–2.4.
- The one real *choice* in router integration is which candidate to accept when several route at 100% with different via counts and lengths. That can be a deterministic score (the A* engine already has one), with a human pick in the UI, following the Quilter pattern.

### Gaps
- I did not read the Specctra DSN spec for diff-pair (`(pair …)`), per-class `(circuit (use_layer …))` or via-per-class syntax, or confirm which of these freerouting honours. This needs checking against freerouting source before extending `to_dsn()`.
- No independent benchmark of freerouting quality on 2–4 layer industrial boards was found.
- I could not confirm whether any freerouting release after v2.4.1 exists (September 2026). The releases page showed v2.4.1 as latest when fetched.

---

## 3. How do Quilter, Flux, JITX, atopile, Celus, DeepPCB and Diode handle constraint setting, net classification and human approval (2025–2026)?

### Takeaway
Across all of them, the human (or code the human wrote) owns the constraints and the machine generates and ranks candidates. Quilter reads net classes/diff pairs/impedance from the user's CAD files and lets the engineer override calculated impedance per class. Flux turns *approved* Copilot suggestions into a knowledge base of rules. atopile, JITX and Diode encode constraints as typed code with tolerances and assertions. None of the sources describes a tool that *derives* net classes from design intent and attaches a reason, which is Circuit OS's claimed gap. No vendor documents a calibrated confidence per constraint.

### Cited Findings
- Quilter: users "provide constraints and intent including net classes, diff pair definitions, and impedance targets if specified", then Quilter generates multiple candidates via RL, validates DRCs, and the user reviews and selects. 2026 releases: "Full clearance constraint support is in active development, letting Quilter read net-class clearance rules, layer-specific clearances, and pair-specific clearances directly from input files", and "engineers can override Quilter's calculated impedance values for individual net classes directly in the app." Also automated BGA fanout (2026). — [Quilter 2026 autorouting review](https://www.quilter.ai/blog/pcb-autorouting-in-2026-a-review-of-traditional-tools-vs-quilters-ai-approach); [AccessNewswire 2026 release](https://www.accessnewswire.com/newsroom/en/electronics-and-engineering/automated-bga-fanout-headlines-quilters-2026-releases-that-expand-the-c-1188028) (search summaries)
- A Quilter community thread is titled "KiCad Net Classes are being ignored". It suggests constraint import from KiCad was not reliable at some point; the content could not be read (proxy blocked). — [community.quilter.ai/t/396](https://community.quilter.ai/t/kicad-net-classes-are-being-ignored/396)
- Quilter's stated view is that the highest-value human work is "deciding intent, constraints, and tradeoffs"; output is "a set of inspectable candidates with evidence attached". — earlier notes Q1, [Quilter interface post](https://www.quilter.ai/blog/the-quilter-interface-comparing-ai-driven-vs-manual-pcb-design-ui)
- Flux: Spring 2026 update brought a "self-correcting AI agent" and improved AI Auto-Layout. Knowledge: "As you approve suggestions, they become part of your personal or project memory: vendor preferences, naming conventions, design rules, review checklists". Flux has a "Layout Rules List" reference doc (content blocked). — [Flux Spring 2026](https://www.flux.ai/p/blog/spring-2026-updates-faster-ai-better-layouts-smarter-sourcing); [Teach Copilot with Knowledge](https://www.flux.ai/p/blog/teach-copilot-how-you-work-with-knowledge); [Flux layout rules doc](https://docs.flux.ai/reference/layout-rules-types) (search summaries)
- atopile: requirements with "units, tolerances, and assertions", a solver picks parts, and the agent skill says to convert exact assignments to toleranced/bounded values when the solver finds contradictions. JITX: parametric families, then a human spot-checks the MPNs. Diode/Zener: Starlark DSL plus automatic SPICE; Claude iterates on simulator feedback. Celus: requirements → block diagram → component compatibility checks → BOM with live stock. DeepPCB warns that RL routing can "violate some subtle constraint", which argues for deterministic DRC afterwards. — earlier notes Q1 (sources there: [atopile](https://github.com/atopile/atopile), [JITX docs](https://docs.jitx.com/en/4.4/jumpstart-kits/js1-stackup-components/part2-parametric-passives/JS1_Part2_Parametric-Passives_Runbook.html), [Diode blog](https://blog.diode.computer/anthropic-partnership), [Celus BusinessWire 2025-12-17](https://www.businesswire.com/news/home/20251217050156/en/CELUS-and-AGS-Devices-Simplify-Electronics-Design-and-Procurement-Processes), [DeepPCB](https://deeppcb.ai/reinforcement-learning-pcb-routing-explained/))
- The PCB_STRATEGY competitor table: Flux "No simulation"; Quilter "Receives a netlist … intent never reached it"; Celus "Stops at the schematic"; KiCad/Altium "The human supplies the constraints." — p2/PCB_STRATEGY.md:74-79. Watch item: "If Quilter or Flux ships intent-aware constraints, the moat closes fast. Flux is closest" — p2/PCB_STRATEGY.md:289-291

### Inferences
- The 2026 evidence partly erodes PCB_STRATEGY §9.2. Quilter is moving toward *reading* engineer-authored constraints (clearance, pair, layer-specific) and exposing per-class overrides. It does not yet *derive* them from intent. That makes Circuit OS's constraint file a feed *into* Quilter's new import path, which supports the "workflow partner" framing (p2/PRODUCT_MASTER.md:452), provided the export is in KiCad-native net classes / `.kicad_dru`, not only DSN.
- Flux's "approve a suggestion → becomes a rule" pattern matches private component libraries and org rule sets (Phase 3 deliverable). The Circuit OS equivalent is the existing sign-off mechanism (user signs a hash of property sentences, HANDOFF §5), extended to org-level constraint profiles.
- No competitor exposes calibrated per-decision confidence. A Jev probability recorded on each classification would be a distinctive audit feature, but only if it is calibrated on Circuit OS's own labelled data.

### Gaps
- Flux layout-rules doc and Quilter community thread content were blocked. No detail on how Flux scopes rules (object/net/layout inheritance).
- I found no public information on how Celus, JITX or atopile log human approvals as audit records.
- DeepPCB 2026 product changes were not researched.

---

## 4. How can the constraint layer carry "each constraint with a plain-English reason" while keeping reasons deterministic, and how would constraints become graded claims with defeaters like Phase 2?

### Takeaway
Keep the pattern already used in Phase 2: the only non-deterministic input is a *label* (or IntentIR field). A versioned table maps (label, signal type, board/fab profile) to a numeric constraint and a reason template. A deterministic check (freerouting `-drc` JSON, the DRC kernel, or a geometric computation) turns each constraint into a claim with verdict, grade and defeaters. Jev's role is limited to choosing the label where the IR does not already fix it (for example environment/pollution class, isolation need, net role for an unrecognised net), and its probability goes into the claim's scope as an assumption. It never sets a value and never writes the reason.

### Cited Findings
- The IR already carries the classification inputs: `SignalType` (power, ground, digital, analog, i2c_*, spi_*, uart_*, rs485_a/b, pwm, one_wire), `ApplicationClass` (hobby_arduino, iot_node, industrial_io, hvac_control, modbus_rtu), `SafetyClass` (general, industrial, life_safety), `ValidationRule` incl. `rs485_bias_resistors`, `operating_temp_range`. — p2/backend/core/ir_schema.py:29-70
- PCB_STRATEGY's example of the target output: "This is an RS-485 bus. A/B is a differential pair, 120Ω termination at both physical ends of the bus and nowhere else, TVS at the connector entry, minimum 8mm from the switching regulator, bias resistors near the master." — p2/PCB_STRATEGY.md:106-110. Its warning: "'How near, given this supply, this load step, this tolerance' is a real engineering problem. If the constraints are vague, the explanation is vague" — p2/PCB_STRATEGY.md:297-300
- Phase 2 assurance machinery to reuse (HANDOFF §5):
  - claims with kind, verdict, grade (G0 proof-checked … G1 z3/closed-form/exact-graph … G5 ngspice nominal, G6 sampled, G7 asserted/not assessed), scope (model, measures, assumes, figures) and cited defeaters;
  - `grade_floor` = worst critical claim;
  - "every implemented rule runs on every design (X8)";
  - figure provenance records with kind guaranteed/typical/derived/standard/stated-assumption (HANDOFF §8);
  - defeater D5 "LLM-written IntentIR untrusted … closed by user sign-off".
- Phase 2 precedent for derived, zero-LLM explanations: `ai/derived_explainer.py` (0 calls) sits alongside the LLM explainer (HANDOFF §5). The decision "Explanation derivability: yes for the baseline, no for the domain layer" — p2/.claude/shared-memory/brain/decisions.md:530
- Jev primitives are Choice (label set with per-label probabilities and `confidence`), Noul (yes/no probability) and Score (ordered rubric). No text is generated. — jev_typesafe_ai.md §2 (typesafe-sdk 0.7.1)
- freerouting produces a DRC report in KiCad JSON schema (`-drc`) — [command_line_arguments.md](https://github.com/freerouting/freerouting/blob/master/docs/command_line_arguments.md). `Keepout.reason` already exists as a field (p2/backend/pcb_engine/board_ir.py:110).
- The earlier notes list Hamel Husain's guidance on LLM judges: binary pass/fail with a calibration set, and against 1–5 scales without data — earlier notes Q2, [hamel.dev](https://hamel.dev/blog/posts/llm-judge/)

### Inferences
Proposed shape (a design sketch, not sourced):
- **ConstraintRule table**: `(rule_id, when: {signal_type | net_role | env_label | safety_class}, emits: {kind: net_class|diff_pair|keepout|placement_group|clearance, params}, reason_template, source: {kind: standard|datasheet|derived|house_rule, ref}, version)`. The reason is rendered from the template and the params, for example: "RS485_A/RS485_B routed as a pair, gap {gap} mm, because the IR types them rs485_a/rs485_b (differential bus); source: TIA-485 practice, house rule HR-12 v1." Byte-identical for identical input, like the netlist.
- **Constraint claim**: kind `layout_constraint`. The verdict comes from the routed board (freerouting DRC JSON + own geometric check). Grade: G1 when the check is exact geometry against a table value. The table value's provenance kind (standard/derived/house rule) goes into `scope.figures`, the same way D7 treats datasheet figures. G7 when the constraint is emitted but unchecked (e.g., a diff-pair impedance target that the ngspice/closed-form layer cannot evaluate above ~100 MHz, per p2/PCB_STRATEGY.md:259-261).
- **New defeaters**:
  - *L1 "constraint value is a house rule, not derived from this circuit's physics"* (open until a derivation exists; this is exactly §9.4);
  - *L2 "input label was judged, not stated by the user"* (open when a Jev-chosen label feeds the table; closed by user sign-off, like D5);
  - *L3 "router ignored or could not express the constraint"*: DSN/KiCad fidelity. Closed by re-checking the routed board independently of the router's own DRC;
  - *L4 "standards applicability judged"* for UL/IEC flags (see §5).
- **Where Jev sits**: `env_label` (e.g., pollution degree 1/2/3, overvoltage category I–IV, indoor-controlled vs field-wired), `isolation_needed` (Noul), and `net_role` for a net whose SignalType is generic (`digital`/`analog`) but whose role matters for layout (e.g., "0–10V VFD output", "4–20mA loop", "relay coil drive"). All are Choice over a fixed enum. The claim stores `{label, jev_probabilities, jev_confidence, model: "jev-1.13.x"}` in `scope.assumes` and cites L2.
- **Negative controls / mutation**, per project process: flip each Jev label to its runner-up and show that the emitted constraint and reason change deterministically, and that some claim or defeater records the difference (the same idea as `figure_audit.py` perturbing each figure, HANDOFF §8).

### Gaps
- No external source describes a production EDA tool attaching deterministic reason text to each constraint. The design above is an inference, not an observed pattern.
- The grade scheme's meaning for geometric layout checks (G1 vs a new grade) was not defined anywhere in the snapshot. It needs an owner decision.

---

## 5. Industrial standards applicability (UL 508A, IEC 61131-2, RS-485 isolation, creepage/clearance per IPC-2221 / IEC 60664): which decisions are rule lookups and which are judgment?

### Takeaway
The numbers are lookups: creepage/clearance from IEC 60664-1 tables given (working voltage, pollution degree, material group/CTI, overvoltage category, insulation type), IPC-2221 spacing given voltage, IEC 61131-2 input thresholds given input Type, and the RS-485 common-mode range. The *inputs* to those lookups need judgment: which end-product standard applies, the pollution degree and overvoltage category of the install, whether a board is part of a UL 508A panel at all, and whether ground-potential difference can exceed ±7 V. Those are fixed-label classifications, which suits Jev as advisory triage. The final applicability call for a safety standard stays with a person, since it is a certification/liability one-way door.

### Cited Findings
- Which UL standard applies depends on the product: UL 60730-1 (and Part 2s) for automatic electrical controls for household and similar use (UL 873 being withdrawn into UL 60730); UL 508A for industrial control *panels*; UL 61010-1 / 61010-2-201 for programmable controllers ("after July 25, 2016, all new investigations of programmable controllers need to comply"). — [UL Solutions HVAC motor controllers](https://www.ul.com/resources/hvac-motor-controllers); [Intertek UL 508 → UL 61010 transition](https://www.intertek.com/standards-updates/transition-from-ul-508-to-ul-61010-1-and-ul61010-2-201/) (search summaries; Intertek blocked)
- UL 508A was revised in 2025 — [Intertek, 2025-08-19](https://www.intertek.com/blog/2025/08-19-ul-508a-revisions-for-industrial-control-panels/) (title only; content blocked, so the specifics of the revisions are unknown).
- IPC-2221 "is a functional requirement, not a safety requirement". It treats <15 V as low voltage. IEC 60664-1 Table F.4 gives minimum creepage by working voltage, pollution degree and material group. Material groups are defined by CTI. Pollution degree 1 = no/non-conductive pollution; 2 = normally non-conductive with occasional condensation-induced conductivity. — [TI SLUP419](https://www.ti.com/lit/pdf/slup419); [EMA clearance/creepage table](https://www.ema-eda.com/ema-resources/blog/pcb-clearance-and-creepage-distance-table/); [NI pollution degree](https://www.ni.com/en/support/documentation/supplemental/22/pollution-degree-rating-for-electrical-equipment.html) (search summaries; TI PDF blocked)
- IEC 61131-2 defines digital input Types 1, 2 and 3. Type 1 is for electromechanical contacts and 3-wire sensors; Type 3 is lower-power. OFF→ON transition between 11 V (Type 2/3) or 15 V (Type 1), ON up to 30 V. Type 1/3 designs aim for ~2 mA ON-state current. — [TI SLLA370](https://www.ti.com/lit/pdf/slla370); [ADI MAX22191 note](https://www.analog.com/en/resources/design-notes/industrial-digital-inputs-with-the-max22191.html); [btbm.ch](https://btbm.ch/24vdc-iec-61131-2-compliant-digital-inputs-with-jelly-bean-parts/) (search summaries)
- RS-485 common-mode range is −7 V to +12 V. Ground-potential differences beyond it cause failure or damage, and transients "can produce ground shifts that far exceed 7V". Isolated transceivers are recommended when GPD is large or unpredictable (separate power circuits, long runs). — [EDN, inside an isolated RS-485 transceiver](https://www.edn.com/inside-an-isolated-rs-485-transceiver/); [Power Systems Design, "Isolate to Communicate"](https://www.powersystemsdesign.com/articles/isolate-to-communicate/22/5838) (search summaries)
- Repo: `SafetyClass` enum {general, industrial, life_safety} exists (p2/backend/core/ir_schema.py:56-59). The kitchen-hood tier is explicitly "life-safety" (p2/PRODUCT_MASTER.md:182). The Phase 3 deliverable is "UL 508A flagging and safety class enforcement" (p2/PRODUCT_MASTER.md:353), and the canonical text says "flagging", not certification.

### Inferences
- PRODUCT_MASTER names UL 508A, but for most Phase 3 boards (a DCV or refrigeration *controller board*) the directly applicable standard is more likely UL 60730-1 or UL 61010-2-201. UL 508A governs the panel the board may be mounted in. The applicability decision is therefore real and non-trivial, and it belongs to a person. Circuit OS should *flag* candidates, not assert compliance.
- Lookup vs judgment split:

| Decision | Nature | Owner |
|---|---|---|
| Creepage/clearance mm, given (V_work, PD, MG, OVC, insulation type) | table lookup | deterministic |
| IPC-2221 spacing, given voltage/layer | table lookup | deterministic |
| IEC 61131-2 input thresholds/current, given Type | table lookup | deterministic (generator envelope) |
| RS-485 common-mode headroom, given declared GPD | arithmetic | deterministic |
| Pollution degree / OVC / indoor-vs-field install | classification from user context | Jev Choice (advisory), user confirms |
| Input Type 1 vs 3 (what is wired to it) | classification | Jev Choice, user confirms; IntentIR field |
| Is isolation needed (GPD unknown, long cable, separate supplies) | yes/no under uncertainty | Jev Noul; <0.9 → pick isolated (the safer, reversible-at-design-time option) and say so |
| Which end-product standard family applies (60730 / 61010 / 508A-panel / none) | applicability | Jev Choice for triage **only**; person decides; never auto-asserted |
| Life-safety classification (hood/gas valve) | one-way door | person only; Jev may flag "possibly life-safety" (Noul) to force review |
| Material group / CTI | datasheet fact of the laminate | deterministic from fab profile; D7-style provenance |

- Guardrail: a Jev label must never *lower* a safety requirement. Asymmetric rule: if Jev says PD2 but the user has not confirmed, use the stricter of {Jev label, default-conservative label} for dimensions, and record L2. This mirrors the "most reversible option" protocol.

### Gaps
- Could not read the actual IEC 60664-1 tables or UL 508A 2025 revision text (paywalled/blocked). Numeric creepage values are not recorded here.
- Could not confirm which UL/IEC standard HVAC OEM customers of the kind targeted would actually require. This is PCB_STRATEGY §9.3's "ask three HVAC people" and cannot be answered from the web.
- IEC 61131-2 applies to PLCs. Whether it should govern a "PLC-style" Circuit OS board is itself an applicability judgment. No source addressed this.

---

## 6. Phase-transition decisions: is Phase 2 done, what to carry, what to defer (criterion 12 trigger, D1 bench, D7 verification), framed as Jev requests. Plus the consolidated Phase 3 decision map

### Takeaway
"Is Phase 2 done?" cannot be answered by Jev or by a check until a person fixes which deliverable list governs (PHASE_2_PLAN_v2 vs PRODUCT_MASTER). After that it is a deterministic checklist. The carry/defer questions (criterion 12 trigger, D1 bench, D7 verification, RS-485 DE/RE pull-down, live pricing) are the kind of calls the project has already put to Jev (RC swamping at 0.83, LED at 0.44 → person/reversible). Each can be framed as a Choice over explicit options with the full scenario as state. Of the Phase 3 decisions themselves, most are deterministic (tables, profiles, DRC), a handful are person-owned one-way doors (first industrial class, UL applicability, life-safety, layer count/fab, Gerber-in-Phase-3), and Jev fits in about eight classification/triage slots.

### Cited Findings
- The owner's open decisions: RS-485 DE/RE 10 kΩ pull-down ("would let fail-safe claim drop D2. Product call"); live pricing X7; bench D1 and datasheet pass D7 "when engineer chooses"; `kind` on exact proofs analytic vs empirical; explainer max_tokens (cost). — HANDOFF §7
- Defeater register:
  - D1 hardware unvalidated (bench sheet `docs/BENCH_D1.md`, evidence-record code not built)
  - D3 = criterion 12, deferred with trigger
  - D4 coverage may outrun one engineer
  - D5 closed by sign-off
  - D7 figures unverified (verify tool built, uncommitted, `figure_verifications.json` empty)
  - D9 generator bug per generator until M1 matrix

  — HANDOFF §5, §8
- Criterion 12 trigger: reopens "before the first external user is shown a generated explanation … a public launch, a demo to a prospect, or onboarding anyone outside this repo" — p2/.claude/shared-memory/brain/decisions.md:429-436. Phase 3's KPI "First enterprise contract signed" (p2/PRODUCT_MASTER.md:358) necessarily involves demos to prospects, so **the trigger fires at the start of Phase 3 sales activity**.
- Precedent for Jev use: two Choices and three Nouls with ~10.6k characters of state. `rc_option` swamp 0.87 (confidence 0.83) was implemented. `led_option` confidence 0.44 was below threshold, so the reversible option was taken and "The user may overrule". — p2/.claude/shared-memory/brain/decisions.md:1431-1474
- Explainer cost/latency: 110–130 s and ~$0.20 per explanation; the RS-485 design still exceeds 8192 tokens; "generation cannot meet the 15 s launch target"; OpenRouter credits exhausted — p2/.claude/shared-memory/brain/decisions.md:1498-1521; HANDOFF §4.
- Bench D1 is a one-hour session for three designs (`docs/BENCH_D1.md`), and the owner has no oscilloscope — p2/.claude/shared-memory/brain/decisions.md:1523-1527; HANDOFF §1.
- Out of Phase 2: "switching converters, PCB layout, foreign-netlist recognition, fine-tuning, team features" — HANDOFF §9. Phase 3 DCV needs a 24VAC→3.3V supply (p2/PRODUCT_MASTER.md:178), i.e. a switching converter, which is out of Phase 2 scope and has no transient simulation (HANDOFF §9: "no transients").

### Inferences

**A. Phase-transition decisions as Jev requests** (all state = HANDOFF + relevant decisions entries, options with costs side by side, as in the 2026-09-23 precedent)

| Request | Primitive / labels | Why Jev fits | Guardrail |
|---|---|---|---|
| `phase2_governing_list` | none: person | Definitional; Jev cannot choose which spec is canonical | Person records it in decisions.md before any "done" check |
| `phase2_exit_ready` | Noul, after the list is fixed | Mostly deterministic (tests, progress.yaml); Jev only on residual items like "Stage 6 BOM route unbuilt: blocking?" | Deterministic checklist wins; Jev only annotates |
| `stage6_finish_before_phase3` | Choice {finish_now, finish_in_parallel, defer_to_phase3} | Real trade-off, reversible | 0.5–0.9 → act with care |
| `criterion12_trigger_timing` | Noul "Will a prospect see an explanation within the first Phase 3 milestone?" | Estimates whether the trigger is imminent | If >0.5, schedule the external read *before* Phase 3 sales; the trigger itself is fixed text and cannot be overridden |
| `d1_bench_timing` | Choice {before_phase3_pcb, before_first_customer, keep_deferred} | Trade-off; one hour but needs equipment the owner lacks | Person decides if <0.9 (owner's time and money) |
| `d7_verify_scope` | Choice {all_155, critical_claim_figures_only, industrial_parts_only_as_added} | Prioritisation over a fixed set | Deterministic figure_audit already ranks sensitivity; Jev picks policy only |
| `rs485_de_re_pulldown` | Choice {add_10k, leave, make_option} | Product call already framed | Owner-listed; Jev advisory only |
| `x7_live_pricing_in_phase3` | none: person | Explicit user approval required (HANDOFF §2) | Jev never used to satisfy an approval |
| `explainer_path` | Choice {thinking_off, faster_model, off_request_path} | Cost/latency trade-off | Reversible; fine for 0.5–0.9 |

**B. Phase 3 decision map**

| # | Decision | Deterministic | Human | Jev (primitive → feeds) | Guardrail |
|---|---|---|---|---|---|
| 1 | Scope ordering: constraint layer + freerouting vs industrial generators vs enterprise features | — | **Yes** (one-way-ish: sets 6–10 months) | Choice {constraints_first, industrial_first, parallel} as advisory with full state | <0.9 → person; the constraint layer needs no customers, so it is the reversible default |
| 2 | First industrial circuit class | Feasibility filter: drop classes needing switching converters/transients (DCV 24VAC supply, EEV stepper) | **Yes**, after PCB_STRATEGY §9.3 customer conversations | Score each candidate class against a fixed rubric (reuse of existing proofs, needs transient sim, rule-library overlap with rs485_node) | Jev ranks; person picks; filter applied before Jev |
| 3 | Net role of each net | SignalType → net class table (existing enum) | — | Choice over `net_role` enum only for generic `digital`/`analog` nets in new industrial generators (e.g., 0–10V out, 4–20mA loop, relay coil, 24V field input) | Generator-declared role wins; Jev only when undeclared; L2 defeater; runner-up mutation test |
| 4 | Net class parameters (width, clearance, via) | **Yes**: table keyed by (net class, fab profile, current from predict()) | Approves table versions (house rules) | None | Jev never emits numbers |
| 5 | Diff pairs | **Yes**: rs485_a/b typed pairs | — | None | Impedance target G7 unless computed; say so (PCB_STRATEGY:259-261) |
| 6 | Keepouts / placement groups | **Yes**: rules keyed on component role (decoupling, transceiver-near-connector, TVS-at-entry, p2/PCB_STRATEGY.md:204-215) | — | Choice `component_role` only for a catalogue part without a declared role | Private libraries must declare roles; Jev fallback flagged |
| 7 | Layer count (2 vs 4) | Rule: 2 unless routing fails at N candidates or a plane requirement exists | Approves when cost changes (fab one-way door) | Noul "is 4-layer justified" only as triage after 2-layer fails | Never auto-upgrade; person confirms |
| 8 | Freerouting parameters | **Yes**: pinned version, profile table, N candidates, deterministic scoring | Picks among 100%-routed candidates (Quilter pattern) | None | `-drc` JSON + independent re-check |
| 9 | DRC waivers | Stored as typed records in Circuit OS (not KiCad `drc_exclusions`, earlier notes Q4) | **Yes**: every waiver signed by a person | Choice triage {cosmetic, needs_review, safety_relevant} to order the review queue | Jev can never grant a waiver; safety_relevant forces review regardless of probability |
| 10 | Environment inputs (pollution degree, OVC, install) | Lookup once chosen | Confirms | Choice from user's description | Use the stricter of {Jev label, conservative default} until confirmed |
| 11 | Isolation needed (RS-485, 24V inputs) | GPD arithmetic if declared | Confirms | Noul when GPD undeclared | <0.9 → isolated option, say so |
| 12 | Standard applicability (UL 60730 / 61010-2-201 / 508A panel / none) and life-safety | — | **Yes** (liability) | Choice triage + Noul "possibly life-safety" to force review | Output worded as "flag", never "compliant" |
| 13 | Private library part admission | Schema, pin, footprint, provenance checks (D7-style records) | Org admin approves | Choice {accept, needs_datasheet_check, reject} triage on the part record | Deterministic checks must pass first; Jev orders the queue only |
| 14 | Audit trail content | **Yes**: every Jev answer stored with model id, state hash, probabilities, threshold band and the acting party | Defines retention/format target (ISO 13485/26262 "ready") | None | Jev answers are evidence records, never approvals (the project already requires only a person's sign-off to close D5) |
| 15 | Gerber in Phase 3 (KPI tension) | — | **Yes** | Noul "Is the prompt-to-ordered-PCB KPI reachable without Gerber export?" advisory | Product decision |

**C. General guardrails for Jev in Phase 3** (derived from repo rules and the sources above)
1. Jev outputs labels only from enums defined in code (`net_role`, `env_label`, `standard_family`, `waiver_triage`). A label outside the enum is impossible by construction (Choice).
2. Labels feed versioned deterministic tables. Reasons are rendered from templates, never from Jev and never from an LLM.
3. Thresholds: >0.9 act, 0.5–0.9 act with care (and record L2), <0.5 person decides or take the reversible/stricter option (HANDOFF:21). For safety-relevant labels the stricter option applies at every band until a person confirms.
4. Calibrate before trusting 0.9. Build a labelled set per question (like Stage 1's 200/200 abstention corpus) and measure. No independent calibration study of Jev exists (jev_typesafe_ai.md §2 Gaps).
5. Every Jev-fed constraint cites a defeater (L2) closed only by user sign-off. Mutation test: flipping to the runner-up label must change output and be caught.
6. Jev never grants an approval, waiver, compliance statement or price approval (X7). It only orders queues and flags.

### Gaps
- Without PHASE_2_PLAN_v2.md, I cannot state the governing Phase 2 exit criteria. The table treats this as a person-owned definitional decision.
- No data exists yet to calibrate any of the proposed Jev questions. The project's two prior Jev uses were one-off judgement calls, not repeated classifications with ground truth.
- No customer evidence (HVAC/refrigeration OEMs) was found to pick the first industrial class. The web cannot answer PCB_STRATEGY §9.3.
