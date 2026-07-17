from fastapi.testclient import TestClient

from agile_ci_demo.app import app

client = TestClient(app)


# ==================================================
# Application Startup Tests
# ==================================================


def test_application_loaded():
    """
    Verify FastAPI application loads successfully
    """

    assert app is not None


def test_health_endpoint():
    """
    Verify API health check
    """

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"


def test_invalid_endpoint_returns_404():
    """
    Verify invalid API route returns 404
    """

    response = client.get("/unknown-route")

    assert response.status_code == 404


# ==================================================
# Router Registration Tests
# ==================================================


def _get_routes():
    """
    Collect all registered routes from FastAPI app
    """

    routes = []

    for route in app.routes:

        # Normal routes
        if hasattr(route, "path"):
            routes.append(route.path)

        # Included router objects
        if hasattr(route, "routes"):

            for sub_route in route.routes:

                if hasattr(sub_route, "path"):
                    routes.append(sub_route.path)

        # Router prefix support
        if hasattr(route, "router"):

            router = route.router

            if hasattr(router, "prefix"):

                routes.append(router.prefix)

    return routes


def test_auth_router_registered():
    """
    Verify authentication router exists
    """

    routes = _get_routes()

    assert any("/auth" in route for route in routes)


def test_room_router_registered():
    """
    Verify room router exists
    """

    routes = _get_routes()

    assert any("/rooms" in route for route in routes)


def test_booking_router_registered():
    """
    Verify booking router exists
    """

    routes = _get_routes()

    assert any("/bookings" in route for route in routes)


def test_admin_router_registered():
    """
    Verify admin router exists
    """

    routes = _get_routes()

    assert any("/admin" in route for route in routes)


# ==================================================
# Documentation Tests
# ==================================================


def test_openapi_available():
    """
    Verify OpenAPI documentation is generated
    """

    response = client.get("/openapi.json")

    assert response.status_code == 200

    data = response.json()

    assert "paths" in data


def test_swagger_page_available():
    """
    Verify Swagger documentation page works
    """

    response = client.get("/docs")

    assert response.status_code == 200
