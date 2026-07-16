"""POST /api/search — NLP product search over Supabase pgvector.

Pipeline: Gemini Flash Lite extracts intent (JSON) || gemini-embedding-001
embeds the raw query (run concurrently) -> match_products RPC (cosine top-K,
optional neighbourhood filter in SQL) -> deterministic re-rank boosting exact
name/brand/in-stock matches -> results + human-readable interpreted_as.
"""

import asyncio
import json
import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api import gemini
from api.madrid import match_barrio
from api.supa import get_client

router = APIRouter()

_RPC_CANDIDATES = 40   # cosine top-K fetched for re-ranking
_MAX_RESULTS = 20

_INTENT_PROMPT = (
    "Extract from this shopping query: item_name (the product being sought, "
    "in the query's own language), item_type (generic kind of product), "
    "brand_hint (brand if any, else null), location (place/neighbourhood "
    "mentioned, else null).\n"
    'Return ONLY JSON: {"item_name": ..., "item_type": ..., '
    '"brand_hint": ..., "location": ...}\n'
    "Query: "
)


class SearchRequest(BaseModel):
    query: str
    neighbourhood: Optional[str] = None


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c)).lower()


def _extract_intent(query: str) -> dict:
    """Gemini intent extraction; on any failure fall back to the raw query."""
    try:
        raw = gemini.chat(
            [{"role": "user", "content": _INTENT_PROMPT + query}],
            temperature=0.0, json_mode=True, max_output_tokens=256,
        )
        intent = json.loads(raw)
        if not isinstance(intent, dict):
            raise ValueError("intent is not an object")
    except Exception:
        intent = {}
    intent.setdefault("item_name", query)
    for k in ("item_type", "brand_hint", "location"):
        intent.setdefault(k, None)
    return intent


def _rerank(rows: list[dict], intent: dict) -> list[dict]:
    """similarity + boosts: exact name > token overlap > brand > in stock."""
    item = _fold(str(intent.get("item_name") or ""))
    item_tokens = {t for t in re.findall(r"\w{3,}", item)}
    brand = _fold(str(intent.get("brand_hint") or "")) or None

    def score(row: dict) -> float:
        s = row.get("similarity") or 0.0
        name = _fold(row["name"])
        hay = name + " " + " ".join(row.get("tags") or [])
        if item and item in name:
            s += 0.30
        elif item_tokens:
            overlap = sum(1 for t in item_tokens if t in hay)
            s += 0.15 * overlap / len(item_tokens)
        if brand and brand in hay:
            s += 0.10
        if (row.get("stock_qty") or 0) > 0:
            s += 0.05
        return s

    ranked = sorted(rows, key=score, reverse=True)[:_MAX_RESULTS]
    return [{**r, "match_score": round(score(r), 4)} for r in ranked]


def _attach_stores(sb, rows: list[dict]) -> None:
    ids = list({r["store_id"] for r in rows})
    if not ids:
        return
    stores = sb.table("stores").select(
        "id,name,neighbourhood,avg_delivery_mins,is_open,rating"
    ).in_("id", ids).execute().data
    by_id = {s["id"]: s for s in stores}
    for r in rows:
        s = by_id.get(r["store_id"])
        if s:
            r["store_name"] = s["name"]
            r["store_rating"] = s["rating"]
            r["store_is_open"] = s["is_open"]
            r["avg_delivery_mins"] = s["avg_delivery_mins"]


@router.post("/api/search")
async def search(req: SearchRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must be non-empty")

    intent, embedding = await asyncio.gather(
        asyncio.to_thread(_extract_intent, query),
        asyncio.to_thread(gemini.embed_query, query),
    )

    # explicit request param wins over location extracted from the text
    barrio = match_barrio(req.neighbourhood) or match_barrio(intent.get("location"))

    def _match():
        sb = get_client()
        rows = sb.rpc("match_products", {
            "query_embedding": embedding,
            "match_count": _RPC_CANDIDATES,
            "p_neighbourhood": barrio,
        }).execute().data or []
        rows = _rerank(rows, intent)
        _attach_stores(sb, rows)
        return rows

    results = await asyncio.to_thread(_match)

    what = intent.get("item_name") or query
    interpreted_as = f"{what} near {barrio}" if barrio else f"{what} anywhere in Madrid"
    return {"results": results, "interpreted_as": interpreted_as}
