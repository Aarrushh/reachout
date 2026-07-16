def test_fake_supa_chat_module(fake_supa):
    tables = {
        "stores": [
            {"id": "s1", "name": "Store 1"},
            {"id": "s2", "name": "Store 2"},
        ],
        "products": [
            {"id": "p1", "store_id": "s1", "name": "B"},
            {"id": "p2", "store_id": "s1", "name": "A"},
            {"id": "p3", "store_id": "s2", "name": "C"},
        ]
    }
    sb = fake_supa(tables=tables)
    
    # from api/chat.py:
    # store_rows = sb.table("stores").select("*").eq("id", req.store_id).execute().data
    store_rows = sb.table("stores").select("*").eq("id", "s1").execute().data
    assert len(store_rows) == 1
    assert store_rows[0]["id"] == "s1"
    
    # from api/chat.py:
    # products = sb.table("products").select(_PRODUCT_FIELDS).eq("store_id", req.store_id).order("name").execute().data
    products = sb.table("products").select("id,name").eq("store_id", "s1").order("name").execute().data
    assert len(products) == 2
    assert products[0]["name"] == "A"
    assert products[1]["name"] == "B"

def test_fake_supa_server_module(fake_supa):
    tables = {
        "products": [
            {"id": "p1", "neighbourhood": "n1", "category": "c1"},
            {"id": "p2", "neighbourhood": "n2", "category": "c1"},
            {"id": "p3", "neighbourhood": "n1", "category": "c2"},
        ],
        "stores": [
            {"id": "s1", "neighbourhood": "n1", "rating": 4.5},
            {"id": "s2", "neighbourhood": "n1", "rating": 4.8},
            {"id": "s3", "neighbourhood": "n2", "rating": 4.0},
        ]
    }
    sb = fake_supa(tables=tables)
    
    # from api/server.py (products):
    # q = _supa_client().table("products").select(_V2_PRODUCT_FIELDS, count="exact")
    # if neighbourhood: q = q.eq("neighbourhood", neighbourhood)
    # if category: q = q.eq("category", category)
    # res = await asyncio.to_thread(lambda: q.range(offset, offset + limit - 1).execute())
    q = sb.table("products").select("id,neighbourhood,category", count="exact")
    q = q.eq("neighbourhood", "n1")
    q = q.eq("category", "c1")
    res = q.range(0, 9).execute()
    assert len(res.data) == 1
    assert res.count == 1
    assert res.data[0]["id"] == "p1"
    
    # from api/server.py (stores):
    # q = _supa_client().table("stores").select("*")
    # if neighbourhood: q = q.eq("neighbourhood", neighbourhood)
    # res = await asyncio.to_thread(lambda: q.order("rating", desc=True).execute())
    q = sb.table("stores").select("*")
    q = q.eq("neighbourhood", "n1")
    res = q.order("rating", desc=True).execute()
    assert len(res.data) == 2
    assert res.data[0]["id"] == "s2"
    assert res.data[1]["id"] == "s1"

def test_fake_supa_search_module(fake_supa):
    tables = {
        "stores": [
            {"id": "s1", "name": "Store 1"},
            {"id": "s2", "name": "Store 2"},
            {"id": "s3", "name": "Store 3"},
        ]
    }
    rpcs = {
        "match_products": [
            {"id": "p1", "store_id": "s1"},
            {"id": "p2", "store_id": "s2"},
        ]
    }
    sb = fake_supa(tables=tables, rpcs=rpcs)
    
    # from api/search.py (match_products rpc):
    # rows = sb.rpc("match_products", {...}).execute().data
    rows = sb.rpc("match_products", {"query_embedding": [0.1, 0.2]}).execute().data
    assert len(rows) == 2
    
    # from api/search.py (stores in_):
    # stores = sb.table("stores").select("id,name...").in_("id", ids).execute().data
    ids = ["s1", "s2"]
    stores = sb.table("stores").select("id,name").in_("id", ids).execute().data
    assert len(stores) == 2
    assert {s["id"] for s in stores} == {"s1", "s2"}
