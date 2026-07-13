import sys
import os
import asyncio
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "reachout"))
sys.path.insert(0, os.path.join(HERE, "reachout", "api"))
sys.path.insert(0, os.path.join(HERE, "reachout", "scripts"))

from reachout.tests.test_api import _client, _seeded_db
from reachout.api import server
from reachout.api.event_bus import BUS
import random
import pathlib

async def test():
    tmp_path = pathlib.Path("/tmp/debug4")
    tmp_path.mkdir(exist_ok=True)
    monkeypatch = pytest.MonkeyPatch()
    
    db_path = _seeded_db(tmp_path)
    monkeypatch.setattr(server, "DB_PATH", db_path)
    
    client = _client(tmp_path, monkeypatch)
    q = BUS.subscribe()
    
    monkeypatch.setattr(random, "random", lambda: 0.1)
    monkeypatch.setattr(random, "choice", lambda seq: list(seq)[0])
    
    import sys
    print("SYS PATH:", sys.path)
    
    def my_pub(evt):
        print("PUBLISHING:", evt)
        q.put_nowait(evt)
        
    import reachout.api.event_bus as eb
    monkeypatch.setattr(eb.BUS, "publish", my_pub)
    
    print("CALLING TICK")
    await server.tick_once()
    
    try:
        print("QUEUE GOT:", q.get_nowait())
    except Exception as e:
        print("QUEUE EXCEPTION:", type(e))

asyncio.run(test())
