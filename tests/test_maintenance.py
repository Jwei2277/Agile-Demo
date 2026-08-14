import io
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
# Fake Storage
# ============================================================


class FakeBucket:
    def upload(self, *args, **kwargs):

        return None

    def get_public_url(self, path):

        return f"https://example.com/{path}"


class FakeStorage:
    def from_(self, name):

        return FakeBucket()


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

    def order(self, *args, **kwargs):

        return self

    def limit(self, number):

        self.data = self.data[:number]

        return self

    def insert(self, payload):

        row = {
            "id": len(self.table) + 1,
            "created_at": datetime.now(UTC).isoformat(),
            "resolved_at": None,
            **payload,
        }

        self.table.append(row)

        self.data = [row]

        return self

    def execute(self):

        return FakeResponse(self.data)


# ============================================================
# Fake Supabase
# ============================================================


class FakeSupabase:
    def __init__(self):

        self.storage = FakeStorage()

        self.tables = {
            "rooms": [
                {
                    "id": 1,
                    "room_number": "101",
                    "hostel_blocks": {"name": "Block A"},
                }
            ],
            "maintenance_requests": [
                {
                    "id": 1,
                    "student_id": "student001",
                    "room_id": 1,
                    "title": "Broken Fan",
                    "category": "Electrical",
                    "priority": "High",
                    "status": "pending",
                    "photo_url": None,
                    "assigned_staff": None,
                    "remarks": None,
                    "created_at": datetime.now(UTC).isoformat(),
                    "resolved_at": None,
                }
            ],
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


@pytest.fixture(autouse=True)
def cleanup():

    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


# ============================================================
# Create Request Tests
# ============================================================


def test_create_request(monkeypatch):
    """
    Student submits a maintenance request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.maintenance.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/maintenance",
        data={
            "title": "Broken Fan",
            "category": "Electrical",
            "priority": "High",
            "room_id": 1,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "Broken Fan"
    assert data["status"] == "pending"

    print("test_create_request PASSED")


def test_create_request_with_photo(monkeypatch):
    """
    Student submits a request with photo.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.maintenance.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    file = (
        "photo.jpg",
        io.BytesIO(b"fake-image"),
        "image/jpeg",
    )

    response = client.post(
        "/maintenance",
        data={
            "title": "Broken Fan",
            "category": "Electrical",
            "priority": "High",
        },
        files={
            "photo": file,
        },
    )

    assert response.status_code == 201

    assert response.json()["photo_url"] is not None

    print("test_create_request_with_photo PASSED")


def test_create_request_invalid_photo(monkeypatch):
    """
    Invalid file type.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.maintenance.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    file = (
        "document.pdf",
        io.BytesIO(b"pdf"),
        "application/pdf",
    )

    response = client.post(
        "/maintenance",
        data={
            "title": "Broken Fan",
        },
        files={
            "photo": file,
        },
    )

    assert response.status_code == 400

    print("test_create_request_invalid_photo PASSED")


def test_create_request_missing_title(monkeypatch):
    """
    Title is required.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.maintenance.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.post(
        "/maintenance",
        data={
            "category": "Electrical",
        },
    )

    assert response.status_code == 422

    print("test_create_request_missing_title PASSED")


# ============================================================
# My Requests
# ============================================================


def test_my_requests(monkeypatch):
    """
    Student views own maintenance requests.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.maintenance.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/maintenance/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["title"] == "Broken Fan"

    print("test_my_requests PASSED")


def test_my_requests_empty(monkeypatch):
    """
    Student has no maintenance requests.
    """

    fake = FakeSupabase()

    fake.tables["maintenance_requests"] = []

    monkeypatch.setattr(
        "agile_ci_demo.maintenance.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/maintenance/me")

    assert response.status_code == 200

    assert response.json() == []

    print("test_my_requests_empty PASSED")


# ============================================================
# _db()
# ============================================================


def test_db(monkeypatch):
    """
    _db returns Supabase instance.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.maintenance.supabase_admin",
        fake,
    )

    from agile_ci_demo.maintenance import _db

    assert _db() == fake

    print("test_db PASSED")


# ============================================================
# _rows()
# ============================================================


def test_rows():

    from agile_ci_demo.maintenance import _rows

    data = [{"id": 1}]

    assert _rows(data) == data

    print("test_rows PASSED")


def test_rows_empty():

    from agile_ci_demo.maintenance import _rows

    assert _rows(None) == []

    print("test_rows_empty PASSED")


# ============================================================
# _room_label()
# ============================================================


def test_room_label():

    from agile_ci_demo.maintenance import _room_label

    fake = FakeSupabase()

    label = _room_label(fake, 1)

    assert label == "Block A · Room 101"

    print("test_room_label PASSED")


def test_room_label_none():

    from agile_ci_demo.maintenance import _room_label

    fake = FakeSupabase()

    label = _room_label(fake, None)

    assert label is None

    print("test_room_label_none PASSED")


def test_room_label_not_found():

    from agile_ci_demo.maintenance import _room_label

    fake = FakeSupabase()

    fake.tables["rooms"] = []

    label = _room_label(fake, 99)

    assert label is None

    print("test_room_label_not_found PASSED")


# ============================================================
# _maintenance_out()
# ============================================================


def test_maintenance_out():

    from agile_ci_demo.maintenance import _maintenance_out

    fake = FakeSupabase()

    row = fake.tables["maintenance_requests"][0]

    result = _maintenance_out(
        fake,
        row,
        "John Tan",
        "TP123456",
    )

    assert result.title == "Broken Fan"

    assert result.student_name == "John Tan"

    assert result.student_id == "TP123456"

    print("test_maintenance_out PASSED")
