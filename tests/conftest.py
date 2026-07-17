# This file runs before pytest collects any test modules, which is what
# matters here: tests/test_*.py import agile_ci_demo.app -> ... ->
# agile_ci_demo.services.supabase_service, which raises RuntimeError at
# *import time* if SUPABASE_URL / SUPABASE_KEY aren't set. Setting them
# here, at module level (not inside a fixture), guarantees they exist in
# os.environ before any of that import chain runs.
#
# setdefault() is used so this never clobbers real values from a local
# .env file or CI secrets — it only fills the gap when nothing else set
# them.
#
# IMPORTANT: SUPABASE_SERVICE_ROLE_KEY is deliberately NOT set here.
# supabase_service.py only builds `supabase_admin` when that var is
# present; several tests (e.g. test_rooms_without_supabase) rely on
# `supabase_admin` being None by default and every route that uses it
# guarding with `if supabase_admin is None: raise HTTPException(501, ...)`.
# If we set a dummy value here, supabase_admin becomes a real (if fake-
# credentialed) client everywhere, and any test that forgets to
# monkeypatch it will try to make a real network call instead of hitting
# that clean 501 path.
import os

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")
