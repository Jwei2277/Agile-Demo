from typing import Any, cast

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel
from supabase import AuthApiError

from agile_ci_demo.services.supabase_service import (
    supabase,
    supabase_admin,
)


class CurrentUser(BaseModel):
    id: str
    email: str
    full_name: str
    student_id: str | None = None
    gender: str | None = None
    role: str


def _extract_bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or malformed Authorization header",
        )

    return authorization.split(" ", 1)[1].strip()


def get_current_user(
    authorization: str | None = Header(default=None),
) -> CurrentUser:
    """
    Resolve bearer token into the logged-in user's profile.
    """

    token = _extract_bearer_token(authorization)

    if supabase is None:
        raise HTTPException(
            status_code=500,
            detail="Supabase client is not configured",
        )

    try:
        auth_response = supabase.auth.get_user(token)
    except AuthApiError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
        ) from exc

    if auth_response is None or auth_response.user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
        )

    user = auth_response.user

    if supabase_admin is None:
        raise HTTPException(
            status_code=500,
            detail="Service role client is not configured",
        )

    response = supabase_admin.table("profiles").select("*").eq("id", user.id).limit(1).execute()

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    profile = cast(dict[str, Any], response.data[0])

    return CurrentUser(
        id=str(profile["id"]),
        email=str(profile["email"]),
        full_name=str(profile["full_name"]),
        student_id=cast(str | None, profile.get("student_id")),
        gender=cast(str | None, profile.get("gender")),
        role=str(profile.get("role", "student")),
    )


def require_admin(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    return user
