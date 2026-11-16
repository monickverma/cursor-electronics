"""
stackup.py — the board's layer stack, owned in one place.

Until 2026-10-21 each Layer carried its own `dielectric_below_mm = 0.48` that
nothing read, while scene3d drew a 1.6 mm board from a constant of its own. Two
answers to one question, and the one an impedance or IR-drop calculation would
have read was wrong by a factor of three. The Board IR now carries one Stackup;
scene3d draws it, and every layout-physics check reads it.

Every figure says where it came from. The default is generic FR-4, not a named
fab's stack: which stack the product commits to (JLCPCB standard, 1 oz?) is an
open owner question in the physics report, so the default is marked assumed and
its Er is a range, not a number.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Annealed copper at 20 °C, IEC 60028 (the International Annealed Copper Standard).
COPPER_RESISTIVITY_OHM_M = 1.724e-8
COPPER_TEMPCO_PER_K = 0.00393          # same standard, at 20 °C

ONE_OZ_MM = 0.035                      # 1 oz/ft² foil, ≈ 34.8 µm, the trade's 35 µm
FR4_ER = (4.0, 4.4, 4.8)               # assumed range for an unnamed FR-4 laminate;
                                       # the laminate's own datasheet narrows it
DEFAULT_SOURCE = ("assumed generic stack: 1.6 mm FR-4, 1 oz copper, Er 4.0-4.8; "
                  "copper resistivity IEC 60028. No fab's stack is named yet "
                  "(owner question, physics report).")


@dataclass
class Range:
    """A figure with its spread: lo <= nom <= hi."""
    lo: float
    nom: float
    hi: float

    def __post_init__(self) -> None:
        if not self.lo <= self.nom <= self.hi:
            raise ValueError(f"range out of order: {self.lo}, {self.nom}, {self.hi}")


@dataclass
class CopperLayer:
    name: str                          # matches Board.layers[i].name
    thickness_mm: float = ONE_OZ_MM


@dataclass
class Dielectric:
    thickness_mm: float
    er: Range = field(default_factory=lambda: Range(*FR4_ER))
    material: str = "FR-4"


@dataclass
class Stackup:
    """Copper layers top to bottom, with one dielectric between each pair."""
    copper: list[CopperLayer]
    dielectrics: list[Dielectric]
    name: str = "generic FR-4"
    source: str = DEFAULT_SOURCE

    def __post_init__(self) -> None:
        if len(self.dielectrics) != max(0, len(self.copper) - 1):
            raise ValueError("a stackup needs one dielectric between each pair of copper layers")
        if any(d.thickness_mm <= 0 for d in self.dielectrics) or \
                any(c.thickness_mm <= 0 for c in self.copper):
            raise ValueError("every layer of a stackup must have a positive thickness")

    @property
    def total_mm(self) -> float:
        return (sum(c.thickness_mm for c in self.copper) +
                sum(d.thickness_mm for d in self.dielectrics))

    def _index(self, layer: str) -> int:
        for i, c in enumerate(self.copper):
            if c.name == layer:
                return i
        raise KeyError(f"{layer} is not in the stackup")

    def copper_mm(self, layer: str) -> float:
        return self.copper[self._index(layer)].thickness_mm

    def dielectric_between(self, a: str, b: str) -> float:
        """Insulation thickness between two copper layers (copper between them counts)."""
        i, j = sorted((self._index(a), self._index(b)))
        return (sum(d.thickness_mm for d in self.dielectrics[i:j]) +
                sum(c.thickness_mm for c in self.copper[i + 1:j]))

    def z_of(self, layer: str) -> float:
        """Height of a copper layer's outer face above the bottom of the board:
        the top layer at the full thickness, the bottom layer at zero (scene3d's
        convention)."""
        i = self._index(layer)
        if i == len(self.copper) - 1:
            return 0.0
        below = (sum(d.thickness_mm for d in self.dielectrics[i:]) +
                 sum(c.thickness_mm for c in self.copper[i + 1:]))
        return below + (self.copper[i].thickness_mm if i == 0 else 0.0)

    @staticmethod
    def from_dict(d: dict) -> "Stackup":
        return Stackup(
            copper=[CopperLayer(**c) for c in d["copper"]],
            dielectrics=[Dielectric(**{**x, "er": Range(**x["er"])}) for x in d["dielectrics"]],
            name=d.get("name", "generic FR-4"), source=d.get("source", DEFAULT_SOURCE))


def _names(layers: int | list[str]) -> list[str]:
    if isinstance(layers, int):
        if layers < 2:
            return ["F.Cu"]
        return ["F.Cu"] + [f"In{i}.Cu" for i in range(1, layers - 1)] + ["B.Cu"]
    return list(layers)


def two_layer(total_mm: float = 1.6, copper_mm: float = ONE_OZ_MM,
              names: tuple[str, str] = ("F.Cu", "B.Cu")) -> Stackup:
    core = total_mm - 2 * copper_mm
    if core <= 0:
        raise ValueError(f"{total_mm} mm cannot hold two {copper_mm} mm copper layers")
    return Stackup([CopperLayer(names[0], copper_mm), CopperLayer(names[1], copper_mm)],
                   [Dielectric(round(core, 6))])


def default_stackup(layers: int | list[str] = 2, total_mm: float = 1.6) -> Stackup:
    """1.6 mm FR-4, 1 oz copper. Above two layers the dielectric is split evenly,
    which is an assumption, not any fab's build: the source says so."""
    names = _names(layers)
    if len(names) == 2:
        return two_layer(total_mm, names=(names[0], names[1]))
    if len(names) == 1:
        return Stackup([CopperLayer(names[0])], [], source=DEFAULT_SOURCE)
    gap = (total_mm - len(names) * ONE_OZ_MM) / (len(names) - 1)
    return Stackup([CopperLayer(n) for n in names],
                   [Dielectric(round(gap, 6)) for _ in names[1:]],
                   source=DEFAULT_SOURCE + " Dielectric split evenly between layers (assumed).")
