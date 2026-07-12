"""Region seeder from the local gazetteer."""

import json
import os
import unicodedata

from . import db
from . import geo

def _slugify(text: str) -> str:
    """Lowercase, strip accents, and convert spaces to dashes."""
    text = text.lower()
    # Normalize accents
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    text = text.replace(" ", "-")
    return text

def seed_regions(conn, gazetteer_path=None):
    """Seed regions from gazetteer into the database."""
    if gazetteer_path is None:
        gazetteer_path = os.path.join(os.path.dirname(__file__), "..", "data", "gazetteer_madrid.json")
    
    with open(gazetteer_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for key, val in data.items():
        if key == "_comment":
            continue
            
        region_id = _slugify(key)
        
        region = {
            "region_id": region_id,
            "name": key.title(),
            "lat": val["lat"],
            "lng": val["lng"],
            "source": "gazetteer",
            "created_at": db.now_iso()
        }
        
        db.upsert_region(conn, region)

def assign_shops(conn, max_km=1.2):
    """Assigns each shop to the nearest region centroid within max_km.
    
    SUGGESTION: nearest-centroid is a crude proxy for real barrio polygons.
    It is good enough for the demo, and polygon data would require a new 
    dependency (shapely) which we do not want to introduce here.
    """
    regions = db.all_regions(conn)
    shops = db.all_shops(conn)
    
    assigned = 0
    unassigned = 0
    
    for shop in shops:
        best_region = None
        best_dist = float('inf')
        
        for region in regions:
            dist = geo.haversine_km(shop["lat"], shop["lng"], region["lat"], region["lng"])
            if dist < best_dist:
                best_dist = dist
                best_region = region
                
        if best_region is not None and best_dist <= max_km:
            conn.execute(
                "UPDATE shops SET region_id=? WHERE shop_id=?", 
                (best_region["region_id"], shop["shop_id"])
            )
            assigned += 1
        else:
            conn.execute(
                "UPDATE shops SET region_id=NULL WHERE shop_id=?", 
                (shop["shop_id"],)
            )
            unassigned += 1
            
    conn.commit()
    
    return {"assigned": assigned, "unassigned": unassigned}
