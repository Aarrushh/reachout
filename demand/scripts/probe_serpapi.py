"""Spend exactly 5 searches to learn what SerpApi actually returns for Madrid.

ALREADY RUN. The captures under `demand/tests/fixtures/trends/captured/` are
its output and are committed; the gate this probe existed to answer is
answered. Running it again costs 5 more searches out of 250/month and buys
nothing, so it now requires `--spend`, exactly like `run_ingest`, and refuses
to overwrite an existing capture without `--overwrite` on top of that.

That second guard is not tidiness. `test_serpapi_provider.py` asserts against
`timeseries_web_5kw.json` field by field; a silent re-capture would rewrite
the fixture underneath the test that proves the parser reads real data.

Written before any parser exists, on purpose. Every parser task in this plan is
tested against the JSON this script captures, so no parser is ever written
against a guessed response shape.

Budget: 5 searches. 1 measurement + 4 discovery. Discovery gets the larger share
because it is the unproven half -- Google Shopping (`gprop=froogle`) on
region-scoped Spanish product terms is exactly the low-volume case where Trends
returns nothing, and four samples is the cheapest honest read on that.
"""

import argparse
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


#: Every file a full run writes. Listed so the overwrite check can be made
#: BEFORE the first search rather than discovered file by file, half-spent.
CAPTURE_NAMES = ["timeseries_web_5kw.json"] + [
    f"related_queries_froogle_{kw.replace(' ', '_')}.json"
    for kw in DISCOVERY_KEYWORDS
]


def _write(name: str, payload: dict) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        shown = path.relative_to(REPO_ROOT)
    except ValueError:
        shown = path
    print(f"  wrote {shown}")


def _existing_captures() -> list:
    return [n for n in CAPTURE_NAMES if (CAPTURE_DIR / n).exists()]


def _scrub(payload: dict) -> dict:
    """Strip anything carrying the key before the payload touches the repo."""
    payload.pop("search_metadata", None)
    params = payload.get("search_parameters")
    if isinstance(params, dict):
        params.pop("api_key", None)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-shot SerpApi shape probe. Already run; see module "
                    "docstring.")
    parser.add_argument("--spend", action="store_true",
                        help="Required. Without it the probe prints its cost "
                             "and exits without calling out.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Required as well when captures already exist. "
                             "They are committed test fixtures.")
    args = parser.parse_args()

    # Checked FIRST, before `load_dotenv`: a run nobody authorised should not
    # even open the credentials file, let alone put a live key into the
    # environment of whatever process happens to be running this.
    if not args.spend:
        print("[Probe] PRE-FLIGHT -- nothing spent.")
        print("         1 TIMESERIES + 4 RELATED_QUERIES = 5 searches "
              "of a 250/month budget.")
        print("         The captures this writes are already committed and "
              "the gate they answered is closed.")
        print("         Re-run with --spend to proceed.")
        return 0

    existing = _existing_captures()
    if existing and not args.overwrite:
        print(f"[Probe] {len(existing)} capture(s) already exist and would be "
              f"overwritten:")
        for name in existing:
            print(f"           {name}")
        print("         demand/tests/test_serpapi_provider.py asserts against "
              "them field by field.")
        print("         Pass --overwrite as well if replacing them is really "
              "the intent.")
        return 1

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

    # No remaining-balance figure. The line here used to read "245 remain this
    # month", hardcoded from the assumption that this run was the only spend
    # -- and it was already wrong by the time it was committed, because 8
    # searches had gone by then, not 5. A number this script cannot observe
    # must not be printed as though it had been observed.
    print("[Probe] Done. 5 searches spent by this run. "
          "Check the SerpApi dashboard for the remaining balance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
