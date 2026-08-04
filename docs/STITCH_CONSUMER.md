> **SUPERSEDED by docs/PLAN_V2_PROMPT.md (2026-08-01)** — mislabelled as an API call series (Stitch has no API); keep as a design specification, implemented directly by the coding agent, optionally pasteable into stitch.withgoogle.com for a visual reference.

# STITCH_CONSUMER.md — Consumer Shopping PWA, Prompt Series for Google Stitch (C1–C8)

*Planning document for Track B's Blinkit/Amazon-style consumer experience
(`docs/IMPLEMENTATION_PLAN.md` §2 tasks B3–B4). "Phone" = responsive web +
PWA (plan §0 decision D3) — no native scaffold. Hand each PROMPT to Google
Stitch (via API, key placeholder `[STITCH_API_KEY]`, from local `.env`) in
order. Operating rules and fallback (v0.dev) as in `docs/archive/STITCH_FRONTEND.md`
§2. This series EXTENDS the shipped Amazon-light redesign — same tokens
(`frontend/src/styles/tokens.css` incl. --price-red, --star-gold,
--stock-green, --amz-navbar), same i18n STRINGS pattern, same no-retry-4xx
query policy, ShopCard conventions from PROMPT 4 of that series. C5 needs
TASK 76 (`GET /api/picks`, `docs/JULES_DEMAND.md`) merged; C1–C4 don't.*

## 1. MASTER CONTEXT BLOCK (prepend to every Stitch call)

```
You are generating React 19 + TypeScript 5.7 components for ReachOut's
consumer shopping experience — MOBILE-FIRST (design at 375px, enhance to
768px/1080px). Vite 6, react-router-dom 7, TanStack Query 5, plain CSS with
the EXISTING design tokens (Amazon-light: white page, #ff9900 CTA,
#0f1111 ink, #b12704 price red, #007185 teal links, navbar darks #131921/
#232f3e — reference them ONLY as var(--token-name)). NO Tailwind, NO
CSS-in-JS, NO component library. Target tree additions:

frontend/src/
├── routes/shop/
│   ├── home.tsx         search-forward mobile home
│   ├── browse.tsx       category browse grid
│   ├── results.tsx      semantic search results
│   └── product.tsx      product detail
├── components/shop/
│   ├── ShopNav.tsx      sticky mobile top bar + bottom tab bar
│   ├── CategoryTile.tsx
│   ├── ProductCard.tsx  consumer product card (distinct from ShopCard)
│   ├── PicksRail.tsx    horizontal "para ti" rail
│   ├── StoreStrip.tsx   store info strip (name, barrio, delivery mins, rating)
│   ├── ReserveCTA.tsx   visit/reserve call-to-action (NO checkout)
│   └── shop.css         ALL new styles for this series
├── api/client.ts        EXTEND with typed fetchers below (ApiError pattern,
│                        TanStack Query never retries 4xx)
└── i18n/strings.ts      ALL copy as STRINGS["key"] = { es, en }

API shapes (authoritative — do not invent fields):
  POST /api/search  body { query: string, neighbourhood?: string }
    -> { results: Product[], interpreted_as: string }
  GET /api/products?neighbourhood=&category=&limit=&offset=
    -> { products: Product[], total: number }
  GET /api/picks?neighbourhood=&limit=
    -> { picks: Product[], generated_by: "deterministic" }
  GET /api/stores?neighbourhood=  -> { stores: Store[] }
  GET /api/neighbourhoods         -> { neighbourhoods: string[] }
  Product: { id, name, description, category, price, stock_qty, store_id,
             neighbourhood, tags[], image_url }
  Store:   { id, name, neighbourhood, avg_delivery_mins, is_open, rating }

HARD PRODUCT RULES: there is NO cart, NO checkout, NO payment anywhere —
the terminal action is always "reserve/visit the shop" (ReserveCTA).
Stock is shown factually from stock_qty (in stock / only N left / out of
stock) — never softened, never invented. Prices .mono with the split
euros/cents style from the existing ShopCard. Spanish default, English via
?lang=en. Touch targets >= 44px.

Generate ONE component (or the one file asked for) per prompt, presentation
only, explicit props; data wiring stays with the integrator.
```

## 2. THE PROMPT SERIES

Run in order; after each: paste into repo, `cd frontend && npm run build &&
npm test`, fix types before continuing. Append the FLAG-AND-SUGGEST note
from `STITCH_FRONTEND.md` §4 to every call.

---

### PROMPT C1 — ShopNav + mobile home (search-forward)

```
Create shop.css foundations + ShopNav.tsx + routes/shop/home.tsx
(presentation). ShopNav: sticky top bar (var(--amz-navbar) background,
logo left, barrio selector button center showing current barrio with ▾,
lang toggle right) + fixed bottom tab bar on <768px (Inicio / Categorías /
Buscar / Para ti, 44px+ targets, active tint var(--terracotta)); on >=768px
the bottom bar hides and tabs move into the top bar. Home: big search
field ("¿Qué necesitas?") that navigates to results on submit, barrio
picker sheet (slide-up panel listing neighbourhoods, accent-insensitive
filter input — reuse the BarrioCombobox filtering convention), a 2-column
(4 at >=768px) category tile grid using CategoryTile.tsx (create it:
pictogram + label + subtle --shadow-card, categories passed as props), and
a PicksRail placeholder slot rendered only when a `picksSlot` prop is
provided. Props explicit for everything; copy via STRINGS shop.nav.*,
shop.home.*.
```

---

### PROMPT C2 — Category browse grid

```
Create routes/shop/browse.tsx (presentation) + ProductCard.tsx. ProductCard
(mobile-first, grid-friendly): image (square, object-fit cover, gray
--ink-700 placeholder with category pictogram when image_url is null),
name (2-line clamp), split price (.mono, euros large / cents superscript,
var(--price-red)), stock line — "En stock" (--stock-green) / "Quedan N"
when stock_qty <= 5 (--stock-amber) / "Agotado" (--sand-dim, card at 60%
opacity, not hidden) — and store name + barrio microcaps. Whole card is a
link to product detail. browse.tsx: props { category, products, total,
page, onPage } — 2-col grid at 375px, 3 at 768px, 4 at 1080px, header with
category name + result count (.mono), pagination reusing the existing
results-pagination classes. STRINGS shop.browse.*, shop.stock.*.
```

---

### PROMPT C3 — Semantic search results with interpreted_as echo

```
Create routes/shop/results.tsx (presentation) reusing ProductCard. Props:
{ query: string; interpretedAs: string | null; results: Product[];
neighbourhood: string | null; state: "pending"|"ok"|"empty"|"error";
onRetry(): void }. Above the grid, when interpretedAs differs from query,
show the echo line: "Mostrando resultados para «{interpretedAs}»" with a
subdued "buscaste: {query}" — this is the AI-interpretation transparency
line; it must always render when present. Empty state: no results in this
barrio -> suggestion chips "Buscar en todo Madrid" (clears neighbourhood)
and "Ver categorías". Pending: 6 ProductCard skeletons (shimmer, CSS
only). Error: existing retry CTA pattern. STRINGS shop.results.*.
```

---

### PROMPT C4 — Product detail + StoreStrip + ReserveCTA

```
Create routes/shop/product.tsx (presentation) + StoreStrip.tsx +
ReserveCTA.tsx. Detail: image top (16:9 crop on mobile, side-by-side at
>=768px), name h1, split price large, factual stock line (same three-state
rule), description paragraph, tag chips. StoreStrip: store name, barrio,
star rating (var(--star-gold), presence-checked with "Sin valoraciones"
fallback — same convention as ShopCard), avg_delivery_mins as "~N min",
open/closed dot (--stock-green / --err). ReserveCTA: full-width bottom-fixed
bar on mobile (static at >=768px): primary button "Reservar en tienda"
(var(--terracotta), disabled + "Agotado" label when stock_qty === 0) and
secondary "Cómo llegar" link button. Reserving opens a confirm sheet
(presentation only: item, store, "te lo guardan hoy" copy, confirm/cancel
callbacks via props). NO price total, NO quantity stepper, NO cart
language anywhere. STRINGS shop.product.*, shop.reserve.*.
```

---

### PROMPT C5 — PicksRail ("para ti") *(needs TASK 76 merged)*

```
Create PicksRail.tsx. Props: { picks: Product[]; title?: string;
onSeeAll(): void }. Horizontal scroll-snap rail of compact ProductCard
variants (140px wide, image + name 1-line + split price + stock dot),
scroll-snap-align start, momentum scrolling, fade-out edge masks, "Ver
todo" text link right of the title ("Para ti" default, STRINGS
shop.picks.title). Under the title, a permanent microcaps line (STRINGS
shop.picks.how): "Selección según valoraciones y stock en tu barrio" —
picks are deterministic (rating + stock + category variety), NOT
behavioral tracking, and the label says so. Renders nothing at all when
picks is empty (no empty state). Mount points (integrator): home
picksSlot and product detail below StoreStrip.
```

---

### PROMPT C6 — Landing/home merge + route wiring audit *(read-only prompt)*

```
Audit prompt — output findings + minimal diffs only, no new components.
Check the /shop/* routes against the existing app: (1) route config —
/shop (home), /shop/c/:category, /shop/s?q=&near=, /shop/p/:id all
registered lazily alongside the existing / and /results routes without
breaking them; (2) every fetcher goes through api/client.ts ApiError +
no-4xx-retry policy; (3) barrio state: one source of truth in the URL
(?near=), shared by home picker, results, browse, picks — flag any
component holding its own copy; (4) lang param propagates across all
/shop/* navigation; (5) list files where shop.css classes collide with
results.css/entry.css and propose renames. Output: numbered findings, each
with file + one-line fix.
```

---

### PROMPT C7 — PWA: manifest, icons, install prompt, offline shell

```
Generate the PWA layer (files only, no service-worker library): (1)
frontend/public/manifest.webmanifest — name "ReachOut", short_name
"ReachOut", start_url "/shop?source=pwa", display "standalone",
background_color "#ffffff", theme_color "#131921", lang "es", icons 192/512
maskable+any (reference /icons/icon-192.png, /icons/icon-512.png; also
output an SVG source icon: white "R" wordmark dot on #131921 rounded
square). (2) frontend/public/sw.js — minimal hand-written service worker:
precache the app shell (/, /shop, built assets via self.__WB_MANIFEST-free
pattern: cache-first for /assets/*, network-first for /api/* with no
caching of POST /api/search, offline fallback page /offline.html showing
"Sin conexión" + retry). NEVER cache /api/* responses beyond a 60s
freshness window and never cache anything with Authorization headers. (3)
frontend/public/offline.html — static, tokens inlined. (4) registration
snippet for main.tsx (feature-detected, prod-only) and the index.html
<link rel="manifest"> + theme-color + apple-touch-icon tags. (5)
InstallPrompt.tsx: listens for beforeinstallprompt, shows a dismissible
bottom sheet after the SECOND visit (localStorage counter), STRINGS
shop.install.*; never blocks content.
```

---

### PROMPT C8 — Mobile/touch + a11y audit *(read-only prompt)*

```
Final audit of C1–C7 at 360px, 375px, 414px, 768px, 1080px — output
findings + minimal diffs only. Verify: all tap targets >= 44px (bottom
tabs, pagination, chips, CTA); no horizontal page scroll at any width
(rails scroll internally); ReserveCTA bottom bar never overlaps content
(padding-bottom on scroll container) and respects
env(safe-area-inset-bottom); text contrast AA on white and on
--amz-navbar; focus order home -> results -> detail -> reserve sheet is
keyboard-completable, sheets trap focus and close on Escape; stock states
distinguishable without color alone (text always present); .mono on every
numeral in new copy; ES strings don't overflow (longest: category names,
"Sin valoraciones"). Number findings, file + one-line fix each.
```

## 3. Verification loop per prompt

As `STITCH_FRONTEND.md` Appendix, plus for this series: after C4 and C8,
drive the flow on a 375px viewport with the repo `verify` skill recipe
(entry → barrio → query "algo para el dolor de cabeza" → results → detail →
reserve sheet), and after C7 run a Lighthouse PWA pass (installability +
offline fallback) against the production build (`npm run build && vite
preview`).
