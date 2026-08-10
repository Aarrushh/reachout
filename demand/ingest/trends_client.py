import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Protocol

from demand.ingest.serpapi_client import (
    SerpApiError, build_params, fetch,
)

#: Google's literal answer when growth exceeds roughly 5000%. It is a refusal
#: to quantify, not a large number, and is stored as one.
#:
#: This token is LOCALIZED by the `hl` parameter -- the Task 1 probe measured
#: `hl=es` returning "Aumento puntual" for the same rows `hl=en` returns
#: "Breakout" for. Discovery therefore pins `hl="en"` (see Task 4), so this
#: constant stays one English string instead of tracking Google's translations.
#: The `query` values are unaffected: those are real user searches and come
#: back in Spanish either way.
BREAKOUT_TOKEN = "Breakout"


def parse_rising_queries(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One RELATED_QUERIES payload -> rising rows.

    Only the `rising` list is read. `top` ranks all-time popularity, which
    would put steady bestsellers into a panel whose entire claim is that these
    products are NEW demand.
    """
    rows: List[Dict[str, Any]] = []
    rising = payload.get("related_queries", {}).get("rising", []) or []

    for item in rising:
        query = item.get("query")
        if not query:
            continue
        # `extracted_value` is populated even on Breakout rows -- the probe
        # measured 89800 and 91000 sitting behind the refusal. That number is
        # Google's internal scale artifact, not a growth percentage anyone can
        # defend to a shopkeeper, so `is_breakout` wins over it here.
        is_breakout = str(item.get("value", "")).strip() == BREAKOUT_TOKEN
        extracted = item.get("extracted_value")
        growth = None if (is_breakout or extracted is None) else float(extracted)
        rows.append({"query": query, "growth_pct": growth,
                     "is_breakout": is_breakout})

    return rows


class TrendsProvider(Protocol):
    def interest_over_time(self, keywords: List[str], geo: str, timeframe: str) -> Dict[str, List[Dict[str, Any]]]:
        ...

    def interest_by_region(self, keyword: str, geo: str) -> List[Dict[str, Any]]:
        ...

    def rising_queries(self, keyword: str, geo: str, date: str,
                       gprop: str) -> List[Dict[str, Any]]:
        ...


#: SerpApi echoes Google's display date ("Jul 6 - Jul 12, 2026"), which is
#: locale-shaped and ambiguous to parse. The `timestamp` epoch seconds is
#: not, so the ISO date is derived from it and the display string is ignored.
def _iso_date(entry: Dict[str, Any]) -> str:
    ts = entry.get("timestamp")
    if ts is None:
        return ""
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def parse_timeseries(payload: Dict[str, Any],
                      keywords: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """One SerpApi TIMESERIES payload -> the provider's contract.

    Returns an entry for EVERY requested keyword. A keyword Google returned
    nothing for gets an empty list, never a missing key -- callers downstream
    index by keyword and a KeyError there would look like a data bug.
    """
    result: Dict[str, List[Dict[str, Any]]] = {k: [] for k in keywords}
    timeline = payload.get("interest_over_time", {}).get("timeline_data", [])

    for entry in timeline:
        date = _iso_date(entry)
        if not date:
            continue
        values = entry.get("values", [])
        for slot, value in enumerate(values):
            # Single-query responses omit `query`; fall back to position.
            keyword = value.get("query")
            if keyword is None and slot < len(keywords):
                keyword = keywords[slot]
            if keyword not in result:
                continue
            extracted = value.get("extracted_value")
            if extracted is None:
                continue
            result[keyword].append({"date": date, "value": float(extracted)})

    return result


class SerpApiProvider:
    """Live provider. Every method call here spends budget -- see BUDGET.md."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def interest_over_time(self, keywords: List[str], geo: str = "ES-MD",
                            timeframe: str = "today 3-m",
                            ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch the whole universe five terms at a time, anchor-rescaled.

        The batching and rescaling are the EXISTING trendspy-era helpers, reused
        unchanged. SerpApi is a proxy: Google still re-normalises every request
        to 0-100 independently, so two batches remain incomparable without a
        shared anchor. Swapping the transport did not remove that problem.
        """
        if not keywords:
            return {}

        anchor = keywords[0]
        batches = _batch_keywords(keywords, anchor)
        result: Dict[str, List[Dict[str, Any]]] = {k: [] for k in keywords}
        reference_mean = 0.0

        for i, batch in enumerate(batches):
            payload = fetch(build_params(
                q=batch, data_type="TIMESERIES", geo=geo,
                date=timeframe, api_key=self.api_key,
            ))
            batch_series = parse_timeseries(payload, batch)

            anchor_points = batch_series.get(anchor, [])
            if i == 0:
                reference_mean = (
                    sum(p["value"] for p in anchor_points) / len(anchor_points)
                    if anchor_points else 0.0
                )
                for kw, points in batch_series.items():
                    if kw in result:
                        result[kw] = points
                continue

            rescaled = _rescale_to_anchor(batch_series, anchor, reference_mean)
            for kw, points in rescaled.items():
                if kw in result:
                    result[kw] = points

        return result

    def interest_by_region(self, keyword: str,
                            geo: str = "ES-MD") -> List[Dict[str, Any]]:
        """Deliberately empty. GEO_MAP_0 costs one search per keyword to answer
        a question the analytics schema already rules out: Google Trends does
        not resolve below ES-MD, so there is no barrio breakdown to buy."""
        return []

    def rising_queries(self, keyword: str, geo: str = "ES-MD",
                       date: str = "today 1-m",
                       gprop: str = "") -> List[Dict[str, Any]]:
        """One search. RELATED_QUERIES takes exactly one query -- no batching
        is possible here, which is why discovery is capped at the top movers
        rather than run across the whole universe.

        `hl="en"` is not cosmetic: Google localizes the Breakout label, and
        `parse_rising_queries` decides `is_breakout` by matching it. At the
        Spanish locale that match fails and a refusal to quantify is stored as
        a quantified 89800% instead.
        """
        try:
            payload = fetch(build_params(
                q=[keyword], data_type="RELATED_QUERIES", geo=geo,
                date=date, api_key=self.api_key, gprop=gprop or None,
                hl="en",
            ))
        except SerpApiError:
            # Google returns its `error` field rather than an empty list when a
            # term has no rising queries in the window. No data is a normal
            # answer, not a failed run.
            return []
        return parse_rising_queries(payload)


def retry_on_429(max_retries: int = 3, base_delay: int = 1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    is_429 = False
                    if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
                        is_429 = True
                    elif '429' in str(e):
                        is_429 = True
                    
                    if is_429 and retries < max_retries:
                        delay = base_delay * (2 ** retries)
                        time.sleep(delay)
                        retries += 1
                    else:
                        raise e
        return wrapper
    return decorator

def _load_trendspy():
    """Import the live-scrape dependencies, or fail with the fix in the message.

    Imported here rather than at module scope on purpose: `FixtureProvider`
    below, and every test in the suite, must keep working on a machine that
    has neither package — which is the normal state of a Jules VM. So the
    cost of a missing dep is paid only by the one caller that actually
    scrapes.

    What this replaces: a bare `ImportError` raised from inside a retry
    wrapper, several frames deep, on the single command V1 depends on — and
    raised *after* `run_ingest.run_chain` has already built the keyword
    universe out of the database, so the failure looked like it came from
    the ingest chain rather than from an uninstalled package.
    """
    try:
        import pandas as pd
        import trendspy
    except ImportError as exc:
        raise ImportError(
            f"--provider trendspy needs the live-scrape dependencies ({exc.name} "
            "is missing). Install them with `pip install -r demand/requirements.txt`, "
            "or re-run with `--provider fixture` to use the committed captures in "
            "demand/tests/fixtures/trends/ instead."
        ) from exc
    return pd, trendspy


#: Google Trends compares at most five terms in one request. Verified live
#: on 2026-08-03: six terms returns `400 Bad Request` from
#: trends.google.com/trends/embed/explore/TIMESERIES, five does not. The
#: keyword universe is ~49 terms, so a single request was never going to
#: work — the first live run died here, and no test caught it because every
#: test drives a mocked client that accepts any number of terms.
MAX_KEYWORDS_PER_REQUEST = 5

#: One slot in every batch is spent on the anchor term, so each batch can
#: carry this many real keywords. See `_rescale_to_anchor` for why the slot
#: is worth it.
KEYWORDS_PER_BATCH = MAX_KEYWORDS_PER_REQUEST - 1

#: Seconds between batches, on top of trendspy's own `request_delay`. Google
#: throttled this project's IP within ~10 requests on 2026-08-03.
BATCH_DELAY_SECONDS = 2.0


def _batch_keywords(keywords: List[str], anchor: str) -> List[List[str]]:
    """Split `keywords` into request-sized batches, each carrying `anchor`.

    Deterministic: same input list, same batches, every time. The anchor is
    never counted as one of the batch's real keywords, and the batch that
    the anchor naturally belongs to does not carry it twice.
    """
    real = [k for k in keywords if k != anchor]
    batches = []
    for i in range(0, len(real), KEYWORDS_PER_BATCH):
        chunk = real[i:i + KEYWORDS_PER_BATCH]
        batches.append([anchor] + chunk)
    return batches or [[anchor]]


def _rescale_to_anchor(
    batch_series: Dict[str, List[Dict[str, Any]]],
    anchor: str,
    reference_mean: float,
) -> Dict[str, List[Dict[str, Any]]]:
    """Put one batch's values on the reference batch's scale.

    Google re-normalises every request independently: whatever term peaks
    inside THAT request becomes 100. So a value of 80 in one batch and 80 in
    another are not the same amount of interest, and ranking them against
    each other — which `compute_signals` does, across the whole universe —
    would be comparing two different scales and calling the result a rank.

    The fix is the standard one: carry a shared anchor term in every batch,
    and multiply each batch by whatever factor puts its anchor back on the
    reference batch's anchor level.

    When the anchor reads zero for a whole batch there is no factor to
    compute. That batch's keywords are then genuinely incomparable to the
    rest, so they are dropped rather than emitted on an unknown scale — a
    missing keyword is honest, a mis-scaled one is a fabricated number.
    """
    anchor_points = batch_series.get(anchor, [])
    anchor_mean = (
        sum(p["value"] for p in anchor_points) / len(anchor_points)
        if anchor_points else 0.0
    )
    if anchor_mean <= 0 or reference_mean <= 0:
        return {}

    factor = reference_mean / anchor_mean
    return {
        kw: [{"date": p["date"], "value": p["value"] * factor} for p in points]
        for kw, points in batch_series.items()
        if kw != anchor
    }


class TrendspyProvider:
    def interest_over_time(self, keywords: List[str], geo: str = "ES-MD", timeframe: str = "today 1-m") -> Dict[str, List[Dict[str, Any]]]:
        """Fetch a whole keyword universe, five terms at a time.

        Returns one entry per requested keyword. A keyword whose batch could
        not be put on a common scale is returned with an empty series, never
        with a value from an unreconciled scale.
        """
        if not keywords:
            return {}

        anchor = keywords[0]
        batches = _batch_keywords(keywords, anchor)

        result: Dict[str, List[Dict[str, Any]]] = {k: [] for k in keywords}
        reference_mean = 0.0

        for i, batch in enumerate(batches):
            if i > 0:
                time.sleep(BATCH_DELAY_SECONDS)
            batch_series = self._fetch_batch(batch, geo=geo, timeframe=timeframe)

            anchor_points = batch_series.get(anchor, [])
            if i == 0:
                reference_mean = (
                    sum(p["value"] for p in anchor_points) / len(anchor_points)
                    if anchor_points else 0.0
                )
                result[anchor] = anchor_points

            for kw, points in _rescale_to_anchor(batch_series, anchor, reference_mean).items():
                if kw in result:
                    result[kw] = points

        return result

    @retry_on_429()
    def _fetch_batch(self, keywords: List[str], geo: str, timeframe: str) -> Dict[str, List[Dict[str, Any]]]:
        """One request. At most `MAX_KEYWORDS_PER_REQUEST` terms."""
        pd, trendspy = _load_trendspy()

        client = trendspy.Trends(request_delay=BATCH_DELAY_SECONDS)
        df = client.interest_over_time(keywords, geo=geo, timeframe=timeframe)

        result = {}
        for keyword in keywords:
            result[keyword] = []
            if df is not None and not df.empty and keyword in df.columns:
                for idx, row in df.iterrows():
                    val = row[keyword]
                    if pd.isna(val):
                        continue
                    date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx).split(' ')[0]
                    result[keyword].append({
                        "date": date_str,
                        "value": float(val)
                    })
        return result

    @retry_on_429()
    def interest_by_region(self, keyword: str, geo: str = "ES-MD") -> List[Dict[str, Any]]:
        pd, trendspy = _load_trendspy()

        client = trendspy.Trends()
        df = client.interest_by_region([keyword], geo=geo)
        
        result = []
        if df is not None and not df.empty and keyword in df.columns:
            for idx, row in df.iterrows():
                val = row[keyword]
                if pd.isna(val):
                    continue
                result.append({
                    "region": str(idx),
                    "value": float(val)
                })
        return result

class FixtureProvider:
    def __init__(self, fixtures_dir: str = None):
        if fixtures_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            fixtures_dir = os.path.join(base_dir, "tests", "fixtures", "trends")
        self.fixtures_dir = fixtures_dir

    def interest_over_time(self, keywords: List[str], geo: str, timeframe: str) -> Dict[str, List[Dict[str, Any]]]:
        file_path = os.path.join(self.fixtures_dir, "interest_over_time.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {k: v for k, v in data.items() if k in keywords}
        except FileNotFoundError:
            return {k: [] for k in keywords}

    def interest_by_region(self, keyword: str, geo: str) -> List[Dict[str, Any]]:
        file_path = os.path.join(self.fixtures_dir, "interest_by_region.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(keyword, [])
        except FileNotFoundError:
            return []

    def rising_queries(self, keyword: str, geo: str = "ES-MD",
                       date: str = "today 1-m",
                       gprop: str = "") -> List[Dict[str, Any]]:
        """Replay a captured discovery response. Costs zero searches."""
        slug = keyword.replace(" ", "_")
        prop = gprop or "web"
        path = os.path.join(self.fixtures_dir, "captured",
                            f"related_queries_{prop}_{slug}.json")
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except FileNotFoundError:
            return []
        return parse_rising_queries(payload)

def get_provider(name: str) -> TrendsProvider:
    if name == "trendspy":
        return TrendspyProvider()
    elif name == "fixture":
        return FixtureProvider()
    else:
        raise ValueError(f"Unknown provider: {name}")
