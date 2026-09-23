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
import sys
from datetime import datetime, timezone
from pathlib import Path

# This script prints emoji. On Windows the console encoding is cp1252, which
# cannot encode them, so an unguarded run dies with UnicodeEncodeError before
# writing anything — the failure looks like a broken script rather than a
# broken terminal. Force UTF-8 here so no caller has to remember
# PYTHONIOENCODING=utf-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

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
    "ai/explainer":            {"file": "backend/ai/explainer.py",                  "test": "tests/test_explainer.py",          "phase": 1},
    "generators/spice":        {"file": "backend/generators/netlist/spice.py",      "test": ["tests/test_simulation.py",
                                                                                             "tests/test_simulation_accuracy.py"], "phase": 1},
    "generators/firmware":     {"file": "backend/generators/firmware/arduino.py",   "test": "tests/test_firmware_generator.py", "phase": 1},
    "generators/kicad":        {"file": "backend/generators/schematic/kicad.py",    "test": "tests/test_schematic_generator.py","phase": 1},
    "generators/bom":          {"file": "backend/generators/bom/compiler.py",       "test": "tests/test_bom.py",                "phase": 1},
    "simulation/runner":       {"file": "backend/simulation/runner.py",             "test": ["tests/test_simulation.py",
                                                                                             "tests/test_simulation_accuracy.py"], "phase": 1},
    "simulation/parser":       {"file": "backend/simulation/parser.py",             "test": ["tests/test_simulation.py",
                                                                                             "tests/test_simulation_accuracy.py",
                                                                                             "tests/test_waveforms.py",
                                                                                             "tests/test_claims.py"], "phase": 1},
    # grader is deliberately NOT covered by test_simulation_accuracy.py — that
    # file compares against closed-form equations directly, bypassing the 15%
    # grader on purpose. Do not add it here.
    "simulation/grader":       {"file": "backend/simulation/grader.py",             "test": "tests/test_simulation.py",         "phase": 1},
    "simulation/monitor":      {"file": "backend/simulation/monitor.py",            "test": None,                               "phase": 1},
    "validation/rule_engine":  {"file": "backend/validation/rule_engine.py",        "test": "tests/test_rule_engine.py",        "phase": 1},
    "tasks/simulation_task":   {"file": "backend/tasks/simulation_task.py",         "test": None,                               "phase": 1},
    "api/routes/design":       {"file": "backend/api/routes/design.py",             "test": None,                               "phase": 1},
    # Rewritten in Stage 2 (X4): patches the requirement, not the circuit.
    "api/routes/patch":        {"file": "backend/api/routes/patch.py",              "test": "tests/test_patch_route.py",        "phase": 1},
    "api/routes/simulate":     {"file": "backend/api/routes/simulate.py",           "test": None,                               "phase": 1},
    "api/routes/auth":         {"file": "backend/api/routes/auth.py",               "test": "tests/test_auth.py",               "phase": 1},
    "db/crud":                 {"file": "backend/db/crud.py",                       "test": None,                               "phase": 1},

    # ── PCB layout engine (pulled forward from Phase 3, shipped 2026-07) ──────
    # Registered 2026-08-07: ~2,400 lines that were previously untracked by the
    # memory system entirely. All currently untested — see current_phase.md.
    "pcb_engine/board_ir":     {"file": "backend/pcb_engine/board_ir.py",           "test": None,                               "phase": 3},
    "pcb_engine/compile_board":{"file": "backend/pcb_engine/compile_board.py",      "test": "tests/test_pcb_placement.py",                               "phase": 3},
    "pcb_engine/footprints":   {"file": "backend/pcb_engine/footprints.py",         "test": "tests/test_pcb_placement.py",                               "phase": 3},
    "pcb_engine/kernel":       {"file": "backend/pcb_engine/kernel.py",             "test": None,                               "phase": 3},
    "pcb_engine/router":       {"file": "backend/pcb_engine/router.py",             "test": None,                               "phase": 3},
    "pcb_engine/render_pretty":{"file": "backend/pcb_engine/render_pretty.py",      "test": None,                               "phase": 3},
    "generators/pcb_netlist":  {"file": "backend/generators/netlist/pcb.py",        "test": "tests/test_pcb_placement.py",                               "phase": 3},
    "api/routes/pcb":          {"file": "backend/api/routes/pcb.py",                "test": "tests/test_pcb_route.py",          "phase": 3},

    # ── Phase 2 — Validation Engine ──────────────────────────────────────────
    # Stage 0 instrumentation. PHASE_2_PLAN_v2.md §4.5.
    "observability/request_log":  {"file": "backend/observability/request_log.py",  "test": "tests/test_request_log.py",        "phase": 2},
    "middleware/instrumentation": {"file": "backend/middleware/instrumentation.py", "test": "tests/test_request_log.py",        "phase": 2},
    "generators/protocol":        {"file": "backend/generators/protocol.py",        "test": "tests/test_generator_protocol.py", "phase": 2},
    "generators/rc_lowpass":      {"file": "backend/generators/rc_lowpass.py",      "test": ["tests/test_rc_lowpass_generator.py",
                                                                                                "tests/test_generator_library.py"], "phase": 2},
    "validation/envelope_grid":   {"file": "backend/validation/envelope_grid.py",   "test": "tests/test_envelope_grid.py",        "phase": 2},
    "ai/derived_explainer":       {"file": "backend/ai/derived_explainer.py",       "test": "tests/test_derived_explainer.py",    "phase": 2},
    "core/intent_ir":             {"file": "backend/core/intent_ir.py",             "test": "tests/test_intent_ir.py",            "phase": 2},
    "generators/registry":        {"file": "backend/generators/registry.py",        "test": "tests/test_registry.py",             "phase": 2},
    "ai/form_producer":           {"file": "backend/ai/form_producer.py",           "test": "tests/test_form_producer.py",        "phase": 2},
    "ai/intent_producer":         {"file": "backend/ai/intent_producer.py",         "test": "tests/test_intent_producer.py",      "phase": 2},
    # Stage 2 — patch model v2 (X2 + X4). ai/patcher.py was removed with it:
    # it let a model write CircuitIR fields. decisions.md [2026-09-21].
    "core/intent_patch":          {"file": "backend/core/intent_patch.py",          "test": "tests/test_intent_patch.py",         "phase": 2},
    "core/annotations":           {"file": "backend/core/annotations.py",           "test": "tests/test_annotations.py",          "phase": 2},
    "generators/realize":         {"file": "backend/generators/realize.py",         "test": "tests/test_realize.py",              "phase": 2},
    "ai/intent_patcher":          {"file": "backend/ai/intent_patcher.py",          "test": "tests/test_intent_patcher.py",       "phase": 2},
    "db/migrations":              {"file": "backend/db/migrations.py",              "test": "tests/test_migrations.py",           "phase": 2},
    # Stage 3 — the generator library, claims, and the defeater register.
    # decisions.md [2026-09-21] X6 + X8.
    "generators/common":          {"file": "backend/generators/common.py",          "test": ["tests/test_rc_lowpass_generator.py", "tests/test_generator_library.py"], "phase": 2},
    "generators/arduino_parts":   {"file": "backend/generators/arduino_parts.py",   "test": "tests/test_generator_library.py",   "phase": 2},
    "generators/netlist_models":  {"file": "backend/generators/netlist/models.py",  "test": ["tests/test_claims.py", "tests/test_generator_library.py"], "phase": 2},
    "generators/voltage_divider": {"file": "backend/generators/voltage_divider.py", "test": "tests/test_generator_library.py",   "phase": 2},
    "generators/led_indicator":   {"file": "backend/generators/led_indicator.py",   "test": "tests/test_generator_library.py",   "phase": 2},
    "generators/dht22_node":      {"file": "backend/generators/dht22_node.py",      "test": "tests/test_generator_library.py",   "phase": 2},
    "generators/rs485_node":      {"file": "backend/generators/rs485_node.py",      "test": "tests/test_generator_library.py",   "phase": 2},
    "validation/claims":          {"file": "backend/validation/claims.py",          "test": ["tests/test_claims.py", "tests/test_generator_library.py"], "phase": 2},
    "validation/defeaters":       {"file": "backend/validation/defeaters.py",       "test": "tests/test_claims.py",               "phase": 2},
    "simulation/waveforms":       {"file": "backend/simulation/waveforms.py",       "test": "tests/test_waveforms.py",            "phase": 2},
    "validation/grid_adapters":   {"file": "backend/validation/grid_adapters.py",   "test": "tests/test_generator_library.py",   "phase": 2},
    # Stage 4 — the proof compiler. decisions.md [2026-09-23].
    "proof/brackets":             {"file": "backend/proof/brackets.py",             "test": "tests/test_proof.py",                "phase": 2},
    "proof/netlist":              {"file": "backend/proof/netlist.py",              "test": "tests/test_proof.py",                "phase": 2},
    "proof/mna":                  {"file": "backend/proof/mna.py",                  "test": "tests/test_proof.py",                "phase": 2},
    "proof/properties":           {"file": "backend/proof/properties.py",           "test": ["tests/test_proof.py", "tests/test_sign_off.py"], "phase": 2},
    "proof/prover":               {"file": "backend/proof/prover.py",               "test": ["tests/test_proof.py", "tests/test_sign_off.py", "tests/test_proof_oracle.py"], "phase": 2},
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

# Criteria DEFERRED out of Phase 1 with a named reopening trigger. These render
# as "⏭" and do NOT count toward done — Phase 1 closes at 11/12 with one
# deferred, not at 12/12. The distinction from SUBSTITUTE_CRITERIA matters: a
# substitute criterion was met by a different gate, a deferred one was not met
# at all. Collapsing the two would be the quiet devaluation that
# brain/decisions.md [2026-08-22] "Criterion 12 moved off the v0.1.0 gate"
# spends a page refusing.
#
# The trigger is what stops "deferred" from meaning "dropped". It is recorded in
# brain/decisions.md, not here — this set only needs to know which index.
DEFERRED_CRITERIA = {11}

# Which criteria map to which test files (auto-checkable)
CRITERIA_TEST_MAP = {
    0: ["tests/test_auth.py"],
    2: ["tests/test_simulation.py"],
    3: ["tests/test_simulation.py"],
    4: ["tests/test_rule_engine.py"],
    5: ["tests/test_firmware_generator.py"],
    # Criterion 7 re-earned at the IntentIR layer in Stage 2. Its Phase 1
    # automation patched CircuitIR and was removed with ai/patcher.py.
    6: ["tests/test_intent_patch.py"],
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
    # 2026-09-20: this was 180s. The suite grew past it — ngspice runs the
    # envelope grid and the accuracy harness — so pytest was killed, the
    # regexes below matched nothing, and zeros were written to state.json:
    # 0 tests, every module untested, on a suite that was fully green. A
    # derived file that reports total collapse is worse than a stale one,
    # because AGENTS.md says to trust it over everything else.
    code, out, err = run(
        ["python", "-m", "pytest", "tests/", "--tb=no", "-v", "--no-header"],
        env=env, timeout=900,
    )
    text = out + err
    passed = int(re.search(r"(\d+) passed", text).group(1)) if re.search(r"(\d+) passed", text) else 0
    failed = int(re.search(r"(\d+) failed", text).group(1)) if re.search(r"(\d+) failed", text) else 0
    skipped = int(re.search(r"(\d+) skipped", text).group(1)) if re.search(r"(\d+) skipped", text) else 0
    errors = int(re.search(r"(\d+) errors?\b", text).group(1)) if re.search(r"(\d+) errors?\b", text) else 0
    total = passed + failed

    # Refuse to write a result we did not actually measure. Aborting leaves the
    # previous state.json in place, which is recoverable; writing over it with
    # a number we did not measure is not.
    #
    # Three ways a run can be unmeasurable, and the first version caught only
    # the first:
    #   - nothing parseable at all (killed, crashed, no summary)
    #   - collection errors: "100 passed, 1 error" leaves failed == 0, so the
    #     run looks clean while some tests never ran
    #   - a non-zero exit with no failures to explain it
    # A run with genuine test failures is measured, and is recorded as such —
    # `broken` modules are exactly what progress.yaml exists to show.
    abort_reason = None
    if total == 0 and skipped == 0:
        abort_reason = "timed out" if "TIMEOUT" in err else f"no parseable summary (exit {code})"
    elif errors:
        abort_reason = f"{errors} collection/setup error(s) — some tests never ran"
    elif code != 0 and failed == 0:
        abort_reason = f"exit {code} with no reported failures"

    if abort_reason:
        print(f"  [ABORT] pytest run is not measurable: {abort_reason}.")
        for line in (err or out).strip().splitlines()[-8:]:
            print(f"     {line}")
        raise SystemExit(
            "regen_state.py: refusing to write state.json from an unmeasured "
            "test run — state.json and progress.yaml are unchanged."
        )
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
        if i in DEFERRED_CRITERIA:
            status = "⏭"   # deferred with a trigger — not met, not counted
        elif i in auto_pass:
            if not auto_pass[i]:
                status = "❌"
            else:
                status = "✅*" if i in SUBSTITUTE_CRITERIA else "✅"
        elif i in (1, 7, 8, 9):  # verified in previous live session
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


# ── Stage 3: the library's grade floor ──────────────────────────────────────
#
# EVIDENCE_CLASSES §5: overall certainty is the *lowest* grade among critical
# claims — never an average — and it is the number at the top of any summary.
# Derived here, like everything else in this file: every registered generator
# is realised at the first point of its own CI grid and its claims summarised.
# Run in a subprocess so importing the backend (which validates settings at
# import) cannot disturb this tool's own environment.
_LIBRARY_PROBE = r"""
import json, os, sys
for k, v in {"ANTHROPIC_API_KEY": "", "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
             "REDIS_URL": "redis://localhost:6379/0", "SECRET_KEY": "x" * 40}.items():
    os.environ.setdefault(k, v)
sys.path.insert(0, "backend")
from core.intent_ir import IntentIR, Producer, Provenance
from generators.realize import realize
from generators.registry import default_registry
from validation.grid_adapters import intent_at
out = {}
for g in default_registry().generators:
    grid = g.grid()
    req = intent_at(g.function, next(iter(grid.points())), grid.sections).requirements
    intent = IntentIR(requirements=req, provenance=Provenance(producer=Producer.FORM))
    cov = realize(g, intent).validation_coverage
    out[g.name] = {k: cov[k] for k in ("grade_floor", "coverage_le_g2", "open_defeaters", "not_assessed")}
    out[g.name]["floor_claims"] = [c["id"] for c in cov["claims"]
                                   if c["critical"] and c["grade"] == cov["grade_floor"]]
    # Stage 4: proofs count only once signed, so the floor is reported both
    # ways — as it stands, and as it would stand with the properties signed.
    props = cov.get("properties") or []
    signed = (realize(g, intent.sign_off("regen_state", properties_hash=cov["properties_hash"])).validation_coverage
              if props else cov)
    out[g.name]["proofs"] = {"declared": len(props), "proven": sum(p["status"] == "proven" for p in props),
                             "floor_if_signed": signed["grade_floor"]}
print(json.dumps(out))
"""


def library_grades() -> dict:
    """Per-generator coverage and the library floor. Empty dict if it cannot run."""
    code, out, err = run(["python", "-c", _LIBRARY_PROBE], cwd=PROJECT_ROOT, timeout=300)
    if code != 0:
        print(f"  ❌ grade-floor probe FAILED (exit {code}) — floor not derived")
        for line in (err or out).strip().splitlines()[-4:]:
            print(f"     {line}")
        return {}
    per = json.loads(out.strip().splitlines()[-1])
    order = ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]
    floors = [v["grade_floor"] for v in per.values() if v["grade_floor"]]
    fan_out: dict = {}
    for name, v in per.items():
        for d in v["open_defeaters"]:
            fan_out.setdefault(d, []).append(name)
    return {
        "grade_floor": max(floors, key=order.index) if floors else None,
        "coverage_le_g2_min": min(v["coverage_le_g2"] for v in per.values()) if per else 0.0,
        "open_defeaters": {d: sorted(n) for d, n in sorted(fan_out.items(), key=lambda kv: int(kv[0][1:]))},
        "not_assessed": {n: v["not_assessed"] for n, v in per.items() if v["not_assessed"]},
        "generators": per,
    }


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

    print()
    print("🧾  Library grade floor (EVIDENCE_CLASSES §5):")
    validation = library_grades()
    for name, v in validation.get("generators", {}).items():
        proofs = v.get("proofs") or {}
        print(f"  {name:18} floor {v['grade_floor']}  coverage≤G2 {v['coverage_le_g2']:.0%}  "
              f"open {', '.join(v['open_defeaters']) or '—'}  "
              f"proofs {proofs.get('proven', 0)}/{proofs.get('declared', 0)} → {proofs.get('floor_if_signed')} signed")

    # ── Write state.json ──────────────────────────────────────────────────────
    state = {
        "_note": "DERIVED file. Run: python .claude/shared-memory/tools/regen_state.py",
        "_layer": "LAYER 4 (Progress) — module-level summary",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_from_commit": commit,
        "project": "Circuit OS",
        "description": "AI hardware compiler: plain English → schematic + firmware + simulation + BOM",
        # Phase 2 is the Validation Engine, per PRODUCT_MASTER.md — declared
        # canonical in brain/decisions.md [2026-08-22]. It was previously named
        # "Physical + External Validation" here, which described the leftover
        # Phase 1 gates rather than a phase: criterion 11 is met by substitute
        # and criterion 12 is deferred, so that name now has no content.
        "phase": {
            "current": 2,
            "name": "Validation Engine",
            "status": "in_progress",
            "phase1_status": "closed_with_deferral",
            "phase1_criteria_done": criteria_done,
            "phase1_criteria_total": 12,
            "phase1_criteria_deferred": sorted(DEFERRED_CRITERIA),
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
        # Stage 3: the weakest-link headline and its companions, never fused.
        "validation": validation,
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
        # progress_gen.py runs the whole suite itself to map tests to entries,
        # so it needs the same headroom run_tests() does. The default 120s was
        # silently too small once the suite passed two minutes — caught only
        # because the exit-code check below now reports it. Third instance of
        # this root cause; the first two were silent.
        # Above progress_gen.py's own 1200 s test budget, so its loud
        # failure can surface instead of being cut off by this one.
        code, out, err = run(["python", str(prog_script)], timeout=1500)
        # The exit code used to be discarded, and the keyword filter below does
        # not match a Python traceback — so when progress_gen.py started dying
        # on a Windows encoding error this step printed nothing and looked
        # like it had worked. progress.yaml went stale for four weeks.
        # A tool that cannot report its own failure is worse than no tool.
        if code != 0:
            print(f"  ❌ progress_gen.py FAILED (exit {code}) — progress.yaml is STALE")
            for line in (err or out).strip().splitlines()[-6:]:
                print(f"     {line}")
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
    # The honest headline goes first (EVIDENCE_CLASSES §5): the worst grade
    # among critical claims across the library, with what makes it defeasible
    # printed beside it rather than folded into it.
    if validation.get("grade_floor"):
        weakest = [n for n, v in validation["generators"].items()
                   if v["grade_floor"] == validation["grade_floor"]]
        print(f"  Floor    : {validation['grade_floor']}  (weakest: {', '.join(weakest)})  "
              f"· coverage≤G2 ≥ {validation['coverage_le_g2_min']:.0%}")
        opened = ", ".join(f"{d}×{len(n)}" for d, n in validation["open_defeaters"].items())
        print(f"             open defeaters (fan-out): {opened or 'none'} — claims are defeasible")
        if validation.get("not_assessed"):
            print(f"             NOT ASSESSED: {validation['not_assessed']}")
        proofs = [v.get("proofs") or {} for v in validation["generators"].values()]
        signed_floors = [p["floor_if_signed"] for p in proofs if p.get("floor_if_signed")]
        order = ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]
        print(f"  Proofs   : {sum(p.get('proven', 0) for p in proofs)}/{sum(p.get('declared', 0) for p in proofs)} "
              f"properties proven from the netlist; count only once signed "
              f"(floor if all signed: {max(signed_floors, key=order.index) if signed_floors else '—'})")
    else:
        print("  Floor    : not derived — see the grade-floor probe output above")
    print(f"  Commit   : {commit}")
    print(f"  Tests    : {tests['passed']} passing  /  {tests['failed']} failing  /  {tests['skipped']} skipped")
    print(f"  Phase    : 2 — Validation Engine")
    subs = [c for i, (st, c) in enumerate(criteria)
            if i in SUBSTITUTE_CRITERIA and st.startswith("✅")]
    deferred = [c for i, (st, c) in enumerate(criteria) if i in DEFERRED_CRITERIA]
    print(f"  Criteria : {criteria_done}/12 Phase 1 done, {len(deferred)} deferred")
    for c in subs:
        print(f"             * {c} — met_by_substitute, NOT met")
    # The asterisk convention exists so a substitute cannot pass as met. A
    # deferral needs the same protection, and more of it: it was not met by any
    # gate at all.
    for c in deferred:
        print(f"             ⏭ {c} — DEFERRED, not met. Trigger in decisions.md")
    print(f"  Modules  : {done} verified_done  /  {in_progress} untested  /  {not_started} not_started")
    if blockers:
        print(f"  Blockers : {len(blockers)}")
        for b in blockers[:3]:
            print(f"             • {b}")
    print(f"\n  To orient any agent: read AGENTS.md → follow 5-step bootstrap")
    print(f"  To continue:         read plan/current_phase.md → the open tasks")
    print("═" * 68 + "\n")


if __name__ == "__main__":
    main()
