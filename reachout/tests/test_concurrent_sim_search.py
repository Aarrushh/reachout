import threading
import time
import sqlite3

from reachout.scripts import db
from reachout.scripts import search_engine
from reachout.scripts import inventory_simulator
from tests.test_api import _seeded_db

def test_concurrent_sim_search(tmp_path):
    # Setup temporary database
    db_path = _seeded_db(tmp_path)
    
    # Run the simulator in a background thread for 3 seconds
    sim_seconds = 3
    sim_interval = 0.05
    
    stop_event = threading.Event()
    sim_thread = threading.Thread(
        target=inventory_simulator.run_simulator,
        kwargs={"stop_event": stop_event, "seconds": sim_seconds, "interval": sim_interval, "db_path": db_path}
    )
    sim_thread.start()
    
    # In the main thread, hammer the database with reads
    start_time = time.time()
    read_conn = db.connect(db_path)
    
    intent = {
        "status": "ok",
        "keywords": ["paracetamol"],
        "category_hints": ["pharmacy"]
    }
    
    geo_shops = {
        "status": "ok",
        "shops": [{
            "shop_id": "osm:node:1001",
            "name": "Farmacia Malasaña",
            "categories": ["pharmacy"],
            "address": "Calle del Pez 1",
            "lat": 40.4270,
            "lng": -3.7035,
            "distance_km": 1.0,
            "distance_type": "haversine"
        }]
    }
    
    # db.inventory_page requires region_id if filtering by region
    region_id = "malasana"
    
    reads_performed = 0
    
    try:
        while (time.time() - start_time) < sim_seconds:
            # 1. Read inventory page
            rows, total = db.inventory_page(read_conn, region_id=region_id, page=1, page_size=10)
            
            # Assert internal consistency
            assert total >= len(rows), f"Total {total} < len(rows) {len(rows)}"
            
            # 2. Run a search
            search_results = search_engine.search(intent, geo_shops, db_path=db_path, do_ping=False)
            
            # Basic check that search results is well-formed
            assert search_results.get("status") in ["ok", "incomplete", "error"]
            
            reads_performed += 1
            # Small sleep to prevent tight loop from starving the simulator thread,
            # though WAL should handle it gracefully
            time.sleep(0.01)
    finally:
        stop_event.set()
        sim_thread.join(timeout=sim_seconds + 2)
        read_conn.close()
        
    assert reads_performed > 0, "No reads were performed during the test"
    assert not sim_thread.is_alive(), "Simulator thread did not exit cleanly"

