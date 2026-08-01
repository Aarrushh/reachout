> **SUPERSEDED by docs/PLAN_V2_PROMPT.md (2026-08-01)** — the product shape changed (one shell + retail-mode toggle, no POC auth); the D1–D8 decision-table pattern carries forward, the task routing does not.

# ReachOut — Overnight Implementation Plan

*Authored 2026-07-30 by the planning session on branch
`claude/reachout-implementation-plan-69xp7o`. This is the single plan the
execution loop (Jules API + Google Stitch, orchestrated from Claude Code)
follows unattended. It follows the Chairman's build order and this repo's
one rule: exactness is pure Python; AI touches only language, and only
behind `additionalProperties: false` schemas.*

---

## 0. Decisions taken in lieu of answers (READ FIRST)

The founder was asked the eight section-3 questions before planning began;
no answers arrived (session unattended). Rather than stall the overnight
run, each question is resolved below with a **default that is explicitly
reversible in the morning**. Every default was chosen to be the
lowest-spend, least-locked-in option. To override one, edit this section
and re-run only the tasks tagged with that decision's ID.

| ID | Question | Default taken | Why / how to reverse |
|----|----------|---------------|----------------------|
| D1 | Trends data source | **Free scraping (trendspy/HTTP) behind a `TrendsProvider` interface.** $0 spend. | Proves the pipeline end-to-end tonight. The interface (Task A3) means a paid provider (Bright Data / DataForSEO / SerpApi) is a new adapter class + config change, no downstream edits. Reverse: implement a second adapter, flip `DEMAND_TRENDS_PROVIDER`. |
| D2 | Dashboard hosting + auth | **Same repo, new top-level `demand/` service (own FastAPI app, own uvicorn process), own Postgres schema `demand` in the existing Supabase project. Retailer auth via Supabase Auth email magic-link, JWT-verified in the demand API.** | Honors the "own service boundary" directive without new infra or a new repo's CI/Jules wiring. Reverse: `demand/` is self-contained by design — extracting it to its own repo later is a folder move. |
| D3 | "Phone" meaning | **Responsive web + PWA (manifest, installable), single React codebase.** No native scaffold. | Pre-product-market-fit, one codebase, reuses the existing Vite/React/TanStack/MapLibre stack, zero app-store friction. A native Expo scaffold now would duplicate every UI surface for no validated demand. Reverse: nothing tonight forecloses a later Expo app — the API contracts are the boundary. |
| D4 | Semantic search model | **Keep `gemini-embedding-001` @ 768 dims.** | The products table is already embedded at 768 dims with an ivfflat index tuned to it; switching models invalidates every stored vector and the index for no measured cost/latency problem at this scale. Revisit only with real latency/cost data. |
| D5 | Jules usage & granularity | **Many small tasks (the proven 52-task pattern), submitted via `tools/jules_runner.py` with a new tasks file `docs/JULES_DEMAND.md`, state file `tools/.jules_runner_state_demand.json`, branch `jules-demand-integration`. Numbering continues at TASK 69.** Claude Code keeps schemas, SQL migrations, live-key verification, and merge review. | Matches existing tooling and the V2 constraint that Jules VMs have **no keys** — so every Jules task must be offline-testable (monkeypatched Supabase/HTTP). Big tasks failed less gracefully in the v1 run (TASK 37 hung). |
| D6 | Stitch usage & design direction | **Page-level prompt series (the `STITCH_FRONTEND.md` pattern: one master context block + numbered self-contained prompts).** Consumer UI carries over the existing Amazon-light design tokens and i18n/ShopCard conventions. The dashboard gets its own small token set (data-dense, neutral) but the same conventions (plain CSS tokens, no Tailwind, no component lib). | Page-level matched the successful 12-prompt run; component-level fragments context. |
| D7 | Delivery partner-vs-build | **Out of scope for the overnight build. One [MANUAL] research memo task only (C1), zero code.** | Chairman's directive: evaluate partner-vs-build before any matching-engine code, and Spain/EU courier classification law is real exposure. Layers 1–2 must prove themselves first. |
| D8 | Budget ceiling | **$0 in new paid API spend.** Allowed: free trendspy scraping, already-provisioned Gemini + Supabase keys at their existing usage pattern, Jules within existing quota, Stitch within existing access. Anything requiring a new paid signup or plan upgrade is blocked and gets logged as a skipped task instead. | Unattended spend with no stated ceiling defaults to zero. Raise it in the morning and re-run any skipped task. |

**Tooling caveat:** the plugin/skill names referenced below (`icm-architect`,
`Understand-Anything`, `superpowers`, `system-design`, `frontend`,
`caveman`, `mattpocock/skills`) must each be verified as actually wired into
the executing session (`ListPlugins`/`ListSkills`) before a task depends on
them. Where a plugin is absent, the task's fallback is written inline.

---

## 1. Scope summary

Tonight builds, in the Chairman's binding order: **(1) the Demand Solutions
dashboard first** — a retailer-facing analytics service fed by a pure-Python
Google Trends batch-ingestion job, living in its own `demand/` service
boundary with its own `demand` Postgres schema in the existing Supabase
instance, every surfaced recommendation carrying a schema-enforced
confidence + caveat label; **(2) in parallel, the consumer shopping UI** —
a Blinkit/Amazon-style responsive-web/PWA experience generated via Google
Stitch against the existing Supabase products/stores data, with semantic
search (existing `POST /api/search`) and a new deterministic
"picks for you" endpoint; **(3) nothing else** — AI shop-chat remains gated
behind live inventory sync (paper checklist only), and delivery/courier is
deferred to a partner-vs-build memo (paper only). Exactness stays pure
Python everywhere; AI output crosses a boundary only after validating
against an `additionalProperties: false` schema.

---

## 2. Task list

Tags: `[JULES]` = autonomous Jules session (offline-testable, no keys),
`[STITCH]` = Google Stitch prompt, `[MANUAL/CLAUDE CODE]` = done directly in
the orchestrating session. Dependencies are listed per task; tasks with the
same "wave" number can run concurrently.

### Track A — Demand Solutions dashboard (build first, ship first)

| # | Wave | Tag | Task | Depends on |
|---|------|-----|------|------------|
| A1 | 1 | [MANUAL/CLAUDE CODE] | Scaffold `demand/` service using icm-architect folder-as-architecture conventions (mirroring `reachout/`'s ICM/MWP layout: `CLAUDE.md`, `CONTEXT.md`, `_config/`, `shared/schemas/`, `ingest/`, `scripts/`, `api/`, `tests/`). If icm-architect isn't wired in, copy the layer structure from `reachout/CLAUDE.md` by hand. Run Understand-Anything (if wired) over `reachout/api/` first so no server.py entanglement leaks in. | — |
| A2 | 1 | [MANUAL/CLAUDE CODE] | Author the data contracts (section 3): four JSON Schemas in `demand/shared/schemas/` and `demand/data/schema.sql` (idempotent DDL for the `demand` Postgres schema, mirroring `reachout/data/schema.sql` style). Apply the DDL to Supabase from this session (Jules VMs have no keys). | A1 |
| A3 | 2 | [JULES] TASK 69 | `demand/ingest/trends_client.py`: `TrendsProvider` protocol + `TrendspyProvider` implementation (interest-over-time + interest-by-region, geo `ES-MD`, batched keywords, polite backoff). Offline tests with canned fixture payloads committed under `demand/tests/fixtures/`. **No network in tests.** | A2 |
| A4 | 2 | [JULES] TASK 70 | `demand/ingest/keywords.py`: keyword-universe builder — pure Python union of (a) distinct `products.category` values fetched via injected client and (b) a curated static Madrid-retail seed list committed at `demand/_config/seed_keywords.json`. Deterministic ordering, dedupe, cap. Tests use a fake client. | A2 |
| A5 | 2 | [JULES] TASK 71 | `demand/ingest/snapshot_store.py`: validate each raw capture against `trend_snapshot.schema.json`, then upsert into `demand.trend_snapshots` via injected Supabase client. Tests monkeypatch the client (reuse the `fake_supa.py` pattern from `reachout/tests/`). | A2 |
| A6 | 3 | [JULES] TASK 72 | `demand/scripts/compute_signals.py`: **pure Python, no AI** derivation of `demand.demand_signals` from snapshots — windowed interest average, week-over-week delta %, direction (rising/falling/flat via fixed thresholds), rank, and deterministic confidence labeling (rules in section 3.3). Golden-file tests: fixture snapshots in → exact expected signal rows out. | A3, A5 |
| A7 | 3 | [JULES] TASK 73 | `demand/scripts/recommend.py`: pure-Python join of demand signals × existing `stores`/`products` composition → per-store recommendation rows ("category X rising in Madrid; you stock N matching products") written to `demand.recommendations`. Every row carries `confidence` + `caveat` (schema-required). Tests with fake client + fixture signals. | A6 |
| A8 | 4 | [JULES] TASK 74 | `demand/api/app.py`: FastAPI app exposing `GET /demand/api/health`, `GET /demand/api/trends`, `GET /demand/api/signals`, `GET /demand/api/recommendations?store_id=`. Responses validated against the section-3 schemas before return. Auth: `Depends` that verifies a Supabase Auth JWT and resolves the caller's `store_id` via `demand.retailers`; monkeypatched in tests. Supabase failures → clean 502 (the TASK 58/66 pattern). | A2, A7 |
| A9 | 4 | [JULES] TASK 75 | `demand/scripts/run_ingest.py`: batch entrypoint (fetch keywords → capture snapshots → compute signals → recommend) with `--dry-run`, structured logging, and idempotent re-runs (re-ingesting a window updates, never duplicates). Plus optional APScheduler wiring gated on `DEMAND_INGEST_CRON=1` (the `REACHOUT_SIM` pattern). Offline tests over the full chain with fakes. | A6, A7 |
| A10 | 4 | [STITCH] prompts D1–D5 | Dashboard frontend at `frontend/src/routes/dashboard/` (own route section, own `dashboard.css` token set — data-dense neutral palette; reuse i18n and fetch-client conventions from the master context block). D1: magic-link login screen + auth session handling. D2: overview — trending categories in Madrid with sparkline tiles. D3: rising/falling movers list. D4: per-store recommendations with the **caveat label pattern** (confidence chip + always-visible "search-interest proxy, not purchases" caption — a schema-required field the UI must render, never suppress). D5: empty/loading/error states + responsive audit. | A8 (contract), B1 (types) |
| A11 | 5 | [MANUAL/CLAUDE CODE] | Retailer auth wiring in Supabase: enable email magic-link, create `demand.retailers` mappings for pilot stores, RLS policies on `demand.recommendations` (retailer sees only their store's rows; `trend_snapshots`/`demand_signals` are service-role only). Needs live keys → cannot be a Jules task. | A2, A8 |
| A12 | 5 | [MANUAL/CLAUDE CODE] | Live end-to-end verify (the only network-touching step): run `run_ingest.py` once for real, confirm rows in all three tables, drive the dashboard against live data with the repo's `verify` skill (Playwright). Log task counts + row counts to `STATUS.md`. | A9, A10, A11 |

### Track B — Consumer UI (parallel with Track A from wave 1)

| # | Wave | Tag | Task | Depends on |
|---|------|-----|------|------------|
| B1 | 1 | [MANUAL/CLAUDE CODE] | Clear the standing follow-up from `docs/FINAL_SUMMARY.md`: run `npm run gen-types` in `frontend/` against current schemas, confirm `stitch-frontend` work is fully merged, frontend builds green. Nothing in Track B's Stitch series starts from stale types. | — |
| B2 | 2 | [JULES] TASK 76 | `GET /api/picks?neighbourhood=&limit=`: deterministic "picks for you" — **pure Python** ranking over existing Supabase products/stores (in-stock only, rating-weighted, category-diverse round-robin, stable tiebreak by id). New `picks_response.schema.json` in `reachout/shared/schemas/` first (schema-first invariant). Mounted as a v2 router, NOT added to server.py's tangle beyond the mount line. Offline tests via `fake_supa`. | B1 |
| B3 | 2 | [STITCH] prompts C1–C6 | Consumer shopping experience, mobile-first, extending the existing `STITCH_FRONTEND.md` master context block and Amazon-light tokens. C1: mobile-first home (search-forward, barrio picker, category tiles). C2: category browse grid. C3: search results on `POST /api/search` with `interpreted_as` echo ("showing results for…"). C4: product detail (price, stock badge, store card, delivery-mins). C5: "picks for you" rail on `GET /api/picks`. C6: "visit/reserve at shop" CTA — **no checkout, no payments** (out of scope). | B1; C5 also needs B2 |
| B4 | 3 | [STITCH] prompts C7–C8 | PWA-ification: C7 — web app manifest, icons, theme color, install prompt, offline shell for static assets. C8 — responsive/touch audit pass across C1–C6 (the P11–P12 audit pattern). | B3 |
| B5 | 4 | [MANUAL/CLAUDE CODE] | End-to-end Playwright drive of the consumer flow (search → results → detail → picks) via the `verify` skill; fix-forward anything broken; log to `STATUS.md`. | B2, B3, B4 |

### Track C — Gated items (paper only, no build)

| # | Wave | Tag | Task | Depends on |
|---|------|-----|------|------------|
| C1 | any | [MANUAL/CLAUDE CODE] | `docs/DELIVERY_PARTNER_VS_BUILD.md`: research memo comparing partner APIs (Glovo-style, Mox-type white-label couriers) vs building courier ops — Spain/EU rider-classification exposure (Ley Rider), integration cost, unit economics at pilot volume. Recommendation + decision criteria. **No matching-engine code.** | — |
| C2 | any | [MANUAL/CLAUDE CODE] | `docs/SHOP_CHAT_GATE.md`: the preconditions checklist that un-gates AI shop-chat — live inventory sync in production, freshness SLA, and the binding design constraint: retrieval-then-template over a fresh stock read at request time, schema-gated (the stage-04 pattern), **never** open-ended generation about stock. No build tasks scheduled. | — |

**Execution order for the loop:** wave 1 (A1, A2, B1) in this session →
submit TASKs 69–75 (A3–A9) to `jules_runner.py --tasks docs/JULES_DEMAND.md
--state tools/.jules_runner_state_demand.json --branch
jules-demand-integration` and TASK 76 (B2) after B1 → Stitch series C1–C8
and D1–D5 as their dependencies land → A11, A12, B5 manual verification
last. C1/C2 fill idle time while Jules sessions poll.

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

## 4. Risks and mitigations

| Risk | Concrete mitigation (built tonight, not aspirational) |
|------|------------------------------------------------------|
| **Two-sided cold-start** — shops churn off inventory-sync obligations before consumer volume exists | The build order *is* the mitigation, made structural: the dashboard (Track A) delivers standalone retailer value from Google Trends data that requires **nothing** from the shop — no sync, no integration, no obligation. The consumer UI (Track B) runs entirely on the existing seeded/synthetic Supabase inventory, so no shop is on the hook during the pilot. Inventory sync is only ever requested *after* a retailer is an active dashboard user (that's why shop-chat is gated behind it, C2). Dashboard logins/opens per pilot store get logged in `STATUS.md` as the explicit go/no-go gate for the sync ask. |
| **GDPR — retailer-facing views re-identifying consumers** | Enforced by schema, not policy: the `demand` schema contains **no user-identifying columns at all** — nothing to leak. Tonight's signals come solely from Google Trends (already aggregate). If in-app search terms ever feed signals later, they enter only through `compute_signals.py` with a k-anonymity floor (suppress any term with <10 distinct sessions per window) — that threshold is written into the module tonight as a guarded, tested code path so the safe version exists before the feature does. Raw snapshot retention capped at 180 days. |
| **Trends-confidence trust risk** — search interest presented as purchase fact | Three layers: (1) `recommendation.schema.json` makes `confidence` and a non-empty `caveat` **required** — a caveat-less recommendation cannot validate, so it cannot be served; (2) confidence labels are assigned by deterministic pure-Python rules (3.3), never by a model; (3) Stitch prompt D4 specifies the caveat as an always-visible caption, not a tooltip, and B5/A12 verification checks it renders. |
| **Free-scrape fragility (D1 consequence)** — trendspy breaks or gets rate-limited mid-run | Provider interface (A3) isolates the blast radius; ingestion failures leave prior snapshots intact (idempotent upserts, A9); the run degrades to "stale data + timestamp shown in UI", never to fabricated data. Paid-adapter swap is a config change when D1 is revisited. |
| **Unattended autonomous execution** — Jules tasks drift or hang | Same controls that carried the 52-task run: small single-concern tasks, offline-testable with no keys, integration branch + state file, full-suite green gate per task, and the runner's reattach-on-restart behavior. Claude Code reviews merges; live keys touch only A11/A12. |

---

## 5. Out of scope for tonight (deliberate)

- **Delivery/courier system** — no matching-engine code of any kind; C1's
  partner-vs-build memo is the only deliverable (D7).
- **AI shop-chat build** — gated on live inventory sync; C2's precondition
  checklist only. The existing `POST /api/chat` prototype is not extended.
- **Live inventory sync with real shops** — precondition for chat, not
  buildable tonight; nothing depends on it.
- **Payments / checkout / cart** — the consumer CTA stops at
  "visit/reserve at shop" (B3-C6).
- **Native mobile app** — D3: responsive web + PWA only.
- **Paid data providers** — D1/D8: $0 ceiling; adapter interface exists,
  paid implementations do not.
- **Embedding-model migration** — D4: `gemini-embedding-001` stays.
- **Refactoring `server.py`** — the tangle is contained, not untangled,
  tonight; new demand code lives in `demand/`, and B2 adds only a router
  mount.
