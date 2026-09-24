# Decision Patterns in AI EDA/PCB Tools and LLM Applications (for Circuit OS)

Method note: the network proxy blocked direct page fetches from flux.ai, quilter.ai and blog.diode.computer, so the claims below come from search-engine summaries of those pages, not full reads. Treat vendor claims as marketing unless noted. Where a date could not be confirmed, it says so. Research date: 2026-09-24.

## Q1. How do AI EDA/PCB tools handle component selection, trade-offs, constraints, design review, and human-in-the-loop approval? What do they log/explain?

### Takeaway
The pattern that recurs across the products is **LLM/AI proposes → a deterministic tool or solver checks → a human approves the ranked or flagged result**. The code-first tools (Diode Zener, atopile, JITX) turn requirements into typed, toleranced constraints in source files that live in version control. A solver picks the parts, and simulation or static netlist checks close the loop. The layout tools (Quilter, DeepPCB, Allegro X AI) generate candidates, and the human's job moves to setting constraints and choosing a candidate. Circuit OS already has this architecture (LLM → IR → compilers). What it lacks is an explicit, logged record of each decision.

### Cited Findings
**Diode Computers + Anthropic (Zener), 2025**
- Zener is a DSL built on Starlark for describing PCB schematics. Diode's `pcb` CLI compiles it to KiCad and adds software-style linting, versioning and automation. — [Zener docs](https://zener.diode.computer/); [spec.mdx on GitHub](https://github.com/diodeinc/pcb/blob/main/docs/pages/spec.mdx); [Gend summary](https://www.gend.co/blog/enhancing-claude-pcb-design-skills)
- Each Zener module can include SPICE simulations that run automatically. When Claude proposes a filter, bias network or power stage, the simulation returns real numbers. If the circuit misses spec, the model sees why and iterates. The full netlist is also available for static checks: tracing power paths, checking signal directionality, and catching floating pins or miswired rails. — [Diode blog "Teaching Claude To Design Circuit Boards That Ship"](https://blog.diode.computer/anthropic-partnership) (via search summary; date not confirmed, likely late 2025)
- Diode's electrical engineers preferred Claude Sonnet 4.5's reference designs 8 out of 10 times. Evaluation was by expert pairwise preference on reference-design generation from chip datasheets. Anthropic says the approach carries over to any domain "on tasks with clear success and failure criteria." — [Anthropic/Claude blog, "Making Claude a better electrical engineer"](https://claude.com/blog/making-claude-a-better-electrical-engineer) (2025, Sonnet 4.5 era)
- Diode raised an $11.4M Series A led by a16z in July 2025. Its toolchain is written in Rust and exports to KiCad and Altium. — [Dealroom](https://app.dealroom.co/news/feed/diode-computers-raises-11-4m-for-ai-pcb-design); [NY Ledger](https://thenyledger.com/markets/diode-computers-is-designing-circuit-boards-with-ai-it-just-raised-11-4-million-led-by-andreessen-horowitz/)

**atopile**
- atopile is a declarative language. Its compiler solves constraints, picks parts, runs checks and updates the KiCad layout. It captures requirements "with units, tolerances, and assertions" and supports automatic parametric picking of discrete parts. — [atopile GitHub](https://github.com/atopile/atopile); [PyPI](https://pypi.org/project/atopile/)
- The repo's Claude skill (`.claude/skills/ato/SKILL.md`) tells agents to prefer stdlib generics (Resistor, Capacitor, LED, Fuse…) with value and package constraints over fixed parts. When the solver reports contradictory constraints, the skill says to "convert exact assignments to toleranced/bounded values" and remove redundant assertions. For unstable part selection, it says to add electrical bounds (value and rating) plus package constraints. — [atopile SKILL.md](https://github.com/atopile/atopile/blob/main/.claude/skills/ato/SKILL.md)

**JITX**
- Designs, libraries, symbols and footprints are all code. JITX's solvers automate low-level work such as component selection, pin assignment and schematic drafting. Users then finish placement and routing in existing CAD. — [jitx.com](https://www.jitx.com/); [JITX FAQ](https://blog.jitx.com/jitx-corporate-blog/frequently-asked-questions)
- Parametric component families: an engineer instantiates parts from family classes, rebuilds, and then spot-checks the generated MPNs against the datasheet part-numbering scheme. This is an explicit human verification step after automated picking. — [JITX docs, JS1 Part 2 runbook (v4.4)](https://docs.jitx.com/en/4.4/jumpstart-kits/js1-stackup-components/part2-parametric-passives/JS1_Part2_Parametric-Passives_Runbook.html)

**Flux.ai Copilot**
- Copilot is described as "an AI agent with access to real tools, structured data, and your active design context," not just a text generator. Its part search is guided by company guidelines: regulatory, pricing, power, operating conditions. — [Flux Copilot: Under the Hood](https://www.flux.ai/p/blog/flux-copilot-under-the-hood); [Research Components Faster with AI](https://www.flux.ai/p/blog/research-components-faster-with-ai)
- The AI Design Review panel "doesn't just check for pass/fail criteria; it interprets the constraints of your project and cross-references them with your design, flagging issues." — [Introducing the AI Design Review Panel](https://www.flux.ai/p/blog/introducing-the-ai-design-review-tab) (date not confirmed)
- Spring 2026 update: a "self-correcting AI agent," improved AI auto-layout, sourcing-aware design with real-time pricing and availability, and templates. — [Flux blog index](https://www.flux.ai/blog)
- Flux also offers a Copilot "Knowledge Base" for engineers' own rules. — [Introducing Copilot Knowledge Base](https://www.flux.ai/p/blog/introducing-copilot-knowledge-base-for-flux-engineers)

**Celus**
- Engineers give high-level requirements or sketches. The AI produces block diagrams and architecture recommendations, selects compatible components, and runs automated checks that connections and interfaces meet requirements and design rules. A BOM layer shows price, stock and lifecycle. Partner AGS Devices validates BOMs against live inventory and suggests alternates (Dec 2025). — [BusinessWire, 2025-12-17](https://www.businesswire.com/news/home/20251217050156/en/CELUS-and-AGS-Devices-Simplify-Electronics-Design-and-Procurement-Processes); [Power Electronics News](https://www.powerelectronicsnews.com/celus-design-platform-revolutionizes-electronics-design-with-ai/)
- Vendor claim: design work cut by up to 90%. Unverified. — same sources

**Quilter (layout)**
- Quilter uses reinforcement learning trained on physics and manufacturing constraints. It generates many complete candidate layouts in parallel and ranks them by routing completion, DRC compliance and physics-rule compliance. It exports to native CAD. — [Quilter 2026 autonomous PCB guide](https://www.quilter.ai/blog/the-2026-guide-to-autonomous-pcb-design-quilter-vs-deeppcb-vs-flux-ai); [Multi-Objective Optimization in AI PCB Layout](https://www.quilter.ai/blog/multi-objective-optimization-ai-pcb-layout)
- Quilter's stated bet is that "the highest-value human work in PCB layout is deciding intent, constraints, and tradeoffs." Humans review alternatives and pick a candidate, framed as "a set of inspectable candidates with evidence attached." — [Quilter Interface post](https://www.quilter.ai/blog/the-quilter-interface-comparing-ai-driven-vs-manual-pcb-design-ui); [Hardware startups post](https://www.quilter.ai/blog/hardware-startups-ai-pcb-design) (2026)

**DeepPCB / Cadence**
- DeepPCB (InstaDeep) is a cloud RL router trained by self-play in a C++ simulator. Its own blog warns that a model may route a net in a way that "looks reasonable but violates some subtle constraint or manufacturing guideline." That is an argument for deterministic DRC after AI routing. — [DeepPCB blog](https://deeppcb.ai/reinforcement-learning-pcb-routing-explained/)
- Allegro X AI automates placement, power-plane creation, critical-signal routing and analysis. Placement AI takes into account mechanical constraints, fixed locations, height limits, assembly rules, room assignments and connectivity. — [EMA Design Automation blog](https://www.ema-eda.com/ema-resources/blog/best-ai-software-for-generative-pcb-design-emd/)

### Inferences
- Circuit OS's "LLM → IR → deterministic compiler" matches the industry pattern that works: Diode, atopile and JITX all put a typed, compilable layer between intent and output. The gaps compared with atopile/Zener are (a) toleranced constraints with explicit ranges instead of point values, and (b) a solver doing parametric part picking. Today Circuit OS lets the LLM choose part values, with a justification string.
- The "decision" objects worth recording are the ones these tools make visible: part choice with alternatives and the reason for choosing, constraint values with tolerance and source (datasheet or rule), review findings, and the human's choice among layout candidates.
- The Diode loop (propose → SPICE → see why → iterate) is essentially Circuit OS's retry loop plus simulator feedback. Circuit OS currently retries only on schema errors, not on simulation or rule failures.

### Gaps
- Could not read full vendor pages, so I found no detail on what Flux, Quilter or Celus persist as an audit log. I found no source describing per-decision logging or approval records in any of these products.
- No independent benchmarks of Quilter, DeepPCB or Celus quality claims.
- Synopsys.ai PCB/board-level decision handling was not covered.

## Q2. LLM decision-governance patterns

### Takeaway
The established patterns are:
- typed or tool-forced outputs;
- deterministic checks first, with LLM-as-judge only for things code can't check;
- binary pass/fail judgments with written critiques, not 1–5 scores;
- evaluator-optimizer loops only where the criteria are clear;
- expert pairwise preference on a golden set, plus regression evals in CI.

The EDA-specific literature shows the strongest pattern is tool feedback (simulator or testbench) driving refinement.

### Cited Findings
- Anthropic's "Building Effective Agents" (Dec 2024) describes the evaluator-optimizer workflow: one LLM call generates and another evaluates and gives feedback in a loop. It is effective "when we have clear evaluation criteria, and when iterative refinement provides measurable value." Avoid it when first-attempt quality is enough, when criteria are subjective, or when cost or latency constraints dominate. — [Anthropic](https://www.anthropic.com/research/building-effective-agents)
- Hamel Husain's "critique shadowing": a principal domain expert makes binary pass/fail calls on representative traces with detailed written critiques, and those become the LLM-judge's few-shot examples and calibration set. He argues against 1–5 scales and says generic "hallucination" judge prompts don't work: "look at your data." — [Hamel, Using LLM-as-a-Judge](https://hamel.dev/blog/posts/llm-judge/) (2024); [Evals FAQ](https://hamel.dev/blog/posts/evals-faq/)
- Husain and Shreya Shankar's course covers error analysis, code-based vs LLM-judge evaluators, evals for agents, wiring evals into CI/CD, and review interfaces. Husain has also published "evals skills" for coding agents. — [Maven course](https://maven.com/parlance-labs/evals); [Evals Skills for Coding Agents](https://hamelhusain.substack.com/p/evals-skills-for-coding-agents); [hamelsmu/evals-skills](https://github.com/hamelsmu/evals-skills/blob/main/questions.md)
- Anthropic/Diode used expert pairwise preference (8/10) as the eval for circuit reference designs. — [Claude blog](https://claude.com/blog/making-claude-a-better-electrical-engineer)
- LLM4EDA survey (Jan 2024): LLM applications in EDA fall into chatbot assistants, HDL/script generation, and verification. AutoChip and ChipNeMo show the value of EDA-tool feedback and domain customization. The LLM agent uses evaluation metrics as feedback to decide whether to refine or terminate. — [arXiv 2401.12224](https://arxiv.org/pdf/2401.12224); [ACM TODAES survey (2025)](https://dl.acm.org/doi/10.1145/3715324) / [arXiv 2501.09655](https://arxiv.org/pdf/2501.09655)
- The core idea in LLM-aided design is that "the LLM proposes actions… and the EDA tool provides ground-truth feedback." Examples: AutoChip (simulation feedback), VeriReason (testbench-outcome RL), AssertLLM (assertions from NL specs). — same surveys; [VeriCoder, arXiv 2504.15659](https://arxiv.org/pdf/2504.15659); [LLM-assisted circuit verification survey, ASP-DAC 2026](https://yuntaolu.github.io/files/Liu-2026-ASPDAC-LLMDVSurvey.pdf)

### Inferences
- For Circuit OS, deterministic graders (ir_validator, rule_engine, SPICE grader at 15%) should be the primary "judges." An LLM judge is justified only for explanation quality, where the "consequential vs descriptive" rule in code-style.md is a natural binary pass/fail criterion. Justification quality is a second candidate.
- The Phase 1 checklist item "20 prompts end-to-end" plus simulation monitor success rates is already a golden set in embryo. It can become a CI regression eval with a pass/fail per template.
- Multi-candidate generation plus deterministic ranking (the Quilter pattern) applies at the IR level too. For example, generate N candidate IRs for an ambiguous prompt, grade each via SPICE and rules, and present the top candidate with the others logged.

### Gaps
- No 2024–2026 primary source was found specifically on confidence/abstention for structured-output LLMs, or on Eugene Yan's eval posts. Not searched due to the tool budget.
- Guardrail frameworks (Guardrails AI, NeMo Guardrails) were not researched.

## Q3. Engineering-process decision patterns for small teams and solo founders, and wiring them into repos, CI and agents

### Takeaway
ADRs (Context / Decision / Consequences, in the repo) are now being generated and maintained by coding agents through skills. The main documented risk is that agents fabricate the rationale. Bezos's Type 1 / Type 2 (one-way / two-way door) framing is the standard triage for how much process a decision gets.

### Cited Findings
- The main ADR repository now ships Claude Code skills that decide whether a decision needs an ADR, set up directories, name files, pick templates, and write Context/Decision/Consequences. — [architecture-decision-record GitHub](https://github.com/architecture-decision-record/architecture-decision-record)
- ADR tooling for agents exists: [adr-agent](https://github.com/macromania/adr-agent), and Codex CLI ADR generation and governance ([Codex KB, 2026-04-28](https://codex.danielvaughan.com/2026/04/28/codex-cli-architecture-decision-records-adr-automated-governance/)). Warning from these sources: agent-generated ADRs from codebase scans "may capture decisions but can fabricate the reasoning," so Context and Consequences need human review. — same sources
- Research: RAD-AI on architecture documentation for AI-augmented systems ([arXiv 2603.28735](https://arxiv.org/pdf/2603.28735)); GADR, which gathers ADRs from meeting transcripts ([arXiv 2608.17694](https://arxiv.org/pdf/2608.17694)); design decisions in agent harnesses ([arXiv 2604.18071](https://arxiv.org/pdf/2604.18071)).
- AGENTS.md was formalized in Aug 2025 (OpenAI, Google, Cursor, Factory), donated to the Linux Foundation's Agentic AI Foundation in Dec 2025, and is reported as adopted by 60k+ projects. — via search summary of the [Codex KB ADR article](https://codex.danielvaughan.com/2026/04/28/codex-cli-architecture-decision-records-adr-automated-governance/); adoption figure not independently verified
- Bezos, 2015 shareholder letter: Type 1 (irreversible, one-way door) decisions should be made "methodically, carefully, slowly, with great deliberation and consultation." Type 2 (reversible) decisions should be made quickly by high-judgment individuals or small groups. Applying Type 1 process to Type 2 decisions causes "slowness, unthoughtful risk aversion, failure to experiment." — [Farnam Street](https://fs.blog/reversible-irreversible-decisions/); [RCM ThinkLabs](https://rcmlabs.io/blog/one-way-door-two-way-door-type-1-type-2-decisions/)

### Inferences
- The repo already makes ADR-like decisions without a formal record. For example, "PCB engine scope decision 2026-08-22 is (b) experimental" in CLAUDE.md and PHASE1_COMPLETE.md §4 is an ADR embedded in prose. A `docs/decisions/` folder, or a structured decision tool, would make these queryable.
- One-way doors in Circuit OS:
  - IR schema field names (explicitly "never rename")
  - simulator licensing (ngspice vs LTspice)
  - persistence model
  - public API shape
  - whether to integrate freerouting vs extend `pcb_engine`

  Two-way doors: prompt wording, retry count, tolerance thresholds behind config, and UI.

### Gaps
- No sources gathered on pre-mortems, weighted scoring matrices, or feature-flag experiment governance specific to AI products (budget exhausted). Nygard's original 2011 ADR post was not fetched directly.

## Q4. PCB autorouting and placement: where decisions occur and how they're parameterized

### Takeaway
Routing decisions are parameterized as:
- stackup and layer set: allowed layers and preferred direction per layer;
- net classes: trace width, clearance, via size;
- router cost weights: via cost, trace-length cost, direction penalties;
- pass selection: fanout, autoroute, post-route optimization;
- DRC severities and exclusions (waivers).

In KiCad, waivers persist as `drc_exclusions` in the project file and custom rules live in `.kicad_dru`. Every one of these is a discrete, loggable decision.

### Cited Findings
- Freerouting lets you set which layers the autorouter may use, the preferred trace direction per layer, and whether it may insert vias. A detail-parameter window exposes the individual cost weights. Optional fanout (pre) and post-route (via-count and length reduction) passes are available. — [FreeRouting manual: Routing Options](https://freerouting.org/freerouting/manual/routing-options)
- Practitioner guidance: turn on via minimization and set via cost ≥3, and limit layers to essential pairs. Set trace widths, clearances and via sizes before routing. — [Sierra Circuits (KiCad + Freerouting)](https://www.protoexpress.com/blog/how-to-autoroute-pcb-layout-in-kicad-using-freerouting-plugin/); [South Electronic](https://southelectronicpcb.com/automate-routing-in-kicad/)
- Freerouting enforces clearances, widths and via restrictions through its `BoardRules` system. An open issue asks for parsing `autoroute_settings` and `layer_rule` blocks in `.rules` files, so some settings are not yet file-configurable. — [DeepWiki](https://deepwiki.com/freerouting/freerouting); [Issue #848](https://github.com/freerouting/freerouting/issues/848)
- KiCad: excluding a DRC violation in the UI adds a key to the `drc_exclusions` array in the project file. Custom rules live in `.kicad_dru` with per-rule `severity`. Violation severities are configurable per category. UI exclusions and custom-rule text behave differently, and there are open bugs where custom exceptions show as errors in `kicad-cli` DRC (#24264) and exclusions are ignored in the Python API (#11562). — [Sierra Circuits design rules](https://www.protoexpress.com/blog/how-to-set-up-design-rules-kicad/); [KiCad #24264](https://gitlab.com/kicad/code/kicad/-/work_items/24264); [KiCad #11562](https://gitlab.com/kicad/code/kicad/-/work_items/11562)
- A third-party tool proposes a `.kct_waivers.json` schema applied to the `kicad-cli` DRC gate. This is an example of waivers as typed, versioned data in CI. — [kicad-tools #4691](https://github.com/rjwalters/kicad-tools/issues/4691)
- Fab design rules (e.g., JLCPCB) can be expressed as a `.kicad_dru` custom-rules file. — [labtroll/KiCad-DesignRules](https://github.com/labtroll/KiCad-DesignRules); [JLCPCB rules guide 2025](https://www.schemalyzer.com/en/blog/manufacturing/jlcpcb/jlcpcb-design-rules)
- Allegro X AI placement inputs: mechanical constraints, fixed parts, height limits, assembly rules, rooms, connectivity. — [EMA](https://www.ema-eda.com/ema-resources/blog/best-ai-software-for-generative-pcb-design-emd/)
- Quilter's human decisions are intent, constraints and trade-offs, followed by candidate selection. — [Quilter](https://www.quilter.ai/blog/the-quilter-interface-comparing-ai-driven-vs-manual-pcb-design-ui)

### Inferences
- If Circuit OS moves to freerouting (per the CLAUDE.md Phase 3 plan), the decision surface fits in a small typed "layout-spec" object alongside the IR:
  - layer count and stackup
  - per-net-class width, clearance and via
  - router cost profile
  - pass toggles
  - fab rule set (e.g., JLCPCB `.kicad_dru`)

  The LLM should propose this object, a validator should check it against fab minimums, and freerouting executes it. This mirrors the "One Rule."
- DRC waivers are the clearest case for a decision record: who waived which violation, why, and whether it is reversible. The kicad-tools waivers-JSON proposal is a ready model. Because of the KiCad CLI/API exclusion bugs, Circuit OS should store waivers itself rather than rely on `drc_exclusions`.
- Layer count and board fab choice are one-way doors (they drive cost and are hard to reverse after ordering). Cost weights and pass toggles are two-way doors that can be tuned automatically by running multiple candidates.

### Gaps
- Could not verify freerouting's current CLI or API parameter names for headless runs (e.g., max passes, optimizer threads) from primary docs within budget.
- No source found on how Quilter or DeepPCB expose layer count and stackup choice to the user.
