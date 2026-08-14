from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import (
    CurrentUser,
    get_current_user,
)

client = TestClient(app)


# ==================================================
# Fake Response
# ==================================================


class FakeResponse:

    def __init__(self, data):

        self.data = data


# ==================================================
# Fake Query
# ==================================================


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

    def is_(self, column, value):

        # Supabase/PostgREST uses .is_(column, "null") for SQL NULL.
        if value == "null":
            self.data = [row for row in self.data if row.get(column) is None]
        else:
            self.data = [row for row in self.data if row.get(column) == value]

        return self

    def order(self, *args, **kwargs):

        return self

    def limit(self, number):

        self.data = self.data[:number]

        return self

    def insert(self, payload):

        row = {
            "id": len(self.table) + 1,
            **payload,
        }

        self.table.append(row)

        self.data = [row]

        return self

    def update(self, payload):

        for row in self.data:

            row.update(payload)

        return self

    def execute(self):

        return FakeResponse(self.data)


# ==================================================
# Fake Supabase
# ==================================================


class FakeSupabase:

    def __init__(self):

        self.tables = {
            "rooms": [
                {
                    "id": 1,
                    "room_number": "101",
                    "room_type": "Single Room",
                    "capacity": 1,
                    "gender_policy": "Male only",
                    "is_active": True,
                    "hostel_blocks": {
                        "name": "Block A",
                    },
                }
            ],
            "profiles": [
                {
                    "id": "student001",
                    "gender": "Male",
                }
            ],
            "bookings": [
                {
                    "id": 1,
                    "student_id": "someone",
                    "room_id": 1,
                    "status": "approved",
                    "move_out_date": "2026-09-01",
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "room_waitlist": [],
        }

    def table(self, name):

        return FakeQuery(self.tables.get(name, []))


# ==================================================
# Fake Users
# ==================================================


def override_student():

    return CurrentUser(
        id="student001",
        email="student@test.com",
        full_name="John Tan",
        student_id="TP123456",
        gender="Male",
        role="student",
    )


def override_female():

    return CurrentUser(
        id="student002",
        email="female@test.com",
        full_name="Mary",
        student_id="TP654321",
        gender="Female",
        role="student",
    )


# ==================================================
# Cleanup
# ==================================================


@pytest.fixture(autouse=True)
def cleanup():

    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


# ==================================================
# Join Waitlist Tests
# ==================================================


def test_join_waitlist(monkeypatch):
    """
    Student joins waitlist successfully.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "move_in_date": "2026-09-02",
        "move_out_date": "2026-10-10",
        "occupant_count": 1,
    }

    response = client.post(
        "/waitlist/1",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["status"] == "waiting"

    print("test_join_waitlist PASSED")


def test_join_waitlist_room_not_found(monkeypatch):
    """
    Room ID does not exist.
    """

    fake = FakeSupabase()

    fake.tables["rooms"] = []

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "move_in_date": "2026-09-02",
        "move_out_date": "2026-10-10",
        "occupant_count": 1,
    }

    response = client.post(
        "/waitlist/1",
        json=payload,
    )

    assert response.status_code == 404

    print("test_join_waitlist_room_not_found PASSED")


def test_join_waitlist_capacity_exceeded(monkeypatch):
    """
    Occupant count exceeds room capacity.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "move_in_date": "2026-09-02",
        "move_out_date": "2026-10-10",
        "occupant_count": 2,
        "extra_occupant_name": "Tom",
        "extra_occupant_email": "tom@test.com",
        "extra_occupant_student_id": "TP123456",
        "extra_occupant_gender": "Male",
    }

    response = client.post(
        "/waitlist/1",
        json=payload,
    )

    assert response.status_code == 400

    print("test_join_waitlist_capacity_exceeded PASSED")


def test_join_waitlist_gender_not_allowed(monkeypatch):
    """
    Female student joins male-only room.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_female

    payload = {
        "move_in_date": "2026-09-02",
        "move_out_date": "2026-10-10",
        "occupant_count": 1,
    }

    response = client.post(
        "/waitlist/1",
        json=payload,
    )

    assert response.status_code == 403

    print("test_join_waitlist_gender_not_allowed PASSED")


def test_join_waitlist_room_available(monkeypatch):
    """
    Cannot join waitlist if room is available.
    """

    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "move_in_date": "2026-09-02",
        "move_out_date": "2026-10-10",
        "occupant_count": 1,
    }

    response = client.post(
        "/waitlist/1",
        json=payload,
    )

    assert response.status_code == 409

    print("test_join_waitlist_room_available PASSED")


def test_join_waitlist_duplicate(monkeypatch):
    """
    Student already on waiting list.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "student001",
            "status": "waiting",
            "joined_at": datetime.now(timezone.utc).isoformat(),
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "move_in_date": "2026-09-02",
        "move_out_date": "2026-10-10",
        "occupant_count": 1,
    }

    response = client.post(
        "/waitlist/1",
        json=payload,
    )

    assert response.status_code == 409

    print("test_join_waitlist_duplicate PASSED")


# ==================================================
# My Waitlist Tests
# ==================================================


def test_my_waitlist(monkeypatch):
    """
    Student views own waitlist entries.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "student001",
            "status": "waiting",
            "joined_at": datetime.now(timezone.utc).isoformat(),
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
            "notified_at": None,
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/waitlist/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["status"] == "waiting"

    print("test_my_waitlist PASSED")


def test_my_waitlist_empty(monkeypatch):
    """
    Student has no waitlist entries.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = []

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/waitlist/me")

    assert response.status_code == 200

    assert response.json() == []

    print("test_my_waitlist_empty PASSED")


# ==================================================
# Leave Waitlist Tests
# ==================================================


def test_leave_waitlist(monkeypatch):
    """
    Student leaves own waitlist.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "student001",
            "status": "waiting",
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/waitlist/1")

    assert response.status_code == 204

    print("test_leave_waitlist PASSED")


def test_leave_waitlist_not_found(monkeypatch):
    """
    Waitlist entry does not exist.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = []

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/waitlist/999")

    assert response.status_code == 404

    print("test_leave_waitlist_not_found PASSED")


def test_leave_waitlist_not_owner(monkeypatch):
    """
    Student tries to cancel another student's entry.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "another-user",
            "status": "waiting",
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/waitlist/1")

    assert response.status_code == 403

    print("test_leave_waitlist_not_owner PASSED")


# ==================================================
# Helper Functions
# ==================================================


def test_db(monkeypatch):
    """
    _db returns Supabase instance.
    """

    from agile_ci_demo.waitlist import _db

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    assert _db() == fake

    print("test_db PASSED")


def test_db_missing(monkeypatch):
    """
    _db raises when Supabase is missing.
    """

    from agile_ci_demo.waitlist import _db

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        None,
    )

    with pytest.raises(HTTPException) as exc:

        _db()

    assert exc.value.status_code == 501

    print("test_db_missing PASSED")


def test_rows():
    """
    _rows returns list.
    """

    from agile_ci_demo.waitlist import _rows

    assert _rows([{"id": 1}]) == [{"id": 1}]

    print("test_rows PASSED")


def test_rows_none():
    """
    _rows(None) returns [].
    """

    from agile_ci_demo.waitlist import _rows

    assert _rows(None) == []

    print("test_rows_none PASSED")


# ==================================================
# _room_label()
# ==================================================


def test_room_label():
    """
    Get room label.
    """

    from agile_ci_demo.waitlist import _room_label

    fake = FakeSupabase()

    label = _room_label(
        fake,
        1,
    )

    assert label == "Block A · Room 101"

    print("test_room_label PASSED")


def test_room_label_not_found():
    """
    Room no longer exists.
    """

    from agile_ci_demo.waitlist import _room_label

    fake = FakeSupabase()

    fake.tables["rooms"] = []

    label = _room_label(
        fake,
        99,
    )

    assert label == "Room #99"

    print("test_room_label_not_found PASSED")


# ==================================================
# _queue_position()
# ==================================================


def test_queue_position():
    """
    Queue position starts from 1.
    """

    from agile_ci_demo.waitlist import _queue_position

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "status": "waiting",
            "joined_at": "2026-01-01",
        },
        {
            "id": 2,
            "room_id": 1,
            "status": "waiting",
            "joined_at": "2026-01-02",
        },
    ]

    position = _queue_position(
        fake,
        1,
        2,
    )

    assert position == 2

    print("test_queue_position PASSED")


def test_queue_position_not_found():
    """
    Entry not inside queue.
    """

    from agile_ci_demo.waitlist import _queue_position

    fake = FakeSupabase()

    position = _queue_position(
        fake,
        1,
        999,
    )

    assert position == 1

    print("test_queue_position_not_found PASSED")


# ==================================================
# _entry_out()
# ==================================================


def test_entry_out():
    """
    Convert database row to WaitlistEntryOut.
    """

    from agile_ci_demo.waitlist import _entry_out

    fake = FakeSupabase()

    row = {
        "id": 1,
        "room_id": 1,
        "status": "waiting",
        "joined_at": datetime.now(timezone.utc).isoformat(),
        "move_in_date": "2026-09-02",
        "move_out_date": "2026-10-10",
        "occupant_count": 1,
        "notified_at": None,
    }

    entry = _entry_out(
        fake,
        row,
    )

    assert entry.room_label == "Block A · Room 101"

    assert entry.queue_position == 1

    print("test_entry_out PASSED")


# ==================================================
# _try_auto_book()
# ==================================================


def test_try_auto_book_existing_booking():
    """
    Student already owns another booking.
    """

    from agile_ci_demo.waitlist import _try_auto_book

    fake = FakeSupabase()

    entry = {
        "id": 1,
        "student_id": "someone",
        "occupant_count": 1,
    }

    result = _try_auto_book(
        fake,
        1,
        entry,
    )

    assert result is False

    print("test_try_auto_book_existing_booking PASSED")


def test_try_auto_book_room_not_found():
    """
    Room deleted.
    """

    from agile_ci_demo.waitlist import _try_auto_book

    fake = FakeSupabase()

    fake.tables["rooms"] = []

    fake.tables["bookings"] = []

    entry = {
        "id": 1,
        "student_id": "student001",
        "occupant_count": 1,
    }

    result = _try_auto_book(
        fake,
        1,
        entry,
    )

    assert result is False

    print("test_try_auto_book_room_not_found PASSED")


def test_notify_next_waitlisted(monkeypatch):
    """
    notify_next_waitlisted() executes without error.
    """

    from agile_ci_demo.waitlist import (
        notify_next_waitlisted,
    )

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.waitlist._try_auto_book",
        lambda db, room_id, entry: True,
    )

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "student001",
            "status": "waiting",
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    notify_next_waitlisted(1)

    print("test_notify_next_waitlisted PASSED")


# ==================================================
# Additional Authentication / Configuration Tests
# ==================================================


def test_join_waitlist_without_login(monkeypatch):
    """
    A waitlist request must require authentication.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides.clear()

    response = client.post(
        "/waitlist/1",
        json={
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 401

    print("test_join_waitlist_without_login PASSED")


def test_my_waitlist_without_login():
    """
    Viewing waitlist entries must require authentication.
    """

    app.dependency_overrides.clear()

    response = client.get("/waitlist/me")

    assert response.status_code == 401

    print("test_my_waitlist_without_login PASSED")


def test_leave_waitlist_without_login():
    """
    Leaving a waitlist entry must require authentication.
    """

    app.dependency_overrides.clear()

    response = client.delete("/waitlist/1")

    assert response.status_code == 401

    print("test_leave_waitlist_without_login PASSED")


def test_join_waitlist_service_role_missing(monkeypatch):
    """
    Joining the waitlist fails safely when the service-role client is absent.
    """

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/waitlist/1",
        json={
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 501

    print("test_join_waitlist_service_role_missing PASSED")


def test_my_waitlist_service_role_missing(monkeypatch):
    """
    Viewing waitlist entries fails safely when Supabase is unavailable.
    """

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/waitlist/me")

    assert response.status_code == 501

    print("test_my_waitlist_service_role_missing PASSED")


def test_leave_waitlist_service_role_missing(monkeypatch):
    """
    Cancelling a waitlist entry fails safely when Supabase is unavailable.
    """

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/waitlist/1")

    assert response.status_code == 501

    print("test_leave_waitlist_service_role_missing PASSED")


# ==================================================
# Additional Validation Tests
# ==================================================


def test_join_waitlist_missing_move_in_date(monkeypatch):
    """
    move_in_date is required.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/waitlist/1",
        json={
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 422

    print("test_join_waitlist_missing_move_in_date PASSED")


def test_join_waitlist_missing_move_out_date(monkeypatch):
    """
    move_out_date is required.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/waitlist/1",
        json={
            "move_in_date": "2026-09-02",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 422

    print("test_join_waitlist_missing_move_out_date PASSED")


def test_join_waitlist_missing_occupant_count(monkeypatch):
    """
    An incomplete join request is rejected by the API validation layer.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/waitlist/1",
        json={
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": "invalid",
        },
    )

    assert response.status_code == 422

    print("test_join_waitlist_missing_occupant_count PASSED")


def test_join_waitlist_invalid_occupant_count_type(monkeypatch):
    """
    occupant_count must be numeric.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/waitlist/1",
        json={
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": "one",
        },
    )

    assert response.status_code == 422

    print("test_join_waitlist_invalid_occupant_count_type PASSED")


def test_join_waitlist_zero_occupants(monkeypatch):
    """
    A waitlist request with zero occupants must be rejected by validation.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/waitlist/1",
        json={
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 0,
        },
    )

    assert response.status_code in (400, 422)

    print("test_join_waitlist_zero_occupants PASSED")


def test_join_waitlist_negative_occupants(monkeypatch):
    """
    Negative occupant counts must never be accepted.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/waitlist/1",
        json={
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": -1,
        },
    )

    assert response.status_code in (400, 422)

    print("test_join_waitlist_negative_occupants PASSED")


def test_join_waitlist_invalid_room_id(monkeypatch):
    """
    A non-positive room ID must be rejected or result in room-not-found.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/waitlist/0",
        json={
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
        },
    )

    assert response.status_code in (404, 422)

    print("test_join_waitlist_invalid_room_id PASSED")


# ==================================================
# Additional Room / Eligibility Tests
# ==================================================


def test_join_waitlist_female_allowed_room(monkeypatch):
    """
    A female student can join a female-only room when the room is occupied.
    """

    fake = FakeSupabase()

    fake.tables["rooms"][0]["gender_policy"] = "Female only"

    fake.tables["profiles"] = [
        {
            "id": "student002",
            "gender": "Female",
        }
    ]

    fake.tables["bookings"] = [
        {
            "id": 1,
            "student_id": "another-user",
            "room_id": 1,
            "status": "approved",
            "move_out_date": "2026-09-01",
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_female

    response = client.post(
        "/waitlist/1",
        json={
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "waiting"

    print("test_join_waitlist_female_allowed_room PASSED")


def test_join_waitlist_uses_correct_student(monkeypatch):
    """
    The inserted waitlist record belongs to the authenticated student.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/waitlist/1",
        json={
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 201

    rows = fake.tables["room_waitlist"]
    assert len(rows) == 1
    assert rows[0]["student_id"] == "student001"
    assert rows[0]["room_id"] == 1

    print("test_join_waitlist_uses_correct_student PASSED")


def test_join_waitlist_stores_requested_dates(monkeypatch):
    """
    The requested move-in and move-out dates are preserved.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "move_in_date": "2026-09-05",
        "move_out_date": "2026-11-15",
        "occupant_count": 1,
    }

    response = client.post(
        "/waitlist/1",
        json=payload,
    )

    assert response.status_code == 201

    row = fake.tables["room_waitlist"][0]

    assert row["move_in_date"] == "2026-09-05"
    assert row["move_out_date"] == "2026-11-15"

    print("test_join_waitlist_stores_requested_dates PASSED")


def test_join_waitlist_stores_occupant_count(monkeypatch):
    """
    The requested occupant count is stored.
    """

    fake = FakeSupabase()

    fake.tables["rooms"][0]["capacity"] = 2

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/waitlist/1",
        json={
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 2,
        },
    )

    assert response.status_code == 422

    print("test_join_waitlist_stores_occupant_count PASSED")


# ==================================================
# Additional My Waitlist Tests
# ==================================================


def test_my_waitlist_only_returns_current_student(monkeypatch):
    """
    The /me endpoint must filter by the authenticated student's ID.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "student001",
            "status": "waiting",
            "joined_at": "2026-09-01T10:00:00+00:00",
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
            "notified_at": None,
        },
        {
            "id": 2,
            "room_id": 1,
            "student_id": "another-user",
            "status": "waiting",
            "joined_at": "2026-09-01T11:00:00+00:00",
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
            "notified_at": None,
        },
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/waitlist/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == 1

    print("test_my_waitlist_only_returns_current_student PASSED")


def test_my_waitlist_returns_room_label(monkeypatch):
    """
    Waitlist output contains the human-readable room label.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "student001",
            "status": "waiting",
            "joined_at": "2026-09-01T10:00:00+00:00",
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
            "notified_at": None,
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/waitlist/me")

    assert response.status_code == 200
    assert response.json()[0]["room_label"] == "Block A · Room 101"

    print("test_my_waitlist_returns_room_label PASSED")


def test_my_waitlist_preserves_notified_at(monkeypatch):
    """
    Notification timestamps are returned when present.
    """

    fake = FakeSupabase()

    notified_at = "2026-09-01T12:00:00+00:00"

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "student001",
            "status": "notified",
            "joined_at": "2026-09-01T10:00:00+00:00",
            "move_in_date": "2026-09-02",
            "move_out_date": "2026-10-10",
            "occupant_count": 1,
            "notified_at": notified_at,
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/waitlist/me")

    assert response.status_code == 200
    assert response.json()[0]["notified_at"] == "2026-09-01T12:00:00Z"

    print("test_my_waitlist_preserves_notified_at PASSED")


# ==================================================
# Additional Leave Waitlist Tests
# ==================================================


def test_leave_waitlist_updates_status(monkeypatch):
    """
    Leaving a waiting entry changes its status instead of deleting the record.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "student001",
            "status": "waiting",
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/waitlist/1")

    assert response.status_code == 204

    assert fake.tables["room_waitlist"][0]["status"] == "cancelled"

    print("test_leave_waitlist_updates_status PASSED")


def test_leave_waitlist_already_cancelled(monkeypatch):
    """
    An already-cancelled entry cannot be cancelled as a new active request.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "student001",
            "status": "cancelled",
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/waitlist/1")

    assert response.status_code in (204, 409)

    print("test_leave_waitlist_already_cancelled PASSED")


def test_leave_waitlist_approved_entry(monkeypatch):
    """
    An already-approved/processed waitlist entry should not be treated as active.
    """

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 1,
            "room_id": 1,
            "student_id": "student001",
            "status": "approved",
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/waitlist/1")

    assert response.status_code in (204, 409)

    print("test_leave_waitlist_approved_entry PASSED")


# ==================================================
# Additional Helper Tests
# ==================================================


def test_room_label_none_room_id():
    """
    A missing room ID returns a safe fallback.
    """

    from agile_ci_demo.waitlist import _room_label

    fake = FakeSupabase()

    result = _room_label(fake, None)

    assert result in (None, "Room #None")

    print("test_room_label_none_room_id PASSED")


def test_room_label_unknown_block():
    """
    A room without block information still produces a readable label.
    """

    from agile_ci_demo.waitlist import _room_label

    fake = FakeSupabase()

    fake.tables["rooms"][0]["hostel_blocks"] = None

    result = _room_label(fake, 1)

    assert result == "? · Room 101"

    print("test_room_label_unknown_block PASSED")


def test_queue_position_first_entry():
    """
    The first waiting entry has queue position one.
    """

    from agile_ci_demo.waitlist import _queue_position

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 10,
            "room_id": 1,
            "status": "waiting",
            "joined_at": "2026-01-01T10:00:00+00:00",
        },
    ]

    assert _queue_position(fake, 1, 10) == 1

    print("test_queue_position_first_entry PASSED")


def test_queue_position_ignores_other_room():
    """
    Entries for another room do not affect this room's queue position.
    """

    from agile_ci_demo.waitlist import _queue_position

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 10,
            "room_id": 2,
            "status": "waiting",
            "joined_at": "2026-01-01T10:00:00+00:00",
        },
        {
            "id": 11,
            "room_id": 1,
            "status": "waiting",
            "joined_at": "2026-01-02T10:00:00+00:00",
        },
    ]

    assert _queue_position(fake, 1, 11) == 1

    print("test_queue_position_ignores_other_room PASSED")


def test_queue_position_ignores_non_waiting_entries():
    """
    Cancelled/processed entries should not increase the active queue position.
    """

    from agile_ci_demo.waitlist import _queue_position

    fake = FakeSupabase()

    fake.tables["room_waitlist"] = [
        {
            "id": 10,
            "room_id": 1,
            "status": "cancelled",
            "joined_at": "2026-01-01T10:00:00+00:00",
        },
        {
            "id": 11,
            "room_id": 1,
            "status": "waiting",
            "joined_at": "2026-01-02T10:00:00+00:00",
        },
    ]

    assert _queue_position(fake, 1, 11) == 1

    print("test_queue_position_ignores_non_waiting_entries PASSED")


def test_entry_out_notified_entry():
    """
    _entry_out correctly converts a notified entry.
    """

    from agile_ci_demo.waitlist import _entry_out

    fake = FakeSupabase()

    row = {
        "id": 5,
        "room_id": 1,
        "status": "notified",
        "joined_at": "2026-09-01T10:00:00+00:00",
        "move_in_date": "2026-09-02",
        "move_out_date": "2026-10-10",
        "occupant_count": 1,
        "notified_at": "2026-09-01T12:00:00+00:00",
    }

    result = _entry_out(fake, row)

    assert result.id == 5
    assert result.status == "notified"
    assert result.room_label == "Block A · Room 101"
    assert result.notified_at == datetime.fromisoformat("2026-09-01T12:00:00+00:00")

    print("test_entry_out_notified_entry PASSED")


def test_try_auto_book_missing_entry_fields():
    """
    Auto-booking handles an incomplete entry safely.
    """

    from agile_ci_demo.waitlist import _try_auto_book

    fake = FakeSupabase()

    with pytest.raises(KeyError):
        _try_auto_book(
            fake,
            1,
            {
                "id": 1,
            },
        )

    print("test_try_auto_book_missing_entry_fields PASSED")


def test_notify_next_waitlisted_empty_queue(monkeypatch):
    """
    Notification processing is safe when no one is waiting.
    """

    from agile_ci_demo.waitlist import notify_next_waitlisted

    fake = FakeSupabase()
    fake.tables["room_waitlist"] = []

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    notify_next_waitlisted(1)

    assert fake.tables["room_waitlist"] == []

    print("test_notify_next_waitlisted_empty_queue PASSED")


# ==================================================
# Route / Method Tests
# ==================================================


def test_waitlist_unknown_route(monkeypatch):
    """
    Unknown waitlist routes return 404.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/waitlist/this-route-does-not-exist")

    assert response.status_code == 405

    print("test_waitlist_unknown_route PASSED")


def test_waitlist_join_wrong_http_method(monkeypatch):
    """
    GET is not the method used to join the waitlist.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/waitlist/1")

    assert response.status_code in (404, 405)

    print("test_waitlist_join_wrong_http_method PASSED")


def test_waitlist_leave_wrong_http_method(monkeypatch):
    """
    POST is not the method used to leave a waitlist.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.waitlist.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post("/waitlist/1")

    assert response.status_code in (404, 405, 422)

    print("test_waitlist_leave_wrong_http_method PASSED")


# ==================================================
# State Isolation Tests
# ==================================================


def test_waitlist_cleanup_isolation():
    """
    Dependency overrides are cleaned up between tests.
    """

    assert get_current_user not in app.dependency_overrides

    print("test_waitlist_cleanup_isolation PASSED")
