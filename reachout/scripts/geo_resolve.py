"""Stage 02: geo-resolve. Pure Python, no AI, no invented facts.

Resolves the query centre (explicit coordinates > location_text via
Nominatim/gazetteer > default centre Puerta del Sol), selects real shops
from the ingested shops table within radius_km, filters by category_hints,
and computes distance (ORS walking if available, else haversine). A named
place that cannot be geocoded is reported incomplete -- it is never
silently replaced by the default centre (constraints.md #3).
"""

import os

import db
import geo
import nominatim
import ors
import osm_ingest

DEFAULT_LAT = 40.4168
DEFAULT_LNG = -3.7038


def _is_offline():
    return os.environ.get("REACHOUT_OFFLINE") == "1"


def _resolve_center(lat, lng, location_text, offline):
    """Returns (lat, lng, resolved_from) or None if location_text can't be geocoded."""
    if lat is not None and lng is not None:
        return lat, lng, "coordinates"

    if location_text:
        hit = nominatim.geocode(location_text, offline=offline)
        if hit is None:
            return None
        resolved_from = "gazetteer" if hit["source"] == "gazetteer" else "nominatim"
        return hit["lat"], hit["lng"], resolved_from

    return DEFAULT_LAT, DEFAULT_LNG, "default_center"


def _shop_source_from_records(records, offline):
    if records:
        return records[0]["source"]
    return "cache" if offline else "overpass_live"


def resolve(intent, lat=None, lng=None, near=None, radius_km=2.0, refresh=False, db_path=None, offline=None):
    """Resolve query centre + candidate shops. Returns a geo_shops-shaped dict."""
    if offline is None:
        offline = _is_offline()

    location_text = near if near is not None else intent.get("location_text")
    category_hints = intent.get("category_hints") or []

    center = _resolve_center(lat, lng, location_text, offline)
    if center is None:
        return {"status": "incomplete", "missing_fields": ["query_location"]}
    center_lat, center_lng, resolved_from = center

    conn = db.connect(db_path)
    try:
        shop_source = "cache"
        if refresh:
            ingest_result = osm_ingest.ingest(refresh=True, conn=conn, offline=offline)
            if isinstance(ingest_result, dict):
                return ingest_result
            shop_source = _shop_source_from_records(ingest_result, offline)

        candidates = []
        for shop in db.all_shops(conn):
            if category_hints and not set(shop["categories"]) & set(category_hints):
                continue
            distance_km = geo.haversine_km(center_lat, center_lng, shop["lat"], shop["lng"])
            if distance_km > radius_km:
                continue
            walking_km = ors.walking_distance_km(center_lat, center_lng, shop["lat"], shop["lng"], offline=offline)
            if walking_km is not None:
                candidates.append((shop, walking_km, "walking"))
            else:
                candidates.append((shop, distance_km, "haversine"))
    finally:
        conn.close()

    candidates.sort(key=lambda c: c[1])

    shops = [
        {
            "shop_id": shop["shop_id"],
            "name": shop["name"],
            "categories": shop["categories"],
            "lat": shop["lat"],
            "lng": shop["lng"],
            "address": shop["address"],
            "distance_km": distance_km,
            "distance_type": distance_type,
        }
        for shop, distance_km, distance_type in candidates
    ]

    return {
        "status": "ok",
        "query_location": {
            "lat": center_lat,
            "lng": center_lng,
            "resolved_from": resolved_from,
            "location_text": location_text,
        },
        "radius_km": radius_km,
        "shop_source": shop_source,
        "shop_count": len(shops),
        "shops": shops,
    }
