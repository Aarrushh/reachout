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
