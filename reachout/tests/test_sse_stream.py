"""Tests for the /api/inventory/stream SSE endpoint (TASK 37).

httpx's ASGITransport awaits the ASGI app to completion before returning a
response, so an unbounded SSE stream would hang the test. Each test therefore
wraps server.app so the client can inject an ``http.disconnect`` once the
expected events have been published; starlette then cancels the generator
(running its ``finally``/unsubscribe) and the buffered frames are parsed.
"""
import asyncio
import json

import httpx
import pytest
import validate as v

import server


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


RAW_SALE = {
    "type": "sale",
    "shop_id": "osm:node:1001",
    "shop": "Farmacia Malasaña",
    "sku": "PHA-0001",
    "name": "Paracetamol 1g 40 comprimidos",
    "sold": 2,
    "qty_now": 8,
}


class _DisconnectableApp:
    """Wrap an ASGI app: receive() reports http.disconnect once the event is
    set, and a final empty body message is guaranteed so ASGITransport's
    response-complete assertion holds even when starlette cancels the stream."""

    def __init__(self, app, disconnect: asyncio.Event):
        self._app = app
        self._disconnect = disconnect

    async def __call__(self, scope, receive, send):
        sent_complete = False
        request_delivered = False

        async def _receive():
            nonlocal request_delivered
            if not request_delivered:
                request_delivered = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await self._disconnect.wait()
            return {"type": "http.disconnect"}

        async def _send(message):
            nonlocal sent_complete
            if (message["type"] == "http.response.body"
                    and not message.get("more_body", False)):
                sent_complete = True
            await send(message)

        try:
            await self._app(scope, _receive, _send)
        finally:
            if not sent_complete:
                await send({"type": "http.response.body", "body": b"",
                            "more_body": False})


def _parse_frames(text: str) -> list[dict]:
    """Parse SSE wire text into [{'event': ..., 'data': ...}] frames,
    ignoring comment/keep-alive lines."""
    frames = []
    for block in text.split("\n\n"):
        frame = {}
        for line in block.split("\n"):
            if line.startswith("event:"):
                frame["event"] = line[len("event:"):].strip()
            elif line.startswith("data:"):
                frame["data"] = line[len("data:"):].strip()
        if frame:
            frames.append(frame)
    return frames


async def _stream_session(url: str, publish):
    """Open the SSE endpoint, wait for it to subscribe, run ``publish``,
    disconnect, and return (frames, baseline_count, count_while_open)."""
    disconnect = asyncio.Event()
    transport = httpx.ASGITransport(app=_DisconnectableApp(server.app, disconnect))
    bus = _event_bus().BUS
    baseline = set(bus._subscribers)
    status = {}

    async def fetch():
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://test") as client:
            async with client.stream("GET", url) as resp:
                status["code"] = resp.status_code
                status["content_type"] = resp.headers.get("content-type", "")
                chunks = [chunk async for chunk in resp.aiter_text()]
        return "".join(chunks)

    task = asyncio.create_task(fetch())
    # Wait (bounded) until the endpoint's generator has registered its queue.
    deadline = asyncio.get_running_loop().time() + 5.0
    while not (bus._subscribers - baseline):
        if task.done():
            task.result()  # surfaces the real exception from fetch()
            raise AssertionError("stream request finished without subscribing")
        if asyncio.get_running_loop().time() > deadline:
            task.cancel()
            raise AssertionError("stream endpoint never subscribed to BUS")
        await asyncio.sleep(0.005)
    new_q = next(iter(bus._subscribers - baseline))
    count_while_open = len(bus._subscribers)

    await publish()
    # Let the generator drain the queue and yield the frames.
    drain_deadline = asyncio.get_running_loop().time() + 5.0
    while not new_q.empty():
        assert asyncio.get_running_loop().time() < drain_deadline, \
            "stream generator never drained published events"
        await asyncio.sleep(0.005)
    await asyncio.sleep(0.05)

    disconnect.set()
    body = await asyncio.wait_for(task, timeout=10)
    assert status["code"] == 200
    assert status["content_type"].startswith("text/event-stream")
    return _parse_frames(body), len(baseline), count_while_open


def test_hello_frame_arrives():
    async def _test():
        async def publish():
            pass

        frames, _, _ = await _stream_session("/api/inventory/stream", publish)
        assert frames, "no SSE frames received"
        hello = frames[0]
        assert hello["event"] == "hello"
        assert json.loads(hello["data"]) == {"region": None}
    asyncio.run(_test())

def test_published_event_is_received_and_schema_valid():
    async def _test():
        event = _event_bus().to_stock_event(dict(RAW_SALE), "malasana")

        async def publish():
            _event_bus().BUS.publish(event)

        frames, _, _ = await _stream_session("/api/inventory/stream", publish)
        stock = [f for f in frames if f.get("event") == "stock"]
        assert len(stock) == 1
        received = json.loads(stock[0]["data"])
        assert received == event
        ok, err = v.validate(received, "stock_event.schema.json")
        assert ok, err
    asyncio.run(_test())

def test_region_filter_drops_mismatches():
    async def _test():
        matching = _event_bus().to_stock_event(dict(RAW_SALE), "malasana")
        mismatching = _event_bus().to_stock_event(dict(RAW_SALE), "chueca")

        async def publish():
            _event_bus().BUS.publish(mismatching)
            _event_bus().BUS.publish(matching)

        frames, _, _ = await _stream_session(
            "/api/inventory/stream?region=malasana", publish)
        hello = frames[0]
        assert json.loads(hello["data"]) == {"region": "malasana"}
        stock = [json.loads(f["data"]) for f in frames if f.get("event") == "stock"]
        assert stock == [matching], "mismatched-region event should be dropped"
    asyncio.run(_test())

def test_disconnect_removes_subscriber():
    async def _test():
        async def publish():
            pass

        frames, baseline, while_open = await _stream_session(
            "/api/inventory/stream", publish)
        assert while_open == baseline + 1
        # The generator's finally block must have unsubscribed by stream end.
        bus = _event_bus().BUS
        for _ in range(50):
            if len(bus._subscribers) == baseline:
                break
            await asyncio.sleep(0.02)
        assert len(bus._subscribers) == baseline
    asyncio.run(_test())
