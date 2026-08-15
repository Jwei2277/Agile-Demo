import pytest
from pydantic import ValidationError

from agile_ci_demo.models import (
    EXTRA_PERSON_FEE,
    MIN_STAY_DAYS,
    BookingCreate,
    BookingUpdate,
    CancellationRequestCreate,
    CancellationRequestReject,
    DocumentRejectRequest,
    DocumentOut,
    MaintenanceCreate,
    MaintenanceOut,
    MaintenanceUpdate,
    PaymentCreate,
    PaymentOut,
    RoomCreate,
    RoomOut,
    RoomUpdate,
    TransferRoomRequestCreate,
    VisitorRequestCreate,
    VisitorRequestOut,
    WaitlistJoinCreate,
    total_fee_for,
)

# ============================================================
# total_fee_for()
# ============================================================


def test_total_fee_for_single_occupant():
    result = total_fee_for(120.0, 1)

    assert result == 120.0

    print("total_fee_for single occupant - PASSED")


def test_total_fee_for_two_occupants():
    result = total_fee_for(120.0, 2)

    assert result == 120.0 + EXTRA_PERSON_FEE
    assert result == 170.0

    print("total_fee_for two occupants - PASSED")


def test_total_fee_for_zero_occupants():
    result = total_fee_for(120.0, 0)

    assert result == 120.0

    print("total_fee_for zero occupants - PASSED")


def test_total_fee_for_negative_occupants():
    result = total_fee_for(120.0, -5)

    assert result == 120.0

    print("total_fee_for negative occupants - PASSED")


def test_total_fee_for_different_base_fee():
    result = total_fee_for(250.0, 2)

    assert result == 300.0

    print("total_fee_for different base fee - PASSED")


# ============================================================
# BookingCreate
# ============================================================


def valid_booking_create_payload():
    return {
        "room_id": 1,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2026-10-01",
        "occupant_count": 1,
    }


def test_booking_create_valid():
    booking = BookingCreate(**valid_booking_create_payload())

    assert booking.room_id == 1
    assert booking.semester == "Semester 1"
    assert booking.occupant_count == 1
    assert booking.extra_occupant_name is None
    assert booking.extra_occupant_email is None
    assert booking.extra_occupant_student_id is None
    assert booking.extra_occupant_gender is None

    print("booking create valid - PASSED")


def test_booking_create_default_occupant_count():
    payload = valid_booking_create_payload()
    payload.pop("occupant_count")

    booking = BookingCreate(**payload)

    assert booking.occupant_count == 1

    print("booking create default occupant count - PASSED")


def test_booking_create_minimum_stay():
    payload = valid_booking_create_payload()

    booking = BookingCreate(**payload)

    days = (booking.move_out_date - booking.move_in_date).days

    assert days >= MIN_STAY_DAYS

    print("booking create minimum stay - PASSED")


def test_booking_create_less_than_minimum_stay():
    payload = valid_booking_create_payload()
    payload["move_out_date"] = "2026-09-20"

    with pytest.raises(ValidationError, match="at least 30 days"):
        BookingCreate(**payload)

    print("booking create less than minimum stay - PASSED")


def test_booking_create_exactly_minimum_stay():
    payload = valid_booking_create_payload()
    payload["move_out_date"] = "2026-10-01"

    booking = BookingCreate(**payload)

    assert (booking.move_out_date - booking.move_in_date).days == MIN_STAY_DAYS

    print("booking create exactly minimum stay - PASSED")


def test_booking_create_two_occupants_valid():
    payload = valid_booking_create_payload()

    payload.update(
        {
            "occupant_count": 2,
            "extra_occupant_name": "Jane Tan",
            "extra_occupant_email": "jane@example.com",
            "extra_occupant_student_id": "TP123456",
            "extra_occupant_gender": "Female",
        }
    )

    booking = BookingCreate(**payload)

    assert booking.occupant_count == 2
    assert booking.extra_occupant_name == "Jane Tan"
    assert str(booking.extra_occupant_email) == "jane@example.com"
    assert booking.extra_occupant_student_id == "TP123456"
    assert booking.extra_occupant_gender == "Female"

    print("booking create two occupants valid - PASSED")


def test_booking_create_two_occupants_missing_name():
    payload = valid_booking_create_payload()

    payload.update(
        {
            "occupant_count": 2,
            "extra_occupant_email": "jane@example.com",
            "extra_occupant_student_id": "TP123456",
            "extra_occupant_gender": "Female",
        }
    )

    with pytest.raises(ValidationError, match="extra_occupant_name"):
        BookingCreate(**payload)

    print("booking create missing extra occupant name - PASSED")


def test_booking_create_two_occupants_missing_email():
    payload = valid_booking_create_payload()

    payload.update(
        {
            "occupant_count": 2,
            "extra_occupant_name": "Jane Tan",
            "extra_occupant_student_id": "TP123456",
            "extra_occupant_gender": "Female",
        }
    )

    with pytest.raises(ValidationError, match="extra_occupant_email"):
        BookingCreate(**payload)

    print("booking create missing extra occupant email - PASSED")


def test_booking_create_two_occupants_missing_student_id():
    payload = valid_booking_create_payload()

    payload.update(
        {
            "occupant_count": 2,
            "extra_occupant_name": "Jane Tan",
            "extra_occupant_email": "jane@example.com",
            "extra_occupant_gender": "Female",
        }
    )

    with pytest.raises(ValidationError, match="extra_occupant_student_id"):
        BookingCreate(**payload)

    print("booking create missing extra occupant student ID - PASSED")


def test_booking_create_two_occupants_missing_gender():
    payload = valid_booking_create_payload()

    payload.update(
        {
            "occupant_count": 2,
            "extra_occupant_name": "Jane Tan",
            "extra_occupant_email": "jane@example.com",
            "extra_occupant_student_id": "TP123456",
        }
    )

    with pytest.raises(ValidationError, match="extra_occupant_gender"):
        BookingCreate(**payload)

    print("booking create missing extra occupant gender - PASSED")


def test_booking_create_occupant_count_zero():
    payload = valid_booking_create_payload()
    payload["occupant_count"] = 0

    with pytest.raises(ValidationError):
        BookingCreate(**payload)

    print("booking create occupant count zero - PASSED")


def test_booking_create_occupant_count_three():
    payload = valid_booking_create_payload()
    payload["occupant_count"] = 3

    with pytest.raises(ValidationError):
        BookingCreate(**payload)

    print("booking create occupant count above two - PASSED")


def test_booking_create_invalid_student_id():
    payload = valid_booking_create_payload()

    payload.update(
        {
            "occupant_count": 2,
            "extra_occupant_name": "Jane Tan",
            "extra_occupant_email": "jane@example.com",
            "extra_occupant_student_id": "invalid",
            "extra_occupant_gender": "Female",
        }
    )

    with pytest.raises(ValidationError):
        BookingCreate(**payload)

    print("booking create invalid student ID - PASSED")


def test_booking_create_invalid_gender():
    payload = valid_booking_create_payload()

    payload.update(
        {
            "occupant_count": 2,
            "extra_occupant_name": "Jane Tan",
            "extra_occupant_email": "jane@example.com",
            "extra_occupant_student_id": "TP123456",
            "extra_occupant_gender": "Unknown",
        }
    )

    with pytest.raises(ValidationError):
        BookingCreate(**payload)

    print("booking create invalid extra occupant gender - PASSED")


def test_booking_create_invalid_email():
    payload = valid_booking_create_payload()

    payload.update(
        {
            "occupant_count": 2,
            "extra_occupant_name": "Jane Tan",
            "extra_occupant_email": "not-an-email",
            "extra_occupant_student_id": "TP123456",
            "extra_occupant_gender": "Female",
        }
    )

    with pytest.raises(ValidationError):
        BookingCreate(**payload)

    print("booking create invalid email - PASSED")


def test_booking_create_clears_extra_details_for_single_occupant():
    payload = valid_booking_create_payload()

    payload.update(
        {
            "occupant_count": 1,
            "extra_occupant_name": "Should Be Removed",
            "extra_occupant_email": "extra@example.com",
            "extra_occupant_student_id": "TP123456",
            "extra_occupant_gender": "Female",
        }
    )

    booking = BookingCreate(**payload)

    assert booking.extra_occupant_name is None
    assert booking.extra_occupant_email is None
    assert booking.extra_occupant_student_id is None
    assert booking.extra_occupant_gender is None

    print("booking create clears stray extra occupant details - PASSED")


# ============================================================
# BookingUpdate
# ============================================================


def test_booking_update_empty():
    booking = BookingUpdate()

    assert booking.room_id is None
    assert booking.move_in_date is None
    assert booking.move_out_date is None
    assert booking.occupant_count == 1

    print("booking update empty - PASSED")


def test_booking_update_valid_dates():
    booking = BookingUpdate(
        move_in_date="2026-09-01",
        move_out_date="2026-10-01",
    )

    assert booking.move_in_date.isoformat() == "2026-09-01"
    assert booking.move_out_date.isoformat() == "2026-10-01"

    print("booking update valid dates - PASSED")


def test_booking_update_only_move_in_date():
    with pytest.raises(ValidationError, match="both move_in_date and move_out_date"):
        BookingUpdate(move_in_date="2026-09-01")

    print("booking update only move in date - PASSED")


def test_booking_update_only_move_out_date():
    with pytest.raises(ValidationError, match="both move_in_date and move_out_date"):
        BookingUpdate(move_out_date="2026-10-01")

    print("booking update only move out date - PASSED")


def test_booking_update_short_stay():
    with pytest.raises(ValidationError, match="at least 30 days"):
        BookingUpdate(
            move_in_date="2026-09-01",
            move_out_date="2026-09-20",
        )

    print("booking update short stay - PASSED")


def test_booking_update_two_occupants_requires_details():
    with pytest.raises(ValidationError, match="extra_occupant_name"):
        BookingUpdate(occupant_count=2)

    print("booking update two occupants requires details - PASSED")


def test_booking_update_two_occupants_valid():
    booking = BookingUpdate(
        occupant_count=2,
        extra_occupant_name="Jane Tan",
        extra_occupant_email="jane@example.com",
        extra_occupant_student_id="TP123456",
        extra_occupant_gender="Female",
    )

    assert booking.occupant_count == 2
    assert booking.extra_occupant_name == "Jane Tan"

    print("booking update two occupants valid - PASSED")


def test_booking_update_single_occupant_clears_extra_details():
    booking = BookingUpdate(
        occupant_count=1,
        extra_occupant_name="Extra Person",
        extra_occupant_email="extra@example.com",
        extra_occupant_student_id="TP123456",
        extra_occupant_gender="Female",
    )

    assert booking.extra_occupant_name is None
    assert booking.extra_occupant_email is None
    assert booking.extra_occupant_student_id is None
    assert booking.extra_occupant_gender is None

    print("booking update clears extra details - PASSED")


# ============================================================
# RoomOut
# ============================================================


def test_room_out_valid():
    room = RoomOut(
        id=1,
        block_name="Block A",
        level=1,
        room_number="101",
        room_type="Single Room",
        capacity=1,
        is_available=True,
        gender_policy="Male only",
        fee_monthly=120.0,
    )

    assert room.id == 1
    assert room.block_name == "Block A"
    assert room.room_number == "101"
    assert room.capacity == 1
    assert room.is_available is True
    assert room.photo_url is None

    print("room out valid - PASSED")


def test_room_out_with_photo():
    room = RoomOut(
        id=1,
        block_name="Block A",
        level=1,
        room_number="101",
        room_type="Single Room",
        capacity=1,
        is_available=True,
        gender_policy="Male only",
        fee_monthly=120.0,
        photo_url="https://example.com/room.jpg",
    )

    assert room.photo_url == "https://example.com/room.jpg"

    print("room out with photo - PASSED")


# ============================================================
# RoomCreate
# ============================================================


def valid_room_create_payload():
    return {
        "block_id": 1,
        "level": 1,
        "room_number": "101",
        "room_type": "Single Room",
        "capacity": 1,
        "gender_policy": "Male only",
        "fee_monthly": 120.0,
    }


def test_room_create_valid():
    room = RoomCreate(**valid_room_create_payload())

    assert room.block_id == 1
    assert room.level == 1
    assert room.room_number == "101"
    assert room.room_type == "Single Room"
    assert room.capacity == 1
    assert room.fee_monthly == 120.0
    assert room.photo_url is None

    print("room create valid - PASSED")


@pytest.mark.parametrize(
    "room_type",
    ["Master Room", "Balcony Room", "Middle Room"],
)
def test_room_create_non_single_types(room_type):
    payload = valid_room_create_payload()
    payload["room_type"] = room_type
    payload["capacity"] = 2

    room = RoomCreate(**payload)

    assert room.room_type == room_type
    assert room.capacity == 2

    print(f"room create {room_type} - PASSED")


def test_room_create_single_room_capacity_two():
    payload = valid_room_create_payload()
    payload["capacity"] = 2

    with pytest.raises(ValidationError, match="Single Room must have capacity 1"):
        RoomCreate(**payload)

    print("room create single room capacity two rejected - PASSED")


def test_room_create_capacity_zero():
    payload = valid_room_create_payload()
    payload["capacity"] = 0

    with pytest.raises(ValidationError):
        RoomCreate(**payload)

    print("room create capacity zero rejected - PASSED")


def test_room_create_capacity_three():
    payload = valid_room_create_payload()
    payload["capacity"] = 3

    with pytest.raises(ValidationError):
        RoomCreate(**payload)

    print("room create capacity above two rejected - PASSED")


def test_room_create_negative_fee():
    payload = valid_room_create_payload()
    payload["fee_monthly"] = -10

    with pytest.raises(ValidationError):
        RoomCreate(**payload)

    print("room create negative fee rejected - PASSED")


def test_room_create_zero_fee():
    payload = valid_room_create_payload()
    payload["fee_monthly"] = 0

    with pytest.raises(ValidationError):
        RoomCreate(**payload)

    print("room create zero fee rejected - PASSED")


def test_room_create_invalid_room_type():
    payload = valid_room_create_payload()
    payload["room_type"] = "Invalid Room"

    with pytest.raises(ValidationError):
        RoomCreate(**payload)

    print("room create invalid room type rejected - PASSED")


# ============================================================
# RoomUpdate
# ============================================================


def test_room_update_empty():
    room = RoomUpdate()

    assert room.level is None
    assert room.room_type is None
    assert room.capacity is None
    assert room.gender_policy is None
    assert room.fee_monthly is None
    assert room.is_active is None

    print("room update empty - PASSED")


def test_room_update_valid():
    room = RoomUpdate(
        level=2,
        room_type="Master Room",
        capacity=2,
        gender_policy="Mixed block",
        fee_monthly=250,
        is_active=True,
    )

    assert room.level == 2
    assert room.room_type == "Master Room"
    assert room.capacity == 2
    assert room.fee_monthly == 250
    assert room.is_active is True

    print("room update valid - PASSED")


def test_room_update_single_room_capacity_two():
    with pytest.raises(ValidationError, match="Single Room must have capacity 1"):
        RoomUpdate(
            room_type="Single Room",
            capacity=2,
        )

    print("room update single room capacity two rejected - PASSED")


def test_room_update_single_room_capacity_one():
    room = RoomUpdate(
        room_type="Single Room",
        capacity=1,
    )

    assert room.capacity == 1

    print("room update single room capacity one - PASSED")


def test_room_update_negative_fee():
    with pytest.raises(ValidationError):
        RoomUpdate(fee_monthly=-1)

    print("room update negative fee rejected - PASSED")


# ============================================================
# MaintenanceCreate / MaintenanceUpdate
# ============================================================


def test_maintenance_create_valid():
    maintenance = MaintenanceCreate(
        title="Broken light",
        category="Electrical",
        priority="High",
        room_id=1,
    )

    assert maintenance.title == "Broken light"
    assert maintenance.category == "Electrical"
    assert maintenance.priority == "High"
    assert maintenance.room_id == 1

    print("maintenance create valid - PASSED")


def test_maintenance_create_defaults():
    maintenance = MaintenanceCreate(title="Broken fan")

    assert maintenance.category == "General"
    assert maintenance.priority == "Normal"
    assert maintenance.room_id is None

    print("maintenance create defaults - PASSED")


def test_maintenance_create_empty_title():
    with pytest.raises(ValidationError):
        MaintenanceCreate(title="")

    print("maintenance create empty title rejected - PASSED")


@pytest.mark.parametrize(
    "status",
    [
        "pending",
        "assigned",
        "in_progress",
        "completed",
        "closed",
        "cancelled",
    ],
)
def test_maintenance_update_valid_status(status):
    maintenance = MaintenanceUpdate(status=status)

    assert maintenance.status == status

    print(f"maintenance update status {status} - PASSED")


def test_maintenance_update_invalid_status():
    with pytest.raises(ValidationError):
        MaintenanceUpdate(status="invalid")

    print("maintenance update invalid status rejected - PASSED")


@pytest.mark.parametrize("priority", ["Low", "Normal", "High"])
def test_maintenance_update_valid_priority(priority):
    maintenance = MaintenanceUpdate(priority=priority)

    assert maintenance.priority == priority

    print(f"maintenance update priority {priority} - PASSED")


def test_maintenance_update_invalid_priority():
    with pytest.raises(ValidationError):
        MaintenanceUpdate(priority="Urgent")

    print("maintenance update invalid priority rejected - PASSED")


# ============================================================
# VisitorRequestCreate
# ============================================================


def valid_visitor_payload():
    return {
        "visitor_name": "John Tan",
        "visitor_email": "john@example.com",
        "visitor_relationship": "Friend",
        "visitor_phone": "0123456789",
        "visit_date": "2026-09-10",
        "visit_time": "14:00",
    }


def test_visitor_request_valid():
    visitor = VisitorRequestCreate(**valid_visitor_payload())

    assert visitor.visitor_name == "John Tan"
    assert str(visitor.visitor_email) == "john@example.com"
    assert visitor.visitor_relationship == "Friend"
    assert visitor.visitor_phone == "0123456789"
    assert visitor.visit_time.hour == 14

    print("visitor request valid - PASSED")


def test_visitor_request_start_time():
    payload = valid_visitor_payload()
    payload["visit_time"] = "08:00"

    visitor = VisitorRequestCreate(**payload)

    assert visitor.visit_time.hour == 8

    print("visitor request 8 AM accepted - PASSED")


def test_visitor_request_end_time():
    payload = valid_visitor_payload()
    payload["visit_time"] = "22:00"

    visitor = VisitorRequestCreate(**payload)

    assert visitor.visit_time.hour == 22

    print("visitor request 10 PM accepted - PASSED")


def test_visitor_request_before_start_time():
    payload = valid_visitor_payload()
    payload["visit_time"] = "07:59"

    with pytest.raises(ValidationError, match="Visiting hours"):
        VisitorRequestCreate(**payload)

    print("visitor request before visiting hours rejected - PASSED")


def test_visitor_request_after_end_time():
    payload = valid_visitor_payload()
    payload["visit_time"] = "22:01"

    with pytest.raises(ValidationError, match="Visiting hours"):
        VisitorRequestCreate(**payload)

    print("visitor request after visiting hours rejected - PASSED")


@pytest.mark.parametrize(
    "name",
    [
        "John123",
        "John@Tan",
        "John_Tan",
        "John-Tan",
    ],
)
def test_visitor_request_invalid_name(name):
    payload = valid_visitor_payload()
    payload["visitor_name"] = name

    with pytest.raises(ValidationError, match="letters and spaces"):
        VisitorRequestCreate(**payload)

    print(f"visitor invalid name {name} - PASSED")


def test_visitor_request_valid_name_with_spaces():
    payload = valid_visitor_payload()
    payload["visitor_name"] = "John Tan"

    visitor = VisitorRequestCreate(**payload)

    assert visitor.visitor_name == "John Tan"

    print("visitor valid name with spaces - PASSED")


@pytest.mark.parametrize(
    "phone",
    [
        "123",
        "123456789",
        "123456789012",
        "01234abcde",
        "012-3456789",
    ],
)
def test_visitor_request_invalid_phone(phone):
    payload = valid_visitor_payload()
    payload["visitor_phone"] = phone

    with pytest.raises(ValidationError, match="10-11 digits"):
        VisitorRequestCreate(**payload)

    print(f"visitor invalid phone {phone} - PASSED")


def test_visitor_request_10_digit_phone():
    payload = valid_visitor_payload()
    payload["visitor_phone"] = "0123456789"

    visitor = VisitorRequestCreate(**payload)

    assert visitor.visitor_phone == "0123456789"

    print("visitor 10 digit phone - PASSED")


def test_visitor_request_11_digit_phone():
    payload = valid_visitor_payload()
    payload["visitor_phone"] = "01234567890"

    visitor = VisitorRequestCreate(**payload)

    assert visitor.visitor_phone == "01234567890"

    print("visitor 11 digit phone - PASSED")


def test_visitor_request_invalid_email():
    payload = valid_visitor_payload()
    payload["visitor_email"] = "invalid-email"

    with pytest.raises(ValidationError):
        VisitorRequestCreate(**payload)

    print("visitor invalid email - PASSED")


# ============================================================
# PaymentCreate
# ============================================================


@pytest.mark.parametrize(
    "method",
    ["Card", "Online Banking", "E-Wallet"],
)
def test_payment_create_valid_methods(method):
    payment = PaymentCreate(
        booking_id=1,
        method=method,
    )

    assert payment.booking_id == 1
    assert payment.method == method

    print(f"payment create {method} - PASSED")


def test_payment_create_invalid_method():
    with pytest.raises(ValidationError):
        PaymentCreate(
            booking_id=1,
            method="Cash",
        )

    print("payment create invalid method rejected - PASSED")


def test_payment_create_missing_booking_id():
    with pytest.raises(ValidationError):
        PaymentCreate(method="Card")

    print("payment create missing booking ID - PASSED")


# ============================================================
# TransferRoomRequestCreate
# ============================================================


def test_transfer_room_request_valid():
    request = TransferRoomRequestCreate(
        room_id=2,
        reason="Need a quieter room",
    )

    assert request.room_id == 2
    assert request.reason == "Need a quieter room"

    print("transfer room request valid - PASSED")


def test_transfer_room_request_empty_reason():
    with pytest.raises(ValidationError):
        TransferRoomRequestCreate(
            room_id=2,
            reason="",
        )

    print("transfer room request empty reason rejected - PASSED")


# ============================================================
# WaitlistJoinCreate
# ============================================================


def test_waitlist_join_valid_single():
    entry = WaitlistJoinCreate(
        move_in_date="2026-09-01",
        move_out_date="2026-10-01",
    )

    assert entry.occupant_count == 1
    assert entry.extra_occupant_name is None

    print("waitlist join valid single - PASSED")


def test_waitlist_join_short_stay():
    with pytest.raises(ValidationError, match="at least 30 days"):
        WaitlistJoinCreate(
            move_in_date="2026-09-01",
            move_out_date="2026-09-20",
        )

    print("waitlist join short stay rejected - PASSED")


def test_waitlist_join_two_occupants_missing_details():
    with pytest.raises(ValidationError, match="extra_occupant_name"):
        WaitlistJoinCreate(
            move_in_date="2026-09-01",
            move_out_date="2026-10-01",
            occupant_count=2,
        )

    print("waitlist join missing second occupant details - PASSED")


def test_waitlist_join_two_occupants_valid():
    entry = WaitlistJoinCreate(
        move_in_date="2026-09-01",
        move_out_date="2026-10-01",
        occupant_count=2,
        extra_occupant_name="Jane Tan",
        extra_occupant_email="jane@example.com",
        extra_occupant_student_id="TP123456",
        extra_occupant_gender="Female",
    )

    assert entry.occupant_count == 2
    assert entry.extra_occupant_name == "Jane Tan"

    print("waitlist join two occupants valid - PASSED")


# ============================================================
# Simple output models
# ============================================================


def test_maintenance_out_valid():
    maintenance = MaintenanceOut(
        id=1,
        title="Broken light",
        category="Electrical",
        priority="High",
        status="pending",
        created_at="2026-08-15T10:00:00Z",
    )

    assert maintenance.id == 1
    assert maintenance.title == "Broken light"
    assert maintenance.completed_at is None
    assert maintenance.room_label is None

    print("maintenance out valid - PASSED")


def test_payment_out_valid():
    payment = PaymentOut(
        id=1,
        booking_id=10,
        amount=170.0,
        method="Card",
        status="paid",
        receipt_number="RCPT-20260815-ABC123",
        paid_at="2026-08-15T10:00:00Z",
    )

    assert payment.id == 1
    assert payment.booking_id == 10
    assert payment.amount == 170.0
    assert payment.status == "paid"
    assert payment.room_label is None

    print("payment out valid - PASSED")


def test_document_out_valid():
    document = DocumentOut(
        id=1,
        document_type="IC / Passport",
        file_name="passport.pdf",
        status="pending",
        uploaded_at="2026-08-15T10:00:00Z",
    )

    assert document.id == 1
    assert document.document_type == "IC / Passport"
    assert document.file_name == "passport.pdf"
    assert document.status == "pending"
    assert document.view_url is None

    print("document out valid - PASSED")


def test_visitor_request_out_valid():
    visitor = VisitorRequestOut(
        id=1,
        visitor_name="John Tan",
        visitor_email="john@example.com",
        visitor_relationship="Friend",
        visitor_phone="0123456789",
        visit_date="2026-09-10",
        visit_time="14:00",
        status="pending",
        requested_at="2026-08-15T10:00:00Z",
    )

    assert visitor.id == 1
    assert visitor.status == "pending"
    assert visitor.rejection_reason is None
    assert visitor.decided_at is None

    print("visitor request out valid - PASSED")


# ============================================================
# Cancellation / rejection models
# ============================================================


def test_cancellation_request_create_valid():
    request = CancellationRequestCreate(
        reason="Change of plans",
    )

    assert request.reason == "Change of plans"

    print("cancellation request create valid - PASSED")


def test_cancellation_request_create_empty():
    with pytest.raises(ValidationError):
        CancellationRequestCreate(reason="")

    print("cancellation request create empty rejected - PASSED")


def test_cancellation_request_reject_valid():
    request = CancellationRequestReject(
        reason="Cancellation period has expired",
    )

    assert request.reason == "Cancellation period has expired"

    print("cancellation request reject valid - PASSED")


def test_cancellation_request_reject_empty():
    with pytest.raises(ValidationError):
        CancellationRequestReject(reason="")

    print("cancellation request reject empty rejected - PASSED")


def test_document_reject_request_valid():
    request = DocumentRejectRequest(
        reason="Document is not readable",
    )

    assert request.reason == "Document is not readable"

    print("document reject request valid - PASSED")


def test_document_reject_request_empty():
    with pytest.raises(ValidationError):
        DocumentRejectRequest(reason="")

    print("document reject request empty rejected - PASSED")
