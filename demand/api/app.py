"""Public, unauthenticated read API for the demand service.

NO AUTH, BY DESIGN (D2). `store_id` is a plain filter parameter, not an
authorization subject; there is no RLS and no GRANT block in
`demand/data/schema.sql`. Do not add auth here — but do assume every byte
of every response body is public, which is why the 5xx paths below return
fixed, described messages and log the underlying detail server-side instead
of interpolating it into the body (W1-FIX-F Finding 14).

Three rules this module lives by:

1. **Never `SELECT *` on a demand table whose rows are schema-validated.**
   `demand.trend_snapshots.captured_date` is a DB-only column deliberately
   absent from `trend_snapshot.schema.json` (`additionalProperties: false`),
   so a widened select turns every row into a contract violation. The column
   lists below are the contract; `demand/tests/test_api.py` asserts that no
   select in this file is `"*"`.
2. **Validation stays ON, and it is the gate, not a decoration.** All
   validation goes through `demand.shared.validation.validate_with_formats`,
   which attaches a `FormatChecker` so draft-07 `format` keywords actually
   assert. Bare `jsonschema.validate()` would let `format: uuid` through as
   an annotation and this API would reflect caller input out of a response
   it calls "schema-validated". (`format: date-time` is still unenforced in
   this venv — see `UNENFORCED_FORMATS` — so do not read a passing
   validation as proof a timestamp is a timestamp.)
3. **Nothing is invented to satisfy a validator.** No placeholder store id,
   no hardcoded confidence label, no metric that was not computed from rows
   that were actually read. A number that cannot be computed is not
   returned.
"""

import asyncio
import datetime
import json
import logging
import os
import sys
from collections import Counter
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
import jsonschema
from supabase import Client, create_client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from demand.api.relevance import annotate
from demand.ingest.trends_client import SERPAPI_PROVIDER
from demand.shared.validation import validate_with_formats


#: Credentials live in `reachout/.env` (gitignored; see
#: `reachout/.env.example`), the same file `reachout/api/supa.py` loads —
#: one credentials file for the whole repo, not one per service. This is
#: the choke point on purpose: `get_client()` below is the only Supabase
#: client constructor in the workspace, and `demand/scripts/run_ingest.py`
#: imports it, so loading here covers both the API process and the CLI
#: chain. Without this the chain only ran if you exported both vars into
#: the shell by hand.
#:
#: Two properties this relies on: `load_dotenv` does not overwrite a var
#: that is already set (so an explicit `export` still wins), and a missing
#: file is a no-op rather than an error. The second is what keeps the
#: Jules-VM rule intact — those VMs hold no keys, and the whole suite runs
#: on fakes and fixtures with no `.env` present.
load_dotenv(Path(__file__).resolve().parents[2] / "reachout" / ".env")

logger = logging.getLogger(__name__)

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "shared" / "schemas"

#: Module-level so a test can point the fixture path somewhere else without
#: monkeypatching `open`.
ANALYTICS_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "analytics_convenience_store.json"
)


def load_schema(name: str) -> dict:
    with open(SCHEMAS_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


TREND_SCHEMA = load_schema("trend_snapshot.schema.json")
SIGNAL_SCHEMA = load_schema("demand_signal.schema.json")
REC_RESPONSE_SCHEMA = load_schema("recommendations_response.schema.json")
ANALYTICS_SCHEMA = load_schema("analytics_response.schema.json")
RISING_QUERY_SCHEMA = load_schema("rising_query.schema.json")

#: A caller-supplied id is checked against the SAME schema fragment the
#: response is later checked against, so the boundary check and the contract
#: check can never disagree about what a uuid is.
UUID_SCHEMA = {"type": "string", "format": "uuid"}

# --- Explicit column lists. Never "*" on a schema-validated demand table. ---
TREND_COLUMNS = (
    "id, keyword, geo, timeframe, provider, captured_at, series, region_breakdown"
)
#: `timeframe` is selected, not omitted: it is `required` in
#: demand_signal.schema.json, so a response without it fails the contract and
#: 500s. It is also what a consumer needs in order NOT to plot a 3-month and a
#: 12-month reading of the same week on one axis -- they are different scales.
SIGNAL_COLUMNS = (
    "id, keyword, category, geo, timeframe, window_start, window_end, "
    "interest_avg, delta_pct, direction, rank, confidence, snapshot_ids, "
    "computed_at"
)
RECOMMENDATION_COLUMNS = (
    "id, store_id, signal_id, headline, body, action, confidence, caveat, created_at"
)
#: The analytics live path builds points, not rows, so it reads only what a
#: point (or the confidence rule, or the ordering) needs.
ANALYTICS_SIGNAL_COLUMNS = (
    "keyword, category, interest_avg, delta_pct, direction, confidence, rank, window_end"
)
#: `stock_qty` is the input the plan (§5.5) names for `stock_out_risk`. It
#: was never selected before W1-FIX-F, which is why the metric was faked.
ANALYTICS_PRODUCT_COLUMNS = "category, stock_qty"
#: Every DB column `rising_query.schema.json` requires that is not one of
#: the four fields `demand/api/relevance.py:annotate()` computes at read
#: time (relevance_score, relevance_tier, relevance_reasons, cluster_id).
RISING_QUERY_COLUMNS = (
    "id, parent_keyword, query, growth_pct, is_breakout, geo, gprop, "
    "captured_at, captured_date"
)

# --- Bounds. Every read is bounded and ordered; none of these are magic. ---
#: The two measurement scales `demand.demand_signals` and
#: `demand.trend_snapshots` hold, discriminated by `timeframe`. Google
#: rescales its 0-100 interest index to the requested window, and this
#: pipeline rescales again onto a shared anchor keyword, so the same keyword
#: in the same calendar week reads differently at 3-m and at 12-m. Every
#: read of either table must pick one.
ALLOWED_TIMEFRAMES = ("today 3-m", "today 12-m")
#: Unchanged default: a caller that never heard of the new param gets
#: exactly the scale every existing consumer already read.
DEFAULT_TIMEFRAME = "today 3-m"

#: Default page size for the three list endpoints.
DEFAULT_PAGE_SIZE = 100
#: Documented hard cap. `limit` above this is a 422 from FastAPI, not a
#: silently-clamped value: a caller that asked for 10_000 rows should be
#: told it cannot have them rather than quietly handed 500.
MAX_PAGE_SIZE = 500
#: `demand.demand_signals` holds one row per keyword per weekly window, but
#: the analytics query is now bounded to a single `window_start` (the most
#: recent one for the requested timeframe, resolved separately -- see
#: `get_analytics`), not to the whole table. The keyword universe is capped
#: at 100 (`build_universe`), so this cap is a backstop against one
#: pathologically large window, not the primary bound.
ANALYTICS_SIGNALS_CAP = 500
#: `public.products` is specified at 3000-5000 rows
#: (`reachout/data/schema.sql`). The cap sits at the top of that range so a
#: full-inventory read is normally complete; when it is not, the composition
#: segments say so through their confidence label (see `_census_confidence`).
ANALYTICS_PRODUCTS_CAP = 5000
#: `top_movers` is a chart, not a data dump.
TOP_MOVERS_MAX_POINTS = 20
#: `demand.rising_queries` holds 658 rows today across 42 parent keywords.
#: This is NOT the caller's `limit` on /rising-queries -- it is a backstop
#: on the database read that happens BEFORE `annotate()`/tiering/`limit`
#: (see that endpoint's docstring for why the order matters). `annotate()`
#: must see the whole result set to cluster correctly, so this cap has to
#: sit comfortably above the live row count, not near the caller-facing
#: page size.
RISING_QUERIES_READ_CAP = 5000
#: /rising-queries has its own caller-facing ceiling, above the shared
#: MAX_PAGE_SIZE = 500 the three list endpoints use. Reason: this route's
#: rows are not a page of a browsable table, they are the input to a
#: client-side clustering render -- 602 of the 658 live rows tier
#: `commercial`, so a 500 cap silently hid 102 of them behind a caption
#: that read like a complete list. The other endpoints keep MAX_PAGE_SIZE;
#: raising that shared constant would loosen three unrelated routes.
#: Above this ceiling the answer is still a 422, never a silent clamp --
#: and X-Total-Count tells the caller what it is missing either way.
RISING_QUERIES_MAX_LIMIT = 1000
#: `include` values for /rising-queries: `commercial` is the default,
#: filtered view; `all` is the audit view over every tier.
ALLOWED_RISING_QUERY_INCLUDES = ("commercial", "all")

#: A SKU with this many units or fewer on hand counts as at risk of stocking
#: out. Deterministic, documented, and applied to `products.stock_qty` — the
#: column §5.5 names. The seeder stocks 0-12 units per SKU
#: (`reachout/data/sku_catalog.json`), so "2 or fewer" is the bottom fifth of
#: that range: low enough to mean something, high enough to be reachable.
STOCK_OUT_QTY_THRESHOLD = 2

#: Weakest to strongest. The only ordering of confidence labels in this file.
CONFIDENCE_ORDER = ("low", "medium", "high")

CANONICAL_CAVEAT = (
    "Basado en interés de búsqueda en Madrid, no en compras reales."
)

#: Fixed body for every dependency failure. The driver's own message can name
#: hosts, credentials and SQL; this service has no auth, so "the caller" is
#: the public. The detail goes to the log instead.
DB_FAILURE_DETAIL = "Database dependency failed"


@lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY not set")
    # In Supabase python client, you can specify schema in ClientOptions
    from supabase.client import ClientOptions
    return create_client(url, key, options=ClientOptions(schema="demand"))


#: The provider the weekly job runs on. Imported from the same module
#: `get_provider` dispatches from, so a rename cannot leave the cron pointing
#: at a name that no longer resolves -- which is exactly what happened when
#: `TrendspyProvider` was deleted and `provider_name="trendspy"` stayed here,
#: raising `ValueError: Unknown provider` every Monday inside a scheduler
#: thread where nobody reads the traceback.
CRON_PROVIDER = SERPAPI_PROVIDER


def _cron_would_duplicate_across_workers() -> bool:
    """True when this process is probably one of several identical workers.

    `AsyncIOScheduler` is per-process. Under `uvicorn --workers 4` each worker
    runs its own copy of this lifespan, starts its own scheduler, and fires
    its own Monday job: 4 x 22 searches out of 250/month. The rows are
    uuid5-keyed, so the three extra runs upsert over the first one's rows and
    buy nothing at all -- the spend is pure loss and nothing in the output
    says it happened.

    Best-effort by construction: a worker cannot ask the parent how many
    siblings it has. `WEB_CONCURRENCY` is what uvicorn and gunicorn both read
    for their default worker count, and the worker flag survives into the
    child's argv, so between them they catch the realistic deployments. The
    contract the operator has to hold is still the plain one: run the ingest
    cron on a single-worker process (or, better, as an external scheduled job
    invoking `run_ingest --spend`).

    All four spellings of the flag are checked, and `-w` is not optional
    thoroughness: it is how gunicorn's own documentation writes it, and
    `WEB_CONCURRENCY` is only gunicorn's *default* -- it is ignored the moment
    `-w` is given. Checking the long form alone meant the commonest spelling of
    the exact deployment this function exists to stop (`gunicorn -w 4 -k
    uvicorn.workers.UvicornWorker demand.api.app:app`) walked straight through
    into 4 x 22 = 88 searches a month, upserting over each other.
    """
    try:
        if int(os.environ.get("WEB_CONCURRENCY", "1")) > 1:
            return True
    except ValueError:
        pass

    def _more_than_one(value: str) -> bool:
        try:
            return int(value) > 1
        except ValueError:
            return False

    for i, arg in enumerate(sys.argv):
        # `-w 4` / `--workers 4`: the count is the next token.
        if arg in ("-w", "--workers") and i + 1 < len(sys.argv):
            if _more_than_one(sys.argv[i + 1]):
                return True
        # `--workers=4`: the count is after the `=`.
        elif arg.startswith("--workers="):
            if _more_than_one(arg.split("=", 1)[1]):
                return True
        # `-w4`: gunicorn accepts the count glued on. Guarded by `isdigit` so
        # this stays an exact match on `-w` and never a prefix match on some
        # future short flag that happens to begin with the same letter.
        elif arg.startswith("-w") and arg[2:].isdigit():
            if _more_than_one(arg[2:]):
                return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if os.environ.get("DEMAND_INGEST_CRON") == "1":
        from demand.scripts.run_ingest import run_chain

        # Two switches, not one. `DEMAND_INGEST_CRON=1` used to both start the
        # scheduler AND authorise 22 live searches a week -- one checkbox on a
        # deploy dashboard, no pre-flight, no confirmation, and no operator
        # watching stdout at midnight on a Monday. Turning the job on and
        # agreeing to pay for it are separate decisions, so they are separate
        # variables, and the job is not scheduled at all unless both are set.
        # Scheduling a job that would only raise is noise, not safety.
        if os.environ.get("DEMAND_INGEST_CRON_SPEND") != "1":
            print("DEMAND_INGEST_CRON=1 but DEMAND_INGEST_CRON_SPEND is not "
                  "'1' -- the weekly job spends real SerpApi searches, so it "
                  "was NOT scheduled. Set DEMAND_INGEST_CRON_SPEND=1 to "
                  "authorise it.")
        elif _cron_would_duplicate_across_workers():
            print("DEMAND_INGEST_CRON=1 but this process looks like one of "
                  "several web workers; each would run its own weekly ingest "
                  "and multiply the spend. The job was NOT scheduled. Run the "
                  "cron on a single-worker process.")
        else:
            scheduler = AsyncIOScheduler()
            # Weekly, not daily: compute_signals aggregates into Monday-to-
            # Sunday windows, so a mid-week ingest produces a partial window
            # (worse than no data). Monday matches that windowing, not a
            # budget choice -- if the SerpApi plan is ever raised, that does
            # not make daily correct.

            async def run_chain_async():
                await asyncio.to_thread(run_chain,
                                        provider_name=CRON_PROVIDER,
                                        dry_run=False,
                                        # The cron opts in explicitly. It does
                                        # not inherit permission from having
                                        # been scheduled -- `run_chain`
                                        # refuses a paid provider by default.
                                        spend=True)

            # `timezone="UTC"` explicitly. APScheduler otherwise uses the
            # server's local zone, and every other date in this chain is UTC:
            # `now_utc` stamps `captured_at`, `select_discovery_parents`
            # compares `window_end` against `now_utc[:10]`, and
            # `compute_signals` builds Monday-to-Sunday windows. A host an hour
            # west of UTC fires the "Monday" job on Sunday evening, inside a
            # window that has not closed -- the partial-window case the weekly
            # cadence was chosen to avoid.
            scheduler.add_job(run_chain_async, 'cron', day_of_week='mon',
                              hour=0, minute=0, timezone='UTC')
            scheduler.start()
            print("Started DEMAND_INGEST_CRON weekly job")

    yield

    if scheduler:
        scheduler.shutdown()
        print("Stopped DEMAND_INGEST_CRON weekly job")


app = FastAPI(title="Demand API", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://localhost:5173$|^https://.*\.netlify\.app$",
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Guarded plumbing. Everything that can touch Supabase goes through _fetch.
# ---------------------------------------------------------------------------

async def _fetch(build_query) -> List[dict]:
    """Build and run one Supabase read; any failure is a clean 502.

    `build_query` is a zero-argument callable, not a built query, because
    **client construction and query construction are part of the failure
    surface**. `get_client()` raises on a missing `SUPABASE_URL`/`SUPABASE_KEY`
    — the single most likely production failure — and `client.schema(...)` /
    `client.table(...)` can raise too. Before W1-FIX-F those calls sat
    outside the try/except and a misconfigured environment produced a raw
    500 with a stack trace on every route. Pass the whole chain in as a
    thunk and there is nowhere for that to hide.
    """
    def _work():
        return build_query().execute()

    try:
        response = await asyncio.to_thread(_work)
    except Exception:
        # str(e) is NOT interpolated into the response: this API is public.
        logger.exception("Supabase read failed")
        raise HTTPException(status_code=502, detail=DB_FAILURE_DETAIL)
    return getattr(response, "data", None) or []


def _validate_response(instance: Any, schema: dict, contract: str) -> None:
    """Validate an outgoing payload, or fail with a described 5xx.

    Mirrors `reachout/api/server.py`'s pattern: a payload that fails its own
    contract is a server-side fault, reported as such, never leaked as a
    stack trace and never served anyway. The DB has no CHECK constraints on
    `direction`, `confidence`, `interest_avg` or `rank`, so a row that
    violates the contract is reachable in production, not hypothetical.
    """
    try:
        validate_with_formats(instance, schema)
    except jsonschema.ValidationError:
        logger.exception("Payload failed the %s contract", contract)
        raise HTTPException(
            status_code=500,
            detail=f"Response failed the {contract} contract",
        )


def _require_uuid(value: Any, field: str) -> str:
    """4xx on a malformed id, without echoing it back.

    Checked against `UUID_SCHEMA` through the format-enforcing helper, i.e.
    exactly the check the response body is held to. The rejected value is
    never reflected into the detail: `?store_id=<script>` used to come back
    200 with the script tag in a body this module called schema-validated.
    """
    try:
        validate_with_formats(value, UUID_SCHEMA)
    except jsonschema.ValidationError:
        raise HTTPException(status_code=422, detail=f"{field} must be a UUID")
    return value


def _require_timeframe(timeframe: str) -> None:
    """4xx on a timeframe outside `ALLOWED_TIMEFRAMES`.

    Same guard style as `inventory_type` below: an unrecognised value is a
    422, not a silent fall-through to one scale or the other.
    `demand_signals` and `trend_snapshots` hold two measurement scales in
    one table; picking the wrong one silently is exactly the bug this
    parameter exists to close.
    """
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise HTTPException(status_code=422, detail="Unsupported timeframe")


def _as_number(value: Any) -> Optional[float]:
    """Coerce a PostgREST `numeric` to float, or None if it is not one.

    None rather than a substituted default: a value we could not read is not
    a zero, and the schema will reject the None loudly instead of us quietly
    inventing a number.
    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> Optional[int]:
    number = _as_number(value)
    if number is None or number != int(number):
        return None
    return int(number)


# ---------------------------------------------------------------------------
# Confidence. Derived, never asserted.
# ---------------------------------------------------------------------------

def _weakest_confidence(rows: List[dict]) -> str:
    """The weakest label carried by the rows a segment was computed from.

    THE rule for any segment whose inputs carry their own deterministic
    confidence (`demand_signals.confidence`, set by `compute_signals.py`):
    a segment is exactly as trustworthy as its least trustworthy input.

    Written down here because the alternative is what this endpoint used to
    do — hardcode `"high"` — while every contributing row said `low`.
    Confidence is the honesty label on a number; asserting one is worse than
    shipping no label at all.

    No rows, or any row whose label is missing or outside the enum, yields
    `low`: an unlabelled input cannot raise a segment's confidence.
    """
    if not rows:
        return "low"
    labels = [row.get("confidence") for row in rows]
    if any(label not in CONFIDENCE_ORDER for label in labels):
        return "low"
    return min(labels, key=CONFIDENCE_ORDER.index)


def _census_confidence(row_count: int, cap: int) -> str:
    """Confidence for a segment computed by counting rows we actually read.

    `category_mix` and `stock_out_risk` come from `public.products`, which
    carries no confidence column of its own — the numbers are a census, not
    an inference. So the only thing that can make them untrustworthy is not
    having seen the whole population:

    - read complete (fewer rows came back than the cap) -> `high`: every row
      in scope was counted, the shares are exact.
    - read truncated (the cap was reached) -> `low`: the shares describe a
      prefix of the table, not the table, and we cannot tell how wrong they
      are.

    Deliberately conservative at the boundary: a read that returns exactly
    `cap` rows is treated as truncated even when it happens to be complete.
    There is no `medium` here because there is no third thing to say.
    """
    return "high" if row_count < cap else "low"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/demand/api/health")
async def health():
    return {"status": "ok"}


@app.get("/demand/api/trends")
async def get_trends(
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    timeframe: str = DEFAULT_TIMEFRAME,
):
    """Newest captures first, bounded. Never the whole table."""
    _require_timeframe(timeframe)
    data = await _fetch(
        lambda: get_client()
        .table("trend_snapshots")
        .select(TREND_COLUMNS)
        .eq("timeframe", timeframe)
        .order("captured_at", desc=True)
        .limit(limit)
    )

    for item in data:
        _validate_response(item, TREND_SCHEMA, "trend_snapshot")

    return data


@app.get("/demand/api/signals")
async def get_signals(
    window: Optional[str] = None,
    direction: Optional[str] = None,
    keyword: Optional[str] = None,
    order: str = "rank",
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    """Signals ordered by `rank` (best first) by default, bounded.

    `order="window_start"` is opt-in only -- flipping the default would
    silently change this endpoint's existing, documented contract for every
    caller who never asked for a time series. It sorts ascending
    (chronological), which is what a caller building a demand-over-time
    chart for one `keyword` needs.
    """
    _require_timeframe(timeframe)
    if order not in ("rank", "window_start"):
        raise HTTPException(status_code=422, detail="Unsupported order")

    def _build():
        query = (
            get_client()
            .table("demand_signals")
            .select(SIGNAL_COLUMNS)
            .eq("timeframe", timeframe)
        )
        if window:
            query = query.eq("window_start", window)
        if direction:
            query = query.eq("direction", direction)
        if keyword:
            query = query.eq("keyword", keyword)
        if order == "window_start":
            query = query.order("window_start")
        else:
            query = query.order("rank")
        return query.limit(limit)

    data = await _fetch(_build)

    for item in data:
        _validate_response(item, SIGNAL_SCHEMA, "demand_signal")

    return data


@app.get("/demand/api/recommendations")
async def get_recommendations(
    store_id: str = Query(..., description="Required. Must be a uuid."),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    """Recommendations for one store, newest first, bounded.

    `store_id` is REQUIRED. `recommendations_response.schema.json` requires
    it and is a DO-NOT-MODIFY contract, so the endpoint requires it too. The
    previous behaviour — fabricating
    `00000000-0000-0000-0000-000000000000` to get past the validator — put a
    store that does not exist into a response body to satisfy a contract
    check. Inventing data to pass validation is the failure the validator is
    there to catch.
    """
    _require_uuid(store_id, "store_id")

    data = await _fetch(
        lambda: get_client()
        .table("recommendations")
        .select(RECOMMENDATION_COLUMNS)
        .eq("store_id", store_id)
        .order("created_at", desc=True)
        .limit(limit)
    )

    response_data = {"store_id": store_id, "recommendations": data}
    _validate_response(response_data, REC_RESPONSE_SCHEMA, "recommendations_response")
    return response_data


def _top_movers_points(signals: List[dict]) -> List[dict]:
    """One point per keyword, best rank first, bounded.

    The live path used to emit one point per signal ROW, so three weekly
    windows for `cerveza` produced three `cerveza` points, unsorted and
    unlimited — a different shape from the committed fixture the frontend
    builds against, which defeats the entire point of shipping a fixture
    first.

    Deduplication rule, fully deterministic so the same table always yields
    the same chart: order by `rank` ascending (dense rank within window, so
    lowest is strongest), ties broken by the most recent `window_end`, then
    by keyword alphabetically. Keep the first row seen per keyword.
    """
    def _rank_key(row):
        rank = _as_number(row.get("rank"))
        # An unrankable row sorts last rather than crashing the comparison.
        return rank if rank is not None else float("inf")

    # Three stable sorts, weakest key first: the result is rank asc, then
    # window_end desc, then keyword asc.
    ordered = sorted(signals, key=lambda row: str(row.get("keyword") or ""))
    ordered.sort(key=lambda row: str(row.get("window_end") or ""), reverse=True)
    ordered.sort(key=_rank_key)

    seen = set()
    points = []
    for row in ordered:
        keyword = row.get("keyword")
        if keyword in seen:
            continue
        seen.add(keyword)
        points.append(
            {
                # .get() throughout: a row missing `keyword` used to be a
                # raw 500. Now it becomes a null the contract rejects with a
                # described error.
                "keyword": row.get("keyword"),
                "category": row.get("category"),
                "interest_avg": _as_number(row.get("interest_avg")),
                "delta_pct": _as_number(row.get("delta_pct")),
                "direction": row.get("direction"),
            }
        )
        if len(points) >= TOP_MOVERS_MAX_POINTS:
            break
    return points


def _contributing_signal_rows(signals: List[dict], points: List[dict]) -> List[dict]:
    """The rows the returned points were actually built from.

    Confidence is derived from these and only these — not from rows that
    were read and then dropped by the per-keyword dedupe or the point cap.
    """
    keywords = {point["keyword"] for point in points}
    contributing = {}
    for row in signals:
        keyword = row.get("keyword")
        if keyword in keywords and keyword not in contributing:
            contributing[keyword] = row
    return list(contributing.values())


def _composition_points(products: List[dict]) -> List[dict]:
    """`category_mix`: a census of the products actually read."""
    categories = [
        str(row.get("category")).strip()
        for row in products
        if row.get("category") and str(row.get("category")).strip()
    ]
    total = len(categories)
    if total == 0:
        return []
    counts = Counter(categories)
    return [
        {
            "category": category,
            "share_pct": round((count / total) * 100, 2),
            "product_count": count,
        }
        for category, count in sorted(counts.items())
    ]


def _stock_out_points(products: List[dict]) -> List[dict]:
    """`stock_out_risk`, computed from `products.stock_qty`.

    Before W1-FIX-F this was `at_risk = total // 2` over a query that never
    selected `stock_qty` at all: every even-sized category reported exactly
    50% risk, a number with no input. It is now a count of SKUs at or below
    `STOCK_OUT_QTY_THRESHOLD`.

    Two documented scoping decisions:

    - **Every category in scope gets a point**, not only categories that
      happen to carry a `rising` signal. Stock-out risk is a property of
      stock; a point shape of `{category, at_risk_count, total_count,
      risk_pct}` has no field in which to disclose "…among rising
      categories", so a hidden filter would silently drop the categories
      whose shelves are emptiest.
    - **A SKU with an unreadable `stock_qty` is excluded from BOTH counts**,
      so `risk_pct` is always computed over the population it was measured
      on. A category with no readable stock level at all is omitted: its
      risk cannot be computed, so it is not reported. (`products.stock_qty`
      is `not null` in `reachout/data/schema.sql`, so this is a guard, not
      an expected path.)
    """
    totals: Dict[str, int] = Counter()
    at_risk: Dict[str, int] = Counter()
    for row in products:
        category = row.get("category")
        if not category or not str(category).strip():
            continue
        stock_qty = _as_int(row.get("stock_qty"))
        if stock_qty is None:
            continue
        category = str(category).strip()
        totals[category] += 1
        if stock_qty <= STOCK_OUT_QTY_THRESHOLD:
            at_risk[category] += 1

    return [
        {
            "category": category,
            "at_risk_count": at_risk.get(category, 0),
            "total_count": total,
            "risk_pct": round((at_risk.get(category, 0) / total) * 100, 2),
        }
        for category, total in sorted(totals.items())
        if total > 0
    ]


@app.get("/demand/api/analytics")
async def get_analytics(
    store_id: Optional[str] = Query(
        None,
        description=(
            "Optional uuid. Scopes the inventory-derived segments "
            "(category_mix, stock_out_risk) to that store's products."
        ),
    ),
    inventory_type: str = "convenience_store",
    timeframe: str = DEFAULT_TIMEFRAME,
):
    """Three chart segments for the retail dashboard.

    `store_id` is USED, not merely accepted: it filters `public.products`, so
    `category_mix` and `stock_out_risk` describe that store's shelves. It
    does not touch `top_movers` — `demand.demand_signals` has no store
    dimension by design (search interest is ES-MD wide, per the caveat), and
    pretending otherwise would be the same class of lie as the numbers this
    fix removed. It is still not an authorization subject: no auth (D2).

    `timeframe` selects which of the two `demand_signals` scales
    `top_movers` reads (see `ALLOWED_TIMEFRAMES`). It is NOT applied to
    `public.products`: `category_mix` and `stock_out_risk` are a census of
    inventory, not a read of search signals, and are timeframe-independent.
    """
    if inventory_type != "convenience_store":
        raise HTTPException(status_code=422, detail="Unsupported inventory_type")

    _require_timeframe(timeframe)

    if store_id is not None:
        _require_uuid(store_id, "store_id")

    source = os.environ.get("DEMAND_ANALYTICS_SOURCE", "fixture")

    if source != "live":
        # Fixture mode is store-agnostic by construction and says so in
        # `generated_from`; it is a canned document, not this store's data.
        with open(ANALYTICS_FIXTURE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _validate_response(data, ANALYTICS_SCHEMA, "analytics_response")
        return data

    # The main signals query used to order by `rank` across every window in
    # the table and take the top ANALYTICS_SIGNALS_CAP rows. With a year of
    # history that slices off everything except the best few ranks --
    # `top_movers` would show a handful of perennial high-volume staples and
    # almost none of the actual movers. Resolving the latest `window_start`
    # first and constraining the main query to it bounds the read to one
    # week, so the cap below is a backstop again, not the primary bound.
    latest_window_rows = await _fetch(
        lambda: get_client()
        .table("demand_signals")
        .select("window_start")
        .eq("timeframe", timeframe)
        .order("window_start", desc=True)
        .limit(1)
    )
    latest_window = (
        latest_window_rows[0].get("window_start") if latest_window_rows else None
    )

    if latest_window is None:
        # No window at all for this timeframe: still a valid, shaped
        # response with empty `points` arrays, not an error --
        # `analytics_response.schema.json` documents that shape as valid.
        signals: List[dict] = []
    else:
        signals = await _fetch(
            lambda: get_client()
            .table("demand_signals")
            .select(ANALYTICS_SIGNAL_COLUMNS)
            .eq("timeframe", timeframe)
            .eq("window_start", latest_window)
            .order("rank")
            .limit(ANALYTICS_SIGNALS_CAP)
        )

    def _products_query():
        query = (
            get_client()
            .schema("public")
            .table("products")
            .select(ANALYTICS_PRODUCT_COLUMNS)
        )
        if store_id:
            query = query.eq("store_id", store_id)
        return query.order("category").limit(ANALYTICS_PRODUCTS_CAP)

    products = await _fetch(_products_query)

    top_movers_points = _top_movers_points(signals)
    contributing = _contributing_signal_rows(signals, top_movers_points)
    census = _census_confidence(len(products), ANALYTICS_PRODUCTS_CAP)

    response_data = {
        "inventory_type": "convenience_store",
        "generated_from": "live",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "caveat": CANONICAL_CAVEAT,
        "segments": {
            "top_movers": {
                "confidence": _weakest_confidence(contributing),
                "points": top_movers_points,
            },
            "category_mix": {
                "confidence": census,
                "points": _composition_points(products),
            },
            "stock_out_risk": {
                "confidence": census,
                "points": _stock_out_points(products),
            },
        },
    }

    _validate_response(response_data, ANALYTICS_SCHEMA, "analytics_response")
    return response_data


@app.get("/demand/api/rising-queries")
async def get_rising_queries(
    response: Response,
    parent_keyword: Optional[str] = None,
    include: str = "commercial",
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=RISING_QUERIES_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """Discovery-pass queries, scored for commercial relevance, bounded.

    `relevance_score` / `relevance_tier` / `relevance_reasons` / `cluster_id`
    are not columns -- `demand/api/relevance.py:annotate()` computes them at
    read time from `query` and `parent_keyword`. That forces a specific,
    non-obvious order of operations, and getting it wrong breaks clustering
    silently, exactly at the scale where it matters (see the task's
    Addendum). In this order, and no other:

    1. Bound and order the database read itself
       (`RISING_QUERIES_READ_CAP`), ordered by `id`. `id` is the primary
       key, so it can never tie between rows -- unlike `captured_at`, which
       many rows in one parent keyword's discovery pass share exactly (see
       `demand/ingest/rising_store.py:build_rows`). An order that can tie
       leaves the tied rows in whatever order Postgres's physical storage
       happens to hand back, which is exactly the non-determinism this
       endpoint must not have.
    2. `annotate()` the FULL set just read, in ONE call. `annotate()`
       assigns `cluster_id` by merging cluster keys ACROSS the batch handed
       to it (`_merge_subset_keys`), so calling it once per page would make
       a row's `cluster_id` depend on which other rows happened to land on
       that page -- the same query could carry two different cluster ids on
       page 1 and page 2. Calling it once, over everything read, is what
       lets a twelve-row cluster like `gafas eclipse` collapse to one card
       no matter how the caller later slices the response.
    3. Filter by `relevance_tier` in Python. `include="commercial"` (the
       default) keeps only rows the scorer tiers `commercial`;
       `include="all"` keeps every row, for auditing the heuristic itself.
       Relevance is computed at read time, not stored in the database, so
       this filter cannot be pushed into the Supabase query.
    4. Apply `offset` then `limit` LAST, after tiering, as a plain slice of
       the already-annotated, already-filtered list. Both bound what the
       caller sees, never the clustering input. `X-Total-Count` is set from
       the pre-slice length, so a caller can always tell whether it holds
       the whole filtered set or one page of it, and page the rest with
       `offset` without any row's `cluster_id` changing underneath it.
    """
    if include not in ALLOWED_RISING_QUERY_INCLUDES:
        raise HTTPException(status_code=422, detail="Unsupported include")

    def _build():
        query = (
            get_client()
            .table("rising_queries")
            .select(RISING_QUERY_COLUMNS)
        )
        if parent_keyword:
            query = query.eq("parent_keyword", parent_keyword)
        return query.order("id").limit(RISING_QUERIES_READ_CAP)

    data = await _fetch(_build)

    annotated = annotate(data)

    if include == "commercial":
        annotated = [row for row in annotated if row.get("relevance_tier") == "commercial"]

    # Set BEFORE slicing: X-Total-Count is the size of the tier-filtered
    # set, which is exactly what the caller needs to know it is looking at
    # a page. Counting after the slice would report the page size and make
    # the header useless. It is a header and not a body field on purpose --
    # rising_query.schema.json is frozen with additionalProperties: false,
    # and the response is a bare array with nowhere to put an envelope.
    response.headers["X-Total-Count"] = str(len(annotated))
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    annotated = annotated[offset:offset + limit]

    for item in annotated:
        _validate_response(item, RISING_QUERY_SCHEMA, "rising_query")

    return annotated
