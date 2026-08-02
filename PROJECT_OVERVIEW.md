# ReachOut — Project Overview & Debugging Guide

*The single orientation document for the whole repository. Shipped-system
sections (§4–§10) last updated 2026-07-08, after the UI phase
(`feature/ui-madrid`) merged into `main`. §1–§3 updated 2026-08-01 with the
aim, the approved plan, and the method the build runs on.*

## 1. What ReachOut is

A hyperlocal demand router — the anti-Amazon. A shopper in Madrid types what
they need ("algo para el dolor de cabeza", "cargador usb c"); shops within a
radius that have it in live stock are pinged instantly; the shopper sees a
ranked, factual list — who has it, how far, at what price — beside a live map
of the city's inventory network. You don't browse a store: you say what you
need and nearby stores answer.

Madrid is the test market. Shop identities are **real** (OpenStreetMap
snapshot, ~3,300 shops); stock is **synthetic**, seeded deterministically per
shop and flagged `synthetic: true`. In production the simulator is replaced
by real point-of-sale feeds; everything else stays the same. To support filtering
and scoped Server-Sent Events (SSE) views, shops are assigned to physical
**regions** (barrios) during the ingest process.

**The aim.** What ships today serves one side of a two-sided market: the
shopper. The other side — the shops — is what the platform actually needs, and
it is blocked by a cold start. Live inventory, AI shop-chat and delivery all
wait on merchants integrating; merchants don't integrate with a platform that
has no shoppers. So the next phase builds the **supply side first**, using the
only data that requires zero merchant participation: public search demand for
Madrid. A retailer gets something useful on day one with nothing to install —
that is what buys the first real inventory feed, and everything else unlocks
behind it.

## 2. What is being added (planned, not yet built)

**Plan in force:** `docs/IMPLEMENTATION_PLAN_V2.md` (decisions D1–D10 +
sub-decisions S1–S6, the M/T/U/V/H task list, data contracts, risks, out of
scope). **Live board:** `docs/TRACKER.md` — what's done, what's next, who
owns what; read it before either plan. The v1 `docs/IMPLEMENTATION_PLAN.md`
and its run-book `docs/EXECUTION_PROMPTS.md` are **superseded for routing** —
do not follow them as instructions — but v1's §3 remains the source text for
the demand data contracts and its §3.4 the preserved authentication reversal
path. The table below is v1's original track shape, historical — for the
current M/T/U/V/H lanes in flight, see `docs/IMPLEMENTATION_PLAN_V2.md` §2:

| Track | What | How |
|---|---|---|
| **A — Demand Solutions** | New `demand/` service: Google Trends batch ingest → snapshots → signals → per-store recommendations → its own FastAPI app; plus the retailer dashboard UI. Every surfaced number carries a confidence label and an always-visible caveat. | Jules TASK 69–75 (`docs/JULES_DEMAND.md`), Stitch D1–D5 (`docs/STITCH_DASHBOARD.md`) |
| **B — Consumer UI** | Blinkit/Amazon-style mobile-first shopping surface over the existing Supabase products/stores, plus a deterministic `GET /api/picks`. Installable PWA — "phone" means responsive web, not a native app. | Jules TASK 76, Stitch C1–C8 (`docs/STITCH_CONSUMER.md`) |
| **C — Gated** | Two memos, no code: delivery partner-vs-build (Spain/EU rider-classification exposure), and the preconditions that un-gate AI shop-chat. | Written directly |

**Why this order.** The dashboard needs nothing from any shop, so it can ship
before a single merchant signs up → a signed-up merchant is what makes live
inventory sync possible → only with live inventory does AI shop-chat become
answerable rather than a hallucination surface, and only with real order flow
is delivery a decision worth costing. Chat stays **gated** (retrieval-then-
template over a fresh stock read, schema-gated — never open-ended generation
about stock). Delivery stays a **decision**, not a build.

Nothing here changes the shipped pipeline below: `demand` is a separate
Postgres schema, `demand/` is a separate service, and `reachout/data/schema.sql`
is untouched.

## 3. The one design rule

**Work that must be exact is pure Python; AI only touches language.**
Locations, distances, stock, matching, ranking, GeoJSON, DB writes live in
`reachout/scripts/` where no AI is allowed. Understanding a vague query and
phrasing results are "agentic" stages — and even their output is validated
against JSON Schemas (`reachout/shared/schemas/`) before anything trusts it.
The schemas are the hallucination gate: `additionalProperties: false`
everywhere, so no invented field can pass.

## 4. Method: ICM layers + graph engineering

Two conventions carry the rule above from principle into structure. Both are
load-bearing — they are why an agent session can change one thing without
reading ninety files, and why the build can run unattended.

### 4.1 ICM — the folder structure *is* the architecture

Context is layered, and each layer is opened only if the job needs it:

| Layer | File(s) | Holds |
|---|---|---|
| L0 | `CLAUDE.md` | workspace identity, the rules — read first |
| L1 | `CONTEXT.md` | routing table: which stage does what |
| L2 | `stages/NN/CONTEXT.md` + `prompt.md` | that one stage's contract and acceptance tests |
| L3 | `_config/` (product, constraints, tech_stack) + `shared/schemas/` | cross-cutting truth |
| L4 | `stages/NN/output/` | working files — outputs, never inputs to a reader |

**Navigation rule:** read `CLAUDE.md` → `CONTEXT.md` → the one stage
`CONTEXT.md` you need. Load nothing else.

The planned `demand/` service repeats this exact shape as a **second ICM
workspace** — its own `CLAUDE.md`, `CONTEXT.md`, `_config/`,
`shared/schemas/`, `ingest/`, `scripts/`, `api/`, `tests/`, its own `demand`
Postgres schema, its own FastAPI app. That is what "own service boundary"
means, and it is why the demand work is *not* added into
`reachout/api/server.py`: a service whose context you can load in four files
stays changeable; one bolted into an existing tangle does not.

### 4.2 Graph engineering — tasks are a dependency graph, not a checklist

Work is decomposed into a DAG and executed by whatever is unblocked:

- **Nodes** — tasks. Jules TASK 69–76 (`docs/JULES_DEMAND.md`), Stitch prompts
  D1–D5 and C1–C8, and the manual scaffold / auth / live-verify steps that
  need keys.
- **Edges** — data contracts, not prose. A JSON Schema in `shared/schemas/`,
  or a phase flag in `SHARED_CONTRACT.md`
  (`DEMAND_INGEST_READY` → `DEMAND_API_READY` → `PICKS_READY`, the same
  convention as the shipped `PHASE_*_READY` flags). A node consumes fixtures
  shaped by its input schema — never another node's live output — so nodes are
  developed and tested independently.
- **Parallelism is derived, not scheduled.** Anything with no unmet edge runs
  now; that is why the build runs in three terminals, and why Track B waits
  only on Track A's *branch*, not its completion. `AGENTS.md`
  ("Dependency graph — who can run in parallel") is the precedent: the
  original ten workstreams were built this way.
- **State lives on the edges, not in a conversation** — runner state JSON,
  `STATUS.md` ticks, contract flags. Any node can fail and be retried without
  replaying the graph, which is what makes an unattended overnight run
  restartable.
- **The runtime is a graph too.** The shipped pipeline is 01→05 with schema
  validation on every edge and a hard halt on any failure; the demand chain
  (trends → snapshots → signals → recommendations → API) is built the same
  way. Same discipline at build time and at run time.

## 5. System at a glance

```
Browser (React SPA, localhost:5173)
  │  GET /api/search            → ranked shop list   (ranked_shops.schema.json)
  │  GET /api/search.geojson    → matched shops map  (map_geojson.schema.json)
  │  GET /api/shops.geojson     → ALL shops (network layer, cached 1h)
  ▼                                                  (shops_geojson.schema.json)
FastAPI (reachout/api/server.py, localhost:8000, CORS: localhost:5173 + Netlify)
  │  per request: throwaway output dir → run_pipeline.run()
  │
  │  [AsyncIOScheduler] ─(ticks)→ Simulator ─(events)→ [Event Bus] ─(SSE)→ /api/inventory/stream
  ▼
Pipeline (reachout/run_pipeline.py) — halts on any non-"ok" or schema failure
  01 parse-query      Agentic    free text → intent.json (rule-based default,
  02 geo-resolve      Hardcoded  intent + Overpass/Nominatim → shops in radius
  03 match-and-ping   Hardcoded  intent + shops + SQLite → matches + ping files
  04 format-results   Agentic    matches → ranked_shops.json      LLM opt-in)
  05 map-render       Hardcoded  ranked shops → shops.geojson
  ▼
Data (reachout/data/): reachout.db (SQLite WAL: shops + inventory),
  events.jsonl (append-only log), notifications/ (per-shop ping inboxes),
  osm_cache/ (committed Madrid snapshot), gazetteer_madrid.json (barrio
  centroids), sku_catalog.json (synthetic item templates)
```

### Endpoints

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/api/search` | `ranked_shops.json` / `search_page.json` | Search pipeline results (paginated) |
| GET | `/api/search.geojson` | `map_geojson.json` | Matched shops as a GeoJSON FeatureCollection |
| GET | `/api/shops.geojson` | `shops_geojson.json` | All known shops (network layer), cached |
| GET | `/api/inventory` | `inventory_response.json` | Paginated inventory (can be filtered by region/in_stock) |
| GET | `/api/inventory/stream` | Server-Sent Events (SSE) | Stream of `stock_event`s (optional region filter) |
| GET | `/api/regions` | `regions_response.json` | List of known regions with shop counts |
| GET | `/api/health` | `health_response.json` | API health, stats, and simulator state |

**Two search backends, one mount point.** `reachout/api/server.py` also
mounts a second, independent search implementation from backend v2:
`POST /api/search` (pgvector + Gemini rerank over the Supabase
products/stores schema, `reachout/api/search.py`) plus `POST /api/chat`.
Same path, different HTTP method, no clash with the `GET /api/search` above.
Decision **S6** (`docs/IMPLEMENTATION_PLAN_V2.md`) keeps the consumer UI on
the pipeline `GET /api/search` — the Supabase path stays mounted and
available but unused by the frontend.

## 6. Repository map

```
reachout/  (repo root)
├── PROJECT_OVERVIEW.md      ← you are here
├── AGENTS.md                the original 10 workstreams + their dependency graph
├── SHARED_CONTRACT.md       phase flags between backend and frontend agents
├── STATUS.md                live build state — ticked by every agent session
├── plan.md                  superseded tick-scheduler micro-plan, shipped;
│                            scheduled for deletion by H1 (see docs/TRACKER.md BLOAT)
├── debug_tick.py, debug_tick2.py,
│   test_tick2.py, test_tick_debug.py
│                            one-off debug scratch from the tick work, shipped;
│                            scheduled for deletion by H1 (see docs/TRACKER.md BLOAT)
├── netlify.toml             frontend deploy config (base frontend/, publish dist/)
├── render.yaml              backend deploy config (uvicorn on Render, free plan)
├── .claude/skills/verify/   how to launch + drive the app for verification
├── docs/
│   ├── TRACKER.md               the live board — read first, updated every session
│   ├── IMPLEMENTATION_PLAN_V2.md the plan in force: decisions D1–D10 + S1–S6,
│   │                              M/T/U/V/H task list, data contracts, risks
│   ├── PLAN_V2_PROMPT.md        the prompt that produced Implementation Plan v2
│   ├── IMPLEMENTATION_PLAN.md   v1 plan — superseded for routing, §3/§3.4 still
│   │                             source text (see §2 above)
│   ├── EXECUTION_PROMPTS.md     v1 run-book — superseded (see docs/TRACKER.md)
│   ├── JULES_DEMAND.md          Jules TASK 69–76 specs
│   ├── STITCH_DASHBOARD.md      dashboard prompt series D1–D5
│   ├── STITCH_CONSUMER.md       consumer prompt series C1–C8
│   ├── STITCH_FRONTEND.md       v1 UI redesign prompt series, executed + merged
│   │                             (design record, history)
│   ├── FINAL_SUMMARY.md         compiled summary of the 52-task backend run +
│   │                             12-prompt Stitch frontend redesign (history)
│   ├── frontend_contract_note.md  fields added to the schemas for the frontend
│   │                             (history)
│   ├── JULES_BACKEND*.md        earlier Jules task files (history)
│   └── superpowers/             UI design spec + implementation plan (history)
├── tools/jules_runner.py    submits task files to Jules, patches + merges
├── frontend/                React SPA (see frontend/README.md)
│   ├── CLAUDE.md            Layer 0: workspace identity + rules
│   ├── CONTEXT.md           Layer 1: what exists today vs. planned (task U0 on)
│   ├── scripts/             gen-types.ts, gen-barrios.ts (code generators)
│   └── src/
│       ├── routes/          search.tsx (entry), results.tsx (split view)
│       ├── components/      TopBar, ResultsPanel, ShopCard, MapPanel (all
│       │                    MapLibre code lives in MapPanel), CSS
│       ├── hooks/           useLang (URL param), usePingSequence (staggered
│       │                    ping presentation state)
│       ├── map/             map-layers.ts — pure GeoJSON builders, unit-tested
│       ├── api/client.ts    typed fetchers + ApiError
│       ├── i18n/strings.ts  ALL UI copy, ES/EN
│       ├── styles/tokens.css design tokens — the only place colors live
│       ├── types/           GENERATED from backend schemas (gen-types)
│       └── data/barrios.ts  GENERATED from the gazetteer (gen-barrios)
└── reachout/                Python backend workspace (ICM layout)
    ├── CLAUDE.md            Layer 0: workspace identity + rules. Read first.
    ├── CONTEXT.md           Layer 1: stage routing table
    ├── TRYME.md / TUTORIAL.md / README.md   hands-on guides
    ├── _config/             product.md, constraints.md, tech_stack.md
    ├── shared/schemas/      the data contracts (single source of truth)
    ├── stages/01…05/        one folder per pipeline stage: CONTEXT.md is the
    │                        stage's contract; output/ is its working files
    ├── scripts/             pure Python core: db, geo, overpass, nominatim,
    │                        search_engine, ping, validate, inventory_*
    ├── agent/               optional LLM adapter + rule-based fallback
    ├── api/server.py        FastAPI wrapper (thin; no business logic)
    ├── tests/               pytest suite (~228 test functions, offline via
    │                        fixtures; see §9 for how that count is sourced)
    ├── data/                live SQLite DB, event log, caches (see §5)
    ├── data/schema.sql      Supabase/Postgres DDL for the public schema
    ├── run_pipeline.py      orchestrator
    ├── demo.py              live demo with stock moving in the background
    └── test_tick_debug.py   stray debug scratch at the workspace root (breaks
                             the layer rule); scheduled for deletion by H1

demand/  (second ICM workspace, own service boundary — scaffolded by M1/M2;
          Lane D. The `.py` chain files below are still PLANNED, built by
          Jules TASK 69–77, not yet run):
├── CLAUDE.md / CONTEXT.md  Layers 0–1, same convention as reachout/
├── _config/                seed_keywords.json — the curated Madrid keyword list
├── shared/schemas/         5 schemas authored before any code: trend_snapshot,
│                           demand_signal, recommendation, recommendations_response,
│                           analytics_response
├── data/schema.sql         idempotent DDL for the `demand` Postgres schema —
│                           written, not yet applied to Supabase (task M3, founder)
├── ingest/                 PLANNED: trends_client.py, keywords.py, snapshot_store.py
│                           (TASK 69–71); only `__init__.py` exists today
├── scripts/                PLANNED: compute_signals.py, recommend.py, run_ingest.py
│                           (TASK 72/73/75); only `__init__.py` exists today
├── api/                    PLANNED: app.py, own FastAPI app, NOT mounted into
│                           reachout/api (TASK 74/77); only `__init__.py` exists today
└── tests/                  conftest.py, fake_supa.py, fixtures/ scaffolded by M1;
                            test files PLANNED alongside their chain file
```

**Navigation rule (ICM):** read `reachout/CLAUDE.md` → `CONTEXT.md` → the one
stage `CONTEXT.md` you need. Load nothing else. See §4.1 for the full layer
table; `demand/` follows the same rule with its own L0/L1.

## 7. Complete tech stack

### Backend
| Part | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | stdlib-first |
| API | FastAPI + uvicorn | thin read-only wrapper; CORS restricted to `localhost:5173`/`127.0.0.1:5173` + a Netlify origin regex, `GET`+`POST` (`reachout/api/server.py` lines 77–83); mounts two independent search implementations — see §5 |
| Store | SQLite, WAL mode | `data/reachout.db`; concurrent sim writes + search reads |
| Validation | `jsonschema` (Draft-07, tolerant multipleOf) | `scripts/validate.py` |
| HTTP client | `requests` | Overpass / Nominatim / ORS |
| Optional AI | `anthropic` SDK, opt-in `--use-llm` | stages 01/04 only; invalid LLM output is discarded |
| Tests | pytest | run offline: `REACHOUT_OFFLINE=1` |

### Frontend
| Part | Choice | Notes |
|---|---|---|
| Framework | React 19 + Vite 6 + TypeScript 5.7 | |
| Routing | react-router-dom 7 | **URL = state of record** (`q`, `near`/`lat`+`lng`, `radius`, `lang`) |
| Server state | TanStack Query 5 | cache key = URL params; no store; 4xx never retried |
| Map | MapLibre GL JS 4 | Carto Dark Matter tiles — free, keyless |
| Fonts | @fontsource: Space Grotesk (display), IBM Plex Mono (all numbers), Inter (UI) | self-hosted |
| Styling | plain CSS + custom-property tokens | no UI library; map reads the same tokens |
| Codegen | json-schema-to-typescript (`gen-types`), gen-barrios | generated files are never hand-edited |
| Tests | vitest + @testing-library/react (jsdom), 14 tests | hooks + pure logic |
| E2E verification | Playwright, system Edge channel | see `.claude/skills/verify/SKILL.md` |

### External data (all free / keyless)
| Source | Used for | Fallback |
|---|---|---|
| Overpass API | real Madrid shops | committed `data/osm_cache/madrid_shops.json` |
| Nominatim | barrio name → coordinates | `data/gazetteer_madrid.json` |
| OpenRouteService (optional key) | walking distance | haversine (`scripts/geo.py`) |
| Carto Dark Matter | map tiles | — (frontend only) |

## 8. Data contracts

Every structured artifact has a schema in `reachout/shared/schemas/`:

| Schema | Produced by | Consumed by |
|---|---|---|
| `search_intent.schema.json` | stage 01 | stage 02/03 |
| `geo_shops.schema.json` | stage 02 | stage 03 |
| `stock_matches.schema.json` | stage 03 | stage 04 |
| `ranked_shops.schema.json` | stage 04 | `/api/search` → frontend cards |
| `map_geojson.schema.json` | stage 05 | `/api/search.geojson` → map matched layer |
| `shops_geojson.schema.json` | `/api/shops.geojson` (validated at request time) | map network layer + entry backdrop |
| `shop_record.schema.json` | `osm_ingest.py` | DB rows |
| `inventory_record.schema.json` | `inventory_seeder.py` / `inventory_simulator.py` | DB rows |
| `inventory_response.schema.json` | `/api/inventory` | frontend / API clients |
| `health_response.schema.json` | `/api/health` | frontend / monitoring |
| `regions_response.schema.json` | `/api/regions` | frontend / API clients |
| `region_record.schema.json` | `db_seeder` / `gazetteer` | SQLite DB / API responses |
| `search_page.schema.json` | `/api/search` | frontend search results |
| `sku_catalog.schema.json` | static data (`sku_catalog.json`) | inventory seeder / search engine |
| `stock_event.schema.json` | `inventory_simulator.py` / event bus | `/api/events` SSE stream |

**The iron rule:** if the frontend needs a field that isn't in a schema —
schema first, backend second, `npm run gen-types` third. Never invent
frontend-side. ("Pinged" is deliberately NOT data: every matched shop is
pinged by definition; the frontend's `usePingSequence` only staggers the
animation.)

## 9. Running everything

```bash
# Backend API (from reachout/api/):
REACHOUT_OFFLINE=1 python -m uvicorn server:app --port 8000
# Frontend (from frontend/):
npm run dev                      # → http://localhost:5173
# One-shot pipeline, no servers:
REACHOUT_OFFLINE=1 python run_pipeline.py "algo para el dolor de cabeza" --near "Malasaña"
# Live demo with moving stock:
python demo.py
# Tests:
cd reachout/tests && python -m pytest          # ~228 backend tests
cd frontend && npm run build && npm test       # typecheck+build, 14 tests
```

`REACHOUT_OFFLINE=1` uses the committed OSM cache + gazetteer (no network).
`--use-llm` + `ANTHROPIC_API_KEY` switches stages 01/04 to an LLM.

**On the test count:** this doc previously claimed a stale count of 93 for
the backend suite. `grep -rc "def test_" reachout/tests/ demand/tests/` currently counts 228 test
functions (approximate: it undercounts parametrized cases pytest expands at
collection time and misses any Jules-added suites not yet merged).
`STATUS.md`'s PHASE 2 entry separately records 240 passing at that point in
the build; the two numbers come from different methods and different
moments, both trustworthy for "many more than 93," neither exact right now.

## 10. Debugging guide (symptom → where to look)

| Symptom | Look at |
|---|---|
| Search 422 / "La búsqueda ha fallado" | Query unparseable: stage 01 (`agent/query_parser.py`). The API surfaces `PipelineError` as 422 with detail. |
| Search 500 | Read the uvicorn traceback; each request runs the full pipeline in a temp dir — reproduce with `run_pipeline.py` + same args to get per-stage `output/` files. |
| Pipeline halts mid-run | The failing stage's `output/error.json` + the schema it violated. Validation messages come from `scripts/validate.py`. |
| Empty results that look wrong | Inventory is synthetic and Spanish-named (`data/sku_catalog.json`) — "usb c charger" matches nothing; "cargador" does. Check matching in `scripts/search_engine.py`. |
| Stock numbers changing between searches | Expected: `scripts/inventory_simulator.py` writes live; watch `tail -f data/events.jsonl`. |
| Wrong/missing shops | `data/reachout.db` shops table (from `scripts/osm_ingest.py` + `data/osm_cache/`). `--refresh` re-pulls from Overpass. |
| Barrio not resolving | `scripts/nominatim.py` → offline fallback `data/gazetteer_madrid.json`. The frontend autocomplete list is generated from the same file (`npm run gen-barrios`). |
| Frontend shows CORS errors | `reachout/api/server.py` CORSMiddleware (localhost:5173 + Netlify origins only, GET+POST). |
| SSE not streaming | `REACHOUT_SIM` environment variable not set to `1` (which starts the simulator/scheduler), or an issue in `api/event_bus.py`. |
| Region empty | The `region_seeder` assignment radius may be too small or missing shops for that specific region. |
| Frontend types don't match API | Regenerate: `npm run gen-types`. Types are slaved to schemas — never edit `src/types/`. |
| Map pins wrong color / theme drift | `frontend/src/styles/tokens.css` — MapPanel reads the same CSS custom properties at map init (`cssVar()`); there is no second palette. |
| Ping animation issues | `frontend/src/hooks/usePingSequence.ts` (unit-tested with fake timers) + the ping/selection effect in `MapPanel.tsx`. Reduced-motion pings everything instantly. |
| Card ↔ pin selection broken | `selectedShopId` in `routes/results.tsx`; feature ids are per-result-set indexes with a `shop_id → index` map in `MapPanel.tsx` (`withIndexIds`). |
| Verifying a change end-to-end | `.claude/skills/verify/SKILL.md` — launch recipe + Playwright drive script patterns + known gotchas. |
| Shop pings on disk | `data/notifications/<shop_id>/` — one JSON per ping, written by `scripts/ping.py` (stage 03). |

## 11. Invariants worth knowing before changing anything

1. **Schema-first.** No response field exists unless a schema defines it.
2. **No AI in `scripts/`.** Facts (stock, distance, coordinates) are computed, never generated.
3. **URL is the state of record** in the frontend; the only client state is presentation (selection, ping timing).
4. **Generated files** (`frontend/src/types/`, `frontend/src/data/barrios.ts`) are regenerated, never edited.
5. **Coordinates are `[lng, lat]`** in every GeoJSON (RFC 7946); the schemas' per-position bounds make a swap fail validation.
6. **Error copy is verbatim** from the API's status envelope — the UI never invents narrative around facts.
7. **All numbers render in IBM Plex Mono**; all UI copy lives in `i18n/strings.ts`, both languages.

## 12. Document index

**The plan (next phase):**

- `docs/TRACKER.md` — **read this first.** The live board: what's done, what's
  next, who owns what, updated in the same commit as the work it tracks
- `docs/IMPLEMENTATION_PLAN_V2.md` — the plan in force: §0 decision table
  D1–D10 + sub-decisions S1–S6 (each reversible), §2 M/T/U/V/H task list,
  §5 data contracts, §6 risk/mitigation, §7 out of scope
- `docs/PLAN_V2_PROMPT.md` — the prompt that produced Implementation Plan v2
- `docs/IMPLEMENTATION_PLAN.md` — the v1 plan: superseded for routing, but
  its §3 remains the source text for the demand data contracts and its §3.4
  the preserved authentication reversal path (see §2 above)
- `docs/EXECUTION_PROMPTS.md` — the v1 run-book: superseded, see
  `docs/TRACKER.md`'s "SKIP THIS"
- `docs/JULES_DEMAND.md` — Jules TASK 69–76 specs (fed to
  `tools/jules_runner.py`; every task offline-testable, Jules VMs hold no keys)
- `docs/STITCH_DASHBOARD.md` — retailer dashboard prompt series D1–D5
- `docs/STITCH_CONSUMER.md` — consumer PWA prompt series C1–C8

**The shipped system:**

- `reachout/README.md` — backend intro; `reachout/TRYME.md` — 5-minute hands-on; `reachout/TUTORIAL.md` — guided walkthrough
- `reachout/CLAUDE.md` / `CONTEXT.md` / `stages/*/CONTEXT.md` — the ICM contract chain
- `reachout/_config/` — product.md, constraints.md, tech_stack.md
- `frontend/README.md` — frontend architecture + commands; `frontend/CLAUDE.md` /
  `CONTEXT.md` — the frontend's own ICM L0/L1, same convention as `reachout/`
- `docs/superpowers/specs/2026-07-07-reachout-ui-design.md` — approved UI design spec
- `docs/superpowers/plans/2026-07-07-reachout-ui.md` — the executed implementation plan
- `.claude/skills/verify/SKILL.md` — end-to-end verification recipe
- `AGENTS.md` — the original 10 parallel workstreams and their dependency graph
  (§"Dependency graph"); the precedent for §4.2
- `SHARED_CONTRACT.md` — phase flags; `STATUS.md` — live build state
