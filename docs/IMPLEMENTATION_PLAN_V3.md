# IMPLEMENTATION_PLAN_V3 — UI Redesign: Bklit demand charts + ReactBits consumer motion

*Written 2026-08-16. Plan only — no repository edits were made in producing this document.
Execution model is §8. Decisions in this plan were locked with the repo owner in a grilling
session on 2026-08-16 (seven decisions, recorded in §1.1).*

---

## 1. Executive summary

**What changes.** Two workstreams:

- **Part A (demand/retail dashboard):** ECharts is removed entirely. The three charts
  (`TopMoversChart`, `CategoryMixChart`, `StockOutRiskChart`) are re-implemented on
  **Bklit UI** — a shadcn-registry chart library whose components are vendored as source
  into `frontend/src/components/retail/charts/bklit/`. One **new panel** is added:
  `RecommendationsPanel`, consuming `/demand/api/recommendations` (1,541 live rows, zero
  pixels today). `RisingQueriesPanel` stays a non-chart `<ul>` and is only restyled.
  A **provenance eyebrow** is added to every dashboard panel stating its data source
  ("search interest" vs "inventory census") — the design signature of the redesign, and
  a direct answer to the confusion the timeframe toggle caption exists to fight.
- **Part B (consumer):** the three repaint-per-frame keyframes (`shimmer`, `ping-pulse`,
  `breathe`, plus `live-pulse` which shares the fault) are rewritten to compositor-only
  `transform`/`opacity` equivalents. Bundle work: `RetailView` goes behind a lazy
  boundary, `maplibre-gl` gets its own chunk, fonts drop to latin subsets. Two ReactBits
  components — **BlurText** (landing headline) and **ClickSpark** (search-submit
  feedback) — are vendored with locally-added `prefers-reduced-motion` gates.

**What does not change.** Every honesty invariant in §5 of this plan: "Breakout" never a
number, fixture banner, verbatim always-visible caveats, per-segment confidence, no
browser arithmetic, no "searches" axis label, `interest_avg` never a percentage,
"Showing N of M", timeframe refetch scoped to `top_movers`, deterministic picks copy,
frozen token names, two routes, dead `AiAnalystButton`, frozen schemas.

**Architecture decisions.**

- **D11 (successor to D9): Bklit UI, scoped.** Bklit replaces ECharts as the single
  chart-library exception. Vendored source + its runtime deps (`@visx/*`, `d3-*`,
  `motion`, `react-use-measure`) may be imported **only** from files inside
  `src/components/retail/charts/`. Because Bklit's install path requires shadcn/Tailwind,
  D11 also admits **Tailwind v4 utilities-only** (no preflight), with `@source` restricted
  to the charts folder — Tailwind exists solely as Bklit's substrate and is forbidden
  anywhere else. **D9 is retired** the moment `echarts` and `echarts-for-react` leave
  `package.json`.
- **D12: ReactBits, scoped.** Exactly two vendored components (`BlurText`, `ClickSpark`),
  living in `src/components/consumer/reactbits/`, importable only from consumer files.
  Both are patched locally to respect `prefers-reduced-motion` (upstream does not).
  Candidates evaluated and rejected: `ShinyText` (JS-driven `background-position` update
  every frame — exactly the repaint class this redesign removes), `AnimatedContent` and
  `FadeContent` (both require `gsap`, a second animation runtime alongside `motion`).

### 1.1 Locked decisions (grilling session, 2026-08-16)

1. Bklit via scoped shadcn/Tailwind exception (utilities-only, no preflight) — not manual
   vendoring without the CLI, not a full unscoped shadcn init.
2. Scope = 3 chart swaps + rising-queries restyle + **recommendations panel**; signals
   line chart is a phase-2 appendix (§8.4); `/trends` deferred.
3. Chart colors move to **additive** `tokens.css` entries with the same hex values;
   frozen names untouched; no `var()` aliasing between chart tokens and map tokens.
4. `StockOutRiskChart` keeps single flat `#ff9900`; the §3.2 snippet's `LinearGradient`
   is dropped deliberately.
5. ReactBits used surgically (2 components, dependency-light); perf fixes are hand CSS.
6. Both workstreams execute via sub-agent-driven development; Google Jules is reserved
   for the phase-2 signals chart.
7. Ship fixture-first, independent of demand-service deployment; the deploy gap is a
   separately-owned precondition for live data (§7).

---

## 2. Live research findings

Everything in this section was fetched live on 2026-08-16. Where a fact comes from the
pre-verified §3 snippets of the brief instead, it is marked *(snippet)*.

### 2.1 Bklit (bklit.com — fetched live)

- **Not an npm package.** It is a shadcn registry: prerequisite `npx shadcn@latest init`,
  then `npx shadcn@latest add @bklit/bar-chart` (registry
  `"@bklit": "https://ui.bklit.com/r/{name}.json"`; that host 301-redirects to
  `https://bklit.com/r/{name}.json`). Components arrive as **source files in your repo**
  (13 files for bar-chart, targeting `components/charts/`), which means local patches are
  a supported, expected practice — this is load-bearing for two gaps below.
- **Registry items needed:** `@bklit/bar-chart`, `@bklit/pie-chart`, `@bklit/legend`
  (plus auto-pulled `@bklit/chart-context`, `@bklit/chart-animation`, `@bklit/grid`,
  `@bklit/chart-tooltip`, `@bklit/utils`).
- **Runtime deps** (from live registry JSON): `@visx/shape`, `@visx/scale`,
  `@visx/responsive`, `@visx/event`, `@visx/grid`, `@visx/group`, `@visx/pattern`,
  `@visx/gradient` (visx at `4.0.1-alpha.0` pins), `d3-array`, `d3-shape`, `motion`,
  `react-use-measure`.
- **Confirmed APIs** (live docs `/docs/components/bar-chart`, `/docs/components/pie-chart`,
  `/docs/utility/legend`):
  - `BarChart`: `data`, `xDataKey`, `margin`, `orientation: "vertical" | "horizontal"`,
    `animationDuration` (default 1100), `aspectRatio`, `barWidth`, `barGap`, `stacked`.
  - `Bar`: `dataKey`, `fill` (**single static string**), `stroke`, `lineCap`,
    `animate` (default true), `animationType`, `staggerDelay`.
  - `BarXAxis` / `BarYAxis`: label-display props only (`showAllLabels`, `maxLabels`,
    `tickerHalfWidth`).
  - `PieChart`: `data` (`{label, value, color?, fill?}[]`), `size`, `innerRadius` (px,
    0 = solid), `padAngle`, `cornerRadius`, `hoveredIndex`/`onHoverChange`.
    `PieSlice`: `index`, `color`, `fill`, `animate`, `showGlow`, `hoverEffect`.
    `PieCenter`: donut-only center label.
  - `Legend` (`@bklit/legend`): `items: {label, value, color}[]`, `title`, controlled
    hover; **no position prop** — placement is your own layout wrapper.
  - Default palette: CSS variables `--chart-1`…`--chart-5`; `Bar`'s default fill is
    `var(--chart-line-primary)`. Bklit theming is CSS-variable-driven, which is why the
    token unification (decision 3) is low-friction.
- **Gaps confirmed against live registry source** (each answered by a local patch to the
  vendored files, §3.4):
  - (a) **No per-datum bar color.** `Bar.fill` is uniform per series. But Bklit's own
    `BarDepthBack` documents `colorAccessor: (datum, index) => string` ("takes precedence
    over color") — we add the identical prop to the vendored `bar.tsx`. → TopMovers.
  - (b) **No axis max clamp.** Scale domain is hardcoded `[0, maxValue * 1.1]`
    (`nice: true`). We add an optional `domainMax` prop to the vendored `bar-chart.tsx`.
    → StockOutRisk `max: 100`.
  - (c) **No label rotation.** Axis labels are HTML portaled over the chart with
    fade/`maxLabels` crowd control instead. StockOutRisk's `rotate: 30` has no
    equivalent; we accept horizontal labels with `maxLabels` — **this is a deliberate,
    signed-off visual change** (the five category names fit at dashboard column width;
    the rotation existed for ECharts' SVG text, not for a data reason).
  - (d) Legend exists (above) — no need to hand-build one.
  - (e) **No `prefers-reduced-motion` handling anywhere.** Animations are JS-driven via
    `motion` — the `tokens.css:44` CSS kill switch **cannot** reach them. Not a problem
    for us: the dashboard's existing rule is "charts never animate" (D9 wrapper's
    `animation: false`), preserved by passing `animate={false}` / `animationDuration={0}`
    everywhere (§3.5). No JS animation ever starts, so there is nothing to gate.
  - (f) **Root element is `<svg>`** + HTML axis labels via `createPortal`. Like ECharts
    SVG output it has no accessible name of its own → keep the wrapping-div
    `role="img"` + `aria-label` pattern from `EChart.tsx`.

### 2.2 ReactBits (reactbits.dev — fetched live, with one caveat)

- **Caveat to state plainly:** `https://reactbits.dev/get-started/index` and the
  component doc pages are a client-rendered SPA; a plain fetch returns only the page
  title, so the human-facing docs were **not readable** from this environment. The
  machine-facing sources on the same domain were: `https://reactbits.dev/llms.txt`
  (full component catalog + install instructions) and the per-component registry
  endpoints `https://reactbits.dev/r/<Component>-<LANG>-<STYLE>` (full source +
  dependency manifests). All ReactBits facts below come from those live fetches —
  nothing from model memory.
- **Install:** each component ships 4 variants (`JS|TS` × `CSS|TW`);
  `npx shadcn@latest add https://reactbits.dev/r/<Component>-TS-CSS` or
  `npx jsrepo@latest add …`. The **TS-CSS variant needs no Tailwind**, which keeps the
  consumer side clean of the D11 Tailwind exception.
- **BlurText-TS-CSS** (fetched): single file, dep `motion@^12.23.12`. Props:
  `text`, `delay` (ms, default 200), `animateBy: 'words'|'letters'`, `direction`,
  `threshold`, `stepDuration`, `onAnimationComplete`, custom `animationFrom/To`.
  IntersectionObserver, fires once. Inline styles only (no stylesheet).
  **No reduced-motion handling** → local patch required (§4.4).
- **ClickSpark-TS-CSS** (fetched): single file, **zero npm deps**. Canvas + rAF burst on
  click; props `sparkColor`, `sparkSize`, `sparkRadius`, `sparkCount`, `duration`,
  `easing`, `extraScale`. **No reduced-motion handling** → local patch required.
- **Rejected after fetching:** `ShinyText-TS-CSS` (motion dep; drives
  `background-position` from `useAnimationFrame` — a per-frame repaint loop, the exact
  pathology Part B removes), `AnimatedContent-TS-CSS` and `FadeContent-TS-CSS` (both
  `gsap@^3.13` — a second animation runtime for no capability `motion`/CSS lacks here).

### 2.3 Repo verification (facts handed in the brief, checked against disk)

Verified ✓: `options.ts` = 115 lines; `tokens.css` = 46 lines; ECharts 6.1 +
`echarts-for-react` 3.0.6; single import point `EChart.tsx`; no Tailwind, no
`components.json`; `RisingQueriesPanel` non-chart with `limit: 1000` and no confidence
chip; `ChartPanel` contract as described; grid/axis constants as described; netlify.toml
has no demand-service base URL; `usePingSequence` 120ms/2500ms with reduced-motion
short-circuit.

Discrepancies to flag (trust the repo, not the brief):

1. **The frontend lives at `frontend/` beside the `reachout/` git-repo folder**
   (`/Users/rajeshgupta/Desktop/reachout/frontend`), not under `reachout/reachout/`.
   All paths in this plan are relative to `frontend/` unless prefixed.
2. **"D10" is taken.** The brief says name the successor "D9-revised or D10", but the
   repo already uses D10 for *fixture-first* (`ChartPanel.tsx:28`,
   `RetailDashboard.tsx:19`, `CODEBASE_OVERVIEW.md:1149`). The successor is therefore
   **D11**, and ReactBits is **D12** (grep confirms both numbers are free).
3. **`/demand/api/recommendations` requires `store_id` (uuid) and has no fixture
   branch** — `DEMAND_ANALYTICS_SOURCE` gates only `/analytics` (`app.py:777`). The
   recommendations schema (frozen) has **no `generated_from` field**. Consequences in
   §3.7 and §7.
4. The recommendations endpoint sends **no `X-Total-Count` header** (unlike
   rising-queries). The "Showing N of M" rule is honoured by never printing an "of M"
   we don't have; adding the header is a flagged optional backend task (§7).
5. `results.css` also has `live-pulse` (1.6s infinite `box-shadow`) — same
   non-compositor fault as the named three; fixed alongside them.

---

## 3. Part A — file-by-file changes (exact code)

**Honesty note on literalness:** files authored by us are given as complete literal
contents. The *vendored* Bklit/ReactBits files are fetched by the CLI at execution time;
for those, the patches in §3.4/§4.4 specify the exact prop, semantics, and acceptance
test, but the surrounding hunk context is determined against the fetched file. Three
Bklit micro-behaviours are marked **[verify-at-install]** with an acceptance criterion:
row order for horizontal bars (first payload row must render topmost — insert the same
`.reverse()` the ECharts builder used if Bklit draws bottom-up), tooltip `%` suffix
formatting, and the interaction of fixed wrapper height with `aspectRatio`.

### 3.1 Install scaffold (agent A0)

```sh
cd frontend
npx shadcn@latest init        # accept: TypeScript, CSS variables; base color neutral
npx shadcn@latest add @bklit/bar-chart @bklit/pie-chart @bklit/legend
npm uninstall echarts echarts-for-react
```

`components.json` (full file — written before running `add`, so the registry targets the
contained folder):

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "src/components/retail/charts/bklit/bklit.css",
    "baseColor": "neutral",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components/retail/charts/bklit",
    "utils": "@/components/retail/charts/bklit/lib/utils",
    "ui": "@/components/retail/charts/bklit/ui",
    "lib": "@/components/retail/charts/bklit/lib",
    "hooks": "@/components/retail/charts/bklit/hooks"
  },
  "registries": {
    "@bklit": "https://ui.bklit.com/r/{name}.json"
  }
}
```

`tsconfig.json` — add path alias (diff):

```diff
   "compilerOptions": {
+    "baseUrl": ".",
+    "paths": { "@/*": ["src/*"] },
```

`vite.config.ts` (full replacement — also carries Part B's chunking, §4.2):

```ts
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          // maplibre is ~a third of today's bundle and only /results uses it.
          if (id.includes("node_modules/maplibre-gl")) return "maplibre";
        },
      },
    },
  },
});
```

New dev deps: `tailwindcss`, `@tailwindcss/vite`. New runtime deps: whatever the
registry writes (the `@visx/*` set, `d3-array`, `d3-shape`, `motion`,
`react-use-measure`, `clsx`, `tailwind-merge`) — **quote `package.json` after the CLI
runs rather than hand-writing versions;** the registry pins visx at `4.0.1-alpha.0`.

`src/components/retail/charts/bklit/bklit.css` (full file). Utilities-only: **no
preflight import**, so no global reset touches consumer CSS. `@source` restricts
class scanning to the charts tree. The `--chart-*` custom properties Bklit themes
against are defined here from the D11 tokens:

```css
/* D11: Tailwind exists in this file's scope ONLY as Bklit's substrate.
 * No preflight — consumer CSS must never feel this file. */
@layer theme, utilities;
@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/utilities.css" layer(utilities);
@source "../";

.chart-panel {
  /* Bklit's own theming hooks, fed from tokens.css (D11 additions). */
  --chart-line-primary: var(--chart-risk);
  --chart-1: var(--chart-cat-1);
  --chart-2: var(--chart-cat-2);
  --chart-3: var(--chart-cat-3);
  --chart-4: var(--chart-cat-4);
  --chart-5: var(--chart-cat-5);
}
```

### 3.2 `src/styles/tokens.css` — additive diff (frozen names untouched)

```diff
   --amz-navbar: #131921;
   --amz-navbar-2: #232f3e;
   --focus-ring: #007185;
   --shadow-card: 0 2px 5px rgba(15, 17, 17, 0.15);
+
+  /* Chart tokens (D11). Literal hex on purpose — never var() aliases of the
+   * frozen map tokens above, so a chart repaint can never silently repaint
+   * the map. Values are byte-identical to what the charts drew before the
+   * Bklit migration, so the contrast figures in this header carry over
+   * unchanged. --chart-risk (#ff9900) is a non-text graphic fill, judged
+   * under the 3:1 graphics rule, and is the same value it has always been.
+   * --chart-cat-1..5 intentionally match the --cat-* values so a category
+   * is the same colour in the pie as on the map — a visual rhyme, not a
+   * runtime coupling. */
+  --chart-rising: #007600;
+  --chart-falling: #b12704;
+  --chart-flat: #565959;
+  --chart-risk: #ff9900;
+  --chart-grid: #eaeded;
+  --chart-axis-text: #565959;
+  --chart-cat-1: #217a4b;
+  --chart-cat-2: #5a7d0e;
+  --chart-cat-3: #b05a1e;
+  --chart-cat-4: #0f6e9e;
+  --chart-cat-5: #8b3fd1;
 }
```

### 3.3 `src/components/retail/charts/options.ts` — full replacement

Same file, same architecture (pure builders, zero arithmetic, tested with literal
payload numbers), new render-config shape:

```ts
/**
 * Pure builders: an analytics segment's `points` in, a Bklit-ready view out.
 *
 * These functions contain NO arithmetic. Every value they hand the charts is
 * a field the demand service already computed and validated against
 * `analytics_response.schema.json` — `delta_pct`, `share_pct`, `risk_pct`.
 * If a chart ever needs a number the payload does not carry, the schema
 * changes and the server computes it; a percentage the browser worked out is
 * a number nobody validated.
 *
 * Formatting is the one thing allowed here — a `%` suffix on a label is
 * presentation, not derivation.
 */
import type { AnalyticsResponse } from "../../../types/AnalyticsResponse";

type Segments = AnalyticsResponse["segments"];
export type TopMoverPoint = Segments["top_movers"]["points"][number];
export type CategoryMixPoint = Segments["category_mix"]["points"][number];
export type StockOutRiskPoint = Segments["stock_out_risk"]["points"][number];

/** Direction is the server's word, so the colour follows it, not the sign. */
export const DIRECTION_FILL: Record<TopMoverPoint["direction"], string> = {
  rising: "var(--chart-rising)",
  falling: "var(--chart-falling)",
  flat: "var(--chart-flat)",
};

export interface TopMoversView {
  data: { keyword: string; delta_pct: number; direction: TopMoverPoint["direction"] }[];
  /** Fed to the vendored Bar's colorAccessor (D11 patch P1). */
  colorAccessor: (d: { direction: TopMoverPoint["direction"] }) => string;
}

/**
 * Top movers: one horizontal bar per keyword, length = `delta_pct`.
 * Horizontal because the labels are Spanish search phrases; rotated vertical
 * labels would be unreadable at the width the dashboard column allows.
 */
export function topMoversView(points: TopMoverPoint[]): TopMoversView {
  return {
    // Payload order is preserved; whether Bklit needs a reverse() to draw the
    // first row topmost is [verify-at-install] — order only, never re-ranked.
    data: points.map((p) => ({
      keyword: p.keyword,
      delta_pct: p.delta_pct,
      direction: p.direction,
    })),
    colorAccessor: (d) => DIRECTION_FILL[d.direction],
  };
}

export interface CategoryMixView {
  /** Doubles as PieChart `data` and Legend `items`. */
  data: { label: string; value: number; color: string }[];
}

/**
 * Category mix: a donut of `share_pct`. The server guarantees the shares;
 * this does not normalise them, so if they do not sum to 100 the chart shows
 * that rather than hiding it behind a rescale. Colour is positional, exactly
 * as the ECharts default palette was.
 */
const PIE_PALETTE = [
  "var(--chart-cat-1)",
  "var(--chart-cat-2)",
  "var(--chart-cat-3)",
  "var(--chart-cat-4)",
  "var(--chart-cat-5)",
];

export function categoryMixView(points: CategoryMixPoint[]): CategoryMixView {
  return {
    data: points.map((p, i) => ({
      label: p.category,
      value: p.share_pct,
      color: PIE_PALETTE[i % PIE_PALETTE.length],
    })),
  };
}

export interface StockOutRiskView {
  data: { category: string; risk_pct: number }[];
  fill: string;
  /** Fed to the vendored BarChart's domainMax (D11 patch P2). The axis is
   * pinned to 100 because risk_pct is a share of certainty, and a bar that
   * fills a rescaled axis would read as more certain than it is. */
  domainMax: 100;
}

/** Stock-out risk: one vertical bar per category, height = `risk_pct`. */
export function stockOutRiskView(points: StockOutRiskPoint[]): StockOutRiskView {
  return {
    data: points.map((p) => ({ category: p.category, risk_pct: p.risk_pct })),
    fill: "var(--chart-risk)",
    domainMax: 100,
  };
}
```

### 3.4 Vendored Bklit patches (agent A1; against fetched source)

- **P1 — `bklit/bar.tsx`:** add `colorAccessor?: (datum: Record<string, unknown>, index: number) => string`
  to `BarProps`; wherever a `<motion.rect>`/`<rect>` receives `fill={fill}`, change to
  `fill={colorAccessor ? colorAccessor(datum, index) : fill}`. Mirrors the API Bklit
  itself documents on `BarDepthBack` ("takes precedence over `color`").
  *Acceptance:* a 3-row payload with directions rising/falling/flat renders three
  distinct computed fills.
- **P2 — `bklit/bar-chart.tsx`:** add `domainMax?: number` to `BarChartProps`; scale
  domain becomes `[0, domainMax ?? maxValue * 1.1]`, and when `domainMax` is set, pass
  `nice: false` so the pinned top stays exactly 100.
  *Acceptance:* with `domainMax={100}` and max datum 40, the top gridline/tick is 100.
- **P3 — provenance comment:** each patched file gets a one-line header comment
  `/* D11 local patch P<n> — see docs/IMPLEMENTATION_PLAN_V3.md §3.4 */` so a future
  registry re-add doesn't silently clobber the patches.

### 3.5 `src/components/retail/charts/BklitFrame.tsx` — full file (replaces `EChart.tsx`)

```tsx
/**
 * The ONLY entry to the chart library (D11, successor to D9's EChart.tsx).
 *
 * Bklit components are vendored source under ./bklit/, and reversing D11 must
 * be a rewrite of this folder and nothing else — so no sibling imports from
 * ./bklit/ except the chart components beside this file, and nothing outside
 * components/retail/charts/ imports any of it.
 *
 * It preserves the two behaviours every panel needs identically, carried
 * over from the ECharts wrapper it replaces:
 *
 * 1. **Charts never animate.** A dashboard that animates on every refetch
 *    draws the eye to motion rather than to the number. Bklit's animations
 *    are JS-driven (motion), so the tokens.css reduced-motion kill switch
 *    cannot reach them — instead, every chart beside this file passes
 *    `animate={false}` / `animationDuration={0}`, and the containment test
 *    greps for it (charts.containment.test.ts).
 * 2. **An accessible name.** Bklit renders an <svg> plus portaled HTML
 *    labels, none of which carries a name — this div is the img.
 */
import type { ReactNode } from "react";
import "./bklit/bklit.css";

export interface BklitFrameProps {
  /** Accessible name — an unlabelled SVG chart reads as nothing. */
  ariaLabel: string;
  height?: number;
  children: ReactNode;
}

export default function BklitFrame({ ariaLabel, height = 240, children }: BklitFrameProps) {
  return (
    <div className="bklit-frame" role="img" aria-label={ariaLabel} style={{ height, width: "100%" }}>
      {children}
    </div>
  );
}
```

### 3.6 The three chart components — full files

`TopMoversChart.tsx`:

```tsx
import { t } from "../../../i18n/strings";
import type { Lang } from "../../../i18n/strings";
import ChartPanel from "./ChartPanel";
import BklitFrame from "./BklitFrame";
import { BarChart, Bar, BarYAxis, Grid, ChartTooltip } from "./bklit";
import { topMoversView } from "./options";
import type { TopMoverPoint } from "./options";

/** S1 metric 1 — which Madrid search terms moved, and by how much. */
export default function TopMoversChart({
  lang, confidence, caveat, points,
}: {
  lang: Lang;
  confidence: "low" | "medium" | "high";
  caveat: string;
  points: TopMoverPoint[];
}) {
  const title = t(lang, "retail.chart.topMovers");
  const view = topMoversView(points);
  return (
    <ChartPanel lang={lang} title={title} eyebrow={t(lang, "retail.provenance.search")}
      confidence={confidence} caveat={caveat} isEmpty={points.length === 0}>
      <BklitFrame ariaLabel={title}>
        <BarChart data={view.data} xDataKey="keyword" orientation="horizontal"
          margin={{ top: 8, right: 16, bottom: 8, left: 80 }} animationDuration={0}>
          <Grid horizontal={false} vertical fadeVertical />
          <Bar dataKey="delta_pct" animate={false} lineCap={4}
            colorAccessor={view.colorAccessor} />
          <BarYAxis showAllLabels />
          <ChartTooltip showCrosshair={false} />
        </BarChart>
      </BklitFrame>
    </ChartPanel>
  );
}
```

`CategoryMixChart.tsx` (donut geometry: wrapper height 240 → `size={200}`; the old
ECharts radii `["45%","70%"]` are a 0.64 inner/outer ratio, so `innerRadius={64}`
against the 100px outer radius — layout constants, not data arithmetic):

```tsx
import { t } from "../../../i18n/strings";
import type { Lang } from "../../../i18n/strings";
import ChartPanel from "./ChartPanel";
import BklitFrame from "./BklitFrame";
import { PieChart, PieSlice, Legend } from "./bklit";
import { categoryMixView } from "./options";
import type { CategoryMixPoint } from "./options";

/** S1 metric 2 — how the shelves split across categories. */
export default function CategoryMixChart({
  lang, confidence, caveat, points,
}: {
  lang: Lang;
  confidence: "low" | "medium" | "high";
  caveat: string;
  points: CategoryMixPoint[];
}) {
  const title = t(lang, "retail.chart.categoryMix");
  const view = categoryMixView(points);
  return (
    <ChartPanel lang={lang} title={title} eyebrow={t(lang, "retail.provenance.inventory")}
      confidence={confidence} caveat={caveat} isEmpty={points.length === 0}>
      <BklitFrame ariaLabel={title}>
        {/* No PieCenter on purpose: the ECharts donut had labels off and no
            centre figure, and inventing a "Total" of share percentages would
            be browser arithmetic. */}
        <PieChart data={view.data} size={200} innerRadius={64}>
          {view.data.map((item, index) => (
            <PieSlice key={item.label} index={index} animate={false} />
          ))}
        </PieChart>
      </BklitFrame>
      {/* Legend below the chart, as before. Bklit's Legend has no position
          prop; placement is this flow-layout wrapper. */}
      <Legend items={view.data} className="chart-legend" />
    </ChartPanel>
  );
}
```

`StockOutRiskChart.tsx` (flat fill per decision 4 — the §3.2 snippet's
`LinearGradient` is deliberately not used):

```tsx
import { t } from "../../../i18n/strings";
import type { Lang } from "../../../i18n/strings";
import ChartPanel from "./ChartPanel";
import BklitFrame from "./BklitFrame";
import { BarChart, Bar, BarXAxis, Grid, ChartTooltip } from "./bklit";
import { stockOutRiskView } from "./options";
import type { StockOutRiskPoint } from "./options";

/** S1 metric 3 — the share of each category's products running low. */
export default function StockOutRiskChart({
  lang, confidence, caveat, points,
}: {
  lang: Lang;
  confidence: "low" | "medium" | "high";
  caveat: string;
  points: StockOutRiskPoint[];
}) {
  const title = t(lang, "retail.chart.stockOutRisk");
  const view = stockOutRiskView(points);
  return (
    <ChartPanel lang={lang} title={title} eyebrow={t(lang, "retail.provenance.inventory")}
      confidence={confidence} caveat={caveat} isEmpty={points.length === 0}>
      <BklitFrame ariaLabel={title}>
        <BarChart data={view.data} xDataKey="category" domainMax={view.domainMax}
          margin={{ top: 16, right: 16, bottom: 8, left: 8 }} animationDuration={0}>
          <Grid horizontal />
          <Bar dataKey="risk_pct" animate={false} fill={view.fill} lineCap={4} />
          <BarXAxis showAllLabels />
          <ChartTooltip />
        </BarChart>
      </BklitFrame>
    </ChartPanel>
  );
}
```

`ChartPanel.tsx` — one additive prop; chip/caveat contract untouched (diff):

```diff
 export interface ChartPanelProps {
   lang: Lang;
   title: string;
+  /** Provenance eyebrow (D11 redesign): one microcaps line naming the data
+   * source — "search interest" vs "inventory census". Structure encoding
+   * truth: it marks, per panel, which half the timeframe toggle can touch. */
+  eyebrow?: string;
   confidence?: Confidence;
   caveat: string;
   /** Empty `points` renders the empty state instead of the chart. */
   isEmpty: boolean;
   children: ReactNode;
 }

 export default function ChartPanel({
-  lang, title, confidence, caveat, isEmpty, children,
+  lang, title, eyebrow, confidence, caveat, isEmpty, children,
 }: ChartPanelProps) {
   return (
     <section className="chart-panel">
+      {eyebrow && <p className="chart-panel__eyebrow microcaps">{eyebrow}</p>}
       <header className="chart-panel__head">
```

### 3.7 `RecommendationsPanel` — new panel (full file) + fetcher + backend prerequisite

`src/api/client.ts` — additive (after `fetchRisingQueries`):

```ts
import type { RecommendationsResponse } from "../types/RecommendationsResponse";

/**
 * `store_id` is REQUIRED by the endpoint and its frozen schema. The dashboard
 * is store-agnostic today, so the id comes from the environment; the fallback
 * uuid matches the committed fixture's own store id, so a build with no env
 * var set behaves exactly like the analytics fixture path does.
 */
const DEMAND_STORE_ID =
  import.meta.env.VITE_DEMAND_STORE_ID ?? "6f1f8f2a-0000-4000-8000-recsfixture0"; // ← the fixture file's uuid

export async function fetchRecommendations(limit = 500): Promise<RecommendationsResponse> {
  const usp = new URLSearchParams({ store_id: DEMAND_STORE_ID, limit: String(limit) });
  const res = await fetch(`${DEMAND_API_BASE}/demand/api/recommendations?${usp.toString()}`);
  if (!res.ok) {
    throw new ApiError(`GET /demand/api/recommendations failed: ${res.status}`, res.status);
  }
  return res.json();
}
```

*(The literal fallback uuid above must equal the one written into the fixture file —
the backend task below mints it; sub-agent A3 substitutes the real value.)*

`src/components/retail/RecommendationsPanel.tsx` — full file:

```tsx
import { useQuery } from "@tanstack/react-query";

import { fetchRecommendations } from "../../api/client";
import { t } from "../../i18n/strings";
import type { Lang } from "../../i18n/strings";
import ChartPanel from "./charts/ChartPanel";
import type { RecommendationsResponse } from "../../types/RecommendationsResponse";

type Recommendation = RecommendationsResponse["recommendations"][number];

const ACTION_KEY = {
  stock_up: "retail.recommendations.action.stockUp",
  feature_in_window: "retail.recommendations.action.feature",
  watch: "retail.recommendations.action.watch",
} as const;

/**
 * The most actionable data in the system, on screen for the first time:
 * `/demand/api/recommendations`, until now 1,541 rows feeding zero pixels.
 *
 * Honesty rules, inherited from the folder it sits beside:
 * - Confidence is PER ROW (the schema carries it per recommendation), so
 *   each card wears its own chip — never one badge for the panel.
 * - Every distinct `caveat` string in the payload is printed verbatim in the
 *   panel footer. Today the canonical text is one string; if the server ever
 *   sends two, both appear, because deduplication may drop repetition but
 *   must never drop a sentence the backend approved.
 * - `headline`/`body` are server text, shown as sent, never translated.
 * - The count line states how many rows are shown. The endpoint sends no
 *   X-Total-Count, so no "of N" is invented (an optional backend task adds
 *   the header; the copy upgrades to shownPartial only when it exists).
 */
export default function RecommendationsPanel({ lang }: { lang: Lang }) {
  const recs = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => fetchRecommendations(),
  });

  const title = t(lang, "retail.chart.recommendations");

  if (recs.isPending) {
    return (
      <ChartPanel lang={lang} title={title} caveat="" isEmpty={false}>
        <p className="retail-dash__state">{t(lang, "retail.loading")}</p>
      </ChartPanel>
    );
  }

  if (recs.isError) {
    return (
      <ChartPanel lang={lang} title={title} caveat="" isEmpty={false}>
        <p className="retail-dash__state retail-dash__state--error" role="alert">
          {t(lang, "retail.loadFailed")}
        </p>
      </ChartPanel>
    );
  }

  const rows = recs.data.recommendations;
  const caveats = [...new Set(rows.map((r) => r.caveat))].join(" ");

  return (
    <ChartPanel lang={lang} title={title} eyebrow={t(lang, "retail.provenance.search")}
      caveat={caveats} isEmpty={rows.length === 0}>
      <p className="recommendations__count-line">
        {t(lang, "retail.recommendations.shown", { count: rows.length })}
      </p>
      <ul className="recommendations__list">
        {rows.map((r: Recommendation) => (
          <li key={r.id} className={`recommendations__row recommendations__row--${r.action}`}>
            <div className="recommendations__row-head">
              <span className="recommendations__action microcaps">
                {t(lang, ACTION_KEY[r.action])}
              </span>
              <span className={`chart-panel__chip chart-panel__chip--${r.confidence}`}>
                {t(lang, "retail.confidenceLabel", {
                  level: t(lang, `retail.confidence.${r.confidence}` as const),
                })}
              </span>
            </div>
            <p className="recommendations__headline">{r.headline}</p>
            <p className="recommendations__body">{r.body}</p>
          </li>
        ))}
      </ul>
    </ChartPanel>
  );
}
```

*(Empty-caveat note: the pending/error states pass `caveat=""` because no payload has
arrived — there is no server sentence to print yet, and inventing one client-side is the
violation the rule exists to stop. Once data exists, the server strings render.)*

`RetailDashboard.tsx` — additive diff (panel joins the grid; analytics banner already
covers the dashboard):

```diff
 import RisingQueriesPanel from "./RisingQueriesPanel";
+import RecommendationsPanel from "./RecommendationsPanel";
@@
         <StockOutRiskChart
           lang={lang}
           confidence={segments.stock_out_risk.confidence}
           caveat={caveat}
           points={segments.stock_out_risk.points}
         />
         <RisingQueriesPanel lang={lang} />
+        <RecommendationsPanel lang={lang} />
       </div>
```

`src/i18n/strings.ts` — additive keys (ES first, as the file does):

```ts
"retail.chart.recommendations": { es: "Recomendaciones para tu tienda", en: "Recommendations for your shop" },
"retail.recommendations.shown": { es: "Mostrando {count} recomendaciones.", en: "Showing {count} recommendations." },
"retail.recommendations.action.stockUp": { es: "Reponer", en: "Stock up" },
"retail.recommendations.action.feature": { es: "Destacar esta semana", en: "Feature this window" },
"retail.recommendations.action.watch": { es: "Vigilar", en: "Watch" },
"retail.provenance.search": { es: "Interés de búsqueda · Madrid", en: "Search interest · Madrid" },
"retail.provenance.inventory": { es: "Censo de inventario · esta tienda", en: "Inventory census · this shop" },
```

**Backend prerequisite (demand service — separate task, flagged not worked-around):**

- `demand/api/fixtures/recommendations_convenience_store.json` — a committed fixture,
  schema-valid against the frozen `recommendations_response.schema.json`, with its own
  store uuid and ~12 rows spanning all three actions and all three confidence levels
  (so the panel's per-row chips exercise the full range), every row carrying the
  canonical caveat.
- `demand/api/app.py` — `get_recommendations` gains the same
  `DEMAND_ANALYTICS_SOURCE=fixture|live` branch `/analytics` has (`app.py:777`): fixture
  mode serves the committed file verbatim (schema-validated on the way out), live mode
  keeps today's Supabase path. **Same env var on purpose**: the frozen recommendations
  schema has no `generated_from` field, so the dashboard-level practice-data banner
  (driven by the analytics response) is the fixture disclosure for this panel too — that
  is only truthful if one switch drives both endpoints.
- Optional: add `X-Total-Count` to the live branch; the panel's copy upgrades to
  "Showing N of M" only when the header exists.

### 3.8 Dashboard chrome (frontend-design pass) — `retail.css` additions

The dashboard already owns a strong identity (Amazon-style tokens, Space Grotesk
display, IBM Plex Mono data). The redesign spends its one deliberate risk on the
**provenance eyebrow**: a mono microcaps line over every panel that says where the
numbers come from — which, on this dashboard, is the difference between "Madrid is
searching for this" and "your shelves hold this". Everything else stays quiet: existing
type scale, existing card shadow, hairline dividers.

```css
/* Provenance eyebrow (D11 redesign): mono microcaps + hairline. Encodes the
 * search-signal vs inventory-census split the timeframe caption describes. */
.chart-panel__eyebrow {
  color: var(--sand-dim);
  border-bottom: 1px solid var(--ink-700);
  padding-bottom: 6px;
  margin: 0 0 10px;
}

.chart-legend { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 8px; }

.recommendations__count-line { color: var(--sand-dim); font-size: 12px; margin: 0 0 8px; }
.recommendations__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; max-height: 420px; overflow-y: auto; }
.recommendations__row { border: 1px solid var(--ink-600); border-left-width: 3px; border-radius: 6px; padding: 10px 12px; background: var(--ink-800); }
.recommendations__row--stock_up { border-left-color: var(--chart-rising); }
.recommendations__row--feature_in_window { border-left-color: var(--chart-risk); }
.recommendations__row--watch { border-left-color: var(--chart-flat); }
.recommendations__row-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.recommendations__action { color: var(--sand-dim); }
.recommendations__headline { font-family: var(--font-display); font-weight: 600; font-size: 14px; margin: 6px 0 2px; }
.recommendations__body { font-size: 13px; color: var(--sand); margin: 0; }
```

(The left-border action colours reuse the D11 chart tokens: rising-green for
"stock up", the risk amber for "feature this window", flat grey for "watch" — the same
vocabulary the charts speak, no new colours, so no new contrast math; borders are
non-text graphics against `--ink-800`.)

`charts/README.md` and the folder's containment command are updated by agent A2
(§6 test plan) — grep target changes from `echarts` to the bklit import set.

---

## 4. Part B — consumer frontend (exact code)

### 4.1 Compositor rewrites (hand CSS — no library, per decision 5)

`results.css` — skeleton shimmer. The sheen becomes a translated overlay instead of a
`background-position` sweep. Needs one markup change (the sheen element):

`ResultsPanel.tsx` diff (loading branch):

```diff
-        {Array.from({ length: 5 }, (_, i) => <div key={i} className="skeleton-card" />)}
+        {Array.from({ length: 5 }, (_, i) => (
+          <div key={i} className="skeleton-card"><span className="skeleton-card__sheen" aria-hidden="true" /></div>
+        ))}
```

`results.css` diff:

```diff
 .skeleton-card {
   position: relative; height: 124px; border-radius: 8px; margin: 0 12px 8px;
   border: 1px solid var(--ink-600); overflow: hidden;
-  /* shimmer sweeps behind the solid tile/bar silhouettes */
-  background: linear-gradient(100deg, var(--ink-900) 40%, var(--ink-700) 50%, var(--ink-900) 60%);
-  background-size: 200% 100%; animation: shimmer 1.4s infinite linear;
+  background: var(--ink-900);
 }
+/* The sheen is its own element moved with transform — compositor-only, no
+ * repaint per frame. The reduced-motion kill switch in tokens.css stops it
+ * like any other CSS animation. */
+.skeleton-card__sheen {
+  position: absolute; inset: 0; z-index: 1;
+  background: linear-gradient(100deg, transparent 40%, var(--ink-700) 50%, transparent 60%);
+  transform: translateX(-100%); will-change: transform;
+  animation: sheen 1.4s infinite linear;
+}
+@keyframes sheen { to { transform: translateX(100%); } }
@@
-@keyframes shimmer { to { background-position: -200% 0; } }
```

*(`.skeleton-card::before/::after` silhouettes are untouched; the sheen `z-index: 1`
sweeps over them as the old background swept behind — a visible-but-equivalent pass,
called out for review.)*

`results.css` — ping ring (replaces the `box-shadow` pulse):

```diff
-.shop-card.pinged .ping-dot { animation: ping-pulse 0.4s ease-out 3; }
-@keyframes ping-pulse { 50% { box-shadow: 0 0 0 5px color-mix(in srgb, var(--terracotta) 35%, transparent); } }
+.shop-card.pinged .ping-dot { position: relative; }
+.shop-card.pinged .ping-dot::after {
+  content: ""; position: absolute; inset: -2px; border-radius: 50%;
+  border: 2px solid color-mix(in srgb, var(--terracotta) 55%, transparent);
+  opacity: 0; will-change: transform, opacity;
+  animation: ping-ring 0.4s ease-out 3;
+}
+@keyframes ping-ring {
+  0% { transform: scale(0.6); opacity: 0.8; }
+  100% { transform: scale(1.9); opacity: 0; }
+}
```

`results.css` — user-dot breathe and the live-pulse dot get the same ring treatment
(each currently animates `box-shadow`):

```diff
-  animation: breathe 2s ease-in-out infinite;
+  position: relative;
 }
-@keyframes breathe { 50% { box-shadow: 0 0 0 9px color-mix(in srgb, var(--terracotta) 8%, transparent); } }
+.user-dot::after {
+  content: ""; position: absolute; inset: -3px; border-radius: 50%;
+  border: 3px solid color-mix(in srgb, var(--terracotta) 30%, transparent);
+  will-change: transform, opacity;
+  animation: breathe-ring 2s ease-in-out infinite;
+}
+@keyframes breathe-ring {
+  0%, 100% { transform: scale(1); opacity: 0.6; }
+  50% { transform: scale(1.7); opacity: 0; }
+}
```

```diff
-  background: var(--stock-green); animation: live-pulse 1.6s ease-in-out infinite;
+  background: var(--stock-green); position: relative;
 }
-@keyframes live-pulse {
-  50% { box-shadow: 0 0 0 5px color-mix(in srgb, var(--stock-green) 30%, transparent); }
-}
+/* ::after ring, same technique as breathe-ring, colour --stock-green 30%,
+ * animation live-ring 1.6s ease-in-out infinite, scale 1 → 1.8 fade-out. */
```

State-swap crossfade (error/empty replace the panel wholesale today — a 200ms
opacity-in on mount keeps the swap but softens it; compositor-only; killed by the
reduced-motion switch):

```css
.results-panel { animation: panel-fade 200ms ease-out; }
@keyframes panel-fade { from { opacity: 0; } }
```

Smooth page-change scroll, gated (`ResultsPanel.tsx` diff):

```diff
   useEffect(() => {
-    panelRef.current?.scrollTo({ top: 0 });
+    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
+    panelRef.current?.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
   }, [page]);
```

**PicksRail:** stays exactly as it is — `null` on loading/error/empty, no skeleton, no
reserved space (documented deliberate; the constraint holds). The layout-shift fix is
**positional**: `search.tsx` moves `<PicksRail …/>` to the last section of the landing
column, after the how-it-works strip, so its late arrival extends the page downward
instead of pushing the search box; arrival is softened with a transform/opacity
entrance the kill switch can stop:

```css
.picks { animation: picks-in 300ms ease-out; }
@keyframes picks-in { from { opacity: 0; transform: translateY(8px); } }
```

**Pagination:** flagged, not rebuilt. 10 results/page against radius-bounded result
sets means single-digit page counts; unwindowed buttons are fine at this scale, and
ReactBits offers no pagination primitive worth the dependency. Revisit only if result
sets grow an order of magnitude.

**chat.css / net-pulse:** already compositor-friendly (`translateX`/`opacity`) — no change.

### 4.2 Bundle (agent B2)

`src/shell/AppShell.tsx` — lazy retail boundary (diff):

```diff
-import type { ReactNode } from "react";
+import { lazy, Suspense } from "react";
+import type { ReactNode } from "react";

-import RetailView from "../components/retail/RetailView";
 import ModeToggle from "./ModeToggle";
 import { useMode } from "./useMode";
 import "./shell.css";
+
+// Retail is a different audience on a different visit: consumer landing and
+// results must never download the chart stack (D11) or its deps.
+const RetailView = lazy(() => import("../components/retail/RetailView"));
@@
       <main className="app-shell__body">
-        {mode === "retail" ? <RetailView /> : children}
+        {mode === "retail" ? (
+          <Suspense fallback={<p className="retail-dash__state" aria-busy="true">Cargando… / Loading…</p>}>
+            <RetailView />
+          </Suspense>
+        ) : (
+          children
+        )}
       </main>
```

`vite.config.ts`: already quoted in §3.1 (`manualChunks` splits `maplibre-gl`; the lazy
boundary gives the bklit+visx+motion stack its own chunk automatically).

`src/main.tsx` — font subsetting (diff). @fontsource v5 ships per-subset CSS; the
latin-only imports drop the cyrillic/cyrillic-ext/greek/vietnamese `@font-face` blocks:

```diff
-import "@fontsource/space-grotesk/600.css";
-import "@fontsource/ibm-plex-mono/500.css";
-import "@fontsource/inter/400.css";
-import "@fontsource/inter/500.css";
+import "@fontsource/space-grotesk/latin-600.css";
+import "@fontsource/ibm-plex-mono/latin-500.css";
+import "@fontsource/inter/latin-400.css";
+import "@fontsource/inter/latin-500.css";
```

*(Spanish needs latin only — ñ/á/é/í/ó/ú are all in the latin subset. The weights
imported are exactly the weights `tokens.css` uses: display 600, mono 500, UI 400/500.)*

### 4.3 ReactBits integration (agent B3) — D12

Vendor (TS-CSS variants):

```sh
npx shadcn@latest add https://reactbits.dev/r/BlurText-TS-CSS
npx shadcn@latest add https://reactbits.dev/r/ClickSpark-TS-CSS
# then move into src/components/consumer/reactbits/ per D12 containment
```

**Local patch R1 (both files):** upstream has no reduced-motion handling. Add to each:

```ts
const prefersReducedMotion =
  typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
```

- `BlurText.tsx`: when `prefersReducedMotion`, render the plain `<p>` with the segments
  visible and skip all `motion.span` animation (content identical, instantly legible).
- `ClickSpark.tsx`: when `prefersReducedMotion`, the click handler returns before
  spawning sparks (children still render and receive clicks).
- Both get the `/* D12 local patch R1 … */` header comment.

**Placement** (`search.tsx` diffs, exact hunks written by B3 against the current file):

- The landing `<h1>` copy is wrapped: `<BlurText text={t(lang, <existing h1 key>)}
  animateBy="words" delay={80} stepDuration={0.3} className="entry-h1" />`. Same i18n
  string in, same text out — no i18n change.
- The search submit button is wrapped in
  `<ClickSpark sparkColor="var(--terracotta)" sparkRadius={18} sparkCount={8}>…</ClickSpark>`
  — the "broadcast" gesture in miniature at the moment of broadcast; deterministic,
  one-shot, canvas-scoped.
- Nothing else. `/api/picks` copy and rail get **no** ReactBits component (deterministic
  picks must not wear personalisation-flavoured motion), chat panel keeps its existing
  compositor-friendly transitions, map keeps MapLibre's own `fitBounds`/`flyTo` with the
  existing `jumpTo` reduced-motion path.

---

## 5. Constraint-by-constraint mapping

| # | Constraint | Where satisfied |
|---|---|---|
| C1 | `is_breakout: true` renders "Breakout", never a number | `RisingQueriesPanel.tsx` untouched (restyle is CSS-only); belt-and-suspenders `growthPct === null` branch preserved verbatim |
| C2 | `generated_from: "fixture"` banner visible | `RetailDashboard.tsx` banner block untouched in §3.7 diff; recommendations fixture is disclosed by the same banner because one env var drives both endpoints (§3.7 backend note) |
| C3 | Server `caveat` verbatim, always visible, never tooltip | `ChartPanel.tsx` caveat rendering untouched (§3.6 diff adds only `eyebrow`); `RecommendationsPanel` prints every distinct row caveat in flow (§3.7) |
| C4 | Confidence per segment, never collapsed | Each chart still receives its own `segments.*.confidence` (§3.6); recommendations chips are per row (§3.7) |
| C5 | No chart arithmetic | `options.ts` builders map fields only (§3.3); donut `innerRadius=64` and `size=200` are layout constants; no `PieCenter` total precisely because summing shares would be arithmetic (§3.6 comment) |
| C6 | No "searches" axis label; `interest_avg` never a % or 0–100-plotted | Only `delta_pct`/`share_pct`/`risk_pct` reach any chart (§3.3); `interest_avg` is not in any view; no axis label says "searches" anywhere in §3 code |
| C7 | "Showing N of M" on `X-Total-Count` overflow | `RisingQueriesPanel` count-line logic untouched; recommendations shows plain N and never invents an M the endpoint doesn't send (§3.7) |
| C8 | Timeframe toggle refetches; scoped to `top_movers` | `RetailDashboard` queryKey/`keepPreviousData`/toggle placement untouched (§3.7 diff is two added lines); `RecommendationsPanel` has its own key with no timeframe |
| C9 | Frozen token names | §3.2 diff is purely additive below the existing block |
| C10 | WCAG (≥4.5:1 text on white, ≥3.4:1 on dark map) | No new colour values introduced anywhere — every §3/§4 colour is an existing token value restated (§3.2 header comment carries the existing math forward) |
| C11 | Two routes; no `/dashboard`; sw.js untouched | No route added; retail stays `?mode=retail` behind the same AppShell conditional (§4.2) |
| C12 | i18n keys not broken | All string changes are additive keys (§3.7); BlurText/ClickSpark wrap `t()` output (§4.3) |
| C13 | Picks deterministic, no personalisation copy/motion | PicksRail code untouched; no ReactBits on the rail (§4.3); copy unchanged |
| C14 | URL-state params stay out of query keys | `results.tsx` query keys untouched (§4.1 touches only `scrollTo` and skeleton markup in `ResultsPanel`) |
| C15 | `AiAnalystButton` stays dead | Not touched by any file in this plan |
| C16 | `src/types/` generated only | `RecommendationsResponse.d.ts` already generated; no hand edits (§3.7 imports it) |
| C17 | `demand/shared/schemas/`, `schema.sql` frozen | Backend task adds a fixture **file** and an env branch — no schema file is touched; the absent `generated_from` field is *why* the shared-env-var design was chosen (§3.7) |
| C18 | PicksRail returns `null`, no skeleton/reserved space | Untouched; shift fixed by reordering sections instead (§4.1) |
| C19 | Charts never animate on refetch (D9 wrapper behaviour) | `animate={false}` / `animationDuration={0}` on every Bklit element; grep-enforced (§6) |
| C20 | Accessible name per chart | `BklitFrame` `role="img"` + `aria-label` (§3.5) |

---

## 6. Test plan

Existing suites (104 frontend tests / 19 files) stay green or are updated only where
the *implementation* they mock changed — never where a constraint is asserted.

1. **`options.test.ts` — rewritten for the new view shapes,** keeping the suite's
   defining property: expected values are the payload's **literal numbers**, never
   expressions. The two named mutation traps carry over: direction-by-sign (a
   rising row with negative `delta_pct` must still get `var(--chart-rising)` from
   `colorAccessor`) and derived-risk (a `risk_pct` datum must equal the payload field,
   not `at_risk_count / total_count`).
2. **`ChartPanel.test.tsx`** — unchanged (contract untouched); one added case: eyebrow
   renders when passed, absent otherwise.
3. **`RetailDashboard.test.tsx`** — `vi.mock` targets move from the ECharts stub to a
   `BklitFrame` stub (jsdom cannot layout visx). Constraint assertions (banner, chips,
   toggle-refetch scoping) unchanged.
4. **New `RecommendationsPanel.test.tsx`:** per-row chips render three different levels
   from one payload (C4); every distinct caveat string visible (C3); count line without
   "of" (C7); empty list renders panel empty-state; error state has `role="alert"`.
5. **New `charts.containment.test.ts`** (replaces the README grep as an executable
   check):
   - no import of `./bklit` outside `components/retail/charts/`;
   - no `motion`/`@visx` import outside `charts/` and `consumer/reactbits/`;
   - every `<Bar`/`<PieSlice` usage in `charts/` carries `animate={false}` (C19);
   - no `reactbits/` import inside `charts/` and no `bklit` import inside
     `consumer/` — the two D-record leak checks from the guardrail checklist.
6. **Reduced-motion tests:** `usePingSequence.test.ts` already covers the hook;
   add a BlurText patch test (matchMedia mock ⇒ plain text, zero `motion.span`).
7. **Vendored patch acceptance** (from §3.4): P1 three-fill render, P2 pinned 100
   domain — written as component tests against the vendored source.
8. **`npm run build` + `npm test`** green is the merge gate for every task in §8.

*Note on the brief's "each constraint backed by a failing test": the constraint tests
exist and pass today; they fail if a migration breaks the behaviour. None may be
weakened or deleted to get a task over the line — a red constraint test means the task
is wrong, not the test.*

---

## 7. Performance budget check

Today (measured, from the brief, verified magnitudes): JS 2,238 KB (695 KB gz), CSS
95.7 KB (15.6 KB maplibre), fonts carrying 4 unicode subsets; `RetailView` (ECharts)
and `maplibre-gl` both in the single initial chunk.

Expected after (estimates until the B2 build runs — the task's acceptance includes
recording actuals in `docs/TRACKER.md`):

| Surface | Before (gz) | Target after (gz) | Why |
|---|---|---|---|
| Consumer landing JS | ~695 KB (everything) | **≤ 280 KB** | maplibre chunk (~220 KB gz) deferred until map mounts; retail chunk (bklit+visx: est. 120–180 KB gz) never downloaded in consumer mode; motion (~40 KB gz) is the one new landing cost (BlurText) and is shared with the retail chunk |
| Retail dashboard JS | ~695 KB | ~460 KB (280 + retail chunk) | swaps ECharts (~330 KB gz share) for bklit+visx+motion; loaded lazily |
| Fonts CSS/woff2 | 4 subsets declared | latin only | §4.2 diff |
| Consumer CSS | 95.7 KB | ≈ same | keyframe rewrites are size-neutral; bklit.css loads only in the retail chunk |

Regression guard: B2's acceptance criterion is landing gz **strictly below** today's
695 KB by at least 50%, else the task returns for re-chunking, and no consumer-mode
request may fetch the retail or bklit chunk (checked in the browser network panel).

---

## 8. Rollout plan

**Shipping this redesign does not deploy the demand service, and nothing in this plan
pretends otherwise.** Order:

1. **Merge order per §9 integration sequence.** Everything ships fixture-first
   (decision 7): with `DEMAND_ANALYTICS_SOURCE` unset the dashboard renders the
   committed fixtures behind the practice-data banner, which is the designed, honest
   production state until infra lands.
2. **Known blocker, owned separately (infra task, not this plan):** the demand FastAPI
   app is not deployed; the hosted frontend falls back to `http://localhost:8001`
   (`client.ts` `DEMAND_API_BASE`) and gets connection-refused on retail. Closing it
   requires: a demand service entry in `render.yaml`; `VITE_DEMAND_API_BASE` in
   `netlify.toml`/Netlify UI (the file currently documents only `VITE_API_BASE`);
   `DEMAND_ANALYTICS_SOURCE=live` on the deployed service (which now also flips
   recommendations, §3.7); `VITE_DEMAND_STORE_ID` set to a real store uuid for live
   recommendations. Until all four exist, production retail shows fixtures — correct
   and labelled — and the weekly-cron staleness note (12-month window has no scheduled
   refresh) still applies to live data quality.
3. **Backend micro-task (demand owner, before or with A3):** recommendations fixture +
   env branch from §3.7. A3 can land against a stubbed fetch in tests but must not
   merge to main before the fixture exists, or hosted retail's new panel would 400.
4. **Phase-2 (post-stabilisation): signals line chart** — §9.4 Jules task.

---

## 9. Execution methodology

Per decision 6: **sub-agent-driven development for both workstreams.** One commander
(this session's operator) decomposes, dispatches, integrates, and runs the §10
checklist on every merge. "ICM methodology" here is the repo owner's **Interpretable
Context Methodology** — the folder-structure-as-architecture discipline this workspace
already follows (per its CLAUDE.md; the earlier Incident-Command reading in the brief
template is superseded by the owner's clarification). Applied to sub-agents it means:
each prompt below hands the agent exactly the files its layer owns plus the constraints
that bind them — no agent needs conversation memory, and no agent touches another's
folder.

**Google Jules** is used for exactly one task (§9.4): the phase-2 signals chart is the
textbook Jules shape — isolated, post-stabilisation, converging on existing tests —
while everything in the critical path shares `package.json`/`vite.config.ts`/token
files and needs the central integrator.

### 9.1 Integration order

```
A0 (scaffold + D11/D12 records + tokens)        ← everything depends on it
├─ A1 (vendor bklit + patches P1–P3 + BklitFrame)
│   └─ A2 (three chart migrations + options.ts + tests + README)
├─ A3 (RecommendationsPanel + fetcher + i18n)   ← merge gated on backend fixture (§8.3)
├─ B1 (compositor CSS + scroll + crossfade + PicksRail move)   ← independent
└─ B2 (lazy RetailView + manualChunks + fonts)  ← after A1 (package.json overlap)
    └─ B3 (ReactBits vendor + patches R1 + landing placement)
Final: commander integration pass — §10 checklist + full test/build + perf actuals.
```

### 9.2 Sub-agent prompts (self-contained; commander pastes verbatim)

Each prompt below is abbreviated here to its scope line + constraint set; the full
prompt = that plus the relevant § of this document pasted inline (the sections are
written to be self-contained for exactly this reason).

- **A0:** "In `frontend/`: apply §3.1 scaffold files exactly (components.json,
  tsconfig paths, vite.config.ts, bklit.css), §3.2 tokens diff, and add the D11/D12
  decision records to `docs/IMPLEMENTATION_PLAN_V3.md`-adjacent locations
  (`charts/README.md` header, new `consumer/reactbits/README.md`). Do not run the
  shadcn add commands (A1's job). Constraints: tokens additive only (C9); no preflight
  import; `@source` restricted to charts tree. Gate: `npm run build` green,
  `git grep -n 'tailwindcss' src | grep -v retail/charts` empty."
- **A1:** "Run the §3.1 install commands; move/verify registry output lands under
  `src/components/retail/charts/bklit/`; apply patches P1–P3 (§3.4) with their
  acceptance tests; write `BklitFrame.tsx` (§3.5) verbatim; create `bklit/index.ts`
  re-exporting `BarChart, Bar, BarXAxis, BarYAxis, Grid, ChartTooltip, PieChart,
  PieSlice, Legend`. Remove `echarts`+`echarts-for-react` from package.json. Resolve
  the three [verify-at-install] items of §3 and record answers in the PR description.
  Gate: patch acceptance tests green; `git grep -rn echarts src/ | grep -v '\.test\.'`
  empty (D9 retired)."
- **A2:** "Replace `options.ts` (§3.3) and the three chart components (§3.6) verbatim,
  apply the ChartPanel diff, delete `EChart.tsx`, rewrite `options.test.ts` per §6.1,
  add `charts.containment.test.ts` per §6.5, update `charts/README.md` (D9→D11 story,
  new grep). Constraints C1–C8, C19, C20 as mapped in §5. Gate: full suite green."
- **A3:** "Add `fetchRecommendations` (§3.7 client diff, substituting the fixture's
  real uuid), `RecommendationsPanel.tsx`, dashboard diff, i18n keys, `retail.css`
  additions (§3.8), `RecommendationsPanel.test.tsx` (§6.4). Do not touch schemas or
  generated types. Merge gate: demand fixture task landed (§8.3)."
- **B1:** "Apply every §4.1 diff to `results.css`/`ResultsPanel.tsx`/`search.tsx`
  (PicksRail moves below the how-strip; component code untouched). Constraints C13,
  C14, C18; all new keyframes animate transform/opacity only; verify each is stopped
  by the tokens.css kill switch. Gate: suite green + a DevTools paint-flash check
  note on the PR."
- **B2:** "Apply §4.2 diffs (AppShell lazy, main.tsx fonts; vite.config landed in A0).
  Gate: build actuals recorded per §7, landing ≤ 50% of today's gz, no retail/bklit
  chunk fetched in consumer mode."
- **B3:** "Vendor BlurText + ClickSpark TS-CSS into `src/components/consumer/reactbits/`,
  apply patch R1 (§4.3) with tests (§6.6), place per §4.3. Constraints C12, C13;
  no ReactBits import outside consumer files. Gate: suite green; landing bundle delta
  recorded (motion only)."

### 9.3 Commander integration pass

Run the §10 checklist item-by-item against the merged tree, run
`npm test && npm run build`, record perf actuals in `docs/TRACKER.md`, and only then
declare the redesign done.

### 9.4 Phase-2 appendix — Jules task (post-stabilisation)

> **Jules prompt:** "Repo `aarrushh/reachout`, dir `frontend/`. Add a
> `SignalHistoryChart` panel to the retail dashboard using the already-vendored Bklit
> line chart (`npx shadcn@latest add @bklit/line-chart` — D11 already covers it; keep
> all imports inside `src/components/retail/charts/`). Data:
> `GET {VITE_DEMAND_API_BASE}/demand/api/signals?keyword=<k>&order=window_start&timeframe=<t>`
> — 53 weekly points per keyword. Constraints (each has an existing test pattern to
> copy in `charts/`): y-axis is the relative interest index, NEVER labelled 'searches',
> NEVER rendered as a percentage, NEVER clamped 0–100 (live max 304.15); timeframe
> follows the dashboard toggle and must refetch (copy the queryKey pattern in
> `RetailDashboard.tsx`); charts perform no arithmetic (plot `interest_avg` as sent);
> `animate={false}` everywhere; wrap in `BklitFrame` + `ChartPanel` with eyebrow
> `retail.provenance.search` and the panel's server-provided caveat. Converge on:
> `npm test` green including a new `SignalHistoryChart.test.tsx` asserting literal
> payload values."

---

## 10. Final guardrail checklist (self-verified against this plan)

- [x] No ReactBits component inside `charts/` or any Bklit-owned file (§4.3 placement; §6.5 grep test)
- [x] No Bklit component in consumer-only files (§6.5 grep test)
- [x] `--cat-*`, `--navy-line`, `--terracotta`, `--sand` unchanged (§3.2 additive diff)
- [x] `PicksRail` still returns `null`, no skeleton, no reserved space (§4.1)
- [x] Every chart exposes an accessible name (§3.5 `BklitFrame`)
- [x] "Breakout" never a number (§5 C1 — panel logic untouched)
- [x] Fixture banner logic untouched (§5 C2)
- [x] Caveats + confidence chips always-visible flow text, never tooltips (§5 C3)
- [x] Three confidence levels renderable in one payload, per segment/row (§5 C4, §6.4)
- [x] No new client-side arithmetic in any chart data path (§3.3, §5 C5)
- [x] No "searches" axis label; `interest_avg` never %/0–100 (§5 C6, §9.4)
- [x] "Showing N of M" preserved; no invented M (§5 C7)
- [x] Timeframe toggle refetches, scoped to `top_movers` (§5 C8)
- [x] Picks deterministic; no shuffle; no "recommended for you" copy (§5 C13)
- [x] No new route; sw.js `isRetailRequest` untouched (§5 C11)
- [x] i18n additive only (§5 C12)
- [x] `AiAnalystButton` stays dead (§5 C15)
- [x] `src/types/` generated only (§5 C16)
- [x] `demand/shared/schemas/` + `schema.sql` untouched (§5 C17)
