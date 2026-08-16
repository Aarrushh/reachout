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
#: Accented spellings ("qué es", "cómo se") are intentionally omitted: this
#: set is only ever matched against `normalized_query`, which _fold() has
#: already accent-stripped, so an accented entry here would never match
#: anything and would be redundant -- do not "fix" that by adding them back.
INFORMATIONAL_MARKERS = frozenset({
    "que es", "como se", "donde tirar", "donde se tiran",
    "en ingles", "significado", "letra", "receta",
    # `se puede` lives here, not in INFORMATIONAL_HEAD_TOKENS: a bare `se`
    # head is just as likely to open a classifieds sale (`se vende ...`),
    # which is a purchase signal, and demoting that for its grammar was a
    # real cost with no live benefit. Every `se`-headed live row is
    # `se puede ...`, and this phrase catches all of them.
    "se puede",
})

#: Interrogative and modal words that mean "I am looking something up",
#: but ONLY in head position and ONLY when no retail modifier is present.
#:
#: Head position, because a `que` or `como` buried mid-phrase is grammar,
#: not intent ("gafas de sol para ver el eclipse" is a purchase); at the
#: head it is the whole point of the query ("como hacer huevos cocidos").
#:
#: The retail-modifier exemption is load-bearing and measured: of the 19
#: live rows with an interrogative head that tiered `commercial`, exactly
#: one is a genuine purchase -- `donde comprar gafas para el eclipse` --
#: and `comprar` is the only thing that separates it from the other 18.
#: Remove the exemption and this rule deletes a real, dated demand spike.
#:
#: RETAIL_MODIFIER_TOKENS only. A chain name is NOT an exemption, even
#: though it scores like one: `como llegar a mercadona` is a navigational
#: lookup, not a shopping list. See `retail_modifier_hits` in score_query().
#:
#: `para` is here for `para que sirve el te matcha` (4 live rows); it is
#: harmless in head position because a query genuinely starting with
#: `para` and meaning a purchase would carry a modifier and be exempt.
#: Accents are omitted deliberately -- these are matched against _tokenize
#: output, which is already accent-folded (see INFORMATIONAL_MARKERS).
INFORMATIONAL_HEAD_TOKENS = frozenset({
    "que", "como", "cuando", "cuanto", "cuantos", "cuantas",
    "donde", "quien", "quienes", "cual", "cuales", "puedo",
    "por", "para",
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

#: Every parent token present but NOT as a contiguous run ("gafas para el
#: eclipse de sol" against parent "gafas de sol"). Half the contiguous
#: signal's weight, because scattered tokens are weaker evidence -- and
#: exactly COMMERCIAL_THRESHOLD, so it rescues a row that has no other
#: signal (six tokens puts it outside the token-count band) without
#: rescuing one that is also carrying a penalty. That is the intended
#: asymmetry: it can lift a 0.0 row to commercial, and can never lift an
#: informational row (which sits at -3.0 before this fires) past the bar.
PARENT_SCATTERED_POINTS = 1.0

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
#: eclipse` both reduce to the sorted pair `eclipse`, `gafas`). Retail
#: decoration (chain names, "comprar", "donde", ...) is stripped separately
#: by CLUSTER_DECORATION_TOKENS below -- see that constant and
#: cluster_key()'s docstring for why. A genuine extra content word that is
#: neither a stopword nor decoration (e.g. "solar" in "comprar gafas
#: eclipse solar") still produces its own, larger key from this function
#: alone; annotate() below merges that into the smaller key via
#: _merge_subset_keys.
CLUSTER_STOPWORDS = frozenset({
    "de", "la", "el", "para", "con", "en", "los", "las", "del", "al", "y",
    # Widened 2026-08-16. Function words only -- copulas, indefinite
    # determiners, the reflexive `se`, possessives, and prepositions that
    # carry no product meaning. Measured effect of THIS widening alone on
    # the 658 live rows (2026-08-16, isolated by re-running annotate() with
    # only the first line of this set): 28 rows change cluster_id, clusters
    # across all tiers 551 -> 548, eclipse clusters 10 -> 8. The
    # commercial-tier cluster count does not move (480 either way) -- the
    # rows this merges had already been demoted to `noise` by the
    # informational-head rule above.
    #
    # Nothing that could name or qualify a product belongs here. `solar`,
    # `homologadas`, `normales` and the like stay OUT on purpose: they are
    # genuine content, and merging on them would tell a shopkeeper to stock
    # a product Madrid did not search for. Under-merging costs redundancy;
    # over-merging costs a wrong stocking decision. Split when unsure.
    #
    # Three words that LOOK like function words are deliberately absent,
    # removed 2026-08-16 after the final review caught them: `sin` is
    # retail negation and names the product (`sin gluten`, `sin lactosa`,
    # `cerveza sin` -- stripping it merged "leche sin lactosa" onto "leche
    # con lactosa"), `sobre` is also a noun (sachet/envelope), and `a`
    # collapsed "vitamina a" onto "vitamina". Guarded by
    # test_negation_is_not_a_stopword.
    "se", "un", "una", "unos", "unas", "que", "o",
    "mi", "su", "tu", "por", "es", "son", "lo",
})

#: Retail decoration to strip when building a CLUSTER key only -- scoring is
#: untouched: RETAIL_MODIFIER_TOKENS and CHAIN_NAME_TOKENS above still score
#: exactly as before in score_query(). These are vendor names and
#: action/intent words wrapped around a query's actual subject
#: ("comprar gafas...", "...gafas eclipse carrefour", "donde comprar..."),
#: not the subject itself, so two rows differing only by one of these
#: should still land on the same cluster card. `donde` is included here on
#: top of RETAIL_MODIFIER_TOKENS because "donde comprar" is decoration for
#: clustering purposes even though "donde" alone earns no retail-modifier
#: score.
CLUSTER_DECORATION_TOKENS = (
    RETAIL_MODIFIER_TOKENS | CHAIN_NAME_TOKENS | frozenset({"donde"})
)


def cluster_key(query: str) -> str:
    """Stable key grouping near-duplicate queries.

    Accent/case-folds the query, drops CLUSTER_STOPWORDS and
    CLUSTER_DECORATION_TOKENS, sorts what remains, and joins it. Two
    queries that differ only in function words or retail decoration
    (`gafas eclipse` vs. `gafas para el eclipse` vs. `gafas eclipse
    carrefour` vs. `donde comprar gafas para el eclipse`) collapse to the
    same key so a consumer can surface one card instead of many
    near-identical rows.

    Returns `"{head}:{sorted_tokens_joined_by_underscore}"`. `head` is the
    first surviving content token in the QUERY'S OWN ORIGINAL order (after
    the same stopword/decoration stripping, before sorting) -- what the
    query is actually about, as opposed to what modifies it. It rides
    alongside the sorted token key so that annotate()'s batch-level merge
    (see _merge_subset_keys) can require two keys to share a head before
    treating one as a more-specific variant of the other: `gafas de sol`
    (head `gafas`) and `funda para gafas de sol` (head `funda`, a
    sunglasses CASE) have `{gafas, sol}` as a strict subset of
    `{funda, gafas, sol}` and would wrongly merge on token-set containment
    alone -- the head differs, so they must not.

    This function is pure and per-query: it has no knowledge of any other
    row in the batch. A variant that adds one genuine extra content word
    neither list covers (e.g. "solar" in "comprar gafas eclipse solar")
    still gets its own, larger key here -- annotate() below does a second,
    batch-level merge pass on top of these keys to fold that case in too,
    when heads also agree.
    """
    tokens = [
        t for t in _tokenize(query)
        if t not in CLUSTER_STOPWORDS and t not in CLUSTER_DECORATION_TOKENS
    ]
    head = tokens[0] if tokens else ""
    return f"{head}:{'_'.join(sorted(tokens))}"


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
    elif parent_tokens and set(parent_tokens) <= set(tokens):
        # `elif`: contiguous already implies scattered, so a contiguous
        # match must never collect both.
        score += PARENT_SCATTERED_POINTS
        reasons.append("contains_parent_tokens_scattered")

    # A chain name normally counts as a retail modifier, but it is weaker
    # evidence than `comprar`, and inside a lookup it is part of the lookup:
    # `como llegar a mercadona` and `que horario tiene lidl` are Maps-shaped
    # navigational queries -- no stock decision follows from either. So when
    # the informational-head rule below is going to fire, the chain name
    # neither exempts the row from it nor scores. `comprar` still does both.
    retail_modifier_hits = {t for t in tokens if t in RETAIL_MODIFIER_TOKENS}
    informational_head = (
        bool(tokens)
        and tokens[0] in INFORMATIONAL_HEAD_TOKENS
        and not retail_modifier_hits
    )

    modifier_hits = sorted(retail_modifier_hits)
    if len(tokens) > 1 and not informational_head:
        modifier_hits = sorted(
            retail_modifier_hits | {t for t in tokens if t in CHAIN_NAME_TOKENS}
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
    elif informational_head:
        # `elif`, not a second `if`: the phrase list and the head list
        # overlap ("donde tirar bombillas" matches both), and the same
        # single signal must never be charged twice.
        score += INFORMATIONAL_MARKER_PENALTY
        reasons.append("informational_head:" + tokens[0])

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

def _merge_subset_keys(keys) -> dict:
    """Map each distinct cluster_key in a batch to its final cluster_id.

    A key whose token set is a strict superset of another present key's
    token set, AND WHICH SHARES THAT KEY'S HEAD TOKEN, collapses into that
    smaller key -- e.g. "comprar gafas eclipse solar" produces the raw key
    `gafas:eclipse_gafas_solar` (its "solar" is genuine content
    cluster_key() cannot drop), and that key's token set
    {eclipse, gafas, solar} is a strict superset of `gafas:eclipse_gafas`'s
    {eclipse, gafas} -- same head `gafas`, also present in the same batch
    -- so it collapses into `gafas:eclipse_gafas`.

    The head-token requirement guards against conflating an accessory with
    the product it accessorizes. Pure token-set containment cannot tell
    "same product, more specific" from "different product that merely
    mentions the first one": `funda para gafas de sol` (a sunglasses CASE)
    strips to {funda, gafas, sol}, a strict superset of `gafas de sol`'s
    {gafas, sol}, and would wrongly merge into the sunglasses cluster on
    token-set containment alone. Its head is `funda`, not `gafas` --
    different subject -- so it must stay its own cluster. Telling a
    shopkeeper to stock sunglasses when Madrid is searching for sunglasses
    cases is a confidently WRONG retail signal, worse than showing two
    separate (truthful) cards.

    This rule is deliberately conservative and will sometimes fail to merge
    two queries a human would still group -- e.g. `pack bombillas led` has
    head `pack`, not `bombillas`, so it will NOT join `bombillas led`. That
    is the correct failure direction on purpose: under-merging costs a
    shopkeeper a little redundancy (two true cards instead of one); over-
    merging costs them a wrong product to stock. When this heuristic is
    unsure, it must split, not join -- do not "improve" this later by
    matching on anything looser than an exact head token.

    This is a batch-level pass over the *set* of distinct keys the batch
    produced -- never per-row and never dependent on which row happened to
    appear first -- so the mapping (and therefore every row's cluster_id)
    cannot depend on row order. See test_cluster_merge_is_order_independent.

    Two further constraints, both load-bearing (unchanged from fix round 1,
    not reworked here):
    - An absorbing (i.e. smaller/target) key must have at least 2 tokens,
      so a bare single-token key such as `gafas` can never swallow every
      other eyewear query in the table.
    - When more than one present key qualifies (same head, strict token
      subset), the smallest one wins -- fewest tokens first, then
      lexicographic key string as a tiebreak -- so the result is a pure
      function of the key set alone, independent of iteration or insertion
      order. Because the strict-subset relation is transitive, picking the
      global minimum qualifying key directly (rather than one merge hop at
      a time) already lands on the fixed point: if some key K were a
      smaller same-head subset of that minimum, K would itself be a
      qualifying same-head strict subset of the original key too, and so
      would have been chosen instead.
    """
    parsed = {}
    for key in keys:
        head, _, tokens_part = key.partition(":")
        parsed[key] = (head, frozenset(tokens_part.split("_")))

    mapping = {}
    for key, (head, tokens) in parsed.items():
        candidates = [
            other for other, (other_head, other_tokens) in parsed.items()
            if other_head == head
            and other_tokens < tokens
            and len(other_tokens) >= 2
        ]
        mapping[key] = (
            min(candidates, key=lambda k: (len(parsed[k][1]), k))
            if candidates else key
        )
    return mapping


def annotate(rows: list) -> list:
    """Adds relevance_score / relevance_tier / relevance_reasons / cluster_id.

    Never drops or reorders a row: output length always equals input length,
    and every original field (including `growth_pct` / `is_breakout`) is
    copied through unchanged. Rows are copied, not mutated in place, so the
    caller's original list is left untouched.

    `cluster_id` is not simply `cluster_key(query)`: after every row's raw
    key is computed, keys whose token set is a strict superset of another
    present key's, AND which share that key's head token, are merged
    toward the smaller key (see _merge_subset_keys), so near-duplicates
    that differ by one genuine extra content word -- not just a stopword or
    retail decoration -- still land on one card, without conflating an
    accessory (`funda para gafas de sol`) with the product it accessorizes
    (`gafas de sol`). That merge is batch-level and order-independent;
    cluster_key() itself stays a pure per-query function with no knowledge
    of any other row, per the endpoint task's public-surface contract.
    """
    raw_keys = [cluster_key(row.get("query", "")) for row in rows]
    merge_map = _merge_subset_keys(set(raw_keys))

    annotated = []
    for row, raw_key in zip(rows, raw_keys):
        result = score_query(row.get("query", ""), row.get("parent_keyword", ""))
        new_row = dict(row)
        new_row["relevance_score"] = result["score"]
        new_row["relevance_tier"] = result["tier"]
        new_row["relevance_reasons"] = result["reasons"]
        new_row["cluster_id"] = merge_map[raw_key]
        annotated.append(new_row)
    return annotated
