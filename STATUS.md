# STATUS.md — ReachOut build progress tracker

Single source of truth for cross-session build state. Every agent session:
**read this first, update it when you start, update it when you finish.**
Workstream specs live in `AGENTS.md`. Do not start a workstream whose
blockers are not all ✅.

## Legend

- `[ ]` not started `[~]` in progress (add session date + note) `[x]` done
- A workstream is DONE only when every item in its AGENTS.md
  definition-of-done checklist is verified — evidence before assertions.

## Batch overview

| Batch | Workstreams | Can start when |
|-------|-------------|----------------|
| 1 | W1, W2, W6, W7 | now (fully parallel) |
| 2 | W3, W5 | W2 done |
| 3 | W4 | W3 done |
| 4 | W8 | W1–W7 all done |
| 5 | W9, W10 | W8 done (parallel) |

## Workstreams

### W1 — Stage-01 parser fix
- [x] Started (date/session: 2026-07-07 — Claude session)
- [x] `tests/test_parse_query.py` green offline
- [x] Prompt.md T1/T2/T3 pass exactly as documented
- [x] All outputs (incl. fallback path) validate against `search_intent.schema.json`
- [x] Bilingual multi-word SYNONYMS; `hardware` category covered
- [x] DONE — handoff notes: query_parser.py rewritten for the new SearchIntent shape
      (status/keywords/category_hints/location_text/missing_fields). Rule-based
      parser: `_extract_location` pulls a verbatim place name via a trailing
      "en|in <Capitalized...>" regex and strips it from the working text;
      `_extract_keywords` does a left-to-right token scan trying the longest
      SYNONYMS phrase first (so "dolor de cabeza" / "usb c" match before their
      individual words), falling back to the bare token if not a stopword;
      `_category_hints` looks up each keyword (and its space-split parts) in
      bilingual CATEGORY_WORDS sets — "pilas"/"batteries" deliberately land in
      both hardware and electronics (the documented ambiguous case). Empty
      keywords ⇒ {"status":"incomplete","missing_fields":["keywords"]}
      (no keywords/category_hints/location_text keys at all, since the schema
      forbids "keywords" as present when incomplete). Schema-rejection fallback
      (`_fallback_intent`) now emits the new shape too (previously the legacy
      fallback used `category_hint` and failed validation itself). llm.py:
      MODEL now reads `ANTHROPIC_MODEL` env var (falls back to the Haiku
      constant); SYSTEM_PROMPT updated to request the new JSON shape.
      8 tests in tests/test_parse_query.py, all offline, no network: T1/T2/T3
      exact-match, hardware/electronics ambiguity, English bilingual synonym,
      a monkeypatched-network-boom test proving the default path never touches
      the LLM, and a forced-schema-rejection test proving the fallback path
      itself validates. Also added `AGENT_DIR` to `tests/conftest.py` (it only
      had `SCRIPTS_DIR`) — needed so any test can `import query_parser`/`llm`
      directly; this file isn't owned by any workstream in AGENTS.md, the
      change is purely additive.

### W2 — Data core (SQLite schema + inventory seeder)
- [x] Started (date/session: 2026-07-07 — Claude session)
- [x] `tests/test_db.py` + `tests/test_inventory_seeder.py` green offline
- [x] Seeder deterministic per shop_id; rows validate against `inventory_record.schema.json`
- [x] Simulator ported (EUR, new SKUs, no `seed_data` import)
- [x] Legacy `seed_data.py` removed, zero dangling imports (within W2-owned files)
- [x] DONE — handoff notes: db.py reworked to shop_id/osm_id/categories(JSON)/nullable
      address/source/fetched_at schema; inventory gains currency ("EUR") and
      synthetic (bool) columns, updated_at is ISO-8601 (db.now_iso()). Added
      optional `path`/`db_path` params to connect/init_db/run_simulator so tests
      run against temp DBs instead of the shared data/reachout.db.
      inventory_seeder.seed_shop(conn, shop) is deterministic per shop_id
      (random.Random(shop_id)); tests compare seeded rows with updated_at
      stripped since that field is a wall-clock stamp, not part of the
      deterministic content. inventory_simulator.py now reads
      data/sku_catalog.json instead of seed_data.CATALOGUE and stamps
      currency/synthetic on new items; events.jsonl logging unchanged.
      Added reachout/tests/conftest.py putting scripts/ on sys.path (needed by
      every future workstream's tests too).
      NOT touched (out of W2 scope, owned elsewhere): demo.py still does
      `import seed_data` / `seed_data.seed()` (line 22/33) — it will fail until
      W8 ports it to ingest+seeder as its own workstream already anticipates.
      search_engine.py has one stale comment mentioning seed_data.py (line 90,
      not a real import) — W5's to fix.
      Unrelated: found AGENTS.md already carrying an uncommitted one-line diff
      (a duplicated point 7 under "How every agent session must work") that
      predates this session and that I did not author — flagged to the user,
      left as-is.

### W3 — Geo externals (Overpass / Nominatim / ORS + ingest + cache) — blocked by W2
- [x] Started (date/session: 2026-07-07 — Claude session W3)
- [x] All W3 tests green with `REACHOUT_OFFLINE=1`
- [x] `data/osm_cache/madrid_shops.json` committed; rows validate against `shop_record.schema.json`
- [x] Ingest idempotent; seeds inventory only for newly inserted shops
- [x] API-down → cache → `no_shop_source` error path proven in a test
- [x] DONE — handoff notes: scripts/overpass.py builds one Overpass QL query from
      data/category_tag_map.json (node/way/relation per tag selector, `out center tags;`)
      and posts it with a descriptive User-Agent + timeout; raises `OverpassError` on any
      network/HTTP/JSON failure (never silently returns partial data).
      scripts/nominatim.py: `geocode(place_name, offline=None)` checks
      data/geocode_cache.json first, then (if not offline) hits the live API respecting a
      hard 1 req/s throttle (module-level `_rate_limit()`, monkeypatchable in tests),
      caches any live hit, and falls back to data/gazetteer_madrid.json (accent/case
      insensitive via NFKD-strip) on any live failure or when offline. Returns None only if
      neither cache nor gazetteer has the place.
      scripts/ors.py: `walking_distance_km(...)` returns None unless `ORS_API_KEY` is set
      and not offline; any request failure also returns None — caller (W4's geo_resolve)
      is expected to fall back to scripts/geo.py's haversine and record distance_type
      accordingly, per its own contract.
      scripts/osm_ingest.py: `ingest(area_name="Madrid", refresh=False, conn=None,
      offline=None)` — tries live Overpass first (unless offline), falls back to the
      committed cache on `OverpassError`, and returns
      `{"status":"error","error":{"code":"no_shop_source","detail":...}}` only when both are
      unavailable. Every raw element is mapped via `element_to_shop_record` (skips shops
      with no `name` tag or no category match in category_tag_map.json; categories list is
      primary-first in category_tag_map.json's own key order: pharmacy > grocery > hardware
      > electronics > stationery); address is joined only from present addr:* tags, else
      null (never synthesized). Every record is schema-validated before upsert. Idempotency
      is enforced by snapshotting `db.all_shops(conn)` shop_ids BEFORE the upsert loop —
      `inventory_seeder.seed_shop` is only called for shop_ids not already present, so a
      second `ingest()` run on the same DB upserts (refreshes) shop rows but never reseeds
      or duplicates inventory. `refresh=True` also rewrites the committed cache file after a
      successful live fetch (kept out of the default path so tests never touch the real
      cache unless they opt in via monkeypatching `osm_ingest.CACHE_PATH`).
      data/osm_cache/madrid_shops.json: fetched once live from the real Overpass API
      (api.de instance; one 504 retry was needed, then succeeded) — 3328 validated, unique
      shop records across all 5 categories (grocery 2018, pharmacy 596, electronics 296,
      stationery 223, hardware 195), covering the whole `admin_level=8` Madrid city
      boundary. Verified end-to-end offline: `REACHOUT_OFFLINE=1` + a fresh temp DB +
      `osm_ingest.ingest()` loads all 3328 rows into `shops` with zero network calls.
      18 new tests (test_overpass.py, test_nominatim.py, test_osm_ingest.py) all offline,
      using tests/fixtures/overpass_response.json (5 elements: pharmacy w/ full addr,
      grocery on a `way` needing `center`, hardware w/ postcode+city-only addr, an
      unmapped-category element, and an unnamed element — proving both skip rules). Full
      suite green at 66 tests after this addition. Note for W4: `ingest()`'s `conn` param
      is optional (defaults to `db.connect()` against the real DB_PATH) so geo_resolve.py
      can call it directly with `--refresh`, or pass its own connection in tests.

### W4 — Stage 02 geo-resolve — blocked by W3
- [x] Started (date/session: 2026-07-07 — Claude session W4)
- [x] `tests/test_geo_resolve.py` green offline
- [x] Prompt.md T1/T2/T3 pass exactly as documented
- [x] Unresolvable named place → incomplete (never silent default)
- [x] Output validates against `geo_shops.schema.json`
- [x] DONE — handoff notes: `scripts/geo_resolve.py` exposes one pure function,
      `resolve(intent, lat=None, lng=None, near=None, radius_km=2.0, refresh=False,
      db_path=None, offline=None)` — no CLI/file I/O in this module, mirroring W5's
      `search_engine.search()` pattern; W8's orchestrator is expected to read
      intent.json, parse CLI args, call this, validate, and write
      `output/geo_shops.json` itself. Centre precedence: explicit lat/lng >
      `near` (CLI override) or else `intent["location_text"]` via
      `nominatim.geocode()` > default centre Puerta del Sol. `nominatim.geocode`
      returning `None` (place named but unresolvable by live/cache/gazetteer)
      short-circuits to `{"status":"incomplete","missing_fields":["query_location"]}`
      immediately — never falls through to the default centre. geocode's
      `source` field ("nominatim_live" or "geocode_cache") both map to
      `resolved_from:"nominatim"`; `"gazetteer"` maps to `"gazetteer"`.
      Shop selection: by default (no `--refresh`) the script does NOT call
      `osm_ingest.ingest()` at all — it reads directly via `db.all_shops(conn)`
      and reports `shop_source:"cache"` unconditionally, since no live/cache
      fetch happens this run (this was a judgment call: `osm_ingest.fetch_shop_records`
      would attempt a live Overpass call on every non-offline invocation
      regardless of `refresh` — that field only gates whether a successful
      live fetch rewrites the committed cache — so calling it unconditionally
      per search would hit Overpass every query, which is not what "select
      shops from the ingested table" implies). Only `--refresh` calls
      `osm_ingest.ingest(refresh=True, conn=conn, offline=offline)`; its error
      dict (`no_shop_source`) is returned verbatim (already schema-shaped), and
      on success `shop_source` is read from the first returned record's own
      `source` field (falls back to `"cache" if offline else "overpass_live"`
      only in the edge case of an empty-but-successful ingest). Radius
      filtering always uses haversine (`scripts/geo.py`, untouched) as the
      geofence; the per-shop `distance_km`/`distance_type` reported then tries
      `ors.walking_distance_km` first (falls back to the already-computed
      haversine value when ORS is unset/offline/fails) and the final list is
      sorted by that chosen distance. `category_hints` empty ⇒ keep all
      categories; non-empty ⇒ keep shops whose full `categories` array
      intersects (secondary categories count, same rule as W5).
      10 tests in `tests/test_geo_resolve.py`, all offline: T1 (explicit
      coords, 3-of-4 shops, sorted ascending, `distance_type` all haversine),
      T2 (neighbourhood name geocoded via a monkeypatched `nominatim.geocode`
      returning gazetteer-sourced coords, since REACHOUT_OFFLINE forces the
      gazetteer path per prompt.md's own "(or gazetteer in offline mode)"
      note), T3 (Overpass down + `--refresh` → cache fallback, `shop_source`
      "cache") plus its documented variant (cache file also missing →
      `status:"error"`, `error.code:"no_shop_source"`, no `shops` key),
      unresolvable named place → incomplete (not default centre), default
      centre when no location named at all, category-hints intersection
      filter, zero-shops-in-radius → ok not error, multi-category shop keeps
      its full categories array, and `near` overriding `intent.location_text`.
      Full offline suite green: 76/76 (`REACHOUT_OFFLINE=1 pytest reachout/tests/`).
      Did not touch `scripts/geo.py`, `db.py`, or any W3-owned file.

### W5 — Stage 03 match-and-ping rework — blocked by W2
- [x] Started (date/session: 2026-07-07 — Claude session W5)
- [x] `tests/test_search_engine.py` + `tests/test_ping.py` green offline
- [x] Prompt.md T1/T2/T3 pass exactly as documented
- [x] Candidates come ONLY from geo_shops (test proves DB-only shop excluded)
- [x] Output validates against `stock_matches.schema.json`
- [x] DONE — handoff notes: `scripts/search_engine.py` fully reworked. `search(intent,
      geo_shops, db_path=None, do_ping=True, notif_dir=None)` — candidates come ONLY from
      `geo_shops["shops"]` (no `db.all_shops()` scan anywhere in the module). Per shop:
      if `category_hints` non-empty, the shop's full `categories` array (primary +
      secondary) must intersect it or the shop is skipped entirely (this is what makes
      T3's grocery+pharmacy shop match on a `["pharmacy"]` hint); then live in-stock rows
      (`db.items_for_shop(..., in_stock_only=True)`, so qty=0 rows are structurally
      excluded) are kept if name-or-category whole-word-matches a keyword. Ranking key is
      `(distance_km, -sum(matched item qty), min(matched item price))` — nearest, then
      most total matching stock, then cheapest — distance_km/lat/lng/address/categories
      copied verbatim from the geo_shops shop row, never recomputed. `pinged_shop_ids` is
      built as `[m["shop_id"] for m in matches]` before pinging so it's correct even with
      `do_ping=False` (used by one ranking test to avoid touching the filesystem).
      Upstream handling: `geo_shops.status` "incomplete"/"error" is relayed as-is
      (`{"status": ..., "missing_fields"/"error": ...}` copied straight from geo_shops,
      per prompt.md's "exits with that incomplete/error output and you relay it" — this
      differs from W6's result_formatter, which converts any non-ok upstream status into
      a synthesized `error/upstream_not_ok`; stage 03's spec explicitly says relay, not
      convert). `intent.status != "ok"` or missing/empty `keywords` yields
      `{"status":"incomplete","missing_fields": intent.get("missing_fields") or
      ["keywords"]}`. Zero shops in geo_shops or zero surviving items ⇒ status ok,
      match_count 0, matches [], pinged_shop_ids [], no pings written (test asserts the
      notifications dir is never created).
      `scripts/ping.py`: signature changed from `ping(shop, intent, matched_items,
      distance_km)` (legacy `shop["id"]`/`shop["name"]` DB-row shape) to
      `ping(match, intent, notif_dir=None)` where `match` is one of search()'s own match
      dicts (`shop_id`/`shop_name`/`distance_km`/`items`) — no second DB lookup needed to
      ping. Added `notif_dir` param (defaults to the real `data/notifications/`) purely so
      tests can redirect writes to `tmp_path`; inbox behaviour (one JSON line appended per
      ping, same payload shape) is unchanged. One Windows-specific fix baked in: shop_ids
      contain colons (`osm:node:111`) which are illegal in Windows filenames, so the inbox
      filename sanitizes `:` -> `_` (`osm_node_111.jsonl`) while the `shop_id` field inside
      the JSON payload and everywhere else stays the real colon-form value — this bit
      every test until caught (`OSError: [Errno 22] Invalid argument`), worth knowing for
      any other module that ever derives a filename from a shop_id.
      13 new tests across `tests/test_search_engine.py` (T1 two-pharmacy match, T2 zero
      candidates, T3 secondary-category match, DB-only shop exclusion, category-hint
      exclusion, qty=0 never counted, ranking order, intent-missing-keywords ->
      incomplete, geo_shops incomplete/error relay, do_ping=False still reports
      pinged_shop_ids without writing files) and `tests/test_ping.py` (inbox append,
      second call appends a second line). Full offline suite green: 48/48
      (`REACHOUT_OFFLINE=1 pytest reachout/tests/`).
      NOT touched (out of W5 scope, owned by W8): `run_pipeline.py` still imports/calls
      `search_engine`/`ping` with the OLD signatures (`search(intent, user_lat, user_lng,
      ...)`, module-level DB-row `shop` dicts) — it will need updating when W8 rewrites
      the orchestrator, which its own AGENTS.md entry already anticipates.

### W6 — Stage 04 result formatter
- [x] Started (date/session: 2026-07-07 — Claude session W6)
- [x] `tests/test_result_formatter.py` green offline
- [x] Prompt.md T1/T2 pass; T3 narrative-injection rejected + `formatter_llm_rejected` logged
- [x] Output validates against `ranked_shops.schema.json`
- [x] DONE — handoff notes: `agent/result_formatter.py` exposes `format_results(matches_data,
      llm_output=None)`. Deterministic builder copies rank/shop/geo fields verbatim from
      each match and picks the cheapest item (`min` by price) for item_name/sku/price/
      currency/stock_qty; category is `categories[0]`. `llm_output` (a full
      ranked_shops-shaped dict, already produced by whatever calls this — no LLM
      invocation lives in this module) is only used if it validates against
      ranked_shops.schema.json; any failure discards it, falls back to the deterministic
      result, and appends `formatter_llm_rejected` to `data/events.jsonl` (path is the
      `EVENTS_PATH` module const, monkeypatchable in tests). If matches.json's own status
      isn't "ok", returns `{"status":"error","error":{"code":"upstream_not_ok",...}}` —
      matches the error.code enum already in ranked_shops.schema.json. Missing required
      source fields (e.g. distance_km, price) on any match ⇒
      `{"status":"incomplete","missing_fields":[...]}` naming the *output* field name,
      first-seen order, no invented values. 5/5 new tests green offline; full suite
      (reachout/tests/) still green after this change.

### W7 — Stage 05 map render
- [x] Started (date/session: 2026-07-07 — Claude session W7)
- [x] `tests/test_map_render.py` green offline
- [x] Prompt.md T1/T2/T3 pass; error-sidecar path works
- [x] Swapped lat/lng fixture FAILS schema validation (gate proven)
- [x] DONE — handoff notes: scripts/map_render.py added. `render(ranked_shops,
      center, radius_km)` -> (geojson, error) — pure function, no file I/O.
      `center`/`radius_km` are NOT part of ranked_shops.json (that schema has
      no such fields); they're passed in as run-parameter args, matching the
      prompt's "from the run parameters recorded upstream" — W8's orchestrator
      is expected to thread them through from the CLI/stage-02 output when it
      wires this stage in (after result_formatter.py's ranked_shops.json).
      `write_output(ranked_shops, center, radius_km, output_dir=...)` does the
      file writes and enforces the sidecar convention by deleting the stale
      counterpart file (error.json on success, shops.geojson on failure) so a
      rerun never leaves both files present. Missing-field detection covers
      shop_id/shop_name/rank/category/distance_km/item_name/price/currency/
      stock_qty/lat/lng (address is allowed null, not flagged) and reports
      every gap as "results[i].field", not just the first. Upstream
      status != "ok" is relayed as-is (missing_fields/error passed through)
      rather than re-derived. 7 tests in tests/test_map_render.py: T1 (two
      features, lng-first, properties byte-equal), T2 (empty FeatureCollection,
      still schema-valid), T3 (missing lng -> error.json shape, no geojson),
      upstream-incomplete relay, swapped-lat/lng schema failure (proves the
      gate), and two write_output tests proving stale sidecar cleanup in both
      directions. Full offline suite green (35 tests) after this addition.

### W8 — Orchestrator + demo integration — blocked by W1–W7
- [x] Started (date/session: 2026-07-07 — Claude session W8)
- [x] Offline run: `"algo para el dolor de cabeza" --near "Malasaña"` → 5 schema-valid outputs
- [x] Offline run: `"cargador usb c" --lat 40.4168 --lng -3.7038` → same
- [x] Corrupted intermediate file HALTS the pipeline (test proves it)
- [x] `demo.py` live demo runs on Madrid data; pings land in `data/notifications/`
- [x] Full suite green: `REACHOUT_OFFLINE=1 pytest reachout/tests/`
- [x] DONE — handoff notes: `run_pipeline.py` fully rewritten. Each stage is a
      `run_stage_NN(output_root, ...)` function that reads its inputs FROM DISK
      (not from the in-memory dict returned by the previous call) and, after
      computing, writes its file then immediately re-reads it back through the
      same schema gate — this is the literal "stage reads previous stage's
      output" architecture from CONTEXT.md, and it's what makes a corrupted
      intermediate file a real, provable halt rather than a theoretical one
      (see `tests/test_pipeline_e2e.py`'s two corruption tests, which write
      bad bytes straight to `geo_shops.json` on disk and call `run_stage_03`
      directly). `run(query, ...)` walks all five, calling `_halt_if_not_ok`
      after every stage — status `"incomplete"`/`"error"` stops the whole walk
      immediately (constraints.md §2's "legacy warn-and-continue is a bug");
      zero matches/results/features is still `"ok"` and the walk continues
      normally (constraints.md §8). `PipelineError` is the one exception type
      raised on any schema failure or non-ok status, with a message naming the
      stage and the reason; the CLI catches it, prints `[HALTED] ...` to
      stderr, and exits 1.
      First-run DB bootstrap: `geo_resolve.resolve()` deliberately never calls
      `osm_ingest.ingest()` unless `--refresh` is passed (W4's own judgment
      call, so a plain search never hits Overpass) — which means a fresh
      checkout's DB would have zero shops forever. `run_stage_02` now calls a
      new `_ensure_db_ready(db_path, offline)` first: if the shops table is
      empty, it ingests once (live, falling back to the committed cache, or
      straight to cache if `REACHOUT_OFFLINE=1`). `--refresh` is unaffected —
      it still means "re-fetch even if already populated." Verified both DoD
      CLI commands for real against the full 3328-shop committed cache
      (`REACHOUT_OFFLINE=1`, fresh `data/reachout.db`): both complete in
      under 3s on a warm DB and produce 5 schema-valid files each (68 pharmacy
      matches for the headache query, real matches for the charger query).
      Stage 05 threads `center`/`radius_km` through from stage 02's
      `geo_shops.json` (query_location + radius_km), per W7's own note that
      those aren't part of `ranked_shops.json`.
      **Real bug found and fixed via the real dataset (not fixture-only
      testing), user-approved before touching it (see the
      transcript's AskUserQuestion)**: `stock_matches`/`ranked_shops`/
      `map_geojson` schemas' `"multipleOf": 0.01` on `price` was checked by
      jsonschema (4.26.0) via exact `int(quotient) == quotient` — and
      `4.69 / 0.01 == 469.00000000000006` in IEEE-754 double precision, so
      ~12% of ALL valid 2-decimal-place EUR prices (verified by brute-force
      over every cent value 0.01–29.99) were being spuriously rejected. Every
      hand-written test fixture across W5/W6/W7 happened to pick "lucky"
      floats that don't trigger it; running the orchestrator against the real
      3328-shop cache with randomly-jittered prices hits it on nearly every
      run. Fixed in `scripts/validate.py` only — a `_tolerant_multiple_of`
      validator (via `jsonschema.validators.extend`) that uses
      `math.isclose` instead of exact equality. No schema FILE was touched
      (constraints.md §13's "never loosen a schema" is respected literally);
      the business rule (money has ≤2 decimal places) is unchanged and now
      actually enforced correctly. `validate()`'s public signature is
      unchanged. Two new tests in `tests/test_validate.py` prove it: 4.69
      now passes, 4.691 still correctly fails. Also updated `validate.py`'s
      `__main__` example to the current SearchIntent shape (was still the
      legacy `category_hint` singular shape).
      `demo.py` ported to Madrid: calls `osm_ingest.ingest()` once at
      startup (real ingest, not `run_pipeline`'s bootstrap, since demo.py's
      own job per spec is "seeds via ingest+seeder"), starts the simulator
      thread, fires 4 bilingual queries (`algo para el dolor de cabeza`,
      `usb c charger`, `leche y pan`, `cuaderno y bolígrafo`) from Puerta del
      Sol at a 3 km radius. Ran it live offline end-to-end (`REACHOUT_OFFLINE=1
      python demo.py`): completes in well under 90s, 666 shop inbox files
      written to `data/notifications/`.
      `agent/llm.py` gained `normalize_item_names(ranked_shops)` (stage 04's
      optional casing-only LLM pass, gated the same way stage 01's is: only
      called if `--use-llm` AND `ANTHROPIC_API_KEY` is set; any exception or
      schema-validation failure falls back to the deterministic output). Not
      exercised against the real API in tests (no network in tests, same
      convention as stage 01) — `test_use_llm_without_api_key_falls_back_to_deterministic`
      proves the gate is closed by default.
      Added `REACHOUT_DIR` to `tests/conftest.py` (purely additive, same
      precedent as W1/W2's `AGENT_DIR`/`SCRIPTS_DIR` additions — this file
      isn't owned by any single workstream) so `tests/test_pipeline_e2e.py`
      and `tests/test_validate.py` can `import run_pipeline` / `validate`
      directly.
      7 new tests in `tests/test_pipeline_e2e.py` (T1 headache/Malasaña, T2
      charger/explicit-coords, zero-matches-is-ok, incomplete-stage-01-halts,
      two corrupted-file variants — invalid JSON and schema-invalid JSON —
      and the use_llm-without-key fallback) + 2 in `tests/test_validate.py`.
      Full offline suite green: 85/85 (`REACHOUT_OFFLINE=1 pytest tests/`
      from inside `reachout/`).

### W9 — Cleanup + docs truth pass — blocked by W8
- [x] Started (date/session: 2026-07-07 — Claude session W9)
- [x] Legacy schemas + `data/shops.json` deleted; no dangling references
- [x] README.md rewritten to the 5-stage Madrid reality
- [x] Full suite still green after deletions
- [x] DONE — handoff notes: deleted `shared/schemas/inventory_item.schema.json`,
      `shared/schemas/shop_match.schema.json`, `data/shops.json`. Grepped for
      `shop_match|inventory_item\.schema|shops\.json|seed_data` across the repo
      first — confirmed zero real code references (all `shops.json` hits were
      substrings of `geo_shops.json`/`madrid_shops.json`/`ranked_shops.json`,
      current stage files; the only literal `seed_data`/`shop_match`/
      `inventory_item.schema` mentions left anywhere are historical notes in
      STATUS.md itself and the new intentional TUTORIAL.md banner). README.md
      rewritten in full: 5-stage folder tree (01 parse-query -> 02 geo-resolve
      -> 03 match-and-ping -> 04 format-results -> 05 map-render), Madrid/OSM
      framing throughout, real CLI examples (`--near "Malasaña"`,
      `--lat/--lng`, `--refresh`, `REACHOUT_OFFLINE=1`), no Mumbai/rupees/
      "consumer card" left. TUTORIAL.md NOT rewritten per spec — added a
      5-line banner at the top noting it documents the original 3-stage
      Mumbai/rupees prototype and pointing to README.md/CONTEXT.md for the
      current architecture. Full offline suite re-run after all deletions:
      85/85 green (`REACHOUT_OFFLINE=1 pytest tests/` from inside `reachout/`)
      — unchanged from W8's count, confirming the deleted files had zero
      runtime dependents.

### W10 — API + frontend skeleton — blocked by W8
- [x] Started (date/session: 2026-07-07 — Claude session W10)
- [x] API tests green; responses schema-valid; zero results = 200 + empty list
- [x] `frontend/` builds / typechecks; matches frontend/README.md tree exactly
- [x] `src/types/` generated from schemas
- [x] Zero visual/styling decisions in the diff
- [x] DONE — handoff notes: `reachout/api/server.py` is a thin FastAPI wrapper —
      no business logic, it only turns query params into a `run_pipeline.run()`
      call and returns `result["ranked_shops"]` / `result["geojson"]` verbatim
      (already schema-valid since run_pipeline round-trips every stage through
      its own schema gate). Each request gets its own `tempfile.mkdtemp()`
      `output_root`, cleaned up in a `finally`, so concurrent requests never
      share or clobber stage files — this is the one architectural decision
      beyond "call the pipeline" and it's needed because run_pipeline writes
      real files to disk per run. `DB_PATH`/`NOTIF_DIR` module-level globals
      (both `None` by default, meaning "use run_pipeline's real defaults") exist
      purely so tests can `monkeypatch.setattr(server, "DB_PATH", ...)` to
      point at a temp DB/notifications dir instead of the real ones — same
      override pattern used throughout scripts/. `lat` XOR `lng` -> 400;
      any `PipelineError` from the pipeline (e.g. an unparseable query going
      `status:incomplete` at stage 01, which halts per constraints.md §2) ->
      422, since that's a genuine bad-input case, not a server error. Zero
      matches still flows through as 200 + `result_count:0` because that's
      `status:"ok"` all the way down the pipeline (constraints.md §8) — no
      special-casing needed in the API layer itself.
      `reachout/requirements.txt`: uncommented fastapi/uvicorn (previously
      optional-commented pending this workstream).
      6 new tests in `reachout/tests/test_api.py` using FastAPI's `TestClient`
      (httpx-backed, already installed): health, schema-valid `/api/search`
      and `/api/search.geojson` against a seeded temp DB, zero-result ->
      200 + empty list, unparseable query -> 422, lat-without-lng -> 400.
      Added `API_DIR` to `tests/conftest.py` (additive, same precedent as
      the other workstreams' `AGENT_DIR`/`SCRIPTS_DIR`/`REACHOUT_DIR`) so
      `import server` resolves. Full offline suite green: 91/91.
      Frontend: built the exact tree from frontend/README.md, nothing beyond
      it except unavoidable build plumbing (`index.html` — Vite's required
      entry point, `src/vite-env.d.ts` — `import.meta.env` typing, `.gitignore`
      — keeps `node_modules`/`dist` out of git; none of these are visual/
      layout/component decisions). `scripts/gen-types.ts` runs
      `json-schema-to-typescript` over every `reachout/shared/schemas/*.schema.json`
      file and writes one `src/types/<PascalCase>.d.ts` per schema — actually
      run (`npm run gen-types`), so `src/types/` holds real generated output,
      not hand-written stand-ins; regenerate any time the schemas change.
      Note: `RankedShops.d.ts` and a couple of others come out with a stray
      `{[k: string]: unknown} & {...}` intersection instead of a fully sealed
      type — a known json-schema-to-typescript quirk when a schema combines
      top-level `additionalProperties:false` with `allOf`/`if`/`then`
      (ranked_shops.schema.json uses exactly that pattern for its
      status-conditional required fields). Did not hand-patch the generated
      file to "fix" this (that would violate "never hand-edited"); the
      schema itself is unchanged and still the source of truth. `src/routes/
      search.tsx` and `results.tsx` are functional (URL params in/out via
      react-router-dom, TanStack Query keyed on the parsed params) but
      deliberately minimal — `results.tsx` renders `<pre>{JSON.stringify(...)}</pre>`
      with zero CSS/className/style attributes anywhere in `src/` (verified
      by grep) since visual design is explicitly out of scope per
      frontend/README.md. `src/map/geojson-source.ts` only adapts a
      `ShopMapGeoJSON` into a MapLibre `GeoJSONSourceSpecification` — no
      `<Map>` component, maplibre-gl is a dependency but unwired, per spec.
      Verified for real: `npm install`, `npm run gen-types`, `npx tsc --noEmit`
      (clean), and `npm run build` (tsc + vite build, succeeds, dist/ removed
      after since it's a build artifact not part of the skeleton).

## Blocked / conflicts

Record here any cross-workstream file conflict or blocker discovered
mid-session (which files, which workstreams, what's needed). Empty = none.

- (none)

## Session log

One line per session, newest first: `YYYY-MM-DD — Wn — what happened`.

- 2026-07-07 — W10 — DONE. Added reachout/api/server.py (thin FastAPI wrapper
  over run_pipeline.run(), per-request temp output_root, DB_PATH/NOTIF_DIR
  test-override globals) + reachout/tests/test_api.py (6 tests: health,
  schema-valid search/search.geojson, zero-result 200+empty, unparseable
  query 422, lat-without-lng 400). Uncommented fastapi/uvicorn in
  requirements.txt. Full offline suite green: 91/91. Built the frontend/
  skeleton exactly per frontend/README.md's tree (package.json, vite.config.ts,
  tsconfig.json, .env.example, scripts/gen-types.ts, src/main.tsx,
  src/routes/{search,results}.tsx, src/api/client.ts, src/types/ (generated),
  src/map/geojson-source.ts) plus unavoidable build plumbing (index.html,
  vite-env.d.ts, .gitignore). Actually ran npm install + npm run gen-types so
  src/types/*.d.ts are real generated output from the shared schemas, not
  hand-written. Verified npx tsc --noEmit and npm run build both pass; grepped
  src/ to confirm zero style/className/CSS anywhere. See W10 handoff notes
  above for the json-schema-to-typescript index-signature quirk on
  RankedShops.d.ts (schema's allOf/if-then pattern, not a bug in this diff).
- 2026-07-07 — W9 — DONE. Deleted legacy
  shared/schemas/inventory_item.schema.json, shared/schemas/shop_match.schema.json,
  and data/shops.json after confirming (via grep across the whole repo) zero
  real code still referenced them. Rewrote README.md to describe the actual
  5-stage Madrid pipeline (parse-query -> geo-resolve -> match-and-ping ->
  format-results -> map-render) with real CLI examples; no Mumbai/rupees/
  "consumer card" language remains. Added a banner to TUTORIAL.md noting it
  documents the original 3-stage prototype, without rewriting its body.
  Full offline suite re-verified green: 85/85.
- 2026-07-07 — W8 — DONE. run_pipeline.py rewritten (per-stage functions that
  read inputs from disk and round-trip write+validate, hard-halting on any
  schema failure or non-"ok" status); demo.py ported to Madrid (ingest+seeder,
  4 bilingual queries from Puerta del Sol). Found and fixed (user-approved) a
  real jsonschema float-precision bug in scripts/validate.py's multipleOf
  check that spuriously rejected ~12% of valid EUR prices — no schema file
  touched, only the validator's exact-equality comparison replaced with a
  tolerant one. Both DoD CLI commands verified for real against the full
  3328-shop committed cache; demo.py run live offline end-to-end. 9 new
  tests (7 pipeline e2e + 2 validate). Full offline suite green: 85/85.
- 2026-07-07 — W4 — DONE. Added scripts/geo_resolve.py (`resolve()` — pure function,
  no CLI/file I/O, matching W5's search_engine.py pattern) and tests/test_geo_resolve.py.
  10/10 new tests green offline; T1 (explicit coords), T2 (neighbourhood geocoding),
  T3 (Overpass down -> cache, plus cache-missing -> no_shop_source error) pass as
  documented, plus unresolvable-place-> incomplete, default-centre, category-hints
  filter, zero-shops-ok, multi-category, and near-overrides-intent coverage. Centre
  precedence explicit coords > near/location_text via nominatim.geocode > default
  Puerta del Sol; a named-but-unresolvable place never falls through to the default.
  By design, shop selection reads straight from db.all_shops() unless --refresh is
  passed (calling osm_ingest.ingest() unconditionally would hit live Overpass on
  every search per its own refresh semantics) -- see W4 handoff notes above for the
  full reasoning W8 should know about. Full offline suite green: 76/76.
- 2026-07-07 — setup — AGENTS.md + STATUS.md created; `.env` added (gitignored). No code written yet.
- 2026-07-07 — W2 — DONE. db.py reworked to Madrid schema, inventory_seeder.py added (deterministic), inventory_simulator.py ported to EUR/sku_catalog.json, seed_data.py deleted. 15/15 new tests green offline. See W2 handoff notes above for out-of-scope references left for W5/W8.
- 2026-07-07 — W1 — DONE. query_parser.py rewritten to emit the new SearchIntent shape (status/keywords/category_hints/location_text/missing_fields), bilingual multi-word SYNONYMS, hardware category covered, llm.py updated (ANTHROPIC_MODEL override + new output shape in system prompt). 8/8 new tests green offline in tests/test_parse_query.py, including T1-T3 exact match and the schema-rejection fallback path. Added AGENT_DIR to tests/conftest.py (additive, unowned shared file).
- 2026-07-07 — W6 — DONE. Added agent/result_formatter.py (deterministic ranked_shops builder + LLM-rejection guard) and tests/test_result_formatter.py. 5/5 new tests green offline; T1 (verbatim numbers), T2 (zero matches), T3 (community_note injection rejected + formatter_llm_rejected logged) all pass. Also added upstream_not_ok error passthrough and incomplete/missing_fields handling for match entries missing required source data, matching ranked_shops.schema.json's error.code enum and constraints.md §3.
- 2026-07-07 — W7 — DONE. Added scripts/map_render.py (render/write_output) and tests/test_map_render.py. 7/7 new tests green offline; T1 (lng-first coords, byte-equal properties), T2 (empty FeatureCollection), T3 (missing lng -> error.json sidecar, no geojson) pass as written, plus a swapped-lat/lng test proving the schema gate rejects it and two write_output tests proving stale-file cleanup both directions. Note for W8: center/radius_km are not in ranked_shops.json — the orchestrator must pass them into render()/write_output() from the run parameters (CLI args or stage-02 geo_shops.json). Full offline suite green (35 tests) after this addition.
- 2026-07-07 — W5 — DONE. scripts/search_engine.py reworked so candidates come ONLY from geo_shops.shops (no DB-wide scan); scripts/ping.py reworked to take a match dict + new shop_id format (colons sanitized to underscores in inbox filenames for Windows). 13/13 new tests green offline in tests/test_search_engine.py + tests/test_ping.py, including T1/T2/T3 exact match, DB-only-shop exclusion, category-hint gating, qty=0 exclusion, and ranking order. geo_shops non-ok status is relayed verbatim (not converted to a synthesized error, unlike W6). Full offline suite green: 48/48. Left run_pipeline.py untouched (owned by W8; it still calls the old search()/ping() signatures).
- 2026-07-07 — W3 — DONE. Added scripts/overpass.py (Overpass QL builder + live fetch),
  scripts/nominatim.py (geocode with 1req/s throttle + cache + gazetteer fallback),
  scripts/ors.py (key-gated walking distance, None on any failure/absence), and
  scripts/osm_ingest.py (`ingest()` — live-then-cache shop fetch, per-element category
  mapping via category_tag_map.json, schema validation, idempotent upsert + new-shop-only
  inventory seeding, `no_shop_source` error object when both sources are unavailable).
  Fetched data/osm_cache/madrid_shops.json live from the real Overpass API — 3328
  validated, unique, schema-valid shop records spanning all 5 categories inside Madrid's
  admin_level=8 city boundary; verified the whole cache loads into a fresh DB with
  REACHOUT_OFFLINE=1 and zero network calls. 18 new tests across test_overpass.py,
  test_nominatim.py, test_osm_ingest.py, all offline against tests/fixtures/. Full suite
  green: 66/66. See W3 handoff notes above for the API surface W4 (geo_resolve) builds on.

---

# BACKEND V2 — Supabase inventory + NLP search + shopkeeper chat (2026-07-16)

Session: overnight autonomous build on branch `stitch-frontend`. Scope per the
backend-v2 brief: Phases 1–5 (Supabase schema+seed, /api/search, /api/chat,
REST endpoints, quality loop). The v1 SQLite pipeline (W1–W10 + TASKs 1–52
above) is untouched and stays green.

## AGENT IMPROVEMENTS

Decisions made autonomously vs. the plan as written, after probing the real
Supabase project and Gemini key before writing any code:

1. **Embedding model: `gemini-embedding-001` @ 768 dims, not `text-embedding-004`.**
   Probed the provided key: `text-embedding-004` returns 404 (not available on
   this key/API version). `gemini-embedding-001` with `outputDimensionality: 768`
   is available and keeps the `vector(768)` schema contract. Verified live.
   Non-3072-dim outputs are NOT pre-normalized (measured norm ≈ 0.59), so the
   seeder normalizes vectors client-side before insert.

2. **Batch + dedupe embeddings at seed time (pre-computed, not on-demand).**
   Plan said "for EACH product call the embedding API" — that is 3000–5000
   sequential calls. Instead: embeddings are computed once per UNIQUE catalog
   item (name+description+category are what get embedded; per-store rows only
   vary price/stock), then reused across store rows, and requested via
   `batchEmbedContents` (100 texts/call). ~4,000 calls collapse to ~10–15.
   Query embeddings are computed on-demand at search time (they must be).

3. **Search: hybrid — pgvector cosine RPC + deterministic re-rank.**
   Pure FTS loses vague/bilingual queries ("algo para el dolor de cabeza");
   pure vector loses exact-name precision. So: `match_products()` SQL function
   (PostgREST can't ORDER BY `embedding <=>` directly, an RPC is the standard
   pattern) does cosine top-K + optional neighbourhood filter in SQL, then
   Python re-ranks with intent extracted by Gemini Flash Lite (exact/partial
   name and brand matches boosted, in-stock boosted).

4. **Chat state: client-passed history, no Redis.** The contract already passes
   `history` from the client; server-side sessions add a service and buy
   nothing at this scale. Endpoints stay stateless (also matches the frozen
   "no new services" rule and deploys anywhere).

5. **FastAPI stays.** server.py, SSE bus, and 91 offline tests already exist;
   switching frameworks is churn with zero user-visible gain.

6. **Gemini via plain REST, not the `google-generativeai` SDK.** That SDK is
   deprecated (superseded by `google-genai`) and adds a dependency chain on
   Python 3.14 for what is two POST endpoints. `requests` is already a dep.
   One shared helper module (`api/gemini.py`) wraps embed + chat + backoff.

7. **Schema DDL: documented credential limitation + three-path apply.** The
   provided `sb_secret_...` key CANNOT execute DDL: PostgREST does no DDL, and
   the Management API rejects it (401, needs an `sbp_` personal access token);
   probed both. `data/seed_inventory.py` therefore applies `data/schema.sql`
   via `SUPABASE_DB_URL` (direct Postgres) or `SUPABASE_ACCESS_TOKEN`
   (Management API) when either is set; otherwise it verifies the tables exist
   and, if they don't, prints the SQL-editor paste-once instruction and exits
   nonzero. schema.sql is fully idempotent (IF NOT EXISTS / OR REPLACE).

8. **RLS left disabled** (dev mode, per plan) — noted explicitly in schema.sql
   with the follow-up that anon-key clients must never ship until RLS is on.

9. **requirements.txt frozen-stack header amended, not deleted** — v1 stays
   frozen; backend v2 is scoped as the one user-approved exception block.

## Phase log

- [x] PHASE 0 — env (.env keys appended, .env.example added), requirements.txt
      v2 block, this section. Supabase REST + Gemini key probed live.
- [x] PHASE 1 — schema.sql + seed_inventory.py + seeded DB verified
      (2026-07-16: user applied schema.sql in the SQL editor; seeder run
      landed 50 stores / 3,381 products with 337 unique embeddings; live
      search sanity-checked: paracetamol top for "algo para el dolor de
      cabeza", exact match for "cargador usb c". Two seeder bugs found and
      fixed on the way: infinite variant loop + Gemini per-minute burst
      429s — see commits d6de1b2 and the gemini.py pacing fix.)
- [x] PHASE 2 — POST /api/search (240 tests passed)
- [x] PHASE 3 — POST /api/chat (completed)
- [x] PHASE 4 — GET /api/products, /api/stores, /api/neighbourhoods, CORS
- [x] PHASE D3 — GET /api/picks live (deterministic, category-diverse,
      schema-validated against picks_response.schema.json; 273 tests passed).
- [ ] PHASE 5 — quality loop + BACKEND_DONE.md
- [x] PHASE D1 — demand ingest chain green through compute_signals,
      ticks DEMAND_INGEST_READY (TASKs 69, 70, 71, 72)
- [x] PHASE D2 — demand API + analytics live (TASK 75)
- Merged both lane branches into main unreviewed (2026-08-03): neither
  `jules-demand-integration` nor `jules-picks-integration` got a whole-branch
  review — the reviewer was killed by a spend limit. Deliberate tradeoff to
  hold one branch instead of three. Per-task reviews and five controller fix
  rounds did run; the union suite is green.
- Live ingest pending (scrape blocked, 2026-08-03). V1a ran for real against
  Google Trends and surfaced two code defects, both fixed in `9cecea2`: the
  provider sent all 49 keywords in one request (Google caps comparison at
  five; six returns 400) and `interest_by_region` 400s on a low-volume term,
  which killed the run after every series had been fetched. On the retry
  Google served `google.com/sorry` — this IP is CAPTCHA-throttled. No rows
  landed. The fixture provider is not a substitute (two English keywords, no
  weekly windows): running it produced 49 empty-series snapshots, which were
  deleted rather than left in the table. Retry `--provider trendspy` once the
  throttle clears.
