from demand.ingest.rising_store import build_rows, rising_query_id


def test_rising_query_id_is_stable_for_same_natural_key():
    a = rising_query_id("café", "café soluble", "ES-MD", "2026-08-10")
    b = rising_query_id("café", "café soluble", "ES-MD", "2026-08-10")
    assert a == b


def test_rising_query_id_differs_per_day():
    a = rising_query_id("café", "café soluble", "ES-MD", "2026-08-10")
    b = rising_query_id("café", "café soluble", "ES-MD", "2026-08-11")
    assert a != b


def test_rising_query_id_differs_per_parent():
    a = rising_query_id("café", "soluble", "ES-MD", "2026-08-10")
    b = rising_query_id("té", "soluble", "ES-MD", "2026-08-10")
    assert a != b


def test_build_rows_maps_every_field():
    rows = build_rows(
        parent_keyword="café",
        rows=[{"query": "café soluble", "growth_pct": 150.0,
               "is_breakout": False}],
        geo="ES-MD", gprop="froogle",
        captured_at="2026-08-10T09:00:00+00:00",
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["parent_keyword"] == "café"
    assert row["query"] == "café soluble"
    assert row["growth_pct"] == 150.0
    assert row["is_breakout"] is False
    assert row["geo"] == "ES-MD"
    assert row["gprop"] == "froogle"
    assert row["captured_date"] == "2026-08-10"
    assert row["id"] == rising_query_id("café", "café soluble", "ES-MD",
                                        "2026-08-10")


def test_build_rows_keeps_breakout_growth_null():
    rows = build_rows(
        parent_keyword="leche",
        rows=[{"query": "leche de avena", "growth_pct": None,
               "is_breakout": True}],
        geo="ES-MD", gprop="froogle",
        captured_at="2026-08-10T09:00:00+00:00",
    )
    assert rows[0]["growth_pct"] is None
    assert rows[0]["is_breakout"] is True


def test_build_rows_returns_empty_for_no_rows():
    assert build_rows("café", [], "ES-MD", "froogle",
                      "2026-08-10T09:00:00+00:00") == []
