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
from demand.ingest.serpapi_client import SerpApiHTTPError
from demand.ingest.trends_client import (
    FIXTURE_PROVIDER,
    KEYWORDS_PER_BATCH,
    PAID_PROVIDERS,
    SERPAPI_PROVIDER,
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

    # `top_n <= 0` means "buy nothing", and it has to be said here rather than
    # left to the loop below: the only stop condition is `len(parents) ==
    # top_n`, which can never fire when `top_n` is 0 or negative, so a bare
    # pass-through would return the ENTIRE eligible universe -- one billed
    # RELATED_QUERIES search per keyword, the exact opposite of what the
    # caller asked for.
    if top_n <= 0:
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


#: How many `demand_signals` rows the anchor read pulls back, and why a bare
#: `.select(...)` was not enough.
#:
#: `pick_anchor` needs exactly one thing: every row of the NEWEST window, so
#: it can rank that window's `interest_avg`. `demand_signals` carries one row
#: per keyword per weekly window, so the newest window is one row per keyword
#: -- 49 today, the size of the universe `build_universe` returns.
#:
#: The ORDER is what makes this safe; the number only buys headroom. Old
#: windows are never deleted and every run adds ~49 more rows per distinct
#: window: a `today 3-m` capture is ~13 windows (~637 rows), the table already
#: holds 686, and the 12-month backfill about to run takes it to roughly 2548.
#: That is past Supabase's default `db-max-rows` (1000), where PostgREST
#: truncates the response on its own, in whatever physical order the rows come
#: back in. An unordered read therefore hands `pick_anchor` an arbitrary page,
#: `max(window_start)` is computed over that page rather than over the table,
#: and the anchor -- the single value all cross-batch comparability depends on
#: -- is chosen from a stale window with nothing printed. Sorting
#: `window_start` descending server-side guarantees the newest window sits at
#: the FRONT of the page, so the limit only has to be wider than that one
#: window.
#:
#: 500 is ~10x the 49-keyword universe, so the universe can grow an order of
#: magnitude before the newest window stops fitting. It stays under
#: `db-max-rows` (1000) on purpose: the page that comes back is then the page
#: this code asked for, not whatever a server-side cap happened to leave.
PRIOR_SIGNALS_LIMIT = 500


def _load_prior_signals(client) -> list:
    """The previous run's `demand_signals`, for anchor selection only.

    Best-effort by design. A missing table, an empty table or a transport
    error must not stop a capture: `pick_anchor` treats an empty list as a
    cold start and falls back to alphabetical, which is what this run would
    have done anyway.

    Ordered and bounded rather than open-ended -- see `PRIOR_SIGNALS_LIMIT`.
    """
    try:
        return (client.table("demand_signals")
                .select("keyword, interest_avg, window_start")
                .order("window_start", desc=True)
                .limit(PRIOR_SIGNALS_LIMIT)
                .execute().data) or []
    except Exception as exc:  # noqa: BLE001 - anchor choice is not worth a run
        print(f"[Ingest] Could not read prior signals for anchor ({exc}); "
              f"falling back to alphabetical")
        return []


class SpendNotAuthorised(RuntimeError):
    """A paid provider was asked to run without `spend=True`.

    Raised, not printed-and-returned: a caller that forgot to ask for spend
    has a bug, and a silent no-op run would look like a successful ingest that
    happened to find nothing.
    """


class SpendWouldBeDiscarded(RuntimeError):
    """A paid provider was asked to run with `dry_run=True`.

    `--dry-run` skips DATABASE writes. It has never skipped API calls, and it
    cannot: the counts it prints are the counts Google has to be asked for.
    Against a paid provider that makes this combination strictly dominated --
    22 billed searches, ~9% of the month, nothing stored, nothing to look at
    afterwards, and no way to recover what was bought. It is not a cheaper
    run; it is the most expensive run with the result deleted.

    Refused rather than documented. The finding could have been closed by
    rewording the `--dry-run` help text, and the help text says it plainly
    now anyway -- but a warning only helps the reader who reads it, and the
    cost of being wrong here is measured in a budget that does not refill
    until the month turns. There is no use case on the other side of the
    trade: anyone wanting a free rehearsal wants `--provider fixture`, and
    anyone wanting to see live numbers wants them stored.
    """


def _resolve_discovery_top_n(value) -> int:
    """`None` means the default; anything else is used as given, once checked.

    Shared by `run_chain` and the CLI pre-flight so that the estimate printed
    in front of a run and the run itself cannot disagree about how many
    searches discovery will buy. A pre-flight that quotes a different number
    than the run spends is worse than no pre-flight, because it is believed.

    Negative is refused rather than clamped. `-1` is far more likely a typo
    than an intention, and every silent reading of it spends money: it slices
    as "all but the last" and never satisfies `len(parents) == top_n`. 0 is a
    legitimate answer -- "measure the universe, skip discovery" -- so it is 0
    that has to be allowed and negative that has to raise.
    """
    if value is None:
        return DISCOVERY_TOP_N
    if value < 0:
        raise ValueError(
            f"discovery_top_n must be >= 0, got {value}. Use 0 to skip the "
            f"discovery pass; a negative count has no meaning and would buy "
            f"one RELATED_QUERIES search per keyword in the universe."
        )
    return value


def run_chain(provider_name: str, dry_run: bool = False, spend: bool = False,
              timeframe: str = None, discovery_top_n: int = None):
    """Run the whole demand chain once.

    `timeframe` and `discovery_top_n` default to `None`, meaning "use
    `INGEST_TIMEFRAME` / `DISCOVERY_TOP_N`". They exist for the one-off runs
    the constants deliberately do not serve -- a 12-month backfill, or a
    discovery pass over more of the universe than a weekly cron can afford --
    without editing source that the cron then inherits. Every existing caller,
    the cron included, keeps exactly the behaviour it was written against.

    `spend` is the budget gate and it lives HERE, at the one place every
    caller passes through, not in `main()`. The previous guard was
    `args.provider == "serpapi" and not args.spend` inside `main()`: it
    protected the CLI and nothing else, and `demand/api/app.py`'s cron called
    `run_chain(provider_name="serpapi", dry_run=False)` directly -- 22 live
    searches every Monday behind a single env var, with no pre-flight and
    nobody reading the output. A guard one caller can walk past is not a
    guard; it is a habit the CLI happens to have.

    Default `False` on purpose: spending is opt-in per call, so a new caller
    added later inherits refusal rather than permission. `--dry-run` is NOT
    this gate -- it skips database writes and still makes every search, which
    is why a paid provider refuses it outright (see `SpendWouldBeDiscarded`).

    Both guards read `PAID_PROVIDERS` rather than the literal `"serpapi"`, and
    both live here rather than in `main()`, for the same reason: a second paid
    provider, or a rename, must inherit the refusal instead of having to be
    remembered in two files.
    """
    if provider_name in PAID_PROVIDERS and not spend:
        raise SpendNotAuthorised(
            f"provider {provider_name!r} spends real SerpApi searches out of a "
            f"250/month budget. Pass spend=True, or run the CLI with --spend "
            f"to see the pre-flight estimate first."
        )

    if provider_name in PAID_PROVIDERS and dry_run:
        raise SpendWouldBeDiscarded(
            f"provider {provider_name!r} bills every search whether or not the "
            f"rows are stored, so dry_run=True buys the whole run and then "
            f"throws it away. Drop --dry-run to keep what you pay for, or use "
            f"--provider {FIXTURE_PROVIDER} to rehearse for free."
        )

    # Both overrides resolve ONCE, here, into locals that the rest of this
    # function reads instead of the module constants. Resolving at each use
    # site is how half a run ends up on one window and half on another.
    #
    # `timeframe` is not merely a fetch parameter. It is the third field of the
    # `trend_snapshots` natural key -- (keyword, geo, timeframe,
    # captured_date) -- which is what `snapshot_id` hashes with uuid5 and what
    # `trend_snapshots_dedupe_idx` in `demand/data/schema.sql` dedupes on. So
    # `run_timeframe` must reach the provider call, the `"timeframe"` field AND
    # `snapshot_id`, all three, or the run is silently destructive: a
    # `today 12-m` backfill that still computes ids from `today 3-m` upserts
    # twelve months of numbers on top of the three-month rows a real capture
    # already wrote, under the ids those rows are addressed by, and the
    # original data is gone. Threaded everywhere or nowhere.
    run_timeframe = INGEST_TIMEFRAME if timeframe is None else timeframe
    run_discovery_top_n = _resolve_discovery_top_n(discovery_top_n)

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

    print(f"[Ingest] Fetching interest_over_time ({run_timeframe})...")
    time_series = provider.interest_over_time(
        universe, geo=INGEST_GEO, timeframe=run_timeframe, anchor=anchor)

    # No id-preserving round-trip: snapshot ids are uuid5 over the same
    # (keyword, geo, timeframe, captured_date) tuple the dedupe index uses,
    # so re-running the same day recomputes the ids already in the table.
    # `run_timeframe` is part of that tuple, so a run on a different window
    # lands on different ids and sits BESIDE the existing rows instead of
    # overwriting them -- which is what makes a backfill safe to run at all.
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
            "id": snapshot_id(kw, INGEST_GEO, run_timeframe, captured_date),
            "keyword": kw,
            "geo": INGEST_GEO,
            "timeframe": run_timeframe,
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

    # No id-preserving round-trip here: `compute_signals` derives each signal
    # id with uuid5 from (keyword, geo, timeframe, window_start, window_end)
    # -- the same tuple `demand_signals_dedupe_tf_idx` uses -- so re-running a
    # window recomputes the id it already wrote and the upsert below
    # updates that row. Reading the table back to copy old ids would be
    # asking the DB a question the data already answers.
    #
    # `timeframe` must appear in BOTH that uuid5 key and this conflict target
    # or the two disagree: `id` is the primary key, so a backfill at a new
    # timeframe would hash to an existing row's id and fail on the primary
    # key while `on_conflict` pointed somewhere else entirely. See
    # `data/migrations/001_demand_signals_timeframe.sql`.

    if not dry_run and signals:
        client.table("demand_signals").upsert(
            signals,
            on_conflict="keyword,geo,timeframe,window_start,window_end"
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
    # reasoning. It may legitimately return FEWER than the cap -- a quiet week
    # buys fewer searches rather than padding the list back up with noise --
    # and at `run_discovery_top_n == 0` it returns nothing at all, so the loop
    # below never asks and the run costs measurement only.
    top_keywords = select_discovery_parents(signals, as_of_date=now_utc[:10],
                                            top_n=run_discovery_top_n)
    print(f"[Ingest] Discovery on {len(top_keywords)}/{run_discovery_top_n} "
          f"eligible movers ({DISCOVERY_GPROP or 'web'}, "
          f"{DISCOVERY_TIMEFRAME}, interest_avg >= {DISCOVERY_MIN_INTEREST})")

    fetched = 0
    stored = 0
    empty = 0
    failed = 0
    store_failed = 0
    for keyword in top_keywords:
        # One billed search per parent, and the rows for each are stored as
        # soon as they arrive. So a failure here loses ONE search, not the
        # nine others: the loop keeps going and whatever already landed
        # stays landed. Same rule as the measurement batch loop.
        #
        # "A failure here" means the whole parent -- fetch AND store. The
        # store call used to sit outside this `try`, which made the promise
        # above false in the one direction nobody would notice: a database
        # error raised straight out of `run_chain` after the search was
        # billed, and under the weekly cron it dies inside an APScheduler job
        # thread where nothing reads it. The parents already banked are not
        # worth one parent's failed write.
        try:
            rows = provider.rising_queries(
                keyword, geo=INGEST_GEO, date=DISCOVERY_TIMEFRAME,
                gprop=DISCOVERY_GPROP,
            )
        except SerpApiHTTPError as exc:
            failed += 1
            if exc.status_code in (429, 401, 403):
                # Not a per-keyword problem: the budget is gone or the key is
                # rejected, and every remaining parent would answer the same.
                print(f"[Ingest] Discovery stopped at {keyword!r}: {exc}. "
                      f"{len(top_keywords) - top_keywords.index(keyword) - 1} "
                      f"parents not attempted "
                      f"({'budget exhausted' if exc.status_code == 429 else 'key rejected'}).")
                break
            print(f"[Ingest] Discovery: {keyword!r} failed ({exc}); "
                  f"one search lost, continuing.")
            continue
        except Exception as exc:  # noqa: BLE001 - one parent, not the pass
            # Everything the provider can raise that is not an HTTP status.
            # `parse_rising_queries` raises `ValueError` on a payload whose
            # shape Google changed, and the client stack can raise transport
            # and attribute errors of its own; only `SerpApiHTTPError` was
            # caught, so any of those ended the pass and threw away every
            # parent still unasked. The measurement half already treats this
            # as one batch's problem (`SerpApiProvider._fetch_batch`'s final
            # `except Exception`) and discovery is one parent's problem for
            # exactly the same reason: the search is billed either way.
            #
            # The TYPE only, never `str(exc)` -- the same rule `_fetch_batch`
            # states. An unrecognised exception's message is text of unknown
            # provenance heading for stdout, and anything built from the
            # request carries the API key.
            failed += 1
            print(f"[Ingest] Discovery: {keyword!r} failed "
                  f"({type(exc).__name__}); one search lost, continuing.")
            continue
        if not rows:
            empty += 1
            continue
        # `now_utc` and `client` are the existing run_chain locals -- the same
        # timestamp the trend_snapshots rows carry, so a run's two passes share
        # one captured_at rather than drifting by however long the fetch took.
        built = build_rows(keyword, rows, INGEST_GEO, DISCOVERY_GPROP,
                           now_utc)
        fetched += len(built)
        if dry_run:
            # Nothing is written, so nothing can fail to be written. The
            # `fetched` count above still tells the rehearsal what the run
            # would have stored, which is the whole point of `--dry-run`.
            continue
        try:
            store_rising_queries(client, built)
        except Exception as exc:  # noqa: BLE001 - one parent's rows, not the run
            # The search is already paid for and these rows are lost, but the
            # parents before this one are in the table and the parents after
            # it are still worth asking. Type only, same reason as above.
            store_failed += 1
            print(f"[Ingest] Discovery: {keyword!r} fetched {len(built)} rows "
                  f"but storing them failed ({type(exc).__name__}); "
                  f"those rows are lost, continuing.")
            continue
        stored += len(built)

    # Coverage is reported, not hidden. Shopping is sparse for region-scoped
    # Spanish terms, and a run where 8 of 10 parents came back empty is a very
    # different result from one where all 10 answered.
    #
    # Stored and fetched are printed apart because they are different claims.
    # The old line printed one number and called it "rising queries" whether
    # or not a row ever reached the database, so a run that fetched 40 and
    # persisted none read exactly like a run that persisted 40.
    #
    # Fetch failures and storage failures are counted apart for the same
    # reason: one is SerpApi or the parser, the other is the database. They
    # have different causes and different fixes, and a single combined number
    # sends whoever reads it to the wrong half of the system.
    print(f"[Ingest] Discovery: {stored} rising queries stored "
          f"({fetched} fetched{', dry run stored none' if dry_run else ''}), "
          f"{empty}/{len(top_keywords)} parents empty, "
          f"{failed} failed, "
          f"{store_failed} storage failures")

    print("[Ingest] Finished.")

def main():
    parser = argparse.ArgumentParser(description="Demand Ingest Chain")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip DATABASE WRITES only. It does NOT skip API "
                             "calls: a paid provider still bills every one of "
                             "them, so this is refused for a paid provider "
                             "rather than buying a run and discarding it. Use "
                             f"--provider {FIXTURE_PROVIDER} to rehearse free.")
    parser.add_argument("--provider", type=str,
                        default=os.environ.get("DEMAND_TRENDS_PROVIDER",
                                               SERPAPI_PROVIDER),
                        help="Trends provider (serpapi or fixture)")
    parser.add_argument("--spend", action="store_true",
                        help="Required for a live provider. Without it the run "
                             "prints its cost and exits without calling out.")
    # Both default to None, not to the constant, so that "not passed" stays
    # distinguishable from "passed the same value as the default" and the
    # weekly cron -- which passes neither -- keeps reading the constants.
    parser.add_argument("--timeframe", type=str, default=None,
                        help="Measurement window for interest_over_time, e.g. "
                             f"'today 12-m' for a one-off backfill. Defaults to "
                             f"{INGEST_TIMEFRAME!r}. The window is part of a "
                             "trend_snapshots row's identity, so a different "
                             "one writes new rows beside the existing ones "
                             "rather than over them.")
    parser.add_argument("--discovery-top-n", type=int, default=None,
                        help="How many top movers get one RELATED_QUERIES "
                             f"search each. Defaults to {DISCOVERY_TOP_N}. "
                             "0 skips discovery entirely (measurement only); "
                             "raising it costs one extra search per keyword "
                             "out of the 250/month budget.")
    args = parser.parse_args()

    # The pre-flight, not the guard. The guard is `spend=` inside `run_chain`,
    # which every caller passes through; this block exists only to turn the
    # CLI's refusal into a useful answer -- what the run would cost -- instead
    # of a traceback. Reading PAID_PROVIDERS rather than comparing to
    # "serpapi" keeps it from disagreeing with the guard it stands in front of.
    if args.provider in PAID_PROVIDERS and not args.spend:
        # `get_client` and `build_universe` are already imported at module
        # scope by run_ingest.py -- `run_chain` calls both. Reading the universe
        # costs a database query, not a search.
        universe = build_universe(get_client())
        # The estimate has to describe THIS run, not the defaults. Quoting
        # `today 3-m` and 10 searches while the next invocation is about to
        # fetch a 12-month window and buy 40 is the worst failure available
        # here: the founder reads the number, believes it, adds --spend, and
        # the budget is gone. Resolved exactly the way `run_chain` will resolve
        # it, through the same helper, so the two cannot drift apart.
        preflight_timeframe = (INGEST_TIMEFRAME if args.timeframe is None
                               else args.timeframe)
        preflight_top_n = _resolve_discovery_top_n(args.discovery_top_n)
        est = estimate_searches(len(universe), preflight_top_n)
        print(f"[Ingest] provider={args.provider}  PRE-FLIGHT")
        print(f"         {est['timeseries']} TIMESERIES "
              f"({len(universe)} kw, {preflight_timeframe}, web)")
        print(f"       + {est['discovery']} RELATED_QUERIES "
              f"({DISCOVERY_TIMEFRAME}, {DISCOVERY_GPROP or 'web'})")
        print(f"         = {est['total']} searches of a 250/month budget.")
        print("         Re-run with --spend to proceed.")
        return

    # Same shape, same reason: `run_chain` is the guard and it raises, this
    # block only turns the CLI's version of that refusal into a sentence
    # instead of a traceback. `--spend --dry-run` is the one combination that
    # spends the whole budget and keeps nothing.
    if args.provider in PAID_PROVIDERS and args.dry_run:
        print(f"[Ingest] provider={args.provider}  REFUSED")
        print("         --dry-run skips database writes, not API calls. Every "
              "search would still")
        print("         be billed and then thrown away. Drop --dry-run, or "
              f"use --provider {FIXTURE_PROVIDER}.")
        return

    run_chain(provider_name=args.provider, dry_run=args.dry_run,
              spend=args.spend, timeframe=args.timeframe,
              discovery_top_n=args.discovery_top_n)

if __name__ == "__main__":
    main()
