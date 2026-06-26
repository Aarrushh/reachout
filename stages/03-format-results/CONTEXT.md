# Stage 03: format-results  (Layer 2 contract)

Kind: Agentic, optional. Turn the ranked matches into a clean card for the
consumer app. The default is deterministic text. An LLM may rephrase, but
it may never change a number.

## Inputs

| Source | File / Location | Scope | Why |
|--------|-----------------|-------|-----|
| Stage 02 | `../02-match-and-ping/output/matches.json` | full | the only source of facts |
| Schema | `../../shared/schemas/shop_match.schema.json` | full | output must conform |

## Process

1. Read the matches. Treat them as the only truth.
2. Build a short card: shop name, distance, item, price, stock.
3. If using an LLM, allow it to reword the text only. Prices, distances,
   stock counts, and shop names are copied verbatim from the input.
4. Validate the card against the schema before serving it.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Consumer card | `output/card.json` | JSON with a `display_text` field |

## Audit before writing

- [ ] every price, distance, and stock count matches Stage 02 exactly.
- [ ] no shop or item appears that was not in the input.
- [ ] card passes shop_match.schema.json.
