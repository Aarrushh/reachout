import json

import db
import inventory_simulator


def _shop(shop_id="osm:node:9", categories=None):
    return {
        "shop_id": shop_id,
        "osm_id": 9,
        "name": "Ferretería Lavapiés",
        "categories": categories or ["hardware"],
        "lat": 40.4090,
        "lng": -3.7018,
        "address": None,
        "source": "overpass_live",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    }


def _seeded_conn(tmp_path, name="sim.db"):
    path = str(tmp_path / name)
    db.init_db(path)
    conn = db.connect(path)
    shop = _shop()
    db.upsert_shop(conn, shop)
    db.upsert_item(conn, {
        "shop_id": shop["shop_id"], "sku": "HRD-0001", "name": "Destornillador plano 5.5mm",
        "category": "hardware", "price": 4.50, "currency": "EUR", "qty": 5, "synthetic": True,
    })
    conn.commit()
    return conn


def test_tick_sell_decrements_qty_and_logs_sale_event(tmp_path, monkeypatch):
    conn = _seeded_conn(tmp_path)
    events_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(inventory_simulator, "EVENTS_PATH", str(events_path))
    monkeypatch.setattr(inventory_simulator.random, "random", lambda: 0.1)
    monkeypatch.setattr(inventory_simulator.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(inventory_simulator.random, "randint", lambda a, b: 2)

    returned_event = inventory_simulator._tick(conn)
    conn.commit()

    items = db.items_for_shop(conn, "osm:node:9", in_stock_only=False)
    conn.close()
    assert items[0]["qty"] == 3

    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(lines[0])
    assert event["type"] == "sale"
    assert event["sku"] == "HRD-0001"
    assert event["qty_now"] == 3
    assert returned_event == event


def test_tick_restock_increments_qty_and_logs_restock_event(tmp_path, monkeypatch):
    conn = _seeded_conn(tmp_path)
    events_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(inventory_simulator, "EVENTS_PATH", str(events_path))
    monkeypatch.setattr(inventory_simulator.random, "random", lambda: 0.7)
    monkeypatch.setattr(inventory_simulator.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(inventory_simulator.random, "randint", lambda a, b: 15)

    returned_event = inventory_simulator._tick(conn)
    conn.commit()

    items = db.items_for_shop(conn, "osm:node:9", in_stock_only=False)
    conn.close()
    assert items[0]["qty"] == 20

    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(lines[0])
    assert event["type"] == "restock"
    assert event["sku"] == "HRD-0001"
    assert event["qty_now"] == 20
    assert returned_event == event


def test_tick_new_item_uses_sku_catalog_with_eur_and_synthetic(tmp_path, monkeypatch):
    conn = _seeded_conn(tmp_path)
    events_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(inventory_simulator, "EVENTS_PATH", str(events_path))
    monkeypatch.setattr(inventory_simulator.random, "random", lambda: 0.9)
    # Return the last item from the choices. For hardware, "HRD-1171" has dummyjson source and ratings.
    monkeypatch.setattr(inventory_simulator.random, "choice", lambda seq: seq[-1])
    monkeypatch.setattr(inventory_simulator.random, "randint", lambda a, b: 10)

    returned_event = inventory_simulator._tick(conn)
    conn.commit()

    items = {i["sku"]: i for i in db.items_for_shop(conn, "osm:node:9", in_stock_only=False)}
    conn.close()

    new_items = [i for sku, i in items.items() if sku != "HRD-0001"]
    assert len(new_items) == 1
    new_item = new_items[0]
    assert new_item["category"] == "hardware"
    assert new_item["currency"] == "EUR"
    assert new_item["synthetic"] is True
    assert new_item["qty"] == 10
    assert new_item["source"] == "dummyjson"
    assert new_item["rating"] == 3.62
    assert new_item["review_count"] == 3

    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(lines[0])
    assert event["type"] == "new_item"
    assert event["source"] == "dummyjson"
    assert returned_event == event


def test_run_simulator_runs_offline_against_new_schema(tmp_path, monkeypatch):
    path = str(tmp_path / "sim.db")
    db.init_db(path)
    conn = db.connect(path)
    db.upsert_shop(conn, _shop())
    conn.commit()
    conn.close()

    events_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(inventory_simulator, "EVENTS_PATH", str(events_path))

    inventory_simulator.run_simulator(interval=0.0, seconds=0.05, db_path=path)
