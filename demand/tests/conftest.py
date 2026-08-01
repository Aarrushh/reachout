import os
import sys

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
def block_network_if_offline(monkeypatch):
    """Enforce offline isolation for tests.

    If REACHOUT_OFFLINE=1 is set (the same repo-wide offline flag
    reachout/tests/conftest.py honors), blocks any network calls via
    requests. Raises RuntimeError to fail the test immediately.
    """
    if os.environ.get("REACHOUT_OFFLINE") == "1":
        def block_request(*args, **kwargs):
            raise RuntimeError(f"Network calls are blocked in offline mode! Blocked call to: {args}")
        monkeypatch.setattr(requests, "get", block_request)
        monkeypatch.setattr(requests, "post", block_request)
        monkeypatch.setattr(requests, "put", block_request)
        monkeypatch.setattr(requests, "patch", block_request)
        monkeypatch.setattr(requests, "delete", block_request)
