import argparse
import math
import os
import sys
import uuid
from datetime import datetime, timezone

# Running this file directly (`python demand/scripts/run_ingest.py`) puts
# demand/scripts on sys.path, not the repo root, so the `demand.` imports below
# would not resolve. Add the repo root -- and ONLY the repo root. The previous
# version added demand/ instead, which both failed to satisfy these imports and
# re-opened the double-import hole for the whole process: with demand/ on the
# path, `ingest.trends_client` and `demand.ingest.trends_client` load as two
# separate modules and monkeypatching one leaves the other billing real money.
# See demand/tests/test_import_hygiene.py.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from demand.api.app import get_client
from demand.ingest.keywords import build_universe, normalize_keyword
from demand.ingest.rising_store import build_rows, store_rising_queries
from demand.ingest.trends_client import (
    KEYWORDS_PER_BATCH,
    get_provider,
    pick_anchor,
)
from demand.ingest.snapshot_store import store_snapshots
from demand.scripts.compute_signals import (
    DEMAND_ID_NAMESPACE,
    NATURAL_KEY_SEP,
    compute_signals,
)
from demand.scripts.recommend import PRODUCTS_SCHEMA, build_recommendations

#: The provider window every capture is taken over. `today 3-m` is ~13
#: weekly windows, so a single capture's series can clear
#: `compute_signals.HIGH_MIN_WINDOWS` (8) and the `high` confidence tier is
#: reachable in production. The previous `today 1-m` (~4 weekly windows)
#: made `high` structurally impossible: the threshold is the spec
#: (IMPLEMENTATION_PLAN_V2.md 5.6, fixtures README) and the ingest window
#: was the side that was wrong, so the window moved, not the threshold.
INGEST_TIMEFRAME = "today 3-m"

INGEST_GEO = "ES-MD"

#: Discovery runs on a SHORTER window than measurement on purpose. It never
#: enters compute_signals, so HIGH_MIN_WINDOWS does not constrain it, and the
#: question it answers -- what is rising NOW -- wants recency.
DISCOVERY_TIMEFRAME = "today 1-m"

#: Web search, not Google Shopping. Shopping is closer to purchase intent and
#: was the first choice, but the Task 1 probe measured it empty on 4 of 4
#: region-scoped Spanish terms while web search returned 25 rising queries on
#: the same keyword, geo and window. An empty panel has no intent to be close
#: to. See the GATE ANSWERS section for the measurement.
DISCOVERY_GPROP = ""

#: RELATED_QUERIES cannot batch, so discovery costs one search per keyword.
#: Ten keeps a full run at 22 searches, ~4 runs a month inside a 250 budget
#: with room left over.
DISCOVERY_TOP_N = 10

#: Floor on `interest_avg` before a keyword is worth a paid search.
#:
#: Measured, not guessed. `compute_signals` emits a flat `delta_pct = 100.0`
#: whenever the previous window averaged 0 and the current one did not, so a
#: keyword with a SINGLE day rounded up to 1 on Google's integer 0-100 scale
#: scores exactly the same delta as a genuine doubling. In the captured probe
#: (`tests/fixtures/trends/captured/timeseries_web_5kw.json`, 5 keywords, 75
#: signals) three of the naive top ten were this artifact: `aspirinas` and
#: `bebidas energéticas` at `interest_avg = 0.14`, which is one day at 1 over
#: a seven-day window.
#:
#: 1.0 is where the data has a cliff, not a round number chosen for looks: of
#: those 75 signals, 33 sit at or above 1.0 and the next one down is at 0.14 --
#: nothing at all lies between. It reads as "the window has to average at
#: least one point on Google's scale", i.e. more than single-day rounding.
#:
#: Under-spending is the correct failure mode. If only three keywords clear
#: this floor, the run makes three discovery searches, not ten.
DISCOVERY_MIN_INTEREST = 1.0


def select_discovery_parents(
    signals: list,
    as_of_date: str,
    top_n: int = DISCOVERY_TOP_N,
    min_interest: float = DISCOVERY_MIN_INTEREST,
) -> list:
    """Pick the keywords worth one RELATED_QUERIES search each.

    Pure function of the signals, no I/O, no provider -- this decides how
    real money is spent, so it is testable in isolation and an AI never
    touches it (`demand/CLAUDE.md`).

    `signals` holds ONE ROW PER KEYWORD PER WEEKLY WINDOW: a `today 3-m`
    capture produces ~13 rows per keyword. Ranking that list directly by
    `delta_pct` and slicing the top ten -- which is what this replaced --
    fails three separate ways at once, all three reproduced against the real
    captured probe in `tests/test_discovery_selection.py`:

    * **Duplicates.** One keyword's thirteen windows compete for all ten
      slots. `abanico` alone took five. Every repeat is a wasted search:
      `rising_query_id` hashes (parent, query, geo, gprop, captured_date), so
      the second search for a keyword upserts over the rows the first one
      just wrote.
    * **Staleness.** Four of the ten winning windows were from May and June
      while `DISCOVERY_TIMEFRAME` asks Google what is rising in the last
      month. A keyword that spiked three months ago is not an answer.
    * **Noise.** See `DISCOVERY_MIN_INTEREST`.

    The last window of a capture is a PARTIAL week -- `today 3-m` ends on the
    day of capture, and the cron fires Monday 00:00 UTC, so the newest window
    is minutes old and its delta compares one Monday against a full week.
    Selection therefore uses the newest window that has actually closed. If
    no window has closed yet (cold start on a very short history), the newest
    window is used rather than discovering nothing.
    """
    if not signals:
        return []

    closed = [s for s in signals if s.get("window_end", "") < as_of_date]
    eligible = closed or signals

    latest = max(s["window_start"] for s in eligible)

    # Deterministic total order: `delta_pct` decides, `keyword` breaks ties,
    # so two runs over the same signals spend on the same keywords.
    ranked = sorted(
        (s for s in eligible
         if s["window_start"] == latest
         and s.get("interest_avg", 0.0) >= min_interest),
        key=lambda s: (-s.get("delta_pct", 0.0), s["keyword"]),
    )

    parents = []
    seen = set()
    for signal in ranked:
        keyword = signal["keyword"]
        if keyword in seen:
            continue
        seen.add(keyword)
        parents.append(keyword)
        if len(parents) == top_n:
            break
    return parents


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


def snapshot_id(keyword: str, geo: str, timeframe: str, captured_date: str) -> str:
    """The id of the trend_snapshots row for this natural key.

    Natural key, verbatim:
        "trend_snapshot|<keyword>|<geo>|<timeframe>|<captured_date>"
    hashed with `uuid5` under `DEMAND_ID_NAMESPACE` (see
    `compute_signals.py`). That is exactly the tuple
    `trend_snapshots_dedupe_idx` in `demand/data/schema.sql` dedupes on, and
    exactly the tuple the upsert below passes to PostgREST as
    `on_conflict`.

    This closes the last non-determinism in the chain. A `uuid4()` here
    forced a compensating read of the whole table on every run just to copy
    the previous run's ids back over the new ones, and any row that read
    missed came back with a fresh id -- which then leaked into the
    `snapshot_ids` provenance column of every signal derived from it. The
    id is now a function of the data, so re-running a day's capture
    recomputes the id it already wrote and nothing has to be looked up.
    """
    natural_key = NATURAL_KEY_SEP.join(
        ["trend_snapshot", keyword, geo, timeframe, captured_date]
    )
    return str(uuid.uuid5(DEMAND_ID_NAMESPACE, natural_key))


def _load_prior_signals(client) -> list:
    """The previous run's `demand_signals`, for anchor selection only.

    Best-effort by design. A missing table, an empty table or a transport
    error must not stop a capture: `pick_anchor` treats an empty list as a
    cold start and falls back to alphabetical, which is what this run would
    have done anyway.
    """
    try:
        return (client.table("demand_signals")
                .select("keyword, interest_avg, window_start")
                .execute().data) or []
    except Exception as exc:  # noqa: BLE001 - anchor choice is not worth a run
        print(f"[Ingest] Could not read prior signals for anchor ({exc}); "
              f"falling back to alphabetical")
        return []


def run_chain(provider_name: str, dry_run: bool = False):
    print(f"[Ingest] Starting run (provider={provider_name}, dry_run={dry_run})")
    client = get_client()

    # 1. Keywords
    universe = build_universe(client)
    print(f"[Ingest] Built universe: {len(universe)} keywords")

    # 2. Capture Trends
    provider = get_provider(provider_name)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshots = []
    

    # Every batch carries the anchor, so the anchor decides whether the
    # batches can be compared at all. Pick it by measured volume: a low-volume
    # anchor rounds to 0 next to a high-volume term and `_rescale_to_anchor`
    # then drops that batch's four keywords for one paid search. This run's
    # signals do not exist yet, so the previous run's are what we have; a cold
    # start falls back to alphabetical inside `pick_anchor`. Reading
    # `demand_signals` is a Supabase read and spends no SerpApi budget.
    anchor = pick_anchor(_load_prior_signals(client), universe)
    print(f"[Ingest] Batch anchor: {anchor!r}")

    print(f"[Ingest] Fetching interest_over_time ({INGEST_TIMEFRAME})...")
    time_series = provider.interest_over_time(
        universe, geo=INGEST_GEO, timeframe=INGEST_TIMEFRAME, anchor=anchor)

    # No id-preserving round-trip: snapshot ids are uuid5 over the same
    # (keyword, geo, timeframe, captured_date) tuple the dedupe index uses,
    # so re-running the same day recomputes the ids already in the table.
    region_failures = []
    for kw in universe:
        series = time_series.get(kw, [])
        # Best-effort, and deliberately so. `region_breakdown` is optional in
        # trend_snapshot.schema.json ("if available", and the type is
        # ["array", "null"]) — it is a nice-to-have breakdown, not the
        # signal. Google's comparedgeo endpoint returns 400 for a low-volume
        # term inside ES-MD (verified live 2026-08-03 on "abanico"), and an
        # unguarded call there killed a whole 49-keyword run AFTER every
        # series had already been fetched. The series is what the pipeline
        # computes on; losing a regional breakdown for one keyword is not a
        # reason to throw away 12 requests' worth of real data.
        try:
            region_breakdown = provider.interest_by_region(kw, geo=INGEST_GEO)
        except Exception as exc:  # noqa: BLE001 — provider raises requests.HTTPError and friends
            region_failures.append((kw, type(exc).__name__))
            region_breakdown = None

        captured_date = now_utc[:10]

        snapshot = {
            "id": snapshot_id(kw, INGEST_GEO, INGEST_TIMEFRAME, captured_date),
            "keyword": kw,
            "geo": INGEST_GEO,
            "timeframe": INGEST_TIMEFRAME,
            "provider": provider_name,
            "captured_at": now_utc,
            "series": series,
            # None, not [] — an empty list claims "we asked and Madrid has
            # no regional interest", which is a different statement from
            # "we could not get a breakdown". The schema permits null.
            "region_breakdown": region_breakdown if region_breakdown else None
        }
        snapshots.append(snapshot)

    
    print(f"[Ingest] Captured {len(snapshots)} snapshots")
    if region_failures:
        print(
            f"[Ingest] region_breakdown unavailable for {len(region_failures)} "
            f"of {len(universe)} keywords (stored as null, series unaffected): "
            + ", ".join(f"{kw} ({err})" for kw, err in region_failures[:5])
            + (" ..." if len(region_failures) > 5 else "")
        )
    
    if not dry_run:
        store_snapshots(snapshots, client)
        print("[Ingest] Stored snapshots in DB")
    
    # 3. Compute Signals
    # public schema: the client is bound to `demand`, and `products` is not
    # in it (see PRODUCTS_SCHEMA in recommend.py).
    result = client.schema(PRODUCTS_SCHEMA).table('products').select('category').execute()
    db_categories = []
    if hasattr(result, 'data') and result.data:
        db_categories = [str(r.get('category')) for r in result.data if r.get('category')]

    # THE casing rule, in the one place the keyword->category join is built:
    # keys are `normalize_keyword(...)` (strip + lower) and `compute_signals`
    # looks up through the same function. The universe deliberately keeps
    # each keyword's ORIGINAL casing (that is what is sent to the provider),
    # so a raw-string map key and an exact-match lookup miss on every
    # keyword whose category is not already lower-case -- which is exactly
    # how every production signal came out with `category: None`.
    # Iterating sorted() so two categories that normalise to the same key
    # resolve the same way regardless of the row order the DB returns.
    cat_map = {}
    for cat in sorted(db_categories):
        cat_map.setdefault(normalize_keyword(cat), cat)

    signals = compute_signals(snapshots, category_map=cat_map, computed_at=now_utc)
    print(f"[Ingest] Computed {len(signals)} signals")

    # No id-preserving round-trip here: `compute_signals` derives each
    # signal id with uuid5 from (keyword, geo, window_start, window_end) --
    # the same tuple `demand_signals_dedupe_idx` uses -- so re-running a
    # window recomputes the id it already wrote and the upsert below
    # updates that row. Reading the table back to copy old ids would be
    # asking the DB a question the data already answers.

    if not dry_run and signals:
        client.table("demand_signals").upsert(
            signals, 
            on_conflict="keyword,geo,window_start,window_end"
        ).execute()
        print("[Ingest] Upserted signals in DB")
        
    # 4. Build Recommendations
    recommendations = build_recommendations(signals, client)
    print(f"[Ingest] Built {len(recommendations)} recommendations")
    
    if not dry_run and recommendations:
        client.table("recommendations").upsert(
            recommendations,
            on_conflict="store_id,signal_id"
        ).execute()
        print("[Ingest] Upserted recommendations in DB")

    # Discovery pass. Runs on the top movers rather than the whole universe
    # because RELATED_QUERIES cannot batch: the universe would cost one search
    # per keyword and blow the monthly budget in two runs.
    #
    # `select_discovery_parents` carries the whole selection rule and its
    # reasoning. It may legitimately return FEWER than DISCOVERY_TOP_N
    # keywords -- a quiet week buys fewer searches rather than padding the
    # list back up with noise.
    top_keywords = select_discovery_parents(signals, as_of_date=now_utc[:10])
    print(f"[Ingest] Discovery on {len(top_keywords)}/{DISCOVERY_TOP_N} "
          f"eligible movers ({DISCOVERY_GPROP or 'web'}, "
          f"{DISCOVERY_TIMEFRAME}, interest_avg >= {DISCOVERY_MIN_INTEREST})")

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

    print("[Ingest] Finished.")

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

if __name__ == "__main__":
    main()
