import ReactECharts from "echarts-for-react";

/**
 * The ONLY file in this repo that imports a charting library.
 *
 * Decision D9 admits ECharts as the single recorded exception to the
 * no-component-library rule, on the condition that reversing it is a rewrite
 * of one folder. That condition is only true if every chart goes through this
 * wrapper, so no sibling imports `echarts-for-react` directly — swapping the
 * library means editing this file and the option builders beside it, and
 * nothing else in the tree.
 *
 * It also holds the two settings every panel needs identically: charts resize
 * with their container, and they never animate. A dashboard that animates on
 * every refetch draws the eye to motion rather than to the number.
 */
export interface EChartProps {
  /** An ECharts option object, built by ./options.ts. Never built inline. */
  option: Record<string, unknown>;
  /** Accessible name — ECharts renders to canvas, which reads as nothing. */
  ariaLabel: string;
  height?: number;
}

export default function EChart({ option, ariaLabel, height = 240 }: EChartProps) {
  return (
    <div className="echart" role="img" aria-label={ariaLabel}>
      <ReactECharts
        option={{ animation: false, ...option }}
        style={{ height, width: "100%" }}
        notMerge
        opts={{ renderer: "svg" }}
      />
    </div>
  );
}
