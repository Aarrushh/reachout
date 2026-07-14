import pytest
from tests.test_api import _client

ERROR_CASES = [
    # (endpoint, params, expected_status, expected_detail_type, expected_snippet)
    
    # /api/search missing required parameter 'q'
    ("/api/search", {}, 422, list, "Field required"),
    
    # /api/search invalid coordinates / regions
    ("/api/search", {"q": "test", "region": "malasana", "near": "madrid"}, 400, str, "cannot be combined"),
    ("/api/search", {"q": "test", "region": "malasana", "lat": 40.0}, 400, str, "cannot be combined"),
    ("/api/search", {"q": "test", "region": "malasana", "lng": -3.0}, 400, str, "cannot be combined"),
    ("/api/search", {"q": "test", "region": "unknown_region"}, 404, str, "not found"),
    ("/api/search", {"q": "test", "lat": 40.0}, 400, str, "must be given together"),
    ("/api/search", {"q": "test", "lng": -3.0}, 400, str, "must be given together"),
    
    # /api/search pipeline error (unparseable query)
    ("/api/search", {"q": "???"}, 422, str, "query"),
    
    # /api/search pagination validation errors
    ("/api/search", {"q": "test", "page": 0}, 422, list, "Input should be greater than or equal to 1"),
    ("/api/search", {"q": "test", "page_size": 0}, 422, list, "Input should be greater than or equal to 1"),
    ("/api/search", {"q": "test", "page_size": 51}, 422, list, "Input should be less than or equal to 50"),
    ("/api/search", {"q": "test", "page": "abc"}, 422, list, "Input should be a valid integer"),

    # /api/search.geojson missing required parameter 'q'
    ("/api/search.geojson", {}, 422, list, "Field required"),

    # /api/search.geojson invalid coordinates / regions
    ("/api/search.geojson", {"q": "test", "region": "malasana", "near": "madrid"}, 400, str, "cannot be combined"),
    ("/api/search.geojson", {"q": "test", "region": "malasana", "lat": 40.0}, 400, str, "cannot be combined"),
    ("/api/search.geojson", {"q": "test", "region": "malasana", "lng": -3.0}, 400, str, "cannot be combined"),
    ("/api/search.geojson", {"q": "test", "region": "unknown_region"}, 404, str, "not found"),
    ("/api/search.geojson", {"q": "test", "lat": 40.0}, 400, str, "must be given together"),
    ("/api/search.geojson", {"q": "test", "lng": -3.0}, 400, str, "must be given together"),
    
    # /api/search.geojson pipeline error
    ("/api/search.geojson", {"q": "???"}, 422, str, "query"),

    # /api/inventory invalid region
    ("/api/inventory", {"region": "unknown_region"}, 404, str, "not found"),
    
    # /api/inventory pagination validation errors
    ("/api/inventory", {"page": 0}, 422, list, "Input should be greater than or equal to 1"),
    ("/api/inventory", {"page_size": 0}, 422, list, "Input should be greater than or equal to 1"),
    ("/api/inventory", {"page_size": 101}, 422, list, "Input should be less than or equal to 100"),
    ("/api/inventory", {"in_stock": -1}, 422, list, "Input should be greater than or equal to 0"),
    ("/api/inventory", {"in_stock": 2}, 422, list, "Input should be less than or equal to 1"),
    ("/api/inventory", {"in_stock": "abc"}, 422, list, "Input should be a valid integer"),
]

@pytest.mark.parametrize("endpoint, params, expected_status, detail_type, expected_snippet", ERROR_CASES)
def test_api_errors(tmp_path, monkeypatch, endpoint, params, expected_status, detail_type, expected_snippet):
    client = _client(tmp_path, monkeypatch)
    
    resp = client.get(endpoint, params=params)
    assert resp.status_code == expected_status
    
    body = resp.json()
    assert "detail" in body
    
    detail = body["detail"]
    assert isinstance(detail, detail_type)
    
    # For lists, stringify them to easily check for snippets like "Input should be a valid integer"
    if isinstance(detail, list):
        detail_str = str(detail)
    else:
        detail_str = detail
        
    assert expected_snippet.lower() in detail_str.lower()
