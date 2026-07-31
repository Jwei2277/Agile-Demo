from fastapi.testclient import TestClient
import pytest

from agile_ci_demo.app import app

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

        self.data = table

    def select(self, *args):

        return self

    def eq(self, column, value):

        self.data = [row for row in self.data if row.get(column) == value]

        return self

    def in_(self, column, values):

        self.data = [row for row in self.data if row.get(column) in values]

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
                    "fee_monthly": 120,
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
                    "fee_monthly": 200,
                    "photo_url": None,
                    "is_active": True,
                    "hostel_blocks": {
                        "name": "Block B",
                    },
                },
            ],
            "bookings": [
                {
                    "room_id": 1,
                    "status": "approved",
                }
            ],
        }

    def table(self, name):

        return FakeQuery(self.tables.get(name, []))


# ============================================================
# Cleanup
# ============================================================


@pytest.fixture(autouse=True)
def cleanup():

    yield


# ============================================================
# List Rooms Tests
# ============================================================


def test_list_rooms(monkeypatch):
    """
    List all active rooms.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["room_number"] == "101"

    print("test_list_rooms PASSED")


def test_list_rooms_gender(monkeypatch):
    """
    Filter rooms by gender.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms?gender=Male%20only")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["gender_policy"] == "Male only"

    print("test_list_rooms_gender PASSED")


def test_list_rooms_room_type(monkeypatch):
    """
    Filter by room type.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms?room_type=Master%20Room")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["room_type"] == "Master Room"

    print("test_list_rooms_room_type PASSED")


def test_list_rooms_block(monkeypatch):
    """
    Filter by hostel block.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms?block=Block%20A")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["block_name"] == "Block A"

    print("test_list_rooms_block PASSED")


def test_list_rooms_available_only(monkeypatch):
    """
    Show only available rooms.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms?only_available=true")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["room_number"] == "201"

    assert data[0]["is_available"] is True

    print("test_list_rooms_available_only PASSED")


def test_list_rooms_none(monkeypatch):
    """
    No rooms available.
    """

    fake = FakeSupabase()

    fake.tables["rooms"] = []

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms")

    assert response.status_code == 200

    assert response.json() == []

    print("test_list_rooms_none PASSED")


def test_list_rooms_service_role_missing(monkeypatch):
    """
    Missing service role client.
    """

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        None,
    )

    response = client.get("/rooms")

    assert response.status_code == 501

    print("test_list_rooms_service_role_missing PASSED")


# ============================================================
# Get Room Tests
# ============================================================


def test_get_room(monkeypatch):
    """
    Get room details.
    """

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms/1")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["room_number"] == "101"

    print("test_get_room PASSED")


def test_get_room_not_found(monkeypatch):
    """
    Room does not exist.
    """

    fake = FakeSupabase()

    fake.tables["rooms"] = []

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    response = client.get("/rooms/99")

    assert response.status_code == 404

    print("test_get_room_not_found PASSED")


def test_get_room_service_role_missing(monkeypatch):
    """
    Missing service role client.
    """

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        None,
    )

    response = client.get("/rooms/1")

    assert response.status_code == 501

    print("test_get_room_service_role_missing PASSED")


# ============================================================
# _room_to_out()
# ============================================================


def test_room_to_out():
    """
    Convert database row to RoomOut.
    """

    from agile_ci_demo.rooms import _room_to_out

    row = {
        "id": 1,
        "level": 1,
        "room_number": "101",
        "room_type": "Single Room",
        "capacity": 1,
        "gender_policy": "Male only",
        "fee_monthly": 120,
        "photo_url": None,
        "hostel_blocks": {
            "name": "Block A",
        },
    }

    room = _room_to_out(
        row,
        set(),
    )

    assert room.room_number == "101"
    assert room.block_name == "Block A"
    assert room.is_available is True

    print("test_room_to_out PASSED")


def test_room_to_out_booked():
    """
    Booked room should not be available.
    """

    from agile_ci_demo.rooms import _room_to_out

    row = {
        "id": 1,
        "level": 1,
        "room_number": "101",
        "room_type": "Single Room",
        "capacity": 1,
        "gender_policy": "Male only",
        "fee_monthly": 120,
        "photo_url": None,
        "hostel_blocks": {
            "name": "Block A",
        },
    }

    room = _room_to_out(
        row,
        {1},
    )

    assert room.is_available is False

    print("test_room_to_out_booked PASSED")


# ============================================================
# _booked_room_ids()
# ============================================================


def test_booked_room_ids(monkeypatch):
    """
    Return booked room IDs.
    """

    from agile_ci_demo.rooms import _booked_room_ids

    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        fake,
    )

    booked = _booked_room_ids()

    assert booked == {1}

    print("test_booked_room_ids PASSED")


def test_booked_room_ids_none(monkeypatch):
    """
    Supabase unavailable.
    """

    from agile_ci_demo.rooms import _booked_room_ids

    monkeypatch.setattr(
        "agile_ci_demo.rooms.supabase_admin",
        None,
    )

    booked = _booked_room_ids()

    assert booked == set()

    print("test_booked_room_ids_none PASSED")
