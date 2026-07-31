import re
from datetime import date, datetime, time
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, model_validator

# Condo-style room categories. "Single Room" always houses 1 person;
# every other type can hold up to 2 (the second occupant costs extra).
ROOM_TYPES = ("Single Room", "Master Room", "Balcony Room", "Middle Room")
RoomType = Literal["Single Room", "Master Room", "Balcony Room", "Middle Room"]

# Flat surcharge for the second occupant in a room, charged on top of
# the room's base monthly fee.
EXTRA_PERSON_FEE = 50.0

# Every booking must run for at least this many days (~1 month).
MIN_STAY_DAYS = 30


def total_fee_for(base_fee: float, occupant_count: int) -> float:
    return base_fee + EXTRA_PERSON_FEE * max(occupant_count - 1, 0)


class RoomOut(BaseModel):
    id: int
    block_name: str
    level: int
    room_number: str
    room_type: str
    capacity: int  # max occupants this room can hold under one booking
    is_available: bool
    gender_policy: str
    fee_monthly: float  # base fee for 1 occupant
    photo_url: str | None = None


class BookingCreate(BaseModel):
    room_id: int
    semester: str = Field(min_length=1)
    move_in_date: date
    move_out_date: date
    occupant_count: int = Field(default=1, ge=1, le=2)
    extra_occupant_name: str | None = Field(default=None, min_length=1)
    extra_occupant_email: EmailStr | None = None
    extra_occupant_student_id: str | None = Field(default=None, pattern=r"^[A-Z]{2}\d{6}$")
    extra_occupant_gender: str | None = Field(default=None, pattern=r"^(Male|Female)$")

    @model_validator(mode="after")
    def _require_extra_occupant_details(self):
        if (self.move_out_date - self.move_in_date).days < MIN_STAY_DAYS:
            raise ValueError(
                f"Bookings must run for at least {MIN_STAY_DAYS} days (about 1 month)."
            )
        if self.occupant_count == 2:
            missing = [
                label
                for label, value in (
                    ("extra_occupant_name", self.extra_occupant_name),
                    ("extra_occupant_email", self.extra_occupant_email),
                    ("extra_occupant_student_id", self.extra_occupant_student_id),
                    ("extra_occupant_gender", self.extra_occupant_gender),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"2nd occupant's full name, email, student ID, and gender are all required: missing {', '.join(missing)}"
                )
        if self.occupant_count == 1:
            # Ignore any stray extra-occupant details sent for a solo booking.
            self.extra_occupant_name = None
            self.extra_occupant_email = None
            self.extra_occupant_student_id = None
            self.extra_occupant_gender = None
        return self


class BookingUpdate(BaseModel):
    room_id: int | None = None
    move_in_date: date | None = None
    move_out_date: date | None = None
    occupant_count: int = Field(default=1, ge=1, le=2)
    extra_occupant_name: str | None = Field(default=None, min_length=1)
    extra_occupant_email: EmailStr | None = None
    extra_occupant_student_id: str | None = Field(default=None, pattern=r"^[A-Z]{2}\d{6}$")
    extra_occupant_gender: str | None = Field(default=None, pattern=r"^(Male|Female)$")

    @model_validator(mode="after")
    def _validate_dates(self):
        if (self.move_in_date is None) != (self.move_out_date is None):
            raise ValueError("Provide both move_in_date and move_out_date together, or neither.")
        if self.move_in_date and self.move_out_date:
            if (self.move_out_date - self.move_in_date).days < MIN_STAY_DAYS:
                raise ValueError(
                    f"Bookings must run for at least {MIN_STAY_DAYS} days (about 1 month)."
                )
        return self

    @model_validator(mode="after")
    def _require_extra_occupant_details(self):
        if self.occupant_count == 2:
            missing = [
                label
                for label, value in (
                    ("extra_occupant_name", self.extra_occupant_name),
                    ("extra_occupant_email", self.extra_occupant_email),
                    ("extra_occupant_student_id", self.extra_occupant_student_id),
                    ("extra_occupant_gender", self.extra_occupant_gender),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"2nd occupant's full name, email, student ID, and gender are all required: missing {', '.join(missing)}"
                )
        if self.occupant_count == 1:
            self.extra_occupant_name = None
            self.extra_occupant_email = None
            self.extra_occupant_student_id = None
            self.extra_occupant_gender = None
        return self


class BookingOut(BaseModel):
    id: int
    status: str
    semester: str
    move_in_date: date
    move_out_date: date
    requested_at: datetime
    decided_at: datetime | None = None
    occupant_count: int
    extra_occupant_name: str | None = None
    extra_occupant_email: str | None = None
    extra_occupant_student_id: str | None = None
    extra_occupant_gender: str | None = None
    total_fee: float
    room: RoomOut
    pending_transfer_room: RoomOut | None = None


class BookingAdminOut(BaseModel):
    id: int
    status: str
    semester: str
    move_in_date: date
    move_out_date: date
    requested_at: datetime
    student_name: str
    student_id: str | None = None
    room_id: int
    room_label: str
    occupant_count: int
    extra_occupant_name: str | None = None
    extra_occupant_email: str | None = None
    extra_occupant_student_id: str | None = None
    extra_occupant_gender: str | None = None
    total_fee: float


class TransferRoomRequestCreate(BaseModel):
    room_id: int
    reason: str = Field(min_length=1)


class TransferRoomRequestOut(BaseModel):
    id: int
    booking_id: int
    requested_room_id: int
    reason: str
    status: str
    requested_at: datetime


class TransferRequestAdminOut(BaseModel):
    id: int
    booking_id: int
    student_name: str
    room_label: str
    requested_room_id: int
    requested_room_label: str
    reason: str
    status: str
    requested_at: datetime


class WaitlistJoinCreate(BaseModel):
    move_in_date: date
    move_out_date: date
    occupant_count: int = Field(default=1, ge=1, le=2)
    extra_occupant_name: str | None = Field(default=None, min_length=1)
    extra_occupant_email: EmailStr | None = None
    extra_occupant_student_id: str | None = Field(default=None, pattern=r"^[A-Z]{2}\d{6}$")
    extra_occupant_gender: str | None = Field(default=None, pattern=r"^(Male|Female)$")

    @model_validator(mode="after")
    def _validate(self):
        if (self.move_out_date - self.move_in_date).days < MIN_STAY_DAYS:
            raise ValueError(
                f"Bookings must run for at least {MIN_STAY_DAYS} days (about 1 month)."
            )
        if self.occupant_count == 2:
            missing = [
                label
                for label, value in (
                    ("extra_occupant_name", self.extra_occupant_name),
                    ("extra_occupant_email", self.extra_occupant_email),
                    ("extra_occupant_student_id", self.extra_occupant_student_id),
                    ("extra_occupant_gender", self.extra_occupant_gender),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"2nd occupant's full name, email, student ID, and gender are all required: missing {', '.join(missing)}"
                )
        if self.occupant_count == 1:
            self.extra_occupant_name = None
            self.extra_occupant_email = None
            self.extra_occupant_student_id = None
            self.extra_occupant_gender = None
        return self


class WaitlistEntryOut(BaseModel):
    id: int
    room_id: int
    room_label: str
    status: str
    queue_position: int
    occupant_count: int
    move_in_date: date
    move_out_date: date
    joined_at: datetime
    notified_at: datetime | None = None


class WaitlistEntryAdminOut(BaseModel):
    id: int
    room_id: int
    room_label: str
    student_name: str
    student_id: str | None = None
    status: str
    queue_position: int
    occupant_count: int
    move_in_date: date
    move_out_date: date
    joined_at: datetime
    notified_at: datetime | None = None


class MaintenanceCreate(BaseModel):
    title: str = Field(min_length=1)
    category: str = "General"
    priority: str = "Normal"
    room_id: int | None = None


class MaintenanceOut(BaseModel):
    id: int
    title: str
    category: str
    priority: str
    status: str
    photo_url: str | None = None
    assigned_staff: str | None = None
    remarks: str | None = None
    room_label: str | None = None
    student_name: str | None = None
    student_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


MAINTENANCE_STATUSES = ("pending", "assigned", "in_progress", "completed", "closed", "cancelled")


class MaintenanceUpdate(BaseModel):
    status: str | None = Field(
        default=None, pattern=r"^(pending|assigned|in_progress|completed|closed|cancelled)$"
    )
    priority: str | None = Field(default=None, pattern=r"^(Low|Normal|High)$")
    assigned_staff: str | None = None
    remarks: str | None = None
    completed_at: datetime | None = None


class DashboardStats(BaseModel):
    available_rooms: int
    occupied_rooms: int
    total_rooms: int
    pending_bookings: int
    pending_maintenance: int
    occupancy_pct: float
    bookings_by_status: dict[str, int]
    rooms_by_type: dict[str, int]


class BlockOut(BaseModel):
    id: int
    name: str


class RoomAdminOut(BaseModel):
    id: int
    block_id: int
    block_name: str
    level: int
    room_number: str
    room_type: str
    capacity: int
    is_booked: bool
    gender_policy: str
    fee_monthly: float
    photo_url: str | None = None
    is_active: bool
    waitlist_count: int = 0


class RoomCreate(BaseModel):
    block_id: int
    level: int
    room_number: str = Field(min_length=1)
    room_type: RoomType
    capacity: int = Field(gt=0, le=2)
    gender_policy: str
    fee_monthly: float = Field(gt=0)
    photo_url: str | None = None

    @model_validator(mode="after")
    def _single_room_capacity(self):
        if self.room_type == "Single Room" and self.capacity != 1:
            raise ValueError("Single Room must have capacity 1")
        return self


class RoomUpdate(BaseModel):
    level: int | None = None
    room_type: RoomType | None = None
    capacity: int | None = Field(default=None, gt=0, le=2)
    gender_policy: str | None = None
    fee_monthly: float | None = Field(default=None, gt=0)
    photo_url: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _single_room_capacity(self):
        if self.room_type == "Single Room" and self.capacity is not None and self.capacity != 1:
            raise ValueError("Single Room must have capacity 1")
        return self


VISITOR_RELATIONSHIPS = ("Parent/Guardian", "Sibling", "Relative", "Friend", "Other")
VISIT_HOURS_START = time(8, 0)
VISIT_HOURS_END = time(22, 0)


class VisitorRequestCreate(BaseModel):
    visitor_name: str = Field(min_length=1)
    visitor_email: EmailStr
    visitor_relationship: str = Field(min_length=1)
    visitor_phone: str = Field(min_length=1)
    visit_date: date
    visit_time: time

    @model_validator(mode="after")
    def _validate_visit_time(self):
        if not (VISIT_HOURS_START <= self.visit_time <= VISIT_HOURS_END):
            raise ValueError("Visiting hours are 8:00 AM to 10:00 PM.")
        return self

    @model_validator(mode="after")
    def _validate_name(self):
        if not re.fullmatch(r"[A-Za-z ]+", self.visitor_name.strip()):
            raise ValueError(
                "Visitor name can only contain letters and spaces — no numbers or symbols."
            )
        return self

    @model_validator(mode="after")
    def _validate_phone(self):
        if not re.fullmatch(r"\d{10,11}", self.visitor_phone.strip()):
            raise ValueError("Visitor phone number must be 10-11 digits, numbers only.")
        return self


class VisitorRequestOut(BaseModel):
    id: int
    visitor_name: str
    visitor_email: str
    visitor_relationship: str
    visitor_phone: str
    visit_date: date
    visit_time: time
    status: str
    rejection_reason: str | None = None
    requested_at: datetime
    decided_at: datetime | None = None


class VisitorRequestAdminOut(BaseModel):
    id: int
    visitor_name: str
    visitor_email: str
    visitor_relationship: str
    visitor_phone: str
    visit_date: date
    visit_time: time
    status: str
    rejection_reason: str | None = None
    requested_at: datetime
    decided_at: datetime | None = None
    student_name: str
    student_id: str | None = None
    student_email: str | None = None


class VisitorRejectRequest(BaseModel):
    reason: str = Field(min_length=1)
