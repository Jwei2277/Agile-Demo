from fastapi import APIRouter, HTTPException, Query

from agile_ci_demo.models import RoomOut
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(prefix="/rooms", tags=["rooms"])


def _room_to_out(row: dict, booked_room_ids: set[int]) -> RoomOut:
    # Rooms are rented as a whole unit now (condo-style): one active
    # booking (pending/approved) occupies the entire room regardless of
    # how many people it's for. "capacity" is just the max occupants
    # that one booking may include (1 for Single Room, up to 2 otherwise).
    block = row.get("hostel_blocks") or {}
    return RoomOut(
        id=row["id"],
        block_name=block.get("name", "Unknown block"),
        level=row["level"],
        room_number=row["room_number"],
        room_type=row["room_type"],
        capacity=row["capacity"],
        is_available=row["id"] not in booked_room_ids,
        gender_policy=row["gender_policy"],
        fee_monthly=float(row["fee_monthly"]),
        photo_url=row.get("photo_url"),
    )


def _booked_room_ids() -> set[int]:
    bookings_resp = (
        supabase_admin.table("bookings")
        .select("room_id")
        .in_("status", ["pending", "approved"])
        .execute()
    )
    return {b["room_id"] for b in (bookings_resp.data or [])}


@router.get("", response_model=list[RoomOut])
def list_rooms(
    gender: str | None = Query(
        default=None, description="'Female only' | 'Male only' | 'Mixed block'"
    ),
    room_type: str | None = Query(
        default=None, description="'Single Room' | 'Master Room' | 'Balcony Room' | 'Middle Room'"
    ),
    block: str | None = Query(default=None, description="Block name, e.g. 'Block A'"),
    only_available: bool = Query(default=False),
):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    query = supabase_admin.table("rooms").select("*, hostel_blocks(name)").eq("is_active", True)

    if gender:
        query = query.eq("gender_policy", gender)
    if room_type:
        query = query.eq("room_type", room_type)

    rooms_resp = query.execute()
    rooms = rooms_resp.data or []

    if block:
        rooms = [r for r in rooms if (r.get("hostel_blocks") or {}).get("name") == block]

    booked_room_ids = _booked_room_ids()

    out = [_room_to_out(r, booked_room_ids) for r in rooms]

    if only_available:
        out = [r for r in out if r.is_available]

    return out


@router.get("/{room_id}", response_model=RoomOut)
def get_room(room_id: int):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    resp = (
        supabase_admin.table("rooms")
        .select("*, hostel_blocks(name)")
        .eq("id", room_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Room not found")

    return _room_to_out(resp.data[0], _booked_room_ids())
