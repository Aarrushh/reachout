"""OpenRouteService walking-distance client. Optional, key-gated.

Only called when ORS_API_KEY is set in the environment; otherwise (or on
any failure) returns None so the caller falls back to haversine
(scripts/geo.py), recording distance_type accordingly (constraints.md #7).
"""

import os

import requests

ORS_URL = "https://api.openrouteservice.org/v2/directions/foot-walking"
USER_AGENT = "ReachOut-Madrid-MVP/0.1 (educational project; https://github.com/reachout/reachout)"
TIMEOUT_S = 10


def walking_distance_km(lat1, lng1, lat2, lng2, offline=None):
    """Walking distance in km via ORS, or None if unavailable/unset/offline."""
    if offline is None:
        offline = os.environ.get("REACHOUT_OFFLINE") == "1"
    if offline:
        return None

    api_key = os.environ.get("ORS_API_KEY")
    if not api_key:
        return None

    try:
        resp = requests.get(
            ORS_URL,
            params={
                "api_key": api_key,
                "start": f"{lng1},{lat1}",
                "end": f"{lng2},{lat2}",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_S,
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    try:
        payload = resp.json()
        meters = payload["features"][0]["properties"]["summary"]["distance"]
    except (ValueError, KeyError, IndexError, TypeError):
        return None

    return meters / 1000.0
