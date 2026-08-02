# TRACKER.md — the live board

**Last updated:** 2026-08-02 (M13 landed)
**Wave in flight:** Wave 0 — unblock and repair. Nothing past wave 0 may start.
**Progress:** 11 of 32 tasks done.
**Next action:** Two wave-0 tasks remain before wave 1 can start: create and
push the two work branches (**M5**, Claude) and amend `docs/JULES_DEMAND.md`
with the no-login TASK 74 + new TASK 77 (**M7**, Claude — waits on M1, M2,
both done). Independently, **M3** (apply the schema to Supabase) needs the
founder.

---

## How to use this file

Read it first. Update it last, **in the same commit as the work.** A session can
die at any moment; a fresh one must be able to resume from files alone, never
from a conversation. Full plan: `docs/IMPLEMENTATION_PLAN_V2.md`.

**Done? states:** `[ ]` not started · `[~] since <date>` in progress ·
`[x] <date>` done · `[!] blocked: <one-line reason>` stuck.
A task with `Waiting on` = **nothing** and `Done?` = `[ ]` is runnable right now.

---

## Task board

**Who** is one of three values: **Jules** (autonomous VM, no keys, offline
tests) · **Claude** (the orchestrating session) · **You (founder)** (needs a
human, live credentials, or a decision).

### Wave 0 — unblock and repair

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **M1** | Build the `demand/` folder: its two layer docs, its seed-keyword list, and the empty folders and test helpers the Jules tasks expect. The task fuel already says this exists; it does not. | Claude | nothing | M2, M7, T69, T70, T71 | `[x] 2026-08-02` |
| **M2** | Write the five data contracts (JSON Schemas) and the database table definitions for the demand service, plus the spec for what the practice data must look like. | Claude | M1 | M3, M7, M13, T69–T71, T77, U3 | `[x] 2026-08-02` |
| **M3** | **Apply the database table definitions to Supabase.** The key we have cannot do this — it has to be pasted into the Supabase SQL editor, same as last time. | **You (founder)** | M2 | V1 | `[ ]` |
| **M4** | Add three missing "phase done" checkboxes to `SHARED_CONTRACT.md`. Three tasks are told to tick lines that aren't in the file. | Claude | nothing | M5, T72, T75, T76 | `[x] 2026-08-02` |
| **M5** | Create and push the two work branches, one per parallel lane. | Claude | M4 | T69–T71, T76 | `[x] 2026-08-02` |
| **M6** | Tell git to ignore the runner's working files, so they stop showing up as clutter or getting committed by accident. | Claude | nothing | — | `[x] 2026-08-02` |
| **M7** | Update the Jules task file: replace task 74 with the no-login version, add the new task 77, and stop the shared preamble from claiming the `demand/` folder already exists. | Claude | M1, M2 | T69–T71, T74, T77 | `[ ]` |
| **M8** | Fix the runner so it tells each task to run *its own* test suite. Right now it tells every task to run the old backend's tests — which would pass without testing any of the new code. | Claude | nothing | M9, M10, T69–T71, T76 | `[x] 2026-08-02` |
| **M9** | Stop two runner processes from fighting over the same files. The old run-book tells you to run two in parallel on one branch and one state file. | Claude | M8 | T69–T71, T76 | `[x] 2026-08-02` |
| **M10** | Stop the runner pushing straight to `main` after every task with no tests run and nobody looking. Run the tests first; make the push to `main` an explicit choice. | Claude | M8 | T69–T71, T76 | `[x] 2026-08-02` |
| **M11** | Fix `reachout/CONTEXT.md`. It tells every arriving agent that two pipeline stages don't exist yet. They shipped. | Claude | nothing | M13 | `[x] 2026-08-02` |
| **M12** | Give the `frontend/` folder the two layer docs every other workspace has, before we split it into consumer and retail halves. | Claude | nothing | M13, U0 | `[x] 2026-08-02` |
| **M13** | Bring `PROJECT_OVERVIEW.md` back in line with what is actually in the repo (missing files, wrong test count, two search backends, the new folders). | Claude | M11, M12 | — | `[x] 2026-08-02` |

### Wave 1 — demand ingest ‖ consumer picks

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **T69** | TASK 69 — the Google Trends reader, plus a fake one that replays saved files, plus the saved practice files themselves. | Jules | M1, M2, M5, M7, M8 | T72 | `[ ]` |
| **T70** | TASK 70 — build the list of search terms to track, from our product categories plus a curated Madrid list. | Jules | M1, M2, M5, M7, M8 | — | `[ ]` |
| **T71** | TASK 71 — save captured trend data to the database without ever creating duplicates. | Jules | M1, M2, M5, M7, M8 | T72 | `[ ]` |
| **T76** | TASK 76 — the "picks for you" endpoint for shoppers. Runs in its own lane, in parallel with everything above. Ticks `PICKS_READY`. | Jules | M4, M5, M8 | U4 | `[ ]` |

### Wave 2 — signals

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **T72** | TASK 72 — turn raw trend data into rising/falling/flat signals with an honest confidence label, all in plain Python, no AI. Ticks `DEMAND_INGEST_READY`. | Jules | T69, T71, M4 | T73 | `[ ]` |

### Wave 3 — recommendations ‖ the app shell

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **T73** | TASK 73 — turn signals into per-shop recommendations, worded from fixed Spanish templates, each carrying its confidence and its caveat. | Jules | T72 | T74, T75, T77 | `[ ]` |
| **U0** | One app shell with a top-right consumer/retail toggle driven by `?mode=retail` in the address bar. Declare the two component folders. | Claude | M12 | U1, U2, U3, U5, U6 | `[ ]` |
| **U1** | Move the existing search-and-map screens into the consumer half of the shell. No behaviour change. | Claude | U0 | U4, U5 | `[ ]` |
| **U2** | Retail mode's chat pane, reusing the chat panel and its client-side mock that already exist. No backend needed at all. | Claude | U0 | — | `[ ]` |
| **U6** | The "ask AI about my analytics" button: visible, greyed out, wired to nothing. It marks the future feature without building it. | Claude | U0 | — | `[ ]` |

### Wave 4 — the demand API ‖ the charts

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **T74** | TASK 74 (rewritten, no login) — the demand service's own API. All endpoints public for the POC. | Jules | T73, M7 | T75 | `[ ]` |
| **T77** | TASK 77 (new) — the analytics endpoint feeding the dashboard: real shape, practice content, three metrics, no footfall. | Jules | T73, M2, M7 | T75, U3 | `[ ]` |
| **U3** | The three dashboard charts (top movers, category mix, stock-out risk) using ECharts. The screen only draws; every number is computed on the server. Confidence chip and caveat caption always visible. | Claude | U0, M2, T77 | U7 | `[ ]` |

### Wave 5 — batch runner ‖ rail and offline

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **T75** | TASK 75 — the one command that runs the whole chain end to end, safe to run twice. Ticks `DEMAND_API_READY`. | Jules | T73, T74, T77, M4 | V1 | `[ ]` |
| **U4** | The "picks for you" rail in consumer mode. | Claude | T76, U1 | U7 | `[ ]` |
| **U5** | Make the app installable and work offline — **consumer screens only.** The offline cache must never hold the retail dashboard. | Claude | U0, U1 | U7 | `[ ]` |
| **U7** | Drive the whole thing in a real browser: consumer flow on a phone-sized screen, retail flow via `?mode=retail`, and check every caveat caption is visible without hovering. | Claude | U3, U4, U5 | V1, H1 | `[ ]` |

### Wave 6–7 — live verify and housekeeping

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **V1** | **Run the ingest against the real Google Trends once**, confirm real rows landed, and view the dashboard on live data. If the scrape is blocked, fall back to practice data and say so — never fake it. | **You (founder)** | M3, T75, U7 | — | `[ ]` |
| **H1** | Delete the six dead scratch files and archive the three finished task documents (see BLOAT below). Authorized; do it here, not earlier. | Claude | U7 | — | `[ ]` |

---

## OWNED — files an in-flight task holds

If a path is listed here and it is not your task, **do not open it for
writing.** Record the conflict as a new row instead of editing around it.
An entry whose `Since` date is stale is an abandoned lock — clear it and say so
in `STATUS.md`.

| File or folder | Held by | Since |
|---|---|---|
| *(nothing in flight)* | — | — |

Reserved in advance, so two tasks never collide on them:

| File or folder | Will be held by | Note |
|---|---|---|
| `demand/` (whole tree) | M1 → M2 → T69–T75, T77 | One task at a time, in wave order |
| `demand/shared/schemas/`, `demand/data/schema.sql` | M2 only | **Jules tasks must never modify these** |
| `SHARED_CONTRACT.md` | M4, then T72 / T75 / T76 (flag flips only) | One line each, nothing else |
| `docs/JULES_DEMAND.md` | M7 | Must be final before any task is submitted |
| `tools/jules_runner.py` | M8 → M9 → M10 | Sequential; three separate concerns |
| `frontend/src/main.tsx`, `frontend/src/components/` | U0 → U1/U2/U6 → U3 → U4/U5 | The shell lands before anything is moved into it |
| `reachout/api/server.py` | T76 only, one `include_router` line | Nothing else in this file changes |
| `PROJECT_OVERVIEW.md` | M13 | Last, so it records the finished state |
| `docs/TRACKER.md` (this file) | **nobody — always writable, always last** | Never treat it as contended |

---

## BLOAT register

> **AUTHORIZED by founder 2026-08-02 — executed by the housekeeping task (H1),
> not before.** Nothing below has been removed. Everything is recoverable from
> git history; the archive moves are renames, not deletions.

| File | Verdict | Reason | Deleted? |
|---|---|---|---|
| `debug_tick.py` (repo root) | DELETE | one-off debug scratch; the tick work shipped | `[ ]` |
| `debug_tick2.py` (repo root) | DELETE | same | `[ ]` |
| `test_tick2.py` (repo root) | DELETE | same | `[ ]` |
| `test_tick_debug.py` (repo root) | DELETE | same | `[ ]` |
| `reachout/test_tick_debug.py` | DELETE | same — and it sits at the workspace root instead of `tests/`, which breaks the layer rule. Missed by the original register; found in the Phase-1 audit. | `[ ]` |
| `plan.md` (repo root) | DELETE | 29-line tick-scheduler micro-plan; the work already shipped (its own banner says so) | `[ ]` |
| `docs/JULES_BACKEND.md` | ARCHIVE → `docs/archive/` | finished task fuel (TASKs 01–52); keep as history, never load as input | `[ ]` |
| `docs/JULES_BACKEND_V2.md` | ARCHIVE → `docs/archive/` | finished task fuel (TASKs 53–68); same | `[ ]` |
| `docs/STITCH_FRONTEND.md` | ARCHIVE → `docs/archive/` | v1 UI spec, executed and merged; keep as the design record | `[ ]` |

---

## READ THIS

In this order. Stop when you have what your task named.

1. **`docs/TRACKER.md`** — this file. What is in flight, what is next, who owns what.
2. **`reachout/CLAUDE.md`** — the workspace identity and the one rule: exactness is pure Python, AI touches only language.
3. **`reachout/CONTEXT.md`** — the stage routing table.
4. **`docs/IMPLEMENTATION_PLAN_V2.md`** — decisions, task list, data contracts, risks, out-of-scope.
5. **The one contract your task names** — a schema in `shared/schemas/`, or the task's own text in `docs/JULES_DEMAND.md`.

Nothing else. That is the point.

## SKIP THIS

| File | Why not |
|---|---|
| `AGENTS.md` | v1's ten workstreams, all finished. Its Batch 1→5 graph is the precedent this plan cites — read it for that, never as instructions. |
| `docs/EXECUTION_PROMPTS.md` | Superseded run-book. Blocks on a Stitch API key that cannot exist, and tells two terminals to share one runner branch. |
| `docs/IMPLEMENTATION_PLAN.md` | Superseded for routing — **except §3, which is still the source text for the demand data contracts, and §3.4, which is the preserved reversal path for authentication.** Do not delete it. |
| `docs/JULES_BACKEND.md`, `docs/JULES_BACKEND_V2.md` | TASKs 01–68, done and merged. Task-shaped, so easy to mistake for fuel — they are not. |
| `docs/STITCH_DASHBOARD.md`, `docs/STITCH_CONSUMER.md`, `docs/STITCH_FRONTEND.md` | Design specifications, not API call series. There is no Stitch API. Open only if you are building that exact screen, and expect the route names to be wrong (they predate the one-shell decision). |
| `plan.md` | Shipped micro-plan. |
| `docs/FINAL_SUMMARY.md`, `docs/frontend_contract_note.md`, `docs/superpowers/` | v1 records. |
| `STATUS.md` | History, 623 lines of it. Read it to answer "why was this done this way", never "what should I do next" — that is this file's job. |

---

## Decisions in force

| ID | In force | Reverse by |
|---|---|---|
| **D1** | Trends data is free scraping behind a swappable provider interface. | Write a second adapter, flip `DEMAND_TRENDS_PROVIDER`. |
| **D2** | `demand/` is its own service — **and there is no authentication at all.** | Restore the design kept in `IMPLEMENTATION_PLAN.md` §3.4. |
| **D3** | "Phone" means responsive web + installable PWA, one codebase. | Nothing here forecloses a native app; the API contracts are the boundary. |
| **D4** | Embeddings stay `gemini-embedding-001` at 768 dims. | Revisit only with real latency or cost data. |
| **D5** | Many small offline-testable Jules tasks — now with per-lane isolation, the right test suite, and a green-tests gate before `main`. | The runner's flag defaults preserve the old behaviour. |
| **D6** | UI design specs are implemented directly by the coding agent. There is no Stitch API. | None needed — the specs are already prompt-shaped. |
| **D7** | Delivery is a memo, not a build. | Raise it after the first real inventory feed. |
| **D8** | $0 in new paid API spend. | Raise the ceiling, re-run anything logged "skipped (budget)". |
| **D9** | Charts are ECharts via `echarts-for-react` — the frontend's first and only component dependency, charts-only. | Every import is confined to `components/retail/charts/`; swap = rewrite one folder. |
| **D10** | Fixture-first: real API shape from day one, practice content behind it, live data swapped in later behind the identical endpoint. | Nothing to reverse — the swap is the design. |

Sub-decisions: **S1** three metrics, footfall dropped for having no data source ·
**S2** toggle lives in the URL (`?mode=retail`) · **S3** practice data is 8 weeks
× 100 SKUs and *must* include one deliberately high-confidence keyword or that
tier goes untested · **S4** task numbers 69–76 unchanged, 77 appended ·
**S5** deletions authorized, executed by H1 · **S6** consumer search stays on the
existing pipeline endpoint, not the Supabase one.

---

## Contract flags — copy

> **`SHARED_CONTRACT.md` is the source of truth. This block is a copy. If they
> disagree, `SHARED_CONTRACT.md` wins and this block is stale.**

```
[x] PHASE_1_DB_READY        Supabase schema + seed complete
[x] PHASE_2_SEARCH_READY    /api/search endpoint live
[x] PHASE_3_CHAT_READY      /api/chat endpoint live
[x] PHASE_4_PRODUCTS_READY  /api/products + /api/stores live
[ ] DEMAND_INGEST_READY     ← added by M4, ticked by T72
[ ] DEMAND_API_READY        ← added by M4, ticked by T75
[ ] PICKS_READY             ← added by M4, ticked by T76
```

The three `DEMAND_*` / `PICKS_*` lines **are now in `SHARED_CONTRACT.md`.**
Task M4 added them on 2026-08-02. All three flags are present and unticked,
ready for T72, T75, and T76 to tick them in turn.

---

## Update protocol

**Read this file first, update it last, in the same commit as the work.**
