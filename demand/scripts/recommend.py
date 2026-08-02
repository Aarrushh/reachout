import os
import json
import uuid
import jsonschema
from datetime import datetime, timezone

def load_schema(schema_name: str) -> dict:
    schema_path = os.path.join(os.path.dirname(__file__), "..", "shared", "schemas", schema_name)
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

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
        products_res = supa_client.table("products").select("*").eq("category", category).execute()
        products = products_res.data
        
        # Group by store and count in-stock products
        store_stock = {}
        for p in products:
            store_id = p.get("store_id")
            if not store_id:
                continue
            stock_qty = p.get("stock_qty", 0)
            if stock_qty > 0:
                store_stock[store_id] = store_stock.get(store_id, 0) + 1
                
        # Generate recommendations per store
        direction = signal["direction"]
        confidence = signal["confidence"]
        
        for store_id, in_stock_count in store_stock.items():
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
                "id": str(uuid.uuid4()),
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
            jsonschema.validate(instance=rec, schema=schema)
            results.append(rec)
            
    return results
