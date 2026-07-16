import pytest
from api.search import _rerank

def test_exact_substring_beats_similarity():
    rows = [
        {"id": 1, "name": "Apple iPhone 13 case", "similarity": 0.5},
        {"id": 2, "name": "Some other phone case", "similarity": 0.7},
    ]
    intent = {"item_name": "iPhone 13"}
    results = _rerank(rows, intent)
    assert results[0]["id"] == 1
    assert results[0]["match_score"] == 0.8
    assert results[1]["id"] == 2
    assert results[1]["match_score"] == 0.7

def test_partial_token_overlap():
    rows = [
        {"id": 1, "name": "Samsung Galaxy", "similarity": 0.5},
        {"id": 2, "name": "Apple iPhone", "similarity": 0.5},
    ]
    intent = {"item_name": "Samsung Galaxy S22"}
    results = _rerank(rows, intent)
    
    assert results[0]["id"] == 1
    assert results[1]["id"] == 2
    assert results[0]["match_score"] == 0.60
    assert results[1]["match_score"] == 0.50

def test_brand_hint_match():
    rows = [
        {"id": 1, "name": "T-Shirt", "tags": ["nike", "clothing"], "similarity": 0.4},
        {"id": 2, "name": "T-Shirt", "tags": ["adidas", "clothing"], "similarity": 0.4},
    ]
    intent = {"item_name": "T-Shirt", "brand_hint": "Nike"}
    results = _rerank(rows, intent)
    
    assert results[0]["id"] == 1
    assert results[1]["id"] == 2
    assert results[0]["match_score"] == 0.8
    assert results[1]["match_score"] == 0.7

def test_stock_qty_boost():
    rows = [
        {"id": 1, "name": "Mouse", "stock_qty": 0, "similarity": 0.5},
        {"id": 2, "name": "Mouse", "stock_qty": 10, "similarity": 0.5},
        {"id": 3, "name": "Mouse", "similarity": 0.5},
    ]
    intent = {"item_name": "Keyboard"} 
    results = _rerank(rows, intent)
    
    assert results[0]["id"] == 2
    assert results[0]["match_score"] == 0.55
    assert results[1]["match_score"] == 0.50
    assert set(r["id"] for r in results[1:]) == {1, 3}

def test_output_capped_and_sorted():
    rows = [
        {"id": i, "name": f"Item {i}", "similarity": i * 0.01}
        for i in range(30)
    ]
    intent = {"item_name": "No Match"}
    results = _rerank(rows, intent)
    
    assert len(results) == 20
    scores = [r["match_score"] for r in results]
    assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
    assert "match_score" in results[0]
