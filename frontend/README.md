# ReachOut frontend

The full UI for ReachOut's Madrid MVP: an entry screen (barrio autocomplete +
geolocation + bilingual search) and a split-view results screen (ranked shop
cards left, MapLibre dark map right with a live "ping" animation). Design
spec: `../docs/superpowers/specs/2026-07-07-reachout-ui-design.md`.

## Framework

React 19 + Vite + TypeScript. MapLibre GL JS (keyless Carto Dark Matter
tiles) for the map, TanStack Query for server state, plain CSS with design
tokens (`src/styles/tokens.css`) — no UI library.

## Routing

React Router, two routes. **The URL is the state of record** — shareable,
back-button-safe, no global store.

- `/` — search entry (barrio or geolocation + query)
- `/results?q=<text>&near=<name>|&lat=&lng=&radius=&lang=` — fires the queries below

`lang=es|en` (absent = Spanish) selects UI copy via `src/i18n/strings.ts`;
data fields (item names, shop names, addresses) are never translated.

## State management

TanStack Query for all server state (cache key = the URL params). The only
client-side presentation state is the card↔pin selection and the ping
sequence (`src/hooks/usePingSequence.ts`) — "pinged" is timing, not data:
every matched shop IS pinged; the hook staggers when each lights up.
Retries: TanStack defaults, except permanent 4xx responses are not retried
(see `ApiError` in `src/api/client.ts`).

## Endpoints consumed

Two backends, two ports. The shopper API (`reachout/api/server.py`) serves
consumer mode; the demand service (`demand/api/app.py`) serves retail mode.
Base URLs are `VITE_API_BASE` (default `:8000`) and `VITE_DEMAND_API_BASE`
(default `:8001`).

| Endpoint | Response contract |
|----------|-------------------|
| `GET /api/search?q&near\|lat,lng&radius` | `reachout/shared/schemas/ranked_shops.schema.json` |
| `GET /api/search.geojson?…same params…` | `reachout/shared/schemas/map_geojson.schema.json` |
| `GET /api/shops.geojson` | `reachout/shared/schemas/shops_geojson.schema.json` (all shops, network layer) |
| `GET /api/health` | `{"status":"ok"}` |
| `GET /demand/api/analytics?inventory_type=&store_id=` | `demand/shared/schemas/analytics_response.schema.json` (retail dashboard, U3) |

If the frontend ever "needs" a field that isn't in a schema, the schema
changes first, backend second, generated types third — never a frontend-side
invention.

## PWA (U5) — consumer routes only

`public/sw.js` is hand-written, with no plugin and no build step. Its one
non-negotiable rule: **the offline cache holds the consumer app and nothing
else.** Anything at `?mode=retail`, and every request to the demand service,
bypasses the cache entirely — served from the network or failed honestly.
A cached dashboard would show yesterday's demand figures with nothing on
screen saying they were stale.

`src/pwa/sw.test.ts` evaluates that shipped file itself rather than a copy of
its logic, so the assertions hold for the artefact that reaches a phone.
`manifest.webmanifest` has `start_url: "/"` — never a retail URL.

## Generated files — never hand-edited

- `src/types/*.d.ts` — from **both** `reachout/shared/schemas/` and
  `demand/shared/schemas/` via `npm run gen-types`. Two roots because the app
  is one frontend over two services; a file name present in both roots aborts
  the run rather than silently overwriting one contract with the other.
- `src/data/barrios.ts` — from `reachout/data/gazetteer_madrid.json` via `npm run gen-barrios`

## Layout

```
src/
├── main.tsx                 router + QueryClientProvider + fonts/tokens + retry policy
├── styles/tokens.css        design tokens (palette, type). The map reads the
│                            same CSS custom properties — one color source.
├── i18n/strings.ts          all UI copy, ES/EN
├── api/client.ts            typed fetchers + ApiError
├── lib/                     format helpers, barrio matching
├── data/barrios.ts          GENERATED barrio names
├── types/                   GENERATED schema types
├── hooks/                   useLang (URL param), usePingSequence
├── chat/shopkeeper.ts       chat types (SHARED_CONTRACT shapes) + mock reply
│                            engine — swaps for POST /api/chat when it ships
├── map/map-layers.ts        pure GeoJSON builders (unit-tested, no maplibre)
├── pwa/register.ts          service-worker registration (U5)
├── shell/                   AppShell + the ?mode= toggle (U0)
├── components/consumer/     entry + results UI, MapPanel, PicksRail, InstallPrompt
├── components/retail/       RetailView, chat pane, dashboard, charts/ (ECharts only here)
└── routes/                  search.tsx (entry), results.tsx (split view)
```

## Commands

```bash
npm run dev          # vite dev server on :5173 (backend expected on :8000)
npm run build        # tsc --noEmit + vite build
npm test             # vitest (formatting, i18n, ping sequence, map builders)
npm run gen-types    # regenerate src/types from backend schemas
npm run gen-barrios  # regenerate src/data/barrios.ts from the gazetteer
```

`VITE_API_BASE` (`.env`, default `http://localhost:8000`) points at the
shopper API; `VITE_DEMAND_API_BASE` (default `http://localhost:8001`) points
at the demand service.
