> **SUPERSEDED by docs/PLAN_V2_PROMPT.md (2026-08-01)** — mislabelled as an API call series (Stitch has no API); keep as a design specification, implemented directly by the coding agent, optionally pasteable into stitch.withgoogle.com for a visual reference.

# STITCH_DASHBOARD.md — Demand Dashboard, Prompt Series for Google Stitch (D1–D5)

*Planning document for Track A's retailer-facing dashboard UI
(`docs/IMPLEMENTATION_PLAN.md` §2 task A10). Hand each PROMPT to Google
Stitch (via API, key placeholder `[STITCH_API_KEY]`, from local `.env`) one
at a time, in order. Same operating rules as `docs/archive/STITCH_FRONTEND.md`
(read its §2 TOOL OVERVIEW: plain-CSS reminder every prompt, one component
per prompt, Stitch generates presentation with explicit props — data wiring
stays in your hands; v0.dev is the drop-in fallback). Depends on the demand
API contract (TASK 74 in `docs/JULES_DEMAND.md`); the shapes are inlined
below so prompts are self-contained.*

## 1. MASTER CONTEXT BLOCK (prepend to every Stitch call)

```
You are generating React 19 + TypeScript 5.7 components for the ReachOut
Demand Dashboard — a retailer-facing analytics screen set. Vite 6,
react-router-dom 7, TanStack Query 5, plain CSS with design tokens
(NO Tailwind, NO CSS-in-JS, NO component library). This is a DATA-DENSE,
NEUTRAL, LIGHT product surface — not the consumer shopping UI. Target tree:

frontend/src/
├── routes/dashboard/
│   ├── login.tsx        magic-link login screen
│   ├── overview.tsx     trending categories overview
│   ├── movers.tsx       rising/falling list
│   └── store.tsx        per-store recommendations
├── components/dashboard/
│   ├── DashShell.tsx    top bar (store name, sign-out) + nav tabs + <Outlet/>
│   ├── TrendTile.tsx    category tile with inline SVG sparkline
│   ├── MoverRow.tsx     one rising/falling row
│   ├── RecCard.tsx      one recommendation card (confidence + caveat)
│   └── dashboard.css    ALL dashboard styles — new token set, see below
├── api/demand.ts        typed fetchers (base /demand/api, Bearer JWT from
│                        Supabase session); ApiError(message, status);
│                        TanStack Query never retries 4xx
└── i18n/strings.ts      ALL UI copy as STRINGS["key"] = { es, en };

dashboard.css token set (create in D1, then reuse by var() only):
  --dash-bg:#fafbfc --dash-panel:#ffffff --dash-line:#e3e6e8
  --dash-ink:#16191c --dash-ink-dim:#5f6b76
  --dash-up:#0a7d33 --dash-down:#b3261e --dash-flat:#5f6b76
  --dash-accent:#0b5fff --dash-warn-bg:#fff8e6 --dash-warn-ink:#7a5a00
  --conf-high:#0a7d33 --conf-medium:#8a6d00 --conf-low:#8a3ffc
  --font-ui / --font-mono: inherit the existing app values.
Numerals are always .mono. Spanish is the default locale, English opt-in.

API shapes (authoritative — do not invent fields; all responses are
schema-validated server-side):
  GET /demand/api/trends
    -> { trends: [{ keyword, category, interest_avg, delta_pct, direction:
         "rising"|"falling"|"flat", rank, confidence: "low"|"medium"|"high",
         series: [{date, value}] }], window_start, window_end }
  GET /demand/api/signals?direction=
    -> { signals: [same row shape minus series] , window_start, window_end }
  GET /demand/api/recommendations?store_id=
    -> { store_id, recommendations: [{ id, headline, body, action:
         "stock_up"|"feature_in_window"|"watch",
         confidence: "low"|"medium"|"high", caveat, created_at }] }
  Auth: Supabase Auth magic-link session; fetchers attach
  Authorization: Bearer <session.access_token>. 401 -> route to /dashboard.

NON-NEGOTIABLE UI RULE: every rendered recommendation and every trend
number carries its confidence chip AND the caveat text as an always-visible
caption (the `caveat` field, verbatim). Never a tooltip, never behind an
info icon, never suppressible. Data here is search-interest, not sales, and
the UI must say so wherever a number could be mistaken for a fact.

Generate ONE component (or the one file asked for) per prompt, presentation
only, props explicit. Plain CSS classes into dashboard.css.
```

## 2. THE PROMPT SERIES

Run in order. After each prompt: paste output into the repo, run
`cd frontend && npm run build && npm test`, fix type errors before
continuing. Append the FLAG-AND-SUGGEST note from `STITCH_FRONTEND.md` §4
to every call.

---

### PROMPT D1 — dashboard.css tokens + DashShell + magic-link login

```
Create three files. (1) frontend/src/components/dashboard/dashboard.css:
the token block from the context (as :root scope .dash-root) plus base
styles: .dash-root full-height light page, .dash-topbar (store name left,
lang toggle + sign-out right, 1px --dash-line bottom border), .dash-tabs
(Overview / Movers / My store; active tab underlined --dash-accent),
.dash-main (max-width 1080px, centered, 24px gutters, single column under
720px). (2) DashShell.tsx: props { storeName: string; onSignOut(): void } —
topbar + tabs (NavLink) + <Outlet/>; no data fetching. (3)
routes/dashboard/login.tsx presentation: centered card, email input +
"Enviar enlace" button, three visual states via props
{ state: "idle"|"sent"|"error"; onSubmit(email: string): void } — "sent"
shows a check-your-inbox message with the submitted email. All copy through
STRINGS keys (dash.login.*, dash.nav.*) with es/en values listed at the top
of your output as a block to merge into i18n/strings.ts. Plain CSS only,
classes in dashboard.css.
```

*Integration (yours, not Stitch's):* wire login to
`supabase.auth.signInWithOtp` and DashShell to the session
(`@supabase/supabase-js` is a new frontend dependency added at this step);
guard `/dashboard/*` routes on session presence.

---

### PROMPT D2 — TrendTile + overview grid

```
Create TrendTile.tsx + styles in dashboard.css. Props: { keyword: string;
category: string | null; interestAvg: number; deltaPct: number; direction:
"rising"|"falling"|"flat"; confidence: "low"|"medium"|"high"; series:
{ date: string; value: number }[]; caveatText: string }. Card: keyword as
title, category as microcaps subtitle, big .mono interest value, delta
badge colored --dash-up/--dash-down/--dash-flat with ▲/▼/– prefix, inline
SVG sparkline (no chart lib: single <polyline>, 120x36 viewBox, stroke
matches the direction color, no axes), a small confidence chip
(text "alta"/"media"/"baja" via STRINGS, background --conf-*at 12% alpha,
text --conf-*), and the caveat as an always-visible caption line at the
card foot in --dash-ink-dim 12px. Then routes/dashboard/overview.tsx
presentation: props { tiles: TrendTileProps[]; windowLabel: string } —
responsive grid (repeat(auto-fill, minmax(240px, 1fr))), window label top
right. New STRINGS keys under dash.overview.*.
```

---

### PROMPT D3 — MoverRow + movers route (rising/falling)

```
Create MoverRow.tsx + styles: a table-like row — rank (.mono, w 2ch),
keyword, category microcaps, delta badge (same visual language as D2),
confidence chip, caveat caption underneath spanning the row. Props mirror
the signals row shape from the context. Then routes/dashboard/movers.tsx
presentation: props { rising: MoverRowProps[]; falling: MoverRowProps[];
windowLabel: string; filter: "all"|"rising"|"falling";
onFilter(f): void } — segmented control (three buttons, active =
--dash-accent), two labeled sections ("En subida" / "En bajada") that the
filter collapses to one. Keyboard accessible: segmented control is
radiogroup with arrow-key support. New STRINGS keys dash.movers.*.
```

---

### PROMPT D4 — RecCard + per-store recommendations route

```
Create RecCard.tsx + styles. Props: { headline: string; body: string;
action: "stock_up"|"feature_in_window"|"watch"; confidence:
"low"|"medium"|"high"; caveat: string; createdAt: string }. Card layout:
action pictogram + microcaps action label (STRINGS dash.action.*:
"Reponer stock" / "Destacar esta semana" / "Observar"), headline bold,
body regular, then a NON-DISMISSIBLE footer strip (background
--dash-warn-bg, text --dash-warn-ink) containing the confidence chip and
the caveat string verbatim. The footer is part of the card's minimum
height — there is no variant without it; do not generate a compact/dense
variant that drops it. Then routes/dashboard/store.tsx presentation: props
{ storeName: string; recs: RecCardProps[]; generatedAt: string } — single
column list, max-width 720px, "Actualizado {generatedAt}" (.mono) header,
plus a permanent page-level note under the header (STRINGS
dash.store.disclaimer): data reflects Madrid search interest, not this
store's sales. New STRINGS keys dash.store.*, dash.action.*, dash.conf.*.
```

---

### PROMPT D5 — skeleton / empty / error states + responsive audit *(audit prompt)*

```
Audit pass over the four dashboard routes; output only diffs/replacement
files. (1) Add skeleton states: TrendTile.skeleton and MoverRow.skeleton
shimmer variants (CSS only, reuse the app's existing shimmer keyframes
pattern), overview shows 6 skeleton tiles while pending, movers 8 rows,
store 3 cards. (2) Empty states: no trends yet -> "Aún no hay datos de esta
semana" + the caveat disclaimer; no recommendations -> "Sin recomendaciones
para tu tienda esta semana". (3) Error state: single retry CTA pattern,
copy via STRINGS dash.error.*. (4) Responsive audit at 360px, 768px,
1080px: tabs collapse to scrollable row, grid to single column, RecCard
footer never truncates the caveat (wrap, don't ellipsize — verify with the
longest ES string). (5) A11y: chips have aria-labels, sparkline has
role="img" + aria-label "tendencia {direction}", segmented control
keyboard-verified. List every class you touched in dashboard.css.
```

## 3. Verification loop per prompt

Same as `STITCH_FRONTEND.md` Appendix: build + vitest after each merge; for
D2–D5 also drive `http://localhost:5173/dashboard` with the repo `verify`
skill recipe (backend up with demand API mounted) and check: caveat caption
visible on every tile/row/card without hover; confidence chip colors meet
WCAG AA on their backgrounds; 401 redirect to login when the session is
absent.
