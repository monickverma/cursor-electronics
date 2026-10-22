"""
stage_artifacts.py — hand the seeded boards to the overlooker as CAD files.

WHY
---
The overlooker is a black-box engineer. It judges the product the way an
engineer would: open the board in KiCad, read it, decide. A JSON blob of
pads and tracks is not a board an engineer can open. A `.kicad_pcb` is.

So each seeded board is written out as a real KiCad 10 project — the board
file, the project file, and a DRC report from KiCad's own rule engine. The
overlooker gets a folder it can open. The folder name says nothing about
which defect is in it, because the name is the one thing that would tell it.

WHAT THIS DOES NOT DO
---------------------
It does not decide whether a defect was caught. That is
`verify_calibration.py` (our own verifier) and `score_overlooker.py` (the
overlooker's own report, scored against the key). This file only puts the
board in the engineer's hands.

    python .claude/shared-memory/alpha/stage_artifacts.py
    python .claude/shared-memory/alpha/stage_artifacts.py --check
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
FIXTURES = REPO / "tests" / "fixtures" / "alpha_known_bad"
OUT = FIXTURES / "artifacts"

sys.path.insert(0, str(BACKEND / "pcb_engine"))

KICAD_CLI = Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")

#: The request the overlooker makes for each seeded case. Plain engineer
#: requests. None of them says a defect was planted, and none of them says
#: which board is which. Kept in one place so the request and the board it
#: goes with cannot drift apart.
REQUESTS: dict[str, str] = {
    "cut_track": (
        "An Arduino Uno reads a DHT22 sensor on a 2 metre cable, drives a relay "
        "through a 2N2222A, and lights an LED on the same board. Lay the board "
        "out and check it before you would send it to a fab."
    ),
    "deleted_via": (
        "An Arduino Uno reads a DHT22 sensor on a 2 metre cable, drives a relay "
        "through a 2N2222A, and lights an LED on the same board. Lay the board "
        "out and check it before you would send it to a fab."
    ),
    "bridged_nets": (
        "An Arduino Uno reads a DHT22 sensor on a 2 metre cable, drives a relay "
        "through a 2N2222A, and lights an LED on the same board. Lay the board "
        "out and check it before you would send it to a fab."
    ),
    "swapped_pins": (
        "An Arduino Uno reads a DHT22 sensor on a 2 metre cable, drives a relay "
        "through a 2N2222A, and lights an LED on the same board. Lay the board "
        "out and check it before you would send it to a fab."
    ),
    "reversed_diode": (
        "An Arduino Uno drives a 30 mA inductive load through a transistor, with "
        "a flyback diode across the load. Lay the board out and check it before "
        "you would send it to a fab."
    ),
    "mains_gap": (
        "An Arduino Uno drives a relay whose contact switches mains, and reads "
        "a DHT22 sensor on the same board. Lay the board out and check it "
        "before you would send it to a fab."
    ),
    "wrong_cap_value": (
        "An Arduino Uno reads a DHT22 sensor on a 2 metre cable with a 100 nF "
        "decoupling capacitor, drives a relay through a 2N2222A, and lights an "
        "LED on the same board. Lay the board out and check it before you would "
        "send it to a fab."
    ),
}


def _cases() -> list[Path]:
    """The seeded cases: a directory that holds the script that seeded it."""
    return sorted(
        p for p in FIXTURES.iterdir()
        if p.is_dir() and (p / "mutate.py").exists() and (p / "board_defective.json").exists()
    )


def _kicad_drc(pcb: Path, out: Path) -> dict | None:
    """KiCad's own DRC on a board file. The second rule engine."""
    if not KICAD_CLI.exists():
        return None
    try:
        subprocess.run(
            [str(KICAD_CLI), "pcb", "drc", "--severity-error", "--severity-warning",
             "--format", "json", "-o", str(out), str(pcb)],
            capture_output=True, timeout=180, check=False,
        )
    except Exception:  # noqa: BLE001
        return None
    if not out.exists():
        return None
    try:
        return json.loads(out.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _summarise(drc: dict | None) -> dict:
    """The DRC report, counted. A count is what an engineer reads first."""
    if drc is None:
        return {"available": False}
    unconnected = drc.get("unconnected_items") or []
    violations = drc.get("violations") or []
    by_type: dict[str, int] = {}
    for v in violations:
        t = v.get("type", "?")
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "available": True,
        "kicad_version": drc.get("kicad_version"),
        "violations": len(violations),
        "unconnected_items": len(unconnected),
        "by_type": by_type,
        "severity_error_violations": sum(
            1 for v in violations if v.get("severity") == "error"
        ),
    }


def _numbering() -> dict[str, str]:
    """Case -> the folder number it already has. Numbers are never reused.

    The staged folder is what a finding names, and the key maps a finding back
    to a case by that name. If the numbering were positional — sorted cases,
    1, 2, 3 — then adding a case would renumber every case after it, and a
    finding written against `artifacts/board_03` would suddenly be scored
    against a different defect. The A1 number would be wrong and nothing
    would say so.

    So the mapping file is the source of truth: a case keeps the number it
    was first given, and a new case takes the next free one.
    """
    path = OUT / "MAPPING.json"
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, str] = {}
    for row in rows:
        folder = str(row.get("folder", ""))
        case = str(row.get("case", ""))
        if folder and case:
            out[case] = folder
    return out


def stage(check: bool = False) -> int:
    try:
        from board_ir import Board
        import kicad_export as kx
    except Exception as exc:  # noqa: BLE001
        print(f"the KiCad export is not available: {type(exc).__name__}: {exc}")
        print("It lands with the peer's export stages. Run the overlooker when")
        print("they are merged, or hand the overlooker the board JSON.")
        return 1

    previous = _numbering()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # A case that already had a number keeps it; a new one takes the next
    # free number. Never reuse, never renumber.
    used = set(previous.values())
    next_free = 1
    numbering: dict[str, str] = {}
    for case in _cases():
        if case.name in previous:
            numbering[case.name] = previous[case.name]
            continue
        while f"board_{next_free:02d}" in used:
            next_free += 1
        numbering[case.name] = f"board_{next_free:02d}"
        used.add(numbering[case.name])
        next_free += 1

    presentation = []
    for case in _cases():
        # The file name carries nothing about the case. The mapping that
        # decodes it stays here and is NOT handed to the overlooker.
        stem = numbering[case.name]
        folder = OUT / stem
        folder.mkdir()

        board = Board.from_json((case / "board_defective.json").read_text(encoding="utf-8"))
        (folder / f"{stem}.kicad_pcb").write_text(kx.write_pcb(board), encoding="utf-8")
        (folder / f"{stem}.kicad_pro").write_text(kx.write_pro(board, stem), encoding="utf-8")
        # The Board IR as the product's own source of truth, for reading nets
        # and part attributes.
        (folder / "board_ir.json").write_text(
            json.dumps(json.loads(board.to_json(indent=2)), indent=2) + "\n", encoding="utf-8")

        drc = _kicad_drc(folder / f"{stem}.kicad_pcb", folder / "drc.json")
        summary = _summarise(drc)
        (folder / "drc_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        manifest = json.loads((case / "manifest.json").read_text(encoding="utf-8"))
        presentation.append({
            "case": case.name,
            "folder": stem,
            "request": REQUESTS.get(case.name, ""),
            "defect_class": manifest.get("defect_class"),
            "critical": bool(manifest.get("critical")),
            "kicad_drc": summary,
        })

    (OUT / "presentation.json").write_text(
        json.dumps(presentation, indent=2) + "\n", encoding="utf-8")
    mapping = [{"folder": p["folder"], "case": p["case"]} for p in presentation]
    (OUT / "MAPPING.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")

    print(f"staged {len(presentation)} board(s) in {OUT}")
    for row in presentation:
        d = row["kicad_drc"]
        drc_txt = ("no KiCad" if not d.get("available")
                   else f"{d['violations']} violations, {d['unconnected_items']} unconnected")
        print(f"  {row['folder']:<12} {row['case']:<18} {drc_txt}")
    print()
    print("The folder names carry no case information. The mapping is in MAPPING.json.")
    print("DO NOT hand MAPPING.json to the overlooker.")
    print("Numbers are never reused: a case added later takes the next free one,")
    print("so a finding written against one board always names that board.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what would be staged and exit")
    raise SystemExit(stage(check=ap.parse_args().check))
