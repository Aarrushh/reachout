"""Thin read-only FastAPI wrapper over run_pipeline.run().

No business logic lives here: every field in a response is exactly what
run_pipeline's stage 04 (ranked_shops) / stage 05 (GeoJSON) already produced
and schema-validated. Each request gets its own throwaway output_root so
concurrent requests never read or clobber each other's stage files.
"""

import os
import shutil
import sys
import tempfile
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REACHOUT_DIR = os.path.dirname(HERE)
for _dir in (os.path.join(REACHOUT_DIR, "scripts"), os.path.join(REACHOUT_DIR, "agent"), REACHOUT_DIR):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

from fastapi import FastAPI, HTTPException  # noqa: E402

import db  # noqa: E402
import run_pipeline  # noqa: E402

# Overridable in tests (monkeypatch.setattr(server, "DB_PATH", ...)); None
# means run_pipeline falls back to its own defaults (the real reachout.db /
# the real data/notifications/).
DB_PATH = None
NOTIF_DIR = None

app = FastAPI(title="ReachOut API")


@app.get("/api/health")
def health():
    return {"status": "ok"}


def _run_pipeline(q, near, lat, lng, radius):
    if (lat is None) != (lng is None):
        raise HTTPException(status_code=400, detail="lat and lng must be given together")

    output_root = tempfile.mkdtemp(prefix="reachout_api_")
    try:
        return run_pipeline.run(
            q, near=near, lat=lat, lng=lng, radius_km=radius,
            db_path=DB_PATH, notif_dir=NOTIF_DIR, output_root=output_root,
        )
    except run_pipeline.PipelineError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    finally:
        shutil.rmtree(output_root, ignore_errors=True)


@app.get("/api/search")
def search(q: str, near: Optional[str] = None, lat: Optional[float] = None,
           lng: Optional[float] = None, radius: float = 2.0):
    result = _run_pipeline(q, near, lat, lng, radius)
    return result["ranked_shops"]


@app.get("/api/search.geojson")
def search_geojson(q: str, near: Optional[str] = None, lat: Optional[float] = None,
                    lng: Optional[float] = None, radius: float = 2.0):
    result = _run_pipeline(q, near, lat, lng, radius)
    return result["geojson"]


@app.get("/api/shops.geojson")
def shops_geojson():
    """All known shops, no inventory: the map's network layer. Pure read."""
    conn = db.connect(DB_PATH)
    try:
        shops = db.all_shops(conn)
    finally:
        conn.close()
    return {
        "type": "FeatureCollection",
        "metadata": {"shop_count": len(shops)},
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s["lng"], s["lat"]]},
                "properties": {
                    "shop_id": s["shop_id"],
                    "shop_name": s["name"],
                    "category": s["categories"][0],
                },
            }
            for s in shops
        ],
    }
