from datetime import datetime, timezone

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


# ---------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------
@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(_: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    rooms_resp = supabase_admin.table("rooms").select("id").eq("is_active", True).execute()
    rooms = rooms_resp.data or []
    total_rooms = len(rooms)

    active_bookings_resp = (
        supabase_admin.table("bookings")
        .select("room_id, status")
        .in_("status", ["pending", "approved"])
        .execute()
    )
    active_bookings = active_bookings_resp.data or []

    # Rooms are rented as a whole unit now, so "occupied" = number of
    # distinct rooms with an active booking, not the number of bookings
    # (those are the same in practice since a room only ever has one
    # active booking at a time, but count distinct rooms to be safe).
    occupied_room_ids = {b["room_id"] for b in active_bookings}
    occupied = len(occupied_room_ids)

    pending_bookings = sum(1 for b in active_bookings if b["status"] == "pending")

    pending_maint_resp = (
        supabase_admin.table("maintenance_requests").select("id").eq("status", "pending").execute()
    )
    pending_maintenance = len(pending_maint_resp.data or [])

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
    query = supabase_admin.table("bookings").select(
        "*, student:profiles!bookings_student_id_fkey(full_name, student_id), "
        "rooms(room_number, fee_monthly, hostel_blocks(name))"
    )
    if status and status != "all":
        query = query.eq("status", status)
    resp = query.order("requested_at", desc=True).execute()

    out = []
    for row in resp.data or []:
        profile = row.get("student") or {}
        room = row.get("rooms") or {}
        block = room.get("hostel_blocks") or {}
        occupant_count = row.get("occupant_count", 1)
        base_fee = float(room.get("fee_monthly", 0))
        out.append(
            BookingAdminOut(
                id=row["id"],
                status=row["status"],
                semester=row["semester"],
                requested_at=row["requested_at"],
                student_name=profile.get("full_name", "Unknown"),
                student_id=profile.get("student_id"),
                room_id=row["room_id"],
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
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return _list_bookings(status)


@router.get("/bookings/pending", response_model=list[BookingAdminOut])
def pending_bookings(_: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return _list_bookings("pending")


def _list_transfer_requests(status: str | None) -> list[TransferRequestAdminOut]:
    try:
        query = supabase_admin.table("room_transfer_requests").select(
            "*, student:profiles!room_transfer_requests_student_id_fkey(full_name), "
            "booking:bookings!room_transfer_requests_booking_id_fkey(id, room_id, semester, status), "
            "requested_room:rooms!room_transfer_requests_requested_room_id_fkey(room_number, hostel_blocks(name))"
        )
        if status and status != "all":
            query = query.eq("status", status)
        resp = query.order("requested_at", desc=True).execute()
        rows = resp.data or []
    except Exception:
        rows = []

    out = []
    for row in rows:
        try:
            student = row.get("student") or {}
            booking = row.get("booking") or {}
            requested_room = row.get("requested_room") or {}
            requested_block = requested_room.get("hostel_blocks") or {}
            out.append(
                TransferRequestAdminOut(
                    id=row["id"],
                    booking_id=row["booking_id"],
                    student_name=student.get("full_name", "Unknown"),
                    room_label=f"Current room {booking.get('room_id', '?')}",
                    requested_room_id=row["requested_room_id"],
                    requested_room_label=f"{requested_block.get('name', '?')} · Room {requested_room.get('room_number', '?')}",
                    reason=row.get("reason", ""),
                    status=row.get("status", "pending"),
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
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return _list_transfer_requests(status)


def _decide_booking(booking_id: int, new_status: str, admin: CurrentUser) -> None:
    resp = supabase_admin.table("bookings").select("*").eq("id", booking_id).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Booking not found")
    if resp.data[0]["status"] != "pending":
        raise HTTPException(status_code=409, detail="Booking already decided")

    supabase_admin.table("bookings").update(
        {
            "status": new_status,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "decided_by": admin.id,
        }
    ).eq("id", booking_id).execute()


def _decide_transfer_request(transfer_request_id: int, new_status: str, admin: CurrentUser) -> None:
    resp = (
        supabase_admin.table("room_transfer_requests")
        .select("*")
        .eq("id", transfer_request_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Transfer request not found")
    if resp.data[0]["status"] != "pending":
        raise HTTPException(status_code=409, detail="Transfer request already decided")

    transfer_request = resp.data[0]
    booking_id = transfer_request["booking_id"]
    requested_room_id = transfer_request["requested_room_id"]

    booking_resp = (
        supabase_admin.table("bookings").select("*").eq("id", booking_id).limit(1).execute()
    )
    if not booking_resp.data:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking_updates = {"status": "approved"}
    if new_status == "approved":
        booking_updates["room_id"] = requested_room_id

    try:
        supabase_admin.table("bookings").update(booking_updates).eq("id", booking_id).execute()
    except Exception:
        fallback_updates = {k: v for k, v in booking_updates.items() if k != "room_id"}
        supabase_admin.table("bookings").update(fallback_updates).eq("id", booking_id).execute()
    supabase_admin.table("room_transfer_requests").update({"status": new_status}).eq(
        "id", transfer_request_id
    ).execute()


@router.post("/bookings/{booking_id}/approve", status_code=204)
def approve_booking(booking_id: int, admin: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    _decide_booking(booking_id, "approved", admin)


@router.post("/bookings/{booking_id}/reject", status_code=204)
def reject_booking(booking_id: int, admin: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    _decide_booking(booking_id, "rejected", admin)


@router.post("/transfer-requests/{transfer_request_id}/approve", status_code=204)
def approve_transfer_request(transfer_request_id: int, admin: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    _decide_transfer_request(transfer_request_id, "approved", admin)


@router.post("/transfer-requests/{transfer_request_id}/reject", status_code=204)
def reject_transfer_request(transfer_request_id: int, admin: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    _decide_transfer_request(transfer_request_id, "rejected", admin)


# ---------------------------------------------------------------
# Maintenance queue
# ---------------------------------------------------------------
def _list_maintenance(status: str | None) -> list[MaintenanceOut]:
    query = supabase_admin.table("maintenance_requests").select("*, profiles(full_name)")
    if status and status != "all":
        query = query.eq("status", status)
    resp = query.order("created_at", desc=True).execute()

    out = []
    for row in resp.data or []:
        profile = row.get("profiles") or {}
        out.append(
            MaintenanceOut(
                id=row["id"],
                title=row["title"],
                category=row["category"],
                priority=row["priority"],
                status=row["status"],
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
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return _list_maintenance(status)


@router.get("/maintenance/pending", response_model=list[MaintenanceOut])
def pending_maintenance(_: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return _list_maintenance("pending")


@router.post("/maintenance/{request_id}/complete", status_code=204)
def complete_maintenance(request_id: int, _: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    resp = (
        supabase_admin.table("maintenance_requests")
        .select("id")
        .eq("id", request_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Request not found")

    supabase_admin.table("maintenance_requests").update(
        {"status": "completed", "resolved_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", request_id).execute()


# ---------------------------------------------------------------
# Rooms management
# ---------------------------------------------------------------
@router.get("/blocks", response_model=list[BlockOut])
def list_blocks(_: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    resp = supabase_admin.table("hostel_blocks").select("id, name").order("name").execute()
    return [BlockOut(id=b["id"], name=b["name"]) for b in (resp.data or [])]


def _room_admin_out(row: dict, booked_room_ids: set[int]) -> RoomAdminOut:
    block = row.get("hostel_blocks") or {}
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
    bookings_resp = (
        supabase_admin.table("bookings")
        .select("room_id")
        .in_("status", ["pending", "approved"])
        .execute()
    )
    return {b["room_id"] for b in (bookings_resp.data or [])}


@router.get("/rooms", response_model=list[RoomAdminOut])
def list_rooms_admin(_: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    rooms_resp = (
        supabase_admin.table("rooms").select("*, hostel_blocks(name)").order("block_id").execute()
    )
    rooms = rooms_resp.data or []

    booked_room_ids = _booked_room_ids()

    return [_room_admin_out(r, booked_room_ids) for r in rooms]


@router.post("/rooms", status_code=201, response_model=RoomAdminOut)
def create_room(data: RoomCreate, _: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    insert_resp = supabase_admin.table("rooms").insert(data.model_dump()).execute()
    if not insert_resp.data:
        raise HTTPException(status_code=400, detail="Could not create room")

    room_resp = (
        supabase_admin.table("rooms")
        .select("*, hostel_blocks(name)")
        .eq("id", insert_resp.data[0]["id"])
        .limit(1)
        .execute()
    )
    return _room_admin_out(room_resp.data[0], set())


@router.patch("/rooms/{room_id}", response_model=RoomAdminOut)
def update_room(room_id: int, data: RoomUpdate, _: CurrentUser = Depends(require_admin)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    existing = supabase_admin.table("rooms").select("id").eq("id", room_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Room not found")

    supabase_admin.table("rooms").update(updates).eq("id", room_id).execute()

    room_resp = (
        supabase_admin.table("rooms")
        .select("*, hostel_blocks(name)")
        .eq("id", room_id)
        .limit(1)
        .execute()
    )

    return _room_admin_out(room_resp.data[0], _booked_room_ids())
