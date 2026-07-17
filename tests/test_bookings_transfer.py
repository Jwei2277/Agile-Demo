from types import SimpleNamespace

from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import RoomOut


class FakeTable:
    def __init__(self, name, rows=None):
        self._name = name
        self._rows = rows or []
        self._insert_payload = None
        self._update_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def update(self, payload):
        self._update_payload = payload
        return self

    def execute(self):
        if self._name == "bookings":
            return SimpleNamespace(
                data=[
                    {
                        "id": 77,
                        "student_id": "student-1",
                        "room_id": 1,
                        "status": "approved",
                        "semester": "2026/2027",
                        "requested_at": "2026-01-01T00:00:00Z",
                    }
                ]
            )
        if self._name == "room_transfer_requests":
            return SimpleNamespace(
                data=[
                    {
                        "id": 1,
                        "booking_id": 77,
                        "requested_room_id": 2,
                        "reason": "Need a quieter room",
                        "status": "pending",
                        "requested_at": "2026-01-02T00:00:00Z",
                    }
                ]
            )
        return SimpleNamespace(data=[])


class FakeSupabaseAdmin:
    def __init__(self):
        self.tables = {}

    def table(self, name):
        if name not in self.tables:
            self.tables[name] = FakeTable(name)
        return self.tables[name]


client = TestClient(app)


def test_student_can_request_room_transfer_for_approved_booking(monkeypatch):
    fake_supabase = FakeSupabaseAdmin()
    monkeypatch.setattr("agile_ci_demo.bookings.supabase_admin", fake_supabase)
    monkeypatch.setattr(
        "agile_ci_demo.bookings._room_out_for",
        lambda room_id: RoomOut(
            id=room_id,
            block_name="Block A",
            level=1,
            room_number="101" if room_id == 1 else "102",
            room_type="Single Room",
            capacity=1,
            is_available=True,
            gender_policy="Mixed",
            fee_monthly=100.0,
        ),
    )
    monkeypatch.setattr(
        "agile_ci_demo.bookings._check_capacity_and_gender", lambda *args, **kwargs: None
    )
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="student-1",
        email="student@example.com",
        full_name="Student One",
        student_id="SD123456",
        gender="Female",
        role="student",
    )

    response = client.post(
        "/bookings/77/transfer-request",
        json={"room_id": 2, "reason": "Need a quieter room"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["requested_room_id"] == 2

    booking_update_payload = fake_supabase.tables["bookings"]._update_payload
    assert booking_update_payload["status"] == "pending"
    assert booking_update_payload["room_id"] == 2
    assert booking_update_payload["pending_transfer_room_id"] == 2


def teardown_function():
    app.dependency_overrides.clear()
