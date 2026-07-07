import json
import os

import db
import osm_ingest
import overpass
import validate

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def _elements():
    return _load_fixture("overpass_response.json")["elements"]


def test_map_categories_primary_first_multi_tag_shop():
    tag_map = overpass.load_category_tag_map()

    assert osm_ingest.map_categories({"shop": "supermarket"}, tag_map) == ["grocery"]
    assert osm_ingest.map_categories({"amenity": "pharmacy"}, tag_map) == ["pharmacy"]
    assert osm_ingest.map_categories({"amenity": "restaurant"}, tag_map) == []


def test_build_address_joins_available_parts():
    assert osm_ingest.build_address({"addr:street": "Calle Mayor", "addr:housenumber": "1"}) == "Calle Mayor 1"
    assert osm_ingest.build_address({"addr:postcode": "28012", "addr:city": "Madrid"}) == "28012 Madrid"
    assert osm_ingest.build_address({}) is None


def test_element_to_shop_record_skips_unnamed_and_uncategorized():
    tag_map = overpass.load_category_tag_map()
    elements = {e["id"]: e for e in _elements()}

    pharmacy = osm_ingest.element_to_shop_record(elements[111], "overpass_live", tag_map)
    assert pharmacy["shop_id"] == "osm:node:111"
    assert pharmacy["categories"] == ["pharmacy"]
    assert pharmacy["address"] == "Calle Mayor 1"

    way_shop = osm_ingest.element_to_shop_record(elements[222], "overpass_live", tag_map)
    assert way_shop["shop_id"] == "osm:way:222"
    assert way_shop["lat"] == 40.4230 and way_shop["lng"] == -3.7010

    assert osm_ingest.element_to_shop_record(elements[444], "overpass_live", tag_map) is None  # no matching category
    assert osm_ingest.element_to_shop_record(elements[555], "overpass_live", tag_map) is None  # no name


def test_element_to_shop_record_validates_against_schema():
    tag_map = overpass.load_category_tag_map()
    elements = {e["id"]: e for e in _elements()}

    record = osm_ingest.element_to_shop_record(elements[111], "overpass_live", tag_map)

    ok, err = validate.validate(record, "shop_record.schema.json")
    assert ok, err


def test_ingest_upserts_shops_and_seeds_only_new_ones(tmp_path, monkeypatch):
    db_path = str(tmp_path / "reachout.db")
    db.init_db(db_path)
    conn = db.connect(db_path)

    monkeypatch.setattr(overpass, "fetch_shops", lambda area_name="Madrid": _elements())

    result = osm_ingest.ingest(conn=conn, offline=False)

    assert isinstance(result, list)
    assert len(result) == 3  # pharmacy, grocery (way), hardware; two elements excluded

    shops = db.all_shops(conn)
    assert len(shops) == 3

    hardware_shop = next(s for s in shops if s["shop_id"] == "osm:node:333")
    items = db.items_for_shop(conn, hardware_shop["shop_id"], in_stock_only=False)
    assert items  # seeded because it's new

    conn.close()


def test_ingest_is_idempotent(tmp_path, monkeypatch):
    db_path = str(tmp_path / "reachout.db")
    db.init_db(db_path)
    conn = db.connect(db_path)

    monkeypatch.setattr(overpass, "fetch_shops", lambda area_name="Madrid": _elements())

    osm_ingest.ingest(conn=conn, offline=False)
    shops_after_first = db.all_shops(conn)
    items_after_first = db.items_for_shop(conn, "osm:node:333", in_stock_only=False)

    osm_ingest.ingest(conn=conn, offline=False)
    shops_after_second = db.all_shops(conn)
    items_after_second = db.items_for_shop(conn, "osm:node:333", in_stock_only=False)

    assert len(shops_after_first) == len(shops_after_second)
    assert [dict(i) for i in items_after_first] == [dict(i) for i in items_after_second]

    conn.close()


def test_ingest_falls_back_to_cache_when_overpass_fails(tmp_path, monkeypatch):
    db_path = str(tmp_path / "reachout.db")
    db.init_db(db_path)
    conn = db.connect(db_path)

    cache_path = str(tmp_path / "madrid_shops.json")
    monkeypatch.setattr(osm_ingest, "CACHE_PATH", cache_path)

    cached_shop = {
        "shop_id": "osm:node:999",
        "osm_id": 999,
        "name": "Farmacia Cache",
        "categories": ["pharmacy"],
        "lat": 40.4168,
        "lng": -3.7038,
        "address": None,
        "source": "cache",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump([cached_shop], f)

    def raise_overpass_error(area_name="Madrid"):
        raise overpass.OverpassError("network down")

    monkeypatch.setattr(overpass, "fetch_shops", raise_overpass_error)

    result = osm_ingest.ingest(conn=conn, offline=False)

    assert result == [cached_shop]
    shops = db.all_shops(conn)
    assert shops[0]["shop_id"] == "osm:node:999"

    conn.close()


def test_ingest_returns_no_shop_source_error_when_both_unavailable(tmp_path, monkeypatch):
    db_path = str(tmp_path / "reachout.db")
    db.init_db(db_path)
    conn = db.connect(db_path)

    monkeypatch.setattr(osm_ingest, "CACHE_PATH", str(tmp_path / "missing_cache.json"))

    def raise_overpass_error(area_name="Madrid"):
        raise overpass.OverpassError("network down")

    monkeypatch.setattr(overpass, "fetch_shops", raise_overpass_error)

    result = osm_ingest.ingest(conn=conn, offline=False)

    assert result == {"status": "error", "error": {"code": "no_shop_source", "detail": result["error"]["detail"]}}
    assert db.all_shops(conn) == []

    conn.close()


def test_ingest_offline_never_calls_overpass(tmp_path, monkeypatch):
    db_path = str(tmp_path / "reachout.db")
    db.init_db(db_path)
    conn = db.connect(db_path)

    cache_path = str(tmp_path / "madrid_shops.json")
    monkeypatch.setattr(osm_ingest, "CACHE_PATH", cache_path)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump([], f)

    def boom(area_name="Madrid"):
        raise AssertionError("overpass.fetch_shops must not be called when offline")

    monkeypatch.setattr(overpass, "fetch_shops", boom)

    result = osm_ingest.ingest(conn=conn, offline=True)

    assert result == []

    conn.close()
