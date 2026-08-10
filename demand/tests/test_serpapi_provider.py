import json
from pathlib import Path

import pytest

from demand.ingest.trends_client import parse_timeseries


def _payload():
    return {"interest_over_time": {"timeline_data": [
        {"date": "Jul 6 - Jul 12, 2026", "timestamp": "1783296000",
         "values": [{"query": "café", "value": "75", "extracted_value": 75},
                    {"query": "cerveza", "value": "40", "extracted_value": 40}]},
        {"date": "Jul 13 - Jul 19, 2026", "timestamp": "1783900800",
         "values": [{"query": "café", "value": "80", "extracted_value": 80},
                    {"query": "cerveza", "value": "0", "extracted_value": 0}]},
    ]}}


def test_parse_timeseries_returns_one_series_per_keyword():
    series = parse_timeseries(_payload(), ["café", "cerveza"])
    assert set(series) == {"café", "cerveza"}
    assert len(series["café"]) == 2


def test_parse_timeseries_converts_timestamp_to_iso_date():
    series = parse_timeseries(_payload(), ["café", "cerveza"])
    assert series["café"][0]["date"] == "2026-07-06"


def test_parse_timeseries_uses_extracted_value_as_float():
    series = parse_timeseries(_payload(), ["café", "cerveza"])
    assert series["café"][0]["value"] == 75.0
    assert isinstance(series["café"][0]["value"], float)


def test_parse_timeseries_keeps_zero_points():
    # A zero is a measurement. Dropping it would turn a flat week into a gap.
    series = parse_timeseries(_payload(), ["café", "cerveza"])
    assert series["cerveza"][1]["value"] == 0.0


def test_parse_timeseries_returns_empty_list_for_absent_keyword():
    series = parse_timeseries(_payload(), ["café", "cerveza", "chocolate"])
    assert series["chocolate"] == []


def test_parse_timeseries_handles_empty_payload():
    assert parse_timeseries({}, ["café"]) == {"café": []}


CAPTURE = (Path(__file__).resolve().parents[1]
           / "tests" / "fixtures" / "trends" / "captured"
           / "timeseries_web_5kw.json")


@pytest.mark.skipif(not CAPTURE.exists(), reason="probe not run yet")
def test_parse_timeseries_against_real_capture():
    payload = json.loads(CAPTURE.read_text(encoding="utf-8"))
    keywords = ["abanico", "agua mineral", "aspirinas", "bañador",
                "bebidas energéticas"]
    series = parse_timeseries(payload, keywords)

    assert set(series) == set(keywords)
    # today 3-m is ~13 weekly points. Assert a floor, not an exact count:
    # Google's window edges shift by run date and an exact assert would go red
    # for a reason that is not a defect.
    assert len(series[keywords[0]]) >= 8
    for points in series.values():
        for point in points:
            assert len(point["date"]) == 10
            assert isinstance(point["value"], float)


import demand.ingest.trends_client as tc
from demand.ingest.serpapi_client import SerpApiError
from demand.ingest.trends_client import SerpApiProvider


def test_rising_queries_sends_exactly_one_query(monkeypatch):
    # RELATED_QUERIES bills one search and accepts one term. Sending two does
    # not error usefully -- it answers for something you did not ask.
    seen = {}

    def fake_fetch(params, timeout=60.0):
        seen.update(params)
        return {"related_queries": {"rising": [
            {"query": "café soluble", "value": "+150%", "extracted_value": 150},
        ]}}

    monkeypatch.setattr(tc, "fetch", fake_fetch)
    rows = SerpApiProvider(api_key="KEY").rising_queries(
        "café", geo="ES-MD", date="today 1-m", gprop="froogle")

    assert seen["q"] == "café"
    assert seen["data_type"] == "RELATED_QUERIES"
    assert seen["gprop"] == "froogle"
    assert seen["date"] == "today 1-m"
    # Pinned to English so BREAKOUT_TOKEN stays one string. At hl=es the same
    # rows read "Aumento puntual" and every breakout would parse as quantified.
    assert seen["hl"] == "en"
    assert rows == [{"query": "café soluble", "growth_pct": 150.0,
                     "is_breakout": False}]


def test_rising_queries_treats_empty_result_as_data_not_failure(monkeypatch):
    # Sparse is the EXPECTED case for Shopping on a region-scoped Spanish term.
    # A run must not die because one of ten parents had nothing.
    def fake_fetch(params, timeout=60.0):
        raise SerpApiError("Google hasn't returned any results for this query.")

    monkeypatch.setattr(tc, "fetch", fake_fetch)
    assert SerpApiProvider(api_key="KEY").rising_queries("café") == []


def test_rising_queries_omits_gprop_when_falling_back_to_web(monkeypatch):
    seen = {}

    def fake_fetch(params, timeout=60.0):
        seen.update(params)
        return {"related_queries": {}}

    monkeypatch.setattr(tc, "fetch", fake_fetch)
    SerpApiProvider(api_key="KEY").rising_queries("café", gprop="")
    assert "gprop" not in seen
