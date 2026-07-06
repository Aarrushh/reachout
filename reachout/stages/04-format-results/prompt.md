# Stage 04 — format-results

## Role
You produce the final consumer-facing artifact: a RANKED SHOP LIST. It is a
factual table, not content. There is no "community card", no store story, no
culture tags, no editorial or narrative text of any kind — those concepts do
not exist in this pipeline. The default path is the deterministic builder in
`agent/result_formatter.py`; an LLM pass is optional and may only be used to
normalise `item_name` casing/whitespace. It may not add, remove, reorder,
rename, or reword anything else, and it may never touch a number.

## Input
- `stages/03-match-and-ping/output/matches.json` — the ONLY source of facts.

## Output
- `stages/04-format-results/output/ranked_shops.json`
- MUST validate against `shared/schemas/ranked_shops.schema.json` — whose
  `additionalProperties:false` is the narrative gate: any extra field, whatever
  its name, fails validation.

## Process
1. Treat matches.json as the complete universe. Rank order is ALREADY decided by
   stage 03; you copy it. `rank` is 1..N with no gaps.
2. For each matched shop emit exactly: rank, shop_id, shop_name, category
   (primary = first of the shop's categories array), address (null allowed),
   distance_km, item_name + sku + price + currency + stock_qty (of the shop's
   cheapest matching item), lat, lng. All copied verbatim.
3. If the optional LLM pass is used, validate its output against the schema.
   ANY failure → discard it entirely, use the deterministic output, and append a
   `formatter_llm_rejected` event to data/events.jsonl. Never retry by loosening.

## Never invent
**Never invent a missing field. If a required input field is missing or empty, stop and
return `{"status": "incomplete", "missing_fields": ["<field>", …]}` naming every missing
field. Do not guess, default, infer, or fill a value that was not in your inputs.**
For this stage concretely: a match entry lacking distance_km or price makes the whole
stage return incomplete naming that field — you never fill in a plausible number,
address, or shop detail. address:null stays null; it is not "improved" into prose.

## Edge cases
- match_count 0 → `{"status":"ok","query":…,"generated_at":…,"result_count":0,"results":[]}`.
  An empty list is the truthful deliverable; do not decorate it with apology text.
- Ties already resolved upstream; identical distance_km rows keep stage 03's order.

## Test cases
### T1 — two matches, verbatim numbers
Input: matches.json from stage-03 T1 (distances 0.4 and 1.1 km, prices 3.95 / 4.20).
Expected: results[0].rank 1, distance_km 0.4, price 3.95, currency "EUR";
results[1].rank 2, distance_km 1.1, price 4.20 — every number byte-equal to input;
no field beyond the schema's list exists.

### T2 — zero matches
Input: matches.json with match_count 0.
Expected: status ok, result_count 0, results []. Validates.

### T3 — LLM tries to add narrative (the attack case)
Input: T1 input; simulated LLM pass returns results[0] plus
`"community_note":"A beloved neighbourhood farmacia…"`.
Expected: schema validation FAILS (additionalProperties:false); deterministic
output is written instead; events.jsonl gains a formatter_llm_rejected line.

## Audit before writing
- [ ] every number and name is byte-equal to matches.json.
- [ ] ranks are 1..N contiguous, order identical to input.
- [ ] zero narrative fields; output validates against ranked_shops.schema.json.
