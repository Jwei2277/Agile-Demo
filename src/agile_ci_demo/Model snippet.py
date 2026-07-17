from pydantic import BaseModel

# Add this class to agile_ci_demo/models.py, near BookingCreate.
# Same shape as BookingCreate but without semester (semester doesn't
# change on an edit — cancel and rebook if that's needed). room_id is
# optional: omit it (or send the same id) to keep the current room and
# only change occupant details; send a different id to transfer rooms.


class BookingUpdate(BaseModel):
    room_id: int | None = None
    occupant_count: int = 1
    extra_occupant_name: str | None = None
    extra_occupant_email: str | None = None
    extra_occupant_student_id: str | None = None
    extra_occupant_gender: str | None = None
