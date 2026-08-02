import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

# Add parent directory to path so we can run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demand.api.app import get_client
from demand.ingest.keywords import build_universe, normalize_keyword
from demand.ingest.trends_client import get_provider
from demand.ingest.snapshot_store import store_snapshots
from demand.scripts.compute_signals import compute_signals
from demand.scripts.recommend import build_recommendations

#: The provider window every capture is taken over. `today 3-m` is ~13
#: weekly windows, so a single capture's series can clear
#: `compute_signals.HIGH_MIN_WINDOWS` (8) and the `high` confidence tier is
#: reachable in production. The previous `today 1-m` (~4 weekly windows)
#: made `high` structurally impossible: the threshold is the spec
#: (IMPLEMENTATION_PLAN_V2.md 5.6, fixtures README) and the ingest window
#: was the side that was wrong, so the window moved, not the threshold.
INGEST_TIMEFRAME = "today 3-m"

INGEST_GEO = "ES-MD"


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
    

    print(f"[Ingest] Fetching interest_over_time ({INGEST_TIMEFRAME})...")
    time_series = provider.interest_over_time(universe, geo=INGEST_GEO, timeframe=INGEST_TIMEFRAME)

    # Pre-fetch existing snapshots for this date to preserve IDs
    existing_snap_res = client.table("trend_snapshots").select("id,keyword,geo,timeframe,captured_date").execute()
    existing_snap_map = {}
    if hasattr(existing_snap_res, "data") and existing_snap_res.data:
        existing_snap_map = {
            (r["keyword"], r["geo"], r["timeframe"], r["captured_date"]): r["id"]
            for r in existing_snap_res.data
        }
        
    for kw in universe:
        series = time_series.get(kw, [])
        region_breakdown = provider.interest_by_region(kw, geo=INGEST_GEO)

        captured_date = now_utc[:10]
        key = (kw, INGEST_GEO, INGEST_TIMEFRAME, captured_date)
        snap_id = existing_snap_map.get(key, str(uuid.uuid4()))

        snapshot = {
            "id": snap_id,
            "keyword": kw,
            "geo": INGEST_GEO,
            "timeframe": INGEST_TIMEFRAME,
            "provider": provider_name,
            "captured_at": now_utc,
            "series": series,
            "region_breakdown": region_breakdown if region_breakdown else []
        }
        snapshots.append(snapshot)

    
    print(f"[Ingest] Captured {len(snapshots)} snapshots")
    
    if not dry_run:
        store_snapshots(snapshots, client)
        print("[Ingest] Stored snapshots in DB")
    
    # 3. Compute Signals
    result = client.table('products').select('category').execute()
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

    print("[Ingest] Finished.")

def main():
    parser = argparse.ArgumentParser(description="Demand Ingest Chain")
    parser.add_argument("--dry-run", action="store_true", help="Print counts, write nothing")
    parser.add_argument("--provider", type=str, default=os.environ.get("DEMAND_TRENDS_PROVIDER", "trendspy"), help="Trends provider (trendspy or fixture)")
    
    args = parser.parse_args()
    run_chain(provider_name=args.provider, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
