"""Overpass API client. Fetches real Madrid shops by OSM tag.

Every category's tag selectors come only from data/category_tag_map.json
(constraints.md #1: a tagging correction is a data edit, never a prompt or
code edit). Network calls are best-effort: osm_ingest.py is responsible for
falling back to the committed cache when this module raises.
"""

import json
import os

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "ReachOut-Madrid-MVP/0.1 (educational project; https://github.com/reachout/reachout)"
TIMEOUT_S = 60

CATEGORY_TAG_MAP_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "category_tag_map.json")
)


class OverpassError(Exception):
    """Raised when Overpass cannot be reached or returns a bad response."""


def load_category_tag_map():
    with open(CATEGORY_TAG_MAP_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def build_query(area_name="Madrid", tag_map=None, timeout=TIMEOUT_S):
    """Build an Overpass QL query selecting every tag in tag_map within area_name."""
    tag_map = tag_map if tag_map is not None else load_category_tag_map()
    selectors = []
    for tags in tag_map.values():
        for tag in tags:
            selectors.append((tag["key"], tag["value"]))
    # de-duplicate while preserving order (pharmacy/grocery can share a selector)
    seen = set()
    unique_selectors = []
    for sel in selectors:
        if sel not in seen:
            seen.add(sel)
            unique_selectors.append(sel)

    lines = [f'[out:json][timeout:{timeout}];', f'area["name"="{area_name}"]["admin_level"="8"]->.searchArea;', "("]
    for key, value in unique_selectors:
        for kind in ("node", "way", "relation"):
            lines.append(f'  {kind}["{key}"="{value}"](area.searchArea);')
    lines.append(");")
    lines.append("out center tags;")
    return "\n".join(lines)


def fetch_shops(area_name="Madrid", timeout=TIMEOUT_S):
    """Live Overpass fetch. Returns the raw list of `elements`. Raises OverpassError on failure."""
    query = build_query(area_name=area_name, timeout=timeout)
    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise OverpassError(f"Overpass request failed: {e}") from e

    if resp.status_code != 200:
        raise OverpassError(f"Overpass returned HTTP {resp.status_code}")

    try:
        payload = resp.json()
    except ValueError as e:
        raise OverpassError(f"Overpass returned non-JSON response: {e}") from e

    return payload.get("elements", [])
