from typing import Any

import pytest
from fastapi.testclient import TestClient

from agile_ci_demo.app import app
from agile_ci_demo.deps import (
    CurrentUser,
    get_current_user,
)

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
        self.tables: dict[str, list[dict[str, Any]]] = {
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

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


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
# Fixtures / Cleanup
# ============================================================


@pytest.fixture(autouse=True)
def cleanup():
    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


# ============================================================
# Authentication
# ============================================================


def test_get_my_payments_without_login():
    app.dependency_overrides.clear()

    response = client.get("/payments/me")

    assert response.status_code == 401


def test_download_receipt_without_login():
    app.dependency_overrides.clear()

    response = client.get("/payments/1/receipt")

    assert response.status_code == 401


# ============================================================
# Database Configuration
# ============================================================


def test_get_my_payments_service_role_missing(
    monkeypatch,
):
    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/me")

    assert response.status_code == 501

    assert response.json()["detail"] == ("Server misconfigured: " "missing service role key")


def test_download_receipt_service_role_missing(
    monkeypatch,
):
    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        None,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 501

    assert response.json()["detail"] == ("Server misconfigured: " "missing service role key")


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
                "paid_at": ("2026-08-15T10:00:00+00:00"),
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


def test_get_my_payments_empty(
    monkeypatch,
):
    fake = FakeSupabase(payment_rows=[])

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/me")

    assert response.status_code == 200
    assert response.json() == []


def test_get_my_payments_only_returns_paid(
    monkeypatch,
):
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
                "paid_at": ("2026-08-15T10:00:00+00:00"),
                "bookings": {
                    "room_id": 10,
                },
            },
            {
                "id": 2,
                "booking_id": 2,
                "student_id": "student001",
                "amount": 200.0,
                "method": "Card",
                "status": "pending",
                "receipt_number": "RCPT-002",
                "paid_at": ("2026-08-14T10:00:00+00:00"),
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

    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["status"] == "paid"


def test_get_my_payments_multiple_records(
    monkeypatch,
):
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
                "paid_at": ("2026-08-15T12:00:00+00:00"),
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
                "paid_at": ("2026-08-14T12:00:00+00:00"),
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


# ============================================================
# Room Label
# ============================================================


def test_get_my_payments_room_label(
    monkeypatch,
):
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
                "paid_at": ("2026-08-15T10:00:00+00:00"),
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

    assert data[0]["room_label"] == ("Block A · Room 101")


def test_room_label_existing_room():
    from agile_ci_demo.payments import _room_label

    fake = FakeSupabase()

    label = _room_label(
        fake,
        10,
    )

    assert label == ("Block A · Room 101")


def test_room_label_missing_room():
    from agile_ci_demo.payments import _room_label

    fake = FakeSupabase(room_rows=[])

    label = _room_label(
        fake,
        999,
    )

    assert label == "Unknown room"


def test_room_label_none():
    from agile_ci_demo.payments import _room_label

    fake = FakeSupabase()

    label = _room_label(
        fake,
        None,
    )

    assert label == "Unknown room"


def test_room_label_unknown_block():
    from agile_ci_demo.payments import _room_label

    fake = FakeSupabase(
        room_rows=[
            {
                "id": 10,
                "room_number": "101",
                "fee_monthly": 120.0,
                "hostel_blocks": {},
            }
        ]
    )

    label = _room_label(
        fake,
        10,
    )

    assert label == ("? · Room 101")


# ============================================================
# Receipt
# ============================================================


def test_download_payment_receipt(
    monkeypatch,
):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 1,
                "booking_id": 1,
                "student_id": "student001",
                "amount": 120.0,
                "method": "Online Banking",
                "status": "paid",
                "receipt_number": ("RCPT-20260815-ABCD1234"),
                "paid_at": ("2026-08-15T10:00:00+00:00"),
                "bookings": {
                    "room_id": 10,
                    "student_id": "student001",
                },
            }
        ]
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 200

    assert "text/html" in (response.headers["content-type"])

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


def test_download_receipt_payment_not_found(
    monkeypatch,
):
    fake = FakeSupabase(payment_rows=[])

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/999/receipt")

    assert response.status_code == 404

    assert response.json()["detail"] == ("Payment not found")


def test_download_receipt_not_your_payment(
    monkeypatch,
):
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
                "paid_at": ("2026-08-15T10:00:00+00:00"),
                "bookings": {
                    "room_id": 10,
                    "student_id": "student002",
                },
            }
        ]
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 403

    assert response.json()["detail"] == ("Not your payment")


def test_admin_can_download_other_student_receipt(
    monkeypatch,
):
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
                "paid_at": ("2026-08-15T10:00:00+00:00"),
                "bookings": {
                    "room_id": 10,
                    "student_id": "student002",
                },
            }
        ]
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = admin_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 200

    assert "RCPT-ADMIN" in response.text


def test_receipt_for_payment_without_room(
    monkeypatch,
):
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
                "paid_at": ("2026-08-15T10:00:00+00:00"),
                "bookings": {},
            }
        ]
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


def test_receipt_unpaid_payment(
    monkeypatch,
):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 1,
                "booking_id": 1,
                "student_id": "student001",
                "amount": 120.0,
                "method": "Card",
                "status": "pending",
                "receipt_number": "RCPT-PENDING",
                "paid_at": None,
                "bookings": {
                    "room_id": 10,
                    "student_id": "student001",
                },
            }
        ]
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = student_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 409

    assert response.json()["detail"] == ("This payment hasn't been completed yet.")


def test_admin_can_download_unpaid_payment(
    monkeypatch,
):
    fake = FakeSupabase(
        payment_rows=[
            {
                "id": 1,
                "booking_id": 1,
                "student_id": "student002",
                "amount": 120.0,
                "method": "Card",
                "status": "pending",
                "receipt_number": "RCPT-PENDING",
                "paid_at": None,
                "bookings": {
                    "room_id": 10,
                    "student_id": "student002",
                },
            }
        ]
    )

    monkeypatch.setattr(
        "agile_ci_demo.payments.supabase_admin",
        fake,
    )

    app.dependency_overrides[get_current_user] = admin_user

    response = client.get("/payments/1/receipt")

    assert response.status_code == 409


# ============================================================
# Payment Output Helper
# ============================================================


def test_payment_output_helper():
    from agile_ci_demo.payments import _payment_out

    fake = FakeSupabase()

    payment = _payment_out(
        fake,
        {
            "id": 1,
            "booking_id": 1,
            "amount": 120.0,
            "method": "Online Banking",
            "status": "paid",
            "receipt_number": "RCPT-TEST",
            "paid_at": ("2026-08-15T10:00:00+00:00"),
            "_room_label": ("Block A · Room 101"),
        },
    )

    assert payment.id == 1
    assert payment.booking_id == 1
    assert payment.amount == 120.0
    assert payment.method == "Online Banking"
    assert payment.status == "paid"
    assert payment.receipt_number == ("RCPT-TEST")
    assert payment.room_label == ("Block A · Room 101")
