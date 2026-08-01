-- ReachOut demand service — Supabase schema (idempotent: safe to run
-- repeatedly). Apply once in the Supabase SQL editor (M3, founder-only —
-- the project's key cannot run DDL). Creates the `demand` Postgres schema
-- only: zero tables added to `public`, zero changes to
-- reachout/data/schema.sql. No `demand.retailers` table and no RLS/GRANT
-- of any kind (D2 override, v2 no-auth decision) — store_id is a plain
-- filter parameter, not an authorization subject.

create schema if not exists demand;

-- ---------------------------------------------------------------------------
-- demand.trend_snapshots: raw Google Trends captures (IMPLEMENTATION_PLAN.md
-- 3.1 / IMPLEMENTATION_PLAN_V2.md 5.1). Produced by TASK 69/71, consumed by
-- TASK 72. series/region_breakdown are schema-validated (trend_snapshot
-- .schema.json) before insert.
-- ---------------------------------------------------------------------------
create table if not exists demand.trend_snapshots (
    id               uuid primary key default gen_random_uuid(),
    keyword          text not null,
    geo              text not null,
    timeframe        text not null,
    provider         text not null,
    captured_at      timestamptz not null,
    series           jsonb not null,
    region_breakdown jsonb
);

-- Unique on (keyword, geo, timeframe, captured_at::date) -> idempotent
-- re-ingestion: re-running the same day's capture upserts, never duplicates.
create unique index if not exists trend_snapshots_dedupe_idx
    on demand.trend_snapshots (keyword, geo, timeframe, (captured_at::date));

create index if not exists trend_snapshots_keyword_idx on demand.trend_snapshots (keyword);
create index if not exists trend_snapshots_captured_at_idx on demand.trend_snapshots (captured_at);

-- ---------------------------------------------------------------------------
-- demand.demand_signals: derived, pure-Python rising/falling/flat signals
-- with a deterministic confidence label (IMPLEMENTATION_PLAN.md 3.2 /
-- IMPLEMENTATION_PLAN_V2.md 5.2 / 5.6). Produced by TASK 72, consumed by
-- TASK 73/77 and GET /demand/api/signals. geo is ES-MD scope only: no
-- barrio column here, so nothing can pretend to resolve below it.
-- ---------------------------------------------------------------------------
create table if not exists demand.demand_signals (
    id            uuid primary key default gen_random_uuid(),
    keyword       text not null,
    category      text,
    geo           text not null,
    window_start  date not null,
    window_end    date not null,
    interest_avg  numeric not null,
    delta_pct     numeric not null,
    direction     text not null,
    rank          int not null,
    confidence    text not null,
    snapshot_ids  uuid[] not null,
    computed_at   timestamptz not null
);

create index if not exists demand_signals_keyword_idx on demand.demand_signals (keyword);
create index if not exists demand_signals_window_idx  on demand.demand_signals (window_start, window_end);
create index if not exists demand_signals_confidence_idx on demand.demand_signals (confidence);

-- ---------------------------------------------------------------------------
-- demand.recommendations: retailer-facing, template-generated (no AI)
-- (IMPLEMENTATION_PLAN.md 3.3 / IMPLEMENTATION_PLAN_V2.md 5.3). Produced by
-- TASK 73, consumed by GET /demand/api/recommendations. caveat is required
-- and non-empty at the schema layer (recommendation.schema.json) so a
-- caveat-less row cannot be served even if one were ever inserted here.
-- ---------------------------------------------------------------------------
create table if not exists demand.recommendations (
    id         uuid primary key default gen_random_uuid(),
    store_id   uuid not null references public.stores (id),
    signal_id  uuid not null references demand.demand_signals (id),
    headline   text not null,
    body       text not null,
    action     text not null,
    confidence text not null,
    caveat     text not null,
    created_at timestamptz not null default now()
);

create index if not exists recommendations_store_id_idx  on demand.recommendations (store_id);
create index if not exists recommendations_signal_id_idx on demand.recommendations (signal_id);

-- Dev mode: RLS stays OFF, same as public.stores/public.products (plan
-- decision, D2 override removes the v1 retailers/RLS block entirely). The
-- API talks to Supabase with the secret key only.
alter table demand.trend_snapshots disable row level security;
alter table demand.demand_signals  disable row level security;
alter table demand.recommendations disable row level security;
