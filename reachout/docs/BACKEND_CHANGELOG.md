# Backend Changelog

## Migrations
* **Migration 1:** `CREATE TABLE regions (...)`
* **Migration 2:** `ALTER TABLE shops ADD COLUMN region_id TEXT; CREATE INDEX idx_shops_region ON shops(region_id);`
* **Migration 3:** `ALTER TABLE inventory ADD COLUMN source TEXT ...`, `ALTER TABLE inventory ADD COLUMN rating REAL;`, `ALTER TABLE inventory ADD COLUMN review_count INTEGER;`

## New Endpoints
* `/api/inventory`
* `/api/regions`
* `/api/inventory/stream`

## Schema Changes
* Added `health_response.schema.json`
* Added `search_page.schema.json`
* Added `inventory_response.schema.json`
* Added `regions_response.schema.json`
* Added `region_record.schema.json`
* Added `stock_event.schema.json`
* Added `sku_catalog.schema.json`

## Reseed Implication
The database needs to be reseeded because inventory contents changed (new columns: `source`, `rating`, `review_count`).

## Rollback Note
The DB is gitignored and regenerated — reverting code + schemas and re-running the seeders rebuilds it.
