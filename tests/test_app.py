from fastapi.testclient import TestClient

from agile_ci_demo.app import app, reset_db

client = TestClient(app)


def setup_function() -> None:
    """Called by pytest before every test in this module."""
    reset_db()


def test_health():
    """
    Scenario: API health check
      Given the API is running
      When I GET /health
      Then I receive 200 and {"status": "ok"}
    """
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_get_item():
    """
    Scenario: Add a todo item
      Given the API is running
      When I POST /items with a new item
      Then I receive 201 and the item is persisted
    """
    item = {"id": 1, "title": "Read agile guide"}

    # Create
    r = client.post("/items", json=item)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["title"] == "Read agile guide"
    assert body["done"] is False

    # Read back
    r2 = client.get("/items/1")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["id"] == 1
    assert body2["title"] == "Read agile guide"
    assert body2["done"] is False


def test_conflict_on_duplicate():
    """
    Scenario: Cannot create duplicate item IDs
      Given an item with ID 2 exists
      When I POST another item with ID 2
      Then I receive 409 Conflict
    """
    item = {"id": 2, "title": "Duplicate"}

    # First create succeeds
    r1 = client.post("/items", json=item)
    assert r1.status_code == 201

    # Second create fails
    r2 = client.post("/items", json=item)
    assert r2.status_code == 409


def test_mark_done():
    """
    Scenario: Mark an item as done
      Given an item with ID 3 exists
      When I PATCH /items/3/done
      Then the item is marked as done
    """
    item = {"id": 3, "title": "Finish demo"}
    client.post("/items", json=item)

    r = client.patch("/items/3/done")
    assert r.status_code == 200
    assert r.json()["done"] is True


def test_student_room_details_page_is_served():
    """
    Scenario: Student room details page is available
      Given the student portal page is requested
      When the room details route is opened
      Then the page is served successfully
    """
    r = client.get("/student-room-details.html")
    assert r.status_code == 200
    assert "Room details" in r.text
    assert "Book this room" in r.text


def test_student_home_browse_link_uses_absolute_route():
    """
    Scenario: Student home browse link is clickable from the summary card
      Given the student home page is requested
      When the browse room link is rendered
      Then it uses an absolute route that works from any page path
    """
    r = client.get("/student-home.html")
    assert r.status_code == 200
    assert 'href="/student-browse-hostels.html"' in r.text


def test_student_browse_page_uses_button_navigation_for_details():
    """
    Scenario: Browse rooms page navigates to room details via a direct button action
      Given the browse rooms page is requested
      When the room card template is rendered
      Then it includes the details navigation hook for click handling
    """
    r = client.get("/student-browse-hostels.html")
    assert r.status_code == 200
    assert "data-detail-room-id" in r.text
