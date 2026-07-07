/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/stock_matches.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Stage 03 output: shops from geo_shops that hold matching in-stock items right now. Facts copied from the DB and geo_shops only. Script invariants: match_count == matches.length; pinged_shop_ids == [m.shop_id for m in matches]; matches preserve the ranking nearest -> most matching stock -> cheapest.
 */
export type StockMatches = {
  [k: string]: unknown;
} & {
  status: "ok" | "incomplete" | "error";
  /**
   * raw_query copied from stage 01.
   */
  query?: string;
  /**
   * Copied verbatim from geo_shops.query_location.
   */
  query_location?: {
    lat: number;
    lng: number;
    resolved_from: "coordinates" | "nominatim" | "gazetteer" | "default_center";
    location_text: string | null;
  };
  radius_km?: number;
  match_count?: number;
  matches?: {
    shop_id: string;
    shop_name: string;
    /**
     * @minItems 1
     */
    categories: [
      "pharmacy" | "grocery" | "hardware" | "electronics" | "stationery",
      ...("pharmacy" | "grocery" | "hardware" | "electronics" | "stationery")[]
    ];
    address: string | null;
    lat: number;
    lng: number;
    distance_km: number;
    distance_type: "walking" | "haversine";
    /**
     * @minItems 1
     */
    items: [
      {
        sku: string;
        name: string;
        category: "pharmacy" | "grocery" | "hardware" | "electronics" | "stationery";
        price: number;
        currency: "EUR";
        /**
         * minimum 1: out-of-stock rows are schema-invalid here by design.
         */
        qty: number;
      },
      ...{
        sku: string;
        name: string;
        category: "pharmacy" | "grocery" | "hardware" | "electronics" | "stationery";
        price: number;
        currency: "EUR";
        /**
         * minimum 1: out-of-stock rows are schema-invalid here by design.
         */
        qty: number;
      }[]
    ];
  }[];
  pinged_shop_ids?: string[];
  /**
   * @minItems 1
   */
  missing_fields?: [string, ...string[]];
  error?: {
    code: "upstream_not_ok" | "db_unavailable" | "internal";
    detail: string;
  };
};
