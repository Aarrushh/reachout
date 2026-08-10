# DECISIONS_V2.md — decisions taken against probed reality

*Extracted verbatim from the retired `STATUS.md` (§AGENT IMPROVEMENTS, July
2026) when that append-only log was removed. Each item below records what a
live probe of the real Supabase project and Gemini key returned, not what a
plan assumed. That is why they were worth keeping.*

*Where any of this disagrees with the code, **the code wins** — see
`docs/CODEBASE_OVERVIEW.md` §10 on authoritative sources. Cited by
`reachout/api/chat.py` and `reachout/data/seed_inventory.py`.*

---


Decisions made autonomously vs. the plan as written, after probing the real
Supabase project and Gemini key before writing any code:

1. **Embedding model: `gemini-embedding-001` @ 768 dims, not `text-embedding-004`.**
   Probed the provided key: `text-embedding-004` returns 404 (not available on
   this key/API version). `gemini-embedding-001` with `outputDimensionality: 768`
   is available and keeps the `vector(768)` schema contract. Verified live.
   Non-3072-dim outputs are NOT pre-normalized (measured norm ≈ 0.59), so the
   seeder normalizes vectors client-side before insert.

2. **Batch + dedupe embeddings at seed time (pre-computed, not on-demand).**
   Plan said "for EACH product call the embedding API" — that is 3000–5000
   sequential calls. Instead: embeddings are computed once per UNIQUE catalog
   item (name+description+category are what get embedded; per-store rows only
   vary price/stock), then reused across store rows, and requested via
   `batchEmbedContents` (100 texts/call). ~4,000 calls collapse to ~10–15.
   Query embeddings are computed on-demand at search time (they must be).

3. **Search: hybrid — pgvector cosine RPC + deterministic re-rank.**
   Pure FTS loses vague/bilingual queries ("algo para el dolor de cabeza");
   pure vector loses exact-name precision. So: `match_products()` SQL function
   (PostgREST can't ORDER BY `embedding <=>` directly, an RPC is the standard
   pattern) does cosine top-K + optional neighbourhood filter in SQL, then
   Python re-ranks with intent extracted by Gemini Flash Lite (exact/partial
   name and brand matches boosted, in-stock boosted).

4. **Chat state: client-passed history, no Redis.** The contract already passes
   `history` from the client; server-side sessions add a service and buy
   nothing at this scale. Endpoints stay stateless (also matches the frozen
   "no new services" rule and deploys anywhere).

5. **FastAPI stays.** server.py, SSE bus, and 91 offline tests already exist;
   switching frameworks is churn with zero user-visible gain.

6. **Gemini via plain REST, not the `google-generativeai` SDK.** That SDK is
   deprecated (superseded by `google-genai`) and adds a dependency chain on
   Python 3.14 for what is two POST endpoints. `requests` is already a dep.
   One shared helper module (`api/gemini.py`) wraps embed + chat + backoff.

7. **Schema DDL: documented credential limitation + three-path apply.** The
   provided `sb_secret_...` key CANNOT execute DDL: PostgREST does no DDL, and
   the Management API rejects it (401, needs an `sbp_` personal access token);
   probed both. `data/seed_inventory.py` therefore applies `data/schema.sql`
   via `SUPABASE_DB_URL` (direct Postgres) or `SUPABASE_ACCESS_TOKEN`
   (Management API) when either is set; otherwise it verifies the tables exist
   and, if they don't, prints the SQL-editor paste-once instruction and exits
   nonzero. schema.sql is fully idempotent (IF NOT EXISTS / OR REPLACE).

8. **RLS left disabled** (dev mode, per plan) — noted explicitly in schema.sql
   with the follow-up that anon-key clients must never ship until RLS is on.

9. **requirements.txt frozen-stack header amended, not deleted** — v1 stays
   frozen; backend v2 is scoped as the one user-approved exception block.

