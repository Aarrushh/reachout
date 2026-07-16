import json
import pytest
from tests.test_api import _client
from tests.fake_supa import FakeSupabase, FakeRPCBuilder

# Canned mock data
_FIXED_EMBEDDING = [0.1] * 768

_MOCK_STORES = [
    {
        "id": "s1",
        "name": "Pizza Planet",
        "neighbourhood": "sol",
        "avg_delivery_mins": 30,
        "is_open": True,
        "rating": 4.8
    }
]

_MOCK_PRODUCTS = [
    {
        "id": "p1",
        "store_id": "s1",
        "name": "Pepperoni Pizza",
        "description": "Delicious pepperoni",
        "category": "food",
        "price": 12.99,
        "stock_qty": 5,
        "tags": ["pizza", "hot"]
    }
]

class SpyRPCBuilder(FakeRPCBuilder):
    def __init__(self, data, name, params, spy_list):
        super().__init__(data)
        self.name = name
        self.params = params
        spy_list.append({"name": name, "params": params})

class SpyFakeSupabase(FakeSupabase):
    def __init__(self, tables=None, rpcs=None, spy_list=None):
        super().__init__(tables, rpcs)
        self.spy_list = spy_list if spy_list is not None else []

    def rpc(self, name, params=None):
        return SpyRPCBuilder(self.rpcs.get(name, []), name, params, self.spy_list)

@pytest.fixture
def mock_gemini_embed(monkeypatch):
    def _embed_query(text):
        return _FIXED_EMBEDDING
    monkeypatch.setattr("api.search.gemini.embed_query", _embed_query)

@pytest.fixture
def mock_gemini_chat(monkeypatch):
    def _chat(*args, **kwargs):
        # Return canned intent JSON string
        return json.dumps({
            "item_name": "pizza",
            "item_type": "food",
            "brand_hint": None,
            "location": "sol"  # Intent says 'sol'
        })
    monkeypatch.setattr("api.search.gemini.chat", _chat)

@pytest.fixture
def rpc_spy():
    return []

@pytest.fixture
def mock_supa_client(monkeypatch, rpc_spy):
    def _get_client():
        return SpyFakeSupabase(
            tables={"stores": _MOCK_STORES},
            rpcs={"match_products": _MOCK_PRODUCTS},
            spy_list=rpc_spy
        )
    monkeypatch.setattr("api.search.get_client", _get_client)

def test_search_happy_path(tmp_path, monkeypatch, mock_gemini_embed, mock_gemini_chat, mock_supa_client, rpc_spy):
    client = _client(tmp_path, monkeypatch)
    
    resp = client.post("/api/search", json={"query": "pizza"})
    assert resp.status_code == 200
    data = resp.json()
    
    # Assert interpreted_as string
    assert data["interpreted_as"] == "pizza near Sol"
    
    # Assert results list
    results = data["results"]
    assert len(results) == 1
    res = results[0]
    assert res["name"] == "Pepperoni Pizza"
    
    # Assert store fields attached
    assert res["store_name"] == "Pizza Planet"
    assert res["avg_delivery_mins"] == 30
    assert res["store_rating"] == 4.8
    assert res["store_is_open"] is True

def test_search_precedence(tmp_path, monkeypatch, mock_gemini_embed, mock_gemini_chat, mock_supa_client, rpc_spy):
    # Explicit neighbourhood param wins over intent location
    client = _client(tmp_path, monkeypatch)
    
    # Send accent-less, lowercase param
    resp = client.post("/api/search", json={"query": "pizza", "neighbourhood": "malasana"})
    assert resp.status_code == 200
    
    # The RPC should receive p_neighbourhood == the request param, accent-normalized
    assert len(rpc_spy) == 1
    rpc_call = rpc_spy[0]
    assert rpc_call["name"] == "match_products"
    assert rpc_call["params"]["p_neighbourhood"] == "Malasaña"
    
    data = resp.json()
    assert data["interpreted_as"] == "pizza near Malasaña"

def test_search_empty_query(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    
    resp = client.post("/api/search", json={"query": "  "})
    assert resp.status_code == 400
    assert "query must be non-empty" in resp.json()["detail"]

def test_search_empty_results(tmp_path, monkeypatch, mock_gemini_embed, mock_gemini_chat):
    client = _client(tmp_path, monkeypatch)
    
    # Mock supa client to return empty match_products
    def _get_client_empty():
        return FakeSupabase(
            tables={"stores": _MOCK_STORES},
            rpcs={"match_products": []}
        )
    monkeypatch.setattr("api.search.get_client", _get_client_empty)
    
    resp = client.post("/api/search", json={"query": "pizza"})
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["results"] == []
    assert data["interpreted_as"] == "pizza near Sol"


from api.gemini import GeminiError

def test_search_embed_failure(tmp_path, monkeypatch, mock_gemini_chat, mock_supa_client, rpc_spy):
    def _embed_fail(text):
        raise GeminiError("embed fail")
    monkeypatch.setattr("api.search.gemini.embed_query", _embed_fail)
    
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/api/search", json={"query": "pizza"})
    assert resp.status_code == 502
    assert "embed fail" in resp.json()["detail"]

def test_search_rpc_failure(tmp_path, monkeypatch, mock_gemini_embed, mock_gemini_chat):
    class FakeRPCErrorSupabase(FakeSupabase):
        def rpc(self, name, params=None):
            raise Exception("rpc fail")

    monkeypatch.setattr("api.search.get_client", FakeRPCErrorSupabase)
    
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/api/search", json={"query": "pizza"})
    assert resp.status_code == 502
    assert "rpc fail" in resp.json()["detail"]

def test_search_attach_stores_failure(tmp_path, monkeypatch, mock_gemini_embed, mock_gemini_chat, rpc_spy):
    class FakeAttachErrorSupabase(FakeSupabase):
        def __init__(self, tables=None, rpcs=None, spy_list=None):
            super().__init__(tables, rpcs)
            self.spy_list = spy_list if spy_list is not None else []
            
        def rpc(self, name, params=None):
            return SpyRPCBuilder(self.rpcs.get(name, []), name, params, self.spy_list)

        def table(self, name):
            if name == "stores":
                raise Exception("db attach error")
            return super().table(name)

    def _get_client():
        return FakeAttachErrorSupabase(
            tables={"stores": _MOCK_STORES},
            rpcs={"match_products": _MOCK_PRODUCTS},
            spy_list=rpc_spy
        )
    monkeypatch.setattr("api.search.get_client", _get_client)
    
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/api/search", json={"query": "pizza"})
    
    # Assert successful response despite failure
    assert resp.status_code == 200
    data = resp.json()
    
    # Results should be returned intact
    results = data["results"]
    assert len(results) == 1
    res = results[0]
    assert res["name"] == "Pepperoni Pizza"
    
    # Store fields should be missing
    assert "store_name" not in res
