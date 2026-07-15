## Frontend Contract Updates

The following fields have been added for the frontend:
- `rating`
- `review_count`
- `source`

The following features have been added:
- Paginated search envelope
- Regions endpoints
- SSE endpoints

The exact regen command to update frontend types is:
`cd frontend && npm run gen-types`

## Phase 4 — shopkeeper chat: what the backend still owes

The frontend chat UI is live (lazy-loaded `ChatPanel.tsx`, triggered from
every result card) but runs on a client-side mock:
`frontend/src/chat/shopkeeper.ts`. To make it real:

1. Implement `POST /api/chat`:
   - Request: `{ "store_id": string, "message": string, "history": [{ "role": "user"|"assistant", "content": string }] }`
   - Response: `{ "reply": string, "suggested_items": Product[] }`
     (`suggested_items` may be empty; the UI treats it as optional today)
   - Replies must be grounded in that shop's real inventory rows (item name,
     price, stock) — the mock never invents inventory and the real endpoint
     must not either.
2. Schema-first: add `chat_request.schema.json` + `chat_response.schema.json`
   to `reachout/shared/schemas/` before writing the endpoint.
3. Set the `PHASE_3_CHAT_READY` flag in `SHARED_CONTRACT.md`.

Frontend swap is then one change: replace the body of `sendChatMessage` in
`frontend/src/chat/shopkeeper.ts` with a fetch, after `npm run gen-types`.
The mock's language handling (ES/EN via the `lang` URL param) should carry
over — pass `lang` alongside the request or infer from the message.
