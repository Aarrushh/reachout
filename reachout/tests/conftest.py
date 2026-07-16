import os
import sys
import pytest
import requests

from fake_supa import FakeSupabase

@pytest.fixture
def fake_supa():
    """Returns the FakeSupabase class for testing."""
    return FakeSupabase

@pytest.fixture(autouse=True)
def block_network_if_offline(monkeypatch):
    """Enforce offline isolation for tests.
    
    If REACHOUT_OFFLINE=1 is set, blocks any network calls via requests.
    Raises RuntimeError to fail the test immediately.
    """
    if os.environ.get("REACHOUT_OFFLINE") == "1":
        def block_request(*args, **kwargs):
            raise RuntimeError(f"Network calls are blocked in offline mode! Blocked call to: {args}")
        monkeypatch.setattr(requests, "get", block_request)
        monkeypatch.setattr(requests, "post", block_request)
        monkeypatch.setattr(requests, "put", block_request)
        monkeypatch.setattr(requests, "patch", block_request)
        monkeypatch.setattr(requests, "delete", block_request)

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent"))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

REACHOUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REACHOUT_DIR not in sys.path:
    sys.path.insert(0, REACHOUT_DIR)

API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api"))
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)
