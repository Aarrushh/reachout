/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/search_page.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: /api/search. Consumer: frontend search results. additionalProperties:false is the hallucination gate. Paginated envelope for GET /api/search. The ranks stay the GLOBAL ranks (page 2 starts at rank 11). result_count equals the slice length.
 */
export type SearchPage = {
  [k: string]: unknown;
} & {
  status: "ok" | "incomplete" | "error";
  query?: string;
  generated_at?: string;
  page?: number;
  page_size?: number;
  total_results?: number;
  total_pages?: number;
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
