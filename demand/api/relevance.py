"""Deterministic commercial-relevance scorer for `demand.rising_queries`.

WHY THIS EXISTS
---------------
`demand.rising_queries` holds 658 discovery rows straight from Google Trends'
"rising queries" feature. That feed is not shippable as-is: it mixes real,
dated, local demand (`bombillas led g9`) with Wikipedia-shaped noise
(`pan am 103` under parent `pan`, the bread), navigational Google Maps
categories (`bancos`, `museos` under parent `café`), and translation/how-to
lookups (`bufanda en ingles`). This module tiers every row into
`"commercial"` / `"ambiguous"` / `"noise"` so a caller can choose what to
show. It never deletes a row -- tiering is a label, not a filter.

Pure Python, deterministic, no AI, no model calls, no network. This
project's root `CLAUDE.md` forbids anything but pure Python near ranking,
because that is exactly where hallucination is most dangerous.

THE TRAP THIS MODULE DELIBERATELY AVOIDS
-----------------------------------------
The obvious filter -- "the query must contain the parent keyword" -- looks
correct and is wrong. Measured on the live table it drops 101 of 658 rows,
and among those 101 is the single most valuable cluster in the dataset:
`gafas eclipse`, `gafas para el eclipse`, `gafas eclipse carrefour`,
`comprar gafas eclipse solar`, `donde comprar gafas para el eclipse` under
parent `gafas de sol` -- a real, dated, local demand spike (the 2026 solar
eclipse) that a Madrid shop could have stocked eclipse glasses for. None of
those five contain the phrase "gafas de sol" as a substring.

Meanwhile the junk that containment *does* catch is only about 17 rows and
is better caught by an explicit blocklist (see BLOCKLIST_EXACT below).

So: parent-keyword containment is a positive *signal* that adds points, it
is never a gate that removes a row from consideration. Any rule that would
delete the eclipse cluster is worse than no rule at all -- see
`test_relevance.py::test_eclipse_regression_guard`, which exists specifically
to catch a future rewrite that reintroduces a containment gate.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
# Spanish accents (café, niño, películas) must fold to plain ASCII so that
# "café" and "cafe" -- two spellings a human typed for the same thing -- score
# and cluster identically. NFD decomposes each accented letter into a base
# letter plus a separate combining mark (e.g. "é" -> "e" + U+0301); dropping
# every codepoint unicodedata.combining() flags as a combining mark then
# leaves the plain base letters. No dependency added, per the brief.

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _fold(text: str) -> str:
    """Lowercase and strip Spanish accents via NFD decomposition."""
    nfd = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in nfd if not unicodedata.combining(ch))
    return stripped.lower()


def _tokenize(text: str) -> list:
    """Accent- and case-folded tokens, in original order, punctuation dropped."""
    return _TOKEN_RE.findall(_fold(text))


def _contains_contiguous_run(tokens: list, sub_tokens: list) -> bool:
    """True if `sub_tokens` appears in `tokens` as a contiguous, in-order run.

    Used only for the positive parent-keyword-containment signal below, never
    as a gate -- see the module docstring's trap section.
    """
    n, m = len(tokens), len(sub_tokens)
    if m == 0 or m > n:
        return False
    return any(tokens[i:i + m] == sub_tokens for i in range(n - m + 1))


# ---------------------------------------------------------------------------
# Signal vocabularies (all entries pre-folded: lowercase, no accents)
# ---------------------------------------------------------------------------

#: Retail-intent words. Presence alongside anything else is a strong signal
#: the shopper wants to buy, not just browse or learn.
RETAIL_MODIFIER_TOKENS = frozenset({
    "comprar", "precio", "barato", "oferta", "rebajas", "tienda", "online",
})

#: Chain names. These only count as a positive retail-modifier signal when
#: they appear *alongside* other tokens (query has more than one token) --
#: a chain name as the ENTIRE query (`mercadona`, `druni`) is a bare
#: retailer-name lookup, not a product search, and is handled by
#: BLOCKLIST_EXACT below instead.
CHAIN_NAME_TOKENS = frozenset({
    "mercadona", "carrefour", "lidl", "aldi", "druni", "alcampo",
})

#: Variant/spec tokens: bulb fittings, clothing sizes, packaging units. Their
#: presence means the shopper already knows what they want and is narrowing
#: a specific SKU -- a strong commercial tell independent of parent
#: containment (e.g. "bombillas led g9").
VARIANT_TOKENS = frozenset({
    "led", "g9", "e14", "h7", "hombre", "mujer", "infantil",
    "nino", "nina", "talla", "pack", "kg", "litro", "ml", "cm",
})

#: Exact-match blocklist: Google Maps navigational categories plus bare
#: chain/retailer names used as the entire query. Matched on the WHOLE
#: normalised query only, never as a substring -- `gafas eclipse carrefour`
#: must keep its retail value, so `carrefour` may never blocklist a query it
#: only appears inside of. This is ~17 rows on the live table (12 of them
#: under parent `café`), smaller than containment's 101 false drops, which
#: is exactly why it is a small explicit list and not a heuristic rule.
_NAVIGATIONAL_TERMS = frozenset({
    "bancos", "empleos", "parques", "museos", "mapas", "vuelos",
    "hoteles", "hospitales", "libros", "juegos", "playa", "peliculas",
})
#: `amazon` is not a modifier chain name above (it is never used as a
#: qualifier alongside other tokens in this dataset) but is cited in the
#: source data as a bare-query row (`amazon`, `mercadona`, `druni`), so it is
#: folded into the blocklist here even though it never earns retail-modifier
#: points.
_BARE_RETAILER_NAMES = CHAIN_NAME_TOKENS | frozenset({"amazon"})
BLOCKLIST_EXACT = _NAVIGATIONAL_TERMS | _BARE_RETAILER_NAMES

#: Informational-intent phrases: the shopper is looking something up, not
#: buying it (a novel's plot, a word's translation, a recipe). Matched as a
#: substring of the space-joined, folded query, since these are multi-word
#: phrases that can appear with other tokens around them
#: (`antes de que se enfrie el cafe` would match if it had "que es" in it;
#: `bufanda en ingles` matches "en ingles" directly).
INFORMATIONAL_MARKERS = frozenset({
    "que es", "como se", "donde tirar", "donde se tiran",
    "en ingles", "significado", "letra", "receta",
})

#: Token-count band a genuine short retail query tends to sit in: long enough
#: to be a real phrase, short enough not to be a sentence someone typed into
#: a question. Named MIN/MAX (not a bare range literal) so the eclipse and
#: café tests below fail loudly at the right line if either bound moves.
MIN_TOKEN_COUNT = 2
MAX_TOKEN_COUNT = 5

# ---------------------------------------------------------------------------
# Scoring weights and tier thresholds
# ---------------------------------------------------------------------------
# Chosen, in the style of demand/scripts/compute_signals.py:77-95, so that
# the eclipse cluster (test_relevance.py::test_eclipse_regression_guard)
# lands in "commercial" and the café Maps categories (bancos, empleos,
# museos, vuelos) land in "noise". Every value below is load-bearing for one
# of those two regressions; do not tune without re-running the full suite.

#: Parent-keyword containment (a POSITIVE signal, never a gate -- see module
#: docstring). Weighted the same as a retail modifier: containment alone
#: (e.g. "bufanda en ingles" contains parent "bufanda") should not be enough
#: to reach "commercial" by itself once an informational marker is present,
#: but should comfortably clear the bar combined with the token-count band.
PARENT_CONTAINMENT_POINTS = 2.0

#: Retail modifier / chain-name-as-qualifier present.
RETAIL_MODIFIER_POINTS = 2.0

#: Variant/spec token present (led, g9, talla, ...).
VARIANT_TOKEN_POINTS = 1.0

#: Token count sits in [MIN_TOKEN_COUNT, MAX_TOKEN_COUNT]. Deliberately the
#: smallest weight: on its own ("gafas para el eclipse", 4 tokens, no other
#: signal fires) it is exactly enough to clear COMMERCIAL_THRESHOLD, which is
#: the eclipse regression guard's second case -- see test_relevance.py.
TOKEN_COUNT_RANGE_POINTS = 1.0

#: Exact blocklist match (navigational term or bare retailer name). Large
#: enough combined with the bare-single-token penalty (both fire together
#: for e.g. "bancos") to overwhelm the token-count-range point and land
#: comfortably below NOISE_THRESHOLD.
BLOCKLIST_PENALTY = -4.0

#: Informational-intent phrase present ("en ingles", "donde tirar", ...).
#: Sized so that a query which ALSO gets parent-containment plus the
#: token-count-range point (e.g. "bufanda en ingles" = +2 +1 -3 = 0) still
#: lands at or below NOISE_THRESHOLD rather than merely "ambiguous" --
#: informational intent is a stronger tell than bare containment is weak.
INFORMATIONAL_MARKER_PENALTY = -3.0

#: Single bare token (e.g. "bancos", "mercadona" alone). Smaller than the
#: blocklist penalty on its own since a one-word query is only ambiguous by
#: itself (a shopper might type just "bufandas"); it is the two penalties
#: firing TOGETHER on blocklisted single words that pushes them to "noise".
BARE_TOKEN_PENALTY = -2.0

#: score >= this -> "commercial". Set to the minimum score a query gets from
#: the token-count-range signal ALONE (1.0), because "gafas para el eclipse"
#: (parent "gafas de sol", no containment, no modifier, no variant token,
#: just 4 tokens) must clear this bar on that signal by itself.
COMMERCIAL_THRESHOLD = 1.0

#: score <= this -> "noise"; strictly between here and COMMERCIAL_THRESHOLD
#: is "ambiguous". 0.0 so that a query with exactly one positive and one
#: matching negative signal (informational markers cancelling containment +
#: range, as above) settles as "noise" rather than "ambiguous".
NOISE_THRESHOLD = 0.0

# ---------------------------------------------------------------------------
# cluster_key
# ---------------------------------------------------------------------------

#: Dropped before sorting/joining so that queries differing only by function
#: words collapse to the same key (`gafas eclipse` and `gafas para el
#: eclipse` both reduce to the sorted pair `eclipse`, `gafas`). This is a
#: syntactic near-duplicate key, not a semantic one: variants that add a
#: genuine extra content word (`gafas eclipse carrefour`, `comprar gafas
#: eclipse solar`) deliberately get their OWN cluster key, because that
#: extra word is itself real information (which retailer, which action) that
#: a stopword-only heuristic has no business discarding.
CLUSTER_STOPWORDS = frozenset({
    "de", "la", "el", "para", "con", "en", "los", "las", "del", "al", "y",
})


def cluster_key(query: str) -> str:
    """Stable key grouping near-duplicate queries.

    Accent/case-folds the query, drops CLUSTER_STOPWORDS, sorts what remains,
    and joins it. Two queries that differ only in function words (`gafas
    eclipse` vs. `gafas para el eclipse`) collapse to the same key so a
    consumer can surface one card instead of many near-identical rows.
    """
    tokens = [t for t in _tokenize(query) if t not in CLUSTER_STOPWORDS]
    return "_".join(sorted(tokens))


# ---------------------------------------------------------------------------
# score_query
# ---------------------------------------------------------------------------

def score_query(query: str, parent_keyword: str) -> dict:
    """Score one rising-query row for commercial relevance.

    Returns {"score": float, "tier": str, "reasons": list[str]}. `tier` is
    exactly one of "commercial" / "ambiguous" / "noise". `reasons` always
    has at least one entry (falls back to "no_signals_detected") so a human
    can audit every tiering decision, including a neutral one.

    This function is a pure label-assigner: it never rejects a query, never
    invents data, and reads only `query`/`parent_keyword` -- it does not
    touch `growth_pct` or `is_breakout`, which `annotate()` below passes
    through unchanged.
    """
    tokens = _tokenize(query)
    parent_tokens = _tokenize(parent_keyword)
    normalized_query = " ".join(tokens)

    score = 0.0
    reasons = []

    if parent_tokens and _contains_contiguous_run(tokens, parent_tokens):
        score += PARENT_CONTAINMENT_POINTS
        reasons.append("contains_parent_keyword")

    modifier_hits = sorted({t for t in tokens if t in RETAIL_MODIFIER_TOKENS})
    if len(tokens) > 1:
        modifier_hits = sorted(
            set(modifier_hits) | {t for t in tokens if t in CHAIN_NAME_TOKENS}
        )
    if modifier_hits:
        score += RETAIL_MODIFIER_POINTS
        reasons.append("retail_modifier:" + ",".join(modifier_hits))

    variant_hits = sorted({t for t in tokens if t in VARIANT_TOKENS})
    if variant_hits:
        score += VARIANT_TOKEN_POINTS
        reasons.append("variant_token:" + ",".join(variant_hits))

    if MIN_TOKEN_COUNT <= len(tokens) <= MAX_TOKEN_COUNT:
        score += TOKEN_COUNT_RANGE_POINTS
        reasons.append("token_count_in_range")

    if normalized_query in BLOCKLIST_EXACT:
        score += BLOCKLIST_PENALTY
        reasons.append("blocklist_exact_match")

    marker_hits = sorted(m for m in INFORMATIONAL_MARKERS if m in normalized_query)
    if marker_hits:
        score += INFORMATIONAL_MARKER_PENALTY
        reasons.append("informational_marker:" + ",".join(marker_hits))

    if len(tokens) == 1:
        score += BARE_TOKEN_PENALTY
        reasons.append("single_bare_token")

    if not reasons:
        reasons.append("no_signals_detected")

    if score >= COMMERCIAL_THRESHOLD:
        tier = "commercial"
    elif score <= NOISE_THRESHOLD:
        tier = "noise"
    else:
        tier = "ambiguous"

    return {"score": score, "tier": tier, "reasons": reasons}


# ---------------------------------------------------------------------------
# annotate
# ---------------------------------------------------------------------------

def annotate(rows: list) -> list:
    """Adds relevance_score / relevance_tier / relevance_reasons / cluster_id.

    Never drops or reorders a row: output length always equals input length,
    and every original field (including `growth_pct` / `is_breakout`) is
    copied through unchanged. Rows are copied, not mutated in place, so the
    caller's original list is left untouched.
    """
    annotated = []
    for row in rows:
        result = score_query(row.get("query", ""), row.get("parent_keyword", ""))
        new_row = dict(row)
        new_row["relevance_score"] = result["score"]
        new_row["relevance_tier"] = result["tier"]
        new_row["relevance_reasons"] = result["reasons"]
        new_row["cluster_id"] = cluster_key(row.get("query", ""))
        annotated.append(new_row)
    return annotated
