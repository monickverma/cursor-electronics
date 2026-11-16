"""
`GET /parts` — the catalogue search behind the parts sheet. A lookup over
data/component_db.json: every word must match, part numbers rank first, and it
never returns more than it was asked for.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.routes.parts as parts_route
from api.routes.auth import get_current_user
from main import app
from middleware.rate_limit import limiter

DB = json.loads((Path(__file__).parent.parent / "backend" / "data" / "component_db.json").read_text(encoding="utf-8"))


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u", email="t@example.com")
    was_enabled = limiter.enabled
    limiter.enabled = False
    yield TestClient(app)
    limiter.enabled = was_enabled
    app.dependency_overrides.clear()


def test_the_catalogue_is_the_database_file():
    assert len(parts_route.catalogue()) == len(DB)


def test_a_part_number_typed_in_part_finds_its_part_first(client):
    target = next(p for p in DB if p["category"] == "sensor")
    body = client.get("/parts", params={"q": target["part_number"][:4]}).json()
    assert body["results"], body
    assert body["results"][0]["part_number"].lower().startswith(target["part_number"][:4].lower())
    assert body["catalogue_size"] == len(DB)


def test_every_word_must_match(client):
    resistor = next(p for p in DB if p["category"] == "resistor")
    both = client.get("/parts", params={"q": f"resistor {resistor['package']}"}).json()["results"]
    assert both and all(r["category"] == "resistor" and r["package"] == resistor["package"] for r in both)
    assert client.get("/parts", params={"q": "resistor no-such-word-xyz"}).json()["results"] == []


def test_category_and_limit_are_respected(client):
    body = client.get("/parts", params={"category": "capacitor", "limit": 3}).json()
    assert len(body["results"]) == 3 and {r["category"] for r in body["results"]} == {"capacitor"}
    assert "capacitor" in body["categories"]
    assert client.get("/parts", params={"limit": 999}).status_code == 422


def test_results_carry_the_dated_price_and_no_more_than_the_listed_fields(client):
    row = client.get("/parts", params={"q": "", "limit": 1}).json()["results"][0]
    assert set(row) == set(parts_route._SHOWN)
    assert ("price_asof" in row) and ("unit_price_usd" in row)


def test_search_needs_a_session():
    assert TestClient(app).get("/parts", params={"q": "led"}).status_code == 401
