from demand.ingest.rising_store import build_rows, rising_query_id, store_rising_queries
from demand.tests.fake_supa import FakeSupabase


def test_rising_query_id_is_stable_for_same_natural_key():
    a = rising_query_id("café", "café soluble", "ES-MD", "froogle", "2026-08-10")
    b = rising_query_id("café", "café soluble", "ES-MD", "froogle", "2026-08-10")
    assert a == b


def test_rising_query_id_differs_per_day():
    a = rising_query_id("café", "café soluble", "ES-MD", "froogle", "2026-08-10")
    b = rising_query_id("café", "café soluble", "ES-MD", "froogle", "2026-08-11")
    assert a != b


def test_rising_query_id_differs_per_parent():
    a = rising_query_id("café", "soluble", "ES-MD", "froogle", "2026-08-10")
    b = rising_query_id("té", "soluble", "ES-MD", "froogle", "2026-08-10")
    assert a != b


def test_rising_query_id_differs_per_gprop():
    # schema.sql:142-144 -- "a Shopping-derived row and a Web-derived row mean
    # different things and must never merge silently". The upsert is on `id`,
    # so if `gprop` is outside the hash the two collapse to one id and
    # whichever is written second overwrites the first with no error.
    a = rising_query_id("café", "soluble", "ES-MD", "froogle", "2026-08-10")
    b = rising_query_id("café", "soluble", "ES-MD", "", "2026-08-10")
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
                                        "froogle", "2026-08-10")


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


def _client():
    """A fake shaped like production: bound to `demand`, same pattern as
    test_snapshot_store.py's make_client()."""
    return FakeSupabase(default_schema="demand", tables={"rising_queries": []})


def test_store_rising_queries_upserts_rows_into_table():
    client = _client()
    rows = build_rows(
        parent_keyword="café",
        rows=[{"query": "café soluble", "growth_pct": 150.0,
               "is_breakout": False}],
        geo="ES-MD", gprop="froogle",
        captured_at="2026-08-10T09:00:00+00:00",
    )

    sent = store_rising_queries(client, rows)

    assert sent == 1
    stored = client.table("rising_queries").select().execute().data
    assert len(stored) == 1
    assert stored[0]["id"] == rows[0]["id"]
    assert stored[0]["query"] == "café soluble"


def test_store_rising_queries_is_idempotent_on_rerun():
    """Task 8 re-runs ingest live and asserts row counts stay flat. This is
    the offline proof of the same property: calling store_rising_queries
    twice with the same input must upsert onto the same row, not double it.
    Catching a missing/wrong on_conflict target here is free; catching it in
    Task 8 costs 22 real SerpApi searches."""
    client = _client()
    rows = build_rows(
        parent_keyword="café",
        rows=[{"query": "café soluble", "growth_pct": 150.0,
               "is_breakout": False}],
        geo="ES-MD", gprop="froogle",
        captured_at="2026-08-10T09:00:00+00:00",
    )

    store_rising_queries(client, rows)
    store_rising_queries(client, rows)

    stored = client.table("rising_queries").select().execute().data
    assert len(stored) == 1
    assert stored[0]["id"] == rows[0]["id"] == rising_query_id(
        "café", "café soluble", "ES-MD", "froogle", "2026-08-10"
    )
