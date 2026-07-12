import re

import db


def _shop(shop_id="osm:node:123", categories=None, address="Calle Mayor 1"):
    return {
        "shop_id": shop_id,
        "osm_id": 123,
        "name": "Farmacia Central",
        "categories": categories or ["pharmacy"],
        "lat": 40.4168,
        "lng": -3.7038,
        "address": address,
        "source": "overpass_live",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    }


def _item(shop_id="osm:node:123", sku="PHA-0001", qty=5):
    return {
        "shop_id": shop_id,
        "sku": sku,
        "name": "Paracetamol 1g 40 comprimidos",
        "category": "pharmacy",
        "price": 3.95,
        "currency": "EUR",
        "qty": qty,
        "synthetic": True,
        "source": "template",
    }


def test_upsert_shop_and_all_shops_roundtrip(tmp_path):
    path = str(tmp_path / "reachout.db")
    db.init_db(path)
    conn = db.connect(path)

    db.upsert_shop(conn, _shop())
    conn.commit()

    shops = db.all_shops(conn)
    conn.close()

    assert len(shops) == 1
    shop = shops[0]
    assert shop["shop_id"] == "osm:node:123"
    assert shop["categories"] == ["pharmacy"]
    assert shop["address"] == "Calle Mayor 1"


def test_upsert_shop_allows_null_address(tmp_path):
    path = str(tmp_path / "reachout.db")
    db.init_db(path)
    conn = db.connect(path)

    db.upsert_shop(conn, _shop(address=None))
    conn.commit()

    shops = db.all_shops(conn)
    conn.close()

    assert shops[0]["address"] is None


def test_upsert_shop_stores_multiple_categories_in_order(tmp_path):
    path = str(tmp_path / "reachout.db")
    db.init_db(path)
    conn = db.connect(path)

    db.upsert_shop(conn, _shop(categories=["pharmacy", "grocery"]))
    conn.commit()

    shops = db.all_shops(conn)
    conn.close()

    assert shops[0]["categories"] == ["pharmacy", "grocery"]


def test_upsert_item_and_items_for_shop_roundtrip(tmp_path):
    path = str(tmp_path / "reachout.db")
    db.init_db(path)
    conn = db.connect(path)

    db.upsert_shop(conn, _shop())
    db.upsert_item(conn, _item())
    conn.commit()

    items = db.items_for_shop(conn, "osm:node:123")
    conn.close()

    assert len(items) == 1
    item = items[0]
    assert item["currency"] == "EUR"
    assert item["synthetic"] is True
    assert item["source"] == "template"
    assert item["rating"] is None
    assert item["review_count"] is None
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", item["updated_at"])


def test_upsert_item_with_optional_fields(tmp_path):
    path = str(tmp_path / "reachout.db")
    db.init_db(path)
    conn = db.connect(path)

    db.upsert_shop(conn, _shop())
    item_data = _item()
    item_data["source"] = "dummyjson"
    item_data["rating"] = 4.5
    item_data["review_count"] = 120
    db.upsert_item(conn, item_data)
    conn.commit()

    items = db.items_for_shop(conn, "osm:node:123")
    conn.close()

    assert len(items) == 1
    item = items[0]
    assert item["source"] == "dummyjson"
    assert item["rating"] == 4.5
    assert item["review_count"] == 120


def test_items_for_shop_in_stock_only_filters_zero_qty(tmp_path):
    path = str(tmp_path / "reachout.db")
    db.init_db(path)
    conn = db.connect(path)

    db.upsert_shop(conn, _shop())
    db.upsert_item(conn, _item(sku="PHA-0001", qty=5))
    db.upsert_item(conn, _item(sku="PHA-0002", qty=0))
    conn.commit()

    in_stock = db.items_for_shop(conn, "osm:node:123", in_stock_only=True)
    everything = db.items_for_shop(conn, "osm:node:123", in_stock_only=False)
    conn.close()

    assert [i["sku"] for i in in_stock] == ["PHA-0001"]
    assert len(everything) == 2


def test_adjust_qty_decreases_and_floors_at_zero(tmp_path):
    path = str(tmp_path / "reachout.db")
    db.init_db(path)
    conn = db.connect(path)

    db.upsert_shop(conn, _shop())
    db.upsert_item(conn, _item(qty=3))
    conn.commit()

    new_qty = db.adjust_qty(conn, "osm:node:123", "PHA-0001", -10)
    conn.close()

    assert new_qty == 0


def test_adjust_qty_unknown_sku_returns_none(tmp_path):
    path = str(tmp_path / "reachout.db")
    db.init_db(path)
    conn = db.connect(path)

    db.upsert_shop(conn, _shop())
    conn.commit()

    result = db.adjust_qty(conn, "osm:node:123", "NOPE-0000", -1)
    conn.close()

    assert result is None
