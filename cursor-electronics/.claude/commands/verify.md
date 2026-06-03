---
Cold-boot verification. Pretend you are a BRAND NEW agent with zero conversation history.
Read ONLY from files. Do not use anything from this conversation.

Read in order:
1. .claude/shared-memory/AGENTS.md
2. .claude/shared-memory/brain/vision.md
3. .claude/shared-memory/brain/architecture.md
4. .claude/shared-memory/brain/decisions.md
5. .claude/shared-memory/plan/current_phase.md
6. .claude/shared-memory/state.json
7. .claude/shared-memory/progress.yaml
8. Run: git log --oneline -5

Then answer every question below FROM THE FILES ONLY. Do not guess.

Q1. What is this project? What problem does it solve?
Q2. Why was it built? What was the personal motivation?
Q3. What is the tech stack and why was it chosen?
Q4. What has been built and is verified working right now?
Q5. What is currently broken or blocked?
Q6. What are the next 3 specific tasks?
Q7. What key decisions were made and why?

After answering, grade each answer:
ANSWERED FROM FILES ✓   — the files had enough to answer it
MISSING FROM FILES ✗    — the files did not cover this — state which file needs updating

Then print this shareable block (any LLM can use this to continue the project):

========================================
PROJECT MEMORY SNAPSHOT
Project: [name]
Generated: [date] from commit [hash]

PURPOSE: [one line]
BUILT BECAUSE: [one line — the personal why]
STACK: [one line]
STATUS: Phase [N] — [X]% done — [X] tests passing
WORKING: [list of verified functions or modules]
BROKEN: [list or "none"]
BLOCKED: [list or "none"]
NEXT 3 TASKS: [list]
========================================

Final verdict:
SHARED MEMORY: WORKING ✓    if all 7 questions scored ANSWERED FROM FILES
SHARED MEMORY: INCOMPLETE ✗  list which files need updating
---
