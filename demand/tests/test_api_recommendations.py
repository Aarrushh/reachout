"""Functional tests for GET /demand/api/recommendations, fixture branch.

`/demand/api/analytics` has had a `DEMAND_ANALYTICS_SOURCE=fixture|live`
branch since the fixture-first rollout (`test_api_analytics.py`);
`/demand/api/recommendations` did not, so the new `RecommendationsPanel`
errored in every environment with no database configured. This file guards
the fixture branch added to close that gap, in the same style as
`test_api_analytics.py`: the committed fixture is validated as a contract in
its own right, then exercised through the endpoint.

`store_id` stays required and uuid-validated in every mode (see
`test_recommendations_requires_store_id` /
`test_recommendations_rejects_malformed_store_id` in `test_api.py`, which
already cover that path before any source branch is reached). This file adds
only the fixture-mode-specific case: a malformed `store_id` must still be
rejected when `DEMAND_ANALYTICS_SOURCE` is unset (the default).

Live-mode coverage for `/demand/api/recommendations` (happy path, unknown
store, limit/cap, out-of-contract row) already lives in `test_api.py` and now
sets `DEMAND_ANALYTICS_SOURCE=live` explicitly, since fixture mode is the new
default.
"""

import json

import jsonschema
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from demand.api import app as api_app
from demand.shared.validation import validate_with_formats
from demand.tests.fake_supa import FakeSupabase

REC_RESPONSE_SCHEMA = api_app.load_schema("recommendations_response.schema.json")

STORE_A = "11111111-1111-1111-1111-111111111111"

ACTIONS = {"stock_up", "feature_in_window", "watch"}
CONFIDENCES = {"low", "medium", "high"}
CANONICAL_CAVEAT = "Basado en interés de búsqueda en Madrid, no en compras reales."


def make_client():
    return FakeSupabase(
        tables={"recommendations": []},
        default_schema="demand",
        schemas={"public": {"products": []}},
    )


@pytest.fixture
def test_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "fake-url")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")

    with patch("demand.api.app.create_client", return_value=make_client()):
        api_app.get_client.cache_clear()
        client = TestClient(api_app.app)
        yield client
        api_app.get_client.cache_clear()


# ---------------------------------------------------------------------------
# The committed fixture is a contract, and it is checked as one
# ---------------------------------------------------------------------------

def load_committed_fixture():
    with open(api_app.REC_FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_committed_fixture_validates_against_its_schema():
    """Catches drift between the committed fixture and the DO-NOT-MODIFY schema.

    Validated through the format-enforcing helper, not bare
    `jsonschema.validate`, so `format` asserts rather than annotates.
    """
    validate_with_formats(load_committed_fixture(), REC_RESPONSE_SCHEMA)


def test_committed_fixture_spans_every_action_and_confidence_level():
    """The property the panel's per-row confidence chips depend on."""
    fixture = load_committed_fixture()
    rows = fixture["recommendations"]

    assert {row["action"] for row in rows} == ACTIONS
    assert {row["confidence"] for row in rows} == CONFIDENCES


def test_committed_fixture_rows_carry_the_canonical_caveat():
    fixture = load_committed_fixture()
    for row in fixture["recommendations"]:
        assert row["caveat"] == CANONICAL_CAVEAT


def test_committed_fixture_has_at_least_a_dozen_rows():
    fixture = load_committed_fixture()
    assert len(fixture["recommendations"]) >= 12


def test_committed_fixture_is_ordered_newest_first():
    """Matches the live path's `.order("created_at", desc=True)`."""
    fixture = load_committed_fixture()
    created_ats = [row["created_at"] for row in fixture["recommendations"]]
    assert created_ats == sorted(created_ats, reverse=True)


# ---------------------------------------------------------------------------
# The endpoint, in fixture mode
# ---------------------------------------------------------------------------

def test_recommendations_default_source_serves_the_committed_fixture(test_client, monkeypatch):
    """Env unset -> fixture mode, 200, body is the committed document verbatim.

    `demand/api/app.py` runs `load_dotenv(reachout/.env)` at import time,
    and that file sets `DEMAND_ANALYTICS_SOURCE=live` for local development,
    so a bare, un-monkeypatched run of this suite inherits "live" from the
    process environment rather than truly leaving the var unset. `delenv`
    forces the actual unset case `os.environ.get(..., "fixture")` falls
    back on -- the same reason every analytics fixture-mode test sets the
    value explicitly instead of relying on omission.
    """
    monkeypatch.delenv("DEMAND_ANALYTICS_SOURCE", raising=False)
    response = test_client.get(f"/demand/api/recommendations?store_id={STORE_A}")
    assert response.status_code == 200
    assert response.json() == load_committed_fixture()


def test_recommendations_fixture_mode_is_explicit_too(test_client, monkeypatch):
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "fixture")
    response = test_client.get(f"/demand/api/recommendations?store_id={STORE_A}")
    assert response.status_code == 200
    assert response.json() == load_committed_fixture()


def test_recommendations_fixture_is_store_agnostic(test_client, monkeypatch):
    """The fixture's own store_id is served verbatim, not rewritten to match
    the caller's, and its rows are not filtered by the caller's store_id --
    exactly like the analytics fixture (`test_live_and_fixture_have_the_same_
    structure` in test_api_analytics.py documents the same rule for that
    endpoint).
    """
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "fixture")
    fixture = load_committed_fixture()
    response = test_client.get(f"/demand/api/recommendations?store_id={STORE_A}")
    data = response.json()

    assert data["store_id"] == fixture["store_id"]
    assert data["store_id"] != STORE_A
    for row in data["recommendations"]:
        assert row["store_id"] == fixture["store_id"]


def test_recommendations_fixture_mode_still_requires_a_uuid_store_id(test_client):
    response = test_client.get("/demand/api/recommendations?store_id=not-a-uuid")
    assert response.status_code == 422
    assert "not-a-uuid" not in response.text


def test_recommendations_fixture_mode_still_requires_store_id_at_all(test_client):
    response = test_client.get("/demand/api/recommendations")
    assert response.status_code == 422


def test_recommendations_fixture_mode_validation_is_on(test_client, monkeypatch, tmp_path):
    """Delete the fixture-path validate call and this goes red.

    A fixture that has drifted out of contract must not be served just
    because it is committed. Mirrors
    `test_fixture_mode_validation_is_on` in test_api_analytics.py.
    """
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "fixture")
    broken = tmp_path / "broken.json"
    payload = load_committed_fixture()
    del payload["recommendations"][0]["caveat"]
    broken.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(api_app, "REC_FIXTURE_PATH", broken)

    response = test_client.get(f"/demand/api/recommendations?store_id={STORE_A}")
    assert response.status_code == 500
    assert (
        response.json()["detail"] == "Response failed the recommendations_response contract"
    )


# ---------------------------------------------------------------------------
# DEMAND_ANALYTICS_SOURCE=live still takes the Supabase path
# ---------------------------------------------------------------------------

def test_recommendations_live_source_takes_the_supabase_path(test_client, monkeypatch):
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "live")
    live_store = "22222222-2222-2222-2222-222222222222"
    row = {
        "id": "33333333-3333-3333-3333-333333333333",
        "store_id": live_store,
        "signal_id": "44444444-4444-4444-4444-444444444444",
        "headline": "Sube el interés por grocery en Madrid",
        "body": "Tienes 3 productos de esta categoría en stock.",
        "action": "stock_up",
        "confidence": "high",
        "caveat": CANONICAL_CAVEAT,
        "created_at": "2024-01-08T12:00:00Z",
    }
    live_client = FakeSupabase(
        tables={"recommendations": [row]},
        default_schema="demand",
        schemas={"public": {"products": []}},
    )
    with patch("demand.api.app.create_client", return_value=live_client):
        api_app.get_client.cache_clear()
        response = test_client.get(f"/demand/api/recommendations?store_id={live_store}")

    assert response.status_code == 200
    data = response.json()
    # The fixture's minted store_id never appears on the live path: this is
    # a real Supabase row, not the canned document.
    assert data["store_id"] == live_store
    assert data != load_committed_fixture()
    assert data["recommendations"] == [row]
