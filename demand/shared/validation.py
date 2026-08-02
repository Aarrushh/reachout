"""Format-enforcing JSON Schema validation for the demand service.

WHY THIS EXISTS
---------------
Every schema in `demand/shared/schemas/` is draft-07, and on draft-07
`format` is an ANNOTATION, not an assertion. A bare
`jsonschema.validate(instance=..., schema=...)` therefore accepts
`id="not-a-uuid"`, `window_start="NOPE"` and `computed_at="NOPE"` against
`"format": "uuid"` / `"date"` / `"date-time"` without a murmur. Every
`format` in every demand contract is silently unenforced unless a
`FormatChecker` is passed in explicitly.

That is not a theoretical hole: an endpoint reflects a caller-supplied
`?store_id=` straight back into a response the code calls
"schema-validated", so `?store_id=<script>alert(1)</script>` validates today
even though the schema says `format: uuid`.

ALL demand code must call `validate_with_formats()` instead of
`jsonschema.validate()`. If you find yourself importing `jsonschema` to
validate a payload, import this instead.

WHAT IS ACTUALLY ENFORCED
-------------------------
`jsonschema`'s `FormatChecker` only registers a checker for a format when
the optional dependency backing it is importable. `UNENFORCED_FORMATS`
names the formats this service cares about that the current environment
CANNOT check, so nobody has to guess. As of this writing, in this venv:

    uuid       enforced (stdlib)
    date       enforced (stdlib)
    date-time  NOT enforced — needs `rfc3339-validator` on the path

so `format: date-time` is still an annotation here. Installing
`rfc3339-validator` turns it on with no code change; `UNENFORCED_FORMATS`
goes empty on its own when that happens. Do not read a passing validation
of a `date-time` field as proof the value is a timestamp until then.
"""

import jsonschema
from jsonschema import FormatChecker

#: The single shared checker. Module-level so the registry lookup that
#: decides which formats are live happens once.
FORMAT_CHECKER = FormatChecker()

#: The formats the demand contracts actually use.
DEMAND_FORMATS = frozenset({"uuid", "date", "date-time"})

#: Of those, the ones this environment cannot check — see the module
#: docstring. Empty is the goal state.
UNENFORCED_FORMATS = frozenset(
    fmt for fmt in DEMAND_FORMATS if fmt not in FORMAT_CHECKER.checkers
)


def validate_with_formats(instance, schema):
    """Validate `instance` against `schema` with `format` actually enforced.

    Drop-in replacement for `jsonschema.validate(instance=..., schema=...)`,
    differing only in that it attaches `FORMAT_CHECKER`, so draft-07
    `format` keywords assert instead of merely annotating.

    Raises `jsonschema.ValidationError` exactly as `jsonschema.validate`
    does, so existing `pytest.raises(ValidationError)` call sites and
    exception handlers keep working unchanged.
    """
    jsonschema.validate(instance=instance, schema=schema, format_checker=FORMAT_CHECKER)
