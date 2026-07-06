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

Stages 02 and 05 are fully specified (schemas in `shared/schemas/`,
contracts in their `CONTEXT.md` + `prompt.md`) but their scripts land in
the execution phase — until then the orchestrator walks 01 -> 03 -> 04 on
the legacy seed data. The execution order and definition-of-done per step
live in the approved project plan.

## Stage kinds

Agentic stages may use an LLM but default to deterministic logic and always
validate output against a schema. Hardcoded stages are pure Python in
`scripts/` and never call an AI. Stages 02, 03, and 05 are hardcoded on
purpose: locations, distances, stock, and coordinates must never be guessed.
