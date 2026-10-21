"""
kicad_cli.py — KiCad as a separate process: find it, pin it, round-trip a board.

Stage 3 of `reports/PCB verification implementation plan.md`. KiCad is a
runtime dependency used only as a subprocess (decision 6): pinned to 10.0.1,
its version recorded in every result, never imported.

`round_trip` writes the project (`kicad_export`), has KiCad load and re-save it
(`pcb upgrade --force`), then reads back what KiCad made of it and compares it
with the IR. Every failure is a writer bug, reported as one — the board itself
is judged later, by `kicad_drc`.

What KiCad says back is checked two ways:
  * the re-saved file: the same footprints, pads, segments, vias and zones,
    and the same net names, as the IR;
  * KiCad's own IPC-D-356 export: every pad where the IR has it, with the IR's
    size, in KiCad's frame. That is KiCad computing pad placement, not us, so a
    rotation or flip written wrongly shows up here. IPC-D-356 is used only for
    geometry; its net names are cut to 14 characters and are never keyed on.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from board_ir import Board
from kicad_export import KICAD_VERSION, FILE_VERSION, from_kicad, write_pcb, write_pro

_DEFAULT_WIN = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
POS_TOL = 0.005          # mm; IPC-D-356 resolves 0.0001 in = 2.54 µm


class KiCadUnavailable(RuntimeError):
    """No kicad-cli on this machine. Callers report the stage as not run."""


class KiCadFailed(RuntimeError):
    """kicad-cli ran and failed: an infrastructure or writer failure."""


def find_cli() -> str:
    """KICAD_CLI, else kicad-cli on PATH, else the default Windows install."""
    for cand in (os.environ.get("KICAD_CLI"), shutil.which("kicad-cli"), _DEFAULT_WIN):
        if cand and Path(cand).is_file():
            return cand
    raise KiCadUnavailable("kicad-cli not found (set KICAD_CLI)")


def available() -> bool:
    try:
        find_cli()
        return True
    except KiCadUnavailable:
        return False


def run(args: list[str], timeout: float = 120.0, cwd: str | Path | None = None
        ) -> subprocess.CompletedProcess:
    return subprocess.run([find_cli(), *args], capture_output=True, text=True,
                          timeout=timeout, cwd=cwd)


_version_cache: str | None = None


def version() -> str:
    global _version_cache
    if _version_cache is None:
        _version_cache = run(["version"], timeout=30).stdout.strip()
    return _version_cache


# ─────────────────────────────────────────────────────────────────────────────
# a minimal s-expression reader — enough to count what KiCad wrote back
# ─────────────────────────────────────────────────────────────────────────────
_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')


def parse_sexpr(text: str) -> list:
    stack: list[list] = [[]]
    for m in _TOK.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif t.startswith('"'):
            stack[-1].append(t[1:-1].replace('\\"', '"').replace("\\\\", "\\"))
        else:
            stack[-1].append(t)
    if len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError("unbalanced s-expression")
    return stack[0][0]


def children(node: list, key: str) -> list[list]:
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def child(node: list, key: str) -> list | None:
    found = children(node, key)
    return found[0] if found else None


def board_inventory(pcb: list) -> dict:
    """What a .kicad_pcb holds, counted the way the IR counts it."""
    fps = children(pcb, "footprint")
    pads = [p for f in fps for p in children(f, "pad")]
    zones = children(pcb, "zone")
    nets = set()
    for item in pads + children(pcb, "segment") + children(pcb, "via") + zones:
        n = child(item, "net")
        if n and len(n) > 1 and n[-1]:
            nets.add(n[-1])
    return {"version": int(child(pcb, "version")[1]),
            "footprints": len(fps), "pads": len(pads),
            "segments": len(children(pcb, "segment")),
            "vias": len(children(pcb, "via")),
            "planes": sum(1 for z in zones if not child(z, "keepout")),
            "keepouts": sum(1 for z in zones if child(z, "keepout")),
            "nets": sorted(nets)}


def ir_inventory(board: Board) -> dict:
    import math
    segs = sum(1 for t in board.tracks for a, b in zip(t.points, t.points[1:])
               if math.dist(a, b) >= 1e-9)
    nets = {p.net for p in board.pads() if p.net}
    nets |= {t.net for t in board.tracks} | {v.net for v in board.vias}
    nets |= board.plane_nets()
    return {"version": FILE_VERSION,
            "footprints": len(board.components), "pads": len(board.pads()),
            "segments": segs, "vias": len(board.vias),
            "planes": sum(1 for l in board.layers if l.plane_net),
            "keepouts": len(board.keepouts), "nets": sorted(nets)}


# ─────────────────────────────────────────────────────────────────────────────
# IPC-D-356: KiCad's own placement of every pad
# ─────────────────────────────────────────────────────────────────────────────
_D356 = re.compile(r"X([+-]\d+)Y([+-]\d+)X(\d+)Y(\d+)R(\d+)")


def ipc356_pads(text: str) -> list[dict]:
    """Pad records of an IPC-D-356 file in KiCad's frame (mm, y down).

    Fixed columns per IPC-D-356: net 4-17, reference 21-26, pin 28-31; the
    numbers are 0.0001 in. KiCad writes Y up (negated), sizes before rotation,
    a round pad as its diameter with height 0, and every via under "VIA"."""
    out = []
    for line in text.splitlines():
        if not (line.startswith("317") or line.startswith("327")):
            continue
        m = _D356.search(line)
        if not m:
            continue
        x, y, w, h, r = (int(g) for g in m.groups())
        w_mm, h_mm = w * 0.00254, h * 0.00254
        if h == 0:                         # a round pad gives its diameter only
            h_mm = w_mm
        if r % 180 == 90:
            w_mm, h_mm = h_mm, w_mm
        out.append({"ref": line[20:26].strip(), "pin": line[27:31].strip().lstrip("-"),
                    "x": x * 0.00254, "y": -y * 0.00254, "w": w_mm, "h": h_mm,
                    "through": line.startswith("317")})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# the round trip
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class RoundTrip:
    pcb: Path
    kicad_version: str
    problems: list[str] = field(default_factory=list)
    inventory: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems

    def to_dict(self) -> dict:
        return {"pcb": str(self.pcb), "kicad_version": self.kicad_version,
                "ok": self.ok, "problems": self.problems,
                "inventory": self.inventory}


def write_project(board: Board, out_dir: str | Path, name: str = "board",
                  severities: dict[str, str] | None = None,
                  dru: str | None = None) -> Path:
    """Write <name>.kicad_pcb, .kicad_pro and (if given) .kicad_dru; return
    the board path. KiCad finds the sibling files by the shared base name."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pcb = out / f"{name}.kicad_pcb"
    pcb.write_text(write_pcb(board), encoding="utf-8")
    (out / f"{name}.kicad_pro").write_text(write_pro(board, name, severities),
                                           encoding="utf-8")
    if dru is not None:
        (out / f"{name}.kicad_dru").write_text(dru, encoding="utf-8")
    return pcb


def round_trip(board: Board, out_dir: str | Path, name: str = "board",
               severities: dict[str, str] | None = None,
               dru: str | None = None) -> RoundTrip:
    """Write the project, have KiCad re-save it, and check what came back."""
    pcb = write_project(board, out_dir, name, severities, dru)
    rt = RoundTrip(pcb=pcb, kicad_version=version())
    if rt.kicad_version != KICAD_VERSION:
        rt.problems.append(f"kicad-cli is {rt.kicad_version}; the writer is "
                           f"proven against {KICAD_VERSION}")
    p = run(["pcb", "upgrade", "--force", str(pcb)])
    if p.returncode != 0:
        # A file KiCad cannot load segfaults 10.0.1's upgrade (exit 139) or
        # exits 3 elsewhere; any non-zero is the same verdict.
        rt.problems.append(f"KiCad could not load or re-save the board "
                           f"(exit {p.returncode}): {(p.stderr or p.stdout).strip()[:300]}")
        return rt

    got = board_inventory(parse_sexpr(pcb.read_text(encoding="utf-8")))
    want = ir_inventory(board)
    rt.inventory = got
    for k in want:
        if got[k] != want[k]:
            rt.problems.append(f"re-saved board has {k} = {got[k]!r}, IR has {want[k]!r}")

    d356 = pcb.with_suffix(".d356")
    p = run(["pcb", "export", "ipcd356", "-o", str(d356), str(pcb)])
    if p.returncode != 0:
        rt.problems.append(f"IPC-D-356 export failed (exit {p.returncode})")
        return rt
    rt.problems += compare_pads(board, ipc356_pads(d356.read_text(encoding="utf-8")))
    return rt


def compare_pads(board: Board, recs: list[dict]) -> list[str]:
    """Every IR pad must have a KiCad pad record at its position, with its size,
    under its reference and pin (both possibly truncated by IPC-D-356)."""
    problems = []
    unused = [r for r in recs if r["ref"] != "VIA"]
    vias = [r for r in recs if r["ref"] == "VIA"]
    for v in board.vias:
        X, Y = v.x, board.outline_h - v.y
        hit = next((r for r in vias if abs(r["x"] - X) <= POS_TOL
                    and abs(r["y"] - Y) <= POS_TOL), None)
        if hit is None:
            problems.append(f"via {v.net}: KiCad has no via at IR ({v.x:.3f}, {v.y:.3f})")
        else:
            vias.remove(hit)
    for r in vias:
        x, y = from_kicad(board, r["x"], r["y"])
        problems.append(f"KiCad via at ({x:.3f}, {y:.3f}) is not in the IR")
    for p in board.pads():
        X, Y = p.x, board.outline_h - p.y            # to_kicad
        hit = next((r for r in unused
                    if abs(r["x"] - X) <= POS_TOL and abs(r["y"] - Y) <= POS_TOL
                    and p.ref.startswith(r["ref"]) and p.pin.startswith(r["pin"])),
                   None)
        if hit is None:
            problems.append(f"pad {p.ref}.{p.pin}: KiCad has no pad at IR "
                            f"({p.x:.3f}, {p.y:.3f})")
            continue
        unused.remove(hit)
        if abs(hit["w"] - p.w) > POS_TOL or abs(hit["h"] - p.h) > POS_TOL:
            problems.append(f"pad {p.ref}.{p.pin}: KiCad size {hit['w']:.3f} x "
                            f"{hit['h']:.3f}, IR {p.w:.3f} x {p.h:.3f}")
        if hit["through"] != (p.shape == "th"):
            problems.append(f"pad {p.ref}.{p.pin}: plating differs (IR {p.shape})")
    for r in unused:
        x, y = from_kicad(board, r["x"], r["y"])
        problems.append(f"KiCad pad {r['ref']}.{r['pin']} at ({x:.3f}, {y:.3f}) "
                        f"is not in the IR")
    return problems
