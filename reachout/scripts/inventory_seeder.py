"""Deterministic synthetic-inventory seeder.

seed_shop(conn, shop) gives a shop a deterministic subset of its primary
category's SKUs from data/sku_catalog.json, jittered +/-15% on price
(rounded to cents) with qty 0-12. The subset and jitter are drawn from
random.Random(shop_id), so the same shop_id produces identical inventory
on every run — see sku_catalog.json's header comment for the spec.
"""

import json
import os
import random

import db

CATALOG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "sku_catalog.json")
)


def _load_catalog():
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def seed_shop(conn, shop):
    catalog = _load_catalog()
    category = shop["categories"][0]
    skus = catalog.get(category, [])
    if not skus:
        return []

    rng = random.Random(shop["shop_id"])
    count = rng.randint(1, len(skus))
    chosen = rng.sample(skus, count)

    now = db.now_iso()
    rows = []
    for entry in chosen:
        jitter = rng.uniform(-0.15, 0.15)
        price = round(entry["base_price_eur"] * (1 + jitter), 2)
        qty = rng.randint(0, 12)
        item = {
            "shop_id": shop["shop_id"],
            "sku": entry["sku"],
            "name": entry["name"],
            "category": category,
            "price": price,
            "currency": "EUR",
            "qty": qty,
            "synthetic": True,
            "source": "template",
        }
        db.upsert_item(conn, item)
        rows.append(dict(item, updated_at=now))

    return rows
