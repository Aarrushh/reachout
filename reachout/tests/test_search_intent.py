import json
import pytest
from api.search import _extract_intent
from api.gemini import GeminiError

def test_extract_intent_valid_json(monkeypatch):
    def mock_chat(*args, **kwargs):
        return json.dumps({
            "item_name": "apple",
            "item_type": "fruit",
            "brand_hint": "granny smith",
            "location": "madrid"
        })
    monkeypatch.setattr("api.search.gemini.chat", mock_chat)
    
    intent = _extract_intent("apple")
    assert intent == {
        "item_name": "apple",
        "item_type": "fruit",
        "brand_hint": "granny smith",
        "location": "madrid"
    }

def test_extract_intent_gemini_error(monkeypatch):
    def mock_chat(*args, **kwargs):
        raise GeminiError("api unavailable")
    monkeypatch.setattr("api.search.gemini.chat", mock_chat)
    
    intent = _extract_intent("some query")
    assert intent == {
        "item_name": "some query",
        "item_type": None,
        "brand_hint": None,
        "location": None
    }

def test_extract_intent_non_json(monkeypatch):
    def mock_chat(*args, **kwargs):
        return "this is not json!"
    monkeypatch.setattr("api.search.gemini.chat", mock_chat)
    
    intent = _extract_intent("garbage query")
    assert intent == {
        "item_name": "garbage query",
        "item_type": None,
        "brand_hint": None,
        "location": None
    }

def test_extract_intent_json_array(monkeypatch):
    def mock_chat(*args, **kwargs):
        return json.dumps(["an", "array"])
    monkeypatch.setattr("api.search.gemini.chat", mock_chat)
    
    intent = _extract_intent("array query")
    assert intent == {
        "item_name": "array query",
        "item_type": None,
        "brand_hint": None,
        "location": None
    }
