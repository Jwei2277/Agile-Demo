from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import PaymentOut
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(prefix="/payments", tags=["payments"])

Row = dict[str, Any]

# Payment is collected offline, in person, at check-in — see
# admin.py's check_in_booking(), which creates the actual payment
# record. There's no student-initiated online payment flow here
# anymore; this module just exposes the resulting records (history +
# receipt download).


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
        method=row.get("method"),
        status=str(row["status"]),
        receipt_number=str(row["receipt_number"]),
        paid_at=row.get("paid_at"),
        room_label=row.get("_room_label"),
    )


@router.get("/me", response_model=list[PaymentOut])
def my_payments(user: CurrentUser = Depends(get_current_user)):
    db = _db()
    resp = (
        db.table("payments")
        .select("*, bookings(room_id)")
        .eq("student_id", user.id)
        .eq("status", "paid")
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
    if payment["status"] != "paid":
        raise HTTPException(status_code=409, detail="This payment hasn't been completed yet.")

    room_label = _room_label(db, booking.get("room_id")) if booking.get("room_id") else "Unknown room"
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
    <div class="row"><span>Payment method</span><span>{payment.get('method') or 'Offline'}</span></div>
    <div class="row"><span>Date paid</span><span>{paid_at}</span></div>
    <div class="row"><span>Booking ID</span><span>#{payment['booking_id']}</span></div>
  </div>
  <button onclick="window.print()">Print / Save as PDF</button>
</body>
</html>"""
    return HTMLResponse(content=html)
