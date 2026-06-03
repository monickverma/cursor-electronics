# Timeline — Circuit OS

> Append-only. One line per significant event. Answers: "how did we get here?"

---

## Format
`**YYYY-MM-DD** — [What changed] — [Outcome / why it matters]`

---

## History

**2025-09-20** — Initial commit (`bb45f4d`). Full Circuit OS backend scaffolded in one push: FastAPI entry, Celery worker, all AI modules (IntentParser, CircuitReasoner, Patcher, Explainer), all generators (SPICE, firmware, KiCad, BOM), simulation pipeline (runner, parser, grader, monitor), validation rule engine, PostgreSQL models, JWT auth, CORS, rate limiting, Jinja2 firmware templates. Frontend: Next.js 14 with ChatPanel, SchematicViewer, SimulationResults, BOMTable, ValidationReport, FirmwareViewer. Test suite: 177 passing, 24 skipped (skipped = live API + ngspice + arduino-cli).

**2026-06-03** — Brain scaffold integrated. Template from `ai-engineer-template-final.zip` merged into project root. brain/, plan/, tools/ all in place. regen_state.py and progress_gen.py customized for Circuit OS (12 backend modules tracked, real function names in PLANNED_FUNCTIONS). UTF-8 encoding fixes applied to both tool scripts (Windows cp1252 issue). `.cargo/` added to root `.gitignore` to suppress LF→CRLF warnings from Rust registry files.

**2026-06-03** — All brain/ files rewritten for Circuit OS from PRODUCT_MASTER.md. brain/vision.md, brain/architecture.md, plan/master_plan.md, plan/current_phase.md reflect real project (5-phase roadmap, actual module map, real launch gate checklist). brain/decisions.md captures 9 architectural decisions with rationale. brain/knowledge.md has ngspice invariants, IR schema rules, hardware formulas, and Claude API patterns. CLAUDE.md updated to boot-strap agents via AGENTS.md.

---

## TEMPLATE — adding an entry

```
**YYYY-MM-DD** — [Concrete change] — [Outcome]
```

Keep entries to 1–2 sentences. Record facts, not summaries.
