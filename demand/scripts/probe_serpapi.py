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
