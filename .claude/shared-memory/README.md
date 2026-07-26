# AI Electronics Engineer — Project Brain

A multi-agent project memory system. Any session, any agent (Claude.ai, Claude Code,
GPT, Gemini) reads a handful of files and continues without context loss.

---

## The Six Layers (your original framing → mapped to files)

| # | Layer | File(s) | How it's written | Read by |
|---|-------|---------|------------------|---------|
| 1 | **Vision** — what / why / end goal | `brain/vision.md` | Manual, rarely changes | Every session |
| 2 | **Architecture** — modules + data flow | `brain/architecture.md` | Manual, occasional updates | Every session |
| 3 | **Decisions** — why each choice was made | `brain/decisions.md` | Manual, append-only | When in doubt |
| 4 | **Progress** — what is actually done | `state.json` + `progress.yaml` | **DERIVED** (auto) | Every session |
| 5 | **Knowledge** — domain facts learned | `brain/knowledge.md` | Manual, append-only | When relevant |
| 6 | **Artifacts** — the actual code + history | `src/` `tests/` `sims/` + `brain/timeline.md` | Worker (code) + manual (timeline) | When inspecting |

---

## The three "where are we" files — and why each exists

This is the part people get wrong: they pick one. You need all three at different zoom levels.

| File | Question it answers | Zoom level | Update frequency |
|------|--------------------|------------|------------------|
| `plan/master_plan.md` | Where are we going? | Strategic — phases 0→12 | Rarely (once per phase change) |
| `plan/current_phase.md` | What am I doing this session? | Tactical — next 3 tasks | Per planning round |
| `state.json` | What's the overall status? | Module-level — quick snapshot | Auto, every session |
| `progress.yaml` | What's actually built at function level? | Function-level — audited reality | Auto, every session |

`master_plan.md` and `current_phase.md` are **set by the planner** (intent).
`state.json` and `progress.yaml` are **derived from reality** (truth).

When they disagree, reality wins. Planner's job is to close the gap.

---

## Full file tree

```
ai-engineer-template/
├── README.md                ← you are here
├── SETUP.md                 ← step-by-step first-time setup
├── AGENTS.md                ← bootstrap loaded by every agent
├── CLAUDE.md                ← pointer to AGENTS.md (Claude Code auto-loads this)
│
├── state.json               ← LAYER 4: high-level derived state
├── progress.yaml            ← LAYER 4: function-level derived state
│
├── brain/                   ← LAYERS 1, 2, 3, 5 — manual knowledge
│   ├── vision.md            ← LAYER 1
│   ├── architecture.md      ← LAYER 2
│   ├── decisions.md         ← LAYER 3 (append-only)
│   ├── knowledge.md         ← LAYER 5 (append-only)
│   └── timeline.md          ← LAYER 6 history (append-only)
│
├── plan/                    ← planner's working files
│   ├── master_plan.md       ← strategic roadmap (phases 0–12)
│   └── current_phase.md     ← tactical task board (next 3 tasks)
│
├── src/                     ← LAYER 6: production code
├── tests/                   ← LAYER 6: test suite
├── sims/                    ← LAYER 6: SPICE netlists + simulation outputs
│
└── tools/
    ├── regen_state.py       ← derives state.json from reality
    ├── progress_gen.py      ← derives progress.yaml from reality (function-level)
    └── snapshot.py          ← bundles bootstrap files for pasting into Claude.ai
```

---

## How Claude.ai and Claude Code share the same memory

This was your original concern. Four ways, pick one:

| Option | How it works | Best for |
|--------|--------------|----------|
| **A. Manual paste** | Run `python tools/snapshot.py` → copies key files to clipboard → paste into Claude.ai | Quick start, no setup |
| **B. GitHub + web_fetch** | Push repo to GitHub → tell Claude.ai to `web_fetch` raw URLs of state.json / progress.yaml | Always-fresh, remote work |
| **C. Google Drive sync** | Sync project folder to Google Drive → Claude.ai's Google Drive connector reads files directly | Seamless if you already use Drive |
| **D. Claude Code as both** | Use `/plan` and `/work` slash commands inside Claude Code — skip Claude.ai entirely | Most automated |

All four work because the memory is plain markdown + JSON + YAML — model-agnostic, tool-agnostic. See `SETUP.md` for the exact steps.

---

## The loop (no reports, ever)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  PLANNER (Claude.ai chat OR Claude Code /plan)                          │
│     reads:  master_plan + current_phase + state.json + progress.yaml    │
│     writes: next 3 tasks → current_phase.md                             │
│                                                                         │
│                            │                                            │
│                            ▼                                            │
│                                                                         │
│  WORKER (Claude Code)                                                   │
│     reads:  current_phase.md (exact tasks)                              │
│     does:   write code, run tests, fix errors                           │
│     runs:   python tools/regen_state.py                                 │
│             └─→ regenerates state.json AND progress.yaml from reality   │
│     commits: git commit                                                 │
│                                                                         │
│                            │                                            │
│                            ▼                                            │
│                                                                         │
│  GROUND TRUTH (the only thing trusted)                                  │
│     • Test results (pytest pass/fail per function)                      │
│     • Source files (existence, function bodies via ast)                 │
│     • Git history                                                       │
│     • Simulation outputs                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

No agent ever writes "I completed X" in prose. The script reads reality.
