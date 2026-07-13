import pytest
import sqlite3
import json
import os

from scripts import db, inventory_seeder, reseed_inventory


def test_reseed_inventory(tmp_path):
    """
    Test that reseed wipes inventory and reseeds every shop.
    After reseed, some items have source='dummyjson' in each mapped category
    and stationery has only 'template'.
    """
    db_path = str(tmp_path / "reachout.db")
    db.init_db(db_path)
    
    # Insert some dummy shops
    shop1 = {
        "shop_id": "osm:node:1",
        "osm_id": 1,
        "name": "Pharmacy 1",
        "categories": ["pharmacy"],
        "lat": 40.0,
        "lng": -3.0,
        "source": "overpass",
        "fetched_at": db.now_iso(),
    }
    shop2 = {
        "shop_id": "osm:node:2",
        "osm_id": 2,
        "name": "Grocery 1",
        "categories": ["grocery"],
        "lat": 40.0,
        "lng": -3.0,
        "source": "overpass",
        "fetched_at": db.now_iso(),
    }
    shop3 = {
        "shop_id": "osm:node:3",
        "osm_id": 3,
        "name": "Hardware 1",
        "categories": ["hardware"],
        "lat": 40.0,
        "lng": -3.0,
        "source": "overpass",
        "fetched_at": db.now_iso(),
    }
    shop4 = {
        "shop_id": "osm:node:4",
        "osm_id": 4,
        "name": "Electronics 1",
        "categories": ["electronics"],
        "lat": 40.0,
        "lng": -3.0,
        "source": "overpass",
        "fetched_at": db.now_iso(),
    }
    shop5 = {
        "shop_id": "osm:node:5",
        "osm_id": 5,
        "name": "Stationery 1",
        "categories": ["stationery"],
        "lat": 40.0,
        "lng": -3.0,
        "source": "overpass",
        "fetched_at": db.now_iso(),
    }
    
    conn = db.connect(db_path)
    db.upsert_shop(conn, shop1)
    db.upsert_shop(conn, shop2)
    db.upsert_shop(conn, shop3)
    db.upsert_shop(conn, shop4)
    db.upsert_shop(conn, shop5)
    
    # Insert some dummy inventory to verify wipe
    item = {
        "shop_id": "osm:node:1",
        "sku": "PHA-9999",
        "name": "Dummy Item to Wipe",
        "category": "pharmacy",
        "price": 10.0,
        "currency": "EUR",
        "qty": 5,
        "synthetic": True,
        "source": "manual",
    }
    db.upsert_item(conn, item)
    
    conn.commit()
    conn.close()
    
    # Run reseed
    num_shops, total_items = reseed_inventory.reseed(db_path=db_path)
    
    assert num_shops == 5
    assert total_items > 0
    
    # Verify inventory table is populated with seeded items and wiped dummy items
    conn = db.connect(db_path)
    items = [dict(row) for row in conn.execute("SELECT * FROM inventory").fetchall()]
    conn.close()
    
    assert len(items) == total_items
    
    # Assert wiped item is gone
    skus = [i["sku"] for i in items]
    assert "PHA-9999" not in skus
    
    # Map sources per category
    cat_sources = {
        "pharmacy": set(),
        "grocery": set(),
        "hardware": set(),
        "electronics": set(),
        "stationery": set(),
    }
    for item in items:
        cat_sources[item["category"]].add(item["source"])
        
    assert "dummyjson" in cat_sources["pharmacy"], "Expected dummyjson items in pharmacy"
    assert "dummyjson" in cat_sources["grocery"], "Expected dummyjson items in grocery"
    assert "dummyjson" in cat_sources["hardware"], "Expected dummyjson items in hardware"
    assert "dummyjson" in cat_sources["electronics"], "Expected dummyjson items in electronics"
    
    assert "dummyjson" not in cat_sources["stationery"], "Expected NO dummyjson items in stationery"
    assert cat_sources["stationery"] == {"template"}, "Stationery should only have 'template' items"
