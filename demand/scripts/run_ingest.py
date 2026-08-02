import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

# Add parent directory to path so we can run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demand.api.app import get_client
from demand.ingest.keywords import build_universe
from demand.ingest.trends_client import get_provider
from demand.ingest.snapshot_store import store_snapshots
from demand.scripts.compute_signals import compute_signals
from demand.scripts.recommend import build_recommendations

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
    

    print("[Ingest] Fetching interest_over_time...")
    time_series = provider.interest_over_time(universe, geo="ES-MD", timeframe="today 1-m")
    
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
        region_breakdown = provider.interest_by_region(kw, geo="ES-MD")
        
        captured_date = now_utc[:10]
        key = (kw, "ES-MD", "today 1-m", captured_date)
        snap_id = existing_snap_map.get(key, str(uuid.uuid4()))
        
        snapshot = {
            "id": snap_id,
            "keyword": kw,
            "geo": "ES-MD",
            "timeframe": "today 1-m",
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
    cat_map = {cat.lower().strip(): cat for cat in db_categories}
    

    signals = compute_signals(snapshots, category_map=cat_map, computed_at=now_utc)
    print(f"[Ingest] Computed {len(signals)} signals")
    
    if signals:
        # Fetch existing signals to preserve their IDs for idempotency
        # Otherwise compute_signals generates new UUIDs and breaks recommendations dedupe
        existing_res = client.table("demand_signals").select("id,keyword,geo,window_start,window_end").execute()
        if hasattr(existing_res, "data") and existing_res.data:
            existing_map = {
                (r["keyword"], r["geo"], r["window_start"], r["window_end"]): r["id"] 
                for r in existing_res.data
            }
            for s in signals:
                key = (s["keyword"], s["geo"], s["window_start"], s["window_end"])
                if key in existing_map:
                    s["id"] = existing_map[key]

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
