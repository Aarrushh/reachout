"""The guard that stands between `pytest` and a billed SerpApi search.

Two facts made this necessary. `demand/api/app.py` calls `load_dotenv` at
module import time, and every test that imports `run_ingest` pulls that in
transitively -- so a developer machine with `reachout/.env` present has a
fully armed 64-character `SERPAPI_API_KEY` sitting in `os.environ` for the
whole session. And the only network guard the suite had blocked `requests`,
while the SerpApi transport uses `httpx`. One test forgetting to monkeypatch
`fetch` was one line away from spending real budget inside a test run.

These tests assert the guard itself, so the guard cannot quietly rot.
"""

import os

import httpx
import pytest
import requests


def test_the_api_key_is_not_visible_to_tests():
    """`load_dotenv` at import time must not arm the live provider here.

    Vacuous on a machine with no `reachout/.env` (the Jules VMs, CI). Not
    vacuous on a developer machine, which is exactly where the money is.
    """
    assert os.environ.get("SERPAPI_API_KEY") is None


def test_httpx_module_level_get_is_blocked():
    # `serpapi_client.fetch` calls exactly this.
    with pytest.raises(RuntimeError, match="Network calls are blocked"):
        httpx.get("https://serpapi.com/search")


def test_httpx_client_transport_is_blocked():
    # Belt and braces: anything that builds its own Client still cannot
    # reach a socket.
    with pytest.raises(RuntimeError, match="Network calls are blocked"):
        httpx.Client().get("https://serpapi.com/search")


def test_requests_is_still_blocked():
    with pytest.raises(RuntimeError, match="Network calls are blocked"):
        requests.get("https://serpapi.com/search")


def test_the_fastapi_test_client_still_works():
    """The guard blocks the real transport, not ASGI in-process calls.

    `fastapi.testclient.TestClient` is an `httpx.Client` over
    `ASGITransport`. Blocking `httpx.Client.send` wholesale would take the
    whole API test suite down with it, so the guard blocks
    `HTTPTransport.handle_request` -- the one that opens a socket.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    assert TestClient(app).get("/ping").json() == {"ok": True}
