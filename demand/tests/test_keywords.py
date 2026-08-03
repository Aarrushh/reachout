import pytest
import os
import json
from demand.ingest.keywords import build_universe
from demand.tests.fake_supa import FakeSupabase


def make_client(products):
    """A fake shaped like production, not like the code's assumptions.

    `build_universe` runs on the client from `demand.api.app.get_client()`,
    which is built with `ClientOptions(schema="demand")`. `products` is a
    `public` table (`reachout/data/schema.sql`) and `demand` has no
    `products` at all, so declaring it in the default schema here would let
    an unqualified `.table("products")` pass in tests and fail against real
    Supabase -- which is exactly what shipped.
    """
    return FakeSupabase(
        default_schema="demand",
        tables={},
        schemas={"public": {"products": products}},
    )

def test_missing_seed_file_raises_error(monkeypatch):
    """Test that missing seed file raises a clear error."""
    # Monkeypatch the config path in keywords.py
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', '/non/existent/path.json')
    
    fake_client = make_client([])

    with pytest.raises(FileNotFoundError, match="Seed file not found"):
        build_universe(fake_client)


def test_products_are_read_from_the_public_schema(monkeypatch, tmp_path):
    """`products` lives in `public`; the client is bound to `demand`. A
    bare `.table("products")` resolves to `demand.products` against real
    Supabase, and that table does not exist."""
    seed_file = tmp_path / "seed_keywords.json"
    seed_file.write_text(json.dumps([]))
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))

    fake_client = make_client([{'category': 'Zapatillas'}])
    asked = []
    original_schema = fake_client.schema

    def recording_schema(name):
        asked.append(name)
        return original_schema(name)

    monkeypatch.setattr(fake_client, "schema", recording_schema)

    assert build_universe(fake_client) == ["Zapatillas"]
    assert asked == ["public"]

def test_deduplication_and_seed_winning(monkeypatch, tmp_path):
    """Test deduplication across sources with seed winning ties."""
    # Create a temporary seed file
    seed_file = tmp_path / "seed_keywords.json"
    seed_file.write_text(json.dumps(["Apple", "Banana", "CHERRY"]))
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    
    # DB has same items but different casing, plus some new ones
    fake_client = make_client([
            {'category': 'apple'}, # Should be ignored, seed "Apple" wins
            {'category': 'bAnAnA'}, # Should be ignored, seed "Banana" wins
            {'category': 'cherry'}, # Should be ignored, seed "CHERRY" wins
            {'category': 'Date'}, # New item
            {'category': 'date'}, # Duplicate from DB, should be ignored
        ])
    
    universe = build_universe(fake_client)
    
    # Check that we have exactly 4 items and seed casings won
    assert len(universe) == 4
    assert "Apple" in universe
    assert "Banana" in universe
    assert "CHERRY" in universe
    assert "Date" in universe
    
    # Not checking full order here as another test will do that

def test_skipping_empty_categories(monkeypatch, tmp_path):
    """Test skipping empty-category rows (None, '', '   ')."""
    seed_file = tmp_path / "seed_keywords.json"
    seed_file.write_text(json.dumps(["Apple"]))
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    
    fake_client = make_client([
            {'category': None},
            {'category': ''},
            {'category': '   '},
            {'category': 'Valid'},
        ])
    
    universe = build_universe(fake_client)
    assert len(universe) == 2
    assert "Apple" in universe
    assert "Valid" in universe
    assert None not in universe
    assert "" not in universe
    assert "   " not in universe

def test_deterministic_sorting(monkeypatch, tmp_path):
    """Test that the output is deterministically sorted."""
    seed_file = tmp_path / "seed_keywords.json"
    seed_file.write_text(json.dumps(["Zebra", "Apple"]))
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    
    fake_client = make_client([
            {'category': 'mango'},
            {'category': 'Banana'},
        ])
    
    universe = build_universe(fake_client)
    
    # Expected case-insensitive sort: Apple, Banana, mango, Zebra
    assert universe == ["Apple", "Banana", "mango", "Zebra"]

def test_cap_100(monkeypatch, tmp_path):
    """Test that the 100-item cap is respected."""
    # Create 60 seed keywords
    seed_keywords = [f"Seed_{i}" for i in range(60)]
    seed_file = tmp_path / "seed_keywords.json"
    seed_file.write_text(json.dumps(seed_keywords))
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    
    # Create 60 DB categories (different from seeds)
    db_categories = [{'category': f"DB_{i}"} for i in range(60)]
    fake_client = make_client(db_categories)
    
    universe = build_universe(fake_client)
    
    assert len(universe) == 100
