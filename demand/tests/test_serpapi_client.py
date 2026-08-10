import pytest

from demand.ingest.serpapi_client import (
    SerpApiError,
    build_params,
    raise_for_api_error,
)


def test_build_params_joins_queries_with_commas():
    params = build_params(
        q=["café", "cerveza"],
        data_type="TIMESERIES",
        geo="ES-MD",
        date="today 3-m",
        api_key="KEY",
    )
    assert params["q"] == "café,cerveza"
    assert params["engine"] == "google_trends"
    assert params["data_type"] == "TIMESERIES"
    assert params["geo"] == "ES-MD"
    assert params["date"] == "today 3-m"
    assert params["api_key"] == "KEY"


def test_build_params_omits_gprop_when_web_search():
    params = build_params(
        q=["café"], data_type="TIMESERIES", geo="ES-MD",
        date="today 3-m", api_key="KEY",
    )
    assert "gprop" not in params


def test_build_params_includes_gprop_when_given():
    params = build_params(
        q=["café"], data_type="RELATED_QUERIES", geo="ES-MD",
        date="today 1-m", api_key="KEY", gprop="froogle",
    )
    assert params["gprop"] == "froogle"


def test_build_params_rejects_more_than_five_queries():
    with pytest.raises(ValueError, match="at most 5"):
        build_params(
            q=["a", "b", "c", "d", "e", "f"], data_type="TIMESERIES",
            geo="ES-MD", date="today 3-m", api_key="KEY",
        )


def test_build_params_rejects_multiple_queries_for_related_queries():
    with pytest.raises(ValueError, match="exactly 1"):
        build_params(
            q=["café", "cerveza"], data_type="RELATED_QUERIES",
            geo="ES-MD", date="today 1-m", api_key="KEY",
        )


def test_raise_for_api_error_raises_on_error_field():
    with pytest.raises(SerpApiError, match="Google hasn't returned any results"):
        raise_for_api_error({"error": "Google hasn't returned any results"})


def test_raise_for_api_error_passes_clean_payload():
    raise_for_api_error({"interest_over_time": {"timeline_data": []}})
