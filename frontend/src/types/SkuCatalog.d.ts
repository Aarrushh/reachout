/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/sku_catalog.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

export type CategoryArray = {
  sku: string;
  name: string;
  base_price_eur: number;
  source: "template" | "dummyjson";
  rating?: number;
  review_count?: number;
}[];

/**
 * Producer: static data (sku_catalog.json). Consumer: inventory seeder / search engine. additionalProperties:false is the hallucination gate. Schema for data/sku_catalog.json which contains template and dummyjson products per category.
 */
export interface SKUCatalog {
  _comment?: string;
  pharmacy?: CategoryArray;
  grocery?: CategoryArray;
  hardware?: CategoryArray;
  electronics?: CategoryArray;
  stationery?: CategoryArray;
}
