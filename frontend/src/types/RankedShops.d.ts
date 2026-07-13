/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/ranked_shops.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * The final consumer-facing artifact: a ranked FACTUAL list of nearby shops holding the item. additionalProperties:false on every object is the narrative gate. Now includes optional rating and review_count. Script invariants: result_count == results.length; ranks are 1..N contiguous in array order.
 */
export type RankedShops = {
  [k: string]: unknown;
} & {
  status: "ok" | "incomplete" | "error";
  query?: string;
  generated_at?: string;
  result_count?: number;
  results?: {
    rank: number;
    shop_id: string;
    shop_name: string;
    /**
     * Primary category (first of the shop's categories array).
     */
    category: "pharmacy" | "grocery" | "hardware" | "electronics" | "stationery";
    address: string | null;
    distance_km: number;
    item_name: string;
    sku: string;
    price: number;
    currency: "EUR";
    stock_qty: number;
    lat: number;
    lng: number;
    rating?: number;
    review_count?: number;
  }[];
  /**
   * @minItems 1
   */
  missing_fields?: [string, ...string[]];
  error?: {
    code: "upstream_not_ok" | "internal";
    detail: string;
  };
};
