"""
The explanation is delivered apart from the design ([2026-10-05]).

Generate queues it and returns; GET /design/{id}/explanation says where it
stands and stores it once written; a failure is kept and shown; with no queue
the route writes it inline as before.

[2026-10-21, F-0006] The route used to re-queue the task on every poll that
landed while it was still running, because the task id was deterministic and
each re-queue replaced the attempt in flight. The attempt ledger (a row per
design version in PostgreSQL) makes the count durable, and each attempt gets
its own task id, so a retry adds an attempt instead of destroying one.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.routes import design as design_route
from api.routes import explanation as explanation_route
from api.routes.auth import get_current_user
from core.intent_ir import IntentIR, Producer, Provenance
from db.models import get_db
from generators.realize import realize
from generators.registry import default_registry
from main import app
from middleware.rate_limit import limiter
from observability.request_log import RequestLogger
from tasks.explain_task import explain_design


def rc_intent():
    return IntentIR(requirements={"function": "low_pass_filter", "targets": {"cutoff_hz": 1000},
                                  "constraints": {"supply_v": 5}, "preferences": {}},
                    provenance=Provenance(producer=Producer.FORM))


@pytest.fixture(scope="module")
def design():
    intent = rc_intent()
    return realize(default_registry().dispatch(intent).generator, intent)


@pytest.fixture
def client(monkeypatch):
    intent = rc_intent()

    class _Producer:
        def __init__(self, registry):
            pass

        def produce(self, prompt):
            return intent

    async def nothing(*args, **kwargs):
        return None

    async def record(self, row):
        return True

    async def record_attempt(db, circuit_id, version, attempts, task_id):
        return None

    monkeypatch.setattr(design_route, "IntentProducer", _Producer)
    monkeypatch.setattr(design_route, "save_design", nothing)
    monkeypatch.setattr(design_route, "save_output", nothing)
    monkeypatch.setattr(design_route, "record_explanation_attempt", record_attempt)
    monkeypatch.setattr(design_route.run_simulation, "apply_async", lambda **kw: None)
    monkeypatch.setattr(RequestLogger, "record", record)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u-explain")
    app.dependency_overrides[get_db] = lambda: None
    was_enabled, limiter.enabled = limiter.enabled, False
    yield TestClient(app)
    limiter.enabled = was_enabled
    app.dependency_overrides.clear()


class TestGenerateDoesNotWait:
    def test_the_explanation_is_queued_and_the_design_returned(self, client, monkeypatch):
        queued = []
        monkeypatch.setattr(design_route, "queue_explanation",
                            lambda ir, attempt=1: queued.append(ir.circuit_id) or f"task-{ir.circuit_id}")
        monkeypatch.setattr(design_route.ExplanationEngine, "explain",
                            lambda self, ir, v: pytest.fail("the route must not write it inline"))
        res = client.post("/design/generate", json={"prompt": "1 kHz low-pass"})
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["explanation"] == "" and body["explanation_status"] == "writing"
        assert queued == [body["circuit_id"]]

    def test_the_first_attempt_is_written_to_the_ledger(self, client, monkeypatch):
        """Without the ledger row the poll cannot tell a lost task from a slow
        one, and re-queues on every poll — which is the loop F-0006 names."""
        recorded = []

        async def record_attempt(db, circuit_id, version, attempts, task_id):
            recorded.append((circuit_id, version, attempts, task_id))

        monkeypatch.setattr(design_route, "queue_explanation",
                            lambda ir, attempt=1: f"task-{ir.circuit_id}")
        monkeypatch.setattr(design_route, "record_explanation_attempt", record_attempt)
        res = client.post("/design/generate", json={"prompt": "1 kHz low-pass"})
        assert res.status_code == 201, res.text
        body = res.json()
        assert recorded == [(body["circuit_id"], body["version"], 1, f"task-{body['circuit_id']}")]

    def test_with_no_queue_it_is_written_inline(self, client, monkeypatch):
        monkeypatch.setattr(design_route.ExplanationEngine, "__init__", lambda self: None)
        monkeypatch.setattr(design_route.ExplanationEngine, "explain", lambda self, ir, v: "R1 sets the cutoff.")
        body = client.post("/design/generate", json={"prompt": "1 kHz low-pass"}).json()
        assert body["explanation"] == "R1 sets the cutoff." and body["explanation_status"] == "written"


class _Outputs:
    """generated_outputs, in memory, for the route's two seams."""

    def __init__(self):
        self.rows = {}

    async def get_output(self, db, circuit_id, output_type, file_name):
        text = self.rows.get((circuit_id, output_type, file_name))
        return None if text is None else SimpleNamespace(file_content=text)

    async def save_output(self, db, circuit_id, output_type, content, file_name):
        self.rows[(circuit_id, output_type, file_name)] = content


@pytest.fixture
def outputs(monkeypatch):
    store = _Outputs()
    monkeypatch.setattr(explanation_route, "get_output", store.get_output)
    monkeypatch.setattr(explanation_route, "save_output", store.save_output)
    return store


class _Ledger:
    """The attempt ledger (explanation_attempts), in memory.

    It is a real table in PostgreSQL; here it is the same shape, so the route
    reads and writes it the way it does in production. A row is
    (attempts, task_id, queued_at).
    """

    def __init__(self):
        self.rows = {}

    def _key(self, circuit_id, version):
        return (circuit_id, version)

    async def get_explanation_attempt(self, db, circuit_id, version):
        row = self.rows.get(self._key(circuit_id, version))
        if row is None:
            return None
        return SimpleNamespace(attempts=row["attempts"], task_id=row["task_id"],
                               queued_at=row["queued_at"])

    async def record_explanation_attempt(self, db, circuit_id, version, attempts, task_id):
        self.rows[self._key(circuit_id, version)] = {
            "attempts": attempts, "task_id": task_id, "queued_at": _old(),
        }


def _old(seconds=1000.0):
    """A timestamp far enough in the past that the staleness window is open."""
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


@pytest.fixture
def ledger(monkeypatch):
    store = _Ledger()
    monkeypatch.setattr(explanation_route, "get_explanation_attempt", store.get_explanation_attempt)
    monkeypatch.setattr(explanation_route, "record_explanation_attempt", store.record_explanation_attempt)
    return store


def view(design, age=0.0):
    return asyncio.run(explanation_route.explanation_view(None, design, age))


class TestWhereTheExplanationStands:
    def test_writing_until_the_task_answers(self, design, outputs, ledger, monkeypatch):
        monkeypatch.setattr(explanation_route, "_poll", lambda task_id: None)
        assert view(design).status == "writing"

    def test_written_once_and_kept(self, design, outputs, ledger, monkeypatch):
        monkeypatch.setattr(explanation_route, "_poll",
                            lambda task_id: {"status": "written", "explanation": "because R1", "error": None})
        first = view(design)
        assert (first.status, first.explanation) == ("written", "because R1")
        # The task result has expired; the stored text is what is read now.
        monkeypatch.setattr(explanation_route, "_poll", lambda task_id: pytest.fail("stored: no poll"))
        assert view(design).explanation == "because R1"

    def test_a_failure_is_kept_with_its_reason(self, design, outputs, ledger, monkeypatch):
        monkeypatch.setattr(explanation_route, "_poll",
                            lambda task_id: {"status": "failed", "explanation": "", "error": "timed out after 150 s"})
        failed = view(design)
        assert failed.status == "failed" and "150 s" in failed.error and failed.explanation == ""
        monkeypatch.setattr(explanation_route, "_poll", lambda task_id: None)
        assert view(design).status == "failed"

    def test_no_worker_is_said_not_hidden(self, design, outputs, ledger, monkeypatch):
        monkeypatch.setattr(explanation_route, "_poll", lambda task_id: None)
        stale = view(design, age=explanation_route.STALE_AFTER_S + 1)     # conftest: no queue
        assert stale.status == "unavailable" and "unavailable" in stale.error

    def test_one_explanation_per_version(self):
        assert explanation_route._task_id("c", 1) != explanation_route._task_id("c", 2)


class TestTheLoopIsClosed:
    """F-0006. The route re-queued the task on every poll that landed while
    it was still running, and each re-queue replaced the attempt in flight —
    so the result was never seen and the loop never ended."""

    def test_a_poll_that_lands_while_the_task_is_running_queues_nothing(
        self, design, outputs, ledger, monkeypatch):
        queued = []
        monkeypatch.setattr(explanation_route, "_poll", lambda task_id: None)
        monkeypatch.setattr(explanation_route, "queue_explanation",
                            lambda ir, attempt=1: queued.append(attempt))
        monkeypatch.setattr(explanation_route, "_is_lost", lambda task_id, age_s: False)
        # The first attempt is on the ledger and is running.
        asyncio.run(ledger.record_explanation_attempt(
            None, design.circuit_id, design.version, 1, "t-1"))
        for _ in range(5):
            assert view(design, age=explanation_route.STALE_AFTER_S + 1).status == "writing"
        assert queued == [], "a running task must not be re-queued"

    def test_the_number_of_model_calls_is_bounded(self, design, outputs, ledger, monkeypatch):
        queued = []
        monkeypatch.setattr(explanation_route, "_poll", lambda task_id: None)
        monkeypatch.setattr(explanation_route, "queue_explanation",
                            lambda ir, attempt=1: queued.append(attempt) or f"t-{attempt}")
        monkeypatch.setattr(explanation_route, "_is_lost", lambda task_id, queued_at: True)
        for _ in range(10):
            view(design, age=explanation_route.STALE_AFTER_S + 1)
        assert len(queued) <= explanation_route.MAX_ATTEMPTS

    def test_the_retry_counter_survives_across_calls(self, design, outputs, ledger, monkeypatch):
        """The count is read from the database, not from memory.

        Each call may queue one attempt, but the count on the ledger is what
        stops it: once the budget is spent, a further poll queues nothing.
        """
        queued = []
        monkeypatch.setattr(explanation_route, "_poll", lambda task_id: None)
        monkeypatch.setattr(explanation_route, "queue_explanation",
                            lambda ir, attempt=1: queued.append(attempt) or f"t-{attempt}")
        monkeypatch.setattr(explanation_route, "_is_lost", lambda task_id, age_s: True)
        for _ in range(10):
            view(design, age=explanation_route.STALE_AFTER_S + 1)
        # The budget, and no more.
        assert len(queued) == explanation_route.MAX_ATTEMPTS
        assert ledger.rows[(design.circuit_id, design.version)]["attempts"] == \
            explanation_route.MAX_ATTEMPTS

    def test_the_budget_spent_is_reported_not_retried_forever(
        self, design, outputs, ledger, monkeypatch):
        monkeypatch.setattr(explanation_route, "_poll", lambda task_id: None)
        monkeypatch.setattr(explanation_route, "_is_lost", lambda task_id, age_s: True)
        asyncio.run(ledger.record_explanation_attempt(
            None, design.circuit_id, design.version, explanation_route.MAX_ATTEMPTS, "t-1"))
        out = view(design, age=explanation_route.STALE_AFTER_S + 1)
        assert out.status == "unavailable"
        assert str(explanation_route.MAX_ATTEMPTS) in out.error

    def test_a_retry_does_not_replace_the_attempt_in_flight(self):
        """Distinct ids per attempt: a retry must not cancel the running one."""
        first = explanation_route._attempt_task_id("c", 1, 1)
        second = explanation_route._attempt_task_id("c", 1, 2)
        assert first != second
        assert first == explanation_route._task_id("c", 1)
        assert explanation_route._attempt_task_id("c", 1, 1) == \
            explanation_route._attempt_task_id("c", 1, 1)

    def test_a_running_task_is_not_lost(self):
        """Celery says PENDING for a task that was never sent AND for one that
        is queued behind other work. STARTED means it is alive."""
        import celery.result as celery_result

        class _Result:
            def __init__(self, state):
                self.state = state

        original = celery_result.AsyncResult
        try:
            for state in ("STARTED", "RETRY", "RECEIVED", "SUCCESS", "FAILURE"):
                celery_result.AsyncResult = lambda task_id, app=None, s=state: _Result(s)
                assert explanation_route._is_lost("t-1", 1000.0) is False, state
            # PENDING long after it was queued is the one that reads as lost.
            celery_result.AsyncResult = lambda task_id, app=None: _Result("PENDING")
            assert explanation_route._is_lost("t-1", 1000.0) is True
            # PENDING, but only just queued: it is waiting, not lost.
            assert explanation_route._is_lost("t-1", 1.0) is False
            # Nothing was ever queued: there is nothing to wait for.
            assert explanation_route._is_lost(None, 1000.0) is True
        finally:
            celery_result.AsyncResult = original

    def test_a_poll_while_the_task_is_still_running_never_re_queues(
        self, design, outputs, ledger, monkeypatch):
        """The end-to-end shape of the bug: five polls, one task, one call."""
        queued = []
        monkeypatch.setattr(explanation_route, "_poll", lambda task_id: None)
        monkeypatch.setattr(explanation_route, "queue_explanation",
                            lambda ir, attempt=1: queued.append(attempt) or f"t-{attempt}")
        # Celery says the task is running: not lost.
        class _Result:
            state = "STARTED"
        import celery.result as celery_result
        original = celery_result.AsyncResult
        celery_result.AsyncResult = lambda task_id, app=None: _Result()
        try:
            asyncio.run(explanation_route.record_explanation_attempt(
                None, design.circuit_id, design.version, 1, "t-1"))
            for _ in range(5):
                view(design, age=explanation_route.STALE_AFTER_S + 1)
        finally:
            celery_result.AsyncResult = original
        assert queued == []


class TestTheTaskNeverRaises:
    @pytest.fixture(autouse=True)
    def _no_state(self, monkeypatch):
        monkeypatch.setattr(explain_design, "update_state", lambda **kw: None)

    def test_it_returns_the_text(self, design, monkeypatch):
        from ai import explainer

        monkeypatch.setattr(explainer.ExplanationEngine, "__init__", lambda self: None)
        monkeypatch.setattr(explainer.ExplanationEngine, "explain", lambda self, ir, v: "If R1 doubles, f_c halves.")
        out = explain_design.run(design.model_dump(mode="json"))
        assert out == {"status": "written", "explanation": "If R1 doubles, f_c halves.", "error": None}

    @pytest.mark.parametrize("raised, fragment", [
        (ValueError("explanation truncated"), "ValueError: explanation truncated"),
        (None, "returned no text"),
    ])
    def test_a_failure_is_a_result(self, design, monkeypatch, raised, fragment):
        from ai import explainer

        def explain(self, ir, v):
            if raised:
                raise raised
            return "   "

        monkeypatch.setattr(explainer.ExplanationEngine, "__init__", lambda self: None)
        monkeypatch.setattr(explainer.ExplanationEngine, "explain", explain)
        out = explain_design.run(design.model_dump(mode="json"))
        assert out["status"] == "failed" and fragment in out["error"] and out["explanation"] == ""
