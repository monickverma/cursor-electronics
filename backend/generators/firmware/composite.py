"""
Firmware for a composed board — Composition M2 (`COMPOSITION_PLAN.md`,
`brain/decisions.md` [2026-10-03]).

One sketch for the whole board, rendered by Jinja2 from the composition: its
blocks' pins (as the composer allocated them) and the project's behaviour
rules (`generators/compose.py`, a closed vocabulary). No model writes any of
it. The project is built and shown only through the existing compile gate,
exactly as a single-block design's is.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from data.mcu_targets import TARGETS
from generators.compose import READS, SETS, Composition
from generators.firmware.project import LIBRARIES, FirmwareProject, platformio_ini

TEMPLATE = "project.ino.j2"
_MODES = {"on": "MODE_ON", "off": "MODE_OFF", "blink": "MODE_BLINK", "heartbeat": "MODE_HEARTBEAT"}


def c_text(text: str) -> str:
    """Safe inside a C string literal and a comment: ASCII only, no quotes, no comment ends."""
    text = text.replace("°", "").replace("\\", "/").replace('"', "'").replace("*/", "* /")
    return "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in text)


def _float(value: float) -> str:
    return f"{float(value)!r}f"


def context(composition: Composition) -> Dict:
    project = composition.project
    target = TARGETS[project.mcu]
    fw = {b.id: target.pin(b.pin).firmware for b in composition.blocks}
    sensors = [{"id": b.id, "var": f"dht_{b.id}", "pin": fw[b.id], "pin_name": b.pin}
               for b in composition.blocks if b.function in READS]
    outputs = [{"id": b.id, "pin": fw[b.id], "pin_name": b.pin}
               for b in composition.blocks if b.function in SETS]
    index = {o["id"]: n for n, o in enumerate(outputs)}

    rules: List[Dict] = []
    for rule in project.behaviour:
        if rule.always is not None:
            rules.append({"kind": "always", "then_out": index[rule.always.block],
                          "then_mode": _MODES[rule.always.set],
                          "text": c_text(f"always: {rule.always.block} {rule.always.set}")})
            continue
        c = rule.when
        units = READS[next(b.function for b in project.blocks if b.id == c.block)][c.reads][2]
        text = f"when {c.block} {c.reads} {c.op} {c.value:g} {units}: {rule.then.block} {rule.then.set}"
        if rule.otherwise is not None:
            text += f", else {rule.otherwise.block} {rule.otherwise.set}"
        rules.append({
            "kind": "when", "guard": f"{c.block}_ok", "expr": f"{c.block}_{c.reads} {c.op} {_float(c.value)}",
            "then_out": index[rule.then.block], "then_mode": _MODES[rule.then.set],
            "else_out": index[rule.otherwise.block] if rule.otherwise else None,
            "else_mode": _MODES[rule.otherwise.set] if rule.otherwise else None,
            "text": c_text(text),
        })
    return {
        "intent": c_text(composition.circuit.intent),
        "board": c_text(target.board),
        "circuit_id": composition.circuit.circuit_id,
        "block_lines": [c_text(f"{b.id}: {b.function} on {b.pin} ({b.generator})") for b in composition.blocks],
        "sensors": sensors, "outputs": outputs, "rules": rules,
    }


def render(composition: Composition) -> str:
    env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
                      undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    return env.get_template(TEMPLATE).render(**context(composition))


def composite_project(composition: Composition) -> FirmwareProject:
    """The board's PlatformIO project — pinned platform and libraries, keyed by SHA-256 like any other."""
    target = TARGETS[composition.project.mcu]
    sensors = any(b.function in READS for b in composition.blocks)
    libraries = LIBRARIES["sensor_read.ino.j2"] if sensors else ()
    files = (("platformio.ini", platformio_ini(target, libraries)), ("src/main.ino", render(composition)))
    return FirmwareProject(target=target.id, board=target.board, files=tuple(sorted(files)))
