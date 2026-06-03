# /update-memory

Scan what actually changed, measure progress against the codebase, update shared-memory, and commit.

## What this command does

1. Runs `python .claude/shared-memory/tools/regen_state.py` — scans real code + real tests, writes state.json + progress.yaml
2. Checks git diff to summarise what changed since last update
3. Appends a new entry to `brain/timeline.md` describing what just happened
4. If brain files are stale (facts are wrong), updates them
5. Updates `plan/current_phase.md` if the current tasks are complete
6. Commits everything with message `brain: /update-memory — <short summary>`

## Instructions for Claude

Run the following steps in order:

### Step 1 — Regenerate derived state files

```bash
cd c:/Users/KIIT/cursor-electronics
PYTHONUTF8=1 python .claude/shared-memory/tools/regen_state.py
```

Read the Reviewer Summary output carefully. Note:
- How many tests pass/fail
- Which Phase 1 criteria are now done (may have changed since last session)
- Which modules changed status

### Step 2 — Check git diff for what changed

```bash
git log --oneline -5
git diff HEAD~1 --name-only
```

List the files that changed and what they mean (new module? bug fix? test added?).

### Step 3 — Append to brain/timeline.md

Add an entry at the bottom of `brain/timeline.md`:
```
**YYYY-MM-DD** — [What changed in code] — [Why it matters / what it unblocks]
```

Keep it to 1-2 sentences. Facts only, no summaries.

### Step 4 — Check if current_phase.md tasks are complete

Read `plan/current_phase.md`. For each task listed:
- If the task's success criterion is now met (test passes, module exists), mark it done
- If all tasks in the phase are done, the planner needs to write new tasks

If tasks are complete: update `plan/current_phase.md` to mark them done and note what's next.

### Step 5 — Update any stale brain facts

Skim `brain/knowledge.md` and `brain/decisions.md` for anything that contradicts what you just observed in the code. If a decision changed (e.g., we switched from X to Y), append a new decision entry — never delete old ones.

### Step 6 — Commit

```bash
cd c:/Users/KIIT/cursor-electronics
git add .claude/shared-memory/
git commit -m "brain: /update-memory — <one-line summary of what changed>"
```

The summary should say what actually changed: "simulation parser fixed, 42/42 tests pass" not "memory updated".

## What agents reading shared-memory will see after this

Any new session — Claude Code, Claude.ai, GPT, or human — can run the 5-step bootstrap from AGENTS.md and immediately know:
- Current test count (from state.json)
- Which modules are verified_done vs broken (from progress.yaml)
- What the next tasks are (from current_phase.md)
- What just changed and why (from timeline.md)

No conversation history needed.
