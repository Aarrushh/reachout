"""The ping layer. When a search matches a shop, that shop gets pinged.

In this MVP a "ping" is two things:
  1. a line appended to data/notifications/<shop_id>.jsonl  (the shop's inbox)
  2. a printed alert so you can see it happen live in the terminal

In production this is where you would call Firebase, SMS, or a websocket
push. The interface stays the same: ping(shop, intent, matched_items).
No AI is involved. A match either happened or it did not.
"""

import json
import os
import time

NOTIF_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "notifications"))


def ping(shop, intent, matched_items, distance_km):
    os.makedirs(NOTIF_DIR, exist_ok=True)
    payload = {
        "ts": time.time(),
        "shop_id": shop["id"],
        "query": intent.get("raw_query", ""),
        "keywords": intent.get("keywords", []),
        "distance_km": round(distance_km, 2),
        "matched_items": [
            {"sku": i["sku"], "name": i["name"], "price": i["price"], "qty": i["qty"]}
            for i in matched_items
        ],
    }
    inbox = os.path.join(NOTIF_DIR, shop["id"] + ".jsonl")
    with open(inbox, "a") as f:
        f.write(json.dumps(payload) + "\n")

    top = matched_items[0]
    print(f"  [PING] {shop['name']} ({distance_km:.1f} km): customer wants "
          f"'{intent.get('raw_query','')}'. You have {top['qty']} x {top['name']}.")
    return payload
