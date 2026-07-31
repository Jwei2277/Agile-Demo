from fastapi.testclient import TestClient
import pytest
from supabase import AuthApiError

from agile_ci_demo.app import app
from agile_ci_demo.deps import (
    CurrentUser,
    get_current_user,
)

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

    def update(self, values):

        for row in self.table:

            row.update(values)

        return self

    def eq(self, *args):

        return self

    def limit(self, *args):

        return self

    def execute(self):

        return FakeResponse(self.data)


# ============================================================
# Fake Auth
# ============================================================


class FakeAuth:

    def sign_in_with_password(self, payload):

        if payload["password"] != "password123":

            raise AuthApiError({"message": "Invalid login credentials"})

        return True

    def set_session(self, *args):

        return True

    def update_user(self, payload):

        return True


# ============================================================
# Fake Supabase
# ============================================================


class FakeSupabase:

    def __init__(self):

        self.auth = FakeAuth()

        self.tables = {
            "profiles": [
                {
                    "id": "user001",
                    "email": "student@test.com",
                    "full_name": "John Tan",
                    "student_id": "TP123456",
                    "gender": "Male",
                    "role": "student",
                }
            ]
        }

    def table(self, name):

        return FakeQuery(self.tables.get(name, []))


# ============================================================
# Fake User
# ============================================================


def override_user():

    return CurrentUser(
        id="user001",
        email="student@test.com",
        full_name="John Tan",
        student_id="TP123456",
        gender="Male",
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
# Update Profile Tests
# ============================================================


def test_update_profile_name(monkeypatch):
    """
    Update full name.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.profile.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    payload = {
        "full_name": "John Updated",
    }

    response = client.patch(
        "/profile",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["full_name"] == "John Updated"

    print("test_update_profile_name PASSED")


def test_update_profile_gender(monkeypatch):
    """
    Update gender.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.profile.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    payload = {
        "gender": "Female",
    }

    response = client.patch(
        "/profile",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["gender"] == "Female"

    print("test_update_profile_gender PASSED")


def test_update_profile_all_fields(monkeypatch):
    """
    Update full name and gender.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.profile.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    payload = {
        "full_name": "Mary Tan",
        "gender": "Female",
    }

    response = client.patch(
        "/profile",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["full_name"] == "Mary Tan"
    assert data["gender"] == "Female"

    print("test_update_profile_all_fields PASSED")


def test_update_profile_no_fields(monkeypatch):
    """
    No fields supplied.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.profile.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.patch(
        "/profile",
        json={},
    )

    assert response.status_code == 400

    print("test_update_profile_no_fields PASSED")


def test_update_profile_not_found(monkeypatch):
    """
    Profile not found.
    """

    fake = FakeSupabase()

    fake.tables["profiles"] = []

    monkeypatch.setattr(
        "agile_ci_demo.profile.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    payload = {
        "full_name": "John",
    }

    response = client.patch(
        "/profile",
        json=payload,
    )

    assert response.status_code == 404

    print("test_update_profile_not_found PASSED")


def test_update_profile_service_role_missing(monkeypatch):
    """
    Service role client missing.
    """

    monkeypatch.setattr(
        "agile_ci_demo.profile.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = override_user

    payload = {
        "full_name": "John",
    }

    response = client.patch(
        "/profile",
        json=payload,
    )

    assert response.status_code == 501

    print("test_update_profile_service_role_missing PASSED")

    # ============================================================


# Change Password Tests
# ============================================================


def test_change_password(monkeypatch):
    """
    Change password successfully.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.profile.supabase",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    payload = {
        "old_password": "password123",
        "new_password": "newpassword123",
    }

    response = client.post(
        "/profile/change-password",
        json=payload,
        headers={
            "Authorization": "Bearer fake-token",
        },
    )

    assert response.status_code == 200

    assert response.json()["message"] == "Password updated."

    print("test_change_password PASSED")


def test_change_password_missing_authorization(monkeypatch):
    """
    Missing Authorization header.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.profile.supabase",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    payload = {
        "old_password": "password123",
        "new_password": "newpassword123",
    }

    response = client.post(
        "/profile/change-password",
        json=payload,
    )

    assert response.status_code == 401

    print("test_change_password_missing_authorization PASSED")


def test_change_password_short_password(monkeypatch):
    """
    New password shorter than 8 characters.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.profile.supabase",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    payload = {
        "old_password": "password123",
        "new_password": "123",
    }

    response = client.post(
        "/profile/change-password",
        json=payload,
        headers={
            "Authorization": "Bearer fake-token",
        },
    )

    assert response.status_code == 422

    print("test_change_password_short_password PASSED")
