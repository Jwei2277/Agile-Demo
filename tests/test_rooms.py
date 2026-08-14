from fastapi.testclient import TestClient

import pytest

from agile_ci_demo.app import app
from agile_ci_demo.rooms import _booked_room_ids, _room_to_out

client = TestClient(app)


# ============================================================
# Fake Response
# ============================================================


class FakeResponse:
    def __init__(self, data):
        self.data = data


# ============================================================
# Fake Query
# ============================================================


class FakeQuery:
    def __init__(self, table):
        self.table = table
        self.data = list(table)

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        self.data = [row for row in self.data if row.get(column) == value]
        return self

    def in_(self, column, values):
        self.data = [row for row in self.data if row.get(column) in values]
        return self

    def is_(self, column, value):
        if value == "null":
            self.data = [row for row in self.data if row.get(column) is None]
        return self

    def limit(self, number):
        self.data = self.data[:number]
        return self

    def execute(self):
        return FakeResponse(self.data)


# ============================================================
# Fake Supabase
# ============================================================


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "rooms": [
                {
                    "id": 1,
                    "level": 1,
                    "room_number": "101",
                    "room_type": "Single Room",
                    "capacity": 1,
                    "gender_policy": "Male only",
                    "fee_monthly": 120.0,
                    "photo_url": None,
                    "is_active": True,
                    "hostel_blocks": {
                        "name": "Block A",
                    },
                },
                {
                    "id": 2,
                    "level": 2,
                    "room_number": "201",
                    "room_type": "Master Room",
                    "capacity": 2,
                    "gender_policy": "Female only",
                    "fee_monthly": 200.0,
                    "photo_url": "https://example.com/201.jpg",
                    "is_active": True,
                    "hostel_blocks": {
                        "name": "Block B",
                    },
                },
                {
                    "id": 3,
                    "level": 3,
                    "room_number": "301",
                    "room_type": "Balcony Room",
                    "capacity": 2,
                    "gender_policy": "Mixed block",
                    "fee_monthly": 250.0,
                    "photo_url": None,
                    "is_active": True,
                    "hostel_blocks": {
                        "name": "Block A",
                    },
                },
                {
                    "id": 4,
                    "level": 4,
                    "room_number": "401",
                    "room_type": "Middle Room",
                    "capacity": 2,
                    "gender_policy": "Mixed block",
                    "fee_monthly": 180.0,
                    "photo_url": None,
                    "is_active": False,
                    "hostel_blocks": {
                        "name": "Block C",
                    },
                },
            ],
            "bookings": [
                {
                    "room_id": 1,
                    "status": "approved",
                    "checked_out_at": None,
                },
            ],
        }

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


# ============================================================
# Cleanup
# ============================================================


@pytest.fixture(autouse=True)
def cleanup():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


# ============================================================
# List Rooms
# ============================================================


def test_list_rooms(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms")

    assert response.status_code == 200

    data = response.json()

    # Only active rooms should be returned.
    assert len(data) == 3

    room_numbers = [room["room_number"] for room in data]

    assert "101" in room_numbers
    assert "201" in room_numbers
    assert "301" in room_numbers
    assert "401" not in room_numbers

    print("list rooms - PASSED")


def test_list_rooms_response_fields(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms")

    assert response.status_code == 200

    room = response.json()[0]

    assert "id" in room
    assert "block_name" in room
    assert "level" in room
    assert "room_number" in room
    assert "room_type" in room
    assert "capacity" in room
    assert "is_available" in room
    assert "gender_policy" in room
    assert "fee_monthly" in room
    assert "photo_url" in room

    print("list rooms response fields - PASSED")


def test_list_rooms_booked_room_is_unavailable(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms")

    assert response.status_code == 200

    rooms = response.json()

    room_101 = next(room for room in rooms if room["room_number"] == "101")

    assert room_101["is_available"] is False

    print("booked room unavailable - PASSED")


def test_list_rooms_unbooked_room_is_available(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms")

    assert response.status_code == 200

    rooms = response.json()

    room_201 = next(room for room in rooms if room["room_number"] == "201")

    assert room_201["is_available"] is True

    print("unbooked room available - PASSED")


# ============================================================
# Gender Filter
# ============================================================


def test_list_rooms_gender_male(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={"gender": "Male only"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["gender_policy"] == "Male only"
    assert data[0]["room_number"] == "101"

    print("gender filter male - PASSED")


def test_list_rooms_gender_female(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={"gender": "Female only"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["gender_policy"] == "Female only"
    assert data[0]["room_number"] == "201"

    print("gender filter female - PASSED")


def test_list_rooms_gender_mixed(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={"gender": "Mixed block"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["gender_policy"] == "Mixed block"
    assert data[0]["room_number"] == "301"

    print("gender filter mixed - PASSED")


def test_list_rooms_gender_no_match(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={"gender": "Unknown"},
    )

    assert response.status_code == 200
    assert response.json() == []

    print("gender filter no match - PASSED")


# ============================================================
# Room Type Filter
# ============================================================


@pytest.mark.parametrize(
    "room_type, expected_room",
    [
        ("Single Room", "101"),
        ("Master Room", "201"),
        ("Balcony Room", "301"),
    ],
)
def test_list_rooms_room_type(
    monkeypatch,
    room_type,
    expected_room,
):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={"room_type": room_type},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["room_type"] == room_type
    assert data[0]["room_number"] == expected_room

    print(f"room type {room_type} - PASSED")


def test_list_rooms_room_type_no_match(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={"room_type": "Unknown Room"},
    )

    assert response.status_code == 200
    assert response.json() == []

    print("room type no match - PASSED")


# ============================================================
# Block Filter
# ============================================================


def test_list_rooms_block_a(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={"block": "Block A"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert all(room["block_name"] == "Block A" for room in data)

    print("block A filter - PASSED")


def test_list_rooms_block_b(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={"block": "Block B"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["room_number"] == "201"
    assert data[0]["block_name"] == "Block B"

    print("block B filter - PASSED")


def test_list_rooms_block_no_match(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={"block": "Block Z"},
    )

    assert response.status_code == 200
    assert response.json() == []

    print("block no match - PASSED")


# ============================================================
# Available Only
# ============================================================


def test_list_rooms_only_available(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={"only_available": True},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert all(room["is_available"] is True for room in data)

    room_numbers = {room["room_number"] for room in data}

    assert room_numbers == {"201", "301"}

    print("only available rooms - PASSED")


def test_list_rooms_only_available_with_gender_filter(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get(
        "/rooms",
        params={
            "gender": "Mixed block",
            "only_available": True,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["room_number"] == "301"
    assert data[0]["is_available"] is True

    print("available rooms combined filter - PASSED")


# ============================================================
# Empty Database
# ============================================================


def test_list_rooms_no_rooms(monkeypatch):
    fake = FakeSupabase()

    fake.tables["rooms"] = []

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms")

    assert response.status_code == 200
    assert response.json() == []

    print("list rooms empty database - PASSED")


def test_list_rooms_no_bookings(monkeypatch):
    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 3

    assert all(room["is_available"] is True for room in data)

    print("list rooms no bookings - PASSED")


# ============================================================
# Supabase Missing
# ============================================================


def test_list_rooms_service_role_missing(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        None,
    )

    response = client.get("/rooms")

    assert response.status_code == 501
    assert response.json()["detail"] == "Server misconfigured: missing service role key"

    print("list rooms service role missing - PASSED")


def test_get_room_service_role_missing(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        None,
    )

    response = client.get("/rooms/1")

    assert response.status_code == 501
    assert response.json()["detail"] == "Server misconfigured: missing service role key"

    print("get room service role missing - PASSED")


# ============================================================
# Get Room
# ============================================================


def test_get_room(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms/1")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["block_name"] == "Block A"
    assert data["level"] == 1
    assert data["room_number"] == "101"
    assert data["room_type"] == "Single Room"
    assert data["capacity"] == 1
    assert data["gender_policy"] == "Male only"
    assert data["fee_monthly"] == 120.0
    assert data["is_available"] is False

    print("get room - PASSED")


def test_get_room_with_photo(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms/2")

    assert response.status_code == 200

    data = response.json()

    assert data["photo_url"] == "https://example.com/201.jpg"

    print("get room with photo - PASSED")


def test_get_room_not_found(monkeypatch):
    fake = FakeSupabase()

    fake.tables["rooms"] = []

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Room not found"

    print("get room not found - PASSED")


def test_get_room_second_room(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms/2")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 2
    assert data["room_number"] == "201"
    assert data["room_type"] == "Master Room"
    assert data["capacity"] == 2
    assert data["is_available"] is True

    print("get second room - PASSED")


# ============================================================
# _room_to_out()
# ============================================================


def make_room():
    return {
        "id": 10,
        "level": 2,
        "room_number": "205",
        "room_type": "Master Room",
        "capacity": 2,
        "gender_policy": "Mixed block",
        "fee_monthly": 220.0,
        "photo_url": "https://example.com/205.jpg",
        "hostel_blocks": {
            "name": "Block B",
        },
    }


def test_room_to_out_available():
    room = _room_to_out(
        make_room(),
        set(),
    )

    assert room.id == 10
    assert room.block_name == "Block B"
    assert room.level == 2
    assert room.room_number == "205"
    assert room.room_type == "Master Room"
    assert room.capacity == 2
    assert room.gender_policy == "Mixed block"
    assert room.fee_monthly == 220.0
    assert room.photo_url == "https://example.com/205.jpg"
    assert room.is_available is True

    print("room to out available - PASSED")


def test_room_to_out_booked():
    room = _room_to_out(
        make_room(),
        {10},
    )

    assert room.is_available is False

    print("room to out booked - PASSED")


def test_room_to_out_multiple_booked_rooms():
    room = _room_to_out(
        make_room(),
        {1, 5, 10, 20},
    )

    assert room.is_available is False

    print("room to out multiple booked rooms - PASSED")


def test_room_to_out_missing_block():
    room_data = make_room()
    room_data["hostel_blocks"] = None

    room = _room_to_out(
        room_data,
        set(),
    )

    assert room.block_name == "Unknown block"

    print("room to out missing block - PASSED")


def test_room_to_out_missing_photo():
    room_data = make_room()
    room_data["photo_url"] = None

    room = _room_to_out(
        room_data,
        set(),
    )

    assert room.photo_url is None

    print("room to out missing photo - PASSED")


# ============================================================
# _booked_room_ids()
# ============================================================


def test_booked_room_ids(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    result = _booked_room_ids()

    assert result == {1}

    print("booked room IDs - PASSED")


def test_booked_room_ids_no_supabase(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        None,
    )

    result = _booked_room_ids()

    assert result == set()

    print("booked room IDs without Supabase - PASSED")


def test_booked_room_ids_multiple_bookings(monkeypatch):
    fake = FakeSupabase()

    fake.tables["bookings"] = [
        {
            "room_id": 1,
            "status": "approved",
            "checked_out_at": None,
        },
        {
            "room_id": 2,
            "status": "pending",
            "checked_out_at": None,
        },
        {
            "room_id": 3,
            "status": "approved",
            "checked_out_at": None,
        },
    ]

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    result = _booked_room_ids()

    assert result == {1, 2, 3}

    print("booked room IDs multiple bookings - PASSED")


def test_booked_room_ids_empty(monkeypatch):
    fake = FakeSupabase()

    fake.tables["bookings"] = []

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    result = _booked_room_ids()

    assert result == set()

    print("booked room IDs empty - PASSED")


# ============================================================
# Booking Status / Checkout Behavior
# ============================================================


def test_checked_out_booking_does_not_make_room_unavailable(
    monkeypatch,
):
    fake = FakeSupabase()

    fake.tables["bookings"] = [
        {
            "room_id": 1,
            "status": "approved",
            "checked_out_at": "2026-08-01T10:00:00Z",
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    result = _booked_room_ids()

    assert result == set()

    print("checked out booking does not block room - PASSED")


def test_pending_booking_blocks_room(monkeypatch):
    fake = FakeSupabase()

    fake.tables["bookings"] = [
        {
            "room_id": 2,
            "status": "pending",
            "checked_out_at": None,
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    result = _booked_room_ids()

    assert result == {2}

    print("pending booking blocks room - PASSED")


def test_approved_booking_blocks_room(monkeypatch):
    fake = FakeSupabase()

    fake.tables["bookings"] = [
        {
            "room_id": 3,
            "status": "approved",
            "checked_out_at": None,
        }
    ]

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    result = _booked_room_ids()

    assert result == {3}

    print("approved booking blocks room - PASSED")
