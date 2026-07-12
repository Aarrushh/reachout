"""
Event bus for fanning out simulator events to connected clients.

Uses a simple singleton pattern with a set of asyncio.Queue instances. 
If a client queue is full, the oldest event is dropped to avoid
blocking the simulator or other clients.
"""
import asyncio

from reachout.scripts import db, validate


def to_stock_event(raw: dict, region_id: str | None) -> dict:
    """Shape a raw simulator event into a valid stock_event schema.
    
    Raises ValueError if the shaped event fails schema validation.
    """
    event = {
        "type": raw["type"],
        "shop_id": raw["shop_id"],
        "shop_name": raw["shop"],
        "region_id": region_id,
        "sku": raw["sku"],
        "name": raw["name"],
        "qty_now": raw["qty_now"],
        "ts": db.now_iso(raw["epoch"]) if "epoch" in raw else db.now_iso(),
    }
    
    if "sold" in raw:
        event["sold"] = raw["sold"]
    if "added" in raw:
        event["added"] = raw["added"]
        
    ok, err = validate.validate(event, "stock_event.schema.json")
    if not ok:
        raise ValueError(f"Invalid stock event: {err}")
        
    return event


class EventBus:
    """In-memory publish-subscribe event bus."""

    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Create and return a new queue for a subscriber."""
        q = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber's queue."""
        self._subscribers.discard(q)

    def publish(self, event: dict) -> None:
        """Fan out an event to all subscribers, dropping oldest if full."""
        # Iterate over a copy or standard iterate, no await here so safe to iterate set directly
        # However, to be extra safe against modifications during iteration, copy is fine.
        # But single thread asyncio loop with no await inside the loop means safe.
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    # Drop the oldest event to make room
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                
                try:
                    # Try putting it again
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass


# Singleton instance
BUS = EventBus()
