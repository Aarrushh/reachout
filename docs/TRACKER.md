# TRACKER.md — the live board

**Last updated:** 2026-08-04 (both lanes merged; **all work is on `main`**)
**Wave in flight:** Waves 1–3 backend are done. The UI chain (U0→U7) is the
only thing left that nobody is blocked on.
**Progress:** 26 of 33 tasks done.
**Next action:** **U3** — the three charts, and the only task that adds a
dependency (`echarts-for-react`, decision D9). It fills the rest of retail
mode's right column, where U6's disabled AI button now sits. The UI chain is
the whole critical path now.

**One thing to know about the retail chat pane:** it quotes a stock number
that is a *sample* — retail mode has no store picker and no inventory sync,
so there is no real figure to answer from. The pane says so on screen, in
both languages, and a test holds that notice in place. Replacing the sample
context and removing the notice are one change, never two.

**Node was not installed on this machine.** `frontend/` had never been built
here: no `node`, no `npm`, no `node_modules`. Installed Node 26.5.1 via the
Homebrew that was already present (not on `PATH` — it lives at
`/opt/homebrew/bin`), then `npm ci`. The frontend gate is
`cd frontend && npm test` (33 passing) and `npm run build` (which runs
`tsc --noEmit` first).

**M3 is done** (verified 2026-08-03 by probe, not by asking: a REST call with
`Accept-Profile: demand` returns `200 []`, which only happens once the schema
exists, is exposed, and `service_role` is granted). Credentials are in
`reachout/.env`, and `demand/` loads them.

**V1a is BLOCKED, and not by us.** The live ingest ran for real and got three
distinct answers out of Google:

1. All 49 keywords in one request → `400`. Google compares five terms at a
   time. Fixed in `9cecea2`: batched at five with a shared anchor term so the
   pieces come back on one scale.
2. `interest_by_region` → `400` on a low-volume term. Fixed in the same
   commit: optional field, best-effort, stored null when unavailable.
3. Re-run → `429` redirecting to `google.com/sorry` — this IP is now serving
   a CAPTCHA. That is Google throttling, not a bug, and no code change gets
   past it.

**The fixture fallback is not a fallback.** `demand/tests/fixtures/trends/`
holds two English keywords (`sneakers`, `coffee`) with three daily points
each. It is a unit-test fixture. Run the ingest against it and you get 49
snapshots with empty series, zero signals, zero recommendations — which is
what happened, and those 49 empty rows were deleted again rather than left
sitting in the table looking like data. So V1a cannot be closed either way
today: no live data, and nothing honest to substitute. **Do not present
fixture output as an ingest.** The retry is free — wait out the throttle (or
run it from a different IP) and re-run `--provider trendspy`.

**The board had drifted, and this is how it was caught.** The previous entry
showed T73–T77 as `[ ]` and described two live lanes. In fact every one of
those tasks had landed: `git log --oneline main..origin/jules-demand-integration`
returned 15 commits and `..origin/jules-picks-integration` returned 3, and
each lane had ticked only *its own* contract flags on *its own* branch, so
neither branch ever showed the true state and `main` showed none of it. The
board is only ever as true as its last commit — when a lane runs unattended,
nothing updates this file for it.

Both lanes are now merged into `main` (`4d0dd05`, `df9b36e`) and both branches
are **deleted**, locally and on the remote, along with their worktrees. There
are no lanes any more. **All work happens on `main`.**

**Merged without a whole-branch review** — the reviewer was killed mid-run by
a spend limit. A deliberate tradeoff to hold one branch instead of three;
recorded in `STATUS.md` and not to be re-litigated. Per-task reviews and five
controller fix rounds (W1-FIX-D…H) did run.

Landed: T69 `76e751e`, T70 `10ffc7d`, T71 `bef4254`, T72 `35fa1d4`, T73
`21df7e2`, T74 `a028047`, T75 `b69ea1a`, T77 `d65465c`, T76 `c50e966` +
controller fix `54284c6` (that fix was not optional — `select("*")` against
an `additionalProperties:false` schema made every real `/api/picks` request a
500, invisible to the tests because the fixtures were trimmed to exactly the
schema's keys). All seven contract flags are now `[x]` on `main`.

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
| **M3** | ✅ **Done — verified live 2026-08-03**, not by asking: a REST probe with `Accept-Profile: demand` returned `200 []`, which only happens once the schema exists, is exposed, and `service_role` has been granted. **Apply the database table definitions to Supabase**, then expose the `demand` schema and grant `service_role` on it — three steps, only the first is in the SQL file. Our key cannot run DDL, so all three happen in the dashboard. Exact wording in the V1a row. | **You (founder)** | M2 | V1a | `[x] 2026-08-03` |
| **M4** | Add three missing "phase done" checkboxes to `SHARED_CONTRACT.md`. Three tasks are told to tick lines that aren't in the file. | Claude | nothing | M5, T72, T75, T76 | `[x] 2026-08-02` |
| **M5** | Create and push the two work branches, one per parallel lane. | Claude | M4 | T69–T71, T76 | `[x] 2026-08-02` |
| **M6** | Tell git to ignore the runner's working files, so they stop showing up as clutter or getting committed by accident. | Claude | nothing | — | `[x] 2026-08-02` |
| **M7** | Update the Jules task file: replace task 74 with the no-login version, add the new task 77, and stop the shared preamble from claiming the `demand/` folder already exists. | Claude | M1, M2 | T69–T71, T74, T77 | `[x] 2026-08-02` |
| **M8** | Fix the runner so it tells each task to run *its own* test suite. Right now it tells every task to run the old backend's tests — which would pass without testing any of the new code. | Claude | nothing | M9, M10, T69–T71, T76 | `[x] 2026-08-02` |
| **M9** | Stop two runner processes from fighting over the same files. The old run-book tells you to run two in parallel on one branch and one state file. | Claude | M8 | T69–T71, T76 | `[x] 2026-08-02` |
| **M10** | Stop the runner pushing straight to `main` after every task with no tests run and nobody looking. Run the tests first; make the push to `main` an explicit choice. | Claude | M8 | T69–T71, T76 | `[x] 2026-08-02` |
| **M11** | Fix `reachout/CONTEXT.md`. It tells every arriving agent that two pipeline stages don't exist yet. They shipped. | Claude | nothing | M13 | `[x] 2026-08-02` |
| **M12** | Give the `frontend/` folder the two layer docs every other workspace has, before we split it into consumer and retail halves. | Claude | nothing | M13, U0 | `[x] 2026-08-02` |
| **M13** | Bring `PROJECT_OVERVIEW.md` back in line with what is actually in the repo (missing files, wrong test count, two search backends, the new folders). | Claude | M11, M12 | — | `[x] 2026-08-02` |

### Wave 1 — demand ingest ‖ consumer picks

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **T69** | TASK 69 — the Google Trends reader, plus a fake one that replays saved files, plus the saved practice files themselves. | Jules | M1, M2, M5, M7, M8 | T72 | `[x] 2026-08-02` |
| **T70** | TASK 70 — build the list of search terms to track, from our product categories plus a curated Madrid list. | Jules | M1, M2, M5, M7, M8 | — | `[x] 2026-08-02` |
| **T71** | TASK 71 — save captured trend data to the database without ever creating duplicates. | Jules | M1, M2, M5, M7, M8 | T72 | `[x] 2026-08-02` |
| **T76** | TASK 76 — the "picks for you" endpoint for shoppers. Runs in its own lane, in parallel with everything above. Ticks `PICKS_READY`. | Jules | M4, M5, M8 | U4 | `[x] 2026-08-02` |

**All work is on `main`.** There are no lanes. Both integration branches
were merged on 2026-08-03 and then deleted, locally and on the remote, along
with their worktrees. The runner launch commands that used to sit here are
gone with them — every Jules task in the 69–77 series has landed, so there is
nothing left to dispatch. Any new work is a commit on `main`.

**The test gate — two commands, not one.** Running `pytest` from the repo root
collects nothing: 21 modules error out. Two independent reasons, both real,
both discovered on 2026-08-03 during the merge:

1. `reachout/tests/*` import `api.server` and `tests.test_api` — relative to
   `reachout/`, not to the repo root. They only resolve with `reachout/` as
   the working directory.
2. `reachout/tests/test_api.py` and `demand/tests/test_api.py` collide on the
   module name `tests.test_api`. One root-level run cannot hold both.

So the gate is:

```
cd reachout && PYTHONPATH=<repo-root> ../.venv/bin/python -m pytest -q   # 273 passed
cd <repo-root> &&               .venv/bin/python -m pytest demand/tests -q   # 153 passed
```

426 total. `PYTHONPATH` is required for the first one because a handful of
`reachout/tests/*` import `reachout.*` while the rest import `api.*` — the
suite is split against itself and needs both roots visible. The `.venv`
interpreter is deliberate: macOS system `python3` is 3.9 and cannot import
`reachout/api/` at all (`X | None` at module scope). Create it once with
`uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r
reachout/requirements.txt -r demand/requirements.txt`.

### Wave 2 — signals

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **T72** | TASK 72 — turn raw trend data into rising/falling/flat signals with an honest confidence label, all in plain Python, no AI. Ticks `DEMAND_INGEST_READY`. | Jules | T69, T71, M4 | T73 | `[x] 2026-08-02` |

### Wave 3 — recommendations ‖ the app shell

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **T73** | TASK 73 — turn signals into per-shop recommendations, worded from fixed Spanish templates, each carrying its confidence and its caveat. | Jules | T72 | T74, T75, T77 | `[x] 2026-08-02` |
| **U0** | One app shell with a top-right consumer/retail toggle driven by `?mode=retail` in the address bar. Declare the two component folders. | Claude | M12 | U1, U2, U3, U5, U6 | `[x] 2026-08-03` |
| **U1** | Move the existing search-and-map screens into the consumer half of the shell. No behaviour change. | Claude | U0 | U4, U5 | `[x] 2026-08-03` |
| **U2** | Retail mode's chat pane, reusing the chat panel and its client-side mock that already exist. No backend needed at all. | Claude | U0 | — | `[x] 2026-08-03` |
| **U6** | The "ask AI about my analytics" button: visible, greyed out, wired to nothing. It marks the future feature without building it. | Claude | U0 | — | `[x] 2026-08-04` |

### Wave 4 — the demand API ‖ the charts

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **T74** | TASK 74 (rewritten, no login) — the demand service's own API. All endpoints public for the POC. | Jules | T73, M7 | T75 | `[x] 2026-08-02` |
| **T77** | TASK 77 (new) — the analytics endpoint feeding the dashboard: real shape, practice content, three metrics, no footfall. | Jules | T73, M2, M7 | T75, U3 | `[x] 2026-08-02` |
| **U3** | The three dashboard charts (top movers, category mix, stock-out risk) using ECharts. The screen only draws; every number is computed on the server. Confidence chip and caveat caption always visible. | Claude | U0, M2, T77 | U7 | `[ ]` |

### Wave 5 — batch runner ‖ rail and offline

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **T75** | TASK 75 — the one command that runs the whole chain end to end, safe to run twice. Ticks `DEMAND_API_READY`. | Jules | T73, T74, T77, M4 | V1a | `[x] 2026-08-02` |
| **U4** | The "picks for you" rail in consumer mode. | Claude | T76, U1 | U7 | `[ ]` |
| **U5** | Make the app installable and work offline — **consumer screens only.** The offline cache must never hold the retail dashboard. | Claude | U0, U1 | U7 | `[ ]` |
| **U7** | Drive the whole thing in a real browser: consumer flow on a phone-sized screen, retail flow via `?mode=retail`, and check every caveat caption is visible without hovering. | Claude | U3, U4, U5 | V1b, H1 | `[ ]` |

### Wave 6–7 — live verify and housekeeping

| # | What it is | Who | Waiting on | Blocks | Done? |
|---|---|---|---|---|---|
| **V1a** | **Live ingest.** Founder does three things first, and only the first is in the SQL file: (a) paste all of `demand/data/schema.sql` into the Supabase SQL editor and run it; (b) Settings → API → Data API → **Exposed schemas** → add `demand` — the client sends `Accept-Profile: demand` and PostgREST refuses any schema not on that list, so skipping this 404s every call with the tables sitting right there; (c) back in the SQL editor, `grant usage on schema demand to service_role;` + `grant all on all tables in schema demand to service_role;` + `alter default privileges in schema demand grant all on tables to service_role;` — a new schema carries zero privileges, so skipping this is 42501 on every call. `service_role` only, **never `anon`**: RLS is off and the service has no auth, so granting `anon` would put write access on the public internet. Then Claude runs the dry-run, the live `--provider trendspy` run, checks rows landed, re-runs and confirms the counts stay **flat** (that is the dedupe indexes and the uuid5 natural keys working — doubling counts is a finding), and curls the API. | **You (founder)** → Claude | M3, T75 | V1b | `[!] blocked: Google IP-throttled (CAPTCHA); no usable fallback dataset` |
| **V1b** | **Live dashboard.** With V1a's real rows in the database and U7 passing, open retail mode and confirm the three charts render the **ingested** numbers, each with its confidence label and its caveat visible without hovering. If the scrape was blocked and the data came from fixtures, the dashboard must **say so** — practice data is never presented as live. | Claude | V1a, U7 | H1 | `[ ]` |
| **H1** | Archive the three finished task documents to `docs/archive/` with `git mv` (see BLOAT below). **The six scratch deletions are already done** (`901b444`, pulled forward on 2026-08-03): `reachout/test_tick_debug.py` was putting `reachout/` on `sys.path` as a pytest rootdir, which shadowed the `reachout` package and broke collection for the entire repo — it could not wait for close-out. | Claude | U7 | — | `[~] since 2026-08-03` |

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
| `debug_tick.py` (repo root) | DELETE | one-off debug scratch; the tick work shipped | `[x] 2026-08-03 (901b444)` |
| `debug_tick2.py` (repo root) | DELETE | same | `[x] 2026-08-03 (901b444)` |
| `test_tick2.py` (repo root) | DELETE | same | `[x] 2026-08-03 (901b444)` |
| `test_tick_debug.py` (repo root) | DELETE | same | `[x] 2026-08-03 (901b444)` |
| `reachout/test_tick_debug.py` | DELETE | same — and it sits at the workspace root instead of `tests/`, which breaks the layer rule. Missed by the original register; found in the Phase-1 audit. | `[x] 2026-08-03 (901b444)` |
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
[x] DEMAND_INGEST_READY     ← added by M4, ticked by T72
[x] DEMAND_API_READY        ← added by M4, ticked by T75
[x] PICKS_READY             ← added by M4, ticked by T76
```

All seven are `[x]` on `main` as of 2026-08-03. They did not all become true
at once: each lane ticked only its own flags on its own branch, so until the
merge no single branch showed more than a partial picture. The union is what
is written above, and it is what `SHARED_CONTRACT.md` now holds.

One caveat that survives the merge: T75 ticked `DEMAND_API_READY — demand
API + analytics live` before T77's analytics endpoint existed. T77 has since
landed (`d65465c`), so the flag is now true — but it was ticked early, and
the lesson is that a flag ticked by the task that *needs* it is not the same
as a flag ticked by the task that *provides* it.

---

## Update protocol

**Read this file first, update it last, in the same commit as the work.**
