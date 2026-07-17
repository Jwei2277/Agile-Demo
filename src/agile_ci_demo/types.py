from typing import TypedDict


class RoomRow(TypedDict):
    id: int
    room_number: str
    capacity: int
    available: bool


class BookingRow(TypedDict):
    id: int
    student_id: str
    room_id: int
