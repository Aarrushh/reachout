import { describe, expect, it } from "vitest";

import { categoryMixOption, stockOutRiskOption, topMoversOption } from "./options";
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
 * The load-bearing property of this whole task: the browser draws the
 * server's numbers and derives none of its own. Every assertion below names
 * the LITERAL value from the payload, not an expression over it — computing
 * the expected value here would only prove the chart agrees with the test's
 * arithmetic, which is exactly the arithmetic that is forbidden.
 */
describe("chart option builders pass server numbers through untouched", () => {
  it("plots delta_pct verbatim for top movers", () => {
    const option = topMoversOption(MOVERS) as any;
    const values = option.series[0].data.map((d: { value: number }) => d.value);

    // Reversed for top-down reading order, so the payload's first row is last.
    expect(values).toEqual([0.4, -18.5, 42.6]);
    expect(option.yAxis.data).toEqual(["pilas AA", "paraguas", "protector solar"]);
  });

  it("colours a top mover by the server's direction, not by the sign", () => {
    const option = topMoversOption([
      // A falling keyword with a positive delta is possible — direction is the
      // service's windowed judgement, not `delta_pct > 0`. If the chart ever
      // colours by sign, this row turns green and contradicts its own label.
      { keyword: "raro", category: null, interest_avg: 10, delta_pct: 3.1, direction: "falling" },
    ]) as any;

    expect(option.series[0].data[0].itemStyle.color).toBe("#b12704");
  });

  it("plots share_pct verbatim and does not normalise the mix to 100", () => {
    const option = categoryMixOption(MIX) as any;

    // These two shares sum to 59.5. A chart that rescaled them to fill the
    // ring would be inventing the missing 40.5 points.
    expect(option.series[0].data).toEqual([
      { name: "electronics", value: 18.0 },
      { name: "grocery", value: 41.5 },
    ]);
  });

  it("plots risk_pct verbatim rather than recomputing it from the counts", () => {
    const option = stockOutRiskOption(RISK) as any;

    expect(option.series[0].data).toEqual([27.78, 0]);
    expect(option.xAxis.data).toEqual(["electronics", "grocery"]);
  });

  it("builds a valid option for an empty segment", () => {
    // Empty-but-shaped is the normal response (D10), so the builders must not
    // throw on it even though the panel renders its empty state instead.
    expect(() => topMoversOption([])).not.toThrow();
    expect((categoryMixOption([]) as any).series[0].data).toEqual([]);
    expect((stockOutRiskOption([]) as any).series[0].data).toEqual([]);
  });
});
