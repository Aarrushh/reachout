# FRONTEND AGENT IMPROVEMENTS

Date: 2026-07-16 · Branch: `stitch-frontend`

The kick-off plan assumed a greenfield app and a backend exposing
`POST /api/search`, `POST /api/chat`, `GET /api/products|stores|neighbourhoods`.
Neither assumption holds, so the plan was adapted rather than followed
literally. This file records each decision and why.

## Reality check (verified against the repo)

- The real backend (`reachout/api/server.py`) exposes:
  `GET /api/health`, `GET /api/search?q&near|lat,lng&radius`,
  `GET /api/search.geojson`, `GET /api/shops.geojson`, `GET /api/inventory`,
  `GET /api/regions`, `GET /api/inventory/stream`.
  **None of the SHARED_CONTRACT.md endpoints exist**, and no status flag was
  ever set. SHARED_CONTRACT.md has been annotated to reflect this.
- The frontend is not greenfield: a complete, tested Amazon-style UI already
  exists (entry hero + barrio autocomplete + split results view with MapLibre
  map, filters, sort, pagination, skeletons, error/empty states, ES/EN i18n).

## Decisions (plan item → what was done)

| Plan proposal | Decision | Why |
|---|---|---|
| React Query vs SWR | **React Query — already in use** | No change needed; retry policy already 4xx-aware. |
| Zustand vs Context for global state | **Neither — URL is the state of record** | The existing architecture keys React Query caches off URL params; it's shareable and back-button-safe. Adding Zustand would create a second source of truth. Chat open/close is ephemeral presentation state → local `useState`. |
| Tailwind + shadcn/ui + Lucide + Framer Motion | **Not installed** | The app has a coherent hand-built design system (`styles/tokens.css`, plain CSS, Space Grotesk/Inter/IBM Plex Mono, inline SVG icons). Bolting on 4 frameworks to restyle working, WCAG-checked components is churn, not improvement. New chat UI uses the same tokens; slide-over animation is ~10 lines of CSS, honoring `prefers-reduced-motion`. |
| react-router-dom installed? | **Yes (v7)** — already routing `/` and `/results`. |
| Neighbourhood selector: map click vs autocomplete | **Autocomplete (already built)** — `BarrioCombobox` over the generated Madrid gazetteer, plus geolocation. The old dropdown was already gone. |
| Chat: floating widget vs slide-over | **Slide-over panel from the right** (plan's choice, agreed) — full conversation surface, mobile-friendly (full-width < 720px), lazy-loaded with `React.lazy`. |
| Chat API | **Mocked client-side** (`src/chat/shopkeeper.ts`) | Backend has no `/api/chat` and `PHASE_3_CHAT_READY` is unset. Per the agentic rules, the UI is built now against the SHARED_CONTRACT request/response shapes with a local mock shopkeeper; swapping to the real endpoint is one function body (`sendChatMessage`). The mock only speaks from real result data (item, price, stock, shop name) — it never invents inventory. |
| Design vision (#FAFAF8 / #2D6A4F palette) | **Kept the existing Amazon-style light theme** | Token names are frozen — `MapPanel` reads them by name at runtime — and the current palette is contrast-audited on both white cards and the dark map. A palette swap is a separate, deliberate task, not a side effect. |

## What was added in this pass

- `src/chat/shopkeeper.ts` — chat types matching SHARED_CONTRACT + mock reply
  engine (bilingual, keyed off real shop/item data, simulated latency).
- `src/components/ChatPanel.tsx` — lazy-loaded slide-over: shop header,
  user/assistant bubbles, three-dot typing indicator, Enter-to-send,
  Escape-to-close, history cleared on close.
- `src/components/chat.css` — panel styles on existing tokens.
- "Ask the shop" ghost button on `ShopCard`.
- `chat.*` i18n strings (ES/EN).
