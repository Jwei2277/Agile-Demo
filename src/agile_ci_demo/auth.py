import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from agile_ci_demo.deps import CurrentUser, get_current_user, _extract_bearer_token

from agile_ci_demo.services.supabase_service import (
    supabase,
    supabase_admin,
)
from agile_ci_demo.config import APP_BASE_URL
from supabase import AuthApiError

router = APIRouter(prefix="/auth")

TRUSTED_DEVICE_DAYS = 30


class Register(BaseModel):
    full_name: str = Field(min_length=1)
    student_id: str = Field(pattern=r"^[A-Z]{2}\d{6}$")
    email: EmailStr
    gender: str = Field(pattern=r"^(Male|Female)$")
    password: str = Field(min_length=8)


class Login(BaseModel):
    identifier: str = Field(min_length=1)  # was: email: EmailStr
    password: str = Field(min_length=1)
    remember_me: bool = False
    # If the frontend has a trusted-device token from a previous "Remember
    # me" login, send it here to skip OTP again on this device.
    trusted_device_token: str | None = None


class VerifyOtp(BaseModel):
    email: EmailStr
    # Supabase's OTP length is a configurable per-project setting (6-10
    # digits) — don't hardcode 6, or a project set to 8 (like this one)
    # will have every valid code rejected here before it even reaches
    # Supabase's own verification.
    otp: str = Field(pattern=r"^\d{6,10}$")
    remember_me: bool = False


class ResendOtp(BaseModel):
    email: EmailStr


class VerifySignupOtp(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6,10}$")


class ResendSignupOtp(BaseModel):
    email: EmailStr


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    access_token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


@router.post("/register", status_code=201)
def register(data: Register):
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
        raise HTTPException(
            status_code=400,
            detail="Supabase accepted the request but returned no user — please try registering again.",
        )

    return {
        "message": "Account created. Check your email for a verification code.",
        "email": data.email,
        "user": {
            "id": response.user.id,
            "email": response.user.email,
        },
    }


@router.post("/verify-signup-otp")
def verify_signup_otp(data: VerifySignupOtp):
    try:
        response = supabase.auth.verify_otp(
            {"email": data.email, "token": data.otp, "type": "signup"}
        )
    except AuthApiError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired code") from e

    if response.user is None or response.session is None:
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    # Verifying the signup code confirms the email *and* proves the person
    # registering owns it — go ahead and log them straight in rather than
    # making them re-enter their password immediately after.
    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "user": {"id": response.user.id, "email": response.user.email},
    }


@router.post("/resend-signup-otp")
def resend_signup_otp(data: ResendSignupOtp):
    try:
        supabase.auth.resend({"type": "signup", "email": data.email})
    except AuthApiError:
        pass
    return {"message": "A new code has been sent if that account exists and isn't verified yet."}


def _resolve_email(identifier: str) -> str:
    identifier = identifier.strip()
    if "@" in identifier:
        return identifier

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

    email_value = lookup.data[0].get("email") if isinstance(lookup.data[0], dict) else None
    if not isinstance(email_value, str):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return email_value


def _hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _is_trusted_device(student_id: str, token: str | None) -> bool:
    if not token or supabase_admin is None:
        return False

    resp = (
        supabase_admin.table("trusted_devices")
        .select("id, expires_at")
        .eq("student_id", student_id)
        .eq("token_hash", _hash_device_token(token))
        .limit(1)
        .execute()
    )
    if not resp.data:
        return False

    expires_at = datetime.fromisoformat(resp.data[0]["expires_at"].replace("Z", "+00:00"))
    return expires_at > datetime.now(timezone.utc)


def _issue_trusted_device_token(student_id: str) -> str:
    token = secrets.token_urlsafe(32)
    supabase_admin.table("trusted_devices").insert(
        {
            "student_id": student_id,
            "token_hash": _hash_device_token(token),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(days=TRUSTED_DEVICE_DAYS)
            ).isoformat(),
        }
    ).execute()
    return token


@router.post("/login")
def login(data: Login):
    email = _resolve_email(data.identifier)

    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": data.password})
    except AuthApiError as e:
        raise HTTPException(status_code=401, detail="Invalid credentials") from e

    if response.user is None or response.session is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    profile_lookup = (
        supabase_admin.table("profiles")
        .select("role")
        .eq("id", response.user.id)
        .limit(1)
        .execute()
    )
    role = profile_lookup.data[0].get("role", "student") if profile_lookup.data else "student"

    # Admins never get OTP-gated. Students skip OTP only if this device
    # already has a valid trusted-device token from a previous
    # "Remember me" login.
    skip_otp = role == "admin" or _is_trusted_device(response.user.id, data.trusted_device_token)

    if skip_otp:
        return {
            "otp_required": False,
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {"id": response.user.id, "email": response.user.email},
        }

    # Credentials are correct but this device isn't trusted — send a
    # one-time code and withhold the session until it's verified.
    try:
        supabase.auth.sign_in_with_otp({"email": email, "options": {"should_create_user": False}})
    except AuthApiError as e:
        raise HTTPException(status_code=500, detail="Could not send verification code") from e

    return {"otp_required": True, "email": email}


@router.post("/verify-otp")
def verify_otp(data: VerifyOtp):
    try:
        response = supabase.auth.verify_otp(
            {"email": data.email, "token": data.otp, "type": "email"}
        )
    except AuthApiError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired code") from e

    if response.user is None or response.session is None:
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    trusted_device_token = None
    if data.remember_me:
        trusted_device_token = _issue_trusted_device_token(response.user.id)

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "user": {"id": response.user.id, "email": response.user.email},
        # Only returned once — the frontend must store this (localStorage)
        # and send it back as trusted_device_token on future /auth/login
        # calls to skip OTP on this device.
        "trusted_device_token": trusted_device_token,
    }


@router.post("/resend-otp")
def resend_otp(data: ResendOtp):
    try:
        supabase.auth.sign_in_with_otp(
            {"email": data.email, "options": {"should_create_user": False}}
        )
    except AuthApiError:
        pass
    return {"message": "A new code has been sent if that account exists."}


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
    # NOTE: this intentionally reveals whether an email is registered,
    # which is normally avoided (see the removed generic-response version)
    # since it lets someone probe which emails exist in the system. Kept
    # this way because it was explicitly requested — worth knowing if you
    # ever tighten this up later.
    if supabase_admin is None:
        raise HTTPException(
            status_code=501, detail="Server misconfigured: missing service role key"
        )

    lookup = (
        supabase_admin.table("profiles").select("id").eq("email", data.email).limit(1).execute()
    )
    if not lookup.data:
        raise HTTPException(status_code=404, detail="No account is registered with that email.")

    try:
        supabase.auth.reset_password_email(
            data.email, {"redirect_to": f"{APP_BASE_URL}/reset-password.html"}
        )
    except AuthApiError as e:
        raise HTTPException(status_code=400, detail=e.message) from e

    return {"message": "A reset link has been sent to your email."}


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

        supabase.auth.update_user({"password": data.new_password})

    except AuthApiError as e:
        raise HTTPException(
            status_code=400,
            detail=e.message,
        ) from e

    return {"message": "Password updated. You can now log in with your new password."}
