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
  /**
   * The capture window this signal was derived from, carried down from trend_snapshots (e.g. 'today 3-m', 'today 12-m'). Part of the natural key and of the table's unique index, NOT decoration: Google scales its 0-100 index to the window requested and this pipeline rescales onto an anchor on top of that, so the same keyword in the same calendar week reads differently at 3-m and at 12-m. Two readings, two rows. A consumer plotting a series MUST filter to one timeframe; mixing them plots incomparable numbers on one axis.
   */
  timeframe: string;
  window_start: string;
  window_end: string;
  /**
   * Mean of rescaled series values. NOT capped at 100: batches are rescaled onto a shared anchor, so a keyword larger than the reference legitimately exceeds 100. Google's raw 0-100 only holds inside one batch.
   */
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
