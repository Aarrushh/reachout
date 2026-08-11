import os
import sys

import httpx
import pytest
import requests

# demand/tests/ carries an __init__.py (unlike reachout/tests/), so pytest's
# default "prepend" import mode puts demand/ (the first parent dir without an
# __init__.py) on sys.path, not tests/ itself. Insert tests/ explicitly,
# before anything below tries to import a sibling module by bare name.
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from fake_supa import FakeSupabase

DEMAND_DIR = os.path.abspath(os.path.join(TESTS_DIR, ".."))
if DEMAND_DIR not in sys.path:
    sys.path.insert(0, DEMAND_DIR)

INGEST_DIR = os.path.abspath(os.path.join(TESTS_DIR, "..", "ingest"))
if INGEST_DIR not in sys.path:
    sys.path.insert(0, INGEST_DIR)

SCRIPTS_DIR = os.path.abspath(os.path.join(TESTS_DIR, "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

API_DIR = os.path.abspath(os.path.join(TESTS_DIR, "..", "api"))
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

REPO_ROOT = os.path.abspath(os.path.join(TESTS_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


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
