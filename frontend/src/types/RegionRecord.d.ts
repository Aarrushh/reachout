/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/region_record.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: db_seeder / gazetteer. Consumer: SQLite DB / API responses. additionalProperties:false is the hallucination gate. A geographical region with associated shop metadata
 */
export interface RegionRecord {
  region_id: string;
  name: string;
  lat: number;
  lng: number;
  source: "gazetteer";
  shop_count: number;
}
