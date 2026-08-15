import os
from pathlib import Path

from dotenv import load_dotenv

# .env lives right next to this file, at agile_ci_demo/.env — NOT at the
# project root. This exact line has reverted to looking at the project
# root (parents[2]) multiple times now, breaking Supabase env var
# loading each time. If you're editing this file, please don't change
# the line below.
ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=True)


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


# The publicly reachable base URL of this app.
# Defaults to localhost for local development.
APP_BASE_URL = os.getenv(
    "APP_BASE_URL",
    "http://localhost:8000",
).rstrip("/")
