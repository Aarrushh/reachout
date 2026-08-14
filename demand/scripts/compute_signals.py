"""Derive `demand.demand_signals` rows from raw trend snapshots.

Pure Python and deterministic by contract (`demand/CLAUDE.md`): the same
snapshots in produce byte-identical rows out, in the same order, no matter
what order the snapshots arrive in and no matter how many times the chain
is re-run. There is no `uuid4()` here on purpose -- see
`DEMAND_ID_NAMESPACE`.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from demand.ingest.keywords import normalize_keyword
from demand.shared.validation import validate_with_formats

# ---------------------------------------------------------------------------
# Deterministic identity
# ---------------------------------------------------------------------------
#: Namespace for every id this service mints. Derived in the open so any
#: reader can recompute an id by hand:
#:
#:     uuid5(NAMESPACE_DNS, "demand.reachout")
#:         == 4ee47505-4a32-5e02-bc8a-d6fb147fa272
#:
#: A row's id is a pure function of its natural key -- the same tuple the
#: DB's unique index dedupes on (`demand/data/schema.sql`,
#: `demand_signals_dedupe_idx`). That is what makes a re-run of the same
#: window idempotent in row IDENTITY and not merely in row COUNT: the
#: `on_conflict` upsert updates the row it already wrote instead of
#: minting a new id for the same logical signal.
DEMAND_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "demand.reachout")

#: Field separator inside a natural key. `|` cannot occur in a date or in
#: `geo`, and a keyword containing one would still hash unambiguously
#: because the field count is fixed.
NATURAL_KEY_SEP = "|"


def signal_id(keyword: str, geo: str, timeframe: str,
              window_start: str, window_end: str) -> str:
    """The id of the signal row for this natural key. Same key -> same id, forever.

    Natural key, verbatim:
        "demand_signal|<keyword>|<geo>|<timeframe>|<window_start>|<window_end>"
    hashed with `uuid5` under `DEMAND_ID_NAMESPACE`. `uuid5` output is a
    real RFC-4122 UUID, so it satisfies the schema's `format: uuid`.

    `timeframe` is in the key because it is in the table's unique index, and
    the two must agree or the row cannot be written at all. `id` is the
    PRIMARY key: leave `timeframe` out here and the `today 3-m` and
    `today 12-m` signals for one keyword and week hash to the SAME uuid, so
    the backfill collides on the primary key while `on_conflict` is pointed
    at a different tuple entirely. The upsert does not resolve that -- it
    fails, after the searches are paid for.

    It is also the honest key. Google's 0-100 index is scaled to the window
    requested and this pipeline rescales onto an anchor on top of that, so
    the same keyword in the same calendar week genuinely reads differently at
    3-m and at 12-m. Two readings, two rows. Same rule as `gprop` in the
    rising_queries key and `timeframe` in `snapshot_id`.
    """
    natural_key = NATURAL_KEY_SEP.join(
        ["demand_signal", keyword, geo, timeframe, window_start, window_end]
    )
    return str(uuid.uuid5(DEMAND_ID_NAMESPACE, natural_key))


# ---------------------------------------------------------------------------
# Thresholds (IMPLEMENTATION_PLAN_V2.md 5.6 -- deterministic, never model-set)
# ---------------------------------------------------------------------------
#: A window is `rising`/`falling` only at or beyond +/-15% vs the prior
#: window; strictly inside the band it is `flat`. The boundary is
#: inclusive: exactly +15.00 is rising, exactly -15.00 is falling.
DIRECTION_THRESHOLD_PCT = 15.0

#: `high` needs >= 8 weekly windows of gap-free data. Reachable ONLY
#: because `run_ingest.py` fetches the `today 3-m` window (~13 weekly
#: windows per capture) -- with the `today 1-m` window it used to fetch
#: (~4 windows) no production signal could ever be labelled `high`, which
#: is the bug this constant's comment exists to prevent recurring. If the
#: ingest window is ever narrowed, this tier goes dead again.
HIGH_MIN_WINDOWS = 8
HIGH_MIN_INTEREST = 20.0

#: `medium` needs >= 4 weekly windows -- inside `today 1-m` as well, which
#: is why the miscalibration was invisible: medium rows kept appearing.
MEDIUM_MIN_WINDOWS = 4
MEDIUM_MIN_INTEREST = 10.0

#: `high` additionally needs the direction to hold across this many
#: consecutive windows, the current one included.
STABLE_DIRECTION_WINDOWS = 3


def load_schema(schema_name: str) -> dict:
    schema_path = os.path.join(os.path.dirname(__file__), "..", "shared", "schemas", schema_name)
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_iso_week_window(date_str: str) -> tuple[str, str]:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    # Monday is 0, Sunday is 6
    start = dt - timedelta(days=dt.weekday())
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def _capture_key(snapshot: Dict[str, Any]) -> Tuple[float, str, str]:
    """Total, deterministic ordering over snapshots by capture recency.

    Returned as (utc timestamp, raw captured_at, snapshot id) so that two
    captures with the identical timestamp still order deterministically
    instead of depending on the order they were passed in. An unparseable
    `captured_at` sorts below every real one rather than raising --
    `format: date-time` is currently unenforced in this environment (see
    `demand/shared/validation.py`), so it can reach here.
    """
    raw = str(snapshot.get("captured_at") or "")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        stamp = parsed.timestamp()
    except ValueError:
        stamp = float("-inf")
    return (stamp, raw, str(snapshot["id"]))


def compute_signals(snapshots: List[Dict[str, Any]], category_map: Dict[str, str] = None, computed_at: str = None) -> List[Dict[str, Any]]:
    """
    Derives demand.demand_signals rows from raw trend snapshots.
    Pure Python derivation: windowed interest average, week-over-week delta %,
    direction, rank, and confidence labeling.

    `category_map` is keyed by NORMALISED keyword (see
    `demand.ingest.keywords.normalize_keyword`), never by raw keyword: the
    universe preserves each keyword's original casing while the map is
    built from `products.category`, and the two casings need not agree.

    Every snapshot is validated against `trend_snapshot.schema.json` before
    it is read. HARD RULE: rows read back from `demand.trend_snapshots`
    carry the DB-only `captured_date` column, which that schema
    (`additionalProperties: false`) rejects. Pass snapshots as built/sent,
    or strip `captured_date` first; never hand this function a `select("*")`
    result.
    """
    if category_map is None:
        category_map = {}

    if computed_at is None:
        computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    schema = load_schema("demand_signal.schema.json")
    snapshot_schema = load_schema("trend_snapshot.schema.json")

    # Phase 1: Group points into windows per keyword/geo.
    #
    # Values are bucketed by CAPTURE, not merged: Google Trends re-normalises
    # every request to its own 0-100 scale, so two requests' values for the
    # same week are not on a comparable scale and averaging them (50 and 90
    # -> 70.0) produces a number that means nothing. Within one capture the
    # scale IS shared, so several daily points inside a week are averaged as
    # before. Across captures, most recent capture wins -- deterministic,
    # and the freshest normalisation is the one the rest of that capture's
    # series is expressed in.
    kw_geo_windows: Dict[Tuple[str, str], Dict[Tuple[str, str], Dict[Tuple[float, str, str], List[float]]]] = {}

    for snap in snapshots:
        validate_with_formats(instance=snap, schema=snapshot_schema)

        kw = snap["keyword"]
        geo = snap["geo"]
        capture_key = _capture_key(snap)

        # `timeframe` partitions here for the same reason `geo` does. Google
        # scales its 0-100 index to the window requested, so a week measured
        # inside `today 3-m` and the same week measured inside `today 12-m`
        # are two readings on two scales. Grouping them together would average
        # across scales -- exactly the merge the capture-bucketing above
        # exists to prevent, one level up.
        key = (kw, geo, snap["timeframe"])
        if key not in kw_geo_windows:
            kw_geo_windows[key] = {}

        for pt in snap["series"]:
            w_start, w_end = get_iso_week_window(pt["date"])
            w_key = (w_start, w_end)
            if w_key not in kw_geo_windows[key]:
                kw_geo_windows[key][w_key] = {}
            kw_geo_windows[key][w_key].setdefault(capture_key, []).append(pt["value"])

    # Compute interest_avg per window per keyword
    window_signals: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}

    for (kw, geo, timeframe), windows in sorted(kw_geo_windows.items()):
        sorted_window_keys = sorted(windows.keys())  # Sorts chronologically

        # Check for provider gaps
        has_gap = False
        for i in range(1, len(sorted_window_keys)):
            prev_end = datetime.strptime(sorted_window_keys[i-1][1], "%Y-%m-%d").date()
            curr_start = datetime.strptime(sorted_window_keys[i][0], "%Y-%m-%d").date()
            if (curr_start - prev_end).days > 1:
                has_gap = True

        series_data = []
        for w_key in sorted_window_keys:
            captures = windows[w_key]
            winning_capture = max(captures)  # most recent capture wins
            vals = captures[winning_capture]
            avg = round(sum(vals) / len(vals), 2) if vals else 0.0
            series_data.append({
                "window_start": w_key[0],
                "window_end": w_key[1],
                "interest_avg": avg,
                # Provenance is the capture the value actually came from,
                # not every capture that happened to touch the window.
                "snapshot_ids": [winning_capture[2]],
            })

        # Compute delta_pct and direction
        for i in range(len(series_data)):
            curr = series_data[i]

            delta_pct = 0.0
            if i > 0:
                prev_avg = series_data[i-1]["interest_avg"]
                if prev_avg > 0:
                    delta_pct = round(((curr["interest_avg"] - prev_avg) / prev_avg) * 100, 2)
                elif curr["interest_avg"] > 0:
                    delta_pct = 100.0

            curr["delta_pct"] = float(delta_pct)

            if delta_pct >= DIRECTION_THRESHOLD_PCT:
                direction = "rising"
            elif delta_pct <= -DIRECTION_THRESHOLD_PCT:
                direction = "falling"
            else:
                direction = "flat"

            curr["direction"] = direction

        # Compute confidence
        for i in range(len(series_data)):
            curr = series_data[i]
            weeks_of_data = i + 1

            if has_gap:
                confidence = "low"
            else:
                stable_direction = False
                if weeks_of_data >= STABLE_DIRECTION_WINDOWS:
                    recent = series_data[i - STABLE_DIRECTION_WINDOWS + 1:i + 1]
                    stable_direction = len({row["direction"] for row in recent}) == 1

                if (
                    weeks_of_data >= HIGH_MIN_WINDOWS
                    and curr["interest_avg"] >= HIGH_MIN_INTEREST
                    and stable_direction
                ):
                    confidence = "high"
                elif weeks_of_data >= MEDIUM_MIN_WINDOWS and curr["interest_avg"] >= MEDIUM_MIN_INTEREST:
                    confidence = "medium"
                else:
                    confidence = "low"

            curr["confidence"] = confidence
            curr["keyword"] = kw
            curr["geo"] = geo
            curr["timeframe"] = timeframe
            # Normalised lookup: the map is keyed by normalized_keyword(),
            # the universe keeps the original casing. An exact-match lookup
            # here missed every time in production and stamped every row
            # with category=None.
            curr["category"] = category_map.get(normalize_keyword(kw), None)

            # Rank is per (window, geo, timeframe): ES-CT and ES-MD are
            # separate markets and separate 0-100 scales, so ranking them
            # against each other would be meaningless -- and would make the
            # output depend on which geos happened to be in the batch.
            # `timeframe` joins the key on identical grounds: a 3-month and a
            # 12-month capture of the same week are different scales too, and
            # ranking across them would let a backfill reshuffle the ranks of
            # rows it has no business touching.
            w_key = (curr["window_start"], curr["window_end"], geo, timeframe)
            if w_key not in window_signals:
                window_signals[w_key] = []
            window_signals[w_key].append(curr)

    final_signals = []

    # Compute rank per window/geo and assemble final signals
    for w_key, signals in window_signals.items():
        # Sort by interest_avg descending, then keyword ascending
        signals.sort(key=lambda x: (-x["interest_avg"], x["keyword"]))

        rank = 1
        for i in range(len(signals)):
            if i > 0 and signals[i]["interest_avg"] < signals[i-1]["interest_avg"]:
                rank += 1

            signal = {
                "id": signal_id(
                    signals[i]["keyword"],
                    signals[i]["geo"],
                    signals[i]["timeframe"],
                    signals[i]["window_start"],
                    signals[i]["window_end"],
                ),
                "keyword": signals[i]["keyword"],
                "category": signals[i]["category"],
                "geo": signals[i]["geo"],
                "timeframe": signals[i]["timeframe"],
                "window_start": signals[i]["window_start"],
                "window_end": signals[i]["window_end"],
                "interest_avg": float(signals[i]["interest_avg"]),
                "delta_pct": signals[i]["delta_pct"],
                "direction": signals[i]["direction"],
                "rank": rank,
                "confidence": signals[i]["confidence"],
                "snapshot_ids": signals[i]["snapshot_ids"],
                "computed_at": computed_at
            }

            # Validate against schema
            validate_with_formats(instance=signal, schema=schema)
            final_signals.append(signal)

    # Deterministic final sort. Total by construction: (keyword, geo,
    # window) is the natural key, so no two rows can compare equal and the
    # order cannot depend on the order the snapshots arrived in.
    final_signals.sort(
        key=lambda x: (
            x["window_start"],
            x["window_end"],
            x["geo"],
            x["rank"],
            x["keyword"],
        )
    )

    return final_signals
