from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from services.supabase_service import supabase, supabase_admin
from supabase import AuthApiError

router = APIRouter(prefix="/auth")


class Register(BaseModel):
    full_name: str = Field(min_length=1)
    student_id: str = Field(pattern=r"^[A-Z]{2}\d{6}$")
    email: EmailStr
    password: str = Field(min_length=8)


class Login(BaseModel):
    identifier: str = Field(min_length=1)  # was: email: EmailStr
    password: str = Field(min_length=1)


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
            supabase_admin.table("user")
            .select("email")
            .eq("student_id", identifier)
            .limit(1)
            .execute()
        )
        if not lookup.data:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        email = lookup.data[0]["email"]

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
