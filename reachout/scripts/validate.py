"""Schema validation. This is the gate that catches hallucinations.

Any output that is meant to be structured (a parsed search intent, a
formatted result card) is checked against a JSON Schema before the next
stage trusts it. If an AI stage invents a field or drops a required one,
validation fails here and the pipeline stops instead of passing bad data
forward.

Uses the `jsonschema` package. Install with: pip install jsonschema
"""

import json
import math
import os

try:
    import jsonschema
    from jsonschema.validators import Draft7Validator, extend
except ImportError:  # keep the message honest and actionable
    jsonschema = None

SCHEMA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared", "schemas"))


def _tolerant_multiple_of(validator, dB, instance, schema):
    """Same rule as Draft7's multipleOf, but tolerant of float noise.

    A price like 4.69 stored as an IEEE-754 double satisfies "must have at
    most 2 decimal places" in every sense that matters, but
    4.69 / 0.01 == 469.00000000000006, so Draft7's exact `int(quotient) ==
    quotient` check spuriously rejects ~12% of valid cent values. The
    schema files (and the "multipleOf: 0.01" business rule they encode) are
    untouched; only the float-comparison bug in how that rule is checked is
    fixed here.
    """
    if not validator.is_type(instance, "number"):
        return
    if isinstance(dB, float):
        quotient = instance / dB
        failed = not math.isclose(quotient, round(quotient), rel_tol=1e-9, abs_tol=1e-9)
    else:
        failed = instance % dB
    if failed:
        yield jsonschema.ValidationError(f"{instance!r} is not a multiple of {dB}")


if jsonschema is not None:
    _Validator = extend(Draft7Validator, {"multipleOf": _tolerant_multiple_of})


def load_schema(name):
    with open(os.path.join(SCHEMA_DIR, name)) as f:
        return json.load(f)


def validate(data, schema_name):
    """Return (True, None) if valid, else (False, error_message)."""
    if jsonschema is None:
        return False, "jsonschema not installed. Run: pip install jsonschema"
    schema = load_schema(schema_name)
    try:
        _Validator(schema).validate(instance=data)
        return True, None
    except jsonschema.ValidationError as e:
        return False, str(e.message)


if __name__ == "__main__":
    good = {
        "status": "ok",
        "raw_query": "algo para el dolor de cabeza",
        "keywords": ["dolor de cabeza", "analgésico", "paracetamol", "ibuprofeno"],
        "category_hints": ["pharmacy"],
        "location_text": None,
    }
    print(validate(good, "search_intent.schema.json"))
