"""The live inventory store. Plain SQLite, standard library only.

Why SQLite and not a JSON file: the simulator writes constantly while
searches read at the same time. SQLite in WAL mode handles that cleanly.
Every change is still observable because we also append plain-text events
to data/events.jsonl (see inventory_simulator.py).

Schema:
  shops(shop_id, osm_id, name, categories, lat, lng, address, source, fetched_at, region_id)
  inventory(shop_id, sku, name, category, price, currency, qty, synthetic, updated_at)
  regions(region_id, name, lat, lng, source, created_at)
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

try:
    from . import migrations
except ImportError:
    import migrations

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
        CREATE TABLE IF NOT EXISTS regions (
            region_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shops (
            shop_id TEXT PRIMARY KEY,
            osm_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            categories TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            address TEXT,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            region_id TEXT
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
            source TEXT NOT NULL DEFAULT 'template',
            rating REAL,
            review_count INTEGER,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (shop_id, sku),
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
        );

        CREATE INDEX IF NOT EXISTS idx_shops_region ON shops(region_id);
        CREATE INDEX IF NOT EXISTS idx_inv_name ON inventory(name);
        CREATE INDEX IF NOT EXISTS idx_inv_qty ON inventory(qty);
        PRAGMA user_version = 3;
        """
    )
    conn.commit()
    migrations.migrate(conn)
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
    update_source = "source=excluded.source" if "source" in item else "source=inventory.source"
    update_rating = "rating=excluded.rating" if "rating" in item else "rating=inventory.rating"
    update_rc = "review_count=excluded.review_count" if "review_count" in item else "review_count=inventory.review_count"

    conn.execute(
        f"""
        INSERT INTO inventory 
        (shop_id, sku, name, category, price, currency, qty, synthetic, source, rating, review_count, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(shop_id, sku) DO UPDATE SET
            name=excluded.name,
            category=excluded.category,
            price=excluded.price,
            currency=excluded.currency,
            qty=excluded.qty,
            synthetic=excluded.synthetic,
            updated_at=excluded.updated_at,
            {update_source},
            {update_rating},
            {update_rc}
        """,
        (
            item["shop_id"],
            item["sku"],
            item["name"],
            item["category"],
            item["price"],
            item["currency"],
            item["qty"],
            1 if item["synthetic"] else 0,
            item.get("source", "template"),
            item.get("rating"),
            item.get("review_count"),
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


def _region_row(row):
    return dict(row)


def all_shops(conn):
    return [_shop_row(r) for r in conn.execute("SELECT * FROM shops").fetchall()]


def items_for_shop(conn, shop_id, in_stock_only=True):
    q = "SELECT * FROM inventory WHERE shop_id=?"
    if in_stock_only:
        q += " AND qty > 0"
    return [_item_row(r) for r in conn.execute(q, (shop_id,)).fetchall()]


def upsert_region(conn, region):
    conn.execute(
        "INSERT OR REPLACE INTO regions "
        "(region_id, name, lat, lng, source, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            region["region_id"],
            region["name"],
            region["lat"],
            region["lng"],
            region["source"],
            region["created_at"],
        ),
    )


def all_regions(conn):
    return [_region_row(r) for r in conn.execute("SELECT * FROM regions ORDER BY name").fetchall()]


def shops_in_region(conn, region_id):
    return [_shop_row(r) for r in conn.execute("SELECT * FROM shops WHERE region_id=?", (region_id,)).fetchall()]


def region_shop_counts(conn):
    rows = conn.execute("SELECT region_id, COUNT(*) as count FROM shops WHERE region_id IS NOT NULL GROUP BY region_id").fetchall()
    return {row["region_id"]: row["count"] for row in rows}


def inventory_page(conn, region_id, page, page_size, in_stock_only=False):
    where_clauses = []
    params = []
    
    if region_id is not None:
        where_clauses.append("shops.region_id = ?")
        params.append(region_id)
        
    if in_stock_only:
        where_clauses.append("inventory.qty > 0")
        
    where_str = ""
    if where_clauses:
        where_str = " WHERE " + " AND ".join(where_clauses)
    
    total_query = f"SELECT COUNT(*) as total FROM inventory JOIN shops ON inventory.shop_id = shops.shop_id{where_str}"
    total = conn.execute(total_query, params).fetchone()["total"]
    
    offset = (page - 1) * page_size
    q = f"SELECT inventory.*, shops.name as shop_name FROM inventory JOIN shops ON inventory.shop_id = shops.shop_id{where_str} ORDER BY inventory.shop_id, inventory.sku LIMIT ? OFFSET ?"
    rows = [_item_row(r) for r in conn.execute(q, params + [page_size, offset]).fetchall()]
    return rows, total


if __name__ == "__main__":
    init_db()
    print("DB ready at", DB_PATH)
