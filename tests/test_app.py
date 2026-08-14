from fastapi.testclient import TestClient

from agile_ci_demo.app import app, reset_db

client = TestClient(app)


# ============================================================
# Fixtures / Cleanup
# ============================================================


def setup_function():
    reset_db()


def teardown_function():
    reset_db()


# ============================================================
# Health Check
# ============================================================


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    print("health - PASSED")


# ============================================================
# Public Login / Authentication Pages
# ============================================================


def test_root_page():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("root login page - PASSED")


def test_login_page():
    response = client.get("/login.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("login page - PASSED")


def test_register_page():
    response = client.get("/register.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("register page - PASSED")


def test_forgot_password_page():
    response = client.get("/forgot-password.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("forgot password page - PASSED")


def test_reset_password_page():
    response = client.get("/reset-password.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("reset password page - PASSED")


# ============================================================
# Student Pages
# ============================================================


def test_student_home_page():
    response = client.get("/student-home.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("student home page - PASSED")


def test_student_profile_page():
    response = client.get("/student-profile.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("student profile page - PASSED")


def test_student_browse_hostels_page():
    response = client.get("/student-browse-hostels.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("student browse hostels page - PASSED")


def test_student_room_details_page():
    response = client.get("/student-room-details.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("student room details page - PASSED")


def test_student_my_booking_page():
    response = client.get("/student-my-booking.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("student my booking page - PASSED")


def test_student_booking_history_page():
    response = client.get("/student-booking-history.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("student booking history page - PASSED")


def test_student_maintenance_page():
    response = client.get("/student-maintenance.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("student maintenance page - PASSED")


def test_student_visitors_page():
    response = client.get("/student-visitors.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("student visitors page - PASSED")


def test_student_documents_page():
    response = client.get("/student-documents.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("student documents page - PASSED")


# ============================================================
# Admin Pages
# ============================================================


def test_admin_dashboard_page():
    response = client.get("/admin-dashboard.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin dashboard page - PASSED")


def test_admin_bookings_page():
    response = client.get("/admin-bookings.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin bookings page - PASSED")


def test_admin_maintenance_page():
    response = client.get("/admin-maintenance.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin maintenance page - PASSED")


def test_admin_visitors_page():
    response = client.get("/admin-visitors.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin visitors page - PASSED")


def test_admin_documents_page():
    response = client.get("/admin-documents.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin documents page - PASSED")


def test_admin_checkinout_page():
    response = client.get("/admin-checkinout.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin check-in/check-out page - PASSED")


def test_admin_reports_page():
    response = client.get("/admin-reports.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin reports page - PASSED")


def test_admin_transfers_page():
    response = client.get("/admin-transfers.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin transfers page - PASSED")


def test_admin_rooms_page():
    response = client.get("/admin-rooms.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin rooms page - PASSED")


def test_admin_dashboard_pending_page():
    response = client.get("/admin-dashboard-pending.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin dashboard pending page - PASSED")


def test_admin_dashboard_clear_page():
    response = client.get("/admin-dashboard-clear.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    print("admin dashboard clear page - PASSED")


# ============================================================
# Invalid HTML Route
# ============================================================


def test_invalid_page():
    response = client.get("/page-not-found.html")

    assert response.status_code == 404

    print("invalid page - PASSED")


# ============================================================
# Item CRUD
# ============================================================


def test_create_item():
    payload = {
        "id": 1,
        "title": "Complete Assignment",
        "done": False,
    }

    response = client.post("/items", json=payload)

    assert response.status_code == 201

    data = response.json()

    assert data["id"] == 1
    assert data["title"] == "Complete Assignment"
    assert data["done"] is False

    print("create item - PASSED")


def test_create_item_default_done():
    payload = {
        "id": 2,
        "title": "Default Done Value",
    }

    response = client.post("/items", json=payload)

    assert response.status_code == 201

    data = response.json()

    assert data["id"] == 2
    assert data["title"] == "Default Done Value"
    assert data["done"] is False

    print("create item default done - PASSED")


def test_create_duplicate_item():
    payload = {
        "id": 1,
        "title": "Task",
        "done": False,
    }

    first = client.post("/items", json=payload)

    assert first.status_code == 201

    response = client.post("/items", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == ("Item with that ID already exists")

    print("create duplicate item - PASSED")


# ============================================================
# Get Item
# ============================================================


def test_get_item():
    payload = {
        "id": 1,
        "title": "Testing",
        "done": False,
    }

    create_response = client.post("/items", json=payload)

    assert create_response.status_code == 201

    response = client.get("/items/1")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["title"] == "Testing"
    assert data["done"] is False

    print("get item - PASSED")


def test_get_item_not_found():
    response = client.get("/items/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not found"

    print("get item not found - PASSED")


# ============================================================
# Mark Item Done
# ============================================================


def test_mark_item_done():
    payload = {
        "id": 1,
        "title": "Testing",
        "done": False,
    }

    create_response = client.post("/items", json=payload)

    assert create_response.status_code == 201

    response = client.patch("/items/1/done")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["title"] == "Testing"
    assert data["done"] is True

    print("mark item done - PASSED")


def test_mark_done_item_not_found():
    response = client.patch("/items/999/done")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not found"

    print("mark missing item done - PASSED")


def test_mark_item_done_twice():
    payload = {
        "id": 1,
        "title": "Repeat Done Test",
        "done": False,
    }

    create_response = client.post("/items", json=payload)

    assert create_response.status_code == 201

    first = client.patch("/items/1/done")

    assert first.status_code == 200
    assert first.json()["done"] is True

    second = client.patch("/items/1/done")

    assert second.status_code == 200
    assert second.json()["done"] is True

    print("mark item done twice - PASSED")


# ============================================================
# Item Validation
# ============================================================


def test_create_item_missing_id():
    payload = {
        "title": "Assignment",
        "done": False,
    }

    response = client.post("/items", json=payload)

    assert response.status_code == 422

    print("create item missing id - PASSED")


def test_create_item_missing_title():
    payload = {
        "id": 1,
        "done": False,
    }

    response = client.post("/items", json=payload)

    assert response.status_code == 422

    print("create item missing title - PASSED")


def test_create_item_invalid_id():
    payload = {
        "id": "abc",
        "title": "Assignment",
        "done": False,
    }

    response = client.post("/items", json=payload)

    assert response.status_code == 422

    print("create item invalid id - PASSED")


def test_create_item_invalid_done():
    payload = {
        "id": 1,
        "title": "Assignment",
        "done": "not-a-boolean",
    }

    response = client.post("/items", json=payload)

    assert response.status_code == 422

    print("create item invalid done - PASSED")


def test_create_item_wrong_json_type():
    response = client.post(
        "/items",
        json={
            "id": "invalid",
            "title": 123,
            "done": "invalid",
        },
    )

    assert response.status_code == 422

    print("create item wrong json types - PASSED")


# ============================================================
# Item Isolation / Reset
# ============================================================


def test_reset_db_removes_items():
    payload = {
        "id": 100,
        "title": "Temporary Item",
        "done": False,
    }

    response = client.post("/items", json=payload)

    assert response.status_code == 201

    reset_db()

    response = client.get("/items/100")

    assert response.status_code == 404

    print("reset database removes items - PASSED")


def test_multiple_items():
    items = [
        {
            "id": 1,
            "title": "First Task",
            "done": False,
        },
        {
            "id": 2,
            "title": "Second Task",
            "done": True,
        },
        {
            "id": 3,
            "title": "Third Task",
            "done": False,
        },
    ]

    for item in items:
        response = client.post("/items", json=item)

        assert response.status_code == 201

    for item in items:
        response = client.get(f"/items/{item['id']}")

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == item["id"]
        assert data["title"] == item["title"]
        assert data["done"] == item["done"]

    print("multiple items CRUD - PASSED")
