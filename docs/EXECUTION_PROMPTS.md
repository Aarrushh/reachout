# EXECUTION_PROMPTS.md — Terminal Run-Book for the Overnight Build

*The operational layer for `docs/IMPLEMENTATION_PLAN.md`. Everything here is
paste-ready: open the terminals listed in §8, paste each fenced PROMPT block
into a local Claude Code session in the stated order, and the loop runs
itself. Fuel files: `docs/JULES_DEMAND.md` (TASKs 69–76),
`docs/STITCH_DASHBOARD.md` (D1–D5), `docs/STITCH_CONSUMER.md` (C1–C8).
Keys: put `JULES_API_KEY` and `STITCH_API_KEY` in the repo-root `.env`
(alongside the existing `SUPABASE_URL`/`SUPABASE_KEY`/`GEMINI_API_KEY`);
`tools/jules_runner.py` already reads `.env` itself.*

---

## §0 Overview — what gets created, with what tools and what logic

### Artifacts this run produces

| Artifact | Where | Built by |
|---|---|---|
| `demand/` service: trends ingest → pure-Python signals → recommendations → auth'd FastAPI | `demand/` (new top-level, own ICM workspace) | Jules TASKs 69–75 on scaffold from Terminal A |
| `demand` Postgres schema (4 tables) + 4 JSON Schemas | `demand/data/schema.sql`, `demand/shared/schemas/` | Terminal A (Claude Code — schemas/DDL never go to Jules) |
| Retailer dashboard UI (login, overview, movers, per-store recs) | `frontend/src/routes/dashboard/`, `components/dashboard/` | Stitch D1–D5, integrated in Terminal A |
| `GET /api/picks` deterministic recommendations + schema | `reachout/api/picks.py`, `reachout/shared/schemas/` | Jules TASK 76 |
| Consumer shopping PWA (home, browse, search, detail, picks rail, reserve CTA, manifest+SW) | `frontend/src/routes/shop/`, `components/shop/`, `frontend/public/` | Stitch C1–C8, integrated in Terminal B |
| Delivery partner-vs-build memo; shop-chat gate checklist | `docs/DELIVERY_PARTNER_VS_BUILD.md`, `docs/SHOP_CHAT_GATE.md` | Terminal C (paper only) |

### Tools in play

- **Jules API** via `tools/jules_runner.py` — runs as a plain background
  Python process (zero Claude tokens while polling); patch-and-merge onto
  `jules-demand-integration`, state in
  `tools/.jules_runner_state_demand.json`, restart-safe.
- **Google Stitch API** (`STITCH_API_KEY` from `.env`) — one screen/
  component per prompt; **fallback** (proven by the 12-prompt Amazon run):
  Claude Code implements the same prompt text directly; v0.dev is the
  secondary fallback per `STITCH_FRONTEND.md` §2.
- **trendspy** (free scraping, $0) behind a `TrendsProvider` interface —
  paid providers are a later config swap (plan §0 D1/D8).
- **Supabase** — Postgres + pgvector (existing), new `demand` schema, Auth
  magic-link + RLS for retailers.
- **FastAPI + APScheduler** backend; **React 19 + Vite + TanStack** front;
  **Playwright** via the repo-local `verify` skill.
- **Token savers**: caveman output style + `rtk` command wrapping (§2).

### Coding logic (the invariants every task obeys)

1. **Exactness is pure Python** — signal math, confidence rules
  (fixed thresholds: ±15% direction, 8-week/20-interest high bar), picks
  ranking, DB writes. No AI call anywhere in `demand/` or `picks.py`.
2. **Schema gates** — every cross-boundary payload validates against an
  `additionalProperties:false` schema before anything trusts it; retailer
  recommendations cannot exist without `confidence` + `caveat` (the schema
  forbids it, the UI renders it non-dismissibly).
3. **Provider interface + idempotent upserts** — ingestion is swappable and
  re-runnable; a failed scrape degrades to stale-data-with-timestamp,
  never fabricated data.
4. **Template copy** — retailer-facing text from Python string templates.
5. **Offline-testable tasks** — Jules VMs hold no keys; fakes + fixtures
  everywhere; live keys touch only Terminal A's final steps.

---

## §1 P0 — Preflight prompt (paste FIRST, in every terminal)

```
PREFLIGHT. Repo: reachout root. Terse mode: answers <=5 lines each step.
1. git fetch origin && git status -sb. If docs/IMPLEMENTATION_PLAN.md,
   docs/JULES_DEMAND.md, docs/STITCH_DASHBOARD.md, docs/STITCH_CONSUMER.md
   missing from this branch: STOP, tell me to merge PR #2 to main first.
2. Check .env has JULES_API_KEY, STITCH_API_KEY, SUPABASE_URL, SUPABASE_KEY,
   GEMINI_API_KEY (report present/absent only, NEVER print values).
3. python tools/jules_runner.py --dry-run --tasks docs/JULES_DEMAND.md
   --state tools/.jules_runner_state_demand.json  -> expect "parsed 8 tasks".
4. which rtk  -> if found, prefix every git/pytest/npm command you run from
   now on with `rtk`; else use -q/--quiet flags everywhere.
5. List wired plugins/skills; report which of these are available:
   caveman, icm-architect, Understand-Anything, superpowers, system-design,
   frontend, mattpocock skills, repo skill `verify`. For each missing one
   use the fallback named in docs/EXECUTION_PROMPTS.md §6 — do not install
   anything, do not ask.
6. If caveman is wired, switch to it now (/caveman or its output style).
Report: READY or the exact blocker. Nothing else.
```

## §2 TOKEN RULES block (paste at the top of the first prompt in each terminal, after P0)

```
TOKEN RULES for this whole session:
- caveman style if wired; else: no preamble, no recap, <=5 lines per status,
  bullet fragments fine, full sentences only in committed files.
- rtk-prefix git/pytest/npm if installed (P0 step 4 said which).
- NEVER paste file contents into chat; name paths. Read only files the
  current task's contract names (ICM discipline, reachout/CLAUDE.md).
- State lives in files (STATUS.md, tools/.jules_runner_state_demand.json,
  SHARED_CONTRACT.md flags), not in this conversation. Assume this session
  can die any time; after every completed step, commit + update STATUS.md
  so a fresh session resumes from files alone.
- Long waits = background processes + file polling, never chat polling.
- Budget: $0 new paid APIs (plan §0 D8). If a step needs one, log it in
  STATUS.md under "skipped (budget)" and continue.
```

---

## §3 Terminal A — Track A orchestrator (demand service + dashboard)

### A-P1 — scaffold + contracts (waves 1)

```
[TOKEN RULES block here]
TRACK A, step 1 of 4. Execute docs/IMPLEMENTATION_PLAN.md §2 tasks A1+A2
exactly; contracts are in §3 of that plan — do not redesign them.
1. If system-design or Understand-Anything wired: one-pass review of
   reachout/api/ boundaries first (<=10 lines, no refactors). Else skip.
2. Scaffold demand/ per icm-architect conventions; fallback: mirror
   reachout/'s layer structure (CLAUDE.md L0, CONTEXT.md L1, _config/,
   shared/schemas/, ingest/, scripts/, api/, tests/ with conftest.py
   sys.path setup copied from reachout/tests style). Write demand/CLAUDE.md
   + CONTEXT.md stating the one rule and stage routing.
3. Author the 4 schemas in demand/shared/schemas/ and demand/data/schema.sql
   (idempotent, schema `demand`, tables trend_snapshots, demand_signals,
   recommendations, retailers, RLS per plan §3.4) + a starter
   demand/_config/seed_keywords.json (30-50 Madrid retail terms, ES).
4. Apply schema.sql to Supabase using .env creds (psql or supabase client).
   Verify: the 4 tables exist under schema demand.
5. Add "DEMAND" flag block ([ ] DEMAND_INGEST_READY / DEMAND_API_READY /
   PICKS_READY) to SHARED_CONTRACT.md + a Track A section in STATUS.md.
6. Commit. Create branch jules-demand-integration from HEAD, push both.
Print: SCAFFOLD DONE + table names verified. Stop.
```

### A-P2 — Jules loop (waves 2–4 backend; runs unattended)

```
TRACK A, step 2 of 4 — the Jules loop. TASKs 69-75 of docs/JULES_DEMAND.md.
1. Launch as a BACKGROUND process (do not foreground, do not sleep-poll):
   python tools/jules_runner.py --tasks docs/JULES_DEMAND.md
     --state tools/.jules_runner_state_demand.json
     --branch jules-demand-integration --from 69 --max 7
2. LOOP until state file shows 69-75 completed: wake only when the
   background process exits or notifies; each wake -> read the state JSON +
   git log of jules-demand-integration; review the newly merged diff
   (contract check only: schemas untouched, no AI calls in demand/, tests
   added); tick STATUS.md; if the runner died, relaunch it (it reattaches).
   If a task FAILED: read its session log, fix forward with a minimal
   commit on jules-demand-integration yourself, then relaunch with
   --from <next>.
3. When 69-75 done and DEMAND_INGEST_READY + DEMAND_API_READY flags are
   [x]: merge jules-demand-integration -> main, push.
Print per wake: TASK nn merged|failed, 1 line. At end: JULES A DONE. Stop.
```

### A-P3 — dashboard UI (Stitch D1–D5) + auth wiring

```
TRACK A, step 3 of 4. Execute docs/STITCH_DASHBOARD.md prompts D1->D5 in
order. For each: if STITCH_API_KEY works, submit master-context+prompt to
the Stitch API and integrate the returned code; else implement the prompt
text directly yourself (proven fallback). After each prompt:
cd frontend && npm run build && npm test (rtk-prefixed), fix types, commit.
Use frontend/mattpocock conventions if those plugins are wired; else match
existing frontend/src style. Then A11 (plan §2): enable Supabase magic-link
auth, insert demand.retailers rows for the pilot stores (ask Supabase for
2-3 existing store ids), apply RLS policies from demand/data/schema.sql.
Print: DASH UI DONE after D5 + auth verified with one magic-link roundtrip
note. Stop.
```

### A-P4 — live verify (A12, the only network-heavy step)

```
TRACK A, final step. Run demand/scripts/run_ingest.py --provider trendspy
once for real (env from .env). Verify row counts >0 in demand.trend_snapshots,
demand_signals, recommendations (print counts). Start backend + demand API +
frontend per the repo `verify` skill; drive /dashboard with Playwright:
login state, overview tiles render, every RecCard shows confidence chip +
caveat caption without hover. Tick STATUS.md Track A COMPLETE with counts.
If trendspy is blocked/rate-limited: rerun with --provider fixture, mark
STATUS.md "live ingest pending (scrape blocked)" — do NOT fake live data.
Print: TRACK A COMPLETE (or the one blocker). Stop.
```

---

## §4 Terminal B — Track B orchestrator (consumer PWA)

### B-P1 — types + picks task

```
[TOKEN RULES block here]
TRACK B, step 1 of 3. Plan §2 tasks B1+B2.
1. cd frontend && npm run gen-types && npm run build && npm test — all
   green, commit any regenerated types.
2. WAIT-CONDITION: branch jules-demand-integration must exist (Terminal A
   A-P1 creates it). If absent, print WAITING ON A-P1 and stop — rerun this
   prompt later.
3. Launch background: python tools/jules_runner.py --tasks
   docs/JULES_DEMAND.md --state tools/.jules_runner_state_demand.json
   --branch jules-demand-integration --only 76
4. On completion wake: review TASK 76 diff (schema-first, single mount line
   in server.py, deterministic ranking, both suites green), then
   cd frontend && npm run gen-types (picks_response schema -> types),
   commit. Tick STATUS.md.
Print: PICKS READY. Stop.
```

### B-P2 — consumer UI loop (Stitch C1–C8)

```
TRACK B, step 2 of 3. Execute docs/STITCH_CONSUMER.md prompts C1->C8 in
order — same Stitch-API-else-direct rule as Terminal A. C5 requires B-P1's
PICKS READY; if not there yet, do C1-C4, print BLOCKED AT C5, stop, and
resume from C5 when re-prompted. C6 and C8 are read-only audits: apply
their minimal diffs only. After each prompt: build + vitest, fix, commit
(one commit per prompt, message "C<n>: <title>").
Print after each: C<n> ok. At end: CONSUMER UI DONE. Stop.
```

### B-P3 — e2e verify

```
TRACK B, final step. Production build (npm run build), then per the repo
`verify` skill drive a 375px viewport: /shop home -> barrio "mala" ->
Malasaña -> query "algo para el dolor de cabeza" -> results with
interpreted_as echo -> product detail -> reserve sheet opens -> picks rail
renders (or absent cleanly if no picks). Then Lighthouse PWA pass on vite
preview: installable + offline fallback. Tick STATUS.md Track B COMPLETE
with check counts. Print: TRACK B COMPLETE (or blockers). Stop.
```

---

## §5 Terminal C — paper track (cheap; run on a small/fast model)

```
[TOKEN RULES block here]
PAPER TRACK, one pass, no code. Write two docs per plan §2 C1+C2 and §5:
1. docs/DELIVERY_PARTNER_VS_BUILD.md — partner APIs (Glovo-style, white-
   label couriers) vs building courier ops for Madrid: Ley Rider / EU
   classification exposure, integration cost, pilot-volume unit economics,
   recommendation + 3 decision criteria that would flip it.
2. docs/SHOP_CHAT_GATE.md — preconditions to un-gate AI shop-chat: live
   inventory sync in prod + freshness SLA + retrieval-then-template over a
   fresh stock read (stage-04 schema-gated pattern), never open-ended
   generation about stock; include the go/no-go checklist.
Commit both, tick STATUS.md Track C. Print: PAPER DONE. Stop.
```

---

## §6 Skills × repo × task matrix

| Repo / skill | Used in | Exactly for | Fallback if not wired |
|---|---|---|---|
| `JuliusBrussee/caveman` | all terminals | compressed output style, every reply | TOKEN RULES manual terse mode (§2) |
| `rtk` (CLI, not a plugin) | all terminals | wrapping git/pytest/npm output | `-q`/`--quiet` flags |
| `RinDig/icm-architect` | A-P1 | `demand/` folder-as-architecture scaffold | mirror `reachout/CLAUDE.md` layers by hand |
| `Egonex-AI/Understand-Anything` | A-P1 step 1; before any `server.py` touch (TASK 76 review in B-P1) | pre-change comprehension pass | targeted Read of the named files only |
| `superpowers` bundle | A-P2/B-P2 loops | plan-execution + TDD discipline (precedent: `docs/superpowers/`) | follow JULES/STITCH doc order literally |
| `system-design` bundle | A-P1 step 1 | one-shot boundary review of `demand/` vs `reachout/` | skip (plan §3 already fixes boundaries) |
| `frontend` bundle | A-P3, B-P2 | integrating Stitch output into React/Vite conventions | match existing `frontend/src` style |
| `mattpocock/skills` | A-P3, B-P2 | TypeScript typing quality on generated code | `npm run build` (tsc) as the gate |
| repo skill `verify` (`.claude/skills/verify`) | A-P4, B-P3 | launch + Playwright drive recipe | commands are inlined in the skill file — read it |
| `hesreallyhim/awesome-claude-code`, `Piebald-AI/claude-code-system-prompts` | — | reference reading only | no runtime role, never load in-loop |

## §7 Morning checklist (founder, ~5 min)

1. `cat STATUS.md` — three track sections ticked? Any "skipped (budget)" or
   "live ingest pending" lines?
2. `cat tools/.jules_runner_state_demand.json` — 69–76 all completed?
3. `git log --oneline main -15` and open PRs — everything merged that
   claims to be?
4. `SHARED_CONTRACT.md` — DEMAND_INGEST_READY / DEMAND_API_READY /
   PICKS_READY all `[x]`?
5. Smoke: dashboard at `/dashboard` (magic-link login → caveat captions
   visible), consumer at `/shop` on your phone (install prompt on second
   visit).
6. Revisit plan §0 decision table — flip D1 (paid trends) or D8 (budget)
   now if you want tonight's fixture-mode gaps filled.

## §8 Launch order (TL;DR)

| Terminal | Paste order | Parallel from |
|---|---|---|
| A | P0 → A-P1 → A-P2 → A-P3 → A-P4 | start |
| B | P0 → B-P1 → B-P2 → B-P3 | start (B-P1 waits only on A-P1's branch push) |
| C | P0 → §5 prompt | any time |

Jules runner and Stitch calls do the heavy lifting; the Claude sessions
only contract-check, integrate, and tick state files — that, plus caveman +
rtk + files-as-state, is where the tokens are saved.
