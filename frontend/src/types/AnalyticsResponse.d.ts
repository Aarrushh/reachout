/* eslint-disable */
/**
 * Generated from demand/shared/schemas/analytics_response.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: GET /demand/api/analytics?store_id=&inventory_type= (TASK 77). Consumer: retail dashboard charts (U3). additionalProperties:false is the hallucination gate. Fixture-first, inventory-type keyed; fixture and live modes are byte-identical in shape. IMPLEMENTATION_PLAN_V2.md 4 (TASK 77) / 5.5. No footfall segment and no field that could be relabelled as one (S1). No barrio field: Google Trends does not resolve below ES-MD.
 */
export interface AnalyticsResponse {
  inventory_type: "convenience_store";
  generated_from: "fixture" | "live";
  generated_at: string;
  /**
   * Required, non-empty. Canonical text: "Basado en interés de búsqueda en Madrid, no en compras reales." An analytics response without one cannot validate and cannot be served.
   */
  caveat: string;
  segments: {
    top_movers: {
      confidence: "low" | "medium" | "high";
      /**
       * MAY be empty. Empty-but-shaped is a valid, expected response, not an error.
       */
      points: {
        keyword: string;
        category: string | null;
        interest_avg: number;
        delta_pct: number;
        direction: "rising" | "falling" | "flat";
      }[];
    };
    category_mix: {
      confidence: "low" | "medium" | "high";
      /**
       * MAY be empty. Empty-but-shaped is a valid, expected response, not an error.
       */
      points: {
        category: string;
        share_pct: number;
        product_count: number;
      }[];
    };
    stock_out_risk: {
      confidence: "low" | "medium" | "high";
      /**
       * MAY be empty. Empty-but-shaped is a valid, expected response, not an error.
       */
      points: {
        category: string;
        at_risk_count: number;
        total_count: number;
        risk_pct: number;
      }[];
    };
  };
}
