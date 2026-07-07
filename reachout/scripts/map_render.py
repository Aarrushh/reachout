"""Stage 05: map-render. Pure Python, no AI, no network.

A mechanical projection of ranked_shops.json into an RFC 7946 GeoJSON
FeatureCollection for a future map UI. Coordinates are [longitude, latitude]
per the RFC; every property is copied verbatim from the input. GeoJSON has
no room for a status field, so a bad input produces error.json instead of
a .geojson file (the error-sidecar convention).
"""

import json
import os

OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "stages", "05-map-render", "output")
)

PROPERTY_FIELDS = [
    "shop_id", "shop_name", "rank", "category", "address",
    "distance_km", "item_name", "price", "currency", "stock_qty",
]

REQUIRED_RESULT_FIELDS = [
    "shop_id", "shop_name", "rank", "category", "distance_km",
    "item_name", "price", "currency", "stock_qty", "lat", "lng",
]


def _missing_fields(results):
    missing = []
    for i, result in enumerate(results):
        for field in REQUIRED_RESULT_FIELDS:
            if result.get(field) is None:
                missing.append(f"results[{i}].{field}")
    return missing


def render(ranked_shops, center, radius_km):
    """Project a ranked_shops dict into a GeoJSON FeatureCollection.

    Returns (geojson, None) on success or (None, error_envelope) on
    incomplete/error input, mirroring the error-sidecar convention.
    """
    status = ranked_shops.get("status")
    if status != "ok":
        error = {"status": status}
        if "missing_fields" in ranked_shops:
            error["missing_fields"] = ranked_shops["missing_fields"]
        if "error" in ranked_shops:
            error["error"] = ranked_shops["error"]
        return None, error

    results = ranked_shops.get("results", [])
    missing = _missing_fields(results)
    if missing:
        return None, {"status": "incomplete", "missing_fields": missing}

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [result["lng"], result["lat"]]},
            "properties": {field: result[field] for field in PROPERTY_FIELDS},
        }
        for result in results
    ]

    geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "query": ranked_shops["query"],
            "generated_at": ranked_shops["generated_at"],
            "result_count": ranked_shops["result_count"],
            "center": center,
            "radius_km": radius_km,
        },
        "features": features,
    }
    return geojson, None


def write_output(ranked_shops, center, radius_km, output_dir=OUTPUT_DIR):
    """Render and write shops.geojson or error.json, clearing the other."""
    os.makedirs(output_dir, exist_ok=True)
    geojson_path = os.path.join(output_dir, "shops.geojson")
    error_path = os.path.join(output_dir, "error.json")

    geojson, error = render(ranked_shops, center, radius_km)

    if geojson is not None:
        with open(geojson_path, "w") as f:
            json.dump(geojson, f, indent=2)
        if os.path.exists(error_path):
            os.remove(error_path)
    else:
        with open(error_path, "w") as f:
            json.dump(error, f, indent=2)
        if os.path.exists(geojson_path):
            os.remove(geojson_path)

    return geojson, error
