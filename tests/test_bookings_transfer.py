from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user

client = TestClient(app)


# ============================================================
# Fake Supabase
# ============================================================


class FakeTable:

    def __init__(self, name):

        self.name = name
        self._update_payload = {}
        self.data = []
        self.booking_missing = False

    def select(self, *args):
        return self

    def eq(self, *args):
        return self

    def limit(self, *args):
        return self

    def update(self, payload):

        self._update_payload = payload

        return self

    def insert(self, payload):

        self.data.append(payload)

        return self

    def execute(self):

        if self.name == "bookings":

            if self.booking_missing:

                return type(
                    "Result",
                    (),
                    {"data": []},
                )()

            return type(
                "Result",
                (),
                {
                    "data": [
                        {
                            "id": 77,
                            "student_id": "student-1",
                            "room_id": 1,
                            "status": "approved",
                            "occupant_count": 1,
                            "extra_occupant_gender": None,
                        }
                    ]
                },
            )()

        if self.name == "rooms":

            return type(
                "Result",
                (),
                {
                    "data": [
                        {
                            "id": 2,
                            "hostel_blocks": {"name": "Block A"},
                            "level": 1,
                            "room_number": "102",
                            "room_type": "Single Room",
                            "capacity": 1,
                            "gender_policy": "Mixed",
                            "fee_monthly": 100.0,
                            "photo_url": None,
                        }
                    ]
                },
            )()

        if self.name == "room_transfer_requests":

            return type(
                "Result",
                (),
                {
                    "data": [
                        {
                            "id": 1,
                            "booking_id": 77,
                            "student_id": "student-1",
                            "requested_room_id": 2,
                            "reason": "Need a quieter room",
                            "status": "pending",
                            "requested_at": "2026-07-18T00:00:00Z",
                        }
                    ]
                },
            )()

        return type(
            "Result",
            (),
            {"data": []},
        )()


class FakeSupabaseAdmin:

    def __init__(self, booking_missing=False):

        self.tables = {
            "bookings": FakeTable("bookings"),
            "rooms": FakeTable("rooms"),
            "room_transfer_requests": FakeTable("room_transfer_requests"),
        }

        for table in self.tables.values():

            table.booking_missing = booking_missing

    def table(self, name):

        return self.tables[name]


# ============================================================
# Cleanup
# ============================================================


def teardown_function():

    app.dependency_overrides.clear()


# ============================================================
# Tests
# ============================================================


def test_transfer_request_without_login():

    app.dependency_overrides.clear()

    response = client.post(
        "/bookings/77/transfer-request",
        json={
            "room_id": 2,
            "reason": "Need another room",
        },
    )

    assert response.status_code == 401


def test_transfer_request_with_invalid_booking(monkeypatch):

    fake = FakeSupabaseAdmin(booking_missing=True)

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="student-1",
        email="student@test.com",
        full_name="Student",
        role="student",
    )

    response = client.post(
        "/bookings/999/transfer-request",
        json={
            "room_id": 2,
            "reason": "Move room",
        },
    )

    assert response.status_code == 404


def test_transfer_request_missing_reason():

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="student-1",
        email="student@test.com",
        full_name="Student",
        role="student",
    )

    response = client.post(
        "/bookings/77/transfer-request",
        json={
            "room_id": 2,
        },
    )

    assert response.status_code == 422
