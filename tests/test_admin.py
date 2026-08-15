import pytest
from fastapi.testclient import TestClient

from agile_ci_demo.admin import (
    _booked_room_ids,
    _room_admin_out,
    _rows,
    _waitlist_counts_by_room,
)
from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user

client = TestClient(app)


# ============================================================
# USERS
# ============================================================

ADMIN = CurrentUser(
    id="admin-001",
    email="admin@test.com",
    full_name="Admin User",
    student_id=None,
    gender=None,
    role="admin",
)

STUDENT = CurrentUser(
    id="student-001",
    email="student@test.com",
    full_name="John Tan",
    student_id="TP123456",
    gender="Male",
    role="student",
)


def override_admin():
    return ADMIN


def override_student():
    return STUDENT


# ============================================================
# CLEANUP
# ============================================================


@pytest.fixture(autouse=True)
def cleanup():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_admin

    yield

    app.dependency_overrides.clear()


# ============================================================
# FAKE RESPONSE
# ============================================================


class FakeResponse:
    def __init__(self, data):
        self.data = data


# ============================================================
# FAKE SUPABASE QUERY
# ============================================================


class FakeQuery:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self.data = list(db.tables.get(table_name, []))
        self._operation = None
        self._payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.data = [row for row in self.data if row.get(column) == value]
        return self

    def in_(self, column, values):
        self.data = [row for row in self.data if row.get(column) in values]
        return self

    def is_(self, column, value):
        if value == "null":
            self.data = [row for row in self.data if row.get(column) is None]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, number):
        self.data = self.data[:number]
        return self

    def insert(self, payload):
        self._operation = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._operation = "update"
        self._payload = payload
        return self

    def delete(self):
        self._operation = "delete"
        return self

    def execute(self):
        table = self.db.tables.setdefault(self.table_name, [])

        if self._operation == "insert":
            row = dict(self._payload)

            if "id" not in row:
                row["id"] = self.db.next_id(self.table_name)

            table.append(row)
            return FakeResponse([row])

        if self._operation == "update":
            for original in table:
                if original in self.data:
                    original.update(self._payload)

            return FakeResponse(self.data)

        if self._operation == "delete":
            for original in list(table):
                if original in self.data:
                    table.remove(original)

            return FakeResponse([])

        return FakeResponse(self.data)


# ============================================================
# FAKE SUPABASE
# ============================================================


class FakeDB:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, name):
        return FakeQuery(self, name)

    def next_id(self, table_name):
        rows = self.tables.get(table_name, [])

        if not rows:
            return 1

        return max(int(row.get("id", 0)) for row in rows) + 1


# ============================================================
# COMMON FIXTURES
# ============================================================


def profile():
    return {
        "full_name": "John Tan",
        "student_id": "TP123456",
    }


def room_row(room_id=1, **overrides):
    row = {
        "id": room_id,
        "block_id": 1,
        "level": 1,
        "room_number": "101",
        "room_type": "Single Room",
        "capacity": 1,
        "gender_policy": "Mixed",
        "fee_monthly": 500.0,
        "photo_url": None,
        "is_active": True,
        "hostel_blocks": {
            "name": "Block A",
        },
    }

    row.update(overrides)
    return row


def booking_row(
    booking_id=1,
    status="pending",
    room_id=1,
    **overrides,
):
    row = {
        "id": booking_id,
        "student_id": "student-001",
        "room_id": room_id,
        "status": status,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-31",
        "occupant_count": 1,
        "extra_occupant_name": None,
        "extra_occupant_email": None,
        "extra_occupant_student_id": None,
        "extra_occupant_gender": None,
        "requested_at": "2026-08-15T10:00:00+00:00",
        "decided_at": None,
        "checked_in_at": None,
        "checked_out_at": None,
        "pending_transfer_room_id": None,
        "student": profile(),
        "rooms": {
            "room_number": "101",
            "fee_monthly": 500.0,
            "hostel_blocks": {
                "name": "Block A",
            },
        },
    }

    if room_id != 1:
        row["rooms"] = {
            "room_number": "201",
            "fee_monthly": 500.0,
            "hostel_blocks": {
                "name": "Block B",
            },
        }

    row.update(overrides)
    return row


def payment_row(payment_id=1, status="paid"):
    return {
        "id": payment_id,
        "booking_id": 1,
        "student_id": "student-001",
        "amount": 500.0,
        "method": "Card",
        "status": status,
        "receipt_number": "RCPT-20260815-AAAA",
        "paid_at": "2026-08-15T10:00:00+00:00",
        "profiles": profile(),
        "bookings": {
            "room_id": 1,
        },
    }


def maintenance_row():
    return {
        "id": 1,
        "student_id": "student-001",
        "room_id": 1,
        "title": "Broken fan",
        "category": "Electrical",
        "priority": "High",
        "status": "pending",
        "photo_url": None,
        "assigned_staff": None,
        "remarks": None,
        "created_at": "2026-08-15T10:00:00+00:00",
        "completed_at": None,
        "resolved_at": None,
        "profiles": profile(),
        "rooms": {
            "room_number": "101",
            "hostel_blocks": {
                "name": "Block A",
            },
        },
    }


def waitlist_row():
    return {
        "id": 1,
        "room_id": 1,
        "student_id": "student-001",
        "status": "waiting",
        "queue_position": 1,
        "occupant_count": 1,
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-31",
        "joined_at": "2026-08-15T10:00:00+00:00",
        "notified_at": None,
        "student": profile(),
        "rooms": {
            "room_number": "101",
            "hostel_blocks": {
                "name": "Block A",
            },
        },
    }


def transfer_row(status="pending"):
    return {
        "id": 1,
        "booking_id": 1,
        "student_id": "student-001",
        "requested_room_id": 2,
        "reason": "Need a quieter room",
        "status": status,
        "requested_at": "2026-08-15T10:00:00+00:00",
        "student": {
            "full_name": "John Tan",
        },
        "booking": {
            "id": 1,
            "room_id": 1,
            "semester": "Semester 1",
            "status": "approved",
            "rooms": {
                "room_number": "101",
                "hostel_blocks": {
                    "name": "Block A",
                },
            },
        },
        "requested_room": {
            "room_number": "201",
            "hostel_blocks": {
                "name": "Block B",
            },
        },
    }


def visitor_row(status="pending"):
    return {
        "id": 1,
        "student_id": "student-001",
        "visitor_name": "Alice",
        "visitor_email": "alice@test.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-10",
        "visit_time": "10:00:00",
        "status": status,
        "rejection_reason": None,
        "requested_at": "2026-08-15T10:00:00+00:00",
        "decided_at": None,
        "student": profile(),
    }


def document_row(status="pending"):
    return {
        "id": 1,
        "student_id": "student-001",
        "document_type": "Student Card",
        "file_name": "student-card.pdf",
        "status": status,
        "rejection_reason": None,
        "uploaded_at": "2026-08-15T10:00:00+00:00",
        "verified_at": None,
        "verified_by": None,
        "file_url": "student-001/student-card.pdf",
        "profiles": profile(),
    }


def cancellation_row(status="pending"):
    return {
        "id": 1,
        "booking_id": 1,
        "student_id": "student-001",
        "reason": "I need to cancel my hostel booking",
        "status": status,
        "rejection_reason": None,
        "requested_at": "2026-08-15T10:00:00+00:00",
        "decided_at": None,
        "profiles": profile(),
        "bookings": {
            "room_id": 1,
        },
    }


# ============================================================
# BASIC HELPERS
# ============================================================


def test_rows_none():
    assert _rows(None) == []


def test_rows_list():
    rows = [{"id": 1}, {"id": 2}]
    assert _rows(rows) == rows


def test_db_missing_service_role(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        None,
    )

    response = client.get("/admin/stats")

    assert response.status_code == 501


# ============================================================
# DASHBOARD
# ============================================================


def test_dashboard_stats(monkeypatch):
    fake = FakeDB(
        {
            "rooms": [
                room_row(1),
                room_row(
                    2,
                    room_number="201",
                    room_type="Master Room",
                ),
                room_row(
                    3,
                    room_number="301",
                    room_type="Master Room",
                ),
            ],
            "bookings": [
                booking_row(1, "pending", 1),
                booking_row(2, "approved", 2),
                booking_row(3, "rejected", 3),
            ],
            "maintenance_requests": [
                {
                    "id": 1,
                    "status": "pending",
                }
            ],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/stats")

    assert response.status_code == 200

    data = response.json()

    assert data["total_rooms"] == 3
    assert data["occupied_rooms"] == 2
    assert data["available_rooms"] == 1
    assert data["pending_bookings"] == 1
    assert data["pending_maintenance"] == 1
    assert data["occupancy_pct"] == 66.7


def test_dashboard_empty_database(monkeypatch):
    fake = FakeDB(
        {
            "rooms": [],
            "bookings": [],
            "maintenance_requests": [],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/stats")

    assert response.status_code == 200

    data = response.json()

    assert data["total_rooms"] == 0
    assert data["occupied_rooms"] == 0
    assert data["available_rooms"] == 0
    assert data["occupancy_pct"] == 0.0


# ============================================================
# BOOKINGS
# ============================================================


def test_list_bookings(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [booking_row()],
            "payments": [payment_row()],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/bookings")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["student_name"] == "John Tan"
    assert data[0]["room_label"] == "Block A · 101"
    assert data[0]["total_fee"] == 500.0
    assert data[0]["is_paid"] is True


def test_list_bookings_filter_status(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                booking_row(1, "pending"),
                booking_row(2, "approved"),
            ],
            "payments": [],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/bookings?status=approved")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["status"] == "approved"


def test_pending_bookings(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [booking_row()],
            "payments": [],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/bookings/pending")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_approve_booking_not_found(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/bookings/999/approve")

    assert response.status_code == 404


def test_approve_booking_already_decided(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [booking_row(status="approved")],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/bookings/1/approve")

    assert response.status_code == 409


# ============================================================
# ROOM MANAGEMENT
# ============================================================


def test_list_blocks(monkeypatch):
    fake = FakeDB(
        {
            "hostel_blocks": [
                {"id": 1, "name": "Block A"},
                {"id": 2, "name": "Block B"},
            ]
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/blocks")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_rooms_admin(monkeypatch):
    fake = FakeDB(
        {
            "rooms": [room_row()],
            "bookings": [booking_row(status="approved")],
            "room_waitlist": [waitlist_row()],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/rooms")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["is_booked"] is True
    assert data[0]["waitlist_count"] == 1
    assert data[0]["block_name"] == "Block A"


def test_room_admin_out():
    result = _room_admin_out(
        room_row(),
        {1},
        {1: 3},
    )

    assert result.id == 1
    assert result.block_name == "Block A"
    assert result.is_booked is True
    assert result.waitlist_count == 3
    assert result.is_active is True


def test_booked_room_ids(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                {
                    "room_id": 1,
                    "status": "pending",
                    "checked_out_at": None,
                },
                {
                    "room_id": 2,
                    "status": "approved",
                    "checked_out_at": None,
                },
            ]
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    assert _booked_room_ids() == {1, 2}


def test_waitlist_counts_by_room(monkeypatch):
    fake = FakeDB(
        {
            "room_waitlist": [
                {
                    "room_id": 1,
                    "status": "waiting",
                },
                {
                    "room_id": 1,
                    "status": "waiting",
                },
                {
                    "room_id": 2,
                    "status": "waiting",
                },
            ]
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    assert _waitlist_counts_by_room() == {
        1: 2,
        2: 1,
    }


# ============================================================
# WAITLIST
# ============================================================


def test_admin_view_waitlist(monkeypatch):
    fake = FakeDB({"room_waitlist": [waitlist_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/waitlist")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["status"] == "waiting"


def test_admin_filter_waitlist(monkeypatch):
    fake = FakeDB({"room_waitlist": [waitlist_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/waitlist?room_id=1")

    assert response.status_code == 200
    assert len(response.json()) == 1


# ============================================================
# TRANSFER REQUESTS
# ============================================================


def test_list_transfer_requests(monkeypatch):
    fake = FakeDB({"room_transfer_requests": [transfer_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/transfer-requests")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["status"] == "pending"


def test_filter_transfer_requests(monkeypatch):
    fake = FakeDB({"room_transfer_requests": [transfer_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/transfer-requests?status=pending")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_approve_transfer_request(monkeypatch):
    fake = FakeDB(
        {
            "room_transfer_requests": [transfer_row()],
            "bookings": [booking_row(status="approved")],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.notify_next_waitlisted",
        lambda *_args: None,
    )

    response = client.post("/admin/transfer-requests/1/approve")

    assert response.status_code == 204
    assert fake.tables["room_transfer_requests"][0]["status"] == "approved"


def test_reject_transfer_request(monkeypatch):
    fake = FakeDB(
        {
            "room_transfer_requests": [transfer_row()],
            "bookings": [booking_row(status="approved")],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/transfer-requests/1/reject")

    assert response.status_code == 204
    assert fake.tables["room_transfer_requests"][0]["status"] == "rejected"


def test_transfer_request_not_found(monkeypatch):
    fake = FakeDB(
        {
            "room_transfer_requests": [],
            "bookings": [],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/transfer-requests/999/approve")

    assert response.status_code == 404


# ============================================================
# MAINTENANCE
# ============================================================


def test_list_maintenance(monkeypatch):
    fake = FakeDB(
        {
            "maintenance_requests": [maintenance_row()],
            "rooms": [room_row()],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/maintenance")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["title"] == "Broken fan"


def test_pending_maintenance(monkeypatch):
    fake = FakeDB(
        {
            "maintenance_requests": [maintenance_row()],
            "rooms": [room_row()],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/maintenance/pending")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_update_maintenance(monkeypatch):
    fake = FakeDB(
        {
            "maintenance_requests": [maintenance_row()],
            "rooms": [room_row()],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.patch(
        "/admin/maintenance/1",
        json={
            "status": "in_progress",
            "priority": "High",
            "assigned_staff": "Staff A",
            "remarks": "Checking fan",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "in_progress"
    assert data["assigned_staff"] == "Staff A"


def test_complete_maintenance(monkeypatch):
    fake = FakeDB({"maintenance_requests": [maintenance_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/maintenance/1/complete")

    assert response.status_code == 204

    assert fake.tables["maintenance_requests"][0]["status"] == "completed"


def test_complete_maintenance_not_found(monkeypatch):
    fake = FakeDB({"maintenance_requests": []})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/maintenance/999/complete")

    assert response.status_code == 404


# ============================================================
# VISITORS
# ============================================================


def test_list_visitor_requests(monkeypatch):
    fake = FakeDB({"visitor_requests": [visitor_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/visitors")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["visitor_name"] == "Alice"
    assert data[0]["status"] == "pending"


def test_filter_visitor_requests(monkeypatch):
    fake = FakeDB({"visitor_requests": [visitor_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/visitors?status=pending")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_approve_visitor(monkeypatch):
    fake = FakeDB({"visitor_requests": [visitor_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/visitors/1/approve")

    assert response.status_code == 204

    assert fake.tables["visitor_requests"][0]["status"] == "approved"


def test_reject_visitor(monkeypatch):
    fake = FakeDB({"visitor_requests": [visitor_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post(
        "/admin/visitors/1/reject",
        json={"reason": "Visitor date is not available"},
    )

    assert response.status_code == 204

    row = fake.tables["visitor_requests"][0]

    assert row["status"] == "rejected"
    assert row["rejection_reason"] == "Visitor date is not available"


def test_approve_visitor_not_found(monkeypatch):
    fake = FakeDB({"visitor_requests": []})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/visitors/999/approve")

    assert response.status_code == 404


# ============================================================
# CHECK-IN / CHECK-OUT
# ============================================================


def test_check_in_success(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [booking_row(status="approved")],
            "payments": [payment_row()],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/bookings/1/check-in")

    assert response.status_code == 204

    assert fake.tables["bookings"][0]["checked_in_at"] is not None


def test_check_in_wrong_status(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [booking_row(status="pending")],
            "payments": [payment_row()],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/bookings/1/check-in")

    assert response.status_code == 409


def test_check_in_already_checked_in(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                booking_row(
                    status="approved",
                    checked_in_at=("2026-08-15T11:00:00+00:00"),
                )
            ],
            "payments": [payment_row()],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/bookings/1/check-in")

    assert response.status_code == 409


def test_check_out_requires_check_in(monkeypatch):
    fake = FakeDB({"bookings": [booking_row(status="approved")]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/bookings/1/check-out")

    assert response.status_code == 409


def test_check_out_success(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                booking_row(
                    status="approved",
                    checked_in_at=("2026-08-15T11:00:00+00:00"),
                )
            ]
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/bookings/1/check-out")

    assert response.status_code == 204

    assert fake.tables["bookings"][0]["checked_out_at"] is not None


def test_check_out_already_checked_out(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                booking_row(
                    status="approved",
                    checked_in_at=("2026-08-15T11:00:00+00:00"),
                    checked_out_at=("2026-08-16T11:00:00+00:00"),
                )
            ]
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/bookings/1/check-out")

    assert response.status_code == 409


# ============================================================
# DOCUMENTS
# ============================================================


def test_list_documents(monkeypatch):
    fake = FakeDB({"student_documents": [document_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/documents")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["file_name"] == "student-card.pdf"
    assert data[0]["student_name"] == "John Tan"


def test_verify_document(monkeypatch):
    fake = FakeDB({"student_documents": [document_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/documents/1/verify")

    assert response.status_code == 204

    row = fake.tables["student_documents"][0]

    assert row["status"] == "verified"
    assert row["verified_by"] == "admin-001"


def test_reject_document(monkeypatch):
    fake = FakeDB({"student_documents": [document_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post(
        "/admin/documents/1/reject",
        json={"reason": "Image is not clear"},
    )

    assert response.status_code == 204

    row = fake.tables["student_documents"][0]

    assert row["status"] == "rejected"
    assert row["rejection_reason"] == "Image is not clear"


def test_verify_document_not_found(monkeypatch):
    fake = FakeDB({"student_documents": []})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/documents/999/verify")

    assert response.status_code == 404


# ============================================================
# PAYMENTS
# ============================================================


# ============================================================
# REPORT HELPERS
# ============================================================


# ============================================================
# CSV REPORTS
# ============================================================


# ============================================================
# XLSX REPORTS
# ============================================================


def test_bookings_report_xlsx(monkeypatch):
    pytest.importorskip("openpyxl")

    fake = FakeDB({"bookings": [booking_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/reports/bookings.xlsx")

    assert response.status_code == 200
    assert response.content[:2] == b"PK"


# ============================================================
# PDF REPORTS
# ============================================================


def test_bookings_report_pdf(monkeypatch):
    pytest.importorskip("reportlab")

    fake = FakeDB({"bookings": [booking_row()]})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.get("/admin/reports/bookings.pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


# ============================================================
# CANCELLATION / REFUND
# ============================================================


def test_approve_cancellation_request_not_found(monkeypatch):
    fake = FakeDB({"booking_cancellation_requests": []})

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    response = client.post("/admin/cancellation-requests/999/approve")

    assert response.status_code == 404


# ============================================================
# AUTHORIZATION
# ============================================================


def test_student_cannot_access_admin_stats():
    app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/stats")

    assert response.status_code == 403


def test_student_cannot_access_admin_rooms():
    app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/rooms")

    assert response.status_code == 403


def test_student_cannot_access_admin_bookings():
    app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/bookings")

    assert response.status_code == 403


def test_student_cannot_access_admin_payments():
    app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/payments")

    assert response.status_code == 403


def test_student_cannot_access_admin_documents():
    app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/documents")

    assert response.status_code == 403


def test_student_cannot_access_admin_waitlist():
    app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/waitlist")

    assert response.status_code == 403
