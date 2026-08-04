# JULES_BACKEND.md — Multi-Region Live Inventory, Task Series for Jules

*Planning document. Each TASK below is submitted to Jules (Google's autonomous
coding agent, API key placeholder `[JULES_API_KEY]`, repo `Aarrushh/reachout`)
one at a time, in order, via the runner in §4. Every task is atomic and
independently testable. No code in this file — specs only.*

---

## 1. MASTER CONTEXT BLOCK (prepend to every Jules task)

```
Repo: Aarrushh/reachout. Python 3.11 backend lives in reachout/ (nested):

reachout/
├── api/server.py          thin read-only FastAPI wrapper; CORS GET-only "*";
│                          endpoints: /api/health, /api/search,
│                          /api/search.geojson, /api/shops.geojson.
│                          Each search request runs the full pipeline in a
│                          throwaway tempdir via run_pipeline.run(q, near, lat,
│                          lng, radius_km, db_path, notif_dir, output_root);
│                          PipelineError → HTTP 422. Module-level DB_PATH /
│                          NOTIF_DIR are None by default and monkeypatched in
│                          tests — preserve that seam in everything you add.
├── run_pipeline.py        5-stage orchestrator; halts on schema failure or
│                          any stage status != "ok" (PipelineError).
├── scripts/               PURE PYTHON ONLY (see rules): db.py (SQLite WAL,
│                          connect/init_db/upsert_shop/upsert_item/adjust_qty/
│                          all_shops/items_for_shop), geo.py (haversine),
│                          inventory_seeder.py (seed_shop: deterministic via
│                          random.Random(shop_id)), inventory_simulator.py
│                          (_tick: sale 55% / restock 30% / new_item 15%;
│                          run_simulator(stop_event, interval, seconds,
│                          db_path); appends data/events.jsonl),
│                          search_engine.py (whole-word matcher; _item_out
│                          shapes the per-item fields), validate.py
│                          (validate(data, schema_filename) -> (ok, err)),
│                          nominatim.py (barrio → coords, offline fallback
│                          data/gazetteer_madrid.json), plus overpass.py,
│                          ors.py, osm_ingest.py, geo_resolve.py, ping.py,
│                          map_render.py.
├── agent/                 query_parser.py, result_formatter.py (stage 04
│                          builds ranked results from stock_matches),
│                          llm.py (opt-in only).
├── shared/schemas/        Draft-07 JSON Schemas, additionalProperties:false
│                          everywhere. Existing: search_intent, geo_shops,
│                          stock_matches, ranked_shops, map_geojson,
│                          shops_geojson, shop_record, inventory_record.
├── data/                  reachout.db (SQLite WAL; tables: shops(shop_id,
│                          osm_id, name, categories JSON-text, lat, lng,
│                          address, source, fetched_at), inventory(shop_id,
│                          sku, name, category, price, currency, qty,
│                          synthetic, updated_at, PK(shop_id,sku)));
│                          events.jsonl; gazetteer_madrid.json (24 barrios:
│                          {"malasaña": {"lat": 40.4267, "lng": -3.7038}, ...},
│                          keys lowercase, accent-insensitive lookup, has a
│                          "_comment" key — always skip it);
│                          sku_catalog.json ({"pharmacy": [{"sku": "PHA-0001",
│                          "name": "...", "base_price_eur": 3.95}, ...], ...} —
│                          5 categories × 10 template SKUs, plus "_comment").
└── tests/                 pytest, 93 tests, all offline (REACHOUT_OFFLINE=1
                           honored; fixtures in conftest.py build temp DBs).

RULES — read before every task:
1. SCHEMA-FIRST (the iron rule). No API response field may exist unless a
   schema in shared/schemas/ defines it, with additionalProperties:false on
   every object. Endpoints validate their response body at request time via
   validate.validate(body, "<name>.schema.json") and return HTTP 500 on
   schema failure, exactly like the existing /api/shops.geojson does.
   Schema task ALWAYS lands before the code task that emits the field.
2. NO AI IN scripts/. scripts/ is pure computation + explicit HTTP fetchers.
   Never import anthropic/llm.py there. Never add an LLM call anywhere in
   this work — no task needs one.
3. DO NOT TOUCH unless a task names the file: scripts/geo.py, geo_resolve.py,
   overpass.py, nominatim.py, ors.py, osm_ingest.py, ping.py, map_render.py,
   validate.py; agent/query_parser.py, agent/llm.py; stages/*/CONTEXT.md;
   run_pipeline.py stage logic (only the bootstrap hook named in TASK 26 may
   change); the existing pipeline schemas except the three with named tasks:
   ranked_shops.schema.json + inventory_record.schema.json (TASK 21) and
   stock_matches.schema.json (TASK 22).
4. TECH STACK IS FROZEN-SIMPLE: SQLite WAL (stdlib sqlite3), APScheduler
   (in-process), asyncio.Queue for the event bus, FastAPI StreamingResponse
   for SSE. NO Redis, NO Kafka, NO Celery, NO websockets, NO sse-starlette,
   NO ORM, NO new services.
5. Categories are exactly: pharmacy, grocery, hardware, electronics,
   stationery. SKU pattern is ^[A-Z]{3}-[0-9]{4}$. Currency is const "EUR".
   synthetic is const true.
6. Every task ships its pytest coverage in the same branch; the full suite
   (cd reachout/tests && python -m pytest) must stay green and offline —
   any network call in a test is a defect. New fetchers get committed
   fixture/cache files like the existing data/osm_cache/ pattern.
7. Style: stdlib-first, plain functions, module docstrings explaining WHY,
   no classes where a function does the job, match the existing code.
```

---

## 2. TOOL OVERVIEW — Jules

**What it is.** Jules (jules.google) is Google's asynchronous coding agent: you
give it a GitHub repo and a prompt; it clones the repo into a Cloud VM, forms a
plan, edits files, runs commands/tests, and pushes a branch / opens a PR for
review. API access (v1alpha, `X-Goog-Api-Key: [JULES_API_KEY]`) exposes
*sessions* (one task each) and *activities* (plan, progress, completion) — see
the runner in §4.

**What it's good at**
- Self-contained, well-specified tasks against an existing test suite — exactly
  what the atomic tasks below are shaped like.
- Running the repo's tests in its VM and iterating until green.

**Limitations to design around**
- Session-scoped memory: it forgets everything between tasks — hence the master
  context block on every submission.
- Quota: concurrent-session and daily-task limits apply (plan-dependent; free
  tier is ~15 tasks/day, 3 concurrent) — the runner submits sequentially and
  a full 52-task run may span multiple days on a free tier.
- It can drift on broad refactors — tasks below never span more than one
  concern; each names its files and its done-criteria.
- It needs the Jules GitHub app installed on `Aarrushh/reachout`, and it works
  on a branch per session — the runner merges (or you review-merge) between
  dependent tasks, so each task starts from the previous task's result. Set
  `startingBranch` accordingly.
- No long-lived processes in the VM: it can run pytest, not a persistent
  uvicorn — SSE tests must use in-process ASGI clients (they do, TASK 46).

**Alternative:** **GitHub Copilot coding agent / Copilot Workspace** — assign
each task as a GitHub Issue to Copilot; same atomic-task discipline applies.
The task specs below work unchanged as issue bodies.

---

## 3. THE TASK SERIES (52 tasks)

Conventions: every task = one Jules session = one reviewable branch. "Tests:"
names the new/changed test files; the whole suite must pass. Tasks are grouped
in phases; order within a phase is mandatory.

### Phase 0 — Foundations

**TASK 01 — Add APScheduler dependency.**
Edit `reachout/requirements.txt`: add `apscheduler>=3.10` with a comment
("in-process scheduler for the live-inventory simulator; no broker"). No other
new dependencies in this entire work. Done: `pip install -r requirements.txt`
clean; suite green.

**TASK 02 — Migration runner.**
New `reachout/scripts/migrations.py`: `migrate(conn)` applies numbered
migrations via `PRAGMA user_version` (list of `(version, sql)` pairs, applied
in a transaction, idempotent, monotonic). `db.init_db()` calls `migrate` after
its `executescript`. Existing DBs (user_version 0) and fresh DBs both end at
the latest version. Tests: new `tests/test_migrations.py` — fresh DB, re-run
idempotence, partial-version upgrade.

**TASK 03 — Migration 1: `regions` table.**
In `migrations.py` add migration 1:
`regions(region_id TEXT PRIMARY KEY, name TEXT NOT NULL, lat REAL NOT NULL,
lng REAL NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL)`.
`region_id` is a lowercase ASCII slug (e.g. `malasana`), `name` the display
form (e.g. `Malasaña`), `source` const-ish `"gazetteer"` for now. Tests:
table exists post-migrate, columns exact.

**TASK 04 — Migration 2: `shops.region_id`.**
Migration 2: `ALTER TABLE shops ADD COLUMN region_id TEXT` (nullable — a shop
outside every region stays NULL) + `CREATE INDEX idx_shops_region ON
shops(region_id)`. Tests: column + index exist; old rows NULL.

**TASK 05 — Migration 3: inventory `source`, `rating`, `review_count`.**
Migration 3: `ALTER TABLE inventory ADD COLUMN source TEXT NOT NULL DEFAULT
'template'`; `ADD COLUMN rating REAL` (nullable, 0–5); `ADD COLUMN
review_count INTEGER` (nullable). `source` ∈ {'template','dummyjson'} —
enforced in code, not SQL. Tests: defaults on existing rows, new columns
readable through `db.items_for_shop`.

**TASK 06 — db.py region + pagination helpers.**
Add to `scripts/db.py`: `upsert_region(conn, region)`; `all_regions(conn)`
(rows as dicts, ordered by name); `shops_in_region(conn, region_id)`;
`region_shop_counts(conn)` → `{region_id: count}`;
`inventory_page(conn, region_id, page, page_size, in_stock_only=False)` →
`(rows, total)` using `LIMIT/OFFSET` with a join on shops for region filtering,
ordered by `shop_id, sku` (stable pagination). Extend `upsert_item` to persist
`source`/`rating`/`review_count` when present (defaults: 'template', None,
None) — keep the existing call sites valid. Tests: extend
`tests/test_db.py` — empty region, page beyond end, total correctness.

### Phase 1 — Schemas (before any endpoint that uses them)

All schemas: Draft-07, `additionalProperties: false` on EVERY object node,
placed in `reachout/shared/schemas/`, each with a `description` saying who
produces and who consumes it. Register example fixtures under
`tests/fixtures/`.

**TASK 07 — `region_record.schema.json`.**
Required: `region_id` (pattern `^[a-z0-9-]+$`), `name` (minLength 1), `lat`
(40.2–40.7), `lng` (−4.0 to −3.4), `source` (enum: `gazetteer`), `shop_count`
(integer ≥ 0). Tests: valid/invalid fixtures through `validate.validate`.

**TASK 08 — `regions_response.schema.json`.**
Envelope for `GET /api/regions`: required `status` (enum ok|error),
`generated_at` (date-time), `region_count` (int ≥ 0), `regions` (array of
region_record's object shape inlined — the validator loads single files, so
inline rather than `$ref` across files, matching existing schema style).
Optional `error {code, detail}` mirroring ranked_shops' error object. Tests:
fixtures both ways.

**TASK 09 — `inventory_response.schema.json`.**
Envelope for `GET /api/inventory`: required `status`, `generated_at`,
`region_id` (nullable string), `page` (int ≥ 1), `page_size` (int 1–100),
`total_items` (int ≥ 0), `total_pages` (int ≥ 0), `items` (array). Item
object: `shop_id`, `shop_name`, `sku`, `name`, `category` (5-enum), `price`,
`currency` (const EUR), `qty` (≥ 0), `synthetic` (const true), `source`
(enum template|dummyjson), `updated_at`; optional `rating` (0–5),
`review_count` (≥ 0). Tests: fixtures.

**TASK 10 — `stock_event.schema.json`.**
One SSE payload: required `type` (enum sale|restock|new_item), `shop_id`
(osm pattern), `shop_name`, `region_id` (string|null), `sku` (SKU pattern),
`name`, `qty_now` (int ≥ 0), `ts` (date-time, ISO — NOT the epoch float the
current events.jsonl uses; the SSE bus is a new contract). Optional: `sold`,
`added` (int ≥ 1, per type). Tests: one fixture per event type + rejects.

**TASK 11 — `health_response.schema.json`.**
Required `status` (enum ok); optional `shop_count` (int ≥ 0), `region_count`
(int ≥ 0), `simulator_running` (boolean). Existing `{"status": "ok"}` must
still validate (backward compatible). Tests: fixtures.

**TASK 12 — `search_page.schema.json`.**
Paginated envelope for `GET /api/search` WHEN `page` is requested: everything
in ranked_shops.schema.json's ok-shape PLUS required `page` (≥ 1), `page_size`
(1–50), `total_results` (≥ 0), `total_pages` (≥ 0). `results` carries only the
page slice; `result_count` equals the slice length; ranks stay the GLOBAL
ranks (page 2 starts at rank 11) — document that in the description. The
un-paginated `/api/search` response continues to use ranked_shops.schema.json
unchanged. Tests: fixtures.

**TASK 13 — Schema round-trip test sweep.**
New `tests/test_new_schemas.py`: table-driven — every fixture from TASKS 07–12
validates; a mutated copy (one extra property injected at every object level)
fails, proving additionalProperties:false coverage. Done: proves the
hallucination gate holds on all six new schemas.

### Phase 2 — DummyJSON product catalog

**TASK 14 — DummyJSON fetcher.**
New `reachout/scripts/dummyjson_fetch.py` (pure fetch + save; pattern-match
`overpass.py`): `fetch_products(cache_only=False)` GETs
`https://dummyjson.com/products?limit=0` (returns all 194 products, no key),
saves raw JSON to `data/dummyjson_cache/products.json`, returns the parsed
list. `REACHOUT_OFFLINE=1` (or `cache_only`) reads the committed cache and
never touches the network. CLI: `python scripts/dummyjson_fetch.py
[--refresh]`. Commit the fetched cache file in this branch (Jules VM has
network). Tests: `tests/test_dummyjson_fetch.py` — offline path only, cache
shape sanity (list, has `title`/`price`/`category`/`rating` keys).

**TASK 15 — Category mapper.**
New pure function `map_category(dummyjson_category) -> str | None` in
`scripts/dummyjson_catalog.py`:
`groceries→grocery`; `beauty, skin-care, fragrances→pharmacy`;
`smartphones, laptops, tablets, mobile-accessories→electronics`;
`furniture, home-decoration, kitchen-accessories, lighting,
sports-accessories, motorcycle, vehicle→hardware`; everything else (apparel,
jewellery, watches, bags, sunglasses…) → None (dropped — a Madrid barrio
pharmacy does not stock womens-dresses). DummyJSON has NO stationery-like
category: stationery keeps only template SKUs — assert that in a test.
Tests: `tests/test_dummyjson_catalog.py` — full mapping table, None cases.

**TASK 16 — Catalog builder + merge.**
In `scripts/dummyjson_catalog.py`: `build_entries(products)` → catalog entries
`{sku, name (=title), base_price_eur (=price, rounded to cents, treated 1:1
as EUR — synthetic data, no FX), rating (float), review_count
(=len(reviews)), source: "dummyjson"}` where sku = `{PHA|GRO|HAR|ELE|STA}-` +
`str(1000 + product id)` — the 1000 offset guarantees no collision with
template SKUs (…-0001 to …-0010) and satisfies `^[A-Z]{3}-[0-9]{4}$`.
`merge_catalog()` writes `data/sku_catalog.json` v2: existing template entries
untouched (they gain `source: "template"`), DummyJSON entries appended under
their mapped category, `_comment` updated. CLI: `python
scripts/dummyjson_catalog.py`. Run it; commit the merged catalog. Tests:
SKU pattern/uniqueness across the whole merged catalog, template entries
byte-identical apart from the source key.

**TASK 17 — Catalog schema.**
New `sku_catalog.schema.json`: object with optional `_comment` (string) and
one optional property per category (5-enum keys), each an array of entries:
required `sku`, `name`, `base_price_eur`, `source` (enum template|dummyjson);
optional `rating` (0–5), `review_count` (≥ 0). *(Schema lands after the file
format in TASK 16 only because the catalog is an internal data file, not an
API response; it still lands before anything consumes the new fields.)* Add a
test validating the actual committed `data/sku_catalog.json` against it.

**TASK 18 — Seeder carries the new fields.**
`scripts/inventory_seeder.py::seed_shop`: each seeded item now includes
`source`, `rating`, `review_count` from its catalog entry (template entries:
'template', None, None). Determinism guarantee unchanged: same shop_id ⇒ same
inventory — but the catalog grew, so seeded subsets change once; that is
expected and the determinism test asserts stability across two runs, not
against pre-merge snapshots. Tests: extend `tests/test_inventory_seeder.py`.

**TASK 19 — Simulator reads the richer catalog.**
`scripts/inventory_simulator.py::_tick` new_item branch: pass the entry's
`source`/`rating`/`review_count` into `db.upsert_item`; event log line gains
`source`. No behavior change otherwise. Tests: extend
`tests/test_inventory_simulator.py` (seeded RNG, temp DB).

**TASK 20 — Reseed script.**
New `scripts/reseed_inventory.py`: CLI that wipes `inventory` and reseeds
every shop via `seed_shop` (transactional, prints counts). The DB file is
gitignored and regenerated per environment — never commit it; the CLI
docstring tells operators to run this once after any catalog change.
Tests: on a temp DB — after reseed, some items have source='dummyjson' in
each mapped category and stationery has only 'template'.

**TASK 21 — Ratings enter the API contract (schema-first).**
Edit `ranked_shops.schema.json`: each result gains OPTIONAL `rating` (number
0–5) and `review_count` (integer ≥ 0) — not in `required`. Edit
`inventory_record.schema.json` identically plus optional `source` (enum
template|dummyjson). Bump both descriptions. Frontend note in the task output:
`cd frontend && npm run gen-types` must be rerun (do not edit
`frontend/src/types/` by hand — flag it, the runner's human does it or TASK 50
covers docs). Tests: fixtures with and without the new fields validate.

**TASK 22 — Ratings flow through the pipeline.**
`scripts/search_engine.py::_item_out` adds `rating`/`review_count`/`source`
when the inventory row has them (omit when NULL — schemas make them optional,
and stock_matches.schema.json must gain the same optional fields in THIS task,
schema edit first within the branch). `agent/result_formatter.py` copies them
into ranked results when present, never invents them. Tests: extend
`tests/test_search_engine.py` + `tests/test_result_formatter.py` — a
dummyjson-sourced row surfaces rating end-to-end; a template row yields no
rating key at all.

### Phase 3 — Regions

**TASK 23 — Region seeder.**
New `scripts/region_seeder.py`: `seed_regions(conn, gazetteer_path=None)` —
reads `data/gazetteer_madrid.json` (skip `_comment`), slugifies each barrio
name to `region_id` (lowercase, strip accents, spaces→`-`), upserts 24 rows
(`source: "gazetteer"`). Idempotent. Tests: `tests/test_region_seeder.py`
with a 3-barrio fixture gazetteer — count, slug correctness
(`Malasaña → malasana`), re-run stability.

**TASK 24 — Shop→region assignment.**
In `region_seeder.py`: `assign_shops(conn, max_km=1.2)` — each shop gets the
`region_id` of the nearest region centroid within `max_km` (use
`geo.haversine` — import it, do NOT modify geo.py), else NULL. Report dict
`{assigned, unassigned}`. SUGGESTION: nearest-centroid is a crude proxy for
real barrio polygons; good enough for the demo, and polygon data would need a
new dependency (shapely) — flag but don't do it. Tests: synthetic shops at
known offsets — inside, boundary, outside.

**TASK 25 — Seeder CLI.**
`python scripts/region_seeder.py` runs seed_regions + assign_shops and prints
the report (the DB is gitignored — nothing to commit; TASK 26's bootstrap
covers fresh environments). Tests: CLI smoke via subprocess on a temp DB
(offline).

**TASK 26 — Bootstrap hook.**
`run_pipeline.py::_ensure_db_ready` (the ONLY permitted run_pipeline edit):
after its existing first-run ingest, if `regions` is empty → call
`region_seeder.seed_regions` + `assign_shops`. Tests: fresh temp DB through
the existing e2e fixture path ends with populated regions
(`tests/test_pipeline_e2e.py` extension).

**TASK 27 — `GET /api/regions`.**
In `api/server.py`: returns `{status, generated_at, region_count, regions:[
{region_id, name, lat, lng, source, shop_count}]}` from `db.all_regions` +
`db.region_shop_counts`; validated against `regions_response.schema.json`
(500 on failure, like shops.geojson); `Cache-Control: public, max-age=3600`.
Tests: extend `tests/test_api.py` (TestClient + monkeypatched DB_PATH) —
shape, counts, schema-validity, cache header.

**TASK 28 — `GET /api/inventory`.**
`/api/inventory?region=<region_id>&page=1&page_size=25&in_stock=0|1` →
`inventory_response.schema.json`. Unknown region → 404; page < 1 or
page_size ∉ [1,100] → 422 (FastAPI validation via Query(ge=, le=)); omitted
region → whole city. Joins shop_name via `db.inventory_page`. Validated at
request time. Tests: pagination math (total_pages ceil), 404, 422 bounds,
empty page, schema-validity.

**TASK 29 — `/api/search` pagination.**
Add optional `page: int | None = Query(None, ge=1)` and `page_size: int =
Query(10, ge=1, le=50)` to `/api/search`. `page is None` → EXACTLY today's
behavior and schema (backward compatible — the deployed frontend keeps
working). `page` given → run the pipeline once, slice `results`, keep global
ranks, emit the `search_page.schema.json` envelope, validate before returning.
Tests: no-page byte-parity with old shape; page math; out-of-range page →
empty results, correct totals; 422 on bad page_size.

**TASK 30 — `/api/search` region parameter.**
Optional `region: str | None` on `/api/search` and `/api/search.geojson`:
resolves the region's centroid from the `regions` table and forwards as
lat/lng to the pipeline (mutually exclusive with near/lat/lng → 400 if
combined; unknown region → 404). This gives the frontend's region selector a
first-class server contract instead of overloading `near`. Tests: resolution
correctness, 400/404 paths, geojson variant.

**TASK 31 — `/api/health` v2.**
Extend to `{status, shop_count, region_count, simulator_running}` per
`health_response.schema.json`, validated. `simulator_running` reads the
scheduler state (False until Phase 4 lands — import guarded). Tests: shape +
schema; still returns fast with no DB rows.

### Phase 4 — Live simulation: APScheduler + SSE

**TASK 32 — Event bus.**
New `reachout/api/event_bus.py`: class `EventBus` — `subscribe() ->
asyncio.Queue` (maxsize 100), `unsubscribe(q)`, `publish(event: dict)` fans
out with `put_nowait`, dropping the OLDEST item on a full queue (slow client
never blocks the simulator or other clients). Module-level singleton `BUS`.
Pure asyncio, no globals beyond the singleton, no locks needed (single loop).
Tests: new `tests/test_event_bus.py` with `pytest` + `asyncio` — fan-out to 2
subscribers, drop-oldest on overflow, unsubscribe stops delivery.

**TASK 33 — Simulator tick returns its event.**
Refactor `scripts/inventory_simulator.py::_tick(conn)` to build the movement
dict once, `_log_event` it (events.jsonl unchanged, epoch `ts` kept there),
and RETURN it (None when the tick chose a shop with nothing to do). Add
`shop_name` alongside the existing `shop` key? No — keep keys as-is in the
jsonl; the API layer remaps. `run_simulator` behavior unchanged. Tests:
extend `tests/test_inventory_simulator.py` — returned dict matches the logged
line for all three movement types (seeded RNG).

**TASK 34 — Stock-event shaping.**
New function in `api/event_bus.py` (or `api/stock_events.py` if cleaner):
`to_stock_event(raw, region_id) -> dict` — maps the simulator dict to the
`stock_event.schema.json` shape (`shop` → `shop_name`, epoch → ISO `ts` via
`db.now_iso()`, inject `region_id`, keep `sold`/`added` when present) and
validates it via `validate.validate`; invalid → raise (a malformed event must
fail loudly in tests, never stream). Tests: all three types validate; a
mutated raw event raises.

**TASK 35 — APScheduler lifespan integration.**
`api/server.py`: FastAPI `lifespan` context manager. When env
`REACHOUT_SIM=1`: start `apscheduler.schedulers.asyncio.AsyncIOScheduler`
with one interval job (every 2s, jitter 1s): run ONE simulator tick —
`await asyncio.to_thread(tick_once)` where `tick_once` opens a short-lived
`db.connect(DB_PATH)` (WAL handles the concurrency; never share a sqlite
connection across threads), commits, closes; look up the shop's `region_id`;
`BUS.publish(to_stock_event(...))` when the tick produced a movement.
Scheduler shuts down cleanly on app exit. Default (env unset — ALL tests) =
no scheduler, exactly today's behavior. Tests: with REACHOUT_SIM unset the
app has no scheduler; a direct call of `tick_once` on a seeded temp DB
publishes one valid event to a subscribed queue.

**TASK 36 — `GET /api/inventory/stream` (SSE).**
`/api/inventory/stream?region=<optional>` → `StreamingResponse`
(`media_type="text/event-stream"`, headers `Cache-Control: no-cache`,
`X-Accel-Buffering: no`). Async generator: `q = BUS.subscribe()`;
`try/finally BUS.unsubscribe(q)`; loop `asyncio.wait_for(q.get(),
timeout=15)` — on timeout yield an SSE comment heartbeat (`": keep-alive\n\n"`),
on event: skip when a region filter is set and doesn't match, else yield
`"event: stock\ndata: " + json.dumps(event) + "\n\n"`. First frame on
connect: `"event: hello\ndata: {\"region\": ...}\n\n"` so clients confirm
subscription. NOTE: CORS middleware currently allows GET only — SSE is GET,
no change needed; do not widen CORS. Tests: see TASK 37.

**TASK 37 — SSE tests.**
`tests/test_sse_stream.py`: using `httpx.AsyncClient` +
`httpx.ASGITransport(app=server.app)` and `client.stream("GET", ...)`:
(a) hello frame arrives; (b) `BUS.publish` of a valid event is received and
parses back to the schema-valid dict; (c) region filter drops mismatches;
(d) disconnect removes the subscriber (bus subscriber count returns to
baseline). `httpx` is already a transitive dev dependency of nothing here —
add `httpx>=0.27` to requirements.txt as a test dependency with a comment
(counts as the one Phase-4 test-only exception to TASK 01's "no other deps",
declared here deliberately).

**TASK 38 — Simulator honors regions in demo.py.**
`demo.py`: mention regions in its printed narration (count from
`db.all_regions`) and set `REACHOUT_SIM=1` guidance in its docstring — demo
still runs the thread-based simulator directly (unchanged behavior), the API
scheduler is for server deployments. Tests: none (demo is uncovered by
design); suite must stay green.

**TASK 39 — events.jsonl ↔ SSE parity test.**
`tests/test_event_parity.py`: run 30 seeded ticks on a temp DB through
`tick_once`; every published SSE event has a corresponding jsonl line (same
sku, type, qty_now) — the two streams may format differently but never
disagree on facts. Guards against the streams drifting apart later.

### Phase 5 — Hardening & consistency

**TASK 40 — Concurrency smoke test.**
`tests/test_concurrent_sim_search.py`: temp DB; thread A runs
`run_simulator(seconds=3, interval=0.05)`; main thread hammers
`db.inventory_page` + `search_engine.search` concurrently; assert no
`sqlite3.OperationalError` (WAL + busy_timeout hold) and every read is
internally consistent (total ≥ len(rows)).

**TASK 41 — 422/400/404 error-shape audit.**
`tests/test_api_errors.py`: table-driven over every new endpoint × every
documented error: status code AND `{"detail": ...}` body shape (FastAPI
default) asserted. No endpoint may 500 on bad user input.

**TASK 42 — Pagination determinism test.**
`tests/test_pagination_stability.py`: with the simulator OFF, walking
`/api/inventory` pages 1..N yields each `(shop_id, sku)` exactly once (the
`ORDER BY shop_id, sku` contract from TASK 06). Prevents a future
unordered-LIMIT regression.

**TASK 43 — Schema description sweep.**
Every schema in `shared/schemas/` (old + new) states: producer, consumer, and
that `additionalProperties:false` is the hallucination gate. Update the
contracts table in `PROJECT_OVERVIEW.md` §6 with the six new schemas. No code.

**TASK 44 — `REACHOUT_OFFLINE=1` full-path verification.**
CI-style test (or session verification if a test is awkward): with
REACHOUT_OFFLINE=1 and network blocked (monkeypatch `requests.get` to raise),
the entire suite passes and `dummyjson_fetch.fetch_products(cache_only=True)`
serves the committed cache. Any test that hits the network fails this task.

### Phase 6 — Documentation

**TASK 45 — README + TRYME.**
`reachout/README.md` + `reachout/TRYME.md`: document the new endpoints (curl
examples for /api/regions, /api/inventory, paginated /api/search,
/api/inventory/stream via `curl -N`), `REACHOUT_SIM=1`, and the DummyJSON
catalog (source, 1:1 EUR convention, offline cache). Keep the existing voice.

**TASK 46 — AGENTS.md + PROJECT_OVERVIEW.md.**
Update the repo-root `AGENTS.md` and `PROJECT_OVERVIEW.md`: new endpoints
table, regions concept, event bus + scheduler in the "System at a glance"
diagram, new debugging rows (SSE not streaming → REACHOUT_SIM + event_bus;
region empty → region_seeder assignment radius).

**TASK 47 — `_config/tech_stack.md` + requirements comment audit.**
Record APScheduler + httpx(test) with one-line whys; state the frozen-simple
rule (no Redis/Kafka/websockets) so future agents don't "upgrade" it.

**TASK 48 — Frontend contract note.**
`docs/` note (or PR description section): fields added for the frontend
(`rating`, `review_count`, `source`; paginated search envelope; regions +
SSE endpoints), and the exact regen command: `cd frontend && npm run
gen-types`. Do NOT run frontend codegen from a backend task — flag only.

### Phase 7 — Verification & PR

**TASK 49 — Full-suite gate.**
Run `cd reachout/tests && python -m pytest` (expect 93 + all new tests green,
offline) and `REACHOUT_OFFLINE=1 python run_pipeline.py "algo para el dolor
de cabeza" --near "Malasaña"` (pipeline smoke). Fix anything red. No new
features in this task.

**TASK 50 — Live end-to-end verification script.**
New `reachout/scripts/verify_live.py` (pure Python, requests + stdlib): boots
nothing itself; against a running `REACHOUT_SIM=1` server it asserts —
/api/health.simulator_running true; /api/regions ≥ 20 regions;
/api/inventory page walk consistent; /api/inventory/stream yields ≥ 1 stock
event within 30s. Exit 0/1. Referenced from TRYME. Tests: unit-test its
assertion helpers only (no live server in CI).

**TASK 51 — Changelog + migration notes.**
`docs/BACKEND_CHANGELOG.md`: every migration (1–3), every new endpoint,
every schema change, the reseed implication (inventory contents changed),
rollback note (the DB is gitignored and regenerated — reverting code +
schemas and re-running the seeders rebuilds it).

**TASK 52 — Final PR.**
Open the PR to `main`: title "feat(backend): multi-region live inventory —
regions, DummyJSON catalog, paginated search, SSE stock stream". Body:
phase-by-phase summary, schema list, endpoint table, test count before/after,
the frontend gen-types follow-up, and explicit confirmation of the four
invariants (schema-first / no AI in scripts/ / offline tests / frozen-simple
stack). Request human review — do not self-merge.

---

## 4. JULES RUNNER SCRIPT — OUTLINE

`tools/jules_runner.py` (repo root `tools/`, NOT `reachout/scripts/` — it
calls an AI service, and scripts/ is the no-AI zone). Outline only; ~120
lines when implemented.

```
CONFIG
  JULES_API_KEY   = os.environ["JULES_API_KEY"]        # placeholder [JULES_API_KEY]
  BASE            = "https://jules.googleapis.com/v1alpha"
  SOURCE          = "sources/github/Aarrushh/reachout" # Jules GitHub app must be installed
  TASKS_FILE      = "docs/JULES_BACKEND.md"
  STATE_FILE      = "tools/.jules_runner_state.json"   # resume support

PARSE
  read TASKS_FILE; split on r"^\*\*TASK (\d{2}) — (.+?)\*\*$" (multiline);
  task body = text until the next TASK heading; also capture §1 master
  context block (the first ``` fenced block) to prepend to every prompt.

SUBMIT LOOP (sequential — Jules quota + tasks depend on each other)
  for each task not marked done in STATE_FILE:
    prompt = master_context + "\n\n" + f"TASK {nn} — {title}\n" + body
             + "\n\nWork ONLY this task. Run the test suite before finishing."
    POST {BASE}/sessions
      headers: {"X-Goog-Api-Key": JULES_API_KEY}
      json: {"prompt": prompt,
             "sourceContext": {"source": SOURCE,
                               "githubRepoContext": {"startingBranch": BRANCH}},
             "title": f"TASK {nn}: {title}"}
    poll GET {BASE}/sessions/{id} (+ /activities for progress logging)
      every 30s until state in {COMPLETED, FAILED}; timeout 45 min
    on COMPLETED:
      print the session's output branch/PR URL
      GATE: input("Review & merge TASK {nn}'s branch, then press Enter…")
      # human merges; next task's startingBranch = main again
      mark done in STATE_FILE
    on FAILED/timeout:
      dump activities, stop — a failed atomic task must not cascade

NOTES
  - --from NN / --only NN flags for reruns.
  - The human merge gate is deliberate: Jules quality varies; each task is
    small enough to review in minutes, and later tasks assume merged results.
  - SUGGESTION: once TASKS 01–13 have all landed cleanly, batches within a
    phase (e.g. the six schema tasks) could run as parallel sessions on
    separate branches — only do this if review bandwidth allows.
```

---

## Inline suggestions recap

- **SUGGESTION (TASK 24):** nearest-centroid region assignment over real
  barrio polygons — accepted crudeness; polygons would add shapely. Flagged,
  not done.
- **SUGGESTION (scheduler):** a bare `asyncio.create_task` loop in the
  lifespan would do this job with zero new dependencies; APScheduler is kept
  because it was specified and its jitter/shutdown handling is free — but if
  the dependency ever bites, the swap is one file (TASK 35).
- **SUGGESTION (SSE):** `sse-starlette` exists and is nice; plain
  `StreamingResponse` is used because the stack is frozen-simple and the
  format is three lines of string concatenation.
- **SUGGESTION (prices):** DummyJSON prices are USD; they are used 1:1 as EUR
  (`currency` stays `const "EUR"`). Synthetic data never claims to be real —
  a per-item currency field would be schema churn with no demo value.
- **SUGGESTION (runner §4):** limited parallelism per phase after the
  foundations land, if review bandwidth allows.
