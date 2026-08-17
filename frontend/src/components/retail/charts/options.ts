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
  /**
   * Fed to the vendored Bar's colorAccessor (D11 patch P1). Typed exactly as
   * Bar declares it — `(datum: Record<string, unknown>, index: number) => string`
   * — rather than narrowed to `{ direction }`, since a narrower parameter
   * type is not assignable where the wider one is expected (Bar may call it
   * with any datum shape). The one place the payload's actual shape is known
   * is the cast inside the function body below.
   */
  colorAccessor: (datum: Record<string, unknown>) => string;
}

/**
 * Top movers: one horizontal bar per keyword, length = `delta_pct`.
 * Horizontal because the labels are Spanish search phrases; rotated vertical
 * labels would be unreadable at the width the dashboard column allows.
 */
export function topMoversView(points: TopMoverPoint[]): TopMoversView {
  return {
    // No reverse(): `BarChart`'s categoryScale domain is `data.map(categoryAccessor)`
    // in unreversed payload order with range [0, innerHeight] (bar-chart.tsx:246-256),
    // so the first payload row lands at SVG y=0 — topmost — natively. The
    // predecessor's builder needed a reverse() because it drew horizontal
    // bars bottom-up; Bklit does not, so adding one here would invert the chart.
    data: points.map((p) => ({
      keyword: p.keyword,
      delta_pct: p.delta_pct,
      direction: p.direction,
    })),
    colorAccessor: (d) => DIRECTION_FILL[(d as { direction: TopMoverPoint["direction"] }).direction],
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
 * as the predecessor's default palette was.
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
