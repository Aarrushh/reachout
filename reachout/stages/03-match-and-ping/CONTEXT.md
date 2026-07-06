# Stage 03: match-and-ping  (Layer 2 contract)

Kind: Hardcoded. No AI. This stage decides what is in stock. Those facts are
never guessed. See `prompt.md` for the executor rules.

## Inputs

| Source | File / Location | Scope | Why |
|--------|-----------------|-------|-----|
| Stage 01 | `../01-parse-query/output/intent.json` | full | the keywords to match |
| Stage 02 | `../02-geo-resolve/output/geo_shops.json` | full | the ONLY candidate shops, already radius-filtered and sorted |
| Live DB | `data/reachout.db` (via `scripts/db.py`) | in-stock rows (qty >= 1) | current truth |

## Process  (all pure Python, see scripts/search_engine.py)

1. For each shop in geo_shops.shops, read its live in-stock items from the DB.
2. Keep items whose name or category matches a keyword (whole-word match).
   A shop's secondary categories count too.
3. Rank shops: nearest first, then most matching stock, then cheapest.
   Distances are copied unchanged from geo_shops.
4. Ping every matched shop. `scripts/ping.py` writes to its inbox.
5. Zero candidates or zero surviving items → status ok, match_count 0,
   no pings. Never an error.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Ranked matches | `output/matches.json` | JSON matching `shared/schemas/stock_matches.schema.json` |
| Pings | `data/notifications/<shop_id>.jsonl` | one line per ping |

## Why no AI here

Stock and ranking are deterministic. If the data says zero, the answer is
zero. An AI guessing here would invent stock that does not exist. That is
the exact failure ReachOut cannot have.
