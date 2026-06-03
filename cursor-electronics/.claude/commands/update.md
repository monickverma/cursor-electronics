---
Run a full brain update. Execute every step:

1. Run: python .claude/shared-memory/tools/regen_state.py
   This updates state.json and progress.yaml from reality.

2. Run: git log --oneline -10
   Open brain/timeline.md. Append any commits not already recorded.
   Format: **YYYY-MM-DD** — [what changed] — [why it matters]

3. Read progress.yaml and plan/current_phase.md together.
   Update task checkboxes in current_phase.md to match reality:
   - verified_done in progress.yaml → ✅ in task list
   - broken → ❌ with a one-line note on why
   - If all tasks for current phase are verified_done → update master_plan.md phase status to DONE
     and write the next phase tasks into current_phase.md

4. Run:
   git add .claude/shared-memory/brain/ .claude/shared-memory/plan/ .claude/shared-memory/state.json .claude/shared-memory/progress.yaml
   git commit -m "brain: sync after session"

5. Print this summary:
   ✅ Brain synced — [date]
   Phase: [current phase] — [status]
   Tests: [X passing / Y failing]
   Blockers: [list or "none"]
   Next tasks: [top 3 from current_phase.md]
---
