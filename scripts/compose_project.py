"""
Compose a project — several blocks on one board — and write what it builds.

    python scripts/compose_project.py docs/projects/room_monitor.json out/room_monitor

Writes `<name>.kicad_sch` (open it in KiCad), `<name>.cir` (the SPICE netlist),
`<name>_bom.csv`, `firmware/` (a PlatformIO project: `cd firmware && pio run -t
upload`), and `<name>_claims.txt`: each block's pin and parts, the behaviour
the firmware runs, and every claim on the board — each block's own and the
board's — including what is not assessed. `COMPOSITION_PLAN.md` M1–M4.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
for key, value in {"ANTHROPIC_API_KEY": "", "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
                   "REDIS_URL": "redis://localhost:6379/0", "SECRET_KEY": "x" * 40}.items():
    os.environ.setdefault(key, value)

from generators.bom.compiler import BOMCompiler  # noqa: E402
from generators.compose import CompositionRefused, Project, board_coverage, compose  # noqa: E402
from generators.firmware.composite import composite_project  # noqa: E402
from generators.netlist.spice import SpiceNetlistGenerator  # noqa: E402
from generators.registry import default_registry  # noqa: E402
from generators.schematic.kicad import KiCadSchematicGenerator  # noqa: E402


def write(project: Project, folder: Path) -> list:
    result = compose(default_registry(), project)
    board = result.circuit
    name = folder.name
    folder.mkdir(parents=True, exist_ok=True)
    paths = []

    def put(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)

    put(folder / f"{name}.kicad_sch", KiCadSchematicGenerator().generate(board))
    put(folder / f"{name}.cir", SpiceNetlistGenerator().generate(board))

    rows = BOMCompiler().compile(board)
    path = folder / f"{name}_bom.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        out = csv.writer(f)
        out.writerow(["ref", "part_number", "manufacturer", "package", "value", "price", "currency", "why"])
        for r in rows:
            out.writerow([r["id"], r["part_number"], r["manufacturer"], r["package"], r["value"] or "",
                          r["unit_price"] if r["price_known"] else "", r["currency"] or "", r["justification"]])
    paths.append(path)

    for file, content in composite_project(result).files:
        put(folder / "firmware" / file, content)

    coverage = board_coverage(result)
    lines = [f"{board.intent} — {board.target_mcu}",
             f"grade floor {coverage['grade_floor']}; open doubts {', '.join(coverage['open_defeaters'])}; "
             f"not assessed: {', '.join(coverage['not_assessed']) or 'none'}", ""]
    for b in coverage["blocks"]:
        lines.append(f"[{b['id']}] {b['function']} on {b['pin']} ({b['generator']}): {', '.join(b['parts'])}")
    lines += ["", "Behaviour the firmware runs:"]
    lines += [f"  {n}. {rule}" for n, rule in enumerate(coverage["behaviour"], 1)] or ["  (none)"]
    lines += ["", "Claims:"]
    for c in coverage["claims"]:
        if c["critical"] or c["verdict"] == "not_assessed":
            lines.append(f"  {c['verdict']:>16} {c['grade'] or '':>2}  {c['claim']}")
    put(folder / f"{name}_claims.txt", "\n".join(lines) + "\n")
    return paths


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    try:
        spec = Project.model_validate(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
        for path in write(spec, Path(sys.argv[2])):
            print(f"wrote {path}")
    except CompositionRefused as exc:
        raise SystemExit("refused:\n  " + "\n  ".join(exc.reasons))
