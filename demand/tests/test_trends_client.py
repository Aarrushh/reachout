import os
import sys
import json
import pytest
import jsonschema
from unittest.mock import MagicMock
from ingest.trends_client import get_provider, TrendspyProvider, FixtureProvider

def load_schema(name):
    schema_path = os.path.join(os.path.dirname(__file__), "..", "shared", "schemas", name)
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_fixture_provider_round_trips():
    schema = load_schema("trend_snapshot.schema.json")
    series_schema = schema["properties"]["series"]
    region_schema = schema["properties"]["region_breakdown"]

    provider = get_provider("fixture")
    
    # Test interest_over_time
    series_res = provider.interest_over_time(["sneakers"], geo="ES-MD", timeframe="today 3-m")
    assert "sneakers" in series_res
    assert len(series_res["sneakers"]) == 3
    jsonschema.validate(instance=series_res["sneakers"], schema=series_schema)

    # Test interest_by_region
    region_res = provider.interest_by_region("sneakers", geo="ES-MD")
    assert len(region_res) == 2
    jsonschema.validate(instance=region_res, schema=region_schema)

def test_trendspy_provider_translates_mocked_response(monkeypatch):
    schema = load_schema("trend_snapshot.schema.json")
    series_schema = schema["properties"]["series"]
    region_schema = schema["properties"]["region_breakdown"]

    # Create dummy DataFrame to mock pandas.DataFrame
    class DummyDataFrame:
        def __init__(self, data, index):
            self.data = data
            self.index = index
            self.columns = list(data.keys())
            self.empty = False
            
        def iterrows(self):
            for i, idx in enumerate(self.index):
                row = {k: self.data[k][i] for k in self.columns}
                yield idx, row

    class DummyIndex:
        def __init__(self, val):
            self.val = val
        def strftime(self, fmt):
            return self.val
        def __str__(self):
            return self.val

    # Mock pandas module
    mock_pd = MagicMock()
    mock_pd.isna = lambda x: x is None
    monkeypatch.setitem(sys.modules, "pandas", mock_pd)

    # Mock trendspy module
    mock_trendspy = MagicMock()
    mock_trends_instance = MagicMock()
    mock_trendspy.Trends.return_value = mock_trends_instance
    monkeypatch.setitem(sys.modules, "trendspy", mock_trendspy)

    provider = get_provider("trendspy")

    # Setup mock for interest_over_time
    mock_trends_instance.interest_over_time.return_value = DummyDataFrame(
        {"sneakers": [10.5, 20.0]},
        [DummyIndex("2023-01-01"), DummyIndex("2023-01-02")]
    )
    
    series_res = provider.interest_over_time(["sneakers"])
    assert "sneakers" in series_res
    assert len(series_res["sneakers"]) == 2
    jsonschema.validate(instance=series_res["sneakers"], schema=series_schema)

    # Setup mock for interest_by_region
    mock_trends_instance.interest_by_region.return_value = DummyDataFrame(
        {"sneakers": [50.0, 60.0]},
        [DummyIndex("Madrid"), DummyIndex("Barcelona")]
    )

    region_res = provider.interest_by_region("sneakers")
    assert len(region_res) == 2
    jsonschema.validate(instance=region_res, schema=region_schema)

def test_trendspy_provider_backoff_retries_on_429(monkeypatch):
    provider = get_provider("trendspy")
    
    # Mock time.sleep to not actually sleep during test
    monkeypatch.setattr("time.sleep", lambda x: None)

    # Create dummy DataFrame to mock pandas.DataFrame
    class DummyDataFrame:
        def __init__(self, data, index):
            self.data = data
            self.index = index
            self.columns = list(data.keys())
            self.empty = False
            
        def iterrows(self):
            for i, idx in enumerate(self.index):
                row = {k: self.data[k][i] for k in self.columns}
                yield idx, row
                
    class DummyIndex:
        def __init__(self, val):
            self.val = val
        def strftime(self, fmt):
            return self.val
        def __str__(self):
            return self.val

    # Mock pandas module
    mock_pd = MagicMock()
    mock_pd.isna = lambda x: x is None
    monkeypatch.setitem(sys.modules, "pandas", mock_pd)

    # Mock trendspy module
    mock_trendspy = MagicMock()
    mock_trends_instance = MagicMock()
    mock_trendspy.Trends.return_value = mock_trends_instance
    monkeypatch.setitem(sys.modules, "trendspy", mock_trendspy)

    call_count = 0

    class MockResponse:
        status_code = 429

    class MockException(Exception):
        response = MockResponse()

    # The mocked method to throw 429 then succeed
    def mock_interest_over_time(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise MockException("429 Too Many Requests")
        
        return DummyDataFrame(
            {"sneakers": [10.0]},
            [DummyIndex("2023-01-01")]
        )

    mock_trends_instance.interest_over_time.side_effect = mock_interest_over_time

    series_res = provider.interest_over_time(["sneakers"])
    assert "sneakers" in series_res
    assert len(series_res["sneakers"]) == 1
    assert call_count == 3

def test_get_provider_factory():
    assert isinstance(get_provider("trendspy"), TrendspyProvider)
    assert isinstance(get_provider("fixture"), FixtureProvider)
    
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("invalid")


# ---------------------------------------------------------------------------
# Batching. Google compares at most five terms per request (verified live
# 2026-08-03: six -> 400 Bad Request). The universe is ~49 terms, so the
# provider must split the request AND put the pieces back on one scale.
# ---------------------------------------------------------------------------

from ingest.trends_client import (  # noqa: E402
    _batch_keywords,
    _rescale_to_anchor,
)


def test_batches_never_exceed_the_google_cap():
    kws = [f"kw{i}" for i in range(49)]
    batches = _batch_keywords(kws, anchor=kws[0])

    assert batches, "49 keywords must produce at least one batch"
    for b in batches:
        # The literal 5 is deliberate. Asserting against
        # MAX_KEYWORDS_PER_REQUEST would only prove the code agrees with
        # itself: raising the constant to 50 leaves such a test green while
        # every live request goes back to 400. 5 is Google's number, not
        # ours, so the test states Google's number.
        assert len(b) <= 5, b
        assert b[0] == kws[0], "every batch carries the anchor first"

    # Every non-anchor keyword appears exactly once across all batches.
    seen = [k for b in batches for k in b[1:]]
    assert sorted(seen) == sorted(kws[1:])
    assert len(seen) == len(set(seen))


def test_batching_is_deterministic():
    kws = [f"kw{i}" for i in range(13)]
    assert _batch_keywords(kws, kws[0]) == _batch_keywords(kws, kws[0])


def test_rescale_puts_a_batch_on_the_reference_scale():
    # This batch's anchor averages 25; the reference batch's anchor averaged
    # 50. Everything in this batch is therefore reading half-scale and must
    # be doubled.
    batch = {
        "anchor": [{"date": "2026-01-01", "value": 20.0},
                   {"date": "2026-01-08", "value": 30.0}],
        "cerveza": [{"date": "2026-01-01", "value": 10.0},
                    {"date": "2026-01-08", "value": 40.0}],
    }
    out = _rescale_to_anchor(batch, anchor="anchor", reference_mean=50.0)

    assert "anchor" not in out, "the anchor is carried, not reported"
    assert [p["value"] for p in out["cerveza"]] == [20.0, 80.0]


def test_a_batch_whose_anchor_reads_zero_is_dropped_not_guessed():
    # No anchor signal means no scale factor. Emitting these values anyway
    # would be publishing a number on an unknown scale.
    batch = {
        "anchor": [{"date": "2026-01-01", "value": 0.0}],
        "cerveza": [{"date": "2026-01-01", "value": 90.0}],
    }
    assert _rescale_to_anchor(batch, anchor="anchor", reference_mean=50.0) == {}


def test_provider_splits_a_large_universe_into_capped_requests(monkeypatch):
    """The regression guard for the bug that killed the first live run."""
    monkeypatch.setattr("time.sleep", lambda x: None)

    class DummyIndex:
        def __init__(self, val):
            self.val = val

        def strftime(self, fmt):
            return self.val

    class DummyDataFrame:
        def __init__(self, data, index):
            self.data = data
            self.index = index
            self.columns = list(data.keys())
            self.empty = False

        def iterrows(self):
            for i, idx in enumerate(self.index):
                yield idx, {k: self.data[k][i] for k in self.columns}

    mock_pd = MagicMock()
    mock_pd.isna = lambda x: x is None
    monkeypatch.setitem(sys.modules, "pandas", mock_pd)

    seen_request_sizes = []

    def fake_iot(keywords, geo, timeframe):
        seen_request_sizes.append(len(keywords))
        # Flat 50 everywhere: same scale in every batch, so the rescale
        # factor is 1 and the assertions below stay about batching.
        return DummyDataFrame(
            {k: [50.0] for k in keywords}, [DummyIndex("2026-01-01")]
        )

    mock_trendspy = MagicMock()
    mock_instance = MagicMock()
    mock_instance.interest_over_time.side_effect = fake_iot
    mock_trendspy.Trends.return_value = mock_instance
    monkeypatch.setitem(sys.modules, "trendspy", mock_trendspy)

    universe = [f"kw{i}" for i in range(49)]
    out = TrendspyProvider().interest_over_time(universe, geo="ES-MD", timeframe="today 3-m")

    assert seen_request_sizes, "provider made no request at all"
    # Literals again, for the same reason as above: 5 terms per request is
    # Google's limit, 4 real slots is what is left once the anchor takes
    # one, and 48 non-anchor keywords therefore need 12 requests.
    assert max(seen_request_sizes) <= 5, seen_request_sizes
    assert len(seen_request_sizes) == 12

    assert set(out) == set(universe), "every requested keyword must be answered"
    assert all(out[k] for k in universe), "flat-50 input should yield a series for each"
