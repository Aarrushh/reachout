import sys
import os
import asyncio
import pytest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "reachout"))

from reachout.tests.test_api import _client, _seeded_db
from reachout.api import server
import db

async def test():
    tmp_path = Path("/tmp/debug5")
    tmp_path.mkdir(exist_ok=True)
    monkeypatch = pytest.MonkeyPatch()
    
    db_path = _seeded_db(tmp_path)
    monkeypatch.setattr(server, "DB_PATH", db_path)
    
    conn = db.connect(db_path)
    try:
        from reachout.scripts import inventory_simulator
        import reachout.api.event_bus as eb
        
        import random
        monkeypatch.setattr(random, "random", lambda: 0.1)
        
        print("SHOPS:", db.all_shops(conn))
        print("ITEMS:", db.items_for_shop(conn, "osm:node:1001", in_stock_only=True))
        
        event = inventory_simulator._tick(conn)
        print("EVENT PRODUCED:", event)
    finally:
        conn.close()

asyncio.run(test())
