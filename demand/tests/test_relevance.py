"""Tests for demand/api/relevance.py -- the commercial-relevance scorer.

Pure unit tests over literal strings pulled from the real
demand.rising_queries table (see the brief this task was built from). No
API key, no network, no database -- demand/tests/conftest.py's
`block_network` fixture would fail any test that tried anyway.
"""

import os
import sys

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
# 5. Eclipse variants that differ only by stopwords share one cluster_key
# ---------------------------------------------------------------------------
# cluster_key's spec is: fold accents, lowercase, drop the named stopword
# list, sort what remains, join it. That is a SYNTACTIC near-duplicate key,
# not a semantic one. Of the five eclipse variants in the source table
# ("gafas eclipse", "gafas para el eclipse", "gafas eclipse carrefour",
# "comprar gafas eclipse solar", "donde comprar gafas para el eclipse"),
# only the first two differ from each other by nothing but stopwords
# ("para", "el") -- the other three each add a genuine extra content word
# (carrefour / comprar / solar / donde) that the stopword list does not
# cover, and by design those words are NOT discarded, so those three
# deliberately get distinct cluster keys. This test covers the pair the
# algorithm, as specified, actually collapses.

def test_eclipse_stopword_variants_share_cluster_key():
    assert cluster_key("gafas eclipse") == cluster_key("gafas para el eclipse")


def test_eclipse_variant_with_extra_content_word_gets_distinct_key():
    # Documents the boundary above: this is NOT a bug, it's the stopword-only
    # heuristic doing exactly what it says on the tin.
    assert cluster_key("gafas eclipse carrefour") != cluster_key("gafas eclipse")


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
        ("xyz", "xyz"),  # a token with no signals at all
    ]
    for query, parent in queries:
        result = score_query(query, parent)
        assert isinstance(result["reasons"], list)
        assert len(result["reasons"]) >= 1

    rows = [{"query": q, "parent_keyword": p} for q, p in queries]
    for row in annotate(rows):
        assert len(row["relevance_reasons"]) >= 1


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
