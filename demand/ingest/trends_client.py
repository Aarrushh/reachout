import json
import os
import re
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

#: What a QUANTIFIED growth label looks like, in any locale: an optional
#: sign, digits with any mix of `.` `,` and spacing separators, a `%`.
#: Matches "+150%", "+4,200%" (en), "+4.200 %" (es), "+1 500 %" (fr,
#: non-breaking spaces).
#:
#: At least one DIGIT is required. Without that, a stray label like " %"
#: parses as quantified and the `extracted_value` beside it gets published
#: as growth -- the exact fabrication this guard exists to stop.
#:
#: This is the guard, and it is deliberately inverted: a row is treated as a
#: refusal UNLESS its label parses as a percentage. Matching the English word
#: "Breakout" instead -- which is what this replaced -- is correct only while
#: `hl="en"` reaches the parser, and nothing structural guarantees that.
#: `SerpApiProvider.rising_queries` pins `hl="en"` and a test pins the pin,
#: but `parse_rising_queries` is public: `FixtureProvider` runs it over
#: whatever JSON is on disk, `serpapi_client.build_params` still defaults to
#: `hl="es"`, and a re-capture or a Google label change routes around the pin
#: entirely. At `hl="es"` the same rows read "Aumento puntual", the equality
#: check misses, and the `extracted_value` sitting next to it -- 91000 in the
#: committed capture -- is published as a growth percentage Google explicitly
#: refused to give.
#:
#: Failing towards "refusal" is the safe direction. An unrecognised label
#: costs a growth number on the dashboard; a mis-read one fabricates it.
QUANTIFIED_GROWTH = re.compile(r"^[+-]?[\d.,\s\xa0\u202f]*\d[\d.,\s\xa0\u202f]*%$")


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
        #
        # Inverted on purpose: a row counts as a refusal unless its label
        # parses as a quantified percentage, in whatever language it arrives.
        # See QUANTIFIED_GROWTH for why equality on one English word was not
        # safe enough.
        label = str(item.get("value", "")).strip()
        is_breakout = QUANTIFIED_GROWTH.match(label) is None
        extracted = item.get("extracted_value")
        growth = None if (is_breakout or extracted is None) else float(extracted)
        rows.append({"query": query, "growth_pct": growth,
                     "is_breakout": is_breakout})

    return rows


def pick_anchor(signals: List[Dict[str, Any]], keywords: List[str]) -> str:
    """Choose the batch anchor by MEASURED volume, not by alphabet.

    Every batch carries the anchor so the batches can be rescaled onto a
    common level, which makes the anchor the one slot the entire cross-batch
    comparability depends on. Taking `keywords[0]` made that an alphabetical
    accident: `build_universe` sorts, so the anchor was `abanico` -- measured
    mean 11.16 in ES-MD over 3 months. Google renormalises every request so
    its own peak term is 100 and rounds to integers, so batching `abanico`
    against `cafe`, `cerveza` or `pan` rounds `abanico` to 0 across the whole
    window, `anchor_mean` is 0, and `_rescale_to_anchor` correctly refuses to
    scale -- dropping that batch's four keywords for one paid search.

    A high-volume anchor is far less likely to round to zero next to anything
    else. `signals` is the PREVIOUS run's `demand_signals`; the newest window
    wins, `interest_avg` ranks, and `keyword` breaks ties so two runs over the
    same signals pick the same anchor.

    Cold start (no signals, or none of them still in the universe) falls back
    to `keywords[0]`, which is the old alphabetical behaviour.
    """
    if not keywords:
        return ""

    universe = set(keywords)
    usable = [s for s in signals or []
              if s.get("keyword") in universe
              and s.get("interest_avg") is not None]
    if not usable:
        return keywords[0]

    latest = max(s.get("window_start", "") for s in usable)
    newest = [s for s in usable if s.get("window_start", "") == latest]
    best = sorted(newest,
                  key=lambda s: (-float(s["interest_avg"]), s["keyword"]))[0]
    return best["keyword"]


class TrendsProvider(Protocol):
    def interest_over_time(self, keywords: List[str], geo: str,
                           timeframe: str,
                           anchor: str = "",
                           ) -> Dict[str, List[Dict[str, Any]]]:
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
                            anchor: str = "",
                            ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch the whole universe five terms at a time, anchor-rescaled.

        The batching and rescaling are the EXISTING trendspy-era helpers, reused
        unchanged. SerpApi is a proxy: Google still re-normalises every request
        to 0-100 independently, so two batches remain incomparable without a
        shared anchor. Swapping the transport did not remove that problem.
        """
        if not keywords:
            return {}

        # `anchor` is chosen by measured volume upstream (see `pick_anchor`).
        # Falling back to `keywords[0]` keeps the old alphabetical behaviour
        # for callers that pass nothing.
        if anchor not in keywords:
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
            if not rescaled:
                # `_rescale_to_anchor` returns {} when the anchor reads zero in
                # this batch -- correct, per the honesty rule, but silent: these
                # keywords keep the [] they were initialised with and get stored
                # as snapshots with an empty series. One paid search, no data.
                # Say so, or it is indistinguishable from Google having nothing.
                dropped = [k for k in batch if k != anchor]
                print(f"[Ingest] batch {i} dropped -- anchor {anchor!r} read "
                      f"zero here; {len(dropped)} keywords have no series this "
                      f"run: {', '.join(dropped)}")
                continue
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


class FixtureProvider:
    def __init__(self, fixtures_dir: str = None):
        if fixtures_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            fixtures_dir = os.path.join(base_dir, "tests", "fixtures", "trends")
        self.fixtures_dir = fixtures_dir

    def interest_over_time(self, keywords: List[str], geo: str,
                            timeframe: str,
                            anchor: str = "",
                            ) -> Dict[str, List[Dict[str, Any]]]:
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
    if name == "serpapi":
        import os

        api_key = os.environ.get("SERPAPI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "SERPAPI_API_KEY is not set. Add it to reachout/.env. "
                "Run with `--provider fixture` to work offline."
            )
        return SerpApiProvider(api_key=api_key)
    if name == "fixture":
        return FixtureProvider()
    raise ValueError(f"Unknown provider: {name}")
