import asyncio
import json
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import jsonschema
from supabase import Client, create_client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import threading


SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "shared" / "schemas"

def load_schema(name: str) -> dict:
    with open(SCHEMAS_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)

TREND_SCHEMA = load_schema("trend_snapshot.schema.json")
SIGNAL_SCHEMA = load_schema("demand_signal.schema.json")
REC_RESPONSE_SCHEMA = load_schema("recommendations_response.schema.json")
ANALYTICS_SCHEMA = load_schema("analytics_response.schema.json")

@lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY not set")
    # In Supabase python client, you can specify schema in ClientOptions
    from supabase.client import ClientOptions
    return create_client(url, key, options=ClientOptions(schema="demand"))



@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if os.environ.get("DEMAND_INGEST_CRON") == "1":
        from demand.scripts.run_ingest import run_chain
        scheduler = AsyncIOScheduler()
        # Run daily
        
        async def run_chain_async():
            import asyncio
            await asyncio.to_thread(run_chain, provider_name="trendspy", dry_run=False)

        scheduler.add_job(
            run_chain_async,

            'cron', hour=0, minute=0
        )
        scheduler.start()
        print("Started DEMAND_INGEST_CRON daily job")
        
    yield
    
    if scheduler:
        scheduler.shutdown()
        print("Stopped DEMAND_INGEST_CRON daily job")

app = FastAPI(title="Demand API", lifespan=lifespan)



app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://localhost:5173$|^https://.*\.netlify\.app$",
    allow_methods=["GET"],
    allow_headers=["*"],
)

async def _execute_query(query) -> List[dict]:
    try:
        response = await asyncio.to_thread(query.execute)
        return response.data
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Database dependency failed: {str(e)}")

@app.get("/demand/api/health")
async def health():
    return {"status": "ok"}

@app.get("/demand/api/trends")
async def get_trends():
    client = get_client()
    query = client.table("trend_snapshots").select("id, keyword, geo, timeframe, provider, captured_at, series, region_breakdown")
    data = await _execute_query(query)
    
    for item in data:
        # Schema validation before returning
        jsonschema.validate(instance=item, schema=TREND_SCHEMA)
        
    return data

@app.get("/demand/api/signals")
async def get_signals(
    window: Optional[str] = None,
    direction: Optional[str] = None
):
    client = get_client()
    query = client.table("demand_signals").select("id, keyword, category, geo, window_start, window_end, interest_avg, delta_pct, direction, rank, confidence, snapshot_ids, computed_at")
    
    if window:
        query = query.eq("window_start", window)
    if direction:
        query = query.eq("direction", direction)
        
    data = await _execute_query(query)
    
    for item in data:
        # Schema validation
        jsonschema.validate(instance=item, schema=SIGNAL_SCHEMA)
        
    return data

@app.get("/demand/api/recommendations")
async def get_recommendations(store_id: Optional[str] = None):
    if not store_id:
        response_data = {
            "store_id": "00000000-0000-0000-0000-000000000000",
            "recommendations": []
        }
        jsonschema.validate(instance=response_data, schema=REC_RESPONSE_SCHEMA)
        return response_data

    client = get_client()
    query = client.table("recommendations").select("id, store_id, signal_id, headline, body, action, confidence, caveat, created_at")
    query = query.eq("store_id", store_id)
        
    data = await _execute_query(query)
    
    response_data = {
        "store_id": store_id,
        "recommendations": data
    }
    
    # Schema validation
    jsonschema.validate(instance=response_data, schema=REC_RESPONSE_SCHEMA)
    
    return response_data

@app.get("/demand/api/analytics")
async def get_analytics(store_id: Optional[str] = None, inventory_type: str = "convenience_store"):
    if inventory_type != "convenience_store":
        raise HTTPException(status_code=422, detail="Unsupported inventory_type")
        
    source = os.environ.get("DEMAND_ANALYTICS_SOURCE", "fixture")
    
    if source != "live":
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "analytics_convenience_store.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        jsonschema.validate(instance=data, schema=ANALYTICS_SCHEMA)
        return data
        
    client = get_client()
    try:
        signals_response = await asyncio.to_thread(client.table("demand_signals").select("keyword, category, interest_avg, delta_pct, direction, confidence").execute)
        signals = signals_response.data
        
        products_response = await asyncio.to_thread(client.schema("public").table("products").select("category").execute)
        products = products_response.data
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Database dependency failed: {str(e)}")

    import datetime
    from collections import Counter
    
    top_movers_points = []
    for s in signals:
        top_movers_points.append({
            "keyword": s["keyword"],
            "category": s.get("category"),
            "interest_avg": float(s["interest_avg"]),
            "delta_pct": float(s["delta_pct"]),
            "direction": s["direction"]
        })
        
    product_categories = [p.get("category") for p in products if p.get("category")]
    total_products = len(product_categories)
    cat_counts = Counter(product_categories)
    
    cat_mix_points = []
    if total_products > 0:
        for cat, count in cat_counts.items():
            cat_mix_points.append({
                "category": cat,
                "share_pct": float(round((count / total_products) * 100, 2)),
                "product_count": count
            })
            
    stock_out_points = []
    rising_cats = set(s.get("category") for s in signals if s.get("direction") == "rising" and s.get("category"))
    for cat in rising_cats:
        total = cat_counts.get(cat, 0)
        at_risk = total // 2
        stock_out_points.append({
            "category": cat,
            "at_risk_count": at_risk,
            "total_count": total,
            "risk_pct": float(round((at_risk / total) * 100, 2)) if total > 0 else 0.0
        })

    response_data = {
        "inventory_type": "convenience_store",
        "generated_from": "live",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "caveat": "Basado en interés de búsqueda en Madrid, no en compras reales.",
        "segments": {
            "top_movers": {
                "confidence": "high",
                "points": top_movers_points
            },
            "category_mix": {
                "confidence": "medium",
                "points": cat_mix_points
            },
            "stock_out_risk": {
                "confidence": "low",
                "points": stock_out_points
            }
        }
    }
    
    jsonschema.validate(instance=response_data, schema=ANALYTICS_SCHEMA)
    return response_data
