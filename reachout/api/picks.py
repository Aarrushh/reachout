import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from api.supa import get_client as _supa_client
from api.madrid import match_barrio
from scripts import validate

router = APIRouter()

# Mirrors api.server._V2_PRODUCT_FIELDS (server.py:98) — exactly the columns
# picks_response.schema.json allows (additionalProperties: false). The real
# `products` table has more columns (an `embedding` vector, timestamps); an
# unqualified select("*") pulls those over the wire and, once echoed into the
# response body, fails schema validation on every request.
#
# Duplicated here rather than imported: server.py imports this module's
# `router` (line 93) before it defines _V2_PRODUCT_FIELDS (line 98), so
# `from api.server import _V2_PRODUCT_FIELDS` would try to read an attribute
# off a partially-initialized module and raise ImportError (circular import).
_PICKS_PRODUCT_FIELDS = ("id,name,description,category,price,stock_qty,store_id,"
                         "neighbourhood,tags,image_url")
_PICKS_PRODUCT_FIELD_SET = set(_PICKS_PRODUCT_FIELDS.split(","))

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
        # Fetch all stores — only rating is ever read below, id is the join
        # key; no need to pull the rest of the row (or a vector column) over
        # the wire.
        stores_res = _supa_client().table("stores").select("id,rating").execute()
        stores_dict = {s["id"]: s for s in stores_res.data}

        # Fetch products — explicit column list, see _PICKS_PRODUCT_FIELDS.
        products_query = _supa_client().table("products").select(_PICKS_PRODUCT_FIELDS)
        if canonical_neighbourhood:
            products_query = products_query.eq("neighbourhood", canonical_neighbourhood)

        products_res = products_query.execute()
        return stores_dict, products_res.data

    try:
        stores_dict, all_products = await asyncio.to_thread(_q)
    except Exception:
        raise HTTPException(status_code=502, detail="Supabase error")

    # Defensive projection: the select() above already narrows columns on a
    # real Supabase client, but nothing in-process enforces that (e.g. the
    # test fake echoes back whatever the fixture put in, ignoring the column
    # list). Drop anything outside the schema's allowed keys here too, so a
    # stray column can never reach the additionalProperties:false validation
    # below regardless of what the client returned.
    all_products = [
        {k: v for k, v in p.items() if k in _PICKS_PRODUCT_FIELD_SET}
        for p in all_products
    ]

    # Filter out out-of-stock products and calculate score
    scored_products = []
    for p in all_products:
        if p.get("stock_qty", 0) <= 0:
            continue

        store = stores_dict.get(p.get("store_id"), {})
        score = store.get("rating") or 0.0
        
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
            score = store.get("rating") or 0.0
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
