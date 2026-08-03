import json
import os
import time
from typing import Any, Dict, List, Protocol

class TrendsProvider(Protocol):
    def interest_over_time(self, keywords: List[str], geo: str, timeframe: str) -> Dict[str, List[Dict[str, Any]]]:
        ...

    def interest_by_region(self, keyword: str, geo: str) -> List[Dict[str, Any]]:
        ...

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

def get_provider(name: str) -> TrendsProvider:
    if name == "trendspy":
        return TrendspyProvider()
    elif name == "fixture":
        return FixtureProvider()
    else:
        raise ValueError(f"Unknown provider: {name}")
