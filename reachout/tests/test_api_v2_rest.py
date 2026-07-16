import pytest
from tests.test_api import _client
from tests.fake_supa import FakeSupabase, FakeQueryBuilder

_MOCK_PRODUCTS = [
    {
        "id": "p1",
        "name": "Laptop",
        "description": "Fast laptop",
        "category": "electronics",
        "price": 1000,
        "stock_qty": 10,
        "store_id": "s1",
        "neighbourhood": "Sol",
        "tags": ["tech", "computer"],
        "image_url": "http://example.com/laptop.png"
    },
    {
        "id": "p2",
        "name": "Pizza",
        "description": "Cheese pizza",
        "category": "food",
        "price": 10,
        "stock_qty": 5,
        "store_id": "s2",
        "neighbourhood": "Malasaña",
        "tags": ["food", "hot"],
        "image_url": "http://example.com/pizza.png"
    }
]

_MOCK_STORES = [
    {
        "id": "s1",
        "name": "Tech Store",
        "neighbourhood": "Sol",
        "avg_delivery_mins": 30,
        "is_open": True,
        "rating": 4.5
    },
    {
        "id": "s2",
        "name": "Pizza Place",
        "neighbourhood": "Malasaña",
        "avg_delivery_mins": 45,
        "is_open": True,
        "rating": 4.8
    }
]

class SpyQueryBuilder(FakeQueryBuilder):
    def __init__(self, data, spy_list, table_name):
        super().__init__(data)
        self.spy_list = spy_list
        self.table_name = table_name

    def eq(self, col, val):
        self.spy_list.append({"table": self.table_name, "method": "eq", "args": (col, val)})
        return super().eq(col, val)

    def range(self, start, end):
        self.spy_list.append({"table": self.table_name, "method": "range", "args": (start, end)})
        return super().range(start, end)
        
    def order(self, col, desc=False):
        self.spy_list.append({"table": self.table_name, "method": "order", "args": (col,), "kwargs": {"desc": desc}})
        return super().order(col, desc)

class SpyFakeSupabase(FakeSupabase):
    def __init__(self, tables=None, rpcs=None, spy_list=None):
        super().__init__(tables, rpcs)
        self.spy_list = spy_list if spy_list is not None else []

    def table(self, name):
        return SpyQueryBuilder(self.tables.get(name, []), self.spy_list, name)

@pytest.fixture
def query_spy():
    return []

@pytest.fixture(autouse=True)
def patch_supa_client(monkeypatch, query_spy):
    def _get_client(*args, **kwargs):
        return SpyFakeSupabase(
            tables={"products": _MOCK_PRODUCTS, "stores": _MOCK_STORES},
            spy_list=query_spy
        )

    # I'll just mock `os.environ.get` to not throw RuntimeError from `get_client()`.
    # `get_client` checks "SUPABASE_URL" and "SUPABASE_KEY". Let's provide them, 
    # but mock `create_client` which it returns.
    monkeypatch.setenv("SUPABASE_URL", "http://fake")
    monkeypatch.setenv("SUPABASE_KEY", "fake")
    
    import api.supa
    if hasattr(api.supa.get_client, 'cache_clear'):
        api.supa.get_client.cache_clear()
    
    monkeypatch.setattr(api.supa, "create_client", _get_client)


def test_products_list_default(tmp_path, monkeypatch, query_spy):
    client = _client(tmp_path, monkeypatch)

    resp = client.get("/api/products")
    assert resp.status_code == 200
    data = resp.json()
    assert "products" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["products"]) == 2
    
    range_calls = [c for c in query_spy if c["table"] == "products" and c["method"] == "range"]
    assert len(range_calls) > 0
    assert range_calls[0]["args"] == (0, 49)

def test_products_list_pagination(tmp_path, monkeypatch, query_spy):
    client = _client(tmp_path, monkeypatch)

    resp = client.get("/api/products", params={"limit": 1, "offset": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["products"]) == 1
    
    range_calls = [c for c in query_spy if c["table"] == "products" and c["method"] == "range"]
    assert range_calls[0]["args"] == (1, 1)

def test_products_list_filters(tmp_path, monkeypatch, query_spy):
    client = _client(tmp_path, monkeypatch)

    resp = client.get("/api/products", params={"neighbourhood": "Sol", "category": "electronics"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["products"]) == 1
    assert data["products"][0]["name"] == "Laptop"
    
    eq_calls = [c for c in query_spy if c["table"] == "products" and c["method"] == "eq"]
    assert {"table": "products", "method": "eq", "args": ("neighbourhood", "Sol")} in eq_calls
    assert {"table": "products", "method": "eq", "args": ("category", "electronics")} in eq_calls

@pytest.mark.parametrize("limit", [0, 201])
def test_products_list_validation(tmp_path, monkeypatch, limit):
    client = _client(tmp_path, monkeypatch)

    resp = client.get("/api/products", params={"limit": limit})
    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], list)

def test_stores_list(tmp_path, monkeypatch, query_spy):
    client = _client(tmp_path, monkeypatch)

    resp = client.get("/api/stores")
    assert resp.status_code == 200
    data = resp.json()
    assert "stores" in data
    assert len(data["stores"]) == 2
    
    order_calls = [c for c in query_spy if c["table"] == "stores" and c["method"] == "order"]
    assert len(order_calls) > 0
    assert order_calls[0]["args"] == ("rating",)
    assert order_calls[0]["kwargs"] == {"desc": True}

def test_stores_list_filters(tmp_path, monkeypatch, query_spy):
    client = _client(tmp_path, monkeypatch)

    resp = client.get("/api/stores", params={"neighbourhood": "Malasaña"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["stores"]) == 1
    assert data["stores"][0]["name"] == "Pizza Place"
    
    eq_calls = [c for c in query_spy if c["table"] == "stores" and c["method"] == "eq"]
    assert {"table": "stores", "method": "eq", "args": ("neighbourhood", "Malasaña")} in eq_calls

def test_neighbourhoods(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/neighbourhoods")
    assert resp.status_code == 200
    data = resp.json()
    assert "neighbourhoods" in data
    
    from api.madrid import BARRIOS
    assert data["neighbourhoods"] == BARRIOS
