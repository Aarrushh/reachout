# JULES_BACKEND_V2.md — Backend v2 verify/harden series (TASKs 53–68)

*Task series for Jules covering backend-v2 Phases 2–4. Continues the v1
numbering (TASKs 01–52 in `docs/JULES_BACKEND.md`) so state files and commit
history never collide. Submitted by `tools/jules_runner.py --tasks
docs/JULES_BACKEND_V2.md --state tools/.jules_runner_state_v2.json --branch
jules-v2-integration`. Every task is atomic, offline-testable, and
independently committable. No code in this file — specs only.*

Tracker (runner ticks nothing here — check `tools/.jules_runner_state_v2.json`
and `SHARED_CONTRACT.md` flags for live status):

| Phase | Tasks | Contract flag |
|-------|-------|---------------|
| 2 — NLP search | 53, 54, 55, 56, 57, 58, 59 | PHASE_2_SEARCH_READY |
| 3 — shopkeeper chat | 60, 61, 62, 63, 64 | PHASE_3_CHAT_READY |
| 4 — REST + CORS | 65, 66, 67, 68 | PHASE_4_PRODUCTS_READY |

## 1. MASTER CONTEXT BLOCK (prepend to every Jules task)

```
Repo: Aarrushh/reachout. Python backend lives in reachout/ (nested).

BACKEND V2 — what already exists (commit a094580, do NOT rewrite it):
reachout/
├── api/gemini.py         Gemini REST helper: embed_texts()/embed_query()
│                         (gemini-embedding-001 @ 768 dims, L2-normalized,
│                         batchEmbedContents chunks of 100, backoff) and
│                         chat() (gemini-2.5-flash-lite, history + system
│                         prompt, optional json_mode). Raises GeminiError.
├── api/supa.py           get_client() -> cached supabase-py Client from
│                         SUPABASE_URL/SUPABASE_KEY env.
├── api/madrid.py         BARRIOS (24 canonical Madrid barrios) +
│                         match_barrio() accent/case-insensitive matcher.
├── api/search.py         POST /api/search {query, neighbourhood?} ->
│                         {results, interpreted_as}. Gemini intent extract +
│                         query embedding (asyncio.gather), match_products
│                         pgvector RPC, _rerank() boosts, _attach_stores().
├── api/chat.py           POST /api/chat {store_id, message, history[]} ->
│                         {reply, suggested_items}. Store+inventory fetched
│                         per call, shopkeeper system prompt, _suggest().
├── api/server.py         Existing v1 endpoints (do not break) + v2 routers
│                         mounted + GET /api/products, /api/stores,
│                         /api/neighbourhoods + CORS (localhost:5173 and
│                         *.netlify.app regex, GET+POST).
├── data/schema.sql       Supabase DDL — DO NOT MODIFY.
├── data/seed_inventory.py Seeder — DO NOT MODIFY.
└── tests/                pytest suite; conftest.py already puts scripts/,
                          agent/, api dirs, and reachout/ on sys.path.

HARD RULES for every task in this series:
1. Your VM has NO .env and NO API keys. Supabase and Gemini are UNREACHABLE.
   All tests must run fully offline: monkeypatch api.gemini functions and
   api.supa.get_client (or the module-level imports in search.py/chat.py/
   server.py). Never make a network call in tests.
2. Run the whole backend suite before finishing:
   cd reachout && python -m pytest tests/ -q   (REACHOUT_OFFLINE=1)
   It must be fully green including all pre-existing v1 tests.
3. Do not modify data/schema.sql, data/seed_inventory.py, or anything in
   frontend/. Do not add dependencies. Endpoints stay async (async def).
4. The scaffolding is believed correct but unverified against live data —
   if a test you write exposes a real bug in api/search.py, api/chat.py,
   api/madrid.py, or the v2 parts of api/server.py, FIX the module (that is
   the point of this series); keep fixes minimal and in-scope.
5. SHARED_CONTRACT.md (repo root) is the API contract: request/response
   shapes for /api/search, /api/chat, /api/products, /api/stores,
   /api/neighbourhoods. Extra response fields are allowed; missing or
   renamed contract fields are not.
6. Work ONLY the single task you were given. Small diff, one concern.
```

## 2. PHASE 2 — NLP search (POST /api/search)

**TASK 53 — Unit tests: api/madrid.py match_barrio.**
New file `reachout/tests/test_madrid.py`. Cover: exact canonical name
("Chueca" -> "Chueca"); accent-insensitive ("malasana" -> "Malasaña",
"chamberi" -> "Chamberí"); barrio embedded in a phrase ("cerca de Lavapiés"
-> "Lavapiés"); None and "" return None; unknown place ("Barcelona") returns
None; BARRIOS has exactly 24 unique entries. Pure unit tests, no app import.

**TASK 54 — Unit tests: search._rerank ordering and boosts.**
New file `reachout/tests/test_search_rerank.py` testing
`api.search._rerank(rows, intent)` directly with hand-built rows. Cover:
exact item_name substring beats higher raw similarity (+0.30 dominates);
partial token overlap scores between no-match and exact; brand_hint match on
tags adds boost; stock_qty > 0 beats identical row with 0; output capped at
20 with `match_score` present and descending. No network, no app import.

**TASK 55 — Unit tests: search._extract_intent fallback paths.**
New file `reachout/tests/test_search_intent.py`. Monkeypatch
`api.search.gemini.chat`: (a) returns valid JSON -> parsed dict with all four
keys; (b) raises `gemini.GeminiError` -> fallback intent with
item_name == raw query and other keys None; (c) returns non-JSON garbage ->
same fallback; (d) returns a JSON array -> same fallback. Assert no exception
ever escapes `_extract_intent`.

**TASK 56 — Shared FakeSupabase test double.**
New file `reachout/tests/fake_supa.py`: a minimal chainable fake of the
supabase-py client covering the calls the v2 code makes — `table(name)`,
`select(cols, count=...)`, `eq`, `in_`, `order`, `range`, `limit`, `rpc`,
`insert`, `execute()` returning an object with `.data` and `.count`.
Constructor takes dicts of canned rows keyed by table name and rpc name.
Add a `fake_supa` pytest fixture in `reachout/tests/conftest.py` (additive
only — do not disturb existing fixtures/path setup). Include a small
self-test file `reachout/tests/test_fake_supa.py` proving the chains used by
search.py/chat.py/server.py resolve.

**TASK 57 — Endpoint tests: POST /api/search happy path + precedence.**
New file `reachout/tests/test_api_search.py` using FastAPI TestClient with
monkeypatched `api.search.gemini.embed_query` (returns a fixed 768-float
vector), `api.search.gemini.chat` (returns canned intent JSON), and
`api.search.get_client` (returns TASK 56's fake with canned match_products
rows + stores). Cover: 200 with `results` list and `interpreted_as` string;
store fields attached (store_name, avg_delivery_mins); explicit
`neighbourhood` request param wins over intent location (assert the RPC
received p_neighbourhood == the request param, accent-normalized); empty
query -> 400; results empty when RPC returns [] (still 200).

**TASK 58 — Hardening: search dependency failures -> clean 502s.**
Tests first, in `reachout/tests/test_api_search.py`: (a) `embed_query`
raising GeminiError -> HTTP 502 with helpful detail, not a 500 traceback;
(b) the supabase RPC raising any Exception -> 502; (c) `_attach_stores`
failure must not lose the search results (results returned without store
fields). Then modify `api/search.py` minimally to pass. Keep intent-extract
fallback behaviour (never fails the request) as is.

**TASK 59 — Tick PHASE_2_SEARCH_READY.**
Only after 53–58 are green: in `SHARED_CONTRACT.md` flip
`# [ ] PHASE_2_SEARCH_READY` to `# [x] PHASE_2_SEARCH_READY`, and in
`STATUS.md` (repo root) tick the `PHASE 2` box in the "Phase log" list under
"BACKEND V2", appending a one-line note with test counts. No code changes.

## 3. PHASE 3 — shopkeeper chat (POST /api/chat)

**TASK 60 — Unit tests: chat._suggest.**
New file `reachout/tests/test_chat_suggest.py` testing
`api.chat._suggest(reply, message, products)` directly. Cover: product whose
name appears (accent/case-insensitively) in the reply is returned first;
mention match caps at 3; with no mention, keyword fallback matches message
tokens against name+tags but only stock_qty > 0 rows; no matches -> [].

**TASK 61 — Unit tests: chat._system_prompt.**
New file `reachout/tests/test_chat_prompt.py`. Assert the prompt contains:
store name and neighbourhood in the persona line; every inventory item as
"- {name} — {price}€ (stock: {qty})" including stock-0 rows; the
avg_delivery_mins value; the under-3-sentences instruction.

**TASK 62 — Endpoint tests: POST /api/chat.**
New file `reachout/tests/test_api_chat.py` (TestClient + TASK 56 fake +
monkeypatched `api.chat.gemini.chat` returning a canned reply). Cover: 200
shape {reply: str, suggested_items: list}; unknown store_id -> 404; empty
message -> 400; history longer than 20 turns is truncated to the last 20 in
what gemini.chat receives (capture the messages arg); gemini.chat raising
GeminiError -> 502.

**TASK 63 — Hardening: bound the chat system prompt + supabase failures.**
Tests first in `reachout/tests/test_api_chat.py`: (a) a store with 500
products must produce a system prompt listing at most 120 inventory lines
plus a "…y {N} artículos más" overflow line (pick in-stock items first);
(b) supabase store/product fetch raising -> 502 not 500. Then modify
`api/chat.py` minimally to pass.

**TASK 64 — Tick PHASE_3_CHAT_READY.**
Only after 60–63 green: flip `# [ ] PHASE_3_CHAT_READY` in
SHARED_CONTRACT.md and tick the PHASE 3 box in STATUS.md "BACKEND V2" phase
log with a one-line note. No code changes.

## 4. PHASE 4 — REST endpoints + CORS

**TASK 65 — Endpoint tests: /api/products, /api/stores, /api/neighbourhoods.**
New file `reachout/tests/test_api_v2_rest.py` (TestClient + TASK 56 fake via
monkeypatched `api.server._supa_client`). Cover: /api/products returns
{products, total} honouring limit/offset and neighbourhood+category filters
(assert the fake received the right eq/range calls); /api/stores returns
{stores} filtered by neighbourhood and ordered by rating desc;
/api/neighbourhoods == {"neighbourhoods": api.madrid.BARRIOS} exactly;
limit=0 and limit=201 -> 422 (Query validation).

**TASK 66 — Hardening: v2 GET endpoints supabase failures -> 502.**
Tests first in `reachout/tests/test_api_v2_rest.py`: fake raising on execute
-> /api/products and /api/stores return 502 with detail, not raw 500.
/api/neighbourhoods never touches supabase (assert fake not called). Then
modify the v2 handlers in `api/server.py` minimally to pass. Do not touch
the v1 endpoints.

**TASK 67 — CORS preflight tests.**
New file `reachout/tests/test_cors.py`. OPTIONS preflight (Origin +
Access-Control-Request-Method headers) against POST /api/search: allowed for
http://localhost:5173, http://127.0.0.1:5173, and https://anything.netlify.app
(assert access-control-allow-origin echoes the origin); a disallowed origin
(https://evil.example.com) gets no allow-origin header. Also assert GET
preflight for /api/products from localhost:5173 passes. No production code
changes expected; if the regex proves wrong, fix the CORSMiddleware config in
api/server.py only.

**TASK 68 — Regression sweep + changelog + tick PHASE_4_PRODUCTS_READY.**
Run the ENTIRE backend suite (v1 + v2) offline and make it green — fix only
what your own series broke, never v1 behaviour. Append a "Backend v2
(TASKs 53–68)" section to `docs/BACKEND_CHANGELOG.md`: new endpoints, models
used, test counts. Flip `# [ ] PHASE_4_PRODUCTS_READY` in SHARED_CONTRACT.md
and tick the PHASE 4 box in STATUS.md "BACKEND V2" phase log.
