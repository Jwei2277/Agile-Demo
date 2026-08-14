import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import MaintenanceOut
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

Row = dict[str, Any]

PHOTO_BUCKET = "maintenance-photos"
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB


def _db():
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return supabase_admin


def _rows(data: Any) -> list[Row]:
    return cast(list[Row], data or [])


def _room_label(db, room_id: int | None) -> str | None:
    if room_id is None:
        return None
    resp = (
        db.table("rooms")
        .select("room_number, hostel_blocks(name)")
        .eq("id", room_id)
        .limit(1)
        .execute()
    )
    rows = _rows(resp.data)
    if not rows:
        return None
    room = rows[0]
    block = room.get("hostel_blocks") or {}
    return f"{block.get('name', '?')} · Room {room.get('room_number', '?')}"


def _maintenance_out(
    db, row: Row, student_name: str | None = None, student_id: str | None = None
) -> MaintenanceOut:
    return MaintenanceOut(
        id=int(row["id"]),
        title=str(row["title"]),
        category=str(row["category"]),
        priority=str(row["priority"]),
        status=str(row["status"]),
        photo_url=row.get("photo_url"),
        assigned_staff=row.get("assigned_staff"),
        remarks=row.get("remarks"),
        room_label=_room_label(db, row.get("room_id")),
        student_name=student_name,
        student_id=student_id,
        created_at=row["created_at"],
        completed_at=row.get("resolved_at"),
    )


def _upload_photo(db, user_id: str, photo: UploadFile) -> str:
    if photo.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Photo must be a JPEG, PNG, WEBP, or GIF image.",
        )

    contents = photo.file.read()
    if len(contents) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="Photo must be under 5 MB.")

    extension = (
        (photo.filename or "").rsplit(".", 1)[-1].lower()
        if "." in (photo.filename or "")
        else "jpg"
    )
    path = f"{user_id}/{uuid.uuid4().hex}.{extension}"

    try:
        db.storage.from_(PHOTO_BUCKET).upload(
            path, contents, {"content-type": photo.content_type, "upsert": "true"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not upload photo: {e}") from e

    return db.storage.from_(PHOTO_BUCKET).get_public_url(path)


@router.post("", status_code=201, response_model=MaintenanceOut)
def create_request(
    title: str = Form(..., min_length=1),
    category: str = Form("General"),
    priority: str = Form("Normal"),
    room_id: int | None = Form(None),
    photo: UploadFile | None = File(None),
    user: CurrentUser = Depends(get_current_user),
):
    db = _db()

    photo_url = None
    if photo is not None and photo.filename:
        photo_url = _upload_photo(db, user.id, photo)

    insert_resp = (
        db.table("maintenance_requests")
        .insert(
            {
                "student_id": user.id,
                "room_id": room_id,
                "title": title,
                "category": category,
                "priority": priority,
                "status": "pending",
                "photo_url": photo_url,
            }
        )
        .execute()
    )
    rows = _rows(insert_resp.data)
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="The maintenance request was rejected by the database — please try again.",
        )

    return _maintenance_out(db, rows[0], student_name=user.full_name, student_id=user.student_id)


@router.get("/me", response_model=list[MaintenanceOut])
def my_requests(user: CurrentUser = Depends(get_current_user)):
    db = _db()
    resp = (
        db.table("maintenance_requests")
        .select("*")
        .eq("student_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    return [
        _maintenance_out(db, row, student_name=user.full_name, student_id=user.student_id)
        for row in _rows(resp.data)
    ]
