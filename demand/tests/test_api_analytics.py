import json
import os
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
import jsonschema

from demand.api import app as api_app
from demand.tests.fake_supa import FakeSupabase

ANALYTICS_SCHEMA = api_app.load_schema("analytics_response.schema.json")

def get_fake_supa_client():
    fake_tables = {
        "demand_signals": [
            {
                "id": str(uuid.uuid4()),
                "keyword": "cerveza",
                "category": "Alcohol",
                "interest_avg": 85.5,
                "delta_pct": 15.2,
                "direction": "rising",
                "confidence": "high"
            }
        ],
        "products": [
            {"id": str(uuid.uuid4()), "category": "Alcohol"} for _ in range(10)
        ] + [
            {"id": str(uuid.uuid4()), "category": "Snacks"} for _ in range(30)
        ]
    }
    return FakeSupabase(tables=fake_tables)

@pytest.fixture
def test_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "fake-url")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")

    with patch("demand.api.app.create_client", return_value=get_fake_supa_client()):
        api_app.get_client.cache_clear()
        client = TestClient(api_app.app)
        yield client
        api_app.get_client.cache_clear()

def test_analytics_fixture_mode(test_client, monkeypatch):
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "fixture")
    response = test_client.get("/demand/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["generated_from"] == "fixture"
    assert data["inventory_type"] == "convenience_store"
    # The endpoint itself validates, but let's double check.
    jsonschema.validate(instance=data, schema=ANALYTICS_SCHEMA)

def test_analytics_live_mode(test_client, monkeypatch):
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "live")
    response = test_client.get("/demand/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["generated_from"] == "live"
    assert data["inventory_type"] == "convenience_store"
    jsonschema.validate(instance=data, schema=ANALYTICS_SCHEMA)
    
    # Check shape logic explicitly
    assert len(data["segments"]["top_movers"]["points"]) == 1
    assert data["segments"]["top_movers"]["points"][0]["keyword"] == "cerveza"
    
    # Categories: Alcohol (10), Snacks (30) -> Total 40
    # Mix: Alcohol 25%, Snacks 75%
    mix_points = data["segments"]["category_mix"]["points"]
    assert len(mix_points) == 2
    for p in mix_points:
        if p["category"] == "Alcohol":
            assert p["share_pct"] == 25.0
            assert p["product_count"] == 10
        elif p["category"] == "Snacks":
            assert p["share_pct"] == 75.0
            assert p["product_count"] == 30

def test_analytics_invalid_inventory_type(test_client):
    response = test_client.get("/demand/api/analytics?inventory_type=grocery")
    assert response.status_code == 422

def test_analytics_empty_points_array_validates():
    import datetime
    payload = {
        "inventory_type": "convenience_store",
        "generated_from": "live",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "caveat": "Basado en interés de búsqueda en Madrid, no en compras reales.",
        "segments": {
            "top_movers": {"confidence": "low", "points": []},
            "category_mix": {"confidence": "low", "points": []},
            "stock_out_risk": {"confidence": "low", "points": []}
        }
    }
    jsonschema.validate(instance=payload, schema=ANALYTICS_SCHEMA)

def test_analytics_missing_caveat_fails_validation():
    import datetime
    from jsonschema.exceptions import ValidationError
    payload = {
        "inventory_type": "convenience_store",
        "generated_from": "live",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        # MISSING "caveat"
        "segments": {
            "top_movers": {"confidence": "low", "points": []},
            "category_mix": {"confidence": "low", "points": []},
            "stock_out_risk": {"confidence": "low", "points": []}
        }
    }
    with pytest.raises(ValidationError):
        jsonschema.validate(instance=payload, schema=ANALYTICS_SCHEMA)

def test_analytics_db_failure_raises_502(test_client, monkeypatch):
    monkeypatch.setenv("DEMAND_ANALYTICS_SOURCE", "live")
    
    class ExceptionQueryBuilder:
        def select(self, *args, **kwargs):
            return self
        def execute(self):
            raise Exception("DB failed")
            
    class ExceptionFakeSupabase:
        def schema(self, name):
            return self
        def table(self, name):
            return ExceptionQueryBuilder()

    with patch("demand.api.app.create_client", return_value=ExceptionFakeSupabase()):
        api_app.get_client.cache_clear()
        response = test_client.get("/demand/api/analytics")
        assert response.status_code == 502
