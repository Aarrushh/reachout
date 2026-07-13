import sys
import os
import asyncio
from pathlib import Path
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from reachout.tests.test_api import _client
from reachout.api import server
from reachout.api.event_bus import BUS
from reachout.scripts import db

async def run_test():
    tmp_path = Path("/tmp/debug")
    tmp_path.mkdir(exist_ok=True)
    monkeypatch = pytest.MonkeyPatch()
    
    client = _client(tmp_path, monkeypatch)
    q = BUS.subscribe()
    
    for _ in range(10):
        server._sync_tick()
        try:
            event = q.get_nowait()
            print("EVENT FOUND:", event)
            break
        except asyncio.QueueEmpty:
            print("Empty Queue")

asyncio.run(run_test())
