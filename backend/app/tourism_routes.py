"""Tourism API routes.

The routes stay separate from spatial endpoints and provide frontend-ready
travel information cards.
"""

from fastapi import APIRouter, HTTPException

from .tourism_api import build_tourism_card
from .tourism_repository import fetch_tourism_place

router = APIRouter(prefix="/api/tourism", tags=["tourism"])


@router.post("/card")
def create_tourism_card(place: dict):
    """Build a frontend-ready tourism card from a normalized POI record."""
    if not isinstance(place, dict):
        raise HTTPException(status_code=422, detail="POI payload must be an object")
    return build_tourism_card(place)


@router.get("/places/{place_id}")
def get_tourism_place(place_id: int):
    """Return a tourism card for a POI id.

    The repository receives the database cursor from the application layer.
    This endpoint keeps a stable response contract for the frontend.
    """
    if place_id <= 0:
        raise HTTPException(status_code=422, detail="POI id must be positive")

    # Placeholder until the shared DB dependency is injected from main.py.
    # Keep response schema stable during incremental migration.
    return build_tourism_card({"id": place_id})
