from fastapi.testclient import TestClient
import pytest

from agile_ci_demo.app import app
from agile_ci_demo.deps import CurrentUser, get_current_user

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
    def __init__(self, rows):
        self.rows = rows
        self.data = list(rows)
        self.payload = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        self.data = [row for row in self.data if row.get(column) == value]
        return self

    def limit(self, number):
        self.data = self.data[:number]
        return self

    def order(self, column, desc=False):
        self.data.sort(
            key=lambda row: row.get(column) or "",
            reverse=desc,
        )
        return self

    def insert(self, payload):
        self.payload = payload

        new_row = dict(payload)

        if "id" not in new_row:
            new_row["id"] = 100

        if "paid_at" not in new_row:
            new_row["paid_at"] = "2026-08-15T12:00:00+00:00"

        self.data = [new_row]

        return self

    def execute(self):
        return FakeResponse(self.data)


# ============================================================
# Fake Supabase
# ============================================================


class FakeSupabase:
    def __init__(
        self,
        *,
        booking_rows=None,
        payment_rows=None,
        room_rows=None,
    ):
        self.tables = {
            "bookings": (
                booking_rows
                if booking_rows is not None
                else [
                    {
                        "id": 1,
                        "student_id": "student001",
                        "room_id": 10,
                        "status": "approved",
                        "occupant_count": 1,
                    }
                ]
            ),
            "payments": (payment_rows if payment_rows is not None else []),
            "rooms": (
                room_rows
                if room_rows is not None
                else [
                    {
                        "id": 10,
                        "room_number": "101",
                        "fee_monthly": 120.0,
                        "hostel_blocks": {
                            "name": "Block A",
                        },
                    }
                ]
            ),
        }

        self.inserted_payment = None

    def table(self, name):
        query = FakeQuery(self.tables.get(name, []))

        original_insert = query.insert

        def insert(payload):
            if name == "payments":
                self.inserted_payment = payload

            return original_insert(payload)

        query.insert = insert

        return query


# ============================================================
# Fake Users
# ============================================================


def student_user():
    return CurrentUser(
        id="student001",
        email="student@test.com",
        full_name="Student One",
        student_id="TP123456",
        gender="Male",
        role="student",
    )


def another_student_user():
    return CurrentUser(
        id="student002",
        email="other@test.com",
        full_name="Other Student",
        student_id="TP999999",
        gender="Female",
        role="student",
    )


def admin_user():
    return CurrentUser(
        id="admin001",
        email="admin@test.com",
        full_name="Admin User",
        role="admin",
    )


# ============================================================
# Cleanup
# ============================================================


@pytest.fixture(autouse=True)
def cleanup():
    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


# ============================================================
# Authentication
# ============================================================


def test_create_payment_without_login():
    app.dependency_overrides.clear()

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 401

    print("create payment without login - PASSED")


def test_get_my_payments_without_login():
    app.dependency_overrides.clear()

    response = client.get("/payments/me")

    assert response.status_code == 401

    print("get payments without login - PASSED")


def test_download_receipt_without_login():
    app.dependency_overrides.clear()

    response = client.get("/payments/1/receipt")

    assert response.status_code == 401

    print("download receipt without login - PASSED")


# ============================================================
# Successful Payment Creation
# ============================================================


def test_create_payment_success(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["booking_id"] == 1
    assert data["amount"] == 120.0
    assert data["method"] == "Card"
    assert data["status"] == "paid"
    assert data["receipt_number"].startswith("RCPT-")
    assert data["paid_at"] is not None

    print("create payment - PASSED")


def test_create_payment_records_student_id(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 201

    assert fake.inserted_payment is not None
    assert fake.inserted_payment["student_id"] == "student001"

    print("payment records student ID - PASSED")


def test_create_payment_records_paid_status(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 201

    assert fake.inserted_payment is not None
    assert fake.inserted_payment["status"] == "paid"

    print("payment status recorded as paid - PASSED")


def test_create_payment_records_method(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "E-Wallet",
        },
    )

    assert response.status_code == 201

    assert fake.inserted_payment is not None
    assert fake.inserted_payment["method"] == "E-Wallet"

    print("payment method recorded - PASSED")


def test_create_payment_generates_receipt_number(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 201

    receipt_number = response.json()["receipt_number"]

    assert receipt_number.startswith("RCPT-")
    assert len(receipt_number) > len("RCPT-")

    print("payment receipt number generated - PASSED")


# ============================================================
# Booking Validation
# ============================================================


def test_create_payment_booking_not_found(monkeypatch):
    fake = FakeSupabase(
        booking_rows=[],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 999,
            "method": "Card",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Booking not found"

    print("payment booking not found - PASSED")


def test_create_payment_not_own_booking(monkeypatch):
    fake = FakeSupabase(
        booking_rows=[
            {
                "id": 1,
                "student_id": "student002",
                "room_id": 10,
                "status": "approved",
                "occupant_count": 1,
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not your booking"

    print("payment ownership validation - PASSED")


def test_create_payment_pending_booking(monkeypatch):
    fake = FakeSupabase(
        booking_rows=[
            {
                "id": 1,
                "student_id": "student001",
                "room_id": 10,
                "status": "pending",
                "occupant_count": 1,
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 409

    assert response.json()["detail"] == "Only approved bookings can be paid for."

    print("pending booking cannot be paid - PASSED")


def test_create_payment_rejected_booking(monkeypatch):
    fake = FakeSupabase(
        booking_rows=[
            {
                "id": 1,
                "student_id": "student001",
                "room_id": 10,
                "status": "rejected",
                "occupant_count": 1,
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 409

    assert response.json()["detail"] == "Only approved bookings can be paid for."

    print("rejected booking cannot be paid - PASSED")


def test_create_payment_cancelled_booking(monkeypatch):
    fake = FakeSupabase(
        booking_rows=[
            {
                "id": 1,
                "student_id": "student001",
                "room_id": 10,
                "status": "cancelled",
                "occupant_count": 1,
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 409

    print("cancelled booking cannot be paid - PASSED")


# ============================================================
# Duplicate Payment
# ============================================================


def test_create_payment_already_paid(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 20,
                "booking_id": 1,
                "student_id": "student001",
                "amount": 120.0,
                "method": "Card",
                "status": "paid",
                "receipt_number": "RCPT-OLD",
                "paid_at": "2026-08-14T10:00:00+00:00",
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 409

    assert response.json()["detail"] == "This booking has already been paid for."

    print("duplicate payment prevented - PASSED")


def test_create_payment_existing_pending_payment_allowed(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 20,
                "booking_id": 1,
                "student_id": "student001",
                "amount": 120.0,
                "method": "Card",
                "status": "pending",
                "receipt_number": "RCPT-PENDING",
                "paid_at": "2026-08-14T10:00:00+00:00",
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 201

    print("pending previous payment does not block payment - PASSED")


# ============================================================
# Room Validation
# ============================================================


def test_create_payment_room_not_found(monkeypatch):
    fake = FakeSupabase(
        room_rows=[],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 404

    assert response.json()["detail"] == "Room not found for this booking"

    print("payment room not found - PASSED")


# ============================================================
# Payment Amount
# ============================================================


def test_create_payment_uses_room_monthly_fee(monkeypatch):
    fake = FakeSupabase(
        room_rows=[
            {
                "id": 10,
                "room_number": "101",
                "fee_monthly": 250.0,
                "hostel_blocks": {
                    "name": "Block A",
                },
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 201

    assert response.json()["amount"] == 250.0

    print("payment uses room monthly fee - PASSED")


def test_create_payment_multiple_occupants(monkeypatch):
    fake = FakeSupabase(
        booking_rows=[
            {
                "id": 1,
                "student_id": "student001",
                "room_id": 10,
                "status": "approved",
                "occupant_count": 2,
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 201

    # Actual total_fee_for() behavior in the project:
    # RM120 base fee + RM50 additional occupant = RM170.
    assert response.json()["amount"] == 170.0

    print("multiple occupant payment calculation - PASSED")


def test_create_payment_missing_occupant_count(monkeypatch):
    fake = FakeSupabase(
        booking_rows=[
            {
                "id": 1,
                "student_id": "student001",
                "room_id": 10,
                "status": "approved",
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 201
    assert response.json()["amount"] == 120.0

    print("default occupant count payment - PASSED")


# ============================================================
# Payment Input Validation
# ============================================================


def test_create_payment_missing_booking_id(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "method": "Card",
        },
    )

    assert response.status_code == 422

    print("payment missing booking ID - PASSED")


def test_create_payment_missing_method(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
        },
    )

    assert response.status_code == 422

    print("payment missing method - PASSED")


def test_create_payment_invalid_booking_id_type(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": "abc",
            "method": "Card",
        },
    )

    assert response.status_code == 422

    print("payment invalid booking ID type - PASSED")


def test_create_payment_invalid_method_type(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": 123,
        },
    )

    assert response.status_code == 422

    print("payment invalid method type - PASSED")


# ============================================================
# Valid Payment Methods
# ============================================================


@pytest.mark.parametrize(
    "method",
    [
        "Card",
        "Online Banking",
        "E-Wallet",
    ],
)
def test_payment_methods(method, monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": method,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["method"] == method
    assert data["status"] == "paid"
    assert data["booking_id"] == 1

    print(f"payment method {method} - PASSED")


# ============================================================
# Invalid Payment Methods
# ============================================================


@pytest.mark.parametrize(
    "method",
    [
        "Credit Card",
        "Debit Card",
        "FPX",
        "Cash",
        "Bitcoin",
        "Cheque",
        "",
    ],
)
def test_invalid_payment_methods_rejected(method):
    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": method,
        },
    )

    assert response.status_code == 422

    print(f"invalid payment method {method!r} - PASSED")


# ============================================================
# Database Configuration
# ============================================================


def test_create_payment_service_role_missing(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 501

    assert response.json()["detail"] == "Server misconfigured: missing service role key"

    print("payment service role missing - PASSED")


def test_get_payments_service_role_missing(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/me")

    assert response.status_code == 501

    assert response.json()["detail"] == "Server misconfigured: missing service role key"

    print("get payments service role missing - PASSED")


def test_receipt_service_role_missing(monkeypatch):
    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 501

    assert response.json()["detail"] == "Server misconfigured: missing service role key"

    print("receipt service role missing - PASSED")


# ============================================================
# My Payments
# ============================================================


def test_get_my_payments(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 1,
                "booking_id": 1,
                "student_id": "student001",
                "amount": 120.0,
                "method": "Online Banking",
                "status": "paid",
                "receipt_number": "RCPT-001",
                "paid_at": "2026-08-15T10:00:00+00:00",
                "bookings": {
                    "room_id": 10,
                },
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["booking_id"] == 1
    assert data[0]["amount"] == 120.0
    assert data[0]["method"] == "Online Banking"
    assert data[0]["status"] == "paid"
    assert data[0]["receipt_number"] == "RCPT-001"

    print("get my payments - PASSED")


def test_get_my_payments_empty(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/me")

    assert response.status_code == 200
    assert response.json() == []

    print("empty payment history - PASSED")


def test_get_my_payments_room_label(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 1,
                "booking_id": 1,
                "student_id": "student001",
                "amount": 120.0,
                "method": "Online Banking",
                "status": "paid",
                "receipt_number": "RCPT-001",
                "paid_at": "2026-08-15T10:00:00+00:00",
                "bookings": {
                    "room_id": 10,
                },
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["room_label"] == "Block A · Room 101"

    print("payment room label - PASSED")


def test_get_my_payments_multiple_records(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 1,
                "booking_id": 1,
                "student_id": "student001",
                "amount": 120.0,
                "method": "Card",
                "status": "paid",
                "receipt_number": "RCPT-001",
                "paid_at": "2026-08-15T12:00:00+00:00",
                "bookings": {
                    "room_id": 10,
                },
            },
            {
                "id": 2,
                "booking_id": 2,
                "student_id": "student001",
                "amount": 200.0,
                "method": "E-Wallet",
                "status": "paid",
                "receipt_number": "RCPT-002",
                "paid_at": "2026-08-14T12:00:00+00:00",
                "bookings": {
                    "room_id": 10,
                },
            },
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/me")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[1]["id"] == 2

    print("multiple payment history records - PASSED")


# ============================================================
# Receipt
# ============================================================


def test_download_payment_receipt(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 1,
                "booking_id": 1,
                "student_id": "student001",
                "amount": 120.0,
                "method": "Online Banking",
                "status": "paid",
                "receipt_number": "RCPT-20260815-ABCD1234",
                "paid_at": "2026-08-15T10:00:00+00:00",
                "bookings": {
                    "room_id": 10,
                    "student_id": "student001",
                },
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    html = response.text

    assert "HostelEase Payment Receipt" in html
    assert "RCPT-20260815-ABCD1234" in html
    assert "RM 120.00" in html
    assert "Block A" in html
    assert "Room 101" in html
    assert "Online Banking" in html
    assert "PAID" in html
    assert "Booking ID" in html
    assert "#1" in html

    print("download payment receipt - PASSED")


def test_download_receipt_payment_not_found(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/999/receipt")

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"

    print("receipt payment not found - PASSED")


def test_download_receipt_not_your_payment(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 1,
                "booking_id": 1,
                "student_id": "student002",
                "amount": 120.0,
                "method": "Online Banking",
                "status": "paid",
                "receipt_number": "RCPT-OTHER",
                "paid_at": "2026-08-15T10:00:00+00:00",
                "bookings": {
                    "room_id": 10,
                    "student_id": "student002",
                },
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 403
    assert response.json()["detail"] == "Not your payment"

    print("receipt ownership validation - PASSED")


def test_admin_can_download_other_student_receipt(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 1,
                "booking_id": 1,
                "student_id": "student002",
                "amount": 120.0,
                "method": "Online Banking",
                "status": "paid",
                "receipt_number": "RCPT-ADMIN",
                "paid_at": "2026-08-15T10:00:00+00:00",
                "bookings": {
                    "room_id": 10,
                    "student_id": "student002",
                },
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = admin_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 200
    assert "RCPT-ADMIN" in response.text

    print("admin receipt access - PASSED")


def test_receipt_for_payment_without_room(monkeypatch):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 1,
                "booking_id": 1,
                "student_id": "student001",
                "amount": 120.0,
                "method": "Card",
                "status": "paid",
                "receipt_number": "RCPT-NOROOM",
                "paid_at": "2026-08-15T10:00:00+00:00",
                "bookings": {},
            }
        ],
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 200
    assert "Unknown room" in response.text
    assert "RCPT-NOROOM" in response.text

    print("receipt without room - PASSED")


# ============================================================
# Helper Functions
# ============================================================


def test_room_label_existing_room():
    fake = FakeSupabase()

    from agile_ci_demo.payments import _room_label

    label = _room_label(fake, 10)

    assert label == "Block A · Room 101"

    print("room label helper - PASSED")


def test_room_label_missing_room():
    fake = FakeSupabase(
        room_rows=[],
    )

    from agile_ci_demo.payments import _room_label

    label = _room_label(fake, 999)

    assert label == "Unknown room"

    print("missing room label helper - PASSED")


def test_payment_output_helper():
    fake = FakeSupabase()

    from agile_ci_demo.payments import _payment_out

    payment = _payment_out(
        fake,
        {
            "id": 1,
            "booking_id": 1,
            "amount": 120.0,
            "method": "Online Banking",
            "status": "paid",
            "receipt_number": "RCPT-TEST",
            "paid_at": "2026-08-15T10:00:00+00:00",
            "_room_label": "Block A · Room 101",
        },
    )

    assert payment.id == 1
    assert payment.booking_id == 1
    assert payment.amount == 120.0
    assert payment.method == "Online Banking"
    assert payment.status == "paid"
    assert payment.receipt_number == "RCPT-TEST"
    assert payment.room_label == "Block A · Room 101"

    print("payment output helper - PASSED")


def test_room_label_unknown_block():
    fake = FakeSupabase(
        room_rows=[
            {
                "id": 10,
                "room_number": "101",
                "fee_monthly": 120.0,
                "hostel_blocks": {},
            }
        ],
    )

    from agile_ci_demo.payments import _room_label

    label = _room_label(fake, 10)

    assert label == "? · Room 101"

    print("unknown block room label - PASSED")


# ============================================================
# Empty / Missing Data
# ============================================================


def test_payment_insert_returns_no_rows(monkeypatch):
    class EmptyInsertQuery(FakeQuery):
        def insert(self, payload):
            self.payload = payload
            self.data = []
            return self

    class EmptyInsertSupabase(FakeSupabase):
        def table(self, name):
            if name == "payments":
                return EmptyInsertQuery([])

            return FakeQuery(self.tables.get(name, []))

    fake = EmptyInsertSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == "Could not record payment — please try again."

    print("payment database insert failure - PASSED")


# ============================================================
# Payment Method Coverage
# ============================================================


def test_card_payment(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Card",
        },
    )

    assert response.status_code == 201
    assert response.json()["method"] == "Card"

    print("Card payment - PASSED")


def test_online_banking_payment(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "Online Banking",
        },
    )

    assert response.status_code == 201
    assert response.json()["method"] == "Online Banking"

    print("Online Banking payment - PASSED")


def test_e_wallet_payment(monkeypatch):
    fake = FakeSupabase()

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.post(
        "/payments",
        json={
            "booking_id": 1,
            "method": "E-Wallet",
        },
    )

    assert response.status_code == 201
    assert response.json()["method"] == "E-Wallet"

    print("E-Wallet payment - PASSED")
