"""POST /api/chat — AI shopkeeper for one store.

Stateless: the client passes the whole conversation history (see STATUS.md
AGENT IMPROVEMENTS #4 — no server-side sessions/Redis). Each call fetches the
store + its live inventory from Supabase, builds the shopkeeper persona
prompt, and answers with Gemini Flash Lite. suggested_items are the inventory
rows the reply actually mentions (fallback: best keyword matches for the
user's message).
"""

import asyncio
import re
import unicodedata
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api import gemini
from api.supa import get_client

router = APIRouter()

_MAX_HISTORY = 20      # last N turns forwarded to the model
_MAX_SUGGESTIONS = 3

_PRODUCT_FIELDS = ("id,name,description,category,price,stock_qty,store_id,"
                   "neighbourhood,tags,image_url")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    store_id: str
    message: str
    history: list[ChatMessage] = []


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c)).lower()


def _system_prompt(store: dict, products: list[dict]) -> str:
    inventory_lines = "\n".join(
        f"- {p['name']} — {p['price']}€ (stock: {p['stock_qty']})"
        for p in products
    )
    return (
        f"You are {store['name']}, a friendly local shopkeeper in "
        f"{store['neighbourhood']}, Madrid.\n"
        f"Your inventory:\n{inventory_lines}\n"
        f"Average delivery: {store['avg_delivery_mins']} minutes.\n"
        "When asked if something is available: check your inventory and answer "
        "naturally.\n"
        f"If available (stock above 0): 'Sí, tengo [item]! Te lo llevo en unos "
        f"{store['avg_delivery_mins']} minutos por [price]€.'\n"
        "If not in your inventory or stock is 0: say so honestly and suggest "
        "the closest alternative from your inventory.\n"
        "Be warm, casual, use light Spanish phrases naturally. "
        "Keep replies under 3 sentences."
    )


def _suggest(reply: str, message: str, products: list[dict]) -> list[dict]:
    """Products the reply mentions by name; else keyword matches on the message."""
    folded_reply = _fold(reply)
    
    mentioned_with_pos = []
    for p in products:
        pos = folded_reply.find(_fold(p["name"]))
        if pos != -1:
            mentioned_with_pos.append((pos, p))
            
    if mentioned_with_pos:
        mentioned_with_pos.sort(key=lambda x: x[0])
        return [p for _, p in mentioned_with_pos[:_MAX_SUGGESTIONS]]
        
    tokens = set(re.findall(r"\w{4,}", _fold(message)))
    scored = []
    for p in products:
        hay = _fold(p["name"]) + " " + " ".join(p.get("tags") or [])
        hits = sum(1 for t in tokens if t in hay)
        if hits and p["stock_qty"] > 0:
            scored.append((hits, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:_MAX_SUGGESTIONS]]


@router.post("/api/chat")
async def chat(req: ChatRequest):
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message must be non-empty")

    def _load():
        sb = get_client()
        store_rows = sb.table("stores").select("*").eq("id", req.store_id).execute().data
        if not store_rows:
            raise HTTPException(status_code=404, detail=f"store {req.store_id} not found")
        products = (sb.table("products").select(_PRODUCT_FIELDS)
                    .eq("store_id", req.store_id).order("name").execute().data)
        return store_rows[0], products

    store, products = await asyncio.to_thread(_load)

    messages = [m.model_dump() for m in req.history[-_MAX_HISTORY:]]
    messages.append({"role": "user", "content": message})

    try:
        reply = await asyncio.to_thread(
            gemini.chat, messages,
            _system_prompt(store, products),
            0.7,
        )
    except gemini.GeminiError as e:
        raise HTTPException(status_code=502, detail=f"LLM unavailable: {e}") from e

    return {"reply": reply, "suggested_items": _suggest(reply, message, products)}
