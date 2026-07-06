# Stage 03 — match-and-ping  (HARDCODED)

## Role
You are an EXECUTOR, not an author. This stage is pure Python
(`scripts/search_engine.py` + `scripts/ping.py`). Stock levels, prices, and
matches are read from the live SQLite store and are NEVER guessed, estimated,
or "corrected" by you. If the database says zero, the answer is zero.
Your job: run the script, validate the output, report verbatim.

## Input
- `stages/01-parse-query/output/intent.json` (keywords, category_hints)
- `stages/02-geo-resolve/output/geo_shops.json` (the ONLY candidate shops)
- Live DB `data/reachout.db` via `scripts/db.py` (the ONLY source of stock truth)

## Output
- `stages/03-match-and-ping/output/matches.json`
  → MUST validate against `shared/schemas/stock_matches.schema.json`
- One ping line per matched shop appended to `data/notifications/<shop_id>.jsonl`

## What the script does
1. For each shop in geo_shops.shops (already radius-filtered and sorted), read its
   live rows with qty >= 1 from the DB.
2. Keep items whose name or category whole-word-matches any keyword; a shop also
   matches if ANY of its `categories` (including secondary) matches a category_hint
   AND it has at least one in-stock item matching a keyword.
3. Rank matched shops: nearest first, then most total matching stock, then cheapest
   best item. Distances are copied unchanged from geo_shops input.
4. Ping every matched shop (and only matched shops) via scripts/ping.py.
5. `pinged_shop_ids` must equal the shop_ids in `matches`, same order.

## Never invent
**Never invent a missing field. If a required input field is missing or empty, stop and
return `{"status": "incomplete", "missing_fields": ["<field>", …]}` naming every missing
field. Do not guess, default, infer, or fill a value that was not in your inputs.**
For this stage concretely: if intent.json lacks `keywords` or geo_shops.json has
status != "ok", the script exits with that incomplete/error output and you relay it.
You never substitute remembered or plausible stock. An item with qty 0 does not
exist for this stage.

## Edge cases
- geo_shops.shop_count == 0 → status ok, match_count 0, matches [], NO pings written.
- Shops match but no items survive the keyword filter → same zero-match shape.
- Multi-category shop (e.g. ["grocery","pharmacy"]) with paracetamol in stock
  matches a pharmacy-hinted query via its secondary category.

## Test cases
### T1 — keyword match across two shops
Input: keywords ["paracetamol", …]; geo_shops with 2 pharmacies (both stocking
PHA-0001 paracetamol qty 5 and 12) and 1 hardware shop.
Expected: status ok; match_count 2; only the pharmacies present, each with the
paracetamol item (qty >= 1, currency "EUR"); pinged_shop_ids == their shop_ids;
2 inbox files appended.

### T2 — zero candidates in
Input: valid intent; geo_shops with status ok, shops [], shop_count 0.
Expected: `{"status":"ok", …, "match_count":0, "matches":[], "pinged_shop_ids":[]}`
and data/notifications/ untouched.

### T3 — secondary-category match
Input: category_hints ["pharmacy"]; one shop categories ["grocery","pharmacy"]
stocking paracetamol qty 3.
Expected: that shop matches; its `categories` array is copied whole into the output.

## Audit before writing
- [ ] every price/qty/distance in matches.json equals a DB row / geo_shops value exactly.
- [ ] no shop appears that was not in geo_shops.shops.
- [ ] pings written for exactly the matched shops.
- [ ] output validates against stock_matches.schema.json.
