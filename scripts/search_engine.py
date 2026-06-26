"""The matching engine. Pure Python. This is the heart of ReachOut.

Given a parsed search intent and the user's location, it:
  1. filters shops to those inside the radius (geo.py, pure math)
  2. matches the query keywords against each shop's LIVE in-stock items
  3. ranks matches by distance, then stock depth, then price
  4. pings every matched shop (ping.py)
  5. returns a structured result

Critical design choice for "no hallucination": stock and distance come
only from the database and from math. An AI never decides whether an item
exists or how far away a shop is. If the data says zero stock, the result
is zero stock.
"""

import re
import db
import geo
from ping import ping


def _matches(item, keywords):
    """Word-aware match. A keyword matches if it equals a whole word in the
    item name or category, or (for longer keywords) appears as a substring.

    Whole-word matching stops noise like the single letter 'c' matching
    'sachet', or 'and' matching 'bandage'.
    """
    haystack = (item["name"] + " " + item["category"]).lower()
    tokens = set(re.findall(r"[a-z0-9]+", haystack))
    for kw in keywords:
        k = kw.lower()
        if k in tokens:
            return True
        if len(k) >= 4 and k in haystack:
            return True
    return False


def search(intent, user_lat, user_lng, radius_km=5.0, do_ping=True):
    keywords = intent.get("keywords", [])
    conn = db.connect()
    results = []

    for shop in db.all_shops(conn):
        distance = geo.haversine_km(user_lat, user_lng, shop["lat"], shop["lng"])
        if distance > radius_km:
            continue

        live_items = db.items_for_shop(conn, shop["id"], in_stock_only=True)
        matched = [i for i in live_items if _matches(i, keywords)]
        if not matched:
            continue

        matched.sort(key=lambda i: i["price"])  # cheapest first within a shop
        results.append({
            "shop_id": shop["id"],
            "shop_name": shop["name"],
            "address": shop.get("address", ""),
            "distance_km": round(distance, 2),
            "items": matched,
        })

    conn.close()

    # Rank shops: nearest first, then most stock of the top item, then cheapest.
    results.sort(key=lambda r: (
        r["distance_km"],
        -max(i["qty"] for i in r["items"]),
        min(i["price"] for i in r["items"]),
    ))

    if do_ping:
        conn2 = db.connect()
        shops_by_id = {s["id"]: s for s in db.all_shops(conn2)}
        conn2.close()
        for r in results:
            ping(shops_by_id[r["shop_id"]], intent, r["items"], r["distance_km"])

    return {
        "query": intent.get("raw_query", ""),
        "keywords": keywords,
        "radius_km": radius_km,
        "match_count": len(results),
        "matches": results,
    }


if __name__ == "__main__":
    # Quick manual test. Assumes seed_data.py has run.
    demo_intent = {"raw_query": "paracetamol", "keywords": ["paracetamol"]}
    out = search(demo_intent, 19.1100, 72.8500, radius_km=5.0, do_ping=True)
    print("matches:", out["match_count"])
