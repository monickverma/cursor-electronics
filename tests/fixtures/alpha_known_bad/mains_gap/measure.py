"""
measure.py — how close the mains copper gets to the SELV copper.

The measurement is edge to edge, everywhere, and it is the same measurement
in both boards: for every net other than MAINS_L, the smallest distance
between that net's copper and the mains copper, over every pair of copper
objects that share a layer. A track is its centreline swept by half its
width, a pad is its rectangle, a via is its disc.

    python tests/fixtures/alpha_known_bad/mains_gap/measure.py

It prints the table for board_base.json and board_defective.json side by
side, and says whether each one clears the 5.0 mm figure this case quotes
from IEC 60664-1 Table F.4.

The numbers to expect, both measured from the files and both reproducible
with KiCad's measure tool:

    board_base.json      DHT22_DATA   5.850 mm   (clears 5.0 mm)
    board_defective.json DHT22_DATA   0.350 mm   (does not)
"""
from __future__ import annotations

import json
import pathlib

import mutate

_HERE = pathlib.Path(__file__).resolve().parent


def _load(name: str) -> dict:
    return json.loads((_HERE / name).read_text(encoding="utf-8"))


def _table(board: dict) -> dict:
    return mutate.gaps_to_mains(board)


def main() -> int:
    boards = {"board_base.json": _load("board_base.json"),
              "board_defective.json": _load("board_defective.json")}
    tables = {name: _table(board) for name, board in boards.items()}

    nets = sorted({net for t in tables.values() for net in t})
    width = max(len(n) for n in nets)
    print(f"{'net':<{width}}  {'base (mm)':>10}  {'defective (mm)':>15}")
    print("-" * (width + 30))
    for net in nets:
        base = tables["board_base.json"].get(net)
        defect = tables["board_defective.json"].get(net)
        base_txt = f"{base[0]:>10.3f}" if base else f"{'-':>10}"
        defect_txt = f"{defect[0]:>15.3f}" if defect else f"{'-':>15}"
        print(f"{net:<{width}}  {base_txt}  {defect_txt}")

    print()
    for name, table in tables.items():
        net, (gap, _) = min(table.items(), key=lambda kv: kv[1][0])
        verdict = "clears" if gap >= mutate.CREEPAGE_MM else "DOES NOT CLEAR"
        print(f"{name:<22} nearest other net: {net} at {gap:.3f} mm "
              f"— {verdict} the {mutate.CREEPAGE_MM:.1f} mm figure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
