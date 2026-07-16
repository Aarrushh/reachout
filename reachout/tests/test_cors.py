import pytest
from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)

def test_cors_preflight_post_search_allowed():
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://anything.netlify.app",
        "https://my-app.netlify.app",
    ]
    
    for origin in allowed_origins:
        response = client.options(
            "/api/search",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200, f"Failed for origin: {origin}"
        assert response.headers.get("access-control-allow-origin") == origin

def test_cors_preflight_post_search_disallowed():
    disallowed_origins = [
        "https://evil.example.com",
        "http://localhost:3000",
        "https://netlify.app.evil.com",
    ]
    
    for origin in disallowed_origins:
        response = client.options(
            "/api/search",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers, f"Failed for origin: {origin}"

def test_cors_preflight_get_products_allowed():
    response = client.options(
        "/api/products",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
