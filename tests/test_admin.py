import pytest

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user

client = TestClient(app)

# ============================================================
# Fake Supabase Response
# ============================================================


class FakeResponse:
    def __init__(self, data):
        self.data = data


# ============================================================
# Fake Query
# ============================================================


class FakeQuery:

    def __init__(self, table_data):
        self.data = table_data

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

    def insert(self, data):

        new_id = len(self.data) + 1

        row = {"id": new_id, **data}

        self.data.append(row)

        return self

    def update(self, data):

        for row in self.data:
            row.update(data)

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
                    "gender_policy": "Female only",
                    "fee_monthly": 100,
                    "photo_url": None,
                    "is_active": True,
                    "hostel_blocks": {"name": "Block A"},
                }
            ],
            "hostel_blocks": [{"id": 1, "name": "Block A"}],
            "bookings": [
                {
                    "id": 1,
                    "room_id": 1,
                    "status": "pending",
                    "semester": "Semester 1",
                    "requested_at": datetime.now(timezone.utc),
                    "move_in_date": "2025-09-01",
                    "move_out_date": "2026-01-01",
                    "occupant_count": 1,
                    "student": {"full_name": "John Tan", "student_id": "TP123456"},
                    "rooms": {
                        "room_number": "101",
                        "fee_monthly": 100,
                        "hostel_blocks": {"name": "Block A"},
                    },
                }
            ],
            "room_transfer_requests": [
                {
                    "id": 1,
                    "booking_id": 1,
                    "requested_room_id": 1,
                    "reason": "Near classroom",
                    "status": "pending",
                    "requested_at": datetime.now(timezone.utc),
                    "student": {"full_name": "John Tan"},
                    "booking": {
                        "id": 1,
                        "room_id": 1,
                        "semester": "Semester 1",
                        "status": "approved",
                        "rooms": {"room_number": "101", "hostel_blocks": {"name": "Block A"}},
                    },
                    "requested_room": {"room_number": "102", "hostel_blocks": {"name": "Block A"}},
                }
            ],
            "maintenance_requests": [
                {
                    "id": 1,
                    "title": "Broken Fan",
                    "category": "Electrical",
                    "priority": "High",
                    "status": "pending",
                    "assigned_staff": None,
                    "remarks": None,
                    "photo_url": None,
                    "room_id": 1,
                    "created_at": datetime.now(timezone.utc),
                    "profiles": {"full_name": "John Tan", "student_id": "TP123456"},
                }
            ],
            "room_waitlist": [
                {
                    "id": 1,
                    "room_id": 1,
                    "status": "waiting",
                    "occupant_count": 1,
                    "move_in_date": "2025-09-01",
                    "move_out_date": "2026-01-01",
                    "joined_at": datetime.now(timezone.utc),
                    "student": {"full_name": "John Tan", "student_id": "TP123456"},
                    "rooms": {"room_number": "101", "hostel_blocks": {"name": "Block A"}},
                }
            ],
            "visitor_requests": [
                {
                    "id": 1,
                    "visitor_name": "Alice",
                    "visitor_email": "alice@test.com",
                    "visitor_relationship": "Friend",
                    "visitor_phone": "0123456789",
                    "visit_date": "2025-09-15",
                    "visit_time": "14:00",
                    "status": "pending",
                    "requested_at": datetime.now(timezone.utc),
                    "rejection_reason": None,
                    "decided_at": None,
                    "profiles": {
                        "full_name": "John Tan",
                        "student_id": "TP123456",
                        "email": "john@test.com",
                    },
                }
            ],
        }

    def table(self, name):

        return FakeQuery(self.tables.get(name, []))


# ============================================================
# Fake Users
# ============================================================


def override_admin():

    return CurrentUser(
        id="admin001",
        email="admin@test.com",
        full_name="Admin User",
        student_id=None,
        gender=None,
        role="admin",
    )


def override_student():

    return CurrentUser(
        id="student001",
        email="student@test.com",
        full_name="Student User",
        student_id="TP123456",
        gender="Male",
        role="student",
    )


# ============================================================
# Dashboard Tests
# ============================================================


def test_admin_dashboard_statistics(monkeypatch):
    """
    Admin views dashboard statistics.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/stats")

    assert response.status_code == 200

    data = response.json()

    assert data["total_rooms"] == 1
    assert data["occupied_rooms"] == 1
    assert data["available_rooms"] == 0
    assert data["pending_bookings"] == 1
    assert data["pending_maintenance"] == 1

    print("test_admin_dashboard_statistics PASSED")


# ============================================================
# Booking Tests
# ============================================================


def test_admin_view_all_bookings(monkeypatch):
    """
    Admin views all bookings.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/bookings")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["status"] == "pending"
    assert data[0]["student_name"] == "John Tan"

    print("test_admin_view_all_bookings PASSED")


def test_admin_view_pending_bookings(monkeypatch):
    """
    Admin views pending bookings.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/bookings/pending")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["status"] == "pending"

    print("test_admin_view_pending_bookings PASSED")


def test_admin_approve_booking(monkeypatch):
    """
    Admin approves booking.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/bookings/1/approve")

    assert response.status_code == 204

    print("test_admin_approve_booking PASSED")


def test_admin_reject_booking(monkeypatch):
    """
    Admin rejects booking.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/bookings/1/reject")

    assert response.status_code in [204, 409]

    print("test_admin_reject_booking PASSED")


def test_admin_booking_not_found(monkeypatch):
    """
    Booking ID does not exist.
    """

    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/bookings/99/approve")

    assert response.status_code == 404

    print("test_admin_booking_not_found PASSED")


def test_admin_booking_already_decided(monkeypatch):
    """
    Booking already approved.
    """

    fake = FakeSupabase()

    fake.tables["bookings"][0]["status"] = "approved"

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/bookings/1/approve")

    assert response.status_code == 409

    print("test_admin_booking_already_decided PASSED")


# ============================================================
# Authorization Tests
# ============================================================


def test_student_cannot_access_admin_dashboard():
    """
    Student cannot access dashboard.
    """

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/stats")

    assert response.status_code == 403

    print("test_student_cannot_access_admin_dashboard PASSED")


def test_student_cannot_view_bookings():
    """
    Student cannot access booking management.
    """

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/bookings")

    assert response.status_code == 403

    print("test_student_cannot_view_bookings PASSED")


# ============================================================
# Transfer Request Tests
# ============================================================


def test_admin_view_transfer_requests(monkeypatch):
    """
    Admin views all transfer requests.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/transfer-requests")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["status"] == "pending"
    assert data[0]["student_name"] == "John Tan"

    print("test_admin_view_transfer_requests PASSED")


def test_admin_approve_transfer_request(monkeypatch):
    """
    Admin approves a transfer request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/transfer-requests/1/approve")

    assert response.status_code == 204

    print("test_admin_approve_transfer_request PASSED")


def test_admin_reject_transfer_request(monkeypatch):
    """
    Admin rejects a transfer request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/transfer-requests/1/reject")

    assert response.status_code == 204

    print("test_admin_reject_transfer_request PASSED")


def test_admin_transfer_request_not_found(monkeypatch):
    """
    Transfer request ID does not exist.
    """

    fake = FakeSupabase()

    fake.tables["room_transfer_requests"] = []

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/transfer-requests/99/approve")

    assert response.status_code == 404

    print("test_admin_transfer_request_not_found PASSED")


def test_admin_transfer_request_already_decided(monkeypatch):
    """
    Transfer request already approved.
    """

    fake = FakeSupabase()

    fake.tables["room_transfer_requests"][0]["status"] = "approved"

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/transfer-requests/1/approve")

    assert response.status_code == 409

    print("test_admin_transfer_request_already_decided PASSED")


def test_admin_filter_pending_transfer_requests(monkeypatch):
    """
    Admin filters pending transfer requests.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/transfer-requests?status=pending")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["status"] == "pending"

    print("test_admin_filter_pending_transfer_requests PASSED")


def test_student_cannot_access_transfer_requests():
    """
    Student cannot access transfer request management.
    """

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/transfer-requests")

    assert response.status_code == 403

    print("test_student_cannot_access_transfer_requests PASSED")


# ============================================================
# Maintenance Tests
# ============================================================


def test_admin_view_maintenance(monkeypatch):
    """
    Admin views all maintenance requests.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/maintenance")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["title"] == "Broken Fan"
    assert data[0]["status"] == "pending"

    print("test_admin_view_maintenance PASSED")


def test_admin_view_pending_maintenance(monkeypatch):
    """
    Admin views pending maintenance requests.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/maintenance/pending")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["status"] == "pending"

    print("test_admin_view_pending_maintenance PASSED")


def test_admin_complete_maintenance(monkeypatch):
    """
    Admin completes a maintenance request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/maintenance/1/complete")

    assert response.status_code == 204

    print("test_admin_complete_maintenance PASSED")


def test_admin_complete_maintenance_not_found(monkeypatch):
    """
    Maintenance request does not exist.
    """

    fake = FakeSupabase()

    fake.tables["maintenance_requests"] = []

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/maintenance/99/complete")

    assert response.status_code == 404

    print("test_admin_complete_maintenance_not_found PASSED")


def test_admin_update_maintenance_status(monkeypatch):
    """
    Admin updates maintenance status.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {"status": "completed"}

    response = client.patch(
        "/admin/maintenance/1",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "completed"

    print("test_admin_update_maintenance_status PASSED")


def test_admin_assign_maintenance_staff(monkeypatch):
    """
    Admin assigns maintenance staff.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {"assigned_staff": "Alex Tan"}

    response = client.patch(
        "/admin/maintenance/1",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["assigned_staff"] == "Alex Tan"

    print("test_admin_assign_maintenance_staff PASSED")


def test_admin_update_maintenance_priority(monkeypatch):
    """
    Admin changes maintenance priority.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {"priority": "Low"}

    response = client.patch(
        "/admin/maintenance/1",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["priority"] == "Low"

    print("test_admin_update_maintenance_priority PASSED")


def test_admin_update_maintenance_remarks(monkeypatch):
    """
    Admin adds remarks to maintenance request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {"remarks": "Repair completed."}

    response = client.patch(
        "/admin/maintenance/1",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["remarks"] == "Repair completed."

    print("test_admin_update_maintenance_remarks PASSED")


def test_admin_update_maintenance_not_found(monkeypatch):
    """
    Maintenance request ID does not exist.
    """

    fake = FakeSupabase()

    fake.tables["maintenance_requests"] = []

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {"status": "completed"}

    response = client.patch(
        "/admin/maintenance/99",
        json=payload,
    )

    assert response.status_code == 404

    print("test_admin_update_maintenance_not_found PASSED")


def test_student_cannot_access_maintenance():
    """
    Student cannot access maintenance management.
    """

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/maintenance")

    assert response.status_code == 403

    print("test_student_cannot_access_maintenance PASSED")


# ============================================================
# Block Management Tests
# ============================================================


def test_admin_list_blocks(monkeypatch):
    """
    Admin views all hostel blocks.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/blocks")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Block A"

    print("test_admin_list_blocks PASSED")


# ============================================================
# Room Management Tests
# ============================================================


def test_admin_list_rooms(monkeypatch):
    """
    Admin views all rooms.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/rooms")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["room_number"] == "101"

    print("test_admin_list_rooms PASSED")


def test_admin_create_room(monkeypatch):
    """
    Admin creates a new room.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {
        "block_id": 1,
        "level": 2,
        "room_number": "101",
        "room_type": "Single Room",
        "capacity": 1,
        "gender_policy": "Male only",
        "fee_monthly": 150,
        "photo_url": None,
        "is_active": True,
    }

    response = client.post(
        "/admin/rooms",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["room_number"] == "101"

    assert fake.tables["rooms"][-1]["room_number"] == "101"

    print("test_admin_create_room PASSED")


def test_admin_update_room(monkeypatch):
    """
    Admin updates room information.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {"fee_monthly": 200}

    response = client.patch(
        "/admin/rooms/1",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["fee_monthly"] == 200

    print("test_admin_update_room PASSED")


def test_admin_update_room_gender(monkeypatch):
    """
    Admin changes room gender policy.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {"gender_policy": "Male only"}

    response = client.patch(
        "/admin/rooms/1",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["gender_policy"] == "Male only"

    print("test_admin_update_room_gender PASSED")


def test_admin_update_room_inactive(monkeypatch):
    """
    Admin deactivates room.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {"is_active": False}

    response = client.patch(
        "/admin/rooms/1",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["is_active"] is False

    print("test_admin_update_room_inactive PASSED")


def test_admin_update_room_not_found(monkeypatch):
    """
    Room ID does not exist.
    """

    fake = FakeSupabase()

    fake.tables["rooms"] = []

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {"fee_monthly": 300}

    response = client.patch(
        "/admin/rooms/99",
        json=payload,
    )

    assert response.status_code == 404

    print("test_admin_update_room_not_found PASSED")


def test_admin_update_room_empty_payload(monkeypatch):
    """
    Empty update request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.patch("/admin/rooms/1", json={})

    assert response.status_code == 400

    print("test_admin_update_room_empty_payload PASSED")


def test_student_cannot_access_rooms():
    """
    Student cannot access room management.
    """

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/rooms")

    assert response.status_code == 403

    print("test_student_cannot_access_rooms PASSED")


def test_student_cannot_access_blocks():
    """
    Student cannot access hostel blocks.
    """

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/blocks")

    assert response.status_code == 403

    print("test_student_cannot_access_blocks PASSED")


# ============================================================
# Waitlist Tests
# ============================================================


def test_admin_view_waitlist(monkeypatch):
    """
    Admin views room waitlist.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/waitlist")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["student_name"] == "John Tan"
    assert data[0]["status"] == "waiting"

    print("test_admin_view_waitlist PASSED")


def test_admin_filter_waitlist(monkeypatch):
    """
    Admin filters waitlist by room.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/waitlist?room_id=1")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["room_id"] == 1

    print("test_admin_filter_waitlist PASSED")


def test_student_cannot_access_waitlist():
    """
    Student cannot access waitlist.
    """

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/waitlist")

    assert response.status_code == 403

    print("test_student_cannot_access_waitlist PASSED")


# ============================================================
# Visitor Request Tests
# ============================================================


def test_admin_view_visitor_requests(monkeypatch):
    """
    Admin views visitor requests.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/visitors")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["visitor_name"] == "Alice"
    assert data[0]["status"] == "pending"

    print("test_admin_view_visitor_requests PASSED")


def test_admin_filter_visitor_status(monkeypatch):
    """
    Admin filters visitor requests by status.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/visitors?status=pending")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["status"] == "pending"

    print("test_admin_filter_visitor_status PASSED")


def test_admin_filter_visitor_date(monkeypatch):
    """
    Admin filters visitor requests by visit date.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/visitors?visit_date=2025-09-15")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    print("test_admin_filter_visitor_date PASSED")


def test_admin_search_visitor(monkeypatch):
    """
    Admin searches visitor by name.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/visitors?search=Alice")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["visitor_name"] == "Alice"

    print("test_admin_search_visitor PASSED")


def test_admin_approve_visitor(monkeypatch):
    """
    Admin approves visitor request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/visitors/1/approve")

    assert response.status_code == 204

    print("test_admin_approve_visitor PASSED")


def test_admin_reject_visitor(monkeypatch):
    """
    Admin rejects visitor request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    payload = {"reason": "Visitor quota exceeded"}

    response = client.post(
        "/admin/visitors/1/reject",
        json=payload,
    )

    assert response.status_code == 204

    print("test_admin_reject_visitor PASSED")


def test_admin_visitor_not_found(monkeypatch):
    """
    Visitor request does not exist.
    """

    fake = FakeSupabase()

    fake.tables["visitor_requests"] = []

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/visitors/99/approve")

    assert response.status_code == 404

    print("test_admin_visitor_not_found PASSED")


def test_admin_visitor_already_decided(monkeypatch):
    """
    Visitor request already approved.
    """

    fake = FakeSupabase()

    fake.tables["visitor_requests"][0]["status"] = "approved"

    monkeypatch.setattr(
        "agile_ci_demo.admin.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/visitors/1/approve")

    assert response.status_code == 409

    print("test_admin_visitor_already_decided PASSED")


def test_student_cannot_access_visitors():
    """
    Student cannot access visitor management.
    """

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/visitors")

    assert response.status_code == 403

    print("test_student_cannot_access_visitors PASSED")


@pytest.fixture(autouse=True)
def cleanup_dependencies():
    """
    Automatically clear dependency overrides after each test.
    """
    yield
    app.dependency_overrides.clear()
