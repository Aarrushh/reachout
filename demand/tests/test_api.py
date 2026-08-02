import os
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from demand.api import app as api_app
from tests.fake_supa import FakeSupabase

def get_fake_supa_client():
    fake_tables = {
        "trend_snapshots": [
            {
                "id": str(uuid.uuid4()),
                "keyword": "cerveza",
                "geo": "ES-MD",
                "timeframe": "today 3-m",
                "provider": "trendspy",
                "captured_at": "2024-01-01T12:00:00Z",
                "series": [{"date": "2024-01-01", "value": 50}],
                "region_breakdown": None
            }
        ],
        "demand_signals": [
            {
                "id": str(uuid.uuid4()),
                "keyword": "cerveza",
                "category": "Alcohol",
                "geo": "ES-MD",
                "window_start": "2024-01-01",
                "window_end": "2024-01-07",
                "interest_avg": 50,
                "delta_pct": 10.0,
                "direction": "rising",
                "rank": 1,
                "confidence": "high",
                "snapshot_ids": [str(uuid.uuid4())],
                "computed_at": "2024-01-08T12:00:00Z"
            }
        ],
        "recommendations": [
            {
                "id": str(uuid.uuid4()),
                "store_id": "11111111-1111-1111-1111-111111111111",
                "signal_id": str(uuid.uuid4()),
                "headline": "Stock up on Cerveza",
                "body": "Interest is high.",
                "action": "stock_up",
                "confidence": "high",
                "caveat": "Basado en interés de búsqueda en Madrid, no en compras reales.",
                "created_at": "2024-01-08T12:00:00Z"
            }
        ]
    }
    return FakeSupabase(tables=fake_tables)


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


def test_health(test_client):
    response = test_client.get("/demand/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_trends(test_client):
    response = test_client.get("/demand/api/trends")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["keyword"] == "cerveza"
    
def test_get_signals(test_client):
    # No filters
    response = test_client.get("/demand/api/signals")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Filter window_start
    response = test_client.get("/demand/api/signals?window=2024-01-01")
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    response = test_client.get("/demand/api/signals?window=2024-02-01")
    assert response.status_code == 200
    assert len(response.json()) == 0
    
    # Filter direction
    response = test_client.get("/demand/api/signals?direction=rising")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_get_recommendations(test_client):
    # No store_id
    response = test_client.get("/demand/api/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == "00000000-0000-0000-0000-000000000000"
    assert len(data["recommendations"]) == 0

    # With store_id (known)
    response = test_client.get("/demand/api/recommendations?store_id=11111111-1111-1111-1111-111111111111")
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == "11111111-1111-1111-1111-111111111111"
    assert len(data["recommendations"]) == 1

    # With store_id (unknown)
    response = test_client.get("/demand/api/recommendations?store_id=22222222-2222-2222-2222-222222222222")
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == "22222222-2222-2222-2222-222222222222"
    assert len(data["recommendations"]) == 0


def test_exception_returns_502(test_client, monkeypatch):
    class ExceptionQueryBuilder:
        def select(self, *args, **kwargs):
            return self
            
        def execute(self):
            raise Exception("Some Supabase error")

    class ExceptionFakeSupabase:
        def table(self, name):
            return ExceptionQueryBuilder()

    with patch("demand.api.app.create_client", return_value=ExceptionFakeSupabase()):
        api_app.get_client.cache_clear()
        
        response = test_client.get("/demand/api/trends")
        assert response.status_code == 502
        assert "Database dependency failed" in response.json()["detail"]


def test_no_auth_endpoints_401_or_403(test_client):
    endpoints = [
        "/demand/api/health",
        "/demand/api/trends",
        "/demand/api/signals",
        "/demand/api/recommendations",
        "/demand/api/signals?window=test",
        "/demand/api/recommendations?store_id=123"
    ]
    for endpoint in endpoints:
        response = test_client.get(endpoint)
        assert response.status_code not in [401, 403], f"Endpoint {endpoint} returned {response.status_code}"
