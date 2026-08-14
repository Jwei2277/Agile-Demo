from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user

client = TestClient(app)


# ============================================================
# Fake Response
# ============================================================


class FakeResponse:
    def __init__(self, data):

        self.data = data


# ============================================================
# Fake Query
# ============================================================


class FakeQuery:
    def __init__(self, table):

        self.table = table
        self.data = table

    def select(self, *args):

        return self

    def eq(self, column, value):

        self.data = [row for row in self.data if row.get(column) == value]

        return self

    def in_(self, column, values):

        self.data = [row for row in self.data if row.get(column) in values]

        return self

    def order(self, *args, **kwargs):

        return self

    def limit(self, number):

        self.data = self.data[:number]

        return self

    def insert(self, payload):

        new_id = len(self.table) + 1

        row = {
            "id": new_id,
            **payload,
        }

        self.table.append(row)

        self.data = [row]

        return self

    def update(self, payload):

        for row in self.data:
            row.update(payload)

        return self

    def delete(self):

        return self

    def execute(self):

        return FakeResponse(self.data)


# ============================================================
# Fake Supabase
# ============================================================


class FakeSupabase:
    def __init__(self):

        self.tables = {
            "rooms": [
                {
                    "id": 1,
                    "block_id": 1,
                    "level": 1,
                    "room_number": "101",
                    "room_type": "Single Room",
                    "capacity": 1,
                    "gender_policy": "Male only",
                    "fee_monthly": 120,
                    "is_active": True,
                    "hostel_blocks": {
                        "name": "Block A",
                    },
                }
            ],
            "bookings": [
                {
                    "id": 1,
                    "student_id": "student001",
                    "room_id": 1,
                    "semester": "Semester 1",
                    "status": "pending",
                    "move_in_date": "2026-09-01",
                    "move_out_date": "2027-01-15",
                    "requested_at": datetime.now(UTC).isoformat(),
                    "occupant_count": 1,
                    "extra_occupant_name": None,
                    "extra_occupant_email": None,
                    "extra_occupant_student_id": None,
                    "extra_occupant_gender": None,
                }
            ],
            "room_transfer_requests": [],
        }

    def table(self, name):

        return FakeQuery(self.tables.get(name, []))


# ============================================================
# Fake User
# ============================================================


def override_student():

    return CurrentUser(
        id="student001",
        email="student@test.com",
        full_name="John Tan",
        student_id="TP123456",
        gender="Male",
        role="student",
    )


def override_student_female():

    return CurrentUser(
        id="student002",
        email="mary@test.com",
        full_name="Mary",
        student_id="TP654321",
        gender="Female",
        role="student",
    )


# ============================================================
# Cleanup
# ============================================================


@pytest.fixture(autouse=True)
def cleanup():

    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


# ============================================================
# Create Booking Tests
# ============================================================


def test_create_booking_existing_booking(monkeypatch):
    """
    Student already has a booking.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 1,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-15",
        "occupant_count": 1,
    }

    response = client.post("/bookings", json=payload)

    assert response.status_code == 409

    print("test_create_booking_existing_booking PASSED")


def test_create_booking_room_not_found(monkeypatch):
    """
    Selected room does not exist.
    """

    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    def room_not_found(room_id):
        raise ValueError("Room not found")

    monkeypatch.setattr(
        "agile_ci_demo.bookings._room_out_for",
        room_not_found,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 99,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-15",
        "occupant_count": 1,
    }

    response = client.post("/bookings", json=payload)

    assert response.status_code == 404

    print("test_create_booking_room_not_found PASSED")


def test_create_booking_room_unavailable(monkeypatch):
    """
    Room already occupied.
    """

    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings._room_out_for",
        lambda room_id: type(
            "Room",
            (),
            {
                "id": 1,
                "room_number": "101",
                "room_type": "Single Room",
                "capacity": 1,
                "gender_policy": "Male only",
                "fee_monthly": 120,
                "is_available": False,
            },
        )(),
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 1,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-15",
        "occupant_count": 1,
    }

    response = client.post("/bookings", json=payload)

    assert response.status_code == 409

    print("test_create_booking_room_unavailable PASSED")


def test_create_booking_capacity_exceeded(monkeypatch):
    """
    Occupant count exceeds room capacity.
    """

    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings._room_out_for",
        lambda room_id: type(
            "Room",
            (),
            {
                "id": 1,
                "room_number": "101",
                "room_type": "Single Room",
                "capacity": 1,
                "gender_policy": "Male only",
                "fee_monthly": 120,
                "is_available": True,
            },
        )(),
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 1,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-15",
        "occupant_count": 2,
        "extra_occupant_gender": "Male",
    }

    response = client.post("/bookings", json=payload)

    assert response.status_code == 422

    print("test_create_booking_capacity_exceeded PASSED")


def test_create_booking_gender_restriction(monkeypatch):
    """
    Female student books male-only room.
    """

    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings._room_out_for",
        lambda room_id: type(
            "Room",
            (),
            {
                "id": 1,
                "room_number": "101",
                "room_type": "Single Room",
                "capacity": 1,
                "gender_policy": "Male only",
                "fee_monthly": 120,
                "is_available": True,
            },
        )(),
    )

    app.dependency_overrides[get_current_user] = override_student_female

    payload = {
        "room_id": 1,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-15",
        "occupant_count": 1,
    }

    response = client.post("/bookings", json=payload)

    assert response.status_code == 403

    print("test_create_booking_gender_restriction PASSED")


# ============================================================
# Get My Booking Tests
# ============================================================


def test_get_my_booking_none(monkeypatch):
    """
    Student has no booking.
    """

    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/bookings/me")

    assert response.status_code == 200

    assert response.json() is None

    print("test_get_my_booking_none PASSED")


# ============================================================
# Update Booking Tests
# ============================================================


def test_update_booking_not_found(monkeypatch):
    """
    Booking ID not found.
    """

    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 1,
        "occupant_count": 1,
    }

    response = client.patch(
        "/bookings/99",
        json=payload,
    )

    assert response.status_code == 404

    print("test_update_booking_not_found PASSED")


def test_update_booking_not_owner(monkeypatch):
    """
    Student edits another student's booking.
    """

    fake = FakeSupabase()

    fake.tables["bookings"][0]["student_id"] = "another-user"

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 1,
        "occupant_count": 1,
    }

    response = client.patch(
        "/bookings/1",
        json=payload,
    )

    assert response.status_code == 403

    print("test_update_booking_not_owner PASSED")


def test_update_booking_already_approved(monkeypatch):
    """
    Approved booking cannot be edited.
    """

    fake = FakeSupabase()

    fake.tables["bookings"][0]["status"] = "approved"

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 1,
        "occupant_count": 1,
    }

    response = client.patch(
        "/bookings/1",
        json=payload,
    )

    assert response.status_code == 409

    print("test_update_booking_already_approved PASSED")


def test_update_booking_room_unavailable(monkeypatch):
    """
    Student changes to occupied room.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings._room_out_for",
        lambda room_id: type(
            "Room",
            (),
            {
                "id": room_id,
                "room_number": "102",
                "room_type": "Single Room",
                "capacity": 1,
                "gender_policy": "Male only",
                "fee_monthly": 120,
                "is_available": False,
            },
        )(),
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 2,
        "occupant_count": 1,
    }

    response = client.patch(
        "/bookings/1",
        json=payload,
    )

    assert response.status_code == 409

    print("test_update_booking_room_unavailable PASSED")


# ============================================================
# Transfer Request Tests
# ============================================================


def test_request_room_transfer(monkeypatch):
    """
    Student requests a room transfer successfully.
    """

    fake = FakeSupabase()

    fake.tables["bookings"][0]["status"] = "approved"

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings._room_out_for",
        lambda room_id: type(
            "Room",
            (),
            {
                "id": room_id,
                "room_number": "102",
                "room_type": "Single Room",
                "capacity": 1,
                "gender_policy": "Male only",
                "fee_monthly": 120,
                "is_available": True,
            },
        )(),
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 2,
        "reason": "Near classroom",
    }

    response = client.post(
        "/bookings/1/transfer-request",
        json=payload,
    )

    assert response.status_code == 200

    print("test_request_room_transfer PASSED")


def test_transfer_booking_not_found(monkeypatch):
    """
    Booking not found.
    """

    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 2,
        "reason": "Near classroom",
    }

    response = client.post(
        "/bookings/99/transfer-request",
        json=payload,
    )

    assert response.status_code == 404

    print("test_transfer_booking_not_found PASSED")


def test_transfer_not_owner(monkeypatch):
    """
    Student requests transfer for another user's booking.
    """

    fake = FakeSupabase()

    fake.tables["bookings"][0]["student_id"] = "someone"

    fake.tables["bookings"][0]["status"] = "approved"

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 2,
        "reason": "Near classroom",
    }

    response = client.post(
        "/bookings/1/transfer-request",
        json=payload,
    )

    assert response.status_code == 403

    print("test_transfer_not_owner PASSED")


def test_transfer_booking_not_approved(monkeypatch):
    """
    Only approved bookings can request transfers.
    """

    fake = FakeSupabase()

    fake.tables["bookings"][0]["status"] = "pending"

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "room_id": 2,
        "reason": "Near classroom",
    }

    response = client.post(
        "/bookings/1/transfer-request",
        json=payload,
    )

    assert response.status_code == 409

    print("test_transfer_booking_not_approved PASSED")


# ============================================================
# Cancel Booking Tests
# ============================================================


def test_cancel_booking(monkeypatch):
    """
    Student cancels booking.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.notify_next_waitlisted",
        lambda room_id: None,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/bookings/1")

    assert response.status_code == 204

    print("test_cancel_booking PASSED")


def test_cancel_booking_not_found(monkeypatch):
    """
    Booking ID does not exist.
    """

    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/bookings/99")

    assert response.status_code == 404

    print("test_cancel_booking_not_found PASSED")


def test_cancel_booking_not_owner(monkeypatch):
    """
    Student tries to cancel another student's booking.
    """

    fake = FakeSupabase()

    fake.tables["bookings"][0]["student_id"] = "another-user"

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/bookings/1")

    assert response.status_code == 403

    print("test_cancel_booking_not_owner PASSED")


def test_cancel_booking_closed(monkeypatch):
    """
    Booking already closed.
    """

    fake = FakeSupabase()

    fake.tables["bookings"][0]["status"] = "cancelled"

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/bookings/1")

    assert response.status_code == 409

    print("test_cancel_booking_closed PASSED")
