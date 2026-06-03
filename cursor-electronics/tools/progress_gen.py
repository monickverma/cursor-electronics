#!/usr/bin/env python3
"""
progress_gen.py — Generates progress.yaml from reality at FUNCTION level.

What it does:
  1. Scans every .py file in backend/ using Python's `ast` module
     → extracts every function: name, signature, docstring, line number
  2. Detects stubs: functions whose body is only a docstring (placeholder)
  3. Runs pytest -v to get per-test pass/fail
  4. Maps source functions to their tests by naming convention
     (test_generate → generate)
  5. Assigns each function a status:
     verified_done  ✅  exists + real body + test passes
     broken         ❌  exists + real body + test fails
     stub           🔲  exists but body is only docstring (placeholder)
     untested       ⚠️   exists + real body + no test mapped
     not_started    ⬜  in plan but not in file
  6. Writes progress.yaml

Run via regen_state.py or standalone:
    python tools/progress_gen.py
"""

import ast
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).parent.parent
SRC   = ROOT / "backend"
TESTS = ROOT / "tests"


# ── The plan: what functions SHOULD exist per file ────────────────────────────
# UPDATE THIS DICT when you add new modules or functions to your roadmap.
# If a function is listed here but missing from the file → not_started.

PLANNED_FUNCTIONS = {
    "backend/ai/intent_parser.py": [
        ("parse",               "Parses user prompt → DesignSpec (tool_use mode)"),
    ],
    "backend/ai/circuit_reasoner.py": [
        ("generate",            "DesignSpec → CircuitIR with 3-attempt retry loop"),
    ],
    "backend/ai/patcher.py": [
        ("patch",               "IR + edit command → changed fields only (not full IR)"),
    ],
    "backend/ai/explainer.py": [
        ("explain",             "CircuitIR → consequential plain English explanation"),
    ],
    "backend/generators/netlist/spice.py": [
        ("generate",            "CircuitIR → SPICE netlist string (MCU as R_MCU, floating node tie-downs)"),
    ],
    "backend/generators/firmware/arduino.py": [
        ("generate",            "CircuitIR + template_id → Arduino .ino from Jinja2"),
    ],
    "backend/generators/schematic/kicad.py": [
        ("generate",            "CircuitIR → .kicad_sch with net labels (no wire routing Phase 1)"),
    ],
    "backend/generators/bom/compiler.py": [
        ("compile",             "CircuitIR → BOM rows with static pricing"),
    ],
    "backend/simulation/runner.py": [
        ("run",                 "SPICE netlist → ngspice subprocess → raw output text"),
    ],
    "backend/simulation/parser.py": [
        ("parse",               "ngspice columnar text output → structured dict (DC + AC)"),
    ],
    "backend/simulation/grader.py": [
        ("grade",               "parsed ngspice data vs IR constraints → pass/fail (15% tolerance)"),
    ],
    "backend/core/ir_validator.py": [
        ("validate_ir",         "CircuitIR → structural validation before any compiler"),
    ],
    "backend/validation/rule_engine.py": [
        ("run",                 "CircuitIR → hardware rule checks (no floating nodes, I2C pull-ups, etc.)"),
    ],
}

STATUS_ICON = {
    "verified_done": "✅",
    "broken":        "❌",
    "stub":          "🔲",
    "untested":      "⚠️ ",
    "not_started":   "⬜",
}


# ── AST extraction ────────────────────────────────────────────────────────────
def extract_functions(filepath: Path) -> dict:
    if not filepath.exists():
        return {}
    try:
        tree = ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError as e:
        print(f"  ⚠ Syntax error in {filepath.name}: {e}")
        return {}

    funcs = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue

        # Signature
        args = []
        for arg in node.args.args:
            ann = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
            args.append(f"{arg.arg}{ann}")
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        signature = f"{node.name}({', '.join(args)}){ret}"

        # Docstring (first line)
        docstring = ast.get_docstring(node) or ""
        description = docstring.split("\n")[0].strip() if docstring else ""

        # Stub detection: body is only a docstring, or only `pass`, or only `...`
        is_stub = (
            len(node.body) == 1 and (
                (isinstance(node.body[0], ast.Expr)
                 and isinstance(node.body[0].value, ast.Constant)
                 and isinstance(node.body[0].value.value, str)) or  # only docstring
                isinstance(node.body[0], ast.Pass) or                 # pass
                (isinstance(node.body[0], ast.Expr)
                 and isinstance(node.body[0].value, ast.Constant)
                 and node.body[0].value.value is Ellipsis)            # ...
            )
        )

        funcs[node.name] = {
            "signature": signature,
            "description": description,
            "line": node.lineno,
            "is_stub": is_stub,
        }
    return funcs


# ── Test runner ───────────────────────────────────────────────────────────────
def run_tests_verbose() -> dict:
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-v", "--tb=no", "--no-header", "-q"],
            capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=120
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}
    out = result.stdout + result.stderr
    test_results = {}
    for line in out.splitlines():
        line = line.strip()
        if " PASSED" in line:
            tid = line.split(" PASSED")[0].strip()
            test_results[tid] = "passing"
        elif " FAILED" in line:
            tid = line.split(" FAILED")[0].strip()
            test_results[tid] = "failing"
    return test_results


def map_function_to_test(func_name: str, test_results: dict):
    target = f"test_{func_name}"
    for tid, status in test_results.items():
        if tid.split("::")[-1] == target:
            return tid, status
    return None, "no_test"


# ── Status derivation ─────────────────────────────────────────────────────────
def derive_status(func_name: str, extracted: dict, test_status: str) -> str:
    if func_name not in extracted:
        return "not_started"
    if extracted[func_name]["is_stub"]:
        return "stub"
    if test_status == "passing":
        return "verified_done"
    if test_status == "failing":
        return "broken"
    return "untested"


# ── YAML writer (fallback to JSON if no PyYAML) ───────────────────────────────
def write_yaml(data: dict, path: Path):
    if yaml:
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False,
                                  allow_unicode=True), encoding="utf-8")
    else:
        import json
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print("  i PyYAML not installed — wrote JSON syntax. Run: pip install pyyaml")


# ── Main ──────────────────────────────────────────────────────────────────────
def generate():
    print("\n📋 Generating function-level progress.yaml...\n")

    test_results = run_tests_verbose()
    print(f"  Test results collected: {len(test_results)}\n")

    progress = {
        "_note": "DERIVED. Do not edit. Run tools/progress_gen.py to update.",
        "_layer": "LAYER 4 (Progress) — function-level reality",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "project": "Circuit OS",
        "files": {},
        "summary": {},
    }

    counts = {"verified_done": 0, "broken": 0, "stub": 0,
              "untested": 0, "not_started": 0}

    for rel_path, planned in PLANNED_FUNCTIONS.items():
        filepath  = ROOT / rel_path
        extracted = extract_functions(filepath)

        file_entry = {"exists": filepath.exists(), "functions": {}}
        print(f"📄 {rel_path}:")

        for func_name, planned_desc in planned:
            test_id, test_status = map_function_to_test(func_name, test_results)
            status = derive_status(func_name, extracted, test_status)
            counts[status] += 1
            icon = STATUS_ICON[status]

            file_entry["functions"][func_name] = {
                "status": status,
                "description": (extracted.get(func_name, {}).get("description")
                                or planned_desc),
                "signature": (extracted.get(func_name, {}).get("signature")
                              or f"{func_name}(...)"),
                "test": test_id,
                "test_status": test_status,
                "line": extracted.get(func_name, {}).get("line"),
            }
            print(f"   {icon} {func_name}: {status}")

        # File-level status
        statuses = [f["status"] for f in file_entry["functions"].values()]
        if all(s == "verified_done" for s in statuses):
            file_entry["status"] = "done"
        elif any(s in ("verified_done", "broken", "stub", "untested") for s in statuses):
            file_entry["status"] = "in_progress"
        else:
            file_entry["status"] = "not_started"

        progress["files"][rel_path] = file_entry
        print()

    total = sum(counts.values())
    progress["summary"] = {
        "functions_total": total,
        "functions_verified_done": counts["verified_done"],
        "functions_broken": counts["broken"],
        "functions_stub": counts["stub"],
        "functions_untested": counts["untested"],
        "functions_not_started": counts["not_started"],
        "pct_verified": round(counts["verified_done"] / max(total, 1) * 100, 1),
    }

    print(f"📊 Summary: {counts['verified_done']}/{total} verified done "
          f"({progress['summary']['pct_verified']}%), "
          f"{counts['broken']} broken, {counts['not_started']} not started\n")

    write_yaml(progress, ROOT / "progress.yaml")
    print(f"✅ progress.yaml written")


if __name__ == "__main__":
    generate()
