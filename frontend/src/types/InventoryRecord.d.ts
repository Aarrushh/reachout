/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/inventory_record.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: inventory_seeder.py / inventory_simulator.py. Consumer: SQLite DB. additionalProperties:false is the hallucination gate. One SKU at one shop. Written only by inventory_seeder.py / inventory_simulator.py — never by an AI stage. synthetic is const true for the entire MVP: real shops, simulated stock, and the data never lies about that. Now includes optional rating, review_count, and source.
 */
export interface InventoryRecord {
  shop_id: string;
  /**
   * From data/sku_catalog.json templates, e.g. PHA-0001.
   */
  sku: string;
  /**
   * Item name from sku_catalog.json — the only source of item names.
   */
  name: string;
  category: "pharmacy" | "grocery" | "hardware" | "electronics" | "stationery";
  price: number;
  currency: "EUR";
  qty: number;
  synthetic: true;
  source?: "template" | "dummyjson";
  rating?: number | null;
  review_count?: number | null;
  updated_at: string;
}
