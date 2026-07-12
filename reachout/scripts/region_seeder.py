"""Region seeder from the local gazetteer."""

import json
import os
import unicodedata

from . import db

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
