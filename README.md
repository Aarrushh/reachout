# ReachOut

A hyperlocal demand router — the anti-Amazon. A shopper types what they need
("algo para el dolor de cabeza", "cargador usb c"); every shop within a radius
that has it in live stock is pinged instantly; the shopper gets a ranked,
factual list — who has it, how far, at what price — beside a live map of the
city's inventory network. You don't browse a store: you say what you need and
nearby stores answer.

Madrid is the test market. Shop identities are **real** (an OpenStreetMap
snapshot, ~3,300 shops, committed to the repo); stock is **synthetic**, seeded
deterministically per shop and flagged `synthetic: true`.

The app has two faces, both served by the same frontend:

| | URL | What it is |
|---|---|---|
| Consumer | `http://localhost:5173/` | Search box, ranked shop results, live map |
| Retail | `http://localhost:5173/?mode=retail` | Demand dashboard for shopkeepers — search-demand trends, picks, recommendations |

## Layout

```
reachout/     shopper backend: FastAPI API + the 5-stage search pipeline + SQLite
demand/       demand backend: separate FastAPI service for the retail dashboard
frontend/     React 19 + Vite SPA (both faces)
docs/         plans, decisions, codebase overview
```

Deeper reading: `PROJECT_OVERVIEW.md` (orientation + debugging guide),
`docs/CODEBASE_OVERVIEW.md` (how the shipped code actually works).

## Running it locally

Prerequisites: Python 3.10+ (3.12 used here), Node 20+.

**One-time setup**

```bash
python3 -m venv .venv
./.venv/bin/pip install -r reachout/requirements.txt -r demand/requirements.txt
cd frontend && npm install && cd ..
```

No credentials are needed for local use. Supabase and Gemini keys only matter
for the v2 Supabase search path and live demand ingest; copy
`reachout/.env.example` to `reachout/.env` if you want those.

**Three processes, three fixed ports.** Run each in its own terminal, from the
repo root:

```bash
# 1. demand API — :8001 (fixture mode, no Supabase needed)
DEMAND_ANALYTICS_SOURCE=fixture ./.venv/bin/uvicorn demand.api.app:app --port 8001

# 2. shopper API — :8000
cd reachout && PYTHONPATH=.. REACHOUT_OFFLINE=1 REACHOUT_SIM=1 \
  ../.venv/bin/uvicorn api.server:app --port 8000

# 3. frontend — :5173
cd frontend && npm run dev
```

Then open **http://localhost:5173/** — that hostname exactly. Both APIs restrict
CORS to `http://localhost:5173`; `127.0.0.1` is blocked, and so is the
production `vite preview` on :4173.

The first search bootstraps `reachout/data/reachout.db` from the committed OSM
cache (~3,300 shops, ~60k synthetic inventory rows, 24 barrios). It takes a
minute and only happens once — the DB file is per-environment and never
committed.

What the environment variables do:

- `REACHOUT_OFFLINE=1` — use the committed OSM cache instead of calling Overpass/Nominatim.
- `REACHOUT_SIM=1` — run the inventory simulator, so stock moves and the SSE stream has something to push. **Requires the repo root on `PYTHONPATH`** as shown above; without it every HTTP endpoint still returns 200 while the 2-second simulator tick raises `ModuleNotFoundError: No module named 'reachout'` forever, visible only in the log.
- `DEMAND_ANALYTICS_SOURCE=fixture` — serve canned analytics. The dashboard shows a "practice data" banner when it does. Any value other than `live` (including a typo) falls back to fixtures silently.

**Other ways to run it**

```bash
# one-shot pipeline, no servers
cd reachout && REACHOUT_OFFLINE=1 ../.venv/bin/python run_pipeline.py \
  "algo para el dolor de cabeza" --near "Malasaña"

# live demo with moving stock
cd reachout && REACHOUT_OFFLINE=1 ../.venv/bin/python demo.py
```

## Tests

```bash
./.venv/bin/python -m pytest reachout/tests demand/tests   # from the repo root
cd frontend && npm run build && npm test                   # typecheck + build + vitest
```

Run the Python suites from the repo root — they import `reachout.*` and
`demand.*`, which only resolve with the root on `sys.path`.

## Deploys

`render.yaml` (backend, Render) and `netlify.toml` (frontend, Netlify) are
committed. The frontend reads `VITE_API_BASE` and `VITE_DEMAND_API_BASE`,
defaulting to the two localhost ports above.
