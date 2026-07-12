"""DummyJSON API client. Fetches dummy products.

Network calls are best-effort. If offline or cache_only, reads from the committed cache.
"""

import json
import os
import sys

import requests

DUMMYJSON_URL = "https://dummyjson.com/products?limit=0"
USER_AGENT = "ReachOut-Madrid-MVP/0.1 (educational project; https://github.com/reachout/reachout)"
TIMEOUT_S = 60

CACHE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "dummyjson_cache", "products.json")
)


class DummyJSONError(Exception):
    """Raised when DummyJSON cannot be reached or returns a bad response."""


def _is_offline():
    return os.environ.get("REACHOUT_OFFLINE") == "1"


def load_cache():
    if not os.path.exists(CACHE_PATH):
        raise DummyJSONError("No committed cache at " + CACHE_PATH)
    with open(CACHE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("products", [])


def save_cache(data):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_products(cache_only=False):
    """Live DummyJSON fetch. Returns the list of products. Raises DummyJSONError on failure.
    If REACHOUT_OFFLINE=1 or cache_only=True, bypasses network and reads from cache.
    """
    if _is_offline() or cache_only:
        return load_cache()

    try:
        resp = requests.get(
            DUMMYJSON_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_S,
        )
    except requests.RequestException as e:
        raise DummyJSONError(f"DummyJSON request failed: {e}") from e

    if resp.status_code != 200:
        raise DummyJSONError(f"DummyJSON returned HTTP {resp.status_code}")

    try:
        payload = resp.json()
    except ValueError as e:
        raise DummyJSONError(f"DummyJSON returned non-JSON response: {e}") from e

    save_cache(payload)
    return payload.get("products", [])


if __name__ == "__main__":
    refresh = "--refresh" in sys.argv
    if refresh:
        print("Fetching live from DummyJSON...")
        try:
            products = fetch_products(cache_only=False)
            print(f"Fetched and cached {len(products)} products.")
        except DummyJSONError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        print("Reading from cache (use --refresh to fetch live)...")
        try:
            products = fetch_products(cache_only=True)
            print(f"Loaded {len(products)} products from cache.")
        except DummyJSONError as e:
            print(f"Error: {e}")
            sys.exit(1)
