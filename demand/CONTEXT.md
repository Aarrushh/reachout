# CONTEXT.md  (Layer 1: Where do I go?)

This routes the demand chain: ingest -> signals -> recommend -> api. The
chain order below is the read/write order. Every file in the "File" column
of the chain table below is **PLANNED** — zero `.py` chain files exist yet;
that has not changed since M1. What M2 added is the scaffolding the chain
will read and write against: the five JSON Schemas in `shared/schemas/`,
the `demand` Postgres DDL (`data/schema.sql`), the seed keyword list, and
the test helpers — those are DONE, committed, and DO-NOT-MODIFY (see
"Build status" below). If a Jules master-context block or any other doc
disagrees with this file about whether a *chain* file (`ingest/`,
`scripts/`, `api/`) exists, trust this table — this file is kept honest on
purpose. That does not extend to the schemas or the DDL: they are real and
committed, and no doc — including this one — licenses treating a
DO-NOT-MODIFY instruction on them as disbelievable.

## Chain (Madrid demand service)

| Step | File | Task | Status | Reads | Writes |
|------|------|------|--------|-------|--------|
| 1 | `ingest/keywords.py` | TASK 70 | PLANNED | `public.products.category` (via injected Supabase client) union `_config/seed_keywords.json` | in-memory keyword universe (`list[str]`) |
| 2 | `ingest/trends_client.py` | TASK 69 | PLANNED | Google Trends (via `trendspy`, lazy-imported) or canned payloads in `tests/fixtures/trends/` | raw capture dicts shaped like `trend_snapshot.schema.json`'s `series` / `region_breakdown` |
| 3 | `ingest/snapshot_store.py` | TASK 71 | PLANNED | step 2's capture dicts, validated against `shared/schemas/trend_snapshot.schema.json` | `demand.trend_snapshots` (idempotent upsert on keyword/geo/timeframe/date) |
| 4 | `scripts/compute_signals.py` | TASK 72 | PLANNED | `demand.trend_snapshots` | `demand.demand_signals`, validated against `shared/schemas/demand_signal.schema.json` |
| 5 | `scripts/recommend.py` | TASK 73 | PLANNED | `demand.demand_signals` + `public.stores` / `public.products` composition | `demand.recommendations`, validated against `shared/schemas/recommendation.schema.json` |
| 6 | `api/app.py` | TASK 74 (amended, no-auth) / TASK 77 | PLANNED | `demand.trend_snapshots`, `demand.demand_signals`, `demand.recommendations`, `public.products` | `GET /demand/api/health`, `/trends`, `/signals`, `/recommendations`, `/analytics` — the `/recommendations` body validates against `shared/schemas/recommendations_response.schema.json` and the `/analytics` body (TASK 77) against `shared/schemas/analytics_response.schema.json` |
| 7 | `scripts/run_ingest.py` | TASK 75 | PLANNED | chains steps 1-5 | batch entrypoint; `--dry-run` writes nothing, `--provider fixture\|trendspy` |

## Run it

Nothing in this chain is runnable yet — every step above is PLANNED. Once
TASK 75 lands, the batch entrypoint will be:

```
python scripts/run_ingest.py --provider fixture --dry-run
```

and the API (TASK 74/77) will serve `GET /demand/api/health` unauthenticated
and the rest schema-validated. Until then this workspace only holds the
scaffold: layer docs, the seed keyword list, empty package folders, and
test helpers.

## Build status

**What exists today (M1 + M2):**

- `CLAUDE.md`, `CONTEXT.md` — this pair, Layer 0/1.
- `_config/seed_keywords.json` — 30-50 curated Madrid retail search terms
  (Spanish), the static half of TASK 70's keyword union.
- `ingest/`, `scripts/`, `api/` — empty Python packages (`__init__.py`
  only; no chain files yet).
- `shared/schemas/` — the five schemas named in the chain table above
  (`trend_snapshot`, `demand_signal`, `recommendation`,
  `recommendations_response`, `analytics_response` — the last one backs
  TASK 77's `/analytics` endpoint, IMPLEMENTATION_PLAN_V2.md §4 and §5.5)
  EXIST — committed by M2 — and are DO-NOT-MODIFY for every later task.
- `data/schema.sql` (the Postgres `demand` schema DDL) EXISTS — committed
  by M2 — and is DO-NOT-MODIFY.
- `tests/conftest.py` — sys.path setup so `demand/` modules import cleanly
  under pytest, plus a `fake_supa` fixture.
- `tests/fake_supa.py` — chainable fake Supabase client, modelled on
  `reachout/tests/fake_supa.py`.
- `tests/fixtures/` — only a README today; TASK 69 commits the first
  canned trends payloads under `tests/fixtures/trends/`.

**What is PLANNED (not yet created, do not assume it exists):** every file
in the "File" column of the chain table above — `ingest/trends_client.py`,
`ingest/keywords.py`, `ingest/snapshot_store.py`, `scripts/compute_signals.py`,
`scripts/recommend.py`, `scripts/run_ingest.py`, `api/app.py`. The five JSON
Schemas and `data/schema.sql` are NOT planned — they already exist (above)
and are DO-NOT-MODIFY.

## Module kinds

Nothing in `demand/` is agentic — see `CLAUDE.md`'s one rule. `ingest/` and
`scripts/` are pure Python: trend math, thresholds, rankings, and database
writes are never guessed and never touch an AI. `api/app.py` is pure
Python too; it only serves what `scripts/` and `ingest/` already computed
and validated. Retailer-facing copy in `scripts/recommend.py` comes from
fixed Python string templates, not generated language.
