## JULES HANDOFF — ACTIVE
Jules: pick up from here. Phase 1 is done. Supabase is seeded.

Your tasks are Phases 2, 3, and 4:
- Phase 2: reachout/api/search.py — NLP search endpoint using Gemini Flash Lite + pgvector
- Phase 3: reachout/api/chat.py — AI shopkeeper chat endpoint
- Phase 4: Mount both on server.py, add /api/products, /api/stores, /api/neighbourhoods

Rules:
- Keys are in .env (SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY)
- Read SHARED_CONTRACT.md for the full API contract
- Commit each phase to main with git push origin main
- Update SHARED_CONTRACT.md status flags as each phase completes
- Do NOT modify schema.sql or seed_inventory.py
- All endpoints must be async FastAPI
- CORS must allow http://localhost:5173 and *.netlify.app

### STATUS NOTE (2026-07-16, pre-handoff session — read before starting)
1. **Seed state**: check `SHARED_CONTRACT.md` for `[x] PHASE_1_DB_READY`
   before trusting the DB. If it is still `[ ]`, the one-time
   `data/schema.sql` apply in the Supabase SQL editor hasn't happened yet
   (the sb_secret key cannot run DDL); after it does, run
   `python data/seed_inventory.py`.
2. **Phases 2-4 scaffolding already exists** (commit a094580):
   `api/search.py`, `api/chat.py`, `api/madrid.py`, and the server.py
   mounts/GET endpoints/CORS are implemented and TestClient-verified.
   Your job is to VERIFY them against the seeded DB, fix what fails, and
   tick the contract flags — do not rewrite from scratch.
3. Embedding model is `gemini-embedding-001` @ 768 dims
   (NOT text-embedding-004 — unavailable on this key); chat model
   `gemini-2.5-flash-lite`; both read from env via `api/gemini.py`.
   Vectors are L2-normalized client-side.

---

# CLAUDE.md  (Layer 0: Where am I?)

This is a ReachOut workspace. It follows ICM (Interpretable Context
Methodology): folder structure is the architecture. One agent reads the
right files at the right moment. There is no orchestration framework.

Reference: Van Clief and McDermott, "Interpretable Context Methodology:
Folder Structure as Agentic Architecture", arXiv:2603.16021 (2026), MIT
licensed. The method inside the paper is called the Model Workspace
Protocol (MWP).

## What ReachOut is

A shopper searches for an item. The search is broadcast to shops within a
radius that have it in live stock. Matched shops are pinged instantly. The
result is a ranked factual shop list — never narrative content. Madrid is
the test market: real shops from OpenStreetMap, synthetic inventory. See
`_config/product.md` for the full description.

## The one rule that matters most

Some work needs intelligence. Most does not. Keep them apart.

- Stock levels, distance, ranking, database writes: pure Python in
  `scripts/`. An AI never touches these. This is where a hallucination
  would be most dangerous, so no AI is allowed near it.
- Understanding a vague query, phrasing a friendly reply: the agent stages
  in `stages/`. Even there, every output is checked against a schema in
  `shared/schemas/` before the next stage trusts it.

## How to move through this workspace

1. Read this file. (You are here.)
2. Read `CONTEXT.md` (Layer 1) to see the stage order.
3. Enter a stage folder and read its `CONTEXT.md` (Layer 2) for the contract.
4. Load only the references and inputs that contract names. Nothing else.

## Layers

```
Layer 0  CLAUDE.md            this file. Always read first.
Layer 1  CONTEXT.md           stage routing.
Layer 2  stages/*/CONTEXT.md  the contract for one stage.
Layer 3  _config/, shared/    stable rules and schemas. The factory.
Layer 4  stages/*/output/     working files for this run. The product.
```


**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
