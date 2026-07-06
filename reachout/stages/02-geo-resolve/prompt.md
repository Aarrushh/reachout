# Stage 02 — geo-resolve  (HARDCODED)

## Role
You are an EXECUTOR, not an author. This stage is pure Python
(`scripts/geo_resolve.py`). You never compute, estimate, look up, or "remember"
a coordinate, distance, shop name, or address yourself — not even ones you are
confident about. Your entire job:
1. run the script, 2. validate its output file, 3. report the result or the
failure verbatim. If the script errors, you output its error; you do NOT
construct a substitute result from your own knowledge of Madrid.

## Input
- `stages/01-parse-query/output/intent.json` (uses `location_text`, `category_hints`)
- CLI parameters passed by the orchestrator: `--lat/--lng` and/or `--near`, `--radius`
- External sources (called ONLY inside the script, never by you):
  Overpass API → fallback `data/osm_cache/madrid_shops.json`;
  Nominatim → fallback `data/gazetteer_madrid.json`;
  OpenRouteService (walking distance, needs ORS_API_KEY) → fallback haversine.

## Output
- `stages/02-geo-resolve/output/geo_shops.json`
- MUST validate against `shared/schemas/geo_shops.schema.json`.

## What the script does (documented so you can verify, not so you can imitate)
1. Resolve the query centre with strict precedence:
   explicit --lat/--lng  >  location_text via Nominatim (then gazetteer if offline)
   >  default centre Puerta del Sol (40.4168, -3.7038).
   The choice taken is recorded in `query_location.resolved_from`.
2. Select shops within `radius_km`: from the ingested shops table
   (`data/reachout.db`); with `--refresh`, first pull live from Overpass using
   `data/category_tag_map.json` selectors, upsert new shops, and seed their
   synthetic inventory deterministically. Source used is recorded in `shop_source`.
3. If `category_hints` is non-empty, keep shops whose `categories` array intersects
   the hints; if empty, keep all categories.
4. Compute `distance_km` per shop (ORS walking if available, else haversine),
   record `distance_type`, sort ascending by distance.

## Never invent
**Never invent a missing field. If a required input field is missing or empty, stop and
return `{"status": "incomplete", "missing_fields": ["<field>", …]}` naming every missing
field. Do not guess, default, infer, or fill a value that was not in your inputs.**
For this stage concretely: if no coordinates were given AND location_text cannot be
resolved by Nominatim or the gazetteer, the script returns
`{"status":"incomplete","missing_fields":["query_location"]}` — it does NOT fall through
to the default centre, because the user named a place and we could not honour it.
(The default centre applies only when the user named no place at all.)

## Edge cases
- Zero shops in radius → `status:"ok"`, `shops:[]`, `shop_count:0`. Not an error.
- Overpass down/timeout → cache fallback, `shop_source:"cache"`. Cache also missing →
  `{"status":"error","error":{"code":"no_shop_source","detail":"…"}}`.
- A shop with several OSM tags → `categories` array, primary first. Never truncated to one.
- Addresses absent in OSM → `address: null`. NEVER a synthesized address string.

## Test cases (fixtures in tests/fixtures/, run with REACHOUT_OFFLINE=1)
### T1 — explicit coordinates, happy path
Input: intent from stage-01 T2; CLI `--lat 40.4260 --lng -3.7025 --radius 1.0`
Fixture DB: 3 electronics shops inside 1 km, 1 outside.
Expected: status ok; resolved_from "coordinates"; shop_count 3; shops sorted by
distance_km ascending; every shop has distance_type "haversine" (offline run).

### T2 — neighbourhood name via geocoding
Input: intent with location_text "Lavapiés"; CLI `--radius 0.8` (no lat/lng)
Fixture: geocode fixture returns 40.4089, -3.7038.
Expected: status ok; query_location.lat 40.4089, lng -3.7038;
resolved_from "nominatim" (or "gazetteer" in offline mode); location_text "Lavapiés".

### T3 — Overpass unreachable, cache fallback
Input: CLI `--lat 40.4168 --lng -3.7038 --radius 2 --refresh` with network blocked.
Expected: status ok; shop_source "cache"; shops served from
data/osm_cache/madrid_shops.json. Variant: cache file removed → status "error",
error.code "no_shop_source", and NO shops array.

## Audit before writing
- [ ] you ran scripts/geo_resolve.py; you produced no values yourself.
- [ ] output validates against geo_shops.schema.json.
- [ ] shops are sorted by distance_km ascending.
- [ ] resolved_from and shop_source honestly record what happened.
