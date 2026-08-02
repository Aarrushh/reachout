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

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "shared" / "schemas"

def load_schema(name: str) -> dict:
    with open(SCHEMAS_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)

TREND_SCHEMA = load_schema("trend_snapshot.schema.json")
SIGNAL_SCHEMA = load_schema("demand_signal.schema.json")
REC_RESPONSE_SCHEMA = load_schema("recommendations_response.schema.json")

@lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY not set")
    # In Supabase python client, you can specify schema in ClientOptions
    from supabase.client import ClientOptions
    return create_client(url, key, options=ClientOptions(schema="demand"))

app = FastAPI(title="Demand API")

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
