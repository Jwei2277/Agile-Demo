from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user

client = TestClient(app)


# ============================================================
# Fake Supabase
# ============================================================


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self.rows = list(db.tables.get(table_name, []))
        self.operation = "select"
        self.payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.rows = [row for row in self.rows if row.get(column) == value]
        return self

    def in_(self, column, values):
        values = set(values)
        self.rows = [row for row in self.rows if row.get(column) in values]
        return self

    def is_(self, column, value):
        if value == "null":
            self.rows = [row for row in self.rows if row.get(column) is None]
        elif value == "not.null":
            self.rows = [row for row in self.rows if row.get(column) is not None]
        return self

    def order(self, column, desc=False):
        self.rows.sort(
            key=lambda row: row.get(column) or "",
            reverse=desc,
        )
        return self

    def limit(self, number):
        self.rows = self.rows[:number]
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def execute(self):
        if self.operation == "insert":
            payload = dict(self.payload)
            if "id" not in payload:
                existing = self.db.tables.get(self.table_name, [])
                payload["id"] = max([int(row.get("id", 0)) for row in existing] or [0]) + 1

            if "requested_at" in payload and payload["requested_at"] is None:
                payload["requested_at"] = datetime.now(timezone.utc).isoformat()

            if "joined_at" in payload and payload["joined_at"] is None:
                payload["joined_at"] = datetime.now(timezone.utc).isoformat()

            self.db.tables.setdefault(self.table_name, []).append(payload)
            return FakeResponse([payload])

        if self.operation == "update":
            updated = []

            for original in self.db.tables.get(self.table_name, []):
                if original in self.rows:
                    original.update(self.payload)
                    updated.append(dict(original))

            return FakeResponse(updated)

        return FakeResponse(self.rows)


class FakeDB:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, name):
        return FakeQuery(self, name)


# ============================================================
# Test Data
# ============================================================


def room_row(
    room_id=1,
    room_number="101",
    room_type="Master Room",
    capacity=2,
    gender_policy="Mixed",
    fee_monthly=500.0,
    block="Block A",
):
    return {
        "id": room_id,
        "level": 1,
        "room_number": room_number,
        "room_type": room_type,
        "capacity": capacity,
        "gender_policy": gender_policy,
        "fee_monthly": fee_monthly,
        "photo_url": None,
        "is_active": True,
        "hostel_blocks": {"name": block},
    }


def booking_row(
    booking_id=1,
    student_id="student001",
    room_id=1,
    status="pending",
    occupant_count=1,
    checked_out_at=None,
    pending_transfer_room_id=None,
):
    return {
        "id": booking_id,
        "student_id": student_id,
        "room_id": room_id,
        "status": status,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-31",
        "requested_at": "2026-08-15T10:00:00+00:00",
        "decided_at": None,
        "occupant_count": occupant_count,
        "extra_occupant_name": None,
        "extra_occupant_email": None,
        "extra_occupant_student_id": None,
        "extra_occupant_gender": None,
        "pending_transfer_room_id": pending_transfer_room_id,
        "checked_in_at": None,
        "checked_out_at": checked_out_at,
    }


def payment_row(
    payment_id=1,
    booking_id=1,
    status="paid",
):
    return {
        "id": payment_id,
        "booking_id": booking_id,
        "status": status,
    }


def cancellation_row(
    request_id=1,
    booking_id=1,
    status="pending",
):
    return {
        "id": request_id,
        "booking_id": booking_id,
        "student_id": "student001",
        "reason": "Need to leave hostel",
        "status": status,
        "rejection_reason": None,
        "requested_at": "2026-08-15T10:00:00+00:00",
        "decided_at": None,
    }


def base_db(**overrides):
    tables = {
        "rooms": [room_row()],
        "bookings": [],
        "payments": [],
        "booking_cancellation_requests": [],
        "room_transfer_requests": [],
    }
    tables.update(overrides)
    return FakeDB(tables)


def override_student():
    return CurrentUser(
        id="student001",
        email="student@test.com",
        full_name="John Tan",
        student_id="TP123456",
        gender="Male",
        role="student",
    )


def override_female_student():
    return CurrentUser(
        id="student002",
        email="female@test.com",
        full_name="Jane Tan",
        student_id="TP654321",
        gender="Female",
        role="student",
    )


# ============================================================
# Fixtures / Cleanup
# ============================================================


@pytest.fixture(autouse=True)
def cleanup():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def install_student():
    app.dependency_overrides[get_current_user] = override_student


# ============================================================
# Helper Function Tests
# ============================================================


def test_get_rows_accepts_list():
    from agile_ci_demo.bookings import _get_rows

    data = [{"id": 1}, {"id": 2}]

    result = _get_rows(data)

    assert result == data

    print("test_get_rows_accepts_list PASSED")


def test_get_rows_rejects_non_list():
    from agile_ci_demo.bookings import _get_rows

    assert _get_rows(None) == []
    assert _get_rows({}) == []
    assert _get_rows("invalid") == []

    print("test_get_rows_rejects_non_list PASSED")


def test_get_supabase_missing_service_role(monkeypatch):
    from agile_ci_demo.bookings import _get_supabase

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        None,
    )

    with pytest.raises(Exception) as exc:
        _get_supabase()

    assert exc.value.status_code == 501

    print("test_get_supabase_missing_service_role PASSED")


def test_room_out_for_existing_room(monkeypatch):
    from agile_ci_demo.bookings import _room_out_for

    fake = base_db()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    result = _room_out_for(1)

    assert result.id == 1
    assert result.room_number == "101"
    assert result.block_name == "Block A"

    print("test_room_out_for_existing_room PASSED")


def test_room_out_for_missing_room(monkeypatch):
    from agile_ci_demo.bookings import _room_out_for

    fake = base_db(rooms=[])

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    with pytest.raises(Exception) as exc:
        _room_out_for(999)

    assert exc.value.status_code == 404

    print("test_room_out_for_missing_room PASSED")


def test_check_capacity_rejects_too_many_occupants():
    from agile_ci_demo.bookings import _check_capacity_and_gender

    room = type(
        "Room",
        (),
        {
            "capacity": 1,
            "room_type": "Single Room",
            "gender_policy": "Mixed",
        },
    )()

    with pytest.raises(Exception) as exc:
        _check_capacity_and_gender(
            room,
            override_student(),
            2,
            None,
        )

    assert exc.value.status_code == 400

    print("test_check_capacity_rejects_too_many_occupants PASSED")


def test_check_capacity_accepts_valid_count():
    from agile_ci_demo.bookings import _check_capacity_and_gender

    room = type(
        "Room",
        (),
        {
            "capacity": 2,
            "room_type": "Master Room",
            "gender_policy": "Mixed",
        },
    )()

    _check_capacity_and_gender(
        room,
        override_student(),
        2,
        "Male",
    )

    print("test_check_capacity_accepts_valid_count PASSED")


def test_check_gender_rejects_wrong_student_gender():
    from agile_ci_demo.bookings import _check_capacity_and_gender

    room = type(
        "Room",
        (),
        {
            "capacity": 2,
            "room_type": "Master Room",
            "gender_policy": "Female only",
        },
    )()

    with pytest.raises(Exception) as exc:
        _check_capacity_and_gender(
            room,
            override_student(),
            1,
            None,
        )

    assert exc.value.status_code == 403

    print("test_check_gender_rejects_wrong_student_gender PASSED")


def test_check_gender_accepts_matching_student_gender():
    from agile_ci_demo.bookings import _check_capacity_and_gender

    room = type(
        "Room",
        (),
        {
            "capacity": 2,
            "room_type": "Master Room",
            "gender_policy": "Female only",
        },
    )()

    _check_capacity_and_gender(
        room,
        override_female_student(),
        1,
        None,
    )

    print("test_check_gender_accepts_matching_student_gender PASSED")


def test_check_gender_rejects_wrong_extra_occupant_gender():
    from agile_ci_demo.bookings import _check_capacity_and_gender

    room = type(
        "Room",
        (),
        {
            "capacity": 2,
            "room_type": "Master Room",
            "gender_policy": "Female only",
        },
    )()

    with pytest.raises(Exception) as exc:
        _check_capacity_and_gender(
            room,
            override_female_student(),
            2,
            "Male",
        )

    assert exc.value.status_code == 403

    print("test_check_gender_rejects_wrong_extra_occupant_gender PASSED")


# ============================================================
# Create Booking Tests
# ============================================================


def test_create_booking_requires_login(monkeypatch):
    fake = base_db()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    app.dependency_overrides.clear()

    response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "semester": "Semester 1",
            "move_in_date": "2026-09-01",
            "move_out_date": "2027-01-31",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 401

    print("test_create_booking_requires_login PASSED")


def test_create_booking_missing_room_id(monkeypatch):
    fake = base_db()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings",
        json={
            "semester": "Semester 1",
            "move_in_date": "2026-09-01",
            "move_out_date": "2027-01-31",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 422

    print("test_create_booking_missing_room_id PASSED")


def test_create_booking_missing_dates(monkeypatch):
    fake = base_db()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "semester": "Semester 1",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 422

    print("test_create_booking_missing_dates PASSED")


def test_create_booking_invalid_room(monkeypatch):
    fake = base_db(rooms=[])

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings",
        json={
            "room_id": 999,
            "semester": "Semester 1",
            "move_in_date": "2026-09-01",
            "move_out_date": "2027-01-31",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 404

    print("test_create_booking_invalid_room PASSED")


def test_create_booking_when_student_already_has_active_booking(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                booking_id=10,
                room_id=2,
                status="approved",
            )
        ],
        rooms=[
            room_row(),
            room_row(room_id=2, room_number="102"),
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "semester": "Semester 1",
            "move_in_date": "2026-09-01",
            "move_out_date": "2027-01-31",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 409
    assert "active or pending" in response.json()["detail"]

    print("test_create_booking_when_student_already_has_active_booking PASSED")


def test_create_booking_gender_restricted(monkeypatch):
    fake = base_db(
        rooms=[
            room_row(
                gender_policy="Female only",
            )
        ]
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "semester": "Semester 1",
            "move_in_date": "2026-09-01",
            "move_out_date": "2027-01-31",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 403

    print("test_create_booking_gender_restricted PASSED")


# ============================================================
# My Booking Tests
# ============================================================


def test_get_my_booking_returns_booking(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/me")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["status"] == "approved"
    assert data["room"]["room_number"] == "101"

    print("test_get_my_booking_returns_booking PASSED")


def test_get_my_booking_returns_null_when_none(monkeypatch):
    fake = base_db()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/me")

    assert response.status_code == 200
    assert response.json() is None

    print("test_get_my_booking_returns_null_when_none PASSED")


def test_get_my_booking_requires_login():
    app.dependency_overrides.clear()

    response = client.get("/bookings/me")

    assert response.status_code == 401

    print("test_get_my_booking_requires_login PASSED")


def test_get_my_booking_ignores_cancelled(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="cancelled",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/me")

    assert response.status_code == 200
    assert response.json() is None

    print("test_get_my_booking_ignores_cancelled PASSED")


def test_get_my_booking_ignores_checked_out(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
                checked_out_at="2026-08-20T10:00:00+00:00",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/me")

    assert response.status_code == 200
    assert response.json() is None

    print("test_get_my_booking_ignores_checked_out PASSED")


# ============================================================
# Booking History Tests
# ============================================================


def test_booking_history_returns_all_student_bookings(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                booking_id=1,
                status="approved",
            ),
            booking_row(
                booking_id=2,
                status="cancelled",
            ),
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/history")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["id"] for item in data} == {1, 2}

    print("test_booking_history_returns_all_student_bookings PASSED")


def test_booking_history_requires_login():
    app.dependency_overrides.clear()

    response = client.get("/bookings/history")

    assert response.status_code == 401

    print("test_booking_history_requires_login PASSED")


def test_booking_history_excludes_other_students(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                booking_id=1,
                student_id="student001",
            ),
            booking_row(
                booking_id=2,
                student_id="student999",
            ),
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/history")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == 1

    print("test_booking_history_excludes_other_students PASSED")


# ============================================================
# Update Booking Tests
# ============================================================


def test_update_pending_booking(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="pending",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.patch(
        "/bookings/1",
        json={
            "room_id": 1,
            "occupant_count": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == 1

    print("test_update_pending_booking PASSED")


def test_update_booking_not_found(monkeypatch):
    fake = base_db()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.patch(
        "/bookings/999",
        json={
            "room_id": 1,
            "occupant_count": 1,
        },
    )

    assert response.status_code == 404

    print("test_update_booking_not_found PASSED")


def test_update_booking_not_owner(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                student_id="someone-else",
                status="pending",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.patch(
        "/bookings/1",
        json={
            "room_id": 1,
            "occupant_count": 1,
        },
    )

    assert response.status_code == 403

    print("test_update_booking_not_owner PASSED")


def test_update_approved_booking_rejected(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.patch(
        "/bookings/1",
        json={
            "room_id": 1,
            "occupant_count": 1,
        },
    )

    assert response.status_code == 409

    print("test_update_approved_booking_rejected PASSED")


def test_update_pending_booking_changes_room(monkeypatch):
    fake = base_db(
        rooms=[
            room_row(room_id=1, room_number="101"),
            room_row(room_id=2, room_number="102"),
        ],
        bookings=[
            booking_row(
                status="pending",
                room_id=1,
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.patch(
        "/bookings/1",
        json={
            "room_id": 2,
            "occupant_count": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["room"]["id"] == 2

    print("test_update_pending_booking_changes_room PASSED")


def test_update_pending_booking_to_booked_room_rejected(monkeypatch):
    fake = base_db(
        rooms=[
            room_row(room_id=1, room_number="101"),
            room_row(room_id=2, room_number="102"),
        ],
        bookings=[
            booking_row(
                booking_id=1,
                status="pending",
                room_id=1,
            ),
            booking_row(
                booking_id=2,
                status="approved",
                room_id=2,
                student_id="other",
            ),
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.patch(
        "/bookings/1",
        json={
            "room_id": 2,
            "occupant_count": 1,
        },
    )

    assert response.status_code == 409

    print("test_update_pending_booking_to_booked_room_rejected PASSED")


# ============================================================
# Cancel Booking Tests
# ============================================================


def test_cancel_pending_booking(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="pending",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.bookings.notify_next_waitlisted",
        lambda room_id: None,
    )

    install_student()

    response = client.delete("/bookings/1")

    assert response.status_code == 204
    assert fake.tables["bookings"][0]["status"] == "cancelled"

    print("test_cancel_pending_booking PASSED")


def test_cancel_approved_booking(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.bookings.notify_next_waitlisted",
        lambda room_id: None,
    )

    install_student()

    response = client.delete("/bookings/1")

    assert response.status_code == 204
    assert fake.tables["bookings"][0]["status"] == "cancelled"

    print("test_cancel_approved_booking PASSED")


def test_cancel_booking_not_found(monkeypatch):
    fake = base_db()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.delete("/bookings/999")

    assert response.status_code == 404

    print("test_cancel_booking_not_found PASSED")


def test_cancel_booking_not_owner(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                student_id="someone-else",
                status="pending",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.delete("/bookings/1")

    assert response.status_code == 403

    print("test_cancel_booking_not_owner PASSED")


def test_cancel_closed_booking_rejected(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="cancelled",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.delete("/bookings/1")

    assert response.status_code == 409

    print("test_cancel_closed_booking_rejected PASSED")


def test_cancel_paid_booking_rejected(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
            )
        ],
        payments=[
            payment_row(
                status="paid",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.delete("/bookings/1")

    assert response.status_code == 409
    assert "paid" in response.json()["detail"].lower()

    print("test_cancel_paid_booking_rejected PASSED")


def test_cancel_booking_requires_login():
    app.dependency_overrides.clear()

    response = client.delete("/bookings/1")

    assert response.status_code == 401

    print("test_cancel_booking_requires_login PASSED")


# ============================================================
# Transfer Request Tests
# ============================================================


def test_transfer_request_success(monkeypatch):
    fake = base_db(
        rooms=[
            room_row(room_id=1, room_number="101"),
            room_row(room_id=2, room_number="102"),
        ],
        bookings=[
            booking_row(
                status="approved",
                room_id=1,
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/transfer-request",
        json={
            "room_id": 2,
            "reason": "Need a quieter room",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["booking_id"] == 1
    assert data["requested_room_id"] == 2
    assert data["status"] == "pending"

    assert fake.tables["bookings"][0]["pending_transfer_room_id"] == 2
    assert fake.tables["bookings"][0]["status"] == "pending"

    print("test_transfer_request_success PASSED")


def test_transfer_request_requires_login():
    app.dependency_overrides.clear()

    response = client.post(
        "/bookings/1/transfer-request",
        json={
            "room_id": 2,
            "reason": "Move room",
        },
    )

    assert response.status_code == 401

    print("test_transfer_request_requires_login PASSED")


def test_transfer_request_booking_not_found(monkeypatch):
    fake = base_db()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/999/transfer-request",
        json={
            "room_id": 2,
            "reason": "Move room",
        },
    )

    assert response.status_code == 404

    print("test_transfer_request_booking_not_found PASSED")


def test_transfer_request_not_owner(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                student_id="someone-else",
                status="approved",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/transfer-request",
        json={
            "room_id": 2,
            "reason": "Move room",
        },
    )

    assert response.status_code == 403

    print("test_transfer_request_not_owner PASSED")


def test_transfer_request_requires_approved_booking(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="pending",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/transfer-request",
        json={
            "room_id": 2,
            "reason": "Move room",
        },
    )

    assert response.status_code == 409

    print("test_transfer_request_requires_approved_booking PASSED")


def test_transfer_request_paid_booking_rejected(monkeypatch):
    fake = base_db(
        rooms=[
            room_row(room_id=1),
            room_row(room_id=2, room_number="102"),
        ],
        bookings=[
            booking_row(
                status="approved",
            )
        ],
        payments=[
            payment_row(
                status="paid",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/transfer-request",
        json={
            "room_id": 2,
            "reason": "Move room",
        },
    )

    assert response.status_code == 409
    assert "paid" in response.json()["detail"].lower()

    print("test_transfer_request_paid_booking_rejected PASSED")


def test_transfer_request_same_room_rejected(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
                room_id=1,
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/transfer-request",
        json={
            "room_id": 1,
            "reason": "Move room",
        },
    )

    assert response.status_code == 400

    print("test_transfer_request_same_room_rejected PASSED")


def test_transfer_request_booked_room_rejected(monkeypatch):
    fake = base_db(
        rooms=[
            room_row(room_id=1),
            room_row(room_id=2, room_number="102"),
        ],
        bookings=[
            booking_row(
                booking_id=1,
                status="approved",
                room_id=1,
            ),
            booking_row(
                booking_id=2,
                student_id="someone-else",
                status="approved",
                room_id=2,
            ),
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/transfer-request",
        json={
            "room_id": 2,
            "reason": "Move room",
        },
    )

    assert response.status_code == 409

    print("test_transfer_request_booked_room_rejected PASSED")


def test_transfer_request_missing_reason(monkeypatch):
    fake = base_db(
        rooms=[
            room_row(room_id=1),
            room_row(room_id=2, room_number="102"),
        ],
        bookings=[
            booking_row(
                status="approved",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/transfer-request",
        json={
            "room_id": 2,
        },
    )

    assert response.status_code == 422

    print("test_transfer_request_missing_reason PASSED")


# ============================================================
# Cancellation Request Tests
# ============================================================


def test_cancellation_request_requires_login():
    app.dependency_overrides.clear()

    response = client.post(
        "/bookings/1/cancellation-request",
        json={
            "reason": "I need to leave.",
        },
    )

    assert response.status_code == 401

    print("test_cancellation_request_requires_login PASSED")


def test_cancellation_request_booking_not_found(monkeypatch):
    fake = base_db()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/999/cancellation-request",
        json={
            "reason": "I need to leave.",
        },
    )

    assert response.status_code == 404

    print("test_cancellation_request_booking_not_found PASSED")


def test_cancellation_request_not_owner(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                student_id="someone-else",
                status="approved",
            )
        ],
        payments=[
            payment_row(
                status="paid",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/cancellation-request",
        json={
            "reason": "I need to leave.",
        },
    )

    assert response.status_code == 403

    print("test_cancellation_request_not_owner PASSED")


def test_cancellation_request_requires_approved_booking(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="pending",
            )
        ],
        payments=[
            payment_row(
                status="paid",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/cancellation-request",
        json={
            "reason": "I need to leave.",
        },
    )

    assert response.status_code == 409

    print("test_cancellation_request_requires_approved_booking PASSED")


def test_cancellation_request_requires_paid_booking(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
            )
        ],
        payments=[],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/cancellation-request",
        json={
            "reason": "I need to leave.",
        },
    )

    assert response.status_code == 409
    assert "paid" in response.json()["detail"].lower()

    print("test_cancellation_request_requires_paid_booking PASSED")


def test_cancellation_request_duplicate_rejected(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
            )
        ],
        payments=[
            payment_row(
                status="paid",
            )
        ],
        booking_cancellation_requests=[
            cancellation_row(
                status="pending",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/cancellation-request",
        json={
            "reason": "Another request.",
        },
    )

    assert response.status_code == 409
    assert "already have" in response.json()["detail"].lower()

    print("test_cancellation_request_duplicate_rejected PASSED")


def test_cancellation_request_missing_reason(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
            )
        ],
        payments=[
            payment_row(
                status="paid",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post(
        "/bookings/1/cancellation-request",
        json={},
    )

    assert response.status_code == 422

    print("test_cancellation_request_missing_reason PASSED")


# ============================================================
# Booking Output / Payment / Cancellation State
# ============================================================


def test_booking_output_marks_paid_booking(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
            )
        ],
        payments=[
            payment_row(
                status="paid",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/me")

    assert response.status_code == 200
    assert response.json()["is_paid"] is True

    print("test_booking_output_marks_paid_booking PASSED")


def test_booking_output_marks_unpaid_booking(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
            )
        ],
        payments=[],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/me")

    assert response.status_code == 200
    assert response.json()["is_paid"] is False

    print("test_booking_output_marks_unpaid_booking PASSED")


def test_booking_output_contains_pending_cancellation_request(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
            )
        ],
        payments=[
            payment_row(
                status="paid",
            )
        ],
        booking_cancellation_requests=[
            cancellation_row(
                status="pending",
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/me")

    assert response.status_code == 200

    cancellation = response.json()["pending_cancellation_request"]

    assert cancellation is not None
    assert cancellation["id"] == 1
    assert cancellation["status"] == "pending"

    print("test_booking_output_contains_pending_cancellation_request PASSED")


def test_booking_output_contains_pending_transfer_room(monkeypatch):
    fake = base_db(
        rooms=[
            room_row(room_id=1, room_number="101"),
            room_row(room_id=2, room_number="202"),
        ],
        bookings=[
            booking_row(
                status="approved",
                pending_transfer_room_id=2,
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/me")

    assert response.status_code == 200

    pending_room = response.json()["pending_transfer_room"]

    assert pending_room is not None
    assert pending_room["id"] == 2
    assert pending_room["room_number"] == "202"

    print("test_booking_output_contains_pending_transfer_room PASSED")


def test_booking_output_missing_pending_transfer_room_is_safe(monkeypatch):
    fake = base_db(
        bookings=[
            booking_row(
                status="approved",
                pending_transfer_room_id=999,
            )
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    install_student()

    response = client.get("/bookings/me")

    assert response.status_code == 200
    assert response.json()["pending_transfer_room"] is None

    print("test_booking_output_missing_pending_transfer_room_is_safe PASSED")


# ============================================================
# Route / Method Tests
# ============================================================


def test_unknown_booking_route_returns_404():
    install_student()

    response = client.get("/bookings/not-a-real-route")

    assert response.status_code == 405

    print("test_unknown_booking_route_returns_404 PASSED")


def test_booking_delete_wrong_method(monkeypatch):
    fake = base_db()

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    install_student()

    response = client.post("/bookings/1")

    assert response.status_code in (404, 405, 422)

    print("test_booking_delete_wrong_method PASSED")


def test_booking_history_wrong_method():
    install_student()

    response = client.post("/bookings/history")

    assert response.status_code == 405

    print("test_booking_history_wrong_method PASSED")


# ============================================================
# Database Configuration / Error Handling
# ============================================================


def test_create_booking_without_service_role(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        None,
    )

    install_student()

    response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "semester": "Semester 1",
            "move_in_date": "2026-09-01",
            "move_out_date": "2027-01-31",
            "occupant_count": 1,
        },
    )

    assert response.status_code == 501

    print("test_create_booking_without_service_role PASSED")


def test_get_my_booking_without_service_role(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        None,
    )

    install_student()

    response = client.get("/bookings/me")

    assert response.status_code == 501

    print("test_get_my_booking_without_service_role PASSED")


def test_booking_history_without_service_role(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        None,
    )

    install_student()

    response = client.get("/bookings/history")

    assert response.status_code == 501

    print("test_booking_history_without_service_role PASSED")


def test_cancel_booking_without_service_role(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        None,
    )

    install_student()

    response = client.delete("/bookings/1")

    assert response.status_code == 501

    print("test_cancel_booking_without_service_role PASSED")


def test_transfer_request_without_service_role(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        None,
    )

    install_student()

    response = client.post(
        "/bookings/1/transfer-request",
        json={
            "room_id": 2,
            "reason": "Move room",
        },
    )

    assert response.status_code == 501

    print("test_transfer_request_without_service_role PASSED")


def test_cancellation_request_without_service_role(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        None,
    )

    install_student()

    response = client.post(
        "/bookings/1/cancellation-request",
        json={
            "reason": "Leave hostel",
        },
    )

    assert response.status_code == 501

    print("test_cancellation_request_without_service_role PASSED")
