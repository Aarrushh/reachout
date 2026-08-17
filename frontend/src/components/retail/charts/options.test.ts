import { describe, expect, it } from "vitest";

import { categoryMixView, stockOutRiskView, topMoversView } from "./options";
import type { CategoryMixPoint, StockOutRiskPoint, TopMoverPoint } from "./options";

const MOVERS: TopMoverPoint[] = [
  { keyword: "protector solar", category: null, interest_avg: 78.4, delta_pct: 42.6, direction: "rising" },
  { keyword: "paraguas", category: "grocery", interest_avg: 31.2, delta_pct: -18.5, direction: "falling" },
  { keyword: "pilas AA", category: "electronics", interest_avg: 55, delta_pct: 0.4, direction: "flat" },
];

const MIX: CategoryMixPoint[] = [
  { category: "electronics", share_pct: 18.0, product_count: 18 },
  { category: "grocery", share_pct: 41.5, product_count: 42 },
];

const RISK: StockOutRiskPoint[] = [
  { category: "electronics", at_risk_count: 5, total_count: 18, risk_pct: 27.78 },
  { category: "grocery", at_risk_count: 0, total_count: 42, risk_pct: 0 },
];

/**
 * The load-bearing property of the whole task: the browser draws the
 * server's numbers and derives none of its own. Every assertion below names
 * the LITERAL value from the payload, not an expression over it — computing
 * the expected value would only prove the chart agrees with the test's own
 * arithmetic, which is exactly the arithmetic this file forbids.
 */
describe("chart view builders pass server numbers through untouched", () => {
  it("plots delta_pct verbatim, in payload order, for top movers", () => {
    const view = topMoversView(MOVERS);

    // No reverse(): BarChart draws the first payload row topmost natively
    // (docs/IMPLEMENTATION_PLAN_V3.md §3, resolved verify-at-install answer),
    // so payload order is preserved rather than flipped for a bottom-up draw.
    expect(view.data).toEqual([
      { keyword: "protector solar", delta_pct: 42.6, direction: "rising" },
      { keyword: "paraguas", delta_pct: -18.5, direction: "falling" },
      { keyword: "pilas AA", delta_pct: 0.4, direction: "flat" },
    ]);
  });

  it("colours a bar by the server's direction, not by the sign of delta_pct", () => {
    const view = topMoversView(MOVERS);

    // Mutation trap: "falling" here carries a NEGATIVE delta_pct, so a
    // colorAccessor that switched to `delta_pct >= 0` would still pass a
    // naive test. direction is a windowed judgement and the sign is not —
    // they can disagree, and the colour must follow the server's word.
    expect(view.colorAccessor({ direction: "rising" })).toBe("var(--chart-rising)");
    expect(view.colorAccessor({ direction: "falling" })).toBe("var(--chart-falling)");
    expect(view.colorAccessor({ direction: "flat" })).toBe("var(--chart-flat)");
    expect(view.colorAccessor(view.data[1])).toBe("var(--chart-falling)");
  });

  it("plots share_pct verbatim and does not normalise the mix to 100", () => {
    const view = categoryMixView(MIX);

    // These two shares sum to 59.5. A chart that rescaled them to fill the
    // ring would be inventing the missing 40.5 points.
    expect(view.data).toEqual([
      { label: "electronics", value: 18.0, color: "var(--chart-cat-1)" },
      { label: "grocery", value: 41.5, color: "var(--chart-cat-2)" },
    ]);
  });

  it("plots risk_pct verbatim rather than recomputing it from the counts", () => {
    const view = stockOutRiskView(RISK);

    // Mutation trap: 5/18 rounds to 27.78, the same value risk_pct already
    // carries, so `at_risk_count / total_count` would pass today too — the
    // point asserted here is that the *field* is what flows through, not an
    // expression over the other two fields, so the two stay independent the
    // first time the service changes how risk is defined.
    expect(view.data).toEqual([
      { category: "electronics", risk_pct: 27.78 },
      { category: "grocery", risk_pct: 0 },
    ]);
    expect(view.fill).toBe("var(--chart-risk)");
    expect(view.domainMax).toBe(100);
  });

  it("builds a valid view for an empty segment", () => {
    // Empty-but-shaped is a normal response (D10), so builders must not
    // throw on it even though the panel renders its empty state instead.
    expect(topMoversView([]).data).toEqual([]);
    expect(categoryMixView([]).data).toEqual([]);
    expect(stockOutRiskView([]).data).toEqual([]);
  });
});
