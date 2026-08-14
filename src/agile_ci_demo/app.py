from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel


from agile_ci_demo.auth import router as auth_router
from agile_ci_demo.rooms import router as rooms_router
from agile_ci_demo.bookings import router as bookings_router
from agile_ci_demo.maintenance import router as maintenance_router
from agile_ci_demo.admin import router as admin_router
from agile_ci_demo.profile import router as profile_router
from agile_ci_demo.waitlist import router as waitlist_router
from agile_ci_demo.visitor import router as visitor_router
from agile_ci_demo.payments import router as payments_router
from agile_ci_demo.documents import router as documents_router

app = FastAPI(title="Agile CI Demo", version="0.1.0")


# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# API Router Registration
# ==================================================

app.include_router(auth_router)

app.include_router(rooms_router)

app.include_router(bookings_router)

app.include_router(maintenance_router)

app.include_router(admin_router)

app.include_router(profile_router)

app.include_router(waitlist_router)
app.include_router(visitor_router)
app.include_router(payments_router)
app.include_router(documents_router)


# ==================================================
# Health Check
# ==================================================


@app.get("/health")
def health() -> dict:

    return {"status": "ok"}


# ==================================================
# HTML Files
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent

HTML_DIR = BASE_DIR / "html"


@app.get("/")
def login_page():

    return FileResponse(HTML_DIR / "login.html")


@app.get("/login.html")
def login_page_explicit():

    return FileResponse(HTML_DIR / "login.html")


@app.get("/register.html")
def register_page():

    return FileResponse(HTML_DIR / "register.html")


@app.get("/forgot-password.html")
def forgot_password_page():

    return FileResponse(HTML_DIR / "forgotPassword.html")


@app.get("/reset-password.html")
def reset_password_page():

    return FileResponse(HTML_DIR / "resetPassword.html")


@app.get("/student-browse-hostels.html")
def browse_hostels_page():

    return FileResponse(HTML_DIR / "student-browse-hostels.html")


@app.get("/student-room-details.html")
def room_details_page():

    return FileResponse(HTML_DIR / "student-room-details.html")


@app.get("/student-my-booking.html")
def my_booking_page():

    return FileResponse(HTML_DIR / "student-my-booking.html")


@app.get("/student-home.html")
def student_home_page():

    return FileResponse(HTML_DIR / "student-home.html")


@app.get("/student-profile.html")
def student_profile_page():

    return FileResponse(HTML_DIR / "student-profile.html")


@app.get("/student-maintenance.html")
def student_maintenance_page():

    return FileResponse(HTML_DIR / "student-maintenance.html")


@app.get("/student-visitors.html")
def student_visitors_page():

    return FileResponse(HTML_DIR / "student-visitors.html")


@app.get("/student-documents.html")
def student_documents_page():

    return FileResponse(HTML_DIR / "student-documents.html")


@app.get("/student-booking-history.html")
def student_booking_history_page():

    return FileResponse(HTML_DIR / "student-booking-history.html")


@app.get("/admin-dashboard.html")
def admin_dashboard_page():

    return FileResponse(HTML_DIR / "admin-dashboard.html")


@app.get("/admin-bookings.html")
def admin_bookings_page():

    return FileResponse(HTML_DIR / "admin-bookings.html")


@app.get("/admin-maintenance.html")
def admin_maintenance_page():

    return FileResponse(HTML_DIR / "admin-maintenance.html")


@app.get("/admin-visitors.html")
def admin_visitors_page():

    return FileResponse(HTML_DIR / "admin-visitors.html")


@app.get("/admin-documents.html")
def admin_documents_page():

    return FileResponse(HTML_DIR / "admin-documents.html")


@app.get("/admin-checkinout.html")
def admin_checkinout_page():

    return FileResponse(HTML_DIR / "admin-checkinout.html")


@app.get("/admin-reports.html")
def admin_reports_page():

    return FileResponse(HTML_DIR / "admin-reports.html")


@app.get("/admin-transfers.html")
def admin_transfers_page():

    return FileResponse(HTML_DIR / "admin-transfers.html")


@app.get("/admin-rooms.html")
def admin_rooms_page():

    return FileResponse(HTML_DIR / "admin-rooms.html")


@app.get("/admin-dashboard-pending.html")
def admin_dashboard_pending_page():

    return FileResponse(HTML_DIR / "admin-dashboard.html")


@app.get("/admin-dashboard-clear.html")
def admin_dashboard_clear_page():

    return FileResponse(HTML_DIR / "admin-dashboard.html")


# ==================================================
# Test CRUD API
# ==================================================


class Item(BaseModel):

    id: int

    title: str

    done: bool = False


_db: Dict[int, Item] = {}


@app.post("/items", status_code=201)
def create_item(item: Item) -> Item:

    if item.id in _db:

        raise HTTPException(status_code=409, detail="Item with that ID already exists")

    _db[item.id] = item

    return item


@app.get("/items/{item_id}")
def get_item(item_id: int) -> Item:

    if item_id not in _db:

        raise HTTPException(status_code=404, detail="Not found")

    return _db[item_id]


@app.patch("/items/{item_id}/done")
def mark_done(item_id: int) -> Item:

    if item_id not in _db:

        raise HTTPException(status_code=404, detail="Not found")

    item = _db[item_id]

    item.done = True

    _db[item_id] = item

    return item


def reset_db():

    _db.clear()
