/* eslint-disable */
/**
 * Generated from demand/shared/schemas/trend_snapshot.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: TASK 69/71 (demand.trend_snapshots row). Consumer: TASK 72. additionalProperties:false is the hallucination gate. Raw Google Trends capture for one keyword/geo/timeframe, as sent to and returned by the provider. IMPLEMENTATION_PLAN.md 3.1 / IMPLEMENTATION_PLAN_V2.md 5.1.
 */
export interface TrendSnapshot {
  id: string;
  /**
   * As sent to the provider.
   */
  keyword: string;
  /**
   * Madrid community scope, e.g. ES-MD.
   */
  geo: string;
  /**
   * Provider timeframe string, e.g. 'today 3-m'.
   */
  timeframe: string;
  /**
   * trendspy now; paid adapter later (D1).
   */
  provider: string;
  captured_at: string;
  series: {
    date: string;
    value: number;
  }[];
  /**
   * Interest-by-region payload if available (region names only, never below ES-MD scope). No barrio field: Google Trends does not resolve below ES-MD.
   */
  region_breakdown?:
    | {
        region: string;
        value: number;
      }[]
    | null;
}
