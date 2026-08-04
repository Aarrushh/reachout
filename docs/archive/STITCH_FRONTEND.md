> **SUPERSEDED by docs/PLAN_V2_PROMPT.md (2026-08-01)** — mislabelled as an API call series (Stitch has no API); the 12 prompts were executed and merged, keep as the design record of that work.

# STITCH_FRONTEND.md — Amazon-Style Redesign, Prompt Series for Google Stitch

*Planning document. Hand each PROMPT below to Google Stitch (via API, key placeholder
`[STITCH_API_KEY]`) one at a time, in order. Each prompt is self-contained but assumes
the outputs of the previous prompts have been merged into the repo.*

---

## 1. MASTER CONTEXT BLOCK (prepend to every Stitch call)

Paste this block verbatim as the system/context input on every Stitch request.

```
You are generating React 19 + TypeScript 5.7 components for ReachOut, a hyperlocal
inventory router. Vite 6, react-router-dom 7, TanStack Query 5, plain CSS with
design tokens (NO Tailwind, NO CSS-in-JS, NO component library). Target file tree:

frontend/src/
├── routes/
│   ├── search.tsx        entry page (full-screen search + location picker)
│   └── results.tsx       split view: <TopBar/> then <div class="split"> with
│                         <ResultsPanel/> (left) + <MapPanel/> (right)
├── components/
│   ├── TopBar.tsx        search bar + radius slider + lang toggle
│   ├── SearchInput.tsx   controlled input + submit button
│   ├── BarrioCombobox.tsx  accent-insensitive barrio autocomplete
│   ├── ResultsPanel.tsx  pending skeletons / error / empty / list of ShopCard
│   ├── ShopCard.tsx      one ranked shop result
│   ├── MapPanel.tsx      ALL MapLibre GL code lives here — DO NOT MODIFY the
│   │                     map init, sources, layers, or feature-state logic
│   ├── results.css       styles for TopBar/ResultsPanel/ShopCard/split/map chrome
│   └── entry.css         styles for the entry page
├── hooks/
│   ├── useLang.ts        lang from URL param ?lang= (es default, en opt-in)
│   └── usePingSequence.ts staggered "pinged" Set<string> presentation state
├── api/client.ts         typed fetchers: fetchRankedShops(params),
│                         fetchShopsGeoJSON(params), fetchAllShops(); throws
│                         ApiError(message, status); TanStack Query never
│                         retries 4xx
├── i18n/strings.ts       ALL UI copy as STRINGS["key"] = { es, en };
│                         t(lang, key, vars) — components NEVER hardcode text
├── styles/tokens.css     THE ONLY place colors exist, as CSS custom properties
├── types/*.d.ts          GENERATED from backend JSON Schemas — never edit;
│                         key type: RankedShops (results[]: rank, shop_id,
│                         shop_name, category, address, distance_km, item_name,
│                         sku, price, currency, stock_qty, lat, lng)
└── data/barrios.ts       GENERATED barrio list — never edit

HARD INVARIANTS — violating any of these makes the output unusable:
1. URL IS THE STATE OF RECORD. All search state lives in URLSearchParams
   (q, near OR lat+lng, radius, lang; you will add: region, sort, page,
   category). No Redux, no Zustand, no Context for search state. New UI state
   that must survive reload goes into the URL via setSearchParams.
2. ALL COLORS come from CSS custom properties defined in src/styles/tokens.css.
   Never write a hex value in a component or any other CSS file.
3. ALL user-facing copy goes through t(lang, "key") in i18n/strings.ts, with
   BOTH es and en values. Data fields from the API (shop names, item names,
   addresses) are never translated.
4. MapPanel.tsx: you may change its container's size/position from CSS and add
   sibling OVERLAY elements rendered by other components, but never touch
   maplibregl.Map init, addSource/addLayer calls, or feature-state effects.
5. Fonts are self-hosted @fontsource packages already installed: Space Grotesk
   (display), Inter (UI), IBM Plex Mono (ALL numbers: prices, distances,
   counts). Numbers always get className="mono".
6. Types in src/types/ are generated from backend schemas (npm run gen-types).
   If a component needs a field that isn't in RankedShops, STOP and flag it —
   the field must be added schema-first on the backend, never invented here.
7. Category values are exactly: pharmacy, grocery, hardware, electronics,
   stationery. Each has a --cat-* token.
8. TanStack Query owns server state; cache keys derive from URL params.
9. Respect prefers-reduced-motion (tokens.css already disables all animation).

Output per prompt: complete file contents for the named files only, TypeScript
strict-mode clean, no new npm dependencies unless the prompt says so.
```

**SUGGESTION:** the current UI has no star ratings and no rating data exists in any
schema. Per invariant 6, star ratings CANNOT be rendered from real data until the
backend adds a `rating` field schema-first (see `docs/JULES_BACKEND.md` TASK 21 —
DummyJSON products ship a `rating` float, so the backend plan already covers it).
The prompts below therefore build the rating row **behind a presence check**
(`r.rating !== undefined`) so the frontend degrades gracefully until the backend
lands. Do not let Stitch fake ratings client-side.

---

## 2. TOOL OVERVIEW — Google Stitch

**What it is.** Google Stitch (stitch.withgoogle.com) is an AI UI generator: prompt
in, UI design + frontend code out. Via the API (`[STITCH_API_KEY]`), you submit a
text prompt (optionally with image references) and receive generated screens and
exportable code.

**What it's good at**
- Generating one screen/component per prompt from a precise textual spec.
- Iterating: follow-up prompts refine the previous output.
- Amazon-style e-commerce layouts are squarely in its training distribution.

**Limitations to design around**
- It defaults to Tailwind and its own design system — every prompt must repeat
  "plain CSS with the provided custom-property tokens, no Tailwind."
- It does not see your repo. Every prompt must carry the context block above plus
  the exact props interface you want, or it will invent its own.
- It will not reliably wire TanStack Query/router state — prompts keep data
  wiring in YOUR hands: Stitch generates presentation components with explicit
  props; you (or a follow-up integration prompt) connect them.
- One component per prompt. Multi-file asks degrade quality sharply.
- Generated a11y is inconsistent — the audit prompt (PROMPT 12) re-checks it.

**Alternative:** if Stitch is unavailable, **v0.dev (Vercel)** accepts the same
prompt series nearly verbatim (v0 is also chat-iterative, also Tailwind-default —
keep the "plain CSS + tokens" instruction). v0's React/TypeScript output quality
is comparable; export as code, not as v0 project blocks.

---

## 3. THE PROMPT SERIES

Run in order. After each prompt: paste output into the repo, run
`cd frontend && npm run build && npm test`, fix type errors before continuing.

---

### PROMPT 1 — Design token override (Amazon palette)

```
Rewrite frontend/src/styles/tokens.css for an Amazon-style light theme while
keeping EVERY existing custom-property NAME unchanged (MapPanel.tsx reads them
by name at runtime via getComputedStyle — renaming any token breaks the map).

Current tokens to re-value (names are frozen):
  --ink-900 --ink-800 --ink-700 --ink-600   (page/surface backgrounds, darkest→lightest)
  --terracotta --terracotta-hot              (primary accent: pings, CTAs, selection)
  --sand --sand-dim                          (primary/secondary text)
  --gold                                     (highlight)
  --navy-line                                (map network dots, hairlines)
  --cat-pharmacy --cat-grocery --cat-hardware --cat-electronics --cat-stationery
  --err
  --font-display --font-mono --font-ui

New values, Amazon-inspired:
  --ink-900: #ffffff (page)  --ink-800: #f7f8f8 (panel)  --ink-700: #eaeded
  --ink-600: #d5d9d9 (borders)
  --terracotta: #ff9900 (Amazon orange, CTA)  --terracotta-hot: #e47911
  --sand: #0f1111 (primary text)  --sand-dim: #565959 (secondary text)
  --gold: #ffa41c (star color)  --navy-line: #007185 (Amazon teal links)
  --err / price red: #b12704
  Keep the five --cat-* hues recognizable but darkened for a white background
  (WCAG AA ≥ 4.5:1 against #ffffff for any text use).

ADD these new tokens (new names allowed, additions only):
  --price-red: #b12704        --star-gold: #ffa41c
  --stock-green: #007600      --stock-amber: #b12704
  --amz-navbar: #131921       --amz-navbar-2: #232f3e  (the two navbar darks)
  --focus-ring: #007185
  --shadow-card: 0 2px 5px rgba(15,17,17,.15)

Keep: the * box-sizing reset, html/body/#root height rules, .mono and
.microcaps utility classes, button/input font inherit, and the
prefers-reduced-motion block — all verbatim except body's colors now read the
new values. Body font-size moves 13px → 14px (Amazon's base).

NOTE: the dark MapLibre basemap (Carto Dark Matter) stays dark — the map panel
is intentionally a dark island in a light page, so --navy-line and --cat-*
values must remain visible on BOTH the dark map and white cards. Choose
mid-lightness values and state the contrast ratio you achieved for each.

Output: the complete new tokens.css only.
```

---

### PROMPT 2 — i18n key additions

```
Extend frontend/src/i18n/strings.ts (pattern: STRINGS["dot.key"] = { es, en };
helper t(lang, key, vars) replaces {var} placeholders). Keep every existing key
untouched. Add keys, with natural Spanish first, for:

  nav.deliverTo         es "Buscar cerca de" / en "Searching near"
  nav.categories.all    "Todas" / "All"
  nav.cat.pharmacy      "Farmacia" / "Pharmacy"     (+ grocery, hardware,
                        electronics, stationery — one key each)
  results.count         "{n} resultados para «{q}»" / "{n} results for \"{q}\""
  results.inStock       "En stock" / "In Stock"
  results.onlyNLeft     "Solo quedan {n}" / "Only {n} left"
  results.outOfStock    "Sin stock" / "Out of Stock"
  results.noRating      "Sin valoraciones" / "No ratings yet"
  sort.label            "Ordenar por" / "Sort by"
  sort.relevance        "Relevancia" / "Relevance"
  sort.priceAsc         "Precio: menor a mayor" / "Price: Low to High"
  sort.priceDesc        "Precio: mayor a menor" / "Price: High to Low"
  sort.distance         "Distancia" / "Distance"
  filter.title          "Filtros" / "Filters"
  filter.category       "Categoría" / "Category"
  filter.inStockOnly    "Solo en stock" / "In stock only"
  page.prev             "Anterior" / "Previous"
  page.next             "Siguiente" / "Next"
  page.of               "Página {p} de {total}" / "Page {p} of {total}"
  map.region            "Zona" / "Region"
  map.allCity           "Todo Madrid" / "All Madrid"
  map.liveShops         "{n} tiendas activas" / "{n} shops live"
  map.live              "EN VIVO" / "LIVE"
  landing.tagline       "Lo que necesitas, ya está cerca" / "What you need is already nearby"
  landing.how1          "Di lo que buscas" / "Say what you need"
  landing.how2          "Las tiendas cercanas reciben un ping al instante" / "Nearby shops get pinged instantly"
  landing.how3          "Elige por distancia, precio y stock real" / "Choose by distance, price and live stock"
  landing.categoriesTitle "Compra por categoría" / "Shop by category"

Output: the complete new strings.ts.
```

---

### PROMPT 3 — TopBar → Amazon navbar with category strip

```
Rewrite frontend/src/components/TopBar.tsx as an Amazon-style navbar. Keep the
EXACT existing props interface and add two optional props:

  interface Props {
    q: string;
    near: string | null;
    radiusKm: number;
    lang: Lang;
    onSearch: (q: string) => void;
    onRadius: (km: number) => void;
    onLang: (l: Lang) => void;
    category?: string | null;              // NEW: active category pill
    onCategory?: (c: string | null) => void; // NEW
  }

Structure (two stacked bars, sticky top):
1. Main bar, background var(--amz-navbar), light text:
   - Wordmark "ReachOut" (Space Grotesk, --terracotta accent on "Out"),
     links to "/".
   - "Deliver to"-style block: t("nav.deliverTo") microcaps over the current
     `near` value (or "Madrid" when near is null) — location pin glyph "◎".
   - Center: the search form — reuse the existing <SearchInput> component
     (import it; do not reimplement) but wrap it so the submit button becomes
     an Amazon-orange square (background var(--terracotta), dark icon).
     SearchInput's props are (value, onChange, onSubmit, lang) — keep the
     existing draft-state pattern: local useState draft synced from prop q
     via useEffect, submit calls onSearch(draft).
   - Right: the radius slider (keep existing 400ms debounce via
     window.setTimeout ref pattern) and the ES/EN lang toggle, restyled
     compactly for the dark bar.
2. Category strip, background var(--amz-navbar-2), height 39px: horizontal
   pills — t("nav.categories.all") plus one pill per category (pharmacy,
   grocery, hardware, electronics, stationery) using t("nav.cat.*") labels
   and the CATEGORY_ICONS glyphs { pharmacy:"⚕", grocery:"⛁", hardware:"⚒",
   electronics:"⚡", stationery:"✎" } imported from ./ShopCard. Active pill =
   white border. Clicking calls onCategory?.(id) or onCategory?.(null) for All.
   When the onCategory prop is absent render the strip inert (no cursor).

All copy via t(); all colors via var(--token); numbers in .mono. Output
TopBar.tsx plus a "TOPBAR" commented CSS section to append to results.css.
```

---

### PROMPT 4 — ShopCard → Amazon product card

```
Rewrite frontend/src/components/ShopCard.tsx as an Amazon search-result card.
Keep the exact existing props { result, pinged, selected, onSelect, lang } and
the existing interaction contract: onClick selects, onMouseEnter selects,
onMouseLeave deselects (map pin highlighting depends on it). Keep exporting
CATEGORY_ICONS.

RankedResult fields available: rank, shop_id, shop_name, category, address,
distance_km, item_name, sku, price, currency, stock_qty, lat, lng — and
OPTIONALLY (after the backend ships them; type via
`RankedResult & { rating?: number; review_count?: number }` locally until
gen-types includes them): rating (0–5 float), review_count (int).

Card layout (horizontal, white bg var(--ink-900), 1px var(--ink-600) border,
var(--shadow-card) on hover, orange 2px outline when selected):
- Left 96px column: category tile — the CATEGORY_ICONS glyph large on a tinted
  circle using color-mix(in srgb, var(--cat-<category>) 15%, white); rank badge
  "#{rank}" top-left in .mono.
- Body:
  - Line 1: item_name as the product title (--navy-line teal, font-ui 16px,
    hover underline — Amazon link style).
  - Line 2 (trust row): IF rating defined → 5-star row (SVG stars, fill
    var(--star-gold), half-star support) + rating value + "(review_count)"
    in --navy-line; ELSE → t("results.noRating") in --sand-dim. Never
    fabricate a rating.
  - Line 3: price — split format Amazon-style: currency symbol and decimals
    superscripted, integer part 21px, ALL in .mono, color var(--price-red).
  - Line 4 (stock badge): stock_qty > 5 → t("results.inStock") in
    var(--stock-green); 1–5 → t("results.onlyNLeft", {n}) in
    var(--stock-amber); (0 never occurs in ranked results today — render
    t("results.outOfStock") in --sand-dim if it ever does.)
  - Line 5: shop_name · formatDistance(distance_km, lang) · address — one
    .microcaps metadata line, --sand-dim. Import formatDistance/formatPrice
    from ../lib/format (formatPrice for aria-label; visual price uses the
    split format).
- Ping badge: when `pinged`, keep the existing "PING" chip (t("results.ping"))
  with the pulsing dot, recolored to var(--terracotta) — top-right corner.
  Pulse must be inside the existing card animation so
  prefers-reduced-motion still kills it via tokens.css.

Output ShopCard.tsx plus a "SHOPCARD" commented CSS section for results.css.
```

---

### PROMPT 5 — ResultsPanel → Amazon results page (sort/filter/pagination)

```
Rewrite frontend/src/components/ResultsPanel.tsx as the left half of a split
screen (the panel itself is width 50vw via .split — don't set width here).
Extend the props:

  interface Props {
    query: UseQueryResult<RankedShops>;
    pingedIds: Set<string>;
    selectedShopId: string | null;
    onSelect: (id: string | null) => void;
    lang: Lang;
    radiusKm: number;
    onWiden: () => void;
    onRetry: () => void;
    sort: "relevance" | "price_asc" | "price_desc" | "distance"; // NEW
    onSort: (s: Props["sort"]) => void;                          // NEW
    category: string | null;                                     // NEW
    onCategory: (c: string | null) => void;                      // NEW
    inStockOnly: boolean;                                        // NEW
    onInStockOnly: (v: boolean) => void;                         // NEW
    page: number;                                                // NEW (1-based)
    onPage: (p: number) => void;                                 // NEW
  }

The three existing states stay behaviorally identical (they are e2e-tested):
- isPending → skeleton cards under a t("results.loading") meta line.
- isError or data.status !== "ok" → the ".results-panel state" error block with
  the verbatim error detail in .mono and a .cta retry button (Amazon-orange now).
- zero results → ".results-panel state" empty block, widen-to-5km .cta.

Results state, new Amazon layout:
- Header row: t("results.count", {n, q}) — n = filtered count — plus a sort
  <select> labeled t("sort.label") with the four t("sort.*") options, value
  from props.sort, onChange → onSort.
- Left rail (180px, inside the panel): t("filter.title"); category checklist
  (same ids/labels/glyphs as the TopBar strip — single-select behaving like
  radio: clicking the active one clears to null → onCategory); an
  "inStockOnly" checkbox (stock_qty > 5 when true) → onInStockOnly.
- Card column: filter client-side (category, inStockOnly), sort client-side
  (relevance = rank asc; price_asc/desc; distance = distance_km asc),
  paginate 10 per page. Render <ShopCard> for the current page slice.
  Client-side is correct here: the API returns the full ranked set for the
  radius; do NOT refetch on sort/filter/page changes.
- Pagination footer: t("page.prev") / numbered buttons / t("page.next"),
  disabled states at the edges, current page in .mono. Reset scroll to the
  panel top on page change (the panel is the scroll container:
  overflow-y auto).
- Keep the generated_at timestamp line (es-ES locale) under the header.

Pure presentation + the local filter/sort/paginate derivation (useMemo) —
NO URL access, NO data fetching in this file; the route owns those.
Output ResultsPanel.tsx plus a "RESULTS PANEL" CSS section for results.css.
```

---

### PROMPT 6 — Results route wiring (URL params for sort/filter/page/region)

```
Rewrite frontend/src/routes/results.tsx to wire the new controls to the URL
(the state of record). Existing pattern to preserve exactly: paramsFromUrl()
reading q/near/lat/lng/radius; two useQuery calls keyed on those params (plus
region now); the all-shops query with staleTime Infinity; usePingSequence keyed
on the data-bearing searchKey; the !enabled → <Navigate to="/"> guard AFTER all
hooks; setParam(key, value) helper writing through setSearchParams.

Add URL params (all optional): sort, category, stock ("1" = in-stock-only),
page (integer, 1-based), region (barrio slug for the map's region selector).
Extend setParam so setting any of category/stock/sort also deletes "page"
(filter changes reset pagination). Add deleteParam(key) for null cases.

Pass through to the new component props:
- TopBar: category + onCategory (writes URL, clears page).
- ResultsPanel: sort/onSort, category/onCategory, inStockOnly/onInStockOnly,
  page/onPage — all URL-backed, defaults: "relevance", null, false, 1.
- MapPanel gets three NEW props: region: string | null,
  onRegion: (r: string | null) => void (URL-backed), and
  networkCount: number (allShops.data?.metadata.shop_count ?? 0).

IMPORTANT: sort/category/stock/page/region must NOT join the searchKey that
drives usePingSequence, and must NOT enter the queryKey of ranked-shops or
shops-geojson (except region IF the API gains a region param later — leave a
one-line comment marking that decision point). Changing them re-renders
locally; it must not refetch or replay pings.

Cold-load rule: a full URL like
/results?q=cargador&near=Chueca&radius=2&sort=price_asc&category=electronics&page=2&lang=en
must reproduce the exact same screen — verify every new control initializes
from URLSearchParams, never from component state.

Output results.tsx only.
```

---

### PROMPT 7 — MapPanel container + overlay (region selector, live indicator)

```
Two deliverables. DO NOT touch any maplibregl code inside MapPanel.tsx's
effects (init, addSource, addLayer, feature-state, popup, fitBounds).

(a) frontend/src/components/MapOverlay.tsx — NEW file, pure presentation:
  interface Props {
    region: string | null;
    onRegion: (r: string | null) => void;
    networkCount: number;
    lang: Lang;
  }
  Absolutely-positioned overlay chrome for the map's top edge (the map panel
  is position:relative):
  - Left: region selector — a <select> (native, dark-styled: background
    var(--amz-navbar), light text) labeled t("map.region"); options:
    t("map.allCity") for null + one option per barrio from
    `import { BARRIOS } from "../data/barrios"` (generated file — import it,
    never inline the list; assume entries expose a display name string).
    onChange → onRegion(value || null).
  - Right: live indicator — a pulsing green dot (CSS animation, killed by
    prefers-reduced-motion) + t("map.live") microcaps +
    t("map.liveShops", { n: networkCount }) in .mono.
  pointer-events: none on the wrapper, auto on the controls, so map pan/zoom
  still works between them.

(b) MapPanel.tsx minimal diff: extend Props with { region: string | null;
  onRegion: (r: string | null) => void; networkCount: number }, and render
  <MapOverlay .../> as a SIBLING of the map container div inside a new
  wrapping <div className="map-panel-wrap"> (the wrapper takes .map-panel's
  flex slot; the map container div keeps className="map-panel" and 100%
  size). One NEW effect is allowed, clearly commented as overlay-owned: when
  `region` changes, look up the barrio's centroid from BARRIOS and call
  mapRef.current?.flyTo({ center: [lng, lat], zoom: 14, duration: 800 }) —
  flyTo is chrome-level camera work, not layer work, so it's within bounds;
  null region → flyTo Madrid center [-3.7038, 40.4168], zoom 13.
  If BARRIOS entries lack centroids, STOP and flag it instead of hardcoding
  coordinates (the generator gen-barrios.ts must then be extended to emit
  {name, lat, lng} from the gazetteer — note this in your output).

(c) CSS: .split becomes a fixed 50vw/50vw grid (grid-template-columns: 1fr
  1fr; height: calc(100vh - <topbar height>)); left column scrolls
  (overflow-y: auto), right column (map) is position: sticky/fixed within
  the grid — always visible, never scrolls away. Mobile (<900px): stack,
  map 40vh on top, results below — flag this breakpoint as a review point.

Output: MapOverlay.tsx, the full modified MapPanel.tsx, and a "SPLIT + MAP
OVERLAY" CSS section for results.css.
```

*(Check before running: `frontend/src/data/barrios.ts` currently exports names
only — extend `frontend/scripts/gen-barrios.ts` to emit `{ name, lat, lng }`
from `reachout/data/gazetteer_madrid.json` first, or Stitch will stop at (b).)*

---

### PROMPT 8 — Landing page → Amazon-style entry (category tiles + how-it-works)

```
Rewrite frontend/src/routes/search.tsx as an Amazon-style landing page, keeping
ALL existing behavior: useLang; BarrioCombobox + "use my location"
(navigator.geolocation, 8s timeout, error copy t("entry.locationDenied"));
submit guard — no query → return, no location → setNeedLocation(true) and show
t("entry.needLocation"); navigate to /results?q=&radius=2&near=|lat+lng&lang.

New structure (light page, var(--ink-800) background):
1. Dark hero band (var(--amz-navbar)): wordmark "ReachOut · Madrid" microcaps,
   t("landing.tagline") as the display headline (Space Grotesk), then the
   search cluster: BarrioCombobox + geo button + SearchInput with the
   Amazon-orange submit — one horizontal bar on desktop, stacked <640px.
   Keep the ES/EN toggle top-right. Keep the existing .entry-net SVG shop
   backdrop (sampled ≤600 dots, viewBox math unchanged) behind the hero,
   dots recolored via var(--navy-line).
2. Category tile row: t("landing.categoriesTitle"); five white cards
   (--shadow-card) — CATEGORY_ICONS glyph large, t("nav.cat.*") label.
   Clicking a tile: if a location is picked, navigate to
   /results?q=<category seed query>&category=<id>&...loc params; seed queries:
   pharmacy→"paracetamol", grocery→"leche", hardware→"tornillos",
   electronics→"cargador", stationery→"cuaderno" (the synthetic inventory is
   Spanish-named — English queries return empty). If no location picked,
   setNeedLocation(true) instead.
3. "How it works" strip: three numbered steps t("landing.how1..3"), each with
   a simple glyph (⌕, ⚡, ✓), horizontal on desktop, stacked mobile.

Output search.tsx plus the full rewritten entry.css.
```

---

### PROMPT 9 — Skeletons, empty & error states restyle

```
Restyle the three non-success states in results.css to match the Amazon look,
without changing ResultsPanel.tsx logic or class names (.results-panel,
.results-panel.state, .skeleton-card, .cta, .error-detail are targeted by e2e
tests — keep them):
- .skeleton-card: white card silhouette of the new ShopCard proportions
  (96px tile + 4 text bars), shimmer via background-position animation
  (auto-killed by the reduced-motion block).
- .results-panel.state: centered, max-width 480px; illustration-free; headline
  in Space Grotesk; .cta = Amazon button (background var(--terracotta), 1px
  var(--terracotta-hot) border, 8px radius, dark text, hover darken).
- .error-detail stays verbatim-mono (--sand-dim on white).
Output: one CSS section replacing the current state styles in results.css.
```

---

### PROMPT 10 — BarrioCombobox + SearchInput restyle

```
Restyle SearchInput.tsx and BarrioCombobox.tsx for the light theme WITHOUT
changing their behavior or public props (SearchInput: value/onChange/onSubmit/
lang/disabled?/autoFocus?; BarrioCombobox: lang/selected/onSelect with
accent-insensitive matching from ../lib/matchBarrios — the .barrio-combobox li
list markup is e2e-tested, keep the structure). White fields, 1px
var(--ink-600) borders, 3px var(--focus-ring) focus ring (Amazon's teal focus
style), 8px radius; the SearchInput submit button becomes the shared orange
square. Output both .tsx files (className/markup-level changes only) + CSS.
```

---

### PROMPT 11 — Pagination-aware ping sequence check *(read-only prompt)*

```
Given hooks/usePingSequence.ts staggers "pinged" ids for the ranked result set
and ResultsPanel now paginates 10-per-page client-side: review whether pinging
ids that are NOT on the current page causes issues (it should not — pinged is
a Set<string> consumed by both the map, which shows all matches, and only the
visible cards). Report: (a) any required change, (b) confirmation the map still
pings all matched shops regardless of the visible page. Output: analysis only,
no code unless a defect is found.
```

---

### PROMPT 12 — Final integration audit

```
Audit the merged result of PROMPTS 1–11 against these invariants and output a
numbered defect list with file:line and a proposed one-line fix each:
1. Zero hex colors outside tokens.css (grep for #[0-9a-fA-F]{3,8} and
   rgb()/hsl() literals in src/ excluding tokens.css).
2. Zero hardcoded user-facing strings in components (every literal shown to
   the user flows through t(); data fields exempt).
3. URL round-trip: enumerate every stateful control (search, radius, sort,
   category filter, stock filter, page, region, lang) and confirm each reads
   from AND writes to URLSearchParams.
4. No new fields consumed from RankedShops that aren't in
   src/types/RankedShops.d.ts (rating/review_count must be optional and
   presence-checked).
5. MapPanel: confirm no maplibregl API call was added/modified except the
   region flyTo effect.
6. TanStack queryKeys unchanged except documented region decision point;
   4xx retry behavior intact.
7. .mono on every rendered number (price, distance, counts, page numbers,
   stock).
8. prefers-reduced-motion kills: skeleton shimmer, ping pulses, live dot,
   region flyTo (flyTo needs an explicit reduced-motion guard —
   window.matchMedia("(prefers-reduced-motion: reduce)") → jumpTo).
9. Both lang values exist for every new i18n key.
10. npm run build (tsc strict) and npx vitest run pass; list any test that
    needs updating because presentation changed (usePingSequence tests must
    NOT need changes — if they do, that's a defect).
```

---

## 4. FLAG-AND-SUGGEST NOTE FOR STITCH (append to every prompt)

```
If any instruction conflicts with something you know about the target
environment, do not silently comply or silently deviate — emit a "FLAGS:"
section at the end of your output. Always evaluate and flag, with a concrete
suggested alternative, at least:
- MOBILE BREAKPOINTS: the 50vw/50vw split and the 180px filter rail assume
  ≥1200px viewports. Propose behavior for 900–1200px (collapse rail into a
  sort/filter dropdown row?) and <900px (map-on-top stack vs. map-as-tab) —
  do not invent one silently.
- FONTS: only Space Grotesk, Inter, and IBM Plex Mono are installed
  (self-hosted @fontsource). If a genuine Amazon look wants Amazon Ember —
  it is not licensed; say so and stick to Inter. Never add a Google Fonts
  <link> (the app is fully self-hosted).
- URL-AS-STATE CONFLICTS: any pattern you'd normally reach for that needs a
  client store (Redux/Zustand/Context), localStorage, or non-URL persistent
  state violates this app's architecture. Flag the pattern, name the URL-param
  alternative you used instead.
```

---

## Appendix — verification loop per prompt

```bash
cd frontend
npm run build         # tsc --noEmit && vite build — must pass
npx vitest run        # 14 existing tests must stay green
# e2e drive (backend + frontend up): see .claude/skills/verify/SKILL.md
```

Selectors the e2e verify skill depends on (do not rename):
`.shop-card`, `.shop-card.pinged`, `.results-meta`, `.results-panel.state`,
`.cta`, `.barrio-combobox li`, `.search-input button`, `.radius-slider input`,
`.lang-toggle`, `.entry-net circle`, `.maplibregl-popup`.
