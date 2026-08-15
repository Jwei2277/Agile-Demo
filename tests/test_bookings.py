from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import get_current_user, CurrentUser

client = TestClient(app)


# ============================================================
# TEST USER
# ============================================================

STUDENT = CurrentUser(
    id="student-001",
    email="student@test.com",
    full_name="John Tan",
    student_id="TP123456",
    gender="Male",
    role="student",
)


def override_student():
    return STUDENT


# ============================================================
# CLEANUP
# ============================================================


def setup_function():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_student


def teardown_function():
    app.dependency_overrides.clear()


# ============================================================
# FAKE SUPABASE
# ============================================================


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self.data = list(db.tables.get(table_name, []))
        self.operation = None
        self.payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.data = [row for row in self.data if row.get(column) == value]
        return self

    def neq(self, column, value):
        self.data = [row for row in self.data if row.get(column) != value]
        return self

    def in_(self, column, values):
        self.data = [row for row in self.data if row.get(column) in values]
        return self

    def is_(self, column, value):
        if value == "null":
            self.data = [row for row in self.data if row.get(column) is None]

        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, number):
        self.data = self.data[:number]
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def execute(self):
        table = self.db.tables.setdefault(
            self.table_name,
            [],
        )

        if self.operation == "insert":
            row = dict(self.payload)

            if "id" not in row:
                row["id"] = self.db.next_id(self.table_name)

            table.append(row)

            return FakeResponse([row])

        if self.operation == "update":
            for original in table:
                if original in self.data:
                    original.update(self.payload)

            return FakeResponse(self.data)

        if self.operation == "delete":
            for original in list(table):
                if original in self.data:
                    table.remove(original)

            return FakeResponse([])

        return FakeResponse(self.data)


class FakeDB:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, name):
        return FakeQuery(self, name)

    def next_id(self, table_name):
        rows = self.tables.get(
            table_name,
            [],
        )

        if not rows:
            return 1

        return max(int(row.get("id", 0)) for row in rows) + 1


# ============================================================
# FIXTURES
# ============================================================


def room():
    return {
        "id": 1,
        "block_id": 1,
        "level": 1,
        "room_number": "101",
        "room_type": "Single Room",
        "capacity": 1,
        "gender_policy": "Mixed",
        "fee_monthly": 500.0,
        "photo_url": None,
        "is_active": True,
        "hostel_blocks": {
            "id": 1,
            "name": "Block A",
        },
    }


def booking(
    booking_id=1,
    status="pending",
):
    return {
        "id": booking_id,
        "student_id": "student-001",
        "room_id": 1,
        "status": status,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-31",
        "occupant_count": 1,
        "extra_occupant_name": None,
        "extra_occupant_email": None,
        "extra_occupant_student_id": None,
        "extra_occupant_gender": None,
        "requested_at": ("2026-08-15T10:00:00+00:00"),
        "decided_at": None,
        "checked_in_at": None,
        "checked_out_at": None,
    }


# ============================================================
# LIST BOOKINGS
# ============================================================


# ============================================================
# GET BOOKING
# ============================================================


# ============================================================
# CREATE BOOKING
# ============================================================


def test_create_booking_invalid_date_range(
    monkeypatch,
):
    fake = FakeDB(
        {
            "rooms": [room()],
            "bookings": [],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    payload = {
        "room_id": 1,
        "semester": "Semester 1",
        "move_in_date": "2027-01-31",
        "move_out_date": "2026-09-01",
        "occupant_count": 1,
    }

    response = client.post(
        "/bookings",
        json=payload,
    )

    assert response.status_code in (
        400,
        422,
    )


def test_create_booking_invalid_occupant_count(
    monkeypatch,
):
    fake = FakeDB(
        {
            "rooms": [room()],
            "bookings": [],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    payload = {
        "room_id": 1,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-31",
        "occupant_count": 0,
    }

    response = client.post(
        "/bookings",
        json=payload,
    )

    assert response.status_code in (
        400,
        422,
    )


# ============================================================
# DUPLICATE BOOKING
# ============================================================


def test_student_cannot_create_duplicate_booking(
    monkeypatch,
):
    fake = FakeDB(
        {
            "rooms": [room()],
            "bookings": [booking(status="pending")],
        }
    )

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    payload = {
        "room_id": 1,
        "semester": "Semester 1",
        "move_in_date": "2026-09-01",
        "move_out_date": "2027-01-31",
        "occupant_count": 1,
    }

    response = client.post(
        "/bookings",
        json=payload,
    )

    assert response.status_code in (
        400,
        409,
    )


# ============================================================
# CANCEL BOOKING
# ============================================================


def test_cancel_booking_not_found(
    monkeypatch,
):
    fake = FakeDB({"bookings": []})

    monkeypatch.setattr(
        "agile_ci_demo.bookings.supabase_admin",
        fake,
    )

    response = client.post("/bookings/999/cancel")

    assert response.status_code == 404


# ============================================================
# CANCELLATION REQUEST
# ============================================================


# ============================================================
# ROOM AVAILABILITY
# ============================================================


# ============================================================
# UNAUTHENTICATED ACCESS
# ============================================================


# ============================================================
# INVALID BOOKING ID
# ============================================================
