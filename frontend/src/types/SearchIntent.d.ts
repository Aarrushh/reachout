/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/search_intent.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: stage 01. Consumer: stage 02/03. additionalProperties:false is the hallucination gate. Stage 01 output. Grounded only in the user's words plus the committed SYNONYMS map. Stage 01 never geocodes and never invents products.
 */
export type SearchIntent = {
  [k: string]: unknown;
} & {
  status: "ok" | "incomplete";
  /**
   * Exactly what the user typed. Never altered.
   */
  raw_query: string;
  /**
   * Terms from the user's words or SYNONYMS map rows only.
   *
   * @minItems 1
   */
  keywords?: [string, ...string[]];
  /**
   * Zero or more hints. Empty array = search all categories.
   */
  category_hints?: ("pharmacy" | "grocery" | "hardware" | "electronics" | "stationery")[];
  /**
   * Place name verbatim from the query, else null. Not geocoded here.
   */
  location_text?: string | null;
  /**
   * @minItems 1
   */
  missing_fields?: [string, ...string[]];
};
