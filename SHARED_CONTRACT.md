# SHARED_CONTRACT.md — phase flags between agents

**The flags below are the contract.** They are single-line, single-writer,
and each was ticked by the task that satisfied it. `docs/CODEBASE_OVERVIEW.md`
§10 lists them as an authoritative source.

**The API contract is the schemas, not this file.** See
`reachout/shared/schemas/` (16 files) and `demand/shared/schemas/` (5 files).
Those are DO-NOT-MODIFY: if a payload fails validation, the payload is wrong.
For which endpoints actually exist, read `docs/CODEBASE_OVERVIEW.md` §6.

*An endpoint list and Product/Store/ChatMessage shapes used to sit here. They
described endpoints the shipped backend does not implement — the file carried
its own banner saying so — and were removed on 2026-08-10. Recoverable from
git history.*

## Status Flags

# Backend agent writes to this file when a phase is done:
# [x] PHASE_1_DB_READY       — Supabase schema + seed complete
# [x] PHASE_2_SEARCH_READY   — /api/search endpoint live
# [x] PHASE_3_CHAT_READY     — /api/chat endpoint live
# [x] PHASE_4_PRODUCTS_READY — /api/products + /api/stores live
# [x] DEMAND_INGEST_READY    — demand ingest chain green through compute_signals
# [x] DEMAND_API_READY       — demand API + analytics live
# [x] PICKS_READY            — /api/picks live

# Frontend agent checks flags before building each feature
