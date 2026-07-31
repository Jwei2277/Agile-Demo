import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# The publicly reachable base URL of this app (no trailing slash), used to
# build links inside emails (e.g. the "reset password" link). Defaults to
# localhost for local dev — set this in .env once you deploy somewhere else,
# e.g. APP_BASE_URL=https://your-app.example.com
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
