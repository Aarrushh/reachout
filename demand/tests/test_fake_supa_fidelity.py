"""W1-FIX-D: proof that the demand test harness can see its own bugs.

Two classes of bug had already shipped past this suite:

  * `select("*")` into a schema-validated response — every real request
    500s, tests stay green, because the old fake threw its column list away
    and the fixtures had been hand-trimmed to exactly the schema's keys.
  * `format` keywords that never assert, because draft-07 treats `format`
    as an annotation unless a `FormatChecker` is passed.

These tests are the regression guard for both. If any of them starts
passing vacuously, the harness has gone blind again.
"""

import json
import uuid
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from demand.shared.validation import (
    DEMAND_FORMATS,
    UNENFORCED_FORMATS,
    validate_with_formats,
)
from demand.tests.fake_supa import (
    FakeSupabase,
    UnknownColumnError,
    UnknownSchemaError,
    UnknownTableError,
)

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "shared" / "schemas"


def load_schema(name):
    with open(SCHEMAS_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


TREND_SNAPSHOT_SCHEMA = load_schema("trend_snapshot.schema.json")
DEMAND_SIGNAL_SCHEMA = load_schema("demand_signal.schema.json")


def snapshot_row():
    """A trend_snapshots row shaped like the REAL table, not like the schema.

    `captured_date` is a DB-only generated column that is deliberately NOT in
    trend_snapshot.schema.json (additionalProperties:false) — see the HARD
    RULE in docs/JULES_DEMAND.md. Fixture rows must carry it, or `select("*")`
    on snapshots looks safe in tests and 500s in production.
    """
    return {
        "id": str(uuid.uuid4()),
        "keyword": "cerveza",
        "geo": "ES-MD",
        "timeframe": "today 3-m",
        "provider": "trendspy",
        "captured_at": "2024-01-01T12:00:00Z",
        "series": [{"date": "2024-01-01", "value": 50}],
        "region_breakdown": None,
        "captured_date": "2024-01-01",
    }


@pytest.fixture
def client():
    return FakeSupabase(tables={"trend_snapshots": [snapshot_row()]})


# --- Finding 1: the fake must honour its column list -----------------------


def test_select_explicit_columns_returns_exactly_those_keys():
    supa = FakeSupabase(tables={"t": [{"a": 1, "b": 2, "c": 3}]})
    rows = supa.table("t").select("a,b").execute().data
    assert len(rows) == 1
    assert set(rows[0].keys()) == {"a", "b"}
    assert rows[0] == {"a": 1, "b": 2}


def test_select_tolerates_whitespace_in_the_column_list():
    # app.py writes "id, keyword, geo" with spaces; PostgREST accepts it.
    supa = FakeSupabase(tables={"t": [{"id": 1, "keyword": "k", "geo": "ES-MD"}]})
    rows = supa.table("t").select("id, keyword").execute().data
    assert set(rows[0].keys()) == {"id", "keyword"}


def test_projection_does_not_mutate_the_fixture():
    supa = FakeSupabase(tables={"t": [{"a": 1, "b": 2}]})
    supa.table("t").select("a").execute()
    assert supa.table("t").select("*").execute().data[0] == {"a": 1, "b": 2}


def test_filters_still_see_columns_the_projection_drops():
    # PostgREST filters run server-side against the whole row; only the
    # response is narrowed. If projection happened before eq(), this returns 0.
    supa = FakeSupabase(tables={"t": [{"a": 1, "b": 2}, {"a": 9, "b": 3}]})
    rows = supa.table("t").select("b").eq("a", 1).execute().data
    assert rows == [{"b": 2}]


def test_select_star_returns_the_row_whole_including_extra_columns(client):
    row = client.table("trend_snapshots").select("*").execute().data[0]
    assert "captured_date" in row, (
        "select('*') must expose the DB-only column, or the trap stays invisible"
    )


def test_select_with_no_argument_is_select_star(client):
    row = client.table("trend_snapshots").select().execute().data[0]
    assert "captured_date" in row


def test_select_star_on_snapshots_fails_schema_validation(client):
    """THE regression guard for the whole class of bug.

    `select("*")` on trend_snapshots returns `captured_date`, which
    trend_snapshot.schema.json (additionalProperties:false) rejects. Any code
    that does `select("*")` here and validates the result must now go red in
    tests, exactly as it already goes 500 in production.
    """
    row = client.table("trend_snapshots").select("*").execute().data[0]
    with pytest.raises(ValidationError):
        validate_with_formats(row, TREND_SNAPSHOT_SCHEMA)


def test_explicit_column_select_on_snapshots_still_validates(client):
    """The other half: the CORRECT read must stay green.

    A guard that fails both ways teaches nothing.
    """
    row = (
        client.table("trend_snapshots")
        .select("id, keyword, geo, timeframe, provider, captured_at, series, region_breakdown")
        .execute()
        .data[0]
    )
    assert "captured_date" not in row
    validate_with_formats(row, TREND_SNAPSHOT_SCHEMA)


# --- Finding 1b: unknown schema / table / column must raise ----------------


def test_unknown_schema_raises(client):
    with pytest.raises(UnknownSchemaError):
        client.schema("bogus")


def test_known_schema_serves_its_own_tables():
    supa = FakeSupabase(
        tables={"demand_signals": []},
        schemas={"public": {"products": [{"category": "Alcohol"}]}},
        default_schema="demand",
    )
    rows = supa.schema("public").table("products").select("category").execute().data
    assert rows == [{"category": "Alcohol"}]


def test_schema_view_does_not_leak_into_later_table_calls():
    supa = FakeSupabase(
        tables={"demand_signals": [{"keyword": "cerveza"}]},
        schemas={"public": {"products": [{"category": "Alcohol"}]}},
        default_schema="demand",
    )
    supa.schema("public").table("products")
    # The client itself is still pointed at its default schema.
    assert supa.table("demand_signals").select("keyword").execute().data == [
        {"keyword": "cerveza"}
    ]
    with pytest.raises(UnknownTableError):
        supa.table("products")


def test_unknown_table_raises_instead_of_auto_vivifying(client):
    with pytest.raises(UnknownTableError):
        client.table("trend_snapsohts")  # typo, on purpose


def test_unknown_table_inside_a_schema_raises():
    supa = FakeSupabase(schemas={"public": {"products": []}}, default_schema="demand")
    with pytest.raises(UnknownTableError):
        supa.schema("public").table("stores")


def test_unknown_column_raises(client):
    with pytest.raises(UnknownColumnError):
        client.table("trend_snapshots").select("id, kyeword")


def test_unknown_column_check_is_skipped_for_an_empty_table():
    # An empty fixture table carries no shape, so there is nothing to check
    # against — and run_ingest.py legitimately selects from an empty table on
    # a first run. A false alarm here would be worse than the missed one.
    supa = FakeSupabase(tables={"trend_snapshots": []})
    assert supa.table("trend_snapshots").select("id,captured_date").execute().data == []


def test_column_absent_from_one_row_reads_back_as_none():
    # A nullable column omitted by a dict fixture is SQL NULL, not an error.
    supa = FakeSupabase(tables={"t": [{"a": 1, "b": 2}, {"a": 3}]})
    rows = supa.table("t").select("a,b").execute().data
    assert rows == [{"a": 1, "b": 2}, {"a": 3, "b": None}]


# --- Finding 2: `format` must actually be enforced -------------------------


def signal_row(**overrides):
    row = {
        "id": str(uuid.uuid4()),
        "keyword": "cerveza",
        "category": "Alcohol",
        "geo": "ES-MD",
        "timeframe": "today 3-m",
        "window_start": "2024-01-01",
        "window_end": "2024-01-07",
        "interest_avg": 50,
        "delta_pct": 10.0,
        "direction": "rising",
        "rank": 1,
        "confidence": "high",
        "snapshot_ids": [str(uuid.uuid4())],
        "computed_at": "2024-01-08T12:00:00Z",
    }
    row.update(overrides)
    return row


def test_a_valid_signal_still_validates():
    validate_with_formats(signal_row(), DEMAND_SIGNAL_SCHEMA)


def test_bad_uuid_raises():
    """`format: uuid` asserts through the helper. Bare jsonschema.validate
    accepts this string — that is the entire reason the helper exists."""
    with pytest.raises(ValidationError):
        validate_with_formats(signal_row(id="not-a-uuid"), DEMAND_SIGNAL_SCHEMA)


def test_reflected_script_tag_in_a_uuid_field_raises():
    with pytest.raises(ValidationError):
        validate_with_formats(
            signal_row(id="<script>alert(1)</script>"), DEMAND_SIGNAL_SCHEMA
        )


def test_bad_uuid_inside_an_array_item_raises():
    with pytest.raises(ValidationError):
        validate_with_formats(
            signal_row(snapshot_ids=["NOPE"]), DEMAND_SIGNAL_SCHEMA
        )


def test_bad_date_raises():
    with pytest.raises(ValidationError):
        validate_with_formats(
            signal_row(window_start="NOPE"), DEMAND_SIGNAL_SCHEMA
        )


def test_bare_jsonschema_validate_would_have_accepted_all_of_that():
    """Pins WHY validate_with_formats exists. If this ever starts raising,
    draft-07 semantics changed and the helper's docstring needs rewriting —
    it does not mean the helper is redundant."""
    import jsonschema

    jsonschema.validate(
        instance=signal_row(id="not-a-uuid", window_start="NOPE"),
        schema=DEMAND_SIGNAL_SCHEMA,
    )


def test_date_time_enforcement_matches_what_the_module_advertises():
    """`date-time` needs `rfc3339-validator` installed to be checkable.

    UNENFORCED_FORMATS is the honest answer for this environment; this test
    holds the module to it in both directions, so the day the dependency
    lands the assertion flips on its own instead of quietly rotting.
    """
    assert UNENFORCED_FORMATS <= DEMAND_FORMATS
    bad = signal_row(computed_at="NOPE")
    if "date-time" in UNENFORCED_FORMATS:
        validate_with_formats(bad, DEMAND_SIGNAL_SCHEMA)  # documented gap
    else:
        with pytest.raises(ValidationError):
            validate_with_formats(bad, DEMAND_SIGNAL_SCHEMA)
