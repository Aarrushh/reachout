# CONTEXT.md  (Layer 1: Where do I go?)

This routes the demand chain: ingest -> signals -> recommend -> api. The
chain order below is the read/write order. Every file this table names is
**PLANNED** — M1 (this scaffold) creates only the folders, the layer docs,
the seed keyword list, and the test helpers. It creates zero `.py` chain
files. If a Jules master-context block or any other doc claims one of
these files already exists, trust this table, not that doc — this file is
kept honest on purpose (see "Build status" below).

## Chain (Madrid demand service)

| Step | File | Task | Status | Reads | Writes |
|------|------|------|--------|-------|--------|
| 1 | `ingest/keywords.py` | TASK 70 | PLANNED | `public.products.category` (via injected Supabase client) union `_config/seed_keywords.json` | in-memory keyword universe (`list[str]`) |
| 2 | `ingest/trends_client.py` | TASK 69 | PLANNED | Google Trends (via `trendspy`, lazy-imported) or canned payloads in `tests/fixtures/trends/` | raw capture dicts shaped like `trend_snapshot.schema.json`'s `series` / `region_breakdown` |
| 3 | `ingest/snapshot_store.py` | TASK 71 | PLANNED | step 2's capture dicts, validated against `shared/schemas/trend_snapshot.schema.json` | `demand.trend_snapshots` (idempotent upsert on keyword/geo/timeframe/date) |
| 4 | `scripts/compute_signals.py` | TASK 72 | PLANNED | `demand.trend_snapshots` | `demand.demand_signals`, validated against `shared/schemas/demand_signal.schema.json` |
| 5 | `scripts/recommend.py` | TASK 73 | PLANNED | `demand.demand_signals` + `public.stores` / `public.products` composition | `demand.recommendations`, validated against `shared/schemas/recommendation.schema.json` |
| 6 | `api/app.py` | TASK 74 (amended, no-auth) / TASK 77 | PLANNED | `demand.trend_snapshots`, `demand.demand_signals`, `demand.recommendations` | `GET /demand/api/health`, `/trends`, `/signals`, `/recommendations` — the `/recommendations` body validates against `shared/schemas/recommendations_response.schema.json` |
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

**What exists today (M1):**

- `CLAUDE.md`, `CONTEXT.md` — this pair, Layer 0/1.
- `_config/seed_keywords.json` — 30-50 curated Madrid retail search terms
  (Spanish), the static half of TASK 70's keyword union.
- `ingest/`, `scripts/`, `api/` — empty Python packages (`__init__.py`
  only; no chain files yet).
- `shared/schemas/` — empty directory (`.gitkeep`); the four schemas named
  in the chain table above (`trend_snapshot`, `demand_signal`,
  `recommendation`, `recommendations_response`) do not exist yet — M2
  writes them, and once written they are DO-NOT-MODIFY for every later
  task.
- `data/` — empty directory (`.gitkeep`); `data/schema.sql` (the Postgres
  `demand` schema DDL) does not exist yet — M2 writes it.
- `tests/conftest.py` — sys.path setup so `demand/` modules import cleanly
  under pytest, plus a `fake_supa` fixture.
- `tests/fake_supa.py` — chainable fake Supabase client, modelled on
  `reachout/tests/fake_supa.py`.
- `tests/fixtures/` — empty directory (`.gitkeep`); TASK 69 commits the
  first canned trends payloads under `tests/fixtures/trends/`.

**What is PLANNED (not yet created, do not assume it exists):** every file
in the "File" column of the chain table above, plus the four JSON Schemas
and `data/schema.sql` (both M2).

## Module kinds

Nothing in `demand/` is agentic — see `CLAUDE.md`'s one rule. `ingest/` and
`scripts/` are pure Python: trend math, thresholds, rankings, and database
writes are never guessed and never touch an AI. `api/app.py` is pure
Python too; it only serves what `scripts/` and `ingest/` already computed
and validated. Retailer-facing copy in `scripts/recommend.py` comes from
fixed Python string templates, not generated language.
