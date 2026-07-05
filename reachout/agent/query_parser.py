"""Turns a messy free-text query into a structured SearchIntent.

This is the one place where natural language understanding helps. A user
might type "something for a headache" rather than "paracetamol". An LLM is
good at that mapping. Pure code is not.

Two paths:
  1. DEFAULT: a deterministic, rule-based parser. No API key needed. The
     whole repo runs end to end with this alone.
  2. OPTIONAL: if ANTHROPIC_API_KEY is set and you pass use_llm=True, it
     calls the model through agent/llm.py.

Either way the output is validated against search_intent.schema.json before
anything downstream uses it. A bad parse is rejected, not trusted.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import validate as v  # noqa: E402

# Tiny synonym map for the rule-based path. Extend freely. This is plain data,
# not intelligence. It only expands obvious everyday phrasings.
SYNONYMS = {
    "headache": ["paracetamol", "ibuprofen"],
    "pain": ["paracetamol", "ibuprofen"],
    "fever": ["paracetamol"],
    "cold": ["cough"],
    "charger": ["charger"],
    "cable": ["cable"],
    "pen": ["pen"],
    "paper": ["paper"],
    "milk": ["milk"],
    "bread": ["bread"],
    "eggs": ["eggs"],
}

CATEGORY_WORDS = {
    "pharmacy": ["paracetamol", "ibuprofen", "ors", "bandage", "vitamin", "cough", "headache", "fever"],
    "grocery": ["milk", "bread", "eggs", "rice", "oil", "sugar"],
    "electronics": ["cable", "charger", "earbuds", "power", "hdmi", "mouse", "usb"],
    "stationery": ["paper", "pen", "notebook", "marker", "stapler", "glue"],
}

STOPWORDS = {"a", "an", "the", "for", "some", "i", "need", "want", "to", "buy",
             "get", "me", "of", "my", "and", "or", "with", "in", "near", "plus", "any"}


def _rule_based_parse(query):
    words = re.findall(r"[a-zA-Z0-9]+", query.lower())
    words = [w for w in words if w not in STOPWORDS]

    keywords = []
    for w in words:
        if w in SYNONYMS:
            keywords.extend(SYNONYMS[w])
        else:
            keywords.append(w)
    # De-duplicate while keeping order.
    seen = set()
    keywords = [k for k in keywords if not (k in seen or seen.add(k))]
    if not keywords:
        keywords = words or [query.strip()]

    category_hint = None
    for cat, markers in CATEGORY_WORDS.items():
        if any(m in keywords or m in words for m in markers):
            category_hint = cat
            break

    return {"raw_query": query, "keywords": keywords, "category_hint": category_hint}


def parse_query(query, use_llm=False):
    if use_llm and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from llm import parse_with_llm
            intent = parse_with_llm(query)
        except Exception as e:
            print(f"  [parser] LLM path failed ({e}). Falling back to rules.")
            intent = _rule_based_parse(query)
    else:
        intent = _rule_based_parse(query)

    ok, err = v.validate(intent, "search_intent.schema.json")
    if not ok:
        # Schema rejected the parse. Fall back to the safest possible intent:
        # the user's own words, nothing invented.
        print(f"  [parser] intent rejected by schema ({err}). Using raw query only.")
        intent = {"raw_query": query, "keywords": [query.strip()], "category_hint": None}
    return intent


if __name__ == "__main__":
    for q in ["something for a headache", "usb c charger", "milk and bread"]:
        print(q, "->", parse_query(q))
