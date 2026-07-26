"""
board_ir.py — the contract.

Everything in this system speaks Board IR. The LLM reads it and proposes
mutations to it; the router consumes it and returns a new one; the DRC kernel
scores it. Nothing else is shared state.

Units are millimetres throughout, origin bottom-left, y-up. Angles in degrees.

WHY AN IR AT ALL
----------------
The temptation is to let the model touch .kicad_pcb or Gerber directly. Don't.
Those formats are lossy in the directions you care about (Gerber has no netlist)
and verbose in the directions you don't. An IR gives you:

  * one place to validate  — a malformed mutation is caught here, not at the fab
  * one place to diff      — revisions are IR snapshots, which is how you get a
                             timeline slider for free
  * format independence    — KiCad, DSN, Gerber become import/export adapters
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Literal

Point = tuple[float, float]
LayerType = Literal["signal", "power", "mixed"]


# ─────────────────────────────────────────────────────────────────────────────
# Geometry primitives
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Layer:
    name: str
    type: LayerType = "signal"
    plane_net: str | None = None          # copper pour net, None = no pour
    thickness_mm: float = 0.035
    dielectric_below_mm: float = 0.48     # to the NEXT layer down


@dataclass
class Pad:
    ref: str                              # owning component designator
    pin: str
    x: float
    y: float
    w: float
    h: float
    net: str
    layer: str = "F.Cu"
    shape: Literal["rect", "round", "th"] = "rect"

    @property
    def center(self) -> Point:
        return (self.x, self.y)

    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x - self.w / 2, self.y - self.h / 2,
                self.x + self.w / 2, self.y + self.h / 2)


@dataclass
class Component:
    ref: str
    x: float
    y: float
    rotation: float = 0.0
    side: Literal["top", "bottom"] = "top"
    courtyard_w: float = 1.0
    courtyard_h: float = 1.0
    locked: bool = False                  # placement tools must not move it
    pads: list[Pad] = field(default_factory=list)
    # free-form hints the LLM may set and read back, e.g. {"thermal": "heat source"}
    attrs: dict = field(default_factory=dict)


@dataclass
class Track:
    layer: str
    net: str
    width: float
    points: list[Point]
    rev: int = 0

    def length(self) -> float:
        return sum(math.dist(a, b) for a, b in zip(self.points, self.points[1:]))


@dataclass
class Via:
    x: float
    y: float
    net: str
    drill: float = 0.4
    diameter: float = 0.8
    rev: int = 0


@dataclass
class Keepout:
    kind: Literal["placement", "wire", "via", "all"]
    layer: str | None          # None = all layers
    x: float
    y: float
    w: float
    h: float
    reason: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Constraints — what the LLM is actually allowed to author
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class NetClass:
    name: str
    nets: list[str]
    track_width: float = 0.2
    clearance: float = 0.15
    via_drill: float = 0.4
    via_diameter: float = 0.8
    priority: int = 0          # higher routes first


@dataclass
class DiffPair:
    name: str
    net_p: str
    net_n: str
    width: float = 0.2
    gap: float = 0.15
    target_impedance: float | None = None
    max_skew_mm: float = 0.5


@dataclass
class Connection:
    """A required electrical connection not yet realised as copper (a ratline)."""
    net: str
    a: Point
    b: Point


# ─────────────────────────────────────────────────────────────────────────────
# The board
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Board:
    name: str = "board"
    outline_w: float = 40.0
    outline_h: float = 24.0
    layers: list[Layer] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    vias: list[Via] = field(default_factory=list)
    keepouts: list[Keepout] = field(default_factory=list)
    net_classes: list[NetClass] = field(default_factory=list)
    diff_pairs: list[DiffPair] = field(default_factory=list)

    # ── queries the agent leans on ──
    def pads(self) -> list[Pad]:
        return [p for c in self.components for p in c.pads]

    def nets(self) -> list[str]:
        return sorted({p.net for p in self.pads() if p.net})

    def signal_layers(self) -> list[Layer]:
        return [l for l in self.layers if l.type == "signal"]

    def net_class_for(self, net: str) -> NetClass:
        for nc in sorted(self.net_classes, key=lambda n: -n.priority):
            if net in nc.nets:
                return nc
        return NetClass(name="default", nets=[])

    def component(self, ref: str) -> Component | None:
        return next((c for c in self.components if c.ref == ref), None)

    def pads_by_net(self) -> dict[str, list[Pad]]:
        out: dict[str, list[Pad]] = {}
        for p in self.pads():
            if p.net:
                out.setdefault(p.net, []).append(p)
        return out

    def plane_nets(self) -> set[str]:
        return {l.plane_net for l in self.layers if l.plane_net}

    def required_connections(self) -> list[Connection]:
        """Minimum spanning tree per net over pad centres (Prim), EXCLUDING
        nets that have a copper plane.

        This is what a ratsnest actually is: not "connect everything to
        everything", but the cheapest tree that makes the net electrically
        whole. Getting this right is what keeps the router's job small.

        The plane exclusion matters enormously. On a 4-layer board GND is
        typically 30-40% of all connections, and every one of them is satisfied
        by a single via down to the pour — not by a trace. Routing them as
        traces anyway is what produces the tell-tale bad-autorouter look: a fat
        ground net looping around the board perimeter, consuming the space the
        signals needed."""
        planes = self.plane_nets()
        conns: list[Connection] = []
        for net, pads in self.pads_by_net().items():
            if len(pads) < 2 or net in planes:
                continue
            inside = [pads[0]]
            outside = pads[1:]
            while outside:
                i, j, _ = min(
                    ((i, j, math.dist(a.center, b.center))
                     for i, a in enumerate(inside)
                     for j, b in enumerate(outside)),
                    key=lambda t: t[2])
                conns.append(Connection(net, inside[i].center, outside[j].center))
                inside.append(outside.pop(j))
        return conns

    def unrouted(self, tol: float = 0.35) -> list[Connection]:
        """Connections with no copper joining their endpoints.

        Deliberately naive endpoint matching — good enough to drive the loop,
        and exactly the check you later replace with union-find over
        track/via/pad connectivity."""
        ends: set[tuple[int, int]] = set()
        q = lambda p: (round(p[0] / tol), round(p[1] / tol))
        for t in self.tracks:
            ends.add(q(t.points[0]))
            ends.add(q(t.points[-1]))
        return [c for c in self.required_connections()
                if not (q(c.a) in ends and q(c.b) in ends)]

    # ── serialisation ──
    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(asdict(self), indent=indent)

    @staticmethod
    def from_json(s: str) -> "Board":
        d = json.loads(s)
        nested = ("layers", "components", "tracks", "vias",
                  "keepouts", "net_classes", "diff_pairs")
        b = Board(**{k: v for k, v in d.items() if k not in nested})
        b.layers = [Layer(**x) for x in d.get("layers", [])]
        b.components = [
            Component(**{**c, "pads": [Pad(**p) for p in c.get("pads", [])]})
            for c in d.get("components", [])]
        b.tracks = [Track(**{**t, "points": [tuple(p) for p in t["points"]]})
                    for t in d.get("tracks", [])]
        b.vias = [Via(**v) for v in d.get("vias", [])]
        b.keepouts = [Keepout(**k) for k in d.get("keepouts", [])]
        b.net_classes = [NetClass(**n) for n in d.get("net_classes", [])]
        b.diff_pairs = [DiffPair(**p) for p in d.get("diff_pairs", [])]
        return b

    def copy(self) -> "Board":
        return Board.from_json(self.to_json(indent=None))

    def summary(self) -> dict:
        """Compact enough to drop into a prompt without burning context."""
        return {
            "name": self.name,
            "outline_mm": [self.outline_w, self.outline_h],
            "layers": [{"name": l.name, "type": l.type, "plane": l.plane_net}
                       for l in self.layers],
            "components": len(self.components),
            "pads": len(self.pads()),
            "nets": len(self.nets()),
            "tracks": len(self.tracks),
            "vias": len(self.vias),
            "unrouted": len(self.unrouted()),
            "net_classes": [nc.name for nc in self.net_classes],
            "diff_pairs": [dp.name for dp in self.diff_pairs],
            "keepouts": len(self.keepouts),
        }


# ─────────────────────────────────────────────────────────────────────────────
# A small demo board so every module is runnable standalone
# ─────────────────────────────────────────────────────────────────────────────
def demo_board() -> Board:
    b = Board(name="demo", outline_w=40, outline_h=24, layers=[
        Layer("F.Cu", "signal"),
        Layer("In1.Cu", "power"),
        Layer("In2.Cu", "power"),
        Layer("B.Cu", "signal"),
    ])

    def qfn(ref, cx, cy, size, per_side, pitch, nets):
        pads, h = [], size / 2
        for s in range(4):
            for i in range(per_side):
                o = (i - (per_side - 1) / 2) * pitch
                n = nets[(s * per_side + i) % len(nets)]
                if s == 0:   px, py, w, hh = cx + o, cy - h - .45, .5, .9
                elif s == 1: px, py, w, hh = cx + h + .45, cy + o, .9, .5
                elif s == 2: px, py, w, hh = cx - o, cy + h + .45, .5, .9
                else:        px, py, w, hh = cx - h - .45, cy - o, .9, .5
                pads.append(Pad(ref, str(s * per_side + i + 1), px, py, w, hh, n))
        return Component(ref, cx, cy, courtyard_w=size + 2,
                         courtyard_h=size + 2, pads=pads)

    signals = ["SPI_SCK", "SPI_MOSI", "SPI_MISO", "SPI_CS",
               "SWCLK", "SWDIO", "NRST", "IRQ", "CE", "LED"]

    # NOTE ON GEOMETRY: 1.27 mm pitch, not 0.5 mm. The grid router in router.py
    # discretises at 0.25 mm, so fine-pitch fanout is beyond it by construction
    # — that is a property of grid routers, not a bug. Production geometry goes
    # to Freerouting. Keeping the reference board coarse keeps this file an
    # honest demonstration of the loop rather than a rigged one.
    b.components.append(qfn("U1", 12, 12, 5.0, 4, 1.27, signals + ["GND", "+3V3"]))
    b.components.append(qfn("U2", 28, 12, 4.4, 4, 1.27, signals[::-1] + ["GND", "+3V3"]))

    passives = [("C1", 8.0, 17.5, "+3V3", "GND"), ("C2", 16.0, 17.5, "+3V3", "GND"),
                ("C3", 23.0, 17.5, "+3V3", "GND"), ("C4", 31.0, 17.5, "+3V3", "GND"),
                ("R1", 8.0, 6.5, "+3V3", "NRST"), ("R2", 16.0, 6.5, "+3V3", "IRQ"),
                ("R3", 23.0, 6.5, "+3V3", "CE"),  ("R4", 31.0, 6.5, "LED", "GND")]
    for ref, x, y, n1, n2 in passives:
        b.components.append(Component(ref, x, y, courtyard_w=2.0, courtyard_h=1.4, pads=[
            Pad(ref, "1", x - .5, y, .5, .5, n1),
            Pad(ref, "2", x + .5, y, .5, .5, n2)]))

    b.net_classes = [
        NetClass("default", b.nets(), track_width=.2, clearance=.15),
        NetClass("power", ["GND", "+3V3"], track_width=.4, clearance=.2, priority=10),
    ]
    return b


if __name__ == "__main__":
    bd = demo_board()
    print(json.dumps(bd.summary(), indent=2))
    print(f"required connections: {len(bd.required_connections())}")
    assert Board.from_json(bd.to_json()).summary() == bd.summary(), "round-trip failed"
    print("IR round-trip OK")
