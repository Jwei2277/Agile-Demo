from fastapi import HTTPException
from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import (
    CurrentUser,
    _extract_bearer_token,
    get_current_user,
    require_admin,
)

# ==================================================
# Fake Objects
# ==================================================


class FakeUser:

    def __init__(self):

        self.id = "user001"


class FakeAuthResponse:

    def __init__(self):

        self.user = FakeUser()


class FakeAuth:

    def get_user(self, token):

        return FakeAuthResponse()


class FakeQuery:

    def __init__(self, data):

        self.data = data

    def select(self, *args):

        return self

    def eq(self, *args):

        return self

    def limit(self, *args):

        return self

    def execute(self):

        class Result:

            def __init__(self, data):

                self.data = data

        return Result(self.data)


class FakeSupabase:

    def __init__(self):

        self.auth = FakeAuth()

        self.profile = [
            {
                "id": "user001",
                "email": "student@test.com",
                "full_name": "John Tan",
                "student_id": "TP123456",
                "gender": "Male",
                "role": "student",
            }
        ]

    def table(self, name):

        return FakeQuery(self.profile)


client = TestClient(app)


# ==================================================
# _extract_bearer_token()
# ==================================================


def test_extract_bearer_token():

    token = _extract_bearer_token("Bearer abc123")

    assert token == "abc123"

    print("test_extract_bearer_token PASSED")


def test_extract_bearer_token_missing():

    try:

        _extract_bearer_token(None)

        assert False

    except HTTPException as exc:

        assert exc.status_code == 401

    print("test_extract_bearer_token_missing PASSED")


def test_extract_bearer_token_invalid():

    try:

        _extract_bearer_token("Basic abc")

        assert False

    except HTTPException as exc:

        assert exc.status_code == 401

    print("test_extract_bearer_token_invalid PASSED")


# ==================================================
# get_current_user()
# ==================================================


def test_get_current_user(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase_admin",
        fake,
    )

    user = get_current_user(authorization="Bearer token")

    assert user.email == "student@test.com"

    assert user.role == "student"

    print("test_get_current_user PASSED")


def test_get_current_user_supabase_none(monkeypatch):

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        None,
    )

    try:

        get_current_user(authorization="Bearer token")

        assert False

    except HTTPException as exc:

        assert exc.status_code == 500

    print("test_get_current_user_supabase_none PASSED")


def test_get_current_user_service_role_none(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase_admin",
        None,
    )

    try:

        get_current_user(authorization="Bearer token")

        assert False

    except HTTPException as exc:

        assert exc.status_code == 500

    print("test_get_current_user_service_role_none PASSED")


def test_get_current_user_profile_not_found(monkeypatch):

    fake = FakeSupabase()

    fake.profile = []

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase_admin",
        fake,
    )

    try:

        get_current_user(authorization="Bearer token")

        assert False

    except HTTPException as exc:

        assert exc.status_code == 404

    print("test_get_current_user_profile_not_found PASSED")


# ==================================================
# require_admin()
# ==================================================


def test_require_admin():

    user = CurrentUser(
        id="1",
        email="admin@test.com",
        full_name="Admin",
        role="admin",
    )

    result = require_admin(user)

    assert result.role == "admin"

    print("test_require_admin PASSED")


def test_require_admin_student():

    user = CurrentUser(
        id="1",
        email="student@test.com",
        full_name="Student",
        role="student",
    )

    try:

        require_admin(user)

        assert False

    except HTTPException as exc:

        assert exc.status_code == 403

    print("test_require_admin_student PASSED")


# ==================================================
# CurrentUser
# ==================================================


def test_current_user_model():

    user = CurrentUser(
        id="1",
        email="student@test.com",
        full_name="John",
        student_id="TP123456",
        gender="Male",
        role="student",
    )

    assert user.student_id == "TP123456"

    assert user.gender == "Male"

    print("test_current_user_model PASSED")


def test_current_user_defaults():

    user = CurrentUser(
        id="2",
        email="admin@test.com",
        full_name="Admin",
        role="admin",
    )

    assert user.student_id is None

    assert user.gender is None

    print("test_current_user_defaults PASSED")
