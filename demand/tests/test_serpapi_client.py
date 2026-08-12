import httpx
import pytest

import demand.ingest.serpapi_client as sc
from demand.ingest.serpapi_client import (
    SerpApiError,
    SerpApiHTTPError,
    build_params,
    fetch,
    raise_for_api_error,
)

#: Stands in for the real 64-character key. Nothing in an exception, a
#: traceback, or a log line may ever contain this string.
FAKE_KEY = "sk-not-a-real-key-0123456789abcdef"


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


# ---------------------------------------------------------------------------
# The API key is a query PARAMETER, so any exception carrying the request URL
# prints it verbatim. `httpx.HTTPStatusError` does exactly that, and nothing
# up the stack catches it -- a 401 (rotated key) or a 429 (the *expected*
# end-state of a 250/month budget) would have dumped the live key onto stdout,
# into CI logs, and into the APScheduler server log.
# ---------------------------------------------------------------------------

def _response(status: int, params: dict) -> httpx.Response:
    request = httpx.Request("GET", sc.SERPAPI_ENDPOINT, params=params)
    return httpx.Response(status, request=request, json={})


def _params():
    return build_params(q=["café"], data_type="TIMESERIES", geo="ES-MD",
                        date="today 3-m", api_key=FAKE_KEY)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 502])
def test_fetch_never_puts_the_api_key_in_the_error(monkeypatch, status):
    params = _params()
    monkeypatch.setattr(sc.httpx, "get",
                        lambda *a, **k: _response(status, params))

    with pytest.raises(SerpApiHTTPError) as excinfo:
        fetch(params)

    assert FAKE_KEY not in str(excinfo.value)
    assert FAKE_KEY not in repr(excinfo.value)
    # And no chained cause dragging the URL back in through `__context__`.
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None
    assert str(status) in str(excinfo.value)


def test_fetch_exposes_the_status_code_for_callers_to_branch_on(monkeypatch):
    params = _params()
    monkeypatch.setattr(sc.httpx, "get", lambda *a, **k: _response(429, params))

    with pytest.raises(SerpApiHTTPError) as excinfo:
        fetch(params)
    assert excinfo.value.status_code == 429


def test_fetch_never_leaks_the_key_from_a_transport_failure(monkeypatch):
    """A connect/timeout error also carries the `Request`, hence the URL."""
    params = _params()
    request = httpx.Request("GET", sc.SERPAPI_ENDPOINT, params=params)

    def boom(*a, **k):
        raise httpx.ConnectTimeout(
            f"timed out talking to {request.url}", request=request)

    monkeypatch.setattr(sc.httpx, "get", boom)

    with pytest.raises(SerpApiHTTPError) as excinfo:
        fetch(params)
    assert FAKE_KEY not in str(excinfo.value)
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None


def test_an_http_failure_is_not_mistaken_for_an_empty_result(monkeypatch):
    """`SerpApiHTTPError` must NOT be a `SerpApiError`.

    `SerpApiProvider.rising_queries` catches `SerpApiError` and returns `[]`,
    because a sparse Shopping result is data, not a failure. Folding transport
    failures into that same class would turn a 429 "budget exhausted" into a
    silent "this parent had no rising queries" -- a wrong answer written to the
    database with no error anywhere.
    """
    assert not issubclass(SerpApiHTTPError, SerpApiError)

    params = _params()
    monkeypatch.setattr(sc.httpx, "get", lambda *a, **k: _response(429, params))
    with pytest.raises(SerpApiHTTPError):
        fetch(params)


def test_fetch_returns_the_payload_on_success(monkeypatch):
    params = _params()
    request = httpx.Request("GET", sc.SERPAPI_ENDPOINT, params=params)
    monkeypatch.setattr(
        sc.httpx, "get",
        lambda *a, **k: httpx.Response(200, request=request,
                                       json={"interest_over_time": {}}))
    assert fetch(params) == {"interest_over_time": {}}


# ---------------------------------------------------------------------------
# HTTP 200 carrying something that is not JSON.
#
# A SerpApi maintenance page, a corporate proxy interstitial, a captive-portal
# login form: all of them answer 200 with HTML. `httpx.Response.json()` is
# `json.loads(self.content)`, so that raises `json.JSONDecodeError`, a
# `ValueError` -- a class nothing in the ingest chain catches. It threw out of
# `_fetch_batch` (which named two SerpApi types), out of `interest_over_time`,
# and out of `run_chain` before `store_snapshots` was ever reached: the same
# "9 billed searches produce zero rows" failure the batch loop exists to
# prevent, arriving through a door the batch loop did not cover.
# ---------------------------------------------------------------------------


def _html_response(params: dict, status: int = 200) -> httpx.Response:
    request = httpx.Request("GET", sc.SERPAPI_ENDPOINT, params=params)
    return httpx.Response(status, request=request,
                          text="<html><body>We are down for maintenance"
                               "</body></html>")


def test_a_200_with_a_non_json_body_raises_a_serpapi_error_not_a_value_error(
        monkeypatch):
    params = _params()
    monkeypatch.setattr(sc.httpx, "get", lambda *a, **k: _html_response(params))

    with pytest.raises(SerpApiHTTPError) as excinfo:
        fetch(params)

    assert excinfo.value.status_code == 200
    assert FAKE_KEY not in str(excinfo.value)
    assert FAKE_KEY not in repr(excinfo.value)
    # Same discipline as every other exit from `fetch`: raised with no
    # exception in flight, so nothing is hanging off the chain.
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None
    # `json.JSONDecodeError` puts a slice of the response body in its message.
    # That slice cannot leak the key (it is the body, not the request URL) but
    # it is unbounded text from the network and it tells the operator nothing
    # that "not JSON" does not already say.
    assert "maintenance" not in str(excinfo.value)
    assert "html" not in str(excinfo.value).lower()


def test_a_non_json_body_is_not_mistaken_for_an_empty_result():
    """It must not be a `SerpApiError`.

    `SerpApiProvider.rising_queries` catches `SerpApiError` and returns `[]`
    because a sparse Shopping panel is data. An HTML error page is not an
    empty result, and writing it down as one is a wrong answer with no error
    anywhere. Being a `SerpApiHTTPError` instead also means `run_chain`'s
    discovery guard already handles it: one parent lost, run continues.
    """
    assert issubclass(sc.SerpApiMalformedResponseError, SerpApiHTTPError)
    assert not issubclass(sc.SerpApiMalformedResponseError, SerpApiError)


def test_a_non_2xx_html_body_still_reports_its_real_status(monkeypatch):
    """A 502 from a gateway is usually an HTML page too.

    The status check runs first, so this stays a plain `SerpApiHTTPError(502)`
    and keeps its place in `RETRYABLE_STATUS` -- it must not be reclassified
    as a malformed body and lose its retry.
    """
    params = _params()
    monkeypatch.setattr(sc.httpx, "get",
                        lambda *a, **k: _html_response(params, status=502))

    with pytest.raises(SerpApiHTTPError) as excinfo:
        fetch(params)
    assert excinfo.value.status_code == 502
    assert not isinstance(excinfo.value, sc.SerpApiMalformedResponseError)
