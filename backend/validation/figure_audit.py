"""
Are the claims' figure declarations complete? D7's guard.

`brain/decisions.md` [2026-09-24] D1, D2, D7: a claim cites D7 while any part
figure it *declares* is untrusted, so a figure it reads without declaring
would let D7 drop once the declared ones are verified. This audit catches
that by experiment: each figure of each part in a design is moved (×1.37)
in the table that owns it, the generator is rebuilt, and every claim whose
sentence, detail or verdict changed must name that figure — or, declaring
nothing, keep D7 by hand.

A move that changes the design itself (a figure the generator *chooses*
with) cannot be attributed to one claim, nor can one the envelope refuses;
it is retried smaller, downward, and — for a min/typ/max figure — with only
the bounds moved (the design is chosen on the typical), and otherwise
reported as skipped, never counted as clean. Figures a module asserts equal
across parts (the TIA-485 threshold and load on both transceivers) move
together.

Modules copy some figures at import, so each move reloads them. Run it in a
process of its own: `python -m validation.figure_audit` prints the report.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import sys
from contextlib import ExitStack, contextmanager
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

GENERATOR_CLASSES = {
    "rc_lowpass": ("generators.rc_lowpass", "RCLowPassGenerator"),
    "voltage_divider": ("generators.voltage_divider", "VoltageDividerGenerator"),
    "led_indicator": ("generators.led_indicator", "LedIndicatorGenerator"),
    "dht22_node": ("generators.dht22_node", "DHT22NodeGenerator"),
    "rs485_node": ("generators.rs485_node", "RS485NodeGenerator"),
}

#: Modules that copy figures into module-level constants, in import order.
_RELOAD = ("generators.common", "generators.netlist.models", "generators.arduino_parts")


#: Parts whose shared figures a module asserts equal; they move together.
_LINKED = ({"MAX485ECSA", "MAX3485ECSA"},)

#: (factor, which entries of a min/typ/max figure move). Tried in order.
ATTEMPTS = ((1.37, "all"), (1.02, "all"), (0.98, "all"), (1.37, "bounds"), (1.02, "bounds"))


def _scale(value: Any, factor: float, mode: str = "all") -> Optional[Any]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value * factor if mode == "all" else None
    if isinstance(value, dict) and value and all(isinstance(v, (int, float)) for v in value.values()):
        return {k: (v if mode == "bounds" and k in ("typ", "nominal") else v * factor) for k, v in value.items()}
    return None


@contextmanager
def perturbed(figure_id: str, factor: float, mode: str = "all") -> Iterator[bool]:
    """Move one figure (and any it is linked to); yields False if it cannot move that way."""
    from data.figures import owner_and_key

    owner, key = owner_and_key(figure_id)
    group = next((g for g in _LINKED if owner in g), {owner})
    with ExitStack() as stack:
        moved = [stack.enter_context(_moved_one(o, key, factor, mode)) for o in sorted(group)
                 if o == owner or _has(o, key)]
        yield all(moved)


def _has(owner: str, key: str) -> bool:
    from data.component_constraints import COMPONENT_CONSTRAINTS

    return key in COMPONENT_CONSTRAINTS.get(owner, {})


@contextmanager
def _moved_one(owner: str, key: str, factor: float, mode: str) -> Iterator[bool]:
    from data.component_constraints import COMPONENT_CONSTRAINTS
    from data.parts import CAPACITORS, RESISTOR_SERIES

    for table in (RESISTOR_SERIES, CAPACITORS):
        if owner in table:
            original = table[owner]
            moved = _scale(getattr(original, key), factor, mode)
            if moved is None:
                yield False
                return
            table[owner] = dataclasses.replace(original, **{key: moved})
            try:
                yield True
            finally:
                table[owner] = original
            return
    entry = COMPONENT_CONSTRAINTS.get(owner)
    moved = _scale(entry.get(key), factor, mode) if entry is not None else None
    if moved is None:
        yield False
        return
    original = entry[key]
    entry[key] = moved
    try:
        yield True
    finally:
        entry[key] = original


def _fresh_generator(name: str):
    for module in _RELOAD:
        importlib.reload(importlib.import_module(module))
    module_name, class_name = GENERATOR_CLASSES[name]
    module = importlib.reload(importlib.import_module(module_name))
    return getattr(module, class_name)()


def _run(name: str, requirements: dict):
    from core.intent_ir import IntentIR, Producer, Provenance
    from generators.realize import realize

    intent = IntentIR(requirements=requirements, provenance=Provenance(producer=Producer.FORM))
    design = realize(_fresh_generator(name), intent)
    rows = {c["id"]: c for c in design.validation_coverage["claims"]}
    shape = tuple((c.id, c.part_number, c.value) for c in design.components)
    return rows, shape


def _fingerprint(row: dict) -> Tuple:
    return (row["verdict"], row["claim"], row.get("detail"), row.get("grade"))


def _relevant(shape: Sequence[Tuple[str, str, Any]]) -> List[str]:
    """Scalar figures of the parts placed: their own entries, their resistor series, their capacitor."""
    from data.figures import FIGURES, owner_and_key
    from data.parts import passive_figures

    owners = set()
    for _, part_number, _ in shape:
        owners.add(part_number)
        found = passive_figures(part_number)
        if found:
            owners.add(found[0])
    return [f for f in FIGURES if not f.startswith("board:") and owner_and_key(f)[0] in owners]


def audit(cases: Optional[Sequence[Tuple[str, Optional[str]]]] = None, attempts=ATTEMPTS) -> Dict[str, Any]:
    from generators.protocol import grid_of
    from validation.grid_adapters import ADAPTERS, board_cases

    report: Dict[str, Any] = {"checked": 0, "violations": [], "skipped": []}
    for name, board in cases or board_cases():
        adapter = ADAPTERS[name].build(board)
        requirements = adapter.intent_for(next(iter(grid_of(adapter.generator, board).points()))).requirements
        requirements = json.loads(json.dumps(dict(requirements)))
        base, base_shape = _run(name, requirements)
        for figure in _relevant(base_shape):
            outcome = None
            for factor, mode in attempts:
                with perturbed(figure, factor, mode) as numeric:
                    if not numeric:
                        outcome = outcome or "not numeric"
                        continue
                    try:
                        rows, shape = _run(name, requirements)
                    except Exception as exc:          # a refusal, or a module's own invariant
                        outcome = f"{type(exc).__name__}: {str(exc)[:120]}"
                        continue
                if shape != base_shape:
                    outcome = "the design changed — a figure the generator chooses with"
                    continue
                outcome = None
                for cid, row in rows.items():
                    before = base.get(cid)
                    if before is not None and _fingerprint(before) == _fingerprint(row):
                        continue
                    scope = row.get("scope") or {}
                    declared = set(scope.get("figures") or ())
                    if figure in declared or (not declared and "D7" in row["defeaters"]):
                        continue
                    report["violations"].append({"case": f"{name}@{board}", "figure": figure, "claim": cid,
                                                 "declared": sorted(declared)})
                report["checked"] += 1
                break
            if outcome is not None:
                report["skipped"].append({"case": f"{name}@{board}", "figure": figure, "why": outcome})
        _fresh_generator(name)                        # leave the modules as they were
    return report


if __name__ == "__main__":
    json.dump(audit(), sys.stdout, indent=1)
