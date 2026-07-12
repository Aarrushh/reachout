"""Database migrations runner."""

MIGRATIONS = [
    (1, """
        CREATE TABLE regions (
            region_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """),
    (2, """
        ALTER TABLE shops ADD COLUMN region_id TEXT;
        CREATE INDEX idx_shops_region ON shops(region_id);
    """)
]

def migrate(conn):
    """
    Apply numbered migrations from MIGRATIONS sequentially.
    Ensures idempotency and monotonicity using PRAGMA user_version.
    """
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    
    for version, sql in MIGRATIONS:
        if version > current_version:
            try:
                # Use executescript with explicit transaction to ensure atomic application
                # SQLite executescript implicitly COMMITs active transactions, so we wrap ours
                script = f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;"
                conn.executescript(script)
            except Exception:
                # Executescript doesn't rollback on failure if we provided BEGIN manually
                # and it crashed halfway (unless it hit a syntax error or constraint).
                # We do a cautious rollback.
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
