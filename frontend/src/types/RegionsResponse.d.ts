/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/regions_response.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: /api/regions. Consumer: frontend / API clients. additionalProperties:false is the hallucination gate. Envelope for GET /api/regions
 */
export type RegionsResponse = {
  [k: string]: unknown;
} & {
  status: "ok" | "error";
  generated_at?: string;
  region_count?: number;
  regions?: {
    region_id: string;
    name: string;
    lat: number;
    lng: number;
    source: "gazetteer";
    shop_count: number;
  }[];
  error?: {
    code: "upstream_not_ok" | "internal";
    detail: string;
  };
};
