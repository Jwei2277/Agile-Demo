from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import BookingCreate, BookingOut, RoomOut, total_fee_for
from agile_ci_demo.rooms import _room_to_out, _booked_room_ids
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _room_out_for(room_id: int) -> RoomOut:
    room_resp = (
        supabase_admin.table("rooms")
        .select("*, hostel_blocks(name)")
        .eq("id", room_id)
        .limit(1)
        .execute()
    )
    if not room_resp.data:
        raise HTTPException(status_code=404, detail="Room not found")

    return _room_to_out(room_resp.data[0], _booked_room_ids())


def _booking_out(row: dict, room: RoomOut) -> BookingOut:
    occupant_count = row.get("occupant_count", 1)
    return BookingOut(
        id=row["id"],
        status=row["status"],
        semester=row["semester"],
        requested_at=row["requested_at"],
        decided_at=row.get("decided_at"),
        occupant_count=occupant_count,
        extra_occupant_name=row.get("extra_occupant_name"),
        extra_occupant_email=row.get("extra_occupant_email"),
        extra_occupant_student_id=row.get("extra_occupant_student_id"),
        extra_occupant_gender=row.get("extra_occupant_gender"),
        total_fee=total_fee_for(room.fee_monthly, occupant_count),
        room=room,
    )


@router.post("", status_code=201, response_model=BookingOut)
def create_booking(data: BookingCreate, user: CurrentUser = Depends(get_current_user)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    # One active booking per student (also enforced by a DB unique index).
    existing = (
        supabase_admin.table("bookings")
        .select("id")
        .eq("student_id", user.id)
        .in_("status", ["pending", "approved"])
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="You already have an active or pending booking")

    room = _room_out_for(data.room_id)
    if not room.is_available:
        raise HTTPException(status_code=409, detail="This room is already booked")

    if data.occupant_count > room.capacity:
        raise HTTPException(
            status_code=400,
            detail=f"{room.room_type} only accommodates up to {room.capacity} occupant(s).",
        )

    # Gender-restricted rooms: "Female only" / "Male only" rooms require a
    # matching profile.gender. "Mixed block" rooms are open to anyone.
    # Students who registered before the gender field existed will have
    # gender=None and are blocked from restricted rooms until they update
    # their profile (there's no self-service profile edit yet — an admin
    # would need to set it directly in Supabase for now).
    if room.gender_policy in ("Female only", "Male only"):
        required_gender = "Female" if room.gender_policy == "Female only" else "Male"
        if user.gender != required_gender:
            raise HTTPException(
                status_code=403,
                detail=f"This room is restricted to {required_gender.lower()} students.",
            )
        # Applies to the 2nd occupant too — a room can't be "female only"
        # for the lead booker but mixed for their roommate.
        if data.occupant_count == 2 and data.extra_occupant_gender != required_gender:
            raise HTTPException(
                status_code=403,
                detail=f"This room is restricted to {required_gender.lower()} occupants — the 2nd occupant doesn't match.",
            )

    insert_resp = (
        supabase_admin.table("bookings")
        .insert(
            {
                "student_id": user.id,
                "room_id": data.room_id,
                "semester": data.semester,
                "status": "pending",
                "occupant_count": data.occupant_count,
                "extra_occupant_name": data.extra_occupant_name,
                "extra_occupant_email": data.extra_occupant_email,
                "extra_occupant_student_id": data.extra_occupant_student_id,
                "extra_occupant_gender": data.extra_occupant_gender,
            }
        )
        .execute()
    )
    if not insert_resp.data:
        raise HTTPException(
            status_code=400,
            detail="The booking was rejected by the database — the room or your account may no longer be valid.",
        )

    return _booking_out(insert_resp.data[0], room)


@router.get("/me", response_model=BookingOut | None)
def get_my_booking(user: CurrentUser = Depends(get_current_user)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    resp = (
        supabase_admin.table("bookings")
        .select("*")
        .eq("student_id", user.id)
        .in_("status", ["pending", "approved"])
        .order("requested_at", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None

    row = resp.data[0]
    room = _room_out_for(row["room_id"])
    return _booking_out(row, room)


@router.delete("/{booking_id}", status_code=204)
def cancel_booking(booking_id: int, user: CurrentUser = Depends(get_current_user)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    resp = supabase_admin.table("bookings").select("*").eq("id", booking_id).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking = resp.data[0]
    if booking["student_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not your booking")
    if booking["status"] not in ("pending", "approved"):
        raise HTTPException(
            status_code=409,
            detail=f"This booking is already '{booking['status']}' and can't be cancelled.",
        )

    supabase_admin.table("bookings").update(
        {"status": "cancelled", "decided_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", booking_id).execute()
