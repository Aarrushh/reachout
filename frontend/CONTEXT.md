# CONTEXT.md  (Layer 1: Where do I go?)

This is a routing table, not a tutorial. It says what exists **today** and
draws a hard line under what is still **planned**. If a doc elsewhere
disagrees with this file, trust this file — it is kept honest on purpose.

**U0 has landed.** The shell and the mode toggle exist; the two component
trees are declared but still empty. U1 onward remain planned.

## Routes — today

| Route | File | Reads | Renders |
|-------|------|-------|---------|
| `/` | `src/routes/search.tsx` | — | Entry hero: barrio autocomplete + geolocation + bilingual search |
| `/results` | `src/routes/results.tsx` | `?q=&near=\|lat,lng&radius=&lang=` | Split view: ranked shop cards left, MapLibre map right, ping animation |

`main.tsx` mounts exactly these two routes inside `BrowserRouter` — no
other routes exist. Since U0 they are wrapped in `AppShell`, which is
inside the router because it reads `?mode=`.

**Modes are not routes.** `?mode=retail` selects the shopkeeper half of the
app on whatever route you are on; anything else (absent, misspelled, wrong
case) is the shopper half. There is no `/dashboard` and there will not be
one — the toggle is a query param so a mode is shareable and a reload cannot
disagree with the address bar.

| File | Role |
|------|------|
| `src/shell/useMode.ts` | `parseMode()` (the rule: only the exact string `retail`) + `useMode()` (URL in, URL out; no store, no context) |
| `src/shell/AppShell.tsx` | The frame both halves render in. Consumer mode renders the wrapped routes; retail mode renders its own surface **instead of** them, never on top of them |
| `src/shell/ModeToggle.tsx` | Top-right switch. `aria-pressed` mirrors the URL |
| `src/shell/shell.css` | Shell chrome only. `.app-shell__body` is a flex column on purpose — `.results-screen` is `height: 100%` and needs a definite parent height or the map collapses | `lang=es|en` (absent = Spanish) selects UI copy via
`src/i18n/strings.ts`; it is read/written through `src/hooks/useLang.ts`.

## Key components — today

| Component | File | Role |
|-----------|------|------|
| `TopBar` | `src/components/TopBar.tsx` | Results-screen header: query recap, language switch |
| `MapPanel` | `src/components/MapPanel.tsx` | All MapLibre code — the only file that touches the map instance |
| `MapOverlay` | `src/components/MapOverlay.tsx` | Non-map UI drawn over the map (legend, controls) |
| `ShopCard` | `src/components/ShopCard.tsx` | One ranked shop: rating, split price, stock badge, "Ask the shop" button |
| `BarrioCombobox` | `src/components/BarrioCombobox.tsx` | Neighbourhood autocomplete over the generated Madrid gazetteer |
| `ResultsPanel` | `src/components/ResultsPanel.tsx` | Ranked card list: filters, sort, pagination, skeleton/error/empty states |
| `ChatPanel` | `src/components/ChatPanel.tsx` | Lazy-loaded slide-over "ask the shopkeeper" chat UI |
| `chat/shopkeeper.ts` | `src/chat/shopkeeper.ts` | Chat message types (SHARED_CONTRACT shapes) + a **mock** reply engine — answers only from real result data, never invents inventory; swaps for a real `POST /api/chat` call in one function body when that endpoint ships |

`src/map/map-layers.ts` and `src/map/geojson-source.ts` are pure GeoJSON
builders `MapPanel` consumes — no MapLibre import, unit-tested standalone.

## Fetchers — today

All server access goes through `src/api/client.ts`. No component calls
`fetch` directly.

| Fetcher | Endpoint | Response type |
|---------|----------|----------------|
| `fetchRankedShops` | `GET /api/search?q&near\|lat,lng&radius` | `RankedShops` |
| `fetchShopsGeoJSON` | `GET /api/search.geojson?…same params…` | `ShopMapGeoJSON` |
| `fetchAllShops` | `GET /api/shops.geojson` | `ShopsGeoJSON` |

These all target the pipeline's `GET /api/search` family in
`reachout/api/server.py` (decision S6) — not the Supabase `POST
/api/search` path, which stays mounted but unused by this frontend.
`ApiError` (same file) carries the HTTP status so `main.tsx`'s TanStack
Query retry predicate can skip retrying 4xx responses.

## Generated files — never hand-edited

| Path | Generator | Source |
|------|-----------|--------|
| `src/types/*.d.ts` | `npm run gen-types` (`scripts/gen-types.ts`) | JSON Schemas in `reachout/shared/schemas/` |
| `src/data/barrios.ts` | `npm run gen-barrios` (`scripts/gen-barrios.ts`) | `reachout/data/gazetteer_madrid.json` |

Edit the schema or the gazetteer, then regenerate — never edit the
generated output by hand.

## PLANNED — the rest of the consumer/retail split (U1 onward)

`src/components/consumer/` and `src/components/retail/` exist and are
**empty** — each holds a README stating what belongs in it and nothing else.
Every component listed under "today" is still in `components/` proper; U1 is
what moves them.

| Task | Adds | Status |
|------|------|--------|
| **U0** | `AppShell` wrapping both routes; top-right toggle reading `?mode=retail` (S2) — absent/unrecognised = consumer; mode derived from the URL only, no store, no context; creates the empty `components/consumer/` and `components/retail/` trees | ✅ **DONE 2026-08-03** |
| **U1** | Re-homes the "today" components above under `components/consumer/`; fetchers stay on `api/client.ts` / `GET /api/search`; no behaviour change | PLANNED |
| **U2** | Retail mode's chat pane — reuses `ChatPanel` + `chat/shopkeeper.ts` as-is, left pane of retail mode, still client-side mock, still no backend | PLANNED |
| **U3** | Analytics dashboard: `echarts-for-react` (D9), three charts confined to `components/retail/charts/`, fed by a new `fetchAnalytics()` in `api/client.ts` against `GET /demand/api/analytics`; the frontend draws only, every rendered number is server-computed | PLANNED |
| **U6** | Disabled "ask AI about my analytics" button — visible, `aria-disabled`, no handler, no fetcher | PLANNED |

There is still no chart dependency in `package.json` — U3 adds it.
