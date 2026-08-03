/**
 * Pure builders: an analytics segment's `points` in, an ECharts option out.
 *
 * These functions contain NO arithmetic. Every value they place on an axis is
 * a field the demand service already computed and validated against
 * `analytics_response.schema.json` — `interest_avg`, `delta_pct`, `share_pct`,
 * `risk_pct`. If a chart ever needs a number the payload does not carry, the
 * schema changes and the server computes it; a percentage the browser worked
 * out is a number nobody validated.
 *
 * Formatting is the one thing allowed here — a `%` suffix on an axis label is
 * presentation, not derivation.
 */
import type { AnalyticsResponse } from "../../../types/AnalyticsResponse";

type Segments = AnalyticsResponse["segments"];
export type TopMoverPoint = Segments["top_movers"]["points"][number];
export type CategoryMixPoint = Segments["category_mix"]["points"][number];
export type StockOutRiskPoint = Segments["stock_out_risk"]["points"][number];

/** Direction is the server's word, so the colour follows it, not the sign. */
const DIRECTION_COLOUR: Record<TopMoverPoint["direction"], string> = {
  rising: "#007600",
  falling: "#b12704",
  flat: "#565959",
};

const GRID = { left: 8, right: 16, top: 16, bottom: 8, containLabel: true };
const AXIS_TEXT = { color: "#565959", fontSize: 11 };

/**
 * Top movers: one horizontal bar per keyword, length = `delta_pct`.
 * Horizontal because the labels are Spanish search phrases; rotated vertical
 * labels would be unreadable at the width the dashboard column allows.
 */
export function topMoversOption(points: TopMoverPoint[]): Record<string, unknown> {
  // ECharts draws a horizontal bar chart bottom-up, so reversing here puts
  // the payload's first row at the top of the panel. Order only — the
  // response's own ranking is preserved, not recomputed.
  const ordered = [...points].reverse();
  return {
    grid: GRID,
    xAxis: {
      type: "value",
      axisLabel: { ...AXIS_TEXT, formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#eaeded" } },
    },
    yAxis: {
      type: "category",
      data: ordered.map((p) => p.keyword),
      axisLabel: AXIS_TEXT,
      axisTick: { show: false },
    },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    series: [
      {
        type: "bar",
        data: ordered.map((p) => ({
          value: p.delta_pct,
          itemStyle: { color: DIRECTION_COLOUR[p.direction] },
        })),
        barMaxWidth: 18,
      },
    ],
  };
}

/**
 * Category mix: a doughnut of `share_pct`. The server guarantees the shares;
 * this does not normalise them, so if they do not sum to 100 the chart shows
 * that rather than hiding it behind a rescale.
 */
export function categoryMixOption(points: CategoryMixPoint[]): Record<string, unknown> {
  return {
    tooltip: { trigger: "item", valueFormatter: (v: number) => `${v}%` },
    legend: { bottom: 0, textStyle: AXIS_TEXT },
    series: [
      {
        type: "pie",
        radius: ["45%", "70%"],
        center: ["50%", "42%"],
        label: { show: false },
        data: points.map((p) => ({ name: p.category, value: p.share_pct })),
      },
    ],
  };
}

/** Stock-out risk: one vertical bar per category, height = `risk_pct`. */
export function stockOutRiskOption(points: StockOutRiskPoint[]): Record<string, unknown> {
  return {
    grid: GRID,
    xAxis: {
      type: "category",
      data: points.map((p) => p.category),
      axisLabel: { ...AXIS_TEXT, interval: 0, rotate: 30 },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      max: 100,
      axisLabel: { ...AXIS_TEXT, formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#eaeded" } },
    },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    series: [
      {
        type: "bar",
        data: points.map((p) => p.risk_pct),
        itemStyle: { color: "#ff9900" },
        barMaxWidth: 32,
      },
    ],
  };
}
