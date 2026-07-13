"""The orchestrator. One agent, reading the right files in order.

This is the ICM idea in code: the folder numbering is the execution order
(see CONTEXT.md). Each stage's script is pure and takes/returns plain dicts;
this module is the only piece that touches the stage output/ folders on
disk, and it re-reads every file it writes before trusting it downstream —
that round trip is the hard schema gate constraints.md #2 requires, and it
is what makes a corrupted intermediate file halt the pipeline instead of
being silently "fixed up" (constraints.md #2, #13).

Stage 01  parse-query     AGENTIC   free text  -> SearchIntent
Stage 02  geo-resolve     HARDCODED location   -> shops in radius
Stage 03  match-and-ping  HARDCODED SearchIntent + geo_shops -> ranked matches + pings
Stage 04  format-results  AGENTIC   matches    -> ranked shop list (optional AI casing pass)
Stage 05  map-render      HARDCODED ranked list -> GeoJSON

Usage:
    python run_pipeline.py "algo para el dolor de cabeza" --near "Malasaña"
    python run_pipeline.py "cargador usb c" --lat 40.4168 --lng -3.7038
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scripts"))
sys.path.insert(0, os.path.join(HERE, "agent"))

import db                                      # noqa: E402
import osm_ingest                              # noqa: E402
import region_seeder                           # noqa: E402
import validate as v                           # noqa: E402
from query_parser import parse_query           # noqa: E402  stage 01
from geo_resolve import resolve as geo_resolve  # noqa: E402  stage 02
from search_engine import search               # noqa: E402  stage 03
from result_formatter import format_results    # noqa: E402  stage 04
import map_render                              # noqa: E402  stage 05

STAGES_DIR = os.path.join(HERE, "stages")

STAGE_FOLDERS = {
    1: "01-parse-query",
    2: "02-geo-resolve",
    3: "03-match-and-ping",
    4: "04-format-results",
    5: "05-map-render",
}


class PipelineError(Exception):
    """A stage's output failed schema validation, or reported status != 'ok'."""


def _is_offline():
    return os.environ.get("REACHOUT_OFFLINE") == "1"


def _stage_output_dir(output_root, stage_folder):
    return os.path.join(output_root, stage_folder, "output")


def _write_stage_output(output_root, stage_folder, filename, data, schema_name, stage_label):
    ok, err = v.validate(data, schema_name)
    if not ok:
        raise PipelineError(f"{stage_label} output failed schema validation: {err}")
    out_dir = _stage_output_dir(output_root, stage_folder)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def _read_stage_output(output_root, stage_folder, filename, schema_name, stage_label):
    path = os.path.join(_stage_output_dir(output_root, stage_folder), filename)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise PipelineError(f"{stage_label} input at {path} is unreadable: {e}") from e
    ok, err = v.validate(data, schema_name)
    if not ok:
        raise PipelineError(f"{stage_label} input at {path} failed schema validation (corrupted?): {err}")
    return data


def _halt_if_not_ok(data, stage_label):
    status = data.get("status")
    if status != "ok":
        detail = data.get("missing_fields") or data.get("error") or status
        raise PipelineError(f"{stage_label} halted: status={status!r} ({detail})")


def _ensure_db_ready(db_path, offline):
    """First-run bootstrap only: if the shops table is empty, ingest once.

    geo_resolve.resolve() deliberately never calls osm_ingest on its own
    unless --refresh is passed (see W4's handoff notes) — that keeps a
    normal search from hitting Overpass every time. Without this, a fresh
    checkout's DB would have zero shops forever. --refresh (threaded through
    to resolve() below) remains the way to force a live re-fetch of an
    already-populated DB.
    """
    path = db_path or db.DB_PATH
    if not os.path.exists(path):
        db.init_db(path)
    conn = db.connect(path)
    try:
        if not db.all_shops(conn):
            osm_ingest.ingest(conn=conn, offline=offline)
            
        if not db.all_regions(conn):
            region_seeder.seed_regions(conn)
            region_seeder.assign_shops(conn)
    finally:
        conn.close()


def run_stage_01(query, output_root, use_llm=False):
    intent = parse_query(query, use_llm=use_llm)
    _write_stage_output(output_root, STAGE_FOLDERS[1], "intent.json", intent,
                         "search_intent.schema.json", "Stage 01 (parse-query)")
    return _read_stage_output(output_root, STAGE_FOLDERS[1], "intent.json",
                               "search_intent.schema.json", "Stage 01 (parse-query)")


def run_stage_02(output_root, lat=None, lng=None, near=None, radius_km=2.0,
                  refresh=False, db_path=None, offline=None):
    intent = _read_stage_output(output_root, STAGE_FOLDERS[1], "intent.json",
                                 "search_intent.schema.json", "Stage 02 (geo-resolve) input")
    _ensure_db_ready(db_path, offline)
    geo_shops = geo_resolve(intent, lat=lat, lng=lng, near=near, radius_km=radius_km,
                             refresh=refresh, db_path=db_path, offline=offline)
    _write_stage_output(output_root, STAGE_FOLDERS[2], "geo_shops.json", geo_shops,
                         "geo_shops.schema.json", "Stage 02 (geo-resolve)")
    return _read_stage_output(output_root, STAGE_FOLDERS[2], "geo_shops.json",
                               "geo_shops.schema.json", "Stage 02 (geo-resolve)")


def run_stage_03(output_root, db_path=None, do_ping=True, notif_dir=None):
    intent = _read_stage_output(output_root, STAGE_FOLDERS[1], "intent.json",
                                 "search_intent.schema.json", "Stage 03 (match-and-ping) input: intent")
    geo_shops = _read_stage_output(output_root, STAGE_FOLDERS[2], "geo_shops.json",
                                    "geo_shops.schema.json", "Stage 03 (match-and-ping) input: geo_shops")
    matches = search(intent, geo_shops, db_path=db_path, do_ping=do_ping, notif_dir=notif_dir)
    _write_stage_output(output_root, STAGE_FOLDERS[3], "matches.json", matches,
                         "stock_matches.schema.json", "Stage 03 (match-and-ping)")
    return _read_stage_output(output_root, STAGE_FOLDERS[3], "matches.json",
                               "stock_matches.schema.json", "Stage 03 (match-and-ping)")


def run_stage_04(output_root, use_llm=False):
    matches = _read_stage_output(output_root, STAGE_FOLDERS[3], "matches.json",
                                  "stock_matches.schema.json", "Stage 04 (format-results) input")
    deterministic = format_results(matches)

    llm_output = None
    if use_llm and deterministic.get("status") == "ok" and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from llm import normalize_item_names
            llm_output = normalize_item_names(deterministic)
        except Exception as e:
            print(f"  [format-results] LLM casing pass failed ({e}). Using deterministic output.")
            llm_output = None

    ranked = format_results(matches, llm_output=llm_output)
    _write_stage_output(output_root, STAGE_FOLDERS[4], "ranked_shops.json", ranked,
                         "ranked_shops.schema.json", "Stage 04 (format-results)")
    return _read_stage_output(output_root, STAGE_FOLDERS[4], "ranked_shops.json",
                               "ranked_shops.schema.json", "Stage 04 (format-results)")


def run_stage_05(output_root):
    ranked = _read_stage_output(output_root, STAGE_FOLDERS[4], "ranked_shops.json",
                                 "ranked_shops.schema.json", "Stage 05 (map-render) input: ranked_shops")
    geo_shops = _read_stage_output(output_root, STAGE_FOLDERS[2], "geo_shops.json",
                                    "geo_shops.schema.json", "Stage 05 (map-render) input: geo_shops")
    center = {"lat": geo_shops["query_location"]["lat"], "lng": geo_shops["query_location"]["lng"]}
    radius_km = geo_shops["radius_km"]

    out_dir = _stage_output_dir(output_root, STAGE_FOLDERS[5])
    geojson, error = map_render.write_output(ranked, center, radius_km, output_dir=out_dir)
    if error is not None:
        raise PipelineError(f"Stage 05 (map-render) halted: {error}")
    return geojson


def run(query, near=None, lat=None, lng=None, radius_km=2.0, refresh=False, use_llm=False,
        db_path=None, notif_dir=None, output_root=None, offline=None):
    output_root = output_root or STAGES_DIR

    print(f"\nStage 01  parse-query    : '{query}'")
    intent = run_stage_01(query, output_root, use_llm=use_llm)
    _halt_if_not_ok(intent, "Stage 01 (parse-query)")
    print("           keywords       :", intent["keywords"])

    print("Stage 02  geo-resolve    : resolving centre and candidate shops")
    geo_shops = run_stage_02(output_root, lat=lat, lng=lng, near=near, radius_km=radius_km,
                              refresh=refresh, db_path=db_path, offline=offline)
    _halt_if_not_ok(geo_shops, "Stage 02 (geo-resolve)")
    print(f"           shops in range : {geo_shops['shop_count']} ({geo_shops['shop_source']})")

    print("Stage 03  match-and-ping : searching live inventory and pinging shops")
    matches = run_stage_03(output_root, db_path=db_path, do_ping=True, notif_dir=notif_dir)
    _halt_if_not_ok(matches, "Stage 03 (match-and-ping)")
    print(f"           matches        : {matches['match_count']}")

    print("Stage 04  format-results : building ranked shop list")
    ranked = run_stage_04(output_root, use_llm=use_llm)
    _halt_if_not_ok(ranked, "Stage 04 (format-results)")

    print("Stage 05  map-render     : projecting to GeoJSON")
    geojson = run_stage_05(output_root)
    print(f"           features       : {len(geojson['features'])}")

    if ranked["result_count"] == 0:
        print(f"\nNo shops within {matches['radius_km']} km have '{query}' in stock right now.\n")
    else:
        print(f"\nFound '{query}' at {ranked['result_count']} nearby shop(s):")
        for r in ranked["results"]:
            print(f"  {r['rank']}. {r['shop_name']} ({r['distance_km']:.1f} km): "
                  f"{r['item_name']} — {r['price']:.2f} {r['currency']}, {r['stock_qty']} in stock")
        print()

    return {
        "intent": intent,
        "geo_shops": geo_shops,
        "matches": matches,
        "ranked_shops": ranked,
        "geojson": geojson,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="ReachOut Madrid pipeline")
    p.add_argument("query")
    p.add_argument("--near", default=None, help="Madrid neighbourhood name (Nominatim/gazetteer)")
    p.add_argument("--lat", type=float, default=None)
    p.add_argument("--lng", type=float, default=None)
    p.add_argument("--radius", type=float, default=2.0)
    p.add_argument("--refresh", action="store_true", help="refresh shop data from Overpass before searching")
    p.add_argument("--use-llm", action="store_true",
                    help="use the LLM for query parsing / item-name casing if ANTHROPIC_API_KEY is set")
    args = p.parse_args()

    if (args.lat is None) != (args.lng is None):
        p.error("--lat and --lng must be given together")

    try:
        run(args.query, near=args.near, lat=args.lat, lng=args.lng, radius_km=args.radius,
            refresh=args.refresh, use_llm=args.use_llm)
    except PipelineError as e:
        print(f"\n[HALTED] {e}", file=sys.stderr)
        sys.exit(1)
