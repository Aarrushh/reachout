# tech_stack.md  (Layer 3: what this MVP uses)

## Backend (this repo, built now)

| Part | Choice | Why |
|------|--------|-----|
| Language | Python 3.11+ | stdlib covers most of it; team standard |
| Live store | SQLite (stdlib, WAL mode) | concurrent reads while the simulator writes; zero ops for a one-city MVP |
| Event log | plain JSONL (`data/events.jsonl`) | readable, tail-able, observable |
| Schema checks | `jsonschema` | the hallucination gate; required dependency |
| HTTP client | `requests` | Overpass / Nominatim / ORS calls |
| Tests | `pytest` | TDD per superpowers; offline via fixtures |
| Optional AI | `anthropic` SDK | stages 01/04 only, opt-in via --use-llm |
| Optional API | FastAPI + uvicorn | thin read-only wrapper for the future frontend; last build step |

## External data sources (all free / open)

| Source | Used for | Key? | Fallback |
|--------|----------|------|----------|
| Overpass API | real Madrid shops by tag + radius | no | `data/osm_cache/madrid_shops.json` |
| Overpass Turbo | manual query prototyping (dev tool, not a runtime dep) | no | — |
| Nominatim | neighbourhood name → coordinates | no (UA header + 1 req/s policy) | `data/gazetteer_madrid.json` |
| OpenRouteService | walking distance | free key, `ORS_API_KEY` env | haversine (`scripts/geo.py`), recorded as `distance_type` |
| Geofabrik Madrid extract | bulk offline OSM dump to (re)build the cache | no | — (it IS the fallback source) |

Inventory: real shop identities from OSM; stock is SYNTHETIC, seeded
deterministically per category from `data/sku_catalog.json`
(`random.Random(shop_id)` — reproducible), flagged `synthetic: true`.

## Frontend (architecture fixed now, built in a future phase)

| Part | Choice | Why |
|------|--------|-----|
| Framework | React 19 + Vite + TypeScript | the designated future-UI tools (v0, 21st.dev, ui-ux-pro-max) emit React; fastest path for that phase |
| Routing | React Router; URL query params are the state of record | shareable/back-button-safe; removes the need for a store |
| Server state | TanStack Query | cache keyed on the URL params; no Redux/Zustand for MVP |
| Types | generated from `reachout/shared/schemas/` via json-schema-to-typescript | backend schemas stay the single source of truth |
| Map (future) | MapLibre GL JS | open-source, keyless — consistent with the anti-centralization positioning; consumes stage 05 GeoJSON as-is |

## MCP
None in this phase. A custom MCP server becomes worthwhile only when a real
retailer POS/inventory feed exists (wrap it as a callable tool with auth and
rate limiting); a second candidate is a shared Overpass/Nominatim proxy tool.
Do not build either now.

## A realistic production version (direction, not a promise)
Postgres + PostGIS (spatial index instead of scanning), POS webhooks for real
inventory, push/SMS/websocket ping delivery, the same schemas served over the
same API shape. The deterministic core stays deterministic.
