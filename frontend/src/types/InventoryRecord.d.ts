/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/inventory_record.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * One SKU at one shop. Written only by inventory_seeder.py / inventory_simulator.py — never by an AI stage. synthetic is const true for the entire MVP: real shops, simulated stock, and the data never lies about that.
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
  updated_at: string;
}
