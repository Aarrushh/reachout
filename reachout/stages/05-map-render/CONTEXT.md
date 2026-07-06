# Stage 05: map-render  (Layer 2 contract)

Kind: Hardcoded. No AI. A mechanical projection of the ranked shop list into
GeoJSON so a FUTURE map UI can consume it. No map is rendered here and no
visual decision of any kind is made — the map itself belongs to a separate
future UI phase. See `prompt.md` for the executor rules.

## Inputs

| Source | File / Location | Scope | Why |
|--------|-----------------|-------|-----|
| Stage 04 | `../04-format-results/output/ranked_shops.json` | full | the only source of facts |
| Schema | `../../shared/schemas/map_geojson.schema.json` | full | output must conform |

## Process  (all pure Python, see scripts/map_render.py)

1. One Point Feature per result. Coordinates in RFC 7946 order:
   [longitude, latitude].
2. Properties copied verbatim: shop_id, shop_name, rank, category, address,
   distance_km, item_name, price, currency, stock_qty. Nothing else.
3. Top-level `metadata` foreign member: query, generated_at, result_count,
   center, radius_km.
4. Bad input → write `output/error.json` (status envelope) and NO .geojson;
   GeoJSON cannot carry a status field, so errors live in the sidecar.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Map data | `output/shops.geojson` | GeoJSON matching map_geojson.schema.json |
| Error sidecar | `output/error.json` | status envelope, only on failure |

## Audit before writing

- [ ] coordinates are [lng, lat] and inside Madrid bounds.
- [ ] feature count equals input result_count (zero is valid).
- [ ] every property value is byte-equal to ranked_shops.json.
