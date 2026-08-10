# IMPLEMENTATION_PLAN.md — v1 plan, reduced to §3

*The v1 "overnight" plan is superseded for routing and task lists by
`docs/IMPLEMENTATION_PLAN_V2.md`. Only §3 survives here, because it is still
cited as source text for the demand data contracts:
`frontend/src/types/RecommendationsResponse.d.ts` cites §3.3, and §3.4 holds
the deferred authentication design — the reversal path for decision D2 (no
auth in the POC).*

*The JSON Schemas in `demand/shared/schemas/` are authoritative. Where this
text and a schema disagree, the schema wins.*

---

## 3. Data contracts — Demand Dashboard

Schema-first: these JSON Schemas land in `demand/shared/schemas/` (task A2)
**before** any code that produces or consumes the shapes. All are
`"additionalProperties": false`. The SQL lives in `demand/data/schema.sql`
as idempotent DDL creating the **`demand`** Postgres schema — zero tables
added to `public`, zero changes to `reachout/data/schema.sql`.

### 3.1 `demand.trend_snapshots` — raw captures (`trend_snapshot.schema.json`)

| column | type | notes |
|--------|------|-------|
| id | uuid pk | |
| keyword | text not null | as sent to the provider |
| geo | text not null | `ES-MD` (Madrid community scope) |
| timeframe | text not null | e.g. `today 3-m` |
| provider | text not null | `trendspy` now; paid adapter later (D1) |
| captured_at | timestamptz not null | |
| series | jsonb not null | `[{date, value 0–100}]`, schema-validated before insert |
| region_breakdown | jsonb | interest-by-region payload if available |

Unique on `(keyword, geo, timeframe, captured_at::date)` → idempotent
re-ingestion. Retention: raw snapshots older than 180 days are pruned
(GDPR-hygiene by habit, though no personal data is present).

### 3.2 `demand.demand_signals` — derived, pure-Python (`demand_signal.schema.json`)

| column | type | notes |
|--------|------|-------|
| id | uuid pk | |
| keyword | text not null | |
| category | text | mapped product category, nullable |
| geo | text not null | `ES-MD` — **honesty note:** Trends does not resolve to barrio; barrio attribution happens only in recommendations via store composition, and the schema has no barrio column here so nothing can pretend otherwise |
| window_start / window_end | date not null | |
| interest_avg | numeric not null | 0–100 |
| delta_pct | numeric not null | vs prior window |
| direction | text not null | enum `rising` / `falling` / `flat` (fixed thresholds: ±15%) |
| rank | int not null | within window |
| confidence | text not null | enum `low` / `medium` / `high` (rules in 3.3) |
| snapshot_ids | uuid[] not null | provenance |
| computed_at | timestamptz not null | |

### 3.3 `demand.recommendations` — retailer-facing (`recommendation.schema.json`, response envelope `recommendations_response.schema.json`)

| column | type | notes |
|--------|------|-------|
| id | uuid pk | |
| store_id | uuid not null | references `public.stores(id)` |
| signal_id | uuid not null | references `demand.demand_signals(id)` |
| headline | text not null | template-generated, pure Python — **no AI** |
| body | text not null | template-generated |
| action | text not null | enum `stock_up` / `feature_in_window` / `watch` |
| confidence | text not null | **required** enum `low`/`medium`/`high` |
| caveat | text not null | **required, non-empty** — the response schema makes it impossible to serve a recommendation without one; canonical text: "Basado en interés de búsqueda en Madrid, no en compras reales." |
| created_at | timestamptz not null | |

**Confidence rules (deterministic, in `compute_signals.py`):**
`high` = ≥8 weeks of data, `interest_avg ≥ 20`, and direction stable across
the last 3 windows; `medium` = ≥4 weeks and `interest_avg ≥ 10`;
`low` = everything else (including any series with provider gaps). Never
model-assigned.

### 3.4 `demand.retailers` — auth mapping

| column | type | notes |
|--------|------|-------|
| auth_user_id | uuid pk | Supabase Auth user |
| store_id | uuid not null | references `public.stores(id)` |
| created_at | timestamptz not null | |

RLS: retailers select only `recommendations` rows where `store_id` matches
their mapping; `trend_snapshots` and `demand_signals` are service-role only.
This is the first RLS in the project (public schema runs secret-key-only,
per `schema.sql`) — it applies to the `demand` schema only.

Consumer-side addition (Track B): `picks_response.schema.json` in
`reachout/shared/schemas/` — `{picks: Product[], generated_by: "deterministic"}`,
reusing the existing Product shape from `SHARED_CONTRACT.md`.

---

*Footnote added 2026-08-10 when this file was reduced: the consumer-side
addition above shipped. `picks_response.schema.json` exists in
`reachout/shared/schemas/` and is the authoritative Product shape — the
`SHARED_CONTRACT.md` reference on the line above predates it. §3.4 has NOT
shipped; `demand.retailers` does not exist and RLS is still disabled
(`demand/data/schema.sql:120-125`).*
