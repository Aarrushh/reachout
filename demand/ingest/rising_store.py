"""Persist the discovery pass. Mirrors snapshot_store.py's uuid5 dedupe."""

import uuid
from typing import Any, Dict, List

#: Same fixed namespace discipline as snapshot_store: a uuid5 over the natural
#: key means re-running a Monday twice upserts the same ids instead of doubling
#: the table. Counts that double on a re-run are a finding, not a busy day.
RISING_NAMESPACE = uuid.UUID("6f1c9b02-6b1d-5a4e-9d4b-2f0f2c9a7e31")


def rising_query_id(parent_keyword: str, query: str, geo: str, gprop: str,
                    captured_date: str) -> str:
    """The natural key: which seed term surfaced which query, where, how, when.

    `gprop` is part of the key because `schema.sql:142-144` says a
    Shopping-derived row and a Web-derived row "mean different things and
    must never merge silently". `store_rising_queries` upserts on `id`, so
    leaving `gprop` out of the hash is exactly that silent merge: the two
    rows collapse to one id and the second write overwrites the first.
    """
    return str(uuid.uuid5(
        RISING_NAMESPACE,
        f"{parent_keyword}|{query}|{geo}|{gprop}|{captured_date}",
    ))


def build_rows(parent_keyword: str, rows: List[Dict[str, Any]], geo: str,
               gprop: str, captured_at: str) -> List[Dict[str, Any]]:
    """Parser output -> database rows. No derivation, only shaping and a dedupe.

    Deduped by `id`, and the FIRST occurrence wins. Google returns the
    `rising` list in rank order, so the first copy of a repeated query is the
    highest-ranked one, and keeping it makes the output a function of the
    payload alone: the same payload always yields the same rows, in the same
    order, with the same values. (The duplicates are not necessarily
    identical -- a repeat can carry a different `growth_pct` -- so "which one
    wins" has to be stated rather than left to whichever the loop saw last.)

    The dedupe is not cosmetic. `store_rising_queries` sends the whole list in
    a single `upsert(on_conflict="id")`, and Postgres refuses a statement that
    touches the same conflict target twice: "ON CONFLICT DO UPDATE command
    cannot affect row a second time" (SQLSTATE 21000). That error aborts the
    entire statement, so ONE repeated query string loses the whole parent's
    rows -- after the search has already been billed. `rising_query_id` hashes
    (parent, query, geo, gprop, captured_date), and every one of those is
    fixed for a single `build_rows` call except `query`, so two identical
    `query` strings in one parent's payload are one id by construction.
    Nothing upstream promises Google will not repeat a string; the committed
    café capture simply happens not to, which is why no test caught this.
    """
    captured_date = captured_at[:10]
    built = []
    seen = set()
    for row in rows:
        row_id = rising_query_id(parent_keyword, row["query"], geo, gprop,
                                 captured_date)
        if row_id in seen:
            continue
        seen.add(row_id)
        built.append({
            "id": row_id,
            "parent_keyword": parent_keyword,
            "query": row["query"],
            "growth_pct": row["growth_pct"],
            "is_breakout": row["is_breakout"],
            "geo": geo,
            "gprop": gprop,
            "captured_at": captured_at,
            "captured_date": captured_date,
        })
    return built


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
