/* eslint-disable */
/**
 * Generated from demand/shared/schemas/recommendation.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: TASK 73, recommend.py (demand.recommendations row). Consumer: GET /demand/api/recommendations. additionalProperties:false is the hallucination gate. Retailer-facing, template-generated pure Python, no AI. IMPLEMENTATION_PLAN.md 3.3 / IMPLEMENTATION_PLAN_V2.md 5.3. confidence and caveat are required so a recommendation without a caveat cannot validate and cannot be served.
 */
export interface Recommendation {
  id: string;
  store_id: string;
  signal_id: string;
  /**
   * Template-generated, pure Python. No AI.
   */
  headline: string;
  /**
   * Template-generated, pure Python. No AI.
   */
  body: string;
  action: "stock_up" | "feature_in_window" | "watch";
  /**
   * Copied verbatim from the signal, never recomputed.
   */
  confidence: "low" | "medium" | "high";
  /**
   * Required, non-empty. Canonical text: "Basado en interés de búsqueda en Madrid, no en compras reales."
   */
  caveat: string;
  created_at: string;
}
