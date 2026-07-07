"""Turns a messy free-text query into a structured SearchIntent.

This is the one place where natural language understanding helps. A user
might type "algo para el dolor de cabeza" rather than "paracetamol". An LLM
is good at that mapping. Pure code is not.

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

CATEGORIES = ["pharmacy", "grocery", "hardware", "electronics", "stationery"]

# Bilingual (Spanish + English) synonym map for the rule-based path. Keys are
# lowercase words or phrases drawn from what a shopper might actually type;
# values are the committed expansion terms. This is plain data, not
# intelligence: the parser selects from it, it never extends it.
SYNONYMS = {
    "dolor de cabeza": ["analgésico", "paracetamol", "ibuprofeno"],
    "headache": ["painkiller", "paracetamol", "ibuprofen"],
    "dolor": ["analgésico"],
    "pain": ["painkiller"],
    "fiebre": ["paracetamol"],
    "fever": ["paracetamol"],
    "tos": ["jarabe"],
    "cough": ["cough syrup"],
    "pilas": ["batteries"],
    "batteries": ["pilas"],
    "usb c": ["charger"],
    "leche": ["milk"],
    "pan": ["bread"],
}

# Bilingual category markers. A term landing in more than one set is a valid
# ambiguous case (e.g. "pilas"/"batteries" are both hardware and
# electronics); stage 03 resolves against real stock.
CATEGORY_WORDS = {
    "pharmacy": {
        "paracetamol", "ibuprofeno", "ibuprofen", "analgésico", "painkiller",
        "fiebre", "fever", "tos", "cough", "jarabe", "vitamina", "vitamin",
        "tirita", "bandage",
    },
    "grocery": {
        "leche", "milk", "pan", "bread", "huevos", "eggs", "arroz", "rice",
        "aceite", "oil", "azúcar", "sugar", "café", "coffee",
    },
    "hardware": {
        "destornillador", "screwdriver", "martillo", "hammer", "tornillos",
        "screws", "bombilla", "bulb", "pilas", "batteries", "cinta", "tape",
        "llave", "wrench", "guantes", "gloves", "sellador", "silicone",
    },
    "electronics": {
        "cargador", "charger", "cable", "usb", "usb c", "auriculares",
        "headphones", "ratón", "mouse", "power bank", "hdmi", "microsd",
        "altavoz", "speaker", "hub", "pilas", "batteries",
    },
    "stationery": {
        "bolígrafo", "pen", "cuaderno", "notebook", "papel", "paper",
        "rotulador", "marker", "grapadora", "stapler", "pegamento", "glue",
        "tijeras", "scissors", "lápices", "pencils",
    },
}

STOPWORDS = {
    # Spanish
    "algo", "para", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "al", "en", "con", "y", "o", "que", "qué", "hay", "por",
    "como", "más", "necesito",
    # English
    "a", "an", "the", "for", "some", "i", "need", "want", "to", "buy",
    "get", "me", "of", "my", "and", "or", "with", "in", "near", "plus",
    "any", "something",
}

_LOCATION_RE = re.compile(
    r"\b(?:en|in)\s+([A-ZÀ-Ý][\wÀ-ÿ]*(?:\s+[A-ZÀ-Ý][\wÀ-ÿ]*)*)"
)


def _extract_location(query):
    """Pull a verbatim place name out of the query, if one is named."""
    m = _LOCATION_RE.search(query)
    if not m:
        return None, query
    location = m.group(1)
    start, end = m.span()
    remaining = query[:start] + query[end:]
    return location, remaining


def _extract_keywords(remaining_text):
    """Left-to-right scan matching the longest SYNONYMS phrase at each token."""
    tokens = re.findall(r"\w+", remaining_text.lower())
    if not tokens:
        return []
    max_len = max((len(k.split()) for k in SYNONYMS), default=1)

    keywords = []
    seen = set()

    def add(term):
        if term not in seen:
            seen.add(term)
            keywords.append(term)

    i = 0
    n = len(tokens)
    while i < n:
        matched = False
        for span in range(min(max_len, n - i), 0, -1):
            phrase = " ".join(tokens[i:i + span])
            if phrase in SYNONYMS:
                add(phrase)
                for term in SYNONYMS[phrase]:
                    add(term)
                i += span
                matched = True
                break
        if matched:
            continue
        token = tokens[i]
        if token not in STOPWORDS:
            add(token)
        i += 1
    return keywords


def _category_hints(keywords):
    probe = set()
    for k in keywords:
        probe.add(k)
        probe.update(k.split())
    return [cat for cat in CATEGORIES if probe & CATEGORY_WORDS[cat]]


def _rule_based_parse(query):
    location_text, remaining = _extract_location(query)
    keywords = _extract_keywords(remaining)
    if not keywords:
        return {"status": "incomplete", "raw_query": query, "missing_fields": ["keywords"]}
    return {
        "status": "ok",
        "raw_query": query,
        "keywords": keywords,
        "category_hints": _category_hints(keywords),
        "location_text": location_text,
    }


def _fallback_intent(query):
    """Safest possible intent: the user's own words, nothing invented."""
    tokens = re.findall(r"\w+", query.lower())
    words = [w for w in tokens if w not in STOPWORDS] or tokens or [query.strip()]
    seen = set()
    keywords = [w for w in words if w and not (w in seen or seen.add(w))]
    return {
        "status": "ok",
        "raw_query": query,
        "keywords": keywords,
        "category_hints": [],
        "location_text": None,
    }


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
        print(f"  [parser] intent rejected by schema ({err}). Falling back to raw words.")
        intent = _fallback_intent(query)

    return intent


if __name__ == "__main__":
    for q in ["algo para el dolor de cabeza en Malasaña", "cargador usb c", "???"]:
        print(q, "->", parse_query(q))
