# SerpApi Demand Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`.
> Steps use checkbox (`- [ ]`) syntax for tracking. One fresh subagent per task.

**Goal:** Replace the IP-throttled `trendspy` scraper with SerpApi as the demand
service's trends provider, and add a second ingest pass that discovers rising
product queries in Madrid — proven first by a 5-search probe against the live API
before the remaining budget is spent.

**Architecture:** The demand service already has a pluggable provider seam
(`TrendsProvider` Protocol + `get_provider()` + `--provider` flag). SerpApi drops
into that seam. Everything downstream of the provider — `compute_signals.py`,
`recommend.py`, `snapshot_store.py` — is untouched. One new table stores the
discovery pass. A probe task runs first and commits real captured responses, so
every parser task afterwards is written against real data, not guessed shapes.

**Tech Stack:** Python 3.12 (`.venv`), `httpx` (already a dependency), `supabase`
PostgREST client, `jsonschema`, `pytest`. SerpApi `engine=google_trends`.

---

## Scope

**In scope:** provider, ingest chain, storage, budget guard, dependency cleanup.

**OUT of scope — do not touch in this plan:** the analytics endpoint
(`/demand/api/analytics`), `analytics_response.schema.json`, the frontend, all
four dashboard panels. The discovery data lands in the database and stops there.
Serving it is a separate plan written after the probe shows what the data
actually looks like.

---

## Global Constraints

- **Budget: 250 SerpApi searches per month, recurring.** This plan spends **27**:
  5 in Task 1 (probe), 22 in Task 8 (first live run). The Task 8 idempotence
  re-run is free — SerpApi caches identical parameter sets for 1 hour.
- **1 request = 1 search**, regardless of how many comma-separated terms in `q`.
- **`q` accepts at most 5 comma-separated terms**, and only for `TIMESERIES` and
  `GEO_MAP`. `RELATED_QUERIES` accepts exactly **1** query per search.
- **Measurement window stays `today 3-m`.** Do not change `INGEST_TIMEFRAME`.
  `compute_signals.HIGH_MIN_WINDOWS = 8` weekly windows; `today 1-m` yields ~4 and
  makes the `high` confidence tier structurally unreachable. This is already
  documented at `demand/scripts/run_ingest.py:21`.
- **Discovery window is `today 1-m`**, a separate constant. It never enters
  `compute_signals`, so the window gate does not apply to it.
- **`geo = "ES-MD"`** everywhere. Google Trends does not resolve below ES-MD;
  no barrio-level data exists and none may be invented.
- **Never fabricate a number Google declined to give.** `value: "Breakout"` stores
  `growth_pct = NULL` and `is_breakout = true`. Never 5000, never max+1.
- **`demand/shared/schemas/` is DO NOT MODIFY** in this plan. No schema in that
  folder changes here.
- **Every test must pass with no API key present.** Jules VMs hold no keys. Only
  `probe_serpapi.py` and `run_ingest.py --provider serpapi --spend` ever make a
  live call; the whole suite runs on captured fixtures.
- **Test gate (two commands, both must be green):**
  ```
  cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests -q
  cd /Users/rajeshgupta/Desktop/reachout/reachout && PYTHONPATH=/Users/rajeshgupta/Desktop/reachout ../.venv/bin/python -m pytest -q
  ```
  Baseline before this plan: demand 158 passed, shopper 273 passed.
- **Secrets:** `SERPAPI_API_KEY` lives in `reachout/.env` (gitignored, the one
  credentials file `python-dotenv` loads). Never commit it, never print it, never
  put it in a captured fixture.

---

## File Structure

| File | Responsibility |
|---|---|
| `demand/ingest/serpapi_client.py` | **Create.** HTTP only. Builds params, calls SerpApi, raises on API error. Zero domain logic. |
| `demand/scripts/probe_serpapi.py` | **Create.** One-shot 5-search probe. Writes raw JSON captures. |
| `demand/ingest/trends_client.py` | **Modify.** Add `SerpApiProvider`. Extend Protocol with `rising_queries`. Delete `TrendspyProvider` + `_load_trendspy`. |
| `demand/ingest/rising_store.py` | **Create.** Persist rising-query rows. Mirrors `snapshot_store.py`. |
| `demand/data/schema.sql` | **Modify.** Append `demand.rising_queries`. |
| `demand/scripts/run_ingest.py` | **Modify.** Pre-flight cost line, `--spend` guard, discovery pass. |
| `demand/requirements.txt` | **Modify.** Drop `trendspy`, `pandas`. |
| `demand/tests/fixtures/trends/captured/` | **Create.** Real SerpApi responses from Task 1. |

Split rationale: `serpapi_client.py` is transport, `trends_client.py` is domain
translation. Keeping them apart means the parser tasks (3, 4) can be tested
entirely offline against captured JSON with no HTTP mocking at all.

---

### Task 1: SerpApi transport + 5-search probe

**Files:**
- Create: `demand/ingest/serpapi_client.py`
- Create: `demand/scripts/probe_serpapi.py`
- Create: `demand/tests/test_serpapi_client.py`
- Create: `demand/tests/fixtures/trends/captured/` (populated by the live run)

**Interfaces:**
- Produces: `build_params(q, data_type, geo, date, gprop, api_key) -> dict[str, str]`
- Produces: `fetch(params: dict, timeout: float = 60.0) -> dict` — raises
  `SerpApiError` on `error` field or non-2xx.
- Produces: `SerpApiError(Exception)`
- Produces: `SERPAPI_ENDPOINT = "https://serpapi.com/search"`

- [ ] **Step 1: Write failing test**

Create `demand/tests/test_serpapi_client.py`:

```python
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
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_serpapi_client.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'demand.ingest.serpapi_client'`

- [ ] **Step 3: Write minimal implementation**

Create `demand/ingest/serpapi_client.py`:

```python
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
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_serpapi_client.py -v`

Expected: PASS — 7 passed

- [ ] **Step 5: Write the probe script**

Create `demand/scripts/probe_serpapi.py`:

```python
"""Spend exactly 5 searches to learn what SerpApi actually returns for Madrid.

Written before any parser exists, on purpose. Every parser task in this plan is
tested against the JSON this script captures, so no parser is ever written
against a guessed response shape.

Budget: 5 searches. 1 measurement + 4 discovery. Discovery gets the larger share
because it is the unproven half -- Google Shopping (`gprop=froogle`) on
region-scoped Spanish product terms is exactly the low-volume case where Trends
returns nothing, and four samples is the cheapest honest read on that.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from demand.ingest.serpapi_client import SerpApiError, build_params, fetch

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPTURE_DIR = REPO_ROOT / "demand" / "tests" / "fixtures" / "trends" / "captured"

GEO = "ES-MD"
MEASUREMENT_DATE = "today 3-m"
DISCOVERY_DATE = "today 1-m"

#: Five real seed keywords from demand/_config/seed_keywords.json. The first
#: five alphabetically, so the probe is reproducible and argument-free.
MEASUREMENT_KEYWORDS = [
    "abanico", "agua mineral", "aspirinas", "bañador", "bebidas energéticas",
]

#: Four discovery probes, chosen to span the volume range: two high-volume
#: staples, two mid. If froogle comes back empty on all four, the plan's
#: discovery pass falls back to web search -- that is the Task 2 gate.
DISCOVERY_KEYWORDS = ["café", "cerveza", "chocolate", "protector solar"]


def _write(name: str, payload: dict) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  wrote {path.relative_to(REPO_ROOT)}")


def _scrub(payload: dict) -> dict:
    """Strip anything carrying the key before the payload touches the repo."""
    payload.pop("search_metadata", None)
    params = payload.get("search_parameters")
    if isinstance(params, dict):
        params.pop("api_key", None)
    return payload


def main() -> int:
    load_dotenv(REPO_ROOT / "reachout" / ".env")
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        print("SERPAPI_API_KEY not set in reachout/.env -- refusing to run.")
        return 1

    print("[Probe] Spending 5 searches: 1 TIMESERIES + 4 RELATED_QUERIES")

    print("[Probe] 1/5 TIMESERIES, web search, 5 keywords, today 3-m")
    payload = fetch(build_params(
        q=MEASUREMENT_KEYWORDS, data_type="TIMESERIES", geo=GEO,
        date=MEASUREMENT_DATE, api_key=api_key,
    ))
    _write("timeseries_web_5kw.json", _scrub(payload))

    for i, keyword in enumerate(DISCOVERY_KEYWORDS, start=2):
        print(f"[Probe] {i}/5 RELATED_QUERIES, froogle, {keyword!r}, today 1-m")
        slug = keyword.replace(" ", "_")
        try:
            payload = fetch(build_params(
                q=[keyword], data_type="RELATED_QUERIES", geo=GEO,
                date=DISCOVERY_DATE, api_key=api_key, gprop="froogle",
            ))
            _write(f"related_queries_froogle_{slug}.json", _scrub(payload))
        except SerpApiError as exc:
            # An empty result is a FINDING, not a crash. Record it as such:
            # it is the sparsity measurement the probe exists to take.
            print(f"  EMPTY: {exc}")
            _write(f"related_queries_froogle_{slug}.json",
                   {"related_queries": {}, "_probe_note": str(exc)})

    print("[Probe] Done. 5 searches spent. 245 remain this month.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Verify the probe refuses to run without a key**

Run: `cd /Users/rajeshgupta/Desktop/reachout && SERPAPI_API_KEY= .venv/bin/python -m demand.scripts.probe_serpapi`

Expected: prints `SERPAPI_API_KEY not set in reachout/.env -- refusing to run.`, exit code 1, **zero searches spent**.

- [ ] **Step 7: Commit the code before spending anything**

```bash
git add demand/ingest/serpapi_client.py demand/scripts/probe_serpapi.py demand/tests/test_serpapi_client.py
git commit -m "feat(demand): SerpApi transport and 5-search probe script"
```

- [ ] **Step 8: HUMAN STEP — add the key, then run the probe**

Founder adds to `reachout/.env`:
```
SERPAPI_API_KEY=<key from serpapi.com/manage-api-key>
```

Then run — **this spends 5 searches and cannot be undone**:
```bash
cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m demand.scripts.probe_serpapi
```

Expected: 5 files in `demand/tests/fixtures/trends/captured/`.

- [ ] **Step 9: Commit the captures**

```bash
git add demand/tests/fixtures/trends/captured/
git commit -m "chore(demand): capture 5 live SerpApi responses for Madrid"
```

---

### ⛔ GATE — read the captures before Task 2

**Stop here. A human reads the five files and answers three questions.** Every
task after this is written against these captures, so a wrong read here is paid
for in every task that follows.

1. **Does `timeseries_web_5kw.json` carry `interest_over_time.timeline_data`, with
   one entry per query inside each `values[]` array?** If the array is flat or the
   `query` field is absent, Task 3's parser changes shape.
2. **How many of the four `related_queries_froogle_*.json` files contain a
   non-empty `related_queries.rising` list?**
   - **3–4 non-empty →** proceed as planned, `gprop=froogle`.
   - **0–2 non-empty →** Shopping is too sparse for Madrid. Change
     `DISCOVERY_GPROP` to `""` (web search) in Task 5 and note it in the plan.
     Everything else is unaffected.
3. **Does any `rising` entry carry `value: "Breakout"`?** If yes, confirm whether
   `extracted_value` is absent or present. Task 4's test asserts on this exact
   shape.

Record the answers in the Task 2 commit message.

---

### Task 2: RELATED_QUERIES parser, Protocol extension, fixture replay

**Files:**
- Modify: `demand/ingest/trends_client.py` (Protocol block, lines 6–11)
- Modify: `demand/tests/test_trends_client.py`

**Interfaces:**
- Produces: `parse_rising_queries(payload: dict) -> List[Dict[str, Any]]`
  returning `[{"query": str, "growth_pct": float | None, "is_breakout": bool}]`
- Produces: `BREAKOUT_TOKEN = "Breakout"`
- Produces: `TrendsProvider.rising_queries(keyword: str, geo: str, date: str, gprop: str) -> List[Dict[str, Any]]`
- Produces: `FixtureProvider.rising_queries(...)` — replays captured JSON.

The parser lands here rather than with the live provider (Task 4) because it is
a pure function over captured JSON. Keeping it with the transport-free half
means this whole task is testable offline and ends green on its own.

- [ ] **Step 1: Write failing test**

Append to `demand/tests/test_trends_client.py`:

```python
from demand.ingest.trends_client import parse_rising_queries


def test_parse_rising_queries_extracts_percentage():
    payload = {"related_queries": {"rising": [
        {"query": "leche sin lactosa", "value": "+4,200%",
         "extracted_value": 4200},
    ]}}
    assert parse_rising_queries(payload) == [
        {"query": "leche sin lactosa", "growth_pct": 4200.0,
         "is_breakout": False},
    ]


def test_parse_rising_queries_flags_breakout_without_inventing_a_number():
    # Google refuses to quantify Breakout. Assigning it 5000 -- or max+1, or
    # anything -- fabricates a figure the source declined to give. The same
    # refusal _rescale_to_anchor already makes when it drops an unreconcilable
    # batch rather than emit it on a guessed scale.
    payload = {"related_queries": {"rising": [
        {"query": "leche de avena", "value": "Breakout"},
    ]}}
    assert parse_rising_queries(payload) == [
        {"query": "leche de avena", "growth_pct": None, "is_breakout": True},
    ]


def test_parse_rising_queries_ignores_the_top_list():
    # `top` is all-time popularity, not growth. Mixing it into a "rising"
    # panel would present steady bestsellers as new demand.
    payload = {"related_queries": {
        "rising": [{"query": "a", "value": "+10%", "extracted_value": 10}],
        "top": [{"query": "b", "value": "100", "extracted_value": 100}],
    }}
    assert [row["query"] for row in parse_rising_queries(payload)] == ["a"]


def test_parse_rising_queries_handles_empty_response():
    assert parse_rising_queries({"related_queries": {}}) == []
    assert parse_rising_queries({}) == []


def test_parse_rising_queries_skips_rows_without_a_query():
    payload = {"related_queries": {"rising": [
        {"value": "+10%", "extracted_value": 10},
        {"query": "válido", "value": "+20%", "extracted_value": 20},
    ]}}
    assert [row["query"] for row in parse_rising_queries(payload)] == ["válido"]


def test_fixture_provider_rising_queries_returns_empty_when_no_capture(tmp_path):
    from demand.ingest.trends_client import FixtureProvider

    provider = FixtureProvider(fixtures_dir=str(tmp_path))
    assert provider.rising_queries("café", geo="ES-MD", date="today 1-m",
                                   gprop="froogle") == []


def test_fixture_provider_rising_queries_replays_capture(tmp_path):
    import json
    from demand.ingest.trends_client import FixtureProvider

    captured = tmp_path / "captured"
    captured.mkdir()
    (captured / "related_queries_froogle_café.json").write_text(
        json.dumps({"related_queries": {"rising": [
            {"query": "café soluble", "value": "+150%", "extracted_value": 150},
        ]}}), encoding="utf-8",
    )

    provider = FixtureProvider(fixtures_dir=str(tmp_path))
    rows = provider.rising_queries("café", geo="ES-MD", date="today 1-m",
                                   gprop="froogle")
    assert rows == [{"query": "café soluble", "growth_pct": 150.0,
                     "is_breakout": False}]
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_trends_client.py -k rising -v`

Expected: FAIL — `ImportError: cannot import name 'parse_rising_queries'`

- [ ] **Step 3: Write the parser, extend the Protocol and FixtureProvider**

Add to `demand/ingest/trends_client.py`:

```python
#: Google's literal answer when growth exceeds roughly 5000%. It is a refusal
#: to quantify, not a large number, and is stored as one.
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
        is_breakout = str(item.get("value", "")).strip() == BREAKOUT_TOKEN
        extracted = item.get("extracted_value")
        growth = None if (is_breakout or extracted is None) else float(extracted)
        rows.append({"query": query, "growth_pct": growth,
                     "is_breakout": is_breakout})

    return rows
```

Add to the `TrendsProvider` Protocol:

```python
    def rising_queries(self, keyword: str, geo: str, date: str,
                       gprop: str) -> List[Dict[str, Any]]:
        ...
```

Add to `FixtureProvider`:

```python
    def rising_queries(self, keyword: str, geo: str = "ES-MD",
                       date: str = "today 1-m",
                       gprop: str = "froogle") -> List[Dict[str, Any]]:
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
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_trends_client.py -v`

Expected: PASS — 7 new tests green (5 parser, 2 fixture replay), plus the
existing `_batch_keywords` / `_rescale_to_anchor` suite still green.

- [ ] **Step 5: Commit**

Record the three GATE answers in the commit body — they are the only place the
probe's findings get written down, and the next task depends on answer 2.

```bash
git add demand/ingest/trends_client.py demand/tests/test_trends_client.py
git commit -m "feat(demand): rising-query parser, protocol extension, fixture replay

GATE answers from the 5-search probe:
1. timeline_data shape: <as expected | describe deviation>
2. froogle non-empty: <N>/4 parents  -> DISCOVERY_GPROP stays 'froogle' | falls back to ''
3. Breakout present: <yes/no>, extracted_value <absent | present>"
```

---

### Task 3: TIMESERIES parser

**Files:**
- Modify: `demand/ingest/trends_client.py`
- Create: `demand/tests/test_serpapi_provider.py`

**Interfaces:**
- Consumes: `build_params`, `fetch` (Task 1); `_batch_keywords`,
  `_rescale_to_anchor` (existing, unchanged)
- Produces: `parse_timeseries(payload: dict, keywords: List[str]) -> Dict[str, List[Dict[str, Any]]]`
- Produces: `SerpApiProvider.interest_over_time(keywords, geo, timeframe)` with
  the same return contract as the deleted `TrendspyProvider`:
  `{keyword: [{"date": "YYYY-MM-DD", "value": float}, ...]}`

- [ ] **Step 1: Write failing test**

Create `demand/tests/test_serpapi_provider.py`:

```python
from demand.ingest.trends_client import parse_timeseries


def _payload():
    return {"interest_over_time": {"timeline_data": [
        {"date": "Jul 6 - Jul 12, 2026", "timestamp": "1751760000",
         "values": [{"query": "café", "value": "75", "extracted_value": 75},
                    {"query": "cerveza", "value": "40", "extracted_value": 40}]},
        {"date": "Jul 13 - Jul 19, 2026", "timestamp": "1752364800",
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
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_serpapi_provider.py -v`

Expected: FAIL — `ImportError: cannot import name 'parse_timeseries'`

- [ ] **Step 3: Write the parser and provider**

Add to `demand/ingest/trends_client.py`. The import must bind `build_params` and
`fetch` as module-level names — Task 4's tests monkeypatch `tc.fetch`, which only
works if this module calls the rebound name rather than `serpapi_client.fetch`:

```python
from datetime import datetime, timezone

from demand.ingest.serpapi_client import build_params, fetch

#: SerpApi echoes Google's display date ("Jul 6 - Jul 12, 2026"), which is
#: locale-shaped and ambiguous to parse. `timestamp` is epoch seconds and is
#: not, so the ISO date is derived from that and the display string ignored.
def _iso_date(entry: Dict[str, Any]) -> str:
    ts = entry.get("timestamp")
    if ts is None:
        return ""
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def parse_timeseries(payload: Dict[str, Any],
                     keywords: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """One SerpApi TIMESERIES payload -> the provider's series contract.

    Returns an entry for EVERY requested keyword. A keyword Google had nothing
    for gets an empty list, never a missing key -- callers downstream index by
    keyword and a KeyError there would read as a bug rather than as no data.
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
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_serpapi_provider.py -v`

Expected: PASS — 6 passed

- [ ] **Step 5: Verify against the real capture**

Add to `demand/tests/test_serpapi_provider.py`:

```python
import json
from pathlib import Path

import pytest

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
```

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_serpapi_provider.py -v`

Expected: PASS — 7 passed (the capture test runs, not skipped, because Task 1 committed the file)

- [ ] **Step 6: Commit**

```bash
git add demand/ingest/trends_client.py demand/tests/test_serpapi_provider.py
git commit -m "feat(demand): SerpApi TIMESERIES parser and provider"
```

---

### Task 4: Live discovery call on SerpApiProvider

**Files:**
- Modify: `demand/ingest/trends_client.py`
- Modify: `demand/tests/test_serpapi_provider.py`

**Interfaces:**
- Consumes: `parse_rising_queries` (Task 2), `build_params` / `fetch` /
  `SerpApiError` (Task 1)
- Produces: `SerpApiProvider.rising_queries(keyword, geo, date, gprop) -> List[Dict[str, Any]]`

- [ ] **Step 1: Write failing test**

Append to `demand/tests/test_serpapi_provider.py`:

```python
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
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_serpapi_provider.py -k rising -v`

Expected: FAIL — `AttributeError: 'SerpApiProvider' object has no attribute 'rising_queries'`

- [ ] **Step 3: Write the method**

Add to `SerpApiProvider` in `demand/ingest/trends_client.py`:

```python
    def rising_queries(self, keyword: str, geo: str = "ES-MD",
                       date: str = "today 1-m",
                       gprop: str = "froogle") -> List[Dict[str, Any]]:
        """One search. RELATED_QUERIES takes exactly one query -- no batching
        is possible here, which is why discovery is capped at the top movers
        rather than run across the whole universe."""
        try:
            payload = fetch(build_params(
                q=[keyword], data_type="RELATED_QUERIES", geo=geo,
                date=date, api_key=self.api_key, gprop=gprop or None,
            ))
        except SerpApiError:
            # Sparse is the expected case on Shopping for a region-scoped
            # Spanish term. No data is a normal answer, not a failed run.
            return []
        return parse_rising_queries(payload)
```

Extend the import at the top of `trends_client.py` — Task 3 already added
`build_params` and `fetch`; this adds the error type:

```python
from demand.ingest.serpapi_client import (
    SerpApiError, build_params, fetch,
)
```

**Note for the implementer:** the tests monkeypatch `tc.fetch`, so
`trends_client` must call the module-level name `fetch(...)` it imported — not
`serpapi_client.fetch(...)`. Rebinding the import is what makes the live path
testable without a network or a key.

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_serpapi_provider.py demand/tests/test_trends_client.py -v`

Expected: PASS — 3 new provider tests green, Task 2 and Task 3 suites still green.

- [ ] **Step 5: Commit**

```bash
git add demand/ingest/trends_client.py demand/tests/test_serpapi_provider.py
git commit -m "feat(demand): live rising_queries call with sparse-result tolerance"
```

---

### Task 5: Database table

**Files:**
- Modify: `demand/data/schema.sql`
- Create: `demand/ingest/rising_store.py`
- Create: `demand/tests/test_rising_store.py`

**Interfaces:**
- Produces: `rising_query_id(parent_keyword, query, geo, captured_date) -> str` (uuid5)
- Produces: `build_rows(parent_keyword, rows, geo, gprop, captured_at) -> List[dict]`
- Produces: `store_rising_queries(supa_client, rows) -> int`

- [ ] **Step 1: Append the table to `demand/data/schema.sql`**

The file is `create table if not exists` throughout, so the founder re-pastes the
whole file into the Supabase SQL editor — there is no separate migration.

```sql
-- Discovery pass: products Madrid started searching for that are NOT in the
-- seed keyword universe. Distinct grain from trend_snapshots: one row per
-- DISCOVERED query per parent keyword per day, not per tracked keyword.
create table if not exists demand.rising_queries (
    id             uuid primary key,
    parent_keyword text        not null,
    query          text        not null,
    -- NULL when Google answered "Breakout" and refused to quantify growth.
    -- A number here is always a number Google gave; never one we chose.
    growth_pct     numeric,
    is_breakout    boolean     not null default false,
    geo            text        not null,
    -- Stored, not constant: a Shopping-derived row and a Web-derived row mean
    -- different things and must never merge silently.
    gprop          text        not null,
    captured_at    timestamptz not null,
    captured_date  date        not null
);

create index if not exists rising_queries_captured_date_idx
    on demand.rising_queries (captured_date desc);
```

- [ ] **Step 2: Write failing test**

Create `demand/tests/test_rising_store.py`:

```python
from demand.ingest.rising_store import build_rows, rising_query_id


def test_rising_query_id_is_stable_for_same_natural_key():
    a = rising_query_id("café", "café soluble", "ES-MD", "2026-08-10")
    b = rising_query_id("café", "café soluble", "ES-MD", "2026-08-10")
    assert a == b


def test_rising_query_id_differs_per_day():
    a = rising_query_id("café", "café soluble", "ES-MD", "2026-08-10")
    b = rising_query_id("café", "café soluble", "ES-MD", "2026-08-11")
    assert a != b


def test_rising_query_id_differs_per_parent():
    a = rising_query_id("café", "soluble", "ES-MD", "2026-08-10")
    b = rising_query_id("té", "soluble", "ES-MD", "2026-08-10")
    assert a != b


def test_build_rows_maps_every_field():
    rows = build_rows(
        parent_keyword="café",
        rows=[{"query": "café soluble", "growth_pct": 150.0,
               "is_breakout": False}],
        geo="ES-MD", gprop="froogle",
        captured_at="2026-08-10T09:00:00+00:00",
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["parent_keyword"] == "café"
    assert row["query"] == "café soluble"
    assert row["growth_pct"] == 150.0
    assert row["is_breakout"] is False
    assert row["geo"] == "ES-MD"
    assert row["gprop"] == "froogle"
    assert row["captured_date"] == "2026-08-10"
    assert row["id"] == rising_query_id("café", "café soluble", "ES-MD",
                                        "2026-08-10")


def test_build_rows_keeps_breakout_growth_null():
    rows = build_rows(
        parent_keyword="leche",
        rows=[{"query": "leche de avena", "growth_pct": None,
               "is_breakout": True}],
        geo="ES-MD", gprop="froogle",
        captured_at="2026-08-10T09:00:00+00:00",
    )
    assert rows[0]["growth_pct"] is None
    assert rows[0]["is_breakout"] is True


def test_build_rows_returns_empty_for_no_rows():
    assert build_rows("café", [], "ES-MD", "froogle",
                      "2026-08-10T09:00:00+00:00") == []
```

- [ ] **Step 3: Run test, verify it fails**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_rising_store.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'demand.ingest.rising_store'`

- [ ] **Step 4: Write the implementation**

Create `demand/ingest/rising_store.py`:

```python
"""Persist the discovery pass. Mirrors snapshot_store.py's uuid5 dedupe."""

import uuid
from typing import Any, Dict, List

#: Same fixed namespace discipline as snapshot_store: a uuid5 over the natural
#: key means re-running a Monday twice upserts the same ids instead of doubling
#: the table. Counts that double on a re-run are a finding, not a busy day.
RISING_NAMESPACE = uuid.UUID("6f1c9b02-6b1d-5a4e-9d4b-2f0f2c9a7e31")


def rising_query_id(parent_keyword: str, query: str, geo: str,
                    captured_date: str) -> str:
    """The natural key: which seed term surfaced which query, where, when."""
    return str(uuid.uuid5(
        RISING_NAMESPACE,
        f"{parent_keyword}|{query}|{geo}|{captured_date}",
    ))


def build_rows(parent_keyword: str, rows: List[Dict[str, Any]], geo: str,
               gprop: str, captured_at: str) -> List[Dict[str, Any]]:
    """Parser output -> database rows. No derivation, only shaping."""
    captured_date = captured_at[:10]
    return [
        {
            "id": rising_query_id(parent_keyword, row["query"], geo,
                                  captured_date),
            "parent_keyword": parent_keyword,
            "query": row["query"],
            "growth_pct": row["growth_pct"],
            "is_breakout": row["is_breakout"],
            "geo": geo,
            "gprop": gprop,
            "captured_at": captured_at,
            "captured_date": captured_date,
        }
        for row in rows
    ]


def store_rising_queries(supa_client: Any, rows: List[Dict[str, Any]]) -> int:
    """Upsert on the primary key. Returns the number of rows sent."""
    if not rows:
        return 0
    supa_client.table("rising_queries").upsert(rows).execute()
    return len(rows)
```

- [ ] **Step 5: Run test, verify it passes**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_rising_store.py -v`

Expected: PASS — 6 passed

- [ ] **Step 6: Commit**

```bash
git add demand/data/schema.sql demand/ingest/rising_store.py demand/tests/test_rising_store.py
git commit -m "feat(demand): rising_queries table and store with uuid5 dedupe"
```

- [ ] **Step 7: HUMAN STEP — apply the DDL**

Founder pastes the whole of `demand/data/schema.sql` into the Supabase SQL
editor and runs it. Existing tables are untouched (`if not exists`).

Then, in the same editor, re-grant — a newly created table does not inherit the
grants issued for the earlier three:

```sql
grant all on all tables in schema demand to service_role;
```

Verify with a REST probe (should return `200 []`):

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "apikey: $SUPABASE_SERVICE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  -H "Accept-Profile: demand" \
  "$SUPABASE_URL/rest/v1/rising_queries?select=id&limit=1"
```

---

### Task 6: Wire the provider and the budget guard into the ingest chain

**Files:**
- Modify: `demand/scripts/run_ingest.py`
- Create: `demand/tests/test_ingest_budget.py`

**Interfaces:**
- Consumes: `SerpApiProvider`, `store_rising_queries`, `build_rows`
- Produces: `estimate_searches(universe_size: int, discovery_count: int) -> dict`
- Produces: `get_provider(name)` gains a `"serpapi"` branch
- Produces: `DISCOVERY_TIMEFRAME = "today 1-m"`, `DISCOVERY_GPROP = "froogle"`,
  `DISCOVERY_TOP_N = 10`

- [ ] **Step 1: Write failing test**

Create `demand/tests/test_ingest_budget.py`:

```python
from demand.scripts.run_ingest import estimate_searches


def test_estimate_batches_timeseries_four_real_keywords_per_request():
    # 49 keywords: 1 anchor + 48 real, 4 real per request => 12 requests.
    est = estimate_searches(universe_size=49, discovery_count=10)
    assert est["timeseries"] == 12


def test_estimate_charges_one_search_per_discovery_keyword():
    # RELATED_QUERIES accepts exactly 1 query -- no batching is possible.
    est = estimate_searches(universe_size=49, discovery_count=10)
    assert est["discovery"] == 10


def test_estimate_total_is_the_sum():
    est = estimate_searches(universe_size=49, discovery_count=10)
    assert est["total"] == 22


def test_estimate_handles_single_keyword_universe():
    est = estimate_searches(universe_size=1, discovery_count=0)
    assert est["timeseries"] == 1
    assert est["total"] == 1


def test_estimate_handles_empty_universe():
    est = estimate_searches(universe_size=0, discovery_count=0)
    assert est["total"] == 0
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_ingest_budget.py -v`

Expected: FAIL — `ImportError: cannot import name 'estimate_searches'`

- [ ] **Step 3: Add the estimator and the discovery constants**

Add to `demand/scripts/run_ingest.py`:

```python
import math

from demand.ingest.rising_store import build_rows, store_rising_queries
from demand.ingest.trends_client import KEYWORDS_PER_BATCH

#: Discovery runs on a SHORTER window than measurement on purpose. It never
#: enters compute_signals, so HIGH_MIN_WINDOWS does not constrain it, and the
#: question it answers -- what is rising NOW -- wants recency.
DISCOVERY_TIMEFRAME = "today 1-m"

#: Google Shopping. Closer to purchase intent than web search, at the cost of
#: sparsity on region-scoped Spanish terms. Set to "" to fall back to web
#: search if the Task 1 probe showed froogle empty for Madrid.
DISCOVERY_GPROP = "froogle"

#: RELATED_QUERIES cannot batch, so discovery costs one search per keyword.
#: Ten keeps a full run at 22 searches, ~4 runs a month inside a 250 budget
#: with room left over.
DISCOVERY_TOP_N = 10


def estimate_searches(universe_size: int, discovery_count: int) -> dict:
    """What a run will cost BEFORE it is allowed to spend anything.

    TIMESERIES carries a shared anchor term in every request, so only
    KEYWORDS_PER_BATCH (4) of the 5 allowed slots hold real keywords.
    """
    if universe_size <= 0:
        timeseries = 0
    else:
        real = max(universe_size - 1, 0)
        timeseries = max(math.ceil(real / KEYWORDS_PER_BATCH), 1)
    return {
        "timeseries": timeseries,
        "discovery": discovery_count,
        "total": timeseries + discovery_count,
    }
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests/test_ingest_budget.py -v`

Expected: PASS — 5 passed

- [ ] **Step 5: Add the `--spend` guard to `main()`**

Replace the `main()` body in `demand/scripts/run_ingest.py`:

```python
def main():
    parser = argparse.ArgumentParser(description="Demand Ingest Chain")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print counts, write nothing")
    parser.add_argument("--provider", type=str,
                        default=os.environ.get("DEMAND_TRENDS_PROVIDER",
                                               "serpapi"),
                        help="Trends provider (serpapi or fixture)")
    parser.add_argument("--spend", action="store_true",
                        help="Required for a live provider. Without it the run "
                             "prints its cost and exits without calling out.")
    args = parser.parse_args()

    # The guard exists because the budget is finite and an accidental
    # `--provider serpapi` in a loop is unrecoverable spend. Defaulting to dry
    # means the expensive path is always an explicit choice.
    if args.provider == "serpapi" and not args.spend:
        # `get_client` and `build_universe` are already imported at module
        # scope by run_ingest.py -- `run_chain` calls both. Reading the universe
        # costs a database query, not a search.
        universe = build_universe(get_client())
        est = estimate_searches(len(universe), DISCOVERY_TOP_N)
        print("[Ingest] provider=serpapi  PRE-FLIGHT")
        print(f"         {est['timeseries']} TIMESERIES "
              f"({len(universe)} kw, {INGEST_TIMEFRAME}, web)")
        print(f"       + {est['discovery']} RELATED_QUERIES "
              f"({DISCOVERY_TIMEFRAME}, {DISCOVERY_GPROP or 'web'})")
        print(f"         = {est['total']} searches of a 250/month budget.")
        print("         Re-run with --spend to proceed.")
        return

    run_chain(provider_name=args.provider, dry_run=args.dry_run)
```

- [ ] **Step 6: Add the `serpapi` branch to `get_provider`**

In `demand/ingest/trends_client.py`, replace the `get_provider` body:

```python
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
```

- [ ] **Step 7: Add the discovery pass to `run_chain`**

Insert into `run_chain`, after signals are computed and before the function
returns — discovery runs on the **top movers**, which only exist once signals do:

```python
    # Discovery pass. Runs on the top movers rather than the whole universe
    # because RELATED_QUERIES cannot batch: the universe would cost one search
    # per keyword and blow the monthly budget in two runs.
    top_keywords = [
        s["keyword"] for s in sorted(
            signals, key=lambda s: s.get("delta_pct", 0.0), reverse=True
        )[:DISCOVERY_TOP_N]
    ]
    print(f"[Ingest] Discovery on {len(top_keywords)} top movers "
          f"({DISCOVERY_GPROP or 'web'}, {DISCOVERY_TIMEFRAME})")

    discovered = 0
    empty = 0
    for keyword in top_keywords:
        rows = provider.rising_queries(
            keyword, geo=INGEST_GEO, date=DISCOVERY_TIMEFRAME,
            gprop=DISCOVERY_GPROP,
        )
        if not rows:
            empty += 1
            continue
        # `now_utc` and `client` are the existing run_chain locals -- the same
        # timestamp the trend_snapshots rows carry, so a run's two passes share
        # one captured_at rather than drifting by however long the fetch took.
        built = build_rows(keyword, rows, INGEST_GEO, DISCOVERY_GPROP,
                           now_utc)
        if not dry_run:
            store_rising_queries(client, built)
        discovered += len(built)

    # Coverage is reported, not hidden. Shopping is sparse for region-scoped
    # Spanish terms, and a run where 8 of 10 parents came back empty is a very
    # different result from one where all 10 answered.
    print(f"[Ingest] Discovery: {discovered} rising queries, "
          f"{empty}/{len(top_keywords)} parents empty")
```

- [ ] **Step 8: Verify the guard spends nothing**

Run: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m demand.scripts.run_ingest --provider serpapi`

Expected: prints the pre-flight block, exits, **zero searches spent**.

Run the offline path: `cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m demand.scripts.run_ingest --provider fixture --dry-run`

Expected: completes on captured fixtures, zero searches.

- [ ] **Step 9: Commit**

```bash
git add demand/scripts/run_ingest.py demand/ingest/trends_client.py demand/tests/test_ingest_budget.py
git commit -m "feat(demand): SerpApi provider wiring, budget guard, discovery pass"
```

---

### Task 7: Delete TrendspyProvider

**Files:**
- Modify: `demand/ingest/trends_client.py`
- Modify: `demand/requirements.txt`
- Modify: `demand/tests/test_trends_client.py`

- [ ] **Step 1: Delete the dead code**

From `demand/ingest/trends_client.py`, remove: `_load_trendspy()`, the entire
`TrendspyProvider` class, and the now-unused `retry_on_429` decorator if nothing
else references it (`grep -n "retry_on_429" demand/` to confirm before removing).

Keep: `MAX_KEYWORDS_PER_REQUEST`, `KEYWORDS_PER_BATCH`, `_batch_keywords`,
`_rescale_to_anchor`. All four are still live — SerpApi is a proxy to the same
Google endpoint and inherits the same 5-term cap and per-request renormalisation.

- [ ] **Step 2: Delete the trendspy tests**

Remove every test in `demand/tests/test_trends_client.py` that monkeypatches
`sys.modules["pandas"]` or `sys.modules["trendspy"]` (lines ~37–130 and ~252).
Keep all `_batch_keywords`, `_rescale_to_anchor`, and `FixtureProvider` tests.

- [ ] **Step 3: Drop the dependencies**

In `demand/requirements.txt`, delete the `trendspy>=0.1` / `pandas>=2.0` block
and its comment. Replace with:

```
# Live provider: SerpApi's Google Trends engine, called over httpx (declared
# above for the API). The previous trendspy scraper was removed on 2026-08-10 --
# it was IP-throttled to a CAPTCHA and had no path back. No new dependency: the
# provider is an HTTP call, and the key lives in reachout/.env as
# SERPAPI_API_KEY.
```

- [ ] **Step 4: Run the full gate**

```bash
cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m pytest demand/tests -q
cd /Users/rajeshgupta/Desktop/reachout/reachout && PYTHONPATH=/Users/rajeshgupta/Desktop/reachout ../.venv/bin/python -m pytest -q
```

Expected: both green. Demand count will differ from the 158 baseline — trendspy
tests removed, SerpApi tests added. Record the new number.

- [ ] **Step 5: Confirm nothing still imports the deleted names**

```bash
grep -rn "trendspy\|TrendspyProvider\|_load_trendspy\|import pandas" demand/ reachout/ tools/ docs/
```

Expected: no hits in code. Hits in `docs/` are historical prose and stay.

- [ ] **Step 6: Commit**

```bash
git add demand/ingest/trends_client.py demand/requirements.txt demand/tests/test_trends_client.py
git commit -m "refactor(demand): remove TrendspyProvider, drop trendspy and pandas"
```

---

### Task 8: First live run

**Files:** none — this is an operational task.

- [ ] **Step 1: Confirm the pre-flight number before spending**

```bash
cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m demand.scripts.run_ingest --provider serpapi
```

Expected: `= 22 searches`. **If it reads higher than 25, stop and investigate** —
the universe grew, and a wrong batch count is the difference between 22 and a
blown budget.

- [ ] **Step 2: Dry run — spends searches, writes nothing**

```bash
cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m demand.scripts.run_ingest --provider serpapi --spend --dry-run
```

Expected: prints snapshot and discovery counts. Database unchanged. **22 spent, 223 left.**

- [ ] **Step 3: Real run**

```bash
cd /Users/rajeshgupta/Desktop/reachout && .venv/bin/python -m demand.scripts.run_ingest --provider serpapi --spend
```

Expected: rows in `demand.trend_snapshots` and `demand.rising_queries`.

**This re-run is free** — SerpApi caches identical parameter sets for 1 hour, so
running within the hour of Step 2 bills nothing.

- [ ] **Step 4: Verify idempotence — the finding that matters**

Record both counts, run the exact command from Step 3 again, then re-count:

```sql
select count(*) from demand.trend_snapshots;
select count(*) from demand.rising_queries;
```

Expected: **counts identical before and after.** Doubling means the uuid5 natural
key is wrong and dedupe is not working — stop and fix before any further run.

Also free, for the same 1-hour cache reason.

- [ ] **Step 5: Verify the discovery rows are honest**

```sql
select query, growth_pct, is_breakout, gprop
from demand.rising_queries
order by is_breakout desc, growth_pct desc nulls last
limit 20;
```

Check: every `is_breakout = true` row has `growth_pct` NULL. Any Breakout row
carrying a number means a fabricated figure reached the database — a correctness
bug, not a cosmetic one.

- [ ] **Step 6: Update the tracker**

In `docs/TRACKER.md`: mark **V1a** done, replacing the
`[!] blocked: Google IP-throttled (CAPTCHA)` state. Record the date, the row
counts, the discovery coverage (`N/10 parents empty`), and searches remaining.

```bash
git add docs/TRACKER.md
git commit -m "docs: V1a done -- live ingest via SerpApi, trendspy blocker retired"
```

---

## Budget Ledger

| Task | Searches | Running total | Remaining of 250 |
|---|---|---|---|
| 1 — probe | 5 | 5 | 245 |
| 2–7 — all offline | 0 | 5 | 245 |
| 8 Step 2 — dry run | 22 | 27 | 223 |
| 8 Step 3 — real run | 0 (cached) | 27 | 223 |
| 8 Step 4 — idempotence | 0 (cached) | 27 | 223 |

Steady state afterwards: one run per Monday, 22 each, ~95/month. Weekly cadence
is set by `compute_signals`'s Monday–Sunday windows — running more often
produces no new window and therefore no new information.

---

## What this plan does NOT deliver

The discovery data lands in `demand.rising_queries` and stops there. Nothing
reads it yet. `/demand/api/analytics` is unchanged, `analytics_response.schema.json`
is unchanged, and the dashboard still shows three panels.

That is deliberate: the fourth panel's shape depends on what the probe and the
first live run actually return — how sparse Shopping is, how many Breakouts
appear, whether growth percentages cluster or spread. Designing the panel before
seeing that data is guessing. A follow-up plan covers the schema segment, the
endpoint, and the UI once there are real rows to look at.
