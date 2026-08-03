/* eslint-disable */
/**
 * Generated from demand/shared/schemas/recommendations_response.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: GET /demand/api/recommendations?store_id=. Consumer: retail dashboard, API clients. additionalProperties:false is the hallucination gate. Top-level envelope is { store_id, recommendations: [...] } (IMPLEMENTATION_PLAN.md 3.3 / IMPLEMENTATION_PLAN_V2.md 5.3). Each recommendations[] item is a full recommendation.schema.json row (all 9 fields, including store_id and signal_id) — this schema is authoritative for that item shape. docs/STITCH_DASHBOARD.md 'API shapes' shows an abbreviated 7-field item ({id, headline, body, action, confidence, caveat, created_at}); that doc predates this schema and is superseded by it, not a second source to reconcile against.
 */
export interface RecommendationsResponse {
  store_id: string;
  recommendations: {
    id: string;
    store_id: string;
    signal_id: string;
    headline: string;
    body: string;
    action: "stock_up" | "feature_in_window" | "watch";
    confidence: "low" | "medium" | "high";
    /**
     * Required, non-empty. Canonical text: "Basado en interés de búsqueda en Madrid, no en compras reales." A caveat-less recommendation cannot validate and cannot be served.
     */
    caveat: string;
    created_at: string;
  }[];
}
