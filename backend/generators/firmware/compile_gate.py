"""
The compile gate: build a firmware project with PlatformIO. Stage 5.

`brain/decisions.md` [2026-09-23] Stage 5, item 7. A build takes seconds with
a warm cache and minutes without, so this is never called inline from an HTTP
handler: `tasks/firmware_task.py` runs it in a Celery worker, and CI runs it
over every firmware variant the generators emit.

Projects are written under a workspace keyed by their hash, and every build
shares one PlatformIO build cache, so compiling a variant already compiled
anywhere on this machine costs seconds.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from generators.firmware.project import FirmwareProject

#: Where projects and the shared build cache live. Overridable for workers.
WORKSPACE_ENV = "CIRCUITOS_FIRMWARE_WORKSPACE"
#: A first build downloads a toolchain; after that a build is seconds.
BUILD_TIMEOUT_S = 900
LOG_TAIL_CHARS = 6000


@dataclass(frozen=True)
class BuildResult:
    status: str                    # passed | failed
    log: str                       # the tail of PlatformIO's output
    seconds: float


def workspace() -> Path:
    root = os.environ.get(WORKSPACE_ENV) or str(Path.home() / ".circuitos" / "firmware")
    return Path(root)


def platformio_available() -> bool:
    try:
        import platformio  # noqa: F401
    except ImportError:
        return shutil.which("pio") is not None
    return True


def compile_project(project: FirmwareProject, root: Optional[Path] = None) -> BuildResult:
    """Build `project`; passed only on a zero exit and a firmware image."""
    root = root or workspace()
    project_dir = root / "projects" / project.hash
    for path, content in project.files:
        target = project_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    env = dict(os.environ, PLATFORMIO_BUILD_CACHE_DIR=str(root / "build_cache"))
    started = time.monotonic()
    try:
        run = subprocess.run(
            [sys.executable, "-m", "platformio", "run", "-d", str(project_dir)],
            capture_output=True, text=True, timeout=BUILD_TIMEOUT_S, env=env,
        )
        output = (run.stdout or "") + (run.stderr or "")
        passed = run.returncode == 0 and "[SUCCESS]" in output
    except subprocess.TimeoutExpired as exc:
        output = f"build timed out after {BUILD_TIMEOUT_S} s\n{exc.stdout or ''}"
        passed = False
    return BuildResult(status="passed" if passed else "failed", log=output[-LOG_TAIL_CHARS:],
                       seconds=round(time.monotonic() - started, 1))
