# ReachOut frontend — ARCHITECTURE ONLY

**Visual design is a separate future phase.** This folder deliberately contains
zero visual, layout, component-styling, or UI decisions. That work belongs to a
later phase using a different skill set (ui-ux-pro-max, 21st.dev, v0). This
document fixes only the architecture those tools will drop into.

## Framework

React 19 + Vite + TypeScript.

Why: (a) the designated future-UI tools (v0, 21st.dev) emit React components,
so this skeleton is what they'll plug into; (b) MapLibre GL JS — open-source
and keyless, consistent with ReachOut's anti-centralization positioning — has
mature React bindings for the future map phase; (c) `json-schema-to-typescript`
keeps frontend types slaved to the backend schemas.

## Routing

React Router, two routes. **The URL is the state of record** — shareable,
back-button-safe, and it removes the need for a global store.

- `/` — search entry (reads/writes URL query params)
- `/results?q=<text>&near=<name>|&lat=&lng=&radius=` — fires the two queries below

## State management

TanStack Query for all server state (cache key = the URL params). No
Redux/Zustand for the MVP; the only client state is the URL.

## Endpoints consumed (from `reachout/api/server.py`)

| Endpoint | Response contract |
|----------|-------------------|
| `GET /api/search?q&near\|lat,lng&radius` | validates against `reachout/shared/schemas/ranked_shops.schema.json` |
| `GET /api/search.geojson?…same params…` | validates against `reachout/shared/schemas/map_geojson.schema.json` |
| `GET /api/health` | `{"status":"ok"}` |

## Data shape expected

Exactly the stage 04 and stage 05 schemas: a ranked list of
`{rank, shop_id, shop_name, category, address, distance_km, item_name, sku,
price, currency, stock_qty, lat, lng}` and a Point FeatureCollection.

If the frontend ever "needs" a field that isn't in a schema, the schema
changes first, backend second, generated types third — never a frontend-side
invention.

## Planned skeleton (built in execution step 11, no visuals)

```
frontend/
├── package.json              react, react-dom, react-router,
│                             @tanstack/react-query, typescript, vite;
│                             maplibre-gl listed but unwired until the UI phase
├── vite.config.ts
├── tsconfig.json
├── .env.example              VITE_API_BASE=http://localhost:8000
├── scripts/
│   └── gen-types.ts          json-schema-to-typescript over
│                             ../reachout/shared/schemas/ → src/types/*.d.ts
└── src/
    ├── main.tsx              router + QueryClientProvider bootstrap only
    ├── routes/
    │   ├── search.tsx        route module: URL params in/out; no visuals
    │   └── results.tsx       route module: fires the two queries; no visuals
    ├── api/
    │   └── client.ts         two typed fetchers, nothing else
    ├── types/                GENERATED from shared/schemas — never hand-edited
    └── map/
        └── geojson-source.ts adapter exposing the stage-05 FeatureCollection
                              to whatever map component the future UI phase
                              builds; no rendering code now
```
