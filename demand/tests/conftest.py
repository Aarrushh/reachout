import os
import sys

import httpx
import pytest
import requests

# The repo root is the ONLY entry this suite adds to sys.path, so every module
# in the workspace has exactly one importable name: its `demand.` package path.
#
# demand/, demand/ingest, demand/scripts, demand/api and demand/tests are
# deliberately absent. When they were present the same file could be imported
# twice under two names -- `ingest.trends_client` and
# `demand.ingest.trends_client` -- which load as two distinct module objects
# carrying two distinct SerpApiProvider classes. A test that monkeypatched
# `fetch` on one copy left the other holding the real one: a live billed
# SerpApi call wearing the costume of a mocked test. See demand/__init__.py,
# which stops pytest from re-adding demand/ on its own.
REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from demand.tests.fake_supa import FakeSupabase  # noqa: E402


@pytest.fixture
def fake_supa():
    """Returns the FakeSupabase class for testing."""
    return FakeSupabase

@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """No test may reach a socket, and no test may see the live API key.

    UNCONDITIONAL, not gated on `REACHOUT_OFFLINE=1`. The gated version of
    this fixture was a safety net that was switched off by default, on a
    suite where one un-mocked call costs real money: SerpApi bills per
    search out of a 250/month budget.

    Three separate holes are closed here.

    1. `httpx`, not just `requests`. `demand/ingest/serpapi_client.py` --
       the only paid path in the workspace -- is an `httpx` caller, so the
       old `requests`-only guard was blind to the exact module that spends.

    2. The key itself. `demand/api/app.py` calls `load_dotenv` at module
       import time, and `demand/scripts/run_ingest.py` imports it, so
       importing anything in the chain injects a real `SERPAPI_API_KEY`
       into `os.environ` for the whole session -- which makes
       `get_provider("serpapi")` return a fully armed live provider inside
       pytest. Deleting it means a test that slips past the transport guard
       fails with "SERPAPI_API_KEY not set" instead of billing. Tests that
       genuinely need a key set a fake one themselves (see
       `test_serpapi_provider.py`, which passes `api_key="KEY"` directly).

    3. `TestClient` still works. The block lands on
       `httpx.HTTPTransport.handle_request` -- the transport that opens a
       socket -- not on `httpx.Client.send`. `fastapi.testclient.TestClient`
       is an `httpx.Client` over `ASGITransport`, so it never touches the
       blocked path and the API suite runs untouched.
    """
    def block(*args, **kwargs):
        raise RuntimeError(
            "Network calls are blocked in the demand test suite. "
            "Monkeypatch the provider or the transport instead."
        )

    async def block_async(*args, **kwargs):
        block()

    for verb in ("get", "post", "put", "patch", "delete", "head",
                 "options", "request", "stream"):
        monkeypatch.setattr(requests, verb, block, raising=False)
        monkeypatch.setattr(httpx, verb, block, raising=False)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", block)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request",
                        block_async)

    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
