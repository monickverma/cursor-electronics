# CLAUDE.md — Circuit OS

Full instructions are in `.claude/CLAUDE.md`. Rule files are in `.claude/rules/`.

---

## The One Rule

> The LLM never writes SPICE, KiCad format, or Arduino firmware directly.
> It writes JSON against the IR schema. Deterministic compilers translate that JSON.

---

## Quick Reference

| Rule file | Covers |
|---|---|
| `.claude/CLAUDE.md` | Project overview, structure, tech stack, Phase 1 scope, commands |
| `.claude/rules/code-style.md` | IR schema fields, AI tool_use pattern, retry loop, Pydantic v2, common mistakes |
| `.claude/rules/testing.md` | Test structure, commands, accuracy gate, Phase 1 launch checklist |
| `.claude/rules/security.md` | Env vars, CORS, rate limits, auth, no in-memory storage, no live BOM API |
| `.claude/rules/simulation.md` | SPICE rules, ngspice columnar format, MCU model, pipeline, validation rules |
| `.claude/rules/frontend/react-style.md` | kicanvas ssr:false, Next.js proxy, component responsibilities, design tokens |

---

## Critical Rules — Never Violate

1. **LLM output → JSON → IR schema → compilers.** Never LLM → ngspice/KiCad/.ino directly.
2. **ngspice always via Celery.** Never inline in HTTP handler. Narrowed 2026-09-20 to ngspice specifically — `predict()` (closed-form, microseconds) is synchronous by design. See `.claude/rules/simulation.md`.
3. **MCU SPICE model = 100Ω resistor.** Never voltage source — causes ngspice singular matrix.
4. **ngspice batch output is columnar.** Regex `v(x) = y` does not match it.
5. **kicanvas = `dynamic import` with `ssr: false`.** Never SSR this component.
6. **All designs persist to PostgreSQL.** No `design_store = {}`.
7. **CORS middleware before any route.** FastAPI port 8000 ≠ Next.js port 3000.
8. **Phase 1 BOM is static.** No Digikey/LCSC live API calls until Phase 2.
