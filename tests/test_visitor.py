from datetime import datetime, date, time, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user

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

    def order(self, *args, **kwargs):

        return self

    def limit(self, number):

        self.data = self.data[:number]

        return self

    def insert(self, payload):

        row = {
            "id": len(self.table) + 1,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "decided_at": None,
            "rejection_reason": None,
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
            "visitor_requests": [
                {
                    "id": 1,
                    "student_id": "student001",
                    "visitor_name": "Alice",
                    "visitor_email": "alice@test.com",
                    "visitor_relationship": "Friend",
                    "visitor_phone": "0123456789",
                    "visit_date": date(2026, 9, 1),
                    "visit_time": time(10, 0),
                    "status": "pending",
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                    "decided_at": None,
                    "rejection_reason": None,
                }
            ]
        }

    def table(self, name):

        return FakeQuery(self.tables.get(name, []))


# ==================================================
# Fake User
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


def override_student2():

    return CurrentUser(
        id="student999",
        email="other@test.com",
        full_name="Other Student",
        student_id="TP999999",
        gender="Male",
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
# Create Visitor Request
# ==================================================


def test_create_visitor_request(monkeypatch):
    """
    Student creates a visitor request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "visitor_name": "Tom",
        "visitor_email": "tom@test.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-10",
        "visit_time": "10:00:00",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["visitor_name"] == "Tom"

    assert data["status"] == "pending"

    print("test_create_visitor_request PASSED")


def test_create_visitor_request_database_fail(monkeypatch):
    """
    Database rejects insert.
    """

    fake = FakeSupabase()

    fake.tables["visitor_requests"] = []

    class FakeInsertQuery(FakeQuery):

        def insert(self, payload):

            self.data = []

            return self

    class FakeInsertSupabase(FakeSupabase):

        def table(self, name):

            return FakeInsertQuery(self.tables.get(name, []))

    fake = FakeInsertSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    payload = {
        "visitor_name": "Tom",
        "visitor_email": "tom@test.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-10",
        "visit_time": "10:00:00",
    }

    response = client.post(
        "/visitors",
        json=payload,
    )

    assert response.status_code == 400

    print("test_create_visitor_request_database_fail PASSED")


# ==================================================
# My Visitor Requests
# ==================================================


def test_my_visitor_requests(monkeypatch):
    """
    Student views visitor requests.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/visitors/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["visitor_name"] == "Alice"

    print("test_my_visitor_requests PASSED")


def test_my_visitor_requests_empty(monkeypatch):
    """
    Student has no visitor requests.
    """

    fake = FakeSupabase()

    fake.tables["visitor_requests"] = []

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.get("/visitors/me")

    assert response.status_code == 200

    assert response.json() == []

    print("test_my_visitor_requests_empty PASSED")


# ==================================================
# Cancel Visitor Request
# ==================================================


def test_cancel_visitor_request(monkeypatch):
    """
    Student cancels own pending request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/visitors/1")

    assert response.status_code == 204

    print("test_cancel_visitor_request PASSED")


def test_cancel_visitor_request_not_found(monkeypatch):
    """
    Visitor request not found.
    """

    fake = FakeSupabase()

    fake.tables["visitor_requests"] = []

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/visitors/999")

    assert response.status_code == 404

    print("test_cancel_visitor_request_not_found PASSED")


# ==================================================
# Cancel Visitor Request (Remaining Tests)
# ==================================================


def test_cancel_visitor_request_not_owner(monkeypatch):
    """
    Student tries to cancel another student's request.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student2

    response = client.delete("/visitors/1")

    assert response.status_code == 403

    print("test_cancel_visitor_request_not_owner PASSED")


def test_cancel_visitor_request_already_approved(monkeypatch):
    """
    Approved request cannot be cancelled.
    """

    fake = FakeSupabase()

    fake.tables["visitor_requests"][0]["status"] = "approved"

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/visitors/1")

    assert response.status_code == 409

    print("test_cancel_visitor_request_already_approved PASSED")


def test_cancel_visitor_request_already_cancelled(monkeypatch):
    """
    Cancelled request cannot be cancelled again.
    """

    fake = FakeSupabase()

    fake.tables["visitor_requests"][0]["status"] = "cancelled"

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_student

    response = client.delete("/visitors/1")

    assert response.status_code == 409

    print("test_cancel_visitor_request_already_cancelled PASSED")


# ==================================================
# Helper Functions
# ==================================================


def test_db(monkeypatch):
    """
    _db() returns Supabase instance.
    """

    from agile_ci_demo.visitor import _db

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        fake,
    )

    assert _db() == fake

    print("test_db PASSED")


def test_db_not_configured(monkeypatch):
    """
    _db() raises when service role client is missing.
    """

    from agile_ci_demo.visitor import _db

    monkeypatch.setattr(
        "agile_ci_demo.visitor.supabase_admin",
        None,
    )

    with pytest.raises(HTTPException) as exc:

        _db()

    assert exc.value.status_code == 501

    print("test_db_not_configured PASSED")


def test_rows():
    """
    _rows() returns list unchanged.
    """

    from agile_ci_demo.visitor import _rows

    rows = [{"id": 1}]

    assert _rows(rows) == rows

    print("test_rows PASSED")


def test_rows_empty():
    """
    _rows(None) returns empty list.
    """

    from agile_ci_demo.visitor import _rows

    assert _rows(None) == []

    print("test_rows_empty PASSED")


def test_visitor_out():
    """
    Convert database row into VisitorRequestOut.
    """

    from agile_ci_demo.visitor import _visitor_out

    row = {
        "id": 1,
        "visitor_name": "Alice",
        "visitor_email": "alice@test.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": date(2026, 9, 1),
        "visit_time": time(10, 0),
        "status": "pending",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "decided_at": None,
        "rejection_reason": None,
    }

    visitor = _visitor_out(row)

    assert visitor.id == 1
    assert visitor.visitor_name == "Alice"
    assert visitor.status == "pending"

    print("test_visitor_out PASSED")
