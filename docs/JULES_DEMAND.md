> **Still current (2026-08-01)** — except TASK 74's auth section, which is superseded by the no-auth POC decision; the v2 plan must amend TASK 74 before it is submitted to the runner. See docs/PLAN_V2_PROMPT.md §B.

# JULES_DEMAND.md — Demand dashboard + picks series (TASKs 69–76)

*Task series for Jules covering Track A (demand service, TASKs 69–75) and
Track B's one backend task (picks endpoint, TASK 76) from
`docs/IMPLEMENTATION_PLAN.md` §2. Continues the numbering from
`docs/JULES_BACKEND.md` (01–52) and `docs/JULES_BACKEND_V2.md` (53–68) so
state files and commit history never collide. Submitted by
`python tools/jules_runner.py --tasks docs/JULES_DEMAND.md
--state tools/.jules_runner_state_demand.json --branch
jules-demand-integration`. Every task is atomic, offline-testable, and
independently committable. No code in this file — specs only.*

**Precondition (done in Terminal A before the runner starts, see
`docs/EXECUTION_PROMPTS.md` §3):** the `demand/` scaffold, its JSON Schemas,
`demand/data/schema.sql`, `demand/_config/seed_keywords.json`, and
`demand/tests/conftest.py` exist on `jules-demand-integration` (branched
from `main`).

Tracker (runner ticks nothing here — check
`tools/.jules_runner_state_demand.json` and `SHARED_CONTRACT.md` flags):

| Phase | Tasks | Contract flag |
|-------|-------|---------------|
| D1 — ingest + signals | 69, 70, 71, 72 | DEMAND_INGEST_READY |
| D2 — recommendations + API | 73, 74, 75 | DEMAND_API_READY |
| D3 — consumer picks | 76 | PICKS_READY |

## 1. MASTER CONTEXT BLOCK (prepend to every Jules task)

```
Repo: Aarrushh/reachout. Two backend roots: reachout/ (existing v1+v2, do
NOT break) and demand/ (NEW demand-dashboard service — your workspace for
TASKs 69-75). Full plan: docs/IMPLEMENTATION_PLAN.md (read §2 task table and
§3 data contracts before coding).

demand/ — what already exists (do NOT rewrite it):
demand/
├── CLAUDE.md, CONTEXT.md       ICM layer docs — read first, follow them.
├── _config/seed_keywords.json  curated Madrid retail seed keywords.
├── shared/schemas/             trend_snapshot.schema.json,
│                               demand_signal.schema.json,
│                               recommendation.schema.json,
│                               recommendations_response.schema.json.
│                               All additionalProperties:false. DO NOT MODIFY.
├── data/schema.sql             Postgres schema `demand` DDL. DO NOT MODIFY.
├── ingest/                     TASKs 69-71 build trends_client.py,
│                               keywords.py, snapshot_store.py here.
├── scripts/                    TASKs 72,73,75 build compute_signals.py,
│                               recommend.py, run_ingest.py here.
├── api/                        TASK 74 builds app.py here.
└── tests/                      conftest.py (sys.path setup) + fixtures/.

THE ONE RULE (from reachout/CLAUDE.md, binding here too): anything exact —
math, thresholds, rankings, DB writes — is pure Python. No AI calls
anywhere in demand/. Retailer-facing copy is template-generated.

HARD RULES for every task in this series:
1. Your VM has NO .env and NO API keys. Supabase, Google Trends, and the
   trendspy package's network paths are UNREACHABLE. All tests run fully
   offline: inject fake Supabase clients (copy the chainable-fake pattern
   from reachout/tests/fake_supa.py) and load canned trends payloads from
   demand/tests/fixtures/. Never make a network call in tests. Any import
   of the trendspy package must be lazy (inside the provider class) so the
   test suite imports cleanly without it installed.
2. Run the demand suite before finishing:
   cd demand && python -m pytest tests/ -q — fully green.
   TASK 76 only: also cd reachout && python -m pytest tests/ -q
   (REACHOUT_OFFLINE=1) — fully green including all v1+v2 tests.
3. Do not modify demand/shared/schemas/, demand/data/schema.sql,
   reachout/data/schema.sql, or anything in frontend/. Do not add
   dependencies beyond trendspy (runtime-only, lazy import). Endpoints are
   async (async def).
4. Every payload crossing a module boundary is validated against its schema
   in demand/shared/schemas/ (jsonschema is already a repo dependency)
   before the next module trusts it.
5. SHARED_CONTRACT.md (repo root) holds the flags DEMAND_INGEST_READY,
   DEMAND_API_READY, PICKS_READY. Only the designated task in each phase
   flips its flag, only after its whole phase is green.
6. Work ONLY the single task you were given. Small diff, one concern.
   Follow demand/CONTEXT.md stage routing; load only what contracts name.
```

## 2. PHASE D1 — ingest + signals (TASKs 69–72)

**TASK 69 — TrendsProvider protocol + trendspy implementation.**
New file `demand/ingest/trends_client.py`: a `TrendsProvider` Protocol with
`interest_over_time(keywords: list[str], geo: str, timeframe: str)` and
`interest_by_region(keyword: str, geo: str)` returning plain dicts shaped
like `trend_snapshot.schema.json`'s `series` / `region_breakdown` fields,
plus a `TrendspyProvider` implementation (lazy `import trendspy` inside the
class; batched keyword requests; exponential backoff on HTTP 429; geo
default `ES-MD`). Also a `FixtureProvider` that replays JSON files — used by
tests and by every later task. Commit 2–3 realistic canned payloads under
`demand/tests/fixtures/trends/`. New `demand/tests/test_trends_client.py`:
FixtureProvider round-trips match the schema; TrendspyProvider translates a
monkeypatched trendspy response object into schema-valid dicts; backoff
retries on a stubbed 429 then succeeds; provider selection helper
`get_provider(name)` returns Trendspy for "trendspy", Fixture for "fixture",
raises on unknown. No network.

**TASK 70 — Keyword-universe builder.**
New file `demand/ingest/keywords.py`: `build_universe(supa_client) ->
list[str]` = distinct non-empty `products.category` values (via the injected
client) UNION the seed list from `demand/_config/seed_keywords.json`,
case-insensitively deduped, deterministically sorted, capped at 100 with the
seed list winning ties. Pure Python. New `demand/tests/test_keywords.py`
with a fake client: dedupe across sources, ordering stable across runs, cap
respected, empty-category rows skipped, missing seed file raises a clear
error.

**TASK 71 — Snapshot store (validate + idempotent upsert).**
New file `demand/ingest/snapshot_store.py`: `store_snapshots(rows,
supa_client)` validates every row against `trend_snapshot.schema.json`
(reject the whole batch on first failure with a precise error naming the
keyword and JSON pointer), then upserts into `demand.trend_snapshots` on the
natural key (keyword, geo, timeframe, capture date) so re-ingesting a window
updates rather than duplicates. New `demand/tests/test_snapshot_store.py`
with a chainable fake client (start a `demand/tests/fake_supa.py` modeled on
`reachout/tests/fake_supa.py`, covering table/upsert/select/eq/execute):
valid batch upserted with the right on-conflict key; schema-invalid row
rejects batch and writes nothing; second identical batch performs upsert not
insert.

**TASK 72 — compute_signals.py + tick DEMAND_INGEST_READY.**
New file `demand/scripts/compute_signals.py`: pure-Python derivation of
`demand.demand_signals` rows from snapshots. Per keyword/window: windowed
`interest_avg`; `delta_pct` vs prior window; `direction` = rising if
delta_pct >= +15, falling if <= -15, else flat; dense `rank` by interest_avg
within the window; `confidence` exactly per docs/IMPLEMENTATION_PLAN.md
§3.3 — high: >=8 weeks of data AND interest_avg >= 20 AND direction stable
across the last 3 windows; medium: >=4 weeks AND interest_avg >= 10; low:
everything else including any series with provider gaps. Every output row
validates against `demand_signal.schema.json`. Golden-file tests in
`demand/tests/test_compute_signals.py`: fixture snapshots in →
byte-for-byte expected signal rows out (commit the expected JSON), plus
edge cases (short series → low; gap → low; boundary deltas ±15 exactly).
Only after 69–71 are merged and the whole demand suite is green: flip
`# [ ] DEMAND_INGEST_READY` to `[x]` in SHARED_CONTRACT.md and tick the
Phase D1 line in STATUS.md with a one-line note (test counts).

## 3. PHASE D2 — recommendations + API (TASKs 73–75)

**TASK 73 — recommend.py (signals × store composition, template copy).**
New file `demand/scripts/recommend.py`: `build_recommendations(signals,
supa_client) -> list[dict]` joining rising/falling signals against
`public.stores` / `public.products` composition (which stores stock products
in the signal's mapped category). Output rows match
`recommendation.schema.json`: headline and body from fixed Python string
templates (Spanish, e.g. "Sube el interés por {category} en Madrid"),
`action` in {stock_up, feature_in_window, watch} chosen by fixed rules
(rising+high/medium → stock_up; rising+low → watch; falling → watch;
feature_in_window when direction rising AND the store already has >=3
in-stock matching products), `confidence` copied verbatim from the signal —
never recomputed, never AI — and `caveat` set to the canonical string from
IMPLEMENTATION_PLAN.md §3.3. Tests in `demand/tests/test_recommend.py` with
fake client + fixture signals: action rules table-driven; every emitted row
schema-validates; a row missing caveat is impossible (assert validation
would fail); stores with zero matching products get no row.

**TASK 74 — demand API app (auth'd, schema-validated, 502 pattern).**
New file `demand/api/app.py`: FastAPI app exposing
`GET /demand/api/health`, `GET /demand/api/trends`,
`GET /demand/api/signals?window=&direction=`,
`GET /demand/api/recommendations?store_id=`. Auth: a `Depends` that reads
`Authorization: Bearer <jwt>`, verifies it as a Supabase Auth JWT
(signature check via SUPABASE_JWT_SECRET env; structure only — no network),
resolves the caller's store via `demand.retailers`, and 403s a store_id
mismatch; health is unauthenticated. Every response body validates against
its schema in demand/shared/schemas/ before return (recommendations use
`recommendations_response.schema.json`). Supabase/dep failures → clean 502
with detail (the reachout TASK 58/66 pattern), never a raw 500. CORS:
localhost:5173 + *.netlify.app, GET only. Tests in
`demand/tests/test_api.py` with TestClient, fake client, and a
test-signed JWT: 200 shapes; missing/garbage token → 401; store mismatch →
403; fake raising → 502; health needs no token.

**TASK 75 — run_ingest.py batch entrypoint + tick DEMAND_API_READY.**
New file `demand/scripts/run_ingest.py`: single entrypoint chaining
keywords → provider capture → store_snapshots → compute_signals →
build_recommendations → write, with `--dry-run` (print counts, write
nothing), `--provider fixture|trendspy` (default from env
DEMAND_TRENDS_PROVIDER, fixture in tests), structured one-line-per-stage
logging, and idempotent re-runs (safe to run twice for the same window).
Optional scheduling: when `DEMAND_INGEST_CRON=1`, demand/api/app.py's
lifespan starts an APScheduler daily job calling the same chain (the
REACHOUT_SIM lifespan pattern). Tests in `demand/tests/test_run_ingest.py`:
full chain over FixtureProvider + fake client lands schema-valid rows in
all three tables; --dry-run writes nothing; double-run row counts stable;
lifespan starts no scheduler without the env flag. Only after 73–74 merged
and the demand suite green: flip DEMAND_API_READY in SHARED_CONTRACT.md and
tick Phase D2 in STATUS.md with a one-line note.

## 4. PHASE D3 — consumer picks (TASK 76)

**TASK 76 — GET /api/picks (deterministic, schema-first) + tick PICKS_READY.**
In the reachout/ backend (NOT demand/). First add
`reachout/shared/schemas/picks_response.schema.json`:
`{picks: Product[], generated_by: const "deterministic"}`,
additionalProperties:false, Product mirroring SHARED_CONTRACT.md. Then a new
router file `reachout/api/picks.py` implementing
`GET /api/picks?neighbourhood=&limit=` (limit 1–50, default 12): pure-Python
ranking over the injected Supabase client's products+stores — in-stock only,
score = product-store blended rating weighted by review presence,
category-diverse round-robin (no two consecutive picks share a category
while alternatives exist), stable tiebreak by id; neighbourhood filter
accent-insensitive via `api.madrid.match_barrio`. Mount in
`api/server.py` with ONE line (`app.include_router(...)`) — change nothing
else in server.py. Response validates against the new schema. Supabase
failure → 502. Tests in `reachout/tests/test_api_picks.py` using the
existing `fake_supa` fixture: ranking order deterministic across runs;
category diversity property; out-of-stock excluded; neighbourhood filter
asserted on the fake; limit bounds → 422; 502 path. Run BOTH suites green
(hard rule 2). Then flip PICKS_READY in SHARED_CONTRACT.md and tick Phase
D3 in STATUS.md with a one-line note.
