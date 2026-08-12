# ReachOut — Implementation Plan v2

*Authored 2026-08-02 by the Phase-2 planning session, per the plan prompt §G
(that prompt was deleted 2026-08-10; recoverable from git history).*

*Supersedes `docs/IMPLEMENTATION_PLAN.md` (v1) for task routing and product
shape; carries v1's §0 decision-table pattern, its D1–D8 rows, and its §3 data
contracts forward. Written after a read-only Phase-1 audit of the repo — every
"wave 0" task below exists because the audit found the thing it fixes actually
broken, not because a document said so.*

**The one rule, unchanged:** work that must be exact is pure Python; AI only
touches language, and only behind `additionalProperties: false` schemas.

---

## 0. Decisions — every row reversible

The founder answered the plan prompt's §F question set on 2026-08-02.
Answers are recorded here. To override a row: edit it, then re-run only the
tasks tagged with that decision's ID.

### 0.1 Decision table D1–D10

| ID | Decision | Taken | Why / how to reverse |
|----|----------|-------|----------------------|
| **D1** | Trends data source | **Free scraping (`trendspy`/HTTP) behind a `TrendsProvider` interface.** $0 spend. | *Carried from v1, unchanged.* The interface (TASK 69) means a paid provider (Bright Data / DataForSEO / SerpApi) is a new adapter class plus a config change, no downstream edits. **Reverse:** implement a second adapter, flip `DEMAND_TRENDS_PROVIDER`. |
| **D2** | Dashboard hosting + auth | **Service boundary KEPT:** new top-level `demand/` service, own FastAPI app, own uvicorn process, own Postgres schema `demand` in the existing Supabase project. **Auth REMOVED (override of v1 D2):** no Supabase magic-link, no JWT, no `demand.retailers` table, no RLS. Every `/demand/api/*` endpoint is public for the POC. Retail mode is reached by the mode toggle alone. | *v1's hosting half stands; v1's auth half is overridden per §F Q5.* Dead auth code is untested auth code, and the POC has no login surface to attach it to. **Reverse:** the full auth design (JWT verification, `demand.retailers` mapping, RLS policy set) is preserved verbatim in `docs/IMPLEMENTATION_PLAN.md` §3.4 and §2 A11 — restore it by re-adding the `demand.retailers` DDL block, the `Depends` verifier, and the 401/403 test cases to TASK 74. Nothing built under this plan forecloses it: no endpoint signature changes when auth is added, only a dependency is inserted. |
| **D3** | "Phone" meaning | **Responsive web + PWA (manifest, installable), single React codebase.** No native scaffold. | *Carried from v1, unchanged.* One codebase, reuses the existing Vite/React/TanStack/MapLibre stack, zero app-store friction. **Reverse:** nothing here forecloses a later Expo app — the API contracts are the boundary. |
| **D4** | Semantic search model | **Keep `gemini-embedding-001` @ 768 dims.** | *Carried from v1, unchanged.* The `products` table is already embedded at 768 dims with an ivfflat index tuned to it; switching invalidates every stored vector for no measured problem at this scale. **Reverse:** revisit only with real latency/cost data. |
| **D5** | Jules usage & granularity | **Many small offline-testable tasks via `tools/jules_runner.py`**, tasks file `docs/JULES_DEMAND.md`, numbering continues at TASK 69. **Amended in v2:** each concurrent lane gets its own `--branch`, `--state`, and worktree (M9); the runner runs the correct per-series test suite (M8); and nothing reaches `main` without a green suite in the worktree (M10). | *Carried from v1 with three amendments the Phase-1 audit forced.* As shipped, the runner appends a hardcoded `cd reachout/tests && python -m pytest` to every task (wrong suite for TASKs 69–75 — it would report green having tested nothing), pushes to `main` after every task with no test gate, and shares one worktree/state file across lanes the run-book tells you to run in parallel. **Reverse:** the flag defaults in `jules_runner.py` preserve v1 behaviour; M8–M10 are additive. |
| **D6** | UI generation | **Design specs implemented directly by the coding agent.** the Stitch files (deleted 2026-08-10, recoverable from git) were design specifications, optionally pasteable into `stitch.withgoogle.com` by a human for a visual reference. There is no Stitch API. | *v1 D6 corrected.* Verified by grep: `stitch` appears in zero `.py`/`.ts`/`.tsx`/`.json`/`.toml`/`.yaml`/`.html` files in this repo; every mention is markdown. Google Stitch is a browser design tool. The v1 "fallback" (the coding agent implements each prompt directly) was always the real path and is now the only path. **Reverse:** none needed — if Stitch ever ships an API, the specs are already prompt-shaped. |
| **D7** | Delivery partner-vs-build | **Out of scope. One `[MANUAL]` research memo, zero code.** | *Carried from v1, unchanged.* Spain/EU courier classification (Ley Rider) is real exposure; layers 1–2 must prove themselves first. **Reverse:** raise it after the first real inventory feed. |
| **D8** | Budget ceiling | **$0 in new paid API spend.** Allowed: free `trendspy` scraping, already-provisioned Gemini + Supabase keys at existing usage, Jules within existing quota. Anything requiring a new paid signup is blocked and logged as skipped. | *Carried from v1, unchanged; reconfirmed by the founder §F Q8.* Note: D9's chart library is free OSS and does not breach this. **Reverse:** raise the ceiling and re-run any task logged as "skipped (budget)". |
| **D9** | Chart library (NEW) | **ECharts via `echarts-for-react`.** Lighter than Plotly.js, denser than Recharts. | *§F Q1.* The frontend draws only; it never computes — every number rendered comes from a `demand/api/analytics` payload computed in pure Python. **Audit note recorded:** this is the frontend's **first component dependency**. `PROJECT_OVERVIEW.md` §7 states the standing convention "plain CSS + custom-property tokens — **no UI library**". D9 is a deliberate, recorded exception scoped to charts only; no other component library enters the tree. **Reverse:** all chart rendering is confined to `frontend/src/components/retail/charts/` behind local wrapper components, so swapping to Plotly.js or Recharts is a rewrite of that one folder — no route, no fetcher, and no schema changes. |
| **D10** | Fixture-first data (NEW) | **Committed fixture JSON served behind the real API shape.** Every demand endpoint returns a payload that validates against its `additionalProperties: false` schema from day one; the content is fixtures until Trends ingestion replaces it behind the *identical* endpoint. The frontend never knows the difference. | *§F Q9 / prompt §B7.* This is what lets the entire UI tree start before any Trends data exists, and what makes a blocked or rate-limited scrape a content problem rather than a build problem. **Reverse:** none required — swapping fixtures for live rows is a data-source change inside the endpoint, invisible to every consumer. The provider selector (`--provider fixture|trendspy`, `DEMAND_TRENDS_PROVIDER`) is the switch. |

### 0.2 Sub-decisions S1–S6 (the remaining §F answers, and one the audit forced)

| ID | Decision | Taken | Why / how to reverse |
|----|----------|-------|----------------------|
| **S1** | Retail-mode metrics (§F Q2) | **Three metrics, in this order: top movers, category mix, stock-out risk.** **Footfall proxy is DROPPED.** | Footfall proxy has **no data source anywhere in this repo**, and `docs/IMPLEMENTATION_PLAN.md` §3.2 states in the schema notes that Google Trends does not resolve below `ES-MD` — *"the schema has no barrio column here so nothing can pretend otherwise."* A footfall tile backed by nothing is exactly the trust failure the confidence/caveat machinery exists to prevent. Recorded in §7 out-of-scope with that reason. **Reverse:** a footfall metric becomes available only with a real source (POS feed, door counter, or a licensed mobility dataset); it is a new schema field plus a new task, never a re-label of trends data. |
| **S2** | Toggle persistence (§F Q3) | **URL query param `?mode=retail`** (absent or any other value = consumer, the default). | Shareable, stateless, trivially testable, and the only option consistent with the repo's standing invariant `PROJECT_OVERVIEW.md` §11.3: *"URL is the state of record."* Netlify already rewrites `/*` → `index.html` (`netlify.toml`), so it works in production today with no config change. **Reverse:** a persisted local setting is an additive `localStorage` read layered *under* the URL param — the param keeps precedence, so nothing breaks. |
| **S3** | Fixture realism (§F Q4) | **8 weeks × 100 SKUs** (founder override of the 12×200 default). | **Recorded caveat, carried into M2 and TASK 69 as a hard requirement:** the `high` confidence tier requires ≥8 weeks of data **and** `interest_avg ≥ 20` **and** direction stable across the last 3 windows. At *exactly* 8 weeks the tier is only marginally exercisable — a fixture set generated naively will contain zero `high` rows and the tier will go untested while every test still passes. **Fixture generation must therefore deliberately include at least one keyword satisfying all three conditions, and `demand/tests/test_compute_signals.py` must assert that a `high` row is produced.** **Reverse:** widen to 12×200 by regenerating fixtures; no code or schema changes, golden files are regenerated with them. |
| **S4** | Task numbering (§F Q6) | **TASKs 69–76 keep their numbers; TASK 77 is appended.** | The runner keys `done`/`pending` on the two-digit task number and `--from`/`--only` do string comparison on it — renumbering invalidates any partial run for no gain. **Reverse:** none wanted. |
| **S5** | Bloat deletions (§F Q7) | **AUTHORIZED**, executed by planned housekeeping task **H1**, not before. Delete: `debug_tick.py`, `debug_tick2.py`, `test_tick2.py`, `test_tick_debug.py` (repo root), `reachout/test_tick_debug.py`, `plan.md`. Archive (move to `docs/archive/`): `docs/JULES_BACKEND.md`, `docs/JULES_BACKEND_V2.md`, `docs/STITCH_FRONTEND.md`. | All five tick-scratch files are tracked in git; the fifth (`reachout/test_tick_debug.py`) sits at the ICM workspace root instead of `reachout/tests/` and was missing from the prompt's register. The tick work shipped (see `plan.md`'s own SUPERSEDED banner and `STATUS.md`). **Reverse:** everything is recoverable from git history; the archive move is a rename, not a delete. |
| **S6** | Which search backend consumer mode uses (**not covered by §F — decided here**) | **Consumer mode keeps the existing SQLite pipeline `GET /api/search` via `frontend/src/api/client.ts`.** The Supabase + Gemini `POST /api/search` (`reachout/api/search.py`) stays mounted and available but the v2 consumer UI does not adopt it. | `reachout/api/server.py` mounts **two** search implementations — `GET /api/search` (pipeline, schema-validated, MapLibre-integrated) and `POST /api/search` (pgvector + Gemini rerank). The prompt's §E says consumer mode "reuses `api/client.ts`", whose only exports are `fetchRankedShops`, `fetchShopsGeoJSON`, `fetchAllShops` — all pipeline endpoints. Adopting the Supabase path would mean new fetchers, a new result shape, and losing the map integration, for no POC gain. **Reverse:** the two backends are independent; migrating consumer search to `POST /api/search` is a `client.ts` change plus a new response schema, and can happen any time after the POC. |

---

## 1. Scope summary

v2 builds **one app, one shell, one toggle.**

- **Consumer mode (default)** — the shipped search-and-map experience, grown into a shell: `/` search and `/results` stay, a top-right toggle appears, and a "picks for you" rail lands behind a new deterministic endpoint. Installable PWA, offline shell scoped to consumer routes only.
- **Retail mode (`?mode=retail`)** — chat pane on the left (the existing client-side `ChatPanel` + `chat/shopkeeper.ts` mock), analytics dashboard on the right: three ECharts charts drawn from numbers computed in pure Python and served as JSON. The frontend only draws. An "ask AI about my analytics" button is visible, disabled, and wired to nothing — it marks the future feature without building it.
- **Behind it** — the `demand/` service: Google Trends batch ingest → snapshots → signals → recommendations → its own public FastAPI app, every surfaced number carrying a deterministic confidence label and a non-suppressible caveat, all of it fixture-first (D10).
- **Nothing else.** No auth, no checkout, no payments, no native app, no delivery build, no AI shop-chat.

**Before any of that**, wave 0 repairs what the Phase-1 audit found broken: the `demand/` workspace does not exist while its own task fuel swears it does; the three contract flags that are supposed to be this plan's dependency edges are not in `SHARED_CONTRACT.md`; the runner tells every demand task to run the wrong test suite; and the run-book instructs two runner processes to share one branch, one state file, and one worktree.

---

## 2. Task list

Tags: `[JULES]` = autonomous Jules session (offline-testable, VM holds no keys) ·
`[UI]` = frontend work in the orchestrating session · `[MANUAL]` = orchestrator
work in this repo · `[MANUAL/FOUNDER]` = **blocks on a human with live
credentials**. Tasks sharing a wave number may run concurrently.

### Wave 0 — unblock and repair (nothing below wave 0 may start until these land)

| # | Tag | Task | Depends on |
|---|-----|------|------------|
| **M1** | [MANUAL] | **Scaffold the `demand/` workspace.** Create `demand/` with `CLAUDE.md` (L0: workspace identity + the one rule, mirroring `reachout/CLAUDE.md`), `CONTEXT.md` (L1: routing for the ingest→signals→recommend→api chain), `_config/seed_keywords.json` (30–50 curated Madrid retail terms, ES), `ingest/`, `scripts/`, `api/`, `shared/schemas/`, `data/`, and `tests/` containing `conftest.py` (sys.path setup, copied from `reachout/tests/conftest.py` style), `fake_supa.py` (chainable fake modelled on `reachout/tests/fake_supa.py`), and `fixtures/`. **Why this is wave 0:** `docs/JULES_DEMAND.md`'s master context block — the text pasted into every Jules VM — states *"demand/ — what already exists (do NOT rewrite it)"* and marks its schemas DO NOT MODIFY. `ls demand` returns *No such file or directory*. Submitting TASK 69 today drops an agent into a repo where its workspace, schemas, conftest and fixtures are all absent while it is forbidden from creating them. | — |
| **M2** | [MANUAL] | **Author the data contracts.** Five JSON Schemas in `demand/shared/schemas/` (`trend_snapshot`, `demand_signal`, `recommendation`, `recommendations_response`, `analytics_response` — the last is new, see §5.5) and `demand/data/schema.sql`: idempotent DDL creating the `demand` Postgres schema with tables `trend_snapshots`, `demand_signals`, `recommendations`. **No `retailers` table and no RLS block** (D2 override). Source of truth for columns and confidence rules is `docs/IMPLEMENTATION_PLAN.md` §3 — carry it forward verbatim except for the auth removals. Also write `demand/tests/fixtures/README.md` fixing the fixture spec from S3: 8 weeks × 100 SKUs, **with at least one keyword deliberately constructed to satisfy all three `high`-confidence conditions.** | M1 |
| **M3** | [MANUAL/FOUNDER] | **Apply `demand/data/schema.sql` to Supabase.** `docs/DECISIONS_V2.md` #7 records, from a live probe, that the available `sb_secret_…` key **cannot execute DDL** — PostgREST does no DDL and the Management API rejects it (401, needs an `sbp_` personal access token). So this is either a `SUPABASE_DB_URL` direct-Postgres run or a paste into the Supabase SQL editor by the founder, exactly as PHASE 1 was applied. Verify the three tables exist under schema `demand`. **This blocks only V1 (live verify). No Jules task and no UI task waits on it** — everything else runs on fixtures (D10). | M2 |
| **M4** | [MANUAL] | **Add the three contract flags to `SHARED_CONTRACT.md`:** `# [ ] DEMAND_INGEST_READY`, `# [ ] DEMAND_API_READY`, `# [ ] PICKS_READY`, in the existing Status Flags block below the `PHASE_*` lines. **Why wave 0:** TASKs 72, 75 and 76 are each instructed to "flip" one of these lines. `grep READY SHARED_CONTRACT.md` returns only `PHASE_1..4`. This plan calls these flags its dependency edges; today the graph has no edges. While in the file, also correct the stale banner: it claims `POST /api/chat` is "the one thing still wanted", but `reachout/api/chat.py` exists and `PHASE_3_CHAT_READY` is ticked. | — |
| **M5** | [MANUAL] | **Create and push the two integration branches** from `main`: `jules-demand-integration` (lane D, TASKs 69–75, 77) and `jules-picks-integration` (lane P, TASK 76). Two branches, not one — see M9. | M4 |
| **M6** | [MANUAL] | **Add the demand runner working files to `.gitignore`:** `tools/.jules_runner_state_demand.json`, `tools/.jules_runner_state_picks.json`, `tools/jules_runner_demand.log`, `tools/jules_runner_picks.log`. v1's `.jules_runner_state.json` and `_v2.json` are already ignored; the new ones are not, so they would surface as untracked noise or get committed and conflict on merge. | — |
| **M7** | [MANUAL] | **Amend `docs/JULES_DEMAND.md` before any submission.** Three edits: (a) replace TASK 74's text with the amended, auth-stripped text in §3 of this plan, verbatim; (b) append TASK 77 (§4 of this plan, verbatim) and add it to the phase table under a new phase **D4 — analytics** with flag `DEMAND_API_READY`; (c) **correct the master context block** — it must stop asserting that `demand/` "already exists" and instead state that M1/M2 created it on the integration branch, and it must drop the `demand.retailers` reference. Re-run `python tools/jules_runner.py --dry-run --tasks docs/JULES_DEMAND.md` and confirm it parses **9** tasks. | M1, M2 |
| **M8** | [MANUAL] | **Fix `tools/jules_runner.py` `build_prompt()`.** It hard-appends *"run the backend suite (cd reachout/tests && python -m pytest) and make it fully green"* to **every** task. TASKs 69–75 and 77 write no code in `reachout/` — that command passes trivially having tested nothing, producing a green signal from a suite that ran none of the new code, while directly contradicting the master block's hard rule 2 (`cd demand && python -m pytest`). Make the suite command a per-series value: a `--test-cmd` flag (or a value parsed from the tasks file header), defaulting to the v1 string so existing behaviour is preserved. | — |
| **M9** | [MANUAL] | **Give each lane its own runner isolation.** `WORKTREE` is already derived from `BRANCH` (`tools/.jules-wt-<BRANCH>`), so two lanes on two branches with two state files are already isolated — the hazard is a run-book that told both terminals to use the **same** `--branch` and `--state` (v1 `EXECUTION_PROMPTS.md` §8: A runs `--from 69 --max 7`, B runs `--only 76`, both on `jules-demand-integration`). Fix by construction (M5's two branches) **and** by guard: add a lock file next to the state file, taken on start and released on exit, so a second process on the same state file exits with a clear message instead of racing `git reset --hard` and `json.dump`. | M8 |
| **M10** | [MANUAL] | **Stop the unreviewed auto-push to `main`.** `main()` calls `merge_integration_into_main()` unconditionally after every task, which does `git push origin <BRANCH>:main` with no test run, no review, and no gate. Two changes: (a) run the task's suite **inside the worktree** after the patch applies and before any push — non-zero exit leaves the task `pending` and stops the run; (b) put the merge-to-`main` behind an explicit `--promote-main` flag, default off, so the integration branch is an actual isolation boundary and `main` moves when a human says so. This is the only mechanical control that would catch a Jules task modifying a DO-NOT-MODIFY schema, and it does not exist today. | M8 |
| **M11** | [MANUAL] | **Fix the stale ICM L1.** `reachout/CONTEXT.md` lines 30–34 tell every arriving agent that stages 02 and 05 have no scripts and *"the orchestrator walks 01 → 03 → 04 on the legacy seed data."* Both stages shipped — `stages/02-geo-resolve/`, `stages/05-map-render/`, `tests/test_geo_resolve.py`, `tests/test_map_render.py` all exist and `PROJECT_OVERVIEW.md` §5 documents the full 01→05 chain. Correct the Build-status section. In an ICM repo the routing layer must be true or the whole method degrades to "read everything". While there: `reachout/api/` (the entire Supabase v2 backend — `search.py`, `chat.py`, `supa.py`, `gemini.py`, `madrid.py`, `event_bus.py`) has no L2 contract and is not routed from L1 at all; add a one-paragraph routing entry naming what lives there. | — |
| **M12** | [MANUAL] | **Give `frontend/` its ICM layers.** Write `frontend/CLAUDE.md` (L0) and `frontend/CONTEXT.md` (L1: routes, components, the shell/mode split, the generated-files rule, the URL-is-state-of-record invariant). `frontend/` has never been an ICM workspace — it has `README.md`, `AGENT_NOTES.md`, `DONE.md` instead — and this plan is about to subdivide it into `consumer/` and `retail/` component trees. Adding a third boundary inside a workspace with no layer 0 or 1 makes it a folder convention with no contract behind it. | — |
| **M13** | [MANUAL] | **Update `PROJECT_OVERVIEW.md`** — §2 tracks table to point at this plan; §6 repo map to include `docs/STITCH_FRONTEND.md`, `docs/FINAL_SUMMARY.md`, `docs/frontend_contract_note.md`, `plan.md`, the tick-scratch files, `netlify.toml`, `render.yaml`, `demand/`, and the new `frontend/` L0/L1; §9's "93 backend tests" (STATUS.md PHASE 2 records 240); §5/§7 to acknowledge that `server.py` mounts two search implementations (S6); §12 index to name `docs/TRACKER.md` first. | M11, M12 |

> **Note (2026-08-10):** completed rows in this task list name documents that have since
> been deleted — `STATUS.md`, the run-book, the Stitch specs, `frontend/DONE.md`
> and `frontend/AGENT_NOTES.md`. The rows are kept as the record of what those
> tasks did. All are recoverable from git history; see `docs/CODEBASE_OVERVIEW.md`
> §10 for the full list.

### Lane D — demand service (Jules, branch `jules-demand-integration`)

| # | Wave | Tag | Task | Depends on |
|---|------|-----|------|------------|
| **T69** | 1 | [JULES] | TASK 69 — `TrendsProvider` protocol + `TrendspyProvider` + `FixtureProvider`; canned payloads under `demand/tests/fixtures/trends/` **per the S3 fixture spec (8 weeks × 100 SKUs, including the deliberate high-confidence keyword).** | M1, M2, M5, M7, M8 |
| **T70** | 1 | [JULES] | TASK 70 — keyword-universe builder (`demand/ingest/keywords.py`). | M1, M2, M5, M7, M8 |
| **T71** | 1 | [JULES] | TASK 71 — snapshot store, validate + idempotent upsert (`demand/ingest/snapshot_store.py`). | M1, M2, M5, M7, M8 |
| **T72** | 2 | [JULES] | TASK 72 — `compute_signals.py`; **flips `DEMAND_INGEST_READY`.** Must assert a `high`-confidence row is produced from the fixtures (S3). | T69, T71, M4 |
| **T73** | 3 | [JULES] | TASK 73 — `recommend.py`, signals × store composition, template copy. | T72 |
| **T74** | 4 | [JULES] | TASK 74 (**amended, auth stripped** — full text in §3) — `demand/api/app.py`, public endpoints, schema-validated, 502 pattern. | T73, M7 |
| **T77** | 4 | [JULES] | TASK 77 (**new** — full text in §4) — `GET /demand/api/analytics`, empty-but-shaped fixture segments for the three S1 metrics. | T73, M2, M7 |
| **T75** | 5 | [JULES] | TASK 75 — `run_ingest.py` batch entrypoint; **flips `DEMAND_API_READY`.** | T73, T74, T77, M4 |

### Lane P — consumer picks (Jules, branch `jules-picks-integration`, parallel with lane D from wave 1)

| # | Wave | Tag | Task | Depends on |
|---|------|-----|------|------------|
| **T76** | 1 | [JULES] | TASK 76 — `GET /api/picks` in `reachout/`, deterministic and schema-first; **flips `PICKS_READY`.** Touches nothing in `demand/`; genuinely parallel to lane D by data dependency, and now by tooling too (M5/M9). Verified unblocked: `api.madrid.match_barrio` exists and `server.py` already uses `app.include_router()`, so the one-line mount is real. | M4, M5, M8 |

### Lane U — the app (UI, orchestrating session)

Every UI task below runs against fixtures and schemas (D10), so none of them
waits on a Jules task completing — only on the **schema** existing (M2).

| # | Wave | Tag | Task | Depends on |
|---|------|-----|------|------------|
| **U0** | 3 | [UI] | **App shell + mode toggle.** `main.tsx` currently mounts exactly two routes (`/` → `SearchRoute`, `/results` → `ResultsRoute`). Wrap both in an `AppShell` carrying a top-right toggle reading `?mode=retail` (S2); absent or unrecognised = consumer. Create the two component trees `frontend/src/components/consumer/` and `frontend/src/components/retail/` (prompt §C's third boundary) and move nothing yet — the split is declared before it is populated. Toggle state is derived from the URL only; no store, no context holding mode. Vitest: toggle renders, param round-trips, unknown value falls back to consumer. | M12, S2 |
| **U1** | 3 | [UI] | **Consumer mode inside the shell.** Re-home the existing surface under `components/consumer/`: `MapPanel`, `MapOverlay`, `ShopCard`, `BarrioCombobox`, `TopBar`, `ResultsPanel`, `SearchInput` (all verified present). Fetchers stay on `api/client.ts` against `GET /api/search` per **S6**. No behaviour change — this task is a boundary move with a green build and green vitest as its definition of done. | U0 |
| **U2** | 3 | [UI] | **Retail mode chat pane.** Reuse `components/ChatPanel.tsx` + `chat/shopkeeper.ts` (both exist; `ChatPanel` is already lazy-imported and wired at `routes/results.tsx:17,132`). Left pane of retail mode, client-side mock only, no backend. **Zero backend dependency — this is the single most unblocked node in the plan.** | U0 |
| **U6** | 3 | [UI] | **Dead "ask AI about my analytics" button.** Visible, `disabled`, `aria-disabled`, no handler, no fetcher, tooltip/caption naming it as not yet available. Copy in `i18n/strings.ts`, both languages. It marks the future feature without building it. | U0 |
| **U3** | 4 | [UI] | **Analytics dashboard.** Add `echarts-for-react` (D9). Three charts in `components/retail/charts/`, one per S1 metric — top movers, category mix, stock-out risk — each behind a local wrapper component so D9 is reversible in one folder. Data via a new `fetchAnalytics()` in `api/client.ts` against `GET /demand/api/analytics`, typed from `analytics_response.schema.json` through `npm run gen-types`. **Every rendered number is server-computed; the frontend performs no arithmetic beyond axis formatting.** Confidence chip + always-visible caveat caption on every panel — caption, never tooltip. Loading / empty / error states from the outset (empty-but-shaped is the *normal* state under D10). | U0, M2, T77 (for live fetch; may build against the schema + committed fixture before T77 merges) |
| **U4** | 5 | [UI] | **"Picks for you" rail** in consumer mode against `GET /api/picks`; run `npm run gen-types` first so `picks_response.schema.json` produces its type. Absent-cleanly when there are no picks. | T76, U1 |
| **U5** | 5 | [UI] | **PWA, scoped to consumer routes only** (prompt §B6). Manifest, icons, theme colour, install prompt, offline shell. `docs/STITCH_CONSUMER.md` C7 as written precaches `/` **and** `/shop` with `start_url: "/shop?source=pwa"` — rewrite: `start_url` is `/`, and the service worker's scope and precache list **must exclude anything reached under `?mode=retail`**. A PWA offline shell must not cache the retail analytics view. Test: a retail-mode request is not served from cache. | U0, U1 |
| **U7** | 6 | [UI] | **End-to-end verification** via `.claude/skills/verify/SKILL.md` (Playwright, system Edge). Consumer at 375px: search → results → map/card selection → picks rail. Retail via `?mode=retail`: chat pane responds, three charts render, every panel shows its confidence chip and caveat caption **without hover**, the AI button is present and disabled. Tick `docs/TRACKER.md` and `STATUS.md` with counts. | U3, U4, U5 |

### Lane V / H — verification and housekeeping

| # | Wave | Tag | Task | Depends on |
|---|------|-----|------|------------|
| **V1** | 7 | [MANUAL/FOUNDER] | **Live ingest verify** — the only network-touching step. Run `python -m demand.scripts.run_ingest --provider serpapi --spend` once for real, confirm row counts > 0 in `demand.trend_snapshots`, `demand_signals`, `recommendations`, then drive retail mode against live data. **If SerpApi is unavailable or the 250/month budget is spent: re-run with `--provider fixture` and log "live ingest pending" — do NOT fake live data.** `--dry-run` is not a cheaper rehearsal: it skips database writes, not API calls, and is refused for a paid provider. Needs live keys and M3's applied DDL. **Supersedes the `--provider trendspy` this line used to carry: `trendspy` was removed and `get_provider` now raises `ValueError: Unknown provider` for it. `docs/TRACKER.md:248` is the operative runbook.** | M3, T75, U7 |
| **H1** | 7 | [MANUAL] | **Housekeeping (S5, founder-authorized 2026-08-02).** Delete `debug_tick.py`, `debug_tick2.py`, `test_tick2.py`, `test_tick_debug.py`, `reachout/test_tick_debug.py`, `plan.md`. Move `docs/JULES_BACKEND.md`, `docs/JULES_BACKEND_V2.md`, `docs/STITCH_FRONTEND.md` into `docs/archive/`. Update every inbound reference (`PROJECT_OVERVIEW.md` §12, `docs/TRACKER.md` SKIP THIS). Both suites green afterwards. One commit, reversible from history. | U7 |

### Wave summary

```
Wave 0  M1 M2 M3* M4 M5 M6 M7 M8 M9 M10 M11 M12 M13   (*M3 = founder)
Wave 1  T69 T70 T71  ‖  T76                      (lane D ‖ lane P)
Wave 2  T72                                      → DEMAND_INGEST_READY
Wave 3  T73  ‖  U0 → U1 U2 U6
Wave 4  T74 T77  ‖  U3
Wave 5  T75  ‖  U4 U5                            → DEMAND_API_READY, PICKS_READY
Wave 6  U7
Wave 7  V1* H1                                   (*V1 = founder + live keys)
```

---

## 3. TASK 74 — amended text, verbatim, ready for the runner

*Replaces the TASK 74 block in `docs/JULES_DEMAND.md` (task M7a). Auth fully
stripped per D2 / §F Q5. Copy this into the tasks file exactly as written —
the runner's regex requires the `**TASK 74 — <title>**` header form.*

```
**TASK 74 — demand API app (public, schema-validated, 502 pattern).**
New file `demand/api/app.py`: FastAPI app exposing
`GET /demand/api/health`, `GET /demand/api/trends`,
`GET /demand/api/signals?window=&direction=`,
`GET /demand/api/recommendations?store_id=`. NO AUTHENTICATION: every
endpoint is public for the POC. There is no Authorization header, no JWT
verification, no `SUPABASE_JWT_SECRET`, no `demand.retailers` table and no
`Depends` security dependency anywhere in this task — do not add one, and do
not leave a disabled or commented-out auth path behind. `store_id` on
`/demand/api/recommendations` is an ordinary optional query parameter used
only as a filter; an unknown or absent store_id returns an empty
`recommendations` list with a 200, never a 401 or 403. Every response body
validates against its schema in demand/shared/schemas/ before return
(recommendations use `recommendations_response.schema.json`). All endpoints
are `async def`. Supabase/dep failures -> clean 502 with detail (the reachout
TASK 58/66 pattern), never a raw 500. CORS: localhost:5173 + *.netlify.app,
GET only. Tests in `demand/tests/test_api.py` with TestClient and the fake
client: 200 shapes for all four endpoints; every response schema-validates;
`?store_id=` filters and an unknown store_id yields 200 with an empty list;
`?direction=` and `?window=` filters are asserted on the fake; the fake
raising -> 502 with a detail string and no traceback leak; health returns
200 with no credentials of any kind supplied. Add one explicit test asserting
that no endpoint returns 401 or 403 under any input, so a future
reintroduction of auth cannot land silently.
```

---

## 4. TASK 77 — new, verbatim, ready for the runner

*Appended to `docs/JULES_DEMAND.md` under a new phase **D4 — analytics**
(flag: `DEMAND_API_READY`), task M7b. Same format as TASKs 69–76.*

```
**TASK 77 — GET /demand/api/analytics (fixture-first, inventory-type keyed).**
First add `demand/shared/schemas/analytics_response.schema.json`,
additionalProperties:false at every level, shaping the retail dashboard's
payload: `{inventory_type: const "convenience_store", generated_from: enum
["fixture","live"], generated_at: date-time, caveat: non-empty string,
segments: {top_movers: {...}, category_mix: {...}, stock_out_risk: {...}}}`.
Each of the three segments is an object `{confidence: enum low|medium|high,
points: [...]}` whose `points` array MAY BE EMPTY — empty-but-shaped is a
valid, expected response, not an error. `top_movers` points are
`{keyword, category, interest_avg, delta_pct, direction}`; `category_mix`
points are `{category, share_pct, product_count}`; `stock_out_risk` points are
`{category, at_risk_count, total_count, risk_pct}`. No barrio field anywhere
(Google Trends does not resolve below ES-MD and nothing may pretend
otherwise). Then extend `demand/api/app.py` with
`GET /demand/api/analytics?store_id=&inventory_type=` (inventory_type default
and only supported value for the POC: `convenience_store`; any other value ->
422). Public, no auth, async, response validated against the new schema
before return, Supabase/dep failure -> 502. The handler reads committed
fixture JSON at `demand/api/fixtures/analytics_convenience_store.json` when
`DEMAND_ANALYTICS_SOURCE` is unset or `fixture` (the default), and computes
from `demand.demand_signals` + `public.products` via the injected client when
it is `live` — the response shape is byte-identical in both modes, which is
the entire point. Commit the fixture file, populated consistently with the
8-week x 100-SKU fixture set (see demand/tests/fixtures/README.md) and
including at least one `high`-confidence segment. `caveat` is the canonical
string from docs/IMPLEMENTATION_PLAN.md 3.3 and is required by the schema, so
an analytics response without one cannot validate and cannot be served. There
is NO footfall metric and no field that could be relabelled as one. Tests in
`demand/tests/test_api_analytics.py` with TestClient and the fake client:
fixture mode returns 200 and schema-validates; an empty `points` array
validates (assert explicitly); live mode over the fake produces the identical
shape; unknown inventory_type -> 422; missing caveat fails validation
(construct the payload and assert the validator rejects it); fake raising ->
502. No network.
```

---

## 5. Data contracts

Schema-first, unchanged as a rule: if a consumer needs a field that no schema
defines — schema first, backend second, `npm run gen-types` third. Every schema
below is `"additionalProperties": false` at every level. The SQL is idempotent
DDL creating the **`demand`** Postgres schema: zero tables added to `public`,
zero changes to `reachout/data/schema.sql`.

Columns and confidence rules are carried forward from
`docs/IMPLEMENTATION_PLAN.md` §3 — **that document remains the source text for
§5.1–§5.3 even though it is superseded for routing.** Amendments below are the
auth removal and the new analytics contract.

### 5.1 `demand.trend_snapshots` — raw captures

**Schema:** `demand/shared/schemas/trend_snapshot.schema.json` ·
**Produced by:** TASK 69/71 · **Consumed by:** TASK 72

| column | type | notes |
|--------|------|-------|
| id | uuid pk | |
| keyword | text not null | as sent to the provider |
| geo | text not null | `ES-MD` (Madrid community scope) |
| timeframe | text not null | e.g. `today 3-m` |
| provider | text not null | `trendspy` now; paid adapter later (D1) |
| captured_at | timestamptz not null | |
| series | jsonb not null | `[{date, value 0–100}]`, schema-validated before insert |
| region_breakdown | jsonb | interest-by-region payload if available |

Unique on `(keyword, geo, timeframe, captured_at::date)` → idempotent
re-ingestion. Raw snapshots older than 180 days are pruned.
**Fixtures:** `demand/tests/fixtures/trends/*.json` (TASK 69), per S3.

### 5.2 `demand.demand_signals` — derived, pure Python

**Schema:** `demand/shared/schemas/demand_signal.schema.json` ·
**Produced by:** TASK 72 · **Consumed by:** TASKs 73, 77, `/demand/api/signals`

| column | type | notes |
|--------|------|-------|
| id | uuid pk | |
| keyword | text not null | |
| category | text | mapped product category, nullable |
| geo | text not null | `ES-MD` — **honesty note:** Trends does not resolve to barrio; barrio attribution happens only in recommendations via store composition, and the schema has no barrio column here so nothing can pretend otherwise |
| window_start / window_end | date not null | |
| interest_avg | numeric not null | 0–100 |
| delta_pct | numeric not null | vs prior window |
| direction | text not null | enum `rising`/`falling`/`flat`, fixed ±15% thresholds |
| rank | int not null | dense, within window |
| confidence | text not null | enum `low`/`medium`/`high` (§5.6) |
| snapshot_ids | uuid[] not null | provenance |
| computed_at | timestamptz not null | |

**Fixtures:** `demand/tests/fixtures/signals/*.json` + committed golden expected
rows for TASK 72's byte-for-byte tests.

### 5.3 `demand.recommendations` — retailer-facing

**Schemas:** `recommendation.schema.json`, envelope
`recommendations_response.schema.json` · **Produced by:** TASK 73 ·
**Consumed by:** `GET /demand/api/recommendations`

| column | type | notes |
|--------|------|-------|
| id | uuid pk | |
| store_id | uuid not null | references `public.stores(id)` |
| signal_id | uuid not null | references `demand.demand_signals(id)` |
| headline | text not null | Python string template, **no AI** |
| body | text not null | Python string template |
| action | text not null | enum `stock_up`/`feature_in_window`/`watch` |
| confidence | text not null | **required**, copied verbatim from the signal, never recomputed |
| caveat | text not null | **required, non-empty** — canonical: "Basado en interés de búsqueda en Madrid, no en compras reales." |
| created_at | timestamptz not null | |

**Removed from v1:** the `demand.retailers` table and all RLS policies (D2).
`store_id` is a plain filter parameter, not an authorization subject.

### 5.4 `picks_response.schema.json` — consumer picks

**Schema:** `reachout/shared/schemas/picks_response.schema.json` ·
**Produced by:** TASK 76 · **Consumed by:** `GET /api/picks` → U4's rail
`{picks: Product[], generated_by: const "deterministic"}`, Product mirroring
`SHARED_CONTRACT.md`. Types flow to the frontend via `npm run gen-types`.

### 5.5 `analytics_response.schema.json` — retail dashboard (NEW)

**Schema:** `demand/shared/schemas/analytics_response.schema.json` ·
**Produced by:** TASK 77 · **Consumed by:** `GET /demand/api/analytics` → U3's
three charts

Top level: `inventory_type` (const `convenience_store`), `generated_from`
(enum `fixture`/`live`), `generated_at`, `caveat` (required, non-empty),
`segments`. Three segments, each `{confidence, points[]}` and each permitted to
be empty:

| segment | point shape | source when live |
|---|---|---|
| `top_movers` | `{keyword, category, interest_avg, delta_pct, direction}` | `demand.demand_signals` |
| `category_mix` | `{category, share_pct, product_count}` | `public.products` composition |
| `stock_out_risk` | `{category, at_risk_count, total_count, risk_pct}` | `public.products.stock_qty` |

No footfall segment and no field that could be relabelled as one (S1).
No barrio field (§5.2 honesty note).
**Fixture standing behind the endpoint:**
`demand/api/fixtures/analytics_convenience_store.json` (committed, D10).

### 5.6 Confidence rules — deterministic, in `compute_signals.py`, never model-assigned

`high` = ≥8 weeks of data **and** `interest_avg ≥ 20` **and** direction stable
across the last 3 windows. `medium` = ≥4 weeks **and** `interest_avg ≥ 10`.
`low` = everything else, including any series with provider gaps.

**S3 consequence, binding on M2 and TASK 69:** the fixture set is exactly 8
weeks, which is the `high` tier's floor. A naively generated fixture set will
produce zero `high` rows and the tier will go untested while the suite stays
green. At least one fixture keyword must be constructed to satisfy all three
conditions, and TASK 72's tests must assert that a `high` row is produced.

### 5.7 Cross-boundary payload index

| Payload | Schema | Producer | Consumer | Fixture standing behind it |
|---|---|---|---|---|
| Trend capture | `trend_snapshot.schema.json` | TASK 69/71 | TASK 72 | `demand/tests/fixtures/trends/*.json` |
| Demand signal | `demand_signal.schema.json` | TASK 72 | TASKs 73, 77 | `demand/tests/fixtures/signals/*.json` + goldens |
| Recommendation | `recommendation.schema.json` | TASK 73 | API | fixture signals via fake client |
| Recommendations response | `recommendations_response.schema.json` | TASK 74 | (no v2 UI consumer) | — |
| Analytics response | `analytics_response.schema.json` | TASK 77 | U3 charts | `demand/api/fixtures/analytics_convenience_store.json` |
| Picks response | `picks_response.schema.json` | TASK 76 | U4 rail | `reachout/tests` `fake_supa` fixtures |
| Ranked shops / map GeoJSON / shops GeoJSON | existing `reachout/shared/schemas/` | pipeline stages 04/05 | U1 consumer mode | `reachout/data/osm_cache/` (S6) |

---

## 6. Risks and concrete mitigations

Only mitigations that a task in §2 actually builds. Aspirations are not listed.

| Risk | Concrete mitigation (a task builds this) |
|---|---|
| **Jules is told to run the wrong test suite** and reports green having tested nothing | **M8** makes the suite command per-series; **M10** runs the suite in the worktree and refuses to push on a non-zero exit. Today neither exists and the failure is silent and green. |
| **A Jules task edits a DO-NOT-MODIFY file** (a schema, `schema.sql`, anything in `frontend/`) and reaches `main` unreviewed | **M10** gates the push on a green in-worktree suite and puts merge-to-`main` behind `--promote-main`, default off. `git apply --3way` inspects nothing; this is the only mechanical check in the system. |
| **Two runner lanes race** on one branch / state file / worktree (the v1 run-book instructs exactly this) | **M5** gives each lane its own branch; `WORKTREE` already derives from `BRANCH`; **M9** adds a lock file beside the state file so a second process on the same state exits with a message instead of racing `git reset --hard`. |
| **Jules works in a `demand/` that does not exist** while its master block says it does | **M1** creates it, **M2** fills the contracts, **M7c** rewrites the master block so it stops asserting a false precondition. `--dry-run` reparse (M7) is the check. |
| **A phase flag flip is skipped or hallucinated** because the target line is absent | **M4** adds the three lines. TASKs 72/75/76 each flip exactly one, only after their phase is green; `docs/TRACKER.md`'s contract-flags block mirrors them with `SHARED_CONTRACT.md` named as authoritative. |
| **Trends interest presented as purchase fact** | Three built layers: (1) `recommendation.schema.json` and `analytics_response.schema.json` both make `confidence` and a non-empty `caveat` **required** — a caveat-less payload cannot validate, so it cannot be served; (2) confidence is assigned by the deterministic rules in §5.6, never by a model; (3) **U3** renders the caveat as an always-visible caption, never a tooltip, and **U7** asserts it renders without hover. |
| **A metric is shown that has no data behind it** | **S1** drops footfall proxy at the plan level, **TASK 77** forbids a footfall segment or any relabellable field at the schema level, and §7 records the reason. The schema is the enforcement, not the policy. |
| **The `high` confidence tier goes untested** because the fixture window is exactly at its floor (S3) | **M2** writes the fixture spec requiring a deliberate high-confidence keyword; **TASK 69** commits it; **TASK 72**'s tests assert a `high` row is produced. |
| **Free-scrape fragility** — `trendspy` breaks or is rate-limited | Provider interface (TASK 69) isolates the blast radius; idempotent upserts (TASK 71/75) leave prior snapshots intact; **D10 + TASK 77's `DEMAND_ANALYTICS_SOURCE=fixture` default** mean the dashboard renders a real, schema-valid, honestly-labelled payload with no live data at all; **V1** explicitly instructs falling back to `--provider fixture` and logging "live ingest pending" rather than faking live data. |
| **DDL cannot be applied by an agent** (probed: the available key cannot execute DDL) | **M3** is tagged `[MANUAL/FOUNDER]` and appears in `docs/TRACKER.md` with Who = "You (founder)", so the stall is visible instead of silent. Nothing except V1 depends on it. |
| **The PWA caches the retail analytics view** | **U5** scopes the service worker and precache list to consumer routes, `start_url` `/`, with a test asserting a `?mode=retail` request is not served from cache. |
| **The chart library becomes a general UI dependency** and erodes the no-UI-library convention | **U3** confines every ECharts import to `components/retail/charts/` behind local wrappers; D9's reversal path is a rewrite of that one folder. |
| **A cold session cannot tell what to do next** | **`docs/TRACKER.md`** — four-line state header, six-column task table with a "You (founder)" actor and a four-state Done? column, read-first/update-last protocol, in the same commit as the work. |
| **The ICM routing layer misinforms every arriving agent** | **M11** corrects `reachout/CONTEXT.md`'s claim that stages 02/05 have no scripts and adds a routing entry for the unrouted `reachout/api/`; **M12** gives `frontend/` its missing L0/L1 before it is subdivided. |

---

## 7. Out of scope (deliberate)

Carried from `docs/IMPLEMENTATION_PLAN.md` §5, updated for v2.

- **Footfall proxy metric** *(new in v2, §F Q2)* — **dropped for lack of any data source.** Nothing in this repo measures footfall, and Google Trends does not resolve below `ES-MD` (`IMPLEMENTATION_PLAN.md` §3.2). A footfall tile would be a number invented to fill a chart, which is the precise failure the confidence/caveat system exists to prevent. It returns only with a real source (POS feed, door counter, or a licensed mobility dataset) as a new schema field and a new task — never as a relabelling of trends data.
- **Authentication of any kind** *(new in v2, D2 override)* — no login, no magic link, no JWT, no `demand.retailers`, no RLS. Retail mode is reached by the toggle. Design preserved at `IMPLEMENTATION_PLAN.md` §3.4.
- **Separate `/shop` and `/dashboard` route trees** *(new in v2)* — replaced by one shell plus `?mode=retail` (S2).
- **Delivery / courier system** — no matching-engine code; the partner-vs-build memo is the only deliverable (D7).
- **AI shop-chat build** — gated on live inventory sync; precondition checklist only. Retail mode's chat pane is the existing client-side mock. The "ask AI about my analytics" button is deliberately dead (U6).
- **Live inventory sync with real shops** — precondition for chat, not buildable now; nothing depends on it.
- **Payments / checkout / cart** — the consumer CTA stops at "visit/reserve at shop".
- **Native mobile app** — D3: responsive web + PWA only.
- **Paid data providers** — D1/D8: $0 ceiling; the adapter interface exists, paid implementations do not.
- **Embedding-model migration** — D4: `gemini-embedding-001` stays.
- **Refactoring `reachout/api/server.py`** — the tangle is contained, not untangled: demand code lives in `demand/`, and TASK 76 adds only a router mount line.
- **Migrating consumer search to the Supabase `POST /api/search`** *(new in v2, S6)* — the two search implementations coexist; the v2 consumer UI stays on the pipeline `GET /api/search`.

---

*Live board: `docs/TRACKER.md` — read it first, update it last, in the same
commit as the work.*
