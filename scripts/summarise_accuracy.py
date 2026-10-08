"""
The accuracy experiment's results, as the tables in `docs/REAL_DATA_CHECK.md`.

    python scripts/summarise_accuracy.py v.json vr.json [> tables.md]

Reads the JSON `scripts/build_check_accuracy.py --json` writes — once for voltage readings alone, once for voltage
plus power-off resistance — and totals them over the designs, so no figure in the report is typed by hand.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


def pct(x: float, n: float) -> str:
    return f"{100 * x / n:.1f} %" if n else "—"


def total(d: Dict[str, Any], names: Iterable[str], key: str) -> Counter:
    c: Counter = Counter()
    for n in names:
        part = d[n].get(key) or {}
        for k, v in part.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                c[k] += v
    return c


def groups(d: Dict[str, Any]) -> Dict[str, List[str]]:
    return {"the five generated designs": [n for n in d if n.startswith("generated:")],
            "ten real reference circuits": [n for n in d if n.startswith("real:")],
            "all fifteen": list(d)}


def correct_table(vs: Dict[str, Any], vr: Dict[str, Any]) -> str:
    L = ["| Boards | Readings | Correct builds | Called as designed | Named a fault that is not there | Charged to the model (D1) | Said a part is off |",
         "|---|---|---:|---:|---:|---:|---:|"]
    for g, names in groups(vr).items():
        for label, d, key in (("voltage only — detect plan", vs, "correct_detect"), ("voltage + ohms — detect plan", vr, "correct_detect"),
                              ("voltage + ohms — identify plan", vr, "correct_identify"), ("voltage + ohms — every reading", vr, "correct_all")):
            c = total(d, [n for n in names if n in d], key)
            n = c["n"]
            L.append(f"| {g} | {label} | {int(n)} | {pct(c['correct'], n)} | {pct(c['false_fault'], n)} | {pct(c['false_unexplained'], n)} | {pct(c['false_part_off'], n)} |")
    return "\n".join(L)


def detect_table(vs: Dict[str, Any], vr: Dict[str, Any]) -> str:
    L = ["| Boards | Readings | Wrong builds | Noticed | Named exactly | Listed among several | Wrong name | Charged to D1 | Said a part is off | Missed |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for g, names in groups(vr).items():
        for label, d, key in (("voltage only — detect plan", vs, "detectable_detect"), ("voltage only — every reading", vs, "detectable_all"),
                              ("voltage + ohms — detect plan", vr, "detectable_detect"), ("voltage + ohms — identify plan", vr, "detectable_identify"),
                              ("voltage + ohms — every reading", vr, "detectable_all")):
            c = total(d, [n for n in names if n in d], key)
            n = c["n"]
            L.append(f"| {g} | {label} | {int(n)} | {pct(n - c['missed'], n)} | {pct(c['exact'], n)} | {pct(c['ambiguous'], n)} | "
                     f"{pct(c['misnamed'], n)} | {pct(c['unexplained_d1'], n)} | {pct(c['unexplained_part_off'], n)} | {pct(c['missed'], n)} |")
    return "\n".join(L)


def per_design_table(vs: Dict[str, Any], vr: Dict[str, Any]) -> str:
    L = ["| Design | Listed faults | Blind: voltage only → with ohms | Detect plan (readings) | Identify plan (readings) | Wrong builds named exactly: identify plan | Guarantee replay: violations / readings |",
         "|---|---:|---:|---:|---:|---:|---:|"]
    for n, r in vr.items():
        v = vs.get(n, {})
        d = r["detectable_identify"]
        g = r["guarantee_replay"]
        L.append(f"| {n.replace('generated:', '').replace('real:', '')} | {r['faults']} | {v.get('blind', '—')} → {r['blind']} | "
                 f"{r['plan_size']} | {r['identify_size']} | {pct(d.get('exact', 0), d['n'])} | {g['violations']} / {g['readings_replayed']} |")
    return "\n".join(L)


def stress_table(vr: Dict[str, Any]) -> str:
    names = list(vr)
    L = ["| Outside what the guarantee covers | Builds | As designed | Named a fault | Charged to D1 | Said a part is off |", "|---|---:|---:|---:|---:|---:|"]
    for label, key in (("parts twice as loose as stated", "correct_loose_parts_2x"), ("a meter twice as inaccurate as stated", "correct_bad_meter_2x")):
        c = total(vr, names, key)
        n = c["n"]
        L.append(f"| a correct board, {label} | {int(n)} | {pct(c['correct'], n)} | {pct(c['false_fault'], n)} | {pct(c['false_unexplained'], n)} | {pct(c['false_part_off'], n)} |")
    u: Counter = Counter()
    for n in names:
        for k, v in (vr[n].get("unlisted") or {}).items():
            u[k] += v
    nm = {k.split(":")[1]: v for k, v in u.items() if k.startswith("near_miss")}
    tf = {k.split(":")[1]: v for k, v in u.items() if k.startswith("two_faults")}
    for label, dd in (("one part 1.25× or 0.8× its value (not a listed fault)", nm), ("two listed faults at once", tf)):
        n = sum(dd.values())
        L.append(f"| a wrong board: {label} | {n} | — | — | {pct(dd.get('unexplained_d1', 0), n)} | {pct(dd.get('unexplained_part_off', 0), n)} |")
    return "\n".join(L)


def stress_unlisted_detail(vs: Dict[str, Any], vr: Dict[str, Any]) -> str:
    L = ["| Readings | One part 1.25× or 0.8× off: charged to D1 | said a part is off | missed | Two faults at once: named one of them | wrong name | charged to D1 | said a part is off | missed |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for label, d in (("voltage only", vs), ("voltage + ohms (identify plan)", vr)):
        u: Counter = Counter()
        for n in d:
            for k, v in (d[n].get("unlisted") or {}).items():
                u[k] += v
        a = sum(v for k, v in u.items() if k.startswith("near_miss"))
        b = sum(v for k, v in u.items() if k.startswith("two_faults"))
        L.append(f"| {label} | {pct(u['near_miss_value:unexplained_d1'], a)} | {pct(u['near_miss_value:unexplained_part_off'], a)} | {pct(u['near_miss_value:missed'], a)} | "
                 f"{pct(u['two_faults:names_one_of_the_two'], b)} | {pct(u['two_faults:misnamed'], b)} | {pct(u['two_faults:unexplained_d1'], b)} | "
                 f"{pct(u['two_faults:unexplained_part_off'], b)} | {pct(u['two_faults:missed'], b)} |")
    return "\n".join(L)


def blind_table(vs: Dict[str, Any], vr: Dict[str, Any]) -> str:
    L = ["| Readings | Listed faults no reading is guaranteed to separate | Of those, tried | The check stayed quiet |", "|---|---:|---:|---:|"]
    for label, d in (("voltage only", vs), ("voltage + ohms", vr)):
        nb = sum(d[n]["blind"] for n in d)
        c = total(d, list(d), "blind_plan")
        L.append(f"| {label} | {nb} | {int(c['n'])} builds | {pct(c['correct'], c['n'])} |")
    return "\n".join(L)


def main(argv: List[str]) -> int:
    vs = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    vr = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    print("### Correct boards\n\n" + correct_table(vs, vr))
    print("\n### Wrong boards (every listed fault, random in-tolerance parts and rail, meter error inside its accuracy)\n\n" + detect_table(vs, vr))
    print("\n### By design\n\n" + per_design_table(vs, vr))
    print("\n### The faults nobody can promise to see\n\n" + blind_table(vs, vr))
    print("\n### Outside the guarantee\n\n" + stress_table(vr))
    print("\n" + stress_unlisted_detail(vs, vr))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
