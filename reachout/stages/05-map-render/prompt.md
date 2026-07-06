# Stage 05 — map-render  (HARDCODED)

## Role
You are an EXECUTOR, not an author. This stage is pure Python
(`scripts/map_render.py`): a mechanical projection of ranked_shops.json into
GeoJSON for a FUTURE map UI. No map is rendered here; no styling, icons,
colours, or zoom decisions exist in this stage — only data. You never supply
a coordinate from memory.

## Input
- `stages/04-format-results/output/ranked_shops.json`

## Output
- Success: `stages/05-map-render/output/shops.geojson`
  → MUST validate against `shared/schemas/map_geojson.schema.json`
- Failure: `stages/05-map-render/output/error.json` (status envelope) and NO
  .geojson file. (GeoJSON cannot carry a status field, so errors live in a
  sidecar — the orchestrator checks for it.)

## What the script does
1. One Point Feature per result. GeoJSON coordinate order is
   **[longitude, latitude]** per RFC 7946 — the single most common bug in this
   file class; the schema's per-position bounds make a swap fail validation.
2. Feature properties: shop_id, shop_name, rank, category, address, distance_km,
   item_name, price, currency, stock_qty — copied verbatim. Nothing else.
3. Top-level foreign member `metadata`: query, generated_at, result_count,
   center {lat,lng}, radius_km (from the run parameters recorded upstream).

## Never invent
**Never invent a missing field. If a required input field is missing or empty, stop and
return `{"status": "incomplete", "missing_fields": ["<field>", …]}` naming every missing
field. Do not guess, default, infer, or fill a value that was not in your inputs.**
For this stage concretely: a result row missing lat or lng → error.json
`{"status":"incomplete","missing_fields":["results[i].lng"]}`; you never look up or
recall the shop's real position, even though it is a real, findable place.

## Edge cases
- result_count 0 → a VALID FeatureCollection with `"features": []` and
  metadata.result_count 0. Empty map data is still map data.
- ranked_shops status != ok → error.json relaying it; no geojson written.

## Test cases
### T1 — two results
Input: ranked_shops T1 output (shops at 40.4265,-3.7031 and 40.4223,-3.7091).
Expected: FeatureCollection, 2 features, coordinates [-3.7031,40.4265] and
[-3.7091,40.4223] (lng first), properties.rank 1 and 2. Validates.

### T2 — zero results
Input: ranked_shops with result_count 0.
Expected: `{"type":"FeatureCollection","metadata":{…,"result_count":0},"features":[]}`.

### T3 — missing coordinate
Input: ranked_shops whose results[0] lacks "lng".
Expected: output/error.json `{"status":"incomplete","missing_fields":["results[0].lng"]}`;
shops.geojson absent.

## Audit before writing
- [ ] coordinates are [lng, lat] and within Madrid bounds.
- [ ] feature count == input result_count; properties byte-equal to input.
- [ ] validates against map_geojson.schema.json (or error.json written instead).
