"""
verify.py — a software-only verification layer for a Board IR.

WHAT THIS IS FOR
----------------
`compile_board.py` emits a board and reports a number it calls "routed". That
number is the router's opinion of its own work, and the router is wrong in ways
this file was built to name:

  * `Board.unrouted()` compares quantisation cells, not distances. A connection
    whose copper ends 0.05 mm from the pad centre can read as open. (See
    `unrouted()` in board_ir.py and the note below it.)
  * `footprints.build()` silently assigns an unrecognised pin label to the first
    free pad, in netlist order. A SOT-23 whose pinout nobody wrote down compiles
    to a board that is wired in whatever order the netlist happened to list.
  * KiCad's own DRC accepts netless "ghost" copper: standalone copper needs no
    connection, so it is not a short and not an unconnected item.

This module is the second opinion. Every check here is authored against the
Board IR contract, never against the router, and every check carries the rung
it stands on:

    exact     decided by arithmetic on the IR. No tolerance beyond the one named.
    sound     an over-approximation: may say "fine" too rarely, never too often.
    bounded   verified up to a stated bound, not globally.
    evidence  a figure to inspect, not a proof.
    unknown   not checked, and said so.

A check that cannot decide reports `unknown` and names the missing tool. It does
not report `pass`. That is the whole discipline: an unchecked thing is never a
checked-and-passed thing.

WHAT IT DOES NOT DO
-------------------
It does not know whether the footprint matches the real part (IV.1 is a registry
comparison, evidence at best), whether the parts will survive assembly (II.3
tombstoning needs a reflow model), or whether the board behaves electrically
parasitics and all). Those are separate rungs and are named as unknown rather
than quietly omitted.

    python verify.py netlist_dht22.json      # compile, then verify
    python verify.py board.json              # verify an already-compiled board
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from board_ir import Board, Component, Pad, Track, Via
import footprints

# Copper closer than this is one piece. Chosen below any fab's minimum feature,
# so a gap this small is not a gap a board house can make.
CONTACT_TOL = 0.06

RUNGS = ("exact", "sound", "bounded", "evidence", "unknown")


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Finding:
    """One check, its claim, the rung it stands on, and what it found."""
    check: str                    # tree id, e.g. "III.1"
    claim: str
    rung: str
    status: str                   # "pass" | "fail" | "unknown"
    detail: str = ""
    subjects: list = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status == "fail"

    def line(self) -> str:
        mark = {"pass": "ok  ", "fail": "FAIL", "unknown": "?   "}[self.status]
        rung = f"[{self.rung}]"
        head = f"{mark} {self.check:<5} {rung:<10} {self.claim}"
        return f"{head}\n           {self.detail}" if self.detail else head


@dataclass
class Report:
    board_name: str
    findings: list[Finding]

    def failed(self) -> list[Finding]:
        return [f for f in self.findings if f.status == "fail"]

    def unknown(self) -> list[Finding]:
        return [f for f in self.findings if f.status == "unknown"]

    def passes(self) -> list[Finding]:
        return [f for f in self.findings if f.status == "pass"]

    @property
    def ok(self) -> bool:
        """True when nothing decidable is wrong. Unknown findings do not make a
        board fail; they make it unproven, which `gate()` distinguishes."""
        return not self.failed()

    @property
    def proven(self) -> bool:
        """True when every check both passed and stood on an exact or sound rung."""
        return self.ok and all(
            f.rung in ("exact", "sound") for f in self.findings)

    def gate(self) -> tuple[bool, str]:
        """Should this board be emitted? A decidable failure is a hard no."""
        bad = self.failed()
        if bad:
            return False, f"{len(bad)} check(s) failed: " + ", ".join(f.check for f in bad)
        return True, ("proven by exact/sound checks" if self.proven
                      else f"{len(self.unknown())} check(s) unproven (unknown rung)")

    def to_dict(self) -> dict:
        return {"board": self.board_name,
                "ok": self.ok, "proven": self.proven,
                "findings": [f.__dict__ for f in self.findings]}

    def render(self) -> str:
        out = [f"verification — {self.board_name}",
               "=" * 68]
        for f in self.findings:
            out.append(f.line())
        out.append("-" * 68)
        ok, why = self.gate()
        out.append(f"gate: {'EMIT' if ok else 'REFUSE'} — {why}")
        return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Geometry — authored from the IR contract, independent of kernel.py
# ─────────────────────────────────────────────────────────────────────────────
def _pt_seg(p, a, b) -> float:
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def _seg_seg(a, b, c, d) -> float:
    return min(_pt_seg(a, c, d), _pt_seg(b, c, d),
               _pt_seg(c, a, b), _pt_seg(d, a, b))


def _corners(pad: Pad):
    x0, y0, x1, y1 = pad.bbox()
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _pad_touches_point(pad: Pad, p) -> bool:
    if pad.shape == "round":
        return math.dist(p, pad.center) <= max(pad.w, pad.h) / 2 + CONTACT_TOL
    x0, y0, x1, y1 = pad.bbox()
    return (x0 - CONTACT_TOL) <= p[0] <= (x1 + CONTACT_TOL) and \
           (y0 - CONTACT_TOL) <= p[1] <= (y1 + CONTACT_TOL)


def _pad_touches_seg(pad: Pad, a, b) -> bool:
    if _pad_touches_point(pad, a) or _pad_touches_point(pad, b):
        return True
    cs = _corners(pad)
    return any(_seg_seg(a, b, c, d) <= CONTACT_TOL
               for c, d in zip(cs, cs[1:] + cs[:1]))


def _layers_meet(a_layer: str, a_th: bool, b_layer: str, b_th: bool) -> bool:
    """Two copper objects on the same side meet; a through-hole pad meets a
    track on any layer, which is what shape == 'th' means in this IR."""
    return a_th or b_th or a_layer == b_layer


def _touches(ka, a, kb, b) -> bool:
    """Do two copper objects physically make contact? Net-agnostic: this is used
    to find both connectivity and the shorts connectivity must not create."""
    if ka == "pad" and kb == "pad":
        if not _layers_meet(a.layer, a.shape == "th", b.layer, b.shape == "th"):
            return False
        x0, y0, x1, y1 = a.bbox(); X0, Y0, X1, Y1 = b.bbox()
        return not (x1 + CONTACT_TOL < X0 or X1 + CONTACT_TOL < x0 or
                    y1 + CONTACT_TOL < Y0 or Y1 + CONTACT_TOL < y0)
    if ka == "pad" and kb == "track":
        if not _layers_meet(a.layer, a.shape == "th", b.layer, False):
            return False
        return any(_pad_touches_seg(a, p, q) for p, q in zip(b.points, b.points[1:]))
    if ka == "track" and kb == "pad":
        return _touches(kb, b, ka, a)
    if ka == "track" and kb == "track":
        if a.layer != b.layer:
            return False
        return any(_seg_seg(p, q, r, s) <= CONTACT_TOL
                   for p, q in zip(a.points, a.points[1:])
                   for r, s in zip(b.points, b.points[1:]))
    if ka == "via" and kb == "track":
        return any(_pt_seg((a.x, a.y), p, q) <= a.diameter / 2 + b.width / 2 + CONTACT_TOL
                   for p, q in zip(b.points, b.points[1:]))
    if ka == "track" and kb == "via":
        return _touches(kb, b, ka, a)
    if ka == "via" and kb == "pad":
        return _pad_touches_point(b, (a.x, a.y))
    if ka == "pad" and kb == "via":
        return _touches(kb, b, ka, a)
    if ka == "via" and kb == "via":
        return math.dist((a.x, a.y), (b.x, b.y)) <= \
            (a.diameter + b.diameter) / 2 + CONTACT_TOL
    return False


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _copper_items(board: Board) -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = [("pad", p) for p in board.pads()]
    items += [("track", t) for t in board.tracks]
    items += [("via", v) for v in board.vias]
    return items


def _groups(board: Board) -> tuple[_UF, list[tuple[str, object]], dict[int, int]]:
    """Union-find over every copper object on the board, ignoring net.

    One pass gives both answers this file needs: which pads share a piece of
    copper (connectivity), and which nets that piece carries (shorts).
    Returns the union-find, the item list, and pad-id -> item-index.
    """
    items = _copper_items(board)
    uf = _UF(len(items))
    for i in range(len(items)):
        ki, oi = items[i]
        for j in range(i + 1, len(items)):
            kj, oj = items[j]
            if _touches(ki, oi, kj, oj):
                uf.union(i, j)
    pad_index = {id(o): i for i, (k, o) in enumerate(items) if k == "pad"}
    return uf, items, pad_index


# ─────────────────────────────────────────────────────────────────────────────
# Checks
# ─────────────────────────────────────────────────────────────────────────────
def _missing_connections(board: Board, uf, pad_index) -> tuple[list, list]:
    """The required connections whose endpoints are not in one piece of copper,
    and those whose endpoints are not pins at all."""
    pads = {}
    for p in board.pads():
        if p.net:
            pads[(p.net, round(p.x, 2), round(p.y, 2))] = p

    missing, orphan_ends = [], []
    for c in board.required_connections():
        pa = pads.get((c.net, round(c.a[0], 2), round(c.a[1], 2)))
        pb = pads.get((c.net, round(c.b[0], 2), round(c.b[1], 2)))
        if pa is None or pb is None:
            orphan_ends.append(c)
            continue
        if uf.find(pad_index[id(pa)]) != uf.find(pad_index[id(pb)]):
            missing.append(c)
    return missing, orphan_ends


def unrouted_connections(board: Board) -> list:
    """Required connections with no copper joining their pads.

    The independent judge `Board.unrouted()` was always meant to be replaced
    with: union-find over the copper itself, not endpoint-cell matching. This is
    that replacement, exposed so generation reports its real completion rather
    than the router's opinion of its own work."""
    uf, _, pad_index = _groups(board)
    return _missing_connections(board, uf, pad_index)[0]


def _check_connectivity(board: Board, uf, items, pad_index) -> list[Finding]:
    missing, orphan_ends = _missing_connections(board, uf, pad_index)

    detail = (f"{len(missing)} of {len(board.required_connections())} required "
              f"connections have no copper path between their pads")
    subjects = [f"{c.net} ({c.a[0]:.1f},{c.a[1]:.1f})->({c.b[0]:.1f},{c.b[1]:.1f})"
                for c in missing[:12]]
    findings = [Finding(
        "III.1", "every required connection is realised in copper", "exact",
        "fail" if missing else "pass",
        detail if missing else
        f"all {len(board.required_connections())} required connections are joined "
        f"by copper (contact tolerance {CONTACT_TOL} mm)",
        subjects)]

    if orphan_ends:
        findings.append(Finding(
            "III.1b", "every required connection has two real pads", "exact",
            "fail", f"{len(orphan_ends)} connection endpoints are not pads",
            [f"{c.net}" for c in orphan_ends[:12]]))

    # Plane nets are not poured as polygons in this IR, so copper-to-plane
    # connectivity cannot be seen here at all.
    planes = board.plane_nets()
    if planes:
        findings.append(Finding(
            "III.1c", "connections satisfied by a copper plane", "unknown",
            "unknown",
            f"plane net(s) {sorted(planes)} are declared but not realised as "
            f"copper in the Board IR; connectivity to them is not checked here"))
    return findings


def _check_shorts(board: Board, uf, items, pad_index) -> list[Finding]:
    by_root: dict[int, set[str]] = defaultdict(set)
    for i, (k, o) in enumerate(items):
        n = o.net
        if n:
            by_root[uf.find(i)].add(n)

    shorts = {r: sorted(ns) for r, ns in by_root.items() if len(ns) > 1}
    if not shorts:
        return [Finding("III.2", "no two nets share a piece of copper", "exact",
                        "pass", "no copper group carries more than one net")]
    subjects = [f"nets {ns} joined" for ns in list(shorts.values())[:12]]
    return [Finding("III.2", "no two nets share a piece of copper", "exact",
                    "fail", f"{len(shorts)} copper group(s) carry two or more nets "
                    f"(a short at {CONTACT_TOL} mm contact tolerance)", subjects)]


def _package_of(comp: Component, nl_comp: dict | None) -> str | None:
    """The package a component was built as. `from_netlist` records it on the IR;
    a hand-built board may not, so fall back to what the netlist declared."""
    pkg = comp.attrs.get("package")
    if pkg:
        return pkg
    return footprints.normalize_package((nl_comp or {}).get("package"))


def _expected_pins(ref: str, package: str, pins: dict) -> tuple[dict, list, list]:
    """Re-derive what footprints.build() should have produced for this part, and
    say which of its choices were forced by a declared map and which were not.

    Returns (expected_pin_nets, undetermined_labels, collisions).
    A label is `undetermined` when nothing declared where it goes, so build()
    put it on the first free pad — the SOT-23-without-a-pinmap case.
    A `collision` is two labels asking for the same pad, which silently drops one.
    """
    pads_rel, _, _ = footprints.PACKAGES[package]()
    avail = [p[0] for p in pads_rel]
    mapping = footprints.PINMAPS.get(package, {})

    expected: dict[str, str] = {}
    undetermined: list[str] = []
    collisions: list[str] = []

    def put(pin: str, net: str, label: str):
        if pin in expected and expected[pin] != net:
            collisions.append(f"'{label}' -> pad {pin} already carries "
                              f"'{expected[pin]}' (now '{net}')")
        expected[pin] = net

    for label, net in pins.items():
        if label in avail:
            put(label, net, label)
            continue
        up = label.upper()
        if up in mapping:
            for t in mapping[up]:
                if t in avail:
                    put(t, net, label)
            continue
        undetermined.append(label)

    for label in undetermined:
        used = set(expected.keys())
        free = [p for p in avail if p not in used]
        if free:
            expected[free[0]] = pins[label]
    return expected, undetermined, collisions


def _check_footprint_parity(board: Board, netlist: dict | None) -> list[Finding]:
    if not netlist:
        return [Finding("III.3/III.4", "footprint matches the netlist", "unknown",
                        "unknown",
                        "no netlist supplied — pin assignment is not checked")]

    nl_by_ref = {c.get("ref"): c for c in netlist.get("components", [])}
    netlist_named_netless = []
    parity_mismatch = []
    undetermined_parts = []
    collisions_all = []
    dropped = []
    missing_pkg = []

    for comp in board.components:
        nl = nl_by_ref.get(comp.ref)
        if nl is None:
            continue
        pkg = _package_of(comp, nl)
        if not pkg or pkg not in footprints.PACKAGES:
            missing_pkg.append(comp.ref)
            continue
        pins = {str(k): v for k, v in (nl.get("pins") or {}).items()}
        avail_n = footprints.pin_count(pkg)
        if len(pins) > avail_n:
            dropped.append(f"{comp.ref} ({pkg}): netlist names {len(pins)} pins, "
                           f"footprint has {avail_n}")

        expected, undetermined, collisions = _expected_pins(
            comp.ref, pkg, pins)
        collisions_all += [f"{comp.ref}: {c}" for c in collisions]
        if undetermined:
            undetermined_parts.append(
                f"{comp.ref} ({pkg}): {', '.join(map(repr, undetermined))} — "
                f"placed on free pads by list order, not by a declared pinout")

        actual = {p.pin: p.net for p in comp.pads}
        for pin, net in expected.items():
            if actual.get(pin, "") != net:
                parity_mismatch.append(
                    f"{comp.ref} pin {pin}: netlist expects {net!r}, board has "
                    f"{actual.get(pin, '')!r}")
        # a pad the netlist named that came out netless
        for pin in expected:
            if actual.get(pin, "") == "" and expected[pin]:
                netlist_named_netless.append(f"{comp.ref} pin {pin} ({expected[pin]})")

    findings = []
    findings.append(Finding(
        "III.4", "the board's pin-to-net map is the netlist's", "exact",
        "fail" if parity_mismatch else "pass",
        (f"{len(parity_mismatch)} pad(s) disagree with the netlist; "
         f"the generator is not deterministic on this netlist: "
         + "; ".join(parity_mismatch[:6]))
        if parity_mismatch else
        "every pad carries the net the netlist assigns to its pin"))

    if dropped:
        findings.append(Finding(
            "III.4b", "the footprint has a pad for every netlist pin", "exact",
            "fail", f"{len(dropped)} part(s) have more named pins than pads: "
            + "; ".join(dropped[:6])))

    if collisions_all:
        findings.append(Finding(
            "III.4c", "no two netlist pins resolve to the same pad", "exact",
            "fail", f"{len(collisions_all)} pin collision(s), one net silently "
            f"dropped: " + "; ".join(collisions_all[:6])))

    ghost = netlist_named_netless
    if ghost:
        findings.append(Finding(
            "III.3", "no pad named by the netlist is left unconnected", "exact",
            "fail", f"{len(ghost)} pad(s) the netlist named carry no net "
            f"(KiCad DRC accepts these silently): " + "; ".join(ghost[:6])))
    else:
        findings.append(Finding(
            "III.3", "no pad named by the netlist is left unconnected", "exact",
            "pass", "every pad the netlist names carries its net"))

    # Pin order: the honest verdict. A declared PINMAPS entry makes the mapping
    # forced; free-pad fallback makes it arbitrary, and no free tool checks pin
    # numbering against the real part.
    if undetermined_parts:
        findings.append(Finding(
            "III.4d", "every pin is placed by a declared pinout, not by luck",
            "unknown", "unknown",
            f"{len(undetermined_parts)} part(s) have unrecognised pin labels; the "
            f"assignment is arbitrary and is NOT checked against the real part: "
            + "; ".join(undetermined_parts[:6])))
    elif missing_pkg:
        findings.append(Finding(
            "III.4d", "every pin is placed by a declared pinout, not by luck",
            "unknown", "unknown",
            f"{len(missing_pkg)} component(s) carry no package on the IR: "
            + ", ".join(missing_pkg[:6])))
    else:
        findings.append(Finding(
            "III.4d", "every pin is placed by a declared pinout, not by luck",
            "exact", "pass",
            "every netlist pin resolved through a declared map or a literal pad id"))
    return findings


def _check_placement(board: Board) -> list[Finding]:
    findings = []
    outside = []
    for c in board.components:
        x0 = c.x - c.courtyard_w / 2; x1 = c.x + c.courtyard_w / 2
        y0 = c.y - c.courtyard_h / 2; y1 = c.y + c.courtyard_h / 2
        if x0 < -1e-9 or y0 < -1e-9 or x1 > board.outline_w + 1e-9 or \
           y1 > board.outline_h + 1e-9:
            outside.append(f"{c.ref} courtyard [{x0:.1f},{y0:.1f}]-[{x1:.1f},{y1:.1f}]"
                           f" vs board {board.outline_w}x{board.outline_h}")
    findings.append(Finding(
        "II.1", "every component courtyard lies inside the board outline",
        "exact", "fail" if outside else "pass",
        ("; ".join(outside[:8])) if outside else
        f"all {len(board.components)} courtyards are within "
        f"{board.outline_w}x{board.outline_h} mm"))

    overlaps = []
    for i, a in enumerate(board.components):
        for b in board.components[i + 1:]:
            if a.side != b.side:
                continue
            if (abs(a.x - b.x) < (a.courtyard_w + b.courtyard_w) / 2 - 1e-9 and
                    abs(a.y - b.y) < (a.courtyard_h + b.courtyard_h) / 2 - 1e-9):
                overlaps.append(f"{a.ref} <-> {b.ref}")
    findings.append(Finding(
        "II.2", "no two courtyards on the same side overlap", "exact",
        "fail" if overlaps else "pass",
        ("; ".join(overlaps[:8])) if overlaps else
        "no courtyard overlap (parts can be placed and reworked)"))
    return findings


def _check_assembly(board: Board) -> list[Finding]:
    """II.3 — tombstoning. Asymmetric pad heating lifts one end of a two-terminal
    part during reflow. Unequal pad copper is the decidable half of that; the
    thermal model that would decide the rest is not in this IR."""
    asym = []
    for c in board.components:
        pads = c.pads
        if len(pads) != 2 or not all(p.shape == "rect" for p in pads):
            continue
        areas = [p.w * p.h for p in pads]
        lo, hi = min(areas), max(areas)
        if lo <= 0 or hi / lo > 1.05:
            asym.append(f"{c.ref}: pad areas {areas[0]:.3f} vs {areas[1]:.3f} mm^2")
    return [
        Finding("II.3", "two-terminal parts have equal pad copper", "exact",
                "fail" if asym else "pass",
                ("; ".join(asym[:8])) if asym else
                "every two-terminal SMD part has symmetric pads"),
        Finding("II.3b", "neither end of a two-terminal part will lift in reflow",
                "unknown", "unknown",
                "the reflow thermal model (paste volume, pad-to-plane thermal "
                "relief, part mass) is not carried by the Board IR"),
    ]


def _check_land_patterns(board: Board, netlist: dict | None = None) -> list[Finding]:
    """IV.1 — compare the generated land pattern to a figure written down
    outside the generator. Two separate claims, two separate rungs."""
    path = Path(__file__).with_name("land_patterns.json")
    try:
        table = json.loads(path.read_text())
    except Exception as e:                                    # noqa: BLE001
        return [Finding("IV.1", "land pattern matches an external figure",
                        "unknown", "unknown",
                        f"land_patterns.json unreadable ({e})")]

    nl_by_ref = {c.get("ref"): c for c in (netlist or {}).get("components", [])}
    mismatch, unlisted, unverified = [], [], set()
    for comp in board.components:
        pkg = _package_of(comp, nl_by_ref.get(comp.ref))
        if not pkg:
            continue
        row = table.get(pkg)
        if not row:
            unlisted.append(comp.ref + ":" + pkg)
            continue
        n_pads = len(comp.pads)
        if row.get("pad_count") is not None and n_pads != row["pad_count"]:
            mismatch.append(f"{comp.ref} ({pkg}): {n_pads} pads, table says "
                            f"{row['pad_count']}")
        if not row.get("verified"):
            unverified.add(pkg)

    findings = [Finding(
        "IV.1", "the footprint the generator makes equals the figure we wrote down",
        "exact", "fail" if mismatch else "pass",
        ("; ".join(mismatch[:8])) if mismatch else
        "generated pad counts match land_patterns.json for every listed package")]

    if unlisted:
        findings.append(Finding(
            "IV.1b", "every package has an entry in the land-pattern table",
            "unknown", "unknown",
            f"{len(unlisted)} package(s) not in the table: " + ", ".join(unlisted[:8])))

    findings.append(Finding(
        "IV.1c", "the land-pattern figures themselves are externally verified",
        "evidence" if unverified else "exact",
        "unknown" if unverified else "pass",
        (f"{len(unverified)} package(s) are self-declared, verified against no "
         f"datasheet or library: " + ", ".join(sorted(unverified)[:8]) +
         ". The table can disagree with footprints.py; nothing yet makes it right.")
        if unverified else
        "every package's land pattern cites a verified external source"))
    return findings


def _check_out_of_reach(board: Board) -> list[Finding]:
    """Checks the tree names that live entirely outside this IR, stated so the
    harness cannot be mistaken for having covered them."""
    return [
        Finding("V", "as-built electrical behaviour matches the design", "unknown",
                "unknown",
                "parasitics, signal integrity, PDN and EMC need an EM solver or a "
                "bench measurement; the IR carries no field data"),
        Finding("VI", "the design itself is electrically correct", "unknown",
                "unknown",
                "analog functional correctness is undecidable in general; see "
                "reports/Analog circuit formal verification.md"),
        Finding("VII", "the board works in its environment", "unknown", "unknown",
                "cables, supply, firmware and enclosure are outside the Board IR"),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# The entry point
# ─────────────────────────────────────────────────────────────────────────────
def verify_board(board: Board, netlist: dict | None = None) -> Report:
    uf, items, pad_index = _groups(board)
    findings: list[Finding] = []
    findings += _check_placement(board)
    findings += _check_assembly(board)
    findings += _check_connectivity(board, uf, items, pad_index)
    findings += _check_shorts(board, uf, items, pad_index)
    findings += _check_footprint_parity(board, netlist)
    findings += _check_land_patterns(board, netlist)
    findings += _check_out_of_reach(board)
    return Report(board.name, findings)


def _load(path: str) -> tuple[Board, dict | None]:
    d = json.loads(Path(path).read_text())
    if "components" in d and "board" in d and "layers" not in d:
        from compile_board import compile_board
        r = compile_board(d)
        return r.board, d
    return Board.from_json(json.dumps(d)), None


def main() -> None:
    try:                                  # the report uses real dashes; cp1252 does not
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                     # noqa: BLE001
        pass
    args = sys.argv[1:] or ["netlist_dht22.json"]
    board, netlist = _load(args[0])
    rep = verify_board(board, netlist)
    print(rep.render())
    ok, why = rep.gate()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
