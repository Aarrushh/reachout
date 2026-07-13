import pytest
from reachout.api import server
from reachout.tests.test_api import _client
from reachout.scripts import db

def test_debug(tmp_path, monkeypatch):
    from reachout.api.event_bus import BUS
    client = _client(tmp_path, monkeypatch)
    q = BUS.subscribe()
    
    conn = db.connect(server.DB_PATH)
    try:
        from reachout.scripts import inventory_simulator
        import reachout.api.event_bus as event_bus
        event = inventory_simulator._tick(conn)
        print("SIM EVENT:", event)
        if event:
            region_id = conn.execute("SELECT region_id FROM shops WHERE shop_id=?", (event["shop_id"],)).fetchone()[0]
            print("REGION ID:", region_id)
            event_bus.BUS.publish(event_bus.to_stock_event(event, region_id))
    finally:
        conn.close()
    
    try:
        print("QUEUE:", q.get_nowait())
    except Exception as e:
        print("QUEUE EXCEPTION:", e)
    
test_debug(pytest.importorskip("pathlib").Path("/tmp"), pytest.importorskip("_pytest.monkeypatch").MonkeyPatch())
