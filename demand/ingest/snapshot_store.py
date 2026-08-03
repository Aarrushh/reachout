import json
import os
from datetime import datetime

import jsonschema

from demand.shared.validation import validate_with_formats

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "shared",
    "schemas",
    "trend_snapshot.schema.json"
)

with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    SNAPSHOT_SCHEMA = json.load(f)

def store_snapshots(rows, supa_client):
    """
    Validates rows against trend_snapshot.schema.json, adds captured_date,
    and upserts into demand.trend_snapshots.

    ORDER IS LOAD-BEARING (the HARD RULE, docs/JULES_DEMAND.md): validation
    happens on the row as handed in, BEFORE `captured_date` is attached.
    `captured_date` is a DB-only storage/dedupe column deliberately absent
    from `trend_snapshot.schema.json`, which is
    `additionalProperties: false`, so validating the row that is actually
    written would fail every time. For the same reason nothing may ever
    `SELECT *` off `demand.trend_snapshots` and feed the result back
    through here.

    Validation goes through `validate_with_formats`, so `format` asserts
    instead of merely annotating: `id` must be a real uuid and every
    `series[].date` a real date. Bare `jsonschema.validate` accepted
    `id="not-a-uuid"` on draft-07 without a murmur.
    """
    if not rows:
        return

    validated_rows = []

    for row in rows:
        try:
            validate_with_formats(instance=row, schema=SNAPSHOT_SCHEMA)
        except jsonschema.exceptions.ValidationError as e:
            keyword = row.get("keyword", "Unknown")
            # Create a descriptive error message indicating the keyword and the validation error pointer/path
            path = list(e.absolute_path)
            pointer = "/" + "/".join(str(p) for p in path) if path else ""
            raise ValueError(
                f"Schema validation failed for keyword '{keyword}' at '{pointer}': {e.message}"
            ) from e
            
        # Add captured_date (extracted from captured_at)
        # captured_at is required and is string with date-time format
        # We can extract the date part (YYYY-MM-DD)
        captured_at = row["captured_at"]
        
        # Make a copy so we don't mutate the caller's input payload
        # (Though some architectures might prefer in-place)
        row_to_insert = row.copy()
        row_to_insert["captured_date"] = captured_at[:10]
        
        validated_rows.append(row_to_insert)
        
    # Upsert the whole batch
    supa_client.table("trend_snapshots").upsert(
        validated_rows,
        on_conflict="keyword,geo,timeframe,captured_date"
    ).execute()
