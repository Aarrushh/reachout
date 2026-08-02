"""Chainable fake Supabase client, modelled on reachout/tests/fake_supa.py.

Kept identical to the reachout version on purpose: it is the fake every
demand/ Jules task (TASK 69-75) is told to build on top of. Extend it in
the task that needs the new chain method (e.g. an explicit `upsert`) rather
than growing it speculatively here.
"""


class FakeResult:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count

class FakeQueryBuilder:
    def __init__(self, data, source_list=None):
        self._data = list(data)
        self._source_list = source_list
        self._count = None
        self._limit = None
        self._range = None

    def select(self, cols="*", count=None):
        self._count = count
        return self

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

        return FakeResult(data=result_data, count=count_val)

class FakeRPCBuilder:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return FakeResult(data=self._data)

class FakeSupabase:
    def __init__(self, tables=None, rpcs=None):
        self.tables = tables or {}
        self.rpcs = rpcs or {}


    def schema(self, schema_name):
        return self

    def table(self, name):

        if name not in self.tables:
            self.tables[name] = []
        return FakeQueryBuilder(self.tables[name], self.tables[name])

    def rpc(self, name, params=None):
        return FakeRPCBuilder(self.rpcs.get(name, []))
