import json
import os

import pytest
import requests

import overpass

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def test_build_query_includes_every_category_selector():
    query = overpass.build_query(area_name="Madrid")

    assert 'area["name"="Madrid"]' in query
    assert 'node["amenity"="pharmacy"]' in query
    assert 'way["shop"="hardware"]' in query
    assert 'relation["shop"="electronics"]' in query
    assert "out center tags;" in query


def test_fetch_shops_returns_elements_on_success(monkeypatch):
    fixture = _load_fixture("overpass_response.json")

    class FakeResponse:
        status_code = 200

        def json(self):
            return fixture

    def fake_post(url, data=None, headers=None, timeout=None):
        assert "User-Agent" in headers
        assert timeout is not None
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    elements = overpass.fetch_shops(area_name="Madrid")

    assert elements == fixture["elements"]


def test_fetch_shops_raises_overpass_error_on_network_failure(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(overpass.OverpassError):
        overpass.fetch_shops(area_name="Madrid")


def test_fetch_shops_raises_overpass_error_on_bad_status(monkeypatch):
    class FakeResponse:
        status_code = 504

        def json(self):
            return {}

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(overpass.OverpassError):
        overpass.fetch_shops(area_name="Madrid")
