import pytest
from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user

client = TestClient(app)


# ==================================================
# Fake Objects
# ==================================================


class FakeUser:
    def __init__(self, user_id, email):

        self.id = user_id
        self.email = email


class FakeSession:
    def __init__(self):

        self.access_token = "fake-access-token"
        self.refresh_token = "fake-refresh-token"


class FakeAuthResponse:
    def __init__(self, user=None, session=None):

        self.user = user
        self.session = session


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

    def limit(self, number):

        self.data = self.data[:number]

        return self

    def insert(self, value):

        self.table.append(value)

        self.data = [value]

        return self

    def execute(self):

        return FakeResponse(self.data)


# ==================================================
# Fake Auth
# ==================================================


class FakeAuth:
    def sign_up(self, data):

        return FakeAuthResponse(
            FakeUser(
                "user001",
                data["email"],
            )
        )

    def verify_otp(self, data):

        return FakeAuthResponse(
            FakeUser(
                "user001",
                data["email"],
            ),
            FakeSession(),
        )

    def resend(self, data):

        return None

    def sign_in_with_password(self, data):

        if data["password"] != "password123":
            raise ValueError("Invalid credentials")

        return FakeAuthResponse(
            FakeUser(
                "user001",
                data["email"],
            ),
            FakeSession(),
        )

    def sign_in_with_otp(self, data):

        return None

    def reset_password_email(self, email, options):

        return None

    def set_session(self, access, refresh):

        return None

    def sign_out(self):

        return None

    def update_user(self, data):

        return None


# ==================================================
# Fake Supabase
# ==================================================


class FakeSupabase:
    def __init__(self):

        self.auth = FakeAuth()

        self.tables = {
            "profiles": [
                {
                    "id": "user001",
                    "email": "student@test.com",
                    "student_id": "TP123456",
                    "role": "student",
                },
                {
                    "id": "admin001",
                    "email": "admin@test.com",
                    "student_id": None,
                    "role": "admin",
                },
            ],
            "trusted_devices": [],
        }

    def table(self, name):

        return FakeQuery(self.tables.get(name, []))


# ==================================================
# Fake Current User
# ==================================================


def override_user():

    return CurrentUser(
        id="user001",
        email="student@test.com",
        full_name="John Tan",
        student_id="TP123456",
        gender="Male",
        role="student",
    )


def override_admin():

    return CurrentUser(
        id="admin001",
        email="admin@test.com",
        full_name="Admin",
        student_id=None,
        gender=None,
        role="admin",
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
# Register Tests
# ==================================================


def test_register(monkeypatch):
    """
    Register a new account.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "full_name": "John Tan",
        "student_id": "TP123456",
        "email": "student@test.com",
        "gender": "Male",
        "password": "password123",
    }

    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == "student@test.com"
    assert data["user"]["id"] == "user001"

    print("test_register PASSED")


def test_register_missing_name(monkeypatch):
    """
    Missing full name.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "student_id": "TP123456",
        "email": "student@test.com",
        "gender": "Male",
        "password": "password123",
    }

    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422

    print("test_register_missing_name PASSED")


def test_register_invalid_student_id(monkeypatch):
    """
    Invalid student ID format.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "full_name": "John",
        "student_id": "123456",
        "email": "student@test.com",
        "gender": "Male",
        "password": "password123",
    }

    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422

    print("test_register_invalid_student_id PASSED")


def test_register_invalid_email(monkeypatch):
    """
    Invalid email.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "full_name": "John",
        "student_id": "TP123456",
        "email": "invalid-email",
        "gender": "Male",
        "password": "password123",
    }

    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422

    print("test_register_invalid_email PASSED")


def test_register_invalid_gender(monkeypatch):
    """
    Invalid gender.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "full_name": "John",
        "student_id": "TP123456",
        "email": "student@test.com",
        "gender": "Other",
        "password": "password123",
    }

    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422

    print("test_register_invalid_gender PASSED")


def test_register_short_password(monkeypatch):
    """
    Password shorter than 8 characters.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "full_name": "John",
        "student_id": "TP123456",
        "email": "student@test.com",
        "gender": "Male",
        "password": "123",
    }

    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422

    print("test_register_short_password PASSED")


# ==================================================
# Signup OTP
# ==================================================


def test_verify_signup_otp(monkeypatch):
    """
    Verify signup OTP.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "email": "student@test.com",
        "otp": "123456",
    }

    response = client.post(
        "/auth/verify-signup-otp",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["access_token"] == "fake-access-token"

    print("test_verify_signup_otp PASSED")


def test_verify_signup_invalid_otp(monkeypatch):
    """
    OTP validation.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "email": "student@test.com",
        "otp": "123",
    }

    response = client.post(
        "/auth/verify-signup-otp",
        json=payload,
    )

    assert response.status_code == 422

    print("test_verify_signup_invalid_otp PASSED")


def test_resend_signup_otp(monkeypatch):
    """
    Resend signup OTP.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "email": "student@test.com",
    }

    response = client.post(
        "/auth/resend-signup-otp",
        json=payload,
    )

    assert response.status_code == 200

    assert "message" in response.json()

    print("test_resend_signup_otp PASSED")


# ==================================================
# Login Tests
# ==================================================


def test_login_with_email(monkeypatch):
    """
    Student login using email.
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)
    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", fake)

    payload = {
        "identifier": "student@test.com",
        "password": "password123",
        "remember_me": False,
        "trusted_device_token": None,
    }

    response = client.post("/auth/login", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert data["otp_required"] is True
    assert data["email"] == "student@test.com"

    print("test_login_with_email PASSED")


def test_login_with_student_id(monkeypatch):
    """
    Student login using student ID.
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)
    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", fake)

    payload = {
        "identifier": "TP123456",
        "password": "password123",
        "remember_me": False,
        "trusted_device_token": None,
    }

    response = client.post("/auth/login", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert data["otp_required"] is True

    print("test_login_with_student_id PASSED")


def test_login_invalid_student_id(monkeypatch):
    """
    Student ID does not exist.
    """

    fake = FakeSupabase()

    fake.tables["profiles"] = []

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)
    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", fake)

    payload = {
        "identifier": "TP999999",
        "password": "password123",
    }

    response = client.post("/auth/login", json=payload)

    assert response.status_code == 401

    print("test_login_invalid_student_id PASSED")


def test_login_missing_identifier(monkeypatch):
    """
    Missing identifier.
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)
    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", fake)

    payload = {
        "password": "password123",
    }

    response = client.post("/auth/login", json=payload)

    assert response.status_code == 422

    print("test_login_missing_identifier PASSED")


def test_login_missing_password(monkeypatch):
    """
    Missing password.
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)
    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", fake)

    payload = {
        "identifier": "student@test.com",
    }

    response = client.post("/auth/login", json=payload)

    assert response.status_code == 422

    print("test_login_missing_password PASSED")


def test_login_empty_password(monkeypatch):
    """
    Empty password.
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)
    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", fake)

    payload = {
        "identifier": "student@test.com",
        "password": "",
    }

    response = client.post("/auth/login", json=payload)

    assert response.status_code == 422

    print("test_login_empty_password PASSED")


# ==================================================
# Verify OTP Tests
# ==================================================


def test_verify_otp(monkeypatch):
    """
    Verify login OTP.
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)
    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", fake)

    payload = {
        "email": "student@test.com",
        "otp": "123456",
        "remember_me": False,
    }

    response = client.post("/auth/verify-otp", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert data["access_token"] == "fake-access-token"
    assert data["refresh_token"] == "fake-refresh-token"

    print("test_verify_otp PASSED")


def test_verify_otp_remember_me(monkeypatch):
    """
    Verify OTP with remember me enabled.
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)
    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", fake)

    monkeypatch.setattr(
        "agile_ci_demo.auth._issue_trusted_device_token",
        lambda student_id: "trusted-device-token",
    )

    payload = {
        "email": "student@test.com",
        "otp": "123456",
        "remember_me": True,
    }

    response = client.post("/auth/verify-otp", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert data["trusted_device_token"] == "trusted-device-token"

    print("test_verify_otp_remember_me PASSED")


def test_verify_invalid_otp(monkeypatch):
    """
    Invalid OTP format.
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)
    monkeypatch.setattr("agile_ci_demo.auth.supabase_admin", fake)

    payload = {
        "email": "student@test.com",
        "otp": "123",
        "remember_me": False,
    }

    response = client.post("/auth/verify-otp", json=payload)

    assert response.status_code == 422

    print("test_verify_invalid_otp PASSED")


# ==================================================
# Resend OTP
# ==================================================


def test_resend_otp(monkeypatch):
    """
    Resend login OTP.
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)

    payload = {
        "email": "student@test.com",
    }

    response = client.post("/auth/resend-otp", json=payload)

    assert response.status_code == 200

    assert "message" in response.json()

    print("test_resend_otp PASSED")


# ==================================================
# Current User
# ==================================================


def test_me(monkeypatch):
    """
    Get current user profile.
    """

    app.dependency_overrides[get_current_user] = override_user

    response = client.get("/auth/me")

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "student@test.com"
    assert data["student_id"] == "TP123456"

    print("test_me PASSED")


def test_me_admin(monkeypatch):
    """
    Get current admin profile.
    """

    app.dependency_overrides[get_current_user] = override_admin

    response = client.get("/auth/me")

    assert response.status_code == 200

    data = response.json()

    assert data["role"] == "admin"

    print("test_me_admin PASSED")


# ==================================================
# Logout
# ==================================================


def test_logout(monkeypatch):
    """
    Logout successfully.
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.auth.supabase", fake)

    response = client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer fake-access-token"},
    )

    assert response.status_code == 200

    assert response.json()["message"] == "Logged out"

    print("test_logout PASSED")


# ==================================================
# Forgot Password Tests
# ==================================================


def test_forgot_password(monkeypatch):
    """
    Forgot password with registered email.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase_admin",
        fake,
    )

    payload = {
        "email": "student@test.com",
    }

    response = client.post(
        "/auth/forgot-password",
        json=payload,
    )

    assert response.status_code == 200

    assert response.json()["message"] == "A reset link has been sent to your email."

    print("test_forgot_password PASSED")


def test_forgot_password_email_not_found(monkeypatch):
    """
    Email not registered.
    """

    fake = FakeSupabase()

    fake.tables["profiles"] = []

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase_admin",
        fake,
    )

    payload = {
        "email": "unknown@test.com",
    }

    response = client.post(
        "/auth/forgot-password",
        json=payload,
    )

    assert response.status_code == 404

    print("test_forgot_password_email_not_found PASSED")


def test_forgot_password_invalid_email(monkeypatch):
    """
    Invalid email format.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase_admin",
        fake,
    )

    payload = {
        "email": "invalid-email",
    }

    response = client.post(
        "/auth/forgot-password",
        json=payload,
    )

    assert response.status_code == 422

    print("test_forgot_password_invalid_email PASSED")


# ==================================================
# Reset Password Tests
# ==================================================


def test_reset_password(monkeypatch):
    """
    Reset password successfully.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "access_token": "fake-access-token",
        "new_password": "newpassword123",
    }

    response = client.post(
        "/auth/reset-password",
        json=payload,
    )

    assert response.status_code == 200

    assert (
        response.json()["message"] == "Password updated. You can now log in with your new password."
    )

    print("test_reset_password PASSED")


def test_reset_password_short_password(monkeypatch):
    """
    Password shorter than 8 characters.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "access_token": "fake-access-token",
        "new_password": "123",
    }

    response = client.post(
        "/auth/reset-password",
        json=payload,
    )

    assert response.status_code == 422

    print("test_reset_password_short_password PASSED")


def test_reset_password_missing_token(monkeypatch):
    """
    Missing access token.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "new_password": "newpassword123",
    }

    response = client.post(
        "/auth/reset-password",
        json=payload,
    )

    assert response.status_code == 422

    print("test_reset_password_missing_token PASSED")


def test_reset_password_missing_password(monkeypatch):
    """
    Missing new password.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "access_token": "fake-access-token",
    }

    response = client.post(
        "/auth/reset-password",
        json=payload,
    )

    assert response.status_code == 422

    print("test_reset_password_missing_password PASSED")


def test_reset_password_empty_token(monkeypatch):
    """
    Empty access token.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.auth.supabase",
        fake,
    )

    payload = {
        "access_token": "",
        "new_password": "newpassword123",
    }

    response = client.post(
        "/auth/reset-password",
        json=payload,
    )

    assert response.status_code == 422

    print("test_reset_password_empty_token PASSED")
