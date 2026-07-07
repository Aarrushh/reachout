import json
import os

import db
import geo
import nominatim
import osm_ingest
import overpass
import validate as v
from geo_resolve import resolve


def _intent(location_text=None, category_hints=None, raw_query="cargador usb c"):
    return {
        "status": "ok",
        "raw_query": raw_query,
        "keywords": ["cargador", "usb c", "charger"],
        "category_hints": category_hints if category_hints is not None else [],
        "location_text": location_text,
    }


def _db_shop(shop_id, name, categories, lat, lng, address="Calle Mayor 1"):
    return {
        "shop_id": shop_id,
        "osm_id": int(shop_id.split(":")[-1]),
        "name": name,
        "categories": categories,
        "lat": lat,
        "lng": lng,
        "address": address,
        "source": "cache",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    }


def _init_db(tmp_path, shops):
    path = str(tmp_path / "reachout.db")
    db.init_db(path)
    conn = db.connect(path)
    for shop in shops:
        db.upsert_shop(conn, shop)
    conn.commit()
    conn.close()
    return path


def _assert_valid(output):
    ok, err = v.validate(output, "geo_shops.schema.json")
    assert ok, err


def test_t1_explicit_coordinates_happy_path(tmp_path):
    center_lat, center_lng, radius_km = 40.4260, -3.7025, 1.0

    inside = [
        _db_shop("osm:node:1", "Electro Uno", ["electronics"], 40.4262, -3.7024),
        _db_shop("osm:node:2", "Electro Dos", ["electronics"], 40.4270, -3.7030),
        _db_shop("osm:node:3", "Electro Tres", ["electronics"], 40.4200, -3.7000),
    ]
    outside = _db_shop("osm:node:4", "Electro Lejos", ["electronics"], 40.4700, -3.6500)
    db_path = _init_db(tmp_path, inside + [outside])

    intent = _intent(category_hints=["electronics"])

    result = resolve(intent, lat=center_lat, lng=center_lng, radius_km=radius_km, db_path=db_path, offline=True)

    _assert_valid(result)
    assert result["status"] == "ok"
    assert result["query_location"]["resolved_from"] == "coordinates"
    assert result["query_location"]["lat"] == center_lat
    assert result["query_location"]["lng"] == center_lng
    assert result["shop_count"] == 3
    shop_ids = [s["shop_id"] for s in result["shops"]]
    assert "osm:node:4" not in shop_ids
    assert all(s["distance_type"] == "haversine" for s in result["shops"])

    expected_order = sorted(
        [s["shop_id"] for s in inside],
        key=lambda sid: geo.haversine_km(
            center_lat, center_lng,
            *next((s["lat"], s["lng"]) for s in inside if s["shop_id"] == sid),
        ),
    )
    assert shop_ids == expected_order
    distances = [s["distance_km"] for s in result["shops"]]
    assert distances == sorted(distances)


def test_t2_neighbourhood_name_via_geocoding(tmp_path, monkeypatch):
    db_path = _init_db(tmp_path, [])
    monkeypatch.setattr(
        nominatim, "geocode",
        lambda place_name, offline=None: {"lat": 40.4089, "lng": -3.7038, "source": "gazetteer"},
    )

    intent = _intent(location_text="Lavapiés")

    result = resolve(intent, radius_km=0.8, db_path=db_path, offline=True)

    _assert_valid(result)
    assert result["status"] == "ok"
    assert result["query_location"]["lat"] == 40.4089
    assert result["query_location"]["lng"] == -3.7038
    assert result["query_location"]["resolved_from"] == "gazetteer"
    assert result["query_location"]["location_text"] == "Lavapiés"
    assert result["shop_count"] == 0
    assert result["shops"] == []


def test_t3_overpass_down_falls_back_to_cache(tmp_path, monkeypatch):
    db_path = _init_db(tmp_path, [])
    conn = db.connect(db_path)
    conn.close()

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

    intent = _intent()
    result = resolve(intent, lat=40.4168, lng=-3.7038, radius_km=2.0, refresh=True, db_path=db_path, offline=True)

    _assert_valid(result)
    assert result["status"] == "ok"
    assert result["shop_source"] == "cache"
    shop_ids = [s["shop_id"] for s in result["shops"]]
    assert shop_ids == ["osm:node:999"]


def test_t3_variant_cache_missing_yields_no_shop_source_error(tmp_path, monkeypatch):
    db_path = _init_db(tmp_path, [])
    monkeypatch.setattr(osm_ingest, "CACHE_PATH", str(tmp_path / "missing_cache.json"))

    def raise_overpass_error(area_name="Madrid"):
        raise overpass.OverpassError("network down")

    monkeypatch.setattr(overpass, "fetch_shops", raise_overpass_error)

    intent = _intent()
    result = resolve(intent, lat=40.4168, lng=-3.7038, radius_km=2.0, refresh=True, db_path=db_path, offline=True)

    _assert_valid(result)
    assert result["status"] == "error"
    assert result["error"]["code"] == "no_shop_source"
    assert "shops" not in result


def test_unresolvable_named_place_is_incomplete_not_default_center(tmp_path, monkeypatch):
    db_path = _init_db(tmp_path, [])
    monkeypatch.setattr(nominatim, "geocode", lambda place_name, offline=None: None)

    intent = _intent(location_text="Nonexistentistan")
    result = resolve(intent, radius_km=1.0, db_path=db_path, offline=True)

    _assert_valid(result)
    assert result == {"status": "incomplete", "missing_fields": ["query_location"]}


def test_no_location_at_all_uses_default_center(tmp_path):
    db_path = _init_db(tmp_path, [])
    intent = _intent(location_text=None)

    result = resolve(intent, radius_km=1.0, db_path=db_path, offline=True)

    _assert_valid(result)
    assert result["status"] == "ok"
    assert result["query_location"]["resolved_from"] == "default_center"
    assert result["query_location"]["lat"] == 40.4168
    assert result["query_location"]["lng"] == -3.7038


def test_category_hints_intersection_filters_shops(tmp_path):
    shops = [
        _db_shop("osm:node:10", "Ferreteria", ["hardware"], 40.4168, -3.7038),
        _db_shop("osm:node:20", "Farmacia", ["pharmacy"], 40.4170, -3.7040),
    ]
    db_path = _init_db(tmp_path, shops)
    intent = _intent(category_hints=["pharmacy"])

    result = resolve(intent, lat=40.4168, lng=-3.7038, radius_km=2.0, db_path=db_path, offline=True)

    _assert_valid(result)
    shop_ids = [s["shop_id"] for s in result["shops"]]
    assert shop_ids == ["osm:node:20"]


def test_zero_shops_in_radius_is_ok_not_error(tmp_path):
    db_path = _init_db(tmp_path, [])
    intent = _intent()

    result = resolve(intent, lat=40.4168, lng=-3.7038, radius_km=1.0, db_path=db_path, offline=True)

    _assert_valid(result)
    assert result["status"] == "ok"
    assert result["shop_count"] == 0
    assert result["shops"] == []


def test_multi_category_shop_keeps_full_categories_array(tmp_path):
    shops = [_db_shop("osm:node:30", "Super Mercado", ["grocery", "pharmacy"], 40.4168, -3.7038)]
    db_path = _init_db(tmp_path, shops)
    intent = _intent(category_hints=["pharmacy"])

    result = resolve(intent, lat=40.4168, lng=-3.7038, radius_km=2.0, db_path=db_path, offline=True)

    _assert_valid(result)
    assert result["shops"][0]["categories"] == ["grocery", "pharmacy"]


def test_near_param_overrides_intent_location_text(tmp_path, monkeypatch):
    db_path = _init_db(tmp_path, [])
    calls = []

    def fake_geocode(place_name, offline=None):
        calls.append(place_name)
        return {"lat": 40.4267, "lng": -3.7038, "source": "gazetteer"}

    monkeypatch.setattr(nominatim, "geocode", fake_geocode)

    intent = _intent(location_text="Lavapiés")
    result = resolve(intent, near="Malasaña", radius_km=1.0, db_path=db_path, offline=True)

    _assert_valid(result)
    assert calls == ["Malasaña"]
    assert result["query_location"]["location_text"] == "Malasaña"
