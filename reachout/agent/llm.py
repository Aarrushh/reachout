"""Optional LLM adapter. Only used if you opt in.

The repo runs fully without this file via the rule-based parser in
query_parser.py. This is here for when you want better handling of vague
queries like "something for a headache".

SDK pattern verified against the official anthropic Python SDK docs
(platform.claude.com/docs/en/api/sdks/python) on 23 June 2026. Model names
change over time. Verify the current model string in the docs before you
ship. At time of writing a cheap, fast option is the Haiku tier.

Install:  pip install anthropic
Set key:  export ANTHROPIC_API_KEY=...
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

# Keep this in sync with the current docs. Haiku is the cheap tier.
# Overridable via ANTHROPIC_MODEL since a local proxy may serve a different name.
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

SYSTEM_PROMPT = (
    "You convert a shopper's free-text request into a JSON search intent. "
    "Output ONLY JSON, no prose, no markdown fences. "
    "Schema: {\"status\": \"ok\"|\"incomplete\", \"raw_query\": string, "
    "\"keywords\": [string] (present only if status is ok), "
    "\"category_hints\": array of zero or more of "
    "pharmacy|grocery|hardware|electronics|stationery (present only if status is ok), "
    "\"location_text\": string or null (present only if status is ok), "
    "\"missing_fields\": [string] (present only if status is incomplete)}. "
    "Rules: keywords must be plain product terms a shop would stock, drawn only "
    "from the user's own words or well-known synonyms. Never invent a brand or "
    "product the user did not imply. location_text is a place name lifted "
    "verbatim from the query, else null; never geocode a location. Put the "
    "user's exact text in raw_query unchanged. If nothing extractable, return "
    "{\"status\": \"incomplete\", \"raw_query\": <text>, \"missing_fields\": [\"keywords\"]}."
)


def _extract_text(message):
    """Concatenate text blocks from a Messages API response."""
    out = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            out.append(block.text)
    return "".join(out)


def parse_with_llm(query):
    import anthropic  # imported here so the repo runs without the package

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    message = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": query}],
    )
    text = _extract_text(message).strip()
    # Strip accidental code fences just in case.
    text = re.sub(r"^```(json)?|```$", "", text).strip()
    intent = json.loads(text)
    # Force raw_query to the real input so the model cannot rewrite it.
    intent["raw_query"] = query
    return intent


# Stage 04 (format-results): the ONLY thing this pass may touch is item_name
# casing/whitespace. agent/result_formatter.py re-validates the result against
# ranked_shops.schema.json and discards it entirely on any deviation.
RESULT_FORMATTER_SYSTEM_PROMPT = (
    "You receive a JSON object matching a RankedShops schema (status, query, "
    "generated_at, result_count, results[]). Return the EXACT same JSON, "
    "byte-identical, except you may normalise the casing/whitespace of each "
    "result's item_name field. Never change any other field, add a field, "
    "remove a field, or reorder results. Output ONLY the JSON object, no "
    "prose, no markdown fences."
)


def normalize_item_names(ranked_shops):
    import anthropic  # imported here so the repo runs without the package

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=RESULT_FORMATTER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(ranked_shops)}],
    )
    text = _extract_text(message).strip()
    text = re.sub(r"^```(json)?|```$", "", text).strip()
    return json.loads(text)
