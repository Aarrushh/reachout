"""Functional tests for GET /demand/api/analytics.

The endpoint this file guards used to return two numbers it had not
computed: `at_risk_count` was `total // 2` over a query that never selected
`stock_qty`, and every segment's `confidence` was a hardcoded literal —
`"high"` on top of rows that all said `low`. Six of six review mutations
survived the previous version of this file.

So these tests assert on VALUES, derived by the documented rules, from
fixtures deliberately built so that the fabricated formulas cannot
accidentally agree with the real ones (no category here has
`at_risk_count == total_count // 2`).

Schema modelling: production builds its client with
`ClientOptions(schema="demand")`, so `demand_signals` lives in the `demand`
schema and `products` in `public`. The fake is configured that way; a single
flat dict would pass while hiding a wrong-schema read.
"""

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import jsonschema
import pytest
from fastapi.testclient import TestClient

from demand.api import app as api_app
from demand.shared.validation import validate_with_formats
from demand.tests.fake_supa import FakeSupabase

ANALYTICS_SCHEMA = api_app.load_schema("analytics_response.schema.json")

REPO_ROOT = Path(__file__).resolve().parents[2]
SKU_CATALOG_PATH = REPO_ROOT / "reachout" / "data" / "sku_catalog.json"

STORE_A = "11111111-1111-1111-1111-111111111111"
STORE_B = "22222222-2222-2222-2222-222222222222"

#: The plan's binding fixture size (S3): 8 weeks x 100 SKUs.
FIXTURE_SKU_COUNT = 100


def real_category_vocabulary():
    """The only categories `products.category` can hold."""
    with open(SKU_CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    return {key for key in catalog if not key.startswith("_")}


def _signal(keyword, rank, window_end, interest_avg, delta_pct, direction,
            confidence, category=None):
    return {
        "keyword": keyword,
        "category": category,
        "interest_avg": interest_avg,
        "delta_pct": delta_pct,
        "direction": direction,
        "confidence": confidence,
        "rank": rank,
        "window_end": window_end,
    }


def signal_rows():
    """Three weekly windows for `cerveza`, plus two other keywords.

    The duplicate keyword is the point: the live path used to emit one point
    per ROW, so `cerveza` appeared three times while the committed fixture
    showed one point per keyword.
    """
    return [
        _signal("cerveza", 3, "2024-01-14", 70.0, 5.0, "rising", "high", "grocery"),
        _signal("paraguas", 4, "2024-01-07", 40.0, 0.5, "flat", "low"),
        _signal("cerveza", 1, "2024-01-07", 85.5, 15.2, "rising", "high", "grocery"),
        _signal("hielo", 2, "2024-01-07", 60.0, -3.0, "falling", "medium", "grocery"),
        _signal("cerveza", 5, "2024-01-21", 55.0, -1.0, "rising", "high", "grocery"),
    ]


def _product(category, stock_qty, store_id):
    return {
        "id": str(uuid.uuid4()),
        "category": category,
        "stock_qty": stock_qty,
        "store_id": store_id,
    }


def product_rows():
    """16 SKUs across two stores.

    Stock levels are chosen so that NO category satisfies
    `at_risk_count == total_count // 2`; the metric this endpoint used to
    fabricate cannot coincide with the metric it now computes.

    store A: grocery 5 (4 at risk), pharmacy 2 (0), electronics 3 (2)
    store B: hardware 4 (1), grocery 2 (0)
    """
    return (
        [_product("grocery", qty, STORE_A) for qty in (0, 1, 2, 2, 9)]
        + [_product("pharmacy", qty, STORE_A) for qty in (7, 8)]
        + [_product("electronics", qty, STORE_A) for qty in (1, 0, 6)]
        + [_product("hardware", qty, STORE_B) for qty in (2, 3, 4, 5)]
        + [_product("grocery", qty, STORE_B) for qty in (10, 11)]
    )


def make_client(signals=None, products=None):
    return FakeSupabase(
        tables={"demand_signals": signal_rows() if signals is None else signals},
        default_schema="demand",
        schemas={"public": {"products": product_rows() if products is None else products}},
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


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "live")


def _with_client(**kwargs):
    return patch("demand.api.app.create_client", return_value=make_client(**kwargs))


def _segment(data, name):
    return data["segments"][name]


def _points(data, name):
    return _segment(data, name)["points"]


def _by_category(points):
    return {point["category"]: point for point in points}


# ---------------------------------------------------------------------------
# The committed fixture is a contract, and it is checked as one
# ---------------------------------------------------------------------------

def load_committed_fixture():
    with open(api_app.ANALYTICS_FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_committed_fixture_validates_against_its_schema():
    """Catches drift between the committed fixture and the DO-NOT-MODIFY schema.

    Validated through the format-enforcing helper, not bare
    `jsonschema.validate`, so `format` asserts rather than annotates.
    """
    validate_with_formats(load_committed_fixture(), ANALYTICS_SCHEMA)


def test_committed_fixture_uses_the_real_category_vocabulary():
    """`Alcohol` is not a category any product can have."""
    vocabulary = real_category_vocabulary()
    fixture = load_committed_fixture()

    for segment in ("category_mix", "stock_out_risk"):
        for point in _points(fixture, segment):
            assert point["category"] in vocabulary, (
                f"{segment} names category {point['category']!r}, which "
                f"products.category cannot hold. Real vocabulary: "
                f"{sorted(vocabulary)}"
            )

    for point in _points(fixture, "top_movers"):
        assert point["category"] is None or point["category"] in vocabulary


def test_committed_fixture_totals_are_internally_consistent():
    """Percentages sum to 100, counts sum to the plan's 100 SKUs."""
    fixture = load_committed_fixture()
    mix = _points(fixture, "category_mix")

    assert sum(point["product_count"] for point in mix) == FIXTURE_SKU_COUNT
    assert round(sum(point["share_pct"] for point in mix), 2) == 100.0
    for point in mix:
        expected = round(point["product_count"] / FIXTURE_SKU_COUNT * 100, 2)
        assert point["share_pct"] == expected

    mix_by_category = _by_category(mix)
    for point in _points(fixture, "stock_out_risk"):
        assert point["at_risk_count"] <= point["total_count"]
        assert point["total_count"] == mix_by_category[point["category"]]["product_count"]
        expected = round(point["at_risk_count"] / point["total_count"] * 100, 2)
        assert point["risk_pct"] == expected


def test_committed_fixture_has_several_points_per_segment():
    """A one-point-per-segment fixture is not the shape live output has."""
    fixture = load_committed_fixture()
    for segment in ("top_movers", "category_mix", "stock_out_risk"):
        assert len(_points(fixture, segment)) > 1, segment


def test_analytics_fixture_mode_serves_the_committed_file(test_client, monkeypatch):
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "fixture")
    response = test_client.get("/demand/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["generated_from"] == "fixture"
    assert data["inventory_type"] == "convenience_store"
    assert data == load_committed_fixture()


def test_fixture_mode_validation_is_on(test_client, monkeypatch, tmp_path):
    """Delete the fixture-path validate call and this goes red.

    A fixture that has drifted out of contract must not be served just
    because it is committed.
    """
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "fixture")
    broken = tmp_path / "broken.json"
    payload = load_committed_fixture()
    del payload["caveat"]
    broken.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(api_app, "ANALYTICS_FIXTURE_PATH", broken)

    response = test_client.get("/demand/api/analytics")
    assert response.status_code == 500
    assert response.json()["detail"] == "Response failed the analytics_response contract"


# ---------------------------------------------------------------------------
# Live mode: shape
# ---------------------------------------------------------------------------

def test_live_top_movers_is_one_point_per_keyword_ordered_by_rank(test_client, live):
    response = test_client.get("/demand/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["generated_from"] == "live"
    validate_with_formats(data, ANALYTICS_SCHEMA)

    points = _points(data, "top_movers")
    keywords = [point["keyword"] for point in points]
    # Three `cerveza` rows, one `cerveza` point.
    assert keywords == ["cerveza", "hielo", "paraguas"]
    assert len(keywords) == len(set(keywords))
    # The best-ranked row wins the keyword, not the last one read.
    assert points[0]["interest_avg"] == 85.5
    assert points[0]["delta_pct"] == 15.2


def test_live_top_movers_is_bounded(test_client, live, monkeypatch):
    monkeypatch.setattr(api_app, "TOP_MOVERS_MAX_POINTS", 2)
    data = test_client.get("/demand/api/analytics").json()
    assert [point["keyword"] for point in _points(data, "top_movers")] == [
        "cerveza",
        "hielo",
    ]


def test_live_and_fixture_have_the_same_structure(test_client, live, monkeypatch):
    live_data = test_client.get("/demand/api/analytics").json()
    fixture_data = load_committed_fixture()

    assert set(live_data) == set(fixture_data)
    assert set(live_data["segments"]) == set(fixture_data["segments"])

    for segment in ("top_movers", "category_mix", "stock_out_risk"):
        live_points = _points(live_data, segment)
        fixture_points = _points(fixture_data, segment)
        assert live_points and fixture_points, segment
        assert set(_segment(live_data, segment)) == set(_segment(fixture_data, segment))
        for point in live_points:
            assert set(point) == set(fixture_points[0]), segment

    # Cardinality rules, identical in both modes.
    for data in (live_data, fixture_data):
        keywords = [point["keyword"] for point in _points(data, "top_movers")]
        assert len(keywords) == len(set(keywords))

        mix = _by_category(_points(data, "category_mix"))
        assert len(mix) == len(_points(data, "category_mix"))

        for point in _points(data, "stock_out_risk"):
            assert point["category"] in mix
            assert point["total_count"] == mix[point["category"]]["product_count"]


# ---------------------------------------------------------------------------
# Live mode: the numbers, computed from real columns
# ---------------------------------------------------------------------------

def test_live_category_mix_counts_the_products_it_read(test_client, live):
    data = test_client.get("/demand/api/analytics").json()
    mix = _by_category(_points(data, "category_mix"))

    assert set(mix) == {"grocery", "pharmacy", "electronics", "hardware"}
    assert mix["grocery"]["product_count"] == 7
    assert mix["pharmacy"]["product_count"] == 2
    assert mix["electronics"]["product_count"] == 3
    assert mix["hardware"]["product_count"] == 4
    assert mix["grocery"]["share_pct"] == 43.75
    assert round(sum(point["share_pct"] for point in mix.values()), 2) == 100.0


def test_live_stock_out_risk_is_computed_from_stock_qty(test_client, live):
    """The metric that used to be `total // 2`.

    Every expectation here differs from `total_count // 2`, so the old
    formula cannot pass this test by coincidence.
    """
    data = test_client.get("/demand/api/analytics").json()
    risk = _by_category(_points(data, "stock_out_risk"))

    expected = {
        "grocery": (4, 7, 57.14),
        "pharmacy": (0, 2, 0.0),
        "electronics": (2, 3, 66.67),
        "hardware": (1, 4, 25.0),
    }
    assert set(risk) == set(expected)
    for category, (at_risk, total, pct) in expected.items():
        assert risk[category]["at_risk_count"] == at_risk, category
        assert risk[category]["total_count"] == total, category
        assert risk[category]["risk_pct"] == pct, category
        assert at_risk != total // 2, f"{category} would pass under total // 2"


def test_live_stock_out_threshold_is_the_documented_one(test_client, live):
    """A SKU one unit above the threshold is not at risk; one at it is."""
    products = [
        _product("grocery", api_app.STOCK_OUT_QTY_THRESHOLD, STORE_A),
        _product("grocery", api_app.STOCK_OUT_QTY_THRESHOLD + 1, STORE_A),
        _product("grocery", api_app.STOCK_OUT_QTY_THRESHOLD + 5, STORE_A),
    ]
    with _with_client(products=products):
        api_app.get_client.cache_clear()
        data = test_client.get("/demand/api/analytics").json()
    risk = _by_category(_points(data, "stock_out_risk"))
    assert risk["grocery"]["at_risk_count"] == 1
    assert risk["grocery"]["total_count"] == 3


def test_live_stock_out_covers_every_category_not_only_rising_ones(test_client, live):
    """`hardware` has no signal at all and still gets a risk point."""
    data = test_client.get("/demand/api/analytics").json()
    risk = _by_category(_points(data, "stock_out_risk"))
    directions = {point["keyword"] for point in _points(data, "top_movers")}
    assert "hardware" in risk
    assert "hardware" not in directions


# ---------------------------------------------------------------------------
# Confidence: derived from the rows, never asserted
# ---------------------------------------------------------------------------

def test_top_movers_confidence_is_the_weakest_contributing_row(test_client, live):
    """cerveza=high, hielo=medium, paraguas=low -> the segment is low."""
    data = test_client.get("/demand/api/analytics").json()
    assert _segment(data, "top_movers")["confidence"] == "low"


def test_a_segment_built_from_low_rows_cannot_report_high(test_client, live):
    """The exact defect: three `low` rows, response claimed `high`."""
    low_rows = [
        _signal("cerveza", 1, "2024-01-07", 85.5, 15.2, "rising", "low", "grocery"),
        _signal("hielo", 2, "2024-01-07", 60.0, -3.0, "falling", "low", "grocery"),
        _signal("paraguas", 3, "2024-01-07", 40.0, 0.5, "flat", "low"),
    ]
    with _with_client(signals=low_rows):
        api_app.get_client.cache_clear()
        data = test_client.get("/demand/api/analytics").json()
    assert _segment(data, "top_movers")["confidence"] == "low"


def test_top_movers_confidence_rises_only_when_every_row_does(test_client, live):
    high_rows = [
        _signal("cerveza", 1, "2024-01-07", 85.5, 15.2, "rising", "high", "grocery"),
        _signal("hielo", 2, "2024-01-07", 60.0, -3.0, "falling", "high", "grocery"),
    ]
    with _with_client(signals=high_rows):
        api_app.get_client.cache_clear()
        data = test_client.get("/demand/api/analytics").json()
    assert _segment(data, "top_movers")["confidence"] == "high"

    mixed = high_rows + [
        _signal("paraguas", 3, "2024-01-07", 40.0, 0.5, "flat", "medium")
    ]
    with _with_client(signals=mixed):
        api_app.get_client.cache_clear()
        data = test_client.get("/demand/api/analytics").json()
    assert _segment(data, "top_movers")["confidence"] == "medium"


def test_confidence_ignores_rows_that_did_not_reach_the_chart(test_client, live):
    """A dropped duplicate row must not drag the label down or up.

    `cerveza`'s three rows all say `high`; only the rank-1 row becomes a
    point. Truncating the chart to one point must leave the label reading
    only from that row.
    """
    monkey_rows = [
        _signal("cerveza", 1, "2024-01-07", 85.5, 15.2, "rising", "high", "grocery"),
        _signal("hielo", 9, "2024-01-07", 60.0, -3.0, "falling", "low", "grocery"),
    ]
    with _with_client(signals=monkey_rows):
        api_app.get_client.cache_clear()
        with patch.object(api_app, "TOP_MOVERS_MAX_POINTS", 1):
            data = test_client.get("/demand/api/analytics").json()
    assert [point["keyword"] for point in _points(data, "top_movers")] == ["cerveza"]
    assert _segment(data, "top_movers")["confidence"] == "high"


def test_composition_confidence_drops_when_the_read_is_truncated(test_client, live, monkeypatch):
    """A share computed over a truncated read says so, in the label."""
    data = test_client.get("/demand/api/analytics").json()
    assert _segment(data, "category_mix")["confidence"] == "high"
    assert _segment(data, "stock_out_risk")["confidence"] == "high"

    monkeypatch.setattr(api_app, "ANALYTICS_PRODUCTS_CAP", 3)
    data = test_client.get("/demand/api/analytics").json()
    assert _segment(data, "category_mix")["confidence"] == "low"
    assert _segment(data, "stock_out_risk")["confidence"] == "low"


def test_empty_inputs_give_empty_but_shaped_low_confidence_segments(test_client, live):
    with _with_client(signals=[], products=[]):
        api_app.get_client.cache_clear()
        response = test_client.get("/demand/api/analytics")
    assert response.status_code == 200
    data = response.json()
    validate_with_formats(data, ANALYTICS_SCHEMA)
    for segment in ("top_movers", "category_mix", "stock_out_risk"):
        assert _points(data, segment) == [], segment
    assert _segment(data, "top_movers")["confidence"] == "low"


# ---------------------------------------------------------------------------
# store_id is used, not merely accepted
# ---------------------------------------------------------------------------

def test_store_id_scopes_the_inventory_segments(test_client, live):
    unscoped = test_client.get("/demand/api/analytics").json()
    scoped = test_client.get(f"/demand/api/analytics?store_id={STORE_A}").json()

    assert _by_category(_points(unscoped, "category_mix")).keys() != _by_category(
        _points(scoped, "category_mix")
    ).keys()

    mix = _by_category(_points(scoped, "category_mix"))
    assert set(mix) == {"grocery", "pharmacy", "electronics"}
    assert mix["grocery"]["product_count"] == 5
    assert mix["grocery"]["share_pct"] == 50.0

    risk = _by_category(_points(scoped, "stock_out_risk"))
    assert risk["grocery"]["at_risk_count"] == 4
    assert risk["grocery"]["total_count"] == 5


def test_store_id_does_not_pretend_to_scope_search_interest(test_client, live):
    """demand_signals has no store dimension; top_movers is ES-MD wide."""
    unscoped = test_client.get("/demand/api/analytics").json()
    scoped = test_client.get(f"/demand/api/analytics?store_id={STORE_B}").json()
    assert _points(unscoped, "top_movers") == _points(scoped, "top_movers")


def test_unknown_store_id_yields_empty_inventory_segments(test_client, live):
    unknown = "44444444-4444-4444-4444-444444444444"
    data = test_client.get(f"/demand/api/analytics?store_id={unknown}").json()
    assert _points(data, "category_mix") == []
    assert _points(data, "stock_out_risk") == []


# ---------------------------------------------------------------------------
# Failure paths: described, never a stack trace
# ---------------------------------------------------------------------------

def test_analytics_invalid_inventory_type(test_client):
    response = test_client.get("/demand/api/analytics?inventory_type=grocery")
    assert response.status_code == 422


@pytest.mark.parametrize(
    "mutation",
    [
        {"interest_avg": 150},
        {"direction": "unknown"},
        {"keyword": None},
        {"interest_avg": "not-a-number"},
    ],
)
def test_out_of_contract_signal_row_is_a_described_500(test_client, live, mutation):
    """No CHECK constraints on these columns, so every case is reachable."""
    rows = signal_rows()
    rows[2].update(mutation)
    with _with_client(signals=rows):
        api_app.get_client.cache_clear()
        response = test_client.get("/demand/api/analytics")
    assert response.status_code == 500
    assert response.json()["detail"] == "Response failed the analytics_response contract"
    assert "Traceback" not in response.text


def test_a_signal_row_missing_keyword_entirely_is_not_a_crash(test_client, live):
    rows = signal_rows()
    del rows[2]["keyword"]
    with _with_client(signals=rows):
        api_app.get_client.cache_clear()
        response = test_client.get("/demand/api/analytics")
    assert response.status_code == 500
    assert response.json()["detail"] == "Response failed the analytics_response contract"


def test_analytics_db_failure_raises_502(test_client, live):
    class ExceptionQueryBuilder:
        def select(self, *args, **kwargs):
            return self

        def eq(self, *args, **kwargs):
            return self

        def order(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def execute(self):
            raise Exception("password=hunter2")

    class ExceptionFakeSupabase:
        def schema(self, name):
            return self

        def table(self, name):
            return ExceptionQueryBuilder()

    with patch("demand.api.app.create_client", return_value=ExceptionFakeSupabase()):
        api_app.get_client.cache_clear()
        response = test_client.get("/demand/api/analytics")
    assert response.status_code == 502
    assert response.json()["detail"] == api_app.DB_FAILURE_DETAIL
    assert "hunter2" not in response.text


def test_analytics_missing_credentials_is_502(live, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    api_app.get_client.cache_clear()
    try:
        response = TestClient(api_app.app).get("/demand/api/analytics")
        assert response.status_code == 502
        assert response.json()["detail"] == api_app.DB_FAILURE_DETAIL
    finally:
        api_app.get_client.cache_clear()


# ---------------------------------------------------------------------------
# Schema-level facts the endpoint depends on
# ---------------------------------------------------------------------------

def test_analytics_empty_points_array_validates():
    payload = {
        "inventory_type": "convenience_store",
        "generated_from": "live",
        "generated_at": "2026-08-03T00:00:00+00:00",
        "caveat": api_app.CANONICAL_CAVEAT,
        "segments": {
            "top_movers": {"confidence": "low", "points": []},
            "category_mix": {"confidence": "low", "points": []},
            "stock_out_risk": {"confidence": "low", "points": []},
        },
    }
    validate_with_formats(payload, ANALYTICS_SCHEMA)


def test_analytics_missing_caveat_fails_validation():
    payload = {
        "inventory_type": "convenience_store",
        "generated_from": "live",
        "generated_at": "2026-08-03T00:00:00+00:00",
        "segments": {
            "top_movers": {"confidence": "low", "points": []},
            "category_mix": {"confidence": "low", "points": []},
            "stock_out_risk": {"confidence": "low", "points": []},
        },
    }
    with pytest.raises(jsonschema.ValidationError):
        validate_with_formats(payload, ANALYTICS_SCHEMA)
