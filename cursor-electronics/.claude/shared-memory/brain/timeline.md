# Timeline — Circuit OS

> Append-only. One line per significant event. Answers: "how did we get here?"
> Format: **YYYY-MM-DD** — [what was built] — [why it matters]

---

## History

**2025-09-20** — Initial commit `bb45f4d` — Full Circuit OS backend scaffolded in one push: FastAPI + Celery entry points (`main.py`, `worker.py`); complete AI layer (`intent_parser.py`, `circuit_reasoner.py`, `patcher.py`, `explainer.py`); all 4 deterministic compilers (SPICE netlist, Arduino firmware with 4 Jinja2 templates, KiCad schematic, BOM); full simulation pipeline (`runner.py`, `parser.py`, `grader.py`, `monitor.py`); hardware rule engine; PostgreSQL models + CRUD + `schema.sql`; JWT auth; CORS; slowapi rate limiting; IR schema + validator + 5 example circuits; Next.js 14 frontend with ChatPanel, SchematicViewer (kicanvas), SimulationResults, BOMTable, ValidationReport, FirmwareViewer, typed API client; 177 tests passing, 24 skipped (live API + ngspice + arduino-cli auto-skipped when not available).

**2026-06-03** — Commits `88dc473`, `eb06def`, `085b449` — Project brain scaffold integrated from `ai-engineer-template-final.zip`. brain/, plan/, tools/ (regen_state.py, progress_gen.py, snapshot.py) added. CLAUDE.md updated with AGENTS.md bootstrap line. UTF-8 encoding fixes applied to both tool scripts for Windows cp1252 terminals (`sys.stdout.reconfigure`, `encoding="utf-8"` on all file writes, `-X utf8` flag for subprocess calls). `.cargo/` added to root `.gitignore` to suppress LF→CRLF warnings from Rust registry files in home-directory git repo.

**2026-06-03** — Commit `f9ff270` — All scaffold files moved from project root into `.claude/shared-memory/` to co-locate Claude tooling with other `.claude/` config. Both tool scripts updated: `SHARED_MEMORY = Path(__file__).parent.parent`, `ROOT = SHARED_MEMORY.parent.parent`. All brain/ and plan/ files rewritten from PRODUCT_MASTER.md with real Circuit OS content.

---

## TEMPLATE — adding an entry

```
**YYYY-MM-DD** — [Concrete change] — [Why it matters / outcome]
```

One to two sentences. Facts, not summaries. Append only, never edit past entries.
