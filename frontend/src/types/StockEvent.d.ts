/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/stock_event.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * SSE event payload for real-time inventory updates
 */
export interface StockEvent {
  type: "sale" | "restock" | "new_item";
  shop_id: string;
  shop_name: string;
  region_id: string | null;
  sku: string;
  name: string;
  qty_now: number;
  ts: string;
  sold?: number;
  added?: number;
}
