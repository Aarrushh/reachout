"""Transport for SerpApi's Google Trends engine. HTTP only, no domain logic.

Kept separate from trends_client.py on purpose: the parsers there are tested
against captured JSON with no HTTP in the picture at all, and this module is
tested for parameter construction with no network in the picture either.
"""

from typing import Any, Dict, List, Optional

import httpx

SERPAPI_ENDPOINT = "https://serpapi.com/search"

#: SerpApi caps `q` at 5 comma-separated terms, and only honours more than one
#: for TIMESERIES and GEO_MAP. RELATED_QUERIES / RELATED_TOPICS / GEO_MAP_0 take
#: exactly one. Sending two to RELATED_QUERIES does not error usefully -- it
#: silently answers for something you did not ask, which is worse.
MAX_QUERIES = 5
SINGLE_QUERY_TYPES = frozenset({"RELATED_QUERIES", "RELATED_TOPICS", "GEO_MAP_0"})


class SerpApiError(Exception):
    """SerpApi answered, but with a refusal rather than data.

    HTTP 200 with an `error` field. Callers treat this as *data*: an empty
    Shopping result for a region-scoped Spanish term is the expected case,
    not a failure (`SerpApiProvider.rising_queries`).
    """


class SerpApiHTTPError(Exception):
    """A non-2xx response, or no response at all.

    Deliberately NOT a subclass of `SerpApiError`. The callers that swallow
    `SerpApiError` mean "Google had nothing for this term"; a 429 means "the
    250/month budget is gone". Folding the second into the first would write
    "no rising queries" into the database and log nothing.

    Carries a status code and NOTHING ELSE. `httpx`'s own exceptions embed
    the request URL in their message, and SerpApi takes the API key as a
    query parameter -- so `raise_for_status()` printed the live key verbatim
    on every 401, 429 and 5xx. Constructing the message by hand, and raising
    `from None`, is what keeps the key out of the message, out of the
    `__cause__` chain, and out of the traceback.
    """

    def __init__(self, status_code: Optional[int] = None):
        self.status_code = status_code
        detail = f"HTTP {status_code}" if status_code is not None else "no response"
        super().__init__(f"SerpApi request failed ({detail})")


def build_params(
    q: List[str],
    data_type: str,
    geo: str,
    date: str,
    api_key: str,
    gprop: Optional[str] = None,
    hl: str = "es",
) -> Dict[str, str]:
    """Assemble one SerpApi query string. One call here == one billed search.

    `hl` selects the locale of Google's *display* strings, and is load-bearing
    for exactly one caller. Discovery passes `hl="en"` because Google localizes
    the "Breakout" label -- at `hl=es` the same rows come back as "Aumento
    puntual", and the parser that decides `is_breakout` by matching that token
    would store a refusal to quantify as a quantified 89800% instead.
    Measurement keeps the Spanish default: it reads only `timestamp` and
    `extracted_value`, neither of which is translated.
    """
    if not q:
        raise ValueError("q must hold at least one query")
    if data_type in SINGLE_QUERY_TYPES and len(q) != 1:
        raise ValueError(f"{data_type} accepts exactly 1 query, got {len(q)}")
    if len(q) > MAX_QUERIES:
        raise ValueError(f"SerpApi accepts at most 5 queries, got {len(q)}")

    params = {
        "engine": "google_trends",
        "q": ",".join(q),
        "data_type": data_type,
        "geo": geo,
        "date": date,
        "hl": hl,
        "api_key": api_key,
    }
    if gprop:
        params["gprop"] = gprop
    return params


def raise_for_api_error(payload: Dict[str, Any]) -> None:
    """SerpApi returns HTTP 200 with an `error` field for empty results."""
    if "error" in payload:
        raise SerpApiError(str(payload["error"]))


def fetch(params: Dict[str, str], timeout: float = 60.0) -> Dict[str, Any]:
    """One live search. Costs exactly one unit of the monthly budget.

    No `httpx` exception is allowed to escape this function. Every one of
    them carries the `Request`, the `Request` carries the full URL, and the
    URL carries `api_key=` -- so letting one propagate prints the live key
    into stdout, CI logs, and the APScheduler server log.

    Note the shape: the replacement is raised AFTER the `except` block has
    exited, never inside it. `raise ... from None` only sets
    `__suppress_context__`, which stops the *default* traceback printer from
    rendering the original -- the original object, URL and key included, is
    still hanging off `__context__` for any log formatter, error reporter or
    test harness that walks the chain itself. Raising with no exception in
    flight leaves `__context__` genuinely empty.
    """
    status: Optional[int] = None
    reached = False
    try:
        response = httpx.get(SERPAPI_ENDPOINT, params=params, timeout=timeout)
        reached = True
        status = response.status_code
    except httpx.HTTPError:
        pass

    if not reached:
        raise SerpApiHTTPError(None)
    if status is not None and status >= 400:
        raise SerpApiHTTPError(status)

    payload = response.json()
    raise_for_api_error(payload)
    return payload
