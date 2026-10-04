"""
Write the bench designs' firmware as PlatformIO projects, ready to flash — D1.

    python scripts/bench_firmware.py fieldwork/firmware
    cd fieldwork/firmware/led_indicator && pio run -t upload

The designs are the ones `bench_template.py --standard` names (the LED, DHT22
and RS-485 nodes on the Uno — the three with firmware), built by the same path a
request takes: form → IntentIR → generator → realize → `project_for`. Each
project's folder carries `PROJECT_SHA256`, the hash the compile gate keys its
build by, so what you flash is provably what the repository compiled.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
for key, value in {"ANTHROPIC_API_KEY": "", "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
                   "REDIS_URL": "redis://localhost:6379/0", "SECRET_KEY": "x" * 40}.items():
    os.environ.setdefault(key, value)

from ai.form_producer import FormProducer  # noqa: E402
from bench_template import STANDARD  # noqa: E402
from generators.firmware.project import project_for  # noqa: E402
from generators.realize import realize  # noqa: E402
from generators.registry import default_registry  # noqa: E402


def write_firmware(folder: Path) -> list:
    registry = default_registry()
    written = []
    for name, (function, fields) in STANDARD.items():
        intent = FormProducer(registry).build(function, fields)
        dispatch = registry.dispatch(intent)
        project = project_for(realize(dispatch.generator, intent))
        if project is None:
            continue                     # passive designs have no firmware
        target = folder / name
        for path, content in project.files:
            (target / path).parent.mkdir(parents=True, exist_ok=True)
            (target / path).write_text(content, encoding="utf-8", newline="\n")
        (target / "PROJECT_SHA256").write_text(project.hash + "\n", encoding="utf-8", newline="\n")
        written.append((target, project.board, project.hash))
    return written


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    for target, board, digest in write_firmware(Path(sys.argv[1])):
        print(f"wrote {target}  ({board}, {digest[:12]})")
