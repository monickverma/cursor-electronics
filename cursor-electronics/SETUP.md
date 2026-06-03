# Setup — Step by Step

> Goal: get to a working two-agent loop in 15 minutes.

---

## Step 1 — Drop the template into your project folder

```bash
unzip ai-engineer-template.zip
cd ai-engineer-template
```

If you're starting a new project, rename the folder. If you're adding to an existing
project, copy `AGENTS.md`, `CLAUDE.md`, `brain/`, `plan/`, `tools/`, `state.json`,
`progress.yaml`, and `README.md` into your existing root.

---

## Step 2 — Initialize git (required — git diff is part of ground truth)

```bash
git init
git add -A
git commit -m "init: project brain scaffolded"
```

---

## Step 3 — Customize the brain (the manual layers)

Open and edit these four files with your actual project:

| File | What to fill in |
|------|-----------------|
| `brain/vision.md` | Your project name, purpose, end goal, success criteria, who uses it |
| `brain/architecture.md` | Your modules, data formats, how they connect |
| `plan/master_plan.md` | Your phases — could be 0–12 like the template, or any structure |
| `tools/progress_gen.py` | Update `PLANNED_FUNCTIONS` dict at the top with YOUR function names |

`brain/decisions.md`, `brain/knowledge.md`, `brain/timeline.md` start mostly empty and
fill up as you work. Don't pre-populate them.

---

## Step 4 — Install Python dependencies (for the tools/ scripts)

```bash
pip install pyyaml pytest
```

That's it for dependencies. Everything else is stdlib.

---

## Step 5 — Verify the loop works (smoke test)

```bash
python tools/regen_state.py
```

You should see:
```
🔄 Regenerating state.json from reality...
📦 Checking modules: ...
🧪 Running tests: ...
✅ state.json written
📋 Generating function-level progress...
✅ progress.yaml updated
```

Both `state.json` and `progress.yaml` should now reflect your actual repo (empty if
you haven't written code yet — that's fine, that's the truth).

---

## Step 6 — Pick how Claude.ai and Claude Code share memory

You need **both** agents reading the same files. Four options — pick one:

### Option A: Manual paste (zero setup, works immediately)

```bash
python tools/snapshot.py
# This copies state.json + progress.yaml + current_phase.md + key brain/ files
# to your clipboard, formatted for pasting.
```

Then start a Claude.ai chat and paste. Claude is now fully oriented.

**Best for:** quick iteration, when you don't want to set up sync.

---

### Option B: GitHub + web_fetch (always-fresh, remote-friendly)

1. Push your repo to GitHub (private is fine if you have a token, or use public)

   ```bash
   git remote add origin https://github.com/yourname/your-project.git
   git push -u origin main
   ```

2. In Claude.ai, start a chat with this exact prompt:

   ```
   Use web_fetch to read these files from my project, in order:
   - https://raw.githubusercontent.com/yourname/your-project/main/AGENTS.md
   - https://raw.githubusercontent.com/yourname/your-project/main/state.json
   - https://raw.githubusercontent.com/yourname/your-project/main/progress.yaml
   - https://raw.githubusercontent.com/yourname/your-project/main/plan/current_phase.md

   Then follow the bootstrap instructions in AGENTS.md.
   ```

Claude.ai will fetch and orient itself. Every push from Claude Code is immediately
visible to Claude.ai with no manual sync.

**Best for:** day-to-day work, when you want the chat side always up to date.

---

### Option C: Google Drive sync (seamless if you use Drive)

1. Install Google Drive desktop client. Put your project folder inside the Drive
   sync directory (or move the project there).
2. In Claude.ai, confirm the **Google Drive connector is connected** (Settings →
   Connectors → Google Drive).
3. At session start in Claude.ai:

   ```
   Read these files from my Google Drive in the folder "your-project":
   AGENTS.md, state.json, progress.yaml, plan/current_phase.md
   ```

Claude.ai reads them through the Google Drive MCP — no pasting, no pushing.

**Best for:** if you already use Drive and want zero friction.

---

### Option D: Claude Code as both planner and worker (most automated)

Skip Claude.ai entirely. Inside Claude Code, create two slash commands:

`.claude/commands/plan.md`:
```markdown
Read plan/master_plan.md, plan/current_phase.md, state.json, and progress.yaml.
Then run `git log --oneline -10`.

Based on what's verified_done, broken, and not_started in progress.yaml,
decide the next 3 tasks at function level (specify exact functions + files).
Write the updated task list into plan/current_phase.md.
Do not write any prose summary outside that file.
```

`.claude/commands/work.md`:
```markdown
Read plan/current_phase.md to get your tasks. Execute them: write code, run tests,
fix errors. When done, run `python tools/regen_state.py` and commit.
Do not write a status summary — let the script update state.json and progress.yaml.
```

Then use `/plan` and `/work` in Claude Code.

**Best for:** maximum automation, single-tool workflow.

---

## Step 7 — Start the loop

First session:
```
1. Tell Claude (via your chosen option) to read AGENTS.md and follow it
2. It will read brain/vision.md, architecture.md, current_phase.md, progress.yaml
3. It now knows your project
4. Give it a task or ask it to plan
```

End every session:
```bash
python tools/regen_state.py
git add -A
git commit -m "session: <brief description>"
git push   # if using Option B
```

The next session — any agent, any model — picks up from where you left off.

---

## Troubleshooting

**`progress.yaml` shows everything as `not_started` even though I have code:**
Open `tools/progress_gen.py`, scroll to `PLANNED_FUNCTIONS`, and add your actual
function names + file paths. The generator only tracks functions you tell it about.

**`pytest: command not found`:**
`pip install pytest`. Or remove the test-running section in `regen_state.py` if you
don't use pytest.

**Claude.ai can't access GitHub repo:**
Make the repo public, OR use Option A (manual paste) / Option C (Drive) instead.

**State drifts from reality:**
That's the whole point of `regen_state.py` — re-run it. State should never be
hand-edited. If it ever drifts, run the regen and the source of truth wins.
