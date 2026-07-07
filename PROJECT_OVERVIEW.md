# ReachOut — Project Overview & Debugging Guide

*The single orientation document for the whole repository. Last updated 2026-07-08, after the UI phase (`feature/ui-madrid`) merged into `main`.*

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
by real point-of-sale feeds; everything else stays the same.

## 2. The one design rule

**Work that must be exact is pure Python; AI only touches language.**
Locations, distances, stock, matching, ranking, GeoJSON, DB writes live in
`reachout/scripts/` where no AI is allowed. Understanding a vague query and
phrasing results are "agentic" stages — and even their output is validated
against JSON Schemas (`reachout/shared/schemas/`) before anything trusts it.
The schemas are the hallucination gate: `additionalProperties: false`
everywhere, so no invented field can pass.

## 3. System at a glance

```
Browser (React SPA, localhost:5173)
  │  GET /api/search            → ranked shop list   (ranked_shops.schema.json)
  │  GET /api/search.geojson    → matched shops map  (map_geojson.schema.json)
  │  GET /api/shops.geojson     → ALL shops (network layer, cached 1h)
  ▼                                                  (shops_geojson.schema.json)
FastAPI (reachout/api/server.py, localhost:8000, CORS *)
  │  per request: throwaway output dir → run_pipeline.run()
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

## 4. Repository map

```
reachout/  (repo root)
├── PROJECT_OVERVIEW.md      ← you are here
├── .claude/skills/verify/   how to launch + drive the app for verification
├── docs/superpowers/        UI design spec + implementation plan (history)
├── frontend/                React SPA (see frontend/README.md)
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
    ├── tests/               pytest suite (93 tests, offline via fixtures)
    ├── data/                live SQLite DB, event log, caches (see §3)
    ├── run_pipeline.py      orchestrator
    └── demo.py              live demo with stock moving in the background
```

**Navigation rule (ICM):** read `reachout/CLAUDE.md` → `CONTEXT.md` → the one
stage `CONTEXT.md` you need. Load nothing else.

## 5. Complete tech stack

### Backend
| Part | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | stdlib-first |
| API | FastAPI + uvicorn | thin read-only wrapper; CORS `*` (GET only) |
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

## 6. Data contracts

Every structured artifact has a schema in `reachout/shared/schemas/`:

| Schema | Produced by | Consumed by |
|---|---|---|
| `search_intent.schema.json` | stage 01 | stage 02/03 |
| `geo_shops.schema.json` | stage 02 | stage 03 |
| `stock_matches.schema.json` | stage 03 | stage 04 |
| `ranked_shops.schema.json` | stage 04 | `/api/search` → frontend cards |
| `map_geojson.schema.json` | stage 05 | `/api/search.geojson` → map matched layer |
| `shops_geojson.schema.json` | `/api/shops.geojson` (validated at request time) | map network layer + entry backdrop |
| `shop_record` / `inventory_record` | ingest/seeder | DB rows |

**The iron rule:** if the frontend needs a field that isn't in a schema —
schema first, backend second, `npm run gen-types` third. Never invent
frontend-side. ("Pinged" is deliberately NOT data: every matched shop is
pinged by definition; the frontend's `usePingSequence` only staggers the
animation.)

## 7. Running everything

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
cd reachout/tests && python -m pytest          # 93 backend tests
cd frontend && npm run build && npm test       # typecheck+build, 14 tests
```

`REACHOUT_OFFLINE=1` uses the committed OSM cache + gazetteer (no network).
`--use-llm` + `ANTHROPIC_API_KEY` switches stages 01/04 to an LLM.

## 8. Debugging guide (symptom → where to look)

| Symptom | Look at |
|---|---|
| Search 422 / "La búsqueda ha fallado" | Query unparseable: stage 01 (`agent/query_parser.py`). The API surfaces `PipelineError` as 422 with detail. |
| Search 500 | Read the uvicorn traceback; each request runs the full pipeline in a temp dir — reproduce with `run_pipeline.py` + same args to get per-stage `output/` files. |
| Pipeline halts mid-run | The failing stage's `output/error.json` + the schema it violated. Validation messages come from `scripts/validate.py`. |
| Empty results that look wrong | Inventory is synthetic and Spanish-named (`data/sku_catalog.json`) — "usb c charger" matches nothing; "cargador" does. Check matching in `scripts/search_engine.py`. |
| Stock numbers changing between searches | Expected: `scripts/inventory_simulator.py` writes live; watch `tail -f data/events.jsonl`. |
| Wrong/missing shops | `data/reachout.db` shops table (from `scripts/osm_ingest.py` + `data/osm_cache/`). `--refresh` re-pulls from Overpass. |
| Barrio not resolving | `scripts/nominatim.py` → offline fallback `data/gazetteer_madrid.json`. The frontend autocomplete list is generated from the same file (`npm run gen-barrios`). |
| Frontend shows CORS errors | `reachout/api/server.py` CORSMiddleware (GET-only, `*`). |
| Frontend types don't match API | Regenerate: `npm run gen-types`. Types are slaved to schemas — never edit `src/types/`. |
| Map pins wrong color / theme drift | `frontend/src/styles/tokens.css` — MapPanel reads the same CSS custom properties at map init (`cssVar()`); there is no second palette. |
| Ping animation issues | `frontend/src/hooks/usePingSequence.ts` (unit-tested with fake timers) + the ping/selection effect in `MapPanel.tsx`. Reduced-motion pings everything instantly. |
| Card ↔ pin selection broken | `selectedShopId` in `routes/results.tsx`; feature ids are per-result-set indexes with a `shop_id → index` map in `MapPanel.tsx` (`withIndexIds`). |
| Verifying a change end-to-end | `.claude/skills/verify/SKILL.md` — launch recipe + Playwright drive script patterns + known gotchas. |
| Shop pings on disk | `data/notifications/<shop_id>/` — one JSON per ping, written by `scripts/ping.py` (stage 03). |

## 9. Invariants worth knowing before changing anything

1. **Schema-first.** No response field exists unless a schema defines it.
2. **No AI in `scripts/`.** Facts (stock, distance, coordinates) are computed, never generated.
3. **URL is the state of record** in the frontend; the only client state is presentation (selection, ping timing).
4. **Generated files** (`frontend/src/types/`, `frontend/src/data/barrios.ts`) are regenerated, never edited.
5. **Coordinates are `[lng, lat]`** in every GeoJSON (RFC 7946); the schemas' per-position bounds make a swap fail validation.
6. **Error copy is verbatim** from the API's status envelope — the UI never invents narrative around facts.
7. **All numbers render in IBM Plex Mono**; all UI copy lives in `i18n/strings.ts`, both languages.

## 10. Document index

- `reachout/README.md` — backend intro; `reachout/TRYME.md` — 5-minute hands-on; `reachout/TUTORIAL.md` — guided walkthrough
- `reachout/CLAUDE.md` / `CONTEXT.md` / `stages/*/CONTEXT.md` — the ICM contract chain
- `reachout/_config/` — product.md, constraints.md, tech_stack.md
- `frontend/README.md` — frontend architecture + commands
- `docs/superpowers/specs/2026-07-07-reachout-ui-design.md` — approved UI design spec
- `docs/superpowers/plans/2026-07-07-reachout-ui.md` — the executed implementation plan
- `.claude/skills/verify/SKILL.md` — end-to-end verification recipe
