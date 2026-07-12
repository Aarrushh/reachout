import os
import sqlite3
import pytest

from scripts import migrations

@pytest.fixture
def clean_db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    # Save the original MIGRATIONS list to restore it later
    original_migrations = migrations.MIGRATIONS.copy()
    yield conn
    # Restore the original MIGRATIONS list
    migrations.MIGRATIONS = original_migrations
    conn.close()

def test_migrate_fresh_db(clean_db):
    """Test that a fresh DB has the latest version."""
    migrations.MIGRATIONS = [
        (1, "CREATE TABLE test1 (id INTEGER);"),
        (2, "CREATE TABLE test2 (id INTEGER);")
    ]
    
    migrations.migrate(clean_db)
    
    version = clean_db.execute("PRAGMA user_version").fetchone()[0]
    assert version == 2
    
    tables = [row[0] for row in clean_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "test1" in tables
    assert "test2" in tables

def test_migrate_idempotence(clean_db):
    """Test that migrations are idempotent."""
    migrations.MIGRATIONS = [
        (1, "CREATE TABLE test1 (id INTEGER);")
    ]
    
    # First run
    migrations.migrate(clean_db)
    assert clean_db.execute("PRAGMA user_version").fetchone()[0] == 1
    
    # Second run should not fail and version should stay the same
    migrations.migrate(clean_db)
    assert clean_db.execute("PRAGMA user_version").fetchone()[0] == 1

def test_migrate_partial_upgrade(clean_db):
    """Test that migrations apply only from the current user_version."""
    clean_db.execute("PRAGMA user_version = 1")
    clean_db.execute("CREATE TABLE test1 (id INTEGER);")
    
    migrations.MIGRATIONS = [
        (1, "CREATE TABLE test1 (id INTEGER);"), # This would fail if applied
        (2, "CREATE TABLE test2 (id INTEGER);"),
        (3, "CREATE TABLE test3 (id INTEGER);")
    ]
    
    migrations.migrate(clean_db)
    
    version = clean_db.execute("PRAGMA user_version").fetchone()[0]
    assert version == 3
    
    tables = [row[0] for row in clean_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "test1" in tables
    assert "test2" in tables
    assert "test3" in tables

def test_migrate_transaction_rollback(clean_db):
    """Test that a failed migration rolls back and doesn't update version."""
    migrations.MIGRATIONS = [
        (1, "CREATE TABLE test1 (id INTEGER);"),
        (2, "CREATE TABLE test2 (id INTEGER); INSERT INTO non_existent_table VALUES (1);"), # This will fail
        (3, "CREATE TABLE test3 (id INTEGER);")
    ]
    
    with pytest.raises(Exception):
        migrations.migrate(clean_db)
        
    version = clean_db.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1
    
    tables = [row[0] for row in clean_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "test1" in tables
    assert "test2" not in tables
    assert "test3" not in tables

def test_migration_1_regions_table(clean_db):
    """Test that migration 1 creates the regions table with the exact columns."""
    migrations.migrate(clean_db)
    
    version = clean_db.execute("PRAGMA user_version").fetchone()[0]
    assert version >= 1
    
    tables = [row[0] for row in clean_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "regions" in tables
    
    columns = clean_db.execute("PRAGMA table_info(regions)").fetchall()
    
    expected_columns = {
        "region_id": {"type": "TEXT", "notnull": 0, "pk": 1},
        "name": {"type": "TEXT", "notnull": 1, "pk": 0},
        "lat": {"type": "REAL", "notnull": 1, "pk": 0},
        "lng": {"type": "REAL", "notnull": 1, "pk": 0},
        "source": {"type": "TEXT", "notnull": 1, "pk": 0},
        "created_at": {"type": "TEXT", "notnull": 1, "pk": 0},
    }
    
    assert len(columns) == len(expected_columns)
    
    for col in columns:
        name = col[1]
        assert name in expected_columns
        assert col[2] == expected_columns[name]["type"]
        assert col[3] == expected_columns[name]["notnull"]
        assert col[5] == expected_columns[name]["pk"]
