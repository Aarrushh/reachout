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

## Endpoints consumed (from `reachout/api/server.py`)

| Endpoint | Response contract |
|----------|-------------------|
| `GET /api/search?q&near\|lat,lng&radius` | `reachout/shared/schemas/ranked_shops.schema.json` |
| `GET /api/search.geojson?…same params…` | `reachout/shared/schemas/map_geojson.schema.json` |
| `GET /api/shops.geojson` | `reachout/shared/schemas/shops_geojson.schema.json` (all shops, network layer) |
| `GET /api/health` | `{"status":"ok"}` |

If the frontend ever "needs" a field that isn't in a schema, the schema
changes first, backend second, generated types third — never a frontend-side
invention.

## Generated files — never hand-edited

- `src/types/*.d.ts` — from `reachout/shared/schemas/` via `npm run gen-types`
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
├── components/              entry + results UI, MapPanel (all maplibre code)
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

`VITE_API_BASE` (`.env`, default `http://localhost:8000`) points at the API.
