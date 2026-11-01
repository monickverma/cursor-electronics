"""
readback.py — hand the fab files and the IR's pad table to the read-back stage.

Stage 7 of `reports/PCB verification implementation plan.md`. The extractor
itself (`tools/readback/gerber_readback.py`) runs in its own Python 3.12
interpreter with Gerbonara and Shapely (owner decision 2026-10-17; Gerbonara
does not install on 3.11). This side only writes the pad table — reference,
pin, net, position, copper layers — in the files' frame, runs that interpreter,
and reads its JSON verdict. Nothing of the backend is imported over there.

The interpreter is READBACK_PYTHON, else `<repo>/.venv-readback`, made with:

    uv venv --python 3.12 .venv-readback
    uv pip install --python .venv-readback -r tools/readback/requirements.txt

Without it the stage did not run, and a caller that needs it must refuse.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from board_ir import Board
from kicad_export import copper_layers

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tools" / "readback" / "gerber_readback.py"
MIN_RING = 0.05        # mm of copper that must ring a plated hole for it to join layers


class ReadbackUnavailable(RuntimeError):
    """No Python 3.12 read-back interpreter on this machine."""


def find_python() -> str:
    env = os.environ.get("READBACK_PYTHON")
    cands = [env] if env else []
    venv = REPO / ".venv-readback"
    cands += [str(venv / "Scripts" / "python.exe"), str(venv / "bin" / "python")]
    for c in cands:
        if c and Path(c).is_file():
            return c
    raise ReadbackUnavailable("no read-back interpreter (set READBACK_PYTHON or create "
                              ".venv-readback from tools/readback/requirements.txt)")


def available() -> bool:
    try:
        find_python()
        return True
    except ReadbackUnavailable:
        return False


def to_file_frame(board: Board, x: float, y: float) -> tuple[float, float]:
    """IR point -> the frame KiCad's Gerber, drill and position files use
    (they negate the board's Y; see kicad_fab manifest)."""
    return x, y - board.outline_h


def pad_table(board: Board) -> dict:
    cu = copper_layers(board)
    pads = []
    for p in board.pads():
        x, y = to_file_frame(board, p.x, p.y)
        through = p.shape == "th"
        pads.append({"ref": p.ref, "pin": p.pin, "net": p.net, "x": x, "y": y,
                     "through": through, "layers": cu if through else [p.layer]})
    vias = []
    for v in board.vias:
        x, y = to_file_frame(board, v.x, v.y)
        vias.append({"net": v.net, "x": x, "y": y})
    return {"copper": cu, "min_ring": MIN_RING, "pads": pads, "vias": vias}


@dataclass
class Readback:
    ran: bool
    result: dict = field(default_factory=dict)
    refusals: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.ran and not self.refusals

    def to_dict(self) -> dict:
        return {"ran": self.ran, "ok": self.ok, "refusals": self.refusals, **self.result}


def _say(p: dict) -> str:
    k = p.get("kind")
    if k == "open":
        return f"open: net {p['net']} is in {p['groups']} separate pieces of copper"
    if k == "short":
        return f"short: nets {p['nets']} share one piece of copper"
    if k == "off_copper":
        return f"pad {p['ref']}.{p['pin']} ({p['net']}) is not on {p['layer']} copper"
    where = f" at {p['at']}" if "at" in p else ""
    return f"{k}{where}: {p.get('detail', '')}".rstrip(": ")


def run_readback(board: Board, fab_dir: str | Path, timeout: float = 300.0) -> Readback:
    """Read the fab files back and compare them with the board's pad table."""
    fab = Path(fab_dir)
    try:
        py = find_python()
    except ReadbackUnavailable as e:
        return Readback(False, refusals=[f"read-back did not run: {e}"])
    spec = fab / "readback_pads.json"
    spec.write_text(json.dumps(pad_table(board)), encoding="utf-8")
    try:
        p = subprocess.run([py, "-I", str(SCRIPT), str(fab), str(spec)],
                           capture_output=True, text=True, timeout=timeout)
    finally:
        spec.unlink(missing_ok=True)
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError:
        return Readback(False, refusals=[f"read-back did not run (exit {p.returncode}): "
                                         f"{(p.stderr or p.stdout).strip()[-300:]}"])
    if "error" in out:
        return Readback(False, out, [f"read-back failed: {out['error']}"])
    return Readback(True, out, [_say(q) for q in out.get("problems", [])])


if __name__ == "__main__":                              # python readback.py board.json fab/
    b = Board.from_json(Path(sys.argv[1]).read_text())
    print(json.dumps(run_readback(b, sys.argv[2]).to_dict(), indent=2))
