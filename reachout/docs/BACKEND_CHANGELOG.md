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

## Pending — Phase 4: shopkeeper chat (requested by frontend, not built)
The frontend shipped a chat slide-over backed by a client-side mock
(`frontend/src/chat/shopkeeper.ts`). It is waiting on one endpoint:

* `POST /api/chat` — request `{ store_id, message, history: [{role, content}] }`,
  response `{ reply, suggested_items?: [] }` (shapes in `SHARED_CONTRACT.md`).

Schema-first like everything else: add `chat_request.schema.json` /
`chat_response.schema.json` under `reachout/shared/schemas/`, then the
frontend runs `npm run gen-types` and swaps the body of `sendChatMessage`.
When live, set `PHASE_3_CHAT_READY` in `SHARED_CONTRACT.md`. Full details in
`docs/frontend_contract_note.md`.
