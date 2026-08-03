/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/health_response.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: /api/health. Consumer: frontend/monitoring. additionalProperties:false is the hallucination gate.
 */
export interface HealthResponse {
  status: "ok";
  shop_count?: number;
  region_count?: number;
  simulator_running?: boolean;
}
