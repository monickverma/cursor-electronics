# SETUP.md — How to share memory between Claude Code and Claude.ai

## What shared-memory is

A set of plain markdown + YAML + JSON files in this repo that any agent reads
to get full project context in under 2 minutes — without needing the conversation history.

Any session (Claude Code, Claude.ai, GPT-4, a new developer) runs the same
5-step bootstrap from `AGENTS.md` and immediately knows:
- What the project is and why it exists (brain/vision.md)
- How it works — every module, every data flow (brain/architecture.md)
- What's actually done — from test results, not from claims (progress.yaml)
- What the exact next tasks are (plan/current_phase.md)
- What decisions were made and why (brain/decisions.md)

---

## Option 1 — Push to GitHub, Claude.ai reads via web_fetch (RECOMMENDED)

This is the best option. Claude.ai always reads the live files — no paste needed.
After every `/update-memory` + `git push`, Claude.ai sees the updated state.

### Step 1 — Create repo on GitHub
```
github.com → New repository → circuit-os → private → Create
```

### Step 2 — Add remote and push
```bash
cd c:/Users/KIIT/cursor-electronics
git remote add origin https://github.com/YOUR_USERNAME/circuit-os.git
git push -u origin master
```

### Step 3 — Get the raw URLs for the brain files

The raw URL format is:
```
https://raw.githubusercontent.com/YOUR_USERNAME/circuit-os/master/.claude/shared-memory/AGENTS.md
```

Key URLs to bookmark:
```
AGENTS.md        → https://raw.githubusercontent.com/YOUR_USERNAME/circuit-os/master/.claude/shared-memory/AGENTS.md
state.json       → https://raw.githubusercontent.com/YOUR_USERNAME/circuit-os/master/.claude/shared-memory/state.json
progress.yaml    → https://raw.githubusercontent.com/YOUR_USERNAME/circuit-os/master/.claude/shared-memory/progress.yaml
current_phase.md → https://raw.githubusercontent.com/YOUR_USERNAME/circuit-os/master/.claude/shared-memory/plan/current_phase.md
```

### Step 4 — Start Claude.ai with this prompt

```
Read https://raw.githubusercontent.com/YOUR_USERNAME/circuit-os/master/.claude/shared-memory/AGENTS.md
Then follow the 5-step bootstrap exactly as instructed.
After reading, tell me where the project is and what the next task is.
```

Claude.ai uses web_fetch to pull the latest committed files automatically.

---

## Option 2 — Manual paste via snapshot.py (no GitHub needed)

```bash
cd c:/Users/KIIT/cursor-electronics
PYTHONUTF8=1 python .claude/shared-memory/tools/snapshot.py > snapshot.md
# Full version including decisions/knowledge/timeline:
PYTHONUTF8=1 python .claude/shared-memory/tools/snapshot.py --full > snapshot_full.md
```

Paste the contents of `snapshot.md` into Claude.ai as the first message.
Claude.ai gets the same context as Claude Code.

---

## Keeping memory fresh — the /update-memory loop

### In Claude Code, after any code change:
```
/update-memory
```

This command:
1. Runs `regen_state.py` — scans real tests + real code, no hallucination
2. Updates `state.json` + `progress.yaml` with actual test results
3. Appends to `brain/timeline.md`
4. Commits all changes

### Then push (if using GitHub):
```bash
git push
```

Claude.ai now sees the fresh state on its next web_fetch call.

---

## How a new Claude.ai session cold-starts

**Start message:**
```
Read these four files using web_fetch:
1. https://raw.githubusercontent.com/YOUR_USERNAME/circuit-os/master/.claude/shared-memory/AGENTS.md
2. https://raw.githubusercontent.com/YOUR_USERNAME/circuit-os/master/.claude/shared-memory/brain/vision.md
3. https://raw.githubusercontent.com/YOUR_USERNAME/circuit-os/master/.claude/shared-memory/plan/current_phase.md
4. https://raw.githubusercontent.com/YOUR_USERNAME/circuit-os/master/.claude/shared-memory/state.json

After reading, tell me: what is this project, what is done, and what is the next task?
Do not ask me to explain anything — everything you need is in those files.
```

Claude.ai will read 4 files, then know:
- This is Circuit OS, an AI hardware compiler
- 257 tests pass, 10/12 Phase 1 criteria done (as of 2026-08-07)
- Next tasks: RC filter bench test + external engineer review
- All key decisions, architecture, and known pitfalls

---

## How Claude Code uses it automatically

`.claude/shared-memory/CLAUDE.md` is loaded by Claude Code at session start.
It says: "Read AGENTS.md immediately and follow the bootstrap instructions."
This happens automatically — no action needed.

---

## Why this works (the trust chain)

```
pytest tests/  →  actual pass/fail
    ↓
regen_state.py reads test output
    ↓
progress.yaml: NgspiceRunner.run = verified_done (test PASSES) not "I think it's done"
    ↓
state.json: summary counts from progress.yaml
    ↓
Any agent reads state.json → knows exactly what's real
```

No agent can claim "it's done" and have shared-memory believe it. Only passing tests
update progress.yaml. This eliminates the worker/planner gap you described:
the worker can't lie to the planner because the state is derived from reality.

---

## The /update-memory workflow in practice

```
You write code in Claude Code
    → tests pass
    → /update-memory
    → state.json + progress.yaml update from real results
    → brain/timeline.md gets a new entry
    → git commit created
    → git push (you do this)
    → Claude.ai reads fresh state on next session
    → Any new Claude Code session reads fresh state automatically
```

The loop is: **code → test → /update-memory → push → any agent continues**.
No context window carries over. No re-explanation needed.
