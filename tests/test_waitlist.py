from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user

client = TestClient(app)


# ============================================================
# Fake Supabase
# ============================================================


class FakeResult:

    def __init__(self, data):
        self.data = data


class FakeTable:

    def __init__(self, name):

        self.name = name
        self.data = []
        self.updated = {}
        self.inserted = []

    def select(self, *args):
        return self

    def eq(self, *args):
        return self

    def in_(self, *args):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args):
        return self

    def update(self, payload):

        self.updated = payload

        return self

    def insert(self, payload):

        self.inserted.append(payload)

        return self

    def execute(self):

        if self.name == "rooms":

            return FakeResult(
                [
                    {
                        "id": 1,
                        "room_number": "101",
                        "room_type": "Single Room",
                        "capacity": 1,
                        "gender_policy": "Mixed",
                        "is_active": True,
                        "hostel_blocks": {"name": "Block A"},
                    }
                ]
            )

        if self.name == "bookings":

            return FakeResult(
                [
                    {
                        "id": 50,
                        "student_id": "student-1",
                        "room_id": 1,
                        "status": "approved",
                        "move_out_date": "2026-08-01",
                    }
                ]
            )

        if self.name == "room_waitlist":

            if self.inserted:

                return FakeResult(
                    [
                        {
                            "id": 1,
                            "room_id": 1,
                            "student_id": "student-1",
                            "status": "waiting",
                            "occupant_count": 1,
                            "move_in_date": "2026-08-02",
                            "move_out_date": "2027-01-01",
                            "joined_at": "2026-07-18",
                        }
                    ]
                )

            return FakeResult([])

        return FakeResult([])


class FakeSupabase:

    def __init__(self):

        self.tables = {
            "rooms": FakeTable("rooms"),
            "bookings": FakeTable("bookings"),
            "room_waitlist": FakeTable("room_waitlist"),
        }

    def table(self, name):

        return self.tables[name]


# ============================================================
# Setup
# ============================================================


def fake_user():

    return CurrentUser(
        id="student-1",
        email="student@test.com",
        full_name="Student",
        student_id="ST001",
        gender="Female",
        role="student",
    )


def teardown_function():

    app.dependency_overrides.clear()


# ============================================================
# Tests
# ============================================================


def test_join_waitlist_success(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.waitlist.supabase_admin", fake)

    app.dependency_overrides[get_current_user] = fake_user

    response = client.post(
        "/waitlist/1",
        json={"occupant_count": 1, "move_in_date": "2026-08-02", "move_out_date": "2027-01-01"},
    )

    assert response.status_code == 201

    body = response.json()

    assert body["status"] == "waiting"

    assert body["room_id"] == 1


def test_join_waitlist_room_not_found(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.waitlist.supabase_admin", fake)

    fake.tables["rooms"].execute = lambda: FakeResult([])

    app.dependency_overrides[get_current_user] = fake_user

    response = client.post(
        "/waitlist/999",
        json={"occupant_count": 1, "move_in_date": "2026-08-02", "move_out_date": "2027-01-01"},
    )

    assert response.status_code == 404


def test_get_my_waitlist(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.waitlist.supabase_admin", fake)

    fake.tables["room_waitlist"].execute = lambda: FakeResult(
        [
            {
                "id": 1,
                "room_id": 1,
                "student_id": "student-1",
                "status": "waiting",
                "occupant_count": 1,
                "move_in_date": "2026-08-02",
                "move_out_date": "2027-01-01",
                "joined_at": "2026-07-18",
            }
        ]
    )

    app.dependency_overrides[get_current_user] = fake_user

    response = client.get("/waitlist/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["status"] == "waiting"


def test_leave_waitlist(monkeypatch):

    fake = FakeSupabase()

    monkeypatch.setattr("agile_ci_demo.waitlist.supabase_admin", fake)

    fake.tables["room_waitlist"].execute = lambda: FakeResult(
        [
            {
                "id": 1,
                "student_id": "student-1",
                "room_id": 1,
                "status": "waiting",
                "occupant_count": 1,
                "move_in_date": "2026-08-02",
                "move_out_date": "2027-01-01",
                "joined_at": "2026-07-18",
            }
        ]
    )

    app.dependency_overrides[get_current_user] = fake_user

    response = client.delete("/waitlist/1")

    assert response.status_code == 204
