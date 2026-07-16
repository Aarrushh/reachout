import pytest
import db
import validate as v
from fastapi.testclient import TestClient

import server


def _seeded_db(tmp_path):
    """One pharmacy near Malasaña, one electronics shop near Puerta del Sol."""
    db_path = str(tmp_path / "reachout.db")
    db.init_db(db_path)
    conn = db.connect(db_path)
    db.upsert_region(conn, {
        "region_id": "malasana", "name": "Malasaña", "lat": 40.4267,
        "lng": -3.7038, "source": "gazetteer", "created_at": "2026-07-07T10:00:00+00:00"
    })
    db.upsert_shop(conn, {
        "shop_id": "osm:node:1001", "osm_id": 1001, "name": "Farmacia Malasaña",
        "categories": ["pharmacy"], "lat": 40.4270, "lng": -3.7035,
        "address": "Calle del Pez 1", "source": "cache",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    })
    # Update region_id manually to test shop counts since upsert_shop doesn't include it.
    conn.execute("UPDATE shops SET region_id=? WHERE shop_id=?", ("malasana", "osm:node:1001"))
    db.upsert_item(conn, {
        "shop_id": "osm:node:1001", "sku": "PHA-0001", "name": "Paracetamol 1g 40 comprimidos",
        "category": "pharmacy", "price": 3.95, "currency": "EUR", "qty": 5, "synthetic": True,
    })
    conn.commit()
    conn.close()
    return db_path


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("REACHOUT_OFFLINE", "1")
    db_path = _seeded_db(tmp_path)
    monkeypatch.setattr(server, "DB_PATH", db_path)
    monkeypatch.setattr(server, "NOTIF_DIR", str(tmp_path / "notifications"))
    return TestClient(server.app)


def test_health(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    # The _client fixture calls _seeded_db which adds 1 shop and 1 region
    assert body == {"status": "ok", "shop_count": 1, "region_count": 1, "simulator_running": False}
    ok, err = v.validate(body, "health_response.schema.json")
    assert ok, err


def test_inventory_pagination_and_schema(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    
    # Valid request for specific region
    resp = client.get("/api/inventory?region=malasana&page=1&page_size=25")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["total_items"] == 1
    assert body["total_pages"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["shop_id"] == "osm:node:1001"
    assert item["shop_name"] == "Farmacia Malasaña"
    assert item["sku"] == "PHA-0001"
    ok, err = v.validate(body, "inventory_response.schema.json")
    assert ok, err

    # Valid request for all regions
    resp = client.get("/api/inventory?page=1&page_size=25")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["total_items"] == 1
    assert body["total_pages"] == 1
    assert len(body["items"]) == 1
    ok, err = v.validate(body, "inventory_response.schema.json")
    assert ok, err

    # Out of bounds page
    resp = client.get("/api/inventory?page=0&page_size=25")
    assert resp.status_code == 422

    # Out of bounds page_size
    resp = client.get("/api/inventory?page=1&page_size=101")
    assert resp.status_code == 422

    # Empty page (page 2 when only 1 item exists)
    resp = client.get("/api/inventory?page=2&page_size=25")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["total_items"] == 1
    assert body["total_pages"] == 1
    assert len(body["items"]) == 0
    ok, err = v.validate(body, "inventory_response.schema.json")
    assert ok, err

    # 404 for unknown region
    resp = client.get("/api/inventory?region=unknown&page=1&page_size=25")
    assert resp.status_code == 404

    # Pagination math test: multiple pages
    # Let's add more items directly to the DB to test total_pages math
    db_path = str(tmp_path / "reachout.db")
    conn = db.connect(db_path)
    for i in range(2, 6):
        db.upsert_item(conn, {
            "shop_id": "osm:node:1001", "sku": f"PHA-000{i}", "name": f"Item {i}",
            "category": "pharmacy", "price": 3.95, "currency": "EUR", "qty": 5, "synthetic": True,
        })
    conn.commit()
    conn.close()

    resp = client.get("/api/inventory?page=1&page_size=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_items"] == 5
    assert body["total_pages"] == 3
    assert len(body["items"]) == 2


def test_search_region_returns_schema_valid_ranked_shops(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/search", params={
        "q": "algo para el dolor de cabeza", "region": "malasana", "radius": 2.0,
    })
    assert resp.status_code == 200
    body = resp.json()
    ok, err = v.validate(body, "ranked_shops.schema.json")
    assert ok, err
    assert body["status"] == "ok"
    assert body["result_count"] == 1
    assert body["results"][0]["shop_id"] == "osm:node:1001"


def test_search_geojson_region_returns_schema_valid(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/search.geojson", params={
        "q": "algo para el dolor de cabeza", "region": "malasana", "radius": 2.0,
    })
    assert resp.status_code == 200
    body = resp.json()
    ok, err = v.validate(body, "map_geojson.schema.json")
    assert ok, err
    assert body["features"][0]["properties"]["shop_id"] == "osm:node:1001"


def test_search_region_mutually_exclusive(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    # Combine region with near
    resp = client.get("/api/search", params={
        "q": "algo", "region": "malasana", "near": "Malasaña"
    })
    assert resp.status_code == 400
    
    # Combine region with lat/lng
    resp = client.get("/api/search", params={
        "q": "algo", "region": "malasana", "lat": 40.4267, "lng": -3.7038
    })
    assert resp.status_code == 400


def test_search_region_not_found(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/search", params={
        "q": "algo", "region": "unknown_region"
    })
    assert resp.status_code == 404


def test_search_returns_schema_valid_ranked_shops(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/search", params={
        "q": "algo para el dolor de cabeza", "near": "Malasaña", "radius": 2.0,
    })
    assert resp.status_code == 200
    body = resp.json()
    ok, err = v.validate(body, "ranked_shops.schema.json")
    assert ok, err
    assert body["status"] == "ok"
    assert body["result_count"] == 1
    assert body["results"][0]["shop_id"] == "osm:node:1001"


def test_search_paginated_returns_schema_valid_search_page(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/search", params={
        "q": "algo para el dolor de cabeza", "near": "Malasaña", "radius": 2.0,
        "page": 1, "page_size": 1
    })
    assert resp.status_code == 200
    body = resp.json()
    ok, err = v.validate(body, "search_page.schema.json")
    assert ok, err
    assert body["status"] == "ok"
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["total_results"] == 1
    assert body["total_pages"] == 1
    assert body["result_count"] == 1
    assert body["results"][0]["shop_id"] == "osm:node:1001"
    assert body["results"][0]["rank"] == 1


def test_search_paginated_multiple_pages_math(tmp_path, monkeypatch):
    # Add another pharmacy and item to have 2 results total for the query
    client = _client(tmp_path, monkeypatch)
    db_path = str(tmp_path / "reachout.db")
    conn = db.connect(db_path)
    db.upsert_shop(conn, {
        "shop_id": "osm:node:1003", "osm_id": 1003, "name": "Otra Farmacia",
        "categories": ["pharmacy"], "lat": 40.4271, "lng": -3.7036,
        "address": "Calle del Pez 2", "source": "cache",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    })
    db.upsert_item(conn, {
        "shop_id": "osm:node:1003", "sku": "PHA-0001", "name": "Paracetamol 1g 40 comprimidos",
        "category": "pharmacy", "price": 4.00, "currency": "EUR", "qty": 10, "synthetic": True,
    })
    conn.commit()
    conn.close()

    # Page 1
    resp1 = client.get("/api/search", params={
        "q": "algo para el dolor de cabeza", "near": "Malasaña", "radius": 2.0,
        "page": 1, "page_size": 1
    })
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["total_results"] == 2
    assert body1["total_pages"] == 2
    assert body1["result_count"] == 1
    assert body1["results"][0]["rank"] == 1
    
    # Page 2
    resp2 = client.get("/api/search", params={
        "q": "algo para el dolor de cabeza", "near": "Malasaña", "radius": 2.0,
        "page": 2, "page_size": 1
    })
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["total_results"] == 2
    assert body2["total_pages"] == 2
    assert body2["result_count"] == 1
    assert body2["results"][0]["rank"] == 2
    
    # Verify both pages validate
    ok1, err1 = v.validate(body1, "search_page.schema.json")
    assert ok1, err1
    ok2, err2 = v.validate(body2, "search_page.schema.json")
    assert ok2, err2


def test_search_paginated_out_of_bounds(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/search", params={
        "q": "algo para el dolor de cabeza", "near": "Malasaña", "radius": 2.0,
        "page": 2, "page_size": 10
    })
    assert resp.status_code == 200
    body = resp.json()
    ok, err = v.validate(body, "search_page.schema.json")
    assert ok, err
    assert body["status"] == "ok"
    assert body["page"] == 2
    assert body["page_size"] == 10
    assert body["total_results"] == 1
    assert body["total_pages"] == 1
    assert body["result_count"] == 0
    assert body["results"] == []


def test_search_paginated_invalid_parameters(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    
    # Invalid page (<= 0)
    resp = client.get("/api/search", params={
        "q": "algo para el dolor de cabeza", "near": "Malasaña", "radius": 2.0,
        "page": 0
    })
    assert resp.status_code == 422
    
    # Invalid page_size (> 50)
    resp = client.get("/api/search", params={
        "q": "algo para el dolor de cabeza", "near": "Malasaña", "radius": 2.0,
        "page": 1, "page_size": 51
    })
    assert resp.status_code == 422


def test_search_geojson_returns_schema_valid_featurecollection(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/search.geojson", params={
        "q": "algo para el dolor de cabeza", "near": "Malasaña", "radius": 2.0,
    })
    assert resp.status_code == 200
    body = resp.json()
    ok, err = v.validate(body, "map_geojson.schema.json")
    assert ok, err
    assert body["features"][0]["properties"]["shop_id"] == "osm:node:1001"


def test_zero_result_query_returns_200_with_empty_list(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/search", params={
        "q": "cuaderno y bolígrafo", "lat": 40.4168, "lng": -3.7038, "radius": 2.0,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["result_count"] == 0
    assert body["results"] == []


def test_unparseable_query_returns_error_not_200(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/search", params={"q": "???"})
    assert resp.status_code == 422


def test_lat_without_lng_is_a_bad_request(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/search", params={"q": "leche", "lat": 40.4168})
    assert resp.status_code == 400


def test_cors_allows_browser_frontends(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_all_shops_geojson_lists_every_shop(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    # A legacy/manual row with no categories must be skipped, not crash the endpoint.
    conn = db.connect(server.DB_PATH)
    db.upsert_shop(conn, {
        "shop_id": "osm:node:1002", "osm_id": 1002, "name": "Sin Categoría",
        "categories": [], "lat": 40.4200, "lng": -3.7000,
        "address": None, "source": "cache",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    })
    conn.commit()
    conn.close()
    resp = client.get("/api/shops.geojson")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "public, max-age=3600"
    body = resp.json()
    ok, err = v.validate(body, "shops_geojson.schema.json")
    assert ok, err
    assert body["metadata"]["shop_count"] == 1
    props = body["features"][0]["properties"]
    assert props == {"shop_id": "osm:node:1001", "shop_name": "Farmacia Malasaña",
                     "category": "pharmacy"}
    assert body["features"][0]["geometry"]["coordinates"] == [-3.7035, 40.4270]


def test_regions_returns_schema_valid_response(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/regions")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "public, max-age=3600"
    body = resp.json()
    ok, err = v.validate(body, "regions_response.schema.json")
    assert ok, err
    assert body["status"] == "ok"
    assert body["region_count"] == 1
    assert len(body["regions"]) == 1
    r = body["regions"][0]
    assert r["region_id"] == "malasana"
    assert r["shop_count"] == 1

def test_scheduler_unset_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("REACHOUT_SIM", raising=False)
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["simulator_running"] is False

def test_tick_once_publishes_valid_event(tmp_path, monkeypatch):
    import asyncio

    async def _test():
        from reachout.api.event_bus import BUS
        
        # Force DB_PATH to use _seeded_db output so _sync_tick has tables.
        db_path = _seeded_db(tmp_path)
        monkeypatch.setattr(server, "DB_PATH", db_path)
        # the client fixture also needs to be called to setup app state if needed,
        # but mostly we need server.DB_PATH correctly monkeypatched.
        client = _client(tmp_path, monkeypatch)
        
        q = BUS.subscribe()
        
        # Simulate a tick. The simulator roll may not produce an event if items is empty 
        # and new items is empty, but we seeded 1 shop with 1 item.
        # Insert an event manually via simulator bypassing the random rolls
        # Or actually just monkeypatch random.random to return a guaranteed value
        import random
        monkeypatch.setattr(random, "random", lambda: 0.1) # 0.1 < 0.55 so sale
        
        # We also need to monkeypatch choice so we definitely select our item, 
        # but there's only 1 shop and 1 item seeded so random.choice is deterministic anyway.
        monkeypatch.setattr(random, "choice", lambda seq: list(seq)[0])

        # Force the event_bus module to be loaded from the same place
        # to avoid the duplicate module issue where `api.event_bus` and
        # `reachout.api.event_bus` have different BUS instances.
        import sys
        import reachout.api.event_bus as eb
        sys.modules["api.event_bus"] = eb
        
        await server.tick_once()
        try:
            event = q.get_nowait()
        except asyncio.QueueEmpty:
            pytest.fail("No event published despite fixed random roll")
        
        # an event should be published
        assert event["type"] in ("sale", "restock", "new_item")
        assert event["shop_id"] == "osm:node:1001"
        assert event["region_id"] == "malasana"
        assert "qty_now" in event
        BUS.unsubscribe(q)

    asyncio.run(_test())
