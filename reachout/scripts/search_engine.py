"""The matching engine. Pure Python. This is the heart of ReachOut.

Given a parsed search intent (stage 01) and the geo-filtered candidate
shops (stage 02, the ONLY candidate set), it:
  1. reads each candidate shop's LIVE in-stock items from the database
  2. keeps items whose name/category whole-word-matches a keyword, gated
     by category_hints against the shop's full categories list (secondary
     categories count)
  3. ranks matched shops: nearest first, then most total matching stock,
     then cheapest best item. Distances are copied unchanged from geo_shops.
  4. pings every matched shop (ping.py)
  5. returns a StockMatches-shaped result

Critical design choice for "no hallucination": stock and distance come
only from the database and from geo_shops. An AI never decides whether an
item exists or how far away a shop is. If the data says zero stock, the
result is zero stock.
"""

import re

import db
from ping import ping


def _matches(item, keywords):
    """Whole-word match. A keyword matches if it equals a whole word in the
    item name or category.
    """
    haystack = (item["name"] + " " + item["category"]).lower()
    tokens = set(re.findall(r"[a-z0-9]+", haystack))
    return any(kw.lower() in tokens for kw in keywords)


def _item_out(item):
    out = {
        "sku": item["sku"],
        "name": item["name"],
        "category": item["category"],
        "price": item["price"],
        "currency": item["currency"],
        "qty": item["qty"],
    }
    for key in ("rating", "review_count", "source"):
        if item.get(key) is not None:
            out[key] = item[key]
    return out


def search(intent, geo_shops, db_path=None, do_ping=True, notif_dir=None):
    geo_status = geo_shops.get("status")
    if geo_status == "incomplete":
        return {"status": "incomplete", "missing_fields": geo_shops.get("missing_fields", [])}
    if geo_status == "error":
        return {"status": "error", "error": geo_shops.get("error")}
    if geo_status != "ok":
        return {"status": "error", "error": {"code": "upstream_not_ok", "detail": f"geo_shops status was '{geo_status}'"}}

    keywords = intent.get("keywords")
    if intent.get("status") != "ok" or not keywords:
        return {"status": "incomplete", "missing_fields": intent.get("missing_fields") or ["keywords"]}

    category_hints = intent.get("category_hints") or []

    conn = db.connect(db_path)
    matches = []
    for shop in geo_shops.get("shops", []):
        if category_hints and not set(shop["categories"]) & set(category_hints):
            continue

        live_items = db.items_for_shop(conn, shop["shop_id"], in_stock_only=True)
        matched_items = [i for i in live_items if _matches(i, keywords)]
        if not matched_items:
            continue

        matched_items.sort(key=lambda i: i["price"])
        matches.append({
            "shop_id": shop["shop_id"],
            "shop_name": shop["name"],
            "categories": shop["categories"],
            "address": shop["address"],
            "lat": shop["lat"],
            "lng": shop["lng"],
            "distance_km": shop["distance_km"],
            "distance_type": shop["distance_type"],
            "items": [_item_out(i) for i in matched_items],
        })
    conn.close()

    matches.sort(key=lambda m: (
        m["distance_km"],
        -sum(i["qty"] for i in m["items"]),
        min(i["price"] for i in m["items"]),
    ))

    pinged_shop_ids = [m["shop_id"] for m in matches]
    if do_ping:
        for m in matches:
            ping(m, intent, notif_dir=notif_dir)

    return {
        "status": "ok",
        "query": intent.get("raw_query", ""),
        "query_location": geo_shops.get("query_location"),
        "radius_km": geo_shops.get("radius_km"),
        "match_count": len(matches),
        "matches": matches,
        "pinged_shop_ids": pinged_shop_ids,
    }
