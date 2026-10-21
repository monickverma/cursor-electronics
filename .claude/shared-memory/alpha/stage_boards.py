"""
stage_boards.py — hand the seeded boards to the overlooker, one file per case.

WHY
---
Every seeded board has to reach the overlooker as a plain request, with the
defect's location unknown. The scorer, on the other hand, has to know which
finding belongs to which case. Those two wants pull in opposite directions:
the overlooker must not be able to tell case A from case B, and the scorer
must not mix them up.

This script resolves that. It writes each defective board to a file NAMED
for its case:

    boards/board_cut_track.json
    boards/board_reversed_diode.json
    ...

and writes a `presentation.json` next to them that says, for each case, the
request the overlooker is to make and which file it gets. The master session
reads the presentation to drive the run; the overlooker is given the REQUEST
and the FILE, and never the presentation, the key, or the case list.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not tell the overlooker which file is defective. Every board it
writes is the DEFECTIVE one, so the file name and every file the overlooker
can reach must carry nothing about the case. The names are opaque
(`board_01.json`), and the mapping that decodes them — the case id AND the
defect class — is written to `MAPPING.json`, a file the overlooker does not
get. `presentation.json` holds only the request and the file name.

That split is the point. A presentation that names the defect class is a
leak waiting to happen: a later run, a different agent, a curious read of the
folder, and the whole recall number is worthless because the answer was in
the prompt.

    python .claude/shared-memory/alpha/stage_boards.py
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "tests" / "fixtures" / "alpha_known_bad"
OUT = FIXTURES / "boards"

#: The request the overlooker makes for each seeded case. These are plain
#: engineer requests. None of them says a defect was planted, and none of
#: them says which board is which.
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
    return sorted(
        p for p in FIXTURES.iterdir()
        if p.is_dir() and (p / "manifest.json").exists() and (p / "board_defective.json").exists()
    )


def stage() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    presentation = []
    mapping = []
    for i, case in enumerate(_cases(), start=1):
        board = json.loads((case / "board_defective.json").read_text(encoding="utf-8"))
        # The name the overlooker sees carries no information about the case.
        # The mapping that decodes it is written separately and is NOT handed
        # to the overlooker.
        filename = f"board_{i:02d}.json"
        (OUT / filename).write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")

        manifest = json.loads((case / "manifest.json").read_text(encoding="utf-8"))
        presentation.append({
            "file": filename,
            "request": REQUESTS.get(case.name, ""),
        })
        mapping.append({
            "file": filename,
            "case": case.name,
            "defect_class": manifest.get("defect_class"),
            "critical": bool(manifest.get("critical")),
        })

    (OUT / "presentation.json").write_text(
        json.dumps(presentation, indent=2) + "\n", encoding="utf-8")
    (OUT / "MAPPING.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")

    print(f"staged {len(presentation)} board(s) in {OUT}")
    for row in mapping:
        print(f"  {row['file']:<20} {row['case']:<18} {row['defect_class']}")
    print()
    print("The file names carry no case information; the mapping is in MAPPING.json.")
    print("DO NOT hand MAPPING.json to the overlooker.")
    return 0


if __name__ == "__main__":
    raise SystemExit(stage())
