import sys
import os
import asyncio
import pytest
from pathlib import Path

sys.path.insert(0, "/app/reachout")
sys.path.insert(0, "/app/reachout/api")
sys.path.insert(0, "/app/reachout/scripts")

from tests.test_api import _client, _seeded_db
import api.server as server
import scripts.db as db

async def test():
    tmp_path = Path("/tmp/debug15")
    tmp_path.mkdir(exist_ok=True)
    monkeypatch = pytest.MonkeyPatch()
    
    db_path = _seeded_db(tmp_path)
    monkeypatch.setattr(server, "DB_PATH", db_path)
    
    import random
    monkeypatch.setattr(random, "random", lambda: 0.1)
    
    from api.event_bus import BUS
    q = BUS.subscribe()
    
    print("BUS ID in test:", id(BUS))
    
    await server.tick_once()
    
    # Check directly inside the file that `api.event_bus.BUS` got it:
    print("BUS ID in test after:", id(BUS))
    print("BUS SUBSCRIBERS:", BUS._subscribers)
    try:
        print("Q:", q.get_nowait())
    except Exception as e:
        print("QE:", type(e))

asyncio.run(test())
