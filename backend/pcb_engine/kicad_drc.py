"""
kicad_drc.py — KiCad's DRC as a second, independent design-rule engine.

Stage 4 of `reports/PCB verification implementation plan.md`. The in-house
kernel (`kernel.py`) and KiCad share no geometry code, so where they agree the
result stands on two engines, and where they disagree one of them is wrong —
`compare_engines` sorts every disagreement for a person to settle.

FOUR TRAPS, EACH WITH A FIXED ANSWER (plan, stage 4)
----------------------------------------------------
1. A broken `.kicad_dru` is dropped without a word: one bad layer name and
   KiCad runs no custom rule at all. Answer: the SENTINEL, an assertion that
   always fails, appended last to every rule file. No sentinel violation in the
   report means "rules not loaded", and the result is refused. Tried on 10.0.1
   (2026-10-21): it fires once, other assertion rules before or after it on the
   same item do not mask it, and a rule file with a bad layer name loses it.
2. KiCad's own severities demote or ignore checks that matter. Answer: POLICY,
   keyed by KiCad's machine names, decides required or advisory; the project
   file sets every policy key to a severity KiCad will report, and a required
   check KiCad lists under `ignored_checks` refuses the result.
3. `--schematic-parity` without a schematic passes silently. Answer: never
   used; connectivity is compared with the IR by `compare_engines`.
4. Exclusions and baseline noise distort totals. Answer: counts are by
   violation type, never a total, and no waiver lives in KiCad.

Exit codes of `kicad-cli pcb drc --exit-code-violations` on 10.0.1: 0 clean,
5 violations; anything else means DRC did not run, and that is refused rather
than read as clean.
"""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from board_ir import Board
import kicad_cli

SENTINEL = "circuitos_sentinel"

# The outline is the one item every written board has (kicad_export.write_pcb).
SENTINEL_RULE = (f'(rule "{SENTINEL}"\n'
                 "\t(condition \"A.Layer == 'Edge.Cuts'\")\n"
                 "\t(constraint assertion \"A.Layer == 'F.Cu'\"))\n")

# ─────────────────────────────────────────────────────────────────────────────
# The policy table. Keys are KiCad 10's machine names (drc_item.cpp). Required:
# the board does not leave with one of these. Advisory: reported, never gates.
# Noise: meaningless for a board with no schematic and no footprint library,
# each with its reason. A type KiCad reports that is not here is treated as
# required — an unknown check fails closed.
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED = "required"
ADVISORY = "advisory"
NOISE = "noise"

POLICY: dict[str, str] = {
    # copper and connectivity — the decidable faults
    "unconnected_items": REQUIRED, "shorting_items": REQUIRED,
    "tracks_crossing": REQUIRED, "clearance": REQUIRED,
    "copper_edge_clearance": REQUIRED, "zones_intersect": REQUIRED,
    "items_not_allowed": REQUIRED, "item_on_disabled_layer": REQUIRED,
    "net_conflict": REQUIRED, "isolated_copper": ADVISORY,
    "starved_thermal": REQUIRED, "connection_width": REQUIRED,
    "copper_sliver": REQUIRED,          # KiCad: warning; a sliver can lift at the fab
    # holes and pads
    "annular_width": REQUIRED, "drill_out_of_range": REQUIRED,
    "microvia_drill_out_of_range": REQUIRED, "hole_clearance": REQUIRED,
    "hole_to_hole": REQUIRED, "hole_near_hole": REQUIRED,
    "holes_co_located": REQUIRED,       # KiCad: warning
    "padstack": REQUIRED, "through_hole_pad_without_hole": REQUIRED,
    "overlapping_pads": ADVISORY,
    # tracks and vias
    "track_width": REQUIRED, "via_diameter": REQUIRED, "length_out_of_range": REQUIRED,
    "skew_out_of_range": REQUIRED, "too_many_vias": REQUIRED,
    "diff_pair_gap_out_of_range": REQUIRED,
    "diff_pair_uncoupled_length_too_long": REQUIRED,
    "track_angle": ADVISORY, "track_segment_length": ADVISORY,
    "track_dangling": ADVISORY, "via_dangling": ADVISORY,
    "track_not_centered_on_via": ADVISORY,
    "track_on_post_machined_layer": REQUIRED,
    # board, placement, mask
    "invalid_outline": REQUIRED, "courtyards_overlap": REQUIRED,
    "malformed_courtyard": REQUIRED,
    "missing_courtyard": REQUIRED,      # KiCad: ignore; the writer always draws one
    "duplicate_footprints": REQUIRED, "solder_mask_bridge": REQUIRED,
    "creepage": REQUIRED,
    "pth_inside_courtyard": ADVISORY, "npth_inside_courtyard": ADVISORY,
    "footprint_type_mismatch": ADVISORY,   # KiCad: ignore
    "assertion_failure": REQUIRED,      # any assertion but the sentinel
    "unresolved_variable": ADVISORY,
    # silk and text: no silk is generated, so these can only be advisory
    "silk_over_copper": ADVISORY, "silk_overlap": ADVISORY,
    "silk_edge_clearance": ADVISORY, "text_height": ADVISORY,
    "text_thickness": ADVISORY, "text_on_edge_cuts": ADVISORY,
    "mirrored_text_on_front_layer": ADVISORY,
    "nonmirrored_text_on_back_layer": ADVISORY,
    # noise: no schematic, no footprint library, no tuning profiles
    "lib_footprint_issues": NOISE,      # footprints are written, not from a library
    "lib_footprint_mismatch": NOISE,
    "footprint_symbol_mismatch": NOISE, "footprint_symbol_field_mismatch": NOISE,
    "footprint_filters_mismatch": NOISE, "extra_footprint": NOISE,
    "missing_footprint": NOISE, "schematic_parity": NOISE,
    "footprint": NOISE, "missing_tuning_profile": NOISE,
    "tuning_profile_track_geometries": NOISE,
}

# What the project file tells KiCad, so nothing the policy needs is left at
# KiCad's "ignore".
SEVERITIES: dict[str, str] = {
    k: {REQUIRED: "error", ADVISORY: "warning", NOISE: "ignore"}[v]
    for k, v in POLICY.items() if k not in ("assertion_failure", "schematic_parity")
}


def write_dru(rules: list[str] | tuple[str, ...] = ()) -> str:
    """A `.kicad_dru`: the given rules, then the sentinel, always last."""
    body = "".join(r if r.endswith("\n") else r + "\n" for r in rules)
    return "(version 1)\n" + body + SENTINEL_RULE


# ─────────────────────────────────────────────────────────────────────────────
# running it
# ─────────────────────────────────────────────────────────────────────────────
_NET = re.compile(r"\[([^\]]*)\]")


def item_nets(v: dict) -> tuple[str, ...]:
    """The nets a KiCad violation names, from its items' "[NET]" labels."""
    nets = []
    for it in v.get("items", []):
        m = _NET.search(it.get("description", ""))
        if m and m.group(1) and m.group(1) != "<no net>":
            nets.append(m.group(1))
    return tuple(nets)


@dataclass
class DrcResult:
    exit_code: int
    kicad_version: str
    sentinel_fired: bool = False
    by_type: dict[str, int] = field(default_factory=dict)
    required: list[dict] = field(default_factory=list)
    advisory: list[dict] = field(default_factory=list)
    unknown_types: list[str] = field(default_factory=list)
    ignored_required: list[str] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def ran(self) -> bool:
        """DRC ran with our rules loaded: the only state whose counts mean anything."""
        return self.exit_code in (0, 5) and self.sentinel_fired

    @property
    def ok(self) -> bool:
        return not self.refusals

    def of_type(self, t: str) -> list[dict]:
        return [v for v in self.required + self.advisory if v["type"] == t]

    def to_dict(self) -> dict:
        return {"engine": "kicad-cli pcb drc", "kicad_version": self.kicad_version,
                "exit_code": self.exit_code, "ran": self.ran, "ok": self.ok,
                "sentinel_fired": self.sentinel_fired, "by_type": self.by_type,
                "required": [{"type": v["type"], "description": v["description"],
                              "nets": list(item_nets(v))} for v in self.required],
                "advisory_by_type": dict(Counter(v["type"] for v in self.advisory)),
                "unknown_types": self.unknown_types,
                "ignored_required": self.ignored_required,
                "refusals": self.refusals}


def parse_report(report: dict, exit_code: int, kicad_version: str = "") -> DrcResult:
    """Sort a KiCad DRC JSON report by the policy table."""
    res = DrcResult(exit_code=exit_code, kicad_version=kicad_version, raw=report)
    every = list(report.get("violations", [])) + list(report.get("unconnected_items", []))
    for v in every:
        t = v.get("type", "?")
        if t == "assertion_failure" and f"'{SENTINEL}'" in v.get("description", ""):
            res.sentinel_fired = True
            continue
        res.by_type[t] = res.by_type.get(t, 0) + 1
        cls = POLICY.get(t)
        if cls is None:
            if t not in res.unknown_types:
                res.unknown_types.append(t)
            cls = REQUIRED
        if cls == REQUIRED:
            res.required.append(v)
        elif cls == ADVISORY:
            res.advisory.append(v)
    res.ignored_required = sorted(c["key"] for c in report.get("ignored_checks", [])
                                  if POLICY.get(c.get("key")) == REQUIRED)
    if exit_code not in (0, 5):
        res.refusals.append(f"DRC did not run (kicad-cli exit {exit_code})")
    elif not res.sentinel_fired:
        res.refusals.append("rules not loaded: the sentinel rule did not fire, so the "
                            ".kicad_dru was dropped and no custom rule ran")
    if res.ignored_required:
        res.refusals.append(f"KiCad did not run required checks: {res.ignored_required}")
    if res.required:
        top = Counter(v["type"] for v in res.required).most_common()
        res.refusals.append("required rules fired: " +
                            ", ".join(f"{t} x{n}" for t, n in top))
    return res


def run_drc(pcb: str | Path, scratch: str | Path | None = None,
            timeout: float = 300.0) -> DrcResult:
    """KiCad DRC on a scratch copy of a written project (board, .kicad_pro,
    .kicad_dru) — refilling zones must never touch the board that ships."""
    pcb = Path(pcb)
    work = Path(scratch) if scratch else pcb.parent / "drc"
    work.mkdir(parents=True, exist_ok=True)
    for ext in (".kicad_pcb", ".kicad_pro", ".kicad_dru"):
        src = pcb.with_suffix(ext)
        if src.exists():
            shutil.copyfile(src, work / src.name)
    out = work / "drc.json"
    if out.exists():
        out.unlink()
    p = kicad_cli.run(["pcb", "drc", "--format", "json", "--severity-all",
                       "--all-track-errors", "--refill-zones", "--exit-code-violations",
                       "--units", "mm", "-o", str(out), str(work / pcb.name)],
                      timeout=timeout)
    report = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    return parse_report(report, p.returncode, kicad_cli.version())


def check_board(board: Board, out_dir: str | Path, name: str = "board",
                rules: list[str] | tuple[str, ...] = ()) -> tuple[kicad_cli.RoundTrip, DrcResult | None]:
    """Write, round-trip, and run KiCad DRC with the policy severities and the
    sentinel. No DRC is run on a board the round trip refused."""
    rt = kicad_cli.round_trip(board, out_dir, name, severities=SEVERITIES,
                              dru=write_dru(rules))
    if not rt.ok:
        return rt, None
    return rt, run_drc(rt.pcb)


# ─────────────────────────────────────────────────────────────────────────────
# the differential harness: kernel vs KiCad on decidable properties
# ─────────────────────────────────────────────────────────────────────────────
# Rule meanings that differ by design, so a disagreement there is expected and
# never a finding. Keyed by property.
DOCUMENTED_DIFFERENCES = {
    "clearance": "KiCad measures pad and via clearance to filled zones as well; "
                 "the kernel has no zone copper, so zone-only clearance pairs are KiCad's alone",
}


def _pairs(items) -> set[frozenset]:
    return {frozenset(n) for n in items if len(set(n)) == 2}


def compare_engines(board: Board, drc: DrcResult,
                    kernel_violations: list | None = None) -> dict:
    """Per decidable property, which net sets each engine flags, and the
    disagreements. A disagreement is a bug in one engine until a person files
    it as kernel miss, kernel false alarm, KiCad miss, or a documented
    difference in rule meaning."""
    from itertools import combinations
    from kernel import drc as kernel_drc
    from verify import _groups, unrouted_connections

    # "Kernel" here is the product's own side: kernel.py for clearance, and
    # verify.py's copper groups (III.1 opens, III.2 shorts) for connectivity.
    kv = kernel_drc(board) if kernel_violations is None else kernel_violations
    uf, items, _ = _groups(board)
    by_root: dict[int, set[str]] = {}
    for i, (_, o) in enumerate(items):
        if o.net:
            by_root.setdefault(uf.find(i), set()).add(o.net)
    kernel = {
        "open": {c.net for c in unrouted_connections(board)},
        "short": {frozenset(p) for ns in by_root.values() if len(ns) > 1
                  for p in combinations(sorted(ns), 2)},
        "clearance": _pairs(v.nets for v in kv if v.rule.startswith("clearance")),
    }
    kernel["clearance"] |= kernel["short"]
    kicad = {
        "open": {n for v in drc.of_type("unconnected_items") for n in item_nets(v)},
        "short": _pairs(item_nets(v) for v in drc.of_type("shorting_items")) |
                 _pairs(item_nets(v) for v in drc.of_type("tracks_crossing")),
        "clearance": _pairs(item_nets(v) for v in drc.of_type("clearance")) |
                     _pairs(item_nets(v) for v in drc.of_type("shorting_items")) |
                     _pairs(item_nets(v) for v in drc.of_type("tracks_crossing")),
    }

    def fmt(s):
        return sorted(sorted(x) if isinstance(x, frozenset) else x for x in s)

    out = {}
    for prop in kernel:
        out[prop] = {"kernel": fmt(kernel[prop]), "kicad": fmt(kicad[prop]),
                     "kicad_only": fmt(kicad[prop] - kernel[prop]),
                     "kernel_only": fmt(kernel[prop] - kicad[prop]),
                     "agree": kernel[prop] == kicad[prop]}
    out["agree"] = all(out[p]["agree"] for p in kernel)
    return out
