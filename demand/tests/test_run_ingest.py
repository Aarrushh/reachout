import pytest
import os
import sys
import uuid
import json

from unittest.mock import patch

# Setting this before anything gets imported
os.environ["DEMAND_TRENDS_PROVIDER"] = "fixture"

from demand.tests.fake_supa import FakeSupabase
from demand.api import app
from demand.scripts.run_ingest import run_chain
import demand.scripts.run_ingest

@pytest.fixture
def fake_client(tmp_path):
    # Set up some dummy categories that the fixture keywords will resolve to.
    # The fixture keywords in interest_over_time.json (sneakers, coffee, etc.)
    products_data = [
        {"category": "sneakers", "store_id": str(uuid.uuid4()), "stock_qty": 5},
        {"category": "coffee", "store_id": str(uuid.uuid4()), "stock_qty": 5}
    ]
    
    # Needs to match the format of keywords seed file
    seed_file = tmp_path / "seed_keywords.json"
    seed_file.write_text(json.dumps(["sneakers", "coffee"]))
    
    client = FakeSupabase(tables={
        'products': products_data,
        'trend_snapshots': [],
        'demand_signals': [],
        'recommendations': []
    })
    return client, seed_file

def test_full_chain_upserts(fake_client, monkeypatch):
    client, seed_file = fake_client
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    
    # Mock the get_client to return our fake client
    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    # Run the chain not in dry run
    run_chain(provider_name="fixture", dry_run=False)
    
    snapshots = client.table('trend_snapshots')._data
    assert len(snapshots) > 0
    assert all("id" in s for s in snapshots)
    
    signals = client.table('demand_signals')._data
    assert len(signals) > 0
    assert all("id" in s for s in signals)
    
    recommendations = client.table('recommendations')._data
    assert len(recommendations) > 0
    assert all("id" in r for r in recommendations)
    assert all("store_id" in r for r in recommendations)
    assert all("signal_id" in r for r in recommendations)

def test_dry_run_writes_nothing(fake_client, monkeypatch):
    client, seed_file = fake_client
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    
    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    # Run the chain in dry run
    run_chain(provider_name="fixture", dry_run=True)
    
    assert len(client.table('trend_snapshots')._data) == 0
    assert len(client.table('demand_signals')._data) == 0
    assert len(client.table('recommendations')._data) == 0

def test_idempotent_rerun(fake_client, monkeypatch):
    client, seed_file = fake_client
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    
    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    # Run the chain first time
    run_chain(provider_name="fixture", dry_run=False)
    
    snap_count = len(client.table('trend_snapshots')._data)
    sig_count = len(client.table('demand_signals')._data)
    rec_count = len(client.table('recommendations')._data)
    
    assert snap_count > 0
    
    # Run again
    run_chain(provider_name="fixture", dry_run=False)
    
    # The counts should be the same
    assert len(client.table('trend_snapshots')._data) == snap_count
    assert len(client.table('demand_signals')._data) == sig_count
    assert len(client.table('recommendations')._data) == rec_count

def test_lifespan_cron_scheduler(monkeypatch):
    # Test without the flag
    monkeypatch.delenv("DEMAND_INGEST_CRON", raising=False)
    
    async def run_without_cron():
        async with app.lifespan(app.app):
            # should not crash
            pass
            
    import asyncio
    asyncio.run(run_without_cron())
    
    # Test with the flag
    monkeypatch.setenv("DEMAND_INGEST_CRON", "1")
    
    async def run_with_cron():
        async with app.lifespan(app.app):
            # should start scheduler and not crash
            pass
            
    asyncio.run(run_with_cron())
