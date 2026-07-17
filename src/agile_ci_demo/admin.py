from datetime import datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query

from agile_ci_demo.deps import CurrentUser, require_admin
from agile_ci_demo.models import (
    BlockOut,
    BookingAdminOut,
    DashboardStats,
    MaintenanceOut,
    RoomAdminOut,
    RoomCreate,
    RoomUpdate,
    TransferRequestAdminOut,
    total_fee_for,
)
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(prefix="/admin", tags=["admin"])

Row = dict[str, Any]


def _db():
    """Return the admin Supabase client, raising 501 if not configured."""
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return supabase_admin


def _rows(data: Any) -> list[Row]:
    """Safely cast Supabase response data to a list of dicts."""
    return [cast(Row, r) for r in (data or [])]


# ---------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------
@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(_: CurrentUser = Depends(require_admin)):
    db = _db()

    rooms_resp = db.table("rooms").select("id").eq("is_active", True).execute()
    rooms = _rows(rooms_resp.data)
    total_rooms = len(rooms)

    active_bookings_resp = (
        db.table("bookings")
        .select("room_id, status")
        .in_("status", ["pending", "approved"])
        .execute()
    )
    active_bookings = _rows(active_bookings_resp.data)

    occupied_room_ids = {b["room_id"] for b in active_bookings}
    occupied = len(occupied_room_ids)

    pending_bookings = sum(1 for b in active_bookings if b["status"] == "pending")

    pending_maint_resp = (
        db.table("maintenance_requests").select("id").eq("status", "pending").execute()
    )
    pending_maintenance = len(_rows(pending_maint_resp.data))

    available_rooms = total_rooms - occupied
    occupancy_pct = round((occupied / total_rooms) * 100, 1) if total_rooms else 0.0

    return DashboardStats(
        available_rooms=available_rooms,
        occupied_rooms=occupied,
        total_rooms=total_rooms,
        pending_bookings=pending_bookings,
        pending_maintenance=pending_maintenance,
        occupancy_pct=occupancy_pct,
    )


# ---------------------------------------------------------------
# Bookings queue
# ---------------------------------------------------------------
def _list_bookings(status: str | None) -> list[BookingAdminOut]:
    db = _db()
    query = db.table("bookings").select(
        "*, student:profiles!bookings_student_id_fkey(full_name, student_id), "
        "rooms!bookings_room_id_fkey(room_number, fee_monthly, hostel_blocks(name))"
    )
    if status and status != "all":
        query = query.eq("status", status)
    resp = query.order("requested_at", desc=True).execute()

    out = []
    for row in _rows(resp.data):
        profile: Row = row.get("student") or {}
        room: Row = row.get("rooms") or {}
        block: Row = room.get("hostel_blocks") or {}
        occupant_count: int = int(row.get("occupant_count", 1))
        base_fee = float(room.get("fee_monthly", 0))
        out.append(
            BookingAdminOut(
                id=int(row["id"]),
                status=str(row["status"]),
                semester=str(row["semester"]),
                requested_at=row["requested_at"],
                student_name=str(profile.get("full_name", "Unknown")),
                student_id=profile.get("student_id"),
                room_id=int(row["room_id"]),
                room_label=f"{block.get('name', '?')} · {room.get('room_number', '?')}",
                occupant_count=occupant_count,
                extra_occupant_name=row.get("extra_occupant_name"),
                extra_occupant_email=row.get("extra_occupant_email"),
                extra_occupant_student_id=row.get("extra_occupant_student_id"),
                extra_occupant_gender=row.get("extra_occupant_gender"),
                total_fee=total_fee_for(base_fee, occupant_count),
            )
        )
    return out


@router.get("/bookings", response_model=list[BookingAdminOut])
def list_bookings(
    status: str = Query(
        default="all", description="'all' | 'pending' | 'approved' | 'rejected' | 'cancelled'"
    ),
    _: CurrentUser = Depends(require_admin),
):
    _db()
    return _list_bookings(status)


@router.get("/bookings/pending", response_model=list[BookingAdminOut])
def pending_bookings(_: CurrentUser = Depends(require_admin)):
    _db()
    return _list_bookings("pending")


def _list_transfer_requests(status: str | None) -> list[TransferRequestAdminOut]:
    db = _db()
    try:
        query = db.table("room_transfer_requests").select(
            "*, student:profiles!room_transfer_requests_student_id_fkey(full_name), "
            "booking:bookings!room_transfer_requests_booking_id_fkey("
            "id, room_id, semester, status, rooms!bookings_room_id_fkey(room_number, hostel_blocks(name))"
            "), "
            "requested_room:rooms!room_transfer_requests_requested_room_id_fkey(room_number, hostel_blocks(name))"
        )
        if status and status != "all":
            query = query.eq("status", status)
        resp = query.order("requested_at", desc=True).execute()
        rows = _rows(resp.data)
    except Exception:
        rows = []

    out = []
    for row in rows:
        try:
            student: Row = row.get("student") or {}
            booking: Row = row.get("booking") or {}
            current_room: Row = booking.get("rooms") or {}
            current_block: Row = current_room.get("hostel_blocks") or {}
            requested_room: Row = row.get("requested_room") or {}
            requested_block: Row = requested_room.get("hostel_blocks") or {}
            current_room_label = (
                f"{current_block.get('name', '?')} · Room {current_room.get('room_number', '?')}"
                if current_room
                else f"Room #{booking.get('room_id', '?')}"
            )
            out.append(
                TransferRequestAdminOut(
                    id=int(row["id"]),
                    booking_id=int(row["booking_id"]),
                    student_name=str(student.get("full_name", "Unknown")),
                    room_label=current_room_label,
                    requested_room_id=int(row["requested_room_id"]),
                    requested_room_label=f"{requested_block.get('name', '?')} · Room {requested_room.get('room_number', '?')}",
                    reason=str(row.get("reason", "")),
                    status=str(row.get("status", "pending")),
                    requested_at=row["requested_at"],
                )
            )
        except Exception:
            continue
    return out


@router.get("/transfer-requests", response_model=list[TransferRequestAdminOut])
def list_transfer_requests(
    status: str = Query(default="all", description="'all' | 'pending' | 'approved' | 'rejected'"),
    _: CurrentUser = Depends(require_admin),
):
    _db()
    return _list_transfer_requests(status)


def _decide_booking(booking_id: int, new_status: str, admin: CurrentUser) -> None:
    db = _db()
    resp = db.table("bookings").select("*").eq("id", booking_id).limit(1).execute()
    rows = _rows(resp.data)
    if not rows:
        raise HTTPException(status_code=404, detail="Booking not found")
    if rows[0]["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"This booking is already '{rows[0]['status']}' — it can't be decided again.",
        )

    db.table("bookings").update(
        {
            "status": new_status,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "decided_by": admin.id,
        }
    ).eq("id", booking_id).execute()


def _decide_transfer_request(transfer_request_id: int, new_status: str, admin: CurrentUser) -> None:
    db = _db()
    resp = (
        db.table("room_transfer_requests")
        .select("*")
        .eq("id", transfer_request_id)
        .limit(1)
        .execute()
    )
    rows = _rows(resp.data)
    if not rows:
        raise HTTPException(status_code=404, detail="Transfer request not found")
    if rows[0]["status"] != "pending":
        raise HTTPException(status_code=409, detail="Transfer request already decided")

    transfer_request = rows[0]
    booking_id: int = int(transfer_request["booking_id"])
    requested_room_id: int = int(transfer_request["requested_room_id"])

    booking_resp = db.table("bookings").select("*").eq("id", booking_id).limit(1).execute()
    if not _rows(booking_resp.data):
        raise HTTPException(status_code=404, detail="Booking not found")

    # Approving actually moves the booking to the new room. Rejecting
    # leaves the booking exactly as it was — the student stays in their
    # current room. Either way, clear pending_transfer_room_id since the
    # request is no longer pending.
    booking_updates: dict[str, Any] = {"pending_transfer_room_id": None}
    if new_status == "approved":
        booking_updates["room_id"] = requested_room_id

    db.table("bookings").update(booking_updates).eq("id", booking_id).execute()
    db.table("room_transfer_requests").update({"status": new_status}).eq(
        "id", transfer_request_id
    ).execute()


@router.post("/bookings/{booking_id}/approve", status_code=204)
def approve_booking(booking_id: int, admin: CurrentUser = Depends(require_admin)):
    _decide_booking(booking_id, "approved", admin)


@router.post("/bookings/{booking_id}/reject", status_code=204)
def reject_booking(booking_id: int, admin: CurrentUser = Depends(require_admin)):
    _decide_booking(booking_id, "rejected", admin)


@router.post("/transfer-requests/{transfer_request_id}/approve", status_code=204)
def approve_transfer_request(transfer_request_id: int, admin: CurrentUser = Depends(require_admin)):
    _decide_transfer_request(transfer_request_id, "approved", admin)


@router.post("/transfer-requests/{transfer_request_id}/reject", status_code=204)
def reject_transfer_request(transfer_request_id: int, admin: CurrentUser = Depends(require_admin)):
    _decide_transfer_request(transfer_request_id, "rejected", admin)


# ---------------------------------------------------------------
# Maintenance queue
# ---------------------------------------------------------------
def _list_maintenance(status: str | None) -> list[MaintenanceOut]:
    db = _db()
    query = db.table("maintenance_requests").select("*, profiles(full_name)")
    if status and status != "all":
        query = query.eq("status", status)
    resp = query.order("created_at", desc=True).execute()

    out = []
    for row in _rows(resp.data):
        profile: Row = row.get("profiles") or {}
        out.append(
            MaintenanceOut(
                id=int(row["id"]),
                title=str(row["title"]),
                category=str(row["category"]),
                priority=str(row["priority"]),
                status=str(row["status"]),
                created_at=row["created_at"],
                student_name=profile.get("full_name"),
            )
        )
    return out


@router.get("/maintenance", response_model=list[MaintenanceOut])
def list_maintenance(
    status: str = Query(
        default="all", description="'all' | 'pending' | 'assigned' | 'completed' | 'cancelled'"
    ),
    _: CurrentUser = Depends(require_admin),
):
    _db()
    return _list_maintenance(status)


@router.get("/maintenance/pending", response_model=list[MaintenanceOut])
def pending_maintenance(_: CurrentUser = Depends(require_admin)):
    _db()
    return _list_maintenance("pending")


@router.post("/maintenance/{request_id}/complete", status_code=204)
def complete_maintenance(request_id: int, _: CurrentUser = Depends(require_admin)):
    db = _db()

    resp = db.table("maintenance_requests").select("id").eq("id", request_id).limit(1).execute()
    if not _rows(resp.data):
        raise HTTPException(status_code=404, detail="Request not found")

    db.table("maintenance_requests").update(
        {"status": "completed", "resolved_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", request_id).execute()


# ---------------------------------------------------------------
# Rooms management
# ---------------------------------------------------------------
@router.get("/blocks", response_model=list[BlockOut])
def list_blocks(_: CurrentUser = Depends(require_admin)):
    db = _db()
    resp = db.table("hostel_blocks").select("id, name").order("name").execute()
    return [BlockOut(id=int(b["id"]), name=str(b["name"])) for b in _rows(resp.data)]


def _room_admin_out(row: Row, booked_room_ids: set[int]) -> RoomAdminOut:
    block: Row = row.get("hostel_blocks") or {}
    return RoomAdminOut(
        id=row["id"],
        block_id=row["block_id"],
        block_name=block.get("name", "Unknown block"),
        level=row["level"],
        room_number=row["room_number"],
        room_type=row["room_type"],
        capacity=row["capacity"],
        is_booked=row["id"] in booked_room_ids,
        gender_policy=row["gender_policy"],
        fee_monthly=float(row["fee_monthly"]),
        photo_url=row.get("photo_url"),
        is_active=row["is_active"],
    )


def _booked_room_ids() -> set[int]:
    db = _db()
    bookings_resp = (
        db.table("bookings").select("room_id").in_("status", ["pending", "approved"]).execute()
    )
    return {int(b["room_id"]) for b in _rows(bookings_resp.data)}


@router.get("/rooms", response_model=list[RoomAdminOut])
def list_rooms_admin(_: CurrentUser = Depends(require_admin)):
    db = _db()
    rooms_resp = db.table("rooms").select("*, hostel_blocks(name)").order("block_id").execute()
    booked_room_ids = _booked_room_ids()
    return [_room_admin_out(r, booked_room_ids) for r in _rows(rooms_resp.data)]


@router.post("/rooms", status_code=201, response_model=RoomAdminOut)
def create_room(data: RoomCreate, _: CurrentUser = Depends(require_admin)):
    db = _db()
    insert_resp = db.table("rooms").insert(data.model_dump()).execute()
    insert_rows = _rows(insert_resp.data)
    if not insert_rows:
        raise HTTPException(
            status_code=400,
            detail="The room was rejected by the database — check the block ID exists and the room number isn't already used in that block.",
        )

    room_resp = (
        db.table("rooms")
        .select("*, hostel_blocks(name)")
        .eq("id", int(insert_rows[0]["id"]))
        .limit(1)
        .execute()
    )
    return _room_admin_out(_rows(room_resp.data)[0], set())


@router.patch("/rooms/{room_id}", response_model=RoomAdminOut)
def update_room(room_id: int, data: RoomUpdate, _: CurrentUser = Depends(require_admin)):
    db = _db()
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    existing = db.table("rooms").select("id").eq("id", room_id).limit(1).execute()
    if not _rows(existing.data):
        raise HTTPException(status_code=404, detail="Room not found")

    db.table("rooms").update(updates).eq("id", room_id).execute()

    room_resp = (
        db.table("rooms").select("*, hostel_blocks(name)").eq("id", room_id).limit(1).execute()
    )
    return _room_admin_out(_rows(room_resp.data)[0], _booked_room_ids())
