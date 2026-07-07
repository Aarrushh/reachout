"""Nominatim geocoding client: place name -> lat/lng.

Manners (constraints.md #7): explicit timeout, descriptive User-Agent, max
1 request/second, results cached to data/geocode_cache.json. Falls back to
data/gazetteer_madrid.json (case- and accent-insensitive) when the API is
unreachable or REACHOUT_OFFLINE=1 is set. Never guesses a coordinate that
isn't backed by one of these two sources.
"""

import json
import os
import time
import unicodedata

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ReachOut-Madrid-MVP/0.1 (educational project; https://github.com/reachout/reachout)"
TIMEOUT_S = 10
MIN_INTERVAL_S = 1.0

GAZETTEER_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "gazetteer_madrid.json")
)
CACHE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "geocode_cache.json")
)

_last_request_at = 0.0


def _normalize(name):
    stripped = unicodedata.normalize("NFKD", name.strip().lower())
    return "".join(c for c in stripped if not unicodedata.combining(c))


def _load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_gazetteer():
    data = _load_json(GAZETTEER_PATH)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _gazetteer_lookup(place_name):
    gazetteer = load_gazetteer()
    normalized = {_normalize(k): v for k, v in gazetteer.items()}
    hit = normalized.get(_normalize(place_name))
    if hit is None:
        return None
    return {"lat": hit["lat"], "lng": hit["lng"], "source": "gazetteer"}


def _cache_lookup(place_name):
    cache = _load_json(CACHE_PATH)
    hit = cache.get(_normalize(place_name))
    if hit is None:
        return None
    return {"lat": hit["lat"], "lng": hit["lng"], "source": "geocode_cache"}


def _cache_store(place_name, lat, lng):
    cache = _load_json(CACHE_PATH)
    cache[_normalize(place_name)] = {"lat": lat, "lng": lng}
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _rate_limit():
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - elapsed)
    _last_request_at = time.monotonic()


def _live_lookup(place_name):
    _rate_limit()
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": f"{place_name}, Madrid, Spain", "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_S,
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    try:
        results = resp.json()
    except ValueError:
        return None

    if not results:
        return None

    lat = float(results[0]["lat"])
    lng = float(results[0]["lon"])
    return {"lat": lat, "lng": lng, "source": "nominatim_live"}


def geocode(place_name, offline=None):
    """Resolve a place name to {"lat", "lng", "source"}, or None if unresolvable.

    offline defaults to the REACHOUT_OFFLINE env var; pass explicitly in tests.
    """
    if offline is None:
        offline = os.environ.get("REACHOUT_OFFLINE") == "1"

    cached = _cache_lookup(place_name)
    if cached is not None:
        return cached

    if not offline:
        live = _live_lookup(place_name)
        if live is not None:
            _cache_store(place_name, live["lat"], live["lng"])
            return live

    return _gazetteer_lookup(place_name)
