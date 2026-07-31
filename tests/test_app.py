from fastapi.testclient import TestClient
import pytest

from agile_ci_demo.app import app, reset_db

client = TestClient(app)


# ==================================================
# Fixture
# ==================================================


@pytest.fixture(autouse=True)
def cleanup():
    reset_db()
    yield
    reset_db()


# ==================================================
# Health Check
# ==================================================


def test_health():

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    print("test_health PASSED")


# ==================================================
# Login Pages
# ==================================================


def test_root_page():

    response = client.get("/")

    assert response.status_code == 200

    print("test_root_page PASSED")


def test_login_page():

    response = client.get("/login.html")

    assert response.status_code == 200

    print("test_login_page PASSED")


def test_register_page():

    response = client.get("/register.html")

    assert response.status_code == 200

    print("test_register_page PASSED")


def test_forgot_password_page():

    response = client.get("/forgot-password.html")

    assert response.status_code == 200

    print("test_forgot_password_page PASSED")


def test_reset_password_page():

    response = client.get("/reset-password.html")

    assert response.status_code == 200

    print("test_reset_password_page PASSED")


# ==================================================
# Student Pages
# ==================================================


def test_student_home_page():

    response = client.get("/student-home.html")

    assert response.status_code == 200

    print("test_student_home_page PASSED")


def test_student_profile_page():

    response = client.get("/student-profile.html")

    assert response.status_code == 200

    print("test_student_profile_page PASSED")


def test_student_browse_hostels_page():

    response = client.get("/student-browse-hostels.html")

    assert response.status_code == 200

    print("test_student_browse_hostels_page PASSED")


def test_student_room_details_page():

    response = client.get("/student-room-details.html")

    assert response.status_code == 200

    print("test_student_room_details_page PASSED")


def test_student_booking_page():

    response = client.get("/student-my-booking.html")

    assert response.status_code == 200

    print("test_student_booking_page PASSED")


def test_student_maintenance_page():

    response = client.get("/student-maintenance.html")

    assert response.status_code == 200

    print("test_student_maintenance_page PASSED")


def test_student_visitors_page():

    response = client.get("/student-visitors.html")

    assert response.status_code == 200

    print("test_student_visitors_page PASSED")


# ==================================================
# Admin Pages
# ==================================================


def test_admin_dashboard_page():

    response = client.get("/admin-dashboard.html")

    assert response.status_code == 200

    print("test_admin_dashboard_page PASSED")


def test_admin_bookings_page():

    response = client.get("/admin-bookings.html")

    assert response.status_code == 200

    print("test_admin_bookings_page PASSED")


def test_admin_maintenance_page():

    response = client.get("/admin-maintenance.html")

    assert response.status_code == 200

    print("test_admin_maintenance_page PASSED")


def test_admin_visitors_page():

    response = client.get("/admin-visitors.html")

    assert response.status_code == 200

    print("test_admin_visitors_page PASSED")


def test_admin_transfers_page():

    response = client.get("/admin-transfers.html")

    assert response.status_code == 200

    print("test_admin_transfers_page PASSED")


def test_admin_rooms_page():

    response = client.get("/admin-rooms.html")

    assert response.status_code == 200

    print("test_admin_rooms_page PASSED")


def test_admin_dashboard_pending_page():

    response = client.get("/admin-dashboard-pending.html")

    assert response.status_code == 200

    print("test_admin_dashboard_pending_page PASSED")


def test_admin_dashboard_clear_page():

    response = client.get("/admin-dashboard-clear.html")

    assert response.status_code == 200

    print("test_admin_dashboard_clear_page PASSED")


# ==================================================
# Invalid Route
# ==================================================


def test_invalid_page():

    response = client.get("/page-not-found.html")

    assert response.status_code == 404

    print("test_invalid_page PASSED")


# ==================================================
# Create Item
# ==================================================


def test_create_item():

    payload = {
        "id": 1,
        "title": "Complete Assignment",
        "done": False,
    }

    response = client.post(
        "/items",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] == 1
    assert data["title"] == "Complete Assignment"
    assert data["done"] is False

    print("test_create_item PASSED")


def test_create_duplicate_item():

    payload = {
        "id": 1,
        "title": "Task",
        "done": False,
    }

    client.post("/items", json=payload)

    response = client.post("/items", json=payload)

    assert response.status_code == 409

    assert response.json()["detail"] == "Item with that ID already exists"

    print("test_create_duplicate_item PASSED")


# ==================================================
# Get Item
# ==================================================


def test_get_item():

    payload = {
        "id": 1,
        "title": "Testing",
        "done": False,
    }

    client.post("/items", json=payload)

    response = client.get("/items/1")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["title"] == "Testing"
    assert data["done"] is False

    print("test_get_item PASSED")


def test_get_item_not_found():

    response = client.get("/items/999")

    assert response.status_code == 404

    assert response.json()["detail"] == "Not found"

    print("test_get_item_not_found PASSED")


# ==================================================
# Mark Done
# ==================================================


def test_mark_item_done():

    payload = {
        "id": 1,
        "title": "Testing",
        "done": False,
    }

    client.post("/items", json=payload)

    response = client.patch("/items/1/done")

    assert response.status_code == 200

    data = response.json()

    assert data["done"] is True

    print("test_mark_item_done PASSED")


def test_mark_done_item_not_found():

    response = client.patch("/items/999/done")

    assert response.status_code == 404

    assert response.json()["detail"] == "Not found"

    print("test_mark_done_item_not_found PASSED")


# ==================================================
# Validation
# ==================================================


def test_create_item_missing_title():

    payload = {
        "id": 1,
        "done": False,
    }

    response = client.post(
        "/items",
        json=payload,
    )

    assert response.status_code == 422

    print("test_create_item_missing_title PASSED")


def test_create_item_missing_id():

    payload = {
        "title": "Assignment",
        "done": False,
    }

    response = client.post(
        "/items",
        json=payload,
    )

    assert response.status_code == 422

    print("test_create_item_missing_id PASSED")


def test_create_item_invalid_id():

    payload = {
        "id": "abc",
        "title": "Assignment",
        "done": False,
    }

    response = client.post(
        "/items",
        json=payload,
    )

    assert response.status_code == 422

    print("test_create_item_invalid_id PASSED")


def test_create_item_without_done():

    payload = {
        "id": 5,
        "title": "Default Done",
    }

    response = client.post(
        "/items",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["done"] is False

    print("test_create_item_without_done PASSED")
