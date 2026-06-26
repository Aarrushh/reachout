# Stage 02: match-and-ping  (Layer 2 contract)

Kind: Hardcoded. No AI. This stage decides what is in stock and how far
away it is. Those facts are never guessed.

## Inputs

| Source | File / Location | Scope | Why |
|--------|-----------------|-------|-----|
| Stage 01 | `../01-parse-query/output/intent.json` | full | the keywords to match |
| Live DB | `data/reachout.db` (via `scripts/db.py`) | in-stock rows | current truth |
| User location | lat, lng, radius passed to the pipeline | full | geofence |

## Process  (all pure Python, see scripts/search_engine.py)

1. Filter shops to those inside the radius. Haversine distance, `scripts/geo.py`.
2. For each in-range shop, read its live in-stock items from the DB.
3. Keep items whose name or category matches a keyword (whole-word match).
4. Rank shops: nearest first, then most stock, then cheapest.
5. Ping every matched shop. `scripts/ping.py` writes to its inbox.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Ranked matches | `output/matches.json` | JSON |
| Pings | `data/notifications/<shop_id>.jsonl` | one line per ping |

## Why no AI here

Stock and distance are deterministic. If the data says zero, the answer is
zero. An AI guessing here would invent stock that does not exist. That is
the exact failure ReachOut cannot have.
