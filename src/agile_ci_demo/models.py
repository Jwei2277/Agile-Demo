from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, model_validator

# Condo-style room categories. "Single Room" always houses 1 person;
# every other type can hold up to 2 (the second occupant costs extra).
ROOM_TYPES = ("Single Room", "Master Room", "Balcony Room", "Middle Room")
RoomType = Literal["Single Room", "Master Room", "Balcony Room", "Middle Room"]

# Flat surcharge for the second occupant in a room, charged on top of
# the room's base monthly fee.
EXTRA_PERSON_FEE = 50.0


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
    occupant_count: int = Field(default=1, ge=1, le=2)
    extra_occupant_name: str | None = Field(default=None, min_length=1)
    extra_occupant_email: EmailStr | None = None
    extra_occupant_student_id: str | None = Field(default=None, pattern=r"^[A-Z]{2}\d{6}$")
    extra_occupant_gender: str | None = Field(default=None, pattern=r"^(Male|Female)$")

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
            # Ignore any stray extra-occupant details sent for a solo booking.
            self.extra_occupant_name = None
            self.extra_occupant_email = None
            self.extra_occupant_student_id = None
            self.extra_occupant_gender = None
        return self


class BookingOut(BaseModel):
    id: int
    status: str
    semester: str
    requested_at: datetime
    decided_at: datetime | None = None
    occupant_count: int
    extra_occupant_name: str | None = None
    extra_occupant_email: str | None = None
    extra_occupant_student_id: str | None = None
    extra_occupant_gender: str | None = None
    total_fee: float
    room: RoomOut


class BookingAdminOut(BaseModel):
    id: int
    status: str
    semester: str
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
    created_at: datetime
    student_name: str | None = None


class DashboardStats(BaseModel):
    available_rooms: int
    occupied_rooms: int
    total_rooms: int
    pending_bookings: int
    pending_maintenance: int
    occupancy_pct: float


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
