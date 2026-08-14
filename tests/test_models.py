from datetime import UTC, date, datetime, time

import pytest
from pydantic import ValidationError

from agile_ci_demo.models import (
    EXTRA_PERSON_FEE,
    MAINTENANCE_STATUSES,
    MIN_STAY_DAYS,
    ROOM_TYPES,
    BookingCreate,
    BookingOut,
    BookingUpdate,
    MaintenanceOut,
    MaintenanceUpdate,
    RoomCreate,
    RoomOut,
    RoomUpdate,
    VisitorRequestCreate,
    WaitlistJoinCreate,
    total_fee_for,
)

# ==========================================================
# total_fee_for()
# ==========================================================


def test_total_fee_single():

    fee = total_fee_for(
        100,
        1,
    )

    assert fee == 100

    print("test_total_fee_single PASSED")


def test_total_fee_double():

    fee = total_fee_for(
        100,
        2,
    )

    assert fee == 100 + EXTRA_PERSON_FEE

    print("test_total_fee_double PASSED")


def test_total_fee_three():

    fee = total_fee_for(
        100,
        3,
    )

    assert fee == 100 + EXTRA_PERSON_FEE * 2

    print("test_total_fee_three PASSED")


# ==========================================================
# BookingCreate
# ==========================================================


def test_booking_create_valid():

    booking = BookingCreate(
        room_id=1,
        semester="Semester 1",
        move_in_date=date(2026, 9, 1),
        move_out_date=date(2026, 10, 5),
        occupant_count=1,
    )

    assert booking.room_id == 1

    assert booking.occupant_count == 1

    print("test_booking_create_valid PASSED")


def test_booking_create_short_stay():

    with pytest.raises(ValidationError):
        BookingCreate(
            room_id=1,
            semester="Semester 1",
            move_in_date=date(2026, 9, 1),
            move_out_date=date(2026, 9, 15),
            occupant_count=1,
        )

    print("test_booking_create_short_stay PASSED")


def test_booking_create_two_people():

    booking = BookingCreate(
        room_id=1,
        semester="Semester 1",
        move_in_date=date(2026, 9, 1),
        move_out_date=date(2026, 10, 5),
        occupant_count=2,
        extra_occupant_name="Mary",
        extra_occupant_email="mary@test.com",
        extra_occupant_student_id="TP123456",
        extra_occupant_gender="Female",
    )

    assert booking.occupant_count == 2

    print("test_booking_create_two_people PASSED")


def test_booking_create_missing_second_person():

    with pytest.raises(ValidationError):
        BookingCreate(
            room_id=1,
            semester="Semester 1",
            move_in_date=date(2026, 9, 1),
            move_out_date=date(2026, 10, 5),
            occupant_count=2,
        )

    print("test_booking_create_missing_second_person PASSED")


def test_booking_create_single_person_clears_extra():

    booking = BookingCreate(
        room_id=1,
        semester="Semester 1",
        move_in_date=date(2026, 9, 1),
        move_out_date=date(2026, 10, 5),
        occupant_count=1,
        extra_occupant_name="Someone",
        extra_occupant_email="someone@test.com",
        extra_occupant_student_id="TP123456",
        extra_occupant_gender="Male",
    )

    assert booking.extra_occupant_name is None

    assert booking.extra_occupant_email is None

    assert booking.extra_occupant_student_id is None

    assert booking.extra_occupant_gender is None

    print("test_booking_create_single_person_clears_extra PASSED")


# ==========================================================
# BookingUpdate
# ==========================================================


def test_booking_update_valid():

    booking = BookingUpdate(
        room_id=2,
        move_in_date=date(2026, 9, 1),
        move_out_date=date(2026, 10, 5),
        occupant_count=1,
    )

    assert booking.room_id == 2

    print("test_booking_update_valid PASSED")


def test_booking_update_only_move_in():

    with pytest.raises(ValidationError):
        BookingUpdate(
            move_in_date=date(2026, 9, 1),
        )

    print("test_booking_update_only_move_in PASSED")


def test_booking_update_only_move_out():

    with pytest.raises(ValidationError):
        BookingUpdate(
            move_out_date=date(2026, 10, 5),
        )

    print("test_booking_update_only_move_out PASSED")


def test_booking_update_short_stay():

    with pytest.raises(ValidationError):
        BookingUpdate(
            move_in_date=date(2026, 9, 1),
            move_out_date=date(2026, 9, 20),
        )

    print("test_booking_update_short_stay PASSED")


def test_booking_update_two_people_valid():

    booking = BookingUpdate(
        occupant_count=2,
        extra_occupant_name="Mary",
        extra_occupant_email="mary@test.com",
        extra_occupant_student_id="TP123456",
        extra_occupant_gender="Female",
    )

    assert booking.occupant_count == 2

    print("test_booking_update_two_people_valid PASSED")


def test_booking_update_two_people_missing():

    with pytest.raises(ValidationError):
        BookingUpdate(
            occupant_count=2,
        )

    print("test_booking_update_two_people_missing PASSED")


def test_booking_update_single_clears_extra():

    booking = BookingUpdate(
        occupant_count=1,
        extra_occupant_name="Someone",
        extra_occupant_email="someone@test.com",
        extra_occupant_student_id="TP123456",
        extra_occupant_gender="Male",
    )

    assert booking.extra_occupant_name is None

    assert booking.extra_occupant_email is None

    assert booking.extra_occupant_student_id is None

    assert booking.extra_occupant_gender is None

    print("test_booking_update_single_clears_extra PASSED")


# ==========================================================
# RoomCreate
# ==========================================================


def test_room_create_valid():

    room = RoomCreate(
        block_id=1,
        level=1,
        room_number="101",
        room_type="Single Room",
        capacity=1,
        gender_policy="Male only",
        fee_monthly=100,
    )

    assert room.capacity == 1

    print("test_room_create_valid PASSED")


def test_room_create_invalid_single_room():

    with pytest.raises(ValidationError):
        RoomCreate(
            block_id=1,
            level=1,
            room_number="101",
            room_type="Single Room",
            capacity=2,
            gender_policy="Male only",
            fee_monthly=100,
        )

    print("test_room_create_invalid_single_room PASSED")


def test_room_create_master_room():

    room = RoomCreate(
        block_id=1,
        level=2,
        room_number="201",
        room_type="Master Room",
        capacity=2,
        gender_policy="Female only",
        fee_monthly=200,
    )

    assert room.capacity == 2

    print("test_room_create_master_room PASSED")


# ==========================================================
# RoomUpdate
# ==========================================================


def test_room_update_valid():

    room = RoomUpdate(
        room_type="Master Room",
        capacity=2,
    )

    assert room.capacity == 2

    print("test_room_update_valid PASSED")


def test_room_update_invalid_single_room():

    with pytest.raises(ValidationError):
        RoomUpdate(
            room_type="Single Room",
            capacity=2,
        )

    print("test_room_update_invalid_single_room PASSED")


# ==========================================================
# WaitlistJoinCreate
# ==========================================================


def test_waitlist_join_valid():

    waitlist = WaitlistJoinCreate(
        move_in_date=date(2026, 9, 1),
        move_out_date=date(2026, 10, 5),
        occupant_count=1,
    )

    assert waitlist.occupant_count == 1

    print("test_waitlist_join_valid PASSED")


def test_waitlist_join_short_stay():

    with pytest.raises(ValidationError):
        WaitlistJoinCreate(
            move_in_date=date(2026, 9, 1),
            move_out_date=date(2026, 9, 15),
            occupant_count=1,
        )

    print("test_waitlist_join_short_stay PASSED")


def test_waitlist_join_two_people():

    waitlist = WaitlistJoinCreate(
        move_in_date=date(2026, 9, 1),
        move_out_date=date(2026, 10, 5),
        occupant_count=2,
        extra_occupant_name="Mary",
        extra_occupant_email="mary@test.com",
        extra_occupant_student_id="TP123456",
        extra_occupant_gender="Female",
    )

    assert waitlist.occupant_count == 2

    print("test_waitlist_join_two_people PASSED")


def test_waitlist_join_missing_second_person():

    with pytest.raises(ValidationError):
        WaitlistJoinCreate(
            move_in_date=date(2026, 9, 1),
            move_out_date=date(2026, 10, 5),
            occupant_count=2,
        )

    print("test_waitlist_join_missing_second_person PASSED")


# ==========================================================
# MaintenanceUpdate
# ==========================================================


def test_maintenance_update_valid():

    update = MaintenanceUpdate(
        status="completed",
        priority="High",
        assigned_staff="Ali",
        remarks="Completed",
    )

    assert update.status == "completed"

    print("test_maintenance_update_valid PASSED")


def test_maintenance_update_invalid_status():

    with pytest.raises(ValidationError):
        MaintenanceUpdate(
            status="done",
        )

    print("test_maintenance_update_invalid_status PASSED")


def test_maintenance_update_invalid_priority():

    with pytest.raises(ValidationError):
        MaintenanceUpdate(
            priority="Urgent",
        )

    print("test_maintenance_update_invalid_priority PASSED")


# ==========================================================
# VisitorRequestCreate
# ==========================================================


def test_visitor_request_valid():

    visitor = VisitorRequestCreate(
        visitor_name="John Tan",
        visitor_email="john@test.com",
        visitor_relationship="Friend",
        visitor_phone="0123456789",
        visit_date=date(2026, 9, 1),
        visit_time=time(10, 0),
    )

    assert visitor.visitor_name == "John Tan"

    print("test_visitor_request_valid PASSED")


def test_visitor_request_invalid_time():

    with pytest.raises(ValidationError):
        VisitorRequestCreate(
            visitor_name="John",
            visitor_email="john@test.com",
            visitor_relationship="Friend",
            visitor_phone="0123456789",
            visit_date=date(2026, 9, 1),
            visit_time=time(23, 0),
        )

    print("test_visitor_request_invalid_time PASSED")


def test_visitor_request_invalid_name():

    with pytest.raises(ValidationError):
        VisitorRequestCreate(
            visitor_name="John123",
            visitor_email="john@test.com",
            visitor_relationship="Friend",
            visitor_phone="0123456789",
            visit_date=date(2026, 9, 1),
            visit_time=time(10, 0),
        )

    print("test_visitor_request_invalid_name PASSED")


def test_visitor_request_invalid_phone():

    with pytest.raises(ValidationError):
        VisitorRequestCreate(
            visitor_name="John",
            visitor_email="john@test.com",
            visitor_relationship="Friend",
            visitor_phone="ABC123",
            visit_date=date(2026, 9, 1),
            visit_time=time(10, 0),
        )

    print("test_visitor_request_invalid_phone PASSED")


# ==========================================================
# Simple Output Models
# ==========================================================


def test_room_out():

    room = RoomOut(
        id=1,
        block_name="Block A",
        level=1,
        room_number="101",
        room_type="Single Room",
        capacity=1,
        is_available=True,
        gender_policy="Male only",
        fee_monthly=120,
        photo_url=None,
    )

    assert room.room_number == "101"

    print("test_room_out PASSED")


def test_booking_out():

    room = RoomOut(
        id=1,
        block_name="Block A",
        level=1,
        room_number="101",
        room_type="Single Room",
        capacity=1,
        is_available=True,
        gender_policy="Male only",
        fee_monthly=120,
        photo_url=None,
    )

    booking = BookingOut(
        id=1,
        status="pending",
        semester="Semester 1",
        move_in_date=date(2026, 9, 1),
        move_out_date=date(2026, 10, 5),
        requested_at=datetime.now(UTC),
        occupant_count=1,
        total_fee=120,
        room=room,
    )

    assert booking.total_fee == 120

    assert booking.room.room_number == "101"

    print("test_booking_out PASSED")


def test_maintenance_out():

    maintenance = MaintenanceOut(
        id=1,
        title="Broken Fan",
        category="Electrical",
        priority="High",
        status="pending",
        photo_url=None,
        assigned_staff=None,
        remarks=None,
        room_label="Block A · Room 101",
        student_name="John Tan",
        student_id="TP123456",
        created_at=datetime.now(UTC),
        completed_at=None,
    )

    assert maintenance.title == "Broken Fan"

    print("test_maintenance_out PASSED")


# ==========================================================
# Constants
# ==========================================================


def test_room_types_constant():

    assert "Single Room" in ROOM_TYPES
    assert "Master Room" in ROOM_TYPES
    assert len(ROOM_TYPES) == 4

    print("test_room_types_constant PASSED")


def test_maintenance_statuses_constant():

    assert "pending" in MAINTENANCE_STATUSES
    assert "completed" in MAINTENANCE_STATUSES

    print("test_maintenance_statuses_constant PASSED")


def test_min_stay_days_constant():

    assert MIN_STAY_DAYS == 30

    print("test_min_stay_days_constant PASSED")


def test_extra_person_fee_constant():

    from agile_ci_demo.models import EXTRA_PERSON_FEE

    assert EXTRA_PERSON_FEE == 50.0

    print("test_extra_person_fee_constant PASSED")
