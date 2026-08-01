# PLAN_V2_PROMPT.md — the prompt that produces Implementation Plan v2

*Written 2026-08-01. Paste this entire file into a fresh Claude (Opus/Fable)
session opened at the repo root. Preconditions: you are on `main`, PR #2 has
been merged (so this file and the v1 plan-pack are both on `main`), and the
working tree is clean. This prompt makes the session ask questions FIRST and
write the plan SECOND. Its only outputs are `docs/IMPLEMENTATION_PLAN_V2.md`
and `docs/TRACKER.md` — no service code, no UI code, no deletions.*

---

## §0 How this prompt works — two phases

**Phase 1 is read-only.** You audit the repo, explain the machine back to the
founder in plain language, and ask the numbered questions in §F in small
batches (3–5 at a time, most important first). Hard rules for Phase 1:

1. Do NOT edit, create, delete, move, or rename any file. Not even docs.
2. No git write commands (commit/push/checkout -b/merge), no subagents, no
   PRs, no Jules calls, no Stitch calls.
3. Read-only tools only: ls, Read, grep, git log / git diff / git status.
4. If you are unsure whether an action writes, assume it does and don't do it.
5. If a doc says something the code contradicts, say so plainly — do not
   paper over a gap with a confident guess.

Phase 1's audit agenda (cover in order, pausing for the founder to react):

- **A. One-paragraph truth** — what this system is and what it does next,
  five sentences max, as told to an engineer joining tomorrow.
- **B. Doc inventory** — verify §A below against the repo; for each file:
  its actual job, who reads it, INPUT / STATE / OUTPUT, needs edits Y/N.
- **C. Governance** — how the repo governs itself and where an agent could
  go off the rails with nothing to catch it.
- **D. Offload model** — who does what work and where the boundary is drawn
  wrong (verify §D below).
- **E. Graph engineering** — the task DAG: nodes, edges, derived
  parallelism, restartability; draw the next phase's dependency tree and
  flag any node secretly blocked by something the docs deny.
- **F. ICM as updated** — the layer rule and the second workspace; report
  any place the repo violates its own rule (verify §C below).
- **G. Context persistence** — what a cold session reads to resume; rate
  each mechanism working vs. aspirational; name the biggest leak.
- **H. Tracker design** — refine the `docs/TRACKER.md` shape specced in §C.
- **I. Orchestration runtime** — lanes, dispatch, merge, failure modes, and
  for each failure mode what catches it (or say "nothing catches this").
- **J. Honest verdict** — well-designed / ceremony / missing-and-will-bite.

**Phase 2 unlocks only when the founder has answered the §F questions** or
explicitly said "take the defaults." Every unanswered question resolves to
its recommended default and is recorded in a **reversible decision table**
(the v1 §0 pattern: what was decided, why, how to reverse it). Phase 2 may
write exactly two files — `docs/IMPLEMENTATION_PLAN_V2.md` and
`docs/TRACKER.md`, per the §G contract — and nothing else. Still no Jules
submission, no code, no UI.

---

## §A What exists right now, in plain words

One line per doc. "Live fuel" = drives future work. "History" = record of
finished work; read for context, never as instructions.

- `docs/IMPLEMENTATION_PLAN.md` — the v1 overnight plan with the D1–D8
  decision table. Superseded (banner on file); its decision-table *pattern*
  and most decisions carry forward, its task routing does not.
- `docs/EXECUTION_PROMPTS.md` — the v1 terminal run-book. Superseded; it
  blocks on a key that cannot exist (see §B) and routes UI work to a
  nonexistent API.
- `docs/JULES_DEMAND.md` — Jules TASKs 69–76 with the master context block
  and phase flags. **Still current** except TASK 74's auth section (see §B);
  this is real fuel the runner already parses.
- `docs/STITCH_DASHBOARD.md`, `docs/STITCH_CONSUMER.md`,
  `docs/STITCH_FRONTEND.md` — good UI design specifications mislabelled as
  API call series. Kept as specs; the "API" framing is dead (see §B).
- `docs/JULES_BACKEND.md`, `docs/JULES_BACKEND_V2.md` — TASKs 01–68,
  finished and merged. History.
- `AGENTS.md` — the v1 ten-workstream protocol and batch graph. History,
  but its Batch 1→5 dependency graph is the precedent §C cites.
- `STATUS.md` — the append-only cross-session log. STATE; stays the
  historical log after `docs/TRACKER.md` becomes the live board.
- `SHARED_CONTRACT.md` — the phase flags (`PHASE_1..4`, all ticked) and the
  planned `DEMAND_INGEST_READY` → `DEMAND_API_READY` → `PICKS_READY` chain
  (not yet in the file — a designated Jules task ticks each one).
  Live fuel: these flags are the DAG's edges.
- `PROJECT_OVERVIEW.md` — orientation: the aim, ICM layers, graph
  engineering. Current.
- `plan.md` (repo root) — a 27-line tick-scheduler micro-plan whose work
  already shipped per STATUS.md. Superseded (banner on file).
- `tools/jules_runner.py` — the Jules submission loop; `--tasks/--state/
  --branch` flags make new task series first-class. Live tooling.

## §B What needs editing, how, and why

Concrete, per file. (These edits are *instructions to the v2 plan*, not
edits this prompt performs.)

1. **Remove the Stitch key prerequisite.** `grep` for Stitch across every
   `.py`, `.ts`, `.tsx`, `.json` in this repo returns zero hits — every
   mention is a markdown placeholder. Google Stitch is a browser design
   tool, not a REST endpoint; there is no key to put in `.env`. The string
   `STITCH_API_KEY` must be deleted from `docs/EXECUTION_PROMPTS.md` §0
   (Keys paragraph and tool list), §1 P0 step 2, §3 A-P3, and §4 B-P2.
   Why: P0's preflight halts every terminal on a key that cannot exist.
   The v1 "fallback" — the coding agent implements each UI prompt directly —
   was always the real path and becomes the *primary* path in v2.
2. **Re-label the three Stitch docs** as "design specification — implemented
   directly by the coding agent; optionally pasteable into
   stitch.withgoogle.com by a human for a visual reference." They are good
   UI specs and bad API contracts.
3. **Override v1 decision D2 (retail auth).** Supabase magic-link auth is
   OUT for the POC. Retail mode is reached by the mode toggle alone — no
   login, no JWT, no `demand.retailers` mapping yet. Reversal path: the v1
   auth design is kept on file in `docs/IMPLEMENTATION_PLAN.md` §3.4.
4. **Amend TASK 74 before submission.** As written it builds JWT
   verification (`SUPABASE_JWT_SECRET`, 401/403 tests, retailer lookup) —
   the superseded design. The v2 plan must rewrite TASK 74's auth section to
   match the founder's §F answer (default: strip auth; every endpoint
   public for the POC) before the runner ever submits it.
5. **Replace the `/shop` + `/dashboard` route split with one shell + a mode
   toggle** (product spec in §E). The dashboard is not a separate route
   tree; it is the same app in retail mode.
6. **Scope the C7 service worker to consumer routes only.** A PWA offline
   shell must not cache the retail analytics view.
7. **Add two decisions to the table:** **D9** — chart library (§F Q1);
   **D10** — fixture-first data: committed fixture JSON served behind the
   real API shape, Trends ingestion swapped in later behind the identical
   endpoint, so the frontend never knows the difference.

## §C Structure and governance

**ICM v2** (ICM = Interpretable Context Methodology: the folder structure
*is* the architecture, and context loads in layers so nobody reads 90 files
to change one function). The layer table from `PROJECT_OVERVIEW.md` §4.1:

| Layer | File(s) | Job |
|-------|---------|-----|
| L0 | `CLAUDE.md` | workspace identity, the rules — read first |
| L1 | `CONTEXT.md` | routing table: which stage does what |
| L2 | `stages/NN/CONTEXT.md` + `prompt.md` | one stage's contract |
| L3 | `_config/` + `shared/schemas/` | cross-cutting truth |
| L4 | `stages/NN/output/` | working files — outputs, never inputs |

What v2 adds: `demand/` is a **second workspace** with its own L0/L1 — that
is what "own service boundary" means in practice. The frontend gains a third
boundary: `consumer/` vs `retail/` component trees under one shell, so the
two modes cannot bleed into each other's components. The navigation rule is
unchanged: read L0 → L1 → the one L2 you need. Load nothing else.

**Graph engineering.** Work is a dependency graph, not a to-do list. Nodes =
tasks (Jules TASKs 69–76, the UI prompts, the manual key-holding steps).
Edges = data contracts: JSON Schemas (`additionalProperties: false` — the
schema rejects any field it doesn't name, which is the hallucination gate)
plus the `SHARED_CONTRACT.md` flags `DEMAND_INGEST_READY` →
`DEMAND_API_READY` → `PICKS_READY`. Parallelism is *derived* — any node
whose edges are all met runs now; nothing is hand-scheduled. State lives on
the edges (`tools/.jules_runner_state_demand.json`, `STATUS.md`, the flags),
which is exactly why an unattended run can fail one node and retry it
without replaying the graph. Precedent: `AGENTS.md`'s Batch 1→5 graph, which
carried the 52-task v1 run.

**Context handoff.** A session may die at any moment. Therefore: after every
completed step, commit and tick the tracker, so a fresh session resumes from
files alone — never from conversation.

**The progress tracker.** The v2 plan seeds `docs/TRACKER.md`, written so a
non-coder can read it: one row per task —
`what it is / who does it / waiting on / done?` — plus three short lists:
**OWNED** (files an in-flight task holds; nobody else touches them),
**BLOAT** (see register below), and **READ THIS / SKIP THIS** (what a new
agent loads and what it must not). `STATUS.md` stays as the historical log;
`TRACKER.md` is the live board every agent reads first and updates last.

**Bloat register** (a proposal — *nothing is deleted by this prompt or by
the planning session*; the founder authorizes deletions via §F Q7):

| File | Verdict | Reason |
|------|---------|--------|
| `debug_tick.py`, `debug_tick2.py`, `test_tick2.py`, `test_tick_debug.py` (repo root) | DELETE | one-off debug scratch; the tick work shipped per STATUS.md |
| `plan.md` (repo root) | DELETE | 27-line micro-plan, work already shipped |
| `docs/JULES_BACKEND.md`, `docs/JULES_BACKEND_V2.md` | ARCHIVE | finished task fuel (TASKs 01–68); keep as history, never load as input |
| `docs/STITCH_FRONTEND.md` | ARCHIVE | v1 UI spec, executed and merged; keep as design record |

## §D Who does what — the offload model

| Actor | Keeps | Why |
|-------|-------|-----|
| Opus/Fable (orchestrator) | planning, JSON Schemas, SQL DDL, merge review, anything touching live keys | the expensive model spends tokens on contracts and judgment, not typing |
| Jules (`tools/jules_runner.py`) | small, single-concern, offline-testable backend tasks | its VMs hold no keys, so every task must pass with fakes and fixtures — which forces testable design |
| Stitch docs | design specs only, implemented by the coding agent | there is no Stitch API; the spec is the value, not the call |
| Cheap/fast models | the paper track (memos, checklists) | prose doesn't need the strong model |

## §E The product spec to plan against

One app, one shell. A **top-right toggle** switches modes:

- **Consumer mode** (default): Amazon/Blinkit-style search plus nearby shops
  on the dot map. Reuses what exists: `frontend/src/components/MapPanel.tsx`
  / `MapOverlay.tsx` (the dot map), `ShopCard`, `BarrioCombobox`, `TopBar`,
  `ResultsPanel`, `api/client.ts`. Current routes are `/` → search and
  `/results` — the shell grows around them.
- **Retail mode**: chat pane on the left (reuse
  `frontend/src/components/ChatPanel.tsx` + the `chat/shopkeeper.ts`
  client-side mock), analytics dashboard on the right — charts drawn by a JS
  charting library (D9) from numbers computed in pure Python and served as
  JSON. The frontend only draws; it never computes.
- The analytics API returns **empty-but-shaped segments** keyed to the
  shopkeeper's inventory type (convenience store for the POC): the response
  shape is the real contract, the content is committed fixture JSON (D10)
  until Trends ingestion replaces it behind the identical endpoint.
- An **"ask AI about my analytics" button exists but is dead** — visible,
  disabled, no backend. It marks the future feature without building it.
- **No auth** for the POC. **No checkout, no payments, no native app** —
  those v1 out-of-scope rulings stand.

## §F The questions to ask the founder (Phase 1, before any writing)

Ask in batches of 3–5. Each has a recommended default so silence never
blocks: if unanswered, take the default and record it in the reversible
decision table.

**Group 1 — product surface**
1. **Chart library (D9)?** Default: **ECharts via `echarts-for-react`** —
   lighter than Plotly.js, denser than Recharts. Choose Plotly.js only if
   the exact Plotly API matters to you.
2. **Which convenience-store metrics does retail mode show first?** Default:
   top movers, category mix, stock-out risk, footfall proxy — in that order.
3. **How does the toggle persist?** Default: URL query param (`?mode=retail`)
   — shareable, stateless, trivially testable; a persisted local setting can
   come later.

**Group 2 — data**
4. **Fixture realism: how many weeks of history, how many SKUs?** Default:
   12 weeks × 200 SKUs — enough for every chart to look real and for the
   `high`-confidence rules to be exercisable.
5. **TASK 74 amendment: strip auth entirely, or build it disabled?**
   Default: **strip** — the POC has no login, and dead auth code is untested
   auth code.

**Group 3 — housekeeping**
6. **Do TASKs 69–76 keep their numbering after amendment?** Default: yes —
   renumbering breaks the runner state file for nothing.
7. **May the bloat register execute its deletions?** Default: no — the
   register stays a proposal until you say the word.
8. **Budget ceiling: still $0 in new paid API spend (v1 D8)?** Default: yes.

## §G Output contract — what Phase 2 must produce

`docs/IMPLEMENTATION_PLAN_V2.md` must contain:

1. **Decision table D1–D10**, every row reversible (what / why / how to
   reverse), carrying forward v1's D1–D8 with D2 overridden and D9/D10 new.
2. **Task list** tagged `[JULES]` / `[UI]` / `[MANUAL]`, each task with a
   wave number and explicit dependencies; TASK 74's amended text included
   verbatim, ready for the runner.
3. **Data contracts** — every cross-boundary payload named, each schema
   `additionalProperties: false`, fixture files listed next to the endpoint
   they stand behind.
4. **Risk table** — concrete mitigations only (things a task builds, not
   aspirations).
5. **Out-of-scope list** — carried from v1, updated.
6. **`docs/TRACKER.md` seeded from the task list**, in the §C shape:
   task rows (`what / who / waiting on / done?`), OWNED files, the bloat
   register, and the READ THIS / SKIP THIS index.

Both files land in a single commit on `main`. Nothing else is written.
