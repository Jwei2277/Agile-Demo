from typing import Any, cast

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from supabase import AuthApiError

from agile_ci_demo.deps import CurrentUser, _extract_bearer_token, get_current_user
from agile_ci_demo.services.supabase_service import supabase, supabase_admin

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1)
    gender: str | None = Field(default=None, pattern=r"^(Male|Female)$")


class ChangePassword(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


@router.patch("", response_model=CurrentUser)
def update_profile(data: ProfileUpdate, user: CurrentUser = Depends(get_current_user)):
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    supabase_admin.table("profiles").update(updates).eq("id", user.id).execute()

    profile_resp = supabase_admin.table("profiles").select("*").eq("id", user.id).limit(1).execute()
    if not profile_resp.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = cast(dict[str, Any], profile_resp.data[0])
    return CurrentUser(
        id=profile["id"],
        email=profile["email"],
        full_name=profile["full_name"],
        student_id=profile.get("student_id"),
        gender=profile.get("gender"),
        role=profile.get("role", "student"),
    )


@router.post("/change-password")
def change_password(
    data: ChangePassword,
    authorization: str | None = Header(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    token = _extract_bearer_token(authorization)

    # Verify the current password actually belongs to this account before
    # allowing a change — otherwise anyone with a stolen/left-open session
    # (e.g. a shared computer) could lock the real owner out.
    try:
        supabase.auth.sign_in_with_password({"email": user.email, "password": data.old_password})
    except AuthApiError as e:
        raise HTTPException(status_code=401, detail="Current password is incorrect") from e

    try:
        supabase.auth.set_session(token, token)
        supabase.auth.update_user({"password": data.new_password})
    except AuthApiError as e:
        raise HTTPException(status_code=400, detail=e.message) from e

    return {"message": "Password updated."}
