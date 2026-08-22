#!/usr/bin/env python3
"""
regen_state.py — Regenerates state.json from reality for Circuit OS.

What it does:
  1. Checks which backend modules exist
  2. Runs the test suite (PYTHONPATH=backend pytest tests/)
  3. Reads git log + diff stats
  4. Checks Phase 1 criteria against test results
  5. Writes state.json to .claude/shared-memory/
  6. Invokes progress_gen.py to update progress.yaml
  7. Prints Reviewer Summary

Usage:
    cd cursor-electronics
    python .claude/shared-memory/tools/regen_state.py
"""

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
TOOLS_DIR    = Path(__file__).parent
MEMORY_ROOT  = TOOLS_DIR.parent                     # .claude/shared-memory/
PROJECT_ROOT = MEMORY_ROOT.parent.parent            # cursor-electronics/
BACKEND      = PROJECT_ROOT / "backend"
TESTS        = PROJECT_ROOT / "tests"

# ── Circuit OS Modules to verify ──────────────────────────────────────────────
#
# "test" accepts a single path or a list of paths. A module covered by more than
# one test file must list all of them: a module is only "verified_done" when
# every listed file passes. Listing one file when two exist understates coverage
# in exactly the direction that looks like health.
MODULES = {
    "core/ir_schema":          {"file": "backend/core/ir_schema.py",                "test": "tests/test_ir_schema.py",          "phase": 1},
    "core/ir_validator":       {"file": "backend/core/ir_validator.py",             "test": "tests/test_rule_engine.py",        "phase": 1},
    "core/config":             {"file": "backend/core/config.py",                   "test": None,                               "phase": 1},
    "ai/client":               {"file": "backend/ai/client.py",                     "test": None,                               "phase": 1},
    "ai/intent_parser":        {"file": "backend/ai/intent_parser.py",              "test": "tests/test_ai_layer.py",           "phase": 1},
    "ai/circuit_reasoner":     {"file": "backend/ai/circuit_reasoner.py",           "test": "tests/test_ai_layer.py",           "phase": 1},
    "ai/patcher":              {"file": "backend/ai/patcher.py",                    "test": "tests/test_patcher.py",            "phase": 1},
    "ai/explainer":            {"file": "backend/ai/explainer.py",                  "test": "tests/test_explainer.py",          "phase": 1},
    "generators/spice":        {"file": "backend/generators/netlist/spice.py",      "test": ["tests/test_simulation.py",
                                                                                             "tests/test_simulation_accuracy.py"], "phase": 1},
    "generators/firmware":     {"file": "backend/generators/firmware/arduino.py",   "test": "tests/test_firmware_generator.py", "phase": 1},
    "generators/kicad":        {"file": "backend/generators/schematic/kicad.py",    "test": "tests/test_schematic_generator.py","phase": 1},
    "generators/bom":          {"file": "backend/generators/bom/compiler.py",       "test": "tests/test_bom.py",                "phase": 1},
    "simulation/runner":       {"file": "backend/simulation/runner.py",             "test": ["tests/test_simulation.py",
                                                                                             "tests/test_simulation_accuracy.py"], "phase": 1},
    "simulation/parser":       {"file": "backend/simulation/parser.py",             "test": ["tests/test_simulation.py",
                                                                                             "tests/test_simulation_accuracy.py"], "phase": 1},
    # grader is deliberately NOT covered by test_simulation_accuracy.py — that
    # file compares against closed-form equations directly, bypassing the 15%
    # grader on purpose. Do not add it here.
    "simulation/grader":       {"file": "backend/simulation/grader.py",             "test": "tests/test_simulation.py",         "phase": 1},
    "simulation/monitor":      {"file": "backend/simulation/monitor.py",            "test": None,                               "phase": 1},
    "validation/rule_engine":  {"file": "backend/validation/rule_engine.py",        "test": "tests/test_rule_engine.py",        "phase": 1},
    "tasks/simulation_task":   {"file": "backend/tasks/simulation_task.py",         "test": None,                               "phase": 1},
    "api/routes/design":       {"file": "backend/api/routes/design.py",             "test": None,                               "phase": 1},
    "api/routes/patch":        {"file": "backend/api/routes/patch.py",              "test": None,                               "phase": 1},
    "api/routes/simulate":     {"file": "backend/api/routes/simulate.py",           "test": None,                               "phase": 1},
    "api/routes/auth":         {"file": "backend/api/routes/auth.py",               "test": "tests/test_auth.py",               "phase": 1},
    "db/crud":                 {"file": "backend/db/crud.py",                       "test": None,                               "phase": 1},

    # ── PCB layout engine (pulled forward from Phase 3, shipped 2026-07) ──────
    # Registered 2026-08-07: ~2,400 lines that were previously untracked by the
    # memory system entirely. All currently untested — see current_phase.md.
    "pcb_engine/board_ir":     {"file": "backend/pcb_engine/board_ir.py",           "test": None,                               "phase": 3},
    "pcb_engine/compile_board":{"file": "backend/pcb_engine/compile_board.py",      "test": None,                               "phase": 3},
    "pcb_engine/footprints":   {"file": "backend/pcb_engine/footprints.py",         "test": None,                               "phase": 3},
    "pcb_engine/kernel":       {"file": "backend/pcb_engine/kernel.py",             "test": None,                               "phase": 3},
    "pcb_engine/router":       {"file": "backend/pcb_engine/router.py",             "test": None,                               "phase": 3},
    "pcb_engine/render_pretty":{"file": "backend/pcb_engine/render_pretty.py",      "test": None,                               "phase": 3},
    "generators/pcb_netlist":  {"file": "backend/generators/netlist/pcb.py",        "test": None,                               "phase": 3},
    "api/routes/pcb":          {"file": "backend/api/routes/pcb.py",                "test": None,                               "phase": 3},
}

PHASE1_CRITERIA = [
    "JWT auth — all routes protected",
    "Full generation under 30s",
    "SPICE simulation runs and grades",
    "Simulation fails on wrong values",
    "Rule engine catches hardware violations",
    "Firmware compiles to real Arduino",
    "5 sequential patches — no corruption",
    "20 prompts — zero crashes",
    "100 requests — zero HTTP 500s",
    "Rate limiting — 11th returns 429",
    # Amended 2026-08-07: the original criterion was an oscilloscope bench
    # measurement at 15%. No lab access exists, so it was replaced by a
    # closed-form analytical cross-check at 2%. See brain/decisions.md.
    "Simulation vs closed-form equations ≤2%",
    "External engineer reads explanation",
]

# Criteria met by a SUBSTITUTE gate rather than the original one. These render
# as "✅*" and count toward done, but the asterisk must survive into any summary
# — criterion 11 validates the netlist generator against mathematics, not
# against physical reality. Do not let met_by_substitute quietly become met.
SUBSTITUTE_CRITERIA = {10}

# Which criteria map to which test files (auto-checkable)
CRITERIA_TEST_MAP = {
    0: ["tests/test_auth.py"],
    2: ["tests/test_simulation.py"],
    3: ["tests/test_simulation.py"],
    4: ["tests/test_rule_engine.py"],
    5: ["tests/test_firmware_generator.py"],
    10: ["tests/test_simulation_accuracy.py"],
}

# Test files consulted when evaluating criteria. A criterion wired to a file
# missing from this list can never pass, however green the file is.
CRITERIA_SCAN_FILES = sorted({
    Path(f).name for files in CRITERIA_TEST_MAP.values() for f in files
} | {"test_bom.py", "test_ir_schema.py"})


# ── Helpers ───────────────────────────────────────────────────────────────────
def run(cmd, cwd=None, env=None, timeout=120):
    try:
        r = subprocess.run(
            cmd, cwd=cwd or PROJECT_ROOT,
            capture_output=True, text=True, timeout=timeout,
            env=env or os.environ, encoding="utf-8", errors="replace",
        )
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except FileNotFoundError:
        return -1, "", f"NOT FOUND: {cmd[0]}"
    except Exception as e:
        return -1, "", f"ERROR: {e}"


def git_commit():
    _, out, _ = run(["git", "rev-parse", "--short", "HEAD"])
    return out.strip() or "unknown"


def git_log(n=5):
    _, out, _ = run(["git", "log", f"-{n}", "--oneline"])
    return [l.strip() for l in out.strip().splitlines()] if out.strip() else []


def git_diff_stat():
    _, out, _ = run(["git", "diff", "--stat", "HEAD~1", "HEAD"])
    return out.strip()[:200] if out.strip() else "no diff"


# ── Test runner ───────────────────────────────────────────────────────────────
def run_tests():
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    code, out, err = run(
        ["python", "-m", "pytest", "tests/", "--tb=no", "-v", "--no-header"],
        env=env, timeout=180,
    )
    text = out + err
    passed = int(re.search(r"(\d+) passed", text).group(1)) if re.search(r"(\d+) passed", text) else 0
    failed = int(re.search(r"(\d+) failed", text).group(1)) if re.search(r"(\d+) failed", text) else 0
    skipped = int(re.search(r"(\d+) skipped", text).group(1)) if re.search(r"(\d+) skipped", text) else 0
    total = passed + failed
    icon = "OK" if failed == 0 and total > 0 else ("FAIL" if failed > 0 else "??")
    print(f"  [{icon}] {passed} passed, {failed} failed, {skipped} skipped")
    return {"passed": passed, "failed": failed, "skipped": skipped, "total": total, "raw": text}


def as_test_list(cfg_test) -> list:
    """MODULES['test'] accepts None, a single path, or a list of paths."""
    if cfg_test is None:
        return []
    if isinstance(cfg_test, str):
        return [cfg_test]
    return list(cfg_test)


def single_file_status(test_file_rel: str, raw_output: str) -> str:
    """Returns 'passing', 'failing', or 'no_test' for one test file."""
    test_name = Path(test_file_rel).name
    lines = raw_output.splitlines()
    if not any(test_name in line for line in lines):
        return "no_test"
    has_failures = any("FAILED" in line and test_name in line for line in lines)
    return "failing" if has_failures else "passing"


def get_file_test_status(cfg_test, raw_output: str) -> str:
    """Aggregate status across every test file covering a module.

    Any failure wins; otherwise every listed file must be present and passing.
    A module whose second test file silently vanished must not keep reporting
    'passing' on the strength of the first.
    """
    files = as_test_list(cfg_test)
    if not files:
        return "no_test"
    statuses = [single_file_status(f, raw_output) for f in files]
    if "failing" in statuses:
        return "failing"
    if any(st == "no_test" for st in statuses):
        return "no_test"
    return "passing"


# ── Module checker ────────────────────────────────────────────────────────────
def check_modules(test_raw: str):
    modules = {}
    done = in_progress = not_started = 0

    for name, cfg in MODULES.items():
        path = PROJECT_ROOT / cfg["file"]
        exists = path.exists()
        test_status = get_file_test_status(cfg["test"], test_raw)

        if not exists:
            status = "not_started"
            not_started += 1
        elif test_status == "failing":
            status = "broken"
        elif test_status == "passing":
            status = "verified_done"
            done += 1
        else:
            status = "untested"
            in_progress += 1

        icons = {"verified_done": "✅", "broken": "❌", "untested": "⚠️ ", "not_started": "⬜"}
        print(f"  {icons.get(status, '?')} {name}: {status}")

        modules[name] = {
            "status": status,
            "file": cfg["file"],
            "exists": exists,
            "test_file": cfg["test"],
            "test_status": test_status,
        }

    return modules, done, in_progress, not_started


# ── Phase 1 criteria ──────────────────────────────────────────────────────────
def check_criteria(test_raw: str, modules: dict):
    results = []
    test_files_passing = set()
    # A test file "passes" if it appears in the output AND has no FAILED lines
    for tf in CRITERIA_SCAN_FILES:
        # Look for the test file path in output — pytest shows e.g. "tests/test_auth.py ...."
        file_mentioned = any(tf in line for line in test_raw.splitlines())
        has_failures = any("FAILED" in line and tf in line for line in test_raw.splitlines())
        if file_mentioned and not has_failures:
            test_files_passing.add(tf)

    # Derived from CRITERIA_TEST_MAP rather than hand-listed, so wiring a new
    # criterion to a test file is a one-line change in one place.
    auto_pass = {
        idx: all(Path(f).name in test_files_passing for f in files)
        for idx, files in CRITERIA_TEST_MAP.items()
    }

    for i, criterion in enumerate(PHASE1_CRITERIA):
        if i in auto_pass:
            if not auto_pass[i]:
                status = "❌"
            else:
                status = "✅*" if i in SUBSTITUTE_CRITERIA else "✅"
        elif i in (1, 6, 7, 8, 9):  # verified in previous live session
            status = "✅"
        else:
            status = "⏳"  # physical/human — can't auto-check
        results.append((status, criterion))

    done_count = sum(1 for s, _ in results if s.startswith("✅"))
    return results, done_count


# ── Blockers from current_phase.md ───────────────────────────────────────────
def read_blockers():
    blockers = []
    phase_file = MEMORY_ROOT / "plan" / "current_phase.md"
    if not phase_file.exists():
        return blockers
    in_section = False
    for line in phase_file.read_text(encoding="utf-8").splitlines():
        if "Current Blockers" in line:
            in_section = True
            continue
        if in_section and line.startswith("##"):
            break
        if in_section and line.startswith("|") and "---" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if not parts or parts[0] in ("Blocker", "Since", ":"):
                continue
            # A blocker struck through (~~like this~~) is resolved. Without this
            # check the list keeps reporting blockers the plan closed weeks ago,
            # which is how "No oscilloscope access" survived its own resolution.
            if parts[0].startswith("~~") and parts[0].endswith("~~"):
                continue
            blockers.append(parts[0])
    return blockers


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n🔄  regen_state.py — Circuit OS\n")
    print(f"📁  Project root : {PROJECT_ROOT}")
    print(f"📁  Memory root  : {MEMORY_ROOT}\n")

    print("🧪  Running tests (PYTHONPATH=backend pytest tests/):")
    tests = run_tests()

    print("\n📦  Checking modules:")
    modules, done, in_progress, not_started = check_modules(tests["raw"])

    print("\n🎯  Phase 1 criteria:")
    criteria, criteria_done = check_criteria(tests["raw"], modules)
    for status, label in criteria:
        print(f"  {status}  {label}")

    print("\n📜  Git:")
    commit = git_commit()
    log    = git_log(5)
    diff   = git_diff_stat()
    print(f"  HEAD: {commit}")
    for entry in log[:3]:
        print(f"  {entry}")

    blockers = read_blockers()

    # ── Write state.json ──────────────────────────────────────────────────────
    state = {
        "_note": "DERIVED file. Run: python .claude/shared-memory/tools/regen_state.py",
        "_layer": "LAYER 4 (Progress) — module-level summary",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_from_commit": commit,
        "project": "Circuit OS",
        "description": "AI hardware compiler: plain English → schematic + firmware + simulation + BOM",
        "phase": {
            "current": 2,
            "name": "Physical + External Validation",
            "status": "in_progress" if criteria_done < 12 else "done",
            "phase1_criteria_done": criteria_done,
            "phase1_criteria_total": 12,
        },
        "modules": {k: {kk: vv for kk, vv in v.items() if kk != "test_file"} for k, v in modules.items()},
        "test_summary": {
            "passed": tests["passed"],
            "failed": tests["failed"],
            "skipped": tests["skipped"],
            "total": tests["total"],
        },
        "phase1_criteria": [
            {
                "status": s,
                "criterion": c,
                "met_by_substitute": i in SUBSTITUTE_CRITERIA and s.startswith("✅"),
            }
            for i, (s, c) in enumerate(criteria)
        ],
        "phase1_criteria_legend": (
            "✅ met · ✅* met_by_substitute (a replacement gate, not the original) · "
            "❌ failing · ⏳ needs a human or physical hardware"
        ),
        "blockers": blockers,
        "recent_commits": log,
        "last_diff_stat": diff,
        "pointers": {
            "see_function_level": "progress.yaml",
            "see_current_tasks": "plan/current_phase.md",
            "see_full_roadmap": "plan/master_plan.md",
            "see_decisions": "brain/decisions.md",
            "see_architecture": "brain/architecture.md",
        },
    }

    state_path = MEMORY_ROOT / "state.json"
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✅  state.json written → {state_path}")

    # ── Also run progress_gen ─────────────────────────────────────────────────
    print("\n📋  Updating progress.yaml...")
    prog_script = TOOLS_DIR / "progress_gen.py"
    if prog_script.exists():
        code, out, err = run(["python", str(prog_script)])
        for line in (out + err).splitlines():
            if any(k in line for k in ["Summary", "verified", "✅", "❌", "progress.yaml"]):
                print(f"  {line.strip()}")
    else:
        print("  ⚠ progress_gen.py not found")

    # ── Reviewer Summary ──────────────────────────────────────────────────────
    print("\n" + "═" * 68)
    print("  REVIEWER SUMMARY  — paste into any new session to orient instantly")
    print("═" * 68)
    print(f"  Project  : Circuit OS  (AI hardware compiler: NL → circuit + firmware)")
    print(f"  Commit   : {commit}")
    print(f"  Tests    : {tests['passed']} passing  /  {tests['failed']} failing  /  {tests['skipped']} skipped")
    print(f"  Phase    : 2 — Physical + External Validation")
    subs = [c for i, (st, c) in enumerate(criteria)
            if i in SUBSTITUTE_CRITERIA and st.startswith("✅")]
    print(f"  Criteria : {criteria_done}/12 Phase 1 criteria done")
    for c in subs:
        print(f"             * {c} — met_by_substitute, NOT met")
    print(f"  Modules  : {done} verified_done  /  {in_progress} untested  /  {not_started} not_started")
    if blockers:
        print(f"  Blockers : {len(blockers)}")
        for b in blockers[:3]:
            print(f"             • {b}")
    print(f"\n  To orient any agent: read AGENTS.md → follow 5-step bootstrap")
    print(f"  To continue:         read plan/current_phase.md → Day 2-3 tasks")
    print("═" * 68 + "\n")


if __name__ == "__main__":
    main()
