import pytest
from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.documents import (
    ALLOWED_DOCUMENT_TYPES,
    DOCUMENT_BUCKET,
    MAX_DOCUMENT_BYTES,
    SIGNED_URL_EXPIRY_SECONDS,
    _db,
    _document_out,
    _rows,
    _signed_url,
)

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


class FakeStorageBucket:
    def __init__(
        self,
        *,
        upload_error=None,
        signed_url=None,
        signed_url_error=None,
    ):
        self.upload_error = upload_error
        self.signed_url = signed_url
        self.signed_url_error = signed_url_error
        self.uploaded = []

    def upload(self, path, contents, options):
        if self.upload_error is not None:
            raise self.upload_error

        self.uploaded.append(
            {
                "path": path,
                "contents": contents,
                "options": options,
            }
        )

        return {"path": path}

    def create_signed_url(self, path, expiry):
        if self.signed_url_error is not None:
            raise self.signed_url_error

        return {
            "signedUrl": (
                self.signed_url
                if self.signed_url is not None
                else f"https://example.com/{path}?expires={expiry}"
            )
        }


class FakeStorage:
    def __init__(
        self,
        *,
        upload_error=None,
        signed_url=None,
        signed_url_error=None,
    ):
        self.bucket = FakeStorageBucket(
            upload_error=upload_error,
            signed_url=signed_url,
            signed_url_error=signed_url_error,
        )

    def from_(self, bucket_name):
        assert bucket_name == DOCUMENT_BUCKET
        return self.bucket


# ============================================================
# Fake Query
# ============================================================


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.current_rows = list(rows)
        self.insert_payload = None
        self.updated = False

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        self.current_rows = [row for row in self.current_rows if row.get(column) == value]
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, number):
        self.current_rows = self.current_rows[:number]
        return self

    def insert(self, payload):
        self.insert_payload = payload

        self.current_rows = [
            {
                "id": 100,
                "student_id": payload["student_id"],
                "document_type": payload["document_type"],
                "file_url": payload["file_url"],
                "file_name": payload["file_name"],
                "status": payload["status"],
                "rejection_reason": None,
                "uploaded_at": "2026-08-15T10:00:00+00:00",
                "verified_at": None,
            }
        ]

        return self

    def execute(self):
        return FakeResponse(self.current_rows)


# ============================================================
# Fake Supabase
# ============================================================


class FakeSupabase:
    def __init__(
        self,
        documents=None,
        *,
        upload_error=None,
        signed_url=None,
        signed_url_error=None,
        insert_empty=False,
    ):
        self.documents = documents or []
        self.insert_empty = insert_empty
        self.storage = FakeStorage(
            upload_error=upload_error,
            signed_url=signed_url,
            signed_url_error=signed_url_error,
        )
        self.last_query = None

    def table(self, name):
        assert name == "student_documents"

        if self.insert_empty:
            query = FakeQuery([])
            original_insert = query.insert

            def insert_empty_result(payload):
                original_insert(payload)
                query.current_rows = []
                return query

            query.insert = insert_empty_result

        else:
            query = FakeQuery(self.documents)

        self.last_query = query
        return query


# ============================================================
# Fake User
# ============================================================


def override_user():
    return CurrentUser(
        id="student-001",
        email="student@test.com",
        full_name="John Tan",
        student_id="TP123456",
        gender="Male",
        role="student",
    )


# ============================================================
# Sample Data
# ============================================================


def sample_document():
    return {
        "id": 1,
        "student_id": "student-001",
        "document_type": "Student ID",
        "file_url": "student-001/test.pdf",
        "file_name": "student-card.pdf",
        "status": "pending",
        "rejection_reason": None,
        "uploaded_at": "2026-08-15T10:00:00+00:00",
        "verified_at": None,
    }


# ============================================================
# Cleanup
# ============================================================


@pytest.fixture(autouse=True)
def cleanup():
    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


# ============================================================
# Constants
# ============================================================


def test_document_bucket():
    assert DOCUMENT_BUCKET == "student-documents"


def test_max_document_size():
    assert MAX_DOCUMENT_BYTES == 10 * 1024 * 1024


def test_signed_url_expiry():
    assert SIGNED_URL_EXPIRY_SECONDS == 600


def test_allowed_document_types():
    assert "image/jpeg" in ALLOWED_DOCUMENT_TYPES
    assert "image/png" in ALLOWED_DOCUMENT_TYPES
    assert "image/webp" in ALLOWED_DOCUMENT_TYPES
    assert "image/gif" in ALLOWED_DOCUMENT_TYPES
    assert "application/pdf" in ALLOWED_DOCUMENT_TYPES

    print("test_allowed_document_types PASSED")


# ============================================================
# _rows()
# ============================================================


def test_rows_with_data():
    rows = [
        {"id": 1},
        {"id": 2},
    ]

    result = _rows(rows)

    assert result == rows

    print("test_rows_with_data PASSED")


def test_rows_with_none():
    result = _rows(None)

    assert result == []

    print("test_rows_with_none PASSED")


def test_rows_with_empty_list():
    result = _rows([])

    assert result == []

    print("test_rows_with_empty_list PASSED")


# ============================================================
# _db()
# ============================================================


def test_db_returns_supabase_admin(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    result = _db()

    assert result is fake

    print("test_db_returns_supabase_admin PASSED")


def test_db_missing_service_role(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        None,
    )

    with pytest.raises(Exception) as exc_info:
        _db()

    assert exc_info.value.status_code == 501

    print("test_db_missing_service_role PASSED")


# ============================================================
# _signed_url()
# ============================================================


def test_signed_url_success():
    fake = FakeSupabase(
        signed_url="https://example.com/signed/document.pdf",
    )

    result = _signed_url(
        fake,
        "student-001/document.pdf",
    )

    assert result == "https://example.com/signed/document.pdf"

    print("test_signed_url_success PASSED")


def test_signed_url_failure():
    fake = FakeSupabase(
        signed_url_error=RuntimeError("Storage unavailable"),
    )

    result = _signed_url(
        fake,
        "student-001/document.pdf",
    )

    assert result is None

    print("test_signed_url_failure PASSED")


def test_signed_url_uses_correct_expiry():
    fake = FakeSupabase(
        signed_url="https://example.com/document.pdf",
    )

    result = _signed_url(
        fake,
        "student-001/document.pdf",
    )

    assert result == "https://example.com/document.pdf"

    print("test_signed_url_uses_correct_expiry PASSED")


# ============================================================
# _document_out()
# ============================================================


def test_document_out():
    fake = FakeSupabase(
        signed_url="https://example.com/document.pdf",
    )

    row = sample_document()

    result = _document_out(
        fake,
        row,
    )

    assert result.id == 1
    assert result.document_type == "Student ID"
    assert result.file_name == "student-card.pdf"
    assert result.status == "pending"
    assert result.rejection_reason is None
    assert result.uploaded_at.isoformat() == row["uploaded_at"]
    assert result.verified_at is None
    assert result.view_url == "https://example.com/document.pdf"

    print("test_document_out PASSED")


def test_document_out_with_rejection_reason():
    fake = FakeSupabase(
        signed_url="https://example.com/rejected.pdf",
    )

    row = sample_document()
    row["status"] = "rejected"
    row["rejection_reason"] = "Document is unclear."

    result = _document_out(
        fake,
        row,
    )

    assert result.status == "rejected"
    assert result.rejection_reason == "Document is unclear."

    print("test_document_out_with_rejection_reason PASSED")


def test_document_out_verified():
    fake = FakeSupabase(
        signed_url="https://example.com/verified.pdf",
    )

    row = sample_document()
    row["status"] = "verified"
    row["verified_at"] = "2026-08-15T11:00:00+00:00"

    result = _document_out(
        fake,
        row,
    )

    assert result.status == "verified"
    assert result.verified_at is not None
    assert result.verified_at.isoformat() == row["verified_at"]

    print("test_document_out_verified PASSED")


def test_document_out_signed_url_failure():
    fake = FakeSupabase(
        signed_url_error=RuntimeError("Storage failure"),
    )

    row = sample_document()

    result = _document_out(
        fake,
        row,
    )

    assert result.view_url is None

    print("test_document_out_signed_url_failure PASSED")


# ============================================================
# Authentication
# ============================================================


def test_upload_document_without_login():
    response = client.post(
        "/documents",
        data={
            "document_type": "Student ID",
        },
        files={
            "file": (
                "student-id.pdf",
                b"PDF DATA",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 401

    print("test_upload_document_without_login PASSED")


def test_my_documents_without_login():
    response = client.get("/documents/me")

    assert response.status_code == 401

    print("test_my_documents_without_login PASSED")


# ============================================================
# Upload Document
# ============================================================


def test_upload_pdf_success(monkeypatch):
    fake = FakeSupabase(
        signed_url="https://example.com/signed/student-id.pdf",
    )

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Student ID",
        },
        files={
            "file": (
                "student-id.pdf",
                b"%PDF-test-content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] == 100
    assert data["document_type"] == "Student ID"
    assert data["file_name"] == "student-id.pdf"
    assert data["status"] == "pending"
    assert data["rejection_reason"] is None
    assert data["verified_at"] is None
    assert data["view_url"] == "https://example.com/signed/student-id.pdf"

    assert len(fake.storage.bucket.uploaded) == 1

    uploaded = fake.storage.bucket.uploaded[0]

    assert uploaded["contents"] == b"%PDF-test-content"
    assert uploaded["options"]["content-type"] == "application/pdf"
    assert uploaded["options"]["upsert"] == "true"

    assert uploaded["path"].startswith("student-001/")
    assert uploaded["path"].endswith(".pdf")

    print("test_upload_pdf_success PASSED")


def test_upload_jpeg_success(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Passport",
        },
        files={
            "file": (
                "passport.jpg",
                b"JPEG DATA",
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["document_type"] == "Passport"
    assert data["file_name"] == "passport.jpg"

    uploaded = fake.storage.bucket.uploaded[0]

    assert uploaded["options"]["content-type"] == "image/jpeg"
    assert uploaded["path"].endswith(".jpg")

    print("test_upload_jpeg_success PASSED")


def test_upload_png_success(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Student Photo",
        },
        files={
            "file": (
                "photo.png",
                b"PNG DATA",
                "image/png",
            )
        },
    )

    assert response.status_code == 201

    assert response.json()["file_name"] == "photo.png"

    uploaded = fake.storage.bucket.uploaded[0]

    assert uploaded["options"]["content-type"] == "image/png"
    assert uploaded["path"].endswith(".png")

    print("test_upload_png_success PASSED")


def test_upload_webp_success(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Supporting Document",
        },
        files={
            "file": (
                "document.webp",
                b"WEBP DATA",
                "image/webp",
            )
        },
    )

    assert response.status_code == 201

    assert response.json()["file_name"] == "document.webp"

    uploaded = fake.storage.bucket.uploaded[0]

    assert uploaded["path"].endswith(".webp")

    print("test_upload_webp_success PASSED")


def test_upload_gif_success(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Other",
        },
        files={
            "file": (
                "document.gif",
                b"GIF DATA",
                "image/gif",
            )
        },
    )

    assert response.status_code == 201

    assert response.json()["file_name"] == "document.gif"

    uploaded = fake.storage.bucket.uploaded[0]

    assert uploaded["path"].endswith(".gif")

    print("test_upload_gif_success PASSED")


# ============================================================
# Invalid File Types
# ============================================================


@pytest.mark.parametrize(
    "content_type,filename",
    [
        ("text/plain", "document.txt"),
        ("application/zip", "document.zip"),
        ("application/octet-stream", "document.bin"),
        ("text/html", "document.html"),
        ("video/mp4", "document.mp4"),
    ],
)
def test_upload_invalid_file_type(monkeypatch, content_type, filename):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Other",
        },
        files={
            "file": (
                filename,
                b"INVALID DATA",
                content_type,
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == "Document must be a JPEG, PNG, WEBP, GIF image, or PDF."

    assert fake.storage.bucket.uploaded == []

    print(f"test_upload_invalid_file_type[{content_type}] PASSED")


# ============================================================
# File Size
# ============================================================


def test_upload_document_too_large(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    oversized_content = b"x" * (MAX_DOCUMENT_BYTES + 1)

    response = client.post(
        "/documents",
        data={
            "document_type": "Student ID",
        },
        files={
            "file": (
                "large.pdf",
                oversized_content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == "Document must be under 10 MB."

    assert fake.storage.bucket.uploaded == []

    print("test_upload_document_too_large PASSED")


def test_upload_document_exactly_max_size(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    content = b"x" * MAX_DOCUMENT_BYTES

    response = client.post(
        "/documents",
        data={
            "document_type": "Student ID",
        },
        files={
            "file": (
                "maximum.pdf",
                content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    assert len(fake.storage.bucket.uploaded) == 1

    print("test_upload_document_exactly_max_size PASSED")


# ============================================================
# Required Fields
# ============================================================


def test_upload_document_missing_document_type(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        files={
            "file": (
                "document.pdf",
                b"PDF DATA",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422

    print("test_upload_document_missing_document_type PASSED")


def test_upload_document_missing_file(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Student ID",
        },
    )

    assert response.status_code == 422

    print("test_upload_document_missing_file PASSED")


# ============================================================
# Storage Errors
# ============================================================


def test_upload_document_storage_failure(monkeypatch):
    fake = FakeSupabase(
        upload_error=RuntimeError("Storage upload failed"),
    )

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Student ID",
        },
        files={
            "file": (
                "student-id.pdf",
                b"PDF DATA",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400

    assert "Could not upload document" in response.json()["detail"]
    assert "Storage upload failed" in response.json()["detail"]

    print("test_upload_document_storage_failure PASSED")


# ============================================================
# Database Errors
# ============================================================


def test_upload_document_database_insert_empty(monkeypatch):
    fake = FakeSupabase(
        insert_empty=True,
    )

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Student ID",
        },
        files={
            "file": (
                "student-id.pdf",
                b"PDF DATA",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "The document upload was rejected by the database — " "please try again."
    )

    assert len(fake.storage.bucket.uploaded) == 1

    print("test_upload_document_database_insert_empty PASSED")


# ============================================================
# Service Role Missing
# ============================================================


def test_upload_document_service_role_missing(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Student ID",
        },
        files={
            "file": (
                "student-id.pdf",
                b"PDF DATA",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 501

    assert response.json()["detail"] == "Server misconfigured: missing service role key"

    print("test_upload_document_service_role_missing PASSED")


def test_my_documents_service_role_missing(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.get("/documents/me")

    assert response.status_code == 501

    print("test_my_documents_service_role_missing PASSED")


# ============================================================
# My Documents
# ============================================================


def test_my_documents_success(monkeypatch):
    documents = [
        sample_document(),
        {
            "id": 2,
            "student_id": "student-001",
            "document_type": "Passport",
            "file_url": "student-001/passport.pdf",
            "file_name": "passport.pdf",
            "status": "verified",
            "rejection_reason": None,
            "uploaded_at": "2026-08-14T10:00:00+00:00",
            "verified_at": "2026-08-15T09:00:00+00:00",
        },
    ]

    fake = FakeSupabase(
        documents=documents,
        signed_url="https://example.com/document.pdf",
    )

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.get("/documents/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["id"] == 1
    assert data[0]["document_type"] == "Student ID"

    assert data[1]["id"] == 2
    assert data[1]["document_type"] == "Passport"
    assert data[1]["status"] == "verified"

    print("test_my_documents_success PASSED")


def test_my_documents_empty(monkeypatch):
    fake = FakeSupabase(
        documents=[],
    )

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.get("/documents/me")

    assert response.status_code == 200

    assert response.json() == []

    print("test_my_documents_empty PASSED")


def test_my_documents_only_current_student(monkeypatch):
    documents = [
        {
            "id": 1,
            "student_id": "student-001",
            "document_type": "Student ID",
            "file_url": "student-001/id.pdf",
            "file_name": "id.pdf",
            "status": "pending",
            "rejection_reason": None,
            "uploaded_at": "2026-08-15T10:00:00+00:00",
            "verified_at": None,
        },
        {
            "id": 2,
            "student_id": "other-student",
            "document_type": "Passport",
            "file_url": "other/passport.pdf",
            "file_name": "passport.pdf",
            "status": "pending",
            "rejection_reason": None,
            "uploaded_at": "2026-08-15T09:00:00+00:00",
            "verified_at": None,
        },
    ]

    fake = FakeSupabase(
        documents=documents,
    )

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.get("/documents/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == 1

    print("test_my_documents_only_current_student PASSED")


# ============================================================
# Document Status Cases
# ============================================================


@pytest.mark.parametrize(
    "status",
    [
        "pending",
        "verified",
        "rejected",
    ],
)
def test_document_status_values(monkeypatch, status):
    row = sample_document()
    row["status"] = status

    fake = FakeSupabase(
        documents=[row],
    )

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.get("/documents/me")

    assert response.status_code == 200
    assert response.json()[0]["status"] == status

    print(f"test_document_status_values[{status}] PASSED")


# ============================================================
# Filename / Extension Handling
# ============================================================


def test_upload_document_filename_without_extension(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Other",
        },
        files={
            "file": (
                "document",
                b"PDF DATA",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    uploaded = fake.storage.bucket.uploaded[0]

    assert uploaded["path"].startswith("student-001/")
    assert uploaded["path"].endswith(".bin")

    assert response.json()["file_name"] == "document"

    print("test_upload_document_filename_without_extension PASSED")


def test_upload_document_uppercase_extension(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Student ID",
        },
        files={
            "file": (
                "STUDENT-ID.PDF",
                b"PDF DATA",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    uploaded = fake.storage.bucket.uploaded[0]

    assert uploaded["path"].endswith(".pdf")

    assert response.json()["file_name"] == "STUDENT-ID.PDF"

    print("test_upload_document_uppercase_extension PASSED")


# ============================================================
# Upload Payload Verification
# ============================================================


def test_upload_document_database_payload(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Passport",
        },
        files={
            "file": (
                "passport.pdf",
                b"PDF DATA",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    payload = fake.last_query.insert_payload

    assert payload is not None
    assert payload["student_id"] == "student-001"
    assert payload["document_type"] == "Passport"
    assert payload["file_name"] == "passport.pdf"
    assert payload["status"] == "pending"

    assert payload["file_url"].startswith("student-001/")
    assert payload["file_url"].endswith(".pdf")

    print("test_upload_document_database_payload PASSED")


# ============================================================
# HTTP Method / Invalid Routes
# ============================================================


def test_documents_invalid_route():
    app.dependency_overrides[get_current_user] = override_user

    response = client.get("/documents/not-a-real-route")

    assert response.status_code == 404

    print("test_documents_invalid_route PASSED")


def test_documents_unknown_route():
    response = client.get("/documents/unknown/path")

    assert response.status_code in [401, 404, 405]

    print("test_documents_unknown_route PASSED")


# ============================================================
# Full Response Structure
# ============================================================


def test_upload_document_response_structure(monkeypatch):
    fake = FakeSupabase(
        signed_url="https://example.com/document.pdf",
    )

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.post(
        "/documents",
        data={
            "document_type": "Student ID",
        },
        files={
            "file": (
                "student-id.pdf",
                b"PDF DATA",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    data = response.json()

    expected_fields = {
        "id",
        "document_type",
        "file_name",
        "status",
        "rejection_reason",
        "uploaded_at",
        "verified_at",
        "view_url",
    }

    assert set(data.keys()) == expected_fields

    print("test_upload_document_response_structure PASSED")


def test_my_documents_response_structure(monkeypatch):
    fake = FakeSupabase(
        documents=[sample_document()],
    )

    monkeypatch.setattr(
        "agile_ci_demo.documents.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = override_user

    response = client.get("/documents/me")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 1

    expected_fields = {
        "id",
        "document_type",
        "file_name",
        "status",
        "rejection_reason",
        "uploaded_at",
        "verified_at",
        "view_url",
    }

    assert set(data[0].keys()) == expected_fields

    print("test_my_documents_response_structure PASSED")
