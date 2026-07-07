# AGENTS.md — Parallel build workstreams for the ReachOut Madrid pipeline

This file divides the approved 11-step execution plan into **10 self-contained
agent workstreams** (tests are TDD inside every workstream, not a separate one).
Any fresh Claude session can pick up one workstream with zero context from
other sessions: everything an agent needs is in this file, in the repo docs it
points to, and in `STATUS.md`.

## How every agent session must work

1. Read, in order: `reachout/CLAUDE.md` → `reachout/CONTEXT.md` →
   `reachout/_config/constraints.md` → `reachout/_config/tech_stack.md` →
   your workstream entry below → `STATUS.md`.
2. Check `STATUS.md`: if your blockers are not checked off, stop and say so.
3. Mark your workstream **in progress** in `STATUS.md` (add your session date).
4. Work test-first (`superpowers` TDD). All tests live in `reachout/tests/`,
   run offline (`REACHOUT_OFFLINE=1`), and never hit a live API.
5. Touch ONLY the files your workstream owns. If you believe you must edit a
   file owned by another workstream, stop and record the conflict in
   `STATUS.md` under "Blocked / conflicts" instead.
6. When done: run your definition-of-done checks, tick your boxes in
   `STATUS.md`, and note anything the next agent must know.
7. update STATUS.md at the end of every session

**Environment:** secrets live in `reachout/.env` (gitignored):
`ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` (a local proxy on
`http://localhost:3001`). Nothing auto-loads this file yet — export the
variables in your shell, or note in your workstream if you add loading
support. The `anthropic` SDK reads both variables from the environment
automatically. Only W1 ever needs them; every other workstream is AI-free by
design.

**Shared contracts:** the JSON Schemas in `reachout/shared/schemas/` are the
interfaces between workstreams. Develop against fixtures shaped by the
schemas, not against another agent's live output. Schemas are never edited to
make a failing output pass (constraints.md §13).

---

## Dependency graph (who can run in parallel)

```
Batch 1 (no blockers, fully parallel):  W1  W2  W6  W7
Batch 2 (after W2):                     W3  W5
Batch 3 (after W3):                     W4
Batch 4 (after W1–W7):                  W8
Batch 5 (after W8, parallel):           W9  W10
```

---

## W1 — Stage-01 parser fix (agentic stage, deterministic default)

**Responsibility:** Make stage 01 emit the NEW `SearchIntent` shape. This is
the current breakage: `agent/query_parser.py` emits the legacy shape
(`category_hint` singular, no `status`), which the new schema rejects on
every run.

**Owns (writes):**
- `reachout/agent/query_parser.py`
- `reachout/agent/llm.py`
- `reachout/tests/test_parse_query.py` (new)

**Reads (never edits):**
- `reachout/shared/schemas/search_intent.schema.json`
- `reachout/stages/01-parse-query/prompt.md` and `CONTEXT.md` (T1–T3 are your acceptance tests)
- `reachout/scripts/validate.py`

**Input contract:** schema + stage prompt exist (they do).

**Output contract:** `parse_query(text)` returns a dict that validates against
`search_intent.schema.json`: `status` ok/incomplete, `raw_query` byte-identical,
`keywords` (array, only from user words or the SYNONYMS map), `category_hints`
(array ⊆ the 5 categories, `hardware` included), `location_text` verbatim or
null, `missing_fields` on incomplete. SYNONYMS becomes bilingual (Spanish +
English) with multi-word phrase matching ("dolor de cabeza"). The LLM path
(`llm.py`) gets the same output shape in its system prompt; keep the model
name in one constant, overridable via `ANTHROPIC_MODEL` env var since a local
proxy is in use.

**Blockers:** none.

**Session prompt (copy-paste):**
> Read AGENTS.md at the repo root and execute workstream W1 (stage-01 parser
> fix) exactly as specified there. Follow the reading order in "How every
> agent session must work", use TDD, and make the three test cases in
> reachout/stages/01-parse-query/prompt.md pass as pytest tests with
> REACHOUT_OFFLINE=1. Update STATUS.md when you start and when you finish.

**Definition of done:**
- [ ] `pytest reachout/tests/test_parse_query.py` green offline.
- [ ] Prompt.md T1 ("algo para el dolor de cabeza en Malasaña"), T2
      ("cargador usb c"), T3 ("???") produce the exact documented outputs.
- [ ] Every output validates against `search_intent.schema.json`; the
      fallback path also validates (the legacy fallback did not).
- [ ] No network call happens unless `--use-llm` AND the key is set.

---

## W2 — Data core: SQLite schema + deterministic Madrid inventory seeder

**Responsibility:** Rework the DB layer to the Madrid data model and build the
deterministic synthetic-inventory seeder. Every other hardcoded stage sits on
this.

**Owns (writes):**
- `reachout/scripts/db.py` (rework: shop_id `osm:*`, `categories` stored as
  JSON text array, nullable `address`, inventory gains `currency` ("EUR") and
  `synthetic` (1) columns, ISO-8601 `updated_at`)
- `reachout/scripts/inventory_seeder.py` (new)
- `reachout/scripts/inventory_simulator.py` (port to new SKUs/EUR; keep the
  sell/restock/new-item behaviour and events.jsonl logging)
- `reachout/scripts/seed_data.py` (delete — replaced by seeder; W3 owns shop
  ingest)
- `reachout/tests/test_db.py`, `reachout/tests/test_inventory_seeder.py` (new)

**Reads (never edits):**
- `reachout/shared/schemas/inventory_record.schema.json`, `shop_record.schema.json`
- `reachout/data/sku_catalog.json` (the ONLY source of item names/prices)
- `reachout/_config/constraints.md` §5, §6

**Input contract:** `sku_catalog.json` exists (it does).

**Output contract:** `inventory_seeder.seed_shop(conn, shop)` gives a shop a
deterministic subset of its category's SKUs via `random.Random(shop_id)`,
price jitter ±15% rounded to cents, qty 0–12, `synthetic: true` — same
shop_id ⇒ identical inventory on every run (the sku_catalog.json header
comment is the spec). Every row validates against
`inventory_record.schema.json`. `db.py` exposes the same call surface style
as today (`connect`, `init_db`, `upsert_shop`, `upsert_item`, `adjust_qty`,
`all_shops`, `items_for_shop`) so W3/W5 code against it.

**Blockers:** none.

**Session prompt (copy-paste):**
> Read AGENTS.md at the repo root and execute workstream W2 (data core:
> SQLite schema + deterministic inventory seeder) exactly as specified there.
> Follow the reading order in "How every agent session must work", use TDD,
> keep tests offline. Determinism is the acceptance bar: seeding the same
> shop_id twice must produce byte-identical inventory. Update STATUS.md when
> you start and when you finish.

**Definition of done:**
- [ ] `pytest reachout/tests/test_db.py reachout/tests/test_inventory_seeder.py` green offline.
- [ ] Seeder is deterministic per shop_id; rows validate against
      `inventory_record.schema.json` (spot-check in a test).
- [ ] Simulator runs against the new schema; events still stream to
      `data/events.jsonl`.
- [ ] Legacy `seed_data.py` removed; nothing imports it (grep proves it —
      note: the simulator currently imports its CATALOGUE; fix that here).

---

## W3 — Geo externals: Overpass, Nominatim, ORS clients + OSM ingest + cache

**Responsibility:** All network I/O for real-world data, each call with
timeout, User-Agent, rate limit, and a committed offline fallback
(constraints.md §7). Build the committed Madrid shop cache.

**Owns (writes):**
- `reachout/scripts/overpass.py`, `reachout/scripts/nominatim.py`,
  `reachout/scripts/ors.py` (new)
- `reachout/scripts/osm_ingest.py` (new — Overpass/cache rows → validated
  `ShopRecord`s → db upsert + seeder call per new shop)
- `reachout/data/osm_cache/madrid_shops.json` (new — fetched once, committed)
- `reachout/tests/test_overpass.py`, `test_nominatim.py`, `test_osm_ingest.py`
  + `reachout/tests/fixtures/` (canned API responses)

**Reads (never edits):**
- `reachout/data/category_tag_map.json` (the only source of OSM selectors)
- `reachout/data/gazetteer_madrid.json` (Nominatim fallback)
- `reachout/shared/schemas/shop_record.schema.json`
- `reachout/scripts/db.py` + `inventory_seeder.py` (W2's API)

**Input contract:** W2 finished (db API + seeder callable).

**Output contract:** `osm_ingest.ingest(radius_or_area, refresh=False)`
returns validated ShopRecords with `shop_id` `osm:node|way|relation:<id>`,
`categories` array mapped via category_tag_map (multi-tag shops keep ALL
categories, primary first), `address` joined from `addr:*` tags or null —
never synthesized, `source` one of overpass_live/cache/geofabrik. Nominatim:
max 1 req/s, results cached to `data/geocode_cache.json`, gazetteer fallback
(case- and accent-insensitive), `REACHOUT_OFFLINE=1` forces fallbacks
everywhere. ORS: only if `ORS_API_KEY` set, else caller falls back to
haversine.

**Blockers:** W2.

**Session prompt (copy-paste):**
> Read AGENTS.md at the repo root and execute workstream W3 (geo externals:
> Overpass/Nominatim/ORS clients, OSM ingest, committed Madrid cache) exactly
> as specified there. Verify in STATUS.md that W2 is done first. Follow
> constraints.md §7 to the letter: timeouts, User-Agent, 1 req/s Nominatim,
> offline fallbacks, and all tests offline against fixtures. Fetch the live
> Overpass data once to build data/osm_cache/madrid_shops.json, then commit
> it. Update STATUS.md when you start and when you finish.

**Definition of done:**
- [ ] All W3 tests green with `REACHOUT_OFFLINE=1` (zero network).
- [ ] `data/osm_cache/madrid_shops.json` committed, non-trivial (hundreds of
      real shops across the 5 categories), every row validates against
      `shop_record.schema.json`.
- [ ] Ingest is idempotent (running twice ⇒ same DB state) and seeds
      inventory only for shops it inserts.
- [ ] Overpass-down path proven in a test: falls to cache; cache missing ⇒
      the documented `no_shop_source` error object.

---

## W4 — Stage 02: geo-resolve script

**Responsibility:** The missing stage 02: resolve the query centre, select
real shops in radius, compute distance, emit `geo_shops.json`.

**Owns (writes):**
- `reachout/scripts/geo_resolve.py` (new)
- `reachout/tests/test_geo_resolve.py` (+ fixtures)

**Reads (never edits):**
- `reachout/stages/02-geo-resolve/prompt.md` + `CONTEXT.md` (the spec; T1–T3
  are your acceptance tests)
- `reachout/shared/schemas/geo_shops.schema.json`
- `reachout/scripts/geo.py` (haversine — already correct, do not modify)
- W2's `db.py`, W3's `nominatim.py` / `osm_ingest.py` / `ors.py`

**Input contract:** W3 finished. Consumes a `SearchIntent` dict (fixture-
shaped by `search_intent.schema.json` — do NOT depend on W1's code) plus CLI
params (lat/lng/near/radius/refresh).

**Output contract:** `geo_shops.json` validating against
`geo_shops.schema.json`. Centre precedence: explicit coords > location_text
via Nominatim/gazetteer > Puerta del Sol default — but a NAMED place that
cannot be resolved is `status:"incomplete"`, never silently defaulted.
`resolved_from` and `shop_source` record honestly what happened.
`category_hints` intersection filter. Shops sorted by `distance_km`
ascending, `distance_type` walking|haversine. Zero shops = `status:"ok"`,
`shops: []`.

**Blockers:** W3 (hard), W2 (transitively).

**Session prompt (copy-paste):**
> Read AGENTS.md at the repo root and execute workstream W4 (stage-02
> geo-resolve script) exactly as specified there. Verify in STATUS.md that W3
> is done first. The spec is reachout/stages/02-geo-resolve/prompt.md — its
> three test cases become pytest tests running offline with fixtures. Update
> STATUS.md when you start and when you finish.

**Definition of done:**
- [ ] `pytest reachout/tests/test_geo_resolve.py` green offline.
- [ ] Prompt.md T1 (explicit coords), T2 (Lavapiés via gazetteer), T3
      (Overpass down → cache; cache gone → error) pass as written.
- [ ] Unresolvable named place returns incomplete, not the default centre.
- [ ] Output always validates against `geo_shops.schema.json`.

---

## W5 — Stage 03: match-and-ping rework

**Responsibility:** Rework the matching engine to consume `geo_shops.json` as
the ONLY candidate set and emit the new `StockMatches` shape.

**Owns (writes):**
- `reachout/scripts/search_engine.py` (rework)
- `reachout/scripts/ping.py` (minor: new shop_id format, keep inbox
  behaviour)
- `reachout/tests/test_search_engine.py`, `reachout/tests/test_ping.py`

**Reads (never edits):**
- `reachout/stages/03-match-and-ping/prompt.md` + `CONTEXT.md` (T1–T3)
- `reachout/shared/schemas/stock_matches.schema.json`
- W2's `db.py`

**Input contract:** W2 finished. Consumes intent + geo_shops dicts
(fixture-shaped by their schemas — not W1/W4 code).

**Output contract:** `matches.json` validating against
`stock_matches.schema.json`: candidates come only from `geo_shops.shops`
(no DB-wide scan), whole-word keyword matching kept, secondary categories
count, qty ≥ 1 only, distances copied unchanged from geo_shops, rank =
nearest → most matching stock → cheapest, `pinged_shop_ids` == matched
shop_ids in order, pings appended one line per matched shop. Zero
candidates/matches ⇒ `status:"ok"`, `match_count:0`, no pings.

**Blockers:** W2 (hard). W4 not required — use fixtures.

**Session prompt (copy-paste):**
> Read AGENTS.md at the repo root and execute workstream W5 (stage-03
> match-and-ping rework) exactly as specified there. Verify in STATUS.md that
> W2 is done first. The spec is reachout/stages/03-match-and-ping/prompt.md —
> its three test cases become pytest tests with fixture inputs shaped by
> geo_shops.schema.json and a temp SQLite DB. Update STATUS.md when you start
> and when you finish.

**Definition of done:**
- [ ] `pytest reachout/tests/test_search_engine.py reachout/tests/test_ping.py` green offline.
- [ ] Prompt.md T1 (two pharmacies), T2 (zero candidates ⇒ ok + no pings),
      T3 (secondary-category match) pass as written.
- [ ] A shop present in the DB but absent from geo_shops NEVER appears in
      output (test proves it).
- [ ] Output always validates against `stock_matches.schema.json`.

---

## W6 — Stage 04: result formatter

**Responsibility:** The deterministic builder that flattens matches into the
final ranked shop list, plus the LLM-rejection guard.

**Owns (writes):**
- `reachout/agent/result_formatter.py` (new)
- `reachout/tests/test_result_formatter.py`

**Reads (never edits):**
- `reachout/stages/04-format-results/prompt.md` + `CONTEXT.md` (T1–T3)
- `reachout/shared/schemas/ranked_shops.schema.json`
- `reachout/shared/schemas/stock_matches.schema.json` (input shape)

**Input contract:** none beyond schemas — fully fixture-driven.

**Output contract:** `ranked_shops.json` validating against
`ranked_shops.schema.json`: rank 1..N contiguous copying stage-03 order,
per shop the CHEAPEST matching item, every value verbatim, category =
primary (first of categories array), address null stays null. Optional LLM
pass may only normalize item_name casing; ANY schema failure ⇒ discard,
use deterministic output, append `formatter_llm_rejected` to
`data/events.jsonl`. Zero matches ⇒ ok, `result_count:0`, `results:[]`,
no apology text.

**Blockers:** none.

**Session prompt (copy-paste):**
> Read AGENTS.md at the repo root and execute workstream W6 (stage-04 result
> formatter) exactly as specified there. The spec is
> reachout/stages/04-format-results/prompt.md — its three test cases,
> including T3 where a simulated LLM injects a "community_note" field and
> must be rejected by additionalProperties:false, become pytest tests. All
> offline, fixture-driven. Update STATUS.md when you start and when you
> finish.

**Definition of done:**
- [ ] `pytest reachout/tests/test_result_formatter.py` green offline.
- [ ] Prompt.md T1 (verbatim numbers), T2 (zero matches), T3 (narrative
      injection rejected + `formatter_llm_rejected` event logged) pass.
- [ ] Output always validates against `ranked_shops.schema.json`.

---

## W7 — Stage 05: map render

**Responsibility:** Mechanical projection of the ranked list into RFC 7946
GeoJSON, with the error-sidecar convention.

**Owns (writes):**
- `reachout/scripts/map_render.py` (new)
- `reachout/tests/test_map_render.py`

**Reads (never edits):**
- `reachout/stages/05-map-render/prompt.md` + `CONTEXT.md` (T1–T3)
- `reachout/shared/schemas/map_geojson.schema.json`
- `reachout/shared/schemas/ranked_shops.schema.json` (input shape)

**Input contract:** none beyond schemas — fully fixture-driven.

**Output contract:** on success `shops.geojson` (FeatureCollection,
coordinates **[longitude, latitude]**, properties copied verbatim, `metadata`
foreign member with query/generated_at/result_count/center/radius_km) and NO
error.json; on bad input `error.json` (status envelope) and NO .geojson.
Zero results ⇒ a VALID FeatureCollection with `features: []`.

**Blockers:** none.

**Session prompt (copy-paste):**
> Read AGENTS.md at the repo root and execute workstream W7 (stage-05 map
> render) exactly as specified there. The spec is
> reachout/stages/05-map-render/prompt.md — its three test cases become
> pytest tests, including the coordinate-order check ([lng, lat]) and the
> error-sidecar path. All offline, fixture-driven. Update STATUS.md when you
> start and when you finish.

**Definition of done:**
- [ ] `pytest reachout/tests/test_map_render.py` green offline.
- [ ] Prompt.md T1 (two features, lng-first), T2 (empty FeatureCollection),
      T3 (missing lng ⇒ error.json, no geojson) pass as written.
- [ ] Output validates against `map_geojson.schema.json`; a deliberately
      swapped lat/lng fixture FAILS validation (test proves the gate works).

---

## W8 — Orchestrator + demo (integration)

**Responsibility:** Rewrite the pipeline walker to run all five stages with
hard schema gates, port the demo to Madrid, and prove the whole thing
end-to-end offline. This is the integration point — it begins only when
W1–W7 are all done.

**Owns (writes):**
- `reachout/run_pipeline.py` (rewrite)
- `reachout/demo.py` (Madrid port)
- `reachout/scripts/validate.py` (update `__main__` example; keep API)
- `reachout/tests/test_pipeline_e2e.py` (new — full offline run)

**Reads (never edits):** everything W1–W7 produced; `CONTEXT.md` routing
table; all schemas.

**Input contract:** W1–W7 checked off in STATUS.md.

**Output contract:** `run_pipeline.py` walks 01→02→03→04→05, writes each
stage's file into its `output/`, validates each against its schema and
**HALTS** on any failure or any `status != "ok"` (constraints.md §2 — the
legacy warn-and-continue is a bug, not a feature). CLI: query, `--near`
(neighbourhood name) OR `--lat/--lng`, `--radius` (default 2.0), `--refresh`,
`--use-llm`. Defaults are Madrid (Puerta del Sol). `demo.py` seeds via
ingest+seeder, runs the simulator thread, fires Spanish/English Madrid
queries. Stage 05's error.json sidecar is checked by the orchestrator.

**Blockers:** W1, W2, W3, W4, W5, W6, W7 (all).

**Session prompt (copy-paste):**
> Read AGENTS.md at the repo root and execute workstream W8 (orchestrator +
> demo integration) exactly as specified there. Verify in STATUS.md that
> W1–W7 are ALL done first. Rewrite reachout/run_pipeline.py to walk the five
> stages per reachout/CONTEXT.md with hard schema validation between every
> stage, port demo.py to Madrid, and add an end-to-end offline pytest that
> runs the full pipeline with REACHOUT_OFFLINE=1 from the committed cache.
> Update STATUS.md when you start and when you finish.

**Definition of done:**
- [ ] `REACHOUT_OFFLINE=1 python reachout/run_pipeline.py "algo para el dolor de cabeza" --near "Malasaña"` completes: 5 output files, all schema-valid.
- [ ] Same for `"cargador usb c" --lat 40.4168 --lng -3.7038`.
- [ ] A deliberately corrupted intermediate file halts the pipeline with a
      clear message (test proves it).
- [ ] `python reachout/demo.py` runs the live demo on Madrid data; pings land
      in `data/notifications/`.
- [ ] Full test suite green offline: `REACHOUT_OFFLINE=1 pytest reachout/tests/`.

---

## W9 — Cleanup + docs truth pass

**Responsibility:** Remove the legacy generation and make the docs match
reality. Runs only after W8 so nothing live still depends on legacy pieces.

**Owns (writes):**
- Delete: `reachout/shared/schemas/inventory_item.schema.json`,
  `reachout/shared/schemas/shop_match.schema.json`, `reachout/data/shops.json`
- `reachout/README.md` (rewrite to the 5-stage Madrid reality; kill every
  mention of "consumer card"/Mumbai/rupees; update run instructions)
- `reachout/TUTORIAL.md` (add a short banner noting it documents the original
  3-stage prototype; do not rewrite the tutorial)

**Reads (never edits):** everything, to verify nothing references the deleted
files.

**Input contract:** W8 done (pipeline green without legacy files).

**Output contract:** `grep -r "shop_match\|inventory_item\.schema\|shops\.json\|seed_data"`
over `reachout/` returns only intentional hits (e.g. the TUTORIAL banner).
Test suite still green after deletions.

**Blockers:** W8.

**Session prompt (copy-paste):**
> Read AGENTS.md at the repo root and execute workstream W9 (cleanup + docs
> truth pass) exactly as specified there. Verify in STATUS.md that W8 is done
> first. Delete the legacy schemas and data listed, rewrite README.md to
> match the actual 5-stage Madrid pipeline, re-run the full offline test
> suite to prove nothing broke, and update STATUS.md.

**Definition of done:**
- [ ] Legacy schemas + `data/shops.json` deleted; no dangling references.
- [ ] README.md describes the real pipeline, real commands, Madrid market.
- [ ] `REACHOUT_OFFLINE=1 pytest reachout/tests/` still green.

---

## W10 — Read-only API + frontend skeleton

**Responsibility:** The thin FastAPI wrapper and the no-visuals frontend
skeleton exactly as fixed in `frontend/README.md`. ARCHITECTURE ONLY — zero
visual/UI decisions; that is a separate future phase (ui-ux-pro-max /
21st.dev / v0).

**Owns (writes):**
- `reachout/api/server.py` (new) + `reachout/tests/test_api.py`
- `reachout/requirements.txt` (uncomment fastapi/uvicorn)
- `frontend/` skeleton per the tree in `frontend/README.md`: `package.json`,
  `vite.config.ts`, `tsconfig.json`, `.env.example`,
  `scripts/gen-types.ts`, `src/main.tsx`, `src/routes/search.tsx`,
  `src/routes/results.tsx`, `src/api/client.ts`, `src/types/` (generated),
  `src/map/geojson-source.ts`

**Reads (never edits):**
- `frontend/README.md` (the spec — follow its planned skeleton exactly)
- `reachout/shared/schemas/ranked_shops.schema.json`, `map_geojson.schema.json`
- `reachout/run_pipeline.py` (call it; do not duplicate its logic)

**Input contract:** W8 done (a working pipeline to wrap).

**Output contract:** `GET /api/search` → ranked_shops JSON,
`GET /api/search.geojson` → the FeatureCollection, `GET /api/health` →
`{"status":"ok"}`; responses validate against their schemas. Frontend:
React Router with URL-as-state, TanStack Query keyed on URL params, types
GENERATED from the schemas (never hand-edited), no styling or layout of any
kind.

**Blockers:** W8. (Parallel with W9 — disjoint files.)

**Session prompt (copy-paste):**
> Read AGENTS.md at the repo root and execute workstream W10 (read-only API +
> frontend skeleton) exactly as specified there. Verify in STATUS.md that W8
> is done first. Build reachout/api/server.py as a thin wrapper over the
> pipeline, then the frontend/ skeleton EXACTLY per frontend/README.md —
> architecture only, zero visual design, no components beyond the listed
> files. Update STATUS.md when you start and when you finish.

**Definition of done:**
- [ ] API tests green; responses schema-valid; zero-result query returns 200
      with an empty list, not an error.
- [ ] `npm run build` (or `npx tsc --noEmit`) passes in `frontend/`.
- [ ] `src/types/` generated from the schemas; no hand-written type drift.
- [ ] Not one CSS/styling/layout decision anywhere in the diff.
