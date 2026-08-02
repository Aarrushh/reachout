import pytest
import jsonschema
import uuid
from demand.scripts.recommend import build_recommendations
from demand.tests.fake_supa import FakeSupabase

# Create some fake stores
F_STORES = [
    {"id": "store_a", "name": "Store A"},
    {"id": "store_b", "name": "Store B"},
    {"id": "store_c", "name": "Store C"},
    {"id": "store_empty", "name": "Store Empty"}
]

# Create some fake products mapped to "clothing"
# Store A: 3 in stock (feature_in_window candidate)
# Store B: 1 in stock (stock_up / watch candidate)
# Store C: 0 in stock (should be ignored)
F_PRODUCTS = [
    {"id": "p1", "store_id": "store_a", "category": "clothing", "stock_qty": 5},
    {"id": "p2", "store_id": "store_a", "category": "clothing", "stock_qty": 2},
    {"id": "p3", "store_id": "store_a", "category": "clothing", "stock_qty": 1},
    {"id": "p4", "store_id": "store_a", "category": "electronics", "stock_qty": 10}, # wrong cat
    
    {"id": "p5", "store_id": "store_b", "category": "clothing", "stock_qty": 1},
    
    {"id": "p6", "store_id": "store_c", "category": "clothing", "stock_qty": 0} # out of stock
]

def make_signal(direction, confidence, category="clothing"):
    return {
        "id": str(uuid.uuid4()),
        "keyword": "test_kw",
        "category": category,
        "geo": "ES-MD",
        "window_start": "2023-01-02",
        "window_end": "2023-01-08",
        "interest_avg": 50.0,
        "delta_pct": 20.0,
        "direction": direction,
        "rank": 1,
        "confidence": confidence,
        "snapshot_ids": [str(uuid.uuid4())],
        "computed_at": "2023-01-09T00:00:00Z"
    }

@pytest.fixture
def supa_client():
    return FakeSupabase(tables={"stores": F_STORES, "products": F_PRODUCTS})

@pytest.mark.parametrize("direction, confidence, store_id, expected_action", [
    # Store A has 3 products -> feature_in_window if rising
    ("rising", "high", "store_a", "feature_in_window"),
    ("rising", "low", "store_a", "feature_in_window"), # in_stock >= 3 overrides confidence for rising
    
    # Store B has 1 product -> stock_up if rising + high/medium
    ("rising", "high", "store_b", "stock_up"),
    ("rising", "medium", "store_b", "stock_up"),
    # Store B has 1 product -> watch if rising + low
    ("rising", "low", "store_b", "watch"),
    
    # Falling -> watch regardless of stock count and confidence
    ("falling", "high", "store_a", "watch"),
    ("falling", "low", "store_b", "watch"),
    
    # Flat -> watch
    ("flat", "high", "store_a", "watch"),
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
    assert "store_a" in store_ids # has 3
    assert "store_b" in store_ids # has 1
    assert "store_c" not in store_ids # has 0 in stock
    assert "store_empty" not in store_ids # has 0 products
    
def test_schema_validation_and_caveat(supa_client):
    signal = make_signal("rising", "high")
    results = build_recommendations([signal], supa_client)
    
    assert len(results) > 0
    rec = results[0]
    
    # Verify the specific non-empty caveat text
    assert rec["caveat"] == "Basado en interés de búsqueda en Madrid, no en compras reales."
    
    # Tamper with caveat to test schema failure
    from demand.scripts.recommend import load_schema
    schema = load_schema("recommendation.schema.json")
    
    del rec["caveat"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=rec, schema=schema)
        
    rec["caveat"] = ""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=rec, schema=schema)
