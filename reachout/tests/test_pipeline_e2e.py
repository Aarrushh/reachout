import json
import os

import pytest

import db
import run_pipeline
import validate as v
from run_pipeline import PipelineError


def _upsert_shop(conn, shop_id, name, categories, lat, lng, address=None):
    db.upsert_shop(conn, {
        "shop_id": shop_id,
        "osm_id": int(shop_id.split(":")[-1]),
        "name": name,
        "categories": categories,
        "lat": lat,
        "lng": lng,
        "address": address,
        "source": "cache",
        "fetched_at": "2026-07-07T10:00:00+00:00",
    })


def _upsert_item(conn, shop_id, sku, name, category, price, qty):
    db.upsert_item(conn, {
        "shop_id": shop_id,
        "sku": sku,
        "name": name,
        "category": category,
        "price": price,
        "currency": "EUR",
        "qty": qty,
        "synthetic": True,
    })


def _seeded_db(tmp_path):
    """One pharmacy near Malasaña, one electronics shop near Puerta del Sol."""
    db_path = str(tmp_path / "reachout.db")
    db.init_db(db_path)
    conn = db.connect(db_path)
    _upsert_shop(conn, "osm:node:1001", "Farmacia Malasaña", ["pharmacy"], 40.4270, -3.7035, "Calle del Pez 1")
    _upsert_item(conn, "osm:node:1001", "PHA-0001", "Paracetamol 1g 40 comprimidos", "pharmacy", 3.95, 5)
    _upsert_shop(conn, "osm:node:2002", "Electro Sol", ["electronics"], 40.4170, -3.7040, "Calle Mayor 1")
    _upsert_item(conn, "osm:node:2002", "ELE-0001", "Cargador USB-C 20W", "electronics", 14.95, 8)
    conn.commit()
    conn.close()
    return db_path


def _load(output_root, stage_folder, filename):
    with open(os.path.join(output_root, stage_folder, "output", filename), encoding="utf-8") as f:
        return json.load(f)


def _assert_all_five_outputs_valid(output_root):
    intent = _load(output_root, "01-parse-query", "intent.json")
    ok, err = v.validate(intent, "search_intent.schema.json")
    assert ok, err

    geo_shops = _load(output_root, "02-geo-resolve", "geo_shops.json")
    ok, err = v.validate(geo_shops, "geo_shops.schema.json")
    assert ok, err

    matches = _load(output_root, "03-match-and-ping", "matches.json")
    ok, err = v.validate(matches, "stock_matches.schema.json")
    assert ok, err

    ranked = _load(output_root, "04-format-results", "ranked_shops.json")
    ok, err = v.validate(ranked, "ranked_shops.schema.json")
    assert ok, err

    geojson_path = os.path.join(output_root, "05-map-render", "output", "shops.geojson")
    assert os.path.exists(geojson_path)
    error_path = os.path.join(output_root, "05-map-render", "output", "error.json")
    assert not os.path.exists(error_path)
    with open(geojson_path, encoding="utf-8") as f:
        geojson = json.load(f)
    ok, err = v.validate(geojson, "map_geojson.schema.json")
    assert ok, err

    return intent, geo_shops, matches, ranked, geojson


def test_t1_headache_query_near_malasana_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("REACHOUT_OFFLINE", "1")
    db_path = _seeded_db(tmp_path)
    output_root = str(tmp_path / "stages")
    notif_dir = str(tmp_path / "notifications")

    result = run_pipeline.run(
        "algo para el dolor de cabeza", near="Malasaña", radius_km=2.0,
        db_path=db_path, notif_dir=notif_dir, output_root=output_root,
    )

    assert result["ranked_shops"]["status"] == "ok"
    assert result["ranked_shops"]["result_count"] == 1
    assert result["ranked_shops"]["results"][0]["shop_id"] == "osm:node:1001"
    assert result["ranked_shops"]["results"][0]["price"] == 3.95

    intent, geo_shops, matches, ranked, geojson = _assert_all_five_outputs_valid(output_root)
    assert geo_shops["query_location"]["resolved_from"] == "gazetteer"
    assert geojson["features"][0]["properties"]["shop_id"] == "osm:node:1001"
    assert os.path.exists(os.path.join(notif_dir, "osm_node_1001.jsonl"))


def test_t2_usb_c_charger_explicit_coords_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("REACHOUT_OFFLINE", "1")
    db_path = _seeded_db(tmp_path)
    output_root = str(tmp_path / "stages")
    notif_dir = str(tmp_path / "notifications")

    result = run_pipeline.run(
        "cargador usb c", lat=40.4168, lng=-3.7038, radius_km=2.0,
        db_path=db_path, notif_dir=notif_dir, output_root=output_root,
    )

    assert result["ranked_shops"]["status"] == "ok"
    assert result["ranked_shops"]["result_count"] == 1
    assert result["ranked_shops"]["results"][0]["shop_id"] == "osm:node:2002"

    _assert_all_five_outputs_valid(output_root)
    assert os.path.exists(os.path.join(notif_dir, "osm_node_2002.jsonl"))


def test_zero_matches_is_ok_not_error(tmp_path, monkeypatch):
    monkeypatch.setenv("REACHOUT_OFFLINE", "1")
    db_path = _seeded_db(tmp_path)
    output_root = str(tmp_path / "stages")
    notif_dir = str(tmp_path / "notifications")

    result = run_pipeline.run(
        "cuaderno y bolígrafo", lat=40.4168, lng=-3.7038, radius_km=2.0,
        db_path=db_path, notif_dir=notif_dir, output_root=output_root,
    )

    assert result["ranked_shops"]["status"] == "ok"
    assert result["ranked_shops"]["result_count"] == 0
    assert result["ranked_shops"]["results"] == []

    _, _, matches, ranked, geojson = _assert_all_five_outputs_valid(output_root)
    assert matches["match_count"] == 0
    assert geojson["features"] == []


def test_incomplete_stage_01_halts_before_stage_02(tmp_path, monkeypatch):
    monkeypatch.setenv("REACHOUT_OFFLINE", "1")
    db_path = _seeded_db(tmp_path)
    output_root = str(tmp_path / "stages")

    with pytest.raises(PipelineError):
        run_pipeline.run("???", db_path=db_path, output_root=output_root)

    intent = _load(output_root, "01-parse-query", "intent.json")
    assert intent["status"] == "incomplete"
    geo_path = os.path.join(output_root, "02-geo-resolve", "output", "geo_shops.json")
    assert not os.path.exists(geo_path)


def test_corrupted_intermediate_file_invalid_json_halts_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("REACHOUT_OFFLINE", "1")
    db_path = _seeded_db(tmp_path)
    output_root = str(tmp_path / "stages")

    run_pipeline.run_stage_01("algo para el dolor de cabeza", output_root)
    run_pipeline.run_stage_02(output_root, near="Malasaña", radius_km=2.0, db_path=db_path, offline=True)

    geo_path = os.path.join(output_root, "02-geo-resolve", "output", "geo_shops.json")
    with open(geo_path, "w", encoding="utf-8") as f:
        f.write("{not valid json")

    with pytest.raises(PipelineError):
        run_pipeline.run_stage_03(output_root, db_path=db_path)


def test_corrupted_intermediate_file_schema_invalid_halts_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("REACHOUT_OFFLINE", "1")
    db_path = _seeded_db(tmp_path)
    output_root = str(tmp_path / "stages")

    run_pipeline.run_stage_01("cargador usb c", output_root)
    run_pipeline.run_stage_02(output_root, lat=40.4168, lng=-3.7038, radius_km=2.0, db_path=db_path, offline=True)

    geo_path = os.path.join(output_root, "02-geo-resolve", "output", "geo_shops.json")
    with open(geo_path, "w", encoding="utf-8") as f:
        json.dump({"status": "ok"}, f)  # missing every field required when status is "ok"

    with pytest.raises(PipelineError):
        run_pipeline.run_stage_03(output_root, db_path=db_path)


def test_use_llm_without_api_key_falls_back_to_deterministic(tmp_path, monkeypatch):
    monkeypatch.setenv("REACHOUT_OFFLINE", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    db_path = _seeded_db(tmp_path)
    output_root = str(tmp_path / "stages")
    notif_dir = str(tmp_path / "notifications")

    result = run_pipeline.run(
        "algo para el dolor de cabeza", near="Malasaña", radius_km=2.0,
        db_path=db_path, notif_dir=notif_dir, output_root=output_root, use_llm=True,
    )

    assert result["ranked_shops"]["status"] == "ok"
    assert result["ranked_shops"]["result_count"] == 1
