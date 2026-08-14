from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException

from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import VisitorRequestCreate, VisitorRequestOut
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(prefix="/visitors", tags=["visitors"])

Row = dict[str, Any]


def _db():
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )
    return supabase_admin


def _rows(data: Any) -> list[Row]:
    return cast(list[Row], data or [])


def _visitor_out(row: Row) -> VisitorRequestOut:
    return VisitorRequestOut(
        id=int(row["id"]),
        visitor_name=str(row["visitor_name"]),
        visitor_email=str(row["visitor_email"]),
        visitor_relationship=str(row["visitor_relationship"]),
        visitor_phone=str(row["visitor_phone"]),
        visit_date=row["visit_date"],
        visit_time=row["visit_time"],
        status=str(row["status"]),
        rejection_reason=row.get("rejection_reason"),
        requested_at=row["requested_at"],
        decided_at=row.get("decided_at"),
    )


@router.post("", status_code=201, response_model=VisitorRequestOut)
def create_visitor_request(
    data: VisitorRequestCreate, user: CurrentUser = Depends(get_current_user)
):
    db = _db()

    insert_resp = (
        db.table("visitor_requests")
        .insert(
            {
                "student_id": user.id,
                "visitor_name": data.visitor_name,
                "visitor_email": data.visitor_email,
                "visitor_relationship": data.visitor_relationship,
                "visitor_phone": data.visitor_phone,
                "visit_date": data.visit_date.isoformat(),
                "visit_time": data.visit_time.isoformat(),
                "status": "pending",
            }
        )
        .execute()
    )
    rows = _rows(insert_resp.data)
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="The visitor request was rejected by the database — please try again.",
        )

    return _visitor_out(rows[0])


@router.get("/me", response_model=list[VisitorRequestOut])
def my_visitor_requests(user: CurrentUser = Depends(get_current_user)):
    db = _db()
    resp = (
        db.table("visitor_requests")
        .select("*")
        .eq("student_id", user.id)
        .order("requested_at", desc=True)
        .execute()
    )
    rows = _rows(resp.data)
    # Cancelled requests sink to the bottom, below pending/approved/rejected;
    # newest-first within each group.
    rows.sort(key=lambda r: r["status"] == "cancelled")
    return [_visitor_out(row) for row in rows]


@router.delete("/{request_id}", status_code=204)
def cancel_visitor_request(request_id: int, user: CurrentUser = Depends(get_current_user)):
    db = _db()

    resp = db.table("visitor_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = _rows(resp.data)
    if not rows:
        raise HTTPException(status_code=404, detail="Visitor request not found")

    request_row = rows[0]
    if request_row["student_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not your visitor request")
    if request_row["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"This request is already '{request_row['status']}' and can't be cancelled.",
        )

    db.table("visitor_requests").update(
        {"status": "cancelled", "decided_at": datetime.now(UTC).isoformat()}
    ).eq("id", request_id).execute()
