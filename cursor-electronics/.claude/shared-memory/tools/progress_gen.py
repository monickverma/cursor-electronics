#!/usr/bin/env python3
"""
progress_gen.py — Generates progress.yaml for Circuit OS at class/method level.

What it does:
  1. Scans every tracked backend .py file using Python's `ast` module
     → extracts every class and public method: name, signature, docstring, line
  2. Detects stubs (body = only docstring / pass / ...)
  3. Runs pytest -v to get per-test-file pass/fail
  4. Maps classes/methods to their test files
  5. Assigns each entry a status:
       verified_done  ✅  exists + real body + test file passes
       broken         ❌  exists + real body + test file fails
       stub           🔲  exists but body is only docstring/pass/...
       untested       ⚠️   exists + real body + no test file mapped
       not_started    ⬜  in plan but not in file
  6. Writes progress.yaml

Run:
    cd cursor-electronics
    python .claude/shared-memory/tools/progress_gen.py
"""

import ast
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR    = Path(__file__).parent
MEMORY_ROOT  = TOOLS_DIR.parent
PROJECT_ROOT = MEMORY_ROOT.parent.parent
BACKEND      = PROJECT_ROOT / "backend"
TESTS        = PROJECT_ROOT / "tests"

# ── What to track: {module_key: {file, test_file, class, methods[]}} ──────────
PLANNED = {
    "core/ir_schema": {
        "file": "backend/core/ir_schema.py",
        "test_file": "tests/test_ir_schema.py",
        "entries": [
            ("CircuitIR",     "class", "Locked IR contract — all downstream generators read from this"),
            ("Component",     "class", "Component model with part_number, value, confidence"),
            ("Node",          "class", "Electrical node with type and voltage"),
            ("Connection",    "class", "component_id + node_id link — NEVER rename these fields"),
            ("SimulationSpec","class", "AC/DC analysis spec with expected_outputs"),
        ],
    },
    "core/ir_validator": {
        "file": "backend/core/ir_validator.py",
        "test_file": "tests/test_rule_engine.py",
        "entries": [
            ("validate_ir", "function", "Structural validation: floating nodes, voltage ratings, I2C pullups"),
        ],
    },
    "ai/intent_parser": {
        "file": "backend/ai/intent_parser.py",
        "test_file": "tests/test_ai_layer.py",
        "entries": [
            ("IntentParser",       "class",  "Converts prompt → DesignSpec via tool_use"),
            ("IntentParser.parse", "method", "Main entry: prompt str → DesignSpec"),
        ],
    },
    "ai/circuit_reasoner": {
        "file": "backend/ai/circuit_reasoner.py",
        "test_file": "tests/test_ai_layer.py",
        "entries": [
            ("CircuitReasoner",          "class",  "Converts DesignSpec → CircuitIR with 3-attempt retry"),
            ("CircuitReasoner.generate", "method", "Main entry: DesignSpec → CircuitIR"),
        ],
    },
    "ai/patcher": {
        "file": "backend/ai/patcher.py",
        "test_file": None,
        "entries": [
            ("CircuitPatcher",         "class",  "Returns only changed fields — never full IR"),
            ("CircuitPatcher.patch",   "method", "Main entry: IR + command → PatchResult"),
            ("PatchResult.apply_to",   "method", "Applies changes to IR, increments version"),
        ],
    },
    "ai/explainer": {
        "file": "backend/ai/explainer.py",
        "test_file": None,
        "entries": [
            ("ExplanationEngine",         "class",  "Consequential plain-English design report"),
            ("ExplanationEngine.explain", "method", "IR → multi-section report with failure analysis"),
        ],
    },
    "generators/spice": {
        "file": "backend/generators/netlist/spice.py",
        "test_file": "tests/test_simulation.py",
        "entries": [
            ("SpiceNetlistGenerator",          "class",  "CircuitIR → SPICE netlist string"),
            ("SpiceNetlistGenerator.generate", "method", "Main entry: MCU=100Ω, floating→1GΩ tie-down"),
        ],
    },
    "generators/firmware": {
        "file": "backend/generators/firmware/arduino.py",
        "test_file": "tests/test_firmware_generator.py",
        "entries": [
            ("ArduinoFirmwareGenerator",          "class",  "CircuitIR → .ino via Jinja2 templates"),
            ("ArduinoFirmwareGenerator.generate", "method", "Main entry: picks template by circuit type"),
        ],
    },
    "generators/bom": {
        "file": "backend/generators/bom/compiler.py",
        "test_file": "tests/test_bom.py",
        "entries": [
            ("BOMCompiler",         "class",  "CircuitIR → BOM rows with static pricing"),
            ("BOMCompiler.compile", "method", "Main entry: returns list of BOM row dicts"),
        ],
    },
    "simulation/runner": {
        "file": "backend/simulation/runner.py",
        "test_file": "tests/test_simulation.py",
        "entries": [
            ("NgspiceRunner",     "class",  "Async subprocess wrapper for ngspice"),
            ("NgspiceRunner.run", "method", "async: writes netlist → -o outfile → reads result"),
        ],
    },
    "simulation/parser": {
        "file": "backend/simulation/parser.py",
        "test_file": "tests/test_simulation.py",
        "entries": [
            ("SpiceResultParser",       "class",  "Parses ngspice -b -o output"),
            ("SpiceResultParser.parse", "method", "Handles DC columnar table + AC multi-table complex"),
        ],
    },
    "simulation/grader": {
        "file": "backend/simulation/grader.py",
        "test_file": "tests/test_simulation.py",
        "entries": [
            ("SimulationGrader",       "class",  "Pass/fail at 15% tolerance"),
            ("SimulationGrader.grade", "method", "Checks each expected_output node against parsed data"),
        ],
    },
    "validation/rule_engine": {
        "file": "backend/validation/rule_engine.py",
        "test_file": "tests/test_rule_engine.py",
        "entries": [
            ("HardwareRuleEngine",     "class",  "RS-485 termination, PWM pin validation"),
            ("HardwareRuleEngine.run", "method", "Runs only rules listed in ir.validation_rules"),
        ],
    },
    "api/auth": {
        "file": "backend/api/routes/auth.py",
        "test_file": "tests/test_auth.py",
        "entries": [
            ("register",        "function", "POST /auth/register → JWT token"),
            ("login",           "function", "POST /auth/login (OAuth2 form) → JWT token"),
            ("get_current_user","function", "JWT dependency — validates Bearer token on every request"),
        ],
    },
}

STATUS_ICON = {
    "verified_done": "✅",
    "broken":        "❌",
    "stub":          "🔲",
    "untested":      "⚠️ ",
    "not_started":   "⬜",
}


# ── AST extraction ────────────────────────────────────────────────────────────
def extract_symbols(filepath: Path) -> dict:
    """Returns {name: {type, signature, description, is_stub, line}} for all
    public classes and their methods (and top-level functions)."""
    if not filepath.exists():
        return {}
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except SyntaxError as e:
        print(f"  ⚠ SyntaxError in {filepath.name}: {e}")
        return {}

    symbols = {}

    def is_stub(node):
        if len(node.body) == 1:
            b = node.body[0]
            if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant):
                return True  # docstring only OR `...`
            if isinstance(b, ast.Pass):
                return True
        if len(node.body) == 2:
            b0, b1 = node.body
            # docstring + pass  or  docstring + ...
            if isinstance(b0, ast.Expr) and isinstance(b0.value, ast.Constant):
                if isinstance(b1, ast.Pass):
                    return True
                if isinstance(b1, ast.Expr) and isinstance(b1.value, ast.Constant):
                    return True
        return False

    def sig(node):
        args = []
        for arg in node.args.args:
            if arg.arg == "self":
                continue
            ann = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
            args.append(f"{arg.arg}{ann}")
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return f"({', '.join(args)}){ret}"

    def doc_first_line(node):
        d = ast.get_docstring(node) or ""
        return d.split("\n")[0].strip()

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                symbols[node.name] = {
                    "type": "function",
                    "signature": node.name + sig(node),
                    "description": doc_first_line(node),
                    "is_stub": is_stub(node),
                    "line": node.lineno,
                }
        elif isinstance(node, ast.ClassDef):
            symbols[node.name] = {
                "type": "class",
                "description": doc_first_line(node),
                "is_stub": False,
                "line": node.lineno,
            }
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not child.name.startswith("_"):
                        key = f"{node.name}.{child.name}"
                        symbols[key] = {
                            "type": "method",
                            "signature": f"{node.name}.{child.name}{sig(child)}",
                            "description": doc_first_line(child),
                            "is_stub": is_stub(child),
                            "line": child.lineno,
                        }

    return symbols


# ── Test runner ───────────────────────────────────────────────────────────────
def run_tests_by_file() -> dict:
    """Returns {test_filename: 'passing'|'failing'|'empty'}."""
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    try:
        r = subprocess.run(
            ["python", "-m", "pytest", "tests/", "--tb=no", "-v", "--no-header"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env=env, timeout=180,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}

    raw = r.stdout + r.stderr
    file_status = {}
    lines = raw.splitlines()

    for tf in TESTS.glob("test_*.py"):
        name = tf.name
        mentioned = any(name in line for line in lines)
        if not mentioned:
            file_status[name] = "empty"
            continue
        has_failures = any("FAILED" in line and name in line for line in lines)
        file_status[name] = "failing" if has_failures else "passing"

    return file_status


# ── Status derivation ─────────────────────────────────────────────────────────
def derive_status(symbol_key: str, symbols: dict, test_file_status: str) -> str:
    if symbol_key not in symbols:
        return "not_started"
    if symbols[symbol_key].get("is_stub"):
        return "stub"
    if test_file_status == "passing":
        return "verified_done"
    if test_file_status == "failing":
        return "broken"
    return "untested"


# ── YAML writer ───────────────────────────────────────────────────────────────
def write_yaml_manual(data: dict, path: Path):
    """Write a clean YAML file without requiring PyYAML for basic structures."""
    try:
        import yaml
        path.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return
    except ImportError:
        pass

    # Manual YAML writer (covers dict/list/str/int/float/bool/None)
    import json
    # Fall back to JSON-compatible subset
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  ℹ PyYAML not installed — wrote JSON. pip install pyyaml for proper YAML.")


# ── Main ──────────────────────────────────────────────────────────────────────
def generate():
    print("\n📋  progress_gen.py — function-level scan\n")

    file_status = run_tests_by_file()
    print(f"  Test files scanned: {len(file_status)}")
    for fname, status in sorted(file_status.items()):
        icon = {"passing": "✅", "failing": "❌", "empty": "⬜"}.get(status, "?")
        print(f"  {icon} {fname}: {status}")
    print()

    progress = {
        "_note": "DERIVED. Run: python .claude/shared-memory/tools/progress_gen.py",
        "_layer": "LAYER 4 (Progress) — class/method-level reality",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "project": "Circuit OS",
        "files": {},
        "summary": {},
    }

    counts = {"verified_done": 0, "broken": 0, "stub": 0, "untested": 0, "not_started": 0}

    for module_key, cfg in PLANNED.items():
        filepath   = PROJECT_ROOT / cfg["file"]
        symbols    = extract_symbols(filepath)
        test_fname = Path(cfg["test_file"]).name if cfg["test_file"] else None
        tf_status  = file_status.get(test_fname, "no_test") if test_fname else "no_test"

        file_entry = {
            "file": cfg["file"],
            "exists": filepath.exists(),
            "test_file": cfg["test_file"],
            "test_file_status": tf_status,
            "entries": {},
        }

        print(f"📄 {module_key}  ({filepath.name}):")
        entry_statuses = []

        for symbol_key, symbol_type, planned_desc in cfg["entries"]:
            status = derive_status(symbol_key, symbols, tf_status)
            counts[status] += 1
            entry_statuses.append(status)

            sym = symbols.get(symbol_key, {})
            icon = STATUS_ICON[status]
            print(f"   {icon} {symbol_key}: {status}")

            file_entry["entries"][symbol_key] = {
                "status": status,
                "type": symbol_type,
                "description": sym.get("description") or planned_desc,
                "signature": sym.get("signature"),
                "line": sym.get("line"),
                "test_file": cfg["test_file"],
            }

        # File-level rollup
        if all(s == "verified_done" for s in entry_statuses):
            file_entry["module_status"] = "done"
        elif any(s in ("verified_done", "untested") for s in entry_statuses):
            file_entry["module_status"] = "in_progress"
        elif any(s == "broken" for s in entry_statuses):
            file_entry["module_status"] = "broken"
        else:
            file_entry["module_status"] = "not_started"

        progress["files"][module_key] = file_entry
        print()

    total = sum(counts.values())
    pct = round(counts["verified_done"] / max(total, 1) * 100, 1)
    progress["summary"] = {
        "entries_total": total,
        "entries_verified_done": counts["verified_done"],
        "entries_broken": counts["broken"],
        "entries_stub": counts["stub"],
        "entries_untested": counts["untested"],
        "entries_not_started": counts["not_started"],
        "pct_verified": pct,
    }

    out_path = MEMORY_ROOT / "progress.yaml"
    write_yaml_manual(progress, out_path)
    print(f"✅  progress.yaml written → {out_path}")
    print(f"📊  Summary: {counts['verified_done']}/{total} verified done ({pct}%), "
          f"{counts['broken']} broken, {counts['not_started']} not started")


if __name__ == "__main__":
    generate()
