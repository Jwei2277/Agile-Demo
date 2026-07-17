from fastapi.testclient import TestClient

from agile_ci_demo.app import app

client = TestClient(app)


# ==========================
# Fake Supabase
# ==========================


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:

    def __init__(self, table_data):
        self.data = table_data

    def select(self, *args):
        return self

    def eq(self, column, value):
        self.data = [item for item in self.data if item.get(column) == value]

        return self

    def in_(self, column, values):
        self.data = [item for item in self.data if item.get(column) in values]

        return self

    def limit(self, number):
        self.data = self.data[:number]

        return self

    def execute(self):
        return FakeResponse(self.data)


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
                    "gender_policy": "Female only",
                    "fee_monthly": 100,
                    "is_active": True,
                    "hostel_blocks": {"name": "Block A"},
                    "photo_url": None,
                },
                {
                    "id": 2,
                    "level": 2,
                    "room_number": "202",
                    "room_type": "Master Room",
                    "capacity": 2,
                    "gender_policy": "Mixed block",
                    "fee_monthly": 200,
                    "is_active": True,
                    "hostel_blocks": {"name": "Block B"},
                    "photo_url": None,
                },
            ],
            "bookings": [{"room_id": 2, "status": "approved"}],
        }

    def table(self, name):

        return FakeQuery(self.tables.get(name, []))


# ==========================
# Tests
# ==========================


def test_get_all_rooms(monkeypatch):
    """
    Get all available rooms
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.rooms.supabase_admin", fake)

    response = client.get("/rooms")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["room_number"] == "101"


def test_get_room_by_id(monkeypatch):
    """
    Get room details using valid room ID
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.rooms.supabase_admin", fake)

    response = client.get("/rooms/1")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1

    assert data["room_type"] == "Single Room"


def test_get_room_invalid_id(monkeypatch):
    """
    Get room with invalid room ID
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.rooms.supabase_admin", fake)

    response = client.get("/rooms/999")

    assert response.status_code == 404


def test_filter_room_by_type(monkeypatch):
    """
    Filter rooms by room type
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.rooms.supabase_admin", fake)

    response = client.get("/rooms?room_type=Single Room")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["room_type"] == "Single Room"


def test_filter_room_by_gender(monkeypatch):
    """
    Filter rooms by gender policy
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.rooms.supabase_admin", fake)

    response = client.get("/rooms?gender=Female only")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1


def test_filter_room_by_block(monkeypatch):
    """
    Filter rooms by hostel block
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.rooms.supabase_admin", fake)

    response = client.get("/rooms?block=Block A")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["block_name"] == "Block A"


def test_only_available_rooms(monkeypatch):
    """
    Return only rooms without active bookings
    """

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.rooms.supabase_admin", fake)

    response = client.get("/rooms?only_available=true")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["id"] == 1


def test_rooms_without_supabase():

    app.dependency_overrides = {}

    response = client.get(
        "/rooms"
    )

    assert response.status_code in [200, 501]
