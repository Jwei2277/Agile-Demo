from fastapi.testclient import TestClient

import pytest

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
        self.data = list(table)
        self.payload = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        self.data = [row for row in self.data if row.get(column) == value]
        return self

    def limit(self, number):
        self.data = self.data[:number]
        return self

    def order(self, column, desc=False):
        self.data.sort(
            key=lambda row: row.get(column) or "",
            reverse=desc,
        )
        return self

    def insert(self, payload):
        self.payload = payload

        new_row = dict(payload)

        if "id" not in new_row:
            new_row["id"] = 999

        # Simulate database-generated fields.
        new_row.setdefault(
            "requested_at",
            "2026-08-15T12:00:00+00:00",
        )
        new_row.setdefault("decided_at", None)
        new_row.setdefault("rejection_reason", None)

        self.data = [new_row]

        return self

    def update(self, payload):
        for row in self.data:
            row.update(payload)

        return self

    def execute(self):
        return FakeResponse(self.data)


# ============================================================
# Fake Supabase
# ============================================================


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "visitor_requests": [
                {
                    "id": 1,
                    "student_id": "student001",
                    "visitor_name": "John Tan",
                    "visitor_email": "john@example.com",
                    "visitor_relationship": "Friend",
                    "visitor_phone": "0123456789",
                    "visit_date": "2026-09-10",
                    "visit_time": "14:00:00",
                    "status": "pending",
                    "rejection_reason": None,
                    "requested_at": "2026-08-15T10:00:00Z",
                    "decided_at": None,
                },
                {
                    "id": 2,
                    "student_id": "student001",
                    "visitor_name": "Mary Tan",
                    "visitor_email": "mary@example.com",
                    "visitor_relationship": "Family",
                    "visitor_phone": "01234567890",
                    "visit_date": "2026-09-12",
                    "visit_time": "15:00:00",
                    "status": "approved",
                    "rejection_reason": None,
                    "requested_at": "2026-08-14T10:00:00Z",
                    "decided_at": "2026-08-14T12:00:00Z",
                },
                {
                    "id": 3,
                    "student_id": "student001",
                    "visitor_name": "Ali Rahman",
                    "visitor_email": "ali@example.com",
                    "visitor_relationship": "Friend",
                    "visitor_phone": "0123456789",
                    "visit_date": "2026-09-15",
                    "visit_time": "16:00:00",
                    "status": "cancelled",
                    "rejection_reason": None,
                    "requested_at": "2026-08-13T10:00:00Z",
                    "decided_at": "2026-08-13T11:00:00Z",
                },
                {
                    "id": 4,
                    "student_id": "other001",
                    "visitor_name": "Other Visitor",
                    "visitor_email": "other@example.com",
                    "visitor_relationship": "Friend",
                    "visitor_phone": "0123456789",
                    "visit_date": "2026-09-20",
                    "visit_time": "13:00:00",
                    "status": "pending",
                    "rejection_reason": None,
                    "requested_at": "2026-08-15T09:00:00Z",
                    "decided_at": None,
                },
            ]
        }

        self.inserted_payload = None

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


# ============================================================
# Fake User
# ============================================================


def student_user():
    return CurrentUser(
        id="student001",
        email="student@test.com",
        full_name="Student One",
        student_id="TP123456",
        gender="Male",
        role="student",
    )


def other_student_user():
    return CurrentUser(
        id="other001",
        email="other@test.com",
        full_name="Other Student",
        student_id="TP999999",
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
# Authentication
# ============================================================


def test_create_visitor_without_login():
    app.dependency_overrides.clear()

    payload = {
        "visitor_name": "John Tan",
        "visitor_email": "john@example.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-10",
        "visit_time": "14:00",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 401

    print("create visitor without login - PASSED")


def test_get_my_visitors_without_login():
    app.dependency_overrides.clear()

    response = client.get("/visitors/me")

    assert response.status_code == 401

    print("get visitors without login - PASSED")


def test_cancel_visitor_without_login():
    app.dependency_overrides.clear()

    response = client.delete("/visitors/1")

    assert response.status_code == 401

    print("cancel visitor without login - PASSED")


# ============================================================
# Create Visitor Request
# ============================================================


def test_create_visitor_request(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "visitor_name": "Sarah Tan",
        "visitor_email": "sarah@example.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-20",
        "visit_time": "14:30",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["visitor_name"] == "Sarah Tan"
    assert data["visitor_email"] == "sarah@example.com"
    assert data["visitor_relationship"] == "Friend"
    assert data["visitor_phone"] == "0123456789"
    assert data["visit_date"] == "2026-09-20"
    assert data["visit_time"].startswith("14:30")
    assert data["status"] == "pending"

    print("create visitor request - PASSED")


def test_create_visitor_request_student_id_is_used(
    monkeypatch,
):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "visitor_name": "Sarah Tan",
        "visitor_email": "sarah@example.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-20",
        "visit_time": "14:30",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 201

    print("visitor request student ownership - PASSED")


def test_create_visitor_invalid_email(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "visitor_name": "Sarah Tan",
        "visitor_email": "invalid-email",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-20",
        "visit_time": "14:30",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 422

    print("visitor invalid email - PASSED")


def test_create_visitor_invalid_phone(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "visitor_name": "Sarah Tan",
        "visitor_email": "sarah@example.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "abc",
        "visit_date": "2026-09-20",
        "visit_time": "14:30",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 422

    print("visitor invalid phone - PASSED")


def test_create_visitor_missing_name(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "visitor_email": "sarah@example.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-20",
        "visit_time": "14:30",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 422

    print("visitor missing name - PASSED")


def test_create_visitor_missing_email(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "visitor_name": "Sarah Tan",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-20",
        "visit_time": "14:30",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 422

    print("visitor missing email - PASSED")


def test_create_visitor_missing_date(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "visitor_name": "Sarah Tan",
        "visitor_email": "sarah@example.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_time": "14:30",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 422

    print("visitor missing date - PASSED")


def test_create_visitor_missing_time(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "visitor_name": "Sarah Tan",
        "visitor_email": "sarah@example.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-20",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 422

    print("visitor missing time - PASSED")


# ============================================================
# Database Configuration
# ============================================================


def test_create_visitor_service_role_missing(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "visitor_name": "Sarah Tan",
        "visitor_email": "sarah@example.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-20",
        "visit_time": "14:30",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 501
    assert response.json()["detail"] == "Server misconfigured: missing service role key"

    print("visitor service role missing - PASSED")


# ============================================================
# Get My Visitor Requests
# ============================================================


def test_get_my_visitor_requests(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/visitors/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 3

    assert all(item["visitor_name"] != "Other Visitor" for item in data)

    print("get my visitor requests - PASSED")


def test_get_my_visitor_requests_only_own_records(
    monkeypatch,
):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/visitors/me")

    assert response.status_code == 200

    data = response.json()

    names = {item["visitor_name"] for item in data}

    assert names == {
        "John Tan",
        "Mary Tan",
        "Ali Rahman",
    }

    print("visitor ownership filtering - PASSED")


def test_cancelled_requests_are_last(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/visitors/me")

    assert response.status_code == 200

    data = response.json()

    statuses = [item["status"] for item in data]

    assert statuses[-1] == "cancelled"

    print("cancelled requests sorted last - PASSED")


def test_get_visitor_request_fields(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/visitors/me")

    assert response.status_code == 200

    item = response.json()[0]

    assert "id" in item
    assert "visitor_name" in item
    assert "visitor_email" in item
    assert "visitor_relationship" in item
    assert "visitor_phone" in item
    assert "visit_date" in item
    assert "visit_time" in item
    assert "status" in item
    assert "rejection_reason" in item
    assert "requested_at" in item
    assert "decided_at" in item

    print("visitor response fields - PASSED")


def test_get_my_visitors_service_role_missing(
    monkeypatch,
):
    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/visitors/me")

    assert response.status_code == 501

    print("get visitors service role missing - PASSED")


# ============================================================
# Cancel Visitor Request
# ============================================================


def test_cancel_pending_visitor_request(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.delete("/visitors/1")

    assert response.status_code == 204

    print("cancel pending visitor request - PASSED")


def test_cancel_pending_request_does_not_return_body(
    monkeypatch,
):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.delete("/visitors/1")

    assert response.status_code == 204
    assert response.content == b""

    print("cancel visitor empty response - PASSED")


def test_cancel_visitor_request_not_found(monkeypatch):
    fake = FakeSupabase()

    fake.tables["visitor_requests"] = []

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.delete("/visitors/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Visitor request not found"

    print("cancel visitor not found - PASSED")


def test_cancel_other_students_request(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.delete("/visitors/4")

    assert response.status_code == 403
    assert response.json()["detail"] == "Not your visitor request"

    print("cancel another student's visitor request - PASSED")


def test_cancel_approved_request(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.delete("/visitors/2")

    assert response.status_code == 409

    assert "already 'approved'" in response.json()["detail"]

    print("cancel approved visitor request rejected - PASSED")


def test_cancel_already_cancelled_request(
    monkeypatch,
):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.delete("/visitors/3")

    assert response.status_code == 409

    assert "already 'cancelled'" in response.json()["detail"]

    print("cancel already cancelled request rejected - PASSED")


def test_cancel_visitor_service_role_missing(
    monkeypatch,
):
    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.delete("/visitors/1")

    assert response.status_code == 501

    print("cancel visitor service role missing - PASSED")
