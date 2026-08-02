import pytest
import os
from fastapi.testclient import TestClient
import unittest.mock

from reachout.api.server import app
from fake_supa import FakeSupabase

@pytest.fixture
def client():
    return TestClient(app)

def patch_db(db):
    patcher_env = unittest.mock.patch.dict(os.environ, {"SUPABASE_URL": "http://fake", "SUPABASE_KEY": "fake"})
    patcher_env.start()

    patcher_create = unittest.mock.patch("supabase.create_client", return_value=db)
    patcher_create.start()
    
    import reachout.api.supa as supa
    supa.get_client.cache_clear()
    
    patcher_picks = unittest.mock.patch("api.picks._supa_client", return_value=db)
    patcher_picks.start()

    return patcher_env, patcher_create, patcher_picks

def test_picks_deterministic(client):
    stores = [
        {"id": "store1", "name": "Store 1", "rating": 4.5},
        {"id": "store2", "name": "Store 2", "rating": 4.0},
    ]
    products = [
        {"id": "p1", "name": "Product 1", "category": "cat1", "price": 10.0, "stock_qty": 5, "store_id": "store1", "neighbourhood": "Sol", "tags": [], "description": "d"},
        {"id": "p2", "name": "Product 2", "category": "cat2", "price": 10.0, "stock_qty": 5, "store_id": "store2", "neighbourhood": "Sol", "tags": [], "description": "d"},
        {"id": "p3", "name": "Product 3", "category": "cat1", "price": 10.0, "stock_qty": 5, "store_id": "store2", "neighbourhood": "Sol", "tags": [], "description": "d"},
    ]
    db = FakeSupabase({"stores": stores, "products": products})
    e, c, p = patch_db(db)
    
    try:
        resp1 = client.get("/api/picks")
        assert resp1.status_code == 200, resp1.text
        picks1 = resp1.json()["picks"]
        
        resp2 = client.get("/api/picks")
        assert resp2.status_code == 200
        picks2 = resp2.json()["picks"]
        
        assert [p["id"] for p in picks1] == [p["id"] for p in picks2]
    finally:
        p.stop()
        c.stop()
        e.stop()

def test_picks_category_diversity(client):
    stores = [
        {"id": "store1", "rating": 5.0},
        {"id": "store2", "rating": 4.0},
    ]
    products = [
        {"id": "p1", "name": "P1", "category": "cat1", "price": 10.0, "stock_qty": 5, "store_id": "store1", "neighbourhood": "Sol", "tags": [], "description": "d"},
        {"id": "p2", "name": "P2", "category": "cat1", "price": 10.0, "stock_qty": 5, "store_id": "store1", "neighbourhood": "Sol", "tags": [], "description": "d"},
        {"id": "p3", "name": "P3", "category": "cat2", "price": 10.0, "stock_qty": 5, "store_id": "store2", "neighbourhood": "Sol", "tags": [], "description": "d"},
    ]
    db = FakeSupabase({"stores": stores, "products": products})
    e, c, p = patch_db(db)

    try:
        resp = client.get("/api/picks")
        assert resp.status_code == 200, resp.text
        picks = resp.json()["picks"]
        
        assert [p["id"] for p in picks] == ["p1", "p3", "p2"]
    finally:
        p.stop()
        c.stop()
        e.stop()

def test_picks_out_of_stock_excluded(client):
    stores = [{"id": "store1", "rating": 5.0}]
    products = [
        {"id": "p1", "name": "P1", "category": "cat1", "price": 10.0, "stock_qty": 5, "store_id": "store1", "neighbourhood": "Sol", "tags": [], "description": "d"},
        {"id": "p2", "name": "P2", "category": "cat1", "price": 10.0, "stock_qty": 0, "store_id": "store1", "neighbourhood": "Sol", "tags": [], "description": "d"},
    ]
    db = FakeSupabase({"stores": stores, "products": products})
    e, c, p = patch_db(db)
    
    try:
        resp = client.get("/api/picks")
        assert resp.status_code == 200, resp.text
        picks = resp.json()["picks"]
        
        assert len(picks) == 1
        assert picks[0]["id"] == "p1"
    finally:
        p.stop()
        c.stop()
        e.stop()

def test_picks_neighbourhood_filter(client):
    stores = [{"id": "store1", "rating": 5.0}]
    products = [
        {"id": "p1", "name": "P1", "category": "cat1", "price": 10.0, "stock_qty": 5, "store_id": "store1", "neighbourhood": "Malasaña", "tags": [], "description": "d"},
        {"id": "p2", "name": "P2", "category": "cat1", "price": 10.0, "stock_qty": 5, "store_id": "store1", "neighbourhood": "Sol", "tags": [], "description": "d"},
    ]
    db = FakeSupabase({"stores": stores, "products": products})
    e, c, p = patch_db(db)
    
    try:
        resp = client.get("/api/picks?neighbourhood=malasana")
        assert resp.status_code == 200, resp.text
        picks = resp.json()["picks"]
        
        assert len(picks) == 1
        assert picks[0]["id"] == "p1"
    finally:
        p.stop()
        c.stop()
        e.stop()

def test_picks_limit_bounds(client):
    resp = client.get("/api/picks?limit=100")
    assert resp.status_code == 422
    
    resp = client.get("/api/picks?limit=0")
    assert resp.status_code == 422

def test_picks_502_error(client):
    class ErrorSupabase:
        def table(self, _):
            class ErrorTable:
                def select(self, _):
                    class ErrorBuilder:
                        def eq(self, *args, **kwargs):
                            return self
                        def execute(self):
                            raise Exception("Boom")
                    return ErrorBuilder()
            return ErrorTable()
            
    db = ErrorSupabase()
    e, c, p = patch_db(db)

    try:
        resp = client.get("/api/picks")
        assert resp.status_code == 502
    finally:
        p.stop()
        c.stop()
        e.stop()
