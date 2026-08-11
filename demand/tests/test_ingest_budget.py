from demand.scripts.run_ingest import estimate_searches


def test_estimate_batches_timeseries_four_real_keywords_per_request():
    # 49 keywords: 1 anchor + 48 real, 4 real per request => 12 requests.
    est = estimate_searches(universe_size=49, discovery_count=10)
    assert est["timeseries"] == 12


def test_estimate_charges_one_search_per_discovery_keyword():
    # RELATED_QUERIES accepts exactly 1 query -- no batching is possible.
    est = estimate_searches(universe_size=49, discovery_count=10)
    assert est["discovery"] == 10


def test_estimate_total_is_the_sum():
    est = estimate_searches(universe_size=49, discovery_count=10)
    assert est["total"] == 22


def test_estimate_handles_single_keyword_universe():
    est = estimate_searches(universe_size=1, discovery_count=0)
    assert est["timeseries"] == 1
    assert est["total"] == 1


def test_estimate_handles_empty_universe():
    est = estimate_searches(universe_size=0, discovery_count=0)
    assert est["total"] == 0
