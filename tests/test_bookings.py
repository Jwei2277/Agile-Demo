from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import get_current_user

client = TestClient(app)


# ==========================
# Override User
# ==========================


def override_student():
    return SimpleNamespace(
        id="student001",
        gender="Female",
        role="student",
    )


# ==========================
# Fake Supabase
# ==========================


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:

    def __init__(self, table_data):
        self.data = table_data
        self.operation = None
        self.insert_data = None

    def select(self, *args):
        return self

    def eq(self, column, value):

        self.data = [item for item in self.data if item.get(column) == value]

        return self

    def in_(self, column, values):

        self.data = [item for item in self.data if item.get(column) in values]

        return self

    def limit(self, number):

        self.data = self.data[:number]

        return self

    def order(self, column, desc=False):

        return self

    def insert(self, data):

        self.operation = "insert"
        self.insert_data = data

        return self

    def update(self, data):

        self.operation = "update"
        self.insert_data = data

        return self

    def delete(self):

        self.operation = "delete"

        return self

    def execute(self):

        if self.operation == "insert":

            new_id = len(self.data) + 1

            new_item = {
                "id": new_id,
                **self.insert_data,
                "requested_at": datetime.now(timezone.utc),
            }

            self.data.append(new_item)

            return FakeResponse([new_item])

        if self.operation == "delete":

            deleted = self.data.copy()

            self.data.clear()

            return FakeResponse(deleted)

        if self.operation == "update":

            for item in self.data:
                item.update(self.insert_data)

            return FakeResponse(self.data)

        return FakeResponse(self.data)


class FakeSupabase:

    def __init__(self):

        self.tables = {
            "rooms": [
                {
                    "id": 1,
                    "level": 1,
                    "room_number": "101",
                    "room_type": "Single Room",
                    "capacity": 1,
                    "gender_policy": "Female only",
                    "fee_monthly": 100,
                    "is_active": True,
                },
            ],
            "bookings": [],
        }

    def table(self, name):

        return FakeQuery(self.tables.get(name, []))


# ==========================
# Tests
# ==========================

# BookingCreate requires move_in_date / move_out_date (bookings.py calls
# .isoformat() on both when building the insert payload), so every POST
# /bookings payload below needs them or FastAPI rejects it with a 422
# before the handler even runs.
BOOKING_DATES = {
    "move_in_date": "2025-09-01",
    "move_out_date": "2026-01-01",
}


def test_create_booking(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "semester": "Semester 1",
            "occupant_count": 1,
            **BOOKING_DATES,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["status"] == "pending"


def test_get_my_booking(monkeypatch):

    fake = FakeSupabase()

    fake.tables["bookings"].append(
        {
            "id": 1,
            "student_id": "student001",
            "room_id": 1,
            "semester": "Semester 1",
            "status": "approved",
            "occupant_count": 1,
            "requested_at": datetime.now(timezone.utc),
            # _booking_out() reads these as row["move_in_date"] /
            # row["move_out_date"] (hard indexing, not .get), so they must
            # be present on the fake row.
            "move_in_date": "2025-09-01",
            "move_out_date": "2026-01-01",
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/bookings/me")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "approved"


def test_create_double_booking_should_fail(monkeypatch):

    fake = FakeSupabase()

    fake.tables["bookings"].append(
        {
            "id": 1,
            "student_id": "student001",
            "room_id": 1,
            "status": "approved",
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "semester": "Semester 1",
            "occupant_count": 1,
            **BOOKING_DATES,
        },
    )

    assert response.status_code in [
        400,
        409,
    ]


def test_cancel_booking(monkeypatch):

    fake = FakeSupabase()

    fake.tables["bookings"].append(
        {
            "id": 1,
            "student_id": "student001",
            "room_id": 1,
            "status": "approved",
            "occupant_count": 1,
            "semester": "Semester 1",
            "requested_at": datetime.now(timezone.utc),
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/bookings/1")

    assert response.status_code == 204


def test_invalid_room_booking(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/bookings",
        json={
            "room_id": 999,
            "semester": "Semester 1",
            "occupant_count": 1,
            **BOOKING_DATES,
        },
    )

    assert response.status_code == 404
