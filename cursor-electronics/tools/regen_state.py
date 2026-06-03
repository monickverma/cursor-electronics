#!/usr/bin/env python3
"""
regen_state.py — Generates state.json from reality (high-level summary).

Also invokes progress_gen.py to update the function-level progress.yaml.

This is the script you run at end of every session:
    python tools/regen_state.py

What it does:
  1. Checks which source files exist
  2. Runs the test suite, captures pass/fail counts
  3. Reads recent git history
  4. Computes overall completion %
  5. Writes state.json
  6. Invokes progress_gen.py to also update progress.yaml
  7. Prints a reviewer summary (paste-friendly)
"""

import io
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 stdout so emoji print correctly on Windows (cp1252 terminals)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
elif hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── Config ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent

EXPECTED_MODULES = {
    # Phase 1 — Hardware Copilot (5 templates, MVP)
    "api_entry":         {"file": "backend/main.py",                         "phase": 1},
    "ir_schema":         {"file": "backend/core/ir_schema.py",               "phase": 1},
    "intent_parser":     {"file": "backend/ai/intent_parser.py",             "phase": 1},
    "circuit_reasoner":  {"file": "backend/ai/circuit_reasoner.py",          "phase": 1},
    "patcher":           {"file": "backend/ai/patcher.py",                   "phase": 1},
    "explainer":         {"file": "backend/ai/explainer.py",                 "phase": 1},
    "spice_generator":   {"file": "backend/generators/netlist/spice.py",     "phase": 1},
    "firmware_gen":      {"file": "backend/generators/firmware/arduino.py",  "phase": 1},
    "kicad_gen":         {"file": "backend/generators/schematic/kicad.py",   "phase": 1},
    "bom_compiler":      {"file": "backend/generators/bom/compiler.py",      "phase": 1},
    "simulation_runner": {"file": "backend/simulation/runner.py",            "phase": 1},
    "rule_engine":       {"file": "backend/validation/rule_engine.py",       "phase": 1},
    # Phase 2 — Validation Engine
    "frontend_app":      {"file": "frontend/app/page.tsx",                   "phase": 2},
    # Phase 3 — Industrial Layer
    "pcb_layout":        {"file": "backend/generators/pcb/layout.py",        "phase": 3},
}
TOTAL_PHASES = 5
CURRENT_PHASE = 1  # Update manually when a phase completes.


# ── Helpers ───────────────────────────────────────────────────────────────────
def run(cmd, cwd=None, timeout=60):
    try:
        r = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except FileNotFoundError:
        return -1, "", f"NOT FOUND: {cmd[0]}"


def get_git_commit():
    code, out, _ = run(["git", "rev-parse", "--short", "HEAD"])
    return out.strip() if code == 0 else "unknown"


def get_git_log(n=5):
    code, out, _ = run(["git", "log", f"-{n}", "--oneline"])
    return [line.strip() for line in out.strip().splitlines()] if code == 0 else []


def run_tests():
    code, out, err = run(
        ["python", "-m", "pytest", "tests/", "--tb=no", "-q"], timeout=120
    )
    result = {"passed": 0, "failed": 0, "total": 0}
    if code == -1:
        print("  ⚠ pytest not available or timed out")
        return result
    text = out + err
    p = re.search(r"(\d+) passed", text)
    f = re.search(r"(\d+) failed", text)
    if p: result["passed"] = int(p.group(1))
    if f: result["failed"] = int(f.group(1))
    result["total"] = result["passed"] + result["failed"]
    icon = "✅" if result["failed"] == 0 else "❌"
    print(f"  {icon} Tests: {result['passed']} passed, {result['failed']} failed")
    return result


def check_modules():
    modules = {}
    for name, cfg in EXPECTED_MODULES.items():
        path = ROOT / cfg["file"]
        exists = path.exists()
        modules[name] = {
            "status": "not_started" if not exists else "exists",
            "file": cfg["file"],
            "exists": exists,
            "phase": cfg["phase"],
        }
        icon = "✅" if exists else "⬜"
        print(f"  {icon} {name}: {'found' if exists else 'missing'} ({cfg['file']})")
    return modules


def read_blockers():
    """Extract blockers from plan/current_phase.md table."""
    blockers = []
    phase_file = ROOT / "plan" / "current_phase.md"
    if not phase_file.exists():
        return blockers
    in_blockers = False
    for line in phase_file.read_text().splitlines():
        if "Current Blockers" in line or "## Blockers" in line:
            in_blockers = True
            continue
        if in_blockers and line.startswith("##"):
            break
        if in_blockers and line.startswith("|") and "---" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if parts and parts[0] not in ("Blocker", ":"):
                blockers.append(parts[0])
    return blockers


def run_progress_gen():
    script = ROOT / "tools" / "progress_gen.py"
    if not script.exists():
        print("  ⚠ tools/progress_gen.py not found — skipping function-level")
        return
    code, out, err = run(["python", str(script)])
    if code != 0:
        print(f"  ⚠ progress_gen failed: {(err or out)[:200]}")
    else:
        # Print the script's summary line
        for line in out.splitlines():
            if "Summary:" in line or "verified done" in line:
                print(f"  {line.strip()}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n🔄 Regenerating state.json from reality...\n")

    print("📦 Checking modules:")
    modules = check_modules()

    print("\n🧪 Running tests:")
    tests = run_tests()

    print("\n📜 Reading git:")
    commit = get_git_commit()
    log = get_git_log(5)
    print(f"  HEAD: {commit}")

    blockers = read_blockers()

    # Determine phase status from current-phase module statuses
    cur_modules = [m for m in modules.values() if m["phase"] == CURRENT_PHASE]
    if all(m["exists"] for m in cur_modules) and tests["failed"] == 0:
        phase_status = "done"
    elif any(m["exists"] for m in cur_modules):
        phase_status = "in_progress"
    else:
        phase_status = "not_started"

    # Crude completion %
    phases_done = max(0, CURRENT_PHASE - 1) if phase_status == "in_progress" else 0
    pct = round((phases_done / TOTAL_PHASES) * 100, 1)

    state = {
        "_note": "DERIVED file. Do not edit by hand. Run: python tools/regen_state.py",
        "_layer": "LAYER 4 (Progress) — module-level summary",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_from_commit": commit,
        "project": "Circuit OS",
        "phase": {
            "current": CURRENT_PHASE,
            "name": "Hardware Copilot",
            "status": phase_status,
        },
        "modules": modules,
        "test_summary": tests,
        "blockers": blockers,
        "completion": {
            "phases_done": phases_done,
            "phases_total": TOTAL_PHASES,
            "pct_overall": pct,
        },
        "recent_commits": log,
        "pointers": {
            "see_function_level": "progress.yaml",
            "see_current_tasks": "plan/current_phase.md",
            "see_full_roadmap": "plan/master_plan.md",
        },
    }

    (ROOT / "state.json").write_text(json.dumps(state, indent=2))

    # Also regenerate progress.yaml
    print("\n📋 Updating function-level progress.yaml...")
    run_progress_gen()

    # Reviewer summary — paste-friendly
    print("\n" + "─" * 64)
    print("REVIEWER SUMMARY  (paste into any new session)")
    print("─" * 64)
    print(f"  Project : Circuit OS")
    print(f"  Phase   : {CURRENT_PHASE} — {phase_status}")
    print(f"  Commit  : {commit}")
    print(f"  Tests   : {tests['passed']} passing / {tests['failed']} failing")
    print(f"  Overall : {pct}%")
    if blockers:
        print(f"  Blocked : {len(blockers)} blocker(s)")
        for b in blockers:
            print(f"            • {b}")
    print(f"  Read    : AGENTS.md → progress.yaml → plan/current_phase.md")
    print("─" * 64 + "\n")


if __name__ == "__main__":
    main()
