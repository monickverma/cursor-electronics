"""/health/worker — says whether a Celery worker is alive to take a simulation."""
import pytest
from fastapi.testclient import TestClient

import main
import worker


@pytest.fixture
def client():
    return TestClient(main.app)


def test_a_worker_that_answers_is_up(client, monkeypatch):
    monkeypatch.setattr(worker.app.control, "ping", lambda timeout=1.0: [{"celery@a": {"ok": "pong"}}])
    assert client.get("/health/worker").json() == {"worker": "up", "workers": 1}


def test_no_answer_is_none_not_up(client, monkeypatch):
    monkeypatch.setattr(worker.app.control, "ping", lambda timeout=1.0: [])
    assert client.get("/health/worker").json() == {"worker": "none", "workers": 0}


def test_a_broker_that_is_down_is_an_answer_not_a_crash(client, monkeypatch):
    def boom(timeout=1.0):
        raise ConnectionError("broker down")
    monkeypatch.setattr(worker.app.control, "ping", boom)
    assert client.get("/health/worker").json() == {"worker": "unreachable", "workers": 0}
