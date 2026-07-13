import pytest
from scripts.validate import validate

SCHEMAS_AND_FIXTURES = [
    (
        "health_response.schema.json",
        {
            "status": "ok",
            "shop_count": 10,
            "region_count": 5,
            "simulator_running": True
        }
    ),
    (
        "region_record.schema.json",
        {
            "region_id": "malasana",
            "name": "Malasaña",
            "lat": 40.4267,
            "lng": -3.7038,
            "source": "gazetteer",
            "shop_count": 12
        }
    ),
    (
        "regions_response.schema.json",
        {
            "status": "ok",
            "generated_at": "2023-10-01T12:00:00Z",
            "region_count": 1,
            "regions": [
                {
                    "region_id": "malasana",
                    "name": "Malasaña",
                    "lat": 40.4267,
                    "lng": -3.7038,
                    "source": "gazetteer",
                    "shop_count": 12
                }
            ]
        }
    ),
    (
        "inventory_response.schema.json",
        {
            "status": "ok",
            "generated_at": "2023-10-01T12:00:00Z",
            "region_id": "malasana",
            "page": 1,
            "page_size": 20,
            "total_items": 1,
            "total_pages": 1,
            "items": [
                {
                    "shop_id": "osm:node:123",
                    "shop_name": "Farmacia",
                    "sku": "PHA-0001",
                    "name": "Paracetamol",
                    "category": "pharmacy",
                    "price": 3.95,
                    "currency": "EUR",
                    "qty": 10,
                    "synthetic": True,
                    "source": "template",
                    "updated_at": "2023-10-01T12:00:00Z"
                }
            ]
        }
    ),
    (
        "search_page.schema.json",
        {
            "status": "ok",
            "query": "dolor",
            "generated_at": "2023-10-01T12:00:00Z",
            "page": 1,
            "page_size": 20,
            "total_results": 1,
            "total_pages": 1,
            "result_count": 1,
            "results": [
                {
                    "rank": 1,
                    "shop_id": "osm:node:123",
                    "shop_name": "Farmacia",
                    "category": "pharmacy",
                    "address": "Calle 1",
                    "distance_km": 0.5,
                    "item_name": "Paracetamol",
                    "sku": "PHA-0001",
                    "price": 3.95,
                    "currency": "EUR",
                    "stock_qty": 10,
                    "lat": 40.4267,
                    "lng": -3.7038
                }
            ]
        }
    ),
    (
        "stock_event.schema.json",
        {
            "type": "sale",
            "shop_id": "osm:node:123",
            "shop_name": "Farmacia",
            "region_id": "malasana",
            "sku": "PHA-0001",
            "name": "Paracetamol",
            "qty_now": 9,
            "ts": "2023-10-01T12:00:00Z",
            "sold": 1
        }
    )
]

def inject_extra_property(obj):
    """Recursively inject an extra property into all dicts to test additionalProperties."""
    if isinstance(obj, dict):
        new_obj = {"_hallucinated": True}
        for k, v in obj.items():
            new_obj[k] = inject_extra_property(v)
        return new_obj
    elif isinstance(obj, list):
        return [inject_extra_property(item) for item in obj]
    else:
        return obj

@pytest.mark.parametrize("schema_name, fixture", SCHEMAS_AND_FIXTURES)
def test_new_schemas_valid(schema_name, fixture):
    """Test that the valid fixtures for new schemas pass validation."""
    is_valid, err = validate(fixture, schema_name)
    assert is_valid is True, f"{schema_name} failed with valid fixture: {err}"

@pytest.mark.parametrize("schema_name, fixture", SCHEMAS_AND_FIXTURES)
def test_new_schemas_additional_properties(schema_name, fixture):
    """Test that additional properties are correctly rejected at every level."""
    mutated = inject_extra_property(fixture)
    is_valid, err = validate(mutated, schema_name)
    assert is_valid is False, f"{schema_name} incorrectly accepted an extra property"
    assert "Additional properties are not allowed" in str(err)
