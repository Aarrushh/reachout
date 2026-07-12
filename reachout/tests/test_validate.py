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
