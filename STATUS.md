# STATUS.md — ReachOut build progress tracker

Single source of truth for cross-session build state. Every agent session:
**read this first, update it when you start, update it when you finish.**
Workstream specs live in `AGENTS.md`. Do not start a workstream whose
blockers are not all ✅.

## Legend

- `[ ]` not started `[~]` in progress (add session date + note) `[x]` done
- A workstream is DONE only when every item in its AGENTS.md
  definition-of-done checklist is verified — evidence before assertions.

## Batch overview

| Batch | Workstreams | Can start when |
|-------|-------------|----------------|
| 1 | W1, W2, W6, W7 | now (fully parallel) |
| 2 | W3, W5 | W2 done |
| 3 | W4 | W3 done |
| 4 | W8 | W1–W7 all done |
| 5 | W9, W10 | W8 done (parallel) |

## Workstreams

### W1 — Stage-01 parser fix
- [ ] Started (date/session: __________)
- [ ] `tests/test_parse_query.py` green offline
- [ ] Prompt.md T1/T2/T3 pass exactly as documented
- [ ] All outputs (incl. fallback path) validate against `search_intent.schema.json`
- [ ] Bilingual multi-word SYNONYMS; `hardware` category covered
- [ ] DONE — handoff notes: __________

### W2 — Data core (SQLite schema + inventory seeder)
- [ ] Started (date/session: __________)
- [ ] `tests/test_db.py` + `tests/test_inventory_seeder.py` green offline
- [ ] Seeder deterministic per shop_id; rows validate against `inventory_record.schema.json`
- [ ] Simulator ported (EUR, new SKUs, no `seed_data` import)
- [ ] Legacy `seed_data.py` removed, zero dangling imports
- [ ] DONE — handoff notes: __________

### W3 — Geo externals (Overpass / Nominatim / ORS + ingest + cache) — blocked by W2
- [ ] Started (date/session: __________)
- [ ] All W3 tests green with `REACHOUT_OFFLINE=1`
- [ ] `data/osm_cache/madrid_shops.json` committed; rows validate against `shop_record.schema.json`
- [ ] Ingest idempotent; seeds inventory only for newly inserted shops
- [ ] API-down → cache → `no_shop_source` error path proven in a test
- [ ] DONE — handoff notes: __________

### W4 — Stage 02 geo-resolve — blocked by W3
- [ ] Started (date/session: __________)
- [ ] `tests/test_geo_resolve.py` green offline
- [ ] Prompt.md T1/T2/T3 pass exactly as documented
- [ ] Unresolvable named place → incomplete (never silent default)
- [ ] Output validates against `geo_shops.schema.json`
- [ ] DONE — handoff notes: __________

### W5 — Stage 03 match-and-ping rework — blocked by W2
- [ ] Started (date/session: __________)
- [ ] `tests/test_search_engine.py` + `tests/test_ping.py` green offline
- [ ] Prompt.md T1/T2/T3 pass exactly as documented
- [ ] Candidates come ONLY from geo_shops (test proves DB-only shop excluded)
- [ ] Output validates against `stock_matches.schema.json`
- [ ] DONE — handoff notes: __________

### W6 — Stage 04 result formatter
- [ ] Started (date/session: __________)
- [ ] `tests/test_result_formatter.py` green offline
- [ ] Prompt.md T1/T2 pass; T3 narrative-injection rejected + `formatter_llm_rejected` logged
- [ ] Output validates against `ranked_shops.schema.json`
- [ ] DONE — handoff notes: __________

### W7 — Stage 05 map render
- [ ] Started (date/session: __________)
- [ ] `tests/test_map_render.py` green offline
- [ ] Prompt.md T1/T2/T3 pass; error-sidecar path works
- [ ] Swapped lat/lng fixture FAILS schema validation (gate proven)
- [ ] DONE — handoff notes: __________

### W8 — Orchestrator + demo integration — blocked by W1–W7
- [ ] Started (date/session: __________)
- [ ] Offline run: `"algo para el dolor de cabeza" --near "Malasaña"` → 5 schema-valid outputs
- [ ] Offline run: `"cargador usb c" --lat 40.4168 --lng -3.7038` → same
- [ ] Corrupted intermediate file HALTS the pipeline (test proves it)
- [ ] `demo.py` live demo runs on Madrid data; pings land in `data/notifications/`
- [ ] Full suite green: `REACHOUT_OFFLINE=1 pytest reachout/tests/`
- [ ] DONE — handoff notes: __________

### W9 — Cleanup + docs truth pass — blocked by W8
- [ ] Started (date/session: __________)
- [ ] Legacy schemas + `data/shops.json` deleted; no dangling references
- [ ] README.md rewritten to the 5-stage Madrid reality
- [ ] Full suite still green after deletions
- [ ] DONE — handoff notes: __________

### W10 — API + frontend skeleton — blocked by W8
- [ ] Started (date/session: __________)
- [ ] API tests green; responses schema-valid; zero results = 200 + empty list
- [ ] `frontend/` builds / typechecks; matches frontend/README.md tree exactly
- [ ] `src/types/` generated from schemas
- [ ] Zero visual/styling decisions in the diff
- [ ] DONE — handoff notes: __________

## Blocked / conflicts

Record here any cross-workstream file conflict or blocker discovered
mid-session (which files, which workstreams, what's needed). Empty = none.

- (none)

## Session log

One line per session, newest first: `YYYY-MM-DD — Wn — what happened`.

- 2026-07-07 — setup — AGENTS.md + STATUS.md created; `.env` added (gitignored). No code written yet.
