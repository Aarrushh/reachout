"""CLI to wipe and reseed inventory for all shops.

Run this script once after any catalog change (e.g., adding or updating SKUs
in data/sku_catalog.json). It transactionally wipes the `inventory` table
and reseeds every shop with a deterministic subset of items via `inventory_seeder`.

The database file (reachout.db) is regenerated per environment and should never
be committed.
"""

import sys
import logging

try:
    from scripts import db
    from scripts import inventory_seeder
except ImportError:
    import db
    import inventory_seeder

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def reseed(db_path=None):
    """Wipe inventory and reseed all shops transactionally."""
    conn = db.connect(db_path)
    try:
        shops = db.all_shops(conn)
        
        # Transactional wipe and reseed
        conn.execute("BEGIN TRANSACTION")
        
        # Wipe inventory
        conn.execute("DELETE FROM inventory")
        
        total_items = 0
        for shop in shops:
            rows = inventory_seeder.seed_shop(conn, shop)
            total_items += len(rows)
            
        conn.execute("COMMIT")
        logging.info(f"Reseed complete. Seeded {total_items} items across {len(shops)} shops.")
        return len(shops), total_items
    except Exception as e:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        logging.error(f"Reseed failed: {e}")
        raise e
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        reseed()
    except Exception:
        sys.exit(1)
