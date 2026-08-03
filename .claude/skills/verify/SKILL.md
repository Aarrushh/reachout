---
name: verify
description: Build/launch/drive recipe for verifying ReachOut end to end (FastAPI backend + Vite frontend + headless Edge via Playwright).
---

# Verifying ReachOut

## Launch

Use the repo venv — the system `python3` is 3.9 and the code needs 3.10+
syntax (`str | None`), so `python3 -m uvicorn` dies on import.

```bash
# Shopper API (from reachout/, repo root on PYTHONPATH — event_bus imports
# reachout.scripts.*). REACHOUT_OFFLINE=1 avoids live Overpass/Nominatim;
# REACHOUT_SIM=1 runs the inventory simulator (feeds /api/inventory/stream).
REACHOUT_OFFLINE=1 REACHOUT_SIM=1 PYTHONPATH=.. ../.venv/bin/python -m uvicorn api.server:app --port 8000

# Demand service (from the repo root) — retail mode's analytics
.venv/bin/python -m uvicorn demand.api.app:app --port 8001

# Frontend (from frontend/). PREVIEW, not dev, when the PWA matters: the
# service worker is skipped under import.meta.env.DEV, so `npm run dev` can
# never exercise U5. Both APIs' CORS allows :5173 only, so pin the port.
npm run build && npx vite preview --port 5173 --strictPort
```

Health probes: `curl http://localhost:8000/api/health`,
`curl http://localhost:8001/demand/api/health`,
`curl -o /dev/null -w "%{http_code}" http://localhost:5173/`.

**First run on a fresh machine:** `reachout/data/reachout.db` may exist as a
0-table file, which `_ensure_db_ready` does not repair (it only calls
`init_db` when the file is ABSENT), so every search 500s with
`no such table: shops`. Bootstrap once, offline, from the committed cache:

```bash
cd reachout && PYTHONPATH=.. ../.venv/bin/python -c "
from scripts import db, osm_ingest, region_seeder
db.init_db(db.DB_PATH); conn = db.connect(db.DB_PATH)
osm_ingest.ingest(conn=conn, offline=True)
region_seeder.seed_regions(conn); region_seeder.assign_shops(conn)
conn.commit(); conn.close()"
```

Expect 3328 shops and 24 regions.

## Drive (browser)

Playwright with the system Edge channel — no browser download needed:

```js
const { chromium } = require("playwright"); // npm i playwright in a scratch dir
const browser = await chromium.launch({ channel: "chrome", headless: true });
```

Edge is **not** installed on this machine (`/Applications` has Chrome only),
so `channel: "msedge"` fails with "Chromium distribution not found". Chrome
is the working channel here; both are Chromium, so selectors behave the same.

Useful selectors: `.entry-net circle` (entry backdrop dots), `.barrio-combobox li`
(autocomplete), `.search-input button` (submit), `.shop-card` / `.shop-card.pinged`
(results + ping stagger), `.results-meta`, `.results-panel.state` (empty/error),
`.cta` (widen/retry), `.maplibregl-popup`, `.radius-slider input`, `.lang-toggle`.

## Flows worth driving

- Entry → pick barrio "mala" → Malasaña (accent-insensitive) → query
  "algo para el dolor de cabeza" → 60+ pharmacy results, ping stagger visible.
- "cargador" near Chueca → electronics results. "usb c charger" → EMPTY state
  (synthetic inventory is Spanish-named) — not a bug.
- "???" → 422 → error state; must be exactly 1 request per query (no 4xx retries).
- Cold-load a full `/results?...&lang=en` URL in a fresh page — must reproduce.

## Gotchas

- Wait ~3s after results for the ping sequence + map fitBounds to settle
  before screenshots.
- The DB has ~3300 shops; the entry backdrop renders one SVG circle each.
- Shopper tests: `cd reachout && PYTHONPATH=.. ../.venv/bin/python -m pytest tests -q`
  (**273**). Running from `reachout/tests/` fails collection with
  `No module named 'reachout'` — the repo root must be on the path.
- Demand tests: `.venv/bin/python -m pytest demand/tests -q` (**158**).
- Frontend: `npm run build` (tsc+vite) and `npx vitest run` (**79**).
- There is no single repo-root pytest command: `reachout/tests/test_api.py`
  and `demand/tests/test_api.py` collide on the module name `tests.test_api`.

## Retail mode (U0–U6)

`?mode=retail` on any route. Selectors: `.chat-panel--pane` (the chat, which
must have NO `.chat-scrim` and no `dialog` role), `.retail-askai__button`
(present and `disabled`), `.chart-panel` (×3), `.chart-panel__chip`,
`.chart-panel__caveat`, `.retail-dash__practice` (the fixture-data banner).

Every chip and caveat must be `isVisible()` **without hovering**, at 1280px
and at 375px. `document.querySelectorAll('.retail-split [title]')` must be
empty — a `title` is a hover-only label and a phone cannot reveal it.
