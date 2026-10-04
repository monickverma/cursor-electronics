"""
The explanation is delivered apart from the design ([2026-10-05]).

Generate queues it and returns; GET /design/{id}/explanation says where it
stands and stores it once written; a failure is kept and shown; with no queue
the route writes it inline as before.
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

    monkeypatch.setattr(design_route, "IntentProducer", _Producer)
    monkeypatch.setattr(design_route, "save_design", nothing)
    monkeypatch.setattr(design_route, "save_output", nothing)
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
        monkeypatch.setattr(design_route, "queue_explanation", queued.append)
        monkeypatch.setattr(design_route.ExplanationEngine, "explain",
                            lambda self, ir, v: pytest.fail("the route must not write it inline"))
        res = client.post("/design/generate", json={"prompt": "1 kHz low-pass"})
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["explanation"] == "" and body["explanation_status"] == "writing"
        assert [ir.circuit_id for ir in queued] == [body["circuit_id"]]

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


def view(design, age=0.0):
    return asyncio.run(explanation_route.explanation_view(None, design, age))


class TestWhereTheExplanationStands:
    def test_writing_until_the_task_answers(self, design, outputs, monkeypatch):
        monkeypatch.setattr(explanation_route, "_poll", lambda cid, v: None)
        assert view(design).status == "writing"

    def test_written_once_and_kept(self, design, outputs, monkeypatch):
        monkeypatch.setattr(explanation_route, "_poll",
                            lambda cid, v: {"status": "written", "explanation": "because R1", "error": None})
        first = view(design)
        assert (first.status, first.explanation) == ("written", "because R1")
        # The task result has expired; the stored text is what is read now.
        monkeypatch.setattr(explanation_route, "_poll", lambda cid, v: pytest.fail("stored: no poll"))
        assert view(design).explanation == "because R1"

    def test_a_failure_is_kept_with_its_reason(self, design, outputs, monkeypatch):
        monkeypatch.setattr(explanation_route, "_poll",
                            lambda cid, v: {"status": "failed", "explanation": "", "error": "timed out after 150 s"})
        failed = view(design)
        assert failed.status == "failed" and "150 s" in failed.error and failed.explanation == ""
        monkeypatch.setattr(explanation_route, "_poll", lambda cid, v: None)
        assert view(design).status == "failed"

    def test_a_task_nothing_has_heard_from_is_queued_again(self, design, outputs, monkeypatch):
        queued = []
        monkeypatch.setattr(explanation_route, "_poll", lambda cid, v: None)
        monkeypatch.setattr(explanation_route, "queue_explanation", queued.append)
        assert view(design, age=10.0).status == "writing" and not queued
        assert view(design, age=explanation_route.STALE_AFTER_S + 1).status == "writing"
        assert len(queued) == 1

    def test_no_worker_is_said_not_hidden(self, design, outputs, monkeypatch):
        monkeypatch.setattr(explanation_route, "_poll", lambda cid, v: None)
        stale = view(design, age=explanation_route.STALE_AFTER_S + 1)     # conftest: no queue
        assert stale.status == "unavailable" and "unavailable" in stale.error

    def test_one_explanation_per_version(self):
        assert explanation_route._task_id("c", 1) != explanation_route._task_id("c", 2)


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
