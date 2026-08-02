# CONTEXT.md  (Layer 1: Where do I go?)

This routes a search through five stages. The folder numbers are the
order. Each stage reads the previous stage's `output/`.

## Pipeline (Madrid test market)

| Stage | Folder | Kind | Reads | Writes |
|-------|--------|------|-------|--------|
| 01 | `stages/01-parse-query/` | Agentic | the user's free text | `output/intent.json` |
| 02 | `stages/02-geo-resolve/` | Hardcoded | `01/output/intent.json` (location_text) + CLI lat/lng/radius + Overpass/Nominatim/ORS (offline fallbacks) | `output/geo_shops.json` |
| 03 | `stages/03-match-and-ping/` | Hardcoded | `01/output/intent.json` + `02/output/geo_shops.json` + live DB | `output/matches.json` + pings |
| 04 | `stages/04-format-results/` | Agentic | `03/output/matches.json` | `output/ranked_shops.json` |
| 05 | `stages/05-map-render/` | Hardcoded | `04/output/ranked_shops.json` | `output/shops.geojson` |

## Run it

```
python run_pipeline.py "algo para el dolor de cabeza" --near "Malasaña" --radius 2
python run_pipeline.py "cargador usb c" --lat 40.4168 --lng -3.7038
```

The orchestrator walks these stages in order and validates every stage's
output against its schema in `shared/schemas/` before the next stage may
read it. It halts on any `status` other than `ok`. To see it live with
stock moving in the background, run `python demo.py`.

## Build status

All five stages are built: 01 `agent/query_parser.py`, 02
`scripts/geo_resolve.py`, 03 `scripts/search_engine.py`, 04
`agent/result_formatter.py`, 05 `scripts/map_render.py`. Each has its
schema in `shared/schemas/`, its contract in its own `CONTEXT.md` +
`prompt.md`, and a test in `tests/`. `run_pipeline.py` walks the full
chain 01 -> 02 -> 03 -> 04 -> 05 in order — no stage is stubbed or
skipped.

## reachout/api/

The Supabase v2 backend: `server.py` (FastAPI app + pipeline endpoints),
`search.py` (`POST /api/search`, pgvector NLP search), `chat.py`
(`POST /api/chat`, AI shopkeeper), `supa.py` (shared Supabase client),
`gemini.py` (Gemini REST helper — embeddings + chat), `madrid.py`
(canonical barrio list), `event_bus.py` (fans out simulator stock events
to SSE subscribers). Reads/writes Supabase (products, stores) plus the
live pipeline's SQLite `data/reachout.db` and `data/events.jsonl` for the
non-v2 endpoints. `server.py` mounts BOTH search implementations on the
same path, split by method: `GET /api/search` is this pipeline (stages
01-05, schema-validated) and `POST /api/search` is the Supabase v2 path
in `search.py`. Decision S6 keeps the consumer UI on the pipeline's
`GET /api/search`; the Supabase path stays mounted but unused by the
frontend. No L2 contract (`CONTEXT.md`) exists for `api/` yet.

## Stage kinds

Agentic stages may use an LLM but default to deterministic logic and always
validate output against a schema. Hardcoded stages are pure Python in
`scripts/` and never call an AI. Stages 02, 03, and 05 are hardcoded on
purpose: locations, distances, stock, and coordinates must never be guessed.
