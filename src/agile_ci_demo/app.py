from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pathlib import Path


app = FastAPI(
    title="Agile CI Demo",
    version="0.1.0"
)


# =========================
# Allow frontend connection
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# HTML Location
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent
HTML_DIR = BASE_DIR / "html"


# =========================
# Serve Login Page
# =========================

@app.get("/")
def login_page():
    return FileResponse(
        HTML_DIR / "login.html"
    )


# =========================
# Health Check
# =========================

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok"
    }


# =========================
# Item Model
# =========================

class Item(BaseModel):
    id: int
    title: str
    done: bool = False



# =========================
# Fake Database
# =========================

_db: Dict[int, Item] = {}



# =========================
# CRUD API
# =========================


@app.post("/items", status_code=201)
def create_item(item: Item) -> Item:

    if item.id in _db:
        raise HTTPException(
            status_code=409,
            detail="Item with that ID already exists"
        )

    _db[item.id] = item

    return item



@app.get("/items/{item_id}")
def get_item(item_id: int) -> Item:

    if item_id not in _db:
        raise HTTPException(
            status_code=404,
            detail="Not found"
        )

    return _db[item_id]



@app.patch("/items/{item_id}/done")
def mark_done(item_id: int) -> Item:

    if item_id not in _db:
        raise HTTPException(
            status_code=404,
            detail="Not found"
        )

    item = _db[item_id]

    item.done = True

    _db[item_id] = item

    return item



# =========================
# Testing Helper
# =========================

def reset_db():
    _db.clear()