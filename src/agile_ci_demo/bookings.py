from datetime import datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException

from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import (
    BookingCreate,
    BookingOut,
    BookingUpdate,
    RoomOut,
    TransferRoomRequestCreate,
    TransferRoomRequestOut,
    total_fee_for,
)
from agile_ci_demo.rooms import _booked_room_ids, _room_to_out
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(
    prefix="/bookings",
    tags=["bookings"],
)


BookingRow = dict[str, Any]


_transfer_request_store: dict[int, BookingRow] = {}
_next_transfer_request_id = 1


def _get_rows(data: Any) -> list[BookingRow]:
    """
    Convert Supabase JSON response data into
    list of dictionaries for mypy.
    """
    if isinstance(data, list):
        return cast(
            list[BookingRow],
            data,
        )

    return []


def _get_supabase():
    """
    Return Supabase client after checking configuration.
    """
    if supabase_admin is None:
        raise HTTPException(
            status_code=501,
            detail="Server misconfigured: missing service role key",
        )

    return supabase_admin


def _room_out_for(
    room_id: int,
) -> RoomOut:

    supabase = _get_supabase()

    room_resp = (
        supabase.table("rooms")
        .select("*, hostel_blocks(name)")
        .eq(
            "id",
            room_id,
        )
        .limit(1)
        .execute()
    )

    rooms = _get_rows(room_resp.data)

    if not rooms:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

    return _room_to_out(
        rooms[0],
        _booked_room_ids(),
    )


def _booking_out(
    row: BookingRow,
    room: RoomOut,
) -> BookingOut:

    occupant_count = int(
        row.get(
            "occupant_count",
            1,
        )
    )

    pending_transfer_room = None

    pending_transfer_room_id = row.get("pending_transfer_room_id")

    if pending_transfer_room_id is not None:
        try:
            pending_transfer_room = _room_out_for(int(pending_transfer_room_id))
        except HTTPException:
            pending_transfer_room = None

    return BookingOut(
        id=int(row["id"]),
        status=str(row["status"]),
        semester=str(row["semester"]),
        requested_at=row["requested_at"],
        decided_at=row.get("decided_at"),
        occupant_count=occupant_count,
        extra_occupant_name=row.get("extra_occupant_name"),
        extra_occupant_email=row.get("extra_occupant_email"),
        extra_occupant_student_id=row.get("extra_occupant_student_id"),
        extra_occupant_gender=row.get("extra_occupant_gender"),
        total_fee=total_fee_for(
            room.fee_monthly,
            occupant_count,
        ),
        room=room,
        pending_transfer_room=pending_transfer_room,
    )


def _check_capacity_and_gender(
    room: RoomOut,
    user: CurrentUser,
    occupant_count: int,
    extra_occupant_gender: str | None,
) -> None:

    if occupant_count > room.capacity:
        raise HTTPException(
            status_code=400,
            detail=(f"{room.room_type} only accommodates " f"up to {room.capacity} occupant(s)."),
        )

    if room.gender_policy in (
        "Female only",
        "Male only",
    ):

        required_gender = "Female" if room.gender_policy == "Female only" else "Male"

        if user.gender != required_gender:
            raise HTTPException(
                status_code=403,
                detail=(f"This room is restricted to " f"{required_gender.lower()} students."),
            )

        if occupant_count == 2 and extra_occupant_gender != required_gender:
            raise HTTPException(
                status_code=403,
                detail=(f"This room is restricted to " f"{required_gender.lower()} occupants."),
            )


@router.post(
    "",
    status_code=201,
    response_model=BookingOut,
)
def create_booking(
    data: BookingCreate,
    user: CurrentUser = Depends(get_current_user),
):

    supabase = _get_supabase()

    existing_resp = (
        supabase.table("bookings")
        .select("id")
        .eq(
            "student_id",
            user.id,
        )
        .in_(
            "status",
            [
                "pending",
                "approved",
            ],
        )
        .execute()
    )

    if _get_rows(existing_resp.data):
        raise HTTPException(
            status_code=409,
            detail="You already have an active or pending booking",
        )

    room = _room_out_for(data.room_id)

    if not room.is_available:
        raise HTTPException(
            status_code=409,
            detail="This room is already booked",
        )

    _check_capacity_and_gender(
        room,
        user,
        data.occupant_count,
        data.extra_occupant_gender,
    )

    payload = cast(
        Any,
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
        },
    )

    insert_resp = supabase.table("bookings").insert(payload).execute()

    rows = _get_rows(insert_resp.data)

    if not rows:
        raise HTTPException(
            status_code=400,
            detail="Could not create booking",
        )

    return _booking_out(
        rows[0],
        room,
    )


@router.get(
    "/me",
    response_model=BookingOut | None,
)
def get_my_booking(
    user: CurrentUser = Depends(get_current_user),
):

    supabase = _get_supabase()

    resp = (
        supabase.table("bookings")
        .select("*")
        .eq(
            "student_id",
            user.id,
        )
        .in_(
            "status",
            [
                "pending",
                "approved",
            ],
        )
        .order(
            "requested_at",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    rows = _get_rows(resp.data)

    if not rows:
        return None

    booking = rows[0]

    room = _room_out_for(int(booking["room_id"]))

    return _booking_out(
        booking,
        room,
    )


@router.patch(
    "/{booking_id}",
    response_model=BookingOut,
)
def update_booking(
    booking_id: int,
    data: BookingUpdate,
    user: CurrentUser = Depends(get_current_user),
):

    supabase = _get_supabase()

    resp = (
        supabase.table("bookings")
        .select("*")
        .eq(
            "id",
            booking_id,
        )
        .limit(1)
        .execute()
    )

    rows = _get_rows(resp.data)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    booking = rows[0]

    if booking["student_id"] != user.id:
        raise HTTPException(
            status_code=403,
            detail="Not your booking",
        )

    if booking["status"] not in (
        "pending",
        "approved",
    ):
        raise HTTPException(
            status_code=409,
            detail="Only pending or approved bookings can be edited",
        )

    new_room_id = data.room_id if data.room_id else int(booking["room_id"])

    changing_room = new_room_id != int(booking["room_id"])

    room = _room_out_for(new_room_id)

    if changing_room and not room.is_available:
        raise HTTPException(
            status_code=409,
            detail="That room is already booked",
        )

    _check_capacity_and_gender(
        room,
        user,
        data.occupant_count,
        data.extra_occupant_gender,
    )

    is_double = data.occupant_count == 2

    update_payload: BookingRow = {
        "room_id": new_room_id,
        "occupant_count": data.occupant_count,
        "extra_occupant_name": (data.extra_occupant_name if is_double else None),
        "extra_occupant_email": (data.extra_occupant_email if is_double else None),
        "extra_occupant_student_id": (data.extra_occupant_student_id if is_double else None),
        "extra_occupant_gender": (data.extra_occupant_gender if is_double else None),
    }

    update_resp = (
        supabase.table("bookings")
        .update(update_payload)
        .eq(
            "id",
            booking_id,
        )
        .execute()
    )

    updated_rows = _get_rows(update_resp.data)

    if not updated_rows:
        raise HTTPException(
            status_code=400,
            detail="Could not update booking",
        )

    return _booking_out(
        updated_rows[0],
        room,
    )


@router.post(
    "/{booking_id}/transfer-request",
    response_model=TransferRoomRequestOut,
)
def request_room_transfer(
    booking_id: int,
    data: TransferRoomRequestCreate,
    user: CurrentUser = Depends(get_current_user),
):

    supabase = _get_supabase()

    booking_resp = (
        supabase.table("bookings")
        .select("*")
        .eq(
            "id",
            booking_id,
        )
        .limit(1)
        .execute()
    )

    booking_rows = _get_rows(booking_resp.data)

    if not booking_rows:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    booking = booking_rows[0]

    if booking["student_id"] != user.id:
        raise HTTPException(
            status_code=403,
            detail="Not your booking",
        )

    if booking["status"] != "approved":
        raise HTTPException(
            status_code=409,
            detail=("Transfer requests are only " "available for approved bookings"),
        )

    if int(booking["room_id"]) == data.room_id:
        raise HTTPException(
            status_code=400,
            detail="Choose a different room for transfer",
        )

    room = _room_out_for(data.room_id)

    if not room.is_available:
        raise HTTPException(
            status_code=409,
            detail="That room is already booked",
        )

    _check_capacity_and_gender(
        room,
        user,
        int(
            booking.get(
                "occupant_count",
                1,
            )
        ),
        cast(
            str | None,
            booking.get("extra_occupant_gender"),
        ),
    )

    requested_at = datetime.now(timezone.utc).isoformat()

    payload = cast(
        Any,
        {
            "booking_id": booking_id,
            "student_id": user.id,
            "requested_room_id": data.room_id,
            "reason": data.reason,
            "status": "pending",
            "requested_at": requested_at,
        },
    )

    global _next_transfer_request_id

    try:

        insert_resp = supabase.table("room_transfer_requests").insert(payload).execute()

        rows = _get_rows(insert_resp.data)

        if not rows:
            raise RuntimeError("No data returned")

        row = rows[0]

    except Exception:

        row = {
            "id": _next_transfer_request_id,
            **payload,
        }

        _transfer_request_store[_next_transfer_request_id] = row

        _next_transfer_request_id += 1

    try:

        (
            supabase.table("bookings")
            .update(
                {
                    "status": "pending",
                    "room_id": data.room_id,
                    "pending_transfer_room_id": data.room_id,
                }
            )
            .eq(
                "id",
                booking_id,
            )
            .execute()
        )

    except Exception:
        pass

    return TransferRoomRequestOut(
        id=int(row["id"]),
        booking_id=int(row["booking_id"]),
        requested_room_id=int(row["requested_room_id"]),
        reason=str(row["reason"]),
        status=str(row["status"]),
        requested_at=row["requested_at"],
    )


@router.delete(
    "/{booking_id}",
    status_code=204,
)
def cancel_booking(
    booking_id: int,
    user: CurrentUser = Depends(get_current_user),
):

    supabase = _get_supabase()

    resp = (
        supabase.table("bookings")
        .select("*")
        .eq(
            "id",
            booking_id,
        )
        .limit(1)
        .execute()
    )

    rows = _get_rows(resp.data)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    booking = rows[0]

    if booking["student_id"] != user.id:
        raise HTTPException(
            status_code=403,
            detail="Not your booking",
        )

    if booking["status"] not in (
        "pending",
        "approved",
    ):
        raise HTTPException(
            status_code=409,
            detail="Booking is already closed",
        )

    (
        supabase.table("bookings")
        .update(
            {
                "status": "cancelled",
                "decided_at": (datetime.now(timezone.utc).isoformat()),
            }
        )
        .eq(
            "id",
            booking_id,
        )
        .execute()
    )
