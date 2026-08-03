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
