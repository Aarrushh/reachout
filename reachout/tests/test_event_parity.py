import asyncio
import json

import pytest

from api import server
from scripts import inventory_simulator
from tests.test_api import _seeded_db

def _event_bus():
    """Resolve "api.event_bus" at call time, exactly as the endpoint's lazy
    import does. Binding BUS at collection time would break: the module can
    exist under two paths (api.event_bus / reachout.api.event_bus) with
    separate BUS singletons, and test_api.py rebinds sys.modules mid-suite."""
    import importlib
    import sys
    if "api.event_bus" in sys.modules:
        return sys.modules["api.event_bus"]
    return importlib.import_module("api.event_bus")

def test_event_parity(tmp_path, monkeypatch):
    """Run 30 ticks on a temp DB, verify SSE events match jsonl lines."""
    async def _test():
        # Setup paths
        db_path = _seeded_db(tmp_path)
        events_path = tmp_path / "events.jsonl"
        
        # Mock global variables
        monkeypatch.setattr(server, "DB_PATH", db_path)
        monkeypatch.setattr(inventory_simulator, "EVENTS_PATH", str(events_path))

        bus_module = _event_bus()
        bus = bus_module.BUS
        q = bus.subscribe()
        
        # We use server.tick_once() to invoke the simulator exactly like production does
        # Tick 30 times
        for _ in range(30):
            await server.tick_once()

        bus.unsubscribe(q)

        # Collect all SSE events
        sse_events = []
        while not q.empty():
            try:
                sse_events.append(q.get_nowait())
            except asyncio.QueueEmpty:
                break

        # Read JSONL file
        jsonl_events = []
        if events_path.exists():
            with open(events_path, "r") as f:
                for line in f:
                    if line.strip():
                        jsonl_events.append(json.loads(line))

        # Assert Parity
        assert len(sse_events) == len(jsonl_events), "Mismatched event counts between SSE and jsonl streams"
        
        for sse, jnl in zip(sse_events, jsonl_events):
            assert sse["sku"] == jnl["sku"]
            assert sse["type"] == jnl["type"]
            assert sse["qty_now"] == jnl["qty_now"]
            
    asyncio.run(_test())
