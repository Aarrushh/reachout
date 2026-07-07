import db
import validate as v
from fastapi.testclient import TestClient

import server


def _seeded_db(tmp_path):
    """One pharmacy near Malasaña, one electronics shop near Puerta del Sol."""
    db_path = str(tmp_path / "reachout.db")
    db.init_db(db_path)
    conn = db.connect(db_path)
    db.upsert_shop(conn, {
        "shop_id": "osm:node:1001", "osm_id": 1001, "name": "Farmacia Malasaña",
        "categories": ["pharmacy"], "lat": 40.4270, "lng": -3.7035,
        "address": "Calle del Pez 1", "source": "cache",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    })
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


def test_health():
    client = TestClient(server.app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


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
    assert resp.headers.get("access-control-allow-origin") == "*"


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
