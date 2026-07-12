"""Thin read-only FastAPI wrapper over run_pipeline.run().

No business logic lives here: every field in a search response is exactly
what run_pipeline's stage 04 (ranked_shops) / stage 05 (GeoJSON) already
produced and schema-validated. Each request gets its own throwaway
output_root so concurrent requests never read or clobber each other's stage
files. The one non-pipeline endpoint (/api/shops.geojson, a static projection
of the shops table) is schema-validated here at request time instead.
"""

import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REACHOUT_DIR = os.path.dirname(HERE)
for _dir in (os.path.join(REACHOUT_DIR, "scripts"), os.path.join(REACHOUT_DIR, "agent"), REACHOUT_DIR):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

from fastapi import FastAPI, HTTPException, Response, Query  # noqa: E402
import math
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

import db  # noqa: E402
import run_pipeline  # noqa: E402
import validate  # noqa: E402

# Overridable in tests (monkeypatch.setattr(server, "DB_PATH", ...)); None
# means run_pipeline falls back to its own defaults (the real reachout.db /
# the real data/notifications/).
DB_PATH = None
NOTIF_DIR = None

app = FastAPI(title="ReachOut API")

# Read-only public API, no credentials: any browser origin may fetch it.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])


@app.get("/api/health")
def health():
    body = {"status": "ok"}
    ok, err = validate.validate(body, "health_response.schema.json")
    if not ok:
        raise HTTPException(status_code=500, detail=f"health_response failed schema: {err}")
    return body


def _run_pipeline(q, near, lat, lng, radius, region=None):
    if region is not None:
        if near is not None or lat is not None or lng is not None:
            raise HTTPException(status_code=400, detail="region cannot be combined with near, lat, or lng")
        
        conn = db.connect(DB_PATH)
        try:
            region_data = db.get_region(conn, region)
        finally:
            conn.close()
            
        if not region_data:
            raise HTTPException(status_code=404, detail=f"Region '{region}' not found")
            
        lat = region_data["lat"]
        lng = region_data["lng"]
        near = None

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
           lng: Optional[float] = None, radius: float = 2.0,
           region: Optional[str] = None,
           page: Optional[int] = Query(None, ge=1),
           page_size: Optional[int] = Query(10, ge=1, le=50)):
    result = _run_pipeline(q, near, lat, lng, radius, region=region)
    ranked = result["ranked_shops"]

    if page is None:
        return ranked

    # Paginate the response based on search_page.schema.json
    if ranked["status"] != "ok":
        # Pass through error/incomplete, but validate as search_page
        ok, err = validate.validate(ranked, "search_page.schema.json")
        if not ok:
            raise HTTPException(status_code=500, detail=f"search_page failed schema: {err}")
        return ranked

    total_results = len(ranked["results"])
    total_pages = math.ceil(total_results / page_size) if total_results > 0 else 0
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    sliced_results = ranked["results"][start_idx:end_idx]

    body = {
        "status": "ok",
        "query": ranked["query"],
        "generated_at": ranked["generated_at"],
        "page": page,
        "page_size": page_size,
        "total_results": total_results,
        "total_pages": total_pages,
        "result_count": len(sliced_results),
        "results": sliced_results,
    }
    
    ok, err = validate.validate(body, "search_page.schema.json")
    if not ok:
        raise HTTPException(status_code=500, detail=f"search_page failed schema: {err}")

    return body


@app.get("/api/search.geojson")
def search_geojson(q: str, near: Optional[str] = None, lat: Optional[float] = None,
                    lng: Optional[float] = None, radius: float = 2.0,
                    region: Optional[str] = None):
    result = _run_pipeline(q, near, lat, lng, radius, region=region)
    return result["geojson"]


@app.get("/api/shops.geojson")
def shops_geojson(response: Response):
    """All known shops, no inventory: the map's network layer. Pure read."""
    conn = db.connect(DB_PATH)
    try:
        shops = db.all_shops(conn)
    finally:
        conn.close()
    features = [
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
        if s["categories"]  # a row with no categories can't be classified; skip it
    ]
    body = {
        "type": "FeatureCollection",
        "metadata": {"shop_count": len(features)},
        "features": features,
    }
    ok, err = validate.validate(body, "shops_geojson.schema.json")
    if not ok:
        raise HTTPException(status_code=500, detail=f"shops_geojson failed schema: {err}")
    # Shop identities change rarely (OSM refresh), unlike inventory: cacheable.
    response.headers["Cache-Control"] = "public, max-age=3600"
    return body


@app.get("/api/inventory")
def inventory(region: Optional[str] = None, page: int = Query(1, ge=1),
              page_size: int = Query(25, ge=1, le=100),
              in_stock: int = Query(0, ge=0, le=1)):
    """Paginated inventory endpoint."""
    conn = db.connect(DB_PATH)
    try:
        if region is not None:
            valid_regions = [r["region_id"] for r in db.all_regions(conn)]
            if region not in valid_regions:
                raise HTTPException(status_code=404, detail=f"Region {region} not found")
        
        items, total_items = db.inventory_page(conn, region, page, page_size, bool(in_stock))
    finally:
        conn.close()
        
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0
    
    body = {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region_id": region,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "items": items,
    }
    
    ok, err = validate.validate(body, "inventory_response.schema.json")
    if not ok:
        raise HTTPException(status_code=500, detail=f"inventory_response failed schema: {err}")
        
    return body


@app.get("/api/regions")
def regions(response: Response):
    """List of all known regions and their shop counts. Pure read."""
    conn = db.connect(DB_PATH)
    try:
        all_regions = db.all_regions(conn)
        shop_counts = db.region_shop_counts(conn)
    finally:
        conn.close()

    regions_list = []
    for r in all_regions:
        regions_list.append({
            "region_id": r["region_id"],
            "name": r["name"],
            "lat": r["lat"],
            "lng": r["lng"],
            "source": r["source"],
            "shop_count": shop_counts.get(r["region_id"], 0),
        })

    body = {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region_count": len(regions_list),
        "regions": regions_list,
    }

    ok, err = validate.validate(body, "regions_response.schema.json")
    if not ok:
        raise HTTPException(status_code=500, detail=f"regions_response failed schema: {err}")

    response.headers["Cache-Control"] = "public, max-age=3600"
    return body
