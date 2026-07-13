/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/inventory_response.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Envelope for GET /api/inventory
 */
export interface InventoryResponse {
  status: "ok" | "error";
  generated_at: string;
  region_id: string | null;
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  items: {
    shop_id: string;
    shop_name: string;
    sku: string;
    name: string;
    category: "pharmacy" | "grocery" | "hardware" | "electronics" | "stationery";
    price: number;
    currency: "EUR";
    qty: number;
    synthetic: true;
    source: "template" | "dummyjson";
    updated_at: string;
    rating?: number | null;
    review_count?: number | null;
  }[];
}
