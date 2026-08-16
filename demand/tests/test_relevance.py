"""Tests for demand/api/relevance.py -- the commercial-relevance scorer.

Pure unit tests over literal strings pulled from the real
demand.rising_queries table (see the brief this task was built from). No
API key, no network, no database -- demand/tests/conftest.py's
`block_network` fixture would fail any test that tried anyway.
"""

import os
import sys

import pytest

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from demand.api.relevance import (  # noqa: E402
    annotate,
    cluster_key,
    score_query,
)


# ---------------------------------------------------------------------------
# 1. The eclipse regression guard
# ---------------------------------------------------------------------------
# `gafas de sol` is the parent keyword. Neither variant below contains that
# phrase as a substring, and a naive "query must contain parent_keyword"
# gate would silently drop both -- along with the rest of a real, dated,
# local demand spike (the solar eclipse) that a Madrid shop could actually
# stock for. This test exists specifically to fail loudly if someone
# reintroduces a containment gate.

def test_eclipse_regression_guard_carrefour_variant():
    result = score_query("gafas eclipse carrefour", "gafas de sol")
    assert result["tier"] == "commercial"
    assert result["reasons"]  # must explain itself


def test_eclipse_regression_guard_no_containment_variant():
    result = score_query("gafas para el eclipse", "gafas de sol")
    assert result["tier"] == "commercial"
    assert result["reasons"]


# ---------------------------------------------------------------------------
# 2. café's Google Maps navigational categories tier as noise
# ---------------------------------------------------------------------------

def test_maps_navigational_categories_tier_as_noise():
    for query in ("bancos", "empleos", "museos", "vuelos"):
        result = score_query(query, "café")
        assert result["tier"] == "noise", (
            f"{query!r} scored {result!r}, expected noise"
        )


# ---------------------------------------------------------------------------
# 3. Informational-intent lookups tier below commercial
# ---------------------------------------------------------------------------

def test_translation_lookup_tiers_below_commercial():
    result = score_query("bufanda en ingles", "bufanda")
    assert result["tier"] != "commercial"


def test_disposal_lookup_tiers_below_commercial():
    result = score_query("donde tirar bombillas", "bombillas")
    assert result["tier"] != "commercial"


# ---------------------------------------------------------------------------
# 4. Genuine retail queries with variant/spec tokens tier commercial
# ---------------------------------------------------------------------------

def test_variant_spec_token_tiers_commercial():
    result = score_query("bombillas led g9", "bombillas")
    assert result["tier"] == "commercial"
    assert any("variant_token" in r for r in result["reasons"])


def test_chain_name_modifier_tiers_commercial():
    result = score_query("zumo de arandanos mercadona", "zumo")
    assert result["tier"] == "commercial"


# ---------------------------------------------------------------------------
# 5. All five eclipse variants share one cluster_id
# ---------------------------------------------------------------------------
# cluster_key() folds accents, lowercases, drops CLUSTER_STOPWORDS and
# CLUSTER_DECORATION_TOKENS (retail decoration: chain names, "comprar",
# "donde", ...), sorts what remains, and joins it. Of the five eclipse
# variants in the source table ("gafas eclipse", "gafas para el eclipse",
# "gafas eclipse carrefour", "comprar gafas eclipse solar", "donde comprar
# gafas para el eclipse"), decoration-stripping alone already collapses
# four of them onto the key `eclipse_gafas`; only "solar" in "comprar gafas
# eclipse solar" is genuine extra content neither list covers, so
# cluster_key() alone still gives that one variant the distinct, larger key
# `eclipse_gafas_solar`. annotate() then merges that larger key into the
# smaller key it is a strict superset of (see _merge_subset_keys in
# relevance.py), so all five variants end up sharing one cluster_id. This
# is the settled requirement -- all five share one id -- not merely
# whatever today's implementation happens to produce.

def test_eclipse_stopword_variants_share_cluster_key():
    assert cluster_key("gafas eclipse") == cluster_key("gafas para el eclipse")


_ECLIPSE_VARIANTS = [
    "gafas eclipse",
    "gafas para el eclipse",
    "gafas eclipse carrefour",
    "comprar gafas eclipse solar",
    "donde comprar gafas para el eclipse",
]


def test_all_five_eclipse_variants_share_one_cluster_id():
    rows = [
        {"query": q, "parent_keyword": "gafas de sol"} for q in _ECLIPSE_VARIANTS
    ]
    result = annotate(rows)
    cluster_ids = {row["cluster_id"] for row in result}
    assert len(cluster_ids) == 1, (
        f"expected all five eclipse variants to share one cluster_id, "
        f"got {cluster_ids!r}"
    )


def test_cluster_merge_is_order_independent():
    rows = [
        {"query": q, "parent_keyword": "gafas de sol"} for q in _ECLIPSE_VARIANTS
    ]

    forward = {row["query"]: row["cluster_id"] for row in annotate(rows)}
    shuffled = {
        row["query"]: row["cluster_id"]
        for row in annotate(list(reversed(rows)))
    }
    assert forward == shuffled


def test_single_token_key_does_not_absorb_unrelated_queries():
    # A bare single-token cluster_key ("gafas") must never act as an
    # absorbing key for a larger, unrelated query that merely shares that
    # one token -- otherwise every eyewear query in the table would
    # collapse into it. "gafas" alone and "gafas eclipse" must stay
    # distinct clusters.
    rows = [
        {"query": "gafas", "parent_keyword": "gafas de sol"},
        {"query": "gafas eclipse", "parent_keyword": "gafas de sol"},
    ]
    result = annotate(rows)
    by_query = {row["query"]: row["cluster_id"] for row in result}
    assert by_query["gafas"] != by_query["gafas eclipse"]


# ---------------------------------------------------------------------------
# 5b. Accessory/product conflation guard (fix round 2)
# ---------------------------------------------------------------------------
# Pure token-set subset containment cannot tell "same product, more
# specific" (`comprar gafas eclipse solar` ⊃ `gafas eclipse`, both about
# sunglasses) from "different product that merely mentions the first one"
# (`funda para gafas de sol` ⊃ `gafas de sol` -- a sunglasses CASE is not
# sunglasses). cluster_key() now also returns a head token -- the first
# surviving content token in the query's own original order -- and
# _merge_subset_keys() only merges keys that share a head. Telling a
# shopkeeper to stock sunglasses when Madrid is actually searching for
# sunglasses cases is a confidently wrong retail signal; two separate,
# truthful cards are strictly better than one false merge.

def test_accessory_and_product_get_different_cluster_ids():
    rows = [
        {"query": "gafas de sol", "parent_keyword": "gafas de sol"},
        {"query": "funda para gafas de sol", "parent_keyword": "gafas de sol"},
    ]
    result = annotate(rows)
    by_query = {row["query"]: row["cluster_id"] for row in result}
    assert by_query["gafas de sol"] != by_query["funda para gafas de sol"]


def test_second_accessory_product_pair_stays_separate():
    # A second, independently-chosen accessory/product pair -- proves the
    # head-token guard is a general rule, not one hardcoded string check.
    # "caja para bombillas led" (a storage box for LED bulbs) is not
    # "bombillas led" (the bulbs themselves), even though its stripped
    # token set {caja, bombillas, led} is a strict superset of
    # {bombillas, led}.
    rows = [
        {"query": "bombillas led", "parent_keyword": "bombillas"},
        {"query": "caja para bombillas led", "parent_keyword": "bombillas"},
    ]
    result = annotate(rows)
    by_query = {row["query"]: row["cluster_id"] for row in result}
    assert by_query["bombillas led"] != by_query["caja para bombillas led"]


def test_same_head_superset_still_merges():
    # Guards against the cheap way to pass the two tests above: simply
    # disabling the subset merge altogether. Here both queries DO share a
    # head ("bombillas"), and one token set IS a strict superset of the
    # other, so they must still collapse to one cluster_id -- proving the
    # head-token gate is an added condition, not a replacement for merging.
    rows = [
        {"query": "bombillas led", "parent_keyword": "bombillas"},
        {"query": "bombillas led g9", "parent_keyword": "bombillas"},
    ]
    result = annotate(rows)
    cluster_ids = {row["cluster_id"] for row in result}
    assert len(cluster_ids) == 1, (
        f"expected same-head superset queries to still merge, got {cluster_ids!r}"
    )


# ---------------------------------------------------------------------------
# 6. Accent folding
# ---------------------------------------------------------------------------

def test_accent_folding_cluster_key():
    assert cluster_key("café") == cluster_key("cafe")


def test_accent_folding_score():
    with_accent = score_query("café", "café")
    without_accent = score_query("cafe", "cafe")
    assert with_accent["score"] == without_accent["score"]
    assert with_accent["tier"] == without_accent["tier"]


# ---------------------------------------------------------------------------
# 7. annotate() never drops a row
# ---------------------------------------------------------------------------

def test_annotate_preserves_row_count():
    rows = [
        {"query": "gafas eclipse carrefour", "parent_keyword": "gafas de sol"},
        {"query": "bancos", "parent_keyword": "café"},
        {"query": "bombillas led g9", "parent_keyword": "bombillas"},
    ]
    result = annotate(rows)
    assert len(result) == len(rows)


def test_annotate_empty_list():
    assert annotate([]) == []


# ---------------------------------------------------------------------------
# 8. Every scored row carries a non-empty reasons list
# ---------------------------------------------------------------------------

def test_reasons_always_non_empty():
    queries = [
        ("gafas eclipse carrefour", "gafas de sol"),
        ("bancos", "café"),
        ("bufanda en ingles", "bufanda"),
        ("bombillas led g9", "bombillas"),
        # query == parent, so contains_parent_keyword fires (the query is a
        # one-token contiguous run of itself) alongside single_bare_token --
        # NOT a case with no signals at all.
        ("xyz", "xyz"),
    ]
    for query, parent in queries:
        result = score_query(query, parent)
        assert isinstance(result["reasons"], list)
        assert len(result["reasons"]) >= 1

    rows = [{"query": q, "parent_keyword": p} for q, p in queries]
    for row in annotate(rows):
        assert len(row["relevance_reasons"]) >= 1


def test_no_signals_detected_fallback_reached():
    # A query that actually trips none of the positive or negative signals:
    # too many tokens for the token-count-range band, no parent-keyword
    # containment, no retail modifier, no chain name, no variant token, not
    # blocklisted, no informational marker, and not a single bare token.
    # This is the only path that should ever emit "no_signals_detected".
    result = score_query(
        "lorem ipsum dolor sit amet consectetur", "unrelated parent"
    )
    assert result["reasons"] == ["no_signals_detected"]
    assert result["score"] == 0.0


# ---------------------------------------------------------------------------
# 9. annotate() never invents a growth number
# ---------------------------------------------------------------------------

def test_annotate_never_invents_growth_pct():
    row = {
        "id": "00000000-0000-0000-0000-000000000000",
        "parent_keyword": "gafas de sol",
        "query": "gafas eclipse carrefour",
        "growth_pct": None,
        "is_breakout": True,
        "geo": "ES-MD",
        "gprop": "",
        "captured_at": "2026-08-11T00:00:00Z",
    }
    result = annotate([row])[0]
    assert result["is_breakout"] is True
    assert result["growth_pct"] is None
    # Original fields survive untouched alongside the new derived ones.
    assert result["parent_keyword"] == "gafas de sol"
    assert result["query"] == "gafas eclipse carrefour"
    assert "relevance_score" in result
    assert "relevance_tier" in result
    assert "relevance_reasons" in result
    assert "cluster_id" in result


# ---------------------------------------------------------------------------
# 10. Informational heads. All eight query strings below are verbatim live
# rows from demand.rising_queries; the first seven tiered `commercial`
# before this rule existed.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query,parent", [
    ("se puede ver el eclipse con gafas de sol normales", "gafas de sol"),
    ("puedo mirar el eclipse con gafas de sol", "gafas de sol"),
    ("cuantos huevos puedo comer al dia", "huevos"),
    ("cuanto duran los huevos cocidos en la nevera", "huevos"),
    ("como hacer huevos cocidos", "huevos"),
    ("para que sirve el te matcha", "te"),
    ("quien invento la cerveza", "cerveza"),
])
def test_interrogative_head_tiers_as_noise(query, parent):
    result = score_query(query, parent)
    assert result["tier"] == "noise", result
    assert any(r.startswith("informational_head:") for r in result["reasons"])


def test_retail_modifier_exempts_an_interrogative_head():
    """`donde comprar ...` is a purchase, not a lookup -- the one live row
    the head rule would otherwise destroy."""
    result = score_query("donde comprar gafas para el eclipse", "gafas de sol")
    assert result["tier"] == "commercial", result
    assert not any(r.startswith("informational_head:") for r in result["reasons"])


def test_informational_penalty_is_applied_at_most_once():
    """`donde tirar bombillas` matches the phrase marker AND the head token;
    it must be charged once, not twice."""
    result = score_query("donde tirar bombillas", "bombillas")
    assert result["score"] == pytest.approx(0.0)
    assert not any(r.startswith("informational_head:") for r in result["reasons"])


# ---------------------------------------------------------------------------
# 11. Widened stopwords (fix round 3)
# ---------------------------------------------------------------------------

def test_function_words_do_not_split_a_cluster():
    """These two live rows are one demand story; `se`/`un` must not head
    two separate cards. Their token sets still differ by the genuine
    content word "solar" (cluster_key() alone must not absorb that -- see
    test_widened_stopwords_do_not_merge_distinct_products below), so this
    checks the annotate()-level cluster_id, which folds the "solar" variant
    in via the shared-head subset merge (_merge_subset_keys), the same way
    test_all_five_eclipse_variants_share_one_cluster_id does above."""
    rows = [
        {
            "query": "se puede ver el eclipse solar con gafas de sol",
            "parent_keyword": "gafas de sol",
        },
        {
            "query": "se puede ver un eclipse con gafas de sol",
            "parent_keyword": "gafas de sol",
        },
    ]
    cluster_ids = {row["cluster_id"] for row in annotate(rows)}
    assert len(cluster_ids) == 1, cluster_ids


def test_widened_stopwords_do_not_merge_distinct_products():
    """Guard the other direction: a genuine content word still splits."""
    assert cluster_key("gafas de sol") != cluster_key("gafas de sol homologadas")
    assert cluster_key("funda para gafas de sol") != cluster_key("gafas de sol")


# ---------------------------------------------------------------------------
# 12. Scattered parent-keyword matches (fix round 5)
# ---------------------------------------------------------------------------

def test_scattered_parent_tokens_still_reach_commercial():
    result = score_query("gafas para el eclipse de sol", "gafas de sol")
    assert result["tier"] == "commercial", result
    assert "contains_parent_tokens_scattered" in result["reasons"]


def test_scattered_signal_does_not_double_count_a_contiguous_match():
    """A contiguous match implies a scattered one; only the stronger
    signal may be credited, or every already-correct row silently
    reweights."""
    result = score_query("gafas de sol para el eclipse", "gafas de sol")
    assert "contains_parent_keyword" in result["reasons"]
    assert "contains_parent_tokens_scattered" not in result["reasons"]
    assert result["score"] == pytest.approx(2.0)


def test_scattered_signal_does_not_rescue_an_informational_row():
    """The scattered signal is worth exactly COMMERCIAL_THRESHOLD so it can
    lift a 0.0 row over the bar and can never lift one already carrying the
    -3.0 informational penalty. This query genuinely reaches the scattered
    branch: `gafas`, `de` and `sol` are all present but not adjacent."""
    result = score_query("que gafas usar para el eclipse de sol", "gafas de sol")
    assert "contains_parent_tokens_scattered" in result["reasons"]
    assert "informational_head:que" in result["reasons"]
    assert result["score"] == pytest.approx(-2.0)
    assert result["tier"] == "noise"
