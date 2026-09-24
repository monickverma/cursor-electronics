"""
Stage 5 — firmware is shown only once it compiles. Gate 1.

`generators/firmware/project.py` turns a design into a PlatformIO project;
`api/routes/firmware.py::firmware_view` is the one gate the generate, patch
and firmware routes go through; `tasks/firmware_task.py` builds it in Celery.
`brain/decisions.md` [2026-09-23] Stage 5, item 7.

The unit tests pin the gate's logic with the database and the broker stubbed:
no response ever carries source whose build has not passed. The compile matrix
(`slow`) builds every firmware variant the generators emit, on every board,
with the real toolchains — skipped where PlatformIO is not installed.
"""

import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import api.routes.firmware as firmware_route
from core.intent_ir import IntentIR, Producer, Provenance
from core.ir_examples import ALL_EXAMPLES
from data.mcu_targets import TARGETS
from db.migrations import MIGRATIONS, is_safe
from db.models import FirmwareBuild
from generators.firmware.compile_gate import compile_project, platformio_available
from generators.firmware.project import LIBRARIES, PLATFORM_VERSIONS, project_for
from generators.realize import realize
from generators.registry import default_registry
from tasks.firmware_task import compile_firmware

SCHEMA_SQL = Path(__file__).resolve().parent.parent / "backend" / "db" / "schema.sql"
REGISTRY = default_registry()

#: One requirement per firmware template, and a second that changes what the
#: sketch says (pins, thresholds, baud), so the matrix sees every branch.
REQUIREMENTS = {
    "led_indicator": [{"targets": {"led_current_ma": 10}},
                      {"targets": {"led_current_ma": 5}}],
    "temperature_humidity_sensor": [
        {"constraints": {"cable_length_m": 2}, "preferences": {"alert_threshold_c": 30}},
        {"constraints": {"cable_length_m": 10}, "preferences": {"alert_threshold_c": 45}}],
    "modbus_rtu_master": [{}, {"constraints": {"baud": 19200}}],
}


def _design(function, mcu, extra=None):
    req = {"function": function, "targets": {}, "constraints": {}, "preferences": {}}
    for key, value in (extra or {}).items():
        req[key] = dict(value)
    req["constraints"]["mcu"] = mcu
    intent = IntentIR(intent_id=f"fw-{function}-{mcu}", requirements=req,
                      provenance=Provenance(producer=Producer.FORM))
    dispatch = REGISTRY.dispatch(intent)
    assert dispatch.accepted, dispatch.refusal_summary()
    return realize(dispatch.generator, intent)


def _variants():
    for function, extras in REQUIREMENTS.items():
        for n, extra in enumerate(extras):
            for mcu in TARGETS:
                yield pytest.param(function, mcu, extra, id=f"{function}-{n}-{mcu}")


def _rc_filter():
    intent = IntentIR(intent_id="fw-rc", provenance=Provenance(producer=Producer.FORM), requirements={
        "function": "low_pass_filter", "targets": {"cutoff_hz": 1000}, "constraints": {}, "preferences": {}})
    return realize(REGISTRY.dispatch(intent).generator, intent)


# ── The project ───────────────────────────────────────────────────────────────

class TestTheProjectIsDeterministic:
    def test_same_design_same_bytes_same_hash(self):
        a, b = project_for(_design("led_indicator", "esp32_devkitc")), project_for(_design("led_indicator", "esp32_devkitc"))
        assert a.files == b.files and a.hash == b.hash

    def test_the_board_is_part_of_the_hash(self):
        hashes = {project_for(_design("led_indicator", mcu)).hash for mcu in TARGETS}
        assert len(hashes) == len(TARGETS)

    def test_a_design_with_no_microcontroller_has_no_project(self):
        assert project_for(_rc_filter()) is None

    @pytest.mark.parametrize("mcu", list(TARGETS))
    def test_platform_and_libraries_are_pinned(self, mcu):
        project = project_for(_design("modbus_rtu_master", mcu))
        ini = project.file("platformio.ini")
        target = TARGETS[mcu]
        assert f"platform = {target.platform}@{PLATFORM_VERSIONS[target.platform]}" in ini
        assert f"board = {target.pio_board}" in ini
        for lib in LIBRARIES["modbus_master.ino.j2"]:
            assert re.search(rf"^\s+{re.escape(lib)}$", ini, re.M), lib
            assert "@" in lib, f"{lib} is not pinned"

    def test_the_task_refuses_files_that_do_not_match_their_hash(self):
        project = project_for(_design("led_indicator", "arduino_uno"))
        tampered = [list(f) for f in project.files]
        tampered[1][1] += "\n// edited after hashing\n"
        result = compile_firmware.run(project.hash, tampered, project.target)
        assert result["status"] == "failed" and "hash" in result["log"]


# ── The gate: never unbuilt source ────────────────────────────────────────────

class _Row:
    def __init__(self, status, log="", created_at=None):
        self.status, self.log = status, log
        self.created_at = created_at or datetime.now(timezone.utc)


@pytest.fixture
def builds(monkeypatch):
    """The firmware_builds table and the broker, in memory."""
    state = {"rows": {}, "dispatched": [], "finished": [], "requeued": [], "poll": None, "broker_down": False}

    async def get(db, build_hash):
        return state["rows"].get(build_hash)

    async def queue(db, build_hash, target):
        state["rows"].setdefault(build_hash, _Row("queued"))

    async def requeue(db, build_hash):
        state["rows"][build_hash].created_at = datetime.now(timezone.utc)
        state["requeued"].append(build_hash)

    async def finish(db, build_hash, status, log, seconds):
        state["rows"][build_hash] = _Row(status, log)
        state["finished"].append((build_hash, status))

    def dispatch(args, task_id):
        if state["broker_down"]:
            raise ConnectionRefusedError("redis is not up")
        state["dispatched"].append(task_id)

    monkeypatch.setattr(firmware_route, "get_firmware_build", get)
    monkeypatch.setattr(firmware_route, "queue_firmware_build", queue)
    monkeypatch.setattr(firmware_route, "requeue_firmware_build", requeue)
    monkeypatch.setattr(firmware_route, "finish_firmware_build", finish)
    monkeypatch.setattr(firmware_route.compile_firmware, "apply_async", dispatch)
    monkeypatch.setattr(firmware_route, "_poll", lambda h: state["poll"])
    return state


def _view(ir):
    return asyncio.run(firmware_route.firmware_view(None, ir))


class TestTheGateNeverShowsUnbuiltSource:
    def test_no_microcontroller_no_firmware_no_build(self, builds):
        view = _view(_rc_filter())
        assert view.status == "none" and view.firmware is None and not builds["dispatched"]

    def test_a_new_project_is_queued_and_its_source_withheld(self, builds):
        ir = _design("temperature_humidity_sensor", "blackpill_f411ce", REQUIREMENTS["temperature_humidity_sensor"][0])
        view = _view(ir)
        project = project_for(ir)
        assert view.status == "compiling" and view.firmware is None and view.platformio_ini is None
        assert builds["dispatched"] == [f"firmware-{project.hash}"]
        assert builds["rows"][project.hash].status == "queued"
        assert view.build == project.hash and view.target == "blackpill_f411ce"

    def test_a_second_view_while_it_builds_does_not_queue_it_again(self, builds):
        ir = _design("led_indicator", "esp32_devkitc")
        _view(ir)
        assert _view(ir).status == "compiling"
        assert len(builds["dispatched"]) == 1

    def test_no_broker_means_unavailable_not_source(self, builds):
        builds["broker_down"] = True
        view = _view(_design("led_indicator", "arduino_uno"))
        assert view.status == "unavailable" and view.firmware is None
        assert not builds["rows"], "a build that was never dispatched must not be recorded as queued"

    def test_a_build_whose_result_was_lost_is_dispatched_again(self, builds):
        # The worker died, or the result backend expired the result before
        # anyone polled: without this the design would say "compiling" forever.
        ir = _design("led_indicator", "esp32_devkitc")
        build_hash = project_for(ir).hash
        stale = datetime.now(timezone.utc) - timedelta(seconds=firmware_route.STALE_AFTER_S + 60)
        builds["rows"][build_hash] = _Row("queued", created_at=stale)
        view = _view(ir)
        assert view.status == "compiling" and view.firmware is None
        assert builds["dispatched"] == [f"firmware-{build_hash}"] and builds["requeued"] == [build_hash]
        _view(ir)
        assert len(builds["dispatched"]) == 1, "a requeued build restarts its clock"

    def test_a_build_still_within_its_time_is_not_dispatched_again(self, builds):
        ir = _design("led_indicator", "esp32_devkitc")
        recent = datetime.now(timezone.utc) - timedelta(seconds=firmware_route.STALE_AFTER_S - 60)
        builds["rows"][project_for(ir).hash] = _Row("queued", created_at=recent)
        assert _view(ir).status == "compiling"
        assert not builds["dispatched"] and not builds["requeued"]

    def test_the_worker_loads_the_compile_task(self):
        # Importing the task here would register it regardless, so ask what a
        # worker process imports: without this, every build is "unregistered".
        from worker import app

        assert "tasks.firmware_task" in app.conf.include

    def test_a_finished_build_is_recorded_when_polled(self, builds):
        ir = _design("modbus_rtu_master", "esp32_devkitc")
        _view(ir)
        builds["poll"] = {"status": "passed", "log": "[SUCCESS]", "seconds": 4.2}
        view = _view(ir)
        project = project_for(ir)
        assert view.status == "compiled" and view.firmware == project.source
        assert view.platformio_ini == project.file("platformio.ini")
        assert builds["finished"] == [(project.hash, "passed")]

    def test_a_cached_pass_is_shown_without_building_again(self, builds):
        ir = _design("led_indicator", "blackpill_f411ce")
        builds["rows"][project_for(ir).hash] = _Row("passed")
        view = _view(ir)
        assert view.status == "compiled" and view.firmware and not builds["dispatched"]

    def test_a_failed_build_shows_its_log_and_not_its_source(self, builds):
        ir = _design("modbus_rtu_master", "blackpill_f411ce")
        builds["rows"][project_for(ir).hash] = _Row("failed", "main.ino:17: error: ...")
        view = _view(ir)
        assert view.status == "failed" and view.firmware is None and view.platformio_ini is None
        assert "error" in view.log and "not shown" in view.message


# ── The cache table: fresh and migrated volumes agree ─────────────────────────

class TestTheBuildCacheTable:
    def _migration(self):
        found = [s for s in MIGRATIONS if "firmware_builds" in s]
        assert len(found) == 1
        return found[0]

    def _columns(self, ddl):
        body = ddl.split("(", 1)[1].rsplit(")", 1)[0]
        return {part.split()[0] for part in body.split(",") if part.strip()}

    def test_the_migration_is_safe_on_every_start(self):
        assert is_safe(self._migration())
        assert not is_safe("CREATE TABLE firmware_builds (build_hash VARCHAR(64))"), "not idempotent"

    def test_schema_sql_the_migration_and_the_model_have_the_same_columns(self):
        schema = SCHEMA_SQL.read_text(encoding="utf-8")
        block = schema.split("CREATE TABLE firmware_builds (", 1)[1].split(");", 1)[0]
        in_schema = {line.split()[0] for line in block.splitlines() if line.strip() and not line.strip().startswith("--")}
        assert in_schema == self._columns(self._migration()) == set(FirmwareBuild.__table__.columns.keys())


# ── Gate 1: every emitted variant compiles, on every board ───────────────────

needs_platformio = pytest.mark.skipif(not platformio_available(), reason="PlatformIO not installed")


@pytest.mark.slow
@needs_platformio
class TestEveryVariantCompiles:
    @pytest.mark.parametrize("function, mcu, extra", list(_variants()))
    def test_generator_output(self, function, mcu, extra):
        project = project_for(_design(function, mcu, extra))
        result = compile_project(project)
        assert result.status == "passed", result.log[-2000:]

    @pytest.mark.parametrize("ir", [ir for ir in ALL_EXAMPLES if project_for(ir) is not None],
                             ids=lambda ir: ir.circuit_id)
    def test_phase_1_examples(self, ir):
        result = compile_project(project_for(ir))
        assert result.status == "passed", result.log[-2000:]


# ── Every route's annotations resolve where the pinned FastAPI looks ─────────

def test_every_route_annotation_resolves_in_its_endpoints_globals():
    """
    FastAPI 0.115 (the pinned version) reads a string annotation against the
    *endpoint's* ``__globals__``. A route module with ``from __future__ import
    annotations`` whose endpoint is wrapped by ``@limiter.limit`` hands it
    slowapi's globals instead, where ``AsyncSession`` does not exist — CI
    failed at collection that way while a newer local FastAPI, which unwraps,
    passed. This checks every route the way the pinned version does.
    """
    import inspect

    from fastapi.routing import APIRoute

    from main import app

    unresolved = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        call = route.endpoint
        namespace = getattr(call, "__globals__", {})
        for name, param in inspect.signature(call).parameters.items():
            if isinstance(param.annotation, str):
                try:
                    eval(param.annotation, namespace)  # noqa: S307 — annotations from our own modules
                except NameError as exc:
                    unresolved.append(f"{route.path} {name}: {exc}")
    assert unresolved == []
