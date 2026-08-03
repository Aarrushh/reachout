"""Chainable fake Supabase client, modelled on reachout/tests/fake_supa.py.

Kept close to the reachout version on purpose: it is the fake every
demand/ Jules task (TASK 69-75) is told to build on top of. Extend it in
the task that needs the new chain method (e.g. an explicit `upsert`) rather
than growing it speculatively here.

W1-FIX-D made this fake stop lying. It previously accepted `select(cols)`
and threw `cols` away, accepted `schema(name)` and threw `name` away, and
auto-vivified any table name it was handed. A fake with all three amnesias
cannot fail a test for a wrong column list, a wrong schema, or a wrong
table name -- and the demand suite stayed green while an agent rewrote
every `.select(...)` in `demand/api/app.py` to `.select("*")` and commented
out all four `jsonschema.validate` calls.

The three rules now enforced:

1. `select("a,b")` projects: every returned row has exactly the keys `a`
   and `b`. Projection happens at `execute()` time, after filtering, so
   `eq()`/`in_()`/`order()` still see the whole row -- that is what
   PostgREST does (filters run server-side against the real row).
2. `select("*")` (or `select()`) returns rows WHOLE, including any extra
   column the fixture carries that the JSON Schema does not allow. That is
   what makes `demand.trend_snapshots.captured_date` -- a DB-only generated
   column deliberately absent from `trend_snapshot.schema.json`, see the
   HARD RULE in docs/JULES_DEMAND.md -- visible to tests instead of
   invisible until production.
3. Unknown schema, unknown table and unknown column all raise. A test that
   asks for data the fixture never defined must go red; silently answering
   "no rows" is the failure mode this fake was built to have and no longer
   has.

Schema modelling: `tables=` populates the default schema (`"public"` unless
`default_schema=` says otherwise); `schemas={"demand": {...}}` declares
further named schemas. `client.schema(name)` returns a view bound to that
schema, so it does not leak into later `client.table(...)` calls the way a
mutable `_active_schema` on the client would.
"""


class FakeSupabaseError(Exception):
    """Base class for every 'your fixture never declared that' failure."""


class UnknownSchemaError(FakeSupabaseError):
    """schema(name) for a schema the fixture does not define."""


class UnknownTableError(FakeSupabaseError):
    """table(name) for a table the fixture does not define."""


class UnknownColumnError(FakeSupabaseError):
    """select() naming a column no row in the fixture table carries."""


def _parse_cols(cols):
    """Return the explicit column list for `cols`, or None for a whole-row read.

    None / "" / "*" all mean "return the row as it is, extra keys included".
    """
    if cols is None:
        return None
    if not isinstance(cols, str):
        raise TypeError(f"select() expects a string column list, got {type(cols)!r}")
    stripped = cols.strip()
    if stripped in ("", "*"):
        return None
    parsed = [c.strip() for c in stripped.split(",")]
    parsed = [c for c in parsed if c]
    return parsed or None


class FakeResult:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count

class FakeQueryBuilder:
    def __init__(self, data, source_list=None, table_name="<unnamed>"):
        self._data = list(data)
        self._source_list = source_list
        self._table_name = table_name
        self._count = None
        self._limit = None
        self._range = None
        self._cols = None

    def select(self, cols="*", count=None):
        self._count = count
        self._cols = _parse_cols(cols)
        if self._cols:
            self._reject_unknown_columns(self._cols)
        return self

    def _reject_unknown_columns(self, cols):
        """Fail loudly on a column the fixture rows have never heard of.

        Only checked when the table has rows: an empty table carries no
        shape, so there is nothing to check against and a false alarm would
        be worse than the missed one. A column that some rows omit is fine
        (a nullable column absent from a dict fixture reads back as None,
        matching SQL NULL), but a column NO row defines is a typo or a
        rename the code has not followed, and PostgREST would 400 on it.
        """
        rows = self._source_list if self._source_list is not None else self._data
        if not rows:
            return
        known = set()
        for row in rows:
            known.update(row.keys())
        unknown = [c for c in cols if c not in known]
        if unknown:
            raise UnknownColumnError(
                f"select() on table {self._table_name!r} asked for column(s) "
                f"{unknown!r} that no fixture row defines. Known columns: "
                f"{sorted(known)!r}"
            )

    def eq(self, col, val):
        self._data = [row for row in self._data if row.get(col) == val]
        return self

    def in_(self, col, vals):
        self._data = [row for row in self._data if row.get(col) in vals]
        return self

    def order(self, col, desc=False):
        def _get_val(row):
            val = row.get(col)
            return val if val is not None else float('-inf')

        try:
            self._data.sort(key=_get_val, reverse=desc)
        except TypeError:
            self._data.sort(key=lambda row: str(row.get(col)), reverse=desc)
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def limit(self, val):
        self._limit = val
        return self

    def insert(self, data):
        if not isinstance(data, list):
            data = [data]
        if self._source_list is not None:
            self._source_list.clear()
            self._source_list.extend(data)
        self._data = data
        return self

    def upsert(self, data, on_conflict=None):
        if not isinstance(data, list):
            data = [data]

        target_list = self._source_list if self._source_list is not None else self._data

        if on_conflict:
            keys = [k.strip() for k in on_conflict.split(",")]
            for new_row in data:
                match_idx = -1
                for i, existing_row in enumerate(target_list):
                    if all(existing_row.get(k) == new_row.get(k) for k in keys):
                        match_idx = i
                        break

                if match_idx >= 0:
                    target_list[match_idx].update(new_row)
                else:
                    target_list.append(new_row)
        else:
            target_list.extend(data)

        if self._source_list is not None:
            self._data = list(self._source_list)

        return self

    def execute(self):
        count_val = len(self._data) if self._count == "exact" else None

        result_data = self._data
        if self._range:
            start, end = self._range
            result_data = result_data[start:end+1]
        elif self._limit is not None:
            result_data = result_data[:self._limit]

        if self._cols:
            # Projection is the last step, exactly as in PostgREST: filters
            # and ordering saw the whole row, the caller sees only what it
            # asked for. Copies, so the caller cannot mutate the fixture.
            cols = self._cols
            result_data = [
                {col: row.get(col) for col in cols} for row in result_data
            ]

        return FakeResult(data=result_data, count=count_val)

class FakeRPCBuilder:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return FakeResult(data=self._data)


class FakeSchemaView:
    """What `client.schema(name)` returns: table access scoped to one schema.

    A view rather than `self`, so `client.schema("public").table("products")`
    cannot silently re-point a later `client.table("demand_signals")`.
    """

    def __init__(self, client, schema_name, tables):
        self._client = client
        self.schema_name = schema_name
        self.tables = tables

    def table(self, name):
        if name not in self.tables:
            raise UnknownTableError(
                f"table({name!r}) is not defined in schema "
                f"{self.schema_name!r}. Declared tables: "
                f"{sorted(self.tables)!r}. Add it to the fixture rather than "
                f"letting the fake invent an empty one."
            )
        return FakeQueryBuilder(self.tables[name], self.tables[name], table_name=name)

    def rpc(self, name, params=None):
        return self._client.rpc(name, params)


class FakeSupabase:
    DEFAULT_SCHEMA = "public"

    def __init__(self, tables=None, rpcs=None, schemas=None, default_schema=None):
        self.default_schema = default_schema or self.DEFAULT_SCHEMA
        self.schemas = {self.default_schema: dict(tables or {})}
        for schema_name, schema_tables in (schemas or {}).items():
            self.schemas.setdefault(schema_name, {}).update(dict(schema_tables or {}))
        self.rpcs = rpcs or {}

    @property
    def tables(self):
        """The default schema's tables — the shape pre-W1-FIX-D fixtures use."""
        return self.schemas[self.default_schema]

    def schema(self, schema_name):
        if schema_name not in self.schemas:
            raise UnknownSchemaError(
                f"schema({schema_name!r}) is not defined by this fixture. "
                f"Declared schemas: {sorted(self.schemas)!r}. Pass "
                f"schemas={{{schema_name!r}: {{...}}}} (or default_schema=) to "
                f"FakeSupabase if the code under test really reads it."
            )
        return FakeSchemaView(self, schema_name, self.schemas[schema_name])

    def table(self, name):
        return self.schema(self.default_schema).table(name)

    def rpc(self, name, params=None):
        return FakeRPCBuilder(self.rpcs.get(name, []))
