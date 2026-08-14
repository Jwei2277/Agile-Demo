from supabase import create_client

from agile_ci_demo.config import (
    SUPABASE_KEY,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)

if SUPABASE_URL is None or SUPABASE_KEY is None:
    raise RuntimeError("Missing Supabase environment variables")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


supabase_admin = None

if SUPABASE_SERVICE_ROLE_KEY is not None:
    supabase_admin = create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY,
    )
