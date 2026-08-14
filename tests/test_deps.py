from fastapi import HTTPException

from agile_ci_demo.deps import (
    CurrentUser,
    _extract_bearer_token,
    get_current_user,
    require_admin,
)

# ============================================================
# Fake Supabase Objects
# ============================================================


class FakeUser:
    def __init__(self, user_id="user001"):
        self.id = user_id


class FakeAuthResponse:
    def __init__(self, user):
        self.user = user


class FakeAuth:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def get_user(self, token):
        if self.error is not None:
            raise self.error

        if self.response is not None:
            return self.response

        return FakeAuthResponse(FakeUser())


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, data):
        self.data = data

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        return FakeResult(self.data)


class FakeSupabase:
    def __init__(
        self,
        *,
        profile=None,
        auth_response=None,
        auth_error=None,
    ):
        self.auth = FakeAuth(
            response=auth_response,
            error=auth_error,
        )

        self.profile = (
            profile
            if profile is not None
            else [
                {
                    "id": "user001",
                    "email": "student@test.com",
                    "full_name": "John Tan",
                    "student_id": "TP123456",
                    "gender": "Male",
                    "role": "student",
                }
            ]
        )

    def table(self, name):
        assert name == "profiles"

        return FakeQuery(self.profile)


# ============================================================
# CurrentUser Model
# ============================================================


def test_current_user_required_fields():
    user = CurrentUser(
        id="user001",
        email="student@test.com",
        full_name="John Tan",
        role="student",
    )

    assert user.id == "user001"
    assert user.email == "student@test.com"
    assert user.full_name == "John Tan"
    assert user.role == "student"

    print("CurrentUser required fields - PASSED")


def test_current_user_optional_fields_default_to_none():
    user = CurrentUser(
        id="user001",
        email="student@test.com",
        full_name="John Tan",
        role="student",
    )

    assert user.student_id is None
    assert user.gender is None

    print("CurrentUser optional defaults - PASSED")


def test_current_user_all_fields():
    user = CurrentUser(
        id="user001",
        email="student@test.com",
        full_name="John Tan",
        student_id="TP123456",
        gender="Male",
        role="student",
    )

    assert user.student_id == "TP123456"
    assert user.gender == "Male"

    print("CurrentUser all fields - PASSED")


def test_current_user_admin():
    user = CurrentUser(
        id="admin001",
        email="admin@test.com",
        full_name="Admin User",
        role="admin",
    )

    assert user.role == "admin"

    print("CurrentUser admin role - PASSED")


# ============================================================
# _extract_bearer_token()
# ============================================================


def test_extract_bearer_token():
    token = _extract_bearer_token("Bearer abc123")

    assert token == "abc123"

    print("bearer token extraction - PASSED")


def test_extract_bearer_token_lowercase():
    token = _extract_bearer_token("bearer abc123")

    assert token == "abc123"

    print("lowercase bearer token - PASSED")


def test_extract_bearer_token_mixed_case():
    token = _extract_bearer_token("BeArEr abc123")

    assert token == "abc123"

    print("mixed-case bearer token - PASSED")


def test_extract_bearer_token_strips_spaces():
    token = _extract_bearer_token("Bearer    abc123   ")

    assert token == "abc123"

    print("bearer token whitespace handling - PASSED")


def test_extract_bearer_token_missing():
    try:
        _extract_bearer_token(None)

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Missing or malformed Authorization header"

    print("missing authorization header - PASSED")


def test_extract_bearer_token_empty_header():
    try:
        _extract_bearer_token("")

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 401

    print("empty authorization header - PASSED")


def test_extract_bearer_token_basic_auth():
    try:
        _extract_bearer_token("Basic abc123")

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Missing or malformed Authorization header"

    print("basic authorization rejected - PASSED")


def test_extract_bearer_token_missing_token():
    try:
        _extract_bearer_token("Bearer")

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 401

    print("missing bearer token - PASSED")


# ============================================================
# get_current_user()
# ============================================================


def test_get_current_user_success(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase_admin",
        fake,
    )

    user = get_current_user(
        authorization="Bearer valid-token",
    )

    assert user.id == "user001"
    assert user.email == "student@test.com"
    assert user.full_name == "John Tan"
    assert user.student_id == "TP123456"
    assert user.gender == "Male"
    assert user.role == "student"

    print("get current user - PASSED")


def test_get_current_user_admin(monkeypatch):
    fake = FakeSupabase(
        profile=[
            {
                "id": "admin001",
                "email": "admin@test.com",
                "full_name": "Admin User",
                "student_id": None,
                "gender": None,
                "role": "admin",
            }
        ]
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase_admin",
        fake,
    )

    user = get_current_user(
        authorization="Bearer admin-token",
    )

    assert user.id == "admin001"
    assert user.email == "admin@test.com"
    assert user.role == "admin"

    print("get current admin - PASSED")


def test_get_current_user_missing_authorization(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase_admin",
        fake,
    )

    try:
        get_current_user(
            authorization=None,
        )

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Missing or malformed Authorization header"

    print("get current user missing authorization - PASSED")


def test_get_current_user_malformed_authorization(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase_admin",
        fake,
    )

    try:
        get_current_user(
            authorization="Basic invalid-token",
        )

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 401

    print("get current user malformed authorization - PASSED")


def test_get_current_user_supabase_missing(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        None,
    )

    try:
        get_current_user(
            authorization="Bearer valid-token",
        )

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 500
        assert exc.detail == "Supabase client is not configured"

    print("supabase client missing - PASSED")


def test_get_current_user_service_role_missing(monkeypatch):
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
        get_current_user(
            authorization="Bearer valid-token",
        )

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 500
        assert exc.detail == "Service role client is not configured"

    print("service role client missing - PASSED")


def test_get_current_user_profile_not_found(monkeypatch):
    fake = FakeSupabase(profile=[])

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase_admin",
        fake,
    )

    try:
        get_current_user(
            authorization="Bearer valid-token",
        )

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 404
        assert "no profile yet" in exc.detail

    print("profile not found - PASSED")


def test_get_current_user_profile_with_null_optional_fields(monkeypatch):
    fake = FakeSupabase(
        profile=[
            {
                "id": "user002",
                "email": "student2@test.com",
                "full_name": "Student Two",
                "student_id": None,
                "gender": None,
                "role": "student",
            }
        ]
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase_admin",
        fake,
    )

    user = get_current_user(
        authorization="Bearer valid-token",
    )

    assert user.id == "user002"
    assert user.student_id is None
    assert user.gender is None
    assert user.role == "student"

    print("profile optional fields - PASSED")


# ============================================================
# Invalid / Expired Authentication
# ============================================================


def test_get_current_user_invalid_auth_response(monkeypatch):
    fake = FakeSupabase(
        auth_response=FakeAuthResponse(user=None),
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase",
        fake,
    )

    monkeypatch.setattr(
        "agile_ci_demo.deps.supabase_admin",
        fake,
    )

    try:
        get_current_user(
            authorization="Bearer invalid-token",
        )

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Invalid or expired session"

    print("invalid auth response - PASSED")


# ============================================================
# require_admin()
# ============================================================


def test_require_admin_success():
    user = CurrentUser(
        id="admin001",
        email="admin@test.com",
        full_name="Admin User",
        role="admin",
    )

    result = require_admin(user)

    assert result is user
    assert result.role == "admin"

    print("admin authorization - PASSED")


def test_require_admin_student_rejected():
    user = CurrentUser(
        id="student001",
        email="student@test.com",
        full_name="Student User",
        role="student",
    )

    try:
        require_admin(user)

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Admin access required"

    print("student admin access rejected - PASSED")


def test_require_admin_other_role_rejected():
    user = CurrentUser(
        id="user001",
        email="user@test.com",
        full_name="Normal User",
        role="staff",
    )

    try:
        require_admin(user)

        assert False, "Expected HTTPException"

    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Admin access required"

    print("non-admin role rejected - PASSED")
