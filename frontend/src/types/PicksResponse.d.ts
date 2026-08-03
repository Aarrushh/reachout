/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/picks_response.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: GET /api/picks. Consumer: Frontend picks UI. additionalProperties:false is the hallucination gate.
 */
export interface PicksResponse {
  picks: {
    id: string;
    name: string;
    description: string;
    category: string;
    price: number;
    stock_qty: number;
    store_id: string;
    neighbourhood: string;
    tags: string[];
    image_url?: string | null;
  }[];
  generated_by: "deterministic";
}
