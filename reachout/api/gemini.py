"""Gemini REST helper — embeddings + chat, shared by seed/search/chat.

Plain REST on purpose: the google-generativeai SDK is deprecated and this is
two endpoints. Models come from .env (GEMINI_EMBED_MODEL / GEMINI_CHAT_MODEL);
embeddings are gemini-embedding-001 @ 768 dims, L2-normalized here because the
API does NOT normalize non-3072-dim outputs.
"""

import math
import os
import random
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE = "https://generativelanguage.googleapis.com/v1beta"
EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001")
CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-2.5-flash-lite")
EMBED_DIMS = 768
# batchEmbedContents allows 100/call, but each item counts against the
# per-minute request quota — a full batch 429s instantly on burst-limited
# keys (observed live). Default well under the window; override via env.
_MAX_BATCH = int(os.environ.get("GEMINI_EMBED_BATCH", "20"))
_MAX_ATTEMPTS = 8


class GeminiError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise GeminiError("GEMINI_API_KEY is not set (see .env.example)")
    return key


def _post(url: str, payload: dict) -> dict:
    """POST with exponential backoff on 429/5xx/network errors."""
    last = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = requests.post(
                url, json=payload, timeout=60,
                headers={"x-goog-api-key": _api_key(),
                         "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                return resp.json()
            last = f"HTTP {resp.status_code}: {resp.text[:600]}"
            if resp.status_code == 429:
                # rate window: wait out a full minute before re-entering
                time.sleep(60 + 10 * attempt + random.random())
                continue
            if resp.status_code not in (500, 502, 503, 504):
                raise GeminiError(last)  # other 4xx: retrying won't help
        except requests.RequestException as e:
            last = f"network error: {e}"
        time.sleep(min(2 ** attempt + random.random(), 30))
    raise GeminiError(f"gave up after {_MAX_ATTEMPTS} attempts: {last}")


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT",
                pause: float = 0.0) -> list[list[float]]:
    """Embed texts in rate-friendly batches. Returns L2-normalized 768-dim
    vectors. `pause` sleeps between batches (bulk seeding etiquette)."""
    out: list[list[float]] = []
    for i in range(0, len(texts), _MAX_BATCH):
        if i and pause:
            time.sleep(pause)
        chunk = texts[i:i + _MAX_BATCH]
        body = {
            "requests": [
                {
                    "model": f"models/{EMBED_MODEL}",
                    "content": {"parts": [{"text": t}]},
                    "taskType": task_type,
                    "outputDimensionality": EMBED_DIMS,
                }
                for t in chunk
            ]
        }
        data = _post(f"{BASE}/models/{EMBED_MODEL}:batchEmbedContents", body)
        embs = data.get("embeddings", [])
        if len(embs) != len(chunk):
            raise GeminiError(f"expected {len(chunk)} embeddings, got {len(embs)}")
        out.extend(_normalize(e["values"]) for e in embs)
    return out


def embed_query(text: str) -> list[float]:
    return embed_texts([text], task_type="RETRIEVAL_QUERY")[0]


def chat(messages: list[dict], system: str | None = None,
         temperature: float = 0.7, json_mode: bool = False,
         max_output_tokens: int = 1024) -> str:
    """messages: [{"role": "user"|"assistant", "content": str}, ...] -> reply text."""
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    payload: dict = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    data = _post(f"{BASE}/models/{CHAT_MODEL}:generateContent", payload)
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError) as e:
        raise GeminiError(f"unexpected generateContent response: {str(data)[:300]}") from e
