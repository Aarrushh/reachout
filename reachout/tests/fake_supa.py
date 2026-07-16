class FakeResult:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count

class FakeQueryBuilder:
    def __init__(self, data):
        self._data = list(data)
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
        self._data = data
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

    def table(self, name):
        return FakeQueryBuilder(self.tables.get(name, []))

    def rpc(self, name, params=None):
        return FakeRPCBuilder(self.rpcs.get(name, []))
