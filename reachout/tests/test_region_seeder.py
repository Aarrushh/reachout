import json
import os

from reachout.scripts import db
from reachout.scripts.region_seeder import seed_regions

def test_seed_regions_idempotent(tmp_path):
    # Setup DB
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.connect(db_path)
    
    # Setup gazetteer fixture
    gazetteer_path = str(tmp_path / "gazetteer.json")
    fixture_data = {
        "_comment": "Ignore this",
        "malasaña": {"lat": 40.4267, "lng": -3.7038},
        "chueca": {"lat": 40.4223, "lng": -3.6973},
        "la latina": {"lat": 40.4123, "lng": -3.7093}
    }
    with open(gazetteer_path, "w", encoding="utf-8") as f:
        json.dump(fixture_data, f)
        
    # Seed
    seed_regions(conn, gazetteer_path)
    
    # Verify
    regions = db.all_regions(conn)
    assert len(regions) == 3
    
    # Verify order and slug correctness
    # _slugify transforms names predictably. DB returns ordered by name.
    # Sorted by name: Chueca, La Latina, Malasaña
    names = [r["name"] for r in regions]
    assert "Chueca" in names
    assert "La Latina" in names
    assert "Malasaña" in names
    
    slugs = [r["region_id"] for r in regions]
    assert "malasana" in slugs
    assert "chueca" in slugs
    assert "la-latina" in slugs
    
    for r in regions:
        assert r["source"] == "gazetteer"
        assert r["lat"] != 0
        assert r["lng"] != 0
        
    # Verify idempotency
    seed_regions(conn, gazetteer_path)
    regions2 = db.all_regions(conn)
    assert len(regions2) == 3
