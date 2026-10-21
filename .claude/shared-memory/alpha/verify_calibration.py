"""
verify_calibration.py — check the Alpha known-bad set, mechanically.

WHY A SCRIPT AND NOT AN AGENT
-----------------------------
The question this file answers is arithmetic, not judgement: for each seeded
defect, does the check that should catch it actually flip from pass to fail
between the clean board and the defective one, and is the defect physically
present in the defective board and absent from the clean one?

A model asked that question can be talked into "yes, it looks detected". This
file cannot. It loads both boards, diffs them, runs the verifier on both, and
prints what it saw.

THE GATE
--------
For a critical defect class (short, open, wrong pinout, reversed diode,
creepage) a defect that this file cannot see is a FALSE PASS, and a false pass
on a critical class blocks Alpha stage A1. That is not a soft metric.

    python .claude/shared-memory/alpha/verify_calibration.py
    python .claude/shared-memory/alpha/verify_calibration.py --json

Exit code 0 when every seeded defect is present AND detected; 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
FIXTURES = REPO / "tests" / "fixtures" / "alpha_known_bad"

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "pcb_engine"))

from pcb_engine.board_ir import Board  # noqa: E402
from pcb_engine.verify import verify_board  # noqa: E402


def _load_board(path: Path) -> Board:
    return Board.from_json(path.read_text(encoding="utf-8"))


def _statuses(report) -> dict[str, str]:
    return {f.check: f.status for f in report.findings}


def _findings_by_check(report) -> dict[str, list]:
    out: dict[str, list] = {}
    for f in report.findings:
        out.setdefault(f.check, []).append(f)
    return out


def _geometry_signature(board: Board) -> dict:
    """The parts of a board a physical defect can change.

    A defect that does not change any of these was not seeded in the geometry
    — it may have changed a field nothing reads, which is not a defect a
    fabricator would ever see.
    """
    return {
        "tracks": sorted(
            (t.net, tuple(map(tuple, t.points)), round(t.width, 6), t.layer)
            for t in board.tracks
        ),
        "vias": sorted((v.net, round(v.x, 6), round(v.y, 6)) for v in board.vias),
        "pads": sorted(
            (p.ref, p.pin, p.net, round(p.x, 6), round(p.y, 6), p.layer)
            for p in board.pads()
        ),
        "components": sorted(
            (c.ref, round(c.x, 6), round(c.y, 6), c.rotation, c.side) for c in board.components
        ),
    }


def _diff(base: Board, defective: Board) -> dict:
    """What actually changed between the two boards."""
    bs, ds = _geometry_signature(base), _geometry_signature(defective)
    out = {}
    for key in ("tracks", "vias", "pads", "components"):
        b, d = set(bs[key]), set(ds[key])
        removed, added = b - d, d - b
        if removed or added:
            out[key] = {
                "removed": len(removed),
                "added": len(added),
                "examples": (
                    [str(x) for x in list(removed)[:2]] + [str(x) for x in list(added)[:2]]
                )[:4],
            }
    return out


def _netlists_for(case: Path) -> tuple[dict | None, dict | None]:
    """The two netlists a case may ship, and which is which.

    A COPPER defect (a cut track, a deleted via) lives in the board, and both
    boards are judged against the SAME netlist — the one the design states.
    A NETLIST defect (a swapped pin, a reversed diode) changes the
    requirement, so each board is judged against the netlist it was actually
    compiled from. That is the product's own path: `compile_board` calls
    `verify_board(board, netlist)` with the same netlist it just compiled
    from, so the verifier can only ever answer "is this board what I was told
    to build".

    Returning the pair rather than one netlist keeps that distinction
    explicit, because it is the whole reason the netlist-level cases are
    false passes rather than detections.

    Returns (design_intent, defective_netlist). Either may be None.
    """
    def _read(name: str) -> dict | None:
        p = case / name
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    base = _read("netlist_base.json") or _read("netlist.json")
    defective = _read("netlist_defective.json")
    return base, defective


def _check_case(case: Path) -> dict:
    manifest_path = case / "manifest.json"
    base_path = case / "board_base.json"
    defect_path = case / "board_defective.json"

    result: dict = {
        "id": case.name,
        "ok": False,
        "problems": [],
        "seeded": False,
        "detected": False,
        "check": None,
        "rung": None,
        "critical": False,
        "false_pass": False,
    }

    if not manifest_path.exists():
        result["problems"].append("no manifest.json")
        return result
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        result["problems"].append(f"manifest unreadable: {exc}")
        return result

    result["critical"] = bool(manifest.get("critical"))
    result["rung"] = manifest.get("rung")
    result["check"] = manifest.get("expected_check_ids")
    expected = manifest.get("expected_check_ids") or []
    if isinstance(expected, str):
        expected = [expected]
    #: A manifest may declare that the product does NOT catch this defect
    #: today, and name the finding that says so. Such a case is a KNOWN GAP,
    #: not a broken seed: the harness must confirm the gap still exists (the
    #: board really is emitted) and must NOT report it as a new false pass.
    #: A case that says "not caught" but IS caught is stale — the gap closed
    #: and the manifest should be updated.
    result["known_gap"] = manifest.get("known_gap")
    result["expected_not_detected"] = bool(manifest.get("expected_not_detected"))

    if not base_path.exists() or not defect_path.exists():
        result["problems"].append("missing board_base.json or board_defective.json")
        return result

    try:
        base = _load_board(base_path)
        defective = _load_board(defect_path)
    except Exception as exc:
        result["problems"].append(f"board unreadable: {exc}")
        return result

    # ── Q1: is the defect physically present? ──
    delta = _diff(base, defective)
    design_netlist, defective_netlist = _netlists_for(case)
    if delta:
        result["seeded"] = True
        result["diff"] = delta
    elif design_netlist is not None and defective_netlist is not None:
        # A netlist-level defect: the boards may be identical because the
        # board faithfully realises the (wrong) netlist. That is still a seeded
        # defect, but only if the netlist actually differs from the base one.
        result["seeded"] = design_netlist != defective_netlist
        result["diff"] = {"netlist": "differs from the base netlist"}
        if not result["seeded"]:
            result["problems"].append(
                "the base and defective netlists are identical — nothing was seeded"
            )
    else:
        result["problems"].append("nothing changed between base and defective board")

    if not result["seeded"]:
        return result

    # ── Q2: does the verifier see it? ──
    #
    # Each board is judged against the netlist it was actually compiled from.
    # That is the product's own path (compile_board -> verify_board(board,
    # netlist) with the same netlist), so this measures what the product does,
    # not a stronger thing the product never does.
    base_netlist = design_netlist or defective_netlist
    defect_netlist = defective_netlist or design_netlist
    try:
        base_report = verify_board(base, base_netlist)
        defect_report = verify_board(defective, defect_netlist)
    except Exception as exc:
        result["problems"].append(f"verifier raised: {type(exc).__name__}: {exc}")
        return result

    # A second measurement, and the one that matters for a netlist-level
    # defect: the defective board judged against the DESIGN INTENT. If the
    # design netlist differs from the one the board was compiled from, this
    # is the check that a design-intent check would make, and the board that
    # survives it is a board the product would ship.
    if design_netlist is not None and defective_netlist is not None \
            and design_netlist != defective_netlist:
        try:
            intent_report = verify_board(defective, design_netlist)
            intent_failed = [f.check for f in intent_report.failed()]
            result["against_design_intent_failed"] = intent_failed
        except Exception as exc:
            result["problems"].append(
                f"verifier raised against the design intent: {type(exc).__name__}: {exc}"
            )

    base_status = _statuses(base_report)
    defect_status = _statuses(defect_report)
    base_by_check = _findings_by_check(base_report)
    defect_by_check = _findings_by_check(defect_report)

    # A check that flips pass -> fail is the detection.
    flipped = [
        check
        for check, status in defect_status.items()
        if status == "fail" and base_status.get(check) != "fail"
    ]
    # A check that fails on BOTH is also a detection if the base was already
    # carrying that fault — but that would mean the base is not clean, which
    # is itself a problem.
    both_fail = [
        check
        for check, status in defect_status.items()
        if status == "fail" and base_status.get(check) == "fail"
    ]

    result["flipped_checks"] = flipped
    result["base_failed_checks"] = [c for c, s in base_status.items() if s == "fail"]
    result["defect_failed_checks"] = [c for c, s in defect_status.items() if s == "fail"]
    result["defect_unknown_checks"] = [c for c, s in defect_status.items() if s == "unknown"]

    # The gate is what the product actually does with the board: emit it, or
    # refuse it. A check that fails makes the gate refuse. A check that stays
    # at "unknown" does not — the board is emitted with the defect in it.
    gate = defect_report.to_dict().get("gate") or {}
    result["gate"] = gate
    result["emitted"] = bool(gate.get("emit"))

    if flipped:
        result["detected"] = True
        result["detected_by"] = flipped
        if result["expected_not_detected"]:
            # The manifest said the product does not catch this. It does now.
            # That is good news, and the manifest is now stale.
            result["problems"].append(
                "STALE: the manifest says this defect is not caught, but the "
                f"verifier now fails it ({flipped}). Update the manifest."
            )
        if expected:
            unmatched = [c for c in flipped if c not in expected]
            if unmatched:
                result["problems"].append(
                    f"detected by {unmatched}, which the manifest did not predict ({expected})"
                )
    elif both_fail:
        result["problems"].append(
            f"the clean base already fails {both_fail} — the base is not a clean board"
        )
    elif result["expected_not_detected"]:
        # A known gap, declared. The harness confirms it is still a gap: the
        # board really is emitted, defect and all.
        result["known_gap_confirmed"] = True
        if not result["emitted"]:
            result["problems"].append(
                "STALE: the manifest says this defect is not caught, and the "
                "board is no longer emitted, but no check failed either. "
                "Update the manifest."
            )
    else:
        result["false_pass"] = True
        result["problems"].append(
            "NOT DETECTED: the verifier reports no new failure on the defective board"
        )
        if result["emitted"]:
            result["problems"].append(
                "FALSE PASS: the product would EMIT this board for fabrication"
            )

    if expected:
        missing = [c for c in expected if c not in defect_status]
        if missing:
            result["problems"].append(f"expected check {missing} is not in the report at all")

    # A case is OK when the defect is seeded, the harness saw what the
    # manifest said it would see, and nothing else went wrong. A declared
    # known gap is OK when the gap is still there — that is the truth today.
    result["ok"] = (result["seeded"] and not result["problems"]
                    and (result["detected"] or result.get("known_gap_confirmed")))
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    if not FIXTURES.exists():
        print(f"no calibration set at {FIXTURES}")
        return 1

    cases = sorted(p for p in FIXTURES.iterdir() if p.is_dir())
    results = []
    for case in cases:
        try:
            results.append(_check_case(case))
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "id": case.name,
                    "ok": False,
                    "seeded": False,
                    "detected": False,
                    "false_pass": False,
                    "critical": False,
                    "problems": [f"harness raised: {type(exc).__name__}: {exc}"],
                }
            )

    seeded = [r for r in results if r["seeded"]]
    detected = [r for r in results if r["detected"]]
    false_passes = [r for r in results if r.get("false_pass")]
    known_gaps = [r for r in results if r.get("known_gap_confirmed")]
    critical = [r for r in results if r.get("critical")]
    critical_false = [r for r in critical if r.get("false_pass")]
    critical_gaps = [r for r in critical if r.get("known_gap_confirmed")]

    if args.json:
        print(json.dumps({
            "total": len(results),
            "seeded": len(seeded),
            "detected": len(detected),
            "false_passes": [r["id"] for r in false_passes],
            "known_gaps": [r["id"] for r in known_gaps],
            "critical_false_passes": [r["id"] for r in critical_false],
            "critical_known_gaps": [r["id"] for r in critical_gaps],
            "results": results,
        }, indent=2))
    else:
        print("=" * 72)
        print("Alpha known-bad set — mechanical verification")
        print("=" * 72)
        for r in results:
            mark = "PASS" if r["ok"] else "FAIL"
            flags = []
            if r.get("critical"):
                flags.append("CRITICAL")
            if r.get("known_gap_confirmed"):
                flags.append("KNOWN-GAP")
            if r.get("false_pass"):
                flags.append("FALSE-PASS")
            print(f"[{mark}] {r['id']:<20} {' '.join(flags)}")
            if r.get("detected_by"):
                print(f"        detected by: {', '.join(r['detected_by'])}")
            if "against_design_intent_failed" in r:
                failed = r["against_design_intent_failed"]
                print(f"        the defective board judged against the DESIGN INTENT: "
                      f"{', '.join(failed) if failed else 'no check fails'}")
            if r.get("known_gap"):
                print(f"        known gap: {r['known_gap']}")
            for p in r["problems"]:
                print(f"        ! {p}")
        print("-" * 72)
        print(f"cases      {len(results)}")
        print(f"seeded     {len(seeded)}")
        print(f"detected   {len(detected)}")
        print(f"known gap  {len(known_gaps)}  {([r['id'] for r in known_gaps] or '')}")
        print(f"false pass {len(false_passes)}  {([r['id'] for r in false_passes] or '')}")
        print(f"critical   {len(critical)} cases, {len(critical_false)} false passes, "
              f"{len(critical_gaps)} known gaps")
        print()
        if critical_false:
            print("GATE: BLOCKED — an undeclared false pass on a critical class.")
        elif critical_gaps:
            print("GATE: BLOCKED — a DECLARED known gap on a critical class. The product")
            print("      does not catch this defect and says so. A1 cannot exit on a")
            print("      gap; it can exit on a fix.")
        else:
            print("GATE: every critical defect is caught by a check that fails.")
        print("NOTE: this file says the defect is DETECTED BY OUR OWN VERIFIER.")
        print("      It does not say an overlooker will find it. That is a different")
        print("      measurement, and it is the one A1 actually gates on.")

    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
