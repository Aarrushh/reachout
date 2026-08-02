import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from api.supa import get_client as _supa_client
from api.madrid import match_barrio
from scripts import validate

router = APIRouter()

@router.get("/api/picks")
async def picks(
    neighbourhood: Optional[str] = Query(None),
    limit: int = Query(12, ge=1, le=50)
):
    """Deterministic, diverse product picks from Supabase."""
    
    canonical_neighbourhood = None
    if neighbourhood:
        canonical_neighbourhood = match_barrio(neighbourhood)

    def _q():
        # Fetch all stores
        stores_res = _supa_client().table("stores").select("*").execute()
        stores_dict = {s["id"]: s for s in stores_res.data}

        # Fetch products
        products_query = _supa_client().table("products").select("*")
        if canonical_neighbourhood:
            products_query = products_query.eq("neighbourhood", canonical_neighbourhood)
            
        products_res = products_query.execute()
        return stores_dict, products_res.data

    try:
        stores_dict, all_products = await asyncio.to_thread(_q)
    except Exception:
        raise HTTPException(status_code=502, detail="Supabase error")

    # Filter out out-of-stock products and calculate score
    scored_products = []
    for p in all_products:
        if p.get("stock_qty", 0) <= 0:
            continue
            
        store = stores_dict.get(p.get("store_id"), {})
        score = store.get("rating", 0.0)
        
        scored_products.append({
            "product": p,
            "score": score
        })
        
    # Sort by score descending, then by id ascending for stability
    scored_products.sort(key=lambda x: (-x["score"], x["product"].get("id", "")))
    
    # Group by category
    from collections import defaultdict
    category_buckets = defaultdict(list)
    for sp in scored_products:
        category = sp["product"].get("category", "")
        category_buckets[category].append(sp["product"])
        
    # Round-robin selection
    results = []
    last_category = None
    
    while len(results) < limit and category_buckets:
        best_category = None
        
        available_categories = list(category_buckets.keys())
        if len(available_categories) > 1 and last_category in available_categories:
            candidate_categories = [c for c in available_categories if c != last_category]
        else:
            candidate_categories = available_categories
            
        best_item = None
        best_score_tuple = None
        
        for cat in candidate_categories:
            item = category_buckets[cat][0]
            store = stores_dict.get(item.get("store_id"), {})
            score = store.get("rating", 0.0)
            score_tuple = (-score, item.get("id", ""))
            
            if best_score_tuple is None or score_tuple < best_score_tuple:
                best_score_tuple = score_tuple
                best_item = item
                best_category = cat
                
        results.append(best_item)
        last_category = best_category
        
        category_buckets[best_category].pop(0)
        if not category_buckets[best_category]:
            del category_buckets[best_category]

    body = {
        "picks": results,
        "generated_by": "deterministic"
    }

    ok, err = validate.validate(body, "picks_response.schema.json")
    if not ok:
        raise HTTPException(status_code=500, detail=f"picks_response failed schema: {err}")

    return body
