import pytest
from fastapi.testclient import TestClient

from scripts import db
from api import server
from tests.test_api import _seeded_db

def test_inventory_pagination_stability(tmp_path, monkeypatch):
    """
    With the simulator OFF, walking /api/inventory pages 1..N yields each
    (shop_id, sku) exactly once. This tests the ORDER BY shop_id, sku contract.
    """
    monkeypatch.setenv("REACHOUT_OFFLINE", "1")
    monkeypatch.delenv("REACHOUT_SIM", raising=False)
    
    # We are allowed to import _seeded_db from test_api based on memories.
    db_path = _seeded_db(tmp_path)
    
    conn = db.connect(db_path)
    # Add items to existing shop
    for i in range(1, 15):
        db.upsert_item(conn, {
            "shop_id": "osm:node:1001",
            "sku": f"PHA-{1000+i:04d}",
            "name": f"Paracetamol Extra {i}",
            "category": "pharmacy",
            "price": 3.95,
            "currency": "EUR",
            "qty": 5,
            "synthetic": True,
        })
        
    # Add new shop and items
    db.upsert_shop(conn, {
        "shop_id": "osm:node:1002", "osm_id": 1002, "name": "Otra Farmacia",
        "categories": ["pharmacy"], "lat": 40.4271, "lng": -3.7036,
        "address": "Calle del Pez 2", "source": "cache",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    })
    for i in range(1, 15):
        db.upsert_item(conn, {
            "shop_id": "osm:node:1002",
            "sku": f"PHA-{2000+i:04d}",
            "name": f"Ibuprofeno {i}",
            "category": "pharmacy",
            "price": 4.00,
            "currency": "EUR",
            "qty": 5,
            "synthetic": True,
        })
    conn.commit()
    conn.close()

    monkeypatch.setattr(server, "DB_PATH", db_path)
    monkeypatch.setattr(server, "NOTIF_DIR", str(tmp_path / "notifications"))
    
    client = TestClient(server.app)
    
    seen = set()
    page = 1
    page_size = 5
    
    # Check total items dynamically instead of hardcoding 29
    resp_total = client.get(f"/api/inventory?page=1&page_size=1")
    assert resp_total.status_code == 200
    total_expected = resp_total.json()["total_items"]
    
    while True:
        resp = client.get(f"/api/inventory?page={page}&page_size={page_size}")
        assert resp.status_code == 200
        data = resp.json()
        items = data["items"]
        
        for item in items:
            pair = (item["shop_id"], item["sku"])
            assert pair not in seen, f"Duplicate item found on page {page}: {pair}"
            seen.add(pair)
            
        if page >= data["total_pages"]:
            break
        page += 1
        
    assert len(seen) == total_expected
    assert data["total_items"] == total_expected
