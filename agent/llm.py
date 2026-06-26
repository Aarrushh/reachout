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
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = (
    "You convert a shopper's free-text request into a JSON search intent. "
    "Output ONLY JSON, no prose, no markdown fences. "
    "Schema: {\"raw_query\": string, \"keywords\": [string], "
    "\"category_hint\": one of pharmacy|grocery|electronics|stationery or null}. "
    "Rules: keywords must be plain product terms a shop would stock. "
    "Never invent a specific brand or product the user did not imply. "
    "Put the user's exact text in raw_query unchanged."
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
