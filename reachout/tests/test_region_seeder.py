import json
import os

from reachout.scripts import db
from reachout.scripts.region_seeder import seed_regions, assign_shops

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

def test_assign_shops(tmp_path):
    # Setup DB
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.connect(db_path)
    
    # 1. Insert a region at known coordinates
    # Let's use lat=0.0, lng=0.0 for simplicity
    central_region = {
        "region_id": "center",
        "name": "Center",
        "lat": 0.0,
        "lng": 0.0,
        "source": "test",
        "created_at": db.now_iso()
    }
    db.upsert_region(conn, central_region)
    
    # 2. Insert shops at known offsets
    # 1 degree of latitude is ~111km, so 0.01 degree is ~1.11km
    
    # Shop 1: Inside radius (e.g. at 0.0, 0.0 distance = 0km)
    db.upsert_shop(conn, {
        "shop_id": "s1",
        "osm_id": 1,
        "name": "Inside",
        "categories": ["pharmacy"],
        "lat": 0.0,
        "lng": 0.0,
        "address": None,
        "source": "test",
        "fetched_at": db.now_iso(),
    })
    
    # Shop 2: Boundary case (just inside max_km=1.2)
    # Using lat=0.01, lng=0.0 -> ~1.11 km away
    db.upsert_shop(conn, {
        "shop_id": "s2",
        "osm_id": 2,
        "name": "Boundary",
        "categories": ["pharmacy"],
        "lat": 0.01,
        "lng": 0.0,
        "address": None,
        "source": "test",
        "fetched_at": db.now_iso(),
    })
    
    # Shop 3: Outside radius (max_km=1.2)
    # Using lat=0.02, lng=0.0 -> ~2.22 km away
    db.upsert_shop(conn, {
        "shop_id": "s3",
        "osm_id": 3,
        "name": "Outside",
        "categories": ["pharmacy"],
        "lat": 0.02,
        "lng": 0.0,
        "address": None,
        "source": "test",
        "fetched_at": db.now_iso(),
    })
    
    # 3. Call assign_shops
    res = assign_shops(conn, max_km=1.2)
    
    # 4. Verify results
    assert res == {"assigned": 2, "unassigned": 1}
    
    shops = db.all_shops(conn)
    shop_dict = {s["shop_id"]: s for s in shops}
    
    assert shop_dict["s1"]["region_id"] == "center"
    assert shop_dict["s2"]["region_id"] == "center"
    assert shop_dict["s3"]["region_id"] is None
