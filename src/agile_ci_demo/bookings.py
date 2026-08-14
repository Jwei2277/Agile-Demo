from datetime import datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException

from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import (
    BookingCreate,
    BookingOut,
    BookingUpdate,
    CancellationRequestCreate,
    CancellationRequestOut,
    RoomOut,
    TransferRoomRequestCreate,
    TransferRoomRequestOut,
    total_fee_for,
)
from agile_ci_demo.rooms import _booked_room_ids, _room_to_out
from agile_ci_demo.services.supabase_service import supabase_admin
from agile_ci_demo.waitlist import notify_next_waitlisted

router = APIRouter(prefix="/bookings", tags=["bookings"])

BookingRow = dict[str, Any]


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

    is_paid = False
    try:
        db = _get_supabase()
        payment_resp = (
            db.table("payments")
            .select("id")
            .eq("booking_id", int(row["id"]))
            .eq("status", "paid")
            .limit(1)
            .execute()
        )
        is_paid = bool(payment_resp.data)
    except Exception:
        # Payment lookup is best-effort — never fail a booking response
        # over it.
        is_paid = False

    pending_cancellation_request = None
    try:
        db = _get_supabase()
        cancellation_resp = (
            db.table("booking_cancellation_requests")
            .select("*")
            .eq("booking_id", int(row["id"]))
            .eq("status", "pending")
            .order("requested_at", desc=True)
            .limit(1)
            .execute()
        )
        cancellation_rows = _get_rows(cancellation_resp.data)
        if cancellation_rows:
            c = cancellation_rows[0]
            pending_cancellation_request = CancellationRequestOut(
                id=int(c["id"]),
                booking_id=int(c["booking_id"]),
                reason=str(c["reason"]),
                status=str(c["status"]),
                rejection_reason=c.get("rejection_reason"),
                requested_at=c["requested_at"],
                decided_at=c.get("decided_at"),
            )
    except Exception:
        pending_cancellation_request = None

    return BookingOut(
        id=int(row["id"]),
        status=str(row["status"]),
        semester=str(row["semester"]),
        move_in_date=row["move_in_date"],
        move_out_date=row["move_out_date"],
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
        checked_in_at=row.get("checked_in_at"),
        checked_out_at=row.get("checked_out_at"),
        is_paid=is_paid,
        pending_cancellation_request=pending_cancellation_request,
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
        .is_("checked_out_at", "null")
        .execute()
    )

    if _get_rows(existing_resp.data):
        raise HTTPException(
            status_code=409,
            detail="You already have an active or pending booking",
        )

    try:
        room = _room_out_for(data.room_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

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
            "move_in_date": data.move_in_date.isoformat(),
            "move_out_date": data.move_out_date.isoformat(),
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
    "/history",
    response_model=list[BookingOut],
)
def get_my_booking_history(
    user: CurrentUser = Depends(get_current_user),
):
    """Every booking the student has ever made, regardless of status —
    active, cancelled, rejected, or otherwise. GET /me only returns the
    single currently-active one; this is the full record."""

    supabase = _get_supabase()

    resp = (
        supabase.table("bookings")
        .select("*")
        .eq(
            "student_id",
            user.id,
        )
        .order(
            "requested_at",
            desc=True,
        )
        .execute()
    )

    out = []
    for booking in _get_rows(resp.data):
        try:
            room = _room_out_for(int(booking["room_id"]))
        except HTTPException:
            # The room may have been deleted since — skip rather than
            # break the whole history over one bad row.
            continue
        out.append(_booking_out(booking, room))
    return out


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
        .is_("checked_out_at", "null")
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

    if booking["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=(
                "Only pending bookings can be edited. Once a booking is approved, "
                "use 'Request room transfer' instead to change rooms."
            ),
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

    if data.move_in_date and data.move_out_date:
        update_payload["move_in_date"] = data.move_in_date.isoformat()
        update_payload["move_out_date"] = data.move_out_date.isoformat()

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
            detail="Transfer requests are only available for approved bookings",
        )

    paid_check = (
        supabase.table("payments")
        .select("id")
        .eq("booking_id", booking_id)
        .eq("status", "paid")
        .limit(1)
        .execute()
    )
    if _get_rows(paid_check.data):
        raise HTTPException(
            status_code=409,
            detail="This booking has already been paid for — room transfers aren't available once payment is complete. Contact an admin if you need to change rooms.",
        )

    if int(booking["room_id"]) == data.room_id:
        raise HTTPException(
            status_code=400,
            detail="Choose a different room for transfer",
        )

    try:

        room = _room_out_for(data.room_id)

    except HTTPException:

        raise

    except Exception:

        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

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

    payload = {
        "booking_id": booking_id,
        "student_id": user.id,
        "requested_room_id": data.room_id,
        "reason": data.reason,
        "status": "pending",
        "requested_at": requested_at,
    }

    insert_resp = supabase.table("room_transfer_requests").insert(payload).execute()

    rows = _get_rows(insert_resp.data)

    if not rows:

        raise HTTPException(
            status_code=400,
            detail="Could not create transfer request",
        )

    row = rows[0]

    # Mark booking as waiting for transfer approval
    # Keep original room until admin approves

    supabase.table("bookings").update(
        {
            "status": "pending",
            "pending_transfer_room_id": data.room_id,
        }
    ).eq(
        "id",
        booking_id,
    ).execute()

    return TransferRoomRequestOut(
        id=int(
            row.get(
                "id",
                0,
            )
        ),
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

    paid_check = (
        supabase.table("payments")
        .select("id")
        .eq("booking_id", booking_id)
        .eq("status", "paid")
        .limit(1)
        .execute()
    )
    if _get_rows(paid_check.data):
        raise HTTPException(
            status_code=409,
            detail="This booking has already been paid for and can't be cancelled directly. Use 'Request cancellation & refund' instead — an admin will need to approve it.",
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

    try:
        # A pending transfer request tied to a now-cancelled booking is
        # meaningless — void it too instead of leaving it stuck in the
        # admin's pending queue forever. Soft-cancel (not delete) to keep
        # it in the audit trail, same as everywhere else in this app.
        supabase.table("room_transfer_requests").update({"status": "cancelled"}).eq(
            "booking_id", booking_id
        ).eq("status", "pending").execute()
    except Exception:
        # Non-critical — don't fail the cancellation itself over this.
        pass

    try:
        notify_next_waitlisted(int(booking["room_id"]))
    except Exception:
        # Waitlist notification is a nice-to-have — don't fail the
        # cancellation itself if this has a problem.
        pass


@router.post(
    "/{booking_id}/cancellation-request",
    status_code=201,
    response_model=CancellationRequestOut,
)
def request_cancellation(
    booking_id: int,
    data: CancellationRequestCreate,
    user: CurrentUser = Depends(get_current_user),
):
    """For a PAID booking only — self-service DELETE is blocked once
    paid, so this is the replacement: the student asks, and an admin has
    to approve it before the booking actually gets cancelled and the
    payment marked refunded."""

    supabase = _get_supabase()

    booking_resp = supabase.table("bookings").select("*").eq("id", booking_id).limit(1).execute()
    booking_rows = _get_rows(booking_resp.data)
    if not booking_rows:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking = booking_rows[0]

    if booking["student_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not your booking")

    if booking["status"] != "approved":
        raise HTTPException(
            status_code=409,
            detail="Only approved bookings can have a cancellation requested.",
        )

    paid_check = (
        supabase.table("payments")
        .select("id")
        .eq("booking_id", booking_id)
        .eq("status", "paid")
        .limit(1)
        .execute()
    )
    if not _get_rows(paid_check.data):
        raise HTTPException(
            status_code=409,
            detail="This booking hasn't been paid for yet — cancel it directly instead.",
        )

    existing_pending = (
        supabase.table("booking_cancellation_requests")
        .select("id")
        .eq("booking_id", booking_id)
        .eq("status", "pending")
        .limit(1)
        .execute()
    )
    if _get_rows(existing_pending.data):
        raise HTTPException(
            status_code=409,
            detail="You already have a pending cancellation request for this booking.",
        )

    insert_resp = (
        supabase.table("booking_cancellation_requests")
        .insert(
            {
                "booking_id": booking_id,
                "student_id": user.id,
                "reason": data.reason,
                "status": "pending",
            }
        )
        .execute()
    )
    rows = _get_rows(insert_resp.data)
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="The cancellation request was rejected by the database — please try again.",
        )

    row = rows[0]
    return CancellationRequestOut(
        id=int(row["id"]),
        booking_id=int(row["booking_id"]),
        reason=str(row["reason"]),
        status=str(row["status"]),
        rejection_reason=row.get("rejection_reason"),
        requested_at=row["requested_at"],
        decided_at=row.get("decided_at"),
    )
