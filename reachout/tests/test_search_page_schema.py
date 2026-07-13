import pytest
import validate as v

def test_search_page_schema_ok():
    base_payload = {
        "status": "ok",
        "query": "test query",
        "generated_at": "2023-01-01T12:00:00Z",
        "page": 1,
        "page_size": 10,
        "total_results": 25,
        "total_pages": 3,
        "result_count": 10,
        "results": [
            {
                "rank": 1,
                "shop_id": "osm:node:1",
                "shop_name": "Test Shop",
                "category": "pharmacy",
                "address": "Test Address",
                "distance_km": 1.5,
                "item_name": "Test Item",
                "sku": "PHA-0001",
                "price": 10.00,
                "currency": "EUR",
                "stock_qty": 5,
                "lat": 40.4,
                "lng": -3.7
            }
        ]
    }
    
    ok, err = v.validate(base_payload, "search_page.schema.json")
    assert ok, err

def test_search_page_schema_missing_fields_ok():
    payload = {
        "status": "incomplete",
        "missing_fields": ["lat", "lng"]
    }
    ok, err = v.validate(payload, "search_page.schema.json")
    assert ok, err

def test_search_page_schema_error_ok():
    payload = {
        "status": "error",
        "error": {
            "code": "internal",
            "detail": "Failed"
        }
    }
    ok, err = v.validate(payload, "search_page.schema.json")
    assert ok, err

def test_search_page_schema_invalid():
    base_payload = {
        "status": "ok",
        "query": "test query",
        "generated_at": "2023-01-01T12:00:00Z",
        "page": 1,
        "page_size": 10,
        "total_results": 25,
        "total_pages": 3,
        "result_count": 10,
        "results": []
    }
    
    # Missing required field 'page'
    payload = dict(base_payload)
    del payload["page"]
    ok, err = v.validate(payload, "search_page.schema.json")
    assert not ok
    
    # Additional properties
    payload = dict(base_payload)
    payload["extra"] = "value"
    ok, err = v.validate(payload, "search_page.schema.json")
    assert not ok
    
    # Invalid page_size
    payload = dict(base_payload)
    payload["page_size"] = 100
    ok, err = v.validate(payload, "search_page.schema.json")
    assert not ok
