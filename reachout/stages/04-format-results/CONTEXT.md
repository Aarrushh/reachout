# Stage 04: format-results  (Layer 2 contract)

Kind: Agentic, deterministic by default. Turn the ranked matches into the
final RANKED SHOP LIST — a factual table, not content. There is no community
card, store story, culture tag, or narrative text anywhere in this pipeline.
An optional LLM pass may normalise item-name casing only; it may never touch
a number, name, or ordering. See `prompt.md` for the full rules.

## Inputs

| Source | File / Location | Scope | Why |
|--------|-----------------|-------|-----|
| Stage 03 | `../03-match-and-ping/output/matches.json` | full | the only source of facts |
| Schema | `../../shared/schemas/ranked_shops.schema.json` | full | output must conform; additionalProperties:false is the narrative gate |

## Process

1. Read the matches. Treat them as the only truth. Rank order is already
   decided by stage 03; copy it as rank 1..N with no gaps.
2. Emit per shop exactly: rank, shop_id, shop_name, category (primary),
   address (null allowed), distance_km, item_name, sku, price, currency,
   stock_qty, lat, lng. All verbatim.
3. If the optional LLM pass fails schema validation for ANY reason, discard
   it, use the deterministic output, and log `formatter_llm_rejected` to
   data/events.jsonl.
4. Zero matches → status ok, result_count 0, results []. No apology text.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Ranked shop list | `output/ranked_shops.json` | JSON matching ranked_shops.schema.json |

## Audit before writing

- [ ] every price, distance, and stock count matches Stage 03 exactly.
- [ ] no shop or item appears that was not in the input.
- [ ] no field exists beyond the schema's list — zero narrative.
- [ ] list passes ranked_shops.schema.json.
