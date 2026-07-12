import asyncio
from unittest.mock import patch
import pytest

from reachout.api.event_bus import EventBus


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_event_bus_fanout(bus):
    q1 = bus.subscribe()
    q2 = bus.subscribe()

    event = {"type": "test", "data": 123}
    bus.publish(event)

    assert await q1.get() == event
    assert await q2.get() == event


@pytest.mark.asyncio
async def test_event_bus_drop_oldest(bus):
    q = bus.subscribe()

    # Fill the queue
    for i in range(100):
        bus.publish({"id": i})

    assert q.qsize() == 100

    # Publish one more item to force dropping the oldest
    bus.publish({"id": 100})

    assert q.qsize() == 100

    # The first item (id: 0) should be dropped, so the next should be id: 1
    first_item = await q.get()
    assert first_item == {"id": 1}

    # Consume remaining and check the last one
    for _ in range(98):
        await q.get()
    
    last_item = await q.get()
    assert last_item == {"id": 100}

@pytest.mark.asyncio
async def test_event_bus_drop_oldest_race_conditions(bus):
    q = bus.subscribe()
    
    # Fill the queue
    for i in range(100):
        bus.publish({"id": i})
        
    # Mock get_nowait to raise QueueEmpty
    with patch.object(q, 'get_nowait', side_effect=asyncio.QueueEmpty):
        # We need to force a QueueFull to reach the QueueEmpty exception block.
        # But putting an item into a full queue raises QueueFull.
        # Then get_nowait is called, which we mocked to raise QueueEmpty.
        # Then put_nowait is called again.
        # If we just let it call put_nowait again, it'll raise QueueFull again.
        bus.publish({"id": 101})

@pytest.mark.asyncio
async def test_event_bus_unsubscribe(bus):
    q = bus.subscribe()
    
    bus.publish({"id": 1})
    assert await q.get() == {"id": 1}
    
    bus.unsubscribe(q)
    
    bus.publish({"id": 2})
    assert q.qsize() == 0


def test_to_stock_event_sale():
    from reachout.api.event_bus import to_stock_event
    
    raw = {
        "type": "sale",
        "shop_id": "osm:node:123",
        "shop": "Test Shop",
        "sku": "PHA-0001",
        "name": "Aspirin",
        "sold": 2,
        "qty_now": 8
    }
    
    with patch('reachout.api.event_bus.db.now_iso', return_value='2024-01-01T12:00:00+00:00'):
        event = to_stock_event(raw, "madrid-centro")
        
    assert event["type"] == "sale"
    assert event["shop_id"] == "osm:node:123"
    assert event["shop_name"] == "Test Shop"
    assert event["region_id"] == "madrid-centro"
    assert event["sku"] == "PHA-0001"
    assert event["name"] == "Aspirin"
    assert event["sold"] == 2
    assert event["qty_now"] == 8
    assert event["ts"] == "2024-01-01T12:00:00+00:00"


def test_to_stock_event_restock():
    from reachout.api.event_bus import to_stock_event
    
    raw = {
        "type": "restock",
        "shop_id": "osm:node:123",
        "shop": "Test Shop",
        "sku": "PHA-0001",
        "name": "Aspirin",
        "added": 10,
        "qty_now": 18
    }
    
    with patch('reachout.api.event_bus.db.now_iso', return_value='2024-01-01T12:00:00+00:00'):
        event = to_stock_event(raw, None)
        
    assert event["type"] == "restock"
    assert event["shop_id"] == "osm:node:123"
    assert event["shop_name"] == "Test Shop"
    assert event["region_id"] is None
    assert event["sku"] == "PHA-0001"
    assert event["name"] == "Aspirin"
    assert event["added"] == 10
    assert event["qty_now"] == 18
    assert event["ts"] == "2024-01-01T12:00:00+00:00"


def test_to_stock_event_new_item():
    from reachout.api.event_bus import to_stock_event
    
    raw = {
        "type": "new_item",
        "shop_id": "osm:node:123",
        "shop": "Test Shop",
        "sku": "PHA-0001",
        "name": "Aspirin",
        "qty_now": 10,
        "source": "template"
    }
    
    with patch('reachout.api.event_bus.db.now_iso', return_value='2024-01-01T12:00:00+00:00'):
        event = to_stock_event(raw, "madrid-centro")
        
    assert event["type"] == "new_item"
    assert event["shop_id"] == "osm:node:123"
    assert event["shop_name"] == "Test Shop"
    assert event["region_id"] == "madrid-centro"
    assert event["sku"] == "PHA-0001"
    assert event["name"] == "Aspirin"
    assert event["qty_now"] == 10
    assert event["ts"] == "2024-01-01T12:00:00+00:00"
    assert "sold" not in event
    assert "added" not in event


def test_to_stock_event_invalid_raises():
    from reachout.api.event_bus import to_stock_event
    
    raw = {
        "type": "sale",
        "shop_id": "osm:node:123",
        "shop": "Test Shop",
        "sku": "PHA-0001",
        "name": "Aspirin",
        "sold": -1,  # Invalid: minimum is 1
        "qty_now": 8
    }
    
    with pytest.raises(ValueError, match="Invalid stock event"):
        to_stock_event(raw, "madrid-centro")
