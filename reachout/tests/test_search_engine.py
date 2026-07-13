import json
import os

import db
import validate as v
from search_engine import search


def _intent(keywords=None, category_hints=None, raw_query="paracetamol"):
    return {
        "status": "ok",
        "raw_query": raw_query,
        "keywords": keywords if keywords is not None else ["paracetamol"],
        "category_hints": category_hints if category_hints is not None else [],
        "location_text": None,
    }


def _query_location():
    return {"lat": 40.4200, "lng": -3.7050, "resolved_from": "coordinates", "location_text": None}


def _geo_shops(shops, radius_km=2.0):
    return {
        "status": "ok",
        "query_location": _query_location(),
        "radius_km": radius_km,
        "shop_source": "cache",
        "shop_count": len(shops),
        "shops": shops,
    }


def _geo_shop(shop_id, name, categories, lat, lng, distance_km, address="Calle Mayor 1"):
    return {
        "shop_id": shop_id,
        "name": name,
        "categories": categories,
        "lat": lat,
        "lng": lng,
        "address": address,
        "distance_km": distance_km,
        "distance_type": "haversine",
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


def _item(shop_id, sku, name, category, price, qty, rating=None, review_count=None, source=None):
    item = {
        "shop_id": shop_id,
        "sku": sku,
        "name": name,
        "category": category,
        "price": price,
        "currency": "EUR",
        "qty": qty,
        "synthetic": True,
    }
    if rating is not None:
        item["rating"] = rating
    if review_count is not None:
        item["review_count"] = review_count
    if source is not None:
        item["source"] = source
    return item


def _init_db(tmp_path, shops, items):
    path = str(tmp_path / "reachout.db")
    db.init_db(path)
    conn = db.connect(path)
    for shop in shops:
        db.upsert_shop(conn, shop)
    for item in items:
        db.upsert_item(conn, item)
    conn.commit()
    conn.close()
    return path


def _assert_valid(output):
    ok, err = v.validate(output, "stock_matches.schema.json")
    assert ok, err


def test_t1_keyword_match_across_two_pharmacies(tmp_path):
    shops = [
        _db_shop("osm:node:111", "Farmacia Sol", ["pharmacy"], 40.4165, -3.7038),
        _db_shop("osm:node:222", "Farmacia Lavapies", ["pharmacy"], 40.4090, -3.7020),
        _db_shop("osm:node:333", "Ferreteria Central", ["hardware"], 40.4100, -3.7100),
    ]
    items = [
        _item("osm:node:111", "PHA-0001", "Paracetamol", "pharmacy", 3.95, 5),
        _item("osm:node:222", "PHA-0001", "Paracetamol", "pharmacy", 3.50, 12),
        _item("osm:node:333", "HRD-0001", "Martillo", "hardware", 9.99, 20),
    ]
    db_path = _init_db(tmp_path, shops, items)
    notif_dir = tmp_path / "notifications"

    geo_shops = _geo_shops([
        _geo_shop("osm:node:111", "Farmacia Sol", ["pharmacy"], 40.4165, -3.7038, 0.4),
        _geo_shop("osm:node:222", "Farmacia Lavapies", ["pharmacy"], 40.4090, -3.7020, 1.1),
        _geo_shop("osm:node:333", "Ferreteria Central", ["hardware"], 40.4100, -3.7100, 0.6),
    ])
    intent = _intent(keywords=["paracetamol"])

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(notif_dir))

    _assert_valid(result)
    assert result["status"] == "ok"
    assert result["match_count"] == 2
    shop_ids = [m["shop_id"] for m in result["matches"]]
    assert shop_ids == ["osm:node:111", "osm:node:222"]
    for m in result["matches"]:
        assert m["categories"] == ["pharmacy"]
        assert all(i["qty"] >= 1 and i["currency"] == "EUR" for i in m["items"])
    assert result["pinged_shop_ids"] == shop_ids

    for shop_id in shop_ids:
        inbox = notif_dir / f"{shop_id.replace(':', '_')}.jsonl"
        assert inbox.exists()
        lines = inbox.read_text().strip().splitlines()
        assert len(lines) == 1

    assert not (notif_dir / "osm_node_333.jsonl").exists()


def test_t2_zero_candidates_yields_ok_zero_matches_no_pings(tmp_path):
    db_path = _init_db(tmp_path, [], [])
    notif_dir = tmp_path / "notifications"

    geo_shops = _geo_shops([])
    intent = _intent()

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(notif_dir))

    _assert_valid(result)
    assert result["status"] == "ok"
    assert result["match_count"] == 0
    assert result["matches"] == []
    assert result["pinged_shop_ids"] == []
    assert not notif_dir.exists() or not list(notif_dir.iterdir())


def test_t3_secondary_category_match(tmp_path):
    shops = [_db_shop("osm:node:444", "Super Mercado", ["grocery", "pharmacy"], 40.4150, -3.7000)]
    items = [_item("osm:node:444", "PHA-0002", "Paracetamol", "pharmacy", 2.99, 3)]
    db_path = _init_db(tmp_path, shops, items)
    notif_dir = tmp_path / "notifications"

    geo_shops = _geo_shops([
        _geo_shop("osm:node:444", "Super Mercado", ["grocery", "pharmacy"], 40.4150, -3.7000, 0.3),
    ])
    intent = _intent(keywords=["paracetamol"], category_hints=["pharmacy"])

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(notif_dir))

    _assert_valid(result)
    assert result["match_count"] == 1
    match = result["matches"][0]
    assert match["shop_id"] == "osm:node:444"
    assert match["categories"] == ["grocery", "pharmacy"]


def test_shop_in_db_but_absent_from_geo_shops_never_appears(tmp_path):
    shops = [
        _db_shop("osm:node:111", "Farmacia Sol", ["pharmacy"], 40.4165, -3.7038),
        _db_shop("osm:node:999", "Farmacia Fantasma", ["pharmacy"], 40.4200, -3.7050),
    ]
    items = [
        _item("osm:node:111", "PHA-0001", "Paracetamol", "pharmacy", 3.95, 5),
        _item("osm:node:999", "PHA-0001", "Paracetamol", "pharmacy", 1.00, 99),
    ]
    db_path = _init_db(tmp_path, shops, items)
    notif_dir = tmp_path / "notifications"

    geo_shops = _geo_shops([
        _geo_shop("osm:node:111", "Farmacia Sol", ["pharmacy"], 40.4165, -3.7038, 0.4),
    ])
    intent = _intent(keywords=["paracetamol"])

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(notif_dir))

    shop_ids = [m["shop_id"] for m in result["matches"]]
    assert shop_ids == ["osm:node:111"]
    assert "osm:node:999" not in shop_ids
    assert not (notif_dir / "osm_node_999.jsonl").exists()


def test_category_hint_excludes_shop_without_matching_category(tmp_path):
    shops = [_db_shop("osm:node:555", "Papeleria Norte", ["stationery"], 40.4180, -3.7010)]
    items = [_item("osm:node:555", "STA-0001", "Paracetamol-branded pen", "stationery", 1.20, 4)]
    db_path = _init_db(tmp_path, shops, items)

    geo_shops = _geo_shops([
        _geo_shop("osm:node:555", "Papeleria Norte", ["stationery"], 40.4180, -3.7010, 0.2),
    ])
    intent = _intent(keywords=["paracetamol"], category_hints=["pharmacy"])

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(tmp_path / "notifications"))

    assert result["match_count"] == 0
    assert result["matches"] == []


def test_zero_qty_item_never_counted_as_stock(tmp_path):
    shops = [_db_shop("osm:node:111", "Farmacia Sol", ["pharmacy"], 40.4165, -3.7038)]
    items = [_item("osm:node:111", "PHA-0001", "Paracetamol", "pharmacy", 3.95, 0)]
    db_path = _init_db(tmp_path, shops, items)

    geo_shops = _geo_shops([
        _geo_shop("osm:node:111", "Farmacia Sol", ["pharmacy"], 40.4165, -3.7038, 0.4),
    ])
    intent = _intent(keywords=["paracetamol"])

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(tmp_path / "notifications"))

    assert result["match_count"] == 0


def test_ranking_nearest_then_most_stock_then_cheapest(tmp_path):
    shops = [
        _db_shop("osm:node:1", "A", ["pharmacy"], 40.41, -3.70),
        _db_shop("osm:node:2", "B", ["pharmacy"], 40.42, -3.71),
        _db_shop("osm:node:3", "C", ["pharmacy"], 40.43, -3.72),
    ]
    items = [
        # A and B are equidistant (0.5) -- B has more total matching stock.
        _item("osm:node:1", "PHA-0001", "Paracetamol", "pharmacy", 3.00, 2),
        _item("osm:node:2", "PHA-0001", "Paracetamol", "pharmacy", 3.00, 10),
        # C is farther away.
        _item("osm:node:3", "PHA-0001", "Paracetamol", "pharmacy", 1.00, 50),
    ]
    db_path = _init_db(tmp_path, shops, items)

    geo_shops = _geo_shops([
        _geo_shop("osm:node:1", "A", ["pharmacy"], 40.41, -3.70, 0.5),
        _geo_shop("osm:node:2", "B", ["pharmacy"], 40.42, -3.71, 0.5),
        _geo_shop("osm:node:3", "C", ["pharmacy"], 40.43, -3.72, 1.5),
    ])
    intent = _intent(keywords=["paracetamol"])

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(tmp_path / "notifications"), do_ping=False)

    shop_ids = [m["shop_id"] for m in result["matches"]]
    assert shop_ids == ["osm:node:2", "osm:node:1", "osm:node:3"]


def test_intent_missing_keywords_yields_incomplete(tmp_path):
    db_path = _init_db(tmp_path, [], [])
    geo_shops = _geo_shops([])
    intent = {"status": "incomplete", "missing_fields": ["keywords"]}

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(tmp_path / "notifications"))

    _assert_valid(result)
    assert result == {"status": "incomplete", "missing_fields": ["keywords"]}


def test_geo_shops_incomplete_is_relayed(tmp_path):
    db_path = _init_db(tmp_path, [], [])
    geo_shops = {"status": "incomplete", "missing_fields": ["location_text"]}
    intent = _intent()

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(tmp_path / "notifications"))

    _assert_valid(result)
    assert result == {"status": "incomplete", "missing_fields": ["location_text"]}


def test_geo_shops_error_is_relayed(tmp_path):
    db_path = _init_db(tmp_path, [], [])
    geo_shops = {"status": "error", "error": {"code": "no_shop_source", "detail": "boom"}}
    intent = _intent()

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(tmp_path / "notifications"))

    assert result["status"] == "error"
    assert result["error"]["detail"] == "boom"


def test_no_ping_when_do_ping_false(tmp_path):
    shops = [_db_shop("osm:node:111", "Farmacia Sol", ["pharmacy"], 40.4165, -3.7038)]
    items = [_item("osm:node:111", "PHA-0001", "Paracetamol", "pharmacy", 3.95, 5)]
    db_path = _init_db(tmp_path, shops, items)
    notif_dir = tmp_path / "notifications"

    geo_shops = _geo_shops([
        _geo_shop("osm:node:111", "Farmacia Sol", ["pharmacy"], 40.4165, -3.7038, 0.4),
    ])
    intent = _intent(keywords=["paracetamol"])

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(notif_dir), do_ping=False)

    assert result["pinged_shop_ids"] == ["osm:node:111"]
    assert not notif_dir.exists()


def test_dummyjson_item_surfaces_ratings(tmp_path):
    shops = [
        _db_shop("osm:node:1", "Farmacia Dummy", ["pharmacy"], 40.41, -3.70),
        _db_shop("osm:node:2", "Farmacia Template", ["pharmacy"], 40.42, -3.71),
    ]
    items = [
        _item("osm:node:1", "PHA-0001", "Paracetamol", "pharmacy", 3.00, 2, rating=4.5, review_count=100, source="dummyjson"),
        _item("osm:node:2", "PHA-0001", "Paracetamol", "pharmacy", 3.00, 10, source="template"),
    ]
    db_path = _init_db(tmp_path, shops, items)

    geo_shops = _geo_shops([
        _geo_shop("osm:node:1", "Farmacia Dummy", ["pharmacy"], 40.41, -3.70, 0.5),
        _geo_shop("osm:node:2", "Farmacia Template", ["pharmacy"], 40.42, -3.71, 1.0),
    ])
    intent = _intent(keywords=["paracetamol"])

    result = search(intent, geo_shops, db_path=db_path, notif_dir=str(tmp_path / "notifications"), do_ping=False)

    _assert_valid(result)
    assert result["match_count"] == 2
    
    # Check dummyjson shop (rank 1 because it is nearer)
    dummy_match = result["matches"][0]
    assert dummy_match["shop_id"] == "osm:node:1"
    assert dummy_match["items"][0]["rating"] == 4.5
    assert dummy_match["items"][0]["review_count"] == 100
    assert dummy_match["items"][0]["source"] == "dummyjson"
    
    # Check template shop (rank 2)
    template_match = result["matches"][1]
    assert template_match["shop_id"] == "osm:node:2"
    assert "rating" not in template_match["items"][0]
    assert "review_count" not in template_match["items"][0]
    assert template_match["items"][0]["source"] == "template"
