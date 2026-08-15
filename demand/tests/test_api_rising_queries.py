"""Functional tests for GET /demand/api/rising-queries.

`demand.rising_queries` was a write-only table until this endpoint: no
route, no script, no frontend code read it back. `relevance_score` /
`relevance_tier` / `relevance_reasons` / `cluster_id` are not columns --
`demand/api/relevance.py:annotate()` computes them at read time -- so this
file exercises the endpoint's whole pipeline (bounded+ordered DB read ->
annotate the full set -> filter by tier -> apply `limit`), not just
`relevance.py` in isolation (see `test_relevance.py` for the scorer's own
unit tests).

Schema modelling: production builds its client with
`ClientOptions(schema="demand")`, so `rising_queries` lives in the `demand`
schema, same as `test_api.py` / `test_api_analytics.py`.
"""

import uuid

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from demand.api import app as api_app
from demand.shared.validation import validate_with_formats
from demand.tests.fake_supa import FakeSupabase

RISING_QUERY_SCHEMA = api_app.load_schema("rising_query.schema.json")


def _rq(n, parent_keyword, query, geo="ES-MD", gprop="", growth_pct=10.0,
        is_breakout=False, captured_at="2026-06-01T08:00:00Z",
        captured_date="2026-06-01"):
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"rising-{n}")),
        "parent_keyword": parent_keyword,
        "query": query,
        "growth_pct": growth_pct,
        "is_breakout": is_breakout,
        "geo": geo,
        "gprop": gprop,
        "captured_at": captured_at,
        "captured_date": captured_date,
    }


# Real eclipse cluster (see test_relevance.py): three variants that score
# "commercial" without any of them containing the parent keyword
# "gafas de sol" as a substring, and that annotate() merges onto one
# cluster_id (`gafas:eclipse_gafas`) via `_merge_subset_keys`.
ROW_ECLIPSE_CARREFOUR = _rq(
    1, "gafas de sol", "gafas eclipse carrefour", gprop="froogle",
    growth_pct=120.5,
)
ROW_ECLIPSE_NO_CONTAINMENT = _rq(
    2, "gafas de sol", "gafas para el eclipse", growth_pct=80.0,
)
ROW_ECLIPSE_SOLAR = _rq(
    3, "gafas de sol", "comprar gafas eclipse solar", growth_pct=45.0,
)
# Google Maps navigational category -- tiers "noise" (test_relevance.py's
# test_maps_navigational_categories_tier_as_noise).
ROW_NOISE_BANCOS = _rq(4, "café", "bancos", growth_pct=200.0)
# "Breakout": Google refused to quantify growth, so growth_pct is NULL in
# the fixture itself, not merely absent -- the honesty invariant this
# endpoint must preserve end to end.
ROW_BREAKOUT = _rq(
    5, "bombillas", "bombillas led g9", growth_pct=None, is_breakout=True,
)
# Same parent ("café") as the noise row, but a different, commercial query
# -- exercises parent_keyword filtering independent of tier filtering.
ROW_CAFE_COMMERCIAL = _rq(6, "café", "cafeteras nespresso", growth_pct=15.0)

ALL_ROWS = [
    ROW_ECLIPSE_CARREFOUR,
    ROW_ECLIPSE_NO_CONTAINMENT,
    ROW_ECLIPSE_SOLAR,
    ROW_NOISE_BANCOS,
    ROW_BREAKOUT,
    ROW_CAFE_COMMERCIAL,
]


def get_fake_supa_client(rows=None):
    return FakeSupabase(
        tables={"rising_queries": ALL_ROWS if rows is None else rows},
        default_schema="demand",
    )


@pytest.fixture
def test_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "fake-url")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")

    with patch("demand.api.app.create_client", return_value=get_fake_supa_client()):
        api_app.get_client.cache_clear()
        client = TestClient(api_app.app)
        yield client
        api_app.get_client.cache_clear()


# ---------------------------------------------------------------------------
# 1 & 2. include=commercial (default) vs include=all
# ---------------------------------------------------------------------------

def test_default_include_excludes_noise(test_client):
    response = test_client.get("/demand/api/rising-queries")
    assert response.status_code == 200
    data = response.json()
    queries = {row["query"] for row in data}
    assert "bancos" not in queries
    assert all(row["relevance_tier"] == "commercial" for row in data)


def test_include_all_returns_every_row_including_noise(test_client):
    response = test_client.get("/demand/api/rising-queries?include=all")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(ALL_ROWS)
    assert "bancos" in {row["query"] for row in data}


# ---------------------------------------------------------------------------
# 3. include=bogus is a 422, same style as the other guards in this file
# ---------------------------------------------------------------------------

def test_include_bogus_is_422(test_client):
    response = test_client.get("/demand/api/rising-queries?include=bogus")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 4. parent_keyword filtering
# ---------------------------------------------------------------------------

def test_parent_keyword_filters(test_client):
    response = test_client.get(
        "/demand/api/rising-queries", params={"parent_keyword": "gafas de sol", "include": "all"}
    )
    assert response.status_code == 200
    data = response.json()
    assert {row["parent_keyword"] for row in data} == {"gafas de sol"}
    assert len(data) == 3

    # Same parent as the noise row, but the default include still filters
    # by tier independently of the parent_keyword filter.
    cafe_default = test_client.get(
        "/demand/api/rising-queries", params={"parent_keyword": "café"}
    ).json()
    assert [row["query"] for row in cafe_default] == ["cafeteras nespresso"]


# ---------------------------------------------------------------------------
# 5. Every response item validates against rising_query.schema.json
# ---------------------------------------------------------------------------

def test_every_row_validates_against_schema(test_client):
    response = test_client.get("/demand/api/rising-queries?include=all")
    assert response.status_code == 200
    for row in response.json():
        validate_with_formats(row, RISING_QUERY_SCHEMA)


# ---------------------------------------------------------------------------
# 6. The honesty invariant: is_breakout=true <=> growth_pct stays null
# ---------------------------------------------------------------------------

def test_breakout_growth_pct_stays_null(test_client):
    response = test_client.get("/demand/api/rising-queries?include=all")
    assert response.status_code == 200
    data = response.json()

    breakout_row = next(row for row in data if row["query"] == "bombillas led g9")
    assert breakout_row["is_breakout"] is True
    assert breakout_row["growth_pct"] is None

    # No row is ever breakout with a fabricated non-null growth_pct.
    for row in data:
        if row["is_breakout"]:
            assert row["growth_pct"] is None, row


# ---------------------------------------------------------------------------
# 7. Over-limit `limit` is a 422, matching the other routes
# ---------------------------------------------------------------------------

def test_limit_is_capped(test_client):
    over = test_client.get(
        f"/demand/api/rising-queries?limit={api_app.MAX_PAGE_SIZE + 1}"
    )
    assert over.status_code == 422
    assert test_client.get("/demand/api/rising-queries?limit=0").status_code == 422


def test_limit_is_honoured(test_client):
    response = test_client.get("/demand/api/rising-queries?include=all&limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# 8. The eclipse regression guard, at the endpoint level
# ---------------------------------------------------------------------------
# "gafas eclipse carrefour" scores commercial without containing "gafas de
# sol" as a substring. A naive containment filter anywhere in this pipeline
# would silently drop it from the default response.

def test_eclipse_carrefour_present_in_default_response(test_client):
    response = test_client.get("/demand/api/rising-queries")
    assert response.status_code == 200
    queries = {row["query"] for row in response.json()}
    assert "gafas eclipse carrefour" in queries


# ---------------------------------------------------------------------------
# Addendum: annotate() is batch-scoped -- rows sharing a cluster must share
# one cluster_id in the response, and that must survive tiering + limit.
# ---------------------------------------------------------------------------

def test_eclipse_cluster_shares_one_cluster_id(test_client):
    response = test_client.get("/demand/api/rising-queries?include=all")
    assert response.status_code == 200
    data = response.json()

    by_query = {row["query"]: row["cluster_id"] for row in data}
    cluster_ids = {
        by_query["gafas eclipse carrefour"],
        by_query["gafas para el eclipse"],
        by_query["comprar gafas eclipse solar"],
    }
    assert len(cluster_ids) == 1, (
        f"expected the three eclipse variants to share one cluster_id, got {cluster_ids!r}"
    )
    # And it must not collide with an unrelated cluster.
    assert by_query["cafeteras nespresso"] not in cluster_ids


def test_cluster_id_is_the_same_whether_or_not_a_noise_row_is_present(test_client):
    """A row's cluster_id must not depend on which OTHER rows the caller's
    tier filter happens to exclude, because annotate() runs over the full DB
    read before tiering (see the endpoint's docstring, step 2 vs step 3).
    This directly regression-guards the Addendum: annotating a
    filtered/paginated slice instead of the whole batch would make
    cluster_id depend on what else was on the page.
    """
    all_rows = test_client.get("/demand/api/rising-queries?include=all").json()
    commercial_only = test_client.get("/demand/api/rising-queries").json()

    all_by_query = {row["query"]: row["cluster_id"] for row in all_rows}
    commercial_by_query = {row["query"]: row["cluster_id"] for row in commercial_only}

    for query, cluster_id in commercial_by_query.items():
        assert all_by_query[query] == cluster_id


# ---------------------------------------------------------------------------
# Ordering is deterministic and does not depend on fixture insertion order
# ---------------------------------------------------------------------------

def test_response_order_is_independent_of_fixture_insertion_order(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "fake-url")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")

    forward = get_fake_supa_client(list(ALL_ROWS))
    shuffled = get_fake_supa_client(list(reversed(ALL_ROWS)))

    with patch("demand.api.app.create_client", return_value=forward):
        api_app.get_client.cache_clear()
        client = TestClient(api_app.app)
        forward_order = [row["id"] for row in client.get("/demand/api/rising-queries?include=all").json()]
        api_app.get_client.cache_clear()

    with patch("demand.api.app.create_client", return_value=shuffled):
        api_app.get_client.cache_clear()
        client = TestClient(api_app.app)
        shuffled_order = [row["id"] for row in client.get("/demand/api/rising-queries?include=all").json()]
        api_app.get_client.cache_clear()

    assert forward_order == shuffled_order
    assert forward_order == sorted(forward_order)


# ---------------------------------------------------------------------------
# gprop "" is a real value (Web-derived discovery), never dropped or nulled
# ---------------------------------------------------------------------------

def test_empty_gprop_round_trips_as_empty_string_not_absent(test_client):
    response = test_client.get(
        "/demand/api/rising-queries", params={"parent_keyword": "bombillas", "include": "all"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["gprop"] == ""


# ---------------------------------------------------------------------------
# No select("*") on this table either
# ---------------------------------------------------------------------------

def test_rising_queries_select_is_explicit(test_client):
    from demand.tests.test_api import RecordingSupabase

    recorder = RecordingSupabase(get_fake_supa_client())
    with patch("demand.api.app.create_client", return_value=recorder):
        api_app.get_client.cache_clear()
        client = TestClient(api_app.app)
        assert client.get("/demand/api/rising-queries?include=all").status_code == 200
        api_app.get_client.cache_clear()

    rising_selects = [cols for label, cols in recorder.selects if label == "demand.rising_queries"]
    assert rising_selects, "no select recorded against demand.rising_queries"
    for cols in rising_selects:
        assert cols.strip() != "*"
        assert "*" not in cols


# ---------------------------------------------------------------------------
# A driver failure is the canonical 502, same as every other route
# ---------------------------------------------------------------------------

def test_query_failure_is_502(test_client, monkeypatch):
    from demand.tests.test_api import ExceptionFakeSupabase

    with patch("demand.api.app.create_client", return_value=ExceptionFakeSupabase()):
        api_app.get_client.cache_clear()
        response = test_client.get("/demand/api/rising-queries")
        assert response.status_code == 502
        assert response.json()["detail"] == api_app.DB_FAILURE_DETAIL
