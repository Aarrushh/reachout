"""Schema validation. This is the gate that catches hallucinations.

Any output that is meant to be structured (a parsed search intent, a
formatted result card) is checked against a JSON Schema before the next
stage trusts it. If an AI stage invents a field or drops a required one,
validation fails here and the pipeline stops instead of passing bad data
forward.

Uses the `jsonschema` package. Install with: pip install jsonschema
"""

import json
import os

try:
    import jsonschema
except ImportError:  # keep the message honest and actionable
    jsonschema = None

SCHEMA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared", "schemas"))


def load_schema(name):
    with open(os.path.join(SCHEMA_DIR, name)) as f:
        return json.load(f)


def validate(data, schema_name):
    """Return (True, None) if valid, else (False, error_message)."""
    if jsonschema is None:
        return False, "jsonschema not installed. Run: pip install jsonschema"
    schema = load_schema(schema_name)
    try:
        jsonschema.validate(instance=data, schema=schema)
        return True, None
    except jsonschema.ValidationError as e:
        return False, str(e.message)


if __name__ == "__main__":
    good = {"raw_query": "paracetamol", "keywords": ["paracetamol"], "category_hint": "pharmacy"}
    print(validate(good, "search_intent.schema.json"))
