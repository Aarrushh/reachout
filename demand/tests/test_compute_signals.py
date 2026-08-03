import json
import os
import uuid
from datetime import date, timedelta

import pytest
from jsonschema import ValidationError

from demand.scripts.compute_signals import compute_signals, signal_id

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "signals")

# Every constructed series starts on a Monday, so week i of a series is the
# ISO week window [FIRST_MONDAY + i weeks, +6 days].
FIRST_MONDAY = date(2023, 10, 2)
CAPTURED_AT = "2023-11-20T10:00:00Z"


def _weekly_series(values, skip_weeks=()):
    """One point per ISO week; `skip_weeks` punches provider gaps in it."""
    return [
        {"date": (FIRST_MONDAY + timedelta(weeks=i)).isoformat(), "value": float(v)}
        for i, v in enumerate(values)
        if i not in skip_weeks
    ]


def _snapshot(keyword, values=None, *, snap_id=None, geo="ES-MD", skip_weeks=(),
              captured_at=CAPTURED_AT, series=None):
    return {
        "id": snap_id or str(uuid.uuid4()),
        "keyword": keyword,
        "geo": geo,
        "timeframe": "today 3-m",
        "provider": "trendspy",
        "captured_at": captured_at,
        "series": series if series is not None else _weekly_series(values, skip_weeks),
        "region_breakdown": None,
    }


def _rows(snapshots, **kwargs):
    kwargs.setdefault("computed_at", "2023-11-20T12:00:00Z")
    return compute_signals(snapshots, **kwargs)


# ---------------------------------------------------------------------------
# The golden file. Hand-derived from the spec, row by row -- never
# regenerated from the code. Only the `id` column was ever rewritten, and
# only by recomputing uuid5 from the documented natural key.
# ---------------------------------------------------------------------------

def test_compute_signals_byte_for_byte():
    with open(os.path.join(FIXTURES_DIR, "input_snapshots.json"), "r", encoding="utf-8") as f:
        snapshots = json.load(f)

    with open(os.path.join(FIXTURES_DIR, "expected_signals.json"), "r", encoding="utf-8") as f:
        expected_signals = json.load(f)

    category_map = {
        "high_kw": "HighCat",
        "medium_kw": "MedCat",
        "short_kw": "ShortCat",
        "gap_kw": "GapCat",
        "boundary_kw": "BoundCat"
    }

    # Compute signals
    actual_signals = compute_signals(snapshots, category_map=category_map, computed_at="2023-11-20T12:00:00Z")

    # Assert exact match (the compute_signals function also validates against the schema internally)
    assert actual_signals == expected_signals


def test_fixture_set_produces_a_high_confidence_row():
    """S3 binding (tests/fixtures/README.md): the 8-week fixture set must
    exercise the `high` tier through the real code path, not just carry a
    pre-baked `high` string in the golden file."""
    with open(os.path.join(FIXTURES_DIR, "input_snapshots.json"), "r", encoding="utf-8") as f:
        snapshots = json.load(f)

    rows = _rows(snapshots)
    high = [r for r in rows if r["confidence"] == "high"]
    assert high, "the fixture set must produce at least one high-confidence signal"
    assert {r["keyword"] for r in high} == {"high_kw"}


# ---------------------------------------------------------------------------
# Confidence tiers. Each of these calls compute_signals and asserts on the
# rows it returns: breaking the corresponding threshold in
# compute_signals.py turns the test red.
# ---------------------------------------------------------------------------

def test_short_series_is_low_confidence():
    """3 windows < MEDIUM_MIN_WINDOWS (4), so `low` regardless of level."""
    rows = _rows([_snapshot("short_kw", [50.0, 50.0, 50.0])])

    assert len(rows) == 3
    assert [r["confidence"] for r in rows] == ["low", "low", "low"]


def test_four_windows_reach_medium():
    """The same series one window longer crosses MEDIUM_MIN_WINDOWS."""
    rows = _rows([_snapshot("medium_kw", [50.0, 50.0, 50.0, 50.0])])

    assert [r["confidence"] for r in rows] == ["low", "low", "low", "medium"]


def test_medium_needs_the_interest_floor():
    """>= 4 windows but under MEDIUM_MIN_INTEREST (10.0) stays `low`."""
    rows = _rows([_snapshot("quiet_kw", [9.0, 9.0, 9.0, 9.0])])

    assert [r["confidence"] for r in rows] == ["low"] * 4
    assert rows[-1]["interest_avg"] == 9.0


def test_high_confidence_needs_eight_windows():
    """8 gap-free windows, >= 20 interest, one direction across the last 3."""
    rising = [20, 24, 29, 35, 42, 50, 60, 72]
    rows = _rows([_snapshot("high_kw", rising)])

    assert len(rows) == 8
    assert all(r["direction"] == "rising" for r in rows[1:])
    assert rows[-1]["confidence"] == "high"

    # One window short of the threshold, the same shape cannot be `high`.
    seven = _rows([_snapshot("high_kw", rising[:7])])
    assert len(seven) == 7
    assert seven[-1]["confidence"] == "medium"


def test_high_confidence_needs_the_interest_floor():
    """8 stable rising windows but ending under HIGH_MIN_INTEREST (20.0)."""
    rows = _rows([_snapshot("small_kw", [5, 6, 7, 9, 11, 13, 16, 19])])

    assert len(rows) == 8
    assert all(r["direction"] == "rising" for r in rows[1:])
    assert rows[-1]["interest_avg"] == 19.0
    assert rows[-1]["confidence"] == "medium"


def test_high_confidence_needs_a_stable_direction():
    """8 windows above the floor, but the last 3 directions disagree."""
    rows = _rows([_snapshot("jumpy_kw", [20, 24, 29, 35, 42, 50, 60, 61])])

    assert len(rows) == 8
    assert [r["direction"] for r in rows[-3:]] == ["rising", "rising", "flat"]
    assert rows[-1]["confidence"] == "medium"


def test_gapped_series_is_low_confidence():
    """A provider gap forces `low` even when every other high condition holds."""
    values = [30.0] * 9
    gapped = _rows([_snapshot("gap_kw", values, skip_weeks={4})])

    assert len(gapped) == 8  # 9 weeks minus the missing one
    assert [r["confidence"] for r in gapped] == ["low"] * 8

    # Control: the identical 8 windows with no hole in them DO reach `high`,
    # so the assertion above is about the gap and nothing else.
    ungapped = _rows([_snapshot("gap_kw", values[:8])])
    assert len(ungapped) == 8
    assert ungapped[-1]["confidence"] == "high"


# ---------------------------------------------------------------------------
# Direction boundary: +/-15% inclusive.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("values, expected_delta, expected_direction", [
    ([80.0, 92.0], 15.0, "rising"),      # exactly +15 -> rising
    ([80.0, 91.9], 14.88, "flat"),       # a hair under -> flat
    ([92.0, 78.2], -15.0, "falling"),    # exactly -15 -> falling
    ([92.0, 78.3], -14.89, "flat"),      # a hair under -> flat
])
def test_direction_boundary_is_inclusive_at_15pct(values, expected_delta, expected_direction):
    rows = _rows([_snapshot("boundary_kw", values)])

    assert rows[1]["delta_pct"] == expected_delta
    assert rows[1]["direction"] == expected_direction
    # The first window has no predecessor: 0% and therefore flat.
    assert rows[0]["delta_pct"] == 0.0
    assert rows[0]["direction"] == "flat"


# ---------------------------------------------------------------------------
# Overlapping captures (Google Trends re-normalises per request).
# ---------------------------------------------------------------------------

def test_overlapping_snapshots_take_the_most_recent_capture():
    older = _snapshot(
        "kw", [50.0],
        snap_id="11111111-1111-1111-1111-111111111111",
        captured_at="2023-11-20T09:00:00Z",
    )
    newer = _snapshot(
        "kw", [90.0],
        snap_id="22222222-2222-2222-2222-222222222222",
        captured_at="2023-11-20T10:00:00Z",
    )

    rows = _rows([older, newer])

    assert len(rows) == 1
    # Not 70.0: averaging two independently-normalised captures is meaningless.
    assert rows[0]["interest_avg"] == 90.0
    assert rows[0]["snapshot_ids"] == ["22222222-2222-2222-2222-222222222222"]

    # And the winner does not depend on the order the snapshots arrive in.
    assert _rows([newer, older]) == rows


def test_daily_points_inside_one_capture_are_still_averaged():
    """Within a single capture the scale IS shared, so a week's daily
    points average -- that is a weekly mean, not a scale mix."""
    series = [
        {"date": "2023-10-02", "value": 50.0},
        {"date": "2023-10-03", "value": 90.0},
    ]
    rows = _rows([_snapshot("kw", series=series)])

    assert len(rows) == 1
    assert rows[0]["interest_avg"] == 70.0


# ---------------------------------------------------------------------------
# Input validation (trend_snapshot.schema.json, with formats enforced).
# ---------------------------------------------------------------------------

def test_null_series_value_raises_validation_error_not_typeerror():
    bad = _snapshot("kw", [10.0])
    bad["series"][0]["value"] = None

    with pytest.raises(ValidationError):
        _rows([bad])


def test_non_uuid_snapshot_id_is_rejected():
    bad = _snapshot("kw", [10.0], snap_id="not-a-uuid")

    with pytest.raises(ValidationError):
        _rows([bad])


def test_non_date_series_date_is_rejected():
    bad = _snapshot("kw", [10.0])
    bad["series"][0]["date"] = "NOPE"

    with pytest.raises(ValidationError):
        _rows([bad])


def test_db_only_captured_date_column_is_rejected():
    """The HARD RULE, asserted: a row read back with `select("*")` from
    demand.trend_snapshots carries `captured_date`, which the contract
    (additionalProperties:false) does not allow."""
    from_db = _snapshot("kw", [10.0])
    from_db["captured_date"] = "2023-11-20"

    with pytest.raises(ValidationError):
        _rows([from_db])


# ---------------------------------------------------------------------------
# Determinism: ids, ranking, ordering.
# ---------------------------------------------------------------------------

def test_ids_are_uuid5_of_the_natural_key():
    snap = _snapshot("kw", [10.0, 12.0], snap_id="33333333-3333-3333-3333-333333333333")
    rows = _rows([snap])

    for row in rows:
        expected = str(uuid.uuid5(
            uuid.uuid5(uuid.NAMESPACE_DNS, "demand.reachout"),
            "|".join(["demand_signal", row["keyword"], row["geo"],
                      row["window_start"], row["window_end"]]),
        ))
        assert row["id"] == expected
        assert row["id"] == signal_id(
            row["keyword"], row["geo"], row["window_start"], row["window_end"]
        )
        assert uuid.UUID(row["id"]).version == 5

    # Same inputs, same ids -- across calls, with no monkeypatching.
    assert [r["id"] for r in _rows([snap])] == [r["id"] for r in rows]


def test_rank_is_scoped_to_geo():
    """ES-CT must not be ranked against ES-MD: separate market, separate
    0-100 normalisation."""
    snaps = [
        _snapshot("loud_kw", [90.0], geo="ES-MD", snap_id="11111111-1111-1111-1111-111111111111"),
        _snapshot("quiet_kw", [10.0], geo="ES-MD", snap_id="22222222-2222-2222-2222-222222222222"),
        _snapshot("other_kw", [50.0], geo="ES-CT", snap_id="33333333-3333-3333-3333-333333333333"),
    ]
    rows = _rows(snaps)

    by_key = {(r["keyword"], r["geo"]): r for r in rows}
    assert by_key[("loud_kw", "ES-MD")]["rank"] == 1
    assert by_key[("quiet_kw", "ES-MD")]["rank"] == 2
    # Ranked in its own geo, not slotted between the two ES-MD rows.
    assert by_key[("other_kw", "ES-CT")]["rank"] == 1


def test_output_is_independent_of_input_order():
    snaps = [
        _snapshot("a_kw", [50.0, 50.0], geo="ES-MD", snap_id="11111111-1111-1111-1111-111111111111"),
        _snapshot("b_kw", [50.0, 50.0], geo="ES-MD", snap_id="22222222-2222-2222-2222-222222222222"),
        _snapshot("c_kw", [50.0, 50.0], geo="ES-CT", snap_id="33333333-3333-3333-3333-333333333333"),
    ]

    assert _rows(list(reversed(snaps))) == _rows(snaps)
    assert json.dumps(_rows(snaps)) == json.dumps(_rows(list(reversed(snaps))))


def test_category_lookup_is_case_insensitive():
    """The map is keyed by normalized keyword; the universe keeps the
    original casing. Both spellings must resolve."""
    rows = _rows(
        [_snapshot("Zapatillas", [10.0])],
        category_map={"zapatillas": "Zapatillas"},
    )

    assert rows[0]["category"] == "Zapatillas"
