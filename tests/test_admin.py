import pytest
from fastapi.testclient import TestClient

from agile_ci_demo.admin import (
    BOOKINGS_REPORT_HEADERS,
    PAYMENTS_REPORT_HEADERS,
    _bookings_report_rows,
    _payments_report_rows,
    _room_admin_out,
    _rows,
    _waitlist_counts_by_room,
    _booked_room_ids,
    _room_label_for_maintenance,
    _visitor_admin_out,
)
from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user, require_admin

client = TestClient(app)


ADMIN = CurrentUser(
    id="admin-001",
    email="admin@test.com",
    full_name="Admin User",
    student_id=None,
    gender=None,
    role="admin",
)


def override_admin():
    return ADMIN


@pytest.fixture(autouse=True)
def cleanup():
    app.dependency_overrides.clear()
    app.dependency_overrides[require_admin] = override_admin
    yield
    app.dependency_overrides.clear()


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self.data = list(db.tables.get(table_name, []))
        self._payload = None
        self._limit = None

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

    def limit(self, number):
        self._limit = number
        self.data = self.data[:number]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self._payload = payload
        return self

    def update(self, payload):
        self._payload = payload
        return self

    def execute(self):
        if self._payload is not None:
            if self.table_name not in self.db.tables:
                self.db.tables[self.table_name] = []

            if self._method_is_update():
                for row in self.db.tables[self.table_name]:
                    # Fake update after filters.  The query's filtered data
                    # contains references to the original row dictionaries.
                    if row in self.data:
                        row.update(self._payload)
                return FakeResponse(self.data)

            new_row = dict(self._payload)
            if "id" not in new_row:
                new_row["id"] = self.db.next_id(self.table_name)
            if self.table_name == "rooms":
                new_row.setdefault("is_active", True)
                new_row.setdefault("photo_url", None)
            self.db.tables[self.table_name].append(new_row)
            return FakeResponse([new_row])

        return FakeResponse(self.data)

    def _method_is_update(self):
        # insert() and update() both set _payload.  FakeTable calls insert
        # only for tests that expect an insert, while update is marked here.
        return getattr(self, "_is_update", False)


class FakeUpdateQuery(FakeQuery):
    def update(self, payload):
        self._payload = payload
        self._is_update = True
        return self


class FakeInsertQuery(FakeQuery):
    def insert(self, payload):
        self._payload = payload
        self._is_update = False
        return self


class FakeStorageBucket:
    def __init__(self, bucket, db):
        self.bucket = bucket
        self.db = db

    def upload(self, path, contents, options):
        self.db.uploads.append((self.bucket, path, contents, options))

    def get_public_url(self, path):
        return f"https://storage.test/{self.bucket}/{path}"

    def create_signed_url(self, path, expiry):
        self.db.signed_urls.append((self.bucket, path, expiry))
        return {"signedUrl": f"https://signed.test/{path}"}


class FakeStorage:
    def __init__(self, db):
        self.db = db

    def from_(self, bucket):
        return FakeStorageBucket(bucket, self.db)


class FakeDB:
    def __init__(self, tables=None):
        self.tables = tables or {}
        self.uploads = []
        self.signed_urls = []

    def table(self, name):
        query = FakeQuery(self, name)
        # Mark mutations so execute() persists them.
        original_update = query.update
        original_insert = query.insert

        def update(payload):
            original_update(payload)
            query._is_update = True
            return query

        def insert(payload):
            original_insert(payload)
            query._is_update = False
            return query

        query.update = update
        query.insert = insert
        return query

    def next_id(self, table_name):
        rows = self.tables.get(table_name, [])
        return max([int(r.get("id", 0)) for r in rows] + [0]) + 1

    @property
    def storage(self):
        return FakeStorage(self)


def profile():
    return {
        "full_name": "John Tan",
        "student_id": "TP123456",
        "email": "student@test.com",
    }


def room_row(room_id=1):
    return {
        "id": room_id,
        "block_id": 10,
        "hostel_blocks": {"name": "Block A"},
        "level": 1,
        "room_number": "101",
        "room_type": "Single Room",
        "capacity": 1,
        "gender_policy": "Male only",
        "fee_monthly": 500.0,
        "photo_url": None,
        "is_active": True,
    }


def booking_row(
    booking_id=1,
    status="pending",
    room_id=1,
    checked_in_at=None,
    checked_out_at=None,
):
    return {
        "id": booking_id,
        "student_id": "student-001",
        "room_id": room_id,
        "status": status,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-31",
        "requested_at": "2026-08-15T10:00:00+00:00",
        "occupant_count": 1,
        "extra_occupant_name": None,
        "extra_occupant_email": None,
        "extra_occupant_student_id": None,
        "extra_occupant_gender": None,
        "checked_in_at": checked_in_at,
        "checked_out_at": checked_out_at,
        "profiles": profile(),
        "rooms": {
            "room_number": "101",
            "fee_monthly": 500.0,
            "hostel_blocks": {"name": "Block A"},
        },
    }


def maintenance_row(request_id=1, status="pending"):
    return {
        "id": request_id,
        "title": "Broken fan",
        "category": "Electrical",
        "priority": "Normal",
        "status": status,
        "photo_url": None,
        "assigned_staff": None,
        "remarks": None,
        "room_id": 1,
        "created_at": "2026-08-15T10:00:00+00:00",
        "resolved_at": None,
        "profiles": profile(),
    }


def visitor_row(request_id=1, status="pending"):
    return {
        "id": request_id,
        "visitor_name": "Jane Tan",
        "visitor_email": "jane@test.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-08-20",
        "visit_time": "14:00:00",
        "status": status,
        "rejection_reason": None,
        "requested_at": "2026-08-15T10:00:00+00:00",
        "decided_at": None,
        "student_id": "student-001",
        "profiles": profile(),
    }


def document_row(document_id=1, status="pending"):
    return {
        "id": document_id,
        "document_type": "Student ID",
        "file_name": "student-card.pdf",
        "status": status,
        "rejection_reason": None,
        "uploaded_at": "2026-08-15T10:00:00+00:00",
        "verified_at": None,
        "verified_by": None,
        "file_url": "student-001/student-card.pdf",
        "profiles": profile(),
    }


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
        "bookings": {"room_id": 1},
    }


def transfer_row(request_id=1, status="pending"):
    return {
        "id": request_id,
        "booking_id": 1,
        "student_id": "student-001",
        "requested_room_id": 2,
        "reason": "Need a quieter room",
        "status": status,
        "requested_at": "2026-08-15T10:00:00+00:00",
        "student": {"full_name": "John Tan"},
        "booking": {
            "id": 1,
            "room_id": 1,
            "semester": "Semester 1",
            "status": "approved",
            "rooms": {
                "room_number": "101",
                "hostel_blocks": {"name": "Block A"},
            },
        },
        "requested_room": {
            "room_number": "201",
            "hostel_blocks": {"name": "Block B"},
        },
    }


def waitlist_row(entry_id=1):
    return {
        "id": entry_id,
        "room_id": 1,
        "student_id": "student-001",
        "status": "waiting",
        "occupant_count": 1,
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-31",
        "joined_at": "2026-08-15T10:00:00+00:00",
        "notified_at": None,
        "student": {"full_name": "John Tan", "student_id": "TP123456"},
        "rooms": {
            "room_number": "101",
            "hostel_blocks": {"name": "Block A"},
        },
    }


# ============================================================
# Basic helpers
# ============================================================


def test_rows_none():
    assert _rows(None) == []


def test_rows_list():
    rows = [{"id": 1}, {"id": 2}]
    assert _rows(rows) == rows


def test_db_missing_service_role(monkeypatch):
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", None)

    response = client.get("/admin/stats")

    assert response.status_code == 501


def test_admin_route_without_login():
    app.dependency_overrides.clear()

    response = client.get("/admin/stats")

    assert response.status_code == 401


# ============================================================
# Dashboard
# ============================================================


def test_dashboard_stats(monkeypatch):
    fake = FakeDB(
        {
            "rooms": [
                room_row(1),
                {**room_row(2), "room_type": "Master Room"},
                {**room_row(3), "room_type": "Master Room"},
            ],
            "bookings": [
                booking_row(1, "pending", 1),
                booking_row(2, "approved", 2),
                booking_row(3, "rejected", 3),
                booking_row(4, "cancelled", 3),
            ],
            "maintenance_requests": [{"id": 1, "status": "pending"}],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total_rooms"] == 3
    assert data["occupied_rooms"] == 2
    assert data["available_rooms"] == 1
    assert data["pending_bookings"] == 1
    assert data["pending_maintenance"] == 1
    assert data["occupancy_pct"] == 66.7
    assert data["bookings_by_status"]["pending"] == 1
    assert data["bookings_by_status"]["approved"] == 1
    assert data["bookings_by_status"]["rejected"] == 1
    assert data["bookings_by_status"]["cancelled"] == 1
    assert data["rooms_by_type"]["Single Room"] == 1
    assert data["rooms_by_type"]["Master Room"] == 2


def test_dashboard_empty_database(monkeypatch):
    fake = FakeDB(
        {
            "rooms": [],
            "bookings": [],
            "maintenance_requests": [],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total_rooms"] == 0
    assert data["occupied_rooms"] == 0
    assert data["available_rooms"] == 0
    assert data["occupancy_pct"] == 0.0


# ============================================================
# Bookings
# ============================================================


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
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/bookings?status=approved")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "approved"


def test_pending_bookings(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [booking_row()],
            "payments": [],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/bookings/pending")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "pending"


def test_list_bookings_unpaid(monkeypatch):
    fake = FakeDB({"bookings": [booking_row()], "payments": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/bookings")

    assert response.status_code == 200
    assert response.json()[0]["is_paid"] is False


def test_approve_booking(monkeypatch):
    fake = FakeDB({"bookings": [booking_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)
    monkeypatch.setattr("agile_ci_demo.admin.notify_next_waitlisted", lambda *_: None)

    response = client.post("/admin/bookings/1/approve")

    assert response.status_code == 204
    assert fake.tables["bookings"][0]["status"] == "approved"
    assert fake.tables["bookings"][0]["decided_by"] == "admin-001"


def test_reject_booking(monkeypatch):
    fake = FakeDB({"bookings": [booking_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)
    monkeypatch.setattr("agile_ci_demo.admin.notify_next_waitlisted", lambda *_: None)

    response = client.post("/admin/bookings/1/reject")

    assert response.status_code == 204
    assert fake.tables["bookings"][0]["status"] == "rejected"


def test_approve_booking_not_found(monkeypatch):
    fake = FakeDB({"bookings": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/bookings/999/approve")

    assert response.status_code == 404


def test_approve_booking_already_decided(monkeypatch):
    fake = FakeDB({"bookings": [booking_row(status="approved")]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/bookings/1/approve")

    assert response.status_code == 409


# ============================================================
# Transfer requests
# ============================================================


def test_list_transfer_requests(monkeypatch):
    fake = FakeDB({"room_transfer_requests": [transfer_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/transfer-requests")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["student_name"] == "John Tan"
    assert data[0]["requested_room_id"] == 2
    assert data[0]["requested_room_label"] == "Block B · Room 201"


def test_list_transfer_requests_filter(monkeypatch):
    fake = FakeDB(
        {
            "room_transfer_requests": [
                transfer_row(1, "pending"),
                transfer_row(2, "approved"),
            ]
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/transfer-requests?status=approved")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "approved"


def test_approve_transfer_request(monkeypatch):
    fake = FakeDB(
        {
            "room_transfer_requests": [transfer_row()],
            "bookings": [booking_row(status="approved", room_id=1)],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)
    monkeypatch.setattr("agile_ci_demo.admin.notify_next_waitlisted", lambda *_: None)

    response = client.post("/admin/transfer-requests/1/approve")

    assert response.status_code == 204
    assert fake.tables["room_transfer_requests"][0]["status"] == "approved"
    assert fake.tables["bookings"][0]["room_id"] == 2
    assert fake.tables["bookings"][0]["pending_transfer_room_id"] is None


def test_reject_transfer_request(monkeypatch):
    fake = FakeDB(
        {
            "room_transfer_requests": [transfer_row()],
            "bookings": [booking_row(status="approved", room_id=1)],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/transfer-requests/1/reject")

    assert response.status_code == 204
    assert fake.tables["room_transfer_requests"][0]["status"] == "rejected"
    assert fake.tables["bookings"][0]["room_id"] == 1
    assert fake.tables["bookings"][0]["pending_transfer_room_id"] is None


def test_approve_transfer_request_not_found(monkeypatch):
    fake = FakeDB({"room_transfer_requests": [], "bookings": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/transfer-requests/999/approve")

    assert response.status_code == 404


# ============================================================
# Maintenance
# ============================================================


def test_list_maintenance(monkeypatch):
    fake = FakeDB(
        {
            "maintenance_requests": [maintenance_row()],
            "rooms": [room_row()],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/maintenance")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Broken fan"
    assert data[0]["student_name"] == "John Tan"
    assert data[0]["room_label"] == "Block A · Room 101"


def test_pending_maintenance(monkeypatch):
    fake = FakeDB(
        {
            "maintenance_requests": [maintenance_row()],
            "rooms": [room_row()],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

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
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.patch(
        "/admin/maintenance/1",
        json={
            "status": "in_progress",
            "priority": "High",
            "assigned_staff": "Staff A",
            "remarks": "Checking the fan",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"
    assert data["priority"] == "High"
    assert data["assigned_staff"] == "Staff A"
    assert data["remarks"] == "Checking the fan"


def test_update_maintenance_no_fields(monkeypatch):
    fake = FakeDB({"maintenance_requests": [{"id": 1}]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.patch("/admin/maintenance/1", json={})

    assert response.status_code == 400


def test_update_maintenance_not_found(monkeypatch):
    fake = FakeDB({"maintenance_requests": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.patch(
        "/admin/maintenance/999",
        json={"remarks": "test"},
    )

    assert response.status_code == 404


def test_complete_maintenance(monkeypatch):
    fake = FakeDB({"maintenance_requests": [maintenance_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/maintenance/1/complete")

    assert response.status_code == 204
    assert fake.tables["maintenance_requests"][0]["status"] == "completed"
    assert fake.tables["maintenance_requests"][0]["resolved_at"] is not None


def test_complete_maintenance_not_found(monkeypatch):
    fake = FakeDB({"maintenance_requests": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/maintenance/999/complete")

    assert response.status_code == 404


# ============================================================
# Rooms
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
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

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
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/rooms")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["is_booked"] is True
    assert data[0]["waitlist_count"] == 1
    assert data[0]["block_name"] == "Block A"


def test_room_admin_out():
    result = _room_admin_out(room_row(), {1}, {1: 3})

    assert result.id == 1
    assert result.block_name == "Block A"
    assert result.is_booked is True
    assert result.waitlist_count == 3


def test_booked_room_ids(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                {"room_id": 1, "status": "pending", "checked_out_at": None},
                {"room_id": 2, "status": "approved", "checked_out_at": None},
            ]
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    assert _booked_room_ids() == {1, 2}


def test_waitlist_counts_by_room(monkeypatch):
    fake = FakeDB(
        {
            "room_waitlist": [
                {"room_id": 1, "status": "waiting"},
                {"room_id": 1, "status": "waiting"},
                {"room_id": 2, "status": "waiting"},
            ]
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    assert _waitlist_counts_by_room() == {1: 2, 2: 1}


def test_create_room_invalid_photo(monkeypatch):
    fake = FakeDB({"rooms": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post(
        "/admin/rooms",
        data={
            "block_id": "1",
            "level": "2",
            "room_number": "202",
            "room_type": "Single Room",
            "capacity": "1",
            "gender_policy": "Mixed",
            "fee_monthly": "550",
        },
        files={
            "photo": (
                "room.txt",
                b"not an image",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400


def test_create_room(monkeypatch):
    fake = FakeDB(
        {
            "rooms": [],
            "hostel_blocks": [{"id": 1, "name": "Block A"}],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post(
        "/admin/rooms",
        data={
            "block_id": "1",
            "level": "2",
            "room_number": "202",
            "room_type": "Single Room",
            "capacity": "1",
            "gender_policy": "Mixed",
            "fee_monthly": "550",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["room_number"] == "202"
    assert data["fee_monthly"] == 550.0


def test_update_room(monkeypatch):
    fake = FakeDB(
        {
            "rooms": [room_row()],
            "bookings": [],
            "room_waitlist": [],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.patch(
        "/admin/rooms/1",
        json={"fee_monthly": 650, "capacity": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["fee_monthly"] == 650.0
    assert data["capacity"] == 2


def test_update_room_no_fields(monkeypatch):
    fake = FakeDB({"rooms": [room_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.patch("/admin/rooms/1", json={})

    assert response.status_code == 400


def test_update_room_not_found(monkeypatch):
    fake = FakeDB({"rooms": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.patch(
        "/admin/rooms/999",
        json={"fee_monthly": 600},
    )

    assert response.status_code == 404


# ============================================================
# Waitlist
# ============================================================


def test_list_waitlist(monkeypatch):
    fake = FakeDB({"room_waitlist": [waitlist_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/waitlist")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["queue_position"] == 1
    assert data[0]["student_name"] == "John Tan"


def test_list_waitlist_filter_room(monkeypatch):
    fake = FakeDB(
        {
            "room_waitlist": [
                waitlist_row(1),
                {**waitlist_row(2), "room_id": 2},
            ]
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/waitlist?room_id=2")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["room_id"] == 2


# ============================================================
# Visitors
# ============================================================


def test_list_visitors(monkeypatch):
    fake = FakeDB({"visitor_requests": [visitor_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/visitors")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["visitor_name"] == "Jane Tan"
    assert data[0]["student_name"] == "John Tan"


def test_list_visitors_search(monkeypatch):
    fake = FakeDB({"visitor_requests": [visitor_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/visitors?search=jane")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_visitors_date_filter(monkeypatch):
    fake = FakeDB({"visitor_requests": [visitor_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/visitors?visit_date=2026-08-20")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_visitor_admin_out():
    result = _visitor_admin_out(visitor_row(), profile())

    assert result.visitor_name == "Jane Tan"
    assert result.student_name == "John Tan"
    assert result.student_id == "TP123456"


def test_approve_visitor(monkeypatch):
    fake = FakeDB({"visitor_requests": [visitor_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/visitors/1/approve")

    assert response.status_code == 204
    assert fake.tables["visitor_requests"][0]["status"] == "approved"
    assert fake.tables["visitor_requests"][0]["decided_by"] == "admin-001"


def test_reject_visitor(monkeypatch):
    fake = FakeDB({"visitor_requests": [visitor_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post(
        "/admin/visitors/1/reject",
        json={"reason": "Visitor date is not available"},
    )

    assert response.status_code == 204
    assert fake.tables["visitor_requests"][0]["status"] == "rejected"
    assert fake.tables["visitor_requests"][0]["rejection_reason"] == (
        "Visitor date is not available"
    )


def test_approve_visitor_not_found(monkeypatch):
    fake = FakeDB({"visitor_requests": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/visitors/999/approve")

    assert response.status_code == 404


def test_approve_visitor_already_decided(monkeypatch):
    fake = FakeDB({"visitor_requests": [visitor_row(status="approved")]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/visitors/1/approve")

    assert response.status_code == 409


# ============================================================
# Check-in / check-out
# ============================================================


def test_check_in_requires_payment(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                booking_row(
                    status="approved",
                    checked_in_at=None,
                    checked_out_at=None,
                )
            ],
            "payments": [],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/bookings/1/check-in")

    assert response.status_code == 409
    assert "payment" in response.json()["detail"].lower()


def test_check_in_success(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                booking_row(
                    status="approved",
                    checked_in_at=None,
                    checked_out_at=None,
                )
            ],
            "payments": [payment_row()],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

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
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/bookings/1/check-in")

    assert response.status_code == 409


def test_check_in_already_checked_in(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                booking_row(
                    status="approved",
                    checked_in_at="2026-08-15T11:00:00+00:00",
                )
            ],
            "payments": [payment_row()],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/bookings/1/check-in")

    assert response.status_code == 409


def test_check_out_requires_check_in(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                booking_row(
                    status="approved",
                    checked_in_at=None,
                    checked_out_at=None,
                )
            ]
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/bookings/1/check-out")

    assert response.status_code == 409


def test_check_out_success(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                booking_row(
                    status="approved",
                    checked_in_at="2026-08-15T11:00:00+00:00",
                    checked_out_at=None,
                )
            ]
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/bookings/1/check-out")

    assert response.status_code == 204
    assert fake.tables["bookings"][0]["checked_out_at"] is not None


def test_check_out_already_checked_out(monkeypatch):
    fake = FakeDB(
        {
            "bookings": [
                booking_row(
                    status="approved",
                    checked_in_at="2026-08-15T11:00:00+00:00",
                    checked_out_at="2026-08-16T11:00:00+00:00",
                )
            ]
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/bookings/1/check-out")

    assert response.status_code == 409


# ============================================================
# Documents
# ============================================================


def test_list_documents(monkeypatch):
    fake = FakeDB({"student_documents": [document_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/documents")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["file_name"] == "student-card.pdf"
    assert data[0]["student_name"] == "John Tan"
    assert data[0]["view_url"].startswith("https://signed.test/")


def test_verify_document(monkeypatch):
    fake = FakeDB({"student_documents": [document_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/documents/1/verify")

    assert response.status_code == 204
    assert fake.tables["student_documents"][0]["status"] == "verified"
    assert fake.tables["student_documents"][0]["verified_by"] == "admin-001"


def test_reject_document(monkeypatch):
    fake = FakeDB({"student_documents": [document_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post(
        "/admin/documents/1/reject",
        json={"reason": "Image is not clear"},
    )

    assert response.status_code == 204
    assert fake.tables["student_documents"][0]["status"] == "rejected"
    assert fake.tables["student_documents"][0]["rejection_reason"] == "Image is not clear"


def test_verify_document_not_found(monkeypatch):
    fake = FakeDB({"student_documents": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/documents/999/verify")

    assert response.status_code == 404


# ============================================================
# Payments
# ============================================================


def test_list_payments(monkeypatch):
    fake = FakeDB(
        {
            "payments": [payment_row()],
            "rooms": [room_row()],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/payments")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["receipt_number"] == "RCPT-20260815-AAAA"
    assert data[0]["amount"] == 500.0
    assert data[0]["student_name"] == "John Tan"


# ============================================================
# Reports
# ============================================================


def test_bookings_report_rows(monkeypatch):
    fake = FakeDB({"bookings": [booking_row()]})

    rows = _bookings_report_rows(fake)

    assert len(rows) == 1
    assert rows[0][0] == "1"
    assert rows[0][1] == "John Tan"
    assert rows[0][3] == "Block A · 101"
    assert rows[0][4] == "pending"


def test_payments_report_rows(monkeypatch):
    fake = FakeDB(
        {
            "payments": [
                payment_row(1, "paid"),
                {
                    **payment_row(2, "refunded"),
                    "amount": 200.0,
                    "receipt_number": "RCPT-REFUND",
                },
            ]
        }
    )

    rows, total = _payments_report_rows(fake)

    assert len(rows) == 2
    assert total == 500.0
    assert rows[0][0] == "RCPT-20260815-AAAA"
    assert rows[0][4] == "500.00"


def test_bookings_report_csv(monkeypatch):
    fake = FakeDB({"bookings": [booking_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/reports/bookings.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Booking ID" in response.text
    assert "John Tan" in response.text


def test_bookings_report_pdf(monkeypatch):
    fake = FakeDB({"bookings": [booking_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/reports/bookings.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_payments_report_csv(monkeypatch):
    fake = FakeDB({"payments": [payment_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/reports/payments.csv")

    assert response.status_code == 200
    assert "Receipt No." in response.text
    assert "500.00" in response.text
    assert "Total collected (RM)" in response.text


def test_payments_report_xlsx(monkeypatch):
    fake = FakeDB({"payments": [payment_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/reports/payments.xlsx")

    assert response.status_code == 200
    assert response.content[:2] == b"PK"


def test_payments_report_pdf(monkeypatch):
    fake = FakeDB({"payments": [payment_row()]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/reports/payments.pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


# ============================================================
# Cancellation / refund requests
# ============================================================


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
        "bookings": {"room_id": 1},
    }


def test_list_cancellation_requests(monkeypatch):
    fake = FakeDB(
        {
            "booking_cancellation_requests": [cancellation_row()],
            "payments": [payment_row()],
            "rooms": [room_row()],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.get("/admin/cancellation-requests")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["student_name"] == "John Tan"
    assert data[0]["amount_paid"] == 500.0
    assert data[0]["room_label"] == "Block A · Room 101"


def test_approve_cancellation_request(monkeypatch):
    fake = FakeDB(
        {
            "booking_cancellation_requests": [cancellation_row()],
            "bookings": [booking_row(status="approved")],
            "payments": [payment_row()],
            "room_transfer_requests": [],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)
    monkeypatch.setattr("agile_ci_demo.admin.notify_next_waitlisted", lambda *_: None)

    response = client.post("/admin/cancellation-requests/1/approve")

    assert response.status_code == 204
    assert fake.tables["booking_cancellation_requests"][0]["status"] == "approved"
    assert fake.tables["bookings"][0]["status"] == "cancelled"
    assert fake.tables["payments"][0]["status"] == "refunded"


def test_reject_cancellation_request(monkeypatch):
    fake = FakeDB(
        {
            "booking_cancellation_requests": [cancellation_row()],
        }
    )
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post(
        "/admin/cancellation-requests/1/reject",
        json={"reason": "Cancellation deadline has passed"},
    )

    assert response.status_code == 204
    assert fake.tables["booking_cancellation_requests"][0]["status"] == "rejected"
    assert fake.tables["booking_cancellation_requests"][0]["rejection_reason"] == (
        "Cancellation deadline has passed"
    )


def test_approve_cancellation_request_not_found(monkeypatch):
    fake = FakeDB({"booking_cancellation_requests": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/cancellation-requests/999/approve")

    assert response.status_code == 404


def test_approve_cancellation_request_already_decided(monkeypatch):
    fake = FakeDB({"booking_cancellation_requests": [cancellation_row(status="approved")]})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    response = client.post("/admin/cancellation-requests/1/approve")

    assert response.status_code == 409


# ============================================================
# Authorization checks for representative admin endpoints
# ============================================================


def test_student_cannot_access_admin_stats():
    app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="student-001",
        email="student@test.com",
        full_name="Student",
        role="student",
    )

    response = client.get("/admin/stats")

    assert response.status_code == 403


def test_student_cannot_access_admin_rooms():
    app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="student-001",
        email="student@test.com",
        full_name="Student",
        role="student",
    )

    response = client.get("/admin/rooms")

    assert response.status_code == 403


# ============================================================
# Useful validation / helper edge cases
# ============================================================


def test_room_label_missing_room(monkeypatch):
    fake = FakeDB({"rooms": []})
    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    assert _room_label_for_maintenance(fake, 999) is None


def test_room_label_none(monkeypatch):
    fake = FakeDB({"rooms": []})

    assert _room_label_for_maintenance(fake, None) is None


def test_rows_empty():
    assert _rows([]) == []


# Keep these constants referenced so changes to report headers are caught
# by the test module rather than silently becoming unused project behavior.
def test_report_headers():
    assert BOOKINGS_REPORT_HEADERS[0] == "Booking ID"
    assert "Student" in BOOKINGS_REPORT_HEADERS
    assert PAYMENTS_REPORT_HEADERS[0] == "Receipt No."
    assert "Amount (RM)" in PAYMENTS_REPORT_HEADERS
