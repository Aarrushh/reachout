import pytest
from fastapi.testclient import TestClient

from api.server import app
from api import gemini
from fake_supa import FakeSupabase

client = TestClient(app)


def test_chat_200_ok(monkeypatch):
    def fake_chat(*args, **kwargs):
        return "¡Hola! Sí, tengo pan."
    monkeypatch.setattr(gemini, "chat", fake_chat)
    
    tables = {
        "stores": [
            {"id": "store123", "name": "Mi Tienda", "neighbourhood": "Malasaña", "avg_delivery_mins": 15}
        ],
        "products": [
            {
                "id": "prod1", "name": "Pan", "description": "Pan fresco", "category": "bakery",
                "price": 1.20, "stock_qty": 10, "store_id": "store123", "neighbourhood": "Malasaña",
                "tags": ["pan", "fresco"], "image_url": "http://example.com/pan.jpg"
            }
        ]
    }
    
    def mock_get_client():
        return FakeSupabase(tables=tables)
    monkeypatch.setattr("api.chat.get_client", mock_get_client)

    resp = client.post("/api/chat", json={
        "store_id": "store123",
        "message": "Hola, ¿tienes pan?",
        "history": []
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["reply"] == "¡Hola! Sí, tengo pan."
    assert len(data["suggested_items"]) == 1
    assert data["suggested_items"][0]["id"] == "prod1"


def test_chat_unknown_store_404(monkeypatch):
    def mock_get_client():
        return FakeSupabase(tables={"stores": []})
    monkeypatch.setattr("api.chat.get_client", mock_get_client)

    resp = client.post("/api/chat", json={
        "store_id": "unknown_store",
        "message": "Hola",
        "history": []
    })
    assert resp.status_code == 404
    assert resp.json()["detail"] == "store unknown_store not found"


def test_chat_empty_message_400():
    resp = client.post("/api/chat", json={
        "store_id": "store123",
        "message": "   ",
        "history": []
    })
    assert resp.status_code == 400
    assert resp.json()["detail"] == "message must be non-empty"


def test_chat_history_truncated_to_20(monkeypatch):
    captured_messages = []
    def fake_chat(*args, **kwargs):
        if kwargs.get("messages"):
            captured_messages.extend(kwargs["messages"])
        elif args:
            captured_messages.extend(args[0])
        return "Reply"
    monkeypatch.setattr(gemini, "chat", fake_chat)

    tables = {
        "stores": [
            {"id": "store123", "name": "Mi Tienda", "neighbourhood": "Malasaña", "avg_delivery_mins": 15}
        ],
        "products": []
    }
    def mock_get_client():
        return FakeSupabase(tables=tables)
    monkeypatch.setattr("api.chat.get_client", mock_get_client)

    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"} for i in range(25)]

    resp = client.post("/api/chat", json={
        "store_id": "store123",
        "message": "New message",
        "history": history
    })
    assert resp.status_code == 200, resp.text
    # 20 from history + 1 new message
    assert len(captured_messages) == 21
    assert captured_messages[-1]["content"] == "New message"
    assert captured_messages[0]["content"] == "msg 5"


def test_chat_gemini_error_502(monkeypatch):
    def fake_chat(*args, **kwargs):
        raise gemini.GeminiError("Test error")
    monkeypatch.setattr(gemini, "chat", fake_chat)

    tables = {
        "stores": [
            {"id": "store123", "name": "Mi Tienda", "neighbourhood": "Malasaña", "avg_delivery_mins": 15}
        ],
        "products": []
    }
    def mock_get_client():
        return FakeSupabase(tables=tables)
    monkeypatch.setattr("api.chat.get_client", mock_get_client)

    resp = client.post("/api/chat", json={
        "store_id": "store123",
        "message": "Hello",
        "history": []
    })
    assert resp.status_code == 502
    assert "LLM unavailable" in resp.json()["detail"]

def test_chat_system_prompt_truncation(monkeypatch):
    captured_sys = []
    def fake_chat(*args, **kwargs):
        captured_sys.append(args[1] if len(args) > 1 else kwargs.get("system_instruction"))
        return "Reply"
    monkeypatch.setattr(gemini, "chat", fake_chat)

    products = []
    for i in range(500):
        # First 100 are in-stock, rest are out-of-stock
        stock = 10 if i < 100 else 0
        products.append({
            "id": f"prod{i}", "name": f"Item {i}", "description": "desc", "category": "cat",
            "price": 1.0, "stock_qty": stock, "store_id": "store123", "neighbourhood": "Malasaña",
            "tags": [], "image_url": "http://example.com"
        })

    tables = {
        "stores": [
            {"id": "store123", "name": "Mi Tienda", "neighbourhood": "Malasaña", "avg_delivery_mins": 15}
        ],
        "products": products
    }
    
    def mock_get_client():
        return FakeSupabase(tables=tables)
    monkeypatch.setattr("api.chat.get_client", mock_get_client)

    resp = client.post("/api/chat", json={
        "store_id": "store123",
        "message": "Hola",
        "history": []
    })
    
    assert resp.status_code == 200, resp.text
    sys_prompt = captured_sys[0]
    
    # Extract the lines that start with "- Item"
    inventory_lines = [line for line in sys_prompt.split('\n') if line.startswith("- Item")]
    assert len(inventory_lines) == 120
    
    # Check that in-stock items are prioritized (we had 100 in-stock, so they should all be here)
    in_stock_lines = [line for line in inventory_lines if "stock: 10" in line]
    assert len(in_stock_lines) == 100
    
    # The remaining 20 should be out of stock
    out_of_stock_lines = [line for line in inventory_lines if "stock: 0" in line]
    assert len(out_of_stock_lines) == 20
    
    # Check the overflow string
    assert "…y 380 artículos más" in sys_prompt


def test_chat_supabase_error_502(monkeypatch):
    class BrokenSupabase:
        def table(self, name):
            raise RuntimeError("Database connection failed")
            
    def mock_get_client():
        return BrokenSupabase()
    monkeypatch.setattr("api.chat.get_client", mock_get_client)

    resp = client.post("/api/chat", json={
        "store_id": "store123",
        "message": "Hola",
        "history": []
    })
    
    assert resp.status_code == 502
    assert "Database connection failed" in resp.json()["detail"]
