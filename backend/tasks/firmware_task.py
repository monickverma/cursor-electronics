"""Celery task: build one firmware project with PlatformIO. Stage 5 — the compile gate."""

from __future__ import annotations

from worker import app as celery_app


@celery_app.task(bind=True, name="tasks.firmware_task.compile_firmware")
def compile_firmware(self, build_hash: str, files: list, target: str) -> dict:
    """
    Build the project whose files are given. Returns {status, log, seconds};
    `api/routes/firmware.py` records it against the hash when it polls. The
    files are checked against the hash first: a build is only ever recorded
    for the project it was asked for.
    """
    from generators.firmware.compile_gate import compile_project
    from generators.firmware.project import FirmwareProject

    project = FirmwareProject(target=target, board=target, files=tuple(tuple(f) for f in files))
    if project.hash != build_hash:
        return {"status": "failed", "log": "the project files do not match their hash", "seconds": 0.0}
    self.update_state(state="STARTED")
    result = compile_project(project)
    return {"status": result.status, "log": result.log, "seconds": result.seconds}
