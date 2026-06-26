# Stage 01: parse-query  (Layer 2 contract)

Kind: Agentic. Turn a shopper's free text into a structured search intent.

## Inputs

| Source | File / Location | Scope | Why |
|--------|-----------------|-------|-----|
| User | the query string passed to the pipeline | full | what to search for |
| Schema | `../../shared/schemas/search_intent.schema.json` | full | output must conform |
| Synonyms | `../../agent/query_parser.py` SYNONYMS map | full | maps everyday words to stock terms |

## Process

1. Take the user's exact text. Never rewrite it.
2. Strip filler words. Expand obvious phrasings ("headache" to pain relief terms).
3. Keep keywords to plain product terms a shop would actually stock.
4. Do not invent a brand or product the user did not imply.
5. Validate the result against the schema. If it fails, fall back to the
   user's raw words only.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Search intent | `output/intent.json` | JSON matching search_intent.schema.json |

## Audit before writing

- [ ] `raw_query` equals the user's exact text.
- [ ] every keyword traces back to something the user said or clearly meant.
- [ ] `category_hint` is one of the four known categories or null.
