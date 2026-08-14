import secrets
from datetime import datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import PaymentCreate, PaymentOut, total_fee_for
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(prefix="/payments", tags=["payments"])

Row = dict[str, Any]


def _db():
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return supabase_admin


def _rows(data: Any) -> list[Row]:
    return cast(list[Row], data or [])


def _room_label(db, room_id: int) -> str:
    resp = (
        db.table("rooms")
        .select("room_number, hostel_blocks(name)")
        .eq("id", room_id)
        .limit(1)
        .execute()
    )
    rows = _rows(resp.data)
    if not rows:
        return "Unknown room"
    room = rows[0]
    block = room.get("hostel_blocks") or {}
    return f"{block.get('name', '?')} · Room {room.get('room_number', '?')}"


def _payment_out(db, row: Row) -> PaymentOut:
    return PaymentOut(
        id=int(row["id"]),
        booking_id=int(row["booking_id"]),
        amount=float(row["amount"]),
        method=str(row["method"]),
        status=str(row["status"]),
        receipt_number=str(row["receipt_number"]),
        paid_at=row["paid_at"],
        room_label=row.get("_room_label"),
    )


@router.post("", status_code=201, response_model=PaymentOut)
def create_payment(data: PaymentCreate, user: CurrentUser = Depends(get_current_user)):
    """Simulated online payment — there's no real payment gateway here,
    but the flow is modeled the way a real one would be: the student
    picks a method, we 'charge' them the booking's total fee, and record
    a receipt. Every attempt is logged (even if it were to fail), but
    given this is a simulation it always succeeds."""
    db = _db()

    booking_resp = db.table("bookings").select("*").eq("id", data.booking_id).limit(1).execute()
    booking_rows = _rows(booking_resp.data)
    if not booking_rows:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking = booking_rows[0]

    if booking["student_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not your booking")
    if booking["status"] != "approved":
        raise HTTPException(
            status_code=409,
            detail="Only approved bookings can be paid for.",
        )

    existing_paid = (
        db.table("payments")
        .select("id")
        .eq("booking_id", data.booking_id)
        .eq("status", "paid")
        .limit(1)
        .execute()
    )
    if _rows(existing_paid.data):
        raise HTTPException(status_code=409, detail="This booking has already been paid for.")

    room_resp = (
        db.table("rooms").select("fee_monthly").eq("id", booking["room_id"]).limit(1).execute()
    )
    room_rows = _rows(room_resp.data)
    if not room_rows:
        raise HTTPException(status_code=404, detail="Room not found for this booking")
    base_fee = float(room_rows[0]["fee_monthly"])
    amount = total_fee_for(base_fee, int(booking.get("occupant_count", 1)))

    receipt_number = f"RCPT-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(4).upper()}"

    insert_resp = (
        db.table("payments")
        .insert(
            {
                "booking_id": data.booking_id,
                "student_id": user.id,
                "amount": amount,
                "method": data.method,
                "status": "paid",
                "receipt_number": receipt_number,
            }
        )
        .execute()
    )
    rows = _rows(insert_resp.data)
    if not rows:
        raise HTTPException(status_code=400, detail="Could not record payment — please try again.")

    row = rows[0]
    row["_room_label"] = _room_label(db, booking["room_id"])
    return _payment_out(db, row)


@router.get("/me", response_model=list[PaymentOut])
def my_payments(user: CurrentUser = Depends(get_current_user)):
    db = _db()
    resp = (
        db.table("payments")
        .select("*, bookings(room_id)")
        .eq("student_id", user.id)
        .order("paid_at", desc=True)
        .execute()
    )
    out = []
    for row in _rows(resp.data):
        booking: Row = row.get("bookings") or {}
        room_id = booking.get("room_id")
        row["_room_label"] = _room_label(db, room_id) if room_id else None
        out.append(_payment_out(db, row))
    return out


@router.get("/{payment_id}/receipt", response_class=HTMLResponse)
def download_receipt(payment_id: int, user: CurrentUser = Depends(get_current_user)):
    db = _db()
    resp = (
        db.table("payments")
        .select("*, bookings(room_id, student_id)")
        .eq("id", payment_id)
        .limit(1)
        .execute()
    )
    rows = _rows(resp.data)
    if not rows:
        raise HTTPException(status_code=404, detail="Payment not found")
    payment = rows[0]
    booking: Row = payment.get("bookings") or {}

    if payment["student_id"] != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not your payment")

    room_id = booking.get("room_id")
    room_label = _room_label(db, room_id) if isinstance(room_id, int) else "Unknown room"
    paid_at = payment["paid_at"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Receipt {payment['receipt_number']}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 560px; margin: 40px auto; color: #0b2545; }}
  .receipt {{ border: 1px solid #dbe2ef; border-radius: 14px; padding: 32px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .sub {{ color: #64748b; font-size: 13px; margin: 0 0 24px; }}
  .row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eef1f6; font-size: 14px; }}
  .row span:first-child {{ color: #64748b; }}
  .amount {{ font-size: 28px; font-weight: 700; margin: 20px 0; }}
  .paid-badge {{ display: inline-block; background: #e8f7ef; color: #1f8a55; font-weight: 700; font-size: 12px; padding: 5px 12px; border-radius: 999px; margin-bottom: 16px; }}
  button {{ margin-top: 24px; padding: 10px 18px; border-radius: 8px; border: none; background: #2f6fed; color: white; font-weight: 600; cursor: pointer; font-size: 14px; }}
  @media print {{ button {{ display: none; }} }}
</style>
</head>
<body>
  <div class="receipt">
    <span class="paid-badge">PAID</span>
    <h1>HostelEase Payment Receipt</h1>
    <p class="sub">Receipt No. {payment['receipt_number']}</p>
    <div class="amount">RM {payment['amount']:.2f}</div>
    <div class="row"><span>Room</span><span>{room_label}</span></div>
    <div class="row"><span>Payment method</span><span>{payment['method']}</span></div>
    <div class="row"><span>Date paid</span><span>{paid_at}</span></div>
    <div class="row"><span>Booking ID</span><span>#{payment['booking_id']}</span></div>
  </div>
  <button onclick="window.print()">Print / Save as PDF</button>
</body>
</html>"""
    return HTMLResponse(content=html)
