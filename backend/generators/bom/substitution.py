"""
Substitutes for a design's passives — Stage 6, gate 1.

`PHASE_2_PLAN_v2.md` §5 Stage 6: *no substitution surfaces that fails the
original's checks* (analytic, G1). `brain/decisions.md` [2026-09-25] Stage 6.

A substitute is never an edit to the circuit. It is a **pinned part** —
`constraints.pinned.<id> = {"part": "<part number>"}` — applied to the
requirement and re-derived through the same gate as any patch (X2): the
envelope, `generate()`, the claims, the proofs. It surfaces only if

1. the envelope accepts it;
2. the circuit is the same circuit: the SPICE netlist is byte-identical and
   no other component's electrical fields moved — only the part, and so its
   figures (tolerance, ratings, package), differ;
3. the re-derived design carries no failing claim and nothing newly not
   assessed, every claim that held on the original holds, and the grade
   floor is no worse;
4. **every property proved for the original — its own bounds — is proved
   again over the substitute's parts.** A 5% resistor in a divider passes its
   own re-derived claims but widens V_out past the band the original proved;
   judged against the original's checks, it fails, and does not surface.

Price orders what surfaces and is shown beside it; it decides nothing.
Accepting a substitute is the patch in `ops`: zero model calls, a new
version, the design re-derived.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict

from core.intent_patch import PatchOp, apply_patch
from core.ir_schema import CircuitIR, Component, ComponentType
from data.parts import CAPACITORS, RESISTOR_SERIES, capacitor, resistor_part, resistor_series, resistor_value
from generators.common import series_makes as _series_makes

#: The electrical fields of a component; the others (justification, notes,
#: confidence) are prose about the part and may mention it.
_ELECTRICAL = ("type", "part_number", "value", "package", "supply_voltage_min", "supply_voltage_max",
               "current_draw_ma")


class Substitute(BaseModel):
    """A part that passed every check the original passed."""

    model_config = ConfigDict(frozen=True)

    component_id: str
    part_number: str
    package: str
    replaces: str
    changes: Tuple[str, ...]             # what the swap changes, in words
    unit_price_usd: Optional[float] = None
    price_asof: Optional[str] = None
    price_delta_usd: Optional[float] = None
    checks: int                          # claims and properties re-checked
    ops: Tuple[Dict[str, Any], ...]      # the patch that applies it


class Rejected(BaseModel):
    """A candidate that did not surface, and the check it failed."""

    model_config = ConfigDict(frozen=True)

    component_id: str
    part_number: str
    reason: str


def candidates(component: Component) -> List[str]:
    """Catalogue parts of the same kind and value, other than the one placed."""
    if component.type == ComponentType.RESISTOR:
        series = resistor_series(component.part_number)
        ohms = resistor_value(component.part_number)
        if series is None or ohms is None:
            return []
        return [resistor_part(ohms, code) for code in RESISTOR_SERIES
                if code != series.code and _series_makes(code, ohms)]
    if component.type == ComponentType.CAPACITOR:
        placed = capacitor(component.part_number)
        if placed is None:
            return []
        return [pn for pn, cap in CAPACITORS.items()
                if pn != placed.part_number and abs(cap.farads - placed.farads) <= 1e-3 * placed.farads]
    return []


def _electrical(circuit: CircuitIR, skip: str) -> Dict[str, Tuple]:
    return {c.id: tuple(getattr(c, f) for f in _ELECTRICAL) for c in circuit.components if c.id != skip}


def _netlist(circuit: CircuitIR) -> str:
    from generators.netlist.spice import SpiceNetlistGenerator

    return SpiceNetlistGenerator().generate(circuit)


def _changes(before: Component, after: Component) -> Tuple[str, ...]:
    from data.parts import passive_figures

    out = [f"{before.id}: {before.part_number} → {after.part_number}"]
    old, new = passive_figures(before.part_number), passive_figures(after.part_number)
    if before.package != after.package:
        out.append(f"package {before.package} → {after.package}")
    if old and new:
        if old[1] != new[1]:
            out.append(f"tolerance ±{old[1] * 100:g}% → ±{new[1] * 100:g}%")
        if old[2] is not None and new[2] is not None and old[2] != new[2]:
            out.append(f"power rating {old[2] * 1000:g} → {new[2] * 1000:g} mW")
        if old[3] != new[3]:
            out.append(f"voltage rating {old[3]:g} → {new[3]:g} V")
    return tuple(out)


def _unsigned(intent: Any) -> Any:
    """
    The requirement without its signature. A substitute is a patch, and a
    patch drops a signature by design; comparing a signed original with an
    unsigned candidate would read the lost signature as a lower grade floor.
    Both are judged unsigned — the part is what is being compared.
    """
    return intent.model_copy(update={"signed_off": None}) if getattr(intent, "signed_off", None) else intent


def check(generator: Any, intent: Any, circuit: CircuitIR, component_id: str,
          part_number: str, prices: Optional[Dict[str, Dict[str, Any]]] = None,
          base: Optional[CircuitIR] = None):
    """One candidate through the gate: a `Substitute`, or a `Rejected` naming the check it failed."""
    from generators.realize import realize
    from validation.claims import prove_properties

    intent = _unsigned(intent)
    circuit = base if base is not None else realize(generator, intent)

    reject = lambda why: Rejected(component_id=component_id, part_number=part_number, reason=why)  # noqa: E731
    ops = [PatchOp(op="add", path=f"/constraints/pinned/{component_id}", value={"part": part_number})]
    try:
        outcome = apply_patch(intent, ops)
    except Exception as exc:                 # the requirement cannot take the pin
        return reject(f"the requirement cannot carry this pin: {exc}")
    decision = generator.envelope(outcome.intent)
    if not decision.accepted:
        return reject(f"refused: {decision.reason}")
    candidate = realize(generator, outcome.intent)

    # 2. The same circuit: only the part, and so its figures, differ.
    if _netlist(candidate) != _netlist(circuit):
        return reject("the re-derived netlist differs — not a like-for-like part")
    if _electrical(candidate, component_id) != _electrical(circuit, component_id):
        return reject("the re-derived design changes other parts")

    # 3. Its own claims, against the original's.
    base = {c["id"]: c for c in circuit.validation_coverage["claims"]}
    new = {c["id"]: c for c in candidate.validation_coverage["claims"]}
    failing = sorted(cid for cid, c in new.items() if c["verdict"] == "fails")
    if failing:
        return reject(f"claims fail: {', '.join(failing)}")
    newly = sorted(set(candidate.validation_coverage["not_assessed"]) - set(circuit.validation_coverage["not_assessed"]))
    if newly:
        return reject(f"no longer assessed: {', '.join(newly)}")
    held = ("holds", "holds_defeasible")
    lost = sorted(cid for cid, c in base.items() if c["verdict"] in held and new.get(cid, {}).get("verdict") not in held)
    if lost:
        return reject(f"claims that held no longer hold: {', '.join(lost)}")
    order = ("G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7")
    old_floor, new_floor = circuit.validation_coverage["grade_floor"], candidate.validation_coverage["grade_floor"]
    if old_floor and new_floor and order.index(new_floor) > order.index(old_floor):
        return reject(f"the grade floor drops from {old_floor} to {new_floor}")

    # 4. The original's own properties, over the substitute's parts.
    original = [p for p in prove_properties(generator, intent, circuit) if p.result and p.result.status == "proven"]
    for p in prove_properties(generator, intent, candidate):
        if p.spec.id in {o.spec.id for o in original} and (p.result is None or p.result.status != "proven"):
            why = p.result.detail if p.result is not None else p.error
            return reject(f"the original's property {p.spec.id} ({p.spec.label}) no longer holds: {why}")

    before = next(c for c in circuit.components if c.id == component_id)
    after = next(c for c in candidate.components if c.id == component_id)
    prices = prices or {}
    old_price, new_price = prices.get(before.part_number), prices.get(part_number)
    delta = (round(new_price["unit_price_usd"] - old_price["unit_price_usd"], 6)
             if old_price and new_price else None)
    return Substitute(
        component_id=component_id, part_number=part_number, package=after.package or "",
        replaces=before.part_number, changes=_changes(before, after),
        unit_price_usd=new_price["unit_price_usd"] if new_price else None,
        price_asof=new_price["price_asof"] if new_price else None,
        price_delta_usd=delta, checks=len(new) + len(original),
        ops=tuple(op.model_dump() for op in ops),
    )


def substitutes(generator: Any, intent: Any, circuit: CircuitIR,
                prices: Optional[Dict[str, Dict[str, Any]]] = None) -> Tuple[List[Substitute], List[Rejected]]:
    """
    Every candidate for every pinnable passive, through the gate. What
    surfaces is ordered priced-first, cheapest first, then by part number;
    price never decides whether a candidate surfaces.
    """
    from generators.realize import realize

    pinnable = _pinnable(generator)
    base = realize(generator, _unsigned(intent))
    found: List[Substitute] = []
    rejected: List[Rejected] = []
    for component in base.components:
        if component.id not in pinnable:
            continue
        for part_number in candidates(component):
            result = check(generator, intent, circuit, component.id, part_number, prices, base=base)
            (found if isinstance(result, Substitute) else rejected).append(result)
    found.sort(key=lambda s: (s.component_id, s.unit_price_usd is None, s.unit_price_usd or 0.0, s.part_number))
    return found, rejected


def _pinnable(generator: Any) -> Sequence[str]:
    import importlib

    module = importlib.import_module(type(generator).__module__)
    return tuple(getattr(module, "PINNABLE", ()))
