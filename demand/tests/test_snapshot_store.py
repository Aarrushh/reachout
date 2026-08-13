import pytest
from demand.ingest.snapshot_store import store_snapshots
from demand.tests.fake_supa import FakeSupabase


def make_client():
    """A fake shaped like production: the client is bound to `demand`.

    `trend_snapshots` IS a demand table (`demand/data/schema.sql`), so
    `store_snapshots` reads it unqualified and correctly. Declaring it in
    the default schema of a `demand`-bound client is what production looks
    like -- unlike `products`, which lives in `public`.
    """
    return FakeSupabase(default_schema="demand", tables={"trend_snapshots": []})


def _rows(client):
    return client.table("trend_snapshots").select().execute().data


def test_valid_batch_upsert():
    fake_client = make_client()

    rows = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "keyword": "Apple",
            "geo": "ES-MD",
            "timeframe": "today 3-m",
            "provider": "trendspy",
            "captured_at": "2023-10-25T14:30:00Z",
            "series": [
                {"date": "2023-08-01", "value": 50},
                {"date": "2023-09-01", "value": 75}
            ],
            "region_breakdown": None
        }
    ]

    store_snapshots(rows, fake_client)

    db_rows = _rows(fake_client)
    assert len(db_rows) == 1

    saved_row = db_rows[0]
    assert saved_row["keyword"] == "Apple"
    assert saved_row["captured_date"] == "2023-10-25"

    # The caller's payload is not mutated: it stays schema-clean, so it can
    # still be validated (and passed to compute_signals) afterwards.
    assert "captured_date" not in rows[0]

def test_schema_invalid_row():
    fake_client = make_client()

    rows = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "keyword": "Apple",
            # missing 'geo', 'timeframe', 'provider', 'captured_at'
            "series": []
        }
    ]

    with pytest.raises(ValueError, match="Schema validation failed for keyword 'Apple'"):
        store_snapshots(rows, fake_client)

    assert len(_rows(fake_client)) == 0


def _valid_row(**overrides):
    row = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "keyword": "Apple",
        "geo": "ES-MD",
        "timeframe": "today 3-m",
        "provider": "trendspy",
        "captured_at": "2023-10-25T14:30:00Z",
        "series": [{"date": "2023-08-01", "value": 50}],
        "region_breakdown": None,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize("overrides, why", [
    ({"id": "not-a-uuid"}, "format: uuid on id"),
    ({"series": [{"date": "NOPE", "value": 50}]}, "format: date on series[].date"),
    ({"series": [{"date": "2023-08-01", "value": None}]}, "null interest value"),
    ({"series": [{"date": "2023-08-01", "value": -1}]}, "negative interest value"),
])
def test_format_and_range_violations_are_rejected(overrides, why):
    """`format` asserts now. Bare `jsonschema.validate` ignores `format` on
    draft-07, so `id="not-a-uuid"` used to be written to a `uuid` column."""
    fake_client = make_client()

    with pytest.raises(ValueError, match="Schema validation failed"):
        store_snapshots([_valid_row(**overrides)], fake_client)

    assert len(_rows(fake_client)) == 0


def test_db_only_captured_date_column_is_rejected_on_input():
    """The HARD RULE: `captured_date` is a DB-only column deliberately
    absent from trend_snapshot.schema.json (additionalProperties:false).
    Validation runs BEFORE it is attached, so a row that arrives already
    carrying it -- i.e. one read back off the table -- is refused rather
    than silently round-tripped."""
    fake_client = make_client()

    with pytest.raises(ValueError, match="Schema validation failed"):
        store_snapshots([_valid_row(captured_date="2023-10-25")], fake_client)

    assert len(_rows(fake_client)) == 0

def test_idempotent_upsert():
    fake_client = make_client()

    row1 = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "keyword": "Banana",
        "geo": "ES-MD",
        "timeframe": "today 1-m",
        "provider": "trendspy",
        "captured_at": "2023-10-26T10:00:00Z",
        "series": [{"date": "2023-10-20", "value": 20}]
    }

    # First insert
    store_snapshots([row1], fake_client)

    db_rows = _rows(fake_client)
    assert len(db_rows) == 1
    assert db_rows[0]["keyword"] == "Banana"

    # Second insert with same unique keys but different value for series
    row2 = dict(row1)
    row2["series"] = [{"date": "2023-10-20", "value": 80}]

    store_snapshots([row2], fake_client)

    db_rows = _rows(fake_client)
    assert len(db_rows) == 1
    assert db_rows[0]["series"][0]["value"] == 80


def test_a_rescaled_value_above_100_is_stored_not_rejected():
    """49 keywords do not fit in one request, so batches are rescaled onto a
    shared anchor. A keyword bigger than the reference then exceeds 100 --
    Google's 0-100 only holds inside a single batch.

    This is not hypothetical: the first live run fetched all 49 snapshots,
    spent 12 searches, and then threw all of them away on
    `163.56821589205396 is greater than the maximum of 100` for 'cafe'.
    Nothing was written. Clamping instead would flatten exactly the peaks
    the rescaling exists to expose, and would invent a number Google never
    gave.
    """
    fake_client = make_client()
    row = _valid_row(series=[{"date": "2023-08-01", "value": 163.56821589205396}])

    store_snapshots([row], fake_client)

    assert _rows(fake_client)[0]["series"][0]["value"] == 163.56821589205396


def test_region_breakdown_keeps_its_100_ceiling():
    """region_breakdown is raw Google, one request, never rescaled. It has no
    reason to exceed 100 and a value that does means something is wrong."""
    fake_client = make_client()
    row = _valid_row(region_breakdown=[{"region": "Madrid", "value": 101}])

    with pytest.raises(ValueError):
        store_snapshots([row], fake_client)
