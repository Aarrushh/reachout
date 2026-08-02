import uuid

import pytest
from jsonschema import ValidationError

from demand.scripts.compute_signals import signal_id
from demand.scripts.recommend import build_recommendations, load_schema, recommendation_id
from demand.shared.validation import validate_with_formats
from demand.tests.fake_supa import FakeSupabase

# store_id and product id are `format: uuid` in recommendation.schema.json /
# public.stores. They are real UUIDs here because validation now enforces
# `format` (demand/shared/validation.py): "store_a" validated only while
# bare jsonschema.validate was silently ignoring the keyword.
STORE_A = "aaaaaaaa-0000-4000-8000-000000000001"
STORE_B = "bbbbbbbb-0000-4000-8000-000000000002"
STORE_C = "cccccccc-0000-4000-8000-000000000003"
STORE_EMPTY = "dddddddd-0000-4000-8000-000000000004"
STORE_NULLSTOCK = "eeeeeeee-0000-4000-8000-000000000005"


def _pid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


# Create some fake stores
F_STORES = [
    {"id": STORE_A, "name": "Store A"},
    {"id": STORE_B, "name": "Store B"},
    {"id": STORE_C, "name": "Store C"},
    {"id": STORE_EMPTY, "name": "Store Empty"}
]

# Create some fake products mapped to "clothing"
# Store A: 3 in stock (feature_in_window candidate)
# Store B: 1 in stock (stock_up / watch candidate)
# Store C: 0 in stock (should be ignored)
F_PRODUCTS = [
    {"id": _pid(1), "store_id": STORE_A, "category": "clothing", "stock_qty": 5},
    {"id": _pid(2), "store_id": STORE_A, "category": "clothing", "stock_qty": 2},
    {"id": _pid(3), "store_id": STORE_A, "category": "clothing", "stock_qty": 1},
    {"id": _pid(4), "store_id": STORE_A, "category": "electronics", "stock_qty": 10},  # wrong cat

    {"id": _pid(5), "store_id": STORE_B, "category": "clothing", "stock_qty": 1},

    {"id": _pid(6), "store_id": STORE_C, "category": "clothing", "stock_qty": 0}  # out of stock
]


def make_signal(direction, confidence, category="clothing", keyword="test_kw"):
    window_start, window_end = "2023-01-02", "2023-01-08"
    return {
        "id": signal_id(keyword, "ES-MD", window_start, window_end),
        "keyword": keyword,
        "category": category,
        "geo": "ES-MD",
        "window_start": window_start,
        "window_end": window_end,
        "interest_avg": 50.0,
        "delta_pct": 20.0,
        "direction": direction,
        "rank": 1,
        "confidence": confidence,
        "snapshot_ids": [str(uuid.uuid4())],
        "computed_at": "2023-01-09T00:00:00Z"
    }

def make_client(products=None, stores=None):
    """A fake shaped like production, not like the code's assumptions.

    The client `run_chain` hands to `build_recommendations` comes from
    `demand.api.app.get_client()`, which is built with
    `ClientOptions(schema="demand")`. `products` and `stores` are
    `public` tables (`reachout/data/schema.sql`); `demand/data/schema.sql`
    creates only trend_snapshots / demand_signals / recommendations. So the
    default schema here is `demand` and `products` is declared under
    `public` -- which means an unqualified `.table("products")` raises
    instead of quietly finding the fixture in the wrong schema.
    """
    return FakeSupabase(
        default_schema="demand",
        tables={"demand_signals": [], "recommendations": []},
        schemas={
            "public": {
                "stores": F_STORES if stores is None else stores,
                "products": F_PRODUCTS if products is None else products,
            }
        },
    )


@pytest.fixture
def supa_client():
    return make_client()

@pytest.mark.parametrize("direction, confidence, store_id, expected_action", [
    # Store A has 3 products -> feature_in_window if rising
    ("rising", "high", STORE_A, "feature_in_window"),
    ("rising", "low", STORE_A, "feature_in_window"), # in_stock >= 3 overrides confidence for rising

    # Store B has 1 product -> stock_up if rising + high/medium
    ("rising", "high", STORE_B, "stock_up"),
    ("rising", "medium", STORE_B, "stock_up"),
    # Store B has 1 product -> watch if rising + low
    ("rising", "low", STORE_B, "watch"),

    # Falling -> watch regardless of stock count and confidence
    ("falling", "high", STORE_A, "watch"),
    ("falling", "low", STORE_B, "watch"),

    # Flat -> watch
    ("flat", "high", STORE_A, "watch"),
])
def test_action_rules(supa_client, direction, confidence, store_id, expected_action):
    signal = make_signal(direction, confidence)
    results = build_recommendations([signal], supa_client)

    # Find the recommendation for the specified store
    rec = next((r for r in results if r["store_id"] == store_id), None)
    assert rec is not None
    assert rec["action"] == expected_action

def test_zero_matching_products_ignored(supa_client):
    signal = make_signal("rising", "high")
    results = build_recommendations([signal], supa_client)

    store_ids = [r["store_id"] for r in results]
    assert STORE_A in store_ids # has 3
    assert STORE_B in store_ids # has 1
    assert STORE_C not in store_ids # has 0 in stock
    assert STORE_EMPTY not in store_ids # has 0 products


def test_null_stock_qty_is_treated_as_zero():
    """Supabase returns a NULL column as the key present with value None, so
    `.get("stock_qty", 0)` never fires its default and `None > 0` raises."""
    products = F_PRODUCTS + [
        {"id": _pid(7), "store_id": STORE_NULLSTOCK, "category": "clothing", "stock_qty": None},
    ]
    client = make_client(products=products)

    results = build_recommendations([make_signal("rising", "high")], client)

    assert STORE_NULLSTOCK not in [r["store_id"] for r in results]
    assert STORE_A in [r["store_id"] for r in results]


def _record_reads(client, monkeypatch):
    """Record every (schema, table, columns) the code asks the client for."""
    asked = []
    original_schema = client.schema

    def recording_schema(schema_name):
        view = original_schema(schema_name)
        original_table = view.table

        def recording_table(table_name):
            builder = original_table(table_name)
            original_select = builder.select

            def recording_select(cols="*", count=None):
                asked.append((schema_name, table_name, cols))
                return original_select(cols, count)

            builder.select = recording_select
            return builder

        view.table = recording_table
        return view

    monkeypatch.setattr(client, "schema", recording_schema)
    return asked


def test_products_are_read_from_the_public_schema(monkeypatch):
    """`products` is a `public` table and the client is bound to `demand`.
    Against real Supabase an unqualified read resolves to
    `demand.products`, which does not exist."""
    client = make_client()
    asked = _record_reads(client, monkeypatch)

    build_recommendations([make_signal("rising", "high")], client)

    product_reads = [r for r in asked if r[1] == "products"]
    assert product_reads, "recommend.py must read products"
    assert all(schema == "public" for schema, _, _ in product_reads)


def test_products_read_is_narrowed_to_the_columns_used(monkeypatch):
    """`select("*")` drags the 768-dim embedding column over the wire once
    per signal. The fake records what the code actually asked for."""
    client = make_client()
    asked = _record_reads(client, monkeypatch)

    build_recommendations([make_signal("rising", "high")], client)

    product_reads = [r for r in asked if r[1] == "products"]
    assert product_reads, "recommend.py must read products"
    for _, _, cols in product_reads:
        assert cols not in ("*", "", None)
        assert set(c.strip() for c in cols.split(",")) == {"store_id", "stock_qty"}


def test_recommendation_ids_are_deterministic(supa_client):
    """Same (store_id, signal_id) -> same row id on every run: the dedupe
    index's key, so the upsert updates instead of churning identities."""
    signal = make_signal("rising", "high")

    first = build_recommendations([signal], supa_client)
    second = build_recommendations([signal], supa_client)

    assert [r["id"] for r in first] == [r["id"] for r in second]
    for rec in first:
        assert rec["id"] == recommendation_id(rec["store_id"], rec["signal_id"])
        assert uuid.UUID(rec["id"]).version == 5


def test_output_order_is_deterministic(supa_client):
    """Ordered by store_id, not by whatever order the product rows arrived."""
    signal = make_signal("rising", "high")
    results = build_recommendations([signal], supa_client)

    assert [r["store_id"] for r in results] == sorted(r["store_id"] for r in results)


def test_schema_validation_and_caveat(supa_client):
    signal = make_signal("rising", "high")
    results = build_recommendations([signal], supa_client)

    assert len(results) > 0
    rec = results[0]

    # Verify the specific non-empty caveat text
    assert rec["caveat"] == "Basado en interés de búsqueda en Madrid, no en compras reales."

    # Tamper with caveat to test schema failure
    schema = load_schema("recommendation.schema.json")

    del rec["caveat"]
    with pytest.raises(ValidationError):
        validate_with_formats(instance=rec, schema=schema)

    rec["caveat"] = ""
    with pytest.raises(ValidationError):
        validate_with_formats(instance=rec, schema=schema)


def test_non_uuid_store_id_fails_validation(supa_client):
    """`format: uuid` is enforced now: the pre-W1-FIX-D fixtures used
    "store_a" and validated only because format was being ignored."""
    client = make_client(
        products=[{"id": _pid(8), "store_id": "store_a", "category": "clothing", "stock_qty": 3}]
    )

    with pytest.raises(ValidationError):
        build_recommendations([make_signal("rising", "high")], client)
