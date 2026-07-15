# DONE — frontend v2 status (2026-07-16)

See `AGENT_NOTES.md` for why the kick-off plan was adapted instead of
followed literally (real backend ≠ SHARED_CONTRACT; app was not greenfield).

## Component inventory

| Piece | File(s) | Status |
|---|---|---|
| Entry hero (search + barrio autocomplete + geolocation + category tiles) | `routes/search.tsx`, `components/BarrioCombobox.tsx`, `SearchInput.tsx`, `entry.css` | pre-existing, kept |
| Results split view (ranked cards + MapLibre map, ping animation) | `routes/results.tsx`, `ResultsPanel.tsx`, `MapPanel.tsx`, `results.css` | pre-existing, kept |
| Shop card (rating, split price, stock badge) | `ShopCard.tsx` | extended with "Ask the shop" button |
| Filters / sort / pagination / skeletons / error / empty states | `ResultsPanel.tsx` | pre-existing, kept |
| **Shopkeeper chat slide-over** | `ChatPanel.tsx`, `chat.css`, `chat/shopkeeper.ts` | **new** — lazy-loaded (own 4 kB chunk), bilingual, typing indicator, suggestion chips, Escape/scrim close, history cleared on close |
| Chat mock engine + unit tests | `chat/shopkeeper.ts`, `chat/shopkeeper.test.ts` | **new** — answers stock/price/reserve/hours from real result data only; drop-in swap for `POST /api/chat` |
| i18n | `i18n/strings.ts` | +12 `chat.*` keys, ES/EN |

## Design decisions

- No Tailwind/shadcn/Zustand/Framer — the existing token-based design system
  and URL-as-state architecture were kept (rationale in AGENT_NOTES.md).
- Chat is a right slide-over (full-width < 420px viewports), 200ms ease
  animations, `prefers-reduced-motion` respected via the global rule.
- A "Preview — simulated replies" notice sits at the top of the chat log so
  mocked replies are never mistaken for the real shop.

## Verification

- `npm run build` — tsc + vite, clean (ChatPanel code-split).
- `npm test` — 5 files, 19 tests passing (5 new for the chat engine).
