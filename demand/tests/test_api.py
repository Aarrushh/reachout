"""Contract tests for the four original demand API endpoints.

What these tests are FOR, beyond "does it return 200":

- A Supabase failure — including the likeliest one, a missing
  `SUPABASE_URL`/`SUPABASE_KEY` — must be a clean 502 on EVERY route that
  touches the database, with nothing of the driver's message in the body.
- Every list read must be bounded and ordered.
- No select in `demand/api/app.py` may be `"*"`, ever
  (`test_selects_are_explicit_and_never_star`). `demand.trend_snapshots`
  carries a DB-only `captured_date` column that
  `trend_snapshot.schema.json` forbids, so a widened select is a
  production-only failure unless a test catches it. The trend fixture below
  carries that column on purpose.
- A caller-supplied `store_id` is never reflected into a response.

Schema modelling: production builds its client with
`ClientOptions(schema="demand")`, so `client.table(...)` reads the `demand`
schema and `public.products` is only reachable through
`client.schema("public")`. The fake is configured the same way — one flat
dict of tables would pass while hiding a wrong-schema bug.
"""

import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from demand.api import app as api_app
from demand.tests.fake_supa import FakeSupabase

STORE_A = "11111111-1111-1111-1111-111111111111"
STORE_B = "22222222-2222-2222-2222-222222222222"
SNAPSHOT_ID = "33333333-3333-3333-3333-333333333333"

CAVEAT = "Basado en interés de búsqueda en Madrid, no en compras reales."


def _trend_row(keyword, captured_at, captured_date, timeframe="today 3-m"):
    return {
        "id": str(uuid.uuid4()),
        "keyword": keyword,
        "geo": "ES-MD",
        "timeframe": timeframe,
        "provider": "trendspy",
        "captured_at": captured_at,
        "series": [{"date": captured_date, "value": 50}],
        "region_breakdown": None,
        # DB-only column: present in demand.trend_snapshots, deliberately
        # absent from trend_snapshot.schema.json (additionalProperties:
        # false). See the HARD RULE in docs/JULES_DEMAND.md. Here so that a
        # select("*") regression fails this suite instead of only failing in
        # production.
        "captured_date": captured_date,
    }


def _signal_row(keyword, rank, direction="rising", confidence="high", window_start="2024-01-01",
                 timeframe="today 3-m"):
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{keyword}-{window_start}")),
        "keyword": keyword,
        "category": "grocery",
        "geo": "ES-MD",
        "timeframe": timeframe,
        "window_start": window_start,
        "window_end": "2024-01-07",
        "interest_avg": 50,
        "delta_pct": 10.0,
        "direction": direction,
        "rank": rank,
        "confidence": confidence,
        "snapshot_ids": [SNAPSHOT_ID],
        "computed_at": "2024-01-08T12:00:00Z",
    }


def _recommendation_row(store_id, headline, created_at):
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{store_id}-{headline}")),
        "store_id": store_id,
        "signal_id": SNAPSHOT_ID,
        "headline": headline,
        "body": "Interest is high.",
        "action": "stock_up",
        "confidence": "high",
        "caveat": CAVEAT,
        "created_at": created_at,
    }


def demand_tables():
    return {
        "trend_snapshots": [
            _trend_row("cerveza", "2024-01-01T12:00:00Z", "2024-01-01"),
            _trend_row("hielo", "2024-01-03T12:00:00Z", "2024-01-03"),
            _trend_row("helados", "2024-01-02T12:00:00Z", "2024-01-02"),
        ],
        "demand_signals": [
            _signal_row("hielo", rank=2, direction="falling"),
            _signal_row("cerveza", rank=1, direction="rising"),
            _signal_row("helados", rank=3, direction="rising", window_start="2024-02-01"),
        ],
        "recommendations": [
            _recommendation_row(STORE_A, "Stock up on cerveza", "2024-01-08T12:00:00Z"),
            _recommendation_row(STORE_A, "Stock up on hielo", "2024-01-09T12:00:00Z"),
            _recommendation_row(STORE_B, "Stock up on helados", "2024-01-10T12:00:00Z"),
        ],
    }


def public_tables():
    return {
        "products": [
            {
                "id": str(uuid.uuid4()),
                "category": "grocery",
                "stock_qty": 5,
                "store_id": STORE_A,
            }
        ]
    }


def get_fake_supa_client():
    """Mirrors production's schema split: demand default, public alongside."""
    return FakeSupabase(
        tables=demand_tables(),
        default_schema="demand",
        schemas={"public": public_tables()},
    )


@pytest.fixture
def test_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "fake-url")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")

    with patch("demand.api.app.create_client", return_value=get_fake_supa_client()):
        # Clear the lru_cache so it picks up the mocked function
        api_app.get_client.cache_clear()

        client = TestClient(api_app.app)
        yield client

        api_app.get_client.cache_clear()


# ---------------------------------------------------------------------------
# Happy paths, now with ordering and bounds
# ---------------------------------------------------------------------------

def test_health(test_client):
    response = test_client.get("/demand/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_trends_is_ordered_newest_first(test_client):
    response = test_client.get("/demand/api/trends")
    assert response.status_code == 200
    data = response.json()
    assert [row["keyword"] for row in data] == ["hielo", "helados", "cerveza"]
    # captured_date is a DB-only column; it must never reach a response body.
    assert all("captured_date" not in row for row in data)


def test_trends_limit_is_honoured_and_capped(test_client):
    assert len(test_client.get("/demand/api/trends?limit=2").json()) == 2
    # The cap is a refusal, not a silent clamp.
    over = test_client.get(f"/demand/api/trends?limit={api_app.MAX_PAGE_SIZE + 1}")
    assert over.status_code == 422
    assert test_client.get("/demand/api/trends?limit=0").status_code == 422


def test_get_signals_is_ordered_by_rank(test_client):
    response = test_client.get("/demand/api/signals")
    assert response.status_code == 200
    data = response.json()
    assert [row["keyword"] for row in data] == ["cerveza", "hielo", "helados"]


def test_get_signals_filters(test_client):
    response = test_client.get("/demand/api/signals?window=2024-01-01")
    assert response.status_code == 200
    assert len(response.json()) == 2

    response = test_client.get("/demand/api/signals?window=2024-03-01")
    assert response.status_code == 200
    assert response.json() == []

    response = test_client.get("/demand/api/signals?direction=rising")
    assert response.status_code == 200
    assert {row["keyword"] for row in response.json()} == {"cerveza", "helados"}


def test_signals_limit_is_honoured_and_capped(test_client):
    assert len(test_client.get("/demand/api/signals?limit=1").json()) == 1
    over = test_client.get(f"/demand/api/signals?limit={api_app.MAX_PAGE_SIZE + 1}")
    assert over.status_code == 422


# ---------------------------------------------------------------------------
# timeframe: the two demand_signals/trend_snapshots scales stay separate
# ---------------------------------------------------------------------------

def test_get_trends_filters_by_timeframe(test_client):
    """A 12-m trend is invisible on the (default) 3-m read, and vice versa."""
    tables = demand_tables()
    tables["trend_snapshots"].append(
        _trend_row("otro", "2024-01-05T12:00:00Z", "2024-01-05", timeframe="today 12-m")
    )
    with _client_with(tables):
        api_app.get_client.cache_clear()
        default_keywords = {
            row["keyword"] for row in test_client.get("/demand/api/trends").json()
        }
        assert "otro" not in default_keywords

        twelve_m = test_client.get(
            "/demand/api/trends", params={"timeframe": "today 12-m"}
        )
        assert [row["keyword"] for row in twelve_m.json()] == ["otro"]


def test_get_signals_filters_by_timeframe(test_client):
    tables = demand_tables()
    tables["demand_signals"].append(
        _signal_row("otro", rank=1, window_start="2024-03-01", timeframe="today 12-m")
    )
    with _client_with(tables):
        api_app.get_client.cache_clear()
        default_keywords = {
            row["keyword"] for row in test_client.get("/demand/api/signals").json()
        }
        assert "otro" not in default_keywords

        twelve_m = test_client.get(
            "/demand/api/signals", params={"timeframe": "today 12-m"}
        )
        assert [row["keyword"] for row in twelve_m.json()] == ["otro"]


@pytest.mark.parametrize(
    "route",
    ["/demand/api/trends", "/demand/api/signals", "/demand/api/analytics"],
)
def test_unrecognised_timeframe_is_422_on_every_endpoint(test_client, route):
    response = test_client.get(route, params={"timeframe": "today 6-m"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /signals: keyword filter and opt-in chronological order (Requirement 3)
# ---------------------------------------------------------------------------

def test_get_signals_keyword_filter(test_client):
    response = test_client.get("/demand/api/signals", params={"keyword": "cerveza"})
    assert response.status_code == 200
    data = response.json()
    assert data and {row["keyword"] for row in data} == {"cerveza"}


def test_get_signals_order_defaults_to_rank(test_client):
    """Unchanged default: no `order` param behaves exactly as before."""
    response = test_client.get("/demand/api/signals")
    assert [row["keyword"] for row in response.json()] == ["cerveza", "hielo", "helados"]


def test_get_signals_order_by_window_start_is_chronological(test_client):
    response = test_client.get("/demand/api/signals", params={"order": "window_start"})
    assert response.status_code == 200
    starts = [row["window_start"] for row in response.json()]
    assert starts == sorted(starts)


def test_get_signals_invalid_order_is_422(test_client):
    response = test_client.get("/demand/api/signals", params={"order": "bogus"})
    assert response.status_code == 422


def test_get_recommendations_for_a_store(test_client):
    response = test_client.get(f"/demand/api/recommendations?store_id={STORE_A}")
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == STORE_A
    assert len(data["recommendations"]) == 2
    # Newest first.
    assert data["recommendations"][0]["headline"] == "Stock up on hielo"


def test_get_recommendations_unknown_store_is_empty_not_invented(test_client):
    unknown = "44444444-4444-4444-4444-444444444444"
    response = test_client.get(f"/demand/api/recommendations?store_id={unknown}")
    assert response.status_code == 200
    assert response.json() == {"store_id": unknown, "recommendations": []}


def test_recommendations_limit_is_honoured_and_capped(test_client):
    response = test_client.get(f"/demand/api/recommendations?store_id={STORE_A}&limit=1")
    assert len(response.json()["recommendations"]) == 1
    over = test_client.get(
        f"/demand/api/recommendations?store_id={STORE_A}&limit={api_app.MAX_PAGE_SIZE + 1}"
    )
    assert over.status_code == 422


# ---------------------------------------------------------------------------
# store_id: required, validated, never reflected
# ---------------------------------------------------------------------------

def test_recommendations_requires_store_id(test_client):
    """No fabricated all-zero store id. Absent store_id is a 4xx.

    recommendations_response.schema.json requires store_id and is a
    DO-NOT-MODIFY contract, so the endpoint requires it too.
    """
    response = test_client.get("/demand/api/recommendations")
    assert response.status_code == 422
    assert "00000000-0000-0000-0000-000000000000" not in response.text


@pytest.mark.parametrize(
    "raw_store_id",
    ["%3Cscript%3E", "123", "not-a-uuid", "1111111-1111-1111-1111-111111111111"],
)
def test_recommendations_rejects_malformed_store_id(test_client, raw_store_id):
    response = test_client.get(f"/demand/api/recommendations?store_id={raw_store_id}")
    assert response.status_code == 422
    # Not a 500, and the value is not echoed back into the body.
    assert "<script>" not in response.text
    assert "not-a-uuid" not in response.text


def test_analytics_rejects_malformed_store_id(test_client):
    response = test_client.get("/demand/api/analytics?store_id=%3Cscript%3E")
    assert response.status_code == 422
    assert "<script>" not in response.text


# ---------------------------------------------------------------------------
# The 502 contract, on every Supabase-backed route
# ---------------------------------------------------------------------------

SUPABASE_BACKED_ROUTES = [
    "/demand/api/trends",
    "/demand/api/signals",
    f"/demand/api/recommendations?store_id={STORE_A}",
    "/demand/api/analytics",
]


class ExceptionQueryBuilder:
    """A builder that supports the whole chain and dies at execute().

    It needs eq/order/limit as well as select: without them it cannot serve
    the filtered routes, and a 502 test that only reaches /trends is a 502
    test for one route out of four.
    """

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def range(self, *args, **kwargs):
        return self

    def execute(self):
        raise Exception("password=hunter2 host=db.internal")


class ExceptionFakeSupabase:
    def schema(self, name):
        return self

    def table(self, name):
        return ExceptionQueryBuilder()


@pytest.mark.parametrize("route", SUPABASE_BACKED_ROUTES)
def test_query_failure_is_502_on_every_route(test_client, monkeypatch, route):
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "live")
    with patch("demand.api.app.create_client", return_value=ExceptionFakeSupabase()):
        api_app.get_client.cache_clear()
        response = test_client.get(route)
        assert response.status_code == 502, route
        assert response.json()["detail"] == api_app.DB_FAILURE_DETAIL


@pytest.mark.parametrize("route", SUPABASE_BACKED_ROUTES)
def test_missing_credentials_is_502_not_a_raw_500(monkeypatch, route):
    """The likeliest production failure: a misconfigured environment.

    `get_client()` used to be called outside the guarded path, so this
    raised straight out of the handler as a 500 with a stack trace on every
    route.
    """
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "live")
    api_app.get_client.cache_clear()
    try:
        client = TestClient(api_app.app)
        response = client.get(route)
        assert response.status_code == 502, route
        assert response.json()["detail"] == api_app.DB_FAILURE_DETAIL
    finally:
        api_app.get_client.cache_clear()


def test_502_body_does_not_leak_the_driver_message(test_client, monkeypatch):
    """No auth here by design, so "any caller" means the public."""
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "live")
    with patch("demand.api.app.create_client", return_value=ExceptionFakeSupabase()):
        api_app.get_client.cache_clear()
        for route in SUPABASE_BACKED_ROUTES:
            response = test_client.get(route)
            assert "hunter2" not in response.text, route
            assert "db.internal" not in response.text, route


# ---------------------------------------------------------------------------
# A row that violates its contract is a described error, not a stack trace
# ---------------------------------------------------------------------------

def _client_with(tables):
    fake = FakeSupabase(
        tables=tables,
        default_schema="demand",
        schemas={"public": public_tables()},
    )
    return patch("demand.api.app.create_client", return_value=fake)


def test_out_of_contract_signal_row_is_a_described_500(test_client):
    """demand/data/schema.sql has no CHECK on `direction`, so this is reachable."""
    tables = demand_tables()
    tables["demand_signals"][0]["direction"] = "unknown"
    with _client_with(tables):
        api_app.get_client.cache_clear()
        response = test_client.get("/demand/api/signals")
        assert response.status_code == 500
        assert response.json()["detail"] == "Response failed the demand_signal contract"
        assert "Traceback" not in response.text


def test_out_of_contract_trend_row_is_a_described_500(test_client):
    tables = demand_tables()
    # Negative, not 500: a rescaled batch legitimately exceeds 100, so a large
    # value is no longer out of contract. Below zero still is -- interest has
    # no negative direction.
    tables["trend_snapshots"][0]["series"] = [{"date": "2024-01-01", "value": -5}]
    with _client_with(tables):
        api_app.get_client.cache_clear()
        response = test_client.get("/demand/api/trends")
        assert response.status_code == 500
        assert response.json()["detail"] == "Response failed the trend_snapshot contract"


def test_out_of_contract_recommendation_row_is_a_described_500(test_client):
    tables = demand_tables()
    tables["recommendations"][0]["confidence"] = "very high"
    with _client_with(tables):
        api_app.get_client.cache_clear()
        response = test_client.get(f"/demand/api/recommendations?store_id={STORE_A}")
        assert response.status_code == 500
        assert (
            response.json()["detail"]
            == "Response failed the recommendations_response contract"
        )


def test_validation_actually_enforces_format(test_client):
    """A non-uuid id in the DB is caught, which needs the FormatChecker.

    With bare `jsonschema.validate` this row sails through: on draft-07
    `format` is an annotation unless a checker is attached. If this test
    goes green after someone drops back to `jsonschema.validate`, the
    contract is decoration.
    """
    tables = demand_tables()
    tables["demand_signals"][0]["id"] = "not-a-uuid"
    with _client_with(tables):
        api_app.get_client.cache_clear()
        response = test_client.get("/demand/api/signals")
        assert response.status_code == 500
        assert response.json()["detail"] == "Response failed the demand_signal contract"


# ---------------------------------------------------------------------------
# No auth, by design (D2)
# ---------------------------------------------------------------------------

def test_no_auth_endpoints_401_or_403(test_client):
    endpoints = [
        "/demand/api/health",
        "/demand/api/trends",
        "/demand/api/signals",
        "/demand/api/analytics",
        "/demand/api/signals?window=2024-01-01",
        f"/demand/api/recommendations?store_id={STORE_A}",
    ]
    for endpoint in endpoints:
        response = test_client.get(endpoint)
        assert response.status_code not in [401, 403], (
            f"Endpoint {endpoint} returned {response.status_code}"
        )


# ---------------------------------------------------------------------------
# The HARD RULE: no select("*") anywhere in app.py
# ---------------------------------------------------------------------------

class _RecordingQuery:
    """Proxies a FakeQueryBuilder and records what columns were asked for."""

    def __init__(self, inner, recorder, label):
        self._inner = inner
        self._recorder = recorder
        self._label = label

    def select(self, cols="*", **kwargs):
        self._recorder.append((self._label, cols))
        self._inner = self._inner.select(cols, **kwargs)
        return self

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def _wrapped(*args, **kwargs):
            result = attr(*args, **kwargs)
            return self if result is self._inner else result

        return _wrapped


class _RecordingSchemaView:
    def __init__(self, inner, recorder, schema_name):
        self._inner = inner
        self._recorder = recorder
        self._schema_name = schema_name

    def table(self, name):
        return _RecordingQuery(
            self._inner.table(name), self._recorder, f"{self._schema_name}.{name}"
        )


class RecordingSupabase:
    def __init__(self, inner):
        self._inner = inner
        self.selects = []

    def schema(self, name):
        return _RecordingSchemaView(self._inner.schema(name), self.selects, name)

    def table(self, name):
        return _RecordingQuery(
            self._inner.table(name), self.selects, f"{self._inner.default_schema}.{name}"
        )


def test_selects_are_explicit_and_never_star(monkeypatch):
    """Every read in app.py names its columns.

    `demand.trend_snapshots.captured_date` is a DB-only column that
    `trend_snapshot.schema.json` forbids, so `select("*")` on it is a
    production-only 500. A reviewer once rewrote all three selects to `"*"`
    and the suite stayed green; this test is what makes that go red now, for
    every route including analytics.
    """
    monkeypatch.setenv("SUPABASE_URL", "fake-url")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "live")

    recorder = RecordingSupabase(get_fake_supa_client())
    with patch("demand.api.app.create_client", return_value=recorder):
        api_app.get_client.cache_clear()
        client = TestClient(api_app.app)
        for route in SUPABASE_BACKED_ROUTES:
            assert client.get(route).status_code == 200, route
        api_app.get_client.cache_clear()

    labels = {label for label, _ in recorder.selects}
    assert labels == {
        "demand.trend_snapshots",
        "demand.demand_signals",
        "demand.recommendations",
        "public.products",
    }

    for label, cols in recorder.selects:
        assert cols.strip() != "*", f"{label} was read with select('*')"
        assert "*" not in cols, f"{label} was read with a wildcard select: {cols!r}"
        assert "captured_date" not in cols, (
            f"{label} asked for the DB-only captured_date column"
        )
