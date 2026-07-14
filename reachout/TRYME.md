# Trying it out

Quick guide to running and testing this repo. Requires Python 3.9+.

## 1. Install

```bash
cd reachout
pip install -r requirements.txt
```

## 2. Try it — fastest path

No API key, no network needed:

```bash
REACHOUT_OFFLINE=1 python run_pipeline.py "algo para el dolor de cabeza" --near "Malasaña"
```

Prints each of the 5 stages running, then a ranked list of nearby shops with
the item in stock. Or search by coordinates instead of a neighbourhood name:

```bash
REACHOUT_OFFLINE=1 python run_pipeline.py "cargador usb c" --lat 40.4168 --lng -3.7038
```

Drop `REACHOUT_OFFLINE=1` to let it hit the live Overpass/Nominatim APIs
instead of the committed Madrid cache.

## 3. Try it — live demo

Watches stock change between searches in real time:

```bash
python demo.py
# or fully offline:
REACHOUT_OFFLINE=1 python demo.py
```

Runs four sample searches a few seconds apart while a background thread
moves inventory. Check `data/notifications/` afterward to see the pings
each matched shop received.

Optional: watch inventory move in one terminal while searching in another:

```bash
python scripts/inventory_simulator.py
# elsewhere:
tail -f data/events.jsonl
```

## 4. Run the test suite

```bash
REACHOUT_OFFLINE=1 pytest tests/
```

All tests run offline against fixtures/committed cache data — no network
calls, no API key required.

## 5. Optional: LLM-backed parsing/formatting

Only needed if you want to test the AI path instead of the default
rule-based one:

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...
python run_pipeline.py "algo para mi resfriado" --use-llm
```

Any LLM output that fails schema validation is discarded and the
deterministic result is used instead — so this is safe to try even if
something goes wrong.

## 6. Optional: Live End-to-End Verification

You can verify that a running backend is healthy, correctly paginates inventory, and streams events via our verification script.
With a local instance running (`REACHOUT_SIM=1 uvicorn api.server:app --reload`), in another terminal run:

```bash
python scripts/verify_live.py
```

It should pass all assertions. You can override the base URL by passing `--url http://other-host:8000`.

## 7. Optional: API + frontend

```bash
# Optional: run with the background inventory simulator ticking
REACHOUT_SIM=1 uvicorn api.server:app --reload
```

Then try the endpoints:

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

The frontend skeleton lives in `../frontend/` (see its own README).
