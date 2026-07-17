from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException

from agile_ci_demo.deps import CurrentUser, get_current_user
from agile_ci_demo.models import MaintenanceCreate, MaintenanceOut
from agile_ci_demo.services.supabase_service import supabase_admin

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.post("", status_code=201, response_model=MaintenanceOut)
def create_request(
    data: MaintenanceCreate,
    user: CurrentUser = Depends(get_current_user),
):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501,
            detail="Server misconfigured: missing service role key",
        )

    response = (
        supabase_admin.table("maintenance_requests")
        .insert(
            {
                "student_id": user.id,
                "room_id": data.room_id,
                "title": data.title,
                "category": data.category,
                "priority": data.priority,
                "status": "pending",
            }
        )
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=400,
            detail="Could not create request",
        )

    row = cast(dict[str, Any], response.data[0])

    return MaintenanceOut(
        id=cast(int, row["id"]),
        title=str(row["title"]),
        category=str(row["category"]),
        priority=str(row["priority"]),
        status=str(row["status"]),
        created_at=row["created_at"],
        student_name=user.full_name,
    )


@router.get("/me", response_model=list[MaintenanceOut])
def my_requests(
    user: CurrentUser = Depends(get_current_user),
):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501,
            detail="Server misconfigured: missing service role key",
        )

    response = (
        supabase_admin.table("maintenance_requests")
        .select("*")
        .eq("student_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )

    rows = cast(list[dict[str, Any]], response.data or [])

    return [
        MaintenanceOut(
            id=cast(int, row["id"]),
            title=str(row["title"]),
            category=str(row["category"]),
            priority=str(row["priority"]),
            status=str(row["status"]),
            created_at=row["created_at"],
            student_name=user.full_name,
        )
        for row in rows
    ]