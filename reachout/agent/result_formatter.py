"""Stage 04 — turns matches.json into the final ranked_shops.json.

The default path is a deterministic builder: it copies rank order, shop
facts, and the cheapest matching item straight from matches.json. There is
no community card, story, or editorial text anywhere in this pipeline — see
stages/04-format-results/prompt.md.

An optional LLM pass may normalise item_name casing/whitespace only. Its
output is re-validated against ranked_shops.schema.json; any failure at all
(a smuggled field, a changed number, anything) discards it, falls back to
the deterministic output, and logs a formatter_llm_rejected event.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import validate as v  # noqa: E402

EVENTS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "events.jsonl"))

# Source fields on a stock_matches match entry that a ranked_shops result is
# built from, mapped to the name they are reported as in missing_fields.
_MATCH_FIELD_MAP = {
    "shop_id": "shop_id",
    "shop_name": "shop_name",
    "categories": "category",
    "address": "address",
    "distance_km": "distance_km",
    "lat": "lat",
    "lng": "lng",
}
_ITEM_FIELD_MAP = {
    "sku": "sku",
    "name": "item_name",
    "price": "price",
    "currency": "currency",
    "qty": "stock_qty",
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _log_event(event, detail):
    os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)
    with open(EVENTS_PATH, "a") as f:
        f.write(json.dumps({"ts": time.time(), "event": event, **detail}) + "\n")


def _cheapest_item(match):
    return min(match["items"], key=lambda i: i["price"])


def _missing_fields(matches):
    """Every field a result needs but a match is missing, in first-seen order."""
    missing = []
    seen = set()

    def add(name):
        if name not in seen:
            seen.add(name)
            missing.append(name)

    for match in matches:
        for src, out_name in _MATCH_FIELD_MAP.items():
            if src not in match:
                add(out_name)
        if not match.get("items"):
            add("item_name")
            continue
        cheapest = _cheapest_item(match)
        for src, out_name in _ITEM_FIELD_MAP.items():
            if src not in cheapest:
                add(out_name)
    return missing


def _build_result(rank, match):
    cheapest = _cheapest_item(match)
    return {
        "rank": rank,
        "shop_id": match["shop_id"],
        "shop_name": match["shop_name"],
        "category": match["categories"][0],
        "address": match["address"],
        "distance_km": match["distance_km"],
        "item_name": cheapest["name"],
        "sku": cheapest["sku"],
        "price": cheapest["price"],
        "currency": cheapest["currency"],
        "stock_qty": cheapest["qty"],
        "lat": match["lat"],
        "lng": match["lng"],
    }


def _deterministic_build(matches_data):
    matches = matches_data.get("matches", [])

    missing = _missing_fields(matches)
    if missing:
        return {"status": "incomplete", "missing_fields": missing}

    results = [_build_result(i + 1, m) for i, m in enumerate(matches)]
    return {
        "status": "ok",
        "query": matches_data["query"],
        "generated_at": _now_iso(),
        "result_count": len(results),
        "results": results,
    }


def format_results(matches_data, llm_output=None):
    """Build ranked_shops.json from a stock_matches.json dict.

    `llm_output` is the optional pre-computed LLM pass result (a full
    ranked_shops-shaped dict), already produced by the caller. It is only
    ever used to normalise item_name; here it is trusted only if it
    validates against the schema, otherwise it is discarded entirely.
    """
    status = matches_data.get("status")
    if status != "ok":
        return {
            "status": "error",
            "error": {
                "code": "upstream_not_ok",
                "detail": f"stage 03 status was '{status}', not 'ok'",
            },
        }

    deterministic = _deterministic_build(matches_data)

    if llm_output is None:
        return deterministic

    ok, err = v.validate(llm_output, "ranked_shops.schema.json")
    if not ok:
        _log_event("formatter_llm_rejected", {"reason": err})
        return deterministic

    return llm_output
