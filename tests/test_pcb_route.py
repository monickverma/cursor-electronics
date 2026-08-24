"""POST /pcb/compile — the experimental-engine gate.

The PCB engine is experimental: on in development, off in production, with
`PCB_ENGINE_ENABLED` overriding either way. These tests pin the gate itself, not
the layout engine — `test_pcb_placement.py` covers that. What matters here is
that the flag is actually consulted, that it is consulted in the right order
relative to auth and body validation, and that a disabled build says so instead
of failing in a way that reads as the caller's fault.

The enabled cases deliberately post an empty netlist so the request stops at the
422 immediately after the gate. Posting a real netlist would run A* routing for
several seconds to prove a point about a flag.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.routes.auth import get_current_user
from core.config import Settings, settings
from db.models import get_db
from main import app


@pytest.fixture
def client():
    """TestClient with auth and DB stubbed out.

    Both are overridden together: get_current_user depends on get_db, so
    leaving the DB live would have these tests open a real connection just to
    reach a route that never touches one.
    """
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001"
    )
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    """No auth override — only the DB is stubbed, so a missing token 401s
    without touching PostgreSQL."""
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


_NETLIST = {"name": "t", "components": [{"ref": "R1", "mpn": "RC0402", "pins": {"1": "A", "2": "B"}}]}


class TestPcbEngineGate:
    def test_disabled_returns_501(self, client, monkeypatch):
        monkeypatch.setattr(settings, "pcb_engine_enabled", False)

        res = client.post("/pcb/compile", json=_NETLIST)

        assert res.status_code == 501
        assert "experimental" in res.json()["detail"].lower()

    def test_disabled_is_not_404(self, client, monkeypatch):
        """404 would read as a wrong URL and send the caller hunting for a
        typo. The endpoint exists; this build just does not offer it."""
        monkeypatch.setattr(settings, "pcb_engine_enabled", False)

        assert client.post("/pcb/compile", json=_NETLIST).status_code != 404

    def test_gate_precedes_body_validation(self, client, monkeypatch):
        """A disabled build must not leak which netlists it would have
        rejected. An empty netlist is a 422 when enabled — off, it is still
        501."""
        monkeypatch.setattr(settings, "pcb_engine_enabled", False)

        res = client.post("/pcb/compile", json={"name": "t", "components": []})

        assert res.status_code == 501

    def test_gate_does_not_bypass_auth(self, anon_client, monkeypatch):
        """The flag is checked inside the handler, so auth still runs first.
        Enabled or not, an unauthenticated caller gets 401 — never a 501 that
        would confirm the endpoint's state to an anonymous prober."""
        monkeypatch.setattr(settings, "pcb_engine_enabled", False)

        assert anon_client.post("/pcb/compile", json=_NETLIST).status_code == 401

    def test_enabled_passes_the_gate(self, client, monkeypatch):
        """Enabled, the request reaches the handler's own validation — proving
        the gate is a flag check and not a hardcoded refusal."""
        monkeypatch.setattr(settings, "pcb_engine_enabled", True)

        res = client.post("/pcb/compile", json={"name": "t", "components": []})

        assert res.status_code == 422
        assert "no components" in res.json()["detail"].lower()

    def test_enabled_still_enforces_component_cap(self, client, monkeypatch):
        monkeypatch.setattr(settings, "pcb_engine_enabled", True)
        oversized = {
            "name": "t",
            "components": [{"ref": f"R{i}", "pins": {"1": "A"}} for i in range(41)],
        }

        res = client.post("/pcb/compile", json=oversized)

        assert res.status_code == 422
        assert "40" in res.json()["detail"]


class TestPcbEngineDefault:
    """The flag defaults to None and is resolved from `environment`.

    Scope decision 2026-08-22 is "experimental and labelled", not "disabled":
    the engine is available in development and off in production. What matters
    is that the *omission* case is safe — a production deploy that never sets
    the variable must not serve an untested surface by accident.
    """

    def _settings(self, **overrides):
        return Settings(
            anthropic_api_key="",
            database_url="postgresql+asyncpg://t:t@localhost/t",
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-minimum-32-characters-long",
            **overrides,
        )

    def test_unset_is_the_sentinel_not_a_literal(self):
        """A bare True/False default would ignore the environment. None is what
        makes the derivation happen at all."""
        assert type(settings).model_fields["pcb_engine_enabled"].default is None

    def test_production_defaults_off(self):
        assert self._settings(environment="production").pcb_engine_enabled is False

    def test_development_defaults_on(self):
        assert self._settings(environment="development").pcb_engine_enabled is True

    def test_explicit_true_overrides_production(self):
        """Opting in must still be possible — otherwise there is no way to
        exercise the engine on a production-like deploy."""
        s = self._settings(environment="production", pcb_engine_enabled=True)
        assert s.pcb_engine_enabled is True

    def test_explicit_false_overrides_development(self):
        s = self._settings(environment="development", pcb_engine_enabled=False)
        assert s.pcb_engine_enabled is False

    def test_resolves_to_a_real_bool(self):
        """Callers do `if not settings.pcb_engine_enabled`. If None ever leaked
        through, that check would silently read as 'disabled' everywhere."""
        assert isinstance(self._settings(environment="development").pcb_engine_enabled, bool)


class TestHealthAdvertisesTheFlag:
    """/health carries the flag so the frontend can hide the PCB tab.

    Without this the tab is decoration: visible, labelled experimental, and
    wired to a route that refuses every click.
    """

    def test_health_reports_flag(self, client, monkeypatch):
        monkeypatch.setattr(settings, "pcb_engine_enabled", True)

        body = client.get("/health").json()

        assert body["pcb_engine_enabled"] is True

    def test_health_tracks_the_flag(self, client, monkeypatch):
        """Read at request time, not captured at import — otherwise the tab
        would reflect whatever the flag was when the module loaded."""
        monkeypatch.setattr(settings, "pcb_engine_enabled", False)

        assert client.get("/health").json()["pcb_engine_enabled"] is False

    def test_health_needs_no_auth(self, anon_client):
        """The tab list is decided before login, so this must answer without a
        token. It reveals nothing /pcb/compile would not."""
        res = anon_client.get("/health")

        assert res.status_code == 200
        assert "pcb_engine_enabled" in res.json()
