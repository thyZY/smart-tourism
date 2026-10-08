"""Database-backed tourism card endpoints."""
from fastapi import APIRouter, HTTPException

from .db import get_db_connection
from .tourism_api import build_tourism_card
from .tourism_repository import build_card_from_cursor

router = APIRouter(prefix="/api/tourism", tags=["tourism"])


@router.post("/card")
def create_tourism_card(place: dict):
    """Normalize supplied card data (utility endpoint; not database storage)."""
    return build_tourism_card(place)


@router.get("/places/{place_id}")
def get_tourism_place(place_id: int):
    """Return stored POI and optional tourism attributes, or a proper 404."""
    if place_id <= 0:
        raise HTTPException(status_code=422, detail="POI id must be positive")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            card = build_card_from_cursor(cursor, place_id)
    finally:
        conn.close()
    if card is None:
        raise HTTPException(status_code=404, detail="未找到该景点")
    return card
