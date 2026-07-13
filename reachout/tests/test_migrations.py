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
    clean_db.executescript("""
        CREATE TABLE IF NOT EXISTS shops (
            shop_id TEXT PRIMARY KEY,
            osm_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            categories TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            address TEXT,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
    """)
    full_migrations = migrations.MIGRATIONS.copy()
    migrations.MIGRATIONS = [full_migrations[0]]
    migrations.migrate(clean_db)
    migrations.MIGRATIONS = full_migrations
    
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


def test_migration_2_shops_region_id(clean_db):
    """Test that migration 2 adds region_id and its index, leaving existing rows NULL."""
    # First, run up to migration 1 to create tables normally but wait on 2.
    # We'll construct a mock of init_db state using only migration 1 plus shops table.
    
    clean_db.executescript("""
        CREATE TABLE IF NOT EXISTS shops (
            shop_id TEXT PRIMARY KEY,
            osm_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            categories TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            address TEXT,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
    """)
    
    full_migrations = migrations.MIGRATIONS.copy()
    migrations.MIGRATIONS = [full_migrations[0]]
    migrations.migrate(clean_db)
    
    # Insert a shop before migration 2
    clean_db.execute(
        "INSERT INTO shops (shop_id, osm_id, name, categories, lat, lng, source, fetched_at) "
        "VALUES ('shop1', 1, 'Shop 1', '[]', 0, 0, 'src', 'now')"
    )
    
    # Restore full migrations and apply
    migrations.MIGRATIONS = [full_migrations[0], full_migrations[1]]
    migrations.migrate(clean_db)
    migrations.MIGRATIONS = full_migrations
    
    version = clean_db.execute("PRAGMA user_version").fetchone()[0]
    assert version >= 2
    
    # Check column
    columns = clean_db.execute("PRAGMA table_info(shops)").fetchall()
    col_names = [col[1] for col in columns]
    assert "region_id" in col_names
    
    region_id_col = next(col for col in columns if col[1] == "region_id")
    assert region_id_col[2] == "TEXT"
    assert region_id_col[3] == 0 # nullable
    
    # Check index
    indices = clean_db.execute("PRAGMA index_list(shops)").fetchall()
    index_names = [idx[1] for idx in indices]
    assert "idx_shops_region" in index_names
    
    # Check existing row
    row = clean_db.execute("SELECT region_id FROM shops WHERE shop_id = 'shop1'").fetchone()
    assert row[0] is None

def test_migration_3_inventory_columns(clean_db):
    """Test that migration 3 adds source, rating, and review_count to inventory."""
    clean_db.executescript("""
        CREATE TABLE IF NOT EXISTS shops (
            shop_id TEXT PRIMARY KEY,
            osm_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            categories TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            address TEXT,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inventory (
            shop_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            currency TEXT NOT NULL,
            qty INTEGER NOT NULL,
            synthetic INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (shop_id, sku),
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
        );
    """)
    
    full_migrations = migrations.MIGRATIONS.copy()
    migrations.MIGRATIONS = [full_migrations[0], full_migrations[1]]
    migrations.migrate(clean_db)
    
    clean_db.execute(
        "INSERT INTO shops (shop_id, osm_id, name, categories, lat, lng, source, fetched_at) "
        "VALUES ('shop1', 1, 'Shop 1', '[]', 0, 0, 'src', 'now')"
    )
    clean_db.execute(
        "INSERT INTO inventory (shop_id, sku, name, category, price, currency, qty, synthetic, updated_at) "
        "VALUES ('shop1', 'sku1', 'Item 1', 'cat', 10.0, 'EUR', 1, 1, 'now')"
    )
    
    migrations.MIGRATIONS = full_migrations
    migrations.migrate(clean_db)
    
    version = clean_db.execute("PRAGMA user_version").fetchone()[0]
    assert version >= 3
    
    columns = clean_db.execute("PRAGMA table_info(inventory)").fetchall()
    col_names = [col[1] for col in columns]
    assert "source" in col_names
    assert "rating" in col_names
    assert "review_count" in col_names
    
    source_col = next(col for col in columns if col[1] == "source")
    assert source_col[2] == "TEXT"
    assert source_col[3] == 1 # not null
    assert source_col[4] == "'template'" # default
    
    rating_col = next(col for col in columns if col[1] == "rating")
    assert rating_col[2] == "REAL"
    assert rating_col[3] == 0 # nullable
    
    review_count_col = next(col for col in columns if col[1] == "review_count")
    assert review_count_col[2] == "INTEGER"
    assert review_count_col[3] == 0 # nullable
    
    row = clean_db.execute("SELECT source, rating, review_count FROM inventory WHERE shop_id = 'shop1'").fetchone()
    assert row[0] == 'template'
    assert row[1] is None
    assert row[2] is None
