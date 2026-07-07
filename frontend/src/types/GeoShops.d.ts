/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/geo_shops.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Stage 02 output: real shops inside the radius, sorted nearest-first, with no stock information yet. Script invariants (tested, not expressible here): shop_count == shops.length; shops sorted ascending by distance_km.
 */
export type GeoShops = {
  [k: string]: unknown;
} & {
  status: "ok" | "incomplete" | "error";
  query_location?: {
    lat: number;
    lng: number;
    resolved_from: "coordinates" | "nominatim" | "gazetteer" | "default_center";
    location_text: string | null;
  };
  radius_km?: number;
  shop_source?: "overpass_live" | "cache" | "geofabrik";
  shop_count?: number;
  shops?: {
    shop_id: string;
    name: string;
    /**
     * @minItems 1
     */
    categories: [
      "pharmacy" | "grocery" | "hardware" | "electronics" | "stationery",
      ...("pharmacy" | "grocery" | "hardware" | "electronics" | "stationery")[]
    ];
    lat: number;
    lng: number;
    address: string | null;
    distance_km: number;
    distance_type: "walking" | "haversine";
  }[];
  /**
   * @minItems 1
   */
  missing_fields?: [string, ...string[]];
  error?: {
    code: "no_shop_source" | "location_unresolvable" | "internal";
    detail: string;
  };
};
