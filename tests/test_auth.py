from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agile_ci_demo.app import app

client = TestClient(app)


# ============================================================
# Fake Supabase Objects
# ============================================================


class FakeAuth:

    def __init__(self):
        self.users = {}

    def sign_up(self, data):

        email = data["email"]

        if email in self.users:
            from supabase import AuthApiError

            raise AuthApiError(
                "User already registered",
                400,
            )

        user = SimpleNamespace(
            id="user-123",
            email=email,
        )

        self.users[email] = {
            "password": data["password"],
            "user": user,
        }

        return SimpleNamespace(user=user)

    def sign_in_with_password(self, data):

        email = data["email"]
        password = data["password"]

        if email not in self.users:
            from supabase import AuthApiError

            raise AuthApiError(
                "Invalid login",
                400,
            )

        if self.users[email]["password"] != password:
            from supabase import AuthApiError

            raise AuthApiError(
                "Invalid password",
                400,
            )

        user = self.users[email]["user"]

        return SimpleNamespace(
            user=user,
            session=SimpleNamespace(
                access_token="fake-access-token",
                refresh_token="fake-refresh-token",
            ),
        )

    # login() sends OTP for untrusted student devices
    def sign_in_with_otp(self, data):
        pass

    def get_user(self, token):

        if token != "valid-token":
            from supabase import AuthApiError

            raise AuthApiError(
                "Invalid token",
                401,
            )

        return SimpleNamespace(user=SimpleNamespace(id="user-123", email="student@example.com"))

    def set_session(self, *_args):
        pass

    def sign_out(self):
        pass

    def verify_otp(self, data):
        pass

    def resend(self, data):
        pass

    def reset_password_email(self, email, options=None):
        pass

    def update_user(self, data):
        pass


class FakeTable:

    def __init__(self):

        self.profile = {
            "id": "user-123",
            "email": "student@example.com",
            "full_name": "Student One",
            "student_id": "SD123456",
            "gender": "Female",
            "role": "student",
        }

    def select(self, *args):
        return self

    def eq(self, *args):
        return self

    def limit(self, *args):
        return self

    def execute(self):

        return SimpleNamespace(data=[self.profile])


class FakeSupabaseAdmin:

    def table(self, name):

        return FakeTable()


class FakeSupabase:

    def __init__(self):

        self.auth = FakeAuth()


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(autouse=True)
def cleanup():

    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


# ============================================================
# REGISTER TESTS
# ============================================================


def test_register_success(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Student One",
            "student_id": "SD123456",
            "email": "student@example.com",
            "gender": "Female",
            "password": "password123",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["message"]

    assert body["user"]["email"] == "student@example.com"


def test_register_invalid_student_id():

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Student",
            "student_id": "123",
            "email": "student@example.com",
            "gender": "Female",
            "password": "password123",
        },
    )

    assert response.status_code == 422


def test_register_invalid_gender():

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Student",
            "student_id": "SD123456",
            "email": "student@example.com",
            "gender": "Other",
            "password": "password123",
        },
    )

    assert response.status_code == 422


def test_register_short_password():

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Student",
            "student_id": "SD123456",
            "email": "student@example.com",
            "gender": "Female",
            "password": "123",
        },
    )

    assert response.status_code == 422


# ============================================================
# LOGIN TESTS
# ============================================================


def test_login_with_email(monkeypatch):

    fake = FakeSupabase()

    fake.auth.users["student@example.com"] = {
        "password": "password123",
        "user": SimpleNamespace(
            id="user-123",
            email="student@example.com",
        ),
    }

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)

    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", FakeSupabaseAdmin())

    response = client.post(
        "/auth/login",
        json={
            "identifier": "student@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 200

    body = response.json()

    # New login flow:
    # student + unknown device => OTP required

    assert body["otp_required"] is True


# ============================================================
# CURRENT USER TEST
# ============================================================


def test_get_current_user(monkeypatch):

    fake = FakeSupabase()

    admin = FakeSupabaseAdmin()

    monkeypatch.setattr("agile_ci_demo.deps.supabase", fake)

    monkeypatch.setattr("agile_ci_demo.deps.supabase_admin", admin)

    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["email"] == "student@example.com"

    assert body["role"] == "student"


def test_current_user_without_token():

    response = client.get("/auth/me")

    assert response.status_code == 401


# ============================================================
# LOGOUT
# ============================================================


def test_logout(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)

    response = client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200

    assert response.json()["message"] == "Logged out"


# ============================================================
# PASSWORD RESET
# ============================================================


def test_forgot_password(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)

    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", FakeSupabaseAdmin())

    response = client.post(
        "/auth/forgot-password",
        json={"email": "student@example.com"},
    )

    assert response.status_code == 200

    assert "message" in response.json()


def test_reset_password(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)

    response = client.post(
        "/auth/reset-password",
        json={
            "access_token": "valid-token",
            "new_password": "newpassword123",
        },
    )

    assert response.status_code == 200

    assert response.json()["message"]
