from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from agile_ci_demo.deps import CurrentUser, get_current_user, _extract_bearer_token

from agile_ci_demo.services.supabase_service import (
    supabase,
    supabase_admin,
)
from supabase import AuthApiError

router = APIRouter(prefix="/auth")


class Register(BaseModel):
    full_name: str = Field(min_length=1)
    student_id: str = Field(pattern=r"^[A-Z]{2}\d{6}$")
    email: EmailStr
    gender: str = Field(pattern=r"^(Male|Female)$")
    password: str = Field(min_length=8)


class Login(BaseModel):
    identifier: str = Field(min_length=1)  # was: email: EmailStr
    password: str = Field(min_length=1)


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    access_token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


@router.post("/register", status_code=201)
def register(data: Register):
    if supabase is None:
        raise HTTPException(
            status_code=500,
            detail="Supabase is not configured.",
        )
    try:
        response = supabase.auth.sign_up(
            {
                "email": data.email,
                "password": data.password,
                "options": {
                    "data": {
                        "full_name": data.full_name,
                        "student_id": data.student_id,
                        "gender": data.gender,
                    }
                },
            }
        )
    except AuthApiError as e:
        # This is where a broken `profiles` trigger, a duplicate email,
        # disabled signups, etc. will actually surface - instead of a
        # blank 500 with no explanation.
        raise HTTPException(status_code=e.status or 400, detail=e.message) from e

    if response.user is None:
        raise HTTPException(status_code=400, detail="Could not create account")

    return {
        "message": "Account created. Check your email to verify your address.",
        "user": {
            "id": response.user.id,
            "email": response.user.email,
        },
    }


@router.post("/login")
def login(data: Login):
    if supabase is None:
        raise HTTPException(
            status_code=500,
            detail="Supabase is not configured.",
        )

    identifier = data.identifier.strip()
    is_email = "@" in identifier

    if is_email:
        email = identifier
    else:
        if supabase_admin is None:
            raise HTTPException(
                status_code=501, detail="Login by student ID isn't configured on this server yet."
            )

        lookup = (
            supabase_admin.table("profiles")
            .select("email")
            .eq("student_id", identifier)
            .limit(1)
            .execute()
        )

        if not lookup.data:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_record = lookup.data[0]

        if not isinstance(user_record, dict):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        email_value = user_record.get("email")

        if not isinstance(email_value, str):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        email = email_value

    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": data.password})
    except AuthApiError as e:
        raise HTTPException(status_code=401, detail="Invalid credentials") from e

    if response.user is None or response.session is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "user": {"id": response.user.id, "email": response.user.email},
    }


@router.get("/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    if supabase is None:
        raise HTTPException(
            status_code=500,
            detail="Supabase is not configured.",
        )

    token = _extract_bearer_token(authorization)

    try:
        # Attach this request's token to the client, then revoke it.
        supabase.auth.set_session(token, token)
        supabase.auth.sign_out()
    except Exception:
        # Ignore invalid/expired tokens.
        pass

    return {"message": "Logged out"}

@router.post("/forgot-password")
def forgot_password(data: ForgotPassword):
    if supabase is None:
        raise HTTPException(
            status_code=500,
            detail="Supabase is not configured.",
        )

    try:
        # Always return the same response so attackers can't
        # discover whether an email exists.
        supabase.auth.reset_password_email(data.email)
    except AuthApiError:
        pass

    return {
        "message": "If that email is registered, a reset link has been sent."
    }

@router.post("/reset-password")
def reset_password(data: ResetPassword):
    if supabase is None:
        raise HTTPException(
            status_code=500,
            detail="Supabase is not configured.",
        )

    try:
        # Complete password reset using the access token.
        supabase.auth.set_session(
            data.access_token,
            data.access_token,
        )

        supabase.auth.update_user(
            {"password": data.new_password}
        )

    except AuthApiError as e:
        raise HTTPException(
            status_code=400,
            detail=e.message,
        ) from e

    return {
        "message": "Password updated. You can now log in with your new password."
    }