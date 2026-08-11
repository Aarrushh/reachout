"""Which keywords the discovery pass is allowed to spend a search on.

Ten RELATED_QUERIES searches is 4% of the monthly budget, and RELATED_QUERIES
cannot batch -- one search buys exactly one parent keyword. So the selection
rule is a budget rule, not a ranking nicety, and it gets its own tests.

The bug these were written against: parents were taken straight off the top of
`signals` sorted by `delta_pct`, but `signals` holds ONE ROW PER KEYWORD PER
WEEKLY WINDOW (~13 per keyword from a `today 3-m` capture). Reproduced against
the real captured probe below.
"""

import json
from pathlib import Path

from demand.ingest.trends_client import parse_timeseries
from demand.scripts.compute_signals import compute_signals
from demand.scripts.run_ingest import (
    DISCOVERY_MIN_INTEREST,
    DISCOVERY_TOP_N,
    select_discovery_parents,
    snapshot_id,
)


def _signal(keyword, window_start, window_end, delta_pct, interest_avg):
    return {"keyword": keyword, "geo": "ES-MD", "window_start": window_start,
            "window_end": window_end, "delta_pct": delta_pct,
            "interest_avg": interest_avg}


def test_no_signals_means_no_searches():
    assert select_discovery_parents([], as_of_date="2026-08-10") == []


def test_a_keyword_can_only_be_picked_once():
    """The defect, minimally. One keyword, many windows, many high deltas.

    Same `parent_keyword` + `geo` + `captured_date` hashes to the SAME
    `rising_query_id`, so the repeat searches upsert over their own rows --
    they buy literally nothing.
    """
    signals = [
        _signal("abanico", "2026-05-18", "2026-05-24", 170.37, 6.57),
        _signal("abanico", "2026-05-25", "2026-05-31", 136.99, 15.57),
        _signal("abanico", "2026-08-03", "2026-08-09", 22.69, 13.14),
        _signal("bañador", "2026-08-03", "2026-08-09", 0.64, 45.86),
    ]
    parents = select_discovery_parents(signals, as_of_date="2026-08-10")
    assert len(parents) == len(set(parents))
    assert sorted(parents) == ["abanico", "bañador"]


def test_only_the_most_recent_closed_window_is_considered():
    """`DISCOVERY_TIMEFRAME` asks "what is rising NOW". A May window is not now."""
    signals = [
        # Huge delta, three months stale.
        _signal("stale", "2026-05-18", "2026-05-24", 900.0, 50.0),
        _signal("fresh", "2026-08-03", "2026-08-09", 5.0, 50.0),
    ]
    assert select_discovery_parents(signals, as_of_date="2026-08-10") == ["fresh"]


def test_the_partial_trailing_window_is_skipped():
    """A `today 3-m` capture ends mid-week, so the last window is 1 day long.

    The cron fires Monday 00:00 UTC, which is the worst case: the newest
    window is a few minutes old and its `delta_pct` compares one Monday
    against a full previous week. Selection uses the last window that has
    actually CLOSED.
    """
    signals = [
        _signal("closed", "2026-08-03", "2026-08-09", 22.69, 13.14),
        # window_end is in the future relative to as_of_date -> still open.
        _signal("partial", "2026-08-10", "2026-08-16", 999.0, 9.0),
    ]
    assert select_discovery_parents(signals, as_of_date="2026-08-10") == ["closed"]


def test_a_history_with_no_closed_window_still_selects():
    """Cold start must not silently discover nothing."""
    signals = [_signal("only", "2026-08-10", "2026-08-16", 12.0, 9.0)]
    assert select_discovery_parents(signals, as_of_date="2026-08-10") == ["only"]


def test_noise_below_the_interest_floor_is_not_worth_a_search():
    """`delta_pct = 100.0` off `interest_avg = 0.14` is rounding, not demand.

    `compute_signals` emits a flat +100.0 whenever the previous window was 0
    and the current one is not (`compute_signals.py`), so a keyword that had a
    single day rounded up to 1 on Google's integer 0-100 scale scores the same
    delta as a genuine doubling.
    """
    signals = [
        _signal("noise", "2026-08-03", "2026-08-09", 100.0, 0.14),
        _signal("real", "2026-08-03", "2026-08-09", 22.69, 13.14),
    ]
    assert select_discovery_parents(signals, as_of_date="2026-08-10") == ["real"]


def test_the_floor_is_inclusive():
    signals = [_signal("edge", "2026-08-03", "2026-08-09", 5.0,
                       DISCOVERY_MIN_INTEREST)]
    assert select_discovery_parents(signals, as_of_date="2026-08-10") == ["edge"]


def test_a_thin_week_spends_fewer_searches_rather_than_padding():
    """Budget rule: under-spending is correct, padding with noise is not."""
    signals = [
        _signal("real", "2026-08-03", "2026-08-09", 30.0, 13.0),
    ] + [
        _signal(f"noise{i}", "2026-08-03", "2026-08-09", 100.0, 0.14)
        for i in range(20)
    ]
    assert select_discovery_parents(signals, as_of_date="2026-08-10") == ["real"]


def test_selection_is_capped_at_the_budgeted_count():
    signals = [
        _signal(f"kw{i:02d}", "2026-08-03", "2026-08-09", float(100 - i), 30.0)
        for i in range(40)
    ]
    parents = select_discovery_parents(signals, as_of_date="2026-08-10")
    assert len(parents) == DISCOVERY_TOP_N
    # Highest delta first.
    assert parents[0] == "kw00"


def test_selection_is_deterministic_when_deltas_tie():
    signals = [
        _signal("zeta", "2026-08-03", "2026-08-09", 10.0, 30.0),
        _signal("alfa", "2026-08-03", "2026-08-09", 10.0, 30.0),
    ]
    assert select_discovery_parents(signals, as_of_date="2026-08-10") == [
        "alfa", "zeta"]


# ---------------------------------------------------------------------------
# Against the real captured probe -- the same data the review reproduced the
# defect on. 5 keywords, 93 daily points, 75 signals over 15 weekly windows.
# ---------------------------------------------------------------------------

CAPTURE = (Path(__file__).resolve().parents[1]
           / "tests" / "fixtures" / "trends" / "captured"
           / "timeseries_web_5kw.json")

PROBE_KEYWORDS = ["abanico", "agua mineral", "aspirinas", "bañador",
                  "bebidas energéticas"]


def _signals_from_capture():
    payload = json.loads(CAPTURE.read_text(encoding="utf-8"))
    series = parse_timeseries(payload, PROBE_KEYWORDS)
    now = "2026-08-10T00:00:00Z"
    snapshots = [{
        "id": snapshot_id(k, "ES-MD", "today 3-m", now[:10]),
        "keyword": k, "geo": "ES-MD", "timeframe": "today 3-m",
        "provider": "serpapi", "captured_at": now, "series": series[k],
        "region_breakdown": None,
    } for k in PROBE_KEYWORDS]
    return compute_signals(snapshots, category_map={}, computed_at=now)


def test_real_capture_selects_distinct_current_non_noise_parents():
    signals = _signals_from_capture()
    # Sanity: the input really does carry many windows per keyword.
    assert len(signals) > 5 * len(PROBE_KEYWORDS)

    parents = select_discovery_parents(signals, as_of_date="2026-08-10")

    assert len(parents) == len(set(parents)), "no keyword may buy two searches"
    assert set(parents) <= set(PROBE_KEYWORDS)
    # aspirinas and bebidas energéticas read 0.00 in the last closed window.
    assert "aspirinas" not in parents
    assert "bebidas energéticas" not in parents
    assert set(parents) == {"abanico", "agua mineral", "bañador"}


def test_real_capture_would_have_wasted_over_half_the_budget_unguarded():
    """Pins the size of the bug so a regression is visible as a number."""
    signals = _signals_from_capture()
    naive = [s["keyword"] for s in sorted(
        signals, key=lambda s: s.get("delta_pct", 0.0), reverse=True
    )[:DISCOVERY_TOP_N]]

    assert len(set(naive)) == 5, "the old rule bought 5 distinct parents for 10 searches"
    assert len(select_discovery_parents(signals, as_of_date="2026-08-10")) == 3
