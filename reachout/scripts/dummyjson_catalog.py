"""
Maps DummyJSON categories to our internal domain categories.
Why: DummyJSON has many specific categories, but our system strictly uses:
pharmacy, grocery, hardware, electronics, stationery. We must map the external
taxonomy to our internal one and drop categories we do not support.
"""

import json
import os
import sys

try:
    from dummyjson_fetch import fetch_products
except ImportError:
    from .dummyjson_fetch import fetch_products

CAT_PREFIX = {
    "pharmacy": "PHA",
    "grocery": "GRO",
    "hardware": "HRD",
    "electronics": "ELE",
    "stationery": "STA",
}

def map_category(dummyjson_category: str) -> str | None:
    """
    Map a DummyJSON category to an internal category.
    Returns None if the category is not supported.
    """
    match dummyjson_category:
        case "groceries":
            return "grocery"
        case "beauty" | "skin-care" | "fragrances":
            return "pharmacy"
        case "smartphones" | "laptops" | "tablets" | "mobile-accessories":
            return "electronics"
        case "furniture" | "home-decoration" | "kitchen-accessories" | "lighting" | "sports-accessories" | "motorcycle" | "vehicle":
            return "hardware"
        case _:
            return None

def build_entries(products: list[dict]) -> dict[str, list[dict]]:
    """
    Build domain-specific catalog entries from DummyJSON products.
    Returns a dictionary mapping our domain category to a list of product dictionaries.
    """
    entries = {cat: [] for cat in CAT_PREFIX}
    for p in products:
        internal_cat = map_category(p.get("category", ""))
        if not internal_cat:
            continue
            
        pid = p.get("id")
        if pid is None:
            continue
            
        sku = f"{CAT_PREFIX[internal_cat]}-{1000 + pid}"
        
        entry = {
            "sku": sku,
            "name": p.get("title", ""),
            "base_price_eur": round(float(p.get("price", 0.0)), 2),
            "rating": float(p.get("rating", 0.0)),
            "review_count": len(p.get("reviews", [])),
            "source": "dummyjson",
        }
        
        entries[internal_cat].append(entry)
        
    return entries

def merge_catalog():
    """
    Reads existing data/sku_catalog.json, assigns 'source: "template"' to existing items,
    appends DummyJSON entries under mapped categories, updates _comment, and overwrites the file.
    """
    catalog_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "sku_catalog.json")
    )
    
    # We will read the original file line-by-line to preserve exact formatting of templates
    with open(catalog_path, encoding="utf-8") as f:
        original_lines = f.readlines()
        
    catalog = json.loads("".join(original_lines))
    
    # Fetch and build dummyjson entries
    products = fetch_products(cache_only=True)
    new_entries = build_entries(products)
    
    # Append
    for cat, items in new_entries.items():
        if cat in catalog:
            # First remove existing dummyjson entries in case of re-run
            catalog[cat] = [i for i in catalog[cat] if not (i.get("source") == "dummyjson" or ("-" in i.get("sku", "") and not i["sku"].split("-")[1].startswith("00")))]
            catalog[cat].extend(items)
        else:
            catalog[cat] = items
            
    # Update comment
    catalog["_comment"] = (
        "Synthetic SKU templates per category. This file is the ONLY source of item names and base prices in the MVP. "
        "inventory_seeder.py picks a deterministic subset per shop via random.Random(shop_id), jitters price +/-15% (rounded to cents), qty 0-12. "
        "Same shop_id => same inventory, every run. "
        "Version 2: Now includes DummyJSON entries appended under their mapped category."
    )
    
    new_lines = []
    
    # Process original lines to modify them inline
    new_lines.append("{\n")
    new_lines.append(f'  "_comment": {json.dumps(catalog["_comment"], ensure_ascii=False)},\n')
    
    cats = list(CAT_PREFIX.keys())
    for i, cat in enumerate(cats):
        if cat not in catalog:
            continue
            
        new_lines.append(f'  "{cat}": [\n')
        items = catalog[cat]
        for j, item in enumerate(items):
            is_template = ("-" in item["sku"] and item["sku"].split("-")[1].startswith("00"))
            if is_template:
                # Find the original line for this template
                orig_line = None
                for line in original_lines:
                    if f'"sku": "{item["sku"]}"' in line:
                        orig_line = line
                        break
                
                if orig_line:
                    # Parse out the inner part
                    stripped = orig_line.strip()
                    if stripped.endswith(","):
                        stripped = stripped[:-1]
                    
                    # If it already has source template, just use the original line as is
                    if '"source": "template"' in orig_line:
                        if j < len(items) - 1:
                            new_lines.append(f"    {stripped},\n")
                        else:
                            new_lines.append(f"    {stripped}\n")
                    else:
                        # Append source
                        new_item_str = stripped[:-1].rstrip() + ', "source": "template" }'
                        if j < len(items) - 1:
                            new_lines.append(f"    {new_item_str},\n")
                        else:
                            new_lines.append(f"    {new_item_str}\n")
                else:
                    item["source"] = "template"
                    item_str = '{ ' + ', '.join(f'"{k}": {json.dumps(v, ensure_ascii=False)}' for k, v in item.items()) + ' }'
                    if j < len(items) - 1:
                        new_lines.append(f"    {item_str},\n")
                    else:
                        new_lines.append(f"    {item_str}\n")
            else:
                # DummyJSON entry
                item_str = '{ ' + ', '.join(f'"{k}": {json.dumps(v, ensure_ascii=False)}' for k, v in item.items()) + ' }'
                if j < len(items) - 1:
                    new_lines.append(f"    {item_str},\n")
                else:
                    new_lines.append(f"    {item_str}\n")
        
        if i < len(cats) - 1:
            new_lines.append("  ],\n")
        else:
            new_lines.append("  ]\n")
            
    new_lines.append("}\n")
    
    with open(catalog_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    merge_catalog()
