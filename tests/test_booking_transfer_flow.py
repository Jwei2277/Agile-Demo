from types import SimpleNamespace

from agile_ci_demo.bookings import update_booking
from agile_ci_demo.models import BookingUpdate, RoomOut


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


def test_update_booking_allows_approved_bookings(monkeypatch):
    booking_row = {
        "id": 1,
        "student_id": 42,
        "room_id": 1,
        "status": "approved",
        "semester": "2025/2026",
        "requested_at": "2025-01-01T00:00:00+00:00",
        "occupant_count": 1,
    }

    fake_admin = FakeSupabaseAdmin(booking_row)
    monkeypatch.setattr("agile_ci_demo.bookings.supabase_admin", fake_admin)
    monkeypatch.setattr(
        "agile_ci_demo.bookings._room_out_for",
        lambda room_id: RoomOut(
            id=room_id,
            block_name="Block A",
            level=1,
            room_number="101",
            room_type="Single Room",
            capacity=1,
            is_available=True,
            gender_policy="Mixed",
            fee_monthly=100.0,
        ),
    )
    monkeypatch.setattr("agile_ci_demo.bookings._check_capacity_and_gender", lambda *a, **k: None)

    user = SimpleNamespace(id=42, gender="Male")
    booking = update_booking(1, BookingUpdate(room_id=2, occupant_count=1), user)

    assert booking.status == "approved"
    assert booking.room.id == 2
