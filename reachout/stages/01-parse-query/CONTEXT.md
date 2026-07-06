# Stage 01: parse-query  (Layer 2 contract)

Kind: Agentic. Turn a shopper's free text (Spanish, English, or mixed) into a
structured search intent. See `prompt.md` for the full role and test cases.

## Inputs

| Source | File / Location | Scope | Why |
|--------|-----------------|-------|-----|
| User | the query string passed to the pipeline | full | what to search for |
| Schema | `../../shared/schemas/search_intent.schema.json` | full | output must conform |
| Synonyms | `../../agent/query_parser.py` SYNONYMS map | full | maps everyday words to stock terms; the ONLY allowed expansion source |

## Process

1. Take the user's exact text. Never rewrite it.
2. Strip filler words. Expand phrasings ONLY via rows of the SYNONYMS map
   ("dolor de cabeza" → its committed pain-relief terms). The map is data;
   select from it, never extend it.
3. Keep keywords to plain product terms a shop would actually stock.
   Do not invent a brand or product the user did not imply.
4. `category_hints` is an array (0..n of: pharmacy, grocery, hardware,
   electronics, stationery). Empty means search all categories.
5. `location_text` is a place name lifted verbatim from the query, else null.
   No geocoding here — that is stage 02.
6. Nothing extractable → `{"status":"incomplete","missing_fields":["keywords"]}`.
7. Validate against the schema. If it fails, fall back to the user's raw
   words only and validate again.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Search intent | `output/intent.json` | JSON matching search_intent.schema.json |

## Audit before writing

- [ ] `raw_query` equals the user's exact text.
- [ ] every keyword traces to the user's words or a triggered SYNONYMS row.
- [ ] `category_hints` ⊆ the five known categories; empty array over guessing.
- [ ] `location_text` is a verbatim substring of the query, or null.
