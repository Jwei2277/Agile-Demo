class DummyResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows, *, update_result=None):
        self.rows = rows
        self.update_result = update_result or rows
        self._method = None
        self._filters = []
        self._payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        self._filters.append(("eq", _args, _kwargs))
        return self

    def in_(self, *_args, **_kwargs):
        self._filters.append(("in_", _args, _kwargs))
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def update(self, payload):
        self._payload = payload
        return self

    def execute(self):
        if self._payload is not None:
            return DummyResponse([self.update_result])
        if isinstance(self.rows, dict):
            return DummyResponse([self.rows])
        return DummyResponse(self.rows)


class FakeSupabaseAdmin:
    def __init__(self, booking_row):
        self.booking_row = booking_row
        self.updated = None

    def table(self, name):
        if name == "bookings":
            return self._booking_query()
        if name == "rooms":
            return FakeQuery([])
        raise AssertionError(f"Unexpected table {name}")

    def _booking_query(self):
        return FakeQuery(self.booking_row)
