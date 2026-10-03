"""
Compose a project — several blocks on one board — and write what it builds.

    python scripts/compose_project.py docs/projects/climate_status.json out/climate_status

Writes `<name>.kicad_sch` (open it in KiCad), `<name>.cir` (the SPICE netlist),
`<name>_bom.csv`, and `<name>_blocks.txt`: each block's pin, its parts as
renumbered on the board, and the properties its own generator proved. M1 of
`COMPOSITION_PLAN.md` — no firmware yet (M2), and nothing claimed about the
board as a whole (M4).
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
from generators.compose import CompositionRefused, Project, compose  # noqa: E402
from generators.netlist.spice import SpiceNetlistGenerator  # noqa: E402
from generators.registry import default_registry  # noqa: E402
from generators.schematic.kicad import KiCadSchematicGenerator  # noqa: E402


def write(project: Project, folder: Path) -> list:
    result = compose(default_registry(), project)
    board = result.circuit
    name = folder.name
    folder.mkdir(parents=True, exist_ok=True)
    paths = []

    def put(suffix: str, text: str) -> None:
        path = folder / f"{name}{suffix}"
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)

    put(".kicad_sch", KiCadSchematicGenerator().generate(board))
    put(".cir", SpiceNetlistGenerator().generate(board))

    rows = BOMCompiler().compile(board)
    path = folder / f"{name}_bom.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        out = csv.writer(f)
        out.writerow(["ref", "part_number", "manufacturer", "package", "value", "price", "currency", "why"])
        for r in rows:
            out.writerow([r["id"], r["part_number"], r["manufacturer"], r["package"], r["value"] or "",
                          r["unit_price"] if r["price_known"] else "", r["currency"] or "", r["justification"]])
    paths.append(path)

    lines = [f"{board.intent} — {board.target_mcu}", ""]
    for b in result.blocks:
        renamed = ", ".join(f"{old}→{new}" for old, new in b.parts.items() if old != new) or "none"
        lines += [f"[{b.id}] {b.function} on {b.pin}  ({b.generator})", f"  parts renumbered: {renamed}"]
        for p in b.circuit.validation_coverage["properties"]:
            lines.append(f"  {p['status']:>8} {p['grade']}  {p['english']}")
        lines.append("")
    lines.append("Board-level claims (shared rail current, cross-block loading): not assessed until M4.")
    put("_blocks.txt", "\n".join(lines) + "\n")
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
