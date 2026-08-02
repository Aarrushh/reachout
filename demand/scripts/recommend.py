import os
import json
import uuid
from datetime import datetime, timezone

from demand.scripts.compute_signals import DEMAND_ID_NAMESPACE, NATURAL_KEY_SEP
from demand.shared.validation import validate_with_formats

#: Only these columns are read off `products`. NEVER `select("*")`: the
#: table carries a 768-dim `embedding` column that this join does not use
#: and that would be dragged over the wire once per signal in the batch.
PRODUCT_COLUMNS = "store_id,stock_qty"


def load_schema(schema_name: str) -> dict:
    schema_path = os.path.join(os.path.dirname(__file__), "..", "shared", "schemas", schema_name)
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def recommendation_id(store_id: str, signal_id: str) -> str:
    """The id of the recommendation row for this (store, signal) pair.

    Natural key, verbatim:
        "recommendation|<store_id>|<signal_id>"
    hashed with `uuid5` under `DEMAND_ID_NAMESPACE` (see
    `compute_signals.py`). That pair is exactly what
    `recommendations_dedupe_idx` in `demand/data/schema.sql` dedupes on, so
    the `on_conflict="store_id,signal_id"` upsert now updates the row it
    already wrote. With `uuid4()` the row COUNT stayed stable across
    re-runs while every row's IDENTITY churned -- the idempotency
    requirement is about rows, not counts.
    """
    natural_key = NATURAL_KEY_SEP.join(["recommendation", str(store_id), str(signal_id)])
    return str(uuid.uuid5(DEMAND_ID_NAMESPACE, natural_key))


def build_recommendations(signals: list[dict], supa_client) -> list[dict]:
    """
    Joining rising/falling signals against public.stores / public.products composition.
    Output rows match recommendation.schema.json.
    """
    schema = load_schema("recommendation.schema.json")
    results = []
    created_at = datetime.now(timezone.utc).isoformat()

    for signal in signals:
        category = signal.get("category")
        if not category:
            continue

        # Fetch products for this category
        products_res = supa_client.table("products").select(PRODUCT_COLUMNS).eq("category", category).execute()
        products = products_res.data

        # Group by store and count in-stock products
        store_stock = {}
        for p in products:
            store_id = p.get("store_id")
            if not store_id:
                continue
            # `or 0`, not `.get(..., 0)`: the default of `.get` only fires
            # when the KEY is absent, and Supabase returns a NULL column as
            # the key present with value None -- `None > 0` is a TypeError
            # that has already 500'd an endpoint in this repo. `stock_qty`
            # is nullable as far as this workspace can prove; the NOT NULL
            # sits in another service's schema.
            stock_qty = p.get("stock_qty") or 0
            if stock_qty > 0:
                store_stock[store_id] = store_stock.get(store_id, 0) + 1

        # Generate recommendations per store
        direction = signal["direction"]
        confidence = signal["confidence"]

        # Sorted so the output order is a function of the data, not of the
        # order PostgREST happened to return the product rows in.
        for store_id in sorted(store_stock):
            in_stock_count = store_stock[store_id]
            if in_stock_count < 1:
                continue

            # Determine action
            if direction == "rising" and in_stock_count >= 3:
                action = "feature_in_window"
            elif direction == "rising" and confidence in ("high", "medium"):
                action = "stock_up"
            else:
                action = "watch"

            # Template headline
            if direction == "rising":
                headline = f"Sube el interés por {category} en Madrid"
            elif direction == "falling":
                headline = f"Baja el interés por {category} en Madrid"
            else:
                headline = f"Interés estable por {category} en Madrid"

            # Template body
            body = f"Tienes {in_stock_count} productos de esta categoría en stock."

            rec = {
                "id": recommendation_id(store_id, signal["id"]),
                "store_id": str(store_id),
                "signal_id": str(signal["id"]),
                "headline": headline,
                "body": body,
                "action": action,
                "confidence": confidence,
                "caveat": "Basado en interés de búsqueda en Madrid, no en compras reales.",
                "created_at": created_at
            }

            # Schema validate
            validate_with_formats(instance=rec, schema=schema)
            results.append(rec)

    return results
