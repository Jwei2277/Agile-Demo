from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from agile_ci_demo.services.supabase_service import supabase, supabase_admin
from supabase import AuthApiError


class CurrentUser(BaseModel):
    id: str
    email: str
    full_name: str
    student_id: str | None = None
    gender: str | None = None
    role: str


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """Resolve the bearer token to a profile row. Used on any endpoint
    that needs to know *who* is calling (student booking their own room,
    admin approving a request, etc.)."""

    token = _extract_bearer_token(authorization)

    try:
        auth_response = supabase.auth.get_user(token)
    except AuthApiError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from e

    user = auth_response.user
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    profile_lookup = (
        supabase_admin.table("profiles").select("*").eq("id", user.id).limit(1).execute()
    )
    if not profile_lookup.data:
        raise HTTPException(status_code=404, detail="Profile not found for this account")

    profile = profile_lookup.data[0]

    return CurrentUser(
        id=profile["id"],
        email=profile["email"],
        full_name=profile["full_name"],
        student_id=profile.get("student_id"),
        gender=profile.get("gender"),
        role=profile.get("role", "student"),
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
