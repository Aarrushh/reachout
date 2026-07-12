import validate as v


def _stock_matches_with_price(price):
    return {
        "status": "ok",
        "query": "algo para el dolor de cabeza",
        "query_location": {
            "lat": 40.4168, "lng": -3.7038,
            "resolved_from": "coordinates", "location_text": None,
        },
        "radius_km": 2.0,
        "match_count": 1,
        "matches": [{
            "shop_id": "osm:node:1",
            "shop_name": "Test Shop",
            "categories": ["pharmacy"],
            "address": None,
            "lat": 40.4168,
            "lng": -3.7038,
            "distance_km": 0.1,
            "distance_type": "haversine",
            "items": [{
                "sku": "PHA-0001",
                "name": "Test Item",
                "category": "pharmacy",
                "price": price,
                "currency": "EUR",
                "qty": 1,
            }],
        }],
        "pinged_shop_ids": ["osm:node:1"],
    }


def test_multiple_of_accepts_a_cent_price_that_is_imprecise_in_binary_float():
    # 4.69 / 0.01 == 469.00000000000006 in IEEE-754 double precision, so an
    # exact-equality multipleOf check spuriously rejects a perfectly valid
    # 2-decimal-place EUR price. That is a validator bug, not a data bug.
    ok, err = v.validate(_stock_matches_with_price(4.69), "stock_matches.schema.json")
    assert ok, err


def test_multiple_of_still_rejects_a_genuine_sub_cent_price():
    ok, err = v.validate(_stock_matches_with_price(4.691), "stock_matches.schema.json")
    assert not ok
    assert "multiple of" in err


def test_region_record_schema():
    base_payload = {
        "region_id": "malasana-madrid",
        "name": "Malasaña",
        "lat": 40.4267,
        "lng": -3.7038,
        "source": "gazetteer",
        "shop_count": 5
    }

    # Valid payload
    ok, err = v.validate(base_payload, "region_record.schema.json")
    assert ok, err

    # Invalid region_id pattern
    bad_id = dict(base_payload, region_id="Malasana!")
    ok, err = v.validate(bad_id, "region_record.schema.json")
    assert not ok

    # Invalid name (minLength 1)
    bad_name = dict(base_payload, name="")
    ok, err = v.validate(bad_name, "region_record.schema.json")
    assert not ok

    # Lat out of bounds
    bad_lat = dict(base_payload, lat=41.0)
    ok, err = v.validate(bad_lat, "region_record.schema.json")
    assert not ok

    # Lng out of bounds
    bad_lng = dict(base_payload, lng=-3.0)
    ok, err = v.validate(bad_lng, "region_record.schema.json")
    assert not ok

    # Invalid source
    bad_source = dict(base_payload, source="unknown")
    ok, err = v.validate(bad_source, "region_record.schema.json")
    assert not ok

    # Invalid shop_count
    bad_count = dict(base_payload, shop_count=-1)
    ok, err = v.validate(bad_count, "region_record.schema.json")
    assert not ok

    # Additional properties
    extra_prop = dict(base_payload, extra="foo")
    ok, err = v.validate(extra_prop, "region_record.schema.json")
    assert not ok

def test_regions_response_schema_ok():
    base_payload = {
        "status": "ok",
        "generated_at": "2023-01-01T12:00:00Z",
        "region_count": 1,
        "regions": [
            {
                "region_id": "malasana-madrid",
                "name": "Malasaña",
                "lat": 40.4267,
                "lng": -3.7038,
                "source": "gazetteer",
                "shop_count": 5
            }
        ]
    }

    # Valid payload
    ok, err = v.validate(base_payload, "regions_response.schema.json")
    assert ok, err

    # Invalid status
    bad_status = dict(base_payload, status="foo")
    ok, err = v.validate(bad_status, "regions_response.schema.json")
    assert not ok

    # Missing generated_at
    bad_payload = dict(base_payload)
    del bad_payload["generated_at"]
    ok, err = v.validate(bad_payload, "regions_response.schema.json")
    assert not ok
    
    # Missing region_count
    bad_payload = dict(base_payload)
    del bad_payload["region_count"]
    ok, err = v.validate(bad_payload, "regions_response.schema.json")
    assert not ok
    
    # Missing regions
    bad_payload = dict(base_payload)
    del bad_payload["regions"]
    ok, err = v.validate(bad_payload, "regions_response.schema.json")
    assert not ok

    # Invalid region count
    bad_count = dict(base_payload, region_count=-1)
    ok, err = v.validate(bad_count, "regions_response.schema.json")
    assert not ok

    # Additional properties
    extra_prop = dict(base_payload, extra="foo")
    ok, err = v.validate(extra_prop, "regions_response.schema.json")
    assert not ok


def test_regions_response_schema_error():
    base_payload = {
        "status": "error",
        "error": {
            "code": "internal",
            "detail": "Something went wrong"
        }
    }

    # Valid payload
    ok, err = v.validate(base_payload, "regions_response.schema.json")
    assert ok, err

    # Invalid code
    bad_code = dict(base_payload, error={"code": "foo", "detail": "foo"})
    ok, err = v.validate(bad_code, "regions_response.schema.json")
    assert not ok

    # Missing detail
    bad_error = dict(base_payload, error={"code": "internal"})
    ok, err = v.validate(bad_error, "regions_response.schema.json")
    assert not ok

    # Missing error object
    bad_payload = {"status": "error"}
    ok, err = v.validate(bad_payload, "regions_response.schema.json")
    assert not ok

def test_inventory_response_schema_ok():
    base_payload = {
        "status": "ok",
        "generated_at": "2023-01-01T12:00:00Z",
        "region_id": "malasana-madrid",
        "page": 1,
        "page_size": 20,
        "total_items": 1,
        "total_pages": 1,
        "items": [
            {
                "shop_id": "osm:node:1",
                "shop_name": "Test Shop",
                "sku": "PHA-0001",
                "name": "Test Item",
                "category": "pharmacy",
                "price": 10.99,
                "currency": "EUR",
                "qty": 5,
                "synthetic": True,
                "source": "template",
                "updated_at": "2023-01-01T12:00:00Z"
            }
        ]
    }

    # Valid payload
    ok, err = v.validate(base_payload, "inventory_response.schema.json")
    assert ok, err

    # Null region_id is allowed
    payload_null_region = dict(base_payload, region_id=None)
    ok, err = v.validate(payload_null_region, "inventory_response.schema.json")
    assert ok, err

    # Optional fields rating and review_count are allowed
    payload_optional = dict(base_payload)
    payload_optional["items"] = [
        dict(base_payload["items"][0], rating=4.5, review_count=10)
    ]
    ok, err = v.validate(payload_optional, "inventory_response.schema.json")
    assert ok, err


def test_inventory_response_schema_error():
    base_payload = {
        "status": "ok",
        "generated_at": "2023-01-01T12:00:00Z",
        "region_id": "malasana-madrid",
        "page": 1,
        "page_size": 20,
        "total_items": 1,
        "total_pages": 1,
        "items": [
            {
                "shop_id": "osm:node:1",
                "shop_name": "Test Shop",
                "sku": "PHA-0001",
                "name": "Test Item",
                "category": "pharmacy",
                "price": 10.99,
                "currency": "EUR",
                "qty": 5,
                "synthetic": True,
                "source": "template",
                "updated_at": "2023-01-01T12:00:00Z"
            }
        ]
    }

    # Missing status
    bad_payload = dict(base_payload)
    del bad_payload["status"]
    ok, err = v.validate(bad_payload, "inventory_response.schema.json")
    assert not ok

    # Invalid page
    bad_page = dict(base_payload, page=0)
    ok, err = v.validate(bad_page, "inventory_response.schema.json")
    assert not ok

    # Invalid page_size (> 100)
    bad_page_size_high = dict(base_payload, page_size=101)
    ok, err = v.validate(bad_page_size_high, "inventory_response.schema.json")
    assert not ok

    # Invalid page_size (< 1)
    bad_page_size_low = dict(base_payload, page_size=0)
    ok, err = v.validate(bad_page_size_low, "inventory_response.schema.json")
    assert not ok

    # Additional properties in root
    extra_prop_root = dict(base_payload, extra="foo")
    ok, err = v.validate(extra_prop_root, "inventory_response.schema.json")
    assert not ok

    # Missing sku in item
    bad_item = dict(base_payload["items"][0])
    del bad_item["sku"]
    bad_payload_item = dict(base_payload, items=[bad_item])
    ok, err = v.validate(bad_payload_item, "inventory_response.schema.json")
    assert not ok

    # Invalid sku pattern
    bad_item_sku = dict(base_payload["items"][0], sku="BADSKU")
    bad_payload_sku = dict(base_payload, items=[bad_item_sku])
    ok, err = v.validate(bad_payload_sku, "inventory_response.schema.json")
    assert not ok

    # Invalid currency
    bad_item_curr = dict(base_payload["items"][0], currency="USD")
    bad_payload_curr = dict(base_payload, items=[bad_item_curr])
    ok, err = v.validate(bad_payload_curr, "inventory_response.schema.json")
    assert not ok

    # Additional properties in item
    bad_item_extra = dict(base_payload["items"][0], extra="foo")
    bad_payload_extra = dict(base_payload, items=[bad_item_extra])
    ok, err = v.validate(bad_payload_extra, "inventory_response.schema.json")
    assert not ok

def test_stock_event_schema_sale_ok():
    payload = {
        "type": "sale",
        "shop_id": "osm:node:123",
        "shop_name": "Test Shop",
        "region_id": "malasana-madrid",
        "sku": "PHA-0001",
        "name": "Test Item",
        "qty_now": 4,
        "ts": "2023-01-01T12:00:00Z",
        "sold": 1
    }
    ok, err = v.validate(payload, "stock_event.schema.json")
    assert ok, err

def test_stock_event_schema_restock_ok():
    payload = {
        "type": "restock",
        "shop_id": "osm:node:123",
        "shop_name": "Test Shop",
        "region_id": "malasana-madrid",
        "sku": "PHA-0001",
        "name": "Test Item",
        "qty_now": 10,
        "ts": "2023-01-01T12:00:00Z",
        "added": 5
    }
    ok, err = v.validate(payload, "stock_event.schema.json")
    assert ok, err

def test_stock_event_schema_new_item_ok():
    payload = {
        "type": "new_item",
        "shop_id": "osm:node:123",
        "shop_name": "Test Shop",
        "region_id": "malasana-madrid",
        "sku": "PHA-0001",
        "name": "Test Item",
        "qty_now": 5,
        "ts": "2023-01-01T12:00:00Z",
        "added": 5
    }
    ok, err = v.validate(payload, "stock_event.schema.json")
    assert ok, err

def test_stock_event_schema_null_region_ok():
    payload = {
        "type": "sale",
        "shop_id": "osm:node:123",
        "shop_name": "Test Shop",
        "region_id": None,
        "sku": "PHA-0001",
        "name": "Test Item",
        "qty_now": 4,
        "ts": "2023-01-01T12:00:00Z",
        "sold": 1
    }
    ok, err = v.validate(payload, "stock_event.schema.json")
    assert ok, err

def test_stock_event_schema_errors():
    base_payload = {
        "type": "sale",
        "shop_id": "osm:node:123",
        "shop_name": "Test Shop",
        "region_id": "malasana-madrid",
        "sku": "PHA-0001",
        "name": "Test Item",
        "qty_now": 4,
        "ts": "2023-01-01T12:00:00Z"
    }

    # Invalid type
    bad_type = dict(base_payload, type="foo")
    ok, err = v.validate(bad_type, "stock_event.schema.json")
    assert not ok

    # Invalid shop_id
    bad_shop = dict(base_payload, shop_id="123")
    ok, err = v.validate(bad_shop, "stock_event.schema.json")
    assert not ok

    # Invalid sku
    bad_sku = dict(base_payload, sku="BADSKU")
    ok, err = v.validate(bad_sku, "stock_event.schema.json")
    assert not ok

    # Invalid qty_now
    bad_qty = dict(base_payload, qty_now=-1)
    ok, err = v.validate(bad_qty, "stock_event.schema.json")
    assert not ok

    # Invalid ts format (not testing full ISO8601 validation here, just that it's present/string)
    # The actual validator might pass simple strings if format is ignored, but missing is bad
    bad_ts = dict(base_payload)
    del bad_ts["ts"]
    ok, err = v.validate(bad_ts, "stock_event.schema.json")
    assert not ok

    # Invalid sold
    bad_sold = dict(base_payload, sold=0)
    ok, err = v.validate(bad_sold, "stock_event.schema.json")
    assert not ok

    # Invalid added
    bad_added = dict(base_payload, added=0)
    ok, err = v.validate(bad_added, "stock_event.schema.json")
    assert not ok

    # Extra properties
    extra_prop = dict(base_payload, extra="foo")
    ok, err = v.validate(extra_prop, "stock_event.schema.json")
    assert not ok
