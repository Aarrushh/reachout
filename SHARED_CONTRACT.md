# SHARED_CONTRACT.md — Backend ↔ Frontend API Contract

> **Reality check (2026-07-16, frontend agent):** the shipped backend
> (`reachout/api/server.py`) does NOT implement the endpoints below. It exposes
> `GET /api/search?q&near|lat,lng&radius`, `GET /api/search.geojson`,
> `GET /api/shops.geojson`, `GET /api/inventory`, `GET /api/regions`,
> `GET /api/inventory/stream`, `GET /api/health` — schema-first, see
> `reachout/shared/schemas/` and `frontend/README.md`. The frontend consumes
> those real endpoints. `POST /api/chat` is the one thing still wanted from
> this contract: the chat UI ships with a client-side mock
> (`frontend/src/chat/shopkeeper.ts`) using the request/response shapes below,
> ready to swap in the real endpoint when `PHASE_3_CHAT_READY` is set.

## Base URL
Backend runs on: http://localhost:8000
Frontend runs on: http://localhost:5173

## Endpoints (Backend publishes, Frontend consumes)

### POST /api/search
Request:  { "query": string, "neighbourhood": string }
Response: { "results": Product[], "interpreted_as": string }

### POST /api/chat
Request:  { "store_id": string, "message": string, "history": ChatMessage[] }
Response: { "reply": string, "suggested_items": Product[] }

### GET /api/products
Response: { "products": Product[], "total": number }

### GET /api/stores
Response: { "stores": Store[] }

### GET /api/neighbourhoods
Response: { "neighbourhoods": string[] }  # Madrid barrios

## Types

### Product
{ id, name, description, category, price, stock_qty, store_id, neighbourhood, tags[], image_url }

### Store
{ id, name, neighbourhood, avg_delivery_mins, is_open, rating }

### ChatMessage
{ role: "user" | "assistant", content: string }

## Status Flags
# Backend agent writes to this file when a phase is done:
# [x] PHASE_1_DB_READY       — Supabase schema + seed complete
# [x] PHASE_2_SEARCH_READY   — /api/search endpoint live
# [x] PHASE_3_CHAT_READY     — /api/chat endpoint live
# [x] PHASE_4_PRODUCTS_READY — /api/products + /api/stores live
# Frontend agent checks these flags before building each feature
