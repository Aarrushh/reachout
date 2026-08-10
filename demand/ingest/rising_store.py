"""Persist the discovery pass. Mirrors snapshot_store.py's uuid5 dedupe."""

import uuid
from typing import Any, Dict, List

#: Same fixed namespace discipline as snapshot_store: a uuid5 over the natural
#: key means re-running a Monday twice upserts the same ids instead of doubling
#: the table. Counts that double on a re-run are a finding, not a busy day.
RISING_NAMESPACE = uuid.UUID("6f1c9b02-6b1d-5a4e-9d4b-2f0f2c9a7e31")


def rising_query_id(parent_keyword: str, query: str, geo: str,
                    captured_date: str) -> str:
    """The natural key: which seed term surfaced which query, where, when."""
    return str(uuid.uuid5(
        RISING_NAMESPACE,
        f"{parent_keyword}|{query}|{geo}|{captured_date}",
    ))


def build_rows(parent_keyword: str, rows: List[Dict[str, Any]], geo: str,
               gprop: str, captured_at: str) -> List[Dict[str, Any]]:
    """Parser output -> database rows. No derivation, only shaping."""
    captured_date = captured_at[:10]
    return [
        {
            "id": rising_query_id(parent_keyword, row["query"], geo,
                                  captured_date),
            "parent_keyword": parent_keyword,
            "query": row["query"],
            "growth_pct": row["growth_pct"],
            "is_breakout": row["is_breakout"],
            "geo": geo,
            "gprop": gprop,
            "captured_at": captured_at,
            "captured_date": captured_date,
        }
        for row in rows
    ]


def store_rising_queries(supa_client: Any, rows: List[Dict[str, Any]]) -> int:
    """Upsert on the primary key. Returns the number of rows sent.

    `on_conflict="id"` is explicit, mirroring `snapshot_store.store_snapshots`,
    rather than relying on an implicit "upsert defaults to the primary key"
    assumption. `id` IS the primary key (`demand/data/schema.sql`) and IS the
    uuid5 of the natural key (`rising_query_id`), so conflict-on-`id` is
    conflict-on-natural-key: re-running the same day's discovery pass updates
    the row it already wrote instead of minting a duplicate.
    """
    if not rows:
        return 0
    supa_client.table("rising_queries").upsert(rows, on_conflict="id").execute()
    return len(rows)
