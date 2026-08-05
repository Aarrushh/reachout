# CONTEXT.md  (Layer 1: Where do I go?)

This routes the demand chain: ingest -> signals -> recommend -> api. The
chain order below is the read/write order.

**The whole chain is BUILT.** Every file in the "File" column exists, is
tested, and runs. The five JSON Schemas in `shared/schemas/` and the
Postgres DDL (`data/schema.sql`) are committed and **DO-NOT-MODIFY** — if
an output fails validation, the OUTPUT is wrong; never widen a schema to
let a payload through.

What is *not* done is the live data: **the three `demand` tables are empty**
(verified 2026-08-05). The chain has never processed a real Google Trends
capture — see "Live status" below. The API still serves a real,
schema-valid payload because of the committed fixture (D10), and it labels
it as practice data.

If a Jules master-context block or any other doc disagrees with this file,
trust this file — it is kept honest on purpose.

## Chain (Madrid demand service)

| Step | File | Task | Status | Reads | Writes |
|------|------|------|--------|-------|--------|
| 1 | `ingest/keywords.py` | TASK 70 | **BUILT** | `public.products.category` (via `.schema("public")` on the injected client) union `_config/seed_keywords.json` (47 Spanish terms) | in-memory keyword universe (`list[str]`, deduped case-insensitively, sorted, capped at 100) |
| 2 | `ingest/trends_client.py` | TASK 69 | **BUILT** | Google Trends via `trendspy` (lazy-imported) or canned payloads in `tests/fixtures/trends/` | raw capture dicts shaped like `trend_snapshot.schema.json`'s `series` / `region_breakdown` |
| 3 | `ingest/snapshot_store.py` | TASK 71 | **BUILT** | step 2's capture dicts, validated against `shared/schemas/trend_snapshot.schema.json` | `demand.trend_snapshots` (upsert on `keyword,geo,timeframe,captured_date`) |
| 4 | `scripts/compute_signals.py` | TASK 72 | **BUILT** | snapshots (as built/sent, **never** a `select("*")` result) | `demand.demand_signals`, validated against `shared/schemas/demand_signal.schema.json` |
| 5 | `scripts/recommend.py` | TASK 73 | **BUILT** | `demand.demand_signals` + `public.products` composition | `demand.recommendations`, validated against `shared/schemas/recommendation.schema.json` |
| 6 | `api/app.py` | TASK 74 / 77 | **BUILT** | `demand.trend_snapshots`, `demand.demand_signals`, `demand.recommendations`, `public.products` | `GET /demand/api/health`, `/trends`, `/signals`, `/recommendations`, `/analytics` |
| 7 | `scripts/run_ingest.py` | TASK 75 | **BUILT** | chains steps 1-5 | batch entrypoint; `--dry-run` writes nothing, `--provider fixture\|trendspy` |

## Run it

From the **repo root** (the modules import `demand.*`, which only resolves
with the repo root on `sys.path`):

```
python -m demand.scripts.run_ingest --provider fixture --dry-run   # writes nothing
python -m demand.scripts.run_ingest --provider trendspy            # the live run
uvicorn demand.api.app:app --port 8001                             # the API
python -m pytest demand/tests -q                                   # 158 tests
```

The API serves `/demand/api/health` unauthenticated (no auth anywhere — D2)
and every other endpoint schema-validated. `/analytics` serves the committed
fixture unless `DEMAND_ANALYTICS_SOURCE=live`.

## Live status — the tables are empty

`demand.trend_snapshots`, `demand.demand_signals` and `demand.recommendations`
all hold **0 rows**. The Supabase schema is applied, exposed on the Data API,
and granted to `service_role` (M3, verified by a live REST probe). The chain
runs. What has not succeeded is the **live scrape**: Google IP-throttled the
project and served a CAPTCHA. Two rounds of hardening came out of the
attempts — 5-terms-per-request batching and anchor rescaling
(`ingest/trends_client.py`), and surviving a missing region breakdown
(`scripts/run_ingest.py`) — but no rows have landed.

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
