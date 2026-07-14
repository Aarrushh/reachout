---
name: verify
description: Build/launch/drive recipe for verifying ReachOut end to end (FastAPI backend + Vite frontend + headless Edge via Playwright).
---

# Verifying ReachOut

## Launch

```bash
# Backend (from reachout/, repo root on PYTHONPATH — event_bus imports
# reachout.scripts.*). REACHOUT_OFFLINE=1 avoids live Overpass/Nominatim;
# REACHOUT_SIM=1 runs the inventory simulator (feeds /api/inventory/stream).
REACHOUT_OFFLINE=1 REACHOUT_SIM=1 PYTHONPATH=.. python -m uvicorn api.server:app --port 8000

# Frontend (from frontend/)
npm run dev        # serves http://localhost:5173
```

Health probes: `curl http://localhost:8000/api/health`, `curl -o /dev/null -w "%{http_code}" http://localhost:5173/`.

## Drive (browser)

Playwright with the system Edge channel — no browser download needed:

```js
const { chromium } = require("playwright"); // npm i playwright in a scratch dir
const browser = await chromium.launch({ channel: "msedge", headless: true });
```

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
- Backend tests: `cd reachout/tests && python -m pytest` (93 tests).
- Frontend: `npm run build` (tsc+vite) and `npx vitest run`.
