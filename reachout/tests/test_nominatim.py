import requests

import nominatim


def test_geocode_offline_uses_gazetteer(monkeypatch, tmp_path):
    monkeypatch.setattr(nominatim, "CACHE_PATH", str(tmp_path / "geocode_cache.json"))

    result = nominatim.geocode("Malasaña", offline=True)

    assert result == {"lat": 40.4267, "lng": -3.7038, "source": "gazetteer"}


def test_geocode_offline_is_accent_and_case_insensitive(monkeypatch, tmp_path):
    monkeypatch.setattr(nominatim, "CACHE_PATH", str(tmp_path / "geocode_cache.json"))

    result = nominatim.geocode("LAVAPIES", offline=True)

    assert result == {"lat": 40.4088, "lng": -3.7005, "source": "gazetteer"}


def test_geocode_offline_unknown_place_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(nominatim, "CACHE_PATH", str(tmp_path / "geocode_cache.json"))

    assert nominatim.geocode("Nowhereville", offline=True) is None


def test_geocode_live_success_is_cached(monkeypatch, tmp_path):
    cache_path = str(tmp_path / "geocode_cache.json")
    monkeypatch.setattr(nominatim, "CACHE_PATH", cache_path)
    monkeypatch.setattr(nominatim, "_rate_limit", lambda: None)

    class FakeResponse:
        status_code = 200

        def json(self):
            return [{"lat": "40.4267", "lon": "-3.7038"}]

    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params)
        assert "User-Agent" in headers
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    first = nominatim.geocode("Malasaña", offline=False)
    assert first == {"lat": 40.4267, "lng": -3.7038, "source": "nominatim_live"}
    assert len(calls) == 1

    # second call hits the cache, no further network call
    second = nominatim.geocode("Malasaña", offline=False)
    assert second["source"] == "geocode_cache"
    assert len(calls) == 1


def test_geocode_live_failure_falls_back_to_gazetteer(monkeypatch, tmp_path):
    monkeypatch.setattr(nominatim, "CACHE_PATH", str(tmp_path / "geocode_cache.json"))
    monkeypatch.setattr(nominatim, "_rate_limit", lambda: None)

    def fake_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(requests, "get", fake_get)

    result = nominatim.geocode("Chueca", offline=False)

    assert result == {"lat": 40.4223, "lng": -3.6973, "source": "gazetteer"}
