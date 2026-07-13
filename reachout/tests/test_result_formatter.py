import json
import os

import validate as v
from result_formatter import format_results


def _assert_valid(output):
    ok, err = v.validate(output, "ranked_shops.schema.json")
    assert ok, err


def _t1_matches():
    return {
        "status": "ok",
        "query": "algo para el dolor de cabeza",
        "query_location": {
            "lat": 40.4200, "lng": -3.7050,
            "resolved_from": "coordinates", "location_text": None,
        },
        "radius_km": 2.0,
        "match_count": 2,
        "matches": [
            {
                "shop_id": "osm:node:111",
                "shop_name": "Farmacia Sol",
                "categories": ["pharmacy"],
                "address": "Calle Mayor 1",
                "lat": 40.4165,
                "lng": -3.7038,
                "distance_km": 0.4,
                "distance_type": "haversine",
                "items": [
                    {"sku": "PHA-0001", "name": "Paracetamol", "category": "pharmacy",
                     "price": 3.95, "currency": "EUR", "qty": 10, "rating": 4.8, "review_count": 50},
                ],
            },
            {
                "shop_id": "osm:node:222",
                "shop_name": "Farmacia Lavapiés",
                "categories": ["pharmacy"],
                "address": None,
                "lat": 40.4090,
                "lng": -3.7020,
                "distance_km": 1.1,
                "distance_type": "haversine",
                "items": [
                    {"sku": "PHA-0002", "name": "Ibuprofeno", "category": "pharmacy",
                     "price": 4.20, "currency": "EUR", "qty": 5},
                ],
            },
        ],
        "pinged_shop_ids": ["osm:node:111", "osm:node:222"],
    }


def test_t1_two_matches_verbatim_numbers():
    result = format_results(_t1_matches())
    _assert_valid(result)

    assert result["status"] == "ok"
    assert result["result_count"] == 2
    r0, r1 = result["results"]

    assert r0["rank"] == 1
    assert r0["distance_km"] == 0.4
    assert r0["price"] == 3.95
    assert r0["currency"] == "EUR"
    assert r0["shop_id"] == "osm:node:111"
    assert r0["address"] == "Calle Mayor 1"

    assert r1["rank"] == 2
    assert r1["distance_km"] == 1.1
    assert r1["price"] == 4.20
    assert r1["address"] is None

    allowed = set(v.load_schema("ranked_shops.schema.json")["properties"]["results"]["items"]["required"])
    assert set(r0.keys()) == allowed | {"rating", "review_count"}
    assert set(r1.keys()) == allowed


def test_t2_zero_matches():
    matches = _t1_matches()
    matches["match_count"] = 0
    matches["matches"] = []
    matches["pinged_shop_ids"] = []

    result = format_results(matches)
    _assert_valid(result)
    assert result == {
        "status": "ok",
        "query": matches["query"],
        "generated_at": result["generated_at"],
        "result_count": 0,
        "results": [],
    }


def test_t3_llm_narrative_injection_rejected(tmp_path, monkeypatch):
    events_path = tmp_path / "events.jsonl"
    monkeypatch.setattr("result_formatter.EVENTS_PATH", str(events_path))

    matches = _t1_matches()
    deterministic = format_results(matches)

    llm_output = json.loads(json.dumps(deterministic))
    llm_output["results"][0]["community_note"] = "A beloved neighbourhood farmacia..."

    result = format_results(matches, llm_output=llm_output)

    _assert_valid(result)
    assert {k: val for k, val in result.items() if k != "generated_at"} == \
        {k: val for k, val in deterministic.items() if k != "generated_at"}
    assert "community_note" not in json.dumps(result)

    assert events_path.exists()
    lines = events_path.read_text().strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "formatter_llm_rejected"


def test_missing_required_field_yields_incomplete():
    matches = _t1_matches()
    del matches["matches"][0]["distance_km"]

    result = format_results(matches)
    _assert_valid(result)
    assert result["status"] == "incomplete"
    assert result["missing_fields"] == ["distance_km"]


def test_upstream_not_ok_becomes_error():
    result = format_results({"status": "incomplete", "missing_fields": ["query"]})
    _assert_valid(result)
    assert result["status"] == "error"
    assert result["error"]["code"] == "upstream_not_ok"


def test_ratings_and_reviews_flow_to_results():
    matches = _t1_matches()
    result = format_results(matches)
    _assert_valid(result)
    
    r0 = result["results"][0]
    assert r0["shop_id"] == "osm:node:111"
    assert r0["rating"] == 4.8
    assert r0["review_count"] == 50
    
    r1 = result["results"][1]
    assert r1["shop_id"] == "osm:node:222"
    assert "rating" not in r1
    assert "review_count" not in r1
