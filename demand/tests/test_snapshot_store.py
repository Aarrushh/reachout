import pytest
from demand.ingest.snapshot_store import store_snapshots
from demand.tests.fake_supa import FakeSupabase

def test_valid_batch_upsert():
    fake_client = FakeSupabase(tables={"trend_snapshots": []})
    
    rows = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "keyword": "Apple",
            "geo": "ES-MD",
            "timeframe": "today 3-m",
            "provider": "trendspy",
            "captured_at": "2023-10-25T14:30:00Z",
            "series": [
                {"date": "2023-08-01", "value": 50},
                {"date": "2023-09-01", "value": 75}
            ],
            "region_breakdown": None
        }
    ]
    
    store_snapshots(rows, fake_client)
    
    db_rows = fake_client.table("trend_snapshots").select().execute().data
    assert len(db_rows) == 1
    
    saved_row = db_rows[0]
    assert saved_row["keyword"] == "Apple"
    assert saved_row["captured_date"] == "2023-10-25"

def test_schema_invalid_row():
    fake_client = FakeSupabase(tables={"trend_snapshots": []})
    
    rows = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "keyword": "Apple",
            # missing 'geo', 'timeframe', 'provider', 'captured_at'
            "series": []
        }
    ]
    
    with pytest.raises(ValueError, match="Schema validation failed for keyword 'Apple'"):
        store_snapshots(rows, fake_client)
        
    db_rows = fake_client.table("trend_snapshots").select().execute().data
    assert len(db_rows) == 0

def test_idempotent_upsert():
    fake_client = FakeSupabase(tables={"trend_snapshots": []})
    
    row1 = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "keyword": "Banana",
        "geo": "ES-MD",
        "timeframe": "today 1-m",
        "provider": "trendspy",
        "captured_at": "2023-10-26T10:00:00Z",
        "series": [{"date": "2023-10-20", "value": 20}]
    }
    
    # First insert
    store_snapshots([row1], fake_client)
    
    db_rows = fake_client.table("trend_snapshots").select().execute().data
    assert len(db_rows) == 1
    assert db_rows[0]["keyword"] == "Banana"
    
    # Second insert with same unique keys but different value for series
    row2 = dict(row1)
    row2["series"] = [{"date": "2023-10-20", "value": 80}]
    
    store_snapshots([row2], fake_client)
    
    db_rows = fake_client.table("trend_snapshots").select().execute().data
    assert len(db_rows) == 1
    assert db_rows[0]["series"][0]["value"] == 80
