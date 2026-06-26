"""Live inventory simulator.

This is the "constantly updated" inventory. On each tick it picks random
shops and does real movements:
  - sells units (qty goes down, can hit zero and go out of stock)
  - restocks existing items (qty goes back up)
  - adds a new SKU the shop did not carry before

Every movement is written to the SQLite store AND appended to
data/events.jsonl so you can watch the stream in a second terminal with:
    tail -f data/events.jsonl

Run continuously:      python scripts/inventory_simulator.py
Run for N seconds:     python scripts/inventory_simulator.py --seconds 30
Run as a background thread: import and call run_simulator(stop_event)
"""

import argparse
import json
import os
import random
import threading
import time

import db
from seed_data import CATALOGUE

EVENTS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "events.jsonl"))


def _log_event(event):
    event["ts"] = time.time()
    with open(EVENTS_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")


def _tick(conn):
    shops = db.all_shops(conn)
    if not shops:
        return
    shop = random.choice(shops)
    roll = random.random()

    if roll < 0.55:
        # Sell. Pick an in-stock item and remove a few units.
        items = db.items_for_shop(conn, shop["id"], in_stock_only=True)
        if items:
            item = random.choice(items)
            sold = random.randint(1, 5)
            new_qty = db.adjust_qty(conn, shop["id"], item["sku"], -sold)
            _log_event({"type": "sale", "shop_id": shop["id"], "shop": shop["name"],
                        "sku": item["sku"], "name": item["name"], "sold": sold, "qty_now": new_qty})

    elif roll < 0.85:
        # Restock an existing item.
        items = db.items_for_shop(conn, shop["id"], in_stock_only=False)
        if items:
            item = random.choice(items)
            added = random.randint(5, 20)
            new_qty = db.adjust_qty(conn, shop["id"], item["sku"], added)
            _log_event({"type": "restock", "shop_id": shop["id"], "shop": shop["name"],
                        "sku": item["sku"], "name": item["name"], "added": added, "qty_now": new_qty})

    else:
        # Add a brand new SKU from the catalogue that the shop does not have yet.
        existing = {i["sku"] for i in db.items_for_shop(conn, shop["id"], in_stock_only=False)}
        choices = [c for c in CATALOGUE[shop["category"]] if c[0] not in existing]
        if choices:
            sku, name, price = random.choice(choices)
            qty = random.randint(8, 25)
            db.upsert_item(conn, {"shop_id": shop["id"], "sku": sku, "name": name,
                                  "category": shop["category"], "price": price, "qty": qty})
            _log_event({"type": "new_item", "shop_id": shop["id"], "shop": shop["name"],
                        "sku": sku, "name": name, "qty_now": qty})


def run_simulator(stop_event=None, interval=1.0, seconds=None):
    """Run until stop_event is set, or for `seconds`, or forever."""
    conn = db.connect()
    start = time.time()
    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            if seconds is not None and (time.time() - start) >= seconds:
                break
            _tick(conn)
            conn.commit()
            time.sleep(interval)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=None, help="run for this many seconds then stop")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between movements")
    args = parser.parse_args()
    print("Simulator running. Events stream to data/events.jsonl . Ctrl+C to stop.")
    try:
        run_simulator(interval=args.interval, seconds=args.seconds)
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
