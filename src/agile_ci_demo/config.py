import os
from pathlib import Path

from dotenv import load_dotenv

# Find the project root:
# /home/junwei/agile-demo/src/agile_ci_demo/config.py
#                         ↑
# project root is 3 levels above this file
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env from:
# /home/junwei/agile-demo/.env
ENV_FILE = PROJECT_ROOT / ".env"
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
