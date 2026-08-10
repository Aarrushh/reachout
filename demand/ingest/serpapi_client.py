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
    """SerpApi answered, but with a refusal rather than data."""


def build_params(
    q: List[str],
    data_type: str,
    geo: str,
    date: str,
    api_key: str,
    gprop: Optional[str] = None,
) -> Dict[str, str]:
    """Assemble one SerpApi query string. One call here == one billed search."""
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
        "hl": "es",
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
    """One live search. Costs exactly one unit of the monthly budget."""
    response = httpx.get(SERPAPI_ENDPOINT, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    raise_for_api_error(payload)
    return payload
