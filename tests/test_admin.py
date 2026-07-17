from datetime import datetime, timezone

from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user

client = TestClient(app)


# ==================================================
# Fake Supabase
# ==================================================


class FakeResponse:
    def __init__(self, data):
        self.data = data


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

        new_data = {"id": new_id, **data}

        self.data.append(new_data)

        return self

    def update(self, data):

        for row in self.data:
            row.update(data)

        return self

    def execute(self):
        return FakeResponse(self.data)


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
                    "is_active": True,
                    "hostel_blocks": {"name": "Block A"},
                    "photo_url": None,
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
                    "student": {"full_name": "John Tan", "student_id": "TP123456"},
                    "rooms": {
                        "room_number": "101",
                        "fee_monthly": 100,
                        "hostel_blocks": {"name": "Block A"},
                    },
                    "occupant_count": 1,
                }
            ],
            "maintenance_requests": [
                {
                    "id": 1,
                    "title": "Broken fan",
                    "category": "Electrical",
                    "priority": "High",
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc),
                    "profiles": {"full_name": "John Tan"},
                }
            ],
            "room_transfer_requests": [],
        }

    def table(self, name):

        return FakeQuery(self.tables.get(name, []))


# ==================================================
# Fake Admin User
# ==================================================


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


# ==================================================
# Tests
# ==================================================


def test_admin_dashboard_statistics(monkeypatch):
    """
    View dashboard statistics
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/stats")

    assert response.status_code == 200

    data = response.json()

    assert "total_rooms" in data
    assert "occupied_rooms" in data
    assert data["total_rooms"] == 1


def test_admin_view_all_bookings(monkeypatch):
    """
    Admin view booking queue
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/bookings")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["status"] == "pending"


def test_admin_view_pending_bookings(monkeypatch):
    """
    Admin filter pending bookings
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/bookings/pending")

    assert response.status_code == 200

    assert len(response.json()) == 1


def test_admin_approve_booking(monkeypatch):
    """
    Admin approve booking request
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/bookings/1/approve")

    assert response.status_code == 204


def test_admin_reject_booking(monkeypatch):
    """
    Admin reject booking request
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/bookings/1/reject")

    assert response.status_code in [204, 409]


def test_admin_view_maintenance(monkeypatch):
    """
    Admin view maintenance requests
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/maintenance")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["title"] == "Broken fan"


def test_admin_complete_maintenance(monkeypatch):
    """
    Admin mark maintenance as completed
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    app.dependency_overrides[get_current_user] = override_admin

    response = client.post("/admin/maintenance/1/complete")

    assert response.status_code == 204


def test_admin_list_rooms(monkeypatch):
    """
    Admin view room management list
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.admin.supabase_admin", fake)

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/admin/rooms")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["room_number"] == "101"


def test_admin_access_without_permission():
    """
    Prevent student from accessing admin API
    """

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/admin/stats")

    assert response.status_code == 403
