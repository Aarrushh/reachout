"""Pure geometry. No AI, no network. Distance between two lat/lng points.

This file is deterministic on purpose. Distance is never something an
AI should guess. Same input always gives the same output.
"""

import math


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points in kilometres."""
    radius = 6371.0  # mean Earth radius in km
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def within_radius(user_lat, user_lng, shop_lat, shop_lng, radius_km):
    """True if the shop sits inside the search radius."""
    return haversine_km(user_lat, user_lng, shop_lat, shop_lng) <= radius_km


if __name__ == "__main__":
    # Sanity check. Two points in Mumbai roughly 2 km apart.
    d = haversine_km(19.0760, 72.8777, 19.0896, 72.8656)
    print("distance km:", round(d, 3))
