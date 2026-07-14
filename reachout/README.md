# ReachOut

A hyperlocal demand router. A shopper searches for an item. Shops within a
radius that have it in live stock get pinged instantly. The shopper sees who
has it, how far, and at what price.

Madrid is the test market: real shops sourced from OpenStreetMap, synthetic
inventory. This repo is built so that the parts that must be exact are
exact, and the AI only handles the parts where language understanding helps.
That split is the whole point. It is how the system avoids inventing stock
that does not exist.

## The idea in one line

You do not browse a store. You say what you need, and nearby stores answer.

## How it is built

The folder structure is the architecture. This follows ICM, the Interpretable
Context Methodology (Van Clief and McDermott, arXiv:2603.16021, 2026). Numbered
stage folders run in order. Each writes a plain file the next one reads.

```
reachout/
  CLAUDE.md            Layer 0. Identity. Read first.
  CONTEXT.md           Layer 1. Stage order.
  _config/             Layer 3. Product, constraints, tech stack.
  shared/schemas/      JSON schemas. The hallucination gate.
  stages/
    01-parse-query/     Agentic.   free text                -> structured intent
    02-geo-resolve/      Hardcoded. intent + lat/lng/radius   -> shops in range
    03-match-and-ping/   Hardcoded. intent + geo shops + DB   -> matches + pings
    04-format-results/   Agentic.   matches                  -> ranked shop list
    05-map-render/       Hardcoded. ranked shops              -> GeoJSON
  scripts/             Pure Python. No AI. The deterministic core.
  agent/               Optional LLM adapter plus rule-based fallback.
  data/                Live SQLite store, event log, shop inboxes, OSM cache.
  run_pipeline.py      Orchestrator. Walks the stages, hard-halts on any
                       non-"ok" status or schema failure.
  demo.py              Live end-to-end demo.
```

## The hardcoded / agentic split

Hardcoded, in `scripts/`, no AI: geocoding/radius selection, distance, stock
levels, matching, ranking, GeoJSON projection, database writes, pings. A
wrong guess here would invent a real-world fact, so no AI is allowed near it.

Agentic, in `stages/` (backed by `agent/`), optional LLM: understanding a
vague query like "algo para el dolor de cabeza", and normalizing item-name
casing in the final list. Even here every output is checked against a schema
before the next stage trusts it.

## Run it

```
pip install -r requirements.txt
python demo.py                       # live demo: stock moves while you search
```

`demo.py` ingests real Madrid shops from the committed OSM cache (or live
Overpass, if reachable) and seeds each one with deterministic synthetic
inventory — no separate seed step required.

Single search, by neighbourhood name:

```
python run_pipeline.py "algo para el dolor de cabeza" --near "Malasaña" --radius 2
```

Single search, by explicit coordinates:

```
python run_pipeline.py "cargador usb c" --lat 40.4168 --lng -3.7038
```

Defaults to Madrid (Puerta del Sol) if neither `--near` nor `--lat`/`--lng`
is given. `--refresh` re-fetches shops from Overpass instead of using the
cached/DB copy. Every stage's output lands in that stage's `output/` folder
and is schema-validated before the next stage may read it; the orchestrator
halts immediately on any `status` other than `"ok"`.

Watch live inventory move in another terminal:

```
python scripts/inventory_simulator.py
# then, elsewhere:
tail -f data/events.jsonl
```

Run fully offline (uses the committed OSM cache and gazetteer, no network
calls):

```
REACHOUT_OFFLINE=1 python run_pipeline.py "leche y pan" --near "Lavapiés"
```

## Optional AI parser and formatter

The repo runs fully without any API key, using rule-based logic for both
stage 01 (query parsing) and stage 04 (result formatting). To use an LLM
instead:

```
pip install anthropic
export ANTHROPIC_API_KEY=...
python run_pipeline.py "algo para mi resfriado" --use-llm
```

See `agent/llm.py` and `agent/result_formatter.py`. The model name is a
single constant, overridable via the `ANTHROPIC_MODEL` env var. Any LLM
output that fails schema validation is discarded and the deterministic
result is used instead.

## What is sample versus real

The shops come from a real OpenStreetMap snapshot of Madrid (committed at
`data/osm_cache/madrid_shops.json`, refreshable live via Overpass). The
stock levels and the inventory simulator are synthetic, seeded
deterministically per shop for the MVP. The product catalog itself is sourced 
from DummyJSON (using a 1:1 EUR conversion rate convention) and cached 
offline. In production the simulator is replaced by a real sync from each 
shop's point-of-sale or inventory system. The matching engine, the schemas, 
and the stage structure stay the same.

## API

The backend runs a read-only FastAPI service:

```bash
cd reachout
# Optional: run with the background inventory simulator ticking
REACHOUT_SIM=1 uvicorn api.server:app --reload
```

Examples of calling the endpoints:

```bash
# List all regions
curl -s "http://localhost:8000/api/regions"

# View paginated inventory
curl -s "http://localhost:8000/api/inventory?page=1&page_size=10"

# Search with pagination
curl -s "http://localhost:8000/api/search?q=cargador&near=Malasana&page=1"

# Stream live stock events (use -N to disable curl buffering)
curl -N "http://localhost:8000/api/inventory/stream"
```

## Tests

```
REACHOUT_OFFLINE=1 pytest tests/
```

## License

MIT. See LICENSE.
