"""
kicad_fab.py — the files a fab would be sent, exported by KiCad from our board.

Stage 6 of `reports/PCB verification implementation plan.md`. Owner decision of
2026-10-17 (plan, decision 1): a board that failed is still shown, but its
fabrication files are REFUSED here. "Failed" means any of:

  * verify.py found a decidable fault (Report.ok is False);
  * the writer round trip failed (KiCad could not load the board as written);
  * KiCad's DRC refused it (kicad_drc: sentinel missing, required rule fired,
    required check skipped, DRC did not run);
  * the exported files, read back into copper (readback.py, stage 7), show an
    open, a short, a pad off copper or a label that disagrees with the IR — or
    the read-back could not run.

A refusal writes no fab file at all — a half-written fab directory is a set of
files someone could still upload. Any export command that exits non-zero is a
refusal too, and whatever it wrote is removed.

What is exported (kicad-cli 10.0.1): Gerber X2 for copper, mask, paste, silk
and the outline; Excellon drill with plated and non-plated holes in separate
files, millimetres; the position file as CSV in millimetres (its default is
inches); IPC-D-356. No auxiliary origin is set by the writer, so every file
shares one frame (kicad_export, FRAME). A manifest records each file's SHA-256,
the KiCad version and the hash of the board text, so a verdict can name exactly
the files it judged.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from board_ir import Board
import kicad_cli
import kicad_drc
from kicad_export import copper_layers
from readback import run_readback

FAB_LAYERS_FIXED = ["F.Paste", "B.Paste", "F.SilkS", "B.SilkS",
                    "F.Mask", "B.Mask", "Edge.Cuts"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class FabExport:
    refusals: list[str] = field(default_factory=list)
    files: dict[str, Path] = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)
    drc: dict = field(default_factory=dict)
    readback: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.refusals

    def to_dict(self) -> dict:
        return {"ok": self.ok, "refusals": self.refusals,
                "files": {k: str(v) for k, v in self.files.items()},
                "manifest": self.manifest, "drc": self.drc,
                "readback": self.readback}


def _verification_ok(board: Board, verification) -> tuple[bool, list[str]]:
    if verification is None:
        from verify import verify_board
        verification = verify_board(board)
    if isinstance(verification, dict):
        failed = verification.get("failed_checks") or [
            f.get("check") for f in verification.get("findings", [])
            if f.get("status") == "fail"]
        return bool(verification.get("ok", not failed)), [str(f) for f in failed]
    return verification.ok, [f.check for f in verification.failed()]


def export_fab(board: Board, out_dir: str | Path, name: str = "board",
               verification=None, rules: list[str] | tuple[str, ...] = ()) -> FabExport:
    """Gate the board, then export its fab files into <out_dir>/fab.

    `verification` is a verify.Report or its dict (as /pcb/compile returns it);
    None runs verify_board here. The KiCad project lands in <out_dir> and the
    fab files in <out_dir>/fab only when every gate passed."""
    out = Path(out_dir)
    res = FabExport()
    fab = out / "fab"
    if fab.exists():
        shutil.rmtree(fab)                 # never mix a new verdict with old files

    ok, failed = _verification_ok(board, verification)
    if not ok:
        res.refusals.append(f"board failed verification ({', '.join(failed) or 'see report'}); "
                            f"it is shown, but its fab files are refused (decision 2026-10-17)")

    rt, drc = kicad_drc.check_board(board, out, name, rules)
    if not rt.ok:
        res.refusals += [f"writer: {p}" for p in rt.problems]
    if drc is not None:
        res.drc = drc.to_dict()
        res.refusals += [f"KiCad DRC: {r}" for r in drc.refusals]
    if res.refusals:
        return res

    pcb = rt.pcb
    layers = ",".join(copper_layers(board) + FAB_LAYERS_FIXED)
    fab.mkdir(parents=True)
    steps = [
        ("gerbers", ["pcb", "export", "gerbers", "--layers", layers, "--check-zones",
                     "-o", str(fab) + "/", str(pcb)]),
        ("drill", ["pcb", "export", "drill", "--format", "excellon",
                   "--excellon-units", "mm", "--excellon-separate-th",
                   "--drill-origin", "absolute", "-o", str(fab) + "/", str(pcb)]),
        ("pos", ["pcb", "export", "pos", "--format", "csv", "--units", "mm",
                 "--side", "both", "-o", str(fab / f"{name}-pos.csv"), str(pcb)]),
        ("ipcd356", ["pcb", "export", "ipcd356", "-o", str(fab / f"{name}.d356"), str(pcb)]),
    ]
    for step, args in steps:
        p = kicad_cli.run(args)
        if p.returncode != 0:
            res.refusals.append(f"{step} export failed (kicad-cli exit {p.returncode}): "
                                f"{(p.stderr or p.stdout).strip()[:300]}")
            shutil.rmtree(fab, ignore_errors=True)
            return res

    for f in sorted(fab.iterdir()):
        res.files[f.name] = f
    expected = [f"{name}-{l.replace('.', '_')}" for l in copper_layers(board) + ["Edge.Cuts"]]
    missing = [e for e in expected if not any(n.startswith(e + ".") for n in res.files)]
    if missing:
        res.refusals.append(f"export wrote no file for {missing}")
        shutil.rmtree(fab, ignore_errors=True)
        res.files = {}
        return res

    # Stage 7: the files themselves, read back into copper, against the IR.
    # A fault only the files carry (a drill hit moved, a track lost in the
    # plot) is invisible to every check above; this is the one that sees it.
    rb = run_readback(board, fab)
    res.readback = rb.to_dict()
    if not rb.ok:
        res.refusals += [f"read-back: {r}" for r in rb.refusals]
        shutil.rmtree(fab, ignore_errors=True)
        res.files = {}
        return res

    res.manifest = {
        "kicad_version": rt.kicad_version,
        "board_sha256": _sha(pcb),
        # Gerber, drill and position files negate KiCad's Y (seen on 10.0.1)
        "frame": "files: X = x, Y = y - outline_h (mm, IR frame shifted); "
                 "board: X = x, Y = outline_h - y; no auxiliary origin",
        "outline_mm": [board.outline_w, board.outline_h],
        "files": {n: _sha(p) for n, p in res.files.items()},
    }
    (fab / "manifest.json").write_text(json.dumps(res.manifest, indent=2), encoding="utf-8")
    res.files["manifest.json"] = fab / "manifest.json"
    return res


def kicad_package(board: Board, verification=None, name: str | None = None) -> dict:
    """Everything KiCad-side about one board, as text for an API response
    (finding F-S2-R001-4): the project KiCad re-saved, its DRC and read-back
    verdicts, and the fab files — the last only when every gate passed.

    The board file is returned for a failed board too: a person fixing it must
    be able to open it in KiCad. Only the fab files are withheld. Nothing is
    kept on disk; the work directory is removed before returning."""
    import tempfile
    from kicad_export import write_pcb

    name = name or "board"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[:60] or "board"
    if not kicad_cli.available():
        return {"available": False,
                "reason": "kicad-cli is not installed on this server; the board file is "
                          "this writer's text, not re-saved by KiCad, and no fab file is given",
                "kicad_pcb": write_pcb(board), "fab": {"ok": False, "files": {},
                "refusals": ["KiCad not available: fab files are not exported unchecked"]}}
    work = Path(tempfile.mkdtemp(prefix="circuitos_kicad_"))
    try:
        res = export_fab(board, work, safe, verification)

        def text(p: Path) -> str | None:
            return p.read_text(encoding="utf-8") if p.exists() else None

        return {
            "available": True,
            "kicad_version": kicad_cli.version(),
            "name": safe,
            "kicad_pcb": text(work / f"{safe}.kicad_pcb") or write_pcb(board),
            "kicad_pro": text(work / f"{safe}.kicad_pro"),
            "kicad_dru": text(work / f"{safe}.kicad_dru"),
            "drc": res.drc,
            "readback": res.readback,
            "fab": {"ok": res.ok, "refusals": res.refusals, "manifest": res.manifest,
                    "files": {n: p.read_text(encoding="utf-8", errors="replace")
                              for n, p in res.files.items()} if res.ok else {}},
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)
