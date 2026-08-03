/* eslint-disable */
/**
 * Generated from demand/shared/schemas/demand_signal.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: TASK 72, compute_signals.py (demand.demand_signals row). Consumer: TASK 73, TASK 77, GET /demand/api/signals. additionalProperties:false is the hallucination gate. Derived, pure-Python, never model-assigned. IMPLEMENTATION_PLAN.md 3.2 / IMPLEMENTATION_PLAN_V2.md 5.2. geo is ES-MD scope only: Trends does not resolve to barrio, and this schema has no barrio column so nothing can pretend otherwise.
 */
export interface DemandSignal {
  id: string;
  keyword: string;
  /**
   * Mapped product category, nullable.
   */
  category: string | null;
  /**
   * ES-MD (Madrid community scope) only.
   */
  geo: string;
  window_start: string;
  window_end: string;
  interest_avg: number;
  /**
   * Vs prior window.
   */
  delta_pct: number;
  direction: "rising" | "falling" | "flat";
  /**
   * Dense rank within window.
   */
  rank: number;
  confidence: "low" | "medium" | "high";
  /**
   * Provenance.
   */
  snapshot_ids: string[];
  computed_at: string;
}
