# CONTEXT.md  (Layer 1: Where do I go?)

This is a routing table, not a tutorial. It says what exists **today** and
draws a hard line under what is still **planned**. If a doc elsewhere
disagrees with this file, trust this file — it is kept honest on purpose.

**U0, U1, U2 and U6 have landed.** The shell and the mode toggle exist, the
consumer surface lives under `src/components/consumer/`, and retail mode
renders a real two-column view with a working chat pane and the deliberately
dead AI button. U3 fills the rest of the right column; U4, U5 and U7 follow.

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
| `TopBar` | `src/components/consumer/TopBar.tsx` | Results-screen header: query recap, language switch |
| `MapPanel` | `src/components/consumer/MapPanel.tsx` | All MapLibre code — the only file that touches the map instance |
| `MapOverlay` | `src/components/consumer/MapOverlay.tsx` | Non-map UI drawn over the map (legend, controls) |
| `ShopCard` | `src/components/consumer/ShopCard.tsx` | One ranked shop: rating, split price, stock badge, "Ask the shop" button |
| `BarrioCombobox` | `src/components/consumer/BarrioCombobox.tsx` | Neighbourhood autocomplete over the generated Madrid gazetteer |
| `ResultsPanel` | `src/components/consumer/ResultsPanel.tsx` | Ranked card list: filters, sort, pagination, skeleton/error/empty states |
| `ChatPanel` | `src/components/ChatPanel.tsx` | The one chat UI, in two presentations. `variant="overlay"` (default) is the consumer slide-over, lazy-loaded from `routes/results.tsx`; `variant="pane"` is retail mode's permanent left column — no scrim, no dialog role, no Escape handler |
| `RetailView` | `src/components/retail/RetailView.tsx` | Everything behind `?mode=retail`: chat left, dashboard right |
| `RetailChatPane` | `src/components/retail/RetailChatPane.tsx` | The retail column. Same mock engine, a **sample** shop context, and an always-visible notice saying so |
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

## PLANNED — the rest of the consumer/retail split (U3 onward)

`src/components/consumer/` is populated (U1) and `src/components/retail/`
now holds `RetailView` + `RetailChatPane` (U2) + `AiAnalystButton` (U6). U3
fills the rest of the dashboard column.

**What deliberately stayed in `components/` proper:** `ChatPanel.tsx` and
`chat.css`. Both halves use it — consumer's "ask the shop" slide-over today,
retail's left pane from U2 — and a component two trees need belongs to
neither. It is not copied into both.

| Task | Adds | Status |
|------|------|--------|
| **U0** | `AppShell` wrapping both routes; top-right toggle reading `?mode=retail` (S2) — absent/unrecognised = consumer; mode derived from the URL only, no store, no context; creates the empty `components/consumer/` and `components/retail/` trees | ✅ **DONE 2026-08-03** |
| **U1** | Re-homes the "today" components above under `components/consumer/`; fetchers stay on `api/client.ts` / `GET /api/search`; no behaviour change | ✅ **DONE 2026-08-03** |
| **U2** | Retail mode's chat pane — reuses `ChatPanel` + `chat/shopkeeper.ts`, left pane of retail mode, still client-side mock, still no backend | ✅ **DONE 2026-08-03** |
| **U3** | Analytics dashboard: `echarts-for-react` (D9), three charts confined to `components/retail/charts/`, fed by a new `fetchAnalytics()` in `api/client.ts` against `GET /demand/api/analytics`; the frontend draws only, every rendered number is server-computed | PLANNED |
| **U6** | Disabled "ask AI about my analytics" button — visible, `disabled` **and** `aria-disabled`, no handler, no fetcher; the reason is an on-screen caption tied by `aria-describedby`, never a `title` tooltip | ✅ **DONE 2026-08-04** |

There is still no chart dependency in `package.json` — U3 adds it.
