# CONTEXT.md  (Layer 1: Where do I go?)

This routes the demand chain: ingest -> signals -> recommend -> api. The
chain order below is the read/write order.

**The whole chain is BUILT.** Every file in the "File" column exists, is
tested, and runs. The five JSON Schemas in `shared/schemas/` and the
Postgres DDL (`data/schema.sql`) are committed and **DO-NOT-MODIFY** — if
an output fails validation, the OUTPUT is wrong; never widen a schema to
let a payload through.

What is *not* done is the live data: **all four `demand` tables are empty**
(verified 2026-08-05; `rising_queries` has never held a row). The chain has
never processed a real Google Trends capture — see "Live status" below. The
API still serves a real, schema-valid payload because of the committed
fixture (D10), and it labels it as practice data.

If a Jules master-context block or any other doc disagrees with this file,
trust this file — it is kept honest on purpose.

## Chain (Madrid demand service)

| Step | File | Task | Status | Reads | Writes |
|------|------|------|--------|-------|--------|
| 1 | `ingest/keywords.py` | TASK 70 | **BUILT** | `public.products.category` (via `.schema("public")` on the injected client) union `_config/seed_keywords.json` (47 Spanish terms) | in-memory keyword universe (`list[str]`, deduped case-insensitively, sorted, capped at 100) |
| 2 | `ingest/trends_client.py` | TASK 69 | **BUILT** | Google Trends via **SerpApi** (`ingest/serpapi_client.py`, one billed search per request) or canned payloads in `tests/fixtures/trends/` | raw capture dicts shaped like `trend_snapshot.schema.json`'s `series` / `region_breakdown` |
| 3 | `ingest/snapshot_store.py` | TASK 71 | **BUILT** | step 2's capture dicts, validated against `shared/schemas/trend_snapshot.schema.json` | `demand.trend_snapshots` (upsert on `keyword,geo,timeframe,captured_date`) |
| 4 | `scripts/compute_signals.py` | TASK 72 | **BUILT** | snapshots (as built/sent, **never** a `select("*")` result) | `demand.demand_signals`, validated against `shared/schemas/demand_signal.schema.json` |
| 5 | `scripts/recommend.py` | TASK 73 | **BUILT** | `demand.demand_signals` + `public.products` composition | `demand.recommendations`, validated against `shared/schemas/recommendation.schema.json` |
| 6 | `api/app.py` | TASK 74 / 77 | **BUILT** | `demand.trend_snapshots`, `demand.demand_signals`, `demand.recommendations`, `public.products` | `GET /demand/api/health`, `/trends`, `/signals`, `/recommendations`, `/analytics` |
| 7 | `ingest/rising_store.py` | SERPAPI TASK 5 | **BUILT** | the discovery pass's RELATED_QUERIES rows (one billed search per parent keyword, `hl="en"`) | `demand.rising_queries` (upsert on `id`, a uuid5 of `parent_keyword,query,geo,gprop,captured_date` — `gprop` is in the key because a Shopping-derived row and a Web-derived row mean different things) |
| 8 | `scripts/run_ingest.py` | TASK 75 / SERPAPI TASK 6 | **BUILT** | chains steps 1-5, then runs the discovery pass into step 7 | batch entrypoint; `--provider serpapi\|fixture`, `--spend` required for the paid provider, `--dry-run` skips database writes |

## Run it

From the **repo root** (the modules import `demand.*`, which only resolves
with the repo root on `sys.path`):

```
python -m demand.scripts.run_ingest --provider fixture --dry-run   # free, writes nothing
python -m demand.scripts.run_ingest --provider serpapi             # prints the cost, spends nothing
python -m demand.scripts.run_ingest --provider serpapi --spend     # the live run — SPENDS ~22 searches
uvicorn demand.api.app:app --port 8001                             # the API
python -m pytest demand/tests -q                                   # 289 tests
```

**`--spend` is the only thing that makes a run cost money, and `--dry-run` is
not the opposite of it.** `--dry-run` skips database writes; it does not skip
API calls, so `--provider serpapi --spend --dry-run` makes all 22 searches and
keeps nothing. The gate itself lives in `run_chain(spend=...)`, not in
`main()`, so no caller can spend by forgetting to check — including
`api/app.py`'s optional weekly cron, which has to set `DEMAND_INGEST_CRON=1`
**and** `DEMAND_INGEST_CRON_SPEND=1` and must run on a single-worker process.

## The budget is the design constraint

SerpApi bills **per search** on a **250/month** plan. One full run is 22:
12 TIMESERIES batches (49 keywords, 4 real + 1 shared anchor per request) plus
10 RELATED_QUERIES for the discovery pass, which cannot batch — RELATED_QUERIES
accepts exactly one query. That is why discovery runs on the top movers rather
than the universe, why the cron is weekly rather than daily, and why a bare
`--provider serpapi` prints a pre-flight estimate instead of running.

Two honesty rules ride on this path:

- **A `Breakout` row stores `growth_pct = null`.** Google returns that label
  instead of a number when growth exceeds roughly 5000%. The
  `extracted_value` sitting beside it (89800, 91000 in the committed capture)
  is an internal scale artifact, not a percentage. `parse_rising_queries`
  treats a row as a refusal *unless* its label parses as a percentage, in any
  locale — failing towards "we don't know" rather than towards a fabricated
  figure.
- **A batch whose anchor reads zero is dropped, not guessed.** Google
  renormalises every request to 0-100 independently, so batches are only
  comparable through the shared anchor. If the anchor rounds to zero in a
  batch, that batch's keywords have no defensible scale and are dropped with
  a printed line saying so.

The API serves `/demand/api/health` unauthenticated (no auth anywhere — D2)
and every other endpoint schema-validated. `/analytics` serves the committed
fixture unless `DEMAND_ANALYTICS_SOURCE=live`.

## Live status — the tables are empty

`demand.trend_snapshots`, `demand.demand_signals`, `demand.recommendations`
and `demand.rising_queries` all hold **0 rows**. The Supabase schema is
applied, exposed on the Data API, and granted to `service_role` (M3, verified
by a live REST probe). The chain runs.

What has not happened is the **first live run**. It is no longer blocked on
anything external. The old blocker was scraping: `trendspy` hit Google
directly, Google IP-throttled the project and served a CAPTCHA, and the
answer was to wait. That provider is deleted and the workspace now goes
through SerpApi, which is a paid API rather than a scrape — there is no
throttle to wait out, and re-reading this section as "we are waiting for
Google" is reading a world that no longer exists.

What stands between here and rows is a **decision to spend**: one run costs
22 of the 250 searches for the month, and 8 are already spent. The run is
`--provider serpapi --spend` from the repo root, and it is deliberately not
something a script, a cron or an agent can trigger on its own.

**The fixture provider is not a substitute for live data.**
`tests/fixtures/trends/interest_over_time.json` holds **two English keywords**
(`sneakers`, `coffee`) with **three daily points each**. Running the chain
against it produces 49 snapshot rows of which 47 carry an empty series — rows
that look like data and are not. Never present a fixture run as a live one;
`api/app.py` stamps `generated_from` for exactly this reason, and the
dashboard renders a visible "practice data" banner off that field.

## Module kinds

Nothing in `demand/` is agentic — see `CLAUDE.md`'s one rule. `ingest/` and
`scripts/` are pure Python: trend math, thresholds, rankings, and database
writes are never guessed and never touch an AI. `api/app.py` is pure Python
too; it only serves what `scripts/` and `ingest/` already computed and
validated. Retailer-facing copy in `scripts/recommend.py` comes from fixed
Python string templates, not generated language.

## Three rules that are easy to break

1. **Never `SELECT *` on a demand table.**
   `demand.trend_snapshots.captured_date` is an application-set, DB-only
   column deliberately absent from `trend_snapshot.schema.json`
   (`additionalProperties: false`), so a widened select turns every row into
   a contract violation. It is not a generated column because
   `timestamptz -> date` is STABLE, not IMMUTABLE, and Postgres rejects it at
   CREATE TABLE. `tests/test_api.py` asserts no select in `api/app.py` is `"*"`.
2. **Name the schema on every cross-schema read.** The client is built with
   `ClientOptions(schema="demand")`, so a bare `.table("products")` asks for
   `demand.products`, which does not exist. `public.products` and
   `public.stores` need an explicit `.schema("public")`.
3. **Join keywords to categories through `normalize_keyword()`, on both
   sides.** The universe keeps each keyword's ORIGINAL casing (that is what
   the provider is sent); the category map is built from `products.category`.
   An exact-match lookup missed on every non-lower-case keyword and wrote
   `category: None` on every signal — which then produced **zero**
   recommendations, since `recommend.py` skips signals with no category.

## Validation

All validation goes through `shared/validation.py::validate_with_formats`,
never bare `jsonschema.validate()`: on draft-07 `format` is an annotation,
not an assertion, so without an attached `FormatChecker` an `id` of
`"not-a-uuid"` passes a `format: uuid` field silently. With
`rfc3339-validator` installed (it is, and it is in `requirements.txt`),
`uuid`, `date` **and** `date-time` are all enforced — `UNENFORCED_FORMATS`
computes empty at import. If that set is ever non-empty, a dependency went
missing and those formats stopped being checked with nothing failing loudly
to say so.
