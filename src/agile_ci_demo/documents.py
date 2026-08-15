import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import DocumentOut
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(prefix="/documents", tags=["documents"])

Row = dict[str, Any]

DOCUMENT_BUCKET = "student-documents"
ALLOWED_DOCUMENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10 MB
SIGNED_URL_EXPIRY_SECONDS = 60 * 10  # 10 minutes


def _db():
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return supabase_admin


def _rows(data: Any) -> list[Row]:
    return cast(list[Row], data or [])


def _signed_url(db, storage_path: str) -> str | None:
    try:
        resp = db.storage.from_(DOCUMENT_BUCKET).create_signed_url(
            storage_path, SIGNED_URL_EXPIRY_SECONDS
        )
        return resp.get("signedUrl") or resp.get("signedURL")
    except Exception:
        return None


def _document_out(db, row: Row) -> DocumentOut:
    return DocumentOut(
        id=int(row["id"]),
        document_type=str(row["document_type"]),
        file_name=str(row["file_name"]),
        status=str(row["status"]),
        rejection_reason=row.get("rejection_reason"),
        uploaded_at=row["uploaded_at"],
        verified_at=row.get("verified_at"),
        view_url=_signed_url(db, row["file_url"]),
    )


@router.post("", status_code=201, response_model=DocumentOut)
def upload_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    db = _db()

    if file.content_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Document must be a JPEG, PNG, WEBP, GIF image, or PDF.",
        )

    contents = file.file.read()
    if len(contents) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=400, detail="Document must be under 10 MB.")

    original_name = file.filename or "document"
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "bin"
    storage_path = f"{user.id}/{uuid.uuid4().hex}.{extension}"

    try:
        db.storage.from_(DOCUMENT_BUCKET).upload(
            storage_path, contents, {"content-type": file.content_type, "upsert": "true"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not upload document: {e}") from e

    insert_resp = (
        db.table("student_documents")
        .insert(
            {
                "student_id": user.id,
                "document_type": document_type,
                "file_url": storage_path,
                "file_name": original_name,
                "status": "pending",
            }
        )
        .execute()
    )
    rows = _rows(insert_resp.data)
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="The document upload was rejected by the database — please try again.",
        )

    return _document_out(db, rows[0])


@router.get("/me", response_model=list[DocumentOut])
def my_documents(user: CurrentUser = Depends(get_current_user)):
    db = _db()
    resp = (
        db.table("student_documents")
        .select("*")
        .eq("student_id", user.id)
        .order("uploaded_at", desc=True)
        .execute()
    )
    return [_document_out(db, row) for row in _rows(resp.data)]
