# Stage 02: geo-resolve  (Layer 2 contract)

Kind: Hardcoded. No AI. This stage decides WHERE the user is and WHICH real
shops are in range. Coordinates, distances, shop names, and addresses are
looked up or computed, never guessed. See `prompt.md` for the executor rules.

## Inputs

| Source | File / Location | Scope | Why |
|--------|-----------------|-------|-----|
| Stage 01 | `../01-parse-query/output/intent.json` | `location_text`, `category_hints` | the place the user named, if any |
| CLI | lat, lng, near, radius passed to the pipeline | full | explicit geofence |
| Overpass API | live, via `scripts/overpass.py` | shops by tag in radius | real Madrid shops |
| OSM cache | `data/osm_cache/madrid_shops.json` | full | offline fallback for Overpass |
| Nominatim | live, via `scripts/nominatim.py` | one geocode per run, cached | neighbourhood name → coordinates |
| Gazetteer | `data/gazetteer_madrid.json` | full | offline fallback for Nominatim |
| ORS | live, needs ORS_API_KEY, via `scripts/ors.py` | walking distance | more honest than straight-line |
| Tag map | `data/category_tag_map.json` | full | internal category → OSM selectors |

## Process  (all pure Python, see scripts/geo_resolve.py)

1. Resolve the query centre: explicit coords > location_text via Nominatim /
   gazetteer > default centre Puerta del Sol (40.4168, -3.7038). Record the
   path taken in `resolved_from`. A named place that cannot be resolved is
   `status: incomplete`, never silently defaulted.
2. Select shops in radius from the ingested shops table; `--refresh` pulls
   live from Overpass first, upserting new shops and seeding their synthetic
   inventory deterministically. Record `shop_source`.
3. Filter by `category_hints` intersection when hints exist.
4. Compute distance (ORS walking, else haversine), record `distance_type`,
   sort nearest first.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Shops in radius | `output/geo_shops.json` | JSON matching `shared/schemas/geo_shops.schema.json` |

## Why no AI here

A wrong guess here invents a real-world fact: a shop that doesn't exist, a
distance that's wrong, an address no one lives at. That is the exact failure
ReachOut cannot have. Every external lookup has a committed offline fallback
so "the API is down" never becomes "make something up".
