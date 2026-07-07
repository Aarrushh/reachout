"""The live inventory store. Plain SQLite, standard library only.

Why SQLite and not a JSON file: the simulator writes constantly while
searches read at the same time. SQLite in WAL mode handles that cleanly.
Every change is still observable because we also append plain-text events
to data/events.jsonl (see inventory_simulator.py).

Schema:
  shops(shop_id, osm_id, name, categories, lat, lng, address, source, fetched_at)
  inventory(shop_id, sku, name, category, price, currency, qty, synthetic, updated_at)
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reachout.db")
DB_PATH = os.path.abspath(DB_PATH)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db(path=None):
    conn = connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS shops (
            shop_id TEXT PRIMARY KEY,
            osm_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            categories TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            address TEXT,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inventory (
            shop_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            currency TEXT NOT NULL,
            qty INTEGER NOT NULL,
            synthetic INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (shop_id, sku),
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
        );

        CREATE INDEX IF NOT EXISTS idx_inv_name ON inventory(name);
        CREATE INDEX IF NOT EXISTS idx_inv_qty ON inventory(qty);
        """
    )
    conn.commit()
    conn.close()


def upsert_shop(conn, shop):
    conn.execute(
        "INSERT OR REPLACE INTO shops "
        "(shop_id, osm_id, name, categories, lat, lng, address, source, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            shop["shop_id"],
            shop["osm_id"],
            shop["name"],
            json.dumps(shop["categories"]),
            shop["lat"],
            shop["lng"],
            shop.get("address"),
            shop["source"],
            shop["fetched_at"],
        ),
    )


def upsert_item(conn, item):
    conn.execute(
        "INSERT OR REPLACE INTO inventory "
        "(shop_id, sku, name, category, price, currency, qty, synthetic, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            item["shop_id"],
            item["sku"],
            item["name"],
            item["category"],
            item["price"],
            item["currency"],
            item["qty"],
            1 if item["synthetic"] else 0,
            now_iso(),
        ),
    )


def adjust_qty(conn, shop_id, sku, delta):
    """Change quantity by delta. Never lets qty go below zero."""
    row = conn.execute(
        "SELECT qty FROM inventory WHERE shop_id=? AND sku=?", (shop_id, sku)
    ).fetchone()
    if row is None:
        return None
    new_qty = max(0, row["qty"] + delta)
    conn.execute(
        "UPDATE inventory SET qty=?, updated_at=? WHERE shop_id=? AND sku=?",
        (new_qty, now_iso(), shop_id, sku),
    )
    return new_qty


def _shop_row(row):
    shop = dict(row)
    shop["categories"] = json.loads(shop["categories"])
    return shop


def _item_row(row):
    item = dict(row)
    item["synthetic"] = bool(item["synthetic"])
    return item


def all_shops(conn):
    return [_shop_row(r) for r in conn.execute("SELECT * FROM shops").fetchall()]


def items_for_shop(conn, shop_id, in_stock_only=True):
    q = "SELECT * FROM inventory WHERE shop_id=?"
    if in_stock_only:
        q += " AND qty > 0"
    return [_item_row(r) for r in conn.execute(q, (shop_id,)).fetchall()]


if __name__ == "__main__":
    init_db()
    print("DB ready at", DB_PATH)
