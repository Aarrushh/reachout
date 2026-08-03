/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/shop_record.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: osm_ingest.py. Consumer: SQLite DB. additionalProperties:false is the hallucination gate. One real shop sourced from OpenStreetMap. Identity fields are never AI-generated; osm_ingest.py validates every row against this before upsert.
 */
export interface ShopRecord {
  shop_id: string;
  osm_id: number;
  name: string;
  /**
   * Every internal category the shop's OSM tags map to, per data/category_tag_map.json. First entry is primary.
   *
   * @minItems 1
   */
  categories: [
    "pharmacy" | "grocery" | "hardware" | "electronics" | "stationery",
    ...("pharmacy" | "grocery" | "hardware" | "electronics" | "stationery")[]
  ];
  lat: number;
  lng: number;
  /**
   * Joined from OSM addr:* tags when present; null when OSM has none. Never synthesized.
   */
  address: string | null;
  source: "overpass_live" | "cache" | "geofabrik";
  fetched_at: string;
}
