"""Overpass/cache -> validated ShopRecords -> db upsert + inventory seeding.

ingest() is the only entry point stage-02 (W4) and demo.py (W8) call. It
never guesses a shop's identity: every row comes from OSM tags (live,
cached, or geofabrik) and is validated against shop_record.schema.json
before it touches the database.
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

import db
import inventory_seeder
import overpass
import validate

CACHE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "osm_cache", "madrid_shops.json")
)

CATEGORIES_IN_ORDER = ["pharmacy", "grocery", "hardware", "electronics", "stationery"]

MADRID_LAT_BOUNDS = (40.2, 40.7)
MADRID_LNG_BOUNDS = (-4.0, -3.4)


class NoShopSourceError(Exception):
    pass


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _is_offline():
    return os.environ.get("REACHOUT_OFFLINE") == "1"


def map_categories(tags, tag_map=None):
    """Every internal category tags matches, primary (tag_map order) first."""
    tag_map = tag_map if tag_map is not None else overpass.load_category_tag_map()
    matched = []
    for category in CATEGORIES_IN_ORDER:
        for selector in tag_map.get(category, []):
            if tags.get(selector["key"]) == selector["value"]:
                matched.append(category)
                break
    return matched


def build_address(tags):
    street = tags.get("addr:street")
    housenumber = tags.get("addr:housenumber")
    postcode = tags.get("addr:postcode")
    city = tags.get("addr:city")

    parts = []
    if street:
        parts.append(f"{street} {housenumber}".strip() if housenumber else street)
    locality = " ".join(p for p in (postcode, city) if p)
    if locality:
        parts.append(locality)

    return ", ".join(parts) if parts else None


def _in_bounds(lat, lng):
    return MADRID_LAT_BOUNDS[0] <= lat <= MADRID_LAT_BOUNDS[1] and MADRID_LNG_BOUNDS[0] <= lng <= MADRID_LNG_BOUNDS[1]


def element_to_shop_record(element, source, tag_map=None):
    """Map one raw Overpass element to a ShopRecord dict, or None if it doesn't qualify."""
    tags = element.get("tags", {})
    name = tags.get("name")
    if not name:
        return None

    categories = map_categories(tags, tag_map)
    if not categories:
        return None

    lat = element.get("lat")
    lng = element.get("lon")
    if lat is None or lng is None:
        center = element.get("center") or {}
        lat = center.get("lat")
        lng = center.get("lon")
    if lat is None or lng is None or not _in_bounds(lat, lng):
        return None

    return {
        "shop_id": f"osm:{element['type']}:{element['id']}",
        "osm_id": element["id"],
        "name": name,
        "categories": categories,
        "lat": lat,
        "lng": lng,
        "address": build_address(tags),
        "source": source,
        "fetched_at": now_iso(),
    }


def load_cache():
    if not os.path.exists(CACHE_PATH):
        return None
    with open(CACHE_PATH, encoding="utf-8") as f:
        records = json.load(f)
    for record in records:
        record["source"] = "cache"
    return records


def save_cache(records):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def fetch_shop_records(area_name="Madrid", refresh=False, offline=None):
    """Return (records, source_label). Raises NoShopSourceError if nothing is available."""
    offline = _is_offline() if offline is None else offline

    if not offline:
        try:
            tag_map = overpass.load_category_tag_map()
            elements = overpass.fetch_shops(area_name=area_name)
            records = [
                r for r in (element_to_shop_record(e, "overpass_live", tag_map) for e in elements) if r is not None
            ]
            if refresh:
                save_cache(records)
            return records, "overpass_live"
        except overpass.OverpassError:
            pass  # fall through to cache

    cached = load_cache()
    if cached is not None:
        return cached, "cache"

    raise NoShopSourceError("Overpass unreachable and no committed cache at " + CACHE_PATH)


def ingest(area_name="Madrid", refresh=False, conn=None, offline=None):
    """Fetch shops (live, falling back to cache), validate, upsert, seed new ones.

    Returns a list of validated ShopRecord dicts on success, or
    {"status": "error", "error": {"code": "no_shop_source", "detail": ...}} if
    neither Overpass nor the committed cache are available.
    """
    try:
        records, _source = fetch_shop_records(area_name=area_name, refresh=refresh, offline=offline)
    except NoShopSourceError as e:
        return {"status": "error", "error": {"code": "no_shop_source", "detail": str(e)}}

    validated = []
    for record in records:
        ok, _ = validate.validate(record, "shop_record.schema.json")
        if ok:
            validated.append(record)

    owns_conn = conn is None
    conn = conn or db.connect()
    try:
        existing_ids = {shop["shop_id"] for shop in db.all_shops(conn)}
        for record in validated:
            db.upsert_shop(conn, record)
            if record["shop_id"] not in existing_ids:
                inventory_seeder.seed_shop(conn, record)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()

    return validated
