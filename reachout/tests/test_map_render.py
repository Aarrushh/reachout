import copy
import json
import os

import pytest

from map_render import render, write_output
from validate import validate

CENTER = {"lat": 40.4168, "lng": -3.7038}
RADIUS_KM = 2.0


def _result(rank, lat, lng, shop_id="osm:node:111", shop_name="Farmacia Sol",
            category="pharmacy", address="Calle Mayor 1", distance_km=0.5,
            item_name="Paracetamol", sku="PHA-0001", price=3.5, stock_qty=4):
    return {
        "rank": rank,
        "shop_id": shop_id,
        "shop_name": shop_name,
        "category": category,
        "address": address,
        "distance_km": distance_km,
        "item_name": item_name,
        "sku": sku,
        "price": price,
        "currency": "EUR",
        "stock_qty": stock_qty,
        "lat": lat,
        "lng": lng,
    }


def _ranked_shops_ok(results):
    return {
        "status": "ok",
        "query": "algo para el dolor de cabeza",
        "generated_at": "2026-07-07T12:00:00Z",
        "result_count": len(results),
        "results": results,
    }


def test_t1_two_results_lng_first():
    results = [
        _result(1, 40.4265, -3.7031, shop_id="osm:node:111", shop_name="Farmacia Sol"),
        _result(2, 40.4223, -3.7091, shop_id="osm:way:222", shop_name="Farmacia Gran Via"),
    ]
    ranked_shops = _ranked_shops_ok(results)

    geojson, error = render(ranked_shops, CENTER, RADIUS_KM)

    assert error is None
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 2
    assert geojson["metadata"]["result_count"] == 2
    assert geojson["metadata"]["center"] == CENTER
    assert geojson["metadata"]["radius_km"] == RADIUS_KM

    f1, f2 = geojson["features"]
    assert f1["type"] == "Feature"
    assert f1["geometry"]["type"] == "Point"
    assert f1["geometry"]["coordinates"] == [-3.7031, 40.4265]
    assert f1["properties"]["rank"] == 1
    assert f2["geometry"]["coordinates"] == [-3.7091, 40.4223]
    assert f2["properties"]["rank"] == 2

    for field in ["shop_id", "shop_name", "rank", "category", "address",
                  "distance_km", "item_name", "price", "currency", "stock_qty"]:
        assert f1["properties"][field] == results[0][field]

    ok, err = validate(geojson, "map_geojson.schema.json")
    assert ok, err


def test_t2_zero_results_valid_empty_collection():
    ranked_shops = _ranked_shops_ok([])

    geojson, error = render(ranked_shops, CENTER, RADIUS_KM)

    assert error is None
    assert geojson == {
        "type": "FeatureCollection",
        "metadata": {
            "query": "algo para el dolor de cabeza",
            "generated_at": "2026-07-07T12:00:00Z",
            "result_count": 0,
            "center": CENTER,
            "radius_km": RADIUS_KM,
        },
        "features": [],
    }
    ok, err = validate(geojson, "map_geojson.schema.json")
    assert ok, err


def test_t3_missing_lng_yields_error_sidecar():
    result = _result(1, 40.4265, -3.7031)
    del result["lng"]
    ranked_shops = _ranked_shops_ok([result])

    geojson, error = render(ranked_shops, CENTER, RADIUS_KM)

    assert geojson is None
    assert error == {"status": "incomplete", "missing_fields": ["results[0].lng"]}


def test_upstream_status_not_ok_relays_and_writes_no_geojson():
    ranked_shops = {"status": "incomplete", "missing_fields": ["location_text"]}

    geojson, error = render(ranked_shops, CENTER, RADIUS_KM)

    assert geojson is None
    assert error == {"status": "incomplete", "missing_fields": ["location_text"]}


def test_swapped_lat_lng_fails_schema_validation():
    results = [_result(1, 40.4265, -3.7031)]
    ranked_shops = _ranked_shops_ok(results)
    geojson, error = render(ranked_shops, CENTER, RADIUS_KM)
    assert error is None

    swapped = copy.deepcopy(geojson)
    lng, lat = swapped["features"][0]["geometry"]["coordinates"]
    swapped["features"][0]["geometry"]["coordinates"] = [lat, lng]

    ok, err = validate(swapped, "map_geojson.schema.json")
    assert not ok


def test_write_output_success_removes_stale_error_file(tmp_path):
    results = [_result(1, 40.4265, -3.7031)]
    ranked_shops = _ranked_shops_ok(results)

    stale_error = tmp_path / "error.json"
    stale_error.write_text("{}")

    geojson, error = write_output(ranked_shops, CENTER, RADIUS_KM, output_dir=str(tmp_path))

    assert error is None
    assert (tmp_path / "shops.geojson").exists()
    assert not (tmp_path / "error.json").exists()
    on_disk = json.loads((tmp_path / "shops.geojson").read_text())
    assert on_disk == geojson


def test_write_output_error_removes_stale_geojson_file(tmp_path):
    result = _result(1, 40.4265, -3.7031)
    del result["lng"]
    ranked_shops = _ranked_shops_ok([result])

    stale_geojson = tmp_path / "shops.geojson"
    stale_geojson.write_text("{}")

    geojson, error = write_output(ranked_shops, CENTER, RADIUS_KM, output_dir=str(tmp_path))

    assert geojson is None
    assert (tmp_path / "error.json").exists()
    assert not (tmp_path / "shops.geojson").exists()
    on_disk = json.loads((tmp_path / "error.json").read_text())
    assert on_disk == error
