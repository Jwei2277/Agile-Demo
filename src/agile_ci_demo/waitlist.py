from datetime import date, datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException

from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import (
    REQUIRED_ENROLLMENT_DOCUMENT_TYPES,
    REQUIRED_IDENTITY_DOCUMENT_TYPE,
    WaitlistEntryOut,
    WaitlistJoinCreate,
)
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

Row = dict[str, Any]


def _db():
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return supabase_admin


def _rows(data: Any) -> list[Row]:
    return cast(list[Row], data or [])


def notify_next_waitlisted(room_id: int) -> None:
    """Called whenever a room frees up (booking cancelled/rejected, or a
    transfer moves someone out of it). Tries to automatically create a
    real booking for the earliest still-waiting student, using the
    occupant/date details they already supplied when they joined the
    waitlist — no manual "book now" step required.

    If the first person in line can't actually be booked any more (they
    picked up another active booking in the meantime, or the room's
    capacity/gender policy changed since they joined), that entry is
    marked 'expired' and the next person in the queue is tried, and so
    on until someone succeeds or the queue is exhausted."""
    db = _db()

    while True:
        resp = (
            db.table("room_waitlist")
            .select("*")
            .eq("room_id", room_id)
            .eq("status", "waiting")
            .order("joined_at")
            .limit(1)
            .execute()
        )
        rows = _rows(resp.data)
        if not rows:
            return

        entry = rows[0]
        if _try_auto_book(db, room_id, entry):
            return
        # _try_auto_book already marked this entry 'expired' (or left it
        # 'waiting' on a transient failure worth not burning their spot
        # over) — either way, re-query and try the next one.


def _try_auto_book(db, room_id: int, entry: Row) -> bool:
    student_id = entry["student_id"]

    def _expire_and_fail() -> bool:
        db.table("room_waitlist").update({"status": "expired"}).eq("id", entry["id"]).execute()
        return False

    # They may have picked up a different active booking while they were
    # waiting — can't have two at once.
    existing = (
        db.table("bookings")
        .select("id")
        .eq("student_id", student_id)
        .in_("status", ["pending", "approved"])
        .is_("checked_out_at", "null")
        .execute()
    )
    if _rows(existing.data):
        return _expire_and_fail()

    room_resp = db.table("rooms").select("*").eq("id", room_id).limit(1).execute()
    room_rows = _rows(room_resp.data)
    if not room_rows or not room_rows[0].get("is_active", True):
        return _expire_and_fail()
    room = room_rows[0]

    occupant_count = int(entry.get("occupant_count", 1))
    if occupant_count > int(room["capacity"]):
        return _expire_and_fail()

    if room["gender_policy"] in ("Female only", "Male only"):
        required_gender = "Female" if room["gender_policy"] == "Female only" else "Male"
        profile_resp = db.table("profiles").select("gender").eq("id", student_id).limit(1).execute()
        profile_rows = _rows(profile_resp.data)
        student_gender = profile_rows[0].get("gender") if profile_rows else None
        if student_gender != required_gender:
            return _expire_and_fail()
        if occupant_count == 2 and entry.get("extra_occupant_gender") != required_gender:
            return _expire_and_fail()

    # Race safety: confirm the room is still actually free right now
    # (the caller only just freed it, but be defensive).
    active_resp = (
        db.table("bookings")
        .select("id")
        .eq("room_id", room_id)
        .in_("status", ["pending", "approved"])
        .is_("checked_out_at", "null")
        .execute()
    )
    if _rows(active_resp.data):
        # Someone/something else already occupies it — leave this entry
        # waiting rather than burning their spot over a timing fluke.
        return False

    booking_payload = {
        "student_id": student_id,
        "room_id": room_id,
        "semester": "Semester 1, 2026/27",
        "move_in_date": entry["move_in_date"],
        "move_out_date": entry["move_out_date"],
        "status": "pending",
        "occupant_count": occupant_count,
        "extra_occupant_name": entry.get("extra_occupant_name"),
        "extra_occupant_email": entry.get("extra_occupant_email"),
        "extra_occupant_student_id": entry.get("extra_occupant_student_id"),
        "extra_occupant_gender": entry.get("extra_occupant_gender"),
    }
    insert_resp = db.table("bookings").insert(booking_payload).execute()
    if not _rows(insert_resp.data):
        # Transient DB issue — don't burn their spot, leave them waiting.
        return False

    db.table("room_waitlist").update({"status": "booked"}).eq("id", entry["id"]).execute()
    return True


def _room_label(db, room_id: int) -> str:
    resp = (
        db.table("rooms")
        .select("room_number, hostel_blocks(name)")
        .eq("id", room_id)
        .limit(1)
        .execute()
    )
    rows = _rows(resp.data)
    if not rows:
        return f"Room #{room_id}"
    room = rows[0]
    block = room.get("hostel_blocks") or {}
    return f"{block.get('name', '?')} · Room {room.get('room_number', '?')}"


def _queue_position(db, room_id: int, entry_id: int) -> int:
    """1-based position among still-waiting entries for this room."""
    resp = (
        db.table("room_waitlist")
        .select("id, joined_at")
        .eq("room_id", room_id)
        .eq("status", "waiting")
        .order("joined_at")
        .execute()
    )
    waiting = _rows(resp.data)
    for i, entry in enumerate(waiting, start=1):
        if int(entry["id"]) == entry_id:
            return i
    return len(waiting) + 1


def _entry_out(db, row: Row) -> WaitlistEntryOut:
    room_id = int(row["room_id"])
    return WaitlistEntryOut(
        id=int(row["id"]),
        room_id=room_id,
        room_label=_room_label(db, room_id),
        status=str(row["status"]),
        queue_position=_queue_position(db, room_id, int(row["id"])),
        occupant_count=int(row.get("occupant_count", 1)),
        move_in_date=row["move_in_date"],
        move_out_date=row["move_out_date"],
        joined_at=row["joined_at"],
        notified_at=row.get("notified_at"),
    )


@router.post("/{room_id}", status_code=201, response_model=WaitlistEntryOut)
def join_waitlist(
    room_id: int, data: WaitlistJoinCreate, user: CurrentUser = Depends(get_current_user)
):
    db = _db()

    documents_resp = (
        db.table("student_documents").select("document_type").eq("student_id", user.id).execute()
    )
    uploaded_types = {str(d["document_type"]) for d in _rows(documents_resp.data)}
    has_identity_doc = REQUIRED_IDENTITY_DOCUMENT_TYPE in uploaded_types
    has_enrollment_doc = any(t in uploaded_types for t in REQUIRED_ENROLLMENT_DOCUMENT_TYPES)

    if not (has_identity_doc and has_enrollment_doc):
        missing = []
        if not has_identity_doc:
            missing.append(REQUIRED_IDENTITY_DOCUMENT_TYPE)
        if not has_enrollment_doc:
            missing.append(" or ".join(REQUIRED_ENROLLMENT_DOCUMENT_TYPES))
        raise HTTPException(
            status_code=409,
            detail=(
                "Please upload the following before joining the waitlist, so we can "
                f"verify your identity: {', '.join(missing)}. You can upload these on "
                "the Documents page."
            ),
        )

    room_resp = (
        db.table("rooms").select("*, hostel_blocks(name)").eq("id", room_id).limit(1).execute()
    )
    room_rows = _rows(room_resp.data)
    if not room_rows:
        raise HTTPException(status_code=404, detail="Room not found")
    room = room_rows[0]

    if int(data.occupant_count) > int(room["capacity"]):
        raise HTTPException(
            status_code=400,
            detail=f"{room['room_type']} only accommodates up to {room['capacity']} occupant(s).",
        )

    if room["gender_policy"] in ("Female only", "Male only"):
        required_gender = "Female" if room["gender_policy"] == "Female only" else "Male"
        if user.gender != required_gender:
            raise HTTPException(
                status_code=403,
                detail=f"This room is restricted to {required_gender.lower()} students.",
            )
        if data.occupant_count == 2 and data.extra_occupant_gender != required_gender:
            raise HTTPException(
                status_code=403,
                detail=f"This room is restricted to {required_gender.lower()} occupants — the 2nd occupant doesn't match.",
            )

    active_booking_resp = (
        db.table("bookings")
        .select("id, move_out_date")
        .eq("room_id", room_id)
        .in_("status", ["pending", "approved"])
        .is_("checked_out_at", "null")
        .order("requested_at", desc=True)
        .limit(1)
        .execute()
    )
    active_bookings = _rows(active_booking_resp.data)

    if not active_bookings:
        raise HTTPException(
            status_code=409,
            detail="This room is available right now — book it directly instead of joining the waitlist.",
        )

    current_move_out = active_bookings[0].get("move_out_date")
    if current_move_out:
        current_move_out_date = (
            current_move_out
            if isinstance(current_move_out, date)
            else date.fromisoformat(str(current_move_out))
        )
        if data.move_in_date < current_move_out_date:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"This room isn't free until {current_move_out_date.isoformat()} — "
                    "choose a move-in date on or after that."
                ),
            )

    existing = (
        db.table("room_waitlist")
        .select("id, status")
        .eq("room_id", room_id)
        .eq("student_id", user.id)
        .limit(1)
        .execute()
    )
    existing_rows = _rows(existing.data)
    if existing_rows and existing_rows[0]["status"] == "waiting":
        raise HTTPException(status_code=409, detail="You're already on the waitlist for this room.")

    payload = {
        "status": "waiting",
        "joined_at": datetime.now(timezone.utc).isoformat(),
        "notified_at": None,
        "occupant_count": data.occupant_count,
        "extra_occupant_name": data.extra_occupant_name,
        "extra_occupant_email": data.extra_occupant_email,
        "extra_occupant_student_id": data.extra_occupant_student_id,
        "extra_occupant_gender": data.extra_occupant_gender,
        "move_in_date": data.move_in_date.isoformat(),
        "move_out_date": data.move_out_date.isoformat(),
    }

    if existing_rows:
        # Re-join after a previous cancelled/expired/notified entry.
        db.table("room_waitlist").update(payload).eq("id", existing_rows[0]["id"]).execute()
        entry_id = int(existing_rows[0]["id"])
    else:
        insert_resp = (
            db.table("room_waitlist")
            .insert({**payload, "room_id": room_id, "student_id": user.id})
            .execute()
        )
        insert_rows = _rows(insert_resp.data)
        if not insert_rows:
            raise HTTPException(
                status_code=400, detail="Could not join the waitlist — please try again."
            )
        entry_id = int(insert_rows[0]["id"])

    row_resp = db.table("room_waitlist").select("*").eq("id", entry_id).limit(1).execute()
    return _entry_out(db, _rows(row_resp.data)[0])


@router.get("/me", response_model=list[WaitlistEntryOut])
def my_waitlist(user: CurrentUser = Depends(get_current_user)):
    db = _db()
    resp = (
        db.table("room_waitlist")
        .select("*")
        .eq("student_id", user.id)
        .in_("status", ["waiting", "notified"])
        .order("joined_at")
        .execute()
    )
    return [_entry_out(db, row) for row in _rows(resp.data)]


@router.delete("/{entry_id}", status_code=204)
def leave_waitlist(entry_id: int, user: CurrentUser = Depends(get_current_user)):
    db = _db()
    resp = db.table("room_waitlist").select("*").eq("id", entry_id).limit(1).execute()
    rows = _rows(resp.data)
    if not rows:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    if rows[0]["student_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not your waitlist entry")

    db.table("room_waitlist").update({"status": "cancelled"}).eq("id", entry_id).execute()
