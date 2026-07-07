import json
import os

import db
import inventory_seeder
import validate

CATALOG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "sku_catalog.json")
)


def _shop(shop_id="osm:node:555", categories=None):
    return {
        "shop_id": shop_id,
        "osm_id": 555,
        "name": "Ferretería Lavapiés",
        "categories": categories or ["hardware"],
        "lat": 40.4090,
        "lng": -3.7018,
        "address": None,
        "source": "overpass_live",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    }


def _seed_fresh(tmp_path, name, shop):
    path = str(tmp_path / name)
    db.init_db(path)
    conn = db.connect(path)
    db.upsert_shop(conn, shop)
    rows = inventory_seeder.seed_shop(conn, shop)
    conn.commit()
    conn.close()
    return rows


def _without_timestamps(rows):
    return [{k: v for k, v in row.items() if k != "updated_at"} for row in rows]


def test_seed_shop_is_deterministic_per_shop_id(tmp_path):
    shop = _shop()
    rows_a = _seed_fresh(tmp_path, "a.db", shop)
    rows_b = _seed_fresh(tmp_path, "b.db", shop)

    assert rows_a
    assert _without_timestamps(rows_a) == _without_timestamps(rows_b)


def test_seed_shop_different_shop_ids_can_differ(tmp_path):
    rows_a = _seed_fresh(tmp_path, "a.db", _shop(shop_id="osm:node:1"))
    rows_b = _seed_fresh(tmp_path, "b.db", _shop(shop_id="osm:node:2"))

    assert _without_timestamps(rows_a) != _without_timestamps(rows_b)


def test_seed_shop_only_uses_shops_primary_category(tmp_path):
    with open(CATALOG_PATH, encoding="utf-8") as f:
        catalog = json.load(f)
    hardware_skus = {entry["sku"] for entry in catalog["hardware"]}

    rows = _seed_fresh(tmp_path, "a.db", _shop(categories=["hardware", "electronics"]))

    assert rows
    for row in rows:
        assert row["sku"] in hardware_skus
        assert row["category"] == "hardware"


def test_seed_shop_rows_stay_within_documented_ranges(tmp_path):
    with open(CATALOG_PATH, encoding="utf-8") as f:
        catalog = json.load(f)
    base_prices = {entry["sku"]: entry["base_price_eur"] for entry in catalog["hardware"]}

    rows = _seed_fresh(tmp_path, "a.db", _shop())

    assert rows
    for row in rows:
        assert row["currency"] == "EUR"
        assert row["synthetic"] is True
        assert 0 <= row["qty"] <= 12
        base = base_prices[row["sku"]]
        assert base * 0.85 - 0.01 <= row["price"] <= base * 1.15 + 0.01
        assert round(row["price"], 2) == row["price"]


def test_seed_shop_rows_validate_against_inventory_record_schema(tmp_path):
    rows = _seed_fresh(tmp_path, "a.db", _shop())

    assert rows
    for row in rows:
        ok, err = validate.validate(row, "inventory_record.schema.json")
        assert ok, err
